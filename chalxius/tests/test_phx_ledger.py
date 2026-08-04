from __future__ import annotations

import hashlib
import json
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import chx_ledger
import phx_ledger


class PHXArchitectureRouteLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="chalxius-phx-ledger-")
        self.base = Path(self.temporary.name).resolve()
        self.global_root = self.base / "global-phx"
        self.project = self.base / "project"
        self.project.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _started(self, *, root: Path | None = None, scope: str = "global-architecture") -> tuple[Path, dict[str, object]]:
        status = phx_ledger.start(
            root=root or self.global_root,
            scope_id=scope,
            project_roots=[self.project],
            allow_custom_root=True,
        )
        return Path(status["ledger_path"]), status

    @staticmethod
    def _route(
        *,
        key: str = "route.aggregate_inspection_context",
        title: str = "Reuse one aggregate inspection context",
        summary: str = "Reuse validated aggregate inputs within one immutable command snapshot.",
        domain: str = "performance_cost",
        kind: str = "command_local_reuse",
        origin: str = "measurement",
        source_chx_refs: list[dict[str, str]] | None = None,
        relations: list[dict[str, str]] | None = None,
    ) -> dict[str, object]:
        return {
            "route_key": key,
            "title": title,
            "summary": summary,
            "route_domain": domain,
            "route_kind": kind,
            "origin": origin,
            "applicability_signals": [
                "administrative work dominates useful projection time",
                "aggregate command repeats immutable validation",
            ],
            "measurement_plan": [
                "capture a before trace",
                "apply the bounded route",
                "compare time and validator call counts",
            ],
            "implementation_options": [
                "bind one owner-scoped inspection object to the command snapshot",
            ],
            "fail_closed_boundaries": [
                "never reuse across project or snapshot identity",
                "preserve every Fact admission gate",
            ],
            "source_chx_refs": source_chx_refs or [],
            "relations": relations or [],
        }

    @staticmethod
    def _measurement(
        route_id: str,
        *,
        outcome: str = "supported",
        elapsed_seconds: float = 1.25,
    ) -> dict[str, object]:
        return {
            "route_id": route_id,
            "scope": "one immutable audit snapshot",
            "operation": "archive-bound aggregate audit",
            "requested_projection": "full administrative audit projection",
            "evaluation_kind": "operational_trace",
            "mutation_scope": "read_only",
            "authorization_consultation_id_or_null": None,
            "authorization_scope_acknowledged_or_null": None,
            "consultation_constraints_acknowledged": [],
            "measurement_method": "bounded wall-clock and validator-call trace",
            "runtime_identity_sha256_or_null": "1" * 64,
            "project_snapshot_sha256_or_null": "2" * 64,
            "outcome": outcome,
            "metrics": [
                {"name": "elapsed_seconds", "value": elapsed_seconds, "unit": "seconds"},
                {"name": "validator_calls", "value": 1, "unit": "calls"},
            ],
            "observations": [
                "Fact admission behavior was unchanged",
                "the repeated scan was eliminated",
            ],
            "evidence_sha256s": ["3" * 64],
        }

    @staticmethod
    def _consultation(
        route_id: str,
        *,
        decision: str = "approved",
        constraints: list[str] | None = None,
        response: str = "Approved for this bounded implementation.",
    ) -> dict[str, object]:
        if constraints is None:
            constraints = (
                ["retain snapshot and project ownership checks"]
                if decision == "approved_with_constraints"
                else []
            )
        return {
            "route_id": route_id,
            "proposal_summary": "Adopt the measured route as a reusable global architecture mechanism.",
            "user_question": "May Chalxius adopt this architecture route under the stated boundaries?",
            "user_response": response,
            "user_response_sha256": hashlib.sha256(response.encode("utf-8")).hexdigest(),
            "decision": decision,
            "constraints": constraints,
            "consultation_context": "Explicit user consultation for PHX architecture adoption.",
            "host_task_scope_id": "test-host-task-scope",
            "user_turn_locator": "test-user-turn-1",
            "authorization_scope": "Implement only the measured route under its recorded boundaries.",
            "implementation_state_at_consultation": "not_started",
            "presented_alternatives": [
                "adopt the bounded route",
                "retain the current architecture",
            ],
            "expected_benefits": ["reduce repeated administrative work"],
            "costs_and_risks": ["new lifecycle and ownership checks require maintenance"],
            "migration_or_rollback": ["retain the prior path as a rollback boundary"],
        }

    @staticmethod
    def _adoption(
        route_id: str,
        measurement_id: str,
        consultation_id: str,
        *,
        summary: str = "Installed the owner-bound aggregate inspection mechanism.",
        acknowledged_constraints: list[str] | None = None,
    ) -> dict[str, object]:
        if acknowledged_constraints is None:
            acknowledged_constraints = []
        return {
            "route_id": route_id,
            "measurement_id": measurement_id,
            "consultation_id": consultation_id,
            "consultation_constraints_acknowledged": acknowledged_constraints,
            "authorization_scope_acknowledged": "Implement only the measured route under its recorded boundaries.",
            "implementation_summary": summary,
            "applicability": "Aggregate administrative projections over one frozen snapshot.",
            "implementation_anchors": ["scripts/mathgraph/v5_lifecycle.py"],
            "implementation_evidence_sha256s": ["4" * 64],
            "regression_evidence": ["tests/test_phx_ledger.py:PASS"],
            "regression_evidence_sha256s": ["5" * 64],
            "residual_boundaries": ["cross-command persistent reuse remains prohibited"],
        }

    @staticmethod
    def _events(path: Path) -> list[dict[str, object]]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    @staticmethod
    def _tree(root: Path) -> list[str]:
        return sorted(str(path.relative_to(root)) for path in root.rglob("*"))

    def test_global_projectless_root_is_private_nontruth_and_does_not_touch_project(self) -> None:
        before = self._tree(self.project)
        ledger, status = self._started()
        route = phx_ledger.record_route(ledger, self._route())

        self.assertEqual(ledger.parent, self.global_root)
        self.assertFalse(self.global_root.is_relative_to(self.project))
        self.assertEqual(stat.S_IMODE(self.global_root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(ledger.stat().st_mode), 0o600)
        self.assertEqual(status["truth_effect"], "none")
        self.assertEqual(status["project_effect"], "none")
        self.assertIs(status["premise_eligible"], False)
        self.assertEqual(route["route_domain"], "performance_cost")
        self.assertEqual(route["origin"], "measurement")
        for event in self._events(ledger):
            self.assertEqual(event["truth_effect"], "none")
            self.assertEqual(event["project_effect"], "none")
            self.assertIs(event["premise_eligible"], False)
        self.assertEqual(self._tree(self.project), before)

        ledger.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "mode 0600"):
            phx_ledger._read_ledger(ledger)
        ledger.chmod(0o600)

        forbidden = self.project / "phx-ledgers"
        with self.assertRaisesRegex(ValueError, "outside every project"):
            phx_ledger.start(
                root=forbidden,
                scope_id="must-not-enter-project",
                project_roots=[self.project],
                allow_custom_root=True,
            )
        self.assertFalse(forbidden.exists())

    def test_public_cli_start_owns_only_start_arguments(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(Path(phx_ledger.__file__).resolve()),
                "start",
                "--root",
                str(self.global_root),
                "--scope-id",
                "cli-start-contract",
                "--project-root",
                str(self.project),
                "--allow-custom-root",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["scope_id"], "cli-start-contract")
        self.assertTrue(Path(payload["ledger_path"]).is_file())

    def test_public_cli_search_forwards_write_receipt(self) -> None:
        ledger, _ = self._started(scope="cli-search-contract")
        phx_ledger.record_route(ledger, self._route())
        phx_ledger.close(ledger)
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(Path(phx_ledger.__file__).resolve()),
                "search",
                "--root",
                str(self.global_root),
                "--query",
                "aggregate",
                "--allow-custom-root",
                "--write-receipt",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        receipt_path = Path(payload["search_receipt_path"])
        self.assertTrue(receipt_path.is_file())
        self.assertEqual(
            payload["search_receipt"],
            json.loads(receipt_path.read_text(encoding="utf-8")),
        )

    def test_route_measurement_consultation_adoption_close_report_and_verify(self) -> None:
        ledger, _ = self._started()
        route = phx_ledger.record_route(
            ledger,
            self._route(
                title="Global Architecture Route",
                domain="coordination",
                kind="architecture_reorganization",
                origin="architecture_review",
            ),
        )
        measurement = phx_ledger.record_measurement(
            ledger, self._measurement(route["route_id"])
        )
        consultation = phx_ledger.record_consultation(
            ledger,
            self._consultation(
                route["route_id"], decision="approved_with_constraints"
            ),
        )
        adoption = phx_ledger.record_adoption(
            ledger,
            self._adoption(
                route["route_id"],
                measurement["measurement_id"],
                consultation["consultation_id"],
                acknowledged_constraints=consultation["constraints"],
            ),
        )

        _, open_status = phx_ledger._read_ledger(ledger)
        self.assertEqual(open_status["route_count"], 1)
        self.assertEqual(open_status["measurement_count"], 1)
        self.assertEqual(open_status["consultation_count"], 1)
        self.assertEqual(open_status["adoption_count"], 1)
        self.assertFalse(open_status["closed"])
        self.assertTrue(adoption["adoption_id"].startswith("adoption-"))

        closed = phx_ledger.close(ledger)
        self.assertEqual(closed["consultation_ids"], [consultation["consultation_id"]])
        ledger_before = ledger.read_bytes()
        with self.assertRaisesRegex(ValueError, "bound global.*root"):
            phx_ledger.write_report(ledger, self.project / "phx-report.md")
        with self.assertRaisesRegex(ValueError, "bound global.*root"):
            phx_ledger.write_report(ledger, ledger)
        self.assertEqual(ledger.read_bytes(), ledger_before)
        report = self.global_root / "reports" / "architecture-routes.md"
        receipt = phx_ledger.write_report(ledger, report)
        idempotent = phx_ledger.write_report(ledger, report)
        verified = phx_ledger.verify_report(ledger, report)
        self.assertTrue(receipt["ok"])
        self.assertTrue(verified["ok"])
        self.assertTrue(idempotent["idempotent"])
        self.assertEqual(receipt["report_sha256"], verified["report_sha256"])
        rendered = report.read_text(encoding="utf-8")
        self.assertIn("Global Architecture Route", rendered)
        self.assertIn(consultation["consultation_id"], rendered)
        self.assertIn("approved_with_constraints", rendered)
        self.assertEqual(self._tree(self.project), [])

    def test_major_architecture_adoption_requires_prior_approved_user_consultation(self) -> None:
        ledger, _ = self._started()
        route = phx_ledger.record_route(
            ledger,
            self._route(
                key="route.global_lifecycle_reorganization",
                title="Reorganize the global lifecycle",
                summary="Change the coordination boundaries of the global lifecycle.",
                domain="coordination",
                kind="architecture_reorganization",
                origin="architecture_review",
            ),
        )
        measurement = phx_ledger.record_measurement(
            ledger, self._measurement(route["route_id"])
        )
        before = ledger.read_bytes()
        missing_consultation = "consultation-" + "0" * 64
        with self.assertRaisesRegex(ValueError, "consult"):
            phx_ledger.record_adoption(
                ledger,
                self._adoption(
                    route["route_id"],
                    measurement["measurement_id"],
                    missing_consultation,
                ),
            )
        self.assertEqual(ledger.read_bytes(), before)

        declined = phx_ledger.record_consultation(
            ledger,
            self._consultation(
                route["route_id"],
                decision="declined",
                response="Do not adopt this architecture change.",
            ),
        )
        before = ledger.read_bytes()
        with self.assertRaisesRegex(ValueError, "approval|approved"):
            phx_ledger.record_adoption(
                ledger,
                self._adoption(
                    route["route_id"],
                    measurement["measurement_id"],
                    declined["consultation_id"],
                ),
            )
        self.assertEqual(ledger.read_bytes(), before)

    def test_adoption_uses_latest_consultation_and_acknowledges_exact_constraints(self) -> None:
        ledger, _ = self._started()
        route = phx_ledger.record_route(
            ledger,
            self._route(
                key="route.user_bounded_reorganization",
                title="User-bounded architecture reorganization",
                domain="coordination",
                kind="architecture_reorganization",
                origin="architecture_review",
            ),
        )
        measurement = phx_ledger.record_measurement(
            ledger, self._measurement(route["route_id"])
        )
        earlier = phx_ledger.record_consultation(
            ledger, self._consultation(route["route_id"])
        )
        latest = phx_ledger.record_consultation(
            ledger,
            self._consultation(
                route["route_id"],
                decision="approved_with_constraints",
                constraints=[
                    "preserve public command compatibility",
                    "retain snapshot and project ownership checks",
                ],
                response="Approved only under both recorded constraints.",
            ),
        )

        before = ledger.read_bytes()
        with self.assertRaisesRegex(ValueError, "latest.*consultation"):
            phx_ledger.record_adoption(
                ledger,
                self._adoption(
                    route["route_id"],
                    measurement["measurement_id"],
                    earlier["consultation_id"],
                ),
            )
        self.assertEqual(ledger.read_bytes(), before)

        with self.assertRaisesRegex(ValueError, "constraint"):
            phx_ledger.record_adoption(
                ledger,
                self._adoption(
                    route["route_id"],
                    measurement["measurement_id"],
                    latest["consultation_id"],
                    acknowledged_constraints=[
                        "retain snapshot and project ownership checks"
                    ],
                ),
            )
        self.assertEqual(ledger.read_bytes(), before)

        adopted = phx_ledger.record_adoption(
            ledger,
            self._adoption(
                route["route_id"],
                measurement["measurement_id"],
                latest["consultation_id"],
                acknowledged_constraints=latest["constraints"],
            ),
        )
        self.assertEqual(
            adopted["consultation_constraints_acknowledged"], latest["constraints"]
        )

    def test_scoped_operational_cost_route_can_be_adopted_after_consultation(self) -> None:
        ledger, _ = self._started(scope="global-cost-routes")
        route = phx_ledger.record_route(
            ledger,
            self._route(
                key="route.skip_inapplicable_optional_subsystem",
                title="Skip inapplicable optional subsystem audits",
                summary="Avoid optional-subsystem scans after canonical applicability binding.",
                domain="performance_cost",
                kind="work_elimination",
                origin="measurement",
            ),
        )
        measurement = phx_ledger.record_measurement(
            ledger, self._measurement(route["route_id"], elapsed_seconds=0.8)
        )
        consultation = phx_ledger.record_consultation(
            ledger,
            {
                **self._consultation(route["route_id"]),
                "consultation_context": "User approved a scoped operational adoption, not a broad redesign.",
            },
        )
        adoption = phx_ledger.record_adoption(
            ledger,
            self._adoption(
                route["route_id"],
                measurement["measurement_id"],
                consultation["consultation_id"],
            ),
        )
        self.assertEqual(adoption["consultation_id"], consultation["consultation_id"])

    def test_exact_duplicates_are_idempotent_and_semantic_drift_fails(self) -> None:
        ledger, _ = self._started()
        route_input = self._route()
        route = phx_ledger.record_route(ledger, route_input)
        after_route = ledger.read_bytes()
        duplicate_route = phx_ledger.record_route(ledger, route_input)
        self.assertTrue(duplicate_route["idempotent"])
        self.assertEqual(ledger.read_bytes(), after_route)

        drifted = {**route_input, "summary": "A materially different route meaning."}
        with self.assertRaisesRegex(ValueError, "different semantics"):
            phx_ledger.record_route(ledger, drifted)
        self.assertEqual(ledger.read_bytes(), after_route)

        measurement_input = self._measurement(route["route_id"])
        measurement = phx_ledger.record_measurement(ledger, measurement_input)
        after_measurement = ledger.read_bytes()
        duplicate_measurement = phx_ledger.record_measurement(ledger, measurement_input)
        self.assertTrue(duplicate_measurement["idempotent"])
        self.assertEqual(ledger.read_bytes(), after_measurement)

        consultation_input = self._consultation(route["route_id"])
        consultation = phx_ledger.record_consultation(ledger, consultation_input)
        after_consultation = ledger.read_bytes()
        duplicate_consultation = phx_ledger.record_consultation(ledger, consultation_input)
        self.assertTrue(duplicate_consultation["idempotent"])
        self.assertEqual(ledger.read_bytes(), after_consultation)

        adoption_input = self._adoption(
            route["route_id"],
            measurement["measurement_id"],
            consultation["consultation_id"],
        )
        adoption = phx_ledger.record_adoption(ledger, adoption_input)
        after_adoption = ledger.read_bytes()
        duplicate_adoption = phx_ledger.record_adoption(ledger, adoption_input)
        self.assertTrue(duplicate_adoption["idempotent"])
        self.assertEqual(duplicate_adoption["adoption_id"], adoption["adoption_id"])
        self.assertEqual(ledger.read_bytes(), after_adoption)

        changed_adoption = {
            **adoption_input,
            "implementation_summary": "A different implementation was adopted.",
        }
        with self.assertRaisesRegex(ValueError, "different adoption"):
            phx_ledger.record_adoption(ledger, changed_adoption)
        self.assertEqual(ledger.read_bytes(), after_adoption)

    def test_same_run_and_closed_cross_run_relations_are_hash_bound(self) -> None:
        first_ledger, first_status = self._started(scope="route-lineage-source")
        base_route = phx_ledger.record_route(
            first_ledger,
            self._route(key="route.base_snapshot_binding", title="Base snapshot binding"),
        )
        same_run = phx_ledger.record_route(
            first_ledger,
            self._route(
                key="route.refined_snapshot_binding",
                title="Refined snapshot binding",
                relations=[
                    {
                        "relation_type": "extends",
                        "target_qualified_id": f"{first_status['run_id']}/{base_route['route_id']}",
                        "target_ledger_path": str(first_ledger),
                    }
                ],
            ),
        )
        relation = same_run["relations"][0]
        self.assertFalse(relation["target_ledger_closed"])
        self.assertIsNone(relation["target_closed_ledger_sha256"])
        self.assertEqual(relation["target_route_event_sha256"], base_route["event_sha256"])

        phx_ledger.close(first_ledger)
        second_ledger, _ = self._started(scope="route-lineage-consumer")
        cross_run = phx_ledger.record_route(
            second_ledger,
            self._route(
                key="route.cross_run_refinement",
                title="Cross-run refinement",
                relations=[
                    {
                        "relation_type": "refines",
                        "target_qualified_id": f"{first_status['run_id']}/{base_route['route_id']}",
                        "target_ledger_path": str(first_ledger),
                    }
                ],
            ),
        )
        relation = cross_run["relations"][0]
        self.assertTrue(relation["target_ledger_closed"])
        self.assertEqual(
            relation["target_closed_ledger_sha256"],
            hashlib.sha256(first_ledger.read_bytes()).hexdigest(),
        )

        active_ledger, active_status = self._started(scope="active-cross-run-source")
        active_route = phx_ledger.record_route(
            active_ledger,
            self._route(key="route.active_target", title="Active target"),
        )
        consumer_ledger, _ = self._started(scope="active-cross-run-consumer")
        with self.assertRaisesRegex(ValueError, "must be closed"):
            phx_ledger.record_route(
                consumer_ledger,
                self._route(
                    key="route.invalid_active_cross_run",
                    title="Invalid active cross-run route",
                    relations=[
                        {
                            "relation_type": "related_to",
                            "target_qualified_id": f"{active_status['run_id']}/{active_route['route_id']}",
                            "target_ledger_path": str(active_ledger),
                        }
                    ],
                ),
            )

    def test_active_chx_source_reference_is_prefix_bound(self) -> None:
        chx_root = self.base / "global-chx"
        chx_status = chx_ledger.start_ledger(
            root=chx_root,
            task="Record a performance problem for PHX synthesis.",
            run_id="run-phx-source-chx-001",
            host_task_scope_id="phx-source-test",
            project_roots=[self.project],
        )
        chx_path = Path(chx_status["ledger_path"])
        issue = chx_ledger.record_issue(
            chx_path,
            {
                "classification": "performance / repeated aggregate validation",
                "causation": "caused",
                "mechanism_type": "interface_contract",
                "mechanism": "One aggregate command repeated immutable validation work.",
                "trigger": "A full administrative projection was requested.",
                "observed_effect": "Administrative runtime dominated useful work.",
                "mathematical_effect": "none",
                "current_workaround": "Run a bounded projection manually.",
                "upgrade_requirement": "Synthesize a reusable, snapshot-bound PHX route.",
                "audit_anchors": ["test:active-chx-source"],
            },
        )

        ledger, _ = self._started()
        route = phx_ledger.record_route(
            ledger,
            self._route(
                key="route.chx_synthesized_context",
                title="CHX-synthesized inspection context",
                origin="chx_synthesis",
                source_chx_refs=[
                    {
                        "ledger_path": str(chx_path),
                        "qualified_issue_id": f"{chx_status['run_id']}/{issue['issue_id']}",
                    }
                ],
            ),
        )
        reference = route["source_chx_refs"][0]
        self.assertEqual(reference["issue_event_sha256"], issue["event_sha256"])
        self.assertFalse(reference["target_ledger_closed"])
        self.assertIsNone(reference["target_closed_ledger_sha256"])
        self.assertRegex(reference["target_event_prefix_sha256"], r"^[0-9a-f]{64}$")

        chx_ledger.close_ledger(chx_path)
        replay = phx_ledger.record_route(
            ledger,
            self._route(
                key="route.chx_synthesized_context",
                title="CHX-synthesized inspection context",
                origin="chx_synthesis",
                source_chx_refs=[
                    {
                        "ledger_path": str(chx_path),
                        "qualified_issue_id": f"{chx_status['run_id']}/{issue['issue_id']}",
                    }
                ],
            ),
        )
        self.assertTrue(replay["idempotent"])

    def test_global_search_marks_superseded_routes_and_current_heads(self) -> None:
        first, first_status = self._started(scope="search-predecessor")
        predecessor = phx_ledger.record_route(
            first,
            self._route(
                key="route.old_global_coordination",
                title="Old global coordination route",
                domain="reliability",
                kind="architecture_reorganization",
                origin="architecture_review",
            ),
        )
        phx_ledger.close(first)

        second, _ = self._started(scope="search-successor")
        successor = phx_ledger.record_route(
            second,
            self._route(
                key="route.current_global_coordination",
                title="Current global coordination route",
                domain="coordination",
                kind="architecture_reorganization",
                origin="architecture_review",
                relations=[
                    {
                        "relation_type": "supersedes",
                        "target_qualified_id": f"{first_status['run_id']}/{predecessor['route_id']}",
                        "target_ledger_path": str(first),
                    }
                ],
            ),
        )
        phx_ledger.close(second)
        result = phx_ledger.search_routes(
            root=self.global_root,
            query="global coordination",
            domains=[],
            relation_types=[],
            allow_custom_root=True,
            write_receipt=True,
        )
        by_id = {item["qualified_route_id"]: item for item in result["routes"]}
        old_id = f"{first_status['run_id']}/{predecessor['route_id']}"
        self.assertEqual(by_id[old_id]["effective_status"], "superseded")
        self.assertEqual(by_id[old_id]["superseded_by"], [successor["run_id"] + "/" + successor["route_id"]])
        self.assertEqual(result["routes"][0]["effective_status"], "current")
        self.assertRegex(result["routes"][0]["route_event_sha256"], r"^[0-9a-f]{64}$")
        receipt_path = Path(result["search_receipt_path"])
        self.assertTrue(receipt_path.is_relative_to(self.global_root / "search-receipts"))
        self.assertEqual(stat.S_IMODE(receipt_path.stat().st_mode), 0o600)
        self.assertEqual(
            result["search_receipt_sha256"],
            hashlib.sha256(
                phx_ledger.canonical_nfc_bytes(result["search_receipt"])
            ).hexdigest(),
        )
        filtered = phx_ledger.search_routes(
            root=self.global_root,
            query="Old global coordination",
            domains=["reliability"],
            allow_custom_root=True,
        )
        self.assertEqual(len(filtered["routes"]), 1)
        self.assertEqual(filtered["routes"][0]["effective_status"], "superseded")

    def test_tamper_truncation_and_post_close_mutation_fail_closed(self) -> None:
        ledger, _ = self._started()
        phx_ledger.record_route(
            ledger,
            self._route(title="Tamper-sensitive route"),
        )
        phx_ledger.close(ledger)
        original = ledger.read_bytes()

        with self.assertRaisesRegex(ValueError, "closed"):
            phx_ledger.record_route(
                ledger,
                self._route(key="route.after_close", title="After close"),
            )
        self.assertEqual(ledger.read_bytes(), original)

        tampered = original.replace(b"Tamper-sensitive", b"Xamper-sensitive", 1)
        self.assertNotEqual(tampered, original)
        ledger.write_bytes(tampered)
        with self.assertRaisesRegex(ValueError, "hash"):
            phx_ledger._read_ledger(ledger)

        ledger.write_bytes(original[:-1])
        with self.assertRaisesRegex(ValueError, "complete final line"):
            phx_ledger._read_ledger(ledger)
        ledger.write_bytes(original)
        _, status = phx_ledger._read_ledger(ledger)
        self.assertTrue(status["closed"])

    def test_adoption_requires_a_supported_measurement_for_the_same_route(self) -> None:
        ledger, _ = self._started()
        route = phx_ledger.record_route(ledger, self._route())
        consultation = phx_ledger.record_consultation(
            ledger, self._consultation(route["route_id"])
        )

        before = ledger.read_bytes()
        unknown_measurement = "measurement-" + "0" * 64
        with self.assertRaisesRegex(ValueError, "measurement"):
            phx_ledger.record_adoption(
                ledger,
                self._adoption(
                    route["route_id"],
                    unknown_measurement,
                    consultation["consultation_id"],
                ),
            )
        self.assertEqual(ledger.read_bytes(), before)

        unsupported = phx_ledger.record_measurement(
            ledger,
            self._measurement(route["route_id"], outcome="not_supported"),
        )
        before = ledger.read_bytes()
        with self.assertRaisesRegex(ValueError, "supporting measurement|supported"):
            phx_ledger.record_adoption(
                ledger,
                self._adoption(
                    route["route_id"],
                    unsupported["measurement_id"],
                    consultation["consultation_id"],
                ),
            )
        self.assertEqual(ledger.read_bytes(), before)

    def test_consultation_provenance_precedes_implementation_and_metrics_are_finite(self) -> None:
        ledger, _ = self._started()
        route = phx_ledger.record_route(ledger, self._route())
        invalid = self._consultation(route["route_id"])
        invalid["user_response_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "response SHA-256"):
            phx_ledger.record_consultation(ledger, invalid)

        late = self._consultation(route["route_id"])
        late["implementation_state_at_consultation"] = "already_in_progress"
        with self.assertRaisesRegex(ValueError, "precede implementation"):
            phx_ledger.record_consultation(ledger, late)

        active = self._measurement(route["route_id"])
        active["mutation_scope"] = "active_architecture"
        with self.assertRaisesRegex(ValueError, "prior user authorization"):
            phx_ledger.record_measurement(ledger, active)
        authorized = phx_ledger.record_consultation(
            ledger, self._consultation(route["route_id"])
        )
        active["authorization_consultation_id_or_null"] = authorized[
            "consultation_id"
        ]
        active["authorization_scope_acknowledged_or_null"] = authorized[
            "authorization_scope"
        ]
        active["consultation_constraints_acknowledged"] = authorized["constraints"]
        recorded = phx_ledger.record_measurement(ledger, active)
        self.assertEqual(recorded["mutation_scope"], "active_architecture")

        nonfinite = self._measurement(route["route_id"])
        nonfinite["metrics"][0]["value"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            phx_ledger.record_measurement(ledger, nonfinite)

        unbound = self._measurement(route["route_id"])
        unbound["evidence_sha256s"] = []
        with self.assertRaisesRegex(ValueError, "digest-bound evidence"):
            phx_ledger.record_measurement(ledger, unbound)

    def test_existing_global_root_must_already_be_private(self) -> None:
        unsafe = self.base / "world-readable-phx"
        unsafe.mkdir(mode=0o755)
        unsafe.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "mode 0700"):
            phx_ledger.start(
                root=unsafe,
                scope_id="unsafe-root",
                project_roots=[self.project],
                allow_custom_root=True,
            )

    def test_first_canonical_search_can_persist_a_hash_bound_empty_receipt(self) -> None:
        canonical = self.base / "fresh-canonical-phx"
        with mock.patch.object(phx_ledger, "DEFAULT_GLOBAL_ROOT", canonical):
            result = phx_ledger.search_routes(
                root=canonical,
                query="first performance route lookup",
                write_receipt=True,
            )
        self.assertEqual(result["route_count"], 0)
        self.assertEqual(result["search_receipt"]["scanned_ledger_heads"], [])
        self.assertTrue(Path(result["search_receipt_path"]).is_file())
        self.assertEqual(stat.S_IMODE(canonical.stat().st_mode), 0o700)

if __name__ == "__main__":
    unittest.main()
