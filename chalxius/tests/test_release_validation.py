from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

import release_validation


class ReleaseValidationTests(unittest.TestCase):
    def _candidate(self, root: Path) -> tuple[Path, list[str], str]:
        candidate = root / "candidate"
        scripts = candidate / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "helper.py").write_text("VALUE = 7\n", encoding="utf-8")
        (scripts / "probe.py").write_text(
            "import helper\nassert helper.VALUE == 7\n", encoding="utf-8"
        )
        entries = ["scripts/helper.py", "scripts/probe.py"]
        rows = []
        for relative in entries:
            digest = hashlib.sha256((candidate / relative).read_bytes()).hexdigest()
            rows.append(f"{digest}  {relative}")
        (candidate / "MANIFEST.sha256").write_text(
            "\n".join(rows) + "\n", encoding="utf-8"
        )
        parsed, manifest_sha256 = release_validation._manifest_entries(candidate)
        return candidate, parsed, manifest_sha256

    def test_manifest_bound_lanes_are_distinct_exact_copies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate, entries, manifest_sha256 = self._candidate(root)
            lane_roots = release_validation._isolated_lane_roots(
                root, ["lane-a", "lane-b"]
            )
            first = lane_roots["lane-a"]
            second = lane_roots["lane-b"]
            release_validation._copy_manifest_tree(candidate, first, entries)
            release_validation._copy_manifest_tree(candidate, second, entries)
            self.assertNotEqual(first.resolve(), second.resolve())
            self.assertEqual(first, first.resolve())
            self.assertEqual(second, second.resolve())
            self.assertEqual(
                release_validation._manifest_entries(first)[1], manifest_sha256
            )
            self.assertEqual(
                release_validation._manifest_entries(second)[1], manifest_sha256
            )
            (first / "unexpected.txt").write_text("drift\n", encoding="utf-8")
            self.assertFalse((second / "unexpected.txt").exists())
            lanes = release_validation._default_lanes(release_validation.sys.executable)
            phases = {lane.name: lane.phase for lane in lanes}
            self.assertGreater(phases["aggressive_bug_audit"], phases["full_suite"])
            self.assertGreater(phases["aggressive_bug_audit"], phases["self_test"])

    def test_lane_runner_suppresses_bytecode_and_rejects_any_lane_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate, entries, manifest_sha256 = self._candidate(root)
            clean = root / "clean"
            release_validation._copy_manifest_tree(candidate, clean, entries)
            clean_result = release_validation._run_lane(
                lane=release_validation.Lane(
                    "clean", (release_validation.sys.executable, "scripts/probe.py")
                ),
                lane_root=clean,
                manifest_sha256=manifest_sha256,
                timeout_seconds=30,
            )
            self.assertTrue(clean_result["ok"])
            self.assertEqual(list(clean.rglob("__pycache__")), [])
            self.assertEqual(list(clean.rglob("*.pyc")), [])

            dirty = root / "dirty"
            release_validation._copy_manifest_tree(candidate, dirty, entries)
            (dirty / "scripts" / "probe.py").write_text(
                "from pathlib import Path\nPath('unexpected.txt').write_text('drift')\n",
                encoding="utf-8",
            )
            dirty_before = release_validation._snapshot(dirty)
            dirty_result = release_validation._run_lane(
                lane=release_validation.Lane(
                    "dirty", (release_validation.sys.executable, "scripts/probe.py")
                ),
                lane_root=dirty,
                manifest_sha256=manifest_sha256,
                timeout_seconds=30,
            )
            self.assertNotEqual(dirty_before, release_validation._snapshot(dirty))
            self.assertFalse(dirty_result["lane_unchanged"])
            self.assertFalse(dirty_result["ok"])


if __name__ == "__main__":
    unittest.main()
