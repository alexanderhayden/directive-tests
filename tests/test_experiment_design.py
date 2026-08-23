from __future__ import annotations

import importlib.util
import sys
import unittest
from collections import Counter, defaultdict
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


design = load_module("experiment001_design_full", EXPERIMENT / "design.py")
sys.modules["design"] = design
runner = load_module("experiment001_run_full", EXPERIMENT / "run.py")


class ExperimentDesignTests(unittest.TestCase):
    def test_full_schedule_counts_and_reproducibility(self):
        first = design.build_schedule()
        second = design.build_schedule()
        self.assertEqual(first, second)
        self.assertEqual(design.schedule_sha256(first), design.schedule_sha256(second))
        self.assertEqual(
            design.schedule_sha256(first),
            "777ade6c69ec325465c6f0c4490f4b2844e928c6c8c4e204efffeb1d6934d1d5",
        )
        self.assertEqual(len(first), 2560)
        self.assertEqual(len({row["trial_id"] for row in first}), 2560)
        cell_counts = Counter(row["cell_id"] for row in first)
        self.assertEqual(len(cell_counts), 128)
        self.assertEqual(set(cell_counts.values()), {20})

    def test_expected_per_model_and_interface_counts(self):
        schedule = design.build_schedule()
        self.assertEqual(set(Counter(row["model_key"] for row in schedule).values()), {640})
        self.assertEqual(Counter(row["interface"] for row in schedule), {"chat": 1280, "completion": 1280})
        for row in schedule:
            expected = "completion" if row["training_stage"] == "base" else "chat"
            self.assertEqual(row["interface"], expected)

    def test_balanced_superblocks(self):
        schedule = design.build_schedule()
        grouped = defaultdict(list)
        for row in schedule:
            grouped[row["superblock_id"]].append(row)
        self.assertEqual(len(grouped), 20)
        for rows in grouped.values():
            self.assertEqual(len(rows), 128)
            self.assertEqual(set(Counter(row["model_key"] for row in rows).values()), {32})
            self.assertEqual(set(row["model_block_position"] for row in rows), {0, 1, 2, 3})

    def test_base_and_instruction_payloads_have_matched_semantic_transcript(self):
        schedule = design.build_schedule()
        base = next(
            row for row in schedule
            if row["family"] == "Llama 3.1 8B" and row["training_stage"] == "base"
            and row["pair_id"] == "pair_0" and row["first_percent"] == 30 and row["arm"] == "BASE"
        )
        instruct = next(
            row for row in schedule
            if row["family"] == "Llama 3.1 8B" and row["training_stage"] == "instruction_tuned"
            and row["pair_id"] == "pair_0" and row["first_percent"] == 30 and row["arm"] == "BASE"
        )
        base_payload = design.build_trial_payload(base)
        chat_payload = design.build_trial_payload(instruct)
        labels = {"user": "User: ", "assistant": "Assistant: "}
        flattened = "\n".join(labels[msg["role"]] + msg["content"] for msg in chat_payload)
        self.assertEqual(base_payload, flattened + "\nAssistant:")

    def test_dry_run_validates_schedule_and_manifest_without_writing_results(self):
        runs_dir = EXPERIMENT / "results" / "runs"
        before = runs_dir.exists()
        report = runner.dry_run_report()
        self.assertEqual(report["mode"], "dry-run-no-provider-contact")
        self.assertEqual(report["planned_trials"], 2560)
        self.assertEqual(report["cell_count"], 128)
        self.assertEqual(report["cell_counts_unique_values"], [20])
        self.assertEqual(report["external_cells"], 32)
        self.assertEqual(report["transport_counts"], {
            "ollama_native_chat": 1280,
            "ollama_native_generate_raw": 1280,
        })
        self.assertTrue(report["manifest_required_fields_present"])
        self.assertEqual(runs_dir.exists(), before)

    def test_inventory_verification_checks_frozen_tags_and_digests(self):
        config = design.load_config()

        class FakeProvider:
            def list_models(self):
                return [
                    {"name": model["model_tag"], "digest": model["expected_digest_prefix"] + "abcdef"}
                    for model in config["models"]
                ]

        verified = runner.verify_model_inventory(FakeProvider(), config)
        self.assertEqual(len(verified), 4)
        self.assertEqual({row["interface"] for row in verified}, {"chat", "completion"})
        base = [row for row in verified if row["interface"] == "completion"]
        instruct = [row for row in verified if row["interface"] == "chat"]
        self.assertEqual({row["transport"] for row in base}, {"ollama_native_generate_raw"})
        self.assertEqual({row["raw"] for row in base}, {True})
        self.assertEqual({row["transport"] for row in instruct}, {"ollama_native_chat"})
        self.assertEqual({row["raw"] for row in instruct}, {None})


if __name__ == "__main__":
    unittest.main()
