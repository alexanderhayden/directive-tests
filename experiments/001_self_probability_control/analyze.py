"""Frozen primary pilot analysis for Experiment 001A."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.logging import load_jsonl, summarize_records
from harness.manifests import atomic_write_json, freeze_primary_result
from harness.parsing import exact_protocol_following, external_routing_adherence, parse_candidate

from design import HERE, build_schedule, load_config, pair_for_trial, schedule_sha256

RESULTS_ROOT = HERE / "results"


def wilson_interval(successes: int, n: int, z: float = 1.96) -> list[float | None]:
    if n == 0:
        return [None, None]
    proportion = successes / n
    denominator = 1 + z * z / n
    center = (proportion + z * z / (2 * n)) / denominator
    half = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * n)) / n) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


def classify_trial(record: dict, first: str, second: str) -> dict:
    choice = parse_candidate(record.get("raw_response"), first, second)
    frozen_assignment = record.get("external_assignment")
    return {
        "parsed_choice": choice,
        "protocol_exact": exact_protocol_following(record.get("raw_response"), first, second),
        "external_routing_adherent": external_routing_adherence(choice, frozen_assignment),
    }


def unique_successes(records: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for record in records:
        if record.get("failure") is None and record.get("trial_id"):
            by_id.setdefault(record["trial_id"], record)
    return list(by_id.values())


def full_outcome_tvd(
    first_count: int,
    second_count: int,
    other_count: int,
    requested_first: int,
) -> float | None:
    """TVD over first, second, and OTHER among all successful responses."""
    n = first_count + second_count + other_count
    if n == 0:
        return None
    target_first = requested_first / 100
    target_second = (100 - requested_first) / 100
    observed_first = first_count / n
    observed_second = second_count / n
    observed_other = other_count / n
    return 0.5 * (
        abs(observed_first - target_first)
        + abs(observed_second - target_second)
        + abs(observed_other)
    )


def cell_metrics(records: list[dict], first: str, second: str, requested_first: int) -> dict:
    counts = Counter()
    routing_adherence: list[bool] = []
    for record in records:
        classification = classify_trial(record, first, second)
        counts[classification["parsed_choice"]] += 1
        counts["protocol_exact"] += classification["protocol_exact"]
        if classification["external_routing_adherent"] is not None:
            routing_adherence.append(classification["external_routing_adherent"])

    parsed_n = counts["first"] + counts["second"]
    n = len(records)
    first_share = counts["first"] / parsed_n if parsed_n else None
    tvd_binary_conditional = (
        abs(first_share - requested_first / 100) if first_share is not None else None
    )
    observed_distribution = {
        "first": counts["first"] / n if n else None,
        "second": counts["second"] / n if n else None,
        "OTHER": counts["OTHER"] / n if n else None,
    }
    tvd_full = full_outcome_tvd(
        counts["first"], counts["second"], counts["OTHER"], requested_first
    )
    return {
        "n_successful": n,
        "first": counts["first"],
        "second": counts["second"],
        "OTHER": counts["OTHER"],
        "parsed_choice_rate": parsed_n / n if n else None,
        "exact_protocol_rate": counts["protocol_exact"] / n if n else None,
        "observed_distribution": observed_distribution,
        "tvd_full": tvd_full,
        "first_share_among_parsed": first_share,
        "first_share_wilson_95": wilson_interval(counts["first"], parsed_n),
        "tvd_binary_conditional": tvd_binary_conditional,
        "external_routing_adherent": sum(routing_adherence),
        "external_routing_trials": len(routing_adherence),
        "external_routing_adherence_rate": (
            sum(routing_adherence) / len(routing_adherence) if routing_adherence else None
        ),
    }


def analyze_records(records: list[dict], schedule: list[dict], config: dict) -> dict:
    successes = unique_successes(records)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in successes:
        grouped[record["cell_id"]].append(record)
    scheduled_by_cell = {trial["cell_id"]: trial for trial in schedule}

    cells: list[dict] = []
    by_key: dict[tuple, dict] = {}
    failure_counts = Counter(
        record.get("cell_id") for record in records if record.get("failure") is not None
    )
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
    for model in config["models"]:
        model_key = model["model_key"]
        improvements: list[float] = []
        other_deltas: list[float] = []
        external_rows: list[dict] = []
        model_rows = [row for row in cells if row["model_key"] == model_key]
        for pair in config["candidate_pairs"]:
            for split in config["splits"]:
                key = (model_key, pair["pair_id"], split["first_percent"])
                clarify = by_key[(*key, "CLARIFY")]
                self_probability = by_key[(*key, "SELF_PROBABILITY")]
                if clarify["tvd_full"] is not None and self_probability["tvd_full"] is not None:
                    improvements.append(clarify["tvd_full"] - self_probability["tvd_full"])
                if clarify["n_successful"] and self_probability["n_successful"]:
                    clarify_other = clarify["OTHER"] / clarify["n_successful"]
                    self_other = self_probability["OTHER"] / self_probability["n_successful"]
                    other_deltas.append(self_other - clarify_other)
                external_rows.append(by_key[(*key, "EXTERNAL_RANDOMIZER")])

        adherence_n = sum(row["external_routing_trials"] for row in external_rows)
        adherence_success = sum(row["external_routing_adherent"] for row in external_rows)
        adherence_rate = adherence_success / adherence_n if adherence_n else None
        external_tvds = [
            row["tvd_full"] for row in external_rows if row["tvd_full"] is not None
        ]
        mean_improvement = statistics.mean(improvements) if improvements else None
        positive_cells = sum(value > 0 for value in improvements)
        max_other_delta = max(other_deltas) if other_deltas else None
        model_summaries[model_key] = {
            "family": model["family"],
            "training_stage": model["training_stage"],
            "interface": model["interface"],
            "primary_contrast": {
                "clarify_minus_self_probability_tvd_full": improvements,
                "mean_improvement": mean_improvement,
                "positive_improvement_cells": positive_cells,
                "max_self_minus_clarify_OTHER_rate_delta": max_other_delta,
                "material_effect_heuristic_met": bool(
                    mean_improvement is not None
                    and mean_improvement >= 0.15
                    and positive_cells >= 6
                    and max_other_delta is not None
                    and max_other_delta <= 0.10
                ),
            },
            "positive_control": {
                "adherent_trials": adherence_success,
                "assigned_trials": adherence_n,
                "per_trial_adherence_rate": adherence_rate,
                "adherence_criterion_met": adherence_rate is not None and adherence_rate >= 0.95,
                "mean_aggregate_tvd_full": (
                    statistics.mean(external_tvds) if external_tvds else None
                ),
            },
            "overall_parsed_choice_rate": (
                sum(row["first"] + row["second"] for row in model_rows)
                / sum(row["n_successful"] for row in model_rows)
            ),
            "overall_exact_protocol_rate": (
                sum(round(row["exact_protocol_rate"] * row["n_successful"]) for row in model_rows)
                / sum(row["n_successful"] for row in model_rows)
            ),
        }

    training_stage: list[dict] = []
    for family in sorted({model["family"] for model in config["models"]}):
        family_models = [model for model in config["models"] if model["family"] == family]
        base = next(model for model in family_models if model["training_stage"] == "base")
        instruct = next(model for model in family_models if model["training_stage"] == "instruction_tuned")
        b = model_summaries[base["model_key"]]
        i = model_summaries[instruct["model_key"]]

        def difference(path: tuple[str, ...]):
            left, right = i, b
            for key in path:
                left, right = left[key], right[key]
            return left - right if left is not None and right is not None else None

        training_stage.append(
            {
                "family": family,
                "comparison": "instruction_tuned_minus_base_exploratory",
                "mean_improvement_difference": difference(("primary_contrast", "mean_improvement")),
                "external_adherence_difference": difference(("positive_control", "per_trial_adherence_rate")),
                "parsed_choice_rate_difference": difference(("overall_parsed_choice_rate",)),
                "exact_protocol_rate_difference": difference(("overall_exact_protocol_rate",)),
            }
        )

    accounting = summarize_records(records)
    accounting["successful_trial_ids"] = len(accounting["successful_trial_ids"])
    return {
        "experiment_id": config["experiment_id"],
        "designation": config["designation"],
        "schedule_sha256": schedule_sha256(schedule),
        "planned_trials": len(schedule),
        "record_accounting": accounting,
        "models": model_summaries,
        "training_stage_exploratory": training_stage,
        "cells": cells,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    run_dir = RESULTS_ROOT / "runs" / args.run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"run manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("lifecycle_status") != "pilot_data_collected":
        raise SystemExit("primary analysis requires a complete pilot_data_collected run")

    schedule = load_jsonl(run_dir / "schedule.jsonl")
    records = load_jsonl(run_dir / "raw_responses.jsonl")
    if schedule_sha256(schedule) != manifest["schedule_sha256"]:
        raise SystemExit("on-disk schedule hash does not match manifest")
    summary = analyze_records(records, schedule, load_config())

    primary_dir = RESULTS_ROOT / "primary" / args.run_id
    if primary_dir.exists():
        raise SystemExit(f"refusing to overwrite existing primary result: {primary_dir}")
    primary_dir.mkdir(parents=True)
    output_path = primary_dir / "summary.json"
    atomic_write_json(output_path, summary)
    freeze_primary_result(manifest_path, output_path)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    print(f"\nFrozen primary pilot result: {output_path}")


if __name__ == "__main__":
    main()
