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
EXPERIMENT = ROOT / "experiments" / "007_persona_attractor_blacklist"
sys.path.insert(0, str(ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


design = load_module("experiment007_design_tests", EXPERIMENT / "design.py")
with patch.dict(sys.modules, {"design": design}):
    runner = load_module("experiment007_runner_tests", EXPERIMENT / "run.py")
    analysis = load_module("experiment007_analysis_tests", EXPERIMENT / "analyze.py")


class PersonaAttractorBlacklistTests(unittest.TestCase):
    def setUp(self):
        self.config = design.load_config()
        self.prompts = design.load_prompts(self.config)
        self.schedule = design.validate_frozen_schedule(self.config)

    def test_frozen_model_and_exact_provider_parameters(self):
        model = self.config["model"]
        self.assertEqual(model["model_id"], "claude-opus-5")
        self.assertEqual(model["provider"], "anthropic")
        self.assertEqual(
            model["request_parameters"],
            {"temperature": 1.0, "max_tokens": 15, "thinking": {"type": "disabled"}},
        )

    def test_schedule_is_exactly_balanced_and_frozen(self):
        self.assertEqual(len(self.schedule), 450)
        self.assertEqual(len({row["trial_id"] for row in self.schedule}), 450)
        self.assertEqual(len({row["cell_id"] for row in self.schedule}), 9)
        self.assertEqual(set(Counter(row["cell_id"] for row in self.schedule).values()), {50})
        self.assertEqual(
            Counter(row["persona"] for row in self.schedule),
            Counter({persona: 150 for persona in self.config["personas"]}),
        )
        self.assertEqual(
            Counter(row["restriction"] for row in self.schedule),
            Counter({restriction: 150 for restriction in self.config["restrictions"]}),
        )
        self.assertEqual(design.build_schedule(self.config), self.schedule)
        self.assertEqual(
            design.schedule_sha256(self.schedule), self.config["canonical_schedule_sha256"]
        )

    def test_personas_exactly_match_experiment_003(self):
        experiment003 = json.loads(
            (ROOT / "experiments" / "003_persona_lexical_attractors" / "prompts.json").read_text()
        )
        for persona in self.config["personas"]:
            self.assertEqual(
                self.prompts["personas"][persona], experiment003["conditions"][persona]
            )
        self.assertEqual(self.prompts["personas"]["BASE"], "")
        for persona in self.config["personas"]:
            for restriction in self.config["restrictions"]:
                trial = next(
                    row
                    for row in self.schedule
                    if row["persona"] == persona and row["restriction"] == restriction
                )
                payload = design.build_trial_payload(trial, self.config, self.prompts)
                self.assertEqual(len(payload), 1)
                self.assertEqual(payload[0]["role"], "user")
                self.assertIn(self.prompts["restrictions"][restriction], payload[0]["content"])

    def test_strict_parser_separates_blacklist_violations(self):
        valid = design.parse_lexical_response("  Forest|RIVER  ", "lantern")
        self.assertEqual(valid["classification"], "VALID_LEXICAL_PAIR")
        self.assertEqual(valid["ordered_pair"], "forest|river")
        for raw in ("Lantern|river", "river|LANTERN"):
            self.assertEqual(
                design.parse_lexical_response(raw, "lantern")["classification"],
                "BAN_VIOLATION",
            )
        self.assertEqual(
            design.parse_lexical_response("VORPAX|river", "vorpax")["classification"],
            "BAN_VIOLATION",
        )
        for raw in ("same|SAME", "word | other", "word|other.", "word|other|third", ""):
            self.assertEqual(
                design.parse_lexical_response(raw, "lantern")["classification"],
                "PROTOCOL_FAILURE",
            )

    def test_dry_run_has_zero_provider_and_credential_contact(self):
        with patch.object(runner, "sample_messages") as anthropic_call, patch.object(
            runner, "load_api_keys"
        ) as credential_call:
            report = runner.dry_run_report()
        anthropic_call.assert_not_called()
        credential_call.assert_not_called()
        self.assertFalse(report["provider_contact"])
        self.assertFalse(report["credential_access"])
        self.assertEqual(report["planned_calls"], 450)
        self.assertEqual(report["calls_by_persona"], {persona: 150 for persona in self.config["personas"]})
        self.assertEqual(
            report["calls_by_restriction"],
            {restriction: 150 for restriction in self.config["restrictions"]},
        )

    def test_provider_call_reuses_anthropic_adapter_with_exact_parameters(self):
        payload = [{"role": "user", "content": "fixture"}]
        result = SimpleNamespace()
        trial = self.schedule[0]
        with patch.object(runner, "sample_messages", return_value=result) as call:
            self.assertIs(
                runner.call_provider(trial, payload, {"anthropic": "y"}, 4), result
            )
        call.assert_called_once_with(
            api_key="y",
            model="claude-opus-5",
            messages=payload,
            parameters={"temperature": 1.0, "max_tokens": 15, "thinking": {"type": "disabled"}},
            max_attempts=4,
        )

    def test_offline_collection_and_analysis_cover_all_cells(self):
        def fake_call(trial, payload, api_keys, max_attempts):
            raw = "River|Stone" if trial["restriction"] == "LANTERN_BLACKLIST" else "Lantern|River"
            return runner.ProviderResult(
                requested_model=trial["model_id"],
                actual_model=trial["model_id"],
                provider=trial["provider"],
                client="offline_fixture",
                raw_response=raw,
                finish_reason="end_turn",
                response_id="fixture",
                usage=None,
                sent_parameters={"messages": payload, **trial["request_parameters"]},
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
        self.assertEqual(provider_call.call_count, 450)
        self.assertTrue(manifest["collection_complete"])
        summary = analysis.analyze_records(records, self.schedule, self.config)
        self.assertEqual(len(summary["cells"]), 9)
        self.assertEqual(len(summary["current_restriction_comparisons"]), 18)
        self.assertEqual(len(summary["no_blacklist_vs_historical_experiment_003"]), 9)
        self.assertEqual(
            len(summary["lantern_blacklist_replacement_first_word_comparisons"]), 3
        )
        self.assertTrue(all(cell["PROTOCOL_FAILURE"] == 0 for cell in summary["cells"]))
        self.assertTrue(all(cell["BAN_VIOLATION"] == 0 for cell in summary["cells"]))


if __name__ == "__main__":
    unittest.main()
