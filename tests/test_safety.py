from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "check_safety.py"
SPEC = importlib.util.spec_from_file_location("check_safety", MODULE_PATH)
check_safety = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_safety)


class SafetyGateTests(unittest.TestCase):
    def test_forbidden_archives_rejected_before_binary_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("protected.zip", "data_archive.zip", "results_archive.zip"):
                with self.subTest(name=name):
                    path = root / name
                    path.write_bytes(b"\x00\xffnot-text")
                    hits = check_safety.scan_paths([path], root)
                    self.assertEqual(hits, [f"forbidden protected artifact name: {name}"])

    def test_unrelated_binary_zip_allowed_without_decoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "benign-results.zip"
            path.write_bytes(b"\x00\xff\x80not-utf8")
            with patch.object(Path, "read_text", side_effect=AssertionError("binary was decoded")):
                self.assertEqual(check_safety.scan_paths([path], root), [])


if __name__ == "__main__":
    unittest.main()
