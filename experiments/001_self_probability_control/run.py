"""Experiment 001A runner. Experiment 001B intentionally has no runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
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
from harness.parsing import exact_protocol_following, parse_candidate
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

RESULTS_ROOT = HERE / "results"
PREREGISTRATION_PATH = HERE / "PREREGISTRATION.md"
ANALYSIS_PATH = HERE / "analyze.py"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def payload_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def execute_schedule(
    schedule: Iterable[dict],
    sampler: Callable[[dict, object], object],
    *,
    config: dict | None = None,
    prompts: dict | None = None,
) -> list[object]:
    """Consume frozen trials without invoking any randomization in the call loop."""
    config = config or load_config()
    prompts = prompts or load_prompts()
    outputs: list[object] = []
    for trial in schedule:
        payload = build_trial_payload(trial, config, prompts)
        outputs.append(sampler(trial, payload))
    return outputs


def verify_model_inventory(provider: OllamaProvider, config: dict) -> list[dict]:
    inventory = provider.list_models()
    by_name: dict[str, dict] = {}
    for item in inventory:
        for key in (item.get("name"), item.get("model")):
            if key:
                by_name[key] = item
    verified: list[dict] = []
    errors: list[str] = []
    for spec in config["models"]:
        item = by_name.get(spec["model_tag"])
        if item is None:
            errors.append(f"missing installed model: {spec['model_tag']}")
            continue
        digest = item.get("digest", "")
        if not digest.startswith(spec["expected_digest_prefix"]):
            errors.append(
                f"digest mismatch for {spec['model_tag']}: expected prefix "
                f"{spec['expected_digest_prefix']}, got {digest or '(missing)'}"
            )
            continue
        verified.append(
            {
                "model_key": spec["model_key"],
                "requested_model": spec["model_tag"],
                "expected_digest_prefix": spec["expected_digest_prefix"],
                "actual_digest": digest,
                "interface": spec["interface"],
                "family": spec["family"],
                "training_stage": spec["training_stage"],
            }
        )
    if errors:
        raise SystemExit("Ollama inventory preflight failed:\n  " + "\n  ".join(errors))
    return verified


def manifest_for(
    run_id: str,
    run_dir: Path,
    schedule: list[dict],
    config: dict,
    model_ids: list[dict],
) -> dict:
    return create_manifest(
        experiment_id=config["experiment_id"],
        run_id=run_id,
        repo_root=REPO_ROOT,
        preregistration=PREREGISTRATION_PATH,
        runner=Path(__file__),
        analysis=ANALYSIS_PATH,
        config_paths=[CONFIG_PATH, PROMPTS_PATH],
        model_ids=model_ids,
        provider="Ollama local",
        sampling_parameters=config["sampling"],
        planned_calls=len(schedule),
        output_directory=run_dir,
        schedule_sha256=schedule_sha256(schedule),
    )


def dry_run_report() -> dict:
    config = load_config()
    prompts = load_prompts()
    schedule = build_schedule(config)
    model_counts = Counter(row["model_key"] for row in schedule)
    interface_counts = Counter(row["interface"] for row in schedule)
    cell_counts = Counter(row["cell_id"] for row in schedule)
    external = [row for row in schedule if row["arm"] == "EXTERNAL_RANDOMIZER"]
    external_counts: dict[str, dict] = {}
    for row in external:
        key = f"{row['model_key']}__{row['pair_id']}__p{row['first_percent']}"
        external_counts.setdefault(key, {"first": 0, "second": 0})
        external_counts[key][row["external_assignment"]] += 1

    payload_hashes = {
        payload_sha256(build_trial_payload(row, config, prompts)) for row in schedule
    }
    preview = manifest_for(
        "DRY-RUN-PREVIEW",
        RESULTS_ROOT / "runs" / "DRY-RUN-PREVIEW",
        schedule,
        config,
        [
            {
                "model_key": model["model_key"],
                "requested_model": model["model_tag"],
                "expected_digest_prefix": model["expected_digest_prefix"],
                "interface": model["interface"],
                "inventory_not_queried": True,
            }
            for model in config["models"]
        ],
    )
    required_manifest_fields = {
        "experiment_id", "utc_start_time", "git_commit", "git_worktree_dirty",
        "preregistration_sha256", "runner_sha256", "analysis_script_sha256",
        "model_ids", "provider", "sampling_parameters", "planned_calls",
        "completed_calls", "failures", "output_directory",
    }
    return {
        "mode": "dry-run-no-provider-contact",
        "experiment_id": config["experiment_id"],
        "planned_trials": len(schedule),
        "cell_count": len(cell_counts),
        "cell_counts_unique_values": sorted(set(cell_counts.values())),
        "model_counts": dict(sorted(model_counts.items())),
        "interface_counts": dict(sorted(interface_counts.items())),
        "schedule_sha256": schedule_sha256(schedule),
        "unique_prompt_payload_hashes": len(payload_hashes),
        "external_cells": len(external_counts),
        "external_assignment_counts": dict(sorted(external_counts.items())),
        "manifest_required_fields_present": required_manifest_fields <= preview.keys(),
        "manifest_preview": preview,
    }


def collect(run_id: str, *, resume: bool) -> None:
    config = load_config()
    prompts = load_prompts()
    schedule = build_schedule(config)
    provider = OllamaProvider()

    # Inventory access does not load a model. It is nevertheless kept out of
    # --dry-run and performed only on an explicitly requested collection run.
    model_ids = verify_model_inventory(provider, config)
    run_dir = prepare_run_directory(RESULTS_ROOT, run_id, resume=resume)
    manifest_path = run_dir / "manifest.json"
    schedule_path = run_dir / "schedule.jsonl"
    raw_path = run_dir / "raw_responses.jsonl"

    if not resume:
        write_jsonl(schedule_path, schedule)
        atomic_write_json(manifest_path, manifest_for(run_id, run_dir, schedule, config, model_ids))
    else:
        on_disk_schedule = load_jsonl(schedule_path)
        if schedule_sha256(on_disk_schedule) != schedule_sha256(schedule):
            raise SystemExit("refusing resume: frozen on-disk schedule differs from current design")

    existing = load_jsonl(raw_path)
    completed = summarize_records(existing)["successful_trial_ids"]
    pending = [trial for trial in schedule if trial["trial_id"] not in completed]
    attempts_by_trial = Counter(record.get("trial_id") for record in existing)
    model_by_key = {model["model_key"]: model for model in config["models"]}
    print(f"run_id={run_id} planned={len(schedule)} complete={len(completed)} pending={len(pending)}")

    def sampler(trial: dict, payload: object) -> None:
        spec = model_by_key[trial["model_key"]]
        sampling = {
            "temperature": config["sampling"]["temperature"],
            "max_tokens": config["sampling"]["max_tokens"],
            "stop": config["sampling"]["stop"],
        }
        result = provider.sample(
            model=spec["model_tag"], interface=spec["interface"], payload=payload,
            parameters=sampling, max_attempts=config["sampling"]["max_attempts"],
        )
        pair = pair_for_trial(trial, config)
        record = {
            **trial,
            "logical_attempt": attempts_by_trial[trial["trial_id"]] + 1,
            "utc_time": utc_now(),
            "prompt_sha256": payload_sha256(payload),
            **result.to_record(),
            "parsed_choice": parse_candidate(result.raw_response, pair["first"], pair["second"]),
            "protocol_exact": exact_protocol_following(result.raw_response, pair["first"], pair["second"]),
        }
        append_jsonl(raw_path, record)
        attempts_by_trial[trial["trial_id"]] += 1
        manifest = update_collection_manifest(manifest_path, load_jsonl(raw_path), len(schedule))
        status = "FAILED" if result.failure else record["parsed_choice"]
        print(f"{manifest['completed_calls']}/{len(schedule)} {trial['trial_id']} "
              f"attempt={record['logical_attempt']} {status}")
        return None

    try:
        execute_schedule(pending, sampler, config=config, prompts=prompts)
    finally:
        manifest = update_collection_manifest(manifest_path, load_jsonl(raw_path), len(schedule))
        print(json.dumps({k: manifest[k] for k in (
            "lifecycle_status", "planned_calls", "completed_calls", "failures", "transport_attempts"
        )}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="validate only; no provider contact")
    parser.add_argument("--list-models", action="store_true", help="inventory only; no generation")
    parser.add_argument("--run-id", help="immutable 001A run identifier")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        if args.run_id or args.resume or args.list_models:
            parser.error("--dry-run cannot be combined with collection or inventory flags")
        print(json.dumps(dry_run_report(), indent=2, ensure_ascii=False, sort_keys=True))
        return
    if args.list_models:
        if args.run_id or args.resume:
            parser.error("--list-models cannot be combined with collection flags")
        models = OllamaProvider().list_models()
        public = [{"name": item.get("name") or item.get("model"), "digest": item.get("digest")} for item in models]
        print(json.dumps(public, indent=2, sort_keys=True))
        return
    if not args.run_id:
        parser.error("collection requires --run-id; use --dry-run for mechanical validation")
    collect(args.run_id, resume=args.resume)


if __name__ == "__main__":
    main()
