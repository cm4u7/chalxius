from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import behavioral_feature_gate as gate


class BehavioralFeatureGateTests(unittest.TestCase):
    def _fixture(self, root: Path) -> dict:
        (root / "scripts").mkdir(parents=True)
        (root / "references").mkdir()
        (root / "tests").mkdir()
        (root / "scripts" / "flow.py").write_text(
            "def path(enabled=True):\n"
            "    return {'ready': enabled}\n",
            encoding="utf-8",
        )
        (root / "tests" / "test_flow.py").write_text(
            "import unittest\n"
            "from flow import path\n\n"
            "class FlowTests(unittest.TestCase):\n"
            "    def test_positive(self):\n"
            "        self.assertTrue(path()['ready'])\n\n"
            "    def test_predicate_false(self):\n"
            "        self.assertFalse(path(False)['ready'])\n\n"
            "    def test_tamper(self):\n"
            "        self.assertNotEqual(path(), {'ready': False})\n\n"
            "    def test_boundary(self):\n"
            "        self.assertFalse(path(False)['ready'])\n",
            encoding="utf-8",
        )
        registry = {
            "schema_version": 1,
            "contract_revision": gate.REGISTRY_REVISION,
            "truth_effect": "none",
            "features": {
                "feature.flow": {
                    "classification": "normal_flow",
                    "lifecycle_decision": "retain_and_integrate",
                    "required": True,
                    "probes": {
                        "positive": "tests.test_flow.FlowTests.test_positive",
                        "predicate_false": (
                            "tests.test_flow.FlowTests.test_predicate_false"
                        ),
                        "tamper": "tests.test_flow.FlowTests.test_tamper",
                    },
                },
                "feature.manual": {
                    "classification": "explicit_manual",
                    "lifecycle_decision": "retain_bounded",
                    "replacement_feature_id": "",
                    "required": False,
                    "boundary_probe": "tests.test_flow.FlowTests.test_boundary",
                },
            },
        }
        self._write_registry(root, registry)
        return registry

    @staticmethod
    def _write_registry(root: Path, registry: dict) -> None:
        (root / gate.REGISTRY_RELATIVE).write_text(
            json.dumps(registry, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_executes_three_distinct_probe_roles_and_seals_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._fixture(root)
            registry_sha256, plan = gate._load_probe_plan(root)
            before = gate._snapshot_sha256(gate._snapshot(root))
            results = gate._execute_probe_plan(
                root=root,
                plan=plan,
                python=sys.executable,
                timeout_seconds=30,
                workers=3,
            )
            after = gate._snapshot_sha256(gate._snapshot(root))
            report = gate._report(
                registry_sha256=registry_sha256,
                plan=plan,
                results=results,
                source_before_sha256=before,
                source_after_sha256=after,
            )
            self.assertTrue(report["ok"], results)
            self.assertEqual(report["feature_count"], 2)
            self.assertEqual(report["probe_count"], 4)
            self.assertEqual(
                report["receipt_sha256"],
                gate._sha256(
                    gate._canonical_bytes(
                        {key: value for key, value in report.items() if key != "receipt_sha256"}
                    )
                ),
            )

    def test_duplicate_role_probe_and_malformed_registry_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = self._fixture(root)
            duplicate = deepcopy(registry)
            duplicate["features"]["feature.flow"]["probes"]["tamper"] = (
                duplicate["features"]["feature.flow"]["probes"]["positive"]
            )
            self._write_registry(root, duplicate)
            with self.assertRaisesRegex(ValueError, "must be distinct"):
                gate._load_probe_plan(root)

            boundary_missing = deepcopy(registry)
            boundary_missing["features"]["feature.manual"].pop("boundary_probe")
            self._write_registry(root, boundary_missing)
            with self.assertRaisesRegex(ValueError, "boundary probe"):
                gate._load_probe_plan(root)

            invalid_decision = deepcopy(registry)
            invalid_decision["features"]["feature.manual"][
                "lifecycle_decision"
            ] = "retire"
            self._write_registry(root, invalid_decision)
            with self.assertRaisesRegex(ValueError, "lifecycle disposition"):
                gate._load_probe_plan(root)

            (root / gate.REGISTRY_RELATIVE).write_text(
                '{"schema_version":1,"schema_version":1}\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "duplicate JSON"):
                gate._load_probe_plan(root)

    def test_failed_probe_and_source_drift_are_observable_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._fixture(root)
            registry_sha256, plan = gate._load_probe_plan(root)
            failed = [
                {
                    **item,
                    "returncode": 1 if item["probe_role"] == "tamper" else 0,
                    "timed_out": False,
                    "duration_seconds": 0.1,
                    "output_sha256": "a" * 64,
                    "output_tail": "failed" if item["probe_role"] == "tamper" else "ok",
                    "ok": item["probe_role"] != "tamper",
                }
                for item in plan
            ]
            report = gate._report(
                registry_sha256=registry_sha256,
                plan=plan,
                results=failed,
                source_before_sha256="b" * 64,
                source_after_sha256="c" * 64,
            )
            self.assertFalse(report["ok"])
            self.assertFalse(report["source_unchanged"])
            self.assertFalse(report["features"][0]["ok"])

            failed_boundary = [
                {
                    **item,
                    "returncode": (
                        1 if item["probe_role"] == gate.BOUNDARY_PROBE_ROLE else 0
                    ),
                    "timed_out": False,
                    "duration_seconds": 0.1,
                    "output_sha256": "d" * 64,
                    "output_tail": (
                        "failed boundary"
                        if item["probe_role"] == gate.BOUNDARY_PROBE_ROLE
                        else "ok"
                    ),
                    "ok": item["probe_role"] != gate.BOUNDARY_PROBE_ROLE,
                }
                for item in plan
            ]
            boundary_report = gate._report(
                registry_sha256=registry_sha256,
                plan=plan,
                results=failed_boundary,
                source_before_sha256="e" * 64,
                source_after_sha256="e" * 64,
            )
            self.assertFalse(boundary_report["ok"])
            manual = next(
                item
                for item in boundary_report["features"]
                if item["feature_id"] == "feature.manual"
            )
            self.assertFalse(manual["ok"])


if __name__ == "__main__":
    unittest.main()
