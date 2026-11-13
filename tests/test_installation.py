import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools/check-installation.py"
spec = importlib.util.spec_from_file_location("installation", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.py"
        self.live = self.root / "installed.py"
        self.source.write_text("original")
        self.live.write_text("original")
        self.data = {"schema": "creation-deployment/1", "records": [{
            "source": str(self.source), "installed": str(self.live), "sha256": module.digest(self.source)}]}

    def test_matching_source_and_installation(self):
        self.assertEqual(module.check(self.data)[0]["status"], "ok")

    def test_changed_installation(self):
        self.live.write_text("changed")
        self.assertEqual(module.check(self.data)[0]["status"], "out-of-sync")
        self.assertEqual(self.source.read_text(), "original")
        self.assertEqual(self.live.read_text(), "changed")

    def test_changed_source(self):
        self.source.write_text("changed")
        self.assertEqual(module.check(self.data)[0]["status"], "out-of-sync")

    def test_matching_changes_require_manifest_refresh(self):
        self.source.write_text("changed")
        self.live.write_text("changed")
        self.assertEqual(module.check(self.data)[0]["status"], "manifest-stale")

    def test_missing_file_and_invalid_manifest(self):
        self.live.unlink()
        self.assertEqual(module.check(self.data)[0]["status"], "missing-or-unreadable")
        for data in [None, {}, {"schema": "creation-deployment/1", "records": [{}]}]:
            with self.assertRaises(ValueError):
                module.check(data)

    def test_cli_exit_codes_and_no_content_disclosure(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps(self.data))
        args = [sys.executable, "-B", str(SCRIPT), "--manifest", str(manifest), "--json"]
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("original", result.stdout)
        self.live.write_text("changed")
        self.assertEqual(subprocess.run(args, capture_output=True).returncode, 1)
        manifest.write_text("invalid")
        self.assertEqual(subprocess.run(args, capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
