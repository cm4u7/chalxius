from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from chx_ledger import (
    CONTRACT_REVISION,
    close_ledger,
    dispose_issue,
    ledger_status,
    main,
    record_issue,
    start_ledger,
)
from mathgraph.store import MathGraphStore


class CHXRunLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="chalxius-chx-ledger-")
        self.root = Path(self.temporary.name) / "host-work"
        self.project = (Path(self.temporary.name) / "project").resolve()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _issue() -> dict[str, object]:
        return {
            "classification": "completion reporting / causal traceability",
            "causation": "caused",
            "mechanism_type": "interface_contract",
            "mechanism": (
                "The host completion contract had no task-scoped CHX ledger "
                "or conditional feedback rule."
            ),
            "trigger": "A Chalxius run reached final reporting.",
            "observed_effect": (
                "A qualifying architecture problem could be omitted from the handoff."
            ),
            "mathematical_effect": "none",
            "current_workaround": "Record the issue explicitly in the task notes.",
            "upgrade_requirement": (
                "Create and close one causal CHX ledger for every new run."
            ),
            "audit_anchors": ["host-task:test-run", "check:completion-contract"],
        }

    def _started(self, run_id: str = "run-test-001") -> Path:
        receipt = start_ledger(
            project_root=self.project,
            task="Exercise the task-scoped CHX ledger.",
            run_id=run_id,
            host_task_scope_id="hosttask-test-scope",
        )
        self.assertEqual(receipt["contract_revision"], CONTRACT_REVISION)
        ledger = Path(receipt["ledger_path"])
        self.assertEqual(ledger.parent, self.project / "chx-ledgers")
        return ledger

    def test_current_contract_uses_project_local_revision(self) -> None:
        self.assertEqual(CONTRACT_REVISION, "chalxius-chx-run-ledger-2")

    def test_project_local_ledger_can_precede_v5_initialization_and_audit(self) -> None:
        ledger = self._started("run-pre-init-001")
        before = ledger.read_bytes()

        store = MathGraphStore(self.project)
        store.initialize(
            project_id="chx-ledger-project",
            title="Project-local CHX ledger compatibility",
            workflow_evidence_version=5,
        )
        report = store.audit()

        self.assertTrue(report.current_ok)
        self.assertEqual(ledger.read_bytes(), before)
        self.assertEqual(store.fact_ids(), [])

    def test_projectless_fallback_remains_available_outside_the_skill(self) -> None:
        receipt = start_ledger(
            root=self.root,
            task="Exercise the projectless fallback.",
            run_id="run-projectless-001",
        )
        ledger = Path(receipt["ledger_path"])
        self.assertEqual(ledger.parent, self.root.resolve())
        self.assertFalse(self.project in ledger.parents)
        self.assertFalse(close_ledger(ledger)["report_required"])

    def test_start_requires_exactly_one_storage_scope(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one"):
            start_ledger(
                task="Missing placement.",
                run_id="run-no-placement-001",
            )
        with self.assertRaisesRegex(ValueError, "exactly one"):
            start_ledger(
                project_root=self.project,
                root=self.root,
                task="Ambiguous placement.",
                run_id="run-two-placements-001",
            )

    def test_empty_run_is_persisted_but_requires_no_feedback(self) -> None:
        ledger = self._started()
        opened = ledger_status(ledger)
        self.assertEqual(opened["state"], "open")
        self.assertEqual(opened["issue_count"], 0)
        self.assertFalse(opened["report_required"])

        closed = close_ledger(ledger)
        self.assertEqual(closed["state"], "closed")
        self.assertEqual(closed["issue_count"], 0)
        self.assertFalse(closed["report_required"])
        self.assertEqual(close_ledger(ledger), closed)

    def test_qualifying_issue_is_hash_chained_and_reportable(self) -> None:
        ledger = self._started()
        recorded = record_issue(ledger, self._issue())
        self.assertEqual(recorded["issue_id"], "CHX-001")

        closed = close_ledger(ledger)
        self.assertTrue(closed["report_required"])
        self.assertEqual(closed["issue_count"], 1)
        self.assertEqual(closed["issues"][0]["issue_id"], "CHX-001")
        self.assertEqual(closed["issues"][0]["status"], "open")

        events = [
            json.loads(line)
            for line in ledger.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(
            [event["event"] for event in events],
            ["run_started", "issue_observed", "run_closed"],
        )
        self.assertEqual(events[0]["previous_event_sha256"], "")
        self.assertEqual(
            events[1]["previous_event_sha256"], events[0]["event_sha256"]
        )
        self.assertEqual(
            events[2]["previous_event_sha256"], events[1]["event_sha256"]
        )

    def test_excluded_noncausal_entry_suppresses_final_feedback(self) -> None:
        ledger = self._started()
        record_issue(ledger, self._issue())
        dispose_issue(
            ledger,
            issue_id="CHX-001",
            disposition={
                "status": "excluded_nonarchitectural",
                "reason": "The observed event was an ordinary host typo.",
                "regression_evidence": [],
            },
        )
        closed = close_ledger(ledger)
        self.assertEqual(closed["issue_count"], 0)
        self.assertEqual(closed["excluded_issue_count"], 1)
        self.assertFalse(closed["report_required"])

    def test_resolution_requires_reproducible_regression_evidence(self) -> None:
        ledger = self._started()
        record_issue(ledger, self._issue())
        with self.assertRaisesRegex(ValueError, "regression evidence"):
            dispose_issue(
                ledger,
                issue_id="CHX-001",
                disposition={
                    "status": "resolved",
                    "reason": "Implemented the repair.",
                    "regression_evidence": [],
                },
            )
        dispose_issue(
            ledger,
            issue_id="CHX-001",
            disposition={
                "status": "resolved",
                "reason": "Implemented the repair.",
                "regression_evidence": ["tests/test_chx_ledger.py:PASS"],
            },
        )
        closed = close_ledger(ledger)
        self.assertTrue(closed["report_required"])
        self.assertEqual(closed["issues"][0]["status"], "resolved")

    def test_schema_rejects_ordinary_or_unanchored_error_notes(self) -> None:
        ledger = self._started()
        issue = self._issue()
        issue["causation"] = "ordinary_error"
        with self.assertRaisesRegex(ValueError, "causation"):
            record_issue(ledger, issue)

        issue = self._issue()
        issue["audit_anchors"] = []
        with self.assertRaisesRegex(ValueError, "audit_anchors"):
            record_issue(ledger, issue)

    def test_tampering_and_post_close_append_fail_closed(self) -> None:
        ledger = self._started()
        record_issue(ledger, self._issue())
        close_ledger(ledger)
        with self.assertRaisesRegex(ValueError, "closed"):
            record_issue(ledger, self._issue())

        lines = ledger.read_text(encoding="utf-8").splitlines()
        event = json.loads(lines[1])
        event["observed_effect"] = "tampered"
        lines[1] = json.dumps(event, ensure_ascii=False, sort_keys=True)
        ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash"):
            ledger_status(ledger)

    def test_concurrent_records_allocate_unique_sequential_ids(self) -> None:
        ledger = self._started("run-concurrent-001")
        with ThreadPoolExecutor(max_workers=6) as pool:
            events = list(pool.map(lambda _: record_issue(ledger, self._issue()), range(12)))
        self.assertEqual(
            sorted(event["issue_id"] for event in events),
            [f"CHX-{index:03d}" for index in range(1, 13)],
        )
        closed = close_ledger(ledger)
        self.assertEqual(closed["issue_count"], 12)

    def test_cli_round_trip_and_skill_root_rejection(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = main(
                [
                    "start",
                    "--project-root",
                    str(self.project),
                    "--run-id",
                    "run-cli-001",
                    "--task",
                    "CLI smoke test",
                ]
            )
        self.assertEqual(code, 0)
        receipt = json.loads(output.getvalue())
        ledger = Path(receipt["ledger_path"])
        self.assertTrue(ledger.is_file())
        self.assertEqual(ledger.parent, self.project / "chx-ledgers")

        skill_root = Path(__file__).resolve().parents[1]
        with self.assertRaisesRegex(ValueError, "outside the skill"):
            start_ledger(
                project_root=skill_root / "forbidden-project",
                task="Forbidden placement",
                run_id="run-forbidden-001",
            )

    def test_symlink_paths_are_rejected(self) -> None:
        real_root = Path(self.temporary.name) / "real-host-state"
        real_root.mkdir()
        linked_root = Path(self.temporary.name) / "linked-host-state"
        linked_root.symlink_to(real_root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            start_ledger(
                project_root=linked_root,
                task="Reject a linked root.",
                run_id="run-linked-root-001",
            )

        ledger = self._started("run-real-ledger-001")
        linked_ledger = Path(self.temporary.name) / "linked-ledger.jsonl"
        linked_ledger.symlink_to(ledger)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            ledger_status(linked_ledger)

    def test_open_revision_one_ledger_remains_appendable_and_closable(self) -> None:
        with patch(
            "chx_ledger.CONTRACT_REVISION",
            "chalxius-chx-run-ledger-1",
        ):
            receipt = start_ledger(
                root=self.root,
                task="Create a pre-placement-contract ledger.",
                run_id="run-revision-one-001",
            )
        ledger = Path(receipt["ledger_path"])

        observed = record_issue(ledger, self._issue())
        self.assertEqual(
            observed["contract_revision"], "chalxius-chx-run-ledger-1"
        )
        disposed = dispose_issue(
            ledger,
            issue_id="CHX-001",
            disposition={
                "status": "resolved",
                "reason": "Compatibility was preserved.",
                "regression_evidence": ["revision-one-round-trip:PASS"],
            },
        )
        self.assertEqual(
            disposed["contract_revision"], "chalxius-chx-run-ledger-1"
        )
        closed = close_ledger(ledger)
        self.assertEqual(
            closed["contract_revision"], "chalxius-chx-run-ledger-1"
        )
        self.assertEqual(closed["issues"][0]["status"], "resolved")

    def test_policy_is_prospective_and_never_reopens_existing_work(self) -> None:
        skill_root = Path(__file__).resolve().parents[1]
        policy = (skill_root / "references" / "chx_runtime_ledger.md").read_text(
            encoding="utf-8"
        )
        skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        for marker in (
            "runs started after the 0.4.1 activation boundary",
            "must not be backfilled",
            "never an audit warning, certification blocker, or reason to redo work",
            "Project-bound runs store their ledger at `PROJECT/chx-ledgers/`",
            "Projectless runs use private host task state outside the skill",
            "If `report_required=false`, say nothing about the CHX ledger",
        ):
            self.assertIn(marker, policy + "\n" + skill)


if __name__ == "__main__":
    unittest.main()
