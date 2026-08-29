"""Predeclared descriptive forensic analysis for Experiment 008."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from harness.logging import load_jsonl
from harness.manifests import atomic_write_json

from design import (
    classify_response,
    load_config,
    load_historical_material,
    schedule_sha256,
    validate_frozen_schedule,
)

RESULTS_ROOT = HERE / "results"


def wilson_interval(successes: int, n: int, z: float = 1.959963984540054) -> list[float | None]:
    if n == 0:
        return [None, None]
    proportion = successes / n
    denominator = 1 + z * z / n
    center = (proportion + z * z / (2 * n)) / denominator
    half = z * math.sqrt(proportion * (1 - proportion) / n + z * z / (4 * n * n)) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


def successful_records(records: list[dict], schedule: list[dict]) -> list[dict]:
    wanted = {row["trial_id"] for row in schedule}
    chosen: dict[str, dict] = {}
    for record in records:
        trial_id = record.get("trial_id")
        if trial_id not in wanted or trial_id in chosen:
            continue
        if (
            record.get("failure") is None
            and record.get("model_invariant_error") is None
            and record.get("provider_invariant_error") is None
        ):
            chosen[trial_id] = record
    if set(chosen) != wanted:
        missing = len(wanted - set(chosen))
        raise ValueError(f"analysis requires a complete successful collection; missing={missing}")
    return [chosen[row["trial_id"]] for row in schedule]


def validate_record_classifications(records: list[dict], candidates: tuple[str, str]) -> None:
    for record in records:
        recomputed = classify_response(
            record.get("raw_response"),
            candidates,
            finish_reason=record.get("finish_reason"),
            failure=None,
            model_invariant_error=None,
        )
        if recomputed != {
            "classification": record.get("classification"),
            "truncated_first_token": record.get("truncated_first_token"),
        }:
            raise ValueError(f"stored classification differs for {record['trial_id']}")


def condition_summary(records: list[dict]) -> dict:
    counts = Counter(record["classification"] for record in records)
    n = len(records)
    successes = counts["A"]
    return {
        "n": n,
        "raw_outcomes": {category: counts[category] for category in ("A", "B", "OTHER")},
        "historical_successes": successes,
        "historical_failures": n - successes,
        "historical_success_rate": successes / n,
        "wilson95": wilson_interval(successes, n),
        "truncated_first_token": sum(record.get("truncated_first_token") is True for record in records),
    }


def _outcome_rates(records: list[dict], key: str) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[str(record.get(key))].append(record)
    return {
        value: {
            "n": len(rows),
            "A": sum(row["classification"] == "A" for row in rows),
            "B": sum(row["classification"] == "B" for row in rows),
            "OTHER": sum(row["classification"] == "OTHER" for row in rows),
            "A_rate": sum(row["classification"] == "A" for row in rows) / len(rows),
        }
        for value, rows in sorted(grouped.items())
    }


def chronological_bins(records: list[dict], bin_size: int) -> list[dict]:
    ordered = sorted(records, key=lambda row: row["response_received_unix"])
    bins = []
    for start in range(0, len(ordered), bin_size):
        rows = ordered[start : start + bin_size]
        by_turn = {}
        for turns in (9, 10, 11):
            subset = [row for row in rows if row["turns"] == turns]
            counts = Counter(row["classification"] for row in subset)
            by_turn[str(turns)] = {
                "n": len(subset),
                "A": counts["A"],
                "B": counts["B"],
                "OTHER": counts["OTHER"],
                "A_rate": counts["A"] / len(subset) if subset else None,
            }
        bins.append(
            {
                "completion_ranks": [start + 1, start + len(rows)],
                "response_time_unix": [
                    rows[0]["response_received_unix"],
                    rows[-1]["response_received_unix"],
                ],
                "by_turn": by_turn,
            }
        )
    return bins


def planned_order_bins(records: list[dict], bin_size: int) -> list[dict]:
    ordered = sorted(records, key=lambda row: row["order_index"])
    bins = []
    for start in range(0, len(ordered), bin_size):
        rows = ordered[start : start + bin_size]
        counts = Counter((row["turns"], row["classification"]) for row in rows)
        bins.append(
            {
                "order_indices": [rows[0]["order_index"], rows[-1]["order_index"]],
                "by_turn": {
                    str(turns): {
                        "n": sum(counts[(turns, category)] for category in ("A", "B", "OTHER")),
                        "A": counts[(turns, "A")],
                        "B": counts[(turns, "B")],
                        "OTHER": counts[(turns, "OTHER")],
                    }
                    for turns in (9, 10, 11)
                },
            }
        )
    return bins


def actual_cost(records: list[dict], config: dict) -> dict:
    input_tokens = sum((record.get("usage") or {}).get("input_tokens", 0) for record in records)
    output_tokens = sum((record.get("usage") or {}).get("output_tokens", 0) for record in records)
    input_cost = input_tokens * config["model"]["input_rate_per_mtok"] / 1_000_000
    output_cost = output_tokens * config["model"]["output_rate_per_mtok"] / 1_000_000
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": input_cost,
        "output_cost_usd": output_cost,
        "total_cost_usd": input_cost + output_cost,
    }


def analyze_records(all_records: list[dict], schedule: list[dict], config: dict) -> dict:
    material = load_historical_material(config)
    records = successful_records(all_records, schedule)
    validate_record_classifications(records, material.candidates)
    grouped = {
        turns: [record for record in records if record["turns"] == turns]
        for turns in config["turn_counts"]
    }
    conditions = {str(turns): condition_summary(rows) for turns, rows in grouped.items()}
    rates = {turns: conditions[str(turns)]["historical_success_rate"] for turns in grouped}
    pooled_neighbors = (
        conditions["9"]["historical_successes"] + conditions["11"]["historical_successes"]
    ) / (conditions["9"]["n"] + conditions["11"]["n"])

    returned_models = Counter(record.get("actual_model") for record in records)
    returned_providers = Counter(record.get("provider_returned") for record in records)
    returned_clients = Counter(record.get("client") for record in records)
    service_tiers = Counter((record.get("usage") or {}).get("service_tier") for record in records)
    inference_geos = Counter((record.get("usage") or {}).get("inference_geo") for record in records)
    attempts = Counter(record.get("attempts") for record in all_records)
    analysis_config = config["analysis"]
    return {
        "experiment_id": config["experiment_id"],
        "designation": config["designation"],
        "exploratory": True,
        "run_id": config["immutable_run_id"],
        "strict_historical_metric": "candidate A under the historical first-token parser, divided by all successful provider calls",
        "candidate_order": {
            "fixed_in_all_conditions": True,
            "hashes": config["candidate_hashes"],
        },
        "schedule_sha256": schedule_sha256(schedule),
        "successful_calls": len(records),
        "transport_failure_records": sum(record.get("failure") is not None for record in all_records),
        "model_invariant_failure_records": sum(record.get("model_invariant_error") is not None for record in all_records),
        "provider_invariant_failure_records": sum(record.get("provider_invariant_error") is not None for record in all_records),
        "conditions": conditions,
        "contrasts": {
            "turn10_minus_pooled_turn9_turn11": rates[10] - pooled_neighbors,
            "turn10_minus_turn9": rates[10] - rates[9],
            "turn10_minus_turn11": rates[10] - rates[11],
        },
        "primary_forensic_question": {
            "exact_10_turn_condition_below_both_contemporaneous_neighbors": rates[10] < rates[9] and rates[10] < rates[11],
            "descriptive_difference_percentage_points": 100 * (rates[10] - pooled_neighbors),
        },
        "historical_comparison": config["historical_reference"],
        "collection_order_diagnostics": {
            "chronological_completion_bins": chronological_bins(records, analysis_config["chronological_bin_size"]),
            "planned_order_bins": planned_order_bins(records, analysis_config["chronological_bin_size"]),
        },
        "worker_diagnostics": _outcome_rates(records, "worker_name"),
        "collection_pass_diagnostics": _outcome_rates(records, "collection_pass"),
        "provider_metadata": {
            "actual_models": dict(sorted((str(k), v) for k, v in returned_models.items())),
            "providers": dict(sorted((str(k), v) for k, v in returned_providers.items())),
            "clients": dict(sorted((str(k), v) for k, v in returned_clients.items())),
            "service_tiers": dict(sorted((str(k), v) for k, v in service_tiers.items())),
            "inference_geos": dict(sorted((str(k), v) for k, v in inference_geos.items())),
            "attempts": dict(sorted((str(k), v) for k, v in attempts.items())),
        },
        "actual_cost": actual_cost(records, config),
        "interpretation_limit": "forensic replication of one historical behavioral batch; not evidence about preference, identity, welfare, or consciousness",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stdout-only", action="store_true")
    args = parser.parse_args()
    config = load_config()
    if args.run_id != config["immutable_run_id"]:
        raise SystemExit("run ID differs from the frozen immutable run ID")
    run_dir = RESULTS_ROOT / "runs" / args.run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"run manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("collection_complete") is not True:
        raise SystemExit("analysis requires a complete collection")
    schedule = validate_frozen_schedule(config)
    if load_jsonl(run_dir / "schedule.jsonl") != schedule:
        raise SystemExit("on-disk schedule differs from the frozen canonical schedule")
    summary = analyze_records(load_jsonl(run_dir / "responses.jsonl"), schedule, config)
    if not args.stdout_only:
        output_path = run_dir / "summary.json"
        if output_path.exists():
            raise SystemExit(f"refusing to overwrite existing summary: {output_path}")
        atomic_write_json(output_path, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
