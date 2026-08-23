import tempfile
import unittest
from pathlib import Path

from harness.logging import append_jsonl, load_jsonl, summarize_records


class LoggingTests(unittest.TestCase):
    def test_raw_records_and_failure_accounting(self):
        records = [
            {"trial_id": "a", "failure": "timeout", "attempts": 4},
            {"trial_id": "a", "failure": None, "attempts": 1},
            {"trial_id": "b", "failure": None, "attempts": 2},
            {"trial_id": "b", "failure": None, "attempts": 1},
        ]
        summary = summarize_records(records)
        self.assertEqual(summary["record_count"], 4)
        self.assertEqual(summary["completed_calls"], 2)
        self.assertEqual(summary["failures"], 1)
        self.assertEqual(summary["transport_attempts"], 8)

    def test_jsonl_append_retains_every_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.jsonl"
            append_jsonl(path, {"trial_id": "a", "failure": "timeout"}, durable=False)
            append_jsonl(path, {"trial_id": "a", "failure": None}, durable=False)
            self.assertEqual(len(load_jsonl(path)), 2)


if __name__ == "__main__":
    unittest.main()
