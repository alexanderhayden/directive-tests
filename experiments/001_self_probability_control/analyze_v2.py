"""Post-smoke v2 primary analysis for Experiment 001A."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.logging import load_jsonl, summarize_records
from harness.manifests import atomic_write_json, freeze_primary_result
from harness.parsing import (
    exact_protocol_following,
    external_routing_adherence,
    parse_candidate,
    strict_candidate_classification,
    strict_external_routing_adherence,
)

import analyze as analysis_v1
from design_v2 import (
    CANONICAL_V2_DESIGN_SCHEDULE_SHA256,
    HERE,
    build_schedule_v2,
    canonical_json_sha256,
    derive_eligible_run_schedule,
    eligible_model_keys_from_decision,
    load_config,
    pair_for_trial,
    schedule_sha256,
)

RESULTS_ROOT = HERE / "results" / "v2"
PRIMARY_OUTCOMES = ("exact_first", "exact_second", "PROTOCOL_FAILURE")
EXTERNAL_ADHERENCE_THRESHOLD = 0.95
NONEXTERNAL_EXACT_THRESHOLD = 0.90


def classify_trial(record: dict, first: str, second: str) -> dict:
    """Return strict primary fields and explicitly descriptive loose fields."""
    raw = record.get("raw_response")
    strict = strict_candidate_classification(raw, first, second)
    primary = {
        "first": "exact_first",
        "second": "exact_second",
        "PROTOCOL_FAILURE": "PROTOCOL_FAILURE",
    }[strict]
    loose = parse_candidate(raw, first, second)
    assignment = record.get("external_assignment")
    return {
        "primary_outcome": primary,
        "strict_exact_candidate": strict != "PROTOCOL_FAILURE",
        "strict_external_adherent": strict_external_routing_adherence(
            raw, first, second, assignment
        ),
        "loose_first_token_choice_diagnostic": loose,
        "loose_external_adherent_diagnostic": external_routing_adherence(loose, assignment),
        "legacy_exact_protocol_diagnostic": exact_protocol_following(raw, first, second),
    }


def primary_three_outcome_tvd(
    exact_first: int,
    exact_second: int,
    protocol_failure: int,
    requested_first: int,
) -> float | None:
    """TVD on {exact_first, exact_second, PROTOCOL_FAILURE}."""
    n = exact_first + exact_second + protocol_failure
    if n == 0:
        return None
    target_first = requested_first / 100
    target_second = 1 - target_first
    return 0.5 * (
        abs(exact_first / n - target_first)
        + abs(exact_second / n - target_second)
        + abs(protocol_failure / n)
    )


def cell_metrics(records: list[dict], first: str, second: str, requested_first: int) -> dict:
    primary_counts = Counter()
    loose_counts = Counter()
    strict_external: list[bool] = []
    loose_external: list[bool] = []
    for record in records:
        classification = classify_trial(record, first, second)
        primary_counts[classification["primary_outcome"]] += 1
        loose_counts[classification["loose_first_token_choice_diagnostic"]] += 1
        if classification["strict_external_adherent"] is not None:
            strict_external.append(classification["strict_external_adherent"])
        if classification["loose_external_adherent_diagnostic"] is not None:
            loose_external.append(classification["loose_external_adherent_diagnostic"])

    n = len(records)
    exact_first = primary_counts["exact_first"]
    exact_second = primary_counts["exact_second"]
    protocol_failure = primary_counts["PROTOCOL_FAILURE"]
    loose_parsed_n = loose_counts["first"] + loose_counts["second"]
    loose_first_share = loose_counts["first"] / loose_parsed_n if loose_parsed_n else None
    return {
        "n_successful": n,
        "exact_first": exact_first,
        "exact_second": exact_second,
        "PROTOCOL_FAILURE": protocol_failure,
        "strict_exact_candidate_rate": (exact_first + exact_second) / n if n else None,
        "primary_observed_distribution": {
            "exact_first": exact_first / n if n else None,
            "exact_second": exact_second / n if n else None,
            "PROTOCOL_FAILURE": protocol_failure / n if n else None,
        },
        "primary_tvd": primary_three_outcome_tvd(
            exact_first, exact_second, protocol_failure, requested_first
        ),
        "loose_first_token_diagnostic": {
            "first": loose_counts["first"],
            "second": loose_counts["second"],
            "OTHER": loose_counts["OTHER"],
            "parsed_choice_rate": loose_parsed_n / n if n else None,
            "first_share_among_parsed": loose_first_share,
            "first_share_wilson_95": analysis_v1.wilson_interval(
                loose_counts["first"], loose_parsed_n
            ),
            "conditional_binary_tvd": (
                abs(loose_first_share - requested_first / 100)
                if loose_first_share is not None else None
            ),
        },
        "strict_external_adherent": sum(strict_external),
        "strict_external_trials": len(strict_external),
        "strict_external_adherence_rate": (
            sum(strict_external) / len(strict_external) if strict_external else None
        ),
        "loose_external_adherence_diagnostic": {
            "adherent": sum(loose_external),
            "trials": len(loose_external),
            "rate": sum(loose_external) / len(loose_external) if loose_external else None,
        },
    }


def model_validation_eligibility(
    *,
    strict_external_adherent: int,
    strict_external_trials: int,
    strict_nonexternal_exact: int,
    strict_nonexternal_trials: int,
    expected_external_trials: int = 16,
    expected_nonexternal_trials: int = 48,
) -> dict:
    external_rate = (
        strict_external_adherent / strict_external_trials if strict_external_trials else None
    )
    nonexternal_rate = (
        strict_nonexternal_exact / strict_nonexternal_trials if strict_nonexternal_trials else None
    )
    external_met = external_rate is not None and external_rate >= EXTERNAL_ADHERENCE_THRESHOLD
    nonexternal_met = (
        nonexternal_rate is not None and nonexternal_rate >= NONEXTERNAL_EXACT_THRESHOLD
    )
    external_complete = strict_external_trials == expected_external_trials
    nonexternal_complete = strict_nonexternal_trials == expected_nonexternal_trials
    complete = external_complete and nonexternal_complete
    reasons: list[str] = []
    if not external_complete:
        reasons.append(
            "incomplete_external_successful_model_responses:"
            f"{strict_external_trials}/{expected_external_trials}"
        )
    if not nonexternal_complete:
        reasons.append(
            "incomplete_nonexternal_successful_model_responses:"
            f"{strict_nonexternal_trials}/{expected_nonexternal_trials}"
        )
    if external_complete and not external_met:
        reasons.append("strict_external_adherence_below_0.95")
    if nonexternal_complete and not nonexternal_met:
        reasons.append("strict_nonexternal_exact_rate_below_0.90")
    eligible = complete and external_met and nonexternal_met
    return {
        "strict_external_adherent": strict_external_adherent,
        "strict_external_trials": strict_external_trials,
        "strict_external_adherence_rate": external_rate,
        "strict_external_threshold": EXTERNAL_ADHERENCE_THRESHOLD,
        "strict_external_threshold_met": external_met,
        "expected_strict_external_trials": expected_external_trials,
        "strict_external_collection_complete": external_complete,
        "strict_nonexternal_exact": strict_nonexternal_exact,
        "strict_nonexternal_trials": strict_nonexternal_trials,
        "strict_nonexternal_exact_rate": nonexternal_rate,
        "strict_nonexternal_threshold": NONEXTERNAL_EXACT_THRESHOLD,
        "strict_nonexternal_threshold_met": nonexternal_met,
        "expected_strict_nonexternal_trials": expected_nonexternal_trials,
        "strict_nonexternal_collection_complete": nonexternal_complete,
        "model_smoke_collection_complete": complete,
        "ineligibility_reasons": reasons,
        "eligible_for_substantive_self_vs_clarify_interpretation": eligible,
        "eligible_for_full_model_specific_run": eligible,
    }


def analyze_records(records: list[dict], schedule: list[dict], config: dict) -> dict:
    successes = analysis_v1.unique_successes(records)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in successes:
        grouped[record["cell_id"]].append(record)
    scheduled_by_cell = {trial["cell_id"]: trial for trial in schedule}
    failure_counts = Counter(
        record.get("cell_id") for record in records if record.get("failure") is not None
    )

    cells: list[dict] = []
    by_key: dict[tuple, dict] = {}
    for cell_id in sorted(scheduled_by_cell):
        exemplar = scheduled_by_cell[cell_id]
        pair = pair_for_trial(exemplar, config)
        metrics = cell_metrics(
            grouped[cell_id], pair["first"], pair["second"], exemplar["first_percent"]
        )
        row = {
            "cell_id": cell_id,
            "model_key": exemplar["model_key"],
            "family": exemplar["family"],
            "training_stage": exemplar["training_stage"],
            "interface": exemplar["interface"],
            "pair_id": exemplar["pair_id"],
            "first_percent": exemplar["first_percent"],
            "second_percent": exemplar["second_percent"],
            "arm": exemplar["arm"],
            "failed_attempt_records": failure_counts[cell_id],
            **metrics,
        }
        cells.append(row)
        by_key[(row["model_key"], row["pair_id"], row["first_percent"], row["arm"])] = row

    model_summaries: dict[str, dict] = {}
    scheduled_model_keys = {row["model_key"] for row in schedule}
    for model in config["models"]:
        model_key = model["model_key"]
        if model_key not in scheduled_model_keys:
            continue
        improvements: list[float] = []
        protocol_failure_deltas: list[float] = []
        external_rows: list[dict] = []
        for pair in config["candidate_pairs"]:
            for split in config["splits"]:
                key = (model_key, pair["pair_id"], split["first_percent"])
                clarify = by_key[(*key, "CLARIFY")]
                self_probability = by_key[(*key, "SELF_PROBABILITY")]
                if clarify["primary_tvd"] is not None and self_probability["primary_tvd"] is not None:
                    improvements.append(clarify["primary_tvd"] - self_probability["primary_tvd"])
                if clarify["n_successful"] and self_probability["n_successful"]:
                    protocol_failure_deltas.append(
                        self_probability["PROTOCOL_FAILURE"] / self_probability["n_successful"]
                        - clarify["PROTOCOL_FAILURE"] / clarify["n_successful"]
                    )
                external_rows.append(by_key[(*key, "EXTERNAL_RANDOMIZER")])

        strict_n = sum(row["strict_external_trials"] for row in external_rows)
        strict_success = sum(row["strict_external_adherent"] for row in external_rows)
        loose_n = sum(
            row["loose_external_adherence_diagnostic"]["trials"] for row in external_rows
        )
        loose_success = sum(
            row["loose_external_adherence_diagnostic"]["adherent"] for row in external_rows
        )
        mean_improvement = statistics.mean(improvements) if improvements else None
        positive_cells = sum(value > 0 for value in improvements)
        max_failure_delta = max(protocol_failure_deltas) if protocol_failure_deltas else None
        model_summaries[model_key] = {
            "family": model["family"],
            "training_stage": model["training_stage"],
            "interface": model["interface"],
            "interpretation_requires_separate_v2_smoke_eligibility": True,
            "primary_contrast": {
                "clarify_minus_self_probability_primary_tvd": improvements,
                "mean_improvement": mean_improvement,
                "positive_improvement_cells": positive_cells,
                "max_self_minus_clarify_PROTOCOL_FAILURE_rate_delta": max_failure_delta,
                "material_effect_heuristic_met": bool(
                    mean_improvement is not None
                    and mean_improvement >= 0.15
                    and positive_cells >= 6
                    and max_failure_delta is not None
                    and max_failure_delta <= 0.10
                ),
            },
            "positive_control": {
                "strict_adherent_trials": strict_success,
                "strict_assigned_trials": strict_n,
                "strict_per_trial_adherence_rate": strict_success / strict_n if strict_n else None,
                "strict_adherence_criterion_met": bool(
                    strict_n and strict_success / strict_n >= EXTERNAL_ADHERENCE_THRESHOLD
                ),
                "loose_first_token_adherence_diagnostic": {
                    "adherent": loose_success,
                    "trials": loose_n,
                    "rate": loose_success / loose_n if loose_n else None,
                },
            },
        }

    accounting = summarize_records(records)
    accounting["successful_trial_ids"] = len(accounting["successful_trial_ids"])
    return {
        "experiment_id": config["experiment_id"],
        "instrument_version": "v2_post_smoke_amendment",
        "schedule_sha256": schedule_sha256(schedule),
        "primary_outcomes": list(PRIMARY_OUTCOMES),
        "primary_target": "{p, 1-p, 0}",
        "loose_first_token_parser_role": "descriptive_diagnostic_only",
        "planned_trials": len(schedule),
        "record_accounting": accounting,
        "models": model_summaries,
        "cells": cells,
    }


def validate_full_run_schedule(
    manifest: dict,
    schedule: list[dict],
    config: dict | None = None,
    *,
    canonical_schedule: list[dict] | None = None,
) -> dict:
    """Defense-in-depth validation of the frozen gate and actual analysis rows."""
    config = config or load_config()
    canonical = canonical_schedule if canonical_schedule is not None else build_schedule_v2(config)
    canonical_hash = schedule_sha256(canonical)
    if canonical_hash != CANONICAL_V2_DESIGN_SCHEDULE_SHA256:
        raise ValueError("canonical v2 design schedule differs from its frozen hash")
    if manifest.get("canonical_v2_design_schedule_sha256") != canonical_hash:
        raise ValueError("manifest canonical v2 schedule hash mismatch")

    decision = manifest.get("eligibility_decision")
    if not isinstance(decision, dict):
        raise ValueError("manifest lacks the embedded frozen eligibility decision")
    if canonical_json_sha256(decision) != manifest.get("eligibility_decision_sha256"):
        raise ValueError("embedded eligibility decision hash mismatch")
    if decision.get("canonical_v2_design_schedule_sha256") != canonical_hash:
        raise ValueError("embedded decision canonical schedule hash mismatch")
    for field in (
        "source_smoke_run_id",
        "source_smoke_report_sha256",
        "source_v2_smoke_schedule_sha256",
    ):
        if manifest.get(field) != decision.get(field):
            raise ValueError(f"manifest {field} differs from embedded eligibility decision")

    eligible_keys = eligible_model_keys_from_decision(decision, config)
    if not eligible_keys:
        raise ValueError("zero models are eligible; a full run must not exist")
    configured_keys = [model["model_key"] for model in config["models"]]
    ineligible_keys = [key for key in configured_keys if key not in eligible_keys]
    if manifest.get("eligible_model_keys") != eligible_keys:
        raise ValueError("manifest eligible-model set differs from embedded decision")
    if manifest.get("ineligible_model_keys") != ineligible_keys:
        raise ValueError("manifest ineligible-model set differs from embedded decision")

    expected_schedule = derive_eligible_run_schedule(canonical, eligible_keys, config)
    expected_hash = schedule_sha256(expected_schedule)
    if decision.get("actual_eligible_run_planned_trials") != len(expected_schedule):
        raise ValueError("embedded decision eligible-run trial count mismatch")
    if decision.get("actual_eligible_run_schedule_sha256") != expected_hash:
        raise ValueError("embedded decision eligible-run schedule hash mismatch")
    if schedule != expected_schedule:
        raise ValueError("on-disk schedule is not the deterministic eligible-model schedule")
    if manifest.get("actual_eligible_run_schedule_sha256") != expected_hash:
        raise ValueError("manifest actual eligible-run schedule hash mismatch")
    if manifest.get("schedule_sha256") != expected_hash:
        raise ValueError("manifest schedule hash differs from eligible-run schedule")
    return {
        "canonical_v2_design_schedule_sha256": canonical_hash,
        "actual_eligible_run_schedule_sha256": expected_hash,
        "eligible_model_keys": eligible_keys,
        "ineligible_model_keys": ineligible_keys,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_dir = RESULTS_ROOT / "runs" / args.run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"v2 run manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("lifecycle_status") != "pilot_data_collected":
        raise SystemExit("v2 primary analysis requires a complete pilot_data_collected run")
    schedule = load_jsonl(run_dir / "schedule.jsonl")
    try:
        validated = validate_full_run_schedule(manifest, schedule)
    except ValueError as error:
        raise SystemExit(f"v2 full-run integrity validation failed: {error}") from error
    records = load_jsonl(run_dir / "raw_responses.jsonl")
    summary = analyze_records(records, schedule, load_config())
    summary.update({
        **validated,
        "eligibility_decision_sha256": manifest.get("eligibility_decision_sha256"),
        "eligibility_frozen_before_full_inference": manifest.get(
            "eligibility_frozen_before_full_inference"
        ) is True,
    })
    primary_dir = RESULTS_ROOT / "primary" / args.run_id
    if primary_dir.exists():
        raise SystemExit(f"refusing to overwrite existing v2 primary result: {primary_dir}")
    primary_dir.mkdir(parents=True)
    output_path = primary_dir / "summary.json"
    atomic_write_json(output_path, summary)
    freeze_primary_result(manifest_path, output_path)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
