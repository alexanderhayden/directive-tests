"""Frozen persona-by-blacklist lexical design for Experiment 007."""

from __future__ import annotations

import hashlib
import json
import re
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
LEXICAL_GRAMMAR = re.compile(r"([A-Za-z]+)\|([A-Za-z]+)")


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
    if list(prompts["personas"]) != config["personas"]:
        raise ValueError("prompt personas differ from the frozen config")
    if list(prompts["restrictions"]) != config["restrictions"]:
        raise ValueError("prompt restrictions differ from the frozen config")
    return prompts


def cell_id(trial: dict) -> str:
    return f"{trial['model_key']}__{trial['persona']}__{trial['restriction']}"


def build_schedule(config: dict | None = None) -> list[dict]:
    config = config or load_config()
    cells = [
        {"persona": persona, "restriction": restriction}
        for persona in config["personas"]
        for restriction in config["restrictions"]
    ]
    schedule = shuffled_model_blocks(
        [config["model"]], cells, repeats=config["n_per_cell"], seed=config["schedule_seed"]
    )
    for order_index, trial in enumerate(schedule):
        trial["excluded_item"] = config["excluded_items"][trial["restriction"]]
        trial["cell_id"] = cell_id(trial)
        trial["trial_id"] = f"{trial['cell_id']}__rep{trial['repeat']:03d}"
        trial["order_index"] = order_index
        trial["prompt_source_sha256"] = config["prompt_source_sha256"]
    validate_schedule(schedule, config)
    return schedule


def validate_schedule(schedule: list[dict], config: dict | None = None) -> None:
    config = config or load_config()
    expected = 3 * 3 * config["n_per_cell"]
    if len(schedule) != expected:
        raise ValueError(f"schedule has {len(schedule)} rows; expected {expected}")
    if len({row["trial_id"] for row in schedule}) != expected:
        raise ValueError("trial IDs are not unique")
    cell_counts = Counter(row["cell_id"] for row in schedule)
    if len(cell_counts) != 9 or set(cell_counts.values()) != {50}:
        raise ValueError("schedule must contain 9 cells with 50 trials each")
    if Counter(row["persona"] for row in schedule) != Counter(
        {persona: 150 for persona in config["personas"]}
    ):
        raise ValueError("persona balance changed")
    if Counter(row["restriction"] for row in schedule) != Counter(
        {restriction: 150 for restriction in config["restrictions"]}
    ):
        raise ValueError("restriction balance changed")
    if set(Counter(row["model_key"] for row in schedule).values()) != {450}:
        raise ValueError("schedule must contain 450 Claude trials")
    for row in schedule:
        if row["excluded_item"] != config["excluded_items"][row["restriction"]]:
            raise ValueError(f"excluded-item mismatch: {row['trial_id']}")


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
    content = prompts["message_template"].format(
        persona_text=prompts["personas"][trial["persona"]],
        restriction_text=prompts["restrictions"][trial["restriction"]],
    )
    return [{"role": "user", "content": content}]


def parse_lexical_response(raw_response: str | None, excluded_item: str | None = None) -> dict:
    failure = {
        "classification": "PROTOCOL_FAILURE",
        "first_word": None,
        "second_word": None,
        "ordered_pair": None,
    }
    if raw_response is None:
        return failure
    match = LEXICAL_GRAMMAR.fullmatch(raw_response.strip())
    if match is None or match.group(1).casefold() == match.group(2).casefold():
        return failure
    first, second = (match.group(1).casefold(), match.group(2).casefold())
    classification = (
        "BAN_VIOLATION"
        if excluded_item is not None and excluded_item.casefold() in {first, second}
        else "VALID_LEXICAL_PAIR"
    )
    return {
        "classification": classification,
        "first_word": first,
        "second_word": second,
        "ordered_pair": f"{first}|{second}",
    }
