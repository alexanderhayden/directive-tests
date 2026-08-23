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
EXPERIMENT = ROOT / "experiments" / "002_frontier_self_probability_feasibility"
LEGACY = ROOT / "experiments" / "001_self_probability_control"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EXPERIMENT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


design = load_module("experiment002_design_tests", EXPERIMENT / "design.py")
sys.modules["design"] = design
runner = load_module("experiment002_runner_tests", EXPERIMENT / "run.py")
analysis = load_module("experiment002_analysis_tests", EXPERIMENT / "analyze.py")


class FrontierFeasibilityTests(unittest.TestCase):
    def setUp(self):
        self.config = design.load_config()
        self.schedule = design.build_schedule(self.config)

    def test_frozen_models_and_provider_specific_settings(self):
        models = {model["model_key"]: model for model in self.config["models"]}
        self.assertEqual(models["gpt41_20250414"]["model_id"], "gpt-4.1-2025-04-14")
        self.assertEqual(
            models["gpt41_20250414"]["request_parameters"],
            {"temperature": 1.0, "max_tokens": 15},
        )
        self.assertEqual(models["claude_opus_5"]["model_id"], "claude-opus-5")
        self.assertEqual(
            models["claude_opus_5"]["request_parameters"],
            {
                "temperature": 1.0,
                "max_tokens": 15,
                "thinking": {"type": "disabled"},
            },
        )

    def test_schedule_has_exact_480_call_balance(self):
        self.assertEqual(len(self.schedule), 480)
        self.assertEqual(len({row["trial_id"] for row in self.schedule}), 480)
        self.assertEqual(set(Counter(row["model_key"] for row in self.schedule).values()), {240})
        self.assertEqual(set(Counter(row["cell_id"] for row in self.schedule).values()), {10})
        self.assertEqual(len({row["cell_id"] for row in self.schedule}), 48)
        self.assertEqual(
            Counter(row["arm"] for row in self.schedule),
            {"CLARIFY": 160, "SELF_PROBABILITY": 160, "EXTERNAL_RANDOMIZER": 160},
        )
        self.assertEqual(Counter(row["pair_id"] for row in self.schedule), {"pair_0": 240, "pair_1": 240})
        self.assertEqual(
            Counter(row["first_percent"] for row in self.schedule),
            {30: 120, 40: 120, 60: 120, 70: 120},
        )

    def test_external_assignments_are_exact_and_frozen(self):
        first = design.build_schedule(self.config)
        second = design.build_schedule(self.config)
        self.assertEqual(first, second)
        grouped = {}
        for row in first:
            if row["arm"] == "EXTERNAL_RANDOMIZER":
                grouped.setdefault(row["cell_id"], []).append(row)
        self.assertEqual(len(grouped), 16)
        for rows in grouped.values():
            requested = rows[0]["first_percent"] // 10
            self.assertEqual(
                Counter(row["external_assignment"] for row in rows),
                {"first": requested, "second": 10 - requested},
            )

    def test_prompt_source_hash_and_payloads_match_approved_v2_builder(self):
        prompts = design.load_approved_prompts(self.config)
        self.assertEqual(
            design.file_sha256(design.prompt_source_path(self.config)),
            self.config["approved_prompt_sha256"],
        )
        legacy_v1 = load_module("experiment001_v1_for_frontier_tests", LEGACY / "design.py")
        with patch.dict(sys.modules, {"design": legacy_v1}):
            legacy_v2 = load_module("experiment001_v2_for_frontier_tests", LEGACY / "design_v2.py")
        for arm in self.config["arms"]:
            for pair_id in ("pair_0", "pair_1"):
                for first_percent in (30, 40, 60, 70):
                    row = next(
                        row
                        for row in self.schedule
                        if row["arm"] == arm
                        and row["pair_id"] == pair_id
                        and row["first_percent"] == first_percent
                    )
                    self.assertEqual(
                        design.build_trial_payload(row, self.config, prompts),
                        legacy_v2.build_trial_payload_v2(row, self.config, prompts),
                    )

    def test_dry_run_is_no_contact_and_balanced(self):
        with patch.object(runner, "sample_chat") as openai_call, patch.object(
            runner, "sample_messages"
        ) as anthropic_call:
            report = runner.dry_run_report()
        openai_call.assert_not_called()
        anthropic_call.assert_not_called()
        self.assertFalse(report["provider_contact"])
        self.assertEqual(report["planned_calls"], 480)
        self.assertEqual(report["cell_count"], 48)
        self.assertEqual(report["cell_counts_unique_values"], [10])
        self.assertEqual(set(report["calls_by_model"].values()), {240})

    def test_provider_calls_reuse_adapters_with_exact_model_specific_parameters(self):
        payload = [{"role": "user", "content": "fixture"}]
        result = SimpleNamespace()
        openai_trial = next(row for row in self.schedule if row["provider"] == "openai")
        anthropic_trial = next(row for row in self.schedule if row["provider"] == "anthropic")
        with patch.object(runner, "sample_chat", return_value=result) as openai_call:
            self.assertIs(
                runner.call_provider(openai_trial, payload, {"openai": "x", "anthropic": "y"}, 4),
                result,
            )
        openai_call.assert_called_once_with(
            api_key="x",
            model="gpt-4.1-2025-04-14",
            messages=payload,
            parameters={"temperature": 1.0, "max_tokens": 15},
            max_attempts=4,
        )
        with patch.object(runner, "sample_messages", return_value=result) as anthropic_call:
            self.assertIs(
                runner.call_provider(
                    anthropic_trial, payload, {"openai": "x", "anthropic": "y"}, 4
                ),
                result,
            )
        anthropic_call.assert_called_once_with(
            api_key="y",
            model="claude-opus-5",
            messages=payload,
            parameters={
                "temperature": 1.0,
                "max_tokens": 15,
                "thinking": {"type": "disabled"},
            },
            max_attempts=4,
        )

    def test_mocked_collection_exercises_files_and_concurrency_without_provider_contact(self):
        def fake_call(trial, payload, api_keys, max_attempts):
            pair = design.pair_for_trial(trial, self.config)
            choice = trial.get("external_assignment", "first")
            return runner.ProviderResult(
                requested_model=trial["model_id"],
                actual_model=trial["model_id"],
                provider="OpenAI" if trial["provider"] == "openai" else "Anthropic",
                client="offline_fixture",
                raw_response=pair[choice],
                finish_reason="stop",
                response_id="offline-fixture",
                usage=None,
                sent_parameters={
                    "model": trial["model_id"],
                    "messages": payload,
                    **trial["request_parameters"],
                },
                attempts=1,
            )

        with tempfile.TemporaryDirectory() as directory, patch.object(
            runner, "RESULTS_ROOT", Path(directory)
        ), patch.object(
            runner, "load_api_keys", return_value={"openai": "x", "anthropic": "y"}
        ), patch.object(runner, "call_provider", side_effect=fake_call) as provider_call, patch(
            "sys.stdout", new=io.StringIO()
        ):
            runner.collect("offline-fixture", resume=False, workers=4)
            run_dir = Path(directory) / "runs" / "offline-fixture"
            manifest = json.loads((run_dir / "manifest.json").read_text())
            records = runner.load_jsonl(run_dir / "responses.jsonl")
        self.assertEqual(provider_call.call_count, 480)
        self.assertTrue(manifest["collection_complete"])
        self.assertEqual(manifest["completed_calls"], 480)
        self.assertEqual(len(records), 480)
        self.assertEqual(
            {record["primary_classification"] for record in records}, {"first", "second"}
        )

    def test_strict_full_tvd_counts_successful_nonexact_as_protocol_failure(self):
        records = [
            {"raw_response": "KEMAR"},
            {"raw_response": "DOVIC"},
            {"raw_response": "KEMAR because"},
            {"raw_response": "Answer: DOVIC"},
        ]
        metrics = analysis.cell_metrics(records, "KEMAR", "DOVIC", 50, False)
        self.assertEqual(metrics["exact_first"], 1)
        self.assertEqual(metrics["exact_second"], 1)
        self.assertEqual(metrics["PROTOCOL_FAILURE"], 2)
        self.assertEqual(metrics["observed_first_candidate_rate"], 0.25)
        self.assertEqual(metrics["full_tvd"], 0.5)

    def test_graded_diagnostics_distinguish_matching_from_majority_switch(self):
        def metric(first: int, requested: int) -> dict:
            return {
                "exact_first": first,
                "exact_second": 10 - first,
                "PROTOCOL_FAILURE": 0,
                "observed_first_candidate_rate": first / 10,
                "full_tvd": abs(first / 10 - requested / 100),
            }

        matching = {split: metric(split // 10, split) for split in (30, 40, 60, 70)}
        threshold = {
            split: metric(0 if split < 50 else 10, split) for split in (30, 40, 60, 70)
        }
        self.assertEqual(
            analysis.graded_pair_summary(matching)["descriptive_closer_to"],
            "requested_probability_magnitudes",
        )
        self.assertEqual(
            analysis.graded_pair_summary(threshold)["descriptive_closer_to"],
            "categorical_majority_switch",
        )

    def test_synthetic_complete_analysis_reports_all_model_pair_split_comparisons(self):
        records = []
        for row in self.schedule:
            pair = design.pair_for_trial(row, self.config)
            if row["arm"] == "EXTERNAL_RANDOMIZER":
                raw = pair[row["external_assignment"]]
            else:
                first_count = row["first_percent"] // 10
                raw = pair["first"] if row["repeat"] < first_count else pair["second"]
            records.append(
                {
                    **row,
                    "raw_response": raw,
                    "failure": None,
                    "model_invariant_error": None,
                    "attempts": 1,
                }
            )
        summary = analysis.analyze_records(records, self.schedule, self.config)
        self.assertEqual(summary["successful_calls"], 480)
        self.assertEqual(len(summary["cells"]), 48)
        self.assertEqual(len(summary["comparisons_by_model_pair_split"]), 16)
        for comparison in summary["comparisons_by_model_pair_split"]:
            self.assertEqual(comparison["TVD_CLARIFY_minus_TVD_SELF"], 0.0)
            self.assertEqual(
                comparison["EXTERNAL_RANDOMIZER"]["strict_external_adherence_rate"], 1.0
            )
        for model in summary["model_summaries"].values():
            self.assertEqual(model["strict_external_adherence"]["rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
