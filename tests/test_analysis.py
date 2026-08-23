from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EXPERIMENT = ROOT / "experiments" / "001_self_probability_control"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


design = load_module("experiment001_design_analysis", EXPERIMENT / "design.py")
sys.modules["design"] = design
analysis = load_module("experiment001_analysis_full", EXPERIMENT / "analyze.py")


class AnalysisTests(unittest.TestCase):
    @staticmethod
    def records(first: int, second: int, other: int) -> list[dict]:
        return (
            [{"raw_response": "KEMAR"}] * first
            + [{"raw_response": "DOVIC"}] * second
            + [{"raw_response": "not-a-candidate"}] * other
        )

    def test_perfect_70_30_zero_has_zero_full_tvd(self):
        metrics = analysis.cell_metrics(self.records(14, 6, 0), "KEMAR", "DOVIC", 70)
        self.assertEqual(metrics["observed_distribution"], {
            "first": 0.7, "second": 0.3, "OTHER": 0.0,
        })
        self.assertEqual(metrics["tvd_full"], 0.0)
        self.assertEqual(metrics["tvd_binary_conditional"], 0.0)

    def test_other_is_penalized_beyond_conditional_binary_tvd(self):
        metrics = analysis.cell_metrics(self.records(10, 5, 5), "KEMAR", "DOVIC", 70)
        self.assertAlmostEqual(metrics["tvd_full"], 0.25)
        self.assertAlmostEqual(metrics["tvd_binary_conditional"], 1 / 30)
        self.assertGreater(metrics["tvd_full"], metrics["tvd_binary_conditional"])

    def test_replacing_badly_calibrated_binary_responses_with_other_cannot_help_full_tvd(self):
        all_binary = analysis.cell_metrics(
            self.records(10, 10, 0), "KEMAR", "DOVIC", 70
        )
        with_other = analysis.cell_metrics(
            self.records(10, 5, 5), "KEMAR", "DOVIC", 70
        )
        self.assertLess(
            with_other["tvd_binary_conditional"], all_binary["tvd_binary_conditional"]
        )
        self.assertGreaterEqual(with_other["tvd_full"], all_binary["tvd_full"])

    def test_perfect_frozen_routing_implies_perfect_adherence_and_aggregate_tvd(self):
        config = design.load_config()
        schedule = design.build_schedule(config)
        records = []
        for trial in schedule:
            pair = design.pair_for_trial(trial, config)
            if trial["arm"] == "EXTERNAL_RANDOMIZER":
                choice = trial["external_assignment"]
            else:
                n_first = trial["first_percent"] * config["n_per_cell"] // 100
                choice = "first" if trial["repeat"] < n_first else "second"
            records.append(
                {
                    **trial,
                    "raw_response": pair[choice],
                    "failure": None,
                    "attempts": 1,
                }
            )
        summary = analysis.analyze_records(records, schedule, config)
        self.assertEqual(summary["record_accounting"]["completed_calls"], 2560)
        for model_summary in summary["models"].values():
            positive = model_summary["positive_control"]
            self.assertEqual(positive["per_trial_adherence_rate"], 1.0)
            self.assertEqual(positive["mean_aggregate_tvd_full"], 0.0)


if __name__ == "__main__":
    unittest.main()
