"""Contact-gated collector for the protected-source Experiment 008 replication."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import sys
import threading
import time
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from harness.logging import append_jsonl, load_jsonl, write_jsonl
from harness.manifests import atomic_write_json, git_state, prepare_run_directory
from harness.providers import ProviderResult
from harness.providers.anthropic import sample_messages

from design import (
    CONFIG_PATH,
    build_schedule,
    classify_response,
    historical_root,
    load_config,
    load_historical_material,
    payload_metrics,
    schedule_sha256,
    validate_frozen_schedule,
)

RESULTS_ROOT = HERE / "results"


def experiment_code_sources() -> dict:
    paths = {
        "config": CONFIG_PATH,
        "design": HERE / "design.py",
        "runner": HERE / "run.py",
        "analysis": HERE / "analyze.py",
        "preregistration": HERE / "PREREGISTRATION.md",
    }
    return {
        label: {
            "path": str(path.relative_to(REPO_ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for label, path in paths.items()
    }


def runtime_versions() -> dict:
    return {
        "python": platform.python_version(),
        "anthropic_sdk": importlib.metadata.version("anthropic"),
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text_fingerprint(value: str | None) -> dict | None:
    if value is None:
        return None
    return {
        "sha256": hashlib.sha256(value.encode()).hexdigest(),
        "characters": len(value),
        "bytes": len(value.encode()),
    }


def _safe_attempt_failures(failures: list[dict]) -> list[dict]:
    safe = []
    for failure in failures:
        safe.append(
            {
                "attempt": failure.get("attempt"),
                "utc_time": failure.get("utc_time"),
                "error_type": failure.get("error_type"),
                "error_fingerprint": _text_fingerprint(failure.get("error")),
            }
        )
    return safe


def successful_trial_ids(records: list[dict]) -> set[str]:
    return {
        record["trial_id"]
        for record in records
        if record.get("failure") is None
        and record.get("model_invariant_error") is None
        and record.get("provider_invariant_error") is None
        and record.get("trial_id")
    }


def manifest_accounting(records: list[dict], planned: int) -> dict:
    complete = successful_trial_ids(records)
    return {
        "completed_calls": len(complete),
        "planned_calls": planned,
        "response_records": len(records),
        "transport_failure_records": sum(record.get("failure") is not None for record in records),
        "model_invariant_failure_records": sum(
            record.get("model_invariant_error") is not None for record in records
        ),
        "provider_invariant_failure_records": sum(
            record.get("provider_invariant_error") is not None for record in records
        ),
        "transport_attempts": sum(int(record.get("attempts", 0)) for record in records),
        "collection_complete": len(complete) == planned,
    }


def estimated_cost(config: dict) -> dict:
    input_tokens = sum(
        config["payloads"][str(turns)]["historical_input_tokens"]
        * config["n_per_condition"]
        for turns in config["turn_counts"]
    )
    output_tokens = config["planned_calls"] * 4
    input_cost = input_tokens * config["model"]["input_rate_per_mtok"] / 1_000_000
    output_cost = output_tokens * config["model"]["output_rate_per_mtok"] / 1_000_000
    return {
        "basis": "historical input-token counts and four output tokens per successful call",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": input_cost,
        "output_cost_usd": output_cost,
        "total_cost_usd": input_cost + output_cost,
    }


def dry_run_report() -> dict:
    """Validate protected hashes and the full schedule without credentials or contact."""
    config = load_config()
    material = load_historical_material(config)
    schedule = validate_frozen_schedule(config)
    return {
        "mode": "dry-run-no-provider-contact",
        "provider_contact": False,
        "credential_access": False,
        "experiment_id": config["experiment_id"],
        "immutable_run_id": config["immutable_run_id"],
        "historical_root": str(historical_root(config)),
        "historical_commit_base": config["historical_commit_base"],
        "experiment_code_sources": experiment_code_sources(),
        "runtime_versions": runtime_versions(),
        "protected_sources": {
            label: {key: value for key, value in record.items() if key in {"path", "sha256", "bytes", "characters", "message_count"}}
            for label, record in config["protected_sources"].items()
        },
        "candidate_hashes": config["candidate_hashes"],
        "payloads": {
            str(turns): {
                **payload_metrics(payload),
                "historical_input_tokens": config["payloads"][str(turns)]["historical_input_tokens"],
                "endpoint_sha256": config["payloads"][str(turns)]["endpoint_sha256"],
            }
            for turns, payload in material.payloads.items()
        },
        "schedule_sha256": schedule_sha256(schedule),
        "planned_calls": len(schedule),
        "calls_by_turns": dict(sorted(Counter(row["turns"] for row in schedule).items())),
        "workers": config["workers"],
        "model": config["model"],
        "estimated_cost": estimated_cost(config),
    }


def load_api_key() -> str:
    try:
        from dotenv import load_dotenv
    except ImportError as error:
        raise SystemExit("python-dotenv is required for --execute") from error
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY is missing")
    return api_key


def call_provider(
    trial: dict,
    payload: list[dict],
    api_key: str,
    config: dict,
) -> ProviderResult:
    model = config["model"]
    return sample_messages(
        api_key=api_key,
        model=model["model_id"],
        messages=payload,
        parameters=model["request_parameters"],
        max_attempts=model["max_attempts"],
    )


def _safe_sent_parameters(result: ProviderResult, expected_payload_hash: str) -> dict:
    sent = dict(result.sent_parameters)
    messages = sent.pop("messages", None)
    if messages is None:
        raise ValueError("provider adapter did not retain the sent message structure")
    metrics = payload_metrics(messages)
    if metrics["sha256"] != expected_payload_hash:
        raise ValueError("provider adapter sent a payload with an unexpected hash")
    return {
        "sent_parameter_keys": sorted(result.sent_parameters),
        "sent_nonmessage_parameters": sent,
        "sent_message_metrics": metrics,
    }


def _write_manifest(path: Path, manifest: dict, records: list[dict], planned: int) -> dict:
    updated = {
        **manifest,
        **manifest_accounting(records, planned),
        "last_updated_utc": utc_now(),
    }
    atomic_write_json(path, updated)
    return updated


def _initial_manifest(config: dict, run_id: str, schedule: list[dict]) -> dict:
    state = git_state(REPO_ROOT)
    return {
        "schema_version": 1,
        "experiment_id": config["experiment_id"],
        "designation": config["designation"],
        "exploratory": True,
        "run_id": run_id,
        "created_utc": utc_now(),
        "git_state": state,
        "config_sha256": hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(),
        "schedule_sha256": schedule_sha256(schedule),
        "historical_root": str(historical_root(config)),
        "historical_commit_base": config["historical_commit_base"],
        "protected_sources": {
            label: {key: value for key, value in record.items() if key in {"path", "sha256", "bytes", "characters", "message_count"}}
            for label, record in config["protected_sources"].items()
        },
        "historical_code_sources": config["historical_code_sources"],
        "experiment_code_sources": experiment_code_sources(),
        "runtime_versions": runtime_versions(),
        "candidate_hashes": config["candidate_hashes"],
        "payloads": config["payloads"],
        "model": config["model"],
        "workers": config["workers"],
        "schedule_seed": config["schedule_seed"],
        "schedule_algorithm": config["schedule_algorithm"],
        "estimated_cost": estimated_cost(config),
        "lifecycle_status": "exploratory_collecting",
    }


def _run_pass(
    pending: list[dict],
    *,
    config: dict,
    material,
    api_key: str,
    raw_path: Path,
    attempts_by_trial: Counter,
    pass_number: int,
) -> bool:
    abort = False
    executor = ThreadPoolExecutor(max_workers=config["workers"])
    futures: dict[Future, tuple[dict, float, str, int]] = {}
    iterator = iter(pending)
    submission_counter = 0

    def execute(trial: dict):
        started = time.time()
        worker_name = threading.current_thread().name
        result = call_provider(trial, material.payloads[trial["turns"]], api_key, config)
        return result, started, time.time(), worker_name

    def submit_next() -> bool:
        nonlocal submission_counter
        if abort:
            return False
        try:
            trial = next(iterator)
        except StopIteration:
            return False
        future = executor.submit(execute, trial)
        futures[future] = (trial, time.time(), threading.current_thread().name, submission_counter)
        submission_counter += 1
        return True

    try:
        for _ in range(min(config["workers"], len(pending))):
            submit_next()
        while futures:
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                trial, submitted_at, submitter, submission_index = futures.pop(future)
                result, started_at, ended_at, worker_name = future.result()
                expected_provider = config["model"]["expected_provider"]
                model_error = None
                provider_error = None
                if result.failure is None and result.actual_model != trial["model_id"]:
                    model_error = "returned model identifier differs from the frozen requested identifier"
                if result.failure is None and result.provider != expected_provider:
                    provider_error = "returned provider differs from the frozen provider"
                invariant_error = model_error or provider_error
                parsed = classify_response(
                    result.raw_response,
                    material.candidates,
                    finish_reason=result.finish_reason,
                    failure=result.failure,
                    model_invariant_error=invariant_error,
                )
                sent = _safe_sent_parameters(result, trial["payload_sha256"])
                attempts_by_trial[trial["trial_id"]] += 1
                record = {
                    **trial,
                    "collection_pass": pass_number,
                    "pass_submission_index": submission_index,
                    "logical_attempt": attempts_by_trial[trial["trial_id"]],
                    "submitted_unix": submitted_at,
                    "request_started_unix": started_at,
                    "response_received_unix": ended_at,
                    "submitter_thread": submitter,
                    "worker_name": worker_name,
                    "raw_response": result.raw_response,
                    **parsed,
                    "requested_model": result.requested_model,
                    "actual_model": result.actual_model,
                    "provider_returned": result.provider,
                    "client": result.client,
                    "finish_reason": result.finish_reason,
                    "response_id": result.response_id,
                    "usage": result.usage,
                    "attempts": result.attempts,
                    "attempt_failures": _safe_attempt_failures(result.attempt_failures),
                    "failure": _text_fingerprint(result.failure),
                    "model_invariant_error": model_error,
                    "provider_invariant_error": provider_error,
                    "provider_timestamp": result.provider_timestamp,
                    **sent,
                }
                append_jsonl(raw_path, record)
                if invariant_error:
                    abort = True
                if len(load_jsonl(raw_path)) % 50 == 0:
                    print(f"records={len(load_jsonl(raw_path))} pass={pass_number}", flush=True)
                if not abort:
                    submit_next()
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    return abort


def collect(run_id: str, *, resume: bool) -> None:
    config = load_config()
    if run_id != config["immutable_run_id"]:
        raise SystemExit("run ID differs from the frozen immutable run ID")
    material = load_historical_material(config)
    schedule = validate_frozen_schedule(config)
    api_key = load_api_key()

    run_dir = prepare_run_directory(RESULTS_ROOT, run_id, resume=resume)
    schedule_path = run_dir / "schedule.jsonl"
    raw_path = run_dir / "responses.jsonl"
    manifest_path = run_dir / "manifest.json"
    if not resume:
        write_jsonl(schedule_path, schedule)
        manifest = _initial_manifest(config, run_id, schedule)
        _write_manifest(manifest_path, manifest, [], len(schedule))
    else:
        if not manifest_path.is_file() or not schedule_path.is_file():
            raise SystemExit("cannot resume without an existing manifest and schedule")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if schedule_sha256(load_jsonl(schedule_path)) != config["canonical_schedule_sha256"]:
            raise SystemExit("on-disk schedule differs from the frozen canonical schedule")
        if manifest.get("config_sha256") != hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest():
            raise SystemExit("configuration differs from the original run")

    records = load_jsonl(raw_path)
    attempts_by_trial = Counter(record.get("trial_id") for record in records)
    completed = successful_trial_ids(records)
    abort = False
    for pass_number in range(config["max_collection_passes"]):
        pending = [row for row in schedule if row["trial_id"] not in completed]
        if not pending:
            break
        if pass_number or resume:
            random.Random(config["schedule_seed"] + pass_number).shuffle(pending)
        print(
            f"run_id={run_id} pass={pass_number} complete={len(completed)} pending={len(pending)} workers={config['workers']}",
            flush=True,
        )
        abort = _run_pass(
            pending,
            config=config,
            material=material,
            api_key=api_key,
            raw_path=raw_path,
            attempts_by_trial=attempts_by_trial,
            pass_number=pass_number,
        )
        records = load_jsonl(raw_path)
        completed = successful_trial_ids(records)
        _write_manifest(manifest_path, manifest, records, len(schedule))
        if abort:
            break

    records = load_jsonl(raw_path)
    final = _write_manifest(manifest_path, manifest, records, len(schedule))
    if abort:
        raise SystemExit("collection stopped on a model/provider invariant failure")
    if not final["collection_complete"]:
        raise SystemExit("collection remains incomplete after the frozen pass limit")
    final["lifecycle_status"] = "exploratory_data_collected"
    final["utc_collection_completed"] = utc_now()
    atomic_write_json(manifest_path, final)
    print(json.dumps({key: final[key] for key in ("run_id", "completed_calls", "response_records", "transport_attempts", "lifecycle_status")}, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        if args.resume:
            raise SystemExit("--resume requires --execute")
        print(json.dumps(dry_run_report(), indent=2, sort_keys=True))
        return
    if args.run_id is None:
        raise SystemExit("--execute requires --run-id")
    collect(args.run_id, resume=args.resume)


if __name__ == "__main__":
    main()
