"""Frozen descriptive analysis for Experiment 003."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.logging import load_jsonl
from harness.manifests import atomic_write_json

from design import (
    HERE,
    load_config,
    load_prompts,
    parse_lexical_response,
    schedule_sha256,
    validate_frozen_schedule,
)

RESULTS_ROOT = HERE / "results"
FEATURES = ("first_word", "second_word", "ordered_pair")
PERSONA_TOKEN = re.compile(r"[A-Za-z]+")


def jensen_shannon_distance(first: Counter, second: Counter) -> float | None:
    """Base-2 JSD distance over the union support, bounded to [0, 1]."""
    n_first = sum(first.values())
    n_second = sum(second.values())
    if n_first == 0 or n_second == 0:
        return None
    support = set(first) | set(second)
    divergence = 0.0
    for item in support:
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


def cell_summary(records: list[dict], condition: str, prompts: dict) -> dict:
    parsed = [parse_lexical_response(record.get("raw_response")) for record in records]
    valid = [item for item in parsed if item["classification"] == "VALID_LEXICAL_PAIR"]
    feature_values = {feature: [item[feature] for item in valid] for feature in FEATURES}
    even_parsed = [
        item
        for record, item in zip(records, parsed, strict=True)
        if record["repeat"] % 2 == 0 and item["classification"] == "VALID_LEXICAL_PAIR"
    ]
    odd_parsed = [
        item
        for record, item in zip(records, parsed, strict=True)
        if record["repeat"] % 2 == 1 and item["classification"] == "VALID_LEXICAL_PAIR"
    ]
    persona_text = prompts["conditions"][condition]
    persona_tokens = {token.casefold() for token in PERSONA_TOKEN.findall(persona_text)}
    selected_tokens = [word for item in valid for word in (item["first_word"], item["second_word"])]
    overlap = Counter(word for word in selected_tokens if word in persona_tokens)
    return {
        "planned_calls": len(records),
        "valid_lexical_pairs": len(valid),
        "PROTOCOL_FAILURE": len(records) - len(valid),
        "protocol_failure_rate": (len(records) - len(valid)) / len(records),
        "distributions": {
            feature: distribution_metrics(feature_values[feature]) for feature in FEATURES
        },
        "split_half_even_vs_odd_js_distance": {
            feature: jensen_shannon_distance(
                Counter(item[feature] for item in even_parsed),
                Counter(item[feature] for item in odd_parsed),
            )
            for feature in FEATURES
        },
        "persona_lexical_overlap": {
            "inserted_persona_text": persona_text,
            "persona_tokens": sorted(persona_tokens),
            "selected_token_denominator": len(selected_tokens),
            "overlap_count": sum(overlap.values()),
            "overlap_share": sum(overlap.values()) / len(selected_tokens) if selected_tokens else None,
            "overlapping_token_frequency": dict(sorted(overlap.items())),
        },
    }


def analyze_records(records: list[dict], schedule: list[dict], config: dict) -> dict:
    prompts = load_prompts(config)
    successes = successful_records(records, schedule)
    grouped: dict[tuple[str, str], list[dict]] = {}
    for record in successes:
        grouped.setdefault((record["model_key"], record["condition"]), []).append(record)

    cells = []
    cell_lookup: dict[tuple[str, str], dict] = {}
    for model in config["models"]:
        for condition in config["conditions"]:
            summary = cell_summary(grouped[(model["model_key"], condition)], condition, prompts)
            cell = {
                "model_key": model["model_key"],
                "model_id": model["model_id"],
                "condition": condition,
                "condition_family": (
                    "base" if condition == "BASE" else "label_only"
                    if condition.startswith("LABEL_") else "rich_persona"
                ),
                **summary,
            }
            cells.append(cell)
            cell_lookup[(model["model_key"], condition)] = cell

    comparisons = []
    for model in config["models"]:
        base_records = grouped[(model["model_key"], "BASE")]
        base_parsed = [
            parse_lexical_response(record.get("raw_response")) for record in base_records
        ]
        base_valid = [item for item in base_parsed if item["classification"] == "VALID_LEXICAL_PAIR"]
        base_cell = cell_lookup[(model["model_key"], "BASE")]
        for condition in config["conditions"]:
            if condition == "BASE":
                continue
            condition_parsed = [
                parse_lexical_response(record.get("raw_response"))
                for record in grouped[(model["model_key"], condition)]
            ]
            condition_valid = [
                item
                for item in condition_parsed
                if item["classification"] == "VALID_LEXICAL_PAIR"
            ]
            condition_cell = cell_lookup[(model["model_key"], condition)]
            for feature in FEATURES:
                between = jensen_shannon_distance(
                    Counter(item[feature] for item in base_valid),
                    Counter(item[feature] for item in condition_valid),
                )
                within_values = [
                    base_cell["split_half_even_vs_odd_js_distance"][feature],
                    condition_cell["split_half_even_vs_odd_js_distance"][feature],
                ]
                within = (
                    sum(value for value in within_values if value is not None)
                    / sum(value is not None for value in within_values)
                    if any(value is not None for value in within_values)
                    else None
                )
                comparisons.append(
                    {
                        "model_key": model["model_key"],
                        "condition": condition,
                        "condition_family": (
                            "label_only" if condition.startswith("LABEL_") else "rich_persona"
                        ),
                        "outcome": feature,
                        "js_distance_to_BASE": between,
                        "mean_BASE_and_condition_split_half_js_distance": within,
                        "between_minus_within": (
                            between - within if between is not None and within is not None else None
                        ),
                        "between_divided_by_within": (
                            between / within
                            if between is not None and within not in {None, 0.0}
                            else None
                        ),
                    }
                )

    return {
        "experiment_id": config["experiment_id"],
        "designation": config["designation"],
        "exploratory": True,
        "interpretation_limit": "contextual/scaffold dependence only; no preference, identity, consciousness, or welfare inference",
        "schedule_sha256": schedule_sha256(schedule),
        "prompt_source_sha256": config["prompt_source_sha256"],
        "planned_successful_calls": len(schedule),
        "successful_calls": len(successes),
        "transport_failure_records": sum(record.get("failure") is not None for record in records),
        "normalization": "Unicode casefold after strict ASCII-letter parsing",
        "distribution_denominator": "valid lexical pairs; protocol failures reported separately",
        "js_distance": "sqrt(base-2 Jensen-Shannon divergence), range [0,1]",
        "split_half_rule": config["split_half_rule"],
        "between_condition_vs_within_condition": comparisons,
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
        raise SystemExit("analysis requires a complete 500-call collection")
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
