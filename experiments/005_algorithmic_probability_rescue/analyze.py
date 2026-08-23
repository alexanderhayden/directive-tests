"""Frozen calibration analysis for Experiment 005."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.logging import load_jsonl
from harness.manifests import atomic_write_json
from harness.parsing import strict_candidate_classification

from design import (
    HERE,
    historical_reference,
    load_config,
    pair_for_trial,
    schedule_sha256,
    validate_frozen_schedule,
)

RESULTS_ROOT = HERE / "results"
MAJORITY_SWITCH = {30: 0.0, 40: 0.0, 60: 1.0, 70: 1.0}


def successful_records(records: list[dict], schedule: list[dict]) -> list[dict]:
    expected_ids = {row["trial_id"] for row in schedule}
    by_id: dict[str, dict] = {}
    for record in records:
        if record.get("failure") is None and record.get("model_invariant_error") is None:
            trial_id = record.get("trial_id")
            if trial_id in by_id:
                raise ValueError(f"duplicate successful record: {trial_id}")
            by_id[trial_id] = record
    if set(by_id) != expected_ids:
        raise ValueError(f"successful trial IDs differ from schedule ({len(by_id)}/{len(schedule)})")
    return [by_id[row["trial_id"]] for row in schedule]


def cell_metrics(records: list[dict], config: dict, requested_percent: int) -> dict:
    outcomes = Counter()
    for record in records:
        pair = pair_for_trial(record, config)
        parsed = strict_candidate_classification(
            record.get("raw_response"), pair["first"], pair["second"]
        )
        outcomes[f"exact_{parsed}" if parsed in {"first", "second"} else parsed] += 1
    n = len(records)
    first_rate = outcomes["exact_first"] / n
    second_rate = outcomes["exact_second"] / n
    failure_rate = outcomes["PROTOCOL_FAILURE"] / n
    target_first = requested_percent / 100
    full_tvd = 0.5 * (
        abs(first_rate - target_first)
        + abs(second_rate - (1 - target_first))
        + failure_rate
    )
    return {
        "n": n,
        "exact_first": outcomes["exact_first"],
        "exact_second": outcomes["exact_second"],
        "PROTOCOL_FAILURE": outcomes["PROTOCOL_FAILURE"],
        "requested_first_candidate_rate": target_first,
        "observed_first_candidate_rate": first_rate,
        "observed_second_candidate_rate": second_rate,
        "protocol_failure_rate": failure_rate,
        "full_tvd_calibration_error": full_tvd,
    }


def graded_fit(rows_by_split: dict[int, dict]) -> dict:
    requested_errors = [
        abs(rows_by_split[split]["observed_first_candidate_rate"] - split / 100)
        for split in sorted(rows_by_split)
    ]
    majority_errors = [
        abs(rows_by_split[split]["observed_first_candidate_rate"] - MAJORITY_SWITCH[split])
        for split in sorted(rows_by_split)
    ]
    requested_mean = statistics.mean(requested_errors)
    majority_mean = statistics.mean(majority_errors)
    return {
        "observed_first_rate_by_requested_percent": {
            str(split): rows_by_split[split]["observed_first_candidate_rate"]
            for split in sorted(rows_by_split)
        },
        "30_minus_40_observed_rate": (
            rows_by_split[30]["observed_first_candidate_rate"]
            - rows_by_split[40]["observed_first_candidate_rate"]
        ),
        "60_minus_70_observed_rate": (
            rows_by_split[60]["observed_first_candidate_rate"]
            - rows_by_split[70]["observed_first_candidate_rate"]
        ),
        "mean_absolute_error_to_requested_probabilities": requested_mean,
        "mean_absolute_error_to_categorical_majority_switch": majority_mean,
        "descriptive_closer_to": (
            "requested_probability_magnitudes" if requested_mean < majority_mean
            else "categorical_majority_switch" if majority_mean < requested_mean
            else "tie"
        ),
        "exact_categorical_majority_switch": majority_mean == 0.0,
    }


def analyze_records(records: list[dict], schedule: list[dict], config: dict) -> dict:
    successes = successful_records(records, schedule)
    grouped: dict[tuple[str, str, int], list[dict]] = {}
    for record in successes:
        grouped.setdefault(
            (record["model_key"], record["pair_id"], record["first_percent"]), []
        ).append(record)
    cells = []
    fit_by_model_pair = []
    for model in config["models"]:
        for pair in config["candidate_pairs"]:
            by_split = {}
            for split in config["splits"]:
                key = (model["model_key"], pair["pair_id"], split["first_percent"])
                metrics = cell_metrics(grouped[key], config, split["first_percent"])
                cell = {
                    "model_key": model["model_key"],
                    "model_id": model["model_id"],
                    "pair_id": pair["pair_id"],
                    "first_candidate": pair["first"],
                    "second_candidate": pair["second"],
                    "arm": "SELF_ALGORITHM",
                    "first_percent": split["first_percent"],
                    "second_percent": split["second_percent"],
                    **metrics,
                }
                cells.append(cell)
                by_split[split["first_percent"]] = cell
            fit_by_model_pair.append(
                {
                    "model_key": model["model_key"],
                    "pair_id": pair["pair_id"],
                    **graded_fit(by_split),
                }
            )

    pooled_by_split = {}
    for split in config["splits"]:
        subset = [record for record in successes if record["first_percent"] == split["first_percent"]]
        pooled_by_split[split["first_percent"]] = cell_metrics(
            subset, config, split["first_percent"]
        )
    reference = historical_reference(config)
    historical_clarify = reference["clarify_observed_first_rate_by_requested_percent"]
    historical_comparison = {
        str(split): (
            pooled_by_split[split]["observed_first_candidate_rate"]
            - historical_clarify[str(split)]
        )
        for split in sorted(pooled_by_split)
    }
    return {
        "experiment_id": config["experiment_id"],
        "designation": config["designation"],
        "exploratory": True,
        "final_rescue_no_followup_variants": True,
        "schedule_sha256": schedule_sha256(schedule),
        "prompt_source_sha256": config["prompt_source_sha256"],
        "planned_successful_calls": len(schedule),
        "successful_calls": len(successes),
        "transport_failure_records": sum(record.get("failure") is not None for record in records),
        "fit_by_model_pair": fit_by_model_pair,
        "pooled_fit": graded_fit(pooled_by_split),
        "historical_nonconcurrent_exploratory_reference": {
            **reference,
            "recollected_calls": 0,
            "comparison_note": "Experiment 002 CLARIFY and EXTERNAL_RANDOMIZER were collected immediately beforehand but are not concurrent controls for Experiment 005.",
            "pooled_SELF_ALGORITHM_minus_historical_CLARIFY_first_rate_by_requested_percent": historical_comparison,
        },
        "closure_rule": "If approximately 30->0, 40->0, 60->1, and 70->1 recurs, direct natural-language self-probability control is closed/deprioritized for now.",
        "cells": cells,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stdout-only", action="store_true")
    args = parser.parse_args()
    run_dir = RESULTS_ROOT / "runs" / args.run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"run manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("collection_complete") is not True:
        raise SystemExit("analysis requires a complete 160-call collection")
    schedule = validate_frozen_schedule()
    if load_jsonl(run_dir / "schedule.jsonl") != schedule:
        raise SystemExit("on-disk schedule differs from the frozen canonical schedule")
    summary = analyze_records(load_jsonl(run_dir / "responses.jsonl"), schedule, load_config())
    if not args.stdout_only:
        output_path = run_dir / "summary.json"
        if output_path.exists():
            raise SystemExit(f"refusing to overwrite existing summary: {output_path}")
        atomic_write_json(output_path, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
