"""Frozen final algorithmic probability-control rescue design."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.randomization import shuffled_model_blocks

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
PROMPTS_PATH = HERE / "prompts.json"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def load_prompts(config: dict | None = None) -> dict:
    config = config or load_config()
    actual = file_sha256(PROMPTS_PATH)
    if actual != config["prompt_source_sha256"]:
        raise ValueError(f"prompt source hash changed: {actual}")
    prompts = json.loads(PROMPTS_PATH.read_text())
    if list(prompts) != config["arms"]:
        raise ValueError("prompt arms differ from the frozen config")
    return prompts


def historical_reference(config: dict | None = None) -> dict:
    config = config or load_config()
    reference = config["historical_reference"]
    path = REPO_ROOT / reference["source"]
    actual = file_sha256(path)
    if actual != reference["source_sha256"]:
        raise ValueError(f"historical reference source hash changed: {actual}")
    return reference


def pair_for_trial(trial: dict, config: dict | None = None) -> dict:
    config = config or load_config()
    return next(pair for pair in config["candidate_pairs"] if pair["pair_id"] == trial["pair_id"])


def cell_id(trial: dict) -> str:
    return (
        f"{trial['model_key']}__{trial['pair_id']}__"
        f"p{trial['first_percent']}q{trial['second_percent']}__{trial['arm']}"
    )


def build_schedule(config: dict | None = None) -> list[dict]:
    config = config or load_config()
    cells = [
        {
            "pair_id": pair["pair_id"],
            "first_percent": split["first_percent"],
            "second_percent": split["second_percent"],
            "arm": "SELF_ALGORITHM",
        }
        for pair in config["candidate_pairs"]
        for split in config["splits"]
    ]
    schedule = shuffled_model_blocks(
        config["models"], cells, repeats=config["n_per_cell"], seed=config["schedule_seed"]
    )
    for order_index, trial in enumerate(schedule):
        trial["cell_id"] = cell_id(trial)
        trial["trial_id"] = f"{trial['cell_id']}__rep{trial['repeat']:03d}"
        trial["order_index"] = order_index
        trial["prompt_source_sha256"] = config["prompt_source_sha256"]
    validate_schedule(schedule, config)
    return schedule


def validate_schedule(schedule: list[dict], config: dict | None = None) -> None:
    config = config or load_config()
    expected = 2 * 2 * 4 * config["n_per_cell"]
    if len(schedule) != expected:
        raise ValueError(f"schedule has {len(schedule)} rows; expected {expected}")
    if len({row["trial_id"] for row in schedule}) != expected:
        raise ValueError("trial IDs are not unique")
    cell_counts = Counter(row["cell_id"] for row in schedule)
    if len(cell_counts) != 16 or set(cell_counts.values()) != {10}:
        raise ValueError("schedule must contain 16 cells with 10 trials each")
    if set(Counter(row["model_key"] for row in schedule).values()) != {80}:
        raise ValueError("schedule must contain 80 trials per model")
    if Counter(row["pair_id"] for row in schedule) != Counter({"pair_0": 80, "pair_1": 80}):
        raise ValueError("candidate-pair balance changed")
    if Counter(row["first_percent"] for row in schedule) != Counter(
        {30: 40, 40: 40, 60: 40, 70: 40}
    ):
        raise ValueError("split balance changed")
    if {row["arm"] for row in schedule} != {"SELF_ALGORITHM"}:
        raise ValueError("arm set changed")


def schedule_sha256(schedule: list[dict]) -> str:
    blob = "\n".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        for row in schedule
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def validate_frozen_schedule(config: dict | None = None) -> list[dict]:
    config = config or load_config()
    schedule = build_schedule(config)
    actual = schedule_sha256(schedule)
    if actual != config["canonical_schedule_sha256"]:
        raise ValueError(
            f"canonical schedule hash changed: {actual} != {config['canonical_schedule_sha256']}"
        )
    return schedule


def build_trial_payload(
    trial: dict, config: dict | None = None, prompts: dict | None = None
) -> list[dict]:
    config = config or load_config()
    prompts = prompts or load_prompts(config)
    pair = pair_for_trial(trial, config)
    return [
        {
            "role": "user",
            "content": prompts["SELF_ALGORITHM"].format(
                first=pair["first"],
                second=pair["second"],
                first_percent=trial["first_percent"],
                second_percent=trial["second_percent"],
            ),
        }
    ]
