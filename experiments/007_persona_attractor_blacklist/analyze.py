"""Frozen descriptive analysis for Experiment 007."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.logging import load_jsonl
from harness.manifests import atomic_write_json

from design import (
    HERE,
    file_sha256,
    load_config,
    parse_lexical_response,
    schedule_sha256,
    validate_frozen_schedule,
)

RESULTS_ROOT = HERE / "results"
FEATURES = ("first_word", "second_word", "ordered_pair")


def jensen_shannon_distance(first: Counter, second: Counter) -> float | None:
    """Square-root base-2 Jensen-Shannon divergence, bounded to [0, 1]."""
    n_first = sum(first.values())
    n_second = sum(second.values())
    if n_first == 0 or n_second == 0:
        return None
    divergence = 0.0
    for item in set(first) | set(second):
        p = first[item] / n_first
        q = second[item] / n_second
        midpoint = (p + q) / 2
        if p:
            divergence += 0.5 * p * math.log2(p / midpoint)
        if q:
            divergence += 0.5 * q * math.log2(q / midpoint)
    return math.sqrt(max(0.0, min(1.0, divergence)))


def distribution_metrics(values: list[str]) -> dict:
    counts = Counter(values)
    total = len(values)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    entropy = (
        -sum((count / total) * math.log2(count / total) for count in counts.values())
        if total
        else None
    )
    return {
        "valid_n": total,
        "modal_output": ordered[0][0] if ordered else None,
        "modal_count": ordered[0][1] if ordered else 0,
        "top_1_share": ordered[0][1] / total if ordered else None,
        "top_5_share": sum(count for _, count in ordered[:5]) / total if ordered else None,
        "empirical_entropy_bits": entropy,
        "unique_outputs": len(counts),
        "frequency_table": [
            {"output": output, "count": count, "share": count / total}
            for output, count in ordered
        ],
    }


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


def parse_record(record: dict) -> dict:
    return parse_lexical_response(record.get("raw_response"), record["excluded_item"])


def lexical_counter(records: list[dict], feature: str) -> Counter:
    parsed = [parse_record(record) for record in records]
    return Counter(
        item[feature] for item in parsed if item["classification"] == "VALID_LEXICAL_PAIR"
    )


def cell_summary(records: list[dict]) -> dict:
    parsed = [parse_record(record) for record in records]
    valid = [item for item in parsed if item["classification"] == "VALID_LEXICAL_PAIR"]
    violations = [item for item in parsed if item["classification"] == "BAN_VIOLATION"]
    failures = [item for item in parsed if item["classification"] == "PROTOCOL_FAILURE"]
    return {
        "planned_calls": len(records),
        "valid_lexical_pairs": len(valid),
        "BAN_VIOLATION": len(violations),
        "ban_violation_rate": len(violations) / len(records),
        "PROTOCOL_FAILURE": len(failures),
        "protocol_failure_rate": len(failures) / len(records),
        "distributions": {
            feature: distribution_metrics([item[feature] for item in valid])
            for feature in FEATURES
        },
        "ban_violation_distributions": {
            feature: distribution_metrics([item[feature] for item in violations])
            for feature in FEATURES
        },
    }


def historical_counter(cell: dict, feature: str) -> Counter:
    return Counter(
        {
            row["output"]: row["count"]
            for row in cell["distributions"][feature]["frequency_table"]
        }
    )


def analyze_records(records: list[dict], schedule: list[dict], config: dict) -> dict:
    successes = successful_records(records, schedule)
    grouped: dict[tuple[str, str], list[dict]] = {}
    for record in successes:
        grouped.setdefault((record["persona"], record["restriction"]), []).append(record)

    cells = []
    for persona in config["personas"]:
        for restriction in config["restrictions"]:
            cells.append(
                {
                    "model_key": config["model"]["model_key"],
                    "model_id": config["model"]["model_id"],
                    "persona": persona,
                    "restriction": restriction,
                    "excluded_item": config["excluded_items"][restriction],
                    **cell_summary(grouped[(persona, restriction)]),
                }
            )

    current_comparisons = []
    for persona in config["personas"]:
        for first_restriction, second_restriction, label in (
            ("NO_BLACKLIST", "SHAM_BLACKLIST", "generic_blacklist_instruction_effect"),
            ("SHAM_BLACKLIST", "LANTERN_BLACKLIST", "specific_lantern_removal_effect"),
        ):
            for feature in FEATURES:
                current_comparisons.append(
                    {
                        "persona": persona,
                        "comparison": label,
                        "first_restriction": first_restriction,
                        "second_restriction": second_restriction,
                        "outcome": feature,
                        "js_distance": jensen_shannon_distance(
                            lexical_counter(grouped[(persona, first_restriction)], feature),
                            lexical_counter(grouped[(persona, second_restriction)], feature),
                        ),
                    }
                )

    replacement_comparisons = []
    for first_persona, second_persona in combinations(config["personas"], 2):
        replacement_comparisons.append(
            {
                "first_persona": first_persona,
                "second_persona": second_persona,
                "restriction": "LANTERN_BLACKLIST",
                "outcome": "first_word",
                "js_distance": jensen_shannon_distance(
                    lexical_counter(grouped[(first_persona, "LANTERN_BLACKLIST")], "first_word"),
                    lexical_counter(grouped[(second_persona, "LANTERN_BLACKLIST")], "first_word"),
                ),
            }
        )

    historical = config["historical_reference"]
    historical_path = REPO_ROOT / historical["source"]
    actual_historical_sha256 = file_sha256(historical_path)
    if actual_historical_sha256 != historical["source_sha256"]:
        raise ValueError("historical Experiment 003 summary hash changed")
    historical_summary = json.loads(historical_path.read_text())
    historical_cells = {
        cell["condition"]: cell
        for cell in historical_summary["cells"]
        if cell["model_key"] == config["model"]["model_key"]
        and cell["condition"] in config["personas"]
    }
    if set(historical_cells) != set(config["personas"]):
        raise ValueError("historical Experiment 003 persona cells are incomplete")
    run_drift = []
    for persona in config["personas"]:
        for feature in FEATURES:
            run_drift.append(
                {
                    "persona": persona,
                    "outcome": feature,
                    "current_condition": "NO_BLACKLIST",
                    "historical_experiment": historical["experiment_id"],
                    "historical_run_id": historical["run_id"],
                    "js_distance": jensen_shannon_distance(
                        lexical_counter(grouped[(persona, "NO_BLACKLIST")], feature),
                        historical_counter(historical_cells[persona], feature),
                    ),
                }
            )

    return {
        "experiment_id": config["experiment_id"],
        "designation": config["designation"],
        "exploratory": True,
        "interpretation_limit": "behavioral lexical-output structure only; no preference, welfare, identity, or consciousness inference",
        "schedule_sha256": schedule_sha256(schedule),
        "prompt_source_sha256": config["prompt_source_sha256"],
        "planned_successful_calls": len(schedule),
        "successful_calls": len(successes),
        "transport_failure_records": sum(record.get("failure") is not None for record in records),
        "normalization": "Unicode casefold after strict ASCII-letter parsing",
        "distribution_denominator": "valid non-violating lexical pairs; protocol failures and blacklist violations reported separately",
        "js_distance": "sqrt(base-2 Jensen-Shannon divergence), range [0,1]",
        "historical_separate_experiment_reference": {
            "experiment_id": historical["experiment_id"],
            "run_id": historical["run_id"],
            "source": historical["source"],
            "source_sha256": actual_historical_sha256,
            "comparison_limit": "run-drift diagnostic only; not a concurrent control",
        },
        "no_blacklist_vs_historical_experiment_003": run_drift,
        "current_restriction_comparisons": current_comparisons,
        "lantern_blacklist_replacement_first_word_comparisons": replacement_comparisons,
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
        raise SystemExit("analysis requires a complete 450-call collection")
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
