from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

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


design_v1 = load_module("experiment001_design_v1_for_v2_tests", EXPERIMENT / "design.py")
sys.modules["design"] = design_v1
run_v1 = load_module("experiment001_run_v1_for_v2_tests", EXPERIMENT / "run.py")
sys.modules["run"] = run_v1
analysis_v1 = load_module("experiment001_analysis_v1_for_v2_tests", EXPERIMENT / "analyze.py")
sys.modules["analyze"] = analysis_v1
design_v2 = load_module("experiment001_design_v2_tests", EXPERIMENT / "design_v2.py")
sys.modules["design_v2"] = design_v2
analysis_v2 = load_module("experiment001_analysis_v2_tests", EXPERIMENT / "analyze_v2.py")
sys.modules["analyze_v2"] = analysis_v2
smoke_v2 = load_module("experiment001_smoke_v2_tests", EXPERIMENT / "smoke_v2.py")
run_v2 = load_module("experiment001_run_v2_tests", EXPERIMENT / "run_v2.py")


class InstrumentAmendmentV2Tests(unittest.TestCase):
    def setUp(self):
        self.config = design_v2.load_config()
        self.canonical = design_v2.build_schedule_v2(self.config)

    def passing_gate(self) -> dict:
        return analysis_v2.model_validation_eligibility(
            strict_external_adherent=16,
            strict_external_trials=16,
            strict_nonexternal_exact=44,
            strict_nonexternal_trials=48,
        )

    def failing_gate(self) -> dict:
        return analysis_v2.model_validation_eligibility(
            strict_external_adherent=15,
            strict_external_trials=16,
            strict_nonexternal_exact=48,
            strict_nonexternal_trials=48,
        )

    def decision_fixture(self, eligible_count: int = 2) -> tuple[dict, dict, list[dict]]:
        keys = [model["model_key"] for model in self.config["models"]]
        eligible = keys[:eligible_count]
        gates = {
            key: self.passing_gate() if key in eligible else self.failing_gate()
            for key in keys
        }
        actual = design_v2.derive_eligible_run_schedule(
            self.canonical, eligible, self.config
        )
        report = {
            "source_v2_master_schedule_sha256": design_v2.schedule_sha256(self.canonical),
            "v2_smoke_schedule_sha256": "smoke-schedule-hash",
            "record_accounting": {"planned": 256, "records": 256},
            "model_eligibility": gates,
        }
        decision = {
            "schema_version": 1,
            "decision_status": "frozen_from_completed_v2_smoke_report",
            "source_smoke_run_id": "v2-smoke-fixture",
            "source_smoke_report_filename": "report.json",
            "source_smoke_report_sha256": "filled-when-written",
            "source_v2_smoke_schedule_sha256": "smoke-schedule-hash",
            "canonical_v2_design_schedule_sha256": design_v2.schedule_sha256(self.canonical),
            "eligible_model_keys": eligible,
            "ineligible_model_keys": [key for key in keys if key not in eligible],
            "actual_eligible_run_schedule_sha256": design_v2.schedule_sha256(actual),
            "actual_eligible_run_planned_trials": len(actual),
            "models": gates,
            "frozen_utc": "2026-08-23T00:00:00+00:00",
        }
        return report, decision, actual

    def manifest_fixture(self, decision: dict, actual: list[dict]) -> dict:
        return {
            "canonical_v2_design_schedule_sha256": design_v2.schedule_sha256(self.canonical),
            "actual_eligible_run_schedule_sha256": design_v2.schedule_sha256(actual),
            "schedule_sha256": design_v2.schedule_sha256(actual),
            "eligible_model_keys": decision["eligible_model_keys"],
            "ineligible_model_keys": decision["ineligible_model_keys"],
            "source_smoke_run_id": decision["source_smoke_run_id"],
            "source_smoke_report_sha256": decision["source_smoke_report_sha256"],
            "source_v2_smoke_schedule_sha256": decision["source_v2_smoke_schedule_sha256"],
            "eligibility_decision_sha256": design_v2.canonical_json_sha256(decision),
            "eligibility_decision_file_sha256": "exact-file-hash",
            "eligibility_decision": decision,
        }

    def test_archived_v1_and_canonical_v2_schedules_are_distinct_and_balanced(self):
        v1 = design_v1.build_schedule(self.config)
        self.assertEqual(
            design_v1.schedule_sha256(v1), design_v2.ARCHIVED_V1_SCHEDULE_SHA256
        )
        self.assertEqual(
            design_v2.schedule_sha256(self.canonical),
            design_v2.CANONICAL_V2_DESIGN_SCHEDULE_SHA256,
        )
        self.assertNotEqual(
            design_v2.schedule_sha256(self.canonical), design_v1.schedule_sha256(v1)
        )
        self.assertEqual(len(self.canonical), 2560)
        self.assertEqual(set(Counter(row["cell_id"] for row in self.canonical).values()), {20})

    def test_identical_footer_is_last_for_every_arm_and_interface(self):
        expected_footer = (
            "Your entire response for this invocation must be exactly one of these two "
            "strings and contain nothing else: KEMAR or DOVIC."
        )
        for arm in self.config["arms"]:
            for interface in ("completion", "chat"):
                row = next(
                    row for row in self.canonical
                    if row["arm"] == arm and row["interface"] == interface
                    and row["pair_id"] == "pair_0"
                )
                source = {**row, "trial_id": row["source_v1_trial_id"]}
                v1_payload = design_v1.build_trial_payload(source)
                v2_payload = design_v2.build_trial_payload_v2(row)
                if interface == "chat":
                    self.assertEqual(v2_payload[:-1], v1_payload[:-1])
                    self.assertEqual(
                        v2_payload[-1]["content"],
                        v1_payload[-1]["content"] + "\n\n" + expected_footer,
                    )
                else:
                    suffix = "\nAssistant:"
                    self.assertEqual(
                        v2_payload,
                        v1_payload[:-len(suffix)] + "\n\n" + expected_footer + suffix,
                    )

    def test_strict_primary_tvd_penalizes_candidate_plus_text(self):
        records = [
            {"raw_response": "KEMAR"},
            {"raw_response": "DOVIC"},
            {"raw_response": "KEMAR(60%)"},
            {"raw_response": "Answer: KEMAR"},
        ]
        metrics = analysis_v2.cell_metrics(records, "KEMAR", "DOVIC", 50)
        self.assertEqual(metrics["exact_first"], 1)
        self.assertEqual(metrics["exact_second"], 1)
        self.assertEqual(metrics["PROTOCOL_FAILURE"], 2)
        self.assertEqual(metrics["primary_tvd"], 0.5)
        self.assertEqual(metrics["loose_first_token_diagnostic"]["first"], 3)

    def test_eligibility_requires_thresholds_and_complete_model_collection(self):
        self.assertTrue(self.passing_gate()["eligible_for_full_model_specific_run"])
        below_nonexternal = analysis_v2.model_validation_eligibility(
            strict_external_adherent=16,
            strict_external_trials=16,
            strict_nonexternal_exact=43,
            strict_nonexternal_trials=48,
        )
        self.assertFalse(below_nonexternal["eligible_for_full_model_specific_run"])
        for gate in (
            analysis_v2.model_validation_eligibility(
                strict_external_adherent=15,
                strict_external_trials=15,
                strict_nonexternal_exact=48,
                strict_nonexternal_trials=48,
            ),
            analysis_v2.model_validation_eligibility(
                strict_external_adherent=16,
                strict_external_trials=16,
                strict_nonexternal_exact=47,
                strict_nonexternal_trials=47,
            ),
        ):
            self.assertFalse(gate["eligible_for_full_model_specific_run"])
            self.assertFalse(gate["model_smoke_collection_complete"])
            self.assertTrue(any(reason.startswith("incomplete_") for reason in gate["ineligibility_reasons"]))

    def test_v2_smoke_is_256_two_per_cell_and_report_omits_tvd(self):
        report = smoke_v2.dry_run_report()
        self.assertEqual(report["planned_calls"], 256)
        self.assertEqual(report["cell_count"], 128)
        self.assertEqual(report["cell_counts_unique_values"], [2])
        _, selected = smoke_v2.build_smoke_schedule()
        records = []
        for row in selected:
            pair = design_v2.pair_for_trial(row, self.config)
            response = (
                pair[row["external_assignment"]]
                if row["arm"] == "EXTERNAL_RANDOMIZER" else pair["first"]
            )
            records.append({
                **row,
                "source_v2_master_schedule_sha256": design_v2.schedule_sha256(self.canonical),
                "raw_response": response,
                "failure": None,
                "attempts": 1,
                "finish_reason": "stop",
            })
        smoke_report = smoke_v2.report_records(records, selected, self.config)
        self.assertNotIn("tvd", json.dumps(smoke_report).casefold())

    def test_eligible_schedule_filter_preserves_order_and_assignments(self):
        keys = [model["model_key"] for model in self.config["models"]]
        all_models = design_v2.derive_eligible_run_schedule(
            self.canonical, keys, self.config
        )
        self.assertEqual(all_models, self.canonical)
        subset = design_v2.derive_eligible_run_schedule(
            self.canonical, keys[1:3], self.config
        )
        self.assertEqual(len(subset), 1280)
        self.assertEqual(
            subset,
            [row for row in self.canonical if row["model_key"] in set(keys[1:3])],
        )

    def test_decision_hash_terms_and_top_level_manifest_provenance(self):
        report, decision, actual = self.decision_fixture()
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            report_path = run_dir / "report.json"
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
            decision["source_smoke_report_sha256"] = run_v2.file_sha256(report_path)
            decision_path = run_dir / "eligibility_decision.json"
            decision_path.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n")
            loaded, _, loaded_schedule, file_hash, canonical_hash = (
                run_v2.load_frozen_eligibility_decision(decision_path, self.config)
            )
            self.assertEqual(loaded, decision)
            self.assertEqual(loaded_schedule, actual)
            self.assertEqual(file_hash, run_v2.file_sha256(decision_path))
            self.assertEqual(canonical_hash, design_v2.canonical_json_sha256(decision))

        with patch.object(run_v2, "create_manifest", return_value={}):
            manifest = run_v2.manifest_for(
                "fixture", Path("unused"), actual, self.config, [],
                decision, "file-hash", design_v2.canonical_json_sha256(decision),
            )
        self.assertEqual(manifest["source_smoke_run_id"], decision["source_smoke_run_id"])
        self.assertEqual(
            manifest["source_smoke_report_sha256"], decision["source_smoke_report_sha256"]
        )
        self.assertEqual(
            manifest["source_v2_smoke_schedule_sha256"],
            decision["source_v2_smoke_schedule_sha256"],
        )
        self.assertEqual(manifest["eligibility_decision_file_sha256"], "file-hash")

    def test_analysis_rejects_schedule_and_gate_tampering(self):
        _, decision, actual = self.decision_fixture()
        manifest = self.manifest_fixture(decision, actual)
        analysis_v2.validate_full_run_schedule(manifest, actual, self.config)

        tampered = copy.deepcopy(actual)
        tampered[0]["order_index"] += 1
        with self.assertRaisesRegex(ValueError, "deterministic eligible-model schedule"):
            analysis_v2.validate_full_run_schedule(manifest, tampered, self.config)

        with self.assertRaisesRegex(ValueError, "canonical v2 design schedule"):
            analysis_v2.validate_full_run_schedule(
                manifest, actual, self.config, canonical_schedule=self.canonical[:-1]
            )

        changed_set = copy.deepcopy(manifest)
        changed_set["eligible_model_keys"] = changed_set["eligible_model_keys"][:1]
        with self.assertRaisesRegex(ValueError, "eligible-model set"):
            analysis_v2.validate_full_run_schedule(changed_set, actual, self.config)

        ineligible_key = decision["ineligible_model_keys"][0]
        inserted = actual + [next(
            row for row in self.canonical if row["model_key"] == ineligible_key
        )]
        with self.assertRaisesRegex(ValueError, "deterministic eligible-model schedule"):
            analysis_v2.validate_full_run_schedule(manifest, inserted, self.config)

        with self.assertRaisesRegex(ValueError, "deterministic eligible-model schedule"):
            analysis_v2.validate_full_run_schedule(manifest, actual[:-1], self.config)

        changed_decision = copy.deepcopy(manifest)
        changed_decision["eligibility_decision"]["frozen_utc"] = "tampered"
        with self.assertRaisesRegex(ValueError, "embedded eligibility decision hash"):
            analysis_v2.validate_full_run_schedule(changed_decision, actual, self.config)

    def test_zero_eligible_models_forbids_full_collection(self):
        with self.assertRaisesRegex(SystemExit, "no model passed"):
            run_v2.require_nonempty_eligible_schedule([])


if __name__ == "__main__":
    unittest.main()
