"""Run manifests and overwrite-safe lifecycle transitions."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from harness.logging import summarize_records

COMPLETED_STATES = {"pilot_data_collected", "primary_result_frozen", "posthoc_diagnostics"}
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_state(repo_root: Path) -> dict:
    def run(*args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=repo_root, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    try:
        commit = run("rev-parse", "HEAD")
        branch = run("branch", "--show-current") or None
        porcelain = run("status", "--porcelain=v1")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": None, "branch": None, "dirty": None, "porcelain": []}
    return {
        "commit": commit,
        "branch": branch,
        "dirty": bool(porcelain),
        "porcelain": porcelain.splitlines() if porcelain else [],
    }


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)


def prepare_run_directory(results_root: Path, run_id: str, *, resume: bool = False) -> Path:
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("run_id may contain only letters, digits, dot, underscore, and hyphen")
    run_dir = results_root / "runs" / run_id
    manifest_path = run_dir / "manifest.json"
    if run_dir.exists():
        if not manifest_path.exists():
            raise FileExistsError(f"existing run directory has no manifest: {run_dir}")
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("lifecycle_status") in COMPLETED_STATES:
            raise FileExistsError(f"refusing to overwrite completed run: {run_dir}")
        if not resume:
            raise FileExistsError(f"run exists but is incomplete; pass --resume: {run_dir}")
        return run_dir
    if resume:
        raise FileNotFoundError(f"cannot resume missing run: {run_dir}")
    run_dir.mkdir(parents=True)
    return run_dir


def create_manifest(
    *,
    experiment_id: str,
    run_id: str,
    repo_root: Path,
    preregistration: Path,
    runner: Path,
    analysis: Path,
    config_paths: list[Path],
    model_ids: list[dict],
    provider: str,
    sampling_parameters: dict,
    planned_calls: int,
    output_directory: Path,
    schedule_sha256: str,
) -> dict:
    state = git_state(repo_root)
    return {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "run_id": run_id,
        "utc_start_time": utc_now(),
        "git_commit": state["commit"],
        "git_branch": state["branch"],
        "git_worktree_dirty": state["dirty"],
        "git_status_porcelain": state["porcelain"],
        "preregistration_sha256": sha256_file(preregistration),
        "runner_sha256": sha256_file(runner),
        "analysis_script_sha256": sha256_file(analysis),
        "config_sha256": {str(path.relative_to(repo_root)): sha256_file(path) for path in config_paths},
        "schedule_sha256": schedule_sha256,
        "model_ids": model_ids,
        "provider": provider,
        "sampling_parameters": sampling_parameters,
        "planned_calls": planned_calls,
        "completed_calls": 0,
        "failures": 0,
        "transport_attempts": 0,
        "output_directory": str(output_directory.resolve()),
        "lifecycle_status": "pilot_collecting",
        "primary_result": None,
    }


def update_collection_manifest(manifest_path: Path, records: list[dict], planned_calls: int) -> dict:
    manifest = json.loads(manifest_path.read_text())
    summary = summarize_records(records)
    manifest.update(
        {
            "completed_calls": summary["completed_calls"],
            "failures": summary["failures"],
            "transport_attempts": summary["transport_attempts"],
            "last_updated_utc": utc_now(),
        }
    )
    if summary["completed_calls"] == planned_calls:
        manifest["lifecycle_status"] = "pilot_data_collected"
        manifest["utc_collection_completed"] = utc_now()
    atomic_write_json(manifest_path, manifest)
    return manifest


def freeze_primary_result(manifest_path: Path, result_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("lifecycle_status") != "pilot_data_collected":
        raise ValueError("primary result can be frozen only after complete pilot collection")
    manifest["primary_result"] = {
        "path": str(result_path),
        "sha256": sha256_file(result_path),
        "frozen_utc": utc_now(),
    }
    manifest["lifecycle_status"] = "primary_result_frozen"
    atomic_write_json(manifest_path, manifest)
    return manifest
