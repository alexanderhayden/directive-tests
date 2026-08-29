from __future__ import annotations

import importlib.util
import hashlib
import io
import json
import re
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "008_claude_10turn_forensic_replication"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EXPERIMENT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


design = load_module("experiment008_design_tests", EXPERIMENT / "design.py")
with patch.dict(sys.modules, {"design": design}):
    runner = load_module("experiment008_runner_tests", EXPERIMENT / "run.py")
    analysis = load_module("experiment008_analysis_tests", EXPERIMENT / "analyze.py")


class ClaudeTenTurnForensicReplicationTests(unittest.TestCase):
    def setUp(self):
        self.config = design.load_config()
        self.material = design.load_historical_material(self.config)
        self.schedule = design.validate_frozen_schedule(self.config)

    def test_historical_sources_are_hash_locked_and_unchanged_by_loading(self):
        root = design.historical_root(self.config)
        before = {
            label: design.file_sha256(root / record["path"])
            for label, record in self.config["protected_sources"].items()
        }
        design.load_historical_material(self.config)
        after = {
            label: design.file_sha256(root / record["path"])
            for label, record in self.config["protected_sources"].items()
        }
        self.assertEqual(before, after)
        self.assertEqual(
            before,
            {
                label: record["sha256"]
                for label, record in self.config["protected_sources"].items()
            },
        )

    def test_exact_payload_hashes_lengths_and_candidate_hashes(self):
        for turns in (9, 10, 11):
            metrics = design.payload_metrics(self.material.payloads[turns])
            expected = self.config["payloads"][str(turns)]
            for key, value in metrics.items():
                self.assertEqual(value, expected[key])
        first, second = self.material.candidates
        self.assertEqual(
            design.stable_hash([first, second]),
            self.config["candidate_hashes"]["ordered_pair_sha256"],
        )

    def test_model_endpoint_and_omitted_parameters_are_frozen(self):
        model = self.config["model"]
        self.assertEqual(model["model_id"], "claude-opus-5")
        self.assertEqual(model["provider"], "anthropic")
        self.assertEqual(model["expected_provider"], "Anthropic")
        self.assertEqual(
            model["request_parameters"],
            {"temperature": 1.0, "max_tokens": 15, "thinking": {"type": "disabled"}},
        )
        self.assertEqual(model["max_attempts"], 4)
        self.assertIn("top_p", model["omitted_parameters"])
        self.assertIn("seed", model["omitted_parameters"])

    def test_schedule_is_deterministic_balanced_and_frozen(self):
        self.assertEqual(len(self.schedule), 600)
        self.assertEqual(len({row["trial_id"] for row in self.schedule}), 600)
        self.assertEqual(Counter(row["turns"] for row in self.schedule), {9: 200, 10: 200, 11: 200})
        self.assertEqual(design.build_schedule(self.config), self.schedule)
        self.assertEqual(
            design.schedule_sha256(self.schedule),
            self.config["canonical_schedule_sha256"],
        )

    def test_historical_parser_semantics_are_not_tightened(self):
        candidates = ("ALPHA", "BETA")
        cases = {
            "ALPHA": "A",
            "  My answer is: beta because": "B",
            "ALPHA because": "A",
            "punctuation-only !!!": "OTHER",
            "": "OTHER",
        }
        for raw, expected in cases.items():
            self.assertEqual(
                design.classify_response(raw, candidates)["classification"], expected
            )

    def test_dry_run_has_no_provider_or_credential_contact(self):
        with patch.object(runner, "sample_messages") as provider, patch.object(
            runner, "load_api_key"
        ) as credentials:
            report = runner.dry_run_report()
        provider.assert_not_called()
        credentials.assert_not_called()
        self.assertFalse(report["provider_contact"])
        self.assertFalse(report["credential_access"])
        self.assertEqual(report["planned_calls"], 600)
        self.assertEqual(report["schedule_sha256"], self.config["canonical_schedule_sha256"])

    def test_provider_adapter_receives_exact_historical_parameters(self):
        trial = self.schedule[0]
        payload = self.material.payloads[trial["turns"]]
        result = object()
        with patch.object(runner, "sample_messages", return_value=result) as provider:
            self.assertIs(runner.call_provider(trial, payload, "key", self.config), result)
        provider.assert_called_once_with(
            api_key="key",
            model="claude-opus-5",
            messages=payload,
            parameters={"temperature": 1.0, "max_tokens": 15, "thinking": {"type": "disabled"}},
            max_attempts=4,
        )

    def test_synthetic_complete_collection_and_analysis(self):
        def fake_call(trial, payload, api_key, config):
            raw = self.material.candidates[1] if trial["turns"] == 10 and trial["repeat"] < 10 else self.material.candidates[0]
            return runner.ProviderResult(
                requested_model="claude-opus-5",
                actual_model="claude-opus-5",
                provider="Anthropic",
                client="offline_fixture",
                raw_response=raw,
                finish_reason="end_turn",
                response_id=f"fixture-{trial['trial_id']}",
                usage={
                    "input_tokens": self.config["payloads"][str(trial["turns"])]["historical_input_tokens"],
                    "output_tokens": 4,
                    "service_tier": "fixture",
                    "inference_geo": "fixture",
                },
                sent_parameters={
                    "model": "claude-opus-5",
                    "messages": payload,
                    **self.config["model"]["request_parameters"],
                },
                attempts=1,
            )

        with tempfile.TemporaryDirectory() as directory, patch.object(
            runner, "RESULTS_ROOT", Path(directory)
        ), patch.object(runner, "load_api_key", return_value="fixture-key"), patch.object(
            runner, "call_provider", side_effect=fake_call
        ) as provider, patch("sys.stdout", new=io.StringIO()):
            runner.collect(self.config["immutable_run_id"], resume=False)
            run_dir = Path(directory) / "runs" / self.config["immutable_run_id"]
            records = runner.load_jsonl(run_dir / "responses.jsonl")
            manifest = json.loads((run_dir / "manifest.json").read_text())
        self.assertEqual(provider.call_count, 600)
        self.assertTrue(manifest["collection_complete"])
        self.assertEqual(len(records), 600)
        self.assertTrue(all("messages" not in row["sent_nonmessage_parameters"] for row in records))
        self.assertTrue(all("sent_parameters" not in row for row in records))
        summary = analysis.analyze_records(records, self.schedule, self.config)
        self.assertEqual(summary["conditions"]["9"]["historical_successes"], 200)
        self.assertEqual(summary["conditions"]["10"]["historical_successes"], 190)
        self.assertEqual(summary["conditions"]["11"]["historical_successes"], 200)
        self.assertAlmostEqual(summary["contrasts"]["turn10_minus_pooled_turn9_turn11"], -0.05)
        self.assertTrue(
            summary["primary_forensic_question"][
                "exact_10_turn_condition_below_both_contemporaneous_neighbors"
            ]
        )

    def test_tracked_experiment_files_do_not_contain_candidate_literals(self):
        candidates = [re.escape(value) for value in self.material.candidates]
        pattern = re.compile(r"(?i)(?<![A-Za-z])(?:" + "|".join(candidates) + r")(?![A-Za-z])")
        paths = [
            path
            for path in EXPERIMENT.rglob("*")
            if path.is_file() and "results" not in path.parts and path.suffix != ".pyc"
        ]
        paths.append(ROOT / "tests" / "test_experiment_008.py")
        for path in paths:
            with self.subTest(path=path):
                self.assertIsNone(pattern.search(path.read_text(errors="ignore")))

    def test_tracked_experiment_files_do_not_copy_protected_source_lines(self):
        root = design.historical_root(self.config)
        tracked_paths = [
            path
            for path in EXPERIMENT.rglob("*")
            if path.is_file() and "results" not in path.parts and path.suffix != ".pyc"
        ]
        tracked_paths.append(ROOT / "tests" / "test_experiment_008.py")
        tracked_text = "\n".join(path.read_text(errors="ignore") for path in tracked_paths)
        for label, record in self.config["protected_sources"].items():
            protected_text = (root / record["path"]).read_text(encoding="utf-8")
            for line in protected_text.splitlines():
                substantial = line.strip()
                if len(substantial) < 32 or substantial not in tracked_text:
                    continue
                fingerprint = hashlib.sha256(substantial.encode()).hexdigest()
                self.fail(
                    f"protected source line copied: label={label} sha256={fingerprint}"
                )


if __name__ == "__main__":
    unittest.main()
