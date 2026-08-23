from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "004_directive_ownership_conflict"
sys.path.insert(0, str(ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


design = load_module("experiment004_design_tests", EXPERIMENT / "design.py")
with patch.dict(sys.modules, {"design": design}):
    runner = load_module("experiment004_runner_tests", EXPERIMENT / "run.py")
    analysis = load_module("experiment004_analysis_tests", EXPERIMENT / "analyze.py")


class DirectiveOwnershipConflictTests(unittest.TestCase):
    def setUp(self):
        self.config = design.load_config()
        self.prompts = design.load_prompts(self.config)
        self.schedule = design.validate_frozen_schedule(self.config)

    def test_frozen_models_and_exact_provider_parameters(self):
        models = {model["model_key"]: model for model in self.config["models"]}
        self.assertEqual(models["gpt41_20250414"]["model_id"], "gpt-4.1-2025-04-14")
        self.assertEqual(
            models["gpt41_20250414"]["request_parameters"],
            {"temperature": 1.0, "max_tokens": 15},
        )
        self.assertEqual(models["claude_opus_5"]["model_id"], "claude-opus-5")
        self.assertEqual(
            models["claude_opus_5"]["request_parameters"],
            {"temperature": 1.0, "max_tokens": 15, "thinking": {"type": "disabled"}},
        )

    def test_schedule_has_exact_320_call_factorial_balance(self):
        self.assertEqual(len(self.schedule), 320)
        self.assertEqual(len({row["trial_id"] for row in self.schedule}), 320)
        self.assertEqual(set(Counter(row["cell_id"] for row in self.schedule).values()), {10})
        self.assertEqual(Counter(row["template"] for row in self.schedule), Counter({t: 80 for t in self.config["templates"]}))
        self.assertEqual(Counter(row["direction"] for row in self.schedule), Counter({d: 160 for d in self.config["directions"]}))
        self.assertEqual(design.schedule_sha256(self.schedule), self.config["canonical_schedule_sha256"])
        for row in self.schedule:
            if row["template"].startswith("AGREEMENT_"):
                self.assertEqual(row["active_assignment"], row["secondary_assignment"])
            else:
                self.assertNotEqual(row["active_assignment"], row["secondary_assignment"])

    def test_four_templates_are_scope_matched_and_reversal_symmetric(self):
        templates = self.prompts["templates"]
        self.assertEqual(set(templates), set(self.config["templates"]))
        self.assertEqual(templates["CONFLICT_DESCRIBED"], templates["AGREEMENT_DESCRIBED"])
        self.assertEqual(templates["CONFLICT_QUOTED"], templates["AGREEMENT_QUOTED"])
        described_middle = templates["CONFLICT_DESCRIBED"].splitlines()[1]
        quoted_middle = templates["CONFLICT_QUOTED"].splitlines()[1]
        self.assertIn("separately described assistant", described_middle)
        self.assertIn("currently producing this response", quoted_middle)
        self.assertLessEqual(abs(len(described_middle.split()) - len(quoted_middle.split())), 2)
        for template in self.config["templates"]:
            first_trial = next(
                row for row in self.schedule if row["template"] == template and row["direction"] == "active_first"
            )
            second_trial = next(
                row for row in self.schedule if row["template"] == template and row["direction"] == "active_second" and row["pair_id"] == first_trial["pair_id"] and row["model_key"] == first_trial["model_key"]
            )
            self.assertNotEqual(
                design.build_trial_payload(first_trial, self.config, self.prompts),
                design.build_trial_payload(second_trial, self.config, self.prompts),
            )

    def test_dry_run_has_zero_provider_and_credential_contact(self):
        with patch.object(runner, "sample_chat") as openai_call, patch.object(
            runner, "sample_messages"
        ) as anthropic_call, patch.object(runner, "load_api_keys") as credential_call:
            report = runner.dry_run_report()
        openai_call.assert_not_called()
        anthropic_call.assert_not_called()
        credential_call.assert_not_called()
        self.assertFalse(report["provider_contact"])
        self.assertFalse(report["credential_access"])
        self.assertEqual(report["planned_calls"], 320)

    def test_provider_calls_reuse_adapters_with_exact_parameters(self):
        payload = [{"role": "user", "content": "fixture"}]
        result = SimpleNamespace()
        openai_trial = next(row for row in self.schedule if row["provider"] == "openai")
        anthropic_trial = next(row for row in self.schedule if row["provider"] == "anthropic")
        with patch.object(runner, "sample_chat", return_value=result) as call:
            self.assertIs(runner.call_provider(openai_trial, payload, {"openai": "x"}, 4), result)
        call.assert_called_once_with(
            api_key="x", model="gpt-4.1-2025-04-14", messages=payload,
            parameters={"temperature": 1.0, "max_tokens": 15}, max_attempts=4,
        )
        with patch.object(runner, "sample_messages", return_value=result) as call:
            self.assertIs(runner.call_provider(anthropic_trial, payload, {"anthropic": "y"}, 4), result)
        call.assert_called_once_with(
            api_key="y", model="claude-opus-5", messages=payload,
            parameters={"temperature": 1.0, "max_tokens": 15, "thinking": {"type": "disabled"}},
            max_attempts=4,
        )

    def test_offline_active_routing_collection_and_analysis(self):
        def fake_call(trial, payload, api_keys, max_attempts):
            pair = design.pair_for_trial(trial, self.config)
            return runner.ProviderResult(
                requested_model=trial["model_id"], actual_model=trial["model_id"],
                provider=trial["provider"], client="offline_fixture",
                raw_response=pair[trial["active_assignment"]], finish_reason="stop",
                response_id="fixture", usage=None,
                sent_parameters={"messages": payload, **trial["request_parameters"]}, attempts=1,
            )

        with tempfile.TemporaryDirectory() as directory, patch.object(
            runner, "RESULTS_ROOT", Path(directory)
        ), patch.object(runner, "load_api_keys", return_value={}), patch.object(
            runner, "call_provider", side_effect=fake_call
        ) as provider_call, patch("sys.stdout", new=io.StringIO()):
            runner.collect("offline-fixture", resume=False, workers=4)
            run_dir = Path(directory) / "runs" / "offline-fixture"
            manifest = json.loads((run_dir / "manifest.json").read_text())
            records = runner.load_jsonl(run_dir / "responses.jsonl")
        self.assertEqual(provider_call.call_count, 320)
        self.assertTrue(manifest["collection_complete"])
        summary = analysis.analyze_records(records, self.schedule, self.config)
        self.assertEqual(len(summary["cells"]), 32)
        self.assertEqual(summary["overall_conflict_routing"]["active_directive_compliance_rate"], 1.0)
        self.assertEqual(summary["overall_conflict_routing"]["secondary_directive_compliance_rate"], 0.0)
        self.assertEqual(summary["overall_agreement_controls"]["agreement_control_accuracy"], 1.0)
        self.assertTrue(all(cell["PROTOCOL_FAILURE"] == 0 for cell in summary["cells"]))


if __name__ == "__main__":
    unittest.main()
