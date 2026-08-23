"""Raw JSON/JSONL persistence and failure accounting."""

from __future__ import annotations

import json
import os
from pathlib import Path


def append_jsonl(path: Path, record: dict, *, durable: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        if durable:
            os.fsync(handle.fileno())


def write_jsonl(path: Path, records: list[dict]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    if not path.exists():
        return records
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
    return records


def summarize_records(records: list[dict]) -> dict:
    successful_ids = {
        record["trial_id"]
        for record in records
        if record.get("trial_id") and record.get("failure") is None
    }
    return {
        "record_count": len(records),
        "completed_calls": len(successful_ids),
        "failures": sum(record.get("failure") is not None for record in records),
        "transport_attempts": sum(int(record.get("attempts", 0)) for record in records),
        "successful_trial_ids": successful_ids,
    }
