"""Isolated post-amendment v2 instrument-validation smoke pilot for Experiment 001A."""

from __future__ import annotations

import argparse
import hashlib
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
    external_routing_adherence,
    parse_candidate,
    parse_first_token,
    strict_candidate_classification,
    strict_external_routing_adherence,
)
from harness.providers.ollama import OllamaProvider

from analyze_v2 import model_validation_eligibility
from design_v2 import (
    ARCHIVED_V1_SCHEDULE_SHA256,
    CONFIG_PATH,
    HERE,
    INSTRUMENT_VERSION,
    PROMPTS_V2_PATH,
    V2_SCHEDULE_SHA256,
    build_schedule_v2,
    build_trial_payload_v2,
    canonical_json_sha256,
    derive_eligible_run_schedule,
    load_config,
    load_prompts_v2,
    pair_for_trial,
    schedule_sha256,
)
from run import payload_sha256, utc_now, verify_model_inventory

SMOKE_REPEATS = (0, 1)
SMOKE_PLANNED_CALLS = 256
SMOKE_EXPERIMENT_ID = "001A_v2_post_amendment_instrument_validation_smoke"
SMOKE_DESIGNATION = "non_substantive_v2_instrument_validation_smoke"
SELECTION_RULE = (
    "From the frozen v2 master schedule, retain rows whose inherited repeat field is "
    "0 or 1, preserving v2 master-schedule order and all archived v1 assignments."
)
AMENDMENT_PATH = HERE / "INSTRUMENT_AMENDMENT_V2.md"
SMOKE_PROTOCOL_PATH = HERE / "SMOKE_PILOT_V2.md"
SMOKE_RESULTS_ROOT = HERE / "results" / "smoke_pilot_v2"
NONEXTERNAL_ARMS = {"BASE", "CLARIFY", "SELF_PROBABILITY"}
FROZEN_REPORT_FILENAME = "report.json"
FROZEN_ELIGIBILITY_FILENAME = "eligibility_decision.json"


def select_smoke_schedule(full_schedule: list[dict]) -> list[dict]:
    if schedule_sha256(full_schedule) != V2_SCHEDULE_SHA256:
        raise ValueError("v2 master schedule hash differs from the frozen amended value")
    selected = [dict(row) for row in full_schedule if row["repeat"] in SMOKE_REPEATS]
    if len(selected) != SMOKE_PLANNED_CALLS:
        raise ValueError(f"v2 smoke subset has {len(selected)} rows; expected 256")
    cell_counts = Counter(row["cell_id"] for row in selected)
    if len(cell_counts) != 128 or set(cell_counts.values()) != {2}:
        raise ValueError("v2 smoke must contain exactly two rows from each of 128 cells")
    combination_counts = Counter(
        (row["model_key"], row["arm"], row["pair_id"], row["first_percent"])
        for row in selected
    )
    if len(combination_counts) != 128 or set(combination_counts.values()) != {2}:
        raise ValueError("v2 smoke is not balanced by model × arm × pair × split")
    for row in selected:
        if row["arm"] == "EXTERNAL_RANDOMIZER":
            if row.get("external_assignment") not in {"first", "second"}:
                raise ValueError(f"external assignment missing from {row['trial_id']}")
            if row.get("external_assignment_source") != "preconstructed_exact_allocation":
                raise ValueError(f"external assignment source changed in {row['trial_id']}")
    return selected


def build_smoke_schedule() -> tuple[list[dict], list[dict]]:
    full_schedule = build_schedule_v2()
    return full_schedule, select_smoke_schedule(full_schedule)


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
        "mode": "v2-smoke-dry-run-no-provider-contact",
        "experiment_id": SMOKE_EXPERIMENT_ID,
        "instrument_version": INSTRUMENT_VERSION,
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
        "archived_v1_schedule_sha256": ARCHIVED_V1_SCHEDULE_SHA256,
        "v2_master_schedule_trials": len(full_schedule),
        "v2_master_schedule_sha256": schedule_sha256(full_schedule),
        "v2_smoke_schedule_sha256": schedule_sha256(selected),
        "results_namespace": str(SMOKE_RESULTS_ROOT.relative_to(REPO_ROOT)),
        "excluded_from_v1_and_v2_full_001A": True,
        "provider_contact": False,
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
        config_paths=[CONFIG_PATH, PROMPTS_V2_PATH, AMENDMENT_PATH],
        model_ids=model_ids,
        provider="Ollama local",
        sampling_parameters=config["sampling"],
        planned_calls=len(selected),
        output_directory=run_dir,
        schedule_sha256=schedule_sha256(selected),
    )
    manifest.update({
        "instrument_version": INSTRUMENT_VERSION,
        "designation": SMOKE_DESIGNATION,
        "lifecycle_status": "v2_smoke_collecting",
        "selection_rule": SELECTION_RULE,
        "selected_repeats": list(SMOKE_REPEATS),
        "archived_v1_schedule_sha256": ARCHIVED_V1_SCHEDULE_SHA256,
        "source_v2_master_schedule_sha256": V2_SCHEDULE_SHA256,
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
        manifest["lifecycle_status"] = "v2_smoke_collection_complete"
        manifest["utc_collection_completed"] = utc_now()
    atomic_write_json(manifest_path, manifest)
    return manifest


def collect(run_id: str) -> None:
    config = load_config()
    prompts = load_prompts_v2()
    _, selected = build_smoke_schedule()
    provider = OllamaProvider()

    # Inventory verification uses /api/tags. The first generation request occurs
    # only after the immutable run directory, schedule, and manifest are written.
    model_ids = verify_model_inventory(provider, config)
    run_dir = prepare_run_directory(SMOKE_RESULTS_ROOT, run_id, resume=False)
    manifest_path = run_dir / "manifest.json"
    schedule_path = run_dir / "schedule.jsonl"
    raw_path = run_dir / "raw_responses.jsonl"
    write_jsonl(schedule_path, selected)
    atomic_write_json(manifest_path, smoke_manifest(run_id, run_dir, selected, config, model_ids))

    model_by_key = {model["model_key"]: model for model in config["models"]}
    print(f"run_id={run_id} v2_smoke_planned={len(selected)}")
    try:
        for trial in selected:
            payload = build_trial_payload_v2(trial, config, prompts)
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
            strict = strict_candidate_classification(
                result.raw_response, pair["first"], pair["second"]
            )
            loose = parse_candidate(result.raw_response, pair["first"], pair["second"])
            record = {
                **trial,
                "dataset_role": "v2_instrument_validation_smoke_excluded_from_full_001A",
                "source_v2_master_schedule_sha256": V2_SCHEDULE_SHA256,
                "logical_attempt": 1,
                "utc_time": utc_now(),
                "prompt_sha256": payload_sha256(payload),
                **result.to_record(),
                "primary_classification": strict,
                "strict_exact_candidate": strict != "PROTOCOL_FAILURE",
                "strict_external_adherent": strict_external_routing_adherence(
                    result.raw_response,
                    pair["first"],
                    pair["second"],
                    trial.get("external_assignment"),
                ),
                "loose_parsed_choice_diagnostic": loose,
                "loose_external_adherent_diagnostic": external_routing_adherence(
                    loose, trial.get("external_assignment")
                ),
            }
            append_jsonl(raw_path, record)
            manifest = update_smoke_manifest(manifest_path, load_jsonl(raw_path), len(selected))
            status = "FAILED" if result.failure else strict
            print(f"{manifest['attempted_trial_ids']}/{len(selected)} {trial['trial_id']} {status}")
    finally:
        manifest = update_smoke_manifest(manifest_path, load_jsonl(raw_path), len(selected))
        print(json.dumps({key: manifest[key] for key in (
            "lifecycle_status", "planned_calls", "attempted_trial_ids",
            "completed_calls", "failures", "transport_attempts",
        )}, indent=2))


def _diagnostic_types(record: dict, strict: str, loose: str) -> list[str]:
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
    if strict == "PROTOCOL_FAILURE":
        types.append("PROTOCOL_FAILURE")
        if loose in {"first", "second"}:
            types.append("candidate_plus_text_or_formatting")
        else:
            types.append("no_candidate_first_token")
    return types


def report_records(records: list[dict], selected: list[dict], config: dict) -> dict:
    scheduled_ids = {row["trial_id"] for row in selected}
    if any(record.get("trial_id") not in scheduled_ids for record in records):
        raise ValueError("v2 smoke records contain a trial outside the deterministic subset")
    if any(
        record.get("source_v2_master_schedule_sha256") != V2_SCHEDULE_SHA256
        for record in records
    ):
        raise ValueError("v2 smoke record source schedule hash mismatch")

    successful = [record for record in records if record.get("failure") is None]
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    diagnostic_rows: dict[str, list[dict]] = defaultdict(list)
    reparsed: list[dict] = []
    for record in successful:
        pair = pair_for_trial(record, config)
        strict = strict_candidate_classification(
            record.get("raw_response"), pair["first"], pair["second"]
        )
        loose = parse_candidate(record.get("raw_response"), pair["first"], pair["second"])
        enriched = {**record, "reparsed_strict": strict, "reparsed_loose": loose}
        reparsed.append(enriched)
        grouped[(record["model_key"], record["arm"])].append(enriched)
        for diagnostic_type in _diagnostic_types(record, strict, loose):
            diagnostic_rows[diagnostic_type].append(enriched)

    model_arm: dict[str, dict] = {}
    for (model_key, arm), rows in sorted(grouped.items()):
        strict_counts = Counter(row["reparsed_strict"] for row in rows)
        loose_counts = Counter(row["reparsed_loose"] for row in rows)
        model_arm[f"{model_key}__{arm}"] = {
            "successful": len(rows),
            "exact_first": strict_counts["first"],
            "exact_second": strict_counts["second"],
            "PROTOCOL_FAILURE": strict_counts["PROTOCOL_FAILURE"],
            "strict_exact_candidate_rate": (
                (strict_counts["first"] + strict_counts["second"]) / len(rows) if rows else None
            ),
            "loose_first_token_diagnostic": {
                "first": loose_counts["first"],
                "second": loose_counts["second"],
                "OTHER": loose_counts["OTHER"],
            },
        }

    eligibility: dict[str, dict] = {}
    external: dict[str, dict] = {}
    for model in config["models"]:
        model_key = model["model_key"]
        model_rows = [row for row in reparsed if row["model_key"] == model_key]
        ext_rows = [row for row in model_rows if row["arm"] == "EXTERNAL_RANDOMIZER"]
        nonext_rows = [row for row in model_rows if row["arm"] in NONEXTERNAL_ARMS]
        strict_ext = []
        loose_ext = []
        for row in ext_rows:
            pair = pair_for_trial(row, config)
            strict_ext.append(strict_external_routing_adherence(
                row.get("raw_response"), pair["first"], pair["second"],
                row.get("external_assignment")
            ))
            loose_ext.append(external_routing_adherence(
                row["reparsed_loose"], row.get("external_assignment")
            ))
        external[model_key] = {
            "strict_adherent": sum(value is True for value in strict_ext),
            "strict_trials": len(strict_ext),
            "strict_adherence_rate": (
                sum(value is True for value in strict_ext) / len(strict_ext) if strict_ext else None
            ),
            "loose_first_token_adherent_diagnostic": sum(value is True for value in loose_ext),
            "loose_first_token_trials_diagnostic": len(loose_ext),
            "loose_first_token_adherence_rate_diagnostic": (
                sum(value is True for value in loose_ext) / len(loose_ext) if loose_ext else None
            ),
        }
        eligibility[model_key] = model_validation_eligibility(
            strict_external_adherent=sum(value is True for value in strict_ext),
            strict_external_trials=len(strict_ext),
            strict_nonexternal_exact=sum(
                row["reparsed_strict"] in {"first", "second"} for row in nonext_rows
            ),
            strict_nonexternal_trials=len(nonext_rows),
        )

    diagnostics: dict[str, dict] = {}
    for diagnostic_type, rows in sorted(diagnostic_rows.items()):
        representatives: list[dict] = []
        seen: set[tuple] = set()
        for row in rows:
            signature = (
                row.get("model_key"), row.get("arm"), row.get("raw_response"),
                row.get("finish_reason"), row.get("reparsed_strict"),
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
                "strict_classification": row.get("reparsed_strict"),
                "loose_classification": row.get("reparsed_loose"),
            })
            if len(representatives) == 8:
                break
        diagnostics[diagnostic_type] = {"count": len(rows), "representatives": representatives}

    attempts = [int(record.get("attempts", 0)) for record in records]
    return {
        "designation": SMOKE_DESIGNATION,
        "interpretation_limit": "instrument validation only; do not evaluate the research hypothesis",
        "archived_v1_schedule_sha256": ARCHIVED_V1_SCHEDULE_SHA256,
        "source_v2_master_schedule_sha256": V2_SCHEDULE_SHA256,
        "v2_smoke_schedule_sha256": schedule_sha256(selected),
        "record_accounting": {
            "planned": len(selected),
            "records": len(records),
            "successful": len(successful),
            "failed": len(records) - len(successful),
            "calls_requiring_retry": sum(attempt > 1 for attempt in attempts),
            "transport_retries": sum(max(0, attempt - 1) for attempt in attempts),
            "transport_attempts": sum(attempts),
            "distinct_transport_failures": dict(sorted(Counter(
                record.get("failure") for record in records if record.get("failure") is not None
            ).items())),
        },
        "model_arm": model_arm,
        "strict_external_randomizer": external,
        "model_eligibility": eligibility,
        "diagnostics": diagnostics,
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


def completed_report(run_id: str) -> tuple[Path, dict]:
    run_dir = SMOKE_RESULTS_ROOT / "runs" / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"v2 smoke manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("lifecycle_status") != "v2_smoke_collection_complete":
        raise SystemExit("v2 smoke report requires all 256 selected trials to be attempted")
    selected = load_jsonl(run_dir / "schedule.jsonl")
    if schedule_sha256(selected) != manifest.get("schedule_sha256"):
        raise SystemExit("on-disk v2 smoke schedule hash does not match manifest")
    summary = report_records(load_jsonl(run_dir / "raw_responses.jsonl"), selected, load_config())
    if summary["record_accounting"]["records"] != SMOKE_PLANNED_CALLS:
        raise SystemExit("v2 smoke report requires exactly 256 logical trial records")
    return run_dir, summary


def report(run_id: str) -> None:
    _, summary = completed_report(run_id)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_eligibility_decision(run_id: str) -> None:
    """Freeze the completed smoke report and its deterministic full-run gate."""
    run_dir, summary = completed_report(run_id)
    report_path = run_dir / FROZEN_REPORT_FILENAME
    decision_path = run_dir / FROZEN_ELIGIBILITY_FILENAME
    if report_path.exists() or decision_path.exists():
        raise SystemExit("refusing to overwrite a frozen v2 smoke report or eligibility decision")
    atomic_write_json(report_path, summary)

    config = load_config()
    canonical = build_schedule_v2(config)
    configured_keys = [model["model_key"] for model in config["models"]]
    eligible_keys = [
        key for key in configured_keys
        if summary["model_eligibility"][key]["eligible_for_full_model_specific_run"]
    ]
    eligible_schedule = derive_eligible_run_schedule(canonical, eligible_keys, config)
    decision = {
        "schema_version": 1,
        "decision_status": "frozen_from_completed_v2_smoke_report",
        "source_smoke_run_id": run_id,
        "source_smoke_report_filename": FROZEN_REPORT_FILENAME,
        "source_smoke_report_sha256": _file_sha256(report_path),
        "source_v2_smoke_schedule_sha256": summary["v2_smoke_schedule_sha256"],
        "canonical_v2_design_schedule_sha256": schedule_sha256(canonical),
        "eligible_model_keys": eligible_keys,
        "ineligible_model_keys": [key for key in configured_keys if key not in eligible_keys],
        "actual_eligible_run_schedule_sha256": schedule_sha256(eligible_schedule),
        "actual_eligible_run_planned_trials": len(eligible_schedule),
        "models": summary["model_eligibility"],
        "frozen_utc": utc_now(),
    }
    atomic_write_json(decision_path, decision)
    decision_hashes = {
        "eligibility_decision_sha256": canonical_json_sha256(decision),
        "eligibility_decision_file_sha256": _file_sha256(decision_path),
    }
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.update({
        **decision_hashes,
        "eligibility_decision_filename": FROZEN_ELIGIBILITY_FILENAME,
        "source_smoke_report_sha256": decision["source_smoke_report_sha256"],
        "source_v2_smoke_schedule_sha256": decision["source_v2_smoke_schedule_sha256"],
        "canonical_v2_design_schedule_sha256": decision[
            "canonical_v2_design_schedule_sha256"
        ],
        "actual_eligible_run_schedule_sha256": decision[
            "actual_eligible_run_schedule_sha256"
        ],
        "eligible_model_keys": decision["eligible_model_keys"],
        "eligibility_decision_frozen_utc": decision["frozen_utc"],
    })
    atomic_write_json(manifest_path, manifest)
    print(json.dumps({
        **decision,
        **decision_hashes,
    }, indent=2, ensure_ascii=False, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--dry-run", action="store_true", help="validate v2 subset; no provider contact")
    actions.add_argument("--run-id", help="new immutable v2 smoke run identifier")
    actions.add_argument("--report-run-id", help="inspect a completed v2 smoke run")
    actions.add_argument(
        "--freeze-eligibility-run-id",
        help="freeze a completed v2 smoke report and deterministic full-run eligibility decision",
    )
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps(dry_run_report(), indent=2, ensure_ascii=False, sort_keys=True))
    elif args.run_id:
        collect(args.run_id)
    elif args.report_run_id:
        report(args.report_run_id)
    else:
        freeze_eligibility_decision(args.freeze_eligibility_run_id)


if __name__ == "__main__":
    main()
