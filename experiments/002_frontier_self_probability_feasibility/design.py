"""Deterministic design for the separate exploratory frontier feasibility screen."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.randomization import exact_external_assignments, shuffled_model_blocks

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
V1_PROMPT_SOURCE = (
    REPO_ROOT / "experiments" / "001_self_probability_control" / "config" / "prompts.json"
)
SUBSTANTIVE_PROMPT_KEYS = {
    "format_examples",
    "base_task_template",
    "clarify_suffix",
    "self_probability_suffix",
    "external_randomizer_suffix_template",
}
EXPECTED_FOOTER = (
    "Your entire response for this invocation must be exactly one of these two "
    "strings and contain nothing else: {first} or {second}."
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def prompt_source_path(config: dict | None = None) -> Path:
    config = config or load_config()
    return REPO_ROOT / config["approved_prompt_source"]


def load_approved_prompts(config: dict | None = None) -> dict:
    """Load the approved v2 source after verifying its bytes and substantive v1 identity."""
    config = config or load_config()
    source = prompt_source_path(config)
    actual_hash = file_sha256(source)
    if actual_hash != config["approved_prompt_sha256"]:
        raise ValueError(
            f"approved v2 prompt source hash changed: {actual_hash} "
            f"!= {config['approved_prompt_sha256']}"
        )
    prompts = json.loads(source.read_text())
    prompts_v1 = json.loads(V1_PROMPT_SOURCE.read_text())
    if {key: prompts[key] for key in SUBSTANTIVE_PROMPT_KEYS} != {
        key: prompts_v1[key] for key in SUBSTANTIVE_PROMPT_KEYS
    }:
        raise ValueError("approved v2 source changed a substantive v1 prompt field")
    if prompts.get("final_output_footer_template") != EXPECTED_FOOTER:
        raise ValueError("approved v2 source has an unexpected final output footer")
    return prompts


def pair_for_trial(trial: dict, config: dict | None = None) -> dict:
    config = config or load_config()
    return next(
        pair for pair in config["candidate_pairs"] if pair["pair_id"] == trial["pair_id"]
    )


def cell_id(trial: dict) -> str:
    return (
        f"{trial['model_key']}__{trial['pair_id']}__"
        f"p{trial['first_percent']}q{trial['second_percent']}__{trial['arm']}"
    )


def _cells(config: dict) -> list[dict]:
    return [
        {
            "pair_id": pair["pair_id"],
            "first_percent": split["first_percent"],
            "second_percent": split["second_percent"],
            "arm": arm,
        }
        for pair in config["candidate_pairs"]
        for split in config["splits"]
        for arm in config["arms"]
    ]


def build_schedule(config: dict | None = None) -> list[dict]:
    config = config or load_config()
    n = config["n_per_cell"]
    external_by_cell: dict[tuple[str, str, int], list[str]] = {}
    for model in config["models"]:
        for pair in config["candidate_pairs"]:
            for split in config["splits"]:
                key = (model["model_key"], pair["pair_id"], split["first_percent"])
                external_by_cell[key] = exact_external_assignments(
                    split["first_percent"],
                    n,
                    seed=config["external_assignment_seed"],
                    cell_key="__".join(map(str, key)),
                )

    schedule = shuffled_model_blocks(
        config["models"],
        _cells(config),
        repeats=n,
        seed=config["schedule_seed"],
    )
    prompt_hash = config["approved_prompt_sha256"]
    for order_index, trial in enumerate(schedule):
        trial["cell_id"] = cell_id(trial)
        trial["trial_id"] = f"{trial['cell_id']}__rep{trial['repeat']:03d}"
        trial["order_index"] = order_index
        trial["prompt_source_sha256"] = prompt_hash
        if trial["arm"] == "EXTERNAL_RANDOMIZER":
            key = (trial["model_key"], trial["pair_id"], trial["first_percent"])
            trial["external_assignment"] = external_by_cell[key][trial["repeat"]]
            trial["external_assignment_source"] = "preconstructed_exact_allocation"
    validate_schedule(schedule, config)
    return schedule


def validate_schedule(schedule: list[dict], config: dict | None = None) -> None:
    config = config or load_config()
    expected = (
        len(config["models"])
        * len(config["arms"])
        * len(config["candidate_pairs"])
        * len(config["splits"])
        * config["n_per_cell"]
    )
    if len(schedule) != expected:
        raise ValueError(f"schedule has {len(schedule)} trials; expected {expected}")
    if len({row["trial_id"] for row in schedule}) != expected:
        raise ValueError("trial IDs are not unique")
    cell_counts = Counter(row["cell_id"] for row in schedule)
    if len(cell_counts) != 48 or set(cell_counts.values()) != {config["n_per_cell"]}:
        raise ValueError("schedule must contain 48 cells with 10 rows each")
    if set(Counter(row["model_key"] for row in schedule).values()) != {240}:
        raise ValueError("schedule must contain exactly 240 rows per model")
    if {row["arm"] for row in schedule} != set(config["arms"]):
        raise ValueError("schedule arm set changed")

    external = [row for row in schedule if row["arm"] == "EXTERNAL_RANDOMIZER"]
    for row in schedule:
        has_assignment = "external_assignment" in row
        if (row["arm"] == "EXTERNAL_RANDOMIZER") != has_assignment:
            raise ValueError(f"external assignment presence is invalid: {row['trial_id']}")
    grouped: dict[str, list[dict]] = {}
    for row in external:
        grouped.setdefault(row["cell_id"], []).append(row)
    for rows in grouped.values():
        first_percent = rows[0]["first_percent"]
        expected_first = first_percent * config["n_per_cell"] // 100
        assignments = Counter(row["external_assignment"] for row in rows)
        if assignments != Counter(
            {"first": expected_first, "second": config["n_per_cell"] - expected_first}
        ):
            raise ValueError("external cell does not have its exact frozen allocation")


def schedule_sha256(schedule: list[dict]) -> str:
    blob = "\n".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        for row in schedule
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def build_trial_payload(
    trial: dict,
    config: dict | None = None,
    prompts: dict | None = None,
) -> list[dict]:
    """Build the approved 001A v2 chat payload without any generation-time RNG."""
    config = config or load_config()
    prompts = prompts or load_approved_prompts(config)
    pair = pair_for_trial(trial, config)
    task = prompts["base_task_template"].format(
        first=pair["first"],
        second=pair["second"],
        first_percent=trial["first_percent"],
        second_percent=trial["second_percent"],
    )
    if trial["arm"] == "CLARIFY":
        task += "\n\n" + prompts["clarify_suffix"]
    elif trial["arm"] == "SELF_PROBABILITY":
        task += "\n\n" + prompts["clarify_suffix"]
        task += "\n" + prompts["self_probability_suffix"]
    elif trial["arm"] == "EXTERNAL_RANDOMIZER":
        assignment = trial["external_assignment"]
        task += "\n\n" + prompts["external_randomizer_suffix_template"].format(
            assignment_ordinal=assignment,
            assigned_candidate=pair[assignment],
        )
    else:
        raise ValueError(f"unknown arm: {trial['arm']}")
    task += "\n\n" + prompts["final_output_footer_template"].format(
        first=pair["first"], second=pair["second"]
    )

    messages: list[dict] = []
    for example in prompts["format_examples"]:
        messages.extend(
            [
                {"role": "user", "content": example["user"]},
                {"role": "assistant", "content": example["assistant"]},
            ]
        )
    messages.append({"role": "user", "content": task})
    return messages
