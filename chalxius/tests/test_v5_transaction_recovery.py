from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.contracts import sha256_bytes
from mathgraph.model import Fact
from mathgraph.paper_continuation_status import PaperContinuationStatusIndex
from mathgraph.store import MathGraphStore


class V5TransactionRecoveryTests(unittest.TestCase):
    def _store(self, root: Path, project_id: str) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id=project_id,
            title="V5 transaction recovery",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _file_inventory(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes())
            for path in sorted(root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }

    def _paper_continuation_recovery_fixture(
        self,
        root: Path,
        *,
        project_id: str,
    ) -> tuple[
        MathGraphStore,
        object,
        PaperContinuationStatusIndex,
        str,
        str,
        dict[str, object],
    ]:
        # Reuse the canonical frozen-Paper fixture builder without exposing the
        # imported TestCase class to unittest's module-level test discovery.
        from tests.test_v5_lifecycle import V5LifecycleTests

        fixture = V5LifecycleTests(
            "test_philosophy_paper_continuation_is_complete_atomic_and_current"
        )
        store = self._store(root, project_id)
        lifecycle = store.v5_lifecycle()
        artifact = root / "paper.txt"
        artifact.write_text(
            "The supporting lemma holds.\n"
            "The root theorem follows from the supporting lemma.\n",
            encoding="utf-8",
        )
        artifact_sha = sha256_bytes(artifact.read_bytes())
        source = {
            "artifact_sha256": artifact_sha,
            "artifact_locator": str(artifact),
            "title": "Transaction recovery fixture",
            "version": "test-v1",
            "mime_type": "text/plain",
            "retrieved_at": "2026-08-04T00:00:00Z",
            "inspection_methods": [
                "rendered_primary",
                "text_extraction_secondary",
            ],
        }
        with store.v5_mutation_lock(command="paper-logic-init"):
            store.paper_logic().initialize(actor="main")
        bundle = fixture._paper_logic_bundle(store=store, source=source)
        with store.v5_mutation_lock(command="paper-logic-freeze"):
            _, frozen = fixture._freeze_paper_bundle(
                store=store,
                bundle=bundle,
                artifact=artifact,
            )
        continuation = lifecycle.paper_continuation()
        plan_status = continuation.create_plan(
            frozen["snapshot_id"],
            {
                "selection_mode": "all_targets",
                "target_node_ids": [],
                "objective": "Exercise the exact status-index commit boundaries.",
                "source_artifact_sha256": artifact_sha,
            },
            actor="main",
        )
        binding = plan_status["target_research_bindings"][0]
        payload = {
            "kind": "proof_attempt",
            "claim": (
                "A managed result resolves the selected Paper continuation target."
            ),
            "relation": "extends",
            "related_research_ids": [binding["research_id"]],
            "worker_outcome": "insight",
        }
        status_index = lifecycle.paper_continuation()._status_index
        return (
            store,
            lifecycle,
            status_index,
            plan_status["plan_id"],
            binding["target_node_id"],
            payload,
        )

    @staticmethod
    def _release_payload(
        *,
        fact: Fact,
        research_id: str,
    ) -> dict[str, object]:
        return {
            "schema_version": 5,
            "bundle_claim": fact.statement,
            "candidates": [fact.as_submission_dict()],
            "research_entry_ids": [research_id],
            "claim_relation": "proves",
            "artifacts": [],
            "verification_plan": {
                "mode": "closed_capsule",
                "authorized_artifact_roles": [],
                "required_checks": [
                    "mathematical",
                    "typing",
                    "scope",
                    "source_and_applicability",
                    "predecessor_interfaces",
                    "computation_replay",
                    "challenge_dispositions",
                    "assurance_scope",
                ],
            },
            "requested_assurance": {
                "validation_subject": {
                    "kind": "theorem",
                    "subject_id": fact.fact_id,
                    "artifact_sha256": None,
                    "load_bearing_node_ids": [],
                },
                "validation_granularity": "monolithic_theorem",
                "coverage": [],
            },
            "challenge_dispositions": [],
            "paper_evidence_refs": [],
            "adverse_actor_ids": [],
        }

    @staticmethod
    def _correct_decision_payload(
        lifecycle: object,
        release: dict[str, object],
    ) -> dict[str, object]:
        capsule = lifecycle.verifier_capsule(release["release_id"])
        reviewer = "fresh-recovery-verifier"
        return {
            "schema_version": 5,
            "release_id": release["release_id"],
            "release_sha256": release["release_sha256"],
            "capsule_sha256": capsule["capsule_sha256"],
            "verdict": "correct",
            "findings": [],
            "check_results": [
                {"check_id": check_id, "status": "pass", "findings": []}
                for check_id in capsule["required_checks"]
            ],
            "candidate_checks": [
                {"fact_id": fact_id, "verdict": "correct", "findings": []}
                for fact_id in release["fact_ids"]
            ],
            "edge_checks": [
                {
                    "predecessor_fact_id": edge[0],
                    "fact_id": edge[1],
                    "verdict": "correct",
                    "findings": [],
                }
                for edge in release["internal_edges"]
            ],
            "assurance_matrix": lifecycle._expected_assurance_matrix(release),
            "reviewer": reviewer,
            "host_attestation": {
                "host": "test-host",
                "agent_id": reviewer,
                "isolation": "fresh_context",
                "fork_turns": "none",
                "allowed_capsule_sha256": capsule["capsule_sha256"],
            },
        }

    def _reject_decision_payload(
        self,
        lifecycle: object,
        release: dict[str, object],
    ) -> dict[str, object]:
        payload = copy.deepcopy(
            self._correct_decision_payload(lifecycle, release)
        )
        payload["verdict"] = "reject"
        payload["findings"] = [
            {
                "id": "finding-recovery-1",
                "severity": "critical_error",
                "class": "mathematical",
                "description": "The claimed derivation omits a required case.",
                "repair_hint": "Supply and independently verify the missing case.",
            }
        ]
        payload["check_results"][0] = {
            "check_id": payload["check_results"][0]["check_id"],
            "status": "fail",
            "findings": ["finding-recovery-1"],
        }
        return payload

    def test_research_retry_reconciles_interrupted_status_index_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(
                Path(temporary) / "v5",
                "v5-research-index-recovery",
            )
            lifecycle = store.v5_lifecycle()
            status_index = lifecycle.paper_continuation()._status_index
            status_index.rebuild()
            head_before = store._read_json(status_index.head_path)
            payload = {
                "kind": "proof_attempt",
                "claim": "The interrupted Research write is recoverable.",
            }

            with patch.object(
                PaperContinuationStatusIndex,
                "commit_research",
                side_effect=RuntimeError("injected status-index interruption"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "injected status-index interruption",
                ):
                    lifecycle.add_research(payload, actor="researcher")

            records = lifecycle.research_records()
            self.assertEqual(len(records), 1)
            research = records[0]
            with self.assertRaisesRegex(ValueError, "index is stale"):
                status_index._load_head(require_current=True)

            recovered = lifecycle.add_research(payload, actor="researcher")
            self.assertEqual(recovered, research)
            head_after = status_index._load_head(require_current=True)
            self.assertEqual(
                head_after["generation"],
                head_before["generation"] + 1,
            )
            lineage = status_index._load_lineage(research["research_id"])
            self.assertEqual(
                lineage["research_record_sha256"],
                research["record_sha256"],
            )

            stable_head = status_index.head_path.read_bytes()
            self.assertEqual(
                lifecycle.add_research(payload, actor="researcher"),
                research,
            )
            self.assertEqual(status_index.head_path.read_bytes(), stable_head)

    def test_research_status_commit_exact_interruption_checkpoints(self) -> None:
        checkpoints = (
            "after_lineage",
            "after_state",
            "after_receipt_before_head",
            "after_head_before_return",
        )
        for checkpoint in checkpoints:
            with self.subTest(checkpoint=checkpoint):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary) / "v5"
                    (
                        store,
                        lifecycle,
                        status_index,
                        plan_id,
                        target_id,
                        payload,
                    ) = self._paper_continuation_recovery_fixture(
                        root,
                        project_id=f"v5-status-index-{checkpoint}",
                    )
                    head_before = status_index._load_head(require_current=True)
                    head_before_bytes = status_index.head_path.read_bytes()
                    old_entry = dict(head_before["plan_heads"][plan_id])
                    old_state = status_index._load_state(
                        old_entry["state_sha256"]
                    )
                    self.assertNotIn(
                        target_id,
                        old_state["researched_target_node_ids"],
                    )
                    lineage_before = set(status_index.lineage_dir.glob("*.json"))
                    states_before = set(status_index.states_dir.glob("*.json"))
                    receipts_before = set(status_index.receipts_dir.glob("*.json"))

                    original_lineage = PaperContinuationStatusIndex._write_lineage
                    original_head = PaperContinuationStatusIndex._write_head
                    original_write_once = store._write_json_once
                    interrupted = False

                    def write_lineage_then_interrupt(
                        index: PaperContinuationStatusIndex,
                        record: dict[str, object],
                    ) -> None:
                        nonlocal interrupted
                        original_lineage(index, record)
                        if not interrupted:
                            interrupted = True
                            raise RuntimeError("injected after lineage")

                    def write_cas_then_interrupt(
                        path: Path,
                        value: object,
                    ) -> None:
                        nonlocal interrupted
                        original_write_once(path, value)
                        is_boundary = (
                            checkpoint == "after_state"
                            and path.parent == status_index.states_dir
                        ) or (
                            checkpoint == "after_receipt_before_head"
                            and path.parent == status_index.receipts_dir
                        )
                        if is_boundary and not interrupted:
                            interrupted = True
                            raise RuntimeError(f"injected {checkpoint}")

                    def write_head_then_interrupt(
                        index: PaperContinuationStatusIndex,
                        *,
                        base_head: dict[str, object] | None,
                        plan_heads: dict[str, dict[str, str]],
                        event: str,
                    ) -> dict[str, object]:
                        nonlocal interrupted
                        committed = original_head(
                            index,
                            base_head=base_head,
                            plan_heads=plan_heads,
                            event=event,
                        )
                        if not interrupted:
                            interrupted = True
                            raise RuntimeError("injected after HEAD before return")
                        return committed

                    if checkpoint == "after_lineage":
                        boundary_patch = patch.object(
                            PaperContinuationStatusIndex,
                            "_write_lineage",
                            new=write_lineage_then_interrupt,
                        )
                    elif checkpoint in {
                        "after_state",
                        "after_receipt_before_head",
                    }:
                        boundary_patch = patch.object(
                            store,
                            "_write_json_once",
                            new=write_cas_then_interrupt,
                        )
                    else:
                        boundary_patch = patch.object(
                            PaperContinuationStatusIndex,
                            "_write_head",
                            new=write_head_then_interrupt,
                        )

                    with boundary_patch:
                        with self.assertRaisesRegex(RuntimeError, "injected"):
                            lifecycle.add_research(payload, actor="paper-worker")
                    self.assertTrue(interrupted)
                    records = lifecycle.research_records()
                    result = next(
                        item
                        for item in records
                        if item["metadata"].get("worker_outcome") == "insight"
                    )
                    self.assertTrue(
                        status_index._lineage_path(result["research_id"]).is_file()
                    )

                    lineage_after = set(status_index.lineage_dir.glob("*.json"))
                    states_after = set(status_index.states_dir.glob("*.json"))
                    receipts_after = set(status_index.receipts_dir.glob("*.json"))
                    self.assertEqual(len(lineage_after - lineage_before), 1)
                    self.assertEqual(
                        len(states_after - states_before),
                        0 if checkpoint == "after_lineage" else 1,
                    )
                    self.assertEqual(
                        len(receipts_after - receipts_before),
                        1
                        if checkpoint
                        in {"after_receipt_before_head", "after_head_before_return"}
                        else 0,
                    )

                    after_interruption = self._file_inventory(root)
                    if checkpoint == "after_head_before_return":
                        self.assertNotEqual(
                            status_index.head_path.read_bytes(),
                            head_before_bytes,
                        )
                        committed_head = status_index._load_head(
                            require_current=True
                        )
                        committed_state = status_index._load_state(
                            committed_head["plan_heads"][plan_id]["state_sha256"]
                        )
                        self.assertIn(
                            target_id,
                            committed_state["researched_target_node_ids"],
                        )
                        self.assertEqual(
                            status_index.summary(plan_id)["counts"]["researched"],
                            1,
                        )
                    else:
                        self.assertEqual(
                            status_index.head_path.read_bytes(),
                            head_before_bytes,
                        )
                        selected_head = status_index._load_head(
                            require_current=False
                        )
                        self.assertEqual(
                            selected_head["plan_heads"][plan_id],
                            old_entry,
                        )
                        selected_state = status_index._load_state(
                            old_entry["state_sha256"]
                        )
                        self.assertNotIn(
                            target_id,
                            selected_state["researched_target_node_ids"],
                        )
                        with self.assertRaisesRegex(ValueError, "index is stale"):
                            status_index.summary(plan_id)
                    self.assertEqual(
                        self._file_inventory(root),
                        after_interruption,
                        "status reader must not repair an interrupted transaction",
                    )

                    recovered = lifecycle.add_research(
                        payload,
                        actor="paper-worker",
                    )
                    self.assertEqual(recovered, result)
                    head_after = status_index._load_head(require_current=True)
                    self.assertEqual(
                        head_after["generation"],
                        head_before["generation"] + 1,
                    )
                    recovered_state = status_index._load_state(
                        head_after["plan_heads"][plan_id]["state_sha256"]
                    )
                    self.assertIn(
                        target_id,
                        recovered_state["researched_target_node_ids"],
                    )
                    self.assertEqual(
                        status_index.summary(plan_id)["counts"]["researched"],
                        1,
                    )
                    stable_tree = self._file_inventory(root)
                    self.assertEqual(
                        lifecycle.add_research(payload, actor="paper-worker"),
                        result,
                    )
                    self.assertEqual(self._file_inventory(root), stable_tree)

    def test_reject_retry_recovers_intent_research_and_effect_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(
                Path(temporary) / "v5",
                "v5-certification-repair-recovery",
            )
            lifecycle = store.v5_lifecycle()
            source_research = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "A candidate claim."},
                actor="candidate-producer",
            )
            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The candidate claim holds.",
                proof="The submitted derivation is intentionally rejected.",
            )
            release = lifecycle.candidate_release(
                self._release_payload(
                    fact=fact,
                    research_id=source_research["research_id"],
                ),
                producer="candidate-producer",
            )
            payload = self._reject_decision_payload(lifecycle, release)
            preflight = lifecycle.certification_record(
                payload,
                preflight_only=True,
            )
            decision_id = preflight["decision_id"]
            intent_path = lifecycle._certification_repair_intent_path(
                decision_id
            )
            effect_path = lifecycle._certification_repair_effect_path(
                decision_id
            )
            decision_path = lifecycle._decision_path(decision_id)
            self.assertFalse(intent_path.exists())
            self.assertFalse(decision_path.exists())
            self.assertFalse(effect_path.exists())

            original_write_once = store._write_json_once

            def interrupt_decision_publish(
                path: Path,
                value: object,
            ) -> None:
                if path == decision_path:
                    raise RuntimeError("injected after durable repair intent")
                original_write_once(path, value)

            with patch.object(
                store,
                "_write_json_once",
                side_effect=interrupt_decision_publish,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "injected after durable repair intent",
                ):
                    lifecycle.certification_record(payload)

            self.assertTrue(intent_path.is_file())
            self.assertFalse(decision_path.exists())
            self.assertFalse(effect_path.exists())
            intent_only_audit = store.audit()
            self.assertTrue(intent_only_audit.current_ok, intent_only_audit.errors)
            self.assertTrue(
                any(
                    "no visible Decision" in warning
                    for warning in intent_only_audit.warnings
                )
            )
            self.assertFalse(decision_path.exists())

            with patch.object(
                lifecycle,
                "add_research",
                side_effect=RuntimeError("injected before repair Research"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "injected before repair Research",
                ):
                    lifecycle.certification_record(payload)

            self.assertTrue(intent_path.is_file())
            self.assertTrue(decision_path.is_file())
            self.assertFalse(effect_path.exists())
            self.assertEqual(len(lifecycle.research_records()), 1)
            interrupted_status = lifecycle.status()
            self.assertEqual(
                interrupted_status["next_safe_command"],
                "certification-record",
            )
            self.assertIn(
                "pending nontruth repair effect",
                interrupted_status["blocking_issue"],
            )
            self.assertFalse(effect_path.exists())

            # A read validates the canonical Decision but must not execute its
            # pending outbox effect.
            lifecycle.decision(decision_id)
            self.assertEqual(len(lifecycle.research_records()), 1)
            self.assertFalse(effect_path.exists())
            interrupted_audit = store.audit()
            self.assertTrue(interrupted_audit.current_ok, interrupted_audit.errors)
            self.assertTrue(
                any(
                    "pending repair effect" in warning
                    for warning in interrupted_audit.warnings
                )
            )
            self.assertFalse(effect_path.exists())

            with patch.object(
                lifecycle,
                "_write_certification_repair_effect",
                side_effect=RuntimeError("injected before effect receipt"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "injected before effect receipt",
                ):
                    lifecycle.certification_record(payload)

            repair_records = [
                item
                for item in lifecycle.research_records()
                if item["kind"] == "repair"
            ]
            self.assertEqual(len(repair_records), 1)
            self.assertEqual(
                repair_records[0]["metadata"]["decision_id"],
                decision_id,
            )
            self.assertFalse(effect_path.exists())

            lifecycle.decision(decision_id)
            self.assertFalse(effect_path.exists())
            decision = lifecycle.certification_record(payload)
            self.assertEqual(decision["decision_id"], decision_id)
            self.assertTrue(effect_path.is_file())
            receipt_bytes = effect_path.read_bytes()
            research_count = len(lifecycle.research_records())

            self.assertEqual(
                lifecycle.certification_record(payload)["decision_id"],
                decision_id,
            )
            self.assertEqual(len(lifecycle.research_records()), research_count)
            self.assertEqual(effect_path.read_bytes(), receipt_bytes)
            self.assertEqual(
                lifecycle.status()["next_safe_command"],
                "research-add",
            )
            report = store.audit()
            self.assertTrue(report.current_ok, report.errors)
            self.assertFalse(
                any(
                    "repair effect" in warning
                    for warning in report.warnings
                )
            )

    def test_projects_without_prospective_repair_directories_remain_compatible(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(
                Path(temporary) / "v5",
                "v5-pre-repair-protocol-compatibility",
            )
            lifecycle = store.v5_lifecycle()
            lifecycle.certification_repair_outbox_dir.rmdir()
            lifecycle.certification_repair_effects_dir.rmdir()
            research = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "A compatible claim."},
                actor="candidate-producer",
            )
            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The compatible claim holds.",
                proof="Direct proof of the compatible claim.",
            )
            release = lifecycle.candidate_release(
                self._release_payload(
                    fact=fact,
                    research_id=research["research_id"],
                ),
                producer="candidate-producer",
            )
            decision = lifecycle.certification_record(
                self._correct_decision_payload(lifecycle, release)
            )
            self.assertEqual(decision["verdict"], "correct")
            self.assertFalse(lifecycle.certification_repair_outbox_dir.exists())
            self.assertFalse(lifecycle.certification_repair_effects_dir.exists())
            report = store.audit()
            self.assertTrue(report.current_ok, report.errors)

    def test_legacy_reject_is_readable_and_upgraded_only_by_write_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(
                Path(temporary) / "v5",
                "v5-legacy-reject-compatibility",
            )
            lifecycle = store.v5_lifecycle()
            source_research = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "A legacy rejected claim."},
                actor="candidate-producer",
            )
            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The legacy rejected claim holds.",
                proof="The legacy derivation is incomplete.",
            )
            release = lifecycle.candidate_release(
                self._release_payload(
                    fact=fact,
                    research_id=source_research["research_id"],
                ),
                producer="candidate-producer",
            )
            payload = self._reject_decision_payload(lifecycle, release)
            decision = lifecycle.certification_record(payload)
            decision_id = decision["decision_id"]
            research_count = len(lifecycle.research_records())
            intent_path = lifecycle._certification_repair_intent_path(
                decision_id
            )
            effect_path = lifecycle._certification_repair_effect_path(
                decision_id
            )

            # Model a project created by the previous release: the rejection
            # and its repair Research exist, but the prospective outbox stores
            # do not.
            effect_path.unlink()
            intent_path.unlink()
            lifecycle.certification_repair_effects_dir.rmdir()
            lifecycle.certification_repair_outbox_dir.rmdir()

            self.assertEqual(
                lifecycle.decision(decision_id)["decision_id"],
                decision_id,
            )
            self.assertFalse(intent_path.exists())
            self.assertFalse(effect_path.exists())
            self.assertEqual(
                lifecycle.status()["next_safe_command"],
                "certification-record",
            )
            self.assertFalse(intent_path.exists())
            legacy_audit = store.audit()
            self.assertTrue(legacy_audit.current_ok, legacy_audit.errors)
            self.assertTrue(
                any(
                    "no durable repair intent" in warning
                    for warning in legacy_audit.warnings
                )
            )

            self.assertEqual(
                lifecycle.certification_record(payload)["decision_id"],
                decision_id,
            )
            self.assertTrue(intent_path.is_file())
            self.assertTrue(effect_path.is_file())
            self.assertEqual(len(lifecycle.research_records()), research_count)


if __name__ == "__main__":
    unittest.main()
