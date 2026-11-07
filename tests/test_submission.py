import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from snapshot_io import safe_path, verify_manifest, enrich_manifest


class SubmissionContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / ".cache").mkdir(exist_ok=True)

    def test_comparison_rejects_nonfinite_values(self):
        spec = importlib.util.spec_from_file_location("suite_compare_test", ROOT / "code/compare.py")
        compare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(compare)
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache") as tmp:
            root = Path(tmp)
            path = root / "questions/q2/results/approach2/fixture/metrics.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"params": {}, "metrics": {"hedging": {"case": {"deep": {"cvar95": float("nan")}, "bs": {"cvar95": 1}}}}, "fit_seconds": 0, "history": {}}))
            with self.assertRaisesRegex(ValueError, "Nonfinite"):
                compare.comparable_groups(root)

    def test_comparison_excludes_historical_leaky_results(self):
        spec = importlib.util.spec_from_file_location("suite_compare_test", ROOT / "code/compare.py")
        compare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(compare)
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache") as tmp:
            root = Path(tmp)
            path = root / "questions/q4/results/approach2/fixture/metrics.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"params": {}, "metrics": {"learned": {"auc": .99}, "baselines": {}}, "fit_seconds": 0, "history": {}}))
            self.assertEqual(compare.comparable_groups(root)[1], {})

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(ValueError):
            safe_path(ROOT, "../outside.csv")

    def test_manifest_detects_corruption_and_missing_files(self):
        cache = ROOT / ".cache"
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as tmp:
            base = Path(tmp)
            file = base / "series.csv"
            file.write_text("date,close\n2025-01-02,100\n")
            manifest = base / "metadata.json"
            manifest.write_text(json.dumps({"artifacts": {"series.csv": {}}}))
            enrich_manifest(base, manifest)
            verify_manifest(base, manifest)
            file.write_text("date,close\n2025-01-02,101\n")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                verify_manifest(base, manifest)
            file.unlink()
            with self.assertRaises(OSError):
                verify_manifest(base, manifest)

    def test_dry_run_verify_has_no_uv_commands(self):
        import contextlib, io
        import run
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            run.main(["all", "--stage", "verify", "--dry-run"])
        self.assertNotIn("command:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
