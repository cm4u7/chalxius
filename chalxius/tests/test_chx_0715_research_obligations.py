from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mathgraph.cli import main as cli_main
from mathgraph.contracts import sha256_bytes
from mathgraph.store import MathGraphStore


class ResearchObligationClosureTests(unittest.TestCase):
    @staticmethod
    def _store(root: Path, *, project_id: str = "chx-0715") -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id=project_id,
            title="CHX 0.7.15 Research obligations",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _blank_assurance() -> dict[str, list[object]]:
        return {
            "source_uses": [],
            "route_invalidations": [],
            "extremal_cases": [],
            "claim_strength": [],
            "contour_substitutions": [],
            "claimed_structures": [],
            "program_math_alignments": [],
        }

    def _ingest_plain_assignment(
        self,
        store: MathGraphStore,
        planned: dict[str, object],
        assignment: dict[str, object],
    ) -> dict[str, object]:
        lifecycle = store.v5_lifecycle()
        card = json.loads(
            Path(str(assignment["task_card_path"])).read_text(encoding="utf-8")
        )
        artifact_dir = store.root / str(assignment["artifact_dir_relpath"])
        artifact_dir.mkdir(parents=True, exist_ok=True)
        report_path = artifact_dir / "worker-report.md"
        report_path.write_text(
            "One bounded constructive result is frozen for supervision.\n",
            encoding="utf-8",
        )
        report = {
            "path": report_path.relative_to(store.root).as_posix(),
            "sha256": sha256_bytes(report_path.read_bytes()),
            "role": "research_report",
        }
        payload = {
            "schema_version": 5,
            "project_id": store.project_id(),
            "round_id": planned["round_id"],
            "assignment_id": assignment["assignment_id"],
            "worker_id": assignment["worker_id"],
            "task_card_sha256": assignment["task_card_sha256"],
            "blackboard_snapshot_sha256": assignment[
                "blackboard_snapshot_sha256"
            ],
            "outcome": "proof",
            "claim": "One constructive worker result is ready for supervision.",
            "content": "This result remains nontruth Research.",
            "narrative": {
                "rationale": "Freeze exact output before supervision.",
                "summary": "One assignment completed.",
                "intuition": "The receipt closes only its source work obligation.",
                "limitations": "This is not Candidate or Fact authority.",
            },
            "artifacts": [report],
            "obligation_dispositions": [
                {
                    "obligation_id": obligation["obligation_id"],
                    "status": "complete",
                    "witness_artifact_sha256s": [report["sha256"]],
                    "rationale": "The exact report is hash-bound.",
                }
                for obligation in card["assurance_contract"]["obligations"]
            ],
            "computation_manifest": None,
            "research_assurance": self._blank_assurance(),
        }
        return_path = Path(str(assignment["return_path"]))
        return_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        receipt = lifecycle.ingest_return(
            round_id=str(planned["round_id"]),
            assignment_id=str(assignment["assignment_id"]),
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        self.assertEqual(receipt["status"], "ingested", receipt)
        return receipt

    def test_main_reuses_identical_unbound_semantics_across_actor_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            payload = {
                "kind": "insight",
                "claim": "A Main-authored unbound Research statement.",
                "content": "The complete semantics are unchanged.",
            }
            first = lifecycle.add_research(
                payload,
                actor="main-session-a",
                reuse_unbound_main_semantics=True,
            )
            second = lifecycle.add_research(
                payload,
                actor="root-session-b",
                reuse_unbound_main_semantics=True,
            )
            self.assertEqual(second["research_id"], first["research_id"])
            self.assertEqual(second["actor"], "main-session-a")
            self.assertEqual(len(lifecycle.research_envelopes()), 1)

    def test_ordinary_and_task_bound_writes_keep_actor_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            payload = {"claim": "Actor-sensitive ordinary Research."}
            first = lifecycle.add_research(payload, actor="main")
            second = lifecycle.add_research(payload, actor="root")
            self.assertNotEqual(second["research_id"], first["research_id"])

            binding = {
                "round_id": "round-test-binding",
                "assignment_id": "a01-test-prove",
            }
            bound = lifecycle.add_research(
                {"claim": "Task-bound Research remains distinct."},
                actor="worker-a",
                task_binding=binding,
            )
            self.assertIn("task_binding", bound["metadata"])
            with self.assertRaisesRegex(ValueError, "requires an unbound"):
                lifecycle.add_research(
                    {"claim": "Task-bound Research remains distinct."},
                    actor="worker-b",
                    task_binding=binding,
                    reuse_unbound_main_semantics=True,
                )

    def test_cli_uses_authority_role_not_actor_text_for_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "main-project"
            self._store(root, project_id="cli-main-reuse")
            payload_path = Path(temporary) / "research.json"
            payload_path.write_text(
                json.dumps({"claim": "CLI role-bound semantic reuse."}),
                encoding="utf-8",
            )

            ids: list[str] = []
            for actor in ("session-a", "session-b"):
                stdout = StringIO()
                with redirect_stdout(stdout), redirect_stderr(StringIO()):
                    code = cli_main(
                        [
                            "--root",
                            str(root),
                            "--role",
                            "main",
                            "memory-add",
                            "--input",
                            str(payload_path),
                            "--actor",
                            actor,
                        ]
                    )
                self.assertEqual(code, 0)
                ids.append(json.loads(stdout.getvalue())["research_id"])
            self.assertEqual(ids[0], ids[1])

            operator_root = Path(temporary) / "operator-project"
            self._store(operator_root, project_id="cli-operator-no-reuse")
            operator_ids: list[str] = []
            for actor in ("main", "root"):
                stdout = StringIO()
                with redirect_stdout(stdout), redirect_stderr(StringIO()):
                    code = cli_main(
                        [
                            "--root",
                            str(operator_root),
                            "--role",
                            "operator",
                            "memory-add",
                            "--input",
                            str(payload_path),
                            "--actor",
                            actor,
                        ]
                    )
                self.assertEqual(code, 0)
                operator_ids.append(json.loads(stdout.getvalue())["research_id"])
            self.assertNotEqual(operator_ids[0], operator_ids[1])

    def test_valid_receipt_closes_source_but_not_worker_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {"claim": "Complete this exact production obligation."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[source["research_id"]],
                host_task_scope_id="valid-production-obligation",
            )
            self.assertIn(
                source["research_id"],
                {item["research_id"] for item in lifecycle.frontier(limit=20)},
            )
            receipt = self._ingest_plain_assignment(
                store, planned, planned["assignments"][0]
            )

            active_ids = {
                item["research_id"] for item in lifecycle.frontier(limit=20)
            }
            self.assertNotIn(source["research_id"], active_ids)
            self.assertIn(receipt["research_id"], active_ids)
            history_ids = {
                item["research_id"]
                for item in lifecycle.frontier(limit=20, include_history=True)
            }
            self.assertIn(source["research_id"], history_ids)

            override_ids = {
                item["research_id"]
                for item in lifecycle.frontier(
                    limit=20,
                    _research_records_override=lifecycle.research_envelopes(),
                )
            }
            self.assertIn(source["research_id"], override_ids)

    def test_one_valid_assignment_closes_only_its_source_obligation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            first = lifecycle.add_research(
                {"claim": "First independent production obligation."},
                actor="main",
            )
            second = lifecycle.add_research(
                {"claim": "Second independent production obligation."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=2,
                mode="prove",
                research_ids=[first["research_id"], second["research_id"]],
                host_task_scope_id="partial-production-obligations",
            )
            assignment = next(
                item
                for item in planned["assignments"]
                if item["research_id"] == first["research_id"]
            )
            receipt = self._ingest_plain_assignment(store, planned, assignment)
            active_ids = {
                item["research_id"] for item in lifecycle.frontier(limit=20)
            }
            self.assertNotIn(first["research_id"], active_ids)
            self.assertIn(second["research_id"], active_ids)
            self.assertIn(receipt["research_id"], active_ids)

    def test_pending_quarantined_invalid_and_aborted_work_do_not_close(self) -> None:
        for state in ("pending", "quarantined", "invalid", "aborted"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temporary:
                store = self._store(
                    Path(temporary) / "project",
                    project_id=f"chx-0715-{state}",
                )
                lifecycle = store.v5_lifecycle()
                source = lifecycle.add_research(
                    {"claim": f"The {state} source obligation remains visible."},
                    actor="main",
                )
                planned = lifecycle.create_production_round(
                    workers=1,
                    mode="prove",
                    research_ids=[source["research_id"]],
                    host_task_scope_id=f"{state}-production-obligation",
                )
                assignment = planned["assignments"][0]

                if state == "quarantined":
                    return_path = Path(str(assignment["return_path"]))
                    return_path.write_text("{}", encoding="utf-8")
                    result = lifecycle.ingest_return(
                        round_id=str(planned["round_id"]),
                        assignment_id=str(assignment["assignment_id"]),
                        worker_final_sha256=sha256_bytes(return_path.read_bytes()),
                    )
                    self.assertEqual(result["status"], "quarantined")
                elif state == "invalid":
                    self._ingest_plain_assignment(store, planned, assignment)
                    receipt_path = (
                        store.rounds_dir
                        / str(planned["round_id"])
                        / "returns"
                        / f"{assignment['assignment_id']}.receipt.json"
                    )
                    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                    receipt["return_sha256"] = "0" * 64
                    receipt_path.write_text(
                        json.dumps(receipt, sort_keys=True),
                        encoding="utf-8",
                    )
                elif state == "aborted":
                    self._ingest_plain_assignment(store, planned, assignment)
                    with store.v5_mutation_lock(command="work-unit-abort"):
                        store.reasoning_modes().abort_work_unit(
                            round_id=str(planned["round_id"]),
                            actor="main",
                            reason="An aborted production unit cannot close the source.",
                        )

                active_ids = {
                    item["research_id"] for item in lifecycle.frontier(limit=20)
                }
                self.assertIn(source["research_id"], active_ids)

    def test_explicit_id_planning_does_not_call_generic_frontier(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {"claim": "Explicit planning remains available."},
                actor="main",
            )
            with patch.object(
                lifecycle,
                "frontier",
                side_effect=AssertionError("generic frontier must not run"),
            ):
                planned = lifecycle.create_production_round(
                    workers=1,
                    mode="prove",
                    research_ids=[source["research_id"]],
                    host_task_scope_id="explicit-id-planning",
                )
            self.assertEqual(
                planned["assignments"][0]["research_id"], source["research_id"]
            )

    def test_generic_planning_rechecks_obligation_closure_under_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {"claim": "Close this obligation during generic selection."},
                actor="main",
            )
            pending = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[source["research_id"]],
                host_task_scope_id="pending-before-generic-selection",
            )
            original_frontier = lifecycle.frontier

            def close_after_selection(*args: object, **kwargs: object) -> list[dict[str, object]]:
                selected = original_frontier(*args, **kwargs)
                self._ingest_plain_assignment(
                    store,
                    pending,
                    pending["assignments"][0],
                )
                return selected

            with patch.object(lifecycle, "frontier", side_effect=close_after_selection):
                with self.assertRaisesRegex(
                    ValueError,
                    "generic production frontier changed before round creation",
                ):
                    lifecycle.create_production_round(
                        workers=1,
                        mode="prove",
                        host_task_scope_id="generic-selection-race",
                    )

            public_rounds = sorted(store.rounds_dir.glob("round-*"))
            self.assertEqual([path.name for path in public_rounds], [pending["round_id"]])


if __name__ == "__main__":
    unittest.main()
