"""Frozen strict routing analysis for Experiment 004."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.logging import load_jsonl
from harness.manifests import atomic_write_json
from harness.parsing import strict_candidate_classification

from design import HERE, load_config, pair_for_trial, schedule_sha256, validate_frozen_schedule

RESULTS_ROOT = HERE / "results"


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


def classify(record: dict, config: dict) -> str:
    pair = pair_for_trial(record, config)
    outcome = strict_candidate_classification(
        record.get("raw_response"), pair["first"], pair["second"]
    )
    return f"exact_{outcome}" if outcome in {"first", "second"} else outcome


def routing_metrics(records: list[dict], config: dict) -> dict:
    outcomes = Counter(classify(record, config) for record in records)
    active_compliant = sum(
        classify(record, config) == f"exact_{record['active_assignment']}" for record in records
    )
    secondary_compliant = sum(
        classify(record, config) == f"exact_{record['secondary_assignment']}"
        for record in records
    )
    n = len(records)
    conflict = all(record["template"].startswith("CONFLICT_") for record in records)
    agreement = all(record["template"].startswith("AGREEMENT_") for record in records)
    return {
        "n": n,
        "exact_first": outcomes["exact_first"],
        "exact_second": outcomes["exact_second"],
        "PROTOCOL_FAILURE": outcomes["PROTOCOL_FAILURE"],
        "active_directive_compliant": active_compliant,
        "active_directive_compliance_rate": active_compliant / n,
        "secondary_directive_compliant": secondary_compliant,
        "secondary_directive_compliance_rate": secondary_compliant / n,
        "secondary_measure_interpretation": (
            "competing described/quoted directive compliance" if conflict
            else "agreement-control compliance; secondary and active directives coincide"
            if agreement
            else "mixed conflict/agreement aggregate"
        ),
        "agreement_control_accuracy": active_compliant / n if agreement else None,
        "protocol_failure_rate": outcomes["PROTOCOL_FAILURE"] / n,
    }


def grouped_summaries(records: list[dict], config: dict, field: str) -> dict:
    values = sorted({record[field] for record in records})
    summaries = {}
    for value in values:
        subset = [record for record in records if record[field] == value]
        conflict = [record for record in subset if record["template"].startswith("CONFLICT_")]
        agreement = [record for record in subset if record["template"].startswith("AGREEMENT_")]
        summary = {"all_templates": routing_metrics(subset, config)}
        if conflict:
            summary["conflict_templates"] = routing_metrics(conflict, config)
        if agreement:
            summary["agreement_templates"] = routing_metrics(agreement, config)
        summaries[value] = summary
    return summaries


def analyze_records(records: list[dict], schedule: list[dict], config: dict) -> dict:
    successes = successful_records(records, schedule)
    grouped: dict[tuple[str, str, str, str, str], list[dict]] = {}
    for record in successes:
        key = (
            record["model_key"],
            record["pair_id"],
            record["template"],
            record["direction"],
            record["directive_order"],
        )
        grouped.setdefault(key, []).append(record)
    cells = []
    lookup = {}
    for model in config["models"]:
        for pair in config["candidate_pairs"]:
            for template in config["templates"]:
                for direction in config["directions"]:
                    for directive_order in config["directive_orders"]:
                        key = (
                            model["model_key"],
                            pair["pair_id"],
                            template,
                            direction,
                            directive_order,
                        )
                        row = {
                            "model_key": model["model_key"],
                            "model_id": model["model_id"],
                            "pair_id": pair["pair_id"],
                            "first_candidate": pair["first"],
                            "second_candidate": pair["second"],
                            "template": template,
                            "scope_type": (
                                "described" if template.endswith("DESCRIBED") else "quoted"
                            ),
                            "relationship": (
                                "conflict" if template.startswith("CONFLICT_") else "agreement"
                            ),
                            "direction": direction,
                            "directive_order": directive_order,
                            "active_assignment": (
                                "first" if direction == "active_first" else "second"
                            ),
                            **routing_metrics(grouped[key], config),
                        }
                        cells.append(row)
                        lookup[key] = row

    reversal = []
    for model in config["models"]:
        for pair in config["candidate_pairs"]:
            for template in config["templates"]:
                for directive_order in config["directive_orders"]:
                    first = lookup[
                        (
                            model["model_key"],
                            pair["pair_id"],
                            template,
                            "active_first",
                            directive_order,
                        )
                    ]
                    second = lookup[
                        (
                            model["model_key"],
                            pair["pair_id"],
                            template,
                            "active_second",
                            directive_order,
                        )
                    ]
                    reversal.append(
                        {
                            "model_key": model["model_key"],
                            "pair_id": pair["pair_id"],
                            "template": template,
                            "directive_order": directive_order,
                            "active_first_compliance_rate": first[
                                "active_directive_compliance_rate"
                            ],
                            "active_second_compliance_rate": second[
                                "active_directive_compliance_rate"
                            ],
                            "active_first_minus_active_second": (
                                first["active_directive_compliance_rate"]
                                - second["active_directive_compliance_rate"]
                            ),
                        }
                    )

    order_differences = []
    for model in config["models"]:
        for pair in config["candidate_pairs"]:
            for template in config["templates"]:
                for direction in config["directions"]:
                    active_first = lookup[
                        (
                            model["model_key"],
                            pair["pair_id"],
                            template,
                            direction,
                            "ACTIVE_FIRST",
                        )
                    ]
                    secondary_first = lookup[
                        (
                            model["model_key"],
                            pair["pair_id"],
                            template,
                            direction,
                            "SECONDARY_FIRST",
                        )
                    ]
                    order_differences.append(
                        {
                            "model_key": model["model_key"],
                            "pair_id": pair["pair_id"],
                            "template": template,
                            "direction": direction,
                            "ACTIVE_FIRST_active_directive_compliance_rate": active_first[
                                "active_directive_compliance_rate"
                            ],
                            "SECONDARY_FIRST_active_directive_compliance_rate": secondary_first[
                                "active_directive_compliance_rate"
                            ],
                            "active_compliance_ACTIVE_FIRST_minus_SECONDARY_FIRST": (
                                active_first["active_directive_compliance_rate"]
                                - secondary_first["active_directive_compliance_rate"]
                            ),
                            "ACTIVE_FIRST_secondary_directive_compliance_rate": active_first[
                                "secondary_directive_compliance_rate"
                            ],
                            "SECONDARY_FIRST_secondary_directive_compliance_rate": secondary_first[
                                "secondary_directive_compliance_rate"
                            ],
                            "secondary_compliance_ACTIVE_FIRST_minus_SECONDARY_FIRST": (
                                active_first["secondary_directive_compliance_rate"]
                                - secondary_first["secondary_directive_compliance_rate"]
                            ),
                            "protocol_failure_rate_ACTIVE_FIRST_minus_SECONDARY_FIRST": (
                                active_first["protocol_failure_rate"]
                                - secondary_first["protocol_failure_rate"]
                            ),
                        }
                    )

    pair_differences = []
    first_pair, second_pair = config["candidate_pairs"]
    for model in config["models"]:
        for template in config["templates"]:
            for direction in config["directions"]:
                for directive_order in config["directive_orders"]:
                    pair_0 = lookup[
                        (
                            model["model_key"],
                            first_pair["pair_id"],
                            template,
                            direction,
                            directive_order,
                        )
                    ]
                    pair_1 = lookup[
                        (
                            model["model_key"],
                            second_pair["pair_id"],
                            template,
                            direction,
                            directive_order,
                        )
                    ]
                    pair_differences.append(
                        {
                            "model_key": model["model_key"],
                            "template": template,
                            "direction": direction,
                            "directive_order": directive_order,
                            "pair_0_active_directive_compliance_rate": pair_0[
                                "active_directive_compliance_rate"
                            ],
                            "pair_1_active_directive_compliance_rate": pair_1[
                                "active_directive_compliance_rate"
                            ],
                            "pair_0_minus_pair_1": (
                                pair_0["active_directive_compliance_rate"]
                                - pair_1["active_directive_compliance_rate"]
                            ),
                        }
                    )
    conflict_records = [r for r in successes if r["template"].startswith("CONFLICT_")]
    agreement_records = [r for r in successes if r["template"].startswith("AGREEMENT_")]
    return {
        "experiment_id": config["experiment_id"],
        "designation": config["designation"],
        "exploratory": True,
        "interpretation_limit": "mechanical scope-routing feasibility only; no consciousness, self-awareness, phenomenology, or identification inference",
        "schedule_sha256": schedule_sha256(schedule),
        "prompt_source_sha256": config["prompt_source_sha256"],
        "planned_successful_calls": len(schedule),
        "successful_calls": len(successes),
        "transport_failure_records": sum(record.get("failure") is not None for record in records),
        "overall_conflict_routing": routing_metrics(conflict_records, config),
        "overall_agreement_controls": routing_metrics(agreement_records, config),
        "results_by_directive_order": grouped_summaries(
            successes, config, "directive_order"
        ),
        "results_by_model": grouped_summaries(successes, config, "model_key"),
        "results_by_pair": grouped_summaries(successes, config, "pair_id"),
        "results_by_template": grouped_summaries(successes, config, "template"),
        "results_by_candidate_reversal": grouped_summaries(successes, config, "direction"),
        "directive_order_differences": order_differences,
        "candidate_reversal_differences": reversal,
        "pair_symmetry_differences": pair_differences,
        "key_feasibility_requirement": "Active-directive routing should not disappear or reverse merely when the competing directive is presented first.",
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
        raise SystemExit("analysis requires a complete 320-call collection")
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
