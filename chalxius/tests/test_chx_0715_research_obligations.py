from __future__ import annotations

import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
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
        return_path = self._write_plain_assignment(store, planned, assignment)
        receipt = store.v5_lifecycle().ingest_return(
            round_id=str(planned["round_id"]),
            assignment_id=str(assignment["assignment_id"]),
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        self.assertEqual(receipt["status"], "ingested", receipt)
        return receipt

    def _write_plain_assignment(
        self,
        store: MathGraphStore,
        planned: dict[str, object],
        assignment: dict[str, object],
    ) -> Path:
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
        return return_path

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

    def test_pending_quarantined_and_aborted_work_do_not_close_but_receipt_drift_does_not_reopen_product(self) -> None:
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
                if state == "invalid":
                    # The receipt is only a workflow marker.  Its tampering is
                    # diagnostic, but the independently hash-bound Research
                    # product still closes the source obligation.
                    self.assertNotIn(source["research_id"], active_ids)
                else:
                    self.assertIn(source["research_id"], active_ids)

    def test_missing_worker_product_does_not_close_source_obligation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {"claim": "A missing product must remain actionable."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[source["research_id"]],
                host_task_scope_id="missing-product-obligation",
            )
            assignment = planned["assignments"][0]
            receipt = self._ingest_plain_assignment(store, planned, assignment)
            (lifecycle.research_entries_dir / f"{receipt['research_id']}.json").unlink()
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
            self.assertEqual(
                [path.name for path in public_rounds], [pending["round_id"]]
            )

    def test_transient_canonical_return_or_artifact_visibility_is_retryable(self) -> None:
        for missing_kind in ("return", "artifact"):
            with self.subTest(missing_kind=missing_kind), tempfile.TemporaryDirectory() as temporary:
                store = self._store(
                    Path(temporary) / "project",
                    project_id=f"chx-0715-visibility-{missing_kind}",
                )
                lifecycle = store.v5_lifecycle()
                source = lifecycle.add_research(
                    {"claim": f"Keep a transient {missing_kind} handoff retryable."},
                    actor="main",
                )
                planned = lifecycle.create_production_round(
                    workers=1,
                    mode="prove",
                    research_ids=[source["research_id"]],
                    host_task_scope_id=f"visibility-{missing_kind}",
                )
                assignment = planned["assignments"][0]
                return_path = self._write_plain_assignment(
                    store, planned, assignment
                )
                preflight = lifecycle.preflight_return(
                    round_id=str(planned["round_id"]),
                    assignment_id=str(assignment["assignment_id"]),
                )
                self.assertTrue(preflight["valid"])
                payload = json.loads(return_path.read_text(encoding="utf-8"))
                missing_path = (
                    return_path
                    if missing_kind == "return"
                    else store.root / payload["artifacts"][0]["path"]
                )
                held_path = missing_path.with_name(missing_path.name + ".held")
                missing_path.rename(held_path)

                round_dir = store.rounds_dir / str(planned["round_id"])
                assignment_id = str(assignment["assignment_id"])
                receipt_path = (
                    round_dir / "returns" / f"{assignment_id}.receipt.json"
                )
                terminal_dir = round_dir / "terminal" / assignment_id
                research_count = len(lifecycle.research_records())
                quarantine_count = len(list(lifecycle.quarantine_dir.glob("*.json")))
                with self.assertRaisesRegex(
                    ValueError,
                    "not stably visible; retry ingest-return",
                ):
                    lifecycle.ingest_return(
                        round_id=str(planned["round_id"]),
                        assignment_id=assignment_id,
                    )
                self.assertFalse(receipt_path.exists())
                self.assertFalse(terminal_dir.exists())
                self.assertEqual(len(lifecycle.research_records()), research_count)
                self.assertEqual(
                    len(list(lifecycle.quarantine_dir.glob("*.json"))),
                    quarantine_count,
                )

                held_path.rename(missing_path)
                receipt = lifecycle.ingest_return(
                    round_id=str(planned["round_id"]),
                    assignment_id=assignment_id,
                )
                self.assertEqual(receipt["status"], "ingested")

    def test_terminal_seal_cow_revokes_worker_paths_and_keeps_authority(self) -> None:
        """CHX-037: post-final worker paths are COW-detached and read-only."""

        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", project_id="chx-037")
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {"claim": "Seal the exact worker artifact before reuse."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[source["research_id"]],
                host_task_scope_id="chx-037-terminal-seal",
            )
            assignment = planned["assignments"][0]
            receipt = self._ingest_plain_assignment(store, planned, assignment)
            result = lifecycle._research_record(str(receipt["research_id"]))
            self.assertTrue(result["metadata"]["artifacts"])
            self.assertTrue(
                all(
                    item["path"].startswith(
                        f"rounds/{planned['round_id']}/terminal/{assignment['assignment_id']}/"
                    )
                    for item in result["metadata"]["artifacts"]
                )
            )

            round_dir = store.rounds_dir / str(planned["round_id"])
            assignment_id = str(assignment["assignment_id"])
            seal_path = round_dir / "terminal" / assignment_id / "seal.json"
            seal = json.loads(seal_path.read_text(encoding="utf-8"))
            source_artifact = store.root / seal["artifacts"][0]["source_path"]
            sealed_artifact = store.root / seal["artifacts"][0]["sealed_path"]
            original = sealed_artifact.read_bytes()
            return_before = Path(str(assignment["return_path"])).read_bytes()
            receipt_path = round_dir / "returns" / f"{assignment_id}.receipt.json"
            receipt_before = receipt_path.read_bytes()
            research_path = (
                lifecycle.research_entries_dir / f"{receipt['research_id']}.json"
            )
            research_before = research_path.read_bytes()
            work_root = store.root / str(assignment["work_dir_relpath"])
            with self.assertRaises(OSError):
                source_artifact.write_text(
                    "bypassed stale write\n", encoding="utf-8"
                )
            with self.assertRaises(OSError):
                Path(str(assignment["return_path"])).write_text(
                    "bypassed stale return\n", encoding="utf-8"
                )
            with self.assertRaises(OSError):
                (work_root / "stale.md").write_text(
                    "bypassed stale draft\n", encoding="utf-8"
                )
            status = lifecycle.round_status(str(planned["round_id"]))
            projected = next(
                item
                for item in status["assignments"]
                if item["assignment_id"] == assignment_id
            )
            self.assertEqual(projected["terminal_source_diagnostics"], [])
            self.assertEqual(projected["terminalized_lease_marker"], "valid")
            self.assertEqual(sealed_artifact.read_bytes(), original)
            self.assertEqual(source_artifact.read_bytes(), original)
            self.assertEqual(Path(str(assignment["return_path"])).read_bytes(), return_before)
            self.assertEqual(receipt_path.read_bytes(), receipt_before)
            self.assertEqual(research_path.read_bytes(), research_before)
            self.assertEqual(
                (store.root / result["metadata"]["artifacts"][0]["path"]).read_bytes(),
                original,
            )
            marker = lifecycle._validate_terminalized_lease_marker(
                round_dir=round_dir,
                assignment=assignment,
                seal=seal,
                required=True,
            )
            self.assertIsNotNone(marker)
            assert marker is not None
            self.assertEqual(marker["truth_effect"], "none")
            self.assertEqual(marker["project_effect"], "none")

    def test_terminal_source_drift_remains_diagnostic_after_explicit_admin_override(self) -> None:
        """A deliberate chmod override is visible but cannot rewrite authority."""

        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", project_id="chx-037-diagnostic")
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {"claim": "Keep post-final source drift diagnostic only."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[source["research_id"]],
                host_task_scope_id="chx-037-diagnostic",
            )
            assignment = planned["assignments"][0]
            receipt = self._ingest_plain_assignment(store, planned, assignment)
            round_dir = store.rounds_dir / str(planned["round_id"])
            seal = json.loads(
                (round_dir / "terminal" / str(assignment["assignment_id"]) / "seal.json")
                .read_text(encoding="utf-8")
            )
            source_artifact = store.root / seal["artifacts"][0]["source_path"]
            sealed_artifact = store.root / seal["artifacts"][0]["sealed_path"]
            source_artifact.chmod(0o600)
            source_artifact.write_text("explicit admin drift\n", encoding="utf-8")
            projected = lifecycle.round_status(str(planned["round_id"]))["assignments"][0]
            self.assertIn(
                "source_artifact_0:bytes_drifted",
                projected["terminal_source_diagnostics"],
            )
            self.assertEqual(
                sealed_artifact.read_bytes(),
                b"One bounded constructive result is frozen for supervision.\n",
            )
            self.assertEqual(projected["research_product_id"], receipt["research_id"])

    def test_terminal_seal_replay_is_idempotent_and_conflicts_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", project_id="chx-037-replay")
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {"claim": "Finalize one assignment exactly once."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[source["research_id"]],
                host_task_scope_id="chx-037-terminal-replay",
            )
            assignment = planned["assignments"][0]
            return_path = self._write_plain_assignment(store, planned, assignment)
            return_sha = sha256_bytes(return_path.read_bytes())
            second_store = MathGraphStore(store.root)
            lifecycles = (lifecycle, second_store.v5_lifecycle())

            def ingest(index: int) -> dict[str, object]:
                return lifecycles[index].ingest_return(
                    round_id=str(planned["round_id"]),
                    assignment_id=str(assignment["assignment_id"]),
                    worker_final_sha256=return_sha,
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(ingest, range(2)))
            self.assertEqual(results[0]["receipt_id"], results[1]["receipt_id"])
            self.assertTrue(all(item["status"] == "ingested" for item in results))

            return_path.chmod(0o600)
            return_path.write_text('{"conflict":true}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "terminal ingest conflict"):
                lifecycle.ingest_return(
                    round_id=str(planned["round_id"]),
                    assignment_id=str(assignment["assignment_id"]),
                    worker_final_sha256=sha256_bytes(return_path.read_bytes()),
                )

    def test_terminal_snapshot_survives_artifact_swap_before_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", project_id="chx-037-swap")
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {"claim": "Snapshot the artifact before terminal publication."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[source["research_id"]],
                host_task_scope_id="chx-037-artifact-swap",
            )
            assignment = planned["assignments"][0]
            return_path = self._write_plain_assignment(store, planned, assignment)
            artifact = (
                store.root
                / str(assignment["artifact_dir_relpath"])
                / "worker-report.md"
            )
            original = artifact.read_bytes()
            prepare = lifecycle._prepare_terminal_seal

            def swap_then_prepare(**kwargs: object) -> dict[str, object]:
                artifact.write_text("swapped after snapshot\n", encoding="utf-8")
                return prepare(**kwargs)  # type: ignore[arg-type]

            with patch.object(
                lifecycle,
                "_prepare_terminal_seal",
                side_effect=swap_then_prepare,
            ):
                receipt = lifecycle.ingest_return(
                    round_id=str(planned["round_id"]),
                    assignment_id=str(assignment["assignment_id"]),
                    worker_final_sha256=sha256_bytes(return_path.read_bytes()),
                )
            result = lifecycle._research_record(str(receipt["research_id"]))
            sealed = store.root / result["metadata"]["artifacts"][0]["path"]
            self.assertEqual(sealed.read_bytes(), original)
            projected = lifecycle.round_status(str(planned["round_id"]))[
                "assignments"
            ][0]
            self.assertEqual(projected["terminal_source_diagnostics"], [])
            self.assertEqual(projected["terminalized_lease_marker"], "valid")

    def test_terminal_cow_failure_recovers_from_sealed_bundle(self) -> None:
        """A COW projection failure does not block Research and retries safely."""

        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", project_id="chx-037-cow-retry")
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {"claim": "Recover terminalization from the sealed bundle."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[source["research_id"]],
                host_task_scope_id="chx-037-cow-retry",
            )
            assignment = planned["assignments"][0]
            return_path = self._write_plain_assignment(store, planned, assignment)
            return_sha = sha256_bytes(return_path.read_bytes())
            round_dir = store.rounds_dir / str(planned["round_id"])
            assignment_id = str(assignment["assignment_id"])
            artifact_root = store.root / str(assignment["artifact_dir_relpath"])
            bundle_dir = round_dir / "terminal" / assignment_id
            receipt_path = round_dir / "returns" / f"{assignment_id}.receipt.json"
            real_replace = os.replace
            injected = False

            def fail_cow_artifact_publish(source_path: object, destination: object) -> None:
                nonlocal injected
                source = Path(source_path)  # type: ignore[arg-type]
                target = Path(destination)  # type: ignore[arg-type]
                if (
                    not injected
                    and target == artifact_root
                    and source.name.startswith(f".{artifact_root.name}.terminalizing-")
                ):
                    injected = True
                    raise OSError("injected COW artifact publication failure")
                real_replace(source_path, destination)  # type: ignore[arg-type]

            with patch(
                "mathgraph.v5_lifecycle.os.replace",
                side_effect=fail_cow_artifact_publish,
            ):
                first_receipt = lifecycle.ingest_return(
                    round_id=str(planned["round_id"]),
                    assignment_id=assignment_id,
                    worker_final_sha256=return_sha,
                )

            self.assertTrue(injected)
            self.assertTrue(bundle_dir.is_dir())
            self.assertEqual(first_receipt["status"], "ingested")
            self.assertEqual(first_receipt["terminalized_lease_status"], "pending")
            self.assertTrue(receipt_path.exists())
            self.assertEqual(len(lifecycle.research_records()), 2)
            marker_path = round_dir / "terminalized" / f"{assignment_id}.json"
            self.assertFalse(marker_path.exists())
            pending_status = lifecycle.round_status(str(planned["round_id"]))
            self.assertEqual(
                pending_status["assignments"][0]["terminalized_lease_marker"],
                "missing",
            )
            self.assertIn(
                "terminalized_lease_marker:missing",
                pending_status["assignments"][0]["terminal_source_diagnostics"],
            )
            # The legacy shared ``returns`` parent still permits an
            # uncooperative atomic replacement; retry must recover from the
            # terminal bundle rather than trusting that stale path.
            stale_return = return_path.parent / ".stale-return.json"
            stale_return.write_bytes(b"stale atomic replacement")
            os.replace(stale_return, return_path)

            receipt = lifecycle.ingest_return(
                round_id=str(planned["round_id"]),
                assignment_id=assignment_id,
                worker_final_sha256=return_sha,
            )
            self.assertEqual(receipt["status"], "ingested")
            self.assertEqual(
                return_path.read_bytes(),
                (bundle_dir / "return.json").read_bytes(),
            )
            self.assertTrue(marker_path.is_file())
            self.assertTrue(receipt_path.is_file())
            self.assertEqual(len(lifecycle.research_records()), 2)
            status = lifecycle.round_status(str(planned["round_id"]))
            self.assertEqual(status["assignments"][0]["terminalized_lease_marker"], "valid")

    def test_terminal_prepublication_failure_leaves_no_bundle_and_retries(
        self,
    ) -> None:
        """CHX-015: final rename follows complete staged sealing and validation."""

        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(
                Path(temporary) / "project",
                project_id="chx-015-prepublication-failure",
            )
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {"claim": "Publish only a fully sealed terminal bundle."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[source["research_id"]],
                host_task_scope_id="chx-015-prepublication-failure",
            )
            assignment = planned["assignments"][0]
            return_path = self._write_plain_assignment(store, planned, assignment)
            return_sha = sha256_bytes(return_path.read_bytes())
            round_dir = store.rounds_dir / str(planned["round_id"])
            assignment_id = str(assignment["assignment_id"])
            bundle_dir = round_dir / "terminal" / assignment_id
            receipt_path = (
                round_dir / "returns" / f"{assignment_id}.receipt.json"
            )
            research_count = len(lifecycle.research_records())
            real_replace = os.replace
            injected = False

            def fail_final_publish(source_path: object, destination: object) -> None:
                nonlocal injected
                source = Path(source_path)  # type: ignore[arg-type]
                target = Path(destination)  # type: ignore[arg-type]
                if (
                    not injected
                    and target == bundle_dir
                    and source.name.startswith(
                        f".terminal-{assignment_id}.staging-"
                    )
                ):
                    injected = True
                    raise OSError("injected terminal pre-publication failure")
                real_replace(source_path, destination)  # type: ignore[arg-type]

            with patch(
                "mathgraph.v5_lifecycle.os.replace",
                side_effect=fail_final_publish,
            ), self.assertRaisesRegex(
                OSError,
                "injected terminal pre-publication failure",
            ):
                lifecycle.ingest_return(
                    round_id=str(planned["round_id"]),
                    assignment_id=assignment_id,
                    worker_final_sha256=return_sha,
                )

            self.assertTrue(injected)
            self.assertFalse(bundle_dir.exists())
            self.assertFalse(receipt_path.exists())
            self.assertEqual(len(lifecycle.research_records()), research_count)
            self.assertEqual(
                list(
                    bundle_dir.parent.glob(
                        f".terminal-{assignment_id}.staging-*"
                    )
                ),
                [],
            )

            receipt = lifecycle.ingest_return(
                round_id=str(planned["round_id"]),
                assignment_id=assignment_id,
                worker_final_sha256=return_sha,
            )
            self.assertEqual(receipt["status"], "ingested")
            self.assertTrue(bundle_dir.is_dir())
            seal = lifecycle._validate_terminal_seal(
                round_dir=round_dir,
                assignment=assignment,
                required=True,
            )
            self.assertIsNotNone(seal)
            assert seal is not None
            self.assertEqual(seal["source_return_sha256"], return_sha)

    def test_terminal_seal_rejects_duplicate_artifact_source_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", project_id="chx-037-duplicate")
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {"claim": "Do not seal the same source artifact twice."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[source["research_id"]],
                host_task_scope_id="chx-037-duplicate-artifact",
            )
            assignment = planned["assignments"][0]
            self._write_plain_assignment(store, planned, assignment)
            snapshot = lifecycle._snapshot_return(
                round_id=str(planned["round_id"]),
                assignment_id=str(assignment["assignment_id"]),
            )
            duplicate = replace(
                snapshot,
                artifacts=(snapshot.artifacts[0], snapshot.artifacts[0]),
            )
            round_dir = store.rounds_dir / str(planned["round_id"])
            with self.assertRaisesRegex(ValueError, "duplicates a source artifact"):
                lifecycle._prepare_terminal_seal(
                    round_dir=round_dir,
                    assignment=assignment,
                    snapshot=duplicate,
                )
            self.assertFalse(
                (round_dir / "terminal" / str(assignment["assignment_id"])).exists()
            )

    def test_terminal_read_uses_stable_parent_descriptors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            parent = root / "parent"
            attacker = root / "attacker"
            parent.mkdir(parents=True)
            attacker.mkdir()
            target = parent / "target.txt"
            target.write_bytes(b"original")
            (attacker / "target.txt").write_bytes(b"attacker")
            real_open = os.open
            swapped = False

            def racing_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
                nonlocal swapped
                if path == "target.txt" and kwargs.get("dir_fd") is not None and not swapped:
                    swapped = True
                    parent.rename(root / "original-parent")
                    parent.symlink_to(attacker, target_is_directory=True)
                return real_open(path, flags, *args, **kwargs)  # type: ignore[arg-type]

            with patch("mathgraph.v5_lifecycle.os.open", side_effect=racing_open):
                from mathgraph.v5_lifecycle import V5LifecycleManager

                raw = V5LifecycleManager._read_regular_bytes_once(
                    target,
                    label="terminal parent race fixture",
                    containment_root=root,
                    require_single_link=True,
                )
            self.assertTrue(swapped)
            self.assertEqual(raw, b"original")

    def test_missing_terminal_seal_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", project_id="chx-037-missing")
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {"claim": "A prospective terminal seal is mandatory."},
                actor="main",
            )
            planned = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[source["research_id"]],
                host_task_scope_id="chx-037-missing-seal",
            )
            assignment = planned["assignments"][0]
            self._ingest_plain_assignment(store, planned, assignment)
            bundle = (
                store.rounds_dir
                / str(planned["round_id"])
                / "terminal"
                / str(assignment["assignment_id"])
            )
            os.chmod(bundle, bundle.stat().st_mode | 0o700)
            (bundle / "seal.json").unlink()
            with self.assertRaisesRegex(ValueError, "seal is missing"):
                lifecycle.round_status(str(planned["round_id"]))
            for current_root, directories, files in os.walk(
                bundle, topdown=False, followlinks=False
            ):
                for name in files:
                    path = Path(current_root) / name
                    os.chmod(path, path.stat().st_mode | 0o600)
                for name in directories:
                    path = Path(current_root) / name
                    os.chmod(path, path.stat().st_mode | 0o700)
                current = Path(current_root)
                os.chmod(current, current.stat().st_mode | 0o700)


if __name__ == "__main__":
    unittest.main()
