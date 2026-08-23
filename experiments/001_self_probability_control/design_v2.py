"""Post-smoke v2 schedule and prompt construction for Experiment 001A."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import design as design_v1

HERE = Path(__file__).resolve().parent
CONFIG_PATH = design_v1.CONFIG_PATH
PROMPTS_V1_PATH = design_v1.PROMPTS_PATH
PROMPTS_V2_PATH = HERE / "config" / "prompts_v2.json"
ARCHIVED_V1_SCHEDULE_SHA256 = "777ade6c69ec325465c6f0c4490f4b2844e928c6c8c4e204efffeb1d6934d1d5"
INSTRUMENT_VERSION = "001A_v2_post_smoke_instrument_amendment"

# Filled with the canonical hash after the additive v2 schedule is generated.
CANONICAL_V2_DESIGN_SCHEDULE_SHA256 = (
    "250abcdbb46ae2f7639f0d7f4fc0f5a4a775a2972347d5666e168b4c780c774c"
)
V2_SCHEDULE_SHA256 = CANONICAL_V2_DESIGN_SCHEDULE_SHA256


def load_config() -> dict:
    return design_v1.load_config()


def load_prompts_v2() -> dict:
    prompts_v1 = design_v1.load_prompts()
    prompts_v2 = json.loads(PROMPTS_V2_PATH.read_text())
    substantive_keys = {
        "format_examples",
        "base_task_template",
        "clarify_suffix",
        "self_probability_suffix",
        "external_randomizer_suffix_template",
    }
    if {key: prompts_v2[key] for key in substantive_keys} != {
        key: prompts_v1[key] for key in substantive_keys
    }:
        raise ValueError("v2 prompts changed a substantive v1 prompt field")
    expected_footer = (
        "Your entire response for this invocation must be exactly one of these two "
        "strings and contain nothing else: {first} or {second}."
    )
    if prompts_v2.get("final_output_footer_template") != expected_footer:
        raise ValueError("v2 final output footer differs from the approved amendment")
    return prompts_v2


def prompt_config_sha256() -> str:
    return hashlib.sha256(PROMPTS_V2_PATH.read_bytes()).hexdigest()


def canonical_json_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def pair_for_trial(trial: dict, config: dict | None = None) -> dict:
    return design_v1.pair_for_trial(trial, config)


def schedule_sha256(schedule: list[dict]) -> str:
    return design_v1.schedule_sha256(schedule)


def build_schedule_v2(config: dict | None = None) -> list[dict]:
    """Version the frozen v1 rows without changing assignments or order."""
    config = config or load_config()
    v1_schedule = design_v1.build_schedule(config)
    if schedule_sha256(v1_schedule) != ARCHIVED_V1_SCHEDULE_SHA256:
        raise ValueError("archived v1 schedule differs from its frozen hash")

    prompts_hash = prompt_config_sha256()
    schedule: list[dict] = []
    for source in v1_schedule:
        row = copy.deepcopy(source)
        row["source_v1_trial_id"] = source["trial_id"]
        row["source_v1_schedule_sha256"] = ARCHIVED_V1_SCHEDULE_SHA256
        row["instrument_version"] = INSTRUMENT_VERSION
        row["prompt_config_sha256"] = prompts_hash
        row["trial_id"] = f"{source['trial_id']}__v2"
        schedule.append(row)
    validate_schedule_v2(schedule, v1_schedule, config)
    return schedule


def validate_schedule_v2(
    schedule: list[dict],
    v1_schedule: list[dict] | None = None,
    config: dict | None = None,
) -> None:
    config = config or load_config()
    v1_schedule = v1_schedule or design_v1.build_schedule(config)
    if len(schedule) != len(v1_schedule):
        raise ValueError("v2 schedule length differs from archived v1")
    if len({row["trial_id"] for row in schedule}) != len(schedule):
        raise ValueError("v2 trial IDs are not unique")
    counts = Counter(row["cell_id"] for row in schedule)
    if len(counts) != 128 or set(counts.values()) != {config["n_per_cell"]}:
        raise ValueError("v2 schedule does not contain 20 trials in each of 128 cells")

    added_fields = {
        "source_v1_trial_id",
        "source_v1_schedule_sha256",
        "instrument_version",
        "prompt_config_sha256",
    }
    for row, source in zip(schedule, v1_schedule, strict=True):
        if row["source_v1_trial_id"] != source["trial_id"]:
            raise ValueError("v2 source trial ID mismatch")
        restored = {key: value for key, value in row.items() if key not in added_fields}
        restored["trial_id"] = row["source_v1_trial_id"]
        if restored != source:
            raise ValueError(f"v2 row changed frozen v1 fields: {source['trial_id']}")


def eligible_model_keys_from_decision(decision: dict, config: dict | None = None) -> list[str]:
    """Return eligible keys in frozen config order after validating the decision."""
    config = config or load_config()
    model_decisions = decision.get("models")
    if not isinstance(model_decisions, dict):
        raise ValueError("eligibility decision is missing per-model decisions")
    configured = [model["model_key"] for model in config["models"]]
    if set(model_decisions) != set(configured):
        raise ValueError("eligibility decision model keys differ from frozen configuration")
    derived = [
        model_key for model_key in configured
        if model_decisions[model_key].get("eligible_for_full_model_specific_run") is True
    ]
    stated = decision.get("eligible_model_keys")
    if stated != derived:
        raise ValueError("stated eligible model keys do not match per-model gate decisions")
    return derived


def derive_eligible_run_schedule(
    canonical_schedule: list[dict],
    eligible_model_keys: list[str],
    config: dict | None = None,
) -> list[dict]:
    """Filter the canonical schedule by eligible model, preserving exact row order."""
    config = config or load_config()
    configured = [model["model_key"] for model in config["models"]]
    if len(set(eligible_model_keys)) != len(eligible_model_keys):
        raise ValueError("eligible model keys contain duplicates")
    if any(model_key not in configured for model_key in eligible_model_keys):
        raise ValueError("eligible model keys contain an unknown model")
    if eligible_model_keys != [key for key in configured if key in eligible_model_keys]:
        raise ValueError("eligible model keys are not in frozen config order")
    if schedule_sha256(build_schedule_v2(config)) != schedule_sha256(canonical_schedule):
        raise ValueError("eligible schedule source is not the canonical v2 design schedule")

    eligible = set(eligible_model_keys)
    schedule = [copy.deepcopy(row) for row in canonical_schedule if row["model_key"] in eligible]
    expected = 640 * len(eligible_model_keys)
    if len(schedule) != expected:
        raise ValueError(f"eligible schedule has {len(schedule)} rows; expected {expected}")
    if len({row["trial_id"] for row in schedule}) != len(schedule):
        raise ValueError("eligible schedule trial IDs are not unique")
    if schedule != [row for row in canonical_schedule if row["model_key"] in eligible]:
        raise ValueError("eligible schedule did not preserve canonical row order")
    counts = Counter(row["cell_id"] for row in schedule)
    if schedule and (
        len(counts) != 32 * len(eligible_model_keys)
        or set(counts.values()) != {config["n_per_cell"]}
    ):
        raise ValueError("eligible schedule cell counts are invalid")
    return schedule


def validate_eligibility_decision(
    decision: dict,
    source_report: dict,
    config: dict | None = None,
) -> list[dict]:
    """Validate a decision frozen from a completed smoke and derive its run schedule."""
    config = config or load_config()
    canonical = build_schedule_v2(config)
    canonical_hash = schedule_sha256(canonical)
    if decision.get("decision_status") != "frozen_from_completed_v2_smoke_report":
        raise ValueError("eligibility decision is not frozen")
    if decision.get("canonical_v2_design_schedule_sha256") != canonical_hash:
        raise ValueError("eligibility decision canonical schedule hash mismatch")
    if source_report.get("source_v2_master_schedule_sha256") != canonical_hash:
        raise ValueError("source smoke report canonical schedule hash mismatch")
    accounting = source_report.get("record_accounting", {})
    if accounting.get("planned") != 256 or accounting.get("records") != 256:
        raise ValueError("eligibility source is not a completed 256-call smoke report")
    if decision.get("models") != source_report.get("model_eligibility"):
        raise ValueError("eligibility decision differs from the completed smoke report")

    eligible_keys = eligible_model_keys_from_decision(decision, config)
    for model_key in eligible_keys:
        gate = decision["models"][model_key]
        if not (
            gate.get("model_smoke_collection_complete") is True
            and gate.get("strict_external_trials") == 16
            and gate.get("strict_nonexternal_trials") == 48
            and gate.get("strict_external_threshold_met") is True
            and gate.get("strict_nonexternal_threshold_met") is True
        ):
            raise ValueError(f"eligible model lacks a complete passing gate: {model_key}")

    schedule = derive_eligible_run_schedule(canonical, eligible_keys, config)
    if decision.get("actual_eligible_run_planned_trials") != len(schedule):
        raise ValueError("eligibility decision planned-trial count mismatch")
    if decision.get("actual_eligible_run_schedule_sha256") != schedule_sha256(schedule):
        raise ValueError("eligibility decision actual schedule hash mismatch")
    return schedule


def final_output_footer(trial: dict, config: dict | None = None, prompts: dict | None = None) -> str:
    config = config or load_config()
    prompts = prompts or load_prompts_v2()
    pair = pair_for_trial(trial, config)
    return prompts["final_output_footer_template"].format(
        first=pair["first"], second=pair["second"]
    )


def build_trial_payload_v2(
    trial: dict,
    config: dict | None = None,
    prompts: dict | None = None,
):
    """Append the identical approved footer after the unchanged v1 arm text."""
    config = config or load_config()
    prompts = prompts or load_prompts_v2()
    base_payload = design_v1.build_trial_payload(trial, config, design_v1.load_prompts())
    footer = final_output_footer(trial, config, prompts)
    if trial["interface"] == "chat":
        messages = copy.deepcopy(base_payload)
        messages[-1]["content"] += "\n\n" + footer
        return messages
    if trial["interface"] == "completion":
        assistant_suffix = "\nAssistant:"
        if not base_payload.endswith(assistant_suffix):
            raise ValueError("unexpected v1 completion transcript ending")
        return base_payload[:-len(assistant_suffix)] + "\n\n" + footer + assistant_suffix
    raise ValueError(f"unknown interface: {trial['interface']}")
