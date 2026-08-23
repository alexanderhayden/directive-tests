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
EXPERIMENT = ROOT / "experiments" / "003_persona_lexical_attractors"
sys.path.insert(0, str(ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


design = load_module("experiment003_design_tests", EXPERIMENT / "design.py")
with patch.dict(sys.modules, {"design": design}):
    runner = load_module("experiment003_runner_tests", EXPERIMENT / "run.py")
    analysis = load_module("experiment003_analysis_tests", EXPERIMENT / "analyze.py")


class PersonaLexicalAttractorTests(unittest.TestCase):
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

    def test_schedule_is_frozen_deterministic_and_exactly_balanced(self):
        self.assertEqual(len(self.schedule), 500)
        self.assertEqual(len({row["trial_id"] for row in self.schedule}), 500)
        self.assertEqual(set(Counter(row["cell_id"] for row in self.schedule).values()), {50})
        self.assertEqual(set(Counter(row["model_key"] for row in self.schedule).values()), {250})
        self.assertEqual(
            Counter(row["condition"] for row in self.schedule),
            Counter({condition: 100 for condition in self.config["conditions"]}),
        )
        self.assertEqual(design.build_schedule(self.config), self.schedule)
        self.assertEqual(
            design.schedule_sha256(self.schedule), self.config["canonical_schedule_sha256"]
        )

    def test_only_persona_field_varies_and_rich_personas_are_matched(self):
        self.assertEqual(self.prompts["conditions"]["BASE"], "")
        payloads = {
            condition: design.build_trial_payload(
                next(row for row in self.schedule if row["condition"] == condition),
                self.config,
                self.prompts,
            )
            for condition in self.config["conditions"]
        }
        self.assertTrue(all(list(payload) == [{"role": "user", "content": payload[0]["content"]}] for payload in payloads.values()))
        for condition, payload in payloads.items():
            self.assertEqual(
                payload[0]["content"],
                self.prompts["message_template"].format(
                    persona_text=self.prompts["conditions"][condition]
                ),
            )
        analytic = self.prompts["conditions"]["ANALYTIC_PERSONA"]
        imaginative = self.prompts["conditions"]["IMAGINATIVE_PERSONA"]
        self.assertEqual(len(analytic.split()), len(imaginative.split()))
        self.assertEqual(
            self.prompts["conditions"]["LABEL_A"].replace("ZELVIQ", "LABEL"),
            self.prompts["conditions"]["LABEL_B"].replace("TORVUN", "LABEL"),
        )

    def test_strict_lexical_grammar_normalizes_and_never_salvages(self):
        parsed = design.parse_lexical_response("  Forest|RIVER  ")
        self.assertEqual(parsed["classification"], "VALID_LEXICAL_PAIR")
        self.assertEqual(parsed["ordered_pair"], "forest|river")
        for raw in ("same|SAME", "word | other", "word|other.", "word|other|third", ""):
            self.assertEqual(
                design.parse_lexical_response(raw)["classification"], "PROTOCOL_FAILURE"
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
        self.assertEqual(report["planned_calls"], 500)

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
            self.assertIs(
                runner.call_provider(anthropic_trial, payload, {"anthropic": "y"}, 4), result
            )
        call.assert_called_once_with(
            api_key="y", model="claude-opus-5", messages=payload,
            parameters={"temperature": 1.0, "max_tokens": 15, "thinking": {"type": "disabled"}},
            max_attempts=4,
        )

    def test_offline_collection_and_analysis_cover_all_cells(self):
        def fake_call(trial, payload, api_keys, max_attempts):
            return runner.ProviderResult(
                requested_model=trial["model_id"], actual_model=trial["model_id"],
                provider=trial["provider"], client="offline_fixture",
                raw_response="Alpha|Beta", finish_reason="stop", response_id="fixture",
                usage=None, sent_parameters={"messages": payload, **trial["request_parameters"]},
                attempts=1,
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
        self.assertEqual(provider_call.call_count, 500)
        self.assertTrue(manifest["collection_complete"])
        summary = analysis.analyze_records(records, self.schedule, self.config)
        self.assertEqual(len(summary["cells"]), 10)
        self.assertEqual(len(summary["between_condition_vs_within_condition"]), 24)
        self.assertTrue(all(cell["PROTOCOL_FAILURE"] == 0 for cell in summary["cells"]))
        self.assertTrue(
            all(row["js_distance_to_BASE"] == 0.0 for row in summary["between_condition_vs_within_condition"])
        )


if __name__ == "__main__":
    unittest.main()
