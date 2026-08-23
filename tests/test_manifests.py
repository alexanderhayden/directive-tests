import json
import tempfile
import unittest
from pathlib import Path

from harness.manifests import (
    atomic_write_json,
    create_manifest,
    prepare_run_directory,
    sha256_file,
)


class ManifestTests(unittest.TestCase):
    def test_manifest_has_required_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prereg = root / "PREREGISTRATION.md"
            runner = root / "run.py"
            analysis = root / "analyze.py"
            config = root / "config.json"
            for path, text in (
                (prereg, "frozen"), (runner, "runner"), (analysis, "analysis"), (config, "{}")
            ):
                path.write_text(text)
            manifest = create_manifest(
                experiment_id="001A", run_id="test", repo_root=root,
                preregistration=prereg, runner=runner, analysis=analysis,
                config_paths=[config], model_ids=[{"model": "local"}], provider="Ollama",
                sampling_parameters={"temperature": 1.0}, planned_calls=2560,
                output_directory=root / "results" / "runs" / "test", schedule_sha256="abc",
            )
            required = {
                "experiment_id", "utc_start_time", "git_commit", "git_worktree_dirty",
                "preregistration_sha256", "runner_sha256", "analysis_script_sha256",
                "model_ids", "provider", "sampling_parameters", "planned_calls",
                "completed_calls", "failures", "output_directory",
            }
            self.assertLessEqual(required, manifest.keys())
            self.assertEqual(manifest["preregistration_sha256"], sha256_file(prereg))
            self.assertEqual(manifest["planned_calls"], 2560)

    def test_completed_run_directory_cannot_be_overwritten_or_resumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = prepare_run_directory(root, "frozen-run")
            atomic_write_json(run_dir / "manifest.json", {"lifecycle_status": "pilot_data_collected"})
            with self.assertRaises(FileExistsError):
                prepare_run_directory(root, "frozen-run")
            with self.assertRaises(FileExistsError):
                prepare_run_directory(root, "frozen-run", resume=True)

    def test_incomplete_run_requires_explicit_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = prepare_run_directory(root, "partial")
            (run_dir / "manifest.json").write_text(json.dumps({"lifecycle_status": "pilot_collecting"}))
            with self.assertRaises(FileExistsError):
                prepare_run_directory(root, "partial")
            self.assertEqual(prepare_run_directory(root, "partial", resume=True), run_dir)


if __name__ == "__main__":
    unittest.main()
