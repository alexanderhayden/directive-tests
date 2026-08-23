"""Approval-gated direct-provider runner for Experiment 004."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.logging import append_jsonl, load_jsonl, write_jsonl
from harness.manifests import atomic_write_json, prepare_run_directory
from harness.parsing import strict_candidate_classification
from harness.providers import ProviderResult
from harness.providers.anthropic import sample_messages
from harness.providers.openai import sample_chat

from design import (
    CONFIG_PATH,
    HERE,
    PROMPTS_PATH,
    build_trial_payload,
    file_sha256,
    load_config,
    load_prompts,
    pair_for_trial,
    schedule_sha256,
    validate_frozen_schedule,
)

RESULTS_ROOT = HERE / "results"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def payload_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def successful_trial_ids(records: list[dict]) -> set[str]:
    return {
        record["trial_id"]
        for record in records
        if record.get("failure") is None
        and record.get("model_invariant_error") is None
        and record.get("trial_id")
    }


def manifest_accounting(records: list[dict], planned: int) -> dict:
    completed = successful_trial_ids(records)
    return {
        "completed_calls": len(completed),
        "planned_calls": planned,
        "transport_failure_records": sum(record.get("failure") is not None for record in records),
        "model_invariant_failure_records": sum(
            record.get("model_invariant_error") is not None for record in records
        ),
        "transport_attempts": sum(int(record.get("attempts", 0)) for record in records),
        "collection_complete": len(completed) == planned,
    }


def dry_run_report() -> dict:
    config = load_config()
    prompts = load_prompts(config)
    schedule = validate_frozen_schedule(config)
    payloads = [build_trial_payload(row, config, prompts) for row in schedule]
    cell_counts = Counter(row["cell_id"] for row in schedule)
    return {
        "mode": "dry-run-no-provider-contact",
        "provider_contact": False,
        "credential_access": False,
        "exploratory": True,
        "experiment_id": config["experiment_id"],
        "proposed_run_id": config["proposed_run_id"],
        "prompt_source_sha256": file_sha256(PROMPTS_PATH),
        "config_sha256": file_sha256(CONFIG_PATH),
        "schedule_sha256": schedule_sha256(schedule),
        "planned_calls": len(schedule),
        "cell_count": len(cell_counts),
        "cell_counts_unique_values": sorted(set(cell_counts.values())),
        "calls_by_model": dict(sorted(Counter(row["model_key"] for row in schedule).items())),
        "calls_by_template": dict(sorted(Counter(row["template"] for row in schedule).items())),
        "calls_by_direction": dict(
            sorted(Counter(row["direction"] for row in schedule).items())
        ),
        "calls_by_directive_order": dict(
            sorted(Counter(row["directive_order"] for row in schedule).items())
        ),
        "calls_by_pair": dict(sorted(Counter(row["pair_id"] for row in schedule).items())),
        "unique_prompt_payloads": len({payload_sha256(payload) for payload in payloads}),
        "models": [
            {
                "model_key": model["model_key"],
                "model_id": model["model_id"],
                "provider": model["provider"],
                "request_parameters": model["request_parameters"],
            }
            for model in config["models"]
        ],
    }


def load_api_keys() -> dict[str, str]:
    try:
        from dotenv import load_dotenv
    except ImportError as error:
        raise SystemExit("python-dotenv is required for --execute") from error
    load_dotenv(REPO_ROOT / ".env")
    keys = {
        "openai": os.environ.get("OPENAI_API_KEY", ""),
        "anthropic": os.environ.get("ANTHROPIC_API_KEY", ""),
    }
    missing = [provider for provider, value in keys.items() if not value]
    if missing:
        names = ", ".join(provider.upper() + "_API_KEY" for provider in missing)
        raise SystemExit(f"missing required environment variables: {names}")
    return keys


def call_provider(
    trial: dict, payload: list[dict], api_keys: dict[str, str], max_attempts: int
) -> ProviderResult:
    if trial["provider"] == "openai":
        return sample_chat(
            api_key=api_keys["openai"], model=trial["model_id"], messages=payload,
            parameters=trial["request_parameters"], max_attempts=max_attempts,
        )
    if trial["provider"] == "anthropic":
        return sample_messages(
            api_key=api_keys["anthropic"], model=trial["model_id"], messages=payload,
            parameters=trial["request_parameters"], max_attempts=max_attempts,
        )
    raise ValueError(f"unknown provider: {trial['provider']}")


def write_manifest(path: Path, manifest: dict, records: list[dict], planned: int) -> dict:
    updated = {**manifest, **manifest_accounting(records, planned), "last_updated_utc": utc_now()}
    atomic_write_json(path, updated)
    return updated


def collect(run_id: str, *, resume: bool, workers: int) -> None:
    if workers < 1:
        raise SystemExit("--workers must be positive")
    config = load_config()
    prompts = load_prompts(config)
    schedule = validate_frozen_schedule(config)
    api_keys = load_api_keys()
    run_dir = prepare_run_directory(RESULTS_ROOT, run_id, resume=resume)
    schedule_path = run_dir / "schedule.jsonl"
    raw_path = run_dir / "responses.jsonl"
    manifest_path = run_dir / "manifest.json"
    frozen_models = [
        {
            "model_key": model["model_key"], "model_id": model["model_id"],
            "provider": model["provider"], "request_parameters": model["request_parameters"],
        }
        for model in config["models"]
    ]
    if not resume:
        write_jsonl(schedule_path, schedule)
        manifest = {
            "schema_version": 1, "experiment_id": config["experiment_id"],
            "designation": config["designation"], "exploratory": True,
            "run_id": run_id, "created_utc": utc_now(),
            "config_sha256": file_sha256(CONFIG_PATH),
            "prompt_source_sha256": file_sha256(PROMPTS_PATH),
            "schedule_sha256": schedule_sha256(schedule), "models": frozen_models,
            "workers": workers,
        }
        write_manifest(manifest_path, manifest, [], len(schedule))
    else:
        if not manifest_path.is_file() or not schedule_path.is_file():
            raise SystemExit("cannot resume: run manifest or schedule is missing")
        manifest = json.loads(manifest_path.read_text())
        if load_jsonl(schedule_path) != schedule:
            raise SystemExit("cannot resume: on-disk schedule differs from canonical schedule")
        if manifest.get("config_sha256") != file_sha256(CONFIG_PATH):
            raise SystemExit("cannot resume: config differs from original run")
        if manifest.get("models") != frozen_models:
            raise SystemExit("cannot resume: model settings differ from original run")

    existing = load_jsonl(raw_path)
    completed = successful_trial_ids(existing)
    pending = [row for row in schedule if row["trial_id"] not in completed]
    attempts_by_trial = Counter(row.get("trial_id") for row in existing)
    print(
        f"run_id={run_id} planned={len(schedule)} complete={len(completed)} "
        f"pending={len(pending)} workers={workers}", flush=True,
    )
    executor = ThreadPoolExecutor(max_workers=workers)
    futures: dict[Future, tuple[dict, list[dict]]] = {}
    pending_iter = iter(pending)

    def submit_next() -> bool:
        try:
            trial = next(pending_iter)
        except StopIteration:
            return False
        payload = build_trial_payload(trial, config, prompts)
        future = executor.submit(call_provider, trial, payload, api_keys, config["max_attempts"])
        futures[future] = (trial, payload)
        return True

    try:
        for _ in range(min(workers, len(pending))):
            submit_next()
        while futures:
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                trial, payload = futures.pop(future)
                result = future.result()
                invariant = None
                if result.failure is None and result.actual_model != trial["model_id"]:
                    invariant = (
                        f"actual model {result.actual_model!r} differs from requested "
                        f"{trial['model_id']!r}"
                    )
                pair = pair_for_trial(trial, config)
                strict = None
                if result.failure is None and invariant is None:
                    parsed = strict_candidate_classification(
                        result.raw_response, pair["first"], pair["second"]
                    )
                    strict = f"exact_{parsed}" if parsed in {"first", "second"} else parsed
                record = {
                    **trial, "logical_attempt": attempts_by_trial[trial["trial_id"]] + 1,
                    "utc_time": utc_now(), "prompt_sha256": payload_sha256(payload),
                    **result.to_record(), "model_invariant_error": invariant,
                    "primary_classification": strict,
                }
                append_jsonl(raw_path, record)
                attempts_by_trial[trial["trial_id"]] += 1
                existing.append(record)
                manifest = write_manifest(manifest_path, manifest, existing, len(schedule))
                status = (
                    "MODEL_INVARIANT_FAILURE" if invariant else "TRANSPORT_FAILURE"
                    if result.failure else strict
                )
                print(
                    f"{manifest['completed_calls']}/{len(schedule)} {trial['trial_id']} {status}",
                    flush=True,
                )
                if invariant:
                    raise SystemExit(f"aborting on model invariant failure: {invariant}")
                submit_next()
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    final = write_manifest(manifest_path, manifest, existing, len(schedule))
    if not final["collection_complete"]:
        raise SystemExit("collection incomplete; retain failures and rerun with --resume")
    print(f"collection complete: {len(schedule)}/{len(schedule)}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--workers", type=int)
    args = parser.parse_args()
    if args.dry_run and args.execute:
        parser.error("choose --dry-run or --execute, not both")
    if not args.execute:
        if args.run_id or args.resume:
            parser.error("--run-id and --resume require --execute")
        print(json.dumps(dry_run_report(), indent=2, ensure_ascii=False, sort_keys=True))
        return
    if not args.run_id:
        parser.error("--execute requires --run-id")
    config = load_config()
    collect(args.run_id, resume=args.resume, workers=args.workers or config["default_workers"])


if __name__ == "__main__":
    main()
