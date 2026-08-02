from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chx_ledger
from mathgraph.cli import (
    _authorized_fact_graph_append_target,
    _authorized_fact_graph_inventory,
)
from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.decision_preflight import (
    V5_FINDING_CLASSES,
    validate_decision_against_capsule,
)
from mathgraph.interfaces import (
    clause_is_conditional,
    referenced_premise_clause_tokens,
)
from mathgraph.model import Fact
from mathgraph.proof_lineage import statement_projection_sha256
from mathgraph.roles import allowed_commands
from mathgraph.runtime_archive import (
    archive_runtime,
    historical_archive_path,
    resolve_historical_runtime,
    runtime_binding_from_root,
    trusted_runtime_archive_root,
)
from mathgraph.store import MathGraphStore
from mathgraph.v5_assurance import V5_ASSURANCE_CONTRACT_REVISION
from mathgraph.v5_reader import _readable_fact_summary


class BTTFFieldRepairTests(unittest.TestCase):
    def _store(self, root: Path, project_id: str) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id=project_id,
            title="BTTF field repair fixture",
            workflow_evidence_version=5,
        )
        return store

    def test_reader_fact_summary_is_mathjax_ready_and_exact_fact_is_unchanged(self) -> None:
        statement = (
            "[CLAIM:MAIN]\n"
            "[HYP:H1] Let Sigma be compact.\n"
            "[HYP:H2] Use B for C=(Sigma,B,dx,dy) and "
            "C^vee=(Sigma,B,dy,dx).\n"
            "Then F_h(C)=F_h(C^vee) for every integer h>=2.\n"
            "[CLAIM:LIMITS] No assertion is made for h=0,1."
        )
        exact_before = statement.encode("utf-8")

        readable = _readable_fact_summary(statement)

        self.assertEqual(statement.encode("utf-8"), exact_before)
        self.assertNotIn("[CLAIM:", readable)
        self.assertNotIn("[HYP:", readable)
        self.assertIn("Claim MAIN.", readable)
        self.assertIn("Hypothesis H1.", readable)
        self.assertIn(r"\(\Sigma\)", readable)
        self.assertIn(r"\(C=(\Sigma,B,dx,dy)\)", readable)
        self.assertIn(r"\(C^{\vee}=(\Sigma,B,dy,dx)\)", readable)
        self.assertIn(r"\(F_h(C)=F_h(C^{\vee})\)", readable)
        self.assertIn(r"\(h\ge 2\)", readable)
        self.assertIn(r"\(h=0,1\)", readable)

    @staticmethod
    def _release_payload(
        facts: list[Fact],
        research_ids: list[str],
        *,
        granularity: str = "monolithic_theorem",
    ) -> dict[str, object]:
        return {
            "schema_version": 5,
            "bundle_claim": facts[-1].statement,
            "candidates": [fact.as_submission_dict() for fact in facts],
            "research_entry_ids": research_ids,
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
                    "subject_id": facts[-1].fact_id,
                    "artifact_sha256": None,
                    "load_bearing_node_ids": [],
                },
                "validation_granularity": granularity,
                "coverage": [],
            },
            "challenge_dispositions": [],
            "paper_evidence_refs": [],
            "adverse_actor_ids": [],
        }

    @staticmethod
    def _correct_decision(lifecycle: object, release: dict[str, object]) -> dict[str, object]:
        capsule = lifecycle.verifier_capsule(release["release_id"])
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
            "reviewer": "field-repair-verifier",
            "host_attestation": {
                "host": "field-repair-host",
                "agent_id": "field-repair-verifier",
                "isolation": "fresh_context",
                "fork_turns": "none",
                "allowed_capsule_sha256": capsule["capsule_sha256"],
            },
        }

    def _admit_release(
        self,
        lifecycle: object,
        release: dict[str, object],
        *,
        gateway: str = "field-repair-gateway",
    ) -> dict[str, object]:
        decision = lifecycle.certification_record(
            self._correct_decision(lifecycle, release)
        )
        return lifecycle.fact_admit(
            release_id=release["release_id"],
            decision_id=decision["decision_id"],
            gateway=gateway,
        )

    def _legacy_fact_release(
        self,
        store: MathGraphStore,
        facts: list[Fact],
        *,
        granularity: str = "monolithic_theorem",
    ) -> tuple[object, dict[str, object]]:
        lifecycle = store.v5_lifecycle()
        research = lifecycle.add_research(
            {"kind": "proof_attempt", "claim": facts[-1].statement},
            actor="field-repair-producer",
        )
        release = lifecycle.candidate_release(
            self._release_payload(
                facts,
                [research["research_id"]],
                granularity=granularity,
            ),
            producer="field-repair-producer",
        )
        return lifecycle, release

    @staticmethod
    def _current_task_bound_research(lifecycle: object, claim: str) -> dict[str, object]:
        return lifecycle.add_research(
            {
                "kind": "proof_attempt",
                "claim": claim,
                "obligation_dispositions": [],
                "computation_manifest": None,
                "research_assurance": {
                    "source_uses": [],
                    "route_invalidations": [],
                    "extremal_cases": [],
                    "claim_strength": [],
                    "contour_substitutions": [],
                    "claimed_structures": [],
                    "program_math_alignments": [],
                },
                "artifacts": [],
            },
            actor="field-repair-producer",
            task_binding={
                "round_id": "round-field-repair",
                "assignment_id": "assignment-field-repair",
                "task_card_sha256": "0" * 64,
                "blackboard_snapshot_sha256": "1" * 64,
                "return_sha256": "2" * 64,
            },
            assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
        )

    def test_chx006_pre_marker_failure_has_no_visibility_and_retry_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", "chx006-pre")
            fact = Fact(
                problem_id=store.project_id(),
                author="field-repair-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The pre-marker claim holds.",
                proof="Direct proof.",
            )
            lifecycle = store.v5_lifecycle()
            research = self._current_task_bound_research(
                lifecycle, fact.statement
            )
            release_payload = self._release_payload(
                [fact], [research["research_id"]]
            )
            release_payload["verification_plan"]["required_checks"].append(
                "research_obligation_evidence"
            )
            release = lifecycle.candidate_release(
                release_payload, producer="field-repair-producer"
            )
            decision = lifecycle.certification_record(
                self._correct_decision(lifecycle, release)
            )
            marker_path = lifecycle._admission_dir(release["release_id"]) / "ACCEPTED.json"
            with patch.object(
                lifecycle,
                "_preflight_admission_projections",
                side_effect=ValueError("injected pre-marker failure"),
            ):
                with self.assertRaisesRegex(ValueError, "pre-marker"):
                    lifecycle.fact_admit(
                        release_id=release["release_id"],
                        decision_id=decision["decision_id"],
                        gateway="field-repair-gateway",
                    )
            self.assertFalse(marker_path.exists())
            self.assertEqual(store.fact_ids(), [])
            marker = lifecycle.fact_admit(
                release_id=release["release_id"],
                decision_id=decision["decision_id"],
                gateway="field-repair-gateway",
            )
            self.assertEqual(marker["fact_ids"], [fact.fact_id])
            self.assertTrue(lifecycle.audit().current_ok)

    def test_chx006_post_marker_partial_retry_is_idempotent_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", "chx006-post")
            fact = Fact(
                problem_id=store.project_id(),
                author="field-repair-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The post-marker claim holds.",
                proof="Direct proof.",
            )
            lifecycle, release = self._legacy_fact_release(store, [fact])
            decision = lifecycle.certification_record(
                self._correct_decision(lifecycle, release)
            )
            with patch.object(
                lifecycle,
                "_materialize_admission_projections",
                side_effect=RuntimeError("injected post-marker failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "post-marker"):
                    lifecycle.fact_admit(
                        release_id=release["release_id"],
                        decision_id=decision["decision_id"],
                        gateway="field-repair-gateway",
                    )
            marker_path = lifecycle._admission_dir(release["release_id"]) / "ACCEPTED.json"
            self.assertTrue(marker_path.is_file())
            self.assertEqual(store.fact_ids(), [fact.fact_id])
            lifecycle.fact_admit(
                release_id=release["release_id"],
                decision_id=decision["decision_id"],
                gateway="field-repair-gateway",
            )
            lifecycle.fact_admit(
                release_id=release["release_id"],
                decision_id=decision["decision_id"],
                gateway="field-repair-gateway",
            )
            events = [
                event
                for event in store._read_jsonl(store.verification_log)
                if event.get("fact_id") == fact.fact_id
            ]
            self.assertEqual(len(events), 1)
            self.assertTrue((store.interfaces_dir / f"{fact.fact_id}.json").is_file())
            self.assertTrue(lifecycle.audit().current_ok)

    def test_chx006_nonempty_successor_contract_uses_nonrecursive_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", "chx006-successor")
            predecessor = Fact(
                problem_id=store.project_id(),
                author="field-repair-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The successor fixture holds.",
                proof="Byte-identical proof body.",
            )
            lifecycle, first_release = self._legacy_fact_release(store, [predecessor])
            self._admit_release(lifecycle, first_release, gateway="first-gateway")
            successor = Fact.from_dict(
                {
                    **predecessor.as_submission_dict(),
                    "fact_id": "",
                    "statement": "[CLAIM:ROOT] [HYP:H1] The successor fixture holds.",
                }
            )
            research = self._current_task_bound_research(
                lifecycle, successor.statement
            )
            payload = self._release_payload(
                [successor], [research["research_id"]]
            )
            payload["verification_plan"]["required_checks"].extend(
                ["research_obligation_evidence", "proof_lineage_conservation"]
            )
            payload["successor_contracts"] = [
                {
                    "mode": "interface_only_successor",
                    "predecessor_fact_id": predecessor.fact_id,
                    "successor_fact_id": successor.fact_id,
                    "predecessor_fact_sha256": sha256_bytes(
                        store.active_fact_path(predecessor.fact_id).read_bytes()
                    ),
                    "predecessor_proof_sha256": sha256_bytes(
                        predecessor.proof.encode("utf-8")
                    ),
                    "successor_proof_sha256": sha256_bytes(
                        successor.proof.encode("utf-8")
                    ),
                    "statement_projection": {
                        "mode": "remove_only_hypothesis_and_geometric_interface_anchors",
                        "predecessor_without_interface_sha256": statement_projection_sha256(
                            predecessor.statement
                        ),
                        "successor_without_interface_sha256": statement_projection_sha256(
                            successor.statement
                        ),
                    },
                    "proof_unit_conservation": [],
                }
            ]
            release = lifecycle.candidate_release(
                payload, producer="field-repair-producer"
            )
            self._admit_release(lifecycle, release, gateway="second-gateway")
            self.assertEqual(
                set(store.fact_ids()), {predecessor.fact_id, successor.fact_id}
            )
            self.assertEqual(
                lifecycle.release(release["release_id"])["successor_contracts"],
                release["successor_contracts"],
            )
            self.assertTrue(lifecycle.audit().current_ok)

    def test_chx005_named_legacy_setup_requires_exact_hashed_witness(self) -> None:
        self.assertTrue(clause_is_conditional("Under the fixed setup hypotheses, X."))
        self.assertIn(
            "SETUP",
            referenced_premise_clause_tokens(
                "Under the fixed setup hypotheses, X."
            ),
        )
        self.assertNotIn(
            "SETUP", referenced_premise_clause_tokens("Under the usual hypotheses, X.")
        )
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", "chx005")
            setup = Fact(
                problem_id=store.project_id(),
                author="legacy-producer",
                predecessors=[],
                statement="[CLAIM:SETUP] Let the ambient surface be P^1.",
                proof="Definitions and setup.",
            )
            setup_anchor = f"[USE:{setup.fact_id}:SETUP:legacy_setup]"
            main = Fact(
                problem_id=store.project_id(),
                author="legacy-producer",
                predecessors=[setup.fact_id],
                statement="[CLAIM:MAIN] Under the fixed setup hypotheses, R holds.",
                proof=f"{setup_anchor} Apply the exact P^1 setup.",
                predecessor_uses=[
                    {
                        "fact_id": setup.fact_id,
                        "clause_id": "SETUP",
                        "use_anchor": setup_anchor,
                        "used_conclusion": "The ambient surface is P^1.",
                        "hypothesis_witnesses": [],
                        "convention_bridge": None,
                    }
                ],
            )
            lifecycle, release = self._legacy_fact_release(
                store, [setup, main], granularity="atomic_fact_dag"
            )
            self._admit_release(lifecycle, release)
            interface = store.statement_interface(setup.fact_id, materialize=False)
            setup_clause = next(
                clause for clause in interface["clauses"] if clause["clause_id"] == "SETUP"
            )
            setup_sha = sha256_bytes(setup_clause["text"].encode("utf-8"))
            witness_id = (
                f"LEGACY-PREMISE:{setup.fact_id}:SETUP:{setup_sha}"
            )
            main_anchor = f"[USE:{main.fact_id}:MAIN:zero_genus_case]"

            def target(witnesses: list[dict[str, str]]) -> Fact:
                return Fact(
                    problem_id=store.project_id(),
                    author="current-producer",
                    predecessors=[main.fact_id],
                    statement=(
                        "[CLAIM:TARGET] [HYP:H1] Let the ambient surface be compact. "
                        "On an arbitrary compact ambient surface, "
                        "the zero-genus branch satisfies R."
                    ),
                    proof=(
                        f"{main_anchor} In the zero-genus branch the ambient surface "
                        "is the projective line, so every exact SETUP premise applies."
                    ),
                    predecessor_uses=[
                        {
                            "fact_id": main.fact_id,
                            "clause_id": "MAIN",
                            "use_anchor": main_anchor,
                            "used_conclusion": "R holds in the P^1 branch.",
                            "hypothesis_witnesses": witnesses,
                            "convention_bridge": None,
                            "conclusion_transport": [],
                        }
                    ],
                )

            plan = {
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
            }
            with self.assertRaisesRegex(ValueError, "hypothesis witnesses mismatch"):
                lifecycle._prepare_candidate_facts(
                    [target([]).as_submission_dict()],
                    artifacts=[],
                    authorized_artifact_hashes=set(),
                    verification_plan=plan,
                    assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
                )
            accepted = target(
                [
                    {
                        "hypothesis": witness_id,
                        "witness": "The proof anchor restricts to the exact P^1 SETUP.",
                        "proof_anchor": main_anchor,
                    }
                ]
            )
            prepared = lifecycle._prepare_candidate_facts(
                [accepted.as_submission_dict()],
                artifacts=[],
                authorized_artifact_hashes=set(),
                verification_plan=plan,
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            self.assertEqual(prepared[2], [accepted.fact_id])

    def test_chx001_current_source_capability_and_legacy_planning_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root, "chx001")
            lifecycle = store.v5_lifecycle()
            source = root / "inputs" / "paper.txt"
            source.parent.mkdir(parents=True)
            source.write_text("frozen source", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source-dependent"):
                lifecycle.add_research(
                    {
                        "kind": "direction",
                        "claim": "Use the exact paper source.",
                        "source_dependent": True,
                        "artifacts": [],
                    },
                    actor="main",
                    assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
                )
            current = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "Use the exact paper source.",
                    "source_dependent": True,
                    "artifacts": [
                        {
                            "path": "inputs/paper.txt",
                            "sha256": sha256_bytes(source.read_bytes()),
                            "role": "primary_source",
                        }
                    ],
                },
                actor="main",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            planned = lifecycle.create_round(
                workers=1, research_ids=[current["research_id"]]
            )
            card_path = Path(planned["assignments"][0]["task_card_path"])
            card = json.loads(card_path.read_text(encoding="utf-8"))
            self.assertEqual(
                card["mathematical_state"]["related_artifacts"][0]["sha256"],
                sha256_bytes(source.read_bytes()),
            )
            source.write_text("mutated source", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "drifted"):
                lifecycle.validate_task_card(card, expected_path=card_path)

            legacy_store = self._store(
                Path(temporary) / "legacy-project", "chx001-legacy"
            )
            legacy_lifecycle = legacy_store.v5_lifecycle()
            legacy = legacy_lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "Legacy path-only source.",
                    "source": "/Users/example/unbound-paper.pdf",
                },
                actor="main",
            )
            rounds_before = sorted(legacy_store.rounds_dir.iterdir())
            with self.assertRaisesRegex(ValueError, "source-dependent Research"):
                legacy_lifecycle.create_round(
                    workers=1, research_ids=[legacy["research_id"]]
                )
            self.assertEqual(
                sorted(legacy_store.rounds_dir.iterdir()), rounds_before
            )

    def test_chx003_evidence_return_from_refute_assignment_remains_adverse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", "chx003")
            lifecycle = store.v5_lifecycle()
            store.adverse_routes().initialize(actor="operator", reason="Field test.")
            source = lifecycle.add_research(
                {"kind": "direction", "claim": "Establish the candidate claim."},
                actor="main",
            )
            planned = lifecycle.create_round(
                workers=1,
                mode="refute",
                research_ids=[source["research_id"]],
            )
            assignment = planned["assignments"][0]
            card = json.loads(
                Path(assignment["task_card_path"]).read_text(encoding="utf-8")
            )
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
                "outcome": "evidence",
                "claim": "No counterexample was found in the bounded attack.",
                "content": "The tested boundary cases remain consistent.",
                "narrative": {
                    "rationale": "The adverse search was bounded.",
                    "summary": "No counterexample.",
                    "intuition": "The boundary survived.",
                    "limitations": "This is not a proof.",
                },
                "artifacts": [],
                "attack_learning": None,
                "obligation_dispositions": [],
                "computation_manifest": None,
                "research_assurance": {
                    "source_uses": [],
                    "route_invalidations": [],
                    "extremal_cases": [],
                    "claim_strength": [],
                    "contour_substitutions": [],
                    "claimed_structures": [],
                    "program_math_alignments": [],
                },
            }
            return_path = Path(assignment["return_path"])
            return_path.write_text(
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            return_sha = hashlib.sha256(return_path.read_bytes()).hexdigest()
            receipt = lifecycle.ingest_return(
                round_id=planned["round_id"],
                assignment_id=assignment["assignment_id"],
                worker_final_sha256=return_sha,
            )
            result = lifecycle._research_record(receipt["research_id"])
            self.assertEqual(result["kind"], "insight")
            self.assertTrue(result["metadata"]["assignment_provenance"]["adverse_assignment"])

            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The candidate claim holds.",
                proof="Direct proof independent of the adverse worker.",
            )
            release_payload = self._release_payload(
                [fact], [source["research_id"]]
            )
            release_payload["verification_plan"]["required_checks"].append(
                "research_obligation_evidence"
            )
            release_payload["challenge_dispositions"] = [
                {
                    "research_id": result["research_id"],
                    "disposition": "resolved_by_candidate",
                    "rationale": "The candidate proof covers the bounded adverse search.",
                }
            ]
            release_payload["adverse_actor_ids"] = [assignment["worker_id"]]
            release = lifecycle.candidate_release(
                release_payload, producer="candidate-producer"
            )
            bound = {item["research_id"] for item in release["research_bindings"]}
            self.assertIn(result["research_id"], bound)
            self.assertIn(assignment["worker_id"], release["excluded_verifier_ids"])
            self.assertEqual(store.adverse_routes().report(host_task_scope_id="test")["attacks"], [])

    def test_chx002_task_card_binds_candidate_runtime_and_ledger_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root, "chx002")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {"kind": "direction", "claim": "Runtime-bound worker task."},
                actor="main",
            )
            planned = lifecycle.create_round(
                workers=1, research_ids=[research["research_id"]]
            )
            card_path = Path(planned["assignments"][0]["task_card_path"])
            card = json.loads(card_path.read_text(encoding="utf-8"))
            candidate_root = Path(card["runtime_binding"]["skill_root"])
            self.assertEqual(card["runtime_binding"]["schema_version"], 2)
            self.assertRegex(
                card["runtime_binding"]["runtime_content_sha256"], r"^[0-9a-f]{64}$"
            )
            self.assertEqual(
                Path(card["runtime_binding"]["historical_archive_root"]),
                trusted_runtime_archive_root(runtime_skill_root=candidate_root)
                / "by-content"
                / card["runtime_binding"]["runtime_content_sha256"],
            )
            self.assertTrue((candidate_root / "scripts" / "chx_ledger.py").is_file())
            self.assertEqual(card["runtime_binding"]["skill_root"], str(candidate_root))
            current_version = (
                Path(__file__).resolve().parents[1] / "VERSION"
            ).read_text(encoding="utf-8").strip()
            self.assertEqual(card["runtime_binding"]["skill_version"], current_version)

            mismatch = copy.deepcopy(card["runtime_binding"])
            mismatch["skill_version"] = "0.4.3"
            with patch.object(chx_ledger, "_runtime_binding", return_value=mismatch):
                with self.assertRaisesRegex(ValueError, "does not match"):
                    chx_ledger.start_ledger(
                        project_root=root,
                        task="Mismatched worker runtime.",
                        run_id="run-runtime-mismatch-001",
                        task_card=card_path,
                    )
            self.assertFalse(
                (root / "chx-ledgers" / "run-runtime-mismatch-001.jsonl").exists()
            )
            started = chx_ledger.start_ledger(
                project_root=root,
                task="Matching worker runtime.",
                run_id="run-runtime-match-001",
                task_card=card_path,
            )
            self.assertEqual(started["skill_version"], current_version)

    def test_chx_worker_ledger_rehashes_the_task_card_runtime_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            runtime_root = base / "candidate" / "chalxius"
            runtime_root.mkdir(parents=True)
            version_path = runtime_root / "VERSION"
            payload_path = runtime_root / "runtime_payload.txt"
            manifest_path = runtime_root / "MANIFEST.sha256"
            version_path.write_text("0.6.1\n", encoding="utf-8")
            payload_path.write_text("worker runtime payload\n", encoding="utf-8")
            manifest_path.write_text(
                f"{sha256_bytes(version_path.read_bytes())}  VERSION\n"
                f"{sha256_bytes(payload_path.read_bytes())}  runtime_payload.txt\n",
                encoding="utf-8",
            )
            binding = runtime_binding_from_root(runtime_root)
            semantic = {"runtime_binding": binding}
            card = {
                **semantic,
                "task_card_semantic_sha256": sha256_json(semantic),
            }
            card_path = base / "task-card.json"
            card_path.write_text(
                json.dumps(card, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            payload_path.write_text("worker runtime drifted\n", encoding="utf-8")
            project_root = base / "worker-project"
            with patch.object(chx_ledger, "_skill_root", return_value=runtime_root):
                with self.assertRaisesRegex(ValueError, "manifest entry drifted"):
                    chx_ledger.start_ledger(
                        project_root=project_root,
                        task="Reject a drifted worker runtime.",
                        run_id="run-runtime-tree-drift-001",
                        task_card=card_path,
                    )
            self.assertFalse(project_root.exists())

    def test_round_runtime_preflight_fails_before_any_project_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            root = base / "project"
            store = self._store(root, "runtime-preflight-atomicity")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "Preflight the runtime before freezing a round.",
                },
                actor="main",
            )
            runtime_root = base / "candidate" / "chalxius"
            runtime_root.mkdir(parents=True)
            version_path = runtime_root / "VERSION"
            payload_path = runtime_root / "runtime_payload.txt"
            manifest_path = runtime_root / "MANIFEST.sha256"
            version_path.write_text("0.6.1\n", encoding="utf-8")
            payload_path.write_text("planner runtime payload\n", encoding="utf-8")
            manifest_path.write_text(
                f"{sha256_bytes(version_path.read_bytes())}  VERSION\n"
                f"{sha256_bytes(payload_path.read_bytes())}  runtime_payload.txt\n",
                encoding="utf-8",
            )
            binding = runtime_binding_from_root(runtime_root)
            payload_path.write_text("planner runtime drifted\n", encoding="utf-8")
            before = {
                path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes())
                for path in root.rglob("*")
                if path.is_file()
            }
            with patch.object(lifecycle, "_runtime_binding", return_value=binding):
                with self.assertRaisesRegex(ValueError, "manifest entry drifted"):
                    lifecycle.create_round(
                        workers=1,
                        research_ids=[research["research_id"]],
                    )
            self.assertEqual(
                before,
                {
                    path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes())
                    for path in root.rglob("*")
                    if path.is_file()
                },
            )

    def test_runtime_binding_is_scanned_once_per_bounded_round_phase(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "project"
            store = self._store(root, "runtime-validation-dedup")
            lifecycle = store.v5_lifecycle()
            research_ids = [
                lifecycle.add_research(
                    {
                        "kind": "direction",
                        "claim": f"Runtime validation branch {index}.",
                    },
                    actor="main",
                )["research_id"]
                for index in range(2)
            ]
            with patch.object(
                lifecycle,
                "_validate_bound_runtime_binding",
                wraps=lifecycle._validate_bound_runtime_binding,
            ) as validator:
                lifecycle.create_round(workers=2, research_ids=research_ids)
            self.assertEqual(
                validator.call_count,
                2,
                "creation and returned status may each scan one unique runtime once",
            )

    def test_chx004_inventory_and_append_target_are_explicit_read_only_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source_store = self._store(base / "source", "source-project")
            fact = Fact(
                problem_id=source_store.project_id(),
                author="source-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The source theorem holds.",
                proof="Source proof.",
            )
            source_lifecycle, release = self._legacy_fact_release(source_store, [fact])
            self._admit_release(source_lifecycle, release)
            current_store = self._store(base / "current", "different-project")
            for command in ("fact-graph-inventory", "fact-graph-append-target"):
                self.assertIn(command, allowed_commands("operator"))
                for role in ("main", "worker", "gateway", "verifier", "host"):
                    self.assertNotIn(command, allowed_commands(role))
            current_before = sorted(
                path.relative_to(current_store.root).as_posix()
                for path in current_store.root.rglob("*")
            )
            inventory = _authorized_fact_graph_inventory(
                current_store, str(source_store.root)
            )
            self.assertEqual(
                inventory["project_id_compatibility"],
                "different_project_no_fact_authority_transfer",
            )
            self.assertEqual(
                [item["fact_id"] for item in inventory["active_facts"]],
                [fact.fact_id],
            )
            self.assertFalse(inventory["automatic_inheritance"])
            self.assertFalse(inventory["federation"])
            with self.assertRaisesRegex(ValueError, "expected project id"):
                _authorized_fact_graph_append_target(
                    current_store,
                    source_root=str(source_store.root),
                    expected_project_id="wrong-project",
                )
            selection = _authorized_fact_graph_append_target(
                current_store,
                source_root=str(source_store.root),
                expected_project_id=source_store.project_id(),
            )
            self.assertEqual(selection["append_target_root"], str(source_store.root))
            self.assertTrue(selection["current_root_unchanged"])
            self.assertFalse(selection["cross_project_fact_import"])
            current_after = sorted(
                path.relative_to(current_store.root).as_posix()
                for path in current_store.root.rglob("*")
            )
            self.assertEqual(current_after, current_before)

    def test_aborted_v5_round_status_is_frozen_and_audit_checks_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root, "abort-status-projection")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "Freeze this work unit before any worker return.",
                },
                actor="main",
            )
            second_research = lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "Independently challenge the same frozen work unit.",
                },
                actor="main",
            )
            planned = lifecycle.create_round(
                workers=2,
                research_ids=[
                    research["research_id"],
                    second_research["research_id"],
                ],
            )
            with store.v5_mutation_lock(command="work-unit-abort"):
                abort = store.reasoning_modes().abort_work_unit(
                    round_id=planned["round_id"],
                    actor="main",
                    reason="Exercise the abort status projection.",
                )

            status = lifecycle.round_status(planned["round_id"])
            self.assertEqual(status["work_unit_state"], "aborted")
            self.assertEqual(status["abort_id"], abort["abort_id"])
            self.assertEqual(status["work_unit_abort"], abort)
            self.assertEqual(status["awaiting_count"], 0)
            self.assertEqual(status["frozen_aborted_count"], 2)
            self.assertEqual(
                {assignment["state"] for assignment in status["assignments"]},
                {"frozen_aborted"},
            )
            readiness = lifecycle.process_readiness_status(planned["round_id"])
            self.assertEqual(readiness["advisory_state"], "work_unit_aborted")
            self.assertEqual(readiness["recommended_actions"], [])
            self.assertEqual(readiness["assignment_summary"]["awaiting"], 0)
            self.assertEqual(readiness["assignment_summary"]["frozen_aborted"], 2)
            self.assertTrue(lifecycle.audit().current_ok)

            real_round_status = lifecycle.round_status

            def stale_round_status(round_id: str) -> dict[str, object]:
                stale = copy.deepcopy(real_round_status(round_id))
                stale["work_unit_state"] = "active"
                stale["abort_id"] = None
                stale["work_unit_abort"] = None
                stale["awaiting_count"] = len(stale["assignments"])
                stale["frozen_aborted_count"] = 0
                for assignment in stale["assignments"]:
                    assignment["state"] = "awaiting_return"
                return stale

            with patch.object(
                lifecycle,
                "round_status",
                side_effect=stale_round_status,
            ):
                stale_audit = lifecycle.audit()
            self.assertFalse(stale_audit.current_ok)
            self.assertTrue(
                any(
                    "work-unit abort/status projection mismatch" in error
                    for error in stale_audit.errors
                )
            )

    def test_chx001_aborted_round_uses_exact_bound_runtime_not_current_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            self.enterContext(
                patch.dict(
                    os.environ,
                    {"CHALXIUS_RUNTIME_ARCHIVE_ROOT": str(base / "host-archive")},
                )
            )
            store = self._store(base / "project", "historical-runtime")
            lifecycle = store.v5_lifecycle()
            bound_root = base / "bound-chalxius-0.4.4"
            bound_root.mkdir()
            version_path = bound_root / "VERSION"
            manifest_path = bound_root / "MANIFEST.sha256"
            version_path.write_text("0.4.4\n", encoding="utf-8")
            payload_path = bound_root / "runtime_payload.txt"
            payload_path.write_text("historical runtime payload\n", encoding="utf-8")
            manifest_path.write_text(
                f"{sha256_bytes(version_path.read_bytes())}  VERSION\n"
                f"{sha256_bytes(payload_path.read_bytes())}  runtime_payload.txt\n",
                encoding="utf-8",
            )
            semantic = {
                "schema_version": 1,
                "skill_root": str(bound_root),
                "skill_version": "0.4.4",
                "version_file_sha256": sha256_bytes(version_path.read_bytes()),
                "manifest_file_sha256": sha256_bytes(manifest_path.read_bytes()),
                "worker_ledger_contract": "exact_task_card_runtime_binding_required",
            }
            bound_runtime = {
                **semantic,
                "runtime_identity_sha256": sha256_json(semantic),
            }
            research = lifecycle.add_research(
                {"kind": "direction", "claim": "Freeze a historical runtime task."},
                actor="main",
            )
            with patch.object(lifecycle, "_runtime_binding", return_value=bound_runtime):
                planned = lifecycle.create_round(
                    workers=1,
                    research_ids=[research["research_id"]],
                )

            with self.assertRaisesRegex(ValueError, "runtime binding drifted"):
                lifecycle.round_status(planned["round_id"])
            with store.v5_mutation_lock(command="work-unit-abort"):
                store.reasoning_modes().abort_work_unit(
                    round_id=planned["round_id"],
                    actor="main",
                    reason="Freeze before inspecting with a newer runtime.",
                )
            status = lifecycle.round_status(planned["round_id"])
            self.assertEqual(status["work_unit_state"], "aborted")
            self.assertEqual(status["frozen_aborted_count"], 1)
            self.assertTrue(lifecycle.audit().current_ok)

            version_path.write_text("0.4.4-corrupted\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "bound Chalxius runtime identity drifted"):
                lifecycle.round_status(planned["round_id"])

            version_path.write_text("0.4.4\n", encoding="utf-8")
            archived = archive_runtime(bound_root, bound_runtime)
            self.assertTrue(archived["created"])
            self.assertEqual(
                Path(archived["archive_path"]), historical_archive_path(bound_runtime)
            )
            version_path.write_text("0.6.1\n", encoding="utf-8")
            recovered = lifecycle.round_status(planned["round_id"])
            self.assertEqual(recovered["work_unit_state"], "aborted")

            archived_payload = historical_archive_path(bound_runtime) / "runtime_payload.txt"
            archived_payload.chmod(0o600)
            archived_payload.write_text("tampered archive\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no valid content-addressed"):
                lifecycle.round_status(planned["round_id"])

    def test_active_round_never_uses_historical_runtime_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            self.enterContext(
                patch.dict(
                    os.environ,
                    {"CHALXIUS_RUNTIME_ARCHIVE_ROOT": str(base / "host-archive")},
                )
            )
            store = self._store(base / "project", "active-runtime-archive-block")
            lifecycle = store.v5_lifecycle()
            bound_root = base / "bound-chalxius-active"
            bound_root.mkdir()
            version_path = bound_root / "VERSION"
            payload_path = bound_root / "runtime_payload.txt"
            manifest_path = bound_root / "MANIFEST.sha256"
            version_path.write_text("0.6.0\n", encoding="utf-8")
            payload_path.write_text("active runtime payload\n", encoding="utf-8")
            manifest_path.write_text(
                f"{sha256_bytes(version_path.read_bytes())}  VERSION\n"
                f"{sha256_bytes(payload_path.read_bytes())}  runtime_payload.txt\n",
                encoding="utf-8",
            )
            semantic = {
                "schema_version": 1,
                "skill_root": str(bound_root),
                "skill_version": "0.6.0",
                "version_file_sha256": sha256_bytes(version_path.read_bytes()),
                "manifest_file_sha256": sha256_bytes(manifest_path.read_bytes()),
                "worker_ledger_contract": "exact_task_card_runtime_binding_required",
            }
            bound_runtime = {
                **semantic,
                "runtime_identity_sha256": sha256_json(semantic),
            }
            source = lifecycle.add_research(
                {"kind": "direction", "claim": "Keep this work unit active."},
                actor="main",
            )
            with patch.object(lifecycle, "_runtime_binding", return_value=bound_runtime):
                planned = lifecycle.create_round(
                    workers=1,
                    research_ids=[source["research_id"]],
                )
            archive_runtime(bound_root, bound_runtime)
            payload_path.write_text("active runtime payload drifted\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "manifest entry drifted"):
                lifecycle.round_status(planned["round_id"])
            payload_path.write_text("active runtime payload\n", encoding="utf-8")
            version_path.write_text("0.6.1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "runtime identity drifted"):
                lifecycle.round_status(planned["round_id"])

    def test_schema2_runtime_archive_is_content_addressed_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            self.enterContext(
                patch.dict(
                    os.environ,
                    {"CHALXIUS_RUNTIME_ARCHIVE_ROOT": str(base / "host-archive")},
                )
            )
            runtime_root = base / "skills" / "chalxius"
            runtime_root.mkdir(parents=True)
            version_path = runtime_root / "VERSION"
            payload_path = runtime_root / "runtime_payload.txt"
            manifest_path = runtime_root / "MANIFEST.sha256"
            version_path.write_text("0.6.1\n", encoding="utf-8")
            payload_path.write_text("schema2 runtime payload\n", encoding="utf-8")
            manifest_path.write_text(
                f"{sha256_bytes(version_path.read_bytes())}  VERSION\n"
                f"{sha256_bytes(payload_path.read_bytes())}  runtime_payload.txt\n",
                encoding="utf-8",
            )
            binding = runtime_binding_from_root(runtime_root)
            self.assertEqual(binding["schema_version"], 2)
            first = archive_runtime(runtime_root, binding)
            second = archive_runtime(runtime_root, binding)
            self.assertTrue(first["created"])
            self.assertFalse(second["created"])
            self.assertEqual(first["archive_path"], binding["historical_archive_root"])

            version_path.write_text("0.6.2\n", encoding="utf-8")
            resolved = resolve_historical_runtime(binding)
            self.assertEqual(
                resolved["resolution"], "content_addressed_historical_archive"
            )
            extra = Path(binding["historical_archive_root"]) / "unexpected.txt"
            extra.parent.chmod(0o700)
            extra.write_text("unexpected\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no valid content-addressed"):
                resolve_historical_runtime(binding)

    def test_completed_round_uses_valid_receipts_as_historical_runtime_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            self.enterContext(
                patch.dict(
                    os.environ,
                    {"CHALXIUS_RUNTIME_ARCHIVE_ROOT": str(base / "host-archive")},
                )
            )
            store = self._store(base / "project", "completed-historical-runtime")
            lifecycle = store.v5_lifecycle()
            bound_root = base / "bound-chalxius-0.4.4"
            bound_root.mkdir()
            version_path = bound_root / "VERSION"
            manifest_path = bound_root / "MANIFEST.sha256"
            version_path.write_text("0.4.4\n", encoding="utf-8")
            payload_path = bound_root / "runtime_payload.txt"
            payload_path.write_text("completed runtime payload\n", encoding="utf-8")
            manifest_path.write_text(
                f"{sha256_bytes(version_path.read_bytes())}  VERSION\n"
                f"{sha256_bytes(payload_path.read_bytes())}  runtime_payload.txt\n",
                encoding="utf-8",
            )
            semantic = {
                "schema_version": 1,
                "skill_root": str(bound_root),
                "skill_version": "0.4.4",
                "version_file_sha256": sha256_bytes(version_path.read_bytes()),
                "manifest_file_sha256": sha256_bytes(manifest_path.read_bytes()),
                "worker_ledger_contract": "exact_task_card_runtime_binding_required",
            }
            bound_runtime = {
                **semantic,
                "runtime_identity_sha256": sha256_json(semantic),
            }
            source = lifecycle.add_research(
                {"kind": "direction", "claim": "Attack the historical fixture."},
                actor="main",
            )
            with patch.object(lifecycle, "_runtime_binding", return_value=bound_runtime):
                planned = lifecycle.create_round(
                    workers=1,
                    mode="refute",
                    research_ids=[source["research_id"]],
                )
                assignment = planned["assignments"][0]
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
                    "outcome": "evidence",
                    "claim": "The bounded historical attack found no counterexample.",
                    "content": "The checked boundary cases survived.",
                    "narrative": {
                        "rationale": "Exercise the completed-round boundary.",
                        "summary": "No counterexample.",
                        "intuition": "The historical result remains useful.",
                        "limitations": "This bounded check is not a proof.",
                    },
                    "artifacts": [],
                    "attack_learning": None,
                    "obligation_dispositions": [],
                    "computation_manifest": None,
                    "research_assurance": {
                        "source_uses": [],
                        "route_invalidations": [],
                        "extremal_cases": [],
                        "claim_strength": [],
                        "contour_substitutions": [],
                        "claimed_structures": [],
                        "program_math_alignments": [],
                    },
                }
                return_path = Path(assignment["return_path"])
                return_path.write_text(
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    encoding="utf-8",
                )
                receipt = lifecycle.ingest_return(
                    round_id=planned["round_id"],
                    assignment_id=assignment["assignment_id"],
                    worker_final_sha256=sha256_bytes(return_path.read_bytes()),
                )
                self.assertEqual(receipt["status"], "ingested")

            status = lifecycle.round_status(planned["round_id"])
            self.assertEqual(status["work_unit_state"], "completed")
            self.assertEqual(status["ingested_count"], 1)
            self.assertTrue(lifecycle.audit().current_ok)
            self.assertTrue(store.experiments().audit_all()["ok"])

            receipt_path = (
                store.rounds_dir
                / planned["round_id"]
                / "returns"
                / f"{assignment['assignment_id']}.receipt.json"
            )
            original_receipt = receipt_path.read_text(encoding="utf-8")
            tampered = json.loads(original_receipt)
            tampered["return_sha256"] = "0" * 64
            receipt_path.write_text(
                json.dumps(tampered, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "return bytes/hash mismatch"):
                lifecycle.round_status(planned["round_id"])
            receipt_path.write_text(original_receipt, encoding="utf-8")

            version_path.write_text("0.4.4-corrupted\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "bound Chalxius runtime identity drifted"):
                lifecycle.round_status(planned["round_id"])

            version_path.write_text("0.4.4\n", encoding="utf-8")
            archive_runtime(bound_root, bound_runtime)
            version_path.write_text("0.6.1\n", encoding="utf-8")
            recovered = lifecycle.round_status(planned["round_id"])
            self.assertEqual(recovered["work_unit_state"], "completed")
            self.assertEqual(recovered["ingested_count"], 1)

    def test_chx002_local_and_gateway_decision_validators_share_finding_classes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", "finding-classes")
            fact = Fact(
                problem_id=store.project_id(),
                author="field-repair-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The finding-class fixture holds.",
                proof="Direct proof.",
            )
            lifecycle, release = self._legacy_fact_release(store, [fact])
            capsule = lifecycle.verifier_capsule(release["release_id"])
            for finding_class in V5_FINDING_CLASSES:
                decision = self._correct_decision(lifecycle, release)
                finding_id = f"finding-{finding_class}"
                decision["verdict"] = "reject"
                decision["findings"] = [
                    {
                        "id": finding_id,
                        "severity": "gap",
                        "class": finding_class,
                        "description": "One bounded verifier finding.",
                        "repair_hint": "Repair and seal a new Candidate Release.",
                    }
                ]
                decision["check_results"][0] = {
                    **decision["check_results"][0],
                    "status": "fail",
                    "findings": [finding_id],
                }
                self.assertTrue(
                    validate_decision_against_capsule(decision, capsule)["valid"]
                )
                self.assertTrue(
                    lifecycle.certification_record(
                        decision, preflight_only=True
                    )["valid"]
                )

            invalid = self._correct_decision(lifecycle, release)
            invalid["verdict"] = "reject"
            invalid["findings"] = [
                {
                    "id": "finding-unknown",
                    "severity": "gap",
                    "class": "source_transcription_coverage",
                    "description": "This class is outside the shared enum.",
                    "repair_hint": "Use one permitted class.",
                }
            ]
            invalid["check_results"][0] = {
                **invalid["check_results"][0],
                "status": "fail",
                "findings": ["finding-unknown"],
            }
            with self.assertRaisesRegex(ValueError, "/findings/0/class is invalid"):
                validate_decision_against_capsule(invalid, capsule)
            with self.assertRaisesRegex(ValueError, r"finding\[1\] class is invalid"):
                lifecycle.certification_record(invalid, preflight_only=True)

    def test_chx003_later_admission_cannot_rewrite_older_rejected_release_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", "sealed-lineage-time")
            lifecycle = store.v5_lifecycle()
            older_fact = Fact(
                problem_id=store.project_id(),
                author="older-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The chronological lineage claim holds.",
                proof="An older candidate argument.",
            )
            older_research = self._current_task_bound_research(
                lifecycle, older_fact.statement
            )
            older_payload = self._release_payload(
                [older_fact], [older_research["research_id"]]
            )
            older_payload["verification_plan"]["required_checks"].append(
                "research_obligation_evidence"
            )
            older_release = lifecycle.candidate_release(
                older_payload,
                producer="older-producer",
            )
            rejection = self._correct_decision(lifecycle, older_release)
            rejection["verdict"] = "reject"
            rejection["findings"] = [
                {
                    "id": "gap-old-route",
                    "severity": "gap",
                    "class": "mathematical",
                    "description": "The older proof route is incomplete.",
                    "repair_hint": "Use an independent repaired route.",
                }
            ]
            rejection["check_results"][0] = {
                **rejection["check_results"][0],
                "status": "fail",
                "findings": ["gap-old-route"],
            }
            lifecycle.certification_record(rejection)

            repaired_fact = Fact(
                problem_id=store.project_id(),
                author="new-producer",
                predecessors=[],
                statement=(
                    "[CLAIM:ROOT] [HYP:H1] The chronological lineage claim holds."
                ),
                proof="A fresh independent proof under H1.",
            )
            repaired_research = self._current_task_bound_research(
                lifecycle, repaired_fact.statement
            )
            repaired_payload = self._release_payload(
                [repaired_fact], [repaired_research["research_id"]]
            )
            repaired_payload["verification_plan"]["required_checks"].append(
                "research_obligation_evidence"
            )
            repaired_release = lifecycle.candidate_release(
                repaired_payload,
                producer="new-producer",
            )
            self._admit_release(
                lifecycle,
                repaired_release,
                gateway="chronology-gateway",
            )

            self.assertEqual(
                lifecycle.release(older_release["release_id"])["successor_contracts"],
                [],
            )
            self.assertIn(repaired_fact.fact_id, store.fact_ids())
            self.assertTrue(lifecycle.audit().current_ok)


if __name__ == "__main__":
    unittest.main()
