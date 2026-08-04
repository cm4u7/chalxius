from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
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
            self.assertLess(
                phases["architecture_reconnaissance"], phases["full_suite"]
            )
            self.assertLess(
                phases["architecture_reconnaissance"], phases["self_test"]
            )
            self.assertLess(
                phases["architecture_reconnaissance"],
                phases["behavioral_feature_gate"],
            )
            self.assertLess(
                phases["behavioral_feature_gate"], phases["full_suite"]
            )
            self.assertLess(
                phases["behavioral_feature_gate"], phases["self_test"]
            )
            self.assertGreater(phases["aggressive_bug_audit"], phases["full_suite"])
            self.assertGreater(phases["aggressive_bug_audit"], phases["self_test"])
            self.assertLess(
                phases["mutant_registry_preflight"], phases["full_suite"]
            )
            self.assertLess(
                phases["mutant_registry_preflight"], phases["self_test"]
            )

    def test_current_mutant_registry_preflight_is_cheap_read_only_lane(self) -> None:
        candidate = Path(release_validation.__file__).resolve().parents[1]
        before = release_validation._snapshot(candidate)
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        outcome = subprocess.run(
            [
                release_validation.sys.executable,
                "scripts/aggressive_bug_audit.py",
                "--preflight-only",
            ],
            cwd=candidate,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        )
        self.assertEqual(outcome.returncode, 0, outcome.stdout)
        receipt = json.loads(outcome.stdout)
        self.assertTrue(receipt["ok"])
        self.assertEqual(
            receipt["mutant_count"], receipt["exact_single_target_count"]
        )
        self.assertEqual(before, release_validation._snapshot(candidate))

    def test_failed_architecture_phase_has_explicit_bounded_skip_records(self) -> None:
        manifest_sha256 = "a" * 64
        lanes = release_validation._default_lanes(release_validation.sys.executable)
        architecture = next(
            lane for lane in lanes if lane.name == "architecture_reconnaissance"
        )
        results = [
            {
                "lane": architecture.name,
                "phase": architecture.phase,
                "manifest_sha256": manifest_sha256,
                "lane_unchanged": True,
                "ok": False,
            }
        ]
        results.extend(
            release_validation._skipped_lane_result(
                lane=lane,
                manifest_sha256=manifest_sha256,
                failed_phase=architecture.phase,
            )
            for lane in lanes
            if lane is not architecture
        )
        report = release_validation._aggregate(
            expected_lanes=lanes,
            manifest_sha256=manifest_sha256,
            results=results,
            source_unchanged=True,
        )
        self.assertFalse(report["ok"])
        self.assertTrue(report["architecture_gate_before_baseline"])
        self.assertTrue(
            report["behavioral_gate_after_architecture_before_baseline"]
        )
        self.assertEqual(
            report["skipped_lanes"],
            sorted(lane.name for lane in lanes if lane is not architecture),
        )
        self.assertTrue(
            all(
                result.get("skipped_due_to_prior_phase") is True
                for result in results[1:]
            )
        )

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
