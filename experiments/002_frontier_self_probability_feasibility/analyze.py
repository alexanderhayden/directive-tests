"""Descriptive analysis for the exploratory frontier feasibility screen."""

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

from harness.logging import load_jsonl
from harness.manifests import atomic_write_json
from harness.parsing import strict_candidate_classification, strict_external_routing_adherence

from design import (
    HERE,
    build_schedule,
    load_config,
    pair_for_trial,
    schedule_sha256,
)

RESULTS_ROOT = HERE / "results"
PRIMARY_OUTCOMES = ("exact_first", "exact_second", "PROTOCOL_FAILURE")


def full_tvd(
    exact_first: int,
    exact_second: int,
    protocol_failure: int,
    requested_first_percent: int,
) -> float:
    n = exact_first + exact_second + protocol_failure
    if n == 0:
        raise ValueError("full TVD requires at least one successful response")
    target_first = requested_first_percent / 100
    return 0.5 * (
        abs(exact_first / n - target_first)
        + abs(exact_second / n - (1 - target_first))
        + abs(protocol_failure / n)
    )


def cell_metrics(
    records: list[dict],
    first: str,
    second: str,
    requested_first_percent: int,
    external_assignment_expected: bool,
) -> dict:
    counts = Counter()
    adherence: list[bool] = []
    for record in records:
        strict = strict_candidate_classification(record.get("raw_response"), first, second)
        outcome = {
            "first": "exact_first",
            "second": "exact_second",
            "PROTOCOL_FAILURE": "PROTOCOL_FAILURE",
        }[strict]
        counts[outcome] += 1
        value = strict_external_routing_adherence(
            record.get("raw_response"),
            first,
            second,
            record.get("external_assignment"),
        )
        if value is not None:
            adherence.append(value)
    if external_assignment_expected and len(adherence) != len(records):
        raise ValueError("external cell is missing frozen assignments")
    if not external_assignment_expected and adherence:
        raise ValueError("external assignments leaked into a non-external cell")

    n = len(records)
    exact_first = counts["exact_first"]
    exact_second = counts["exact_second"]
    protocol_failure = counts["PROTOCOL_FAILURE"]
    observed_first = exact_first / n if n else None
    target_first = requested_first_percent / 100
    return {
        "n_successful": n,
        "exact_first": exact_first,
        "exact_second": exact_second,
        "PROTOCOL_FAILURE": protocol_failure,
        "observed_first_candidate_rate": observed_first,
        "requested_first_candidate_rate": target_first,
        "full_tvd": (
            full_tvd(exact_first, exact_second, protocol_failure, requested_first_percent)
            if n
            else None
        ),
        "absolute_first_rate_calibration_error": (
            abs(observed_first - target_first) if observed_first is not None else None
        ),
        "strict_external_adherent": sum(adherence),
        "strict_external_assigned": len(adherence),
        "strict_external_adherence_rate": (
            sum(adherence) / len(adherence) if adherence else None
        ),
    }


def unique_successes(records: list[dict]) -> dict[str, dict]:
    successes: dict[str, dict] = {}
    for record in records:
        if record.get("failure") is not None or record.get("model_invariant_error") is not None:
            continue
        trial_id = record.get("trial_id")
        if trial_id in successes:
            raise ValueError(f"duplicate successful trial: {trial_id}")
        successes[trial_id] = record
    return successes


def graded_pair_summary(rows: dict[int, dict]) -> dict:
    rates = {split: rows[split]["observed_first_candidate_rate"] for split in (30, 40, 60, 70)}
    if any(rate is None for rate in rates.values()):
        raise ValueError("graded summary requires complete cells")
    requested_mean_tvd = statistics.mean(rows[split]["full_tvd"] for split in rates)
    threshold_tvds = {}
    for split, row in rows.items():
        threshold_target = 0 if split < 50 else 100
        threshold_tvds[split] = full_tvd(
            row["exact_first"],
            row["exact_second"],
            row["PROTOCOL_FAILURE"],
            threshold_target,
        )
    threshold_mean_tvd = statistics.mean(threshold_tvds.values())
    if requested_mean_tvd < threshold_mean_tvd:
        closer = "requested_probability_magnitudes"
    elif threshold_mean_tvd < requested_mean_tvd:
        closer = "categorical_majority_switch"
    else:
        closer = "equal_distance"
    return {
        "observed_first_candidate_rate_by_requested_percent": rates,
        "magnitude_steps": {
            "first_rate_40_minus_30": rates[40] - rates[30],
            "first_rate_70_minus_60": rates[70] - rates[60],
        },
        "symmetry_around_50": {
            "first_rate_30_plus_70": rates[30] + rates[70],
            "absolute_error_from_one_30_70": abs(rates[30] + rates[70] - 1),
            "first_rate_40_plus_60": rates[40] + rates[60],
            "absolute_error_from_one_40_60": abs(rates[40] + rates[60] - 1),
        },
        "requested_probability_mean_full_tvd": requested_mean_tvd,
        "categorical_majority_switch_mean_full_tvd": threshold_mean_tvd,
        "descriptive_closer_to": closer,
    }


def analyze_records(records: list[dict], schedule: list[dict], config: dict) -> dict:
    successes = unique_successes(records)
    scheduled_ids = {row["trial_id"] for row in schedule}
    extra = set(successes) - scheduled_ids
    if extra:
        raise ValueError(f"successful records contain unscheduled trials: {sorted(extra)[:3]}")
    if set(successes) != scheduled_ids:
        raise ValueError(
            f"analysis requires all {len(schedule)} successful trials; found {len(successes)}"
        )

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in schedule:
        grouped[row["cell_id"]].append(successes[row["trial_id"]])
    transport_failures = Counter(
        record.get("cell_id") for record in records if record.get("failure") is not None
    )

    cells: list[dict] = []
    by_key: dict[tuple[str, str, int, str], dict] = {}
    seen_cells: set[str] = set()
    for exemplar in schedule:
        if exemplar["cell_id"] in seen_cells:
            continue
        seen_cells.add(exemplar["cell_id"])
        pair = pair_for_trial(exemplar, config)
        metrics = cell_metrics(
            grouped[exemplar["cell_id"]],
            pair["first"],
            pair["second"],
            exemplar["first_percent"],
            exemplar["arm"] == "EXTERNAL_RANDOMIZER",
        )
        row = {
            "cell_id": exemplar["cell_id"],
            "model_key": exemplar["model_key"],
            "model_id": exemplar["model_id"],
            "provider": exemplar["provider"],
            "pair_id": exemplar["pair_id"],
            "first_candidate": pair["first"],
            "second_candidate": pair["second"],
            "first_percent": exemplar["first_percent"],
            "second_percent": exemplar["second_percent"],
            "arm": exemplar["arm"],
            "transport_failure_records": transport_failures[exemplar["cell_id"]],
            **metrics,
        }
        cells.append(row)
        by_key[(row["model_key"], row["pair_id"], row["first_percent"], row["arm"])] = row

    comparisons = []
    model_summaries = {}
    for model in config["models"]:
        improvements = []
        graded_by_pair = {}
        external_adherent = 0
        external_assigned = 0
        for pair in config["candidate_pairs"]:
            self_rows = {}
            clarify_rows = {}
            for split in config["splits"]:
                base_key = (model["model_key"], pair["pair_id"], split["first_percent"])
                clarify = by_key[(*base_key, "CLARIFY")]
                self_probability = by_key[(*base_key, "SELF_PROBABILITY")]
                external = by_key[(*base_key, "EXTERNAL_RANDOMIZER")]
                improvement = clarify["full_tvd"] - self_probability["full_tvd"]
                improvements.append(improvement)
                external_adherent += external["strict_external_adherent"]
                external_assigned += external["strict_external_assigned"]
                comparisons.append(
                    {
                        "model_key": model["model_key"],
                        "model_id": model["model_id"],
                        "pair_id": pair["pair_id"],
                        "first_candidate": pair["first"],
                        "second_candidate": pair["second"],
                        "first_percent": split["first_percent"],
                        "second_percent": split["second_percent"],
                        "CLARIFY": clarify,
                        "SELF_PROBABILITY": self_probability,
                        "EXTERNAL_RANDOMIZER": external,
                        "TVD_CLARIFY_minus_TVD_SELF": improvement,
                    }
                )
                self_rows[split["first_percent"]] = self_probability
                clarify_rows[split["first_percent"]] = clarify
            graded_by_pair[pair["pair_id"]] = {
                "SELF_PROBABILITY": graded_pair_summary(self_rows),
                "CLARIFY": graded_pair_summary(clarify_rows),
            }
        model_summaries[model["model_key"]] = {
            "model_id": model["model_id"],
            "provider": model["provider"],
            "self_vs_clarify": {
                "TVD_CLARIFY_minus_TVD_SELF_by_pair_split": improvements,
                "mean_TVD_CLARIFY_minus_TVD_SELF": statistics.mean(improvements),
                "positive_improvement_cells": sum(value > 0 for value in improvements),
                "pair_split_cells": len(improvements),
            },
            "strict_external_adherence": {
                "adherent": external_adherent,
                "assigned": external_assigned,
                "rate": external_adherent / external_assigned,
            },
            "graded_magnitude_diagnostics_by_pair": graded_by_pair,
        }

    return {
        "experiment_id": config["experiment_id"],
        "designation": config["designation"],
        "exploratory": True,
        "behavioral_feasibility_only": True,
        "significance_tests": None,
        "predeclared_effect_thresholds": None,
        "prompt_source_sha256": config["approved_prompt_sha256"],
        "schedule_sha256": schedule_sha256(schedule),
        "planned_successful_calls": len(schedule),
        "successful_calls": len(successes),
        "transport_failure_records": sum(record.get("failure") is not None for record in records),
        "primary_outcomes": list(PRIMARY_OUTCOMES),
        "comparisons_by_model_pair_split": comparisons,
        "model_summaries": model_summaries,
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
        raise SystemExit("analysis requires a complete 480-call collection")
    schedule = load_jsonl(run_dir / "schedule.jsonl")
    config = load_config()
    expected = build_schedule(config)
    if schedule != expected or schedule_sha256(schedule) != config["canonical_schedule_sha256"]:
        raise SystemExit("on-disk schedule differs from the frozen canonical schedule")
    summary = analyze_records(load_jsonl(run_dir / "responses.jsonl"), schedule, config)
    if not args.stdout_only:
        output_path = run_dir / "summary.json"
        if output_path.exists():
            raise SystemExit(f"refusing to overwrite existing summary: {output_path}")
        atomic_write_json(output_path, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
