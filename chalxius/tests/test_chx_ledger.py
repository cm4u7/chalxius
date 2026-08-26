from __future__ import annotations

import hashlib
import json
import os
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
    inventory_project_ledgers,
    ledger_status,
    main,
    record_finding,
    record_architecture_reconnaissance,
    record_global_repair,
    record_integrated_repair,
    record_issue,
    record_tactical_repair,
    reconcile_finding,
    start_ledger,
    validate_public_disclosure_contract,
    verify_architecture_report,
    verify_global_repair,
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

    @staticmethod
    def _candidate_reference(relpath: str = "scripts/chx_ledger.py") -> str:
        candidate_root = Path(chx_ledger.__file__).resolve().parents[1]
        path = candidate_root / relpath
        return (
            f"candidate:{relpath}#sha256="
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}"
        )

    def _project_regression_reference(self) -> str:
        path = self.project / "global-repair-regression.txt"
        path.write_text("focused global repair regression: PASS\n", encoding="utf-8")
        return (
            "project:global-repair-regression.txt#sha256="
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}"
        )

    def _global_repair_input(
        self,
        inventory: dict[str, object],
        *,
        supersedes_global_repair_id: str = "",
    ) -> dict[str, object]:
        ledgers = inventory["ledgers"]
        assert isinstance(ledgers, list)
        qualified = sorted(
            {
                issue_id
                for ledger in ledgers
                for issue_id in ledger["issue_ids"]
            },
            key=chx_ledger._qualified_issue_sort_key,
        )
        implementation_anchor = self._candidate_reference()
        evidence = self._project_regression_reference()
        candidate_root = Path(chx_ledger.__file__).resolve().parents[1]
        return {
            "candidate_root": str(candidate_root),
            "candidate_version": (candidate_root / "VERSION").read_text(
                encoding="utf-8"
            ).strip(),
            "candidate_manifest_sha256": hashlib.sha256(
                (candidate_root / "MANIFEST.sha256").read_bytes()
            ).hexdigest(),
            "inventory_sha256": inventory["inventory_sha256"],
            "covered_issue_snapshot_sha256": (
                chx_ledger._covered_issue_snapshot_sha256(
                    inventory,
                    qualified,
                )
            ),
            "included_issue_ids": qualified,
            "issue_dispositions": [
                {
                    "qualified_issue_id": issue_id,
                    "status": "resolved",
                    "basis": "fixed_by_unified_repair",
                    "reason": "The exact integrated repair covers this issue.",
                    "evidence": [evidence],
                }
                for issue_id in qualified
            ],
            "mechanism_groups": [
                {
                    "group_id": "mechanism.global_test",
                    "issue_ids": qualified,
                    "summary": "One exact mechanism-level repair covers the fixture.",
                    "implementation_anchors": [implementation_anchor],
                    "fail_closed_boundary": "Any identity drift invalidates the repair.",
                    "evidence": [evidence],
                }
            ],
            "risk_evidence": [evidence],
            "regression_evidence": [evidence],
            "supersedes_global_repair_id": supersedes_global_repair_id,
        }

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
            if index >= 3:
                report_path = ledger.with_name(
                    ledger.stem + ".architecture-report.md"
                )
                projection_text = report_path.read_text(encoding="utf-8").split(
                    "```json\n", 1
                )[1].split("\n```", 1)[0]
                projection = json.loads(projection_text)
                self.assertEqual(
                    "predecessor_issue_ids" in projection,
                    revision == "chalxius-chx-run-ledger-4",
                )
                self.assertEqual(
                    "predecessor_lineage" in projection,
                    revision == "chalxius-chx-run-ledger-4",
                )
                self.assertEqual(
                    verify_architecture_report(ledger)["status"],
                    "exact",
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

    def test_inventory_rejects_valid_same_path_predecessor_replacement(
        self,
    ) -> None:
        predecessor = self._started("run-inventory-digest-base-001")
        record_issue(predecessor, self._issue())
        close_ledger(predecessor)
        successor = Path(
            start_ledger(
                project_root=self.project,
                task="Bind the exact predecessor bytes.",
                run_id="run-inventory-digest-child-001",
                predecessor_ledger=predecessor,
            )["ledger_path"]
        )
        close_ledger(successor)

        replacement_root = Path(self.temporary.name) / "replacement-ledger"
        replacement = Path(
            start_ledger(
                root=replacement_root,
                task="Create different valid bytes under the same run id.",
                run_id="run-inventory-digest-base-001",
            )["ledger_path"]
        )
        replacement_issue = self._issue()
        replacement_issue["audit_anchors"] = ["replacement:valid-but-different"]
        record_issue(replacement, replacement_issue)
        close_ledger(replacement)

        predecessor.write_bytes(replacement.read_bytes())
        chx_ledger.write_architecture_report(predecessor)
        inventory = inventory_project_ledgers(
            self.project,
            full=True,
            include_global=False,
        )
        self.assertEqual(inventory["report_compatibility_drift"], [])
        self.assertTrue(
            any(
                "predecessor ledger digest binding drifted" in error
                for error in inventory["lineage_errors"]
            ),
            inventory["lineage_errors"],
        )
        plan = self._global_repair_input(inventory)
        with patch.object(
            chx_ledger, "_validate_global_repair_candidate", return_value={}
        ), self.assertRaisesRegex(ValueError, "lineage errors"):
            record_global_repair(self.project, plan)

    def test_inventory_distinguishes_closed_orphan_from_active_issue(self) -> None:
        predecessor = self._started("run-inventory-orphan-001")
        record_issue(predecessor, self._issue())
        close_ledger(predecessor)

        active = self._started("run-inventory-active-001")
        record_issue(active, self._issue() | {"audit_anchors": ["active:anchor"]})

        inventory = inventory_project_ledgers(self.project, full=True)
        self.assertEqual(inventory["ledger_count"], 2)
        self.assertEqual(inventory["counts"]["orphan_open_issues"], 1)
        self.assertEqual(inventory["counts"]["active_open_issues"], 1)
        self.assertEqual(inventory["global_repair"]["status"], "absent")
        self.assertEqual(inventory["global_repair"]["uncovered_issue_count"], 2)
        self.assertEqual(
            {
                item["resolution"] for item in inventory["unresolved"]
            },
            {"open_orphan", "open_active"},
        )
        self.assertEqual(inventory["truth_effect"], "none")
        self.assertEqual(inventory["project_effect"], "none")

    def test_inventory_shared_lock_is_read_only_and_does_not_create_state(self) -> None:
        ledger = self._started("run-inventory-read-only-lock-001")
        record_issue(ledger, self._issue())
        close_ledger(ledger)
        lock_path = self.project / "chx-ledgers" / ".global-repair.lock"
        lock_path.unlink(missing_ok=True)
        before = sorted(path.name for path in (self.project / "chx-ledgers").iterdir())

        inventory = inventory_project_ledgers(self.project, full=True)
        self.assertEqual(inventory["ledger_count"], 1)
        self.assertFalse(lock_path.exists())
        self.assertEqual(
            sorted(path.name for path in (self.project / "chx-ledgers").iterdir()),
            before,
        )

        lock_path.write_bytes(b"")
        os.chmod(lock_path, 0o444)
        self.assertEqual(
            inventory_project_ledgers(self.project, full=True)["ledger_count"],
            1,
        )

    def test_inventory_follows_only_a_unique_supersedes_successor(self) -> None:
        predecessor = self._started("run-inventory-successor-base-001")
        record_issue(predecessor, self._issue())
        close_ledger(predecessor)

        successor = Path(
            start_ledger(
                project_root=self.project,
                task="Resolve one inventory issue through a successor.",
                run_id="run-inventory-successor-001",
                predecessor_ledger=predecessor,
            )["ledger_path"]
        )
        successor_issue = self._issue()
        successor_issue["audit_anchors"] = ["successor:anchor"]
        record_issue(
            successor,
            successor_issue,
            relations=[{"relation_type": "supersedes", "issue_id": "CHX-001"}],
        )
        self._repair_chain(successor, ["CHX-002"])
        dispose_issue(
            successor,
            issue_id="CHX-002",
            disposition={
                "status": "resolved",
                "reason": "The successor has reproducible evidence.",
                "regression_evidence": ["lineage-predecessor:PASS"],
            },
        )
        close_ledger(successor)

        inventory = inventory_project_ledgers(self.project, full=True)
        self.assertEqual(inventory["counts"]["unresolved_issues"], 0)
        successor_chain = next(
            item
            for item in inventory["chains"]
            if item["terminal_run_id"] == "run-inventory-successor-001"
        )
        self.assertEqual(successor_chain["unresolved_issue_ids"], [])

    def test_inventory_cli_is_read_only_and_reports_report_drift(self) -> None:
        ledger = self._started("run-inventory-cli-001")
        close_ledger(ledger)
        report_path = ledger.with_name(ledger.stem + ".architecture-report.md")
        report_path.write_text(
            report_path.read_text(encoding="utf-8") + "drift",
            encoding="utf-8",
        )
        before = ledger.read_bytes()
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(
                main(["inventory", "--project-root", str(self.project)]),
                0,
            )
        result = json.loads(output.getvalue())
        self.assertEqual(result["ledger_count"], 1)
        self.assertEqual(result["counts"]["report_compatibility_drift"], 1)
        self.assertEqual(result["unresolved"], [])
        self.assertNotIn("ledgers", result)
        self.assertNotIn("chains", result)
        self.assertEqual(ledger.read_bytes(), before)

        full_output = StringIO()
        with redirect_stdout(full_output):
            self.assertEqual(
                main(
                    [
                        "inventory",
                        "--project-root",
                        str(self.project),
                        "--full",
                    ]
                ),
                0,
            )
        full_result = json.loads(full_output.getvalue())
        self.assertEqual(len(full_result["ledgers"]), 1)
        self.assertEqual(len(full_result["chains"]), 1)
        self.assertEqual(ledger.read_bytes(), before)

    def test_global_install_integration_covers_current_open_issue_without_tactical_events(
        self,
    ) -> None:
        first = self._started("run-global-repair-first-001")
        record_issue(first, self._issue())
        close_ledger(first)

        second = self._started("run-global-repair-second-001")
        second_issue = self._issue()
        second_issue["audit_anchors"] = ["global-repair:second"]
        record_issue(second, second_issue)
        self.assertNotIn(
            "tactical_repair_recorded",
            {json.loads(line)["event"] for line in second.read_text().splitlines()},
        )

        base = inventory_project_ledgers(
            self.project,
            full=True,
            include_global=False,
        )
        integration = self._global_repair_input(base)
        stale_candidate = dict(integration)
        stale_candidate["candidate_manifest_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "candidate manifest is stale"):
            record_global_repair(self.project, stale_candidate)
        with patch.object(
            chx_ledger, "_validate_global_repair_candidate", return_value={}
        ):
            receipt = record_global_repair(self.project, integration)
            self.assertEqual(receipt["covered_issue_count"], 2)
            self.assertEqual(verify_global_repair(self.project)["status"], "current")
            projected = inventory_project_ledgers(self.project, full=True)
            self.assertEqual(projected["counts"]["unresolved_issues"], 0)
            self.assertEqual(projected["global_repair"]["status"], "current")
            bounded = inventory_project_ledgers(self.project)
            self.assertEqual(
                bounded["inventory_sha256"], projected["inventory_sha256"]
            )
            self.assertEqual(bounded["counts"], projected["counts"])
            self.assertEqual(bounded["global_repair"], projected["global_repair"])
            self.assertNotIn("ledgers", bounded)
            self.assertNotIn("chains", bounded)

            # A later zero-issue ledger does not change the exact historical
            # issue snapshot covered by this repair.
            empty = Path(
                start_ledger(
                    project_root=self.project,
                    task="Append a zero-issue successor after global repair.",
                    run_id="run-global-repair-after-empty-001",
                    predecessor_ledger=first,
                )["ledger_path"]
            )
            close_ledger(empty)
            after_empty = inventory_project_ledgers(self.project, full=True)
            self.assertEqual(after_empty["global_repair"]["status"], "current")
            self.assertEqual(
                after_empty["global_repair"]["uncovered_issue_count"], 0
            )
            self.assertEqual(verify_global_repair(self.project)["status"], "current")

            # A genuinely new issue remains unresolved without invalidating
            # the exact earlier repair coverage.
            later = Path(
                start_ledger(
                    project_root=self.project,
                    task="Append one genuinely new issue after global repair.",
                    run_id="run-global-repair-after-issue-001",
                    predecessor_ledger=empty,
                )["ledger_path"]
            )
            later_issue = self._issue()
            later_issue["audit_anchors"] = ["later-global-repair:issue"]
            record_issue(later, later_issue)
            after_issue = inventory_project_ledgers(self.project, full=True)
            self.assertEqual(after_issue["global_repair"]["status"], "current")
            self.assertEqual(
                after_issue["global_repair"]["uncovered_issue_count"], 1
            )
            self.assertEqual(after_issue["counts"]["unresolved_issues"], 1)
            self.assertEqual(
                verify_global_repair(self.project)["uncovered_issue_count"], 1
            )
        with patch.object(
            chx_ledger,
            "_validate_global_repair_candidate",
            side_effect=ValueError("candidate tree drifted"),
        ):
            candidate_stale = inventory_project_ledgers(self.project, full=True)
            self.assertEqual(candidate_stale["global_repair"]["status"], "stale")
            with self.assertRaisesRegex(
                ValueError, "candidate manifest is not current"
            ):
                verify_global_repair(self.project)

    def test_historical_global_repair_survives_relocated_candidate_root(
        self,
    ) -> None:
        ledger = self._started("run-global-relocated-candidate-001")
        record_issue(ledger, self._issue())
        close_ledger(ledger)
        base = inventory_project_ledgers(
            self.project,
            full=True,
            include_global=False,
        )
        plan = self._global_repair_input(base)
        historical_candidate = (
            Path(self.temporary.name) / "historical-candidate"
        ).resolve()
        historical_candidate.mkdir()
        plan["candidate_root"] = str(historical_candidate)

        with patch.object(
            chx_ledger,
            "_skill_root",
            return_value=historical_candidate,
        ), patch.object(
            chx_ledger,
            "_skill_version",
            return_value=plan["candidate_version"],
        ), patch.object(
            chx_ledger,
            "_validate_global_repair_candidate",
            return_value={},
        ), patch.object(
            chx_ledger,
            "_verify_global_repair_references",
            return_value=None,
        ):
            receipt = record_global_repair(self.project, plan)

        archived_candidate = historical_candidate.with_name(
            "archived-historical-candidate"
        )
        historical_candidate.rename(archived_candidate)
        projected = inventory_project_ledgers(self.project, full=True)
        self.assertEqual(projected["global_repair"]["status"], "stale")
        self.assertEqual(
            projected["global_repair"]["stale_reason_codes"],
            ["candidate_root_not_current"],
        )
        self.assertEqual(
            projected["global_repair"]["global_repair_id"],
            receipt["global_repair_id"],
        )
        records, chain = chx_ledger._collect_global_repair_records(self.project)
        self.assertEqual(len(records), 1)
        self.assertEqual(chain, [receipt["global_repair_id"]])

    def test_new_global_repair_rejects_missing_or_symlink_candidate_root(
        self,
    ) -> None:
        ledger = self._started("run-global-live-candidate-001")
        record_issue(ledger, self._issue())
        close_ledger(ledger)
        base = inventory_project_ledgers(
            self.project,
            full=True,
            include_global=False,
        )
        plan = self._global_repair_input(base)

        missing = (Path(self.temporary.name) / "missing-candidate").resolve()
        plan["candidate_root"] = str(missing)
        with self.assertRaisesRegex(ValueError, "candidate_root is unsafe"):
            record_global_repair(self.project, plan)

        real_candidate = (Path(self.temporary.name) / "real-candidate").resolve()
        real_candidate.mkdir()
        symlink_candidate = Path(self.temporary.name) / "candidate-link"
        symlink_candidate.symlink_to(real_candidate, target_is_directory=True)
        plan["candidate_root"] = str(symlink_candidate)
        with self.assertRaisesRegex(ValueError, "candidate_root is unsafe"):
            record_global_repair(self.project, plan)

    def test_global_repair_counts_resolved_and_excluded_separately(self) -> None:
        first = self._started("run-global-count-first-001")
        record_issue(first, self._issue())
        close_ledger(first)
        second = self._started("run-global-count-second-001")
        second_issue = self._issue()
        second_issue["audit_anchors"] = ["global-count:excluded"]
        record_issue(second, second_issue)
        close_ledger(second)
        base = inventory_project_ledgers(
            self.project,
            full=True,
            include_global=False,
        )
        integration = self._global_repair_input(base)
        integration["issue_dispositions"][1].update(
            {
                "status": "excluded_nonarchitectural",
                "basis": "historical_nonarchitectural",
                "reason": "The second fixture is intentionally excluded.",
            }
        )
        with patch.object(
            chx_ledger, "_validate_global_repair_candidate", return_value={}
        ):
            record_global_repair(self.project, integration)
            projected = inventory_project_ledgers(self.project, full=True)
        self.assertEqual(projected["counts"]["global_repaired_issues"], 1)
        self.assertEqual(projected["counts"]["global_resolved_issues"], 1)
        self.assertEqual(
            projected["counts"]["global_excluded_nonarchitectural_issues"],
            1,
        )
        self.assertEqual(projected["counts"]["global_disposed_issues"], 2)

    def test_global_repair_storage_fails_closed_on_races_and_unexpected_entries(
        self,
    ) -> None:
        first = self._started("run-global-repair-race-001")
        record_issue(first, self._issue())
        close_ledger(first)
        base = inventory_project_ledgers(
            self.project,
            full=True,
            include_global=False,
        )
        integration = self._global_repair_input(base)
        with patch.object(
            chx_ledger, "_validate_global_repair_candidate", return_value={}
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(record_global_repair, self.project, integration)
                    for _ in range(2)
                ]
            successes = []
            for future in futures:
                successes.append(future.result())
            self.assertEqual(
                sorted(item["status"] for item in successes),
                ["existing", "recorded"],
            )
            self.assertEqual(
                len({item["global_repair_id"] for item in successes}),
                1,
            )
            self.assertEqual(
                verify_global_repair(self.project)["status"], "current"
            )

        repair_dir = self.project / "chx-ledgers" / "global-repairs"
        (repair_dir / "unexpected.txt").write_text("drift", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unexpected entry"):
            inventory_project_ledgers(self.project)

    def test_global_repair_reuses_exclusive_lock_for_inventory_rechecks(
        self,
    ) -> None:
        ledger = self._started("run-global-repair-lock-reentry-001")
        record_issue(ledger, self._issue())
        close_ledger(ledger)
        base = inventory_project_ledgers(
            self.project,
            full=True,
            include_global=False,
        )
        integration = self._global_repair_input(base)
        calls: list[tuple[bool, bool]] = []

        def require_existing_exclusive_lock(
            project_root: Path,
            *,
            full: bool = False,
            include_global: bool = True,
            _lock_held: bool = False,
        ) -> dict[str, object]:
            self.assertTrue(_lock_held)
            calls.append((full, include_global))
            return chx_ledger._inventory_project_ledgers_unlocked(
                project_root,
                full=full,
                include_global=include_global,
            )

        with patch.object(
            chx_ledger,
            "inventory_project_ledgers",
            side_effect=require_existing_exclusive_lock,
        ), patch.object(
            chx_ledger,
            "_validate_global_repair_candidate",
            return_value={},
        ):
            receipt = record_global_repair(self.project, integration)
        self.assertEqual(receipt["status"], "recorded")
        self.assertEqual(calls, [(True, False), (True, False)])

    def test_global_repair_rejects_manifest_tree_drift(self) -> None:
        ledger = self._started("run-global-manifest-tree-001")
        record_issue(ledger, self._issue())
        close_ledger(ledger)
        base = inventory_project_ledgers(
            self.project, full=True, include_global=False
        )

        candidate = (Path(self.temporary.name) / "chalxius-fixture").resolve()
        candidate.mkdir()
        version = candidate / "VERSION"
        payload = candidate / "payload.txt"
        version.write_text("test-version\n", encoding="utf-8")
        payload.write_text("original\n", encoding="utf-8")
        manifest = candidate / "MANIFEST.sha256"
        manifest.write_text(
            "\n".join(
                [
                    f"{hashlib.sha256(version.read_bytes()).hexdigest()}  VERSION",
                    f"{hashlib.sha256(payload.read_bytes()).hexdigest()}  payload.txt",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        payload.write_text("drifted\n", encoding="utf-8")
        evidence = (
            "candidate:payload.txt#sha256="
            + hashlib.sha256(payload.read_bytes()).hexdigest()
        )
        plan = self._global_repair_input(base)
        plan.update(
            {
                "candidate_root": str(candidate),
                "candidate_version": "test-version",
                "candidate_manifest_sha256": hashlib.sha256(
                    manifest.read_bytes()
                ).hexdigest(),
                "issue_dispositions": [
                    {
                        **plan["issue_dispositions"][0],
                        "evidence": [evidence],
                    }
                ],
                "mechanism_groups": [
                    {
                        **plan["mechanism_groups"][0],
                        "implementation_anchors": [evidence],
                        "evidence": [evidence],
                    }
                ],
                "risk_evidence": [evidence],
                "regression_evidence": [evidence],
            }
        )
        with patch.object(chx_ledger, "_skill_root", return_value=candidate), patch.object(
            chx_ledger, "_skill_version", return_value="test-version"
        ):
            with self.assertRaisesRegex(ValueError, "manifest entry drifted"):
                record_global_repair(self.project, plan)

    def test_global_repair_rejects_missing_predecessor_inventory(self) -> None:
        predecessor = self._started("run-global-missing-base-001")
        record_issue(predecessor, self._issue())
        close_ledger(predecessor)
        successor = Path(
            start_ledger(
                project_root=self.project,
                task="Preserve a missing-predecessor regression fixture.",
                run_id="run-global-missing-child-001",
                predecessor_ledger=predecessor,
            )["ledger_path"]
        )
        issue = self._issue()
        issue["audit_anchors"] = ["missing-predecessor:child"]
        record_issue(successor, issue)
        close_ledger(successor)
        predecessor.replace(Path(self.temporary.name) / predecessor.name)
        report = predecessor.with_name(
            predecessor.stem + ".architecture-report.md"
        )
        if report.exists():
            report.replace(Path(self.temporary.name) / report.name)

        base = inventory_project_ledgers(
            self.project, full=True, include_global=False
        )
        self.assertTrue(base["lineage_errors"])
        self.assertEqual(base["counts"]["observed_issues"], 1)
        plan = self._global_repair_input(base)
        with patch.object(
            chx_ledger, "_validate_global_repair_candidate", return_value={}
        ):
            with self.assertRaisesRegex(ValueError, "lineage errors"):
                record_global_repair(self.project, plan)

    def test_global_repair_accepts_closed_issue_bearing_parallel_successors(
        self,
    ) -> None:
        predecessor = self._started("run-global-fork-base-001")
        record_issue(predecessor, self._issue())
        close_ledger(predecessor)
        for index, run_id in enumerate(
            ("run-global-fork-a-001", "run-global-fork-b-001"),
            1,
        ):
            successor = Path(
                start_ledger(
                    project_root=self.project,
                    task="Create a predecessor-fork regression fixture.",
                    run_id=run_id,
                    predecessor_ledger=predecessor,
                )["ledger_path"]
            )
            successor_issue = self._issue()
            successor_issue["audit_anchors"] = [f"issue-bearing-fork:{index}"]
            record_issue(successor, successor_issue)
            close_ledger(successor)
        base = inventory_project_ledgers(
            self.project, full=True, include_global=False
        )
        self.assertFalse(base["lineage_errors"], base["lineage_errors"])
        self.assertEqual(
            base["parallel_closed_successors"],
            [
                {
                    "predecessor_run_id": "run-global-fork-base-001",
                    "successor_run_id": "run-global-fork-a-001",
                    "successor_subtree_run_ids": ["run-global-fork-a-001"],
                    "successor_subtree_issue_count": 1,
                },
                {
                    "predecessor_run_id": "run-global-fork-base-001",
                    "successor_run_id": "run-global-fork-b-001",
                    "successor_subtree_run_ids": ["run-global-fork-b-001"],
                    "successor_subtree_issue_count": 1,
                },
            ],
        )
        plan = self._global_repair_input(base)
        with patch.object(
            chx_ledger, "_validate_global_repair_candidate", return_value={}
        ):
            record_global_repair(self.project, plan)
            self.assertEqual(verify_global_repair(self.project)["status"], "current")

    def test_global_repair_rejects_predecessor_fork(self) -> None:
        """Keep the historical anchor while exercising the new closed-branch rule."""

        self.test_global_repair_accepts_closed_issue_bearing_parallel_successors()

    def test_global_repair_accepts_closed_issue_free_parallel_successor(
        self,
    ) -> None:
        predecessor = self._started("run-global-empty-fork-base-001")
        record_issue(predecessor, self._issue())
        close_ledger(predecessor)

        issue_bearing = Path(
            start_ledger(
                project_root=self.project,
                task="Create the only issue-bearing successor branch.",
                run_id="run-global-empty-fork-issue-001",
                predecessor_ledger=predecessor,
            )["ledger_path"]
        )
        issue = self._issue()
        issue["audit_anchors"] = ["issue-free-parallel:issue-bearing"]
        record_issue(issue_bearing, issue)
        close_ledger(issue_bearing)

        issue_free = Path(
            start_ledger(
                project_root=self.project,
                task="Create a closed issue-free parallel task branch.",
                run_id="run-global-empty-fork-empty-001",
                predecessor_ledger=predecessor,
            )["ledger_path"]
        )
        close_ledger(issue_free)

        base = inventory_project_ledgers(
            self.project,
            full=True,
            include_global=False,
        )
        self.assertFalse(
            any(
                "multiple direct successors" in item
                for item in base["lineage_errors"]
            ),
            base["lineage_errors"],
        )
        self.assertEqual(
            base["parallel_issue_free_successors"],
            [
                {
                    "predecessor_run_id": "run-global-empty-fork-base-001",
                    "successor_run_id": "run-global-empty-fork-empty-001",
                    "successor_subtree_run_ids": [
                        "run-global-empty-fork-empty-001"
                    ],
                    "successor_subtree_issue_count": 0,
                }
            ],
        )
        plan = self._global_repair_input(base)
        with patch.object(
            chx_ledger,
            "_validate_global_repair_candidate",
            return_value={},
        ):
            record_global_repair(self.project, plan)
            self.assertEqual(
                verify_global_repair(self.project)["status"],
                "current",
            )

    def test_inventory_deduplicates_common_parallel_ancestor_issue(self) -> None:
        predecessor = self._started("run-parallel-dedup-base-001")
        record_issue(predecessor, self._issue())
        close_ledger(predecessor)
        for suffix in ("a", "b"):
            branch = Path(
                start_ledger(
                    project_root=self.project,
                    task="Close one issue-free parallel branch.",
                    run_id=f"run-parallel-dedup-{suffix}-001",
                    predecessor_ledger=predecessor,
                )["ledger_path"]
            )
            close_ledger(branch)

        inventory = inventory_project_ledgers(
            self.project,
            full=True,
            include_global=False,
        )
        qualified = "run-parallel-dedup-base-001/CHX-001"
        self.assertEqual(inventory["counts"]["unresolved_issues"], 1)
        self.assertEqual(
            [item["qualified_issue_id"] for item in inventory["unresolved"]],
            [qualified],
        )
        self.assertTrue(
            all(
                chain["unresolved_issue_ids"] == [qualified]
                for chain in inventory["chains"]
            )
        )

    def test_unique_parallel_supersedes_resolves_common_ancestor_globally(
        self,
    ) -> None:
        predecessor = self._started("run-parallel-resolve-base-001")
        record_issue(predecessor, self._issue())
        close_ledger(predecessor)

        resolving = Path(
            start_ledger(
                project_root=self.project,
                task="Resolve the common ancestor on one closed branch.",
                run_id="run-parallel-resolve-a-001",
                predecessor_ledger=predecessor,
            )["ledger_path"]
        )
        successor_issue = self._issue()
        successor_issue["audit_anchors"] = ["parallel-resolve:unique"]
        record_issue(
            resolving,
            successor_issue,
            relations=[{"relation_type": "supersedes", "issue_id": "CHX-001"}],
        )
        self._repair_chain(resolving, ["CHX-002"])
        dispose_issue(
            resolving,
            issue_id="CHX-002",
            disposition={
                "status": "resolved",
                "reason": "The unique parallel successor has exact evidence.",
                "regression_evidence": ["tests/test_chx_ledger.py:PASS"],
            },
        )
        close_ledger(resolving)

        independent = Path(
            start_ledger(
                project_root=self.project,
                task="Close one logically independent parallel branch.",
                run_id="run-parallel-resolve-b-001",
                predecessor_ledger=predecessor,
            )["ledger_path"]
        )
        close_ledger(independent)

        inventory = inventory_project_ledgers(
            self.project,
            full=True,
            include_global=False,
        )
        self.assertFalse(inventory["lineage_errors"], inventory["lineage_errors"])
        self.assertEqual(inventory["counts"]["unresolved_issues"], 0)
        self.assertEqual(inventory["unresolved"], [])
        self.assertTrue(
            all(not chain["unresolved_issue_ids"] for chain in inventory["chains"])
        )

    def test_global_repair_accepts_active_issue_free_parallel_successor(
        self,
    ) -> None:
        predecessor = self._started("run-global-active-empty-fork-base-001")
        record_issue(predecessor, self._issue())
        close_ledger(predecessor)

        issue_bearing = Path(
            start_ledger(
                project_root=self.project,
                task="Create one closed issue-bearing successor branch.",
                run_id="run-global-active-empty-fork-issue-001",
                predecessor_ledger=predecessor,
            )["ledger_path"]
        )
        issue = self._issue()
        issue["audit_anchors"] = ["active-issue-free-parallel:issue-bearing"]
        record_issue(issue_bearing, issue)
        close_ledger(issue_bearing)

        active = start_ledger(
            project_root=self.project,
            task="Leave one issue-free parallel branch active.",
            run_id="run-global-active-empty-fork-empty-001",
            predecessor_ledger=predecessor,
        )
        base = inventory_project_ledgers(
            self.project,
            full=True,
            include_global=False,
            current_run_ids=["run-global-active-empty-fork-empty-001"],
        )
        self.assertFalse(base["lineage_errors"], base["lineage_errors"])
        self.assertIn(
            "run-global-active-empty-fork-empty-001",
            base["active_run_ids"],
        )
        self.assertEqual(base["parallel_issue_free_successors"], [])
        self.assertEqual(
            [
                item["successor_run_id"]
                for item in base["parallel_closed_successors"]
            ],
            ["run-global-active-empty-fork-issue-001"],
        )
        self.assertTrue(Path(active["ledger_path"]).is_file())
        plan = self._global_repair_input(base)
        with patch.object(
            chx_ledger, "_validate_global_repair_candidate", return_value={}
        ):
            record_global_repair(self.project, plan)
            self.assertEqual(verify_global_repair(self.project)["status"], "current")

    def test_global_repair_rejects_competing_parallel_supersedes(self) -> None:
        predecessor = self._started("run-global-competing-supersedes-base-001")
        record_issue(predecessor, self._issue())
        close_ledger(predecessor)
        relations = [{"issue_id": "CHX-001", "relation_type": "supersedes"}]
        for suffix in ("a", "b"):
            successor = Path(
                start_ledger(
                    project_root=self.project,
                    task="Create a competing parallel supersedes successor.",
                    run_id=f"run-global-competing-supersedes-{suffix}-001",
                    predecessor_ledger=predecessor,
                )["ledger_path"]
            )
            issue = self._issue()
            issue["audit_anchors"] = [f"competing-supersedes:{suffix}"]
            record_issue(successor, issue, relations=relations)
            close_ledger(successor)
        base = inventory_project_ledgers(
            self.project, full=True, include_global=False
        )
        self.assertTrue(
            any("competing supersedes successors" in item for item in base["lineage_errors"]),
            base["lineage_errors"],
        )

    def test_excluded_successor_does_not_resolve_predecessor(self) -> None:
        predecessor = self._started("run-excluded-successor-base-001")
        record_issue(predecessor, self._issue())
        close_ledger(predecessor)
        successor = Path(
            start_ledger(
                project_root=self.project,
                task="Exclude a nonarchitectural successor.",
                run_id="run-excluded-successor-child-001",
                predecessor_ledger=predecessor,
            )["ledger_path"]
        )
        issue = self._issue()
        issue["audit_anchors"] = ["excluded-successor:child"]
        record_issue(
            successor,
            issue,
            relations=[{"relation_type": "supersedes", "issue_id": "CHX-001"}],
        )
        dispose_issue(
            successor,
            issue_id="CHX-002",
            disposition={
                "status": "excluded_nonarchitectural",
                "reason": "The successor finding failed the architecture causal test.",
                "regression_evidence": [],
            },
        )
        close_ledger(successor)
        inventory = inventory_project_ledgers(
            self.project, full=True, include_global=False
        )
        self.assertEqual(inventory["counts"]["unresolved_issues"], 1)
        self.assertEqual(
            inventory["unresolved"][0]["qualified_issue_id"],
            "run-excluded-successor-base-001/CHX-001",
        )
        self.assertEqual(
            inventory["ignored_supersedes"][0]["reason"],
            "excluded_successor_has_no_repair_effect",
        )

    def test_same_ledger_supersedes_is_not_a_strict_successor(self) -> None:
        ledger = self._started("run-same-ledger-supersedes-001")
        record_issue(ledger, self._issue())
        issue = self._issue()
        issue["audit_anchors"] = ["same-ledger:second"]
        record_issue(
            ledger,
            issue,
            relations=[{"relation_type": "supersedes", "issue_id": "CHX-001"}],
        )
        self._repair_chain(ledger, ["CHX-002"])
        dispose_issue(
            ledger,
            issue_id="CHX-002",
            disposition={
                "status": "resolved",
                "reason": "The second issue itself has been repaired.",
                "regression_evidence": ["tests/test_chx_ledger.py:PASS"],
            },
        )
        close_ledger(ledger)
        inventory = inventory_project_ledgers(
            self.project, full=True, include_global=False
        )
        self.assertEqual(inventory["counts"]["unresolved_issues"], 1)
        self.assertEqual(
            inventory["ignored_supersedes"][0]["reason"],
            "same_ledger_not_strictly_later",
        )

    def test_global_repair_accepts_active_snapshot_and_stales_on_later_mutation(
        self,
    ) -> None:
        ledger = self._started("run-global-active-001")
        record_issue(ledger, self._issue())
        active = inventory_project_ledgers(
            self.project, full=True, include_global=False
        )
        active_plan = self._global_repair_input(active)
        with patch.object(
            chx_ledger, "_validate_global_repair_candidate", return_value={}
        ):
            receipt = record_global_repair(self.project, active_plan)
            self.assertEqual(receipt["status"], "recorded")
            self.assertEqual(verify_global_repair(self.project)["status"], "current")

            later = self._issue()
            later["audit_anchors"] = ["active-global-snapshot:later-issue"]
            record_issue(ledger, later)
            inventory = inventory_project_ledgers(self.project, full=True)
            self.assertEqual(inventory["global_repair"]["status"], "stale")
            with self.assertRaisesRegex(ValueError, "covered issue snapshot drifted"):
                verify_global_repair(self.project)

    def test_global_repair_rechecks_inventory_before_final_write(self) -> None:
        ledger = self._started("run-global-final-recheck-001")
        record_issue(ledger, self._issue())
        close_ledger(ledger)
        base = inventory_project_ledgers(
            self.project, full=True, include_global=False
        )
        plan = self._global_repair_input(base)
        real_inventory = chx_ledger.inventory_project_ledgers
        calls = 0

        def drifted_inventory(*args, **kwargs):
            nonlocal calls
            calls += 1
            result = real_inventory(*args, **kwargs)
            if calls == 2:
                result = json.loads(json.dumps(result))
                result["inventory_sha256"] = "f" * 64
            return result

        with patch.object(
            chx_ledger, "_validate_global_repair_candidate", return_value={}
        ), patch.object(
            chx_ledger,
            "inventory_project_ledgers",
            side_effect=drifted_inventory,
        ):
            with self.assertRaisesRegex(ValueError, "changed before final write"):
                record_global_repair(self.project, plan)

    def test_global_repair_requires_basis_pairing_and_digest_bound_evidence(
        self,
    ) -> None:
        ledger = self._started("run-global-evidence-001")
        record_issue(ledger, self._issue())
        close_ledger(ledger)
        base = inventory_project_ledgers(
            self.project, full=True, include_global=False
        )
        invalid_pair = self._global_repair_input(base)
        invalid_pair["issue_dispositions"][0]["status"] = (
            "excluded_nonarchitectural"
        )
        with self.assertRaisesRegex(ValueError, "basis/status pairing"):
            record_global_repair(self.project, invalid_pair)

        stale_snapshot = self._global_repair_input(base)
        stale_snapshot["covered_issue_snapshot_sha256"] = "0" * 64
        with patch.object(
            chx_ledger, "_validate_global_repair_candidate", return_value={}
        ):
            with self.assertRaisesRegex(ValueError, "covered issue snapshot is stale"):
                record_global_repair(self.project, stale_snapshot)

        arbitrary = self._global_repair_input(base)
        arbitrary["issue_dispositions"][0]["evidence"] = ["claimed:PASS"]
        with self.assertRaisesRegex(ValueError, "ROOT:relative/path"):
            record_global_repair(self.project, arbitrary)

        source_as_regression = self._global_repair_input(base)
        candidate_source = self._candidate_reference()
        source_as_regression["issue_dispositions"][0]["evidence"] = [
            candidate_source
        ]
        source_as_regression["mechanism_groups"][0]["evidence"] = [
            candidate_source
        ]
        source_as_regression["regression_evidence"] = [candidate_source]
        with patch.object(
            chx_ledger, "_validate_global_repair_candidate", return_value={}
        ):
            with self.assertRaisesRegex(ValueError, "must bind project receipts"):
                record_global_repair(self.project, source_as_regression)

        missing = self._global_repair_input(base)
        missing_reference = "project:missing.txt#sha256=" + "0" * 64
        missing["issue_dispositions"][0]["evidence"] = [missing_reference]
        missing["mechanism_groups"][0]["evidence"] = [missing_reference]
        missing["regression_evidence"] = [missing_reference]
        with patch.object(
            chx_ledger, "_validate_global_repair_candidate", return_value={}
        ):
            with self.assertRaisesRegex(ValueError, "reference file is missing"):
                record_global_repair(self.project, missing)

        wrong_hash = self._global_repair_input(base)
        drifted_reference = (
            "project:global-repair-regression.txt#sha256=" + "0" * 64
        )
        wrong_hash["issue_dispositions"][0]["evidence"] = [drifted_reference]
        wrong_hash["mechanism_groups"][0]["evidence"] = [drifted_reference]
        wrong_hash["regression_evidence"] = [drifted_reference]
        with patch.object(
            chx_ledger, "_validate_global_repair_candidate", return_value={}
        ):
            with self.assertRaisesRegex(ValueError, "reference hash drifted"):
                record_global_repair(self.project, wrong_hash)

        project_anchor = self._global_repair_input(base)
        stable_ledger = Path(base["ledgers"][0]["path"])
        project_reference = (
            f"project:chx-ledgers/{stable_ledger.name}#sha256="
            f"{hashlib.sha256(stable_ledger.read_bytes()).hexdigest()}"
        )
        project_anchor["mechanism_groups"][0]["implementation_anchors"] = [
            project_reference
        ]
        with patch.object(
            chx_ledger, "_validate_global_repair_candidate", return_value={}
        ):
            with self.assertRaisesRegex(ValueError, "must bind candidate files"):
                record_global_repair(self.project, project_anchor)

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

    def test_public_disclosure_accepts_exact_resolved_superseding_successor(
        self,
    ) -> None:
        predecessor = self._started("run-public-open-predecessor-001")
        record_issue(predecessor, self._issue())
        close_ledger(predecessor)
        successor = Path(
            start_ledger(
                project_root=self.project,
                task="Publish an exact superseding successor.",
                run_id="run-public-resolved-successor-001",
                predecessor_ledger=predecessor,
            )["ledger_path"]
        )
        successor_issue = self._issue()
        successor_issue["audit_anchors"] = ["resolved-superseding-successor:PASS"]
        record_issue(
            successor,
            successor_issue,
            relations=[
                {"relation_type": "supersedes", "issue_id": "CHX-001"}
            ],
        )
        self._repair_chain(successor, ["CHX-002"])
        dispose_issue(
            successor,
            issue_id="CHX-002",
            disposition={
                "status": "resolved",
                "reason": "The successor safely replaces the predecessor mechanism.",
                "regression_evidence": ["test-public-successor:PASS"],
            },
        )
        close_ledger(successor)

        skill_root = Path(self.temporary.name) / "superseding-public-skill"
        (skill_root / "references").mkdir(parents=True)
        (skill_root / "KNOWN_LIMITATIONS.md").write_text(
            "1. **CHX-001 — predecessor.** immutable open mechanism\n"
            "2. **CHX-002 — successor.** exact resolved supersedes relation\n",
            encoding="utf-8",
        )
        (skill_root / "references" / "v5_release_traceability.md").write_text(
            "CHX-001 CHX-002 immutable predecessor resolved supersedes successor\n",
            encoding="utf-8",
        )
        contract = {
            "contract_revision": "chalxius-chx-public-disclosure-2",
            "included_issue_ids": ["CHX-001", "CHX-002"],
            "ledger_lineage": [
                {
                    "ledger_run_id": "run-public-open-predecessor-001",
                    "ledger_sha256": __import__("hashlib").sha256(
                        predecessor.read_bytes()
                    ).hexdigest(),
                    "ledger_contract_revision": CONTRACT_REVISION,
                    "predecessor_run_id": "",
                    "included_issue_ids": ["CHX-001"],
                },
                {
                    "ledger_run_id": "run-public-resolved-successor-001",
                    "ledger_sha256": __import__("hashlib").sha256(
                        successor.read_bytes()
                    ).hexdigest(),
                    "ledger_contract_revision": CONTRACT_REVISION,
                    "predecessor_run_id": "run-public-open-predecessor-001",
                    "included_issue_ids": ["CHX-002"],
                },
            ],
            "latest_issue_id": "CHX-002",
            "document_contracts": {
                "KNOWN_LIMITATIONS.md": {
                    "explicit_issue_enumeration": True,
                    "required_markers": ["immutable open", "supersedes"],
                },
                "references/v5_release_traceability.md": {
                    "explicit_issue_enumeration": False,
                    "required_markers": ["CHX-001", "CHX-002", "supersedes"],
                },
            },
            "private_ledger_included": False,
            "truth_effect": "none",
        }
        (skill_root / "INHERITANCE.lock.json").write_text(
            json.dumps({"chx_public_disclosure": contract}, sort_keys=True),
            encoding="utf-8",
        )
        self.assertEqual(
            verify_public_disclosure(successor, skill_root)["status"],
            "pass",
        )

    def test_public_disclosure_retains_explicitly_excluded_issue_ownership(
        self,
    ) -> None:
        ledger = self._started("run-public-excluded-lineage-001")
        record_issue(ledger, self._issue())
        dispose_issue(
            ledger,
            issue_id="CHX-001",
            disposition={
                "status": "excluded_nonarchitectural",
                "reason": "The reproduced event is not an architecture defect.",
                "regression_evidence": [],
            },
        )
        second = self._issue()
        second["audit_anchors"] = ["public-excluded-successor:PASS"]
        record_issue(ledger, second)
        self._repair_chain(ledger, ["CHX-002"])
        dispose_issue(
            ledger,
            issue_id="CHX-002",
            disposition={
                "status": "resolved",
                "reason": "The included architecture issue is repaired.",
                "regression_evidence": ["tests/test_chx_ledger.py:PASS"],
            },
        )
        close_ledger(ledger)

        skill_root = Path(self.temporary.name) / "excluded-public-skill"
        (skill_root / "references").mkdir(parents=True)
        (skill_root / "KNOWN_LIMITATIONS.md").write_text(
            "1. **CHX-001 — excluded.** excluded_nonarchitectural\n"
            "2. **CHX-002 — resolved.** publication repair\n",
            encoding="utf-8",
        )
        (skill_root / "references" / "v5_release_traceability.md").write_text(
            "CHX-001 excluded_nonarchitectural CHX-002 resolved\n",
            encoding="utf-8",
        )
        contract = {
            "contract_revision": "chalxius-chx-public-disclosure-2",
            "included_issue_ids": ["CHX-001", "CHX-002"],
            "ledger_lineage": [
                {
                    "ledger_run_id": "run-public-excluded-lineage-001",
                    "ledger_sha256": hashlib.sha256(
                        ledger.read_bytes()
                    ).hexdigest(),
                    "ledger_contract_revision": CONTRACT_REVISION,
                    "predecessor_run_id": "",
                    "included_issue_ids": ["CHX-001", "CHX-002"],
                }
            ],
            "latest_issue_id": "CHX-002",
            "document_contracts": {
                "KNOWN_LIMITATIONS.md": {
                    "explicit_issue_enumeration": True,
                    "required_markers": ["excluded_nonarchitectural"],
                },
                "references/v5_release_traceability.md": {
                    "explicit_issue_enumeration": False,
                    "required_markers": ["CHX-001", "CHX-002"],
                },
            },
            "private_ledger_included": False,
            "truth_effect": "none",
        }
        (skill_root / "INHERITANCE.lock.json").write_text(
            json.dumps({"chx_public_disclosure": contract}, sort_keys=True),
            encoding="utf-8",
        )
        self.assertEqual(
            verify_public_disclosure(ledger, skill_root)["status"],
            "pass",
        )

    def test_public_disclosure_excluded_successor_does_not_repair_predecessor(
        self,
    ) -> None:
        predecessor = self._started("run-public-excluded-predecessor-001")
        record_issue(predecessor, self._issue())
        close_ledger(predecessor)
        successor = Path(
            start_ledger(
                project_root=self.project,
                task="Exclude a later observation without repairing its predecessor.",
                run_id="run-public-excluded-successor-001",
                predecessor_ledger=predecessor,
            )["ledger_path"]
        )
        successor_issue = self._issue()
        successor_issue["audit_anchors"] = ["excluded-successor:NOT-A-REPAIR"]
        record_issue(
            successor,
            successor_issue,
            relations=[
                {"relation_type": "supersedes", "issue_id": "CHX-001"}
            ],
        )
        dispose_issue(
            successor,
            issue_id="CHX-002",
            disposition={
                "status": "excluded_nonarchitectural",
                "reason": "The later observation was not architecture-caused.",
                "regression_evidence": [],
            },
        )
        close_ledger(successor)

        skill_root = Path(self.temporary.name) / "excluded-successor-public-skill"
        (skill_root / "references").mkdir(parents=True)
        (skill_root / "KNOWN_LIMITATIONS.md").write_text(
            "1. **CHX-001 — predecessor.** remains unresolved\n"
            "2. **CHX-002 — excluded.** excluded_nonarchitectural\n",
            encoding="utf-8",
        )
        (skill_root / "references" / "v5_release_traceability.md").write_text(
            "CHX-001 unresolved CHX-002 excluded_nonarchitectural\n",
            encoding="utf-8",
        )
        contract = {
            "contract_revision": "chalxius-chx-public-disclosure-2",
            "included_issue_ids": ["CHX-001", "CHX-002"],
            "ledger_lineage": [
                {
                    "ledger_run_id": "run-public-excluded-predecessor-001",
                    "ledger_sha256": hashlib.sha256(
                        predecessor.read_bytes()
                    ).hexdigest(),
                    "ledger_contract_revision": CONTRACT_REVISION,
                    "predecessor_run_id": "",
                    "included_issue_ids": ["CHX-001"],
                },
                {
                    "ledger_run_id": "run-public-excluded-successor-001",
                    "ledger_sha256": hashlib.sha256(
                        successor.read_bytes()
                    ).hexdigest(),
                    "ledger_contract_revision": CONTRACT_REVISION,
                    "predecessor_run_id": "run-public-excluded-predecessor-001",
                    "included_issue_ids": ["CHX-002"],
                },
            ],
            "latest_issue_id": "CHX-002",
            "document_contracts": {
                "KNOWN_LIMITATIONS.md": {
                    "explicit_issue_enumeration": True,
                    "required_markers": ["excluded_nonarchitectural"],
                },
                "references/v5_release_traceability.md": {
                    "explicit_issue_enumeration": False,
                    "required_markers": ["CHX-001", "CHX-002"],
                },
            },
            "private_ledger_included": False,
            "truth_effect": "none",
        }
        (skill_root / "INHERITANCE.lock.json").write_text(
            json.dumps({"chx_public_disclosure": contract}, sort_keys=True),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "unresolved included issue: CHX-001"):
            verify_public_disclosure(successor, skill_root)


if __name__ == "__main__":
    unittest.main()
