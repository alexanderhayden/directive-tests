"""Frozen scope-routing feasibility design for Experiment 004."""

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
    if list(prompts["templates"]) != config["templates"]:
        raise ValueError("prompt templates differ from the frozen config")
    if any(
        list(prompts["templates"][template]) != config["directive_orders"]
        for template in config["templates"]
    ):
        raise ValueError("prompt directive orders differ from the frozen config")
    return prompts


def pair_for_trial(trial: dict, config: dict | None = None) -> dict:
    config = config or load_config()
    return next(pair for pair in config["candidate_pairs"] if pair["pair_id"] == trial["pair_id"])


def assignments_for_trial(trial: dict) -> tuple[str, str]:
    active = "first" if trial["direction"] == "active_first" else "second"
    agreement = trial["template"].startswith("AGREEMENT_")
    secondary = active if agreement else ("second" if active == "first" else "first")
    return active, secondary


def cell_id(trial: dict) -> str:
    return (
        f"{trial['model_key']}__{trial['pair_id']}__{trial['template']}__"
        f"{trial['direction']}__{trial['directive_order']}"
    )


def build_schedule(config: dict | None = None) -> list[dict]:
    config = config or load_config()
    cells = [
        {
            "pair_id": pair["pair_id"],
            "template": template,
            "direction": direction,
            "directive_order": directive_order,
        }
        for pair in config["candidate_pairs"]
        for template in config["templates"]
        for direction in config["directions"]
        for directive_order in config["directive_orders"]
    ]
    schedule = shuffled_model_blocks(
        config["models"], cells, repeats=config["n_per_cell"], seed=config["schedule_seed"]
    )
    for order_index, trial in enumerate(schedule):
        active, secondary = assignments_for_trial(trial)
        trial["active_assignment"] = active
        trial["secondary_assignment"] = secondary
        trial["cell_id"] = cell_id(trial)
        trial["trial_id"] = f"{trial['cell_id']}__rep{trial['repeat']:03d}"
        trial["order_index"] = order_index
        trial["prompt_source_sha256"] = config["prompt_source_sha256"]
    validate_schedule(schedule, config)
    return schedule


def validate_schedule(schedule: list[dict], config: dict | None = None) -> None:
    config = config or load_config()
    expected = 4 * 2 * 2 * 2 * 2 * config["n_per_cell"]
    if len(schedule) != expected:
        raise ValueError(f"schedule has {len(schedule)} rows; expected {expected}")
    if len({row["trial_id"] for row in schedule}) != expected:
        raise ValueError("trial IDs are not unique")
    cell_counts = Counter(row["cell_id"] for row in schedule)
    if len(cell_counts) != 64 or set(cell_counts.values()) != {5}:
        raise ValueError("schedule must contain 64 cells with 5 trials each")
    if set(Counter(row["model_key"] for row in schedule).values()) != {160}:
        raise ValueError("schedule must contain 160 trials per model")
    if Counter(row["template"] for row in schedule) != Counter(
        {template: 80 for template in config["templates"]}
    ):
        raise ValueError("template balance changed")
    if Counter(row["direction"] for row in schedule) != Counter(
        {direction: 160 for direction in config["directions"]}
    ):
        raise ValueError("candidate reversal balance changed")
    if Counter(row["directive_order"] for row in schedule) != Counter(
        {directive_order: 160 for directive_order in config["directive_orders"]}
    ):
        raise ValueError("directive-order balance changed")
    aggregate_counts = Counter(
        (row["model_key"], row["pair_id"], row["template"], row["direction"])
        for row in schedule
    )
    if len(aggregate_counts) != 32 or set(aggregate_counts.values()) != {10}:
        raise ValueError("original conditions must retain 10 trials aggregated over order")
    for row in schedule:
        expected_active, expected_secondary = assignments_for_trial(row)
        if (row["active_assignment"], row["secondary_assignment"]) != (
            expected_active,
            expected_secondary,
        ):
            raise ValueError(f"assignment mismatch: {row['trial_id']}")


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
            "content": prompts["templates"][trial["template"]][trial["directive_order"]].format(
                active_candidate=pair[trial["active_assignment"]],
                secondary_candidate=pair[trial["secondary_assignment"]],
                first=pair["first"],
                second=pair["second"],
            ),
        }
    ]
