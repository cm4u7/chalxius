from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import chx_ledger
from chx_ledger import (
    ARCHITECTURE_RECONNAISSANCE_CONTRACT_REVISION,
    CONTRACT_REVISION,
    close_ledger,
    dispose_issue,
    ledger_status,
    main,
    record_finding,
    record_architecture_reconnaissance,
    record_integrated_repair,
    record_issue,
    record_tactical_repair,
    reconcile_finding,
    start_ledger,
    validate_public_disclosure_contract,
    verify_architecture_report,
    verify_public_disclosure,
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

    def _reconnaissance_report(self) -> dict[str, object]:
        candidate_root = Path(chx_ledger.__file__).resolve().parents[1]
        report: dict[str, object] = {
            "schema_version": 1,
            "contract_revision": ARCHITECTURE_RECONNAISSANCE_CONTRACT_REVISION,
            "root": str(candidate_root),
            "version": (candidate_root / "VERSION").read_text(
                encoding="utf-8"
            ).strip(),
            "counts": {"files": 1},
            "generated_artifacts": [],
            "manifest": {},
            "modules": {},
            "unreferenced_modules": [],
            "production_unreferenced_modules": [],
            "orphan_modules": [],
            "exact_duplicate_files": [],
            "duplicate_function_bodies": [],
            "duplicate_body_adjudication": {
                "registry_sha256": "3" * 64,
                "ok": True,
            },
            "commands": {},
            "capability_registry": {"registry_sha256": "1" * 64},
            "behavioral_features": {"registry_sha256": "2" * 64},
            "baseline_comparison": None,
            "installed_comparison": None,
            "errors": [],
            "warnings": [],
            "truth_effect": "none",
        }
        report["inventory_sha256"] = hashlib.sha256(
            json.dumps(
                report,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return report

    @staticmethod
    def _tactical(mechanism_id: str = "mechanism.chx_repair_gate") -> dict[str, object]:
        return {
            "mechanism_id": mechanism_id,
            "summary": "Bind a reusable repair before resolution.",
            "applicability": "Any repair-aware CHX issue with this failure mode.",
            "implementation": "Record a typed, fail-closed repair handoff.",
            "fail_closed_boundary": "Resolution is unavailable when the handoff is missing.",
            "reusable_domains": ["cross_domain"],
            "implementation_anchors": ["scripts/chx_ledger.py"],
            "bounded_validation_evidence": ["tests/test_chx_ledger.py:PASS"],
        }

    @staticmethod
    def _integration(issue_ids: list[str]) -> dict[str, object]:
        return {
            "included_issue_ids": issue_ids,
            "coordination_decisions": [
                {
                    "decision_id": "decision.coordinated_gate",
                    "affected_issue_ids": issue_ids,
                    "decision": "Use one coordinated repair gate.",
                    "rationale": "The selected mechanisms must compose without bypass.",
                }
            ],
            "risk_evidence": ["risk-matrix:PASS"],
            "regression_evidence": [
                "lineage-predecessor:PASS",
                "test-public-predecessor:PASS",
                "test-public-successor:PASS",
                "tests/test_chx_ledger.py:PASS",
            ],
        }

    def _repair_chain(self, ledger: Path, issue_ids: list[str]) -> dict[str, object]:
        reconnaissance = record_architecture_reconnaissance(
            ledger, self._reconnaissance_report()
        )
        for issue_id in issue_ids:
            record_tactical_repair(
                ledger,
                issue_id=issue_id,
                reconnaissance_id=reconnaissance["reconnaissance_id"],
                repair=self._tactical(),
            )
        return record_integrated_repair(ledger, self._integration(issue_ids))

    def test_current_contract_uses_project_local_revision(self) -> None:
        self.assertEqual(CONTRACT_REVISION, "chalxius-chx-run-ledger-5")

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
        self.assertEqual(closed["architecture_report"]["status"], "exact")
        self.assertEqual(
            verify_architecture_report(ledger),
            closed["architecture_report"],
        )
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
            [
                "run_started",
                "finding_observed",
                "issue_observed",
                "finding_reconciled",
                "run_closed",
            ],
        )
        self.assertEqual(events[0]["previous_event_sha256"], "")
        self.assertEqual(
            events[1]["previous_event_sha256"], events[0]["event_sha256"]
        )
        for previous, event in zip(events, events[1:]):
            self.assertEqual(
                event["previous_event_sha256"], previous["event_sha256"]
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
        self._repair_chain(ledger, ["CHX-001"])
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

    def test_revision_five_resolution_requires_all_three_repair_gates(self) -> None:
        ledger = self._started("run-repair-gates-001")
        record_issue(ledger, self._issue())
        disposition = {
            "status": "resolved",
            "reason": "Exercise the prospective repair gates.",
            "regression_evidence": ["tests/test_chx_ledger.py:PASS"],
        }
        with self.assertRaisesRegex(ValueError, "tactical repair"):
            dispose_issue(ledger, issue_id="CHX-001", disposition=disposition)

        with self.assertRaisesRegex(ValueError, "prior architecture reconnaissance"):
            record_tactical_repair(
                ledger,
                issue_id="CHX-001",
                reconnaissance_id="reconnaissance-" + "0" * 64,
                repair=self._tactical(),
            )
        reconnaissance = record_architecture_reconnaissance(
            ledger, self._reconnaissance_report()
        )
        tactical = record_tactical_repair(
            ledger,
            issue_id="CHX-001",
            reconnaissance_id=reconnaissance["reconnaissance_id"],
            repair=self._tactical(),
        )
        self.assertEqual(tactical["issue_id"], "CHX-001")
        with self.assertRaisesRegex(ValueError, "integrated repair"):
            dispose_issue(ledger, issue_id="CHX-001", disposition=disposition)

        integrated = record_integrated_repair(
            ledger, self._integration(["CHX-001"])
        )
        self.assertEqual(
            integrated["reusable_mechanism_registry"]["mechanisms"][0][
                "issue_bindings"
            ][0]["tactical_repair_id"],
            tactical["tactical_repair_id"],
        )
        unbound = {**disposition, "regression_evidence": ["unbound:PASS"]}
        with self.assertRaisesRegex(ValueError, "not bound"):
            dispose_issue(ledger, issue_id="CHX-001", disposition=unbound)
        dispose_issue(ledger, issue_id="CHX-001", disposition=disposition)
        status = close_ledger(ledger)
        self.assertTrue(status["repair_gate"]["all_resolved_covered"])
        self.assertEqual(close_ledger(ledger), status)
        self.assertEqual(ledger_status(ledger), status)

    def test_integrated_registry_tamper_fails_beyond_the_event_hash(self) -> None:
        ledger = self._started("run-repair-tamper-001")
        record_issue(ledger, self._issue())
        self._repair_chain(ledger, ["CHX-001"])
        lines = ledger.read_text(encoding="utf-8").splitlines()
        event = json.loads(lines[-1])
        event["reusable_mechanism_registry"]["mechanisms"][0]["summary"] = (
            "tampered reusable mechanism"
        )
        semantic = {
            key: value for key, value in event.items() if key != "event_sha256"
        }
        event["event_sha256"] = hashlib.sha256(
            json.dumps(
                semantic,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        lines[-1] = json.dumps(
            event,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "registry drifted"):
            ledger_status(ledger)

    def test_late_issue_requires_a_superseding_integrated_full_coverage(self) -> None:
        ledger = self._started("run-late-repair-001")
        record_issue(ledger, self._issue())
        first = self._repair_chain(ledger, ["CHX-001"])
        dispose_issue(
            ledger,
            issue_id="CHX-001",
            disposition={
                "status": "resolved",
                "reason": "First repair is complete.",
                "regression_evidence": ["tests/test_chx_ledger.py:PASS"],
            },
        )
        second_issue = self._issue()
        second_issue["audit_anchors"] = ["late-repair:CHX-002"]
        record_issue(ledger, second_issue)
        reconnaissance_id = ledger_status(ledger)[
            "architecture_reconnaissance_receipts"
        ][0]["reconnaissance_id"]
        record_tactical_repair(
            ledger,
            issue_id="CHX-002",
            reconnaissance_id=reconnaissance_id,
            repair=self._tactical(),
        )
        with self.assertRaisesRegex(ValueError, "previously resolved"):
            record_integrated_repair(ledger, self._integration(["CHX-002"]))
        second = record_integrated_repair(
            ledger, self._integration(["CHX-001", "CHX-002"])
        )
        self.assertEqual(
            second["supersedes_integrated_repair_id"],
            first["integrated_repair_id"],
        )
        dispose_issue(
            ledger,
            issue_id="CHX-002",
            disposition={
                "status": "resolved",
                "reason": "Late repair is coordinated with the prior repair.",
                "regression_evidence": ["tests/test_chx_ledger.py:PASS"],
            },
        )
        status = close_ledger(ledger)
        self.assertEqual(
            status["repair_gate"]["latest_covered_issue_ids"],
            ["CHX-001", "CHX-002"],
        )

    def test_revisions_one_through_four_keep_their_original_event_shapes(self) -> None:
        revisions = [
            "chalxius-chx-run-ledger-1",
            "chalxius-chx-run-ledger-2",
            "chalxius-chx-run-ledger-3",
            "chalxius-chx-run-ledger-4",
        ]
        for index, revision in enumerate(revisions, 1):
            with self.subTest(revision=revision), patch(
                "chx_ledger.CONTRACT_REVISION", revision
            ):
                ledger = Path(
                    start_ledger(
                        root=self.root,
                        task="Preserve historical append semantics.",
                        run_id=f"run-historical-{index:03d}",
                    )["ledger_path"]
                )
            record_issue(ledger, self._issue())
            dispose_issue(
                ledger,
                issue_id="CHX-001",
                disposition={
                    "status": "resolved",
                    "reason": "Historical semantics remain appendable.",
                    "regression_evidence": ["historical-round-trip:PASS"],
                },
            )
            status = close_ledger(ledger)
            self.assertEqual(status["contract_revision"], revision)
            self.assertNotIn("repair_gate", status)
            events = [
                json.loads(line)
                for line in ledger.read_text(encoding="utf-8").splitlines()
            ]
            expected = (
                ["run_started", "issue_observed", "issue_disposition", "run_closed"]
                if index <= 2
                else [
                    "run_started",
                    "finding_observed",
                    "issue_observed",
                    "finding_reconciled",
                    "issue_disposition",
                    "run_closed",
                ]
            )
            self.assertEqual([event["event"] for event in events], expected)
            self.assertEqual(
                "predecessor_lineage" in events[0],
                revision == "chalxius-chx-run-ledger-4",
            )

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
        def distinct_issue(index: int) -> dict[str, object]:
            issue = self._issue()
            issue["audit_anchors"] = [
                *issue["audit_anchors"],
                f"concurrent-finding:{index}",
            ]
            return issue

        with ThreadPoolExecutor(max_workers=6) as pool:
            events = list(pool.map(
                lambda index: record_issue(ledger, distinct_issue(index)),
                range(12),
            ))
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

    def test_revision_five_repair_cli_round_trip(self) -> None:
        ledger = self._started("run-repair-cli-001")
        record_issue(ledger, self._issue())
        inputs = Path(self.temporary.name) / "repair-inputs"
        inputs.mkdir()
        reconnaissance_path = inputs / "reconnaissance.json"
        tactical_path = inputs / "tactical.json"
        integrated_path = inputs / "integrated.json"
        reconnaissance_path.write_text(
            json.dumps(self._reconnaissance_report(), sort_keys=True),
            encoding="utf-8",
        )
        tactical_path.write_text(
            json.dumps(self._tactical(), sort_keys=True),
            encoding="utf-8",
        )
        integrated_path.write_text(
            json.dumps(self._integration(["CHX-001"]), sort_keys=True),
            encoding="utf-8",
        )
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(
                main(
                    [
                        "record-reconnaissance",
                        "--ledger",
                        str(ledger),
                        "--input",
                        str(reconnaissance_path),
                    ]
                ),
                0,
            )
        reconnaissance_id = json.loads(output.getvalue())[
            "reconnaissance_id"
        ]
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(
                main(
                    [
                        "record-tactical-repair",
                        "--ledger",
                        str(ledger),
                        "--issue-id",
                        "CHX-001",
                        "--reconnaissance-id",
                        reconnaissance_id,
                        "--input",
                        str(tactical_path),
                    ]
                ),
                0,
            )
        self.assertEqual(json.loads(output.getvalue())["issue_id"], "CHX-001")
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(
                main(
                    [
                        "record-integrated-repair",
                        "--ledger",
                        str(ledger),
                        "--input",
                        str(integrated_path),
                    ]
                ),
                0,
            )
        self.assertEqual(
            json.loads(output.getvalue())["included_issue_ids"],
            ["CHX-001"],
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

    def test_finding_gate_and_derived_report_fail_closed(self) -> None:
        ledger = self._started("run-finding-gate-001")
        issue = self._issue()
        finding = {key: value for key, value in issue.items() if key != "causation"}
        observed = record_finding(ledger, finding)
        with self.assertRaisesRegex(ValueError, "unreconciled findings"):
            close_ledger(ledger)
        reconcile_finding(
            ledger,
            finding_id=observed["finding_id"],
            status="excluded_with_reason",
            reason="The mechanism was ruled out by the frozen audit anchor.",
        )
        closed = close_ledger(ledger)
        report = verify_architecture_report(ledger)
        self.assertEqual(report["status"], "exact")
        self.assertEqual(closed["unreconciled_finding_ids"], [])
        report_path = Path(report["report_path"])
        report_path.write_text(report_path.read_text() + "drift", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "drifted"):
            ledger_status(ledger)

    def test_closed_ledger_late_finding_uses_hash_bound_successor(self) -> None:
        predecessor = self._started("run-predecessor-001")
        record_issue(predecessor, self._issue())
        close_ledger(predecessor)
        issue = self._issue()
        issue["audit_anchors"] = ["late-finding:CHX-013"]
        finding = {key: value for key, value in issue.items() if key != "causation"}
        receipt = start_ledger(
            project_root=self.project,
            task="Capture a late finding without reopening history.",
            run_id="run-successor-001",
            predecessor_ledger=predecessor,
            inherited_findings=[finding],
        )
        successor = Path(receipt["ledger_path"])
        self.assertEqual(
            receipt["predecessor_ledger_sha256"],
            __import__("hashlib").sha256(predecessor.read_bytes()).hexdigest(),
        )
        inherited_id = receipt["unreconciled_finding_ids"][0]
        promoted = record_issue(successor, issue, finding_id=inherited_id)
        self.assertEqual(promoted["issue_id"], "CHX-002")

    def test_successor_carries_transitive_issue_lineage_across_empty_hop(self) -> None:
        predecessor = self._started("run-lineage-predecessor-001")
        record_issue(predecessor, self._issue())
        self._repair_chain(predecessor, ["CHX-001"])
        dispose_issue(
            predecessor,
            issue_id="CHX-001",
            disposition={
                "status": "resolved",
                "reason": "The first mechanism was repaired.",
                "regression_evidence": ["lineage-predecessor:PASS"],
            },
        )
        close_ledger(predecessor)

        middle = Path(
            start_ledger(
                project_root=self.project,
                task="Preserve an issue-free lineage hop.",
                run_id="run-lineage-middle-001",
                predecessor_ledger=predecessor,
            )["ledger_path"]
        )
        close_ledger(middle)
        successor_status = start_ledger(
            project_root=self.project,
            task="Exercise transitive issue allocation and relations.",
            run_id="run-lineage-successor-001",
            predecessor_ledger=middle,
        )
        self.assertEqual(successor_status["predecessor_issue_ids"], ["CHX-001"])
        self.assertEqual(
            [entry["ledger_run_id"] for entry in successor_status["predecessor_lineage"]],
            ["run-lineage-predecessor-001", "run-lineage-middle-001"],
        )
        successor = Path(successor_status["ledger_path"])
        issue = self._issue()
        issue["audit_anchors"] = ["transitive-relation:CHX-001"]
        recorded = record_issue(
            successor,
            issue,
            relations=[{"relation_type": "extends", "issue_id": "CHX-001"}],
        )
        self.assertEqual(recorded["issue_id"], "CHX-002")
        self.assertEqual(
            recorded["relations"],
            [{"relation_type": "extends", "issue_id": "CHX-001"}],
        )

    def test_public_disclosure_binds_ledger_registry_and_documents(self) -> None:
        unresolved = self._started("run-public-unresolved-001")
        record_issue(unresolved, self._issue())
        close_ledger(unresolved)
        skill_root = Path(self.temporary.name) / "public-skill"
        (skill_root / "references").mkdir(parents=True)
        (skill_root / "KNOWN_LIMITATIONS.md").write_text(
            "1. **CHX-001 — publication disclosure.** research-target continuity\n",
            encoding="utf-8",
        )
        (skill_root / "references" / "v5_release_traceability.md").write_text(
            "CHX-001 publication disclosure ledger equality\n",
            encoding="utf-8",
        )
        contract = {
            "contract_revision": "chalxius-chx-public-disclosure-2",
            "included_issue_ids": ["CHX-001"],
            "ledger_lineage": [
                {
                    "ledger_run_id": "run-public-unresolved-001",
                    "ledger_sha256": __import__("hashlib").sha256(
                        unresolved.read_bytes()
                    ).hexdigest(),
                    "ledger_contract_revision": CONTRACT_REVISION,
                    "predecessor_run_id": "",
                    "included_issue_ids": ["CHX-001"],
                }
            ],
            "latest_issue_id": "CHX-001",
            "document_contracts": {
                "KNOWN_LIMITATIONS.md": {
                    "explicit_issue_enumeration": True,
                    "required_markers": [
                        "publication disclosure",
                        "research-target continuity",
                    ],
                },
                "references/v5_release_traceability.md": {
                    "explicit_issue_enumeration": False,
                    "required_markers": [
                        "CHX-001",
                        "ledger equality",
                        "publication disclosure",
                    ],
                },
            },
            "private_ledger_included": False,
            "truth_effect": "none",
        }
        (skill_root / "INHERITANCE.lock.json").write_text(
            json.dumps({"chx_public_disclosure": contract}, sort_keys=True),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "unresolved included issue"):
            verify_public_disclosure(unresolved, skill_root)

        predecessor = self._started("run-public-predecessor-001")
        record_issue(predecessor, self._issue())
        self._repair_chain(predecessor, ["CHX-001"])
        dispose_issue(
            predecessor,
            issue_id="CHX-001",
            disposition={
                "status": "resolved",
                "reason": "The predecessor publication contract was implemented.",
                "regression_evidence": ["test-public-predecessor:PASS"],
            },
        )
        close_ledger(predecessor)
        successor = Path(
            start_ledger(
                project_root=self.project,
                task="Publish a successor CHX disclosure.",
                run_id="run-public-successor-001",
                predecessor_ledger=predecessor,
            )["ledger_path"]
        )
        successor_issue = self._issue()
        successor_issue["audit_anchors"] = ["successor-publication:PASS"]
        record_issue(successor, successor_issue)
        self._repair_chain(successor, ["CHX-002"])
        dispose_issue(
            successor,
            issue_id="CHX-002",
            disposition={
                "status": "resolved",
                "reason": "The successor publication contract was implemented.",
                "regression_evidence": ["test-public-successor:PASS"],
            },
        )
        close_ledger(successor)
        contract["included_issue_ids"] = ["CHX-001", "CHX-002"]
        contract["latest_issue_id"] = "CHX-002"
        contract["ledger_lineage"] = [
            {
                "ledger_run_id": "run-public-predecessor-001",
                "ledger_sha256": __import__("hashlib").sha256(
                    predecessor.read_bytes()
                ).hexdigest(),
                "ledger_contract_revision": CONTRACT_REVISION,
                "predecessor_run_id": "",
                "included_issue_ids": ["CHX-001"],
            },
            {
                "ledger_run_id": "run-public-successor-001",
                "ledger_sha256": __import__("hashlib").sha256(
                    successor.read_bytes()
                ).hexdigest(),
                "ledger_contract_revision": CONTRACT_REVISION,
                "predecessor_run_id": "run-public-predecessor-001",
                "included_issue_ids": ["CHX-002"],
            },
        ]
        contract["document_contracts"]["KNOWN_LIMITATIONS.md"][
            "required_markers"
        ].append("lineage ownership")
        contract["document_contracts"]["KNOWN_LIMITATIONS.md"][
            "required_markers"
        ].sort()
        contract["document_contracts"]["references/v5_release_traceability.md"][
            "required_markers"
        ].append("lineage ownership")
        contract["document_contracts"]["references/v5_release_traceability.md"][
            "required_markers"
        ].sort()
        (skill_root / "KNOWN_LIMITATIONS.md").write_text(
            "1. **CHX-001 — publication disclosure.** research-target continuity\n"
            "2. **CHX-002 — lineage ownership.** exact predecessor namespace\n",
            encoding="utf-8",
        )
        (skill_root / "references" / "v5_release_traceability.md").write_text(
            "CHX-001 CHX-002 publication disclosure ledger equality lineage ownership\n",
            encoding="utf-8",
        )
        (skill_root / "INHERITANCE.lock.json").write_text(
            json.dumps({"chx_public_disclosure": contract}, sort_keys=True),
            encoding="utf-8",
        )
        self.assertEqual(
            validate_public_disclosure_contract(skill_root)["status"],
            "current",
        )
        self.assertEqual(
            verify_public_disclosure(successor, skill_root)["status"],
            "pass",
        )

        contract["ledger_lineage"][0]["ledger_run_id"] = "run-public-other-001"
        contract["ledger_lineage"][1]["predecessor_run_id"] = "run-public-other-001"
        (skill_root / "INHERITANCE.lock.json").write_text(
            json.dumps({"chx_public_disclosure": contract}, sort_keys=True),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "lineage differs"):
            verify_public_disclosure(successor, skill_root)
        contract["ledger_lineage"][0]["ledger_run_id"] = (
            "run-public-predecessor-001"
        )
        contract["ledger_lineage"][1]["predecessor_run_id"] = (
            "run-public-predecessor-001"
        )
        contract["ledger_lineage"][0]["ledger_sha256"] = "0" * 64
        (skill_root / "INHERITANCE.lock.json").write_text(
            json.dumps({"chx_public_disclosure": contract}, sort_keys=True),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "lineage differs"):
            verify_public_disclosure(successor, skill_root)
        contract["ledger_lineage"][0]["ledger_sha256"] = __import__(
            "hashlib"
        ).sha256(predecessor.read_bytes()).hexdigest()
        contract["ledger_lineage"][0]["included_issue_ids"] = []
        contract["ledger_lineage"][1]["included_issue_ids"] = [
            "CHX-001",
            "CHX-002",
        ]
        (skill_root / "INHERITANCE.lock.json").write_text(
            json.dumps({"chx_public_disclosure": contract}, sort_keys=True),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "lineage differs"):
            verify_public_disclosure(successor, skill_root)
        contract["ledger_lineage"][0]["included_issue_ids"] = ["CHX-001"]
        contract["ledger_lineage"][1]["included_issue_ids"] = ["CHX-002"]
        (skill_root / "INHERITANCE.lock.json").write_text(
            json.dumps({"chx_public_disclosure": contract}, sort_keys=True),
            encoding="utf-8",
        )
        (skill_root / "KNOWN_LIMITATIONS.md").write_text(
            "research-target continuity publication disclosure lineage ownership\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "enumeration drifted"):
            validate_public_disclosure_contract(skill_root)


if __name__ == "__main__":
    unittest.main()
