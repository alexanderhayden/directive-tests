#!/usr/bin/env python3
"""Repository-local credential and protected-artifact safety gate."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".pyc"}
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv"}
FORBIDDEN_NAMES = {
    "protected.zip",
    "wordpairs_10.json",
    "leak_patterns.txt",
    "data_archive.zip",
    "results_archive.zip",
    "CANARY.txt",
}
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Anthropic key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "OpenRouter key": re.compile(r"\bsk-or-v1-[A-Za-z0-9_-]{20,}\b"),
}


def repository_files(root: Path = ROOT) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [root / line for line in result.stdout.splitlines() if line]


def scan_paths(paths: list[Path], root: Path) -> list[str]:
    """Return safe-to-print findings without printing secret contents."""
    hits: list[str] = []
    for path in paths:
        rel = path.relative_to(root)

        # Filename rejection deliberately precedes suffix handling. Protected
        # archives are forbidden even though arbitrary binary archives are not
        # opened for content scanning.
        if path.name in FORBIDDEN_NAMES:
            hits.append(f"forbidden protected artifact name: {rel}")
            continue

        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in rel.parts):
            continue

        text = path.read_text(errors="ignore")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                hits.append(f"{label}: {rel}")
    return hits


def main() -> int:
    hits = scan_paths(repository_files(ROOT), ROOT)
    if hits:
        print("SAFETY CHECK FAILED")
        for hit in hits:
            print("  " + hit)
        return 1
    print("clean - no credential patterns or forbidden protected artifacts found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
