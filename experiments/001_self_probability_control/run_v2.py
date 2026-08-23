"""Post-smoke v2 full runner for eligible Experiment 001A models only."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.logging import append_jsonl, load_jsonl, summarize_records, write_jsonl
from harness.manifests import (
    atomic_write_json,
    create_manifest,
    prepare_run_directory,
    update_collection_manifest,
)
from harness.parsing import (
    external_routing_adherence,
    parse_candidate,
    strict_candidate_classification,
    strict_external_routing_adherence,
)
from harness.providers.ollama import OllamaProvider

from design_v2 import (
    ARCHIVED_V1_SCHEDULE_SHA256,
    CANONICAL_V2_DESIGN_SCHEDULE_SHA256,
    CONFIG_PATH,
    HERE,
    INSTRUMENT_VERSION,
    PROMPTS_V2_PATH,
    build_schedule_v2,
    build_trial_payload_v2,
    canonical_json_sha256,
    load_config,
    load_prompts_v2,
    pair_for_trial,
    schedule_sha256,
    validate_eligibility_decision,
)
from run import payload_sha256, utc_now, verify_model_inventory

RESULTS_ROOT = HERE / "results" / "v2"
AMENDMENT_PATH = HERE / "INSTRUMENT_AMENDMENT_V2.md"
ANALYSIS_PATH = HERE / "analyze_v2.py"
FROZEN_REPORT_FILENAME = "report.json"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen_eligibility_decision(
    decision_path: Path,
    config: dict | None = None,
) -> tuple[dict, dict, list[dict], str, str]:
    """Load and validate the frozen post-smoke gate before any provider access."""
    config = config or load_config()
    if not decision_path.is_file():
        raise SystemExit(f"frozen eligibility decision missing: {decision_path}")
    decision = json.loads(decision_path.read_text())
    report_filename = decision.get("source_smoke_report_filename")
    if report_filename != FROZEN_REPORT_FILENAME:
        raise SystemExit("eligibility decision has an unexpected smoke report filename")
    report_path = decision_path.parent / report_filename
    if not report_path.is_file():
        raise SystemExit(f"frozen source smoke report missing: {report_path}")
    report_hash = file_sha256(report_path)
    if report_hash != decision.get("source_smoke_report_sha256"):
        raise SystemExit("frozen source smoke report hash differs from eligibility decision")
    source_report = json.loads(report_path.read_text())
    try:
        eligible_schedule = validate_eligibility_decision(decision, source_report, config)
    except ValueError as error:
        raise SystemExit(f"invalid frozen eligibility decision: {error}") from error
    return (
        decision,
        source_report,
        eligible_schedule,
        file_sha256(decision_path),
        canonical_json_sha256(decision),
    )


def require_nonempty_eligible_schedule(schedule: list[dict]) -> None:
    if not schedule:
        raise SystemExit("no model passed the frozen v2 smoke gate; full collection is forbidden")


def manifest_for(
    run_id: str,
    run_dir: Path,
    schedule: list[dict],
    config: dict,
    model_ids: list[dict],
    decision: dict,
    decision_file_sha256: str,
    decision_sha256: str,
) -> dict:
    manifest = create_manifest(
        experiment_id=f"{config['experiment_id']}_v2_eligible_models",
        run_id=run_id,
        repo_root=REPO_ROOT,
        preregistration=AMENDMENT_PATH,
        runner=Path(__file__),
        analysis=ANALYSIS_PATH,
        config_paths=[CONFIG_PATH, PROMPTS_V2_PATH],
        model_ids=model_ids,
        provider="Ollama local",
        sampling_parameters=config["sampling"],
        planned_calls=len(schedule),
        output_directory=run_dir,
        schedule_sha256=schedule_sha256(schedule),
    )
    manifest.update({
        "instrument_version": INSTRUMENT_VERSION,
        "archived_v1_schedule_sha256": ARCHIVED_V1_SCHEDULE_SHA256,
        "canonical_v2_design_schedule_sha256": CANONICAL_V2_DESIGN_SCHEDULE_SHA256,
        "actual_eligible_run_schedule_sha256": schedule_sha256(schedule),
        "eligible_model_keys": decision["eligible_model_keys"],
        "ineligible_model_keys": decision["ineligible_model_keys"],
        "source_smoke_run_id": decision["source_smoke_run_id"],
        "source_smoke_report_sha256": decision["source_smoke_report_sha256"],
        "source_v2_smoke_schedule_sha256": decision["source_v2_smoke_schedule_sha256"],
        "eligibility_decision_sha256": decision_sha256,
        "eligibility_decision_file_sha256": decision_file_sha256,
        "eligibility_decision": decision,
        "eligibility_frozen_before_full_inference": True,
    })
    return manifest


def dry_run_report(decision_path: Path | None = None) -> dict:
    """Validate canonical or eligible schedules without provider contact or writes."""
    config = load_config()
    prompts = load_prompts_v2()
    canonical = build_schedule_v2(config)
    canonical_hash = schedule_sha256(canonical)
    if canonical_hash != CANONICAL_V2_DESIGN_SCHEDULE_SHA256:
        raise ValueError("canonical v2 design schedule differs from its frozen hash")

    report = {
        "mode": "v2-dry-run-no-provider-contact",
        "provider_contact": False,
        "instrument_version": INSTRUMENT_VERSION,
        "archived_v1_schedule_sha256": ARCHIVED_V1_SCHEDULE_SHA256,
        "canonical_v2_design_schedule_sha256": canonical_hash,
        "canonical_v2_design_trials": len(canonical),
        "canonical_model_counts": dict(sorted(Counter(
            row["model_key"] for row in canonical
        ).items())),
        "canonical_cell_count": len({row["cell_id"] for row in canonical}),
        "canonical_unique_prompt_payload_hashes": len({
            payload_sha256(build_trial_payload_v2(row, config, prompts)) for row in canonical
        }),
        "actual_eligible_run_schedule_status": "pending_frozen_v2_smoke_eligibility_decision",
    }
    if decision_path is not None:
        decision, _, schedule, decision_file_hash, decision_hash = load_frozen_eligibility_decision(
            decision_path, config
        )
        report.update({
            "actual_eligible_run_schedule_status": "derived_from_frozen_v2_smoke_decision",
            "eligibility_decision_sha256": decision_hash,
            "eligibility_decision_file_sha256": decision_file_hash,
            "eligible_model_keys": decision["eligible_model_keys"],
            "ineligible_model_keys": decision["ineligible_model_keys"],
            "actual_eligible_run_schedule_sha256": schedule_sha256(schedule),
            "actual_eligible_run_trials": len(schedule),
            "actual_eligible_cell_count": len({row["cell_id"] for row in schedule}),
        })
    return report


def collect(run_id: str, decision_path: Path, *, resume: bool) -> None:
    config = load_config()
    prompts = load_prompts_v2()
    decision, _, schedule, decision_file_hash, decision_hash = load_frozen_eligibility_decision(
        decision_path, config
    )
    require_nonempty_eligible_schedule(schedule)

    eligible_keys = set(decision["eligible_model_keys"])
    eligible_config = {
        **config,
        "models": [model for model in config["models"] if model["model_key"] in eligible_keys],
    }
    provider = OllamaProvider()
    model_ids = verify_model_inventory(provider, eligible_config)
    run_dir = prepare_run_directory(RESULTS_ROOT, run_id, resume=resume)
    manifest_path = run_dir / "manifest.json"
    schedule_path = run_dir / "schedule.jsonl"
    raw_path = run_dir / "raw_responses.jsonl"

    if not resume:
        write_jsonl(schedule_path, schedule)
        atomic_write_json(manifest_path, manifest_for(
            run_id,
            run_dir,
            schedule,
            config,
            model_ids,
            decision,
            decision_file_hash,
            decision_hash,
        ))
    else:
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("eligibility_decision_sha256") != decision_hash:
            raise SystemExit("refusing resume: eligibility decision differs from original run")
        if manifest.get("eligibility_decision_file_sha256") != decision_file_hash:
            raise SystemExit("refusing resume: eligibility decision file differs from original run")
        on_disk_schedule = load_jsonl(schedule_path)
        if schedule_sha256(on_disk_schedule) != schedule_sha256(schedule):
            raise SystemExit("refusing resume: actual eligible schedule differs from frozen decision")

    existing = load_jsonl(raw_path)
    completed = summarize_records(existing)["successful_trial_ids"]
    pending = [trial for trial in schedule if trial["trial_id"] not in completed]
    attempts_by_trial = Counter(record.get("trial_id") for record in existing)
    model_by_key = {model["model_key"]: model for model in eligible_config["models"]}
    print(
        f"run_id={run_id} eligible_models={len(eligible_keys)} planned={len(schedule)} "
        f"complete={len(completed)} pending={len(pending)}"
    )

    try:
        for trial in pending:
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
                "logical_attempt": attempts_by_trial[trial["trial_id"]] + 1,
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
            attempts_by_trial[trial["trial_id"]] += 1
            manifest = update_collection_manifest(manifest_path, load_jsonl(raw_path), len(schedule))
            status = "FAILED" if result.failure else strict
            print(
                f"{manifest['completed_calls']}/{len(schedule)} {trial['trial_id']} "
                f"attempt={record['logical_attempt']} {status}"
            )
    finally:
        manifest = update_collection_manifest(manifest_path, load_jsonl(raw_path), len(schedule))
        print(json.dumps({key: manifest[key] for key in (
            "lifecycle_status", "planned_calls", "completed_calls", "failures",
            "transport_attempts", "canonical_v2_design_schedule_sha256",
            "actual_eligible_run_schedule_sha256", "eligible_model_keys",
        )}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="validate only; no provider contact")
    parser.add_argument("--run-id", help="new immutable v2 full-run identifier")
    parser.add_argument(
        "--eligibility-decision",
        type=Path,
        help="frozen eligibility_decision.json from a completed v2 smoke",
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        if args.run_id or args.resume:
            parser.error("--dry-run cannot be combined with collection flags")
        print(json.dumps(
            dry_run_report(args.eligibility_decision),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        ))
        return
    if not args.run_id or not args.eligibility_decision:
        parser.error("v2 collection requires --run-id and --eligibility-decision")
    collect(args.run_id, args.eligibility_decision, resume=args.resume)


if __name__ == "__main__":
    main()
