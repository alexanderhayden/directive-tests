from __future__ import annotations

import importlib.util
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.parsing import external_routing_adherence
from harness.randomization import exact_external_assignments


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


EXPERIMENT = ROOT / "experiments" / "001_self_probability_control"
design = load_module("experiment001_design", EXPERIMENT / "design.py")
sys.modules["design"] = design
runner = load_module("experiment001_run", EXPERIMENT / "run.py")
analysis = load_module("experiment001_analysis", EXPERIMENT / "analyze.py")


class ExternalAllocationTests(unittest.TestCase):
    EXPECTED = {
        30: {"first": 6, "second": 14},
        40: {"first": 8, "second": 12},
        60: {"first": 12, "second": 8},
        70: {"first": 14, "second": 6},
    }

    def test_exact_preregistered_allocations_at_n20(self):
        for first_percent, expected in self.EXPECTED.items():
            with self.subTest(first_percent=first_percent):
                assignments = exact_external_assignments(
                    first_percent, 20, seed=2026082202, cell_key=f"cell-{first_percent}"
                )
                self.assertEqual(dict(Counter(assignments)), expected)

    def test_same_seed_and_cell_key_reproduce_sequence(self):
        first = exact_external_assignments(40, 20, seed=17, cell_key="model-pair-split")
        second = exact_external_assignments(40, 20, seed=17, cell_key="model-pair-split")
        self.assertEqual(first, second)

    def test_changed_cell_key_changes_permutation_but_not_counts(self):
        first = exact_external_assignments(60, 20, seed=17, cell_key="cell-a")
        second = exact_external_assignments(60, 20, seed=17, cell_key="cell-b")
        self.assertNotEqual(first, second)
        self.assertEqual(Counter(first), Counter(second))
        self.assertEqual(Counter(first), Counter({"first": 12, "second": 8}))

    def test_frozen_assignments_are_in_complete_schedule_with_exact_cell_counts(self):
        schedule = design.build_schedule()
        external = [row for row in schedule if row["arm"] == "EXTERNAL_RANDOMIZER"]
        self.assertTrue(external)
        self.assertTrue(all(row["external_assignment_source"] == "preconstructed_exact_allocation" for row in external))

        grouped = defaultdict(Counter)
        for row in external:
            key = (row["model_key"], row["pair_id"], row["first_percent"])
            grouped[key][row["external_assignment"]] += 1
        self.assertEqual(len(grouped), 4 * 2 * 4)
        for (_, _, first_percent), counts in grouped.items():
            self.assertEqual(dict(counts), self.EXPECTED[first_percent])

    def test_call_loop_consumes_frozen_assignment_without_generating_one(self):
        external_trial = next(
            row for row in design.build_schedule() if row["arm"] == "EXTERNAL_RANDOMIZER"
        )
        original = dict(external_trial)
        seen = []

        def fake_sampler(trial, payload):
            seen.append((dict(trial), payload))
            return "not-a-model-call"

        with patch.object(
            design,
            "exact_external_assignments",
            side_effect=AssertionError("assignment generated inside call loop"),
        ):
            outputs = runner.execute_schedule([external_trial], fake_sampler)

        self.assertEqual(outputs, ["not-a-model-call"])
        self.assertEqual(external_trial, original)
        self.assertEqual(seen[0][0]["external_assignment"], original["external_assignment"])


class ExternalRoutingAdherenceTests(unittest.TestCase):
    def test_adherence_requires_match_to_individual_frozen_assignment(self):
        self.assertTrue(external_routing_adherence("first", "first"))
        self.assertTrue(external_routing_adherence("second", "second"))
        self.assertFalse(external_routing_adherence("first", "second"))
        self.assertFalse(external_routing_adherence("second", "first"))
        self.assertFalse(external_routing_adherence("OTHER", "first"))
        self.assertIsNone(external_routing_adherence("first", None))

    def test_trial_classifier_uses_record_assignment(self):
        matching = analysis.classify_trial(
            {"raw_response": "KEMAR", "external_assignment": "first"}, "KEMAR", "DOVIC"
        )
        mismatching = analysis.classify_trial(
            {"raw_response": "KEMAR", "external_assignment": "second"}, "KEMAR", "DOVIC"
        )
        self.assertTrue(matching["external_routing_adherent"])
        self.assertFalse(mismatching["external_routing_adherent"])


if __name__ == "__main__":
    unittest.main()
