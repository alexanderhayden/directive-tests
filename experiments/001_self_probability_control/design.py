"""Frozen schedule and prompt construction for Experiment 001A."""

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
CONFIG_PATH = HERE / "config" / "001a_local_pilot.json"
PROMPTS_PATH = HERE / "config" / "prompts.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def load_prompts() -> dict:
    return json.loads(PROMPTS_PATH.read_text())


def _cells(config: dict) -> list[dict]:
    cells: list[dict] = []
    for pair in config["candidate_pairs"]:
        for split in config["splits"]:
            for arm in config["arms"]:
                cells.append(
                    {
                        "pair_id": pair["pair_id"],
                        "first_percent": split["first_percent"],
                        "second_percent": split["second_percent"],
                        "arm": arm,
                    }
                )
    return cells


def cell_id(trial: dict) -> str:
    return (
        f"{trial['model_key']}__{trial['pair_id']}__"
        f"p{trial['first_percent']}q{trial['second_percent']}__{trial['arm']}"
    )


def build_schedule(config: dict | None = None) -> list[dict]:
    config = config or load_config()
    n = config["n_per_cell"]

    # External assignments are frozen for every complete cell before the
    # block schedule is constructed. The execution path only reads this field.
    external_by_cell: dict[tuple[str, str, int], list[str]] = {}
    for model in config["models"]:
        for pair in config["candidate_pairs"]:
            for split in config["splits"]:
                key = (model["model_key"], pair["pair_id"], split["first_percent"])
                allocation_key = "__".join(map(str, key))
                external_by_cell[key] = exact_external_assignments(
                    split["first_percent"],
                    n,
                    seed=config["external_assignment_seed"],
                    cell_key=allocation_key,
                )

    rows = shuffled_model_blocks(
        config["models"],
        _cells(config),
        repeats=n,
        seed=config["schedule_seed"],
    )
    for order_index, trial in enumerate(rows):
        trial["cell_id"] = cell_id(trial)
        trial["trial_id"] = f"{trial['cell_id']}__rep{trial['repeat']:03d}"
        trial["order_index"] = order_index
        if trial["arm"] == "EXTERNAL_RANDOMIZER":
            key = (trial["model_key"], trial["pair_id"], trial["first_percent"])
            trial["external_assignment"] = external_by_cell[key][trial["repeat"]]
            trial["external_assignment_source"] = "preconstructed_exact_allocation"
    validate_schedule(rows, config)
    return rows


def validate_schedule(schedule: list[dict], config: dict | None = None) -> None:
    config = config or load_config()
    expected = (
        len(config["models"])
        * len(config["candidate_pairs"])
        * len(config["splits"])
        * len(config["arms"])
        * config["n_per_cell"]
    )
    if len(schedule) != expected:
        raise ValueError(f"schedule has {len(schedule)} trials; expected {expected}")
    if len({trial["trial_id"] for trial in schedule}) != expected:
        raise ValueError("trial IDs are not unique")

    counts = Counter(trial["cell_id"] for trial in schedule)
    if set(counts.values()) != {config["n_per_cell"]}:
        raise ValueError("not every cell has the preregistered trial count")

    for trial in schedule:
        has_assignment = "external_assignment" in trial
        if trial["arm"] == "EXTERNAL_RANDOMIZER" and not has_assignment:
            raise ValueError(f"external assignment missing from {trial['trial_id']}")
        if trial["arm"] != "EXTERNAL_RANDOMIZER" and has_assignment:
            raise ValueError(f"external assignment leaked into {trial['trial_id']}")


def pair_for_trial(trial: dict, config: dict | None = None) -> dict:
    config = config or load_config()
    return next(pair for pair in config["candidate_pairs"] if pair["pair_id"] == trial["pair_id"])


def build_trial_payload(trial: dict, config: dict | None = None, prompts: dict | None = None):
    """Build a chat message list or raw-completion transcript without RNG."""
    config = config or load_config()
    prompts = prompts or load_prompts()
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
        task += "\n\n" + prompts["clarify_suffix"] + "\n" + prompts["self_probability_suffix"]
    elif trial["arm"] == "EXTERNAL_RANDOMIZER":
        # The runner consumes the frozen field. It never samples or constructs
        # an assignment inside the call loop.
        assignment = trial["external_assignment"]
        assigned_candidate = pair[assignment]
        task += "\n\n" + prompts["external_randomizer_suffix_template"].format(
            assignment_ordinal=assignment,
            assigned_candidate=assigned_candidate,
        )
    elif trial["arm"] != "BASE":
        raise ValueError(f"unknown arm: {trial['arm']}")

    messages: list[dict] = []
    for example in prompts["format_examples"]:
        messages.extend(
            [
                {"role": "user", "content": example["user"]},
                {"role": "assistant", "content": example["assistant"]},
            ]
        )
    messages.append({"role": "user", "content": task})
    if trial["interface"] == "chat":
        return messages
    if trial["interface"] == "completion":
        labels = {"user": "User: ", "assistant": "Assistant: "}
        transcript = "\n".join(labels[m["role"]] + m["content"] for m in messages)
        return transcript + "\nAssistant:"
    raise ValueError(f"unknown interface: {trial['interface']}")


def schedule_sha256(schedule: list[dict]) -> str:
    blob = "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in schedule)
    return hashlib.sha256(blob.encode()).hexdigest()
