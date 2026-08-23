from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "001_self_probability_control"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EXPERIMENT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


design = load_module("experiment001_design_smoke", EXPERIMENT / "design.py")
sys.modules["design"] = design
runner = load_module("experiment001_run_smoke", EXPERIMENT / "run.py")
sys.modules["run"] = runner
smoke = load_module("experiment001_smoke", EXPERIMENT / "smoke.py")


class SmokePilotTests(unittest.TestCase):
    def test_deterministic_subset_has_two_immutable_rows_per_cell(self):
        full = design.build_schedule()
        before = json.dumps(full, ensure_ascii=False, sort_keys=True)
        selected = smoke.select_smoke_schedule(full)

        self.assertEqual(json.dumps(full, ensure_ascii=False, sort_keys=True), before)
        self.assertEqual(design.schedule_sha256(full), smoke.FULL_SCHEDULE_SHA256)
        self.assertEqual(len(selected), 256)
        self.assertEqual({row["repeat"] for row in selected}, {0, 1})
        counts = Counter(row["cell_id"] for row in selected)
        self.assertEqual(len(counts), 128)
        self.assertEqual(set(counts.values()), {2})
        self.assertEqual(
            [row["trial_id"] for row in selected],
            [row["trial_id"] for row in full if row["repeat"] in {0, 1}],
        )

    def test_subset_is_balanced_by_model_arm_pair_and_split(self):
        _, selected = smoke.build_smoke_schedule()
        counts = Counter(
            (row["model_key"], row["arm"], row["pair_id"], row["first_percent"])
            for row in selected
        )
        self.assertEqual(len(counts), 128)
        self.assertEqual(set(counts.values()), {2})
        self.assertEqual(set(Counter(row["model_key"] for row in selected).values()), {64})
        self.assertEqual(set(Counter(row["arm"] for row in selected).values()), {64})
        self.assertEqual(set(Counter(row["pair_id"] for row in selected).values()), {128})
        self.assertEqual(set(Counter(row["first_percent"] for row in selected).values()), {64})

    def test_selected_external_assignments_match_frozen_source_rows(self):
        full, selected = smoke.build_smoke_schedule()
        source = {row["trial_id"]: row for row in full}
        external = [row for row in selected if row["arm"] == "EXTERNAL_RANDOMIZER"]
        self.assertEqual(len(external), 64)
        for row in external:
            self.assertEqual(row["external_assignment"], source[row["trial_id"]]["external_assignment"])
            self.assertEqual(
                row["external_assignment_source"],
                source[row["trial_id"]]["external_assignment_source"],
            )

    def test_smoke_dry_run_is_no_contact_and_uses_separate_namespace(self):
        report = smoke.dry_run_report()
        self.assertEqual(report["mode"], "smoke-dry-run-no-provider-contact")
        self.assertEqual(report["planned_calls"], 256)
        self.assertEqual(report["cell_count"], 128)
        self.assertEqual(report["cell_counts_unique_values"], [2])
        self.assertEqual(report["model_arm_pair_split_combinations"], 128)
        self.assertEqual(report["model_arm_pair_split_counts_unique_values"], [2])
        self.assertEqual(report["full_schedule_sha256"], smoke.FULL_SCHEDULE_SHA256)
        self.assertEqual(
            report["results_namespace"],
            "experiments/001_self_probability_control/results/smoke_pilot",
        )
        self.assertTrue(report["excluded_from_full_001A"])


if __name__ == "__main__":
    unittest.main()
