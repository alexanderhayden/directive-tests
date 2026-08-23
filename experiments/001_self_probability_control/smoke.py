"""Separate, non-substantive instrument-validation smoke pilot for Experiment 001A."""

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

from harness.logging import append_jsonl, load_jsonl, summarize_records, write_jsonl
from harness.manifests import atomic_write_json, create_manifest, prepare_run_directory
from harness.parsing import (
    exact_protocol_following,
    external_routing_adherence,
    parse_candidate,
    parse_first_token,
)
from harness.providers.ollama import OllamaProvider

from design import (
    CONFIG_PATH,
    HERE,
    PROMPTS_PATH,
    build_schedule,
    build_trial_payload,
    load_config,
    load_prompts,
    pair_for_trial,
    schedule_sha256,
)
from run import payload_sha256, utc_now, verify_model_inventory

FULL_SCHEDULE_SHA256 = "777ade6c69ec325465c6f0c4490f4b2844e928c6c8c4e204efffeb1d6934d1d5"
SMOKE_REPEATS = (0, 1)
SMOKE_PLANNED_CALLS = 256
SMOKE_EXPERIMENT_ID = "001A_self_probability_control_instrument_validation_smoke"
SMOKE_DESIGNATION = "non_substantive_instrument_validation_smoke"
SELECTION_RULE = (
    "From the unchanged frozen full 001A schedule, retain rows whose frozen repeat field "
    "is 0 or 1, preserving full-schedule order."
)
SMOKE_PROTOCOL_PATH = HERE / "SMOKE_PILOT.md"
SMOKE_RESULTS_ROOT = HERE / "results" / "smoke_pilot"


def select_smoke_schedule(full_schedule: list[dict]) -> list[dict]:
    """Select two immutable rows per full cell without changing the source schedule."""
    if schedule_sha256(full_schedule) != FULL_SCHEDULE_SHA256:
        raise ValueError("full 001A schedule hash differs from the frozen value")

    selected = [dict(row) for row in full_schedule if row["repeat"] in SMOKE_REPEATS]
    if len(selected) != SMOKE_PLANNED_CALLS:
        raise ValueError(f"smoke subset has {len(selected)} rows; expected {SMOKE_PLANNED_CALLS}")

    cell_counts = Counter(row["cell_id"] for row in selected)
    if len(cell_counts) != 128 or set(cell_counts.values()) != {2}:
        raise ValueError("smoke subset must contain exactly two rows from each of 128 cells")

    combination_counts = Counter(
        (row["model_key"], row["arm"], row["pair_id"], row["first_percent"])
        for row in selected
    )
    if len(combination_counts) != 128 or set(combination_counts.values()) != {2}:
        raise ValueError("smoke subset is not balanced by model × arm × pair × split")

    for row in selected:
        if row["arm"] == "EXTERNAL_RANDOMIZER":
            if row.get("external_assignment") not in {"first", "second"}:
                raise ValueError(f"frozen external assignment missing from {row['trial_id']}")
            if row.get("external_assignment_source") != "preconstructed_exact_allocation":
                raise ValueError(f"unexpected external assignment source in {row['trial_id']}")
    return selected


def build_smoke_schedule() -> tuple[list[dict], list[dict]]:
    full_schedule = build_schedule()
    selected = select_smoke_schedule(full_schedule)
    if schedule_sha256(full_schedule) != FULL_SCHEDULE_SHA256:
        raise AssertionError("smoke selection mutated the full 001A schedule")
    return full_schedule, selected


def _string_counts(rows: list[dict], fields: tuple[str, ...]) -> dict[str, int]:
    counts = Counter("__".join(str(row[field]) for field in fields) for row in rows)
    return dict(sorted(counts.items()))


def dry_run_report() -> dict:
    full_schedule, selected = build_smoke_schedule()
    cell_counts = Counter(row["cell_id"] for row in selected)
    combination_counts = Counter(
        (row["model_key"], row["arm"], row["pair_id"], row["first_percent"])
        for row in selected
    )
    external = [row for row in selected if row["arm"] == "EXTERNAL_RANDOMIZER"]
    return {
        "mode": "smoke-dry-run-no-provider-contact",
        "experiment_id": SMOKE_EXPERIMENT_ID,
        "designation": SMOKE_DESIGNATION,
        "selection_rule": SELECTION_RULE,
        "selected_repeats": list(SMOKE_REPEATS),
        "planned_calls": len(selected),
        "cell_count": len(cell_counts),
        "cell_counts_unique_values": sorted(set(cell_counts.values())),
        "model_arm_pair_split_combinations": len(combination_counts),
        "model_arm_pair_split_counts_unique_values": sorted(set(combination_counts.values())),
        "model_counts": _string_counts(selected, ("model_key",)),
        "arm_counts": _string_counts(selected, ("arm",)),
        "pair_counts": _string_counts(selected, ("pair_id",)),
        "split_counts": _string_counts(selected, ("first_percent", "second_percent")),
        "model_arm_pair_split_counts": _string_counts(
            selected, ("model_key", "arm", "pair_id", "first_percent", "second_percent")
        ),
        "external_selected_trials": len(external),
        "external_assignment_counts": dict(sorted(Counter(
            row["external_assignment"] for row in external
        ).items())),
        "full_schedule_trials": len(full_schedule),
        "full_schedule_sha256": schedule_sha256(full_schedule),
        "smoke_schedule_sha256": schedule_sha256(selected),
        "results_namespace": str(SMOKE_RESULTS_ROOT.relative_to(REPO_ROOT)),
        "excluded_from_full_001A": True,
    }


def smoke_manifest(
    run_id: str,
    run_dir: Path,
    selected: list[dict],
    config: dict,
    model_ids: list[dict],
) -> dict:
    manifest = create_manifest(
        experiment_id=SMOKE_EXPERIMENT_ID,
        run_id=run_id,
        repo_root=REPO_ROOT,
        preregistration=SMOKE_PROTOCOL_PATH,
        runner=Path(__file__),
        analysis=Path(__file__),
        config_paths=[CONFIG_PATH, PROMPTS_PATH],
        model_ids=model_ids,
        provider="Ollama local",
        sampling_parameters=config["sampling"],
        planned_calls=len(selected),
        output_directory=run_dir,
        schedule_sha256=schedule_sha256(selected),
    )
    manifest.update({
        "designation": SMOKE_DESIGNATION,
        "lifecycle_status": "smoke_collecting",
        "selection_rule": SELECTION_RULE,
        "selected_repeats": list(SMOKE_REPEATS),
        "source_full_experiment_id": config["experiment_id"],
        "source_full_schedule_sha256": FULL_SCHEDULE_SHA256,
        "smoke_outcomes_excluded_from_full_001A": True,
        "attempted_trial_ids": 0,
    })
    return manifest


def update_smoke_manifest(manifest_path: Path, records: list[dict], planned_calls: int) -> dict:
    manifest = json.loads(manifest_path.read_text())
    accounting = summarize_records(records)
    attempted_ids = {record.get("trial_id") for record in records if record.get("trial_id")}
    manifest.update({
        "completed_calls": accounting["completed_calls"],
        "failures": accounting["failures"],
        "transport_attempts": accounting["transport_attempts"],
        "attempted_trial_ids": len(attempted_ids),
        "last_updated_utc": utc_now(),
    })
    if len(attempted_ids) == planned_calls:
        manifest["lifecycle_status"] = "smoke_collection_complete"
        manifest["utc_collection_completed"] = utc_now()
    atomic_write_json(manifest_path, manifest)
    return manifest


def collect(run_id: str) -> None:
    config = load_config()
    prompts = load_prompts()
    _, selected = build_smoke_schedule()
    provider = OllamaProvider()

    # Inventory verification precedes the first inference request and uses only /api/tags.
    model_ids = verify_model_inventory(provider, config)
    run_dir = prepare_run_directory(SMOKE_RESULTS_ROOT, run_id, resume=False)
    manifest_path = run_dir / "manifest.json"
    schedule_path = run_dir / "schedule.jsonl"
    raw_path = run_dir / "raw_responses.jsonl"
    write_jsonl(schedule_path, selected)
    atomic_write_json(manifest_path, smoke_manifest(run_id, run_dir, selected, config, model_ids))

    model_by_key = {model["model_key"]: model for model in config["models"]}
    print(f"run_id={run_id} smoke_planned={len(selected)}")
    try:
        for trial in selected:
            payload = build_trial_payload(trial, config, prompts)
            spec = model_by_key[trial["model_key"]]
            sampling = {
                key: value for key, value in config["sampling"].items()
                if key != "max_attempts"
            }
            result = provider.sample(
                model=spec["model_tag"],
                interface=spec["interface"],
                payload=payload,
                parameters=sampling,
                max_attempts=config["sampling"]["max_attempts"],
            )
            pair = pair_for_trial(trial, config)
            record = {
                **trial,
                "dataset_role": "instrument_validation_smoke_excluded_from_full_001A",
                "source_full_schedule_sha256": FULL_SCHEDULE_SHA256,
                "logical_attempt": 1,
                "utc_time": utc_now(),
                "prompt_sha256": payload_sha256(payload),
                **result.to_record(),
                "parsed_choice": parse_candidate(result.raw_response, pair["first"], pair["second"]),
                "protocol_exact": exact_protocol_following(
                    result.raw_response, pair["first"], pair["second"]
                ),
            }
            append_jsonl(raw_path, record)
            manifest = update_smoke_manifest(manifest_path, load_jsonl(raw_path), len(selected))
            status = "FAILED" if result.failure else record["parsed_choice"]
            print(f"{manifest['attempted_trial_ids']}/{len(selected)} {trial['trial_id']} {status}")
    finally:
        manifest = update_smoke_manifest(manifest_path, load_jsonl(raw_path), len(selected))
        print(json.dumps({key: manifest[key] for key in (
            "lifecycle_status", "planned_calls", "attempted_trial_ids",
            "completed_calls", "failures", "transport_attempts",
        )}, indent=2))


def _diagnostic_types(record: dict, parsed_choice: str, protocol_exact: bool) -> list[str]:
    raw = record.get("raw_response")
    types: list[str] = []
    if raw is None:
        types.append("null_response")
    elif not raw.strip():
        types.append("blank_response")
    if isinstance(raw, str) and "\n" in raw:
        types.append("contains_newline")
    if record.get("finish_reason") in {"length", "max_tokens"}:
        types.append("length_truncated")
    if parsed_choice == "OTHER":
        types.append("OTHER_first_token")
    if not protocol_exact and parsed_choice in {"first", "second"}:
        types.append("candidate_with_extra_text_or_formatting")
    return types


def report_records(records: list[dict], selected: list[dict], config: dict) -> dict:
    scheduled_ids = {row["trial_id"] for row in selected}
    if any(record.get("trial_id") not in scheduled_ids for record in records):
        raise ValueError("smoke records contain a trial outside the deterministic subset")
    if any(
        record.get("source_full_schedule_sha256") != FULL_SCHEDULE_SHA256
        for record in records
    ):
        raise ValueError("smoke record source schedule hash mismatch")

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    diagnostic_rows: dict[str, list[dict]] = defaultdict(list)
    external_adherence: dict[str, list[bool]] = defaultdict(list)
    successful = [record for record in records if record.get("failure") is None]

    for record in successful:
        pair = pair_for_trial(record, config)
        choice = parse_candidate(record.get("raw_response"), pair["first"], pair["second"])
        exact = exact_protocol_following(record.get("raw_response"), pair["first"], pair["second"])
        enriched = {**record, "reparsed_choice": choice, "reparsed_protocol_exact": exact}
        grouped[(record["model_key"], record["arm"])].append(enriched)
        adherence = external_routing_adherence(choice, record.get("external_assignment"))
        if adherence is not None:
            external_adherence[record["model_key"]].append(adherence)
        for diagnostic_type in _diagnostic_types(record, choice, exact):
            diagnostic_rows[diagnostic_type].append(enriched)

    model_arm: dict[str, dict] = {}
    for (model_key, arm), rows in sorted(grouped.items()):
        counts = Counter(row["reparsed_choice"] for row in rows)
        exact_n = sum(row["reparsed_protocol_exact"] for row in rows)
        model_arm[f"{model_key}__{arm}"] = {
            "successful": len(rows),
            "first": counts["first"],
            "second": counts["second"],
            "OTHER": counts["OTHER"],
            "exact_protocol": exact_n,
            "exact_protocol_rate": exact_n / len(rows) if rows else None,
        }

    external: dict[str, dict] = {}
    for model_key, values in sorted(external_adherence.items()):
        external[model_key] = {
            "adherent": sum(values),
            "trials": len(values),
            "adherence_rate": sum(values) / len(values) if values else None,
        }

    diagnostics: dict[str, dict] = {}
    for diagnostic_type, rows in sorted(diagnostic_rows.items()):
        representatives: list[dict] = []
        seen: set[tuple] = set()
        for row in rows:
            signature = (
                row.get("model_key"), row.get("arm"), row.get("raw_response"),
                row.get("finish_reason"), row.get("reparsed_choice"),
            )
            if signature in seen:
                continue
            seen.add(signature)
            representatives.append({
                "trial_id": row.get("trial_id"),
                "model_key": row.get("model_key"),
                "training_stage": row.get("training_stage"),
                "arm": row.get("arm"),
                "raw_response": row.get("raw_response"),
                "finish_reason": row.get("finish_reason"),
                "first_token": parse_first_token(row.get("raw_response")),
                "parsed_choice": row.get("reparsed_choice"),
            })
            if len(representatives) == 8:
                break
        diagnostics[diagnostic_type] = {"count": len(rows), "representatives": representatives}

    transport_failures = Counter(
        record.get("failure") for record in records if record.get("failure") is not None
    )
    format_by_stage: dict[str, dict] = {}
    for stage in ("base", "instruction_tuned"):
        rows = [row for rows in grouped.values() for row in rows if row["training_stage"] == stage]
        exact_n = sum(row["reparsed_protocol_exact"] for row in rows)
        other_n = sum(row["reparsed_choice"] == "OTHER" for row in rows)
        newline_n = sum("\n" in (row.get("raw_response") or "") for row in rows)
        format_by_stage[stage] = {
            "successful": len(rows),
            "exact_protocol_rate": exact_n / len(rows) if rows else None,
            "OTHER_rate": other_n / len(rows) if rows else None,
            "responses_containing_newline": newline_n,
        }

    attempts = [int(record.get("attempts", 0)) for record in records]
    return {
        "designation": SMOKE_DESIGNATION,
        "interpretation_limit": "instrument debugging only; never evaluate the research hypothesis",
        "source_full_schedule_sha256": FULL_SCHEDULE_SHA256,
        "smoke_schedule_sha256": schedule_sha256(selected),
        "record_accounting": {
            "planned": len(selected),
            "records": len(records),
            "successful": len(successful),
            "failed": len(records) - len(successful),
            "calls_requiring_retry": sum(attempt > 1 for attempt in attempts),
            "transport_retries": sum(max(0, attempt - 1) for attempt in attempts),
            "transport_attempts": sum(attempts),
            "distinct_transport_failures": dict(sorted(transport_failures.items())),
        },
        "model_arm": model_arm,
        "external_randomizer": external,
        "diagnostics": diagnostics,
        "formatting_by_training_stage": format_by_stage,
        "finish_reasons": dict(sorted(Counter(
            str(record.get("finish_reason")) for record in successful
        ).items())),
        "response_length_characters": {
            "min": min((len(record.get("raw_response") or "") for record in successful), default=None),
            "median": statistics.median(
                [len(record.get("raw_response") or "") for record in successful]
            ) if successful else None,
            "max": max((len(record.get("raw_response") or "") for record in successful), default=None),
        },
    }


def report(run_id: str) -> None:
    run_dir = SMOKE_RESULTS_ROOT / "runs" / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"smoke manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("lifecycle_status") != "smoke_collection_complete":
        raise SystemExit("smoke report requires all 256 selected logical trials to be attempted")
    selected = load_jsonl(run_dir / "schedule.jsonl")
    if schedule_sha256(selected) != manifest.get("schedule_sha256"):
        raise SystemExit("on-disk smoke schedule hash does not match manifest")
    summary = report_records(load_jsonl(run_dir / "raw_responses.jsonl"), selected, load_config())
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--dry-run", action="store_true", help="validate subset; no provider contact")
    actions.add_argument("--run-id", help="new immutable smoke-pilot run identifier")
    actions.add_argument("--report-run-id", help="inspect a completed smoke-pilot run")
    args = parser.parse_args()

    if args.dry_run:
        print(json.dumps(dry_run_report(), indent=2, ensure_ascii=False, sort_keys=True))
    elif args.run_id:
        collect(args.run_id)
    else:
        report(args.report_run_id)


if __name__ == "__main__":
    main()
