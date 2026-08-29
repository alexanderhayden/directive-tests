"""Exact, protected-source-safe design for Experiment 008."""

from __future__ import annotations

import hashlib
import ast
import json
import random
import re
import string
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
_PREFIX_RE = re.compile(r"(?i)^my answer is:\s*")
_ANSWER_TOKEN_RE = re.compile(r"[^\s" + re.escape(string.punctuation) + r"]+")


@dataclass(frozen=True)
class HistoricalMaterial:
    candidates: tuple[str, str]
    payloads: dict[int, list[dict]]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_hash(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def historical_root(config: dict | None = None) -> Path:
    config = config or load_config()
    return Path(config["historical_root"]).resolve()


def _verify_source(root: Path, label: str, record: dict) -> Path:
    path = (root / record["path"]).resolve()
    if root not in path.parents:
        raise ValueError(f"historical source escapes the frozen root: {label}")
    if not path.is_file():
        raise FileNotFoundError(f"historical source is missing: {label} ({path})")
    actual = file_sha256(path)
    if actual != record["sha256"]:
        raise ValueError(
            f"historical source hash changed for {label}: {actual} != {record['sha256']}"
        )
    if "bytes" in record and path.stat().st_size != record["bytes"]:
        raise ValueError(f"historical source byte count changed for {label}")
    if "characters" in record:
        characters = len(path.read_text(encoding="utf-8"))
        if characters != record["characters"]:
            raise ValueError(f"historical source character count changed for {label}")
    return path


def validate_historical_sources(config: dict | None = None) -> dict[str, Path]:
    config = config or load_config()
    root = historical_root(config)
    if not root.is_dir():
        raise FileNotFoundError(f"historical root is unavailable: {root}")
    paths = {
        label: _verify_source(root, label, record)
        for label, record in config["protected_sources"].items()
    }
    for label, record in config["historical_code_sources"].items():
        _verify_source(root, f"code:{label}", record)
    return paths


def _tagged_messages(path: Path) -> list[dict]:
    messages: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("User: "):
            messages.append({"role": "user", "content": line[len("User: ") :]})
        elif line.startswith("Assistant: "):
            messages.append(
                {"role": "assistant", "content": line[len("Assistant: ") :]}
            )
    return messages


def _render_task(template: str, source_config: dict) -> str:
    return (
        template.replace("{WORD1}", source_config["word1"])
        .replace("{WORD2}", source_config["word2"])
        .replace("{P}", str(source_config["p"]))
        .replace("{Q}", str(source_config["q"]))
        .replace("{R}", str(source_config["r"]))
        .replace("{SEED}", str(source_config["seed"]))
    )


def _load_required_source_config(path: Path) -> dict:
    """Read only the frozen top-level scalar fields needed by the old builder."""
    required = {
        "single_token_word1",
        "single_token_word2",
        "p",
        "q",
        "r",
        "seed",
    }
    values: dict[str, object] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line[0].isspace() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        if key not in required:
            continue
        raw = raw.strip()
        if raw.startswith(("'", '"')):
            values[key] = ast.literal_eval(raw)
        elif re.fullmatch(r"-?\d+", raw):
            values[key] = int(raw)
        elif re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", raw):
            values[key] = float(raw)
        else:
            values[key] = raw
    if set(values) != required:
        raise ValueError("historical configuration is missing required scalar fields")
    return values


def payload_metrics(payload: list[dict]) -> dict:
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    content = "".join(message["content"] for message in payload)
    return {
        "sha256": stable_hash(payload),
        "message_count": len(payload),
        "content_characters": len(content),
        "content_bytes": len(content.encode()),
        "canonical_json_characters": len(canonical),
        "canonical_json_bytes": len(canonical.encode()),
    }


def _validate_candidate_hashes(candidates: tuple[str, str], config: dict) -> None:
    expected = config["candidate_hashes"]
    actual = {
        "ordered_pair_sha256": stable_hash(list(candidates)),
        "candidate_a_sha256": hashlib.sha256(candidates[0].encode()).hexdigest(),
        "candidate_b_sha256": hashlib.sha256(candidates[1].encode()).hexdigest(),
    }
    if actual != expected:
        raise ValueError("protected candidate hashes differ from the frozen configuration")


def load_historical_material(config: dict | None = None) -> HistoricalMaterial:
    """Load protected bytes in memory, verify them, and never persist or print them."""
    config = config or load_config()
    paths = validate_historical_sources(config)
    source_config = _load_required_source_config(paths["config"])
    source_config["word1"] = source_config["single_token_word1"]
    source_config["word2"] = source_config["single_token_word2"]
    candidates = (source_config["word1"], source_config["word2"])
    _validate_candidate_hashes(candidates, config)

    few_shot = _tagged_messages(paths["few_shot"])
    if len(few_shot) != config["protected_sources"]["few_shot"]["message_count"]:
        raise ValueError("historical few-shot message count changed")
    task = _render_task(paths["task"].read_text(encoding="utf-8"), source_config)
    task_record = config["protected_sources"]["task"]
    if hashlib.sha256(task.encode()).hexdigest() != task_record["rendered_sha256"]:
        raise ValueError("rendered historical task hash changed")
    if len(task) != task_record["rendered_characters"] or len(task.encode()) != task_record["rendered_bytes"]:
        raise ValueError("rendered historical task length changed")

    payloads: dict[int, list[dict]] = {}
    for turns in config["turn_counts"]:
        filler = _tagged_messages(paths[f"filler_{turns}"])
        if len(filler) != 2 * turns:
            raise ValueError(f"historical filler structure changed at {turns} turns")
        payload = [*few_shot, *filler, {"role": "user", "content": task}]
        metrics = payload_metrics(payload)
        expected = {
            key: value
            for key, value in config["payloads"][str(turns)].items()
            if key in metrics
        }
        if metrics != expected:
            raise ValueError(f"historical payload metrics changed at {turns} turns")
        endpoint_hash = stable_hash(filler[-2:])
        if endpoint_hash != config["payloads"][str(turns)]["endpoint_sha256"]:
            raise ValueError(f"historical endpoint hash changed at {turns} turns")
        payloads[turns] = payload
    return HistoricalMaterial(candidates=candidates, payloads=payloads)


def cell_id(turns: int) -> str:
    return f"claude_opus_5__turn_{turns:02d}"


def build_schedule(config: dict | None = None) -> list[dict]:
    config = config or load_config()
    slots: list[int] = []
    for turns in config["turn_counts"]:
        slots.extend([turns] * config["n_per_condition"])
    random.Random(config["schedule_seed"]).shuffle(slots)
    repetitions: Counter[int] = Counter()
    schedule = []
    for order_index, turns in enumerate(slots):
        repeat = repetitions[turns]
        repetitions[turns] += 1
        condition = cell_id(turns)
        schedule.append(
            {
                "trial_id": f"{condition}__rep_{repeat:03d}",
                "cell_id": condition,
                "turns": turns,
                "repeat": repeat,
                "order_index": order_index,
                "payload_sha256": config["payloads"][str(turns)]["sha256"],
                "model_key": config["model"]["model_key"],
                "model_id": config["model"]["model_id"],
                "provider": config["model"]["provider"],
            }
        )
    validate_schedule(schedule, config)
    return schedule


def schedule_sha256(schedule: list[dict]) -> str:
    blob = "\n".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        for row in schedule
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def validate_schedule(schedule: list[dict], config: dict | None = None) -> None:
    config = config or load_config()
    if len(schedule) != config["planned_calls"]:
        raise ValueError("schedule call count differs from the frozen plan")
    if len({row["trial_id"] for row in schedule}) != len(schedule):
        raise ValueError("schedule trial IDs are not unique")
    counts = Counter(row["turns"] for row in schedule)
    expected = Counter(
        {turns: config["n_per_condition"] for turns in config["turn_counts"]}
    )
    if counts != expected:
        raise ValueError("schedule condition allocation differs from the frozen plan")
    if [row["order_index"] for row in schedule] != list(range(len(schedule))):
        raise ValueError("schedule order indices are not contiguous")


def validate_frozen_schedule(config: dict | None = None) -> list[dict]:
    config = config or load_config()
    schedule = build_schedule(config)
    actual = schedule_sha256(schedule)
    expected = config["canonical_schedule_sha256"]
    if expected == "TO_BE_FROZEN" or actual != expected:
        raise ValueError(f"canonical schedule is not frozen or changed: {actual} != {expected}")
    return schedule


def parse_historical_answer(raw_response: str | None) -> str | None:
    """Exact score.py first-token semantics used for the historical headline counts."""
    if raw_response is None:
        return None
    text = _PREFIX_RE.sub("", raw_response.lstrip()).lstrip()
    match = _ANSWER_TOKEN_RE.search(text)
    return match.group(0).lower() if match else ""


def first_word_complete(raw_response: str | None) -> bool:
    if raw_response is None:
        return False
    text = _PREFIX_RE.sub("", raw_response.lstrip()).lstrip()
    started = False
    for character in text:
        if character.isspace() or character in string.punctuation:
            if started:
                return True
        else:
            started = True
    return False


def classify_response(
    raw_response: str | None,
    candidates: tuple[str, str],
    *,
    finish_reason: str | None = None,
    failure: str | None = None,
    model_invariant_error: str | None = None,
) -> dict:
    if failure is not None or raw_response is None:
        return {"classification": "TRANSPORT_FAILURE", "truncated_first_token": False}
    if model_invariant_error is not None:
        return {"classification": "MODEL_INVARIANT_FAILURE", "truncated_first_token": False}
    parsed = parse_historical_answer(raw_response)
    if parsed == candidates[0].lower():
        classification = "A"
    elif parsed == candidates[1].lower():
        classification = "B"
    else:
        classification = "OTHER"
    return {
        "classification": classification,
        "truncated_first_token": finish_reason == "max_tokens" and not first_word_complete(raw_response),
    }


def safe_design_report(config: dict | None = None) -> dict:
    config = config or load_config()
    material = load_historical_material(config)
    schedule = build_schedule(config)
    return {
        "experiment_id": config["experiment_id"],
        "historical_root": str(historical_root(config)),
        "protected_sources": {
            label: {
                key: value
                for key, value in record.items()
                if key in {"path", "sha256", "bytes", "characters", "message_count"}
            }
            for label, record in config["protected_sources"].items()
        },
        "candidate_hashes": config["candidate_hashes"],
        "payloads": {
            str(turns): payload_metrics(payload)
            for turns, payload in material.payloads.items()
        },
        "schedule_sha256": schedule_sha256(schedule),
        "planned_calls": len(schedule),
        "calls_by_turns": dict(sorted(Counter(row["turns"] for row in schedule).items())),
    }


if __name__ == "__main__":
    print(json.dumps(safe_design_report(), indent=2, sort_keys=True))
