from __future__ import annotations

import json
import hashlib
import copy
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mathgraph.cli import main as cli_main
from mathgraph.blackboard import make_node
from mathgraph.computations import INDEPENDENCE_AXES
from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.model import Fact
from mathgraph.paper_logic import PaperLogicStore
from mathgraph.paper_continuation import (
    PAPER_CONTINUATION_CONTRACT_REVISION,
    PHILOSOPHY_ATOMICITY_CONTRACT_REVISION,
    PaperContinuationManager,
)
from mathgraph.paper_logic_contracts import (
    PAPER_LOGIC_FEATURE_REVISION,
    REVIEW_GLOBAL_CHECKS,
    scan_high_risk_operators,
)
from mathgraph.reader_html import render_reader_html
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import (
    V5_LIFECYCLE_CONTRACT_SHA256,
    V5_POLICY_REVISION,
    V5_TASK_CONTEXT_REVISION,
    V5LifecycleManager,
)
from mathgraph.v5_reader import build_v5_reader_packet


def _operator_ledger(text: str) -> list[dict[str, object]]:
    return [
        {
            "operator_id": f"op-{index}",
            "token": item["token"],
            "occurrence": item["occurrence"],
            "kind": item["kind"],
            "scope": "surface scope checked against the rendered source",
            "disposition": "logical",
            "depends_on": [],
        }
        for index, item in enumerate(scan_high_risk_operators(text))
    ]


class V5LifecycleTests(unittest.TestCase):
    def _store(self, root: Path, project_id: str = "v5-research") -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id=project_id,
            title="V5 research",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _paper_source_unit(local_id: str, text: str, order: int) -> dict[str, object]:
        return {
            "local_id": local_id,
            "object_type": "source_unit",
            "payload": {
                "unit_kind": "sentence",
                "order": order,
                "locator": {
                    "kind": "pdf",
                    "pdf_page_index": 0,
                    "printed_page_label": "1",
                    "region": f"sentence-{order}",
                },
                "text": text,
                "text_sha256": sha256_bytes(text.encode("utf-8")),
                "speaker": "author",
                "inspection_methods": [
                    "rendered_primary",
                    "text_extraction_secondary",
                ],
                "render_sha256": sha256_bytes(f"render-{order}".encode("utf-8")),
                "context_before": "",
                "context_after": "",
                "operator_ledger": _operator_ledger(text),
            },
        }

    @staticmethod
    def _paper_claim(
        local_id: str,
        statement: str,
        *,
        source_unit_id: str = "",
        role: str = "premise",
    ) -> dict[str, object]:
        literal = bool(source_unit_id)
        return {
            "local_id": local_id,
            "object_type": "claim",
            "payload": {
                "representation_kind": (
                    "source_literal" if literal else "researcher_reconstruction"
                ),
                "attribution": "author" if literal else "researcher",
                "discourse_role": role,
                "content_type": "conceptual",
                "statement": statement,
                "statement_sha256": sha256_bytes(statement.encode("utf-8")),
                "source_unit_ids": [source_unit_id] if literal else [],
                "semantic_diff": (
                    ""
                    if literal
                    else (
                        "This explicit synthesis is the graph builder's "
                        "reconstruction, not a source quotation."
                    )
                ),
                "modality": "asserted",
                "scope_notes": "Scope is limited to this fixture argument.",
                "operator_ledger": _operator_ledger(statement),
                "definition_ids": [],
                "parent_claim_id": "",
            },
        }

    def _paper_logic_bundle(
        self,
        *,
        store: MathGraphStore,
        source: dict[str, object],
    ) -> dict[str, object]:
        sentences = [
            "The supporting lemma holds.",
            "The root theorem follows from the supporting lemma.",
        ]
        nodes: list[dict[str, object]] = []
        coverage_units: list[dict[str, object]] = []
        premise_ids: list[str] = []
        for index, sentence in enumerate(sentences, 1):
            source_id = f"s{index}"
            claim_id = f"c{index}"
            nodes.append(self._paper_source_unit(source_id, sentence, index))
            nodes.append(
                self._paper_claim(
                    claim_id,
                    sentence,
                    source_unit_id=source_id,
                )
            )
            premise_ids.append(claim_id)
            coverage_units.append(
                {
                    "unit_id": source_id,
                    "classification": "argumentative",
                    "mapped_node_ids": [source_id, claim_id, "i-head"],
                    "reason": "",
                }
            )
        nodes.extend(
            [
                self._paper_claim(
                    "c-head",
                    "The bounded paper theorem holds.",
                    role="headline_conclusion",
                ),
                {
                    "local_id": "i-head",
                    "object_type": "inference",
                    "payload": {
                        "premise_ids": premise_ids,
                        "conclusion_id": "c-head",
                        "inference_kind": "deductive",
                        "strength": "strict",
                        "authorial_status": "researcher_reconstructed",
                        "source_unit_ids": ["s1", "s2"],
                        "bridge_claim_ids": [],
                        "defeater_claim_ids": [],
                        "rationale": "The fixture exposes exact nodewise coverage.",
                    },
                },
                {
                    "local_id": "t-head",
                    "object_type": "paper_target",
                    "payload": {
                        "target_role": "headline",
                        "claim_id": "c-head",
                        "rationale": "This is the bounded headline target.",
                    },
                },
            ]
        )
        local_nodes = {str(item["local_id"]): item for item in nodes}
        return {
            "schema_version": 1,
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "project_id": store.project_id(),
            "paper_id": "fixture-paper",
            "graph_kind": "logic",
            "domain_profile": "mathematics",
            "source_role": "external_reference",
            "builder": "paper-builder",
            "builder_context_id": "paper-builder-context",
            "source": copy.deepcopy(source),
            "base_snapshot_id": "",
            "supersedes_snapshot_id": "",
            "coverage": {
                "scope_kind": "bounded",
                "included_locators": ["pdf:0"],
                "excluded_locators": [],
                "units": coverage_units,
                "unresolved_load_bearing_units": [],
                "completeness_claim": "Complete for the bounded fixture paper.",
            },
            "nodes": nodes,
            "edges": PaperLogicStore._expected_logic_edges(local_nodes),
        }

    def _paper_audit_bundle(
        self,
        *,
        store: MathGraphStore,
        source: dict[str, object],
        base_snapshot_id: str,
        target_id: str,
        evidence_id: str,
    ) -> dict[str, object]:
        nodes: list[dict[str, object]] = [
            {
                "local_id": "finding",
                "object_type": "audit_finding",
                "payload": {
                    "finding_kind": "negation_or_polarity",
                    "severity": "critical",
                    "status": "corroborated",
                    "target_id": target_id,
                    "claim": "The target polarity must remain exact.",
                    "rationale": "The exact rendered sentence controls polarity.",
                    "evidence_unit_ids": [evidence_id],
                    "observed_excerpt": "The supporting lemma holds.",
                    "compared_text": "The supporting lemma does not hold.",
                    "load_bearing_tokens": ["not"],
                },
            }
        ]
        local_nodes = {str(item["local_id"]): item for item in nodes}
        return {
            "schema_version": 1,
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "project_id": store.project_id(),
            "paper_id": "fixture-paper",
            "graph_kind": "audit",
            "domain_profile": "mathematics",
            "source_role": "external_reference",
            "builder": "audit-builder",
            "builder_context_id": "audit-builder-context",
            "source": copy.deepcopy(source),
            "base_snapshot_id": base_snapshot_id,
            "supersedes_snapshot_id": "",
            "coverage": {
                "scope_kind": "audit_subset",
                "included_locators": ["fixture:audit"],
                "excluded_locators": [],
                "units": [
                    {
                        "unit_id": "audit-scope",
                        "classification": "audit_target",
                        "mapped_node_ids": ["finding"],
                        "reason": "",
                    }
                ],
                "unresolved_load_bearing_units": [],
                "completeness_claim": "Complete for the selected audit target.",
            },
            "nodes": nodes,
            "edges": PaperLogicStore._expected_audit_edges(local_nodes),
        }

    @staticmethod
    def _freeze_paper_bundle(
        *,
        store: MathGraphStore,
        bundle: dict[str, object],
        artifact: Path,
    ) -> tuple[dict[str, object], dict[str, object]]:
        paper = store.paper_logic()
        staged = paper.stage(bundle, artifact_path=artifact, actor=bundle["builder"])
        revision = paper.revision(staged["revision_id"])
        for index, profile in enumerate(revision["required_review_profiles"], 1):
            object_ids = paper._expected_review_object_ids(revision, profile)
            paper.record_review(
                {
                    "schema_version": 1,
                    "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
                    "project_id": store.project_id(),
                    "revision_id": revision["revision_id"],
                    "bundle_sha256": revision["bundle_sha256"],
                    "profile": profile,
                    "verdict": "correct",
                    "reviewer": f"reviewer-{index}-{profile}",
                    "reviewer_context_id": f"fresh-context-{index}-{profile}",
                    "fresh_context_contract": "fresh-context-v1",
                    "object_checks": [
                        {
                            "object_id": object_id,
                            "status": "pass",
                            "finding": "Checked against the frozen packet.",
                        }
                        for object_id in sorted(object_ids)
                    ],
                    "global_checks": [
                        {
                            "kind": kind,
                            "status": "pass",
                            "finding": "Required global check passed.",
                        }
                        for kind in sorted(REVIEW_GLOBAL_CHECKS[profile])
                    ],
                    "critical_errors": [],
                    "gaps": [],
                    "truth_effect": "none",
                }
            )
        frozen = paper.freeze(revision["revision_id"], actor="main")
        return revision, frozen

    def _release_payload(
        self,
        *,
        facts: list[Fact],
        research_ids: list[str],
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

    def _correct_decision_payload(
        self,
        lifecycle: object,
        release: dict[str, object],
        *,
        reviewer: str = "fresh-verifier",
    ) -> dict[str, object]:
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
            "reviewer": reviewer,
            "host_attestation": {
                "host": "test-host",
                "agent_id": reviewer,
                "isolation": "fresh_context",
                "fork_turns": "none",
                "allowed_capsule_sha256": capsule["capsule_sha256"],
            },
        }

    def test_v5_initialization_starts_with_empty_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = MathGraphStore(root)
            store.initialize(
                project_id="v5-empty",
                title="V5 empty authority",
                workflow_evidence_version=5,
                reasoning_mode="auto",
            )

            project = store.project()
            self.assertEqual(project["workflow_evidence_version"], 5)
            self.assertEqual(project["policy_revision"], V5_POLICY_REVISION)
            self.assertEqual(store.fact_ids(), [])
            status = store.v5_lifecycle().status()
            self.assertEqual(status["current_state"], "Research")
            self.assertEqual(status["next_safe_command"], "research-add")
            self.assertEqual(status["counts"]["facts"], 0)
            self.assertEqual(
                status["lifecycle_contract_sha256"],
                V5_LIFECYCLE_CONTRACT_SHA256,
            )
            self.assertTrue(store.audit().current_ok, store.audit().errors)

    def test_v5_generic_and_legacy_truth_writers_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = MathGraphStore(Path(temporary) / "v5")
            store.initialize(
                project_id="v5-guard",
                title="V5 guard",
                workflow_evidence_version=5,
            )
            with self.assertRaisesRegex(
                ValueError, "explicit lifecycle or capability adapter"
            ):
                store.memory_add(
                    {"kind": "direction", "claim": "unscoped write"},
                    actor="main",
                )
            with store.v5_mutation_lock(command="submit"):
                with self.assertRaisesRegex(ValueError, "legacy submit"):
                    store.submit(
                        Fact(
                            problem_id=store.project_id(),
                            author="worker",
                            predecessors=[],
                            statement="[CLAIM:X] X holds.",
                            proof="Proof.",
                        ),
                        worker="worker",
                    )

            with store.v5_mutation_lock(command="memory-add"):
                memory_id = store.memory_add(
                    {"kind": "direction", "claim": "adapted optional write"},
                    actor="main",
                )
            self.assertIn(memory_id, store.memory_latest())

    def test_cli_init_defaults_to_v5_but_v4_remains_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            v5_root = base / "v5"
            stdout = StringIO()
            with redirect_stdout(stdout), redirect_stderr(StringIO()):
                code = cli_main(
                    [
                        "--root",
                        str(v5_root),
                        "--role",
                        "operator",
                        "init",
                        "--project-id",
                        "cli-v5",
                        "--title",
                        "CLI V5",
                    ]
                )
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["project"]["workflow_evidence_version"], 5)
            self.assertEqual(payload["lifecycle"]["current_state"], "Research")

            v4_root = base / "v4"
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                code = cli_main(
                    [
                        "--root",
                        str(v4_root),
                        "--role",
                        "operator",
                        "init",
                        "--project-id",
                        "cli-v4",
                        "--title",
                        "CLI V4",
                        "--workflow-version",
                        "4",
                    ]
                )
            self.assertEqual(code, 0)
            v4_store = MathGraphStore(v4_root)
            self.assertEqual(v4_store.workflow_evidence_version(), 4)
            self.assertTrue(v4_store.audit().current_ok, v4_store.audit().errors)

    def test_research_ledger_is_cumulative_and_dispositions_do_not_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5")
            lifecycle = store.v5_lifecycle()
            challenge = lifecycle.add_research(
                {
                    "kind": "counterexample",
                    "claim": "The proposed bound fails at the boundary.",
                    "content": "Take the boundary parameter to zero.",
                    "rationale": "Adverse work must remain cumulative.",
                },
                actor="adverse-worker",
            )
            original_bytes = lifecycle._research_path(
                challenge["research_id"]
            ).read_bytes()
            disposition = lifecycle.update_research(
                challenge["research_id"],
                status="blocked",
                actor="main",
                note="Requires a repaired hypothesis.",
            )

            self.assertNotEqual(
                disposition["research_id"], challenge["research_id"]
            )
            self.assertEqual(
                lifecycle._research_path(challenge["research_id"]).read_bytes(),
                original_bytes,
            )
            self.assertEqual(lifecycle.frontier(), [])
            history = lifecycle.frontier(include_history=True)
            self.assertEqual(history[0]["status"], "blocked")
            self.assertEqual(
                history[0]["latest_disposition_id"],
                disposition["research_id"],
            )

    def test_candidate_release_cannot_hide_linked_existing_adverse_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "v5-adverse-filter")
            lifecycle = store.v5_lifecycle()
            proof = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Prove the filtered claim.",
                },
                actor="candidate-producer",
            )
            challenge = lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "Check the proof at its singular boundary.",
                    "relation": "challenges",
                    "related_research_ids": [proof["research_id"]],
                },
                actor="adverse-worker",
            )
            unrelated = lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "Challenge an unrelated project branch.",
                },
                actor="unrelated-adverse-worker",
            )
            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The filtered claim holds.",
                proof="Direct proof with the singular boundary handled.",
            )
            payload = self._release_payload(
                facts=[fact], research_ids=[proof["research_id"]]
            )
            with self.assertRaisesRegex(ValueError, "undisposed bound challenges"):
                lifecycle.candidate_release(
                    copy.deepcopy(payload), producer="candidate-producer"
                )

            payload["challenge_dispositions"] = [
                {
                    "research_id": challenge["research_id"],
                    "disposition": "resolved_by_candidate",
                    "rationale": "The proof now treats the singular boundary explicitly.",
                }
            ]
            with self.assertRaisesRegex(ValueError, "exactly match"):
                lifecycle.candidate_release(
                    copy.deepcopy(payload), producer="candidate-producer"
                )

            payload["adverse_actor_ids"] = ["adverse-worker"]
            release = lifecycle.candidate_release(
                payload, producer="candidate-producer"
            )
            bound_ids = {
                item["research_id"] for item in release["research_bindings"]
            }
            self.assertEqual(
                bound_ids, {proof["research_id"], challenge["research_id"]}
            )
            self.assertNotIn(unrelated["research_id"], bound_ids)
            self.assertIn("adverse-worker", release["excluded_verifier_ids"])

    def test_frontier_limits_and_explicit_last_entry_have_no_truncation_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "v5-frontier-boundary")
            lifecycle = store.v5_lifecycle()
            entries = [
                lifecycle.add_research(
                    {"kind": "direction", "claim": f"Branch {index}."},
                    actor="main",
                )
                for index in range(4)
            ]
            lifecycle.update_research(
                entries[0]["research_id"],
                status="blocked",
                actor="main",
                note="Boundary fixture disposition.",
            )
            with self.assertRaisesRegex(ValueError, "positive"):
                lifecycle.frontier(limit=0)
            self.assertEqual(len(lifecycle.frontier(limit=1)), 1)
            self.assertEqual(len(lifecycle.frontier(limit=2)), 2)
            self.assertEqual(len(lifecycle.frontier(limit=3)), 3)
            self.assertEqual(len(lifecycle.frontier(limit=4)), 3)
            last = entries[-1]["research_id"]
            planned = lifecycle.create_round(
                workers=1,
                research_ids=[last],
            )
            self.assertEqual(planned["assignments"][0]["research_id"], last)

    def test_three_plane_cards_share_one_snapshot_without_closure_coupling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5")
            lifecycle = store.v5_lifecycle()
            first = lifecycle.add_research(
                {"kind": "direction", "claim": "Prove the local lemma."},
                actor="main",
            )
            second = lifecycle.add_research(
                {
                    "kind": "counterexample",
                    "claim": "Stress-test the local lemma.",
                },
                actor="adverse-worker",
            )
            round_status = lifecycle.create_round(
                workers=2,
                research_ids=[first["research_id"], second["research_id"]],
                host_task_scope_id="host-task-v5-test",
            )
            snapshots = {
                item["blackboard_snapshot_sha256"]
                for item in round_status["assignments"]
            }
            self.assertEqual(len(snapshots), 1)
            for assignment in round_status["assignments"]:
                card = json.loads(
                    Path(assignment["task_card_path"]).read_text(encoding="utf-8")
                )
                lifecycle.validate_task_card(
                    card, expected_path=Path(assignment["task_card_path"])
                )
                self.assertEqual(card["control_plane"]["plane"], "control")
                self.assertEqual(
                    card["mathematical_state"]["plane"], "mathematical_state"
                )
                self.assertEqual(card["narrative_plane"]["plane"], "narrative")
                self.assertNotIn("profile_closure", card)
                self.assertNotIn("pulse_closure", card)
                self.assertIsNone(card["campaign_id"])
            self.assertFalse(round_status["round_closure_required"])

    def test_post_admission_refute_card_binds_complete_dossier_and_current_authority(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "v5-post-admission-refute")
            lifecycle = store.v5_lifecycle()
            proof_research = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Prove the target theorem.",
                    "content": "The proof uses the sealed calculation packet.",
                },
                actor="candidate-producer",
            )
            artifact = root / "inputs" / "proof-calculation.txt"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("sealed proof calculation\n", encoding="utf-8")
            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The target theorem holds for every h >= 2.",
                proof="The complete proof is checked against the sealed calculation.",
            )
            release_payload = self._release_payload(
                facts=[fact],
                research_ids=[proof_research["research_id"]],
            )
            release_payload["artifacts"] = [
                {
                    "path": "inputs/proof-calculation.txt",
                    "sha256": sha256_bytes(artifact.read_bytes()),
                    "role": "proof_calculation",
                }
            ]
            release_payload["verification_plan"][
                "authorized_artifact_roles"
            ] = ["proof_calculation"]
            release = lifecycle.candidate_release(
                release_payload,
                producer="candidate-producer",
            )
            decision = lifecycle.certification_record(
                self._correct_decision_payload(lifecycle, release)
            )
            marker = lifecycle.fact_admit(
                release_id=release["release_id"],
                decision_id=decision["decision_id"],
                gateway="independent-gateway",
            )

            stale_background = (
                "# Project background\n\n"
                "The project starts with an empty Fact Graph and the target is open.\n"
            )
            background_path = root / "PROJECT_BACKGROUND.md"
            background_path.write_text(stale_background, encoding="utf-8")
            release_path = lifecycle._release_path(release["release_id"])
            challenge = lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "Attack the admitted theorem at every quantifier boundary.",
                    "content": (
                        "Check quantifiers, signs, common-pole regularity, cancellation, "
                        "and computational independence."
                    ),
                    "rationale": "A clean adverse worker needs the complete dossier.",
                    "source": str(release_path),
                    "related_fact_id": fact.fact_id,
                    "attack_target_release_id": release["release_id"],
                    "attack_target_decision_id": decision["decision_id"],
                    "logic_signals": ["quantifier", "domain", "computation"],
                },
                actor="adverse-worker",
            )
            planned = lifecycle.create_round(
                workers=1,
                research_ids=[challenge["research_id"]],
            )
            task_card_path = Path(planned["assignments"][0]["task_card_path"])
            card_bytes_before = task_card_path.read_bytes()
            card = json.loads(card_bytes_before)
            state = card["mathematical_state"]

            self.assertEqual(
                card["task_context_revision"],
                V5_TASK_CONTEXT_REVISION,
            )
            self.assertEqual(state["source_research_dossier"], challenge)
            self.assertEqual(
                state["source_research_dossier"]["content"],
                challenge["content"],
            )
            self.assertEqual(
                state["source_research_dossier"]["source"],
                str(release_path),
            )
            self.assertEqual(
                state["source_research_dossier"]["metadata"],
                challenge["metadata"],
            )
            authority = state["authority_snapshot"]
            self.assertEqual(
                authority["precedence_rule"],
                "machine_validated_v5_authority_overrides_nontruth_"
                "project_background_status_claims",
            )
            self.assertEqual(authority["attack_target"]["admission_status"], "active")
            self.assertEqual(
                authority["attack_target"]["acceptance_id"],
                marker["acceptance_id"],
            )
            self.assertEqual(
                authority["attack_target"]["release_id"],
                release["release_id"],
            )
            self.assertEqual(
                authority["attack_target"]["decision_id"],
                decision["decision_id"],
            )
            target_binding = next(
                item
                for item in authority["fact_bindings"]
                if item["fact_id"] == fact.fact_id
            )
            self.assertEqual(target_binding["status"], "active")
            self.assertIsNotNone(target_binding["statement_interface"])
            capability_roles = {
                item["role"] for item in authority["capabilities"]
            }
            self.assertTrue(
                {
                    "attack_target_candidate_release",
                    "attack_target_certification_decision",
                    "attack_target_admission_marker",
                    f"attack_target_admitted_fact:{fact.fact_id}",
                    "attack_target_artifact:proof_calculation",
                }.issubset(capability_roles)
            )
            for capability in authority["capabilities"]:
                capability_path = root / capability["path"]
                self.assertEqual(
                    sha256_bytes(capability_path.read_bytes()),
                    capability["sha256"],
                )
            background = state["project_background"]
            self.assertNotIn("body", background)
            self.assertEqual(
                background["source_sha256"],
                sha256_bytes(stale_background.encode("utf-8")),
            )
            self.assertEqual(
                background["index"]["coverage_receipt"]["omitted_byte_count"],
                0,
            )
            self.assertEqual(
                (root / background["snapshot_relpath"]).read_text(encoding="utf-8"),
                stale_background,
            )
            self.assertEqual(background_path.read_text(encoding="utf-8"), stale_background)
            prompt = Path(planned["assignments"][0]["prompt_path"]).read_text(
                encoding="utf-8"
            )
            self.assertIn("source_research_dossier", prompt)
            self.assertIn("authority_snapshot controls", prompt)
            lifecycle.validate_task_card(card, expected_path=task_card_path)

            tampered_dossier = copy.deepcopy(card)
            tampered_dossier["mathematical_state"]["source_research_dossier"][
                "content"
            ] = "truncated"
            with self.assertRaisesRegex(ValueError, "dossier drifted or is incomplete"):
                lifecycle.validate_task_card(tampered_dossier)

            legacy_projection = copy.deepcopy(card)
            legacy_projection.pop("task_context_revision")
            legacy_projection.pop("context_selection")
            legacy_projection["mathematical_state"].pop("source_research_dossier")
            legacy_projection["mathematical_state"].pop("authority_snapshot")
            legacy_projection["mathematical_state"]["project_background"] = {
                "read_policy": "default_if_present",
                "relpath": "PROJECT_BACKGROUND.md",
                "sha256": sha256_bytes(stale_background.encode("utf-8")),
                "body": stale_background,
                "truth_effect": "nontruth_background_only",
                "load_bearing_rule": "return_to_exact_cited_source",
            }
            legacy_semantic = {
                key: value
                for key, value in legacy_projection.items()
                if key != "task_card_semantic_sha256"
            }
            legacy_projection["task_card_semantic_sha256"] = sha256_json(
                legacy_semantic
            )
            lifecycle.validate_task_card(legacy_projection)

            related_only = lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "Check only the admitted statement interface.",
                    "related_fact_id": fact.fact_id,
                },
                actor="adverse-worker",
            )
            related_only_round = lifecycle.create_round(
                workers=1,
                research_ids=[related_only["research_id"]],
            )
            related_only_card = json.loads(
                Path(
                    related_only_round["assignments"][0]["task_card_path"]
                ).read_text(encoding="utf-8")
            )
            related_only_authority = related_only_card["mathematical_state"][
                "authority_snapshot"
            ]
            self.assertIsNone(related_only_authority["attack_target"])
            self.assertEqual(related_only_authority["capabilities"], [])
            self.assertEqual(
                related_only_authority["fact_bindings"][0]["status"],
                "active",
            )

            lifecycle.revoke(
                fact.fact_id,
                reason="Exercise authority drift handling.",
                actor="gateway",
            )
            with self.assertRaisesRegex(ValueError, "authority snapshot is stale"):
                lifecycle.validate_task_card(card)
            self.assertEqual(task_card_path.read_bytes(), card_bytes_before)
            replanned = lifecycle.create_round(
                workers=1,
                research_ids=[challenge["research_id"]],
            )
            replanned_card = json.loads(
                Path(replanned["assignments"][0]["task_card_path"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                replanned_card["mathematical_state"]["authority_snapshot"]
                ["attack_target"]["admission_status"],
                "revoked",
            )
            self.assertEqual(background_path.read_text(encoding="utf-8"), stale_background)

    def test_partial_attack_target_is_rejected_before_round_directory_creation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "v5-partial-attack-target")
            lifecycle = store.v5_lifecycle()
            partial = lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "Attack a partially named authority target.",
                    "attack_target_release_id": "release-" + "a" * 64,
                },
                actor="adverse-worker",
            )
            before = sorted(store.rounds_dir.iterdir())
            with self.assertRaisesRegex(ValueError, "must bind both"):
                lifecycle.create_round(
                    workers=1,
                    research_ids=[partial["research_id"]],
                )
            self.assertEqual(sorted(store.rounds_dir.iterdir()), before)

    def test_profile_closure_commands_are_nontruth_repair_advice_in_v5(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "v5-readiness")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "Prove the advisory claim."},
                actor="candidate-producer",
            )
            round_status = lifecycle.create_round(
                workers=1,
                research_ids=[research["research_id"]],
            )
            advice = lifecycle.process_readiness_status(round_status["round_id"])
            self.assertFalse(advice["admission_authority"])
            self.assertEqual(advice["truth_effect"], "none")
            self.assertEqual(
                {item["category"] for item in advice["recommended_actions"]},
                {"return_missing"},
            )
            recorded = lifecycle.record_process_readiness(
                round_status["round_id"],
                {"note": "Keep the missing return visible as a repair suggestion."},
                actor="main",
            )
            guidance = lifecycle._research_record(
                recorded["recorded_research_id"]
            )
            self.assertEqual(guidance["kind"], "guidance")
            self.assertFalse(guidance["metadata"]["admission_authority"])
            self.assertEqual(
                lifecycle.process_readiness_status(round_status["round_id"])[
                    "recommended_actions"
                ],
                advice["recommended_actions"],
            )

            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The advisory claim holds.",
                proof="Direct proof of the advisory claim.",
            )
            release = lifecycle.candidate_release(
                self._release_payload(
                    facts=[fact], research_ids=[research["research_id"]]
                ),
                producer="candidate-producer",
            )
            decision = lifecycle.certification_record(
                self._correct_decision_payload(lifecycle, release)
            )
            lifecycle.fact_admit(
                release_id=release["release_id"],
                decision_id=decision["decision_id"],
                gateway="independent-gateway",
            )
            self.assertEqual(store.fact_ids(), [fact.fact_id])
            after_admission = lifecycle.process_readiness_status(
                round_status["round_id"]
            )
            self.assertIn(
                "return_missing",
                {item["category"] for item in after_admission["recommended_actions"]},
            )
            self.assertFalse(after_admission["admission_authority"])

    def test_bad_peer_is_quarantined_without_destroying_valid_research(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5")
            lifecycle = store.v5_lifecycle()
            source_entries = [
                lifecycle.add_research(
                    {"kind": "direction", "claim": f"Investigate branch {index}."},
                    actor="main",
                )
                for index in (1, 2)
            ]
            round_status = lifecycle.create_round(
                workers=2,
                research_ids=[item["research_id"] for item in source_entries],
            )
            assignments = round_status["assignments"]

            def return_payload(assignment: dict[str, object]) -> dict[str, object]:
                card = json.loads(
                    Path(str(assignment["task_card_path"])).read_text(
                        encoding="utf-8"
                    )
                )
                payload: dict[str, object] = {
                    "schema_version": 5,
                    "project_id": store.project_id(),
                    "round_id": round_status["round_id"],
                    "assignment_id": assignment["assignment_id"],
                    "worker_id": assignment["worker_id"],
                    "task_card_sha256": assignment["task_card_sha256"],
                    "blackboard_snapshot_sha256": assignment[
                        "blackboard_snapshot_sha256"
                    ],
                    "outcome": "insight",
                    "claim": "A useful local reduction survives.",
                    "content": "Reduce to the bounded subcase.",
                    "narrative": {
                        "rationale": "The reduction isolates the obstruction.",
                        "summary": "One local reduction.",
                        "intuition": "Cut away the irrelevant branch.",
                        "limitations": "The boundary case remains open.",
                    },
                    "artifacts": [],
                }
                if "assurance_contract" in card:
                    payload.update(
                        {
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
                    )
                return payload

            valid_payload = return_payload(assignments[0])
            valid_path = Path(assignments[0]["return_path"])
            valid_path.write_text(
                json.dumps(valid_payload, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            valid_sha = hashlib.sha256(valid_path.read_bytes()).hexdigest()
            ingested = lifecycle.ingest_return(
                round_id=round_status["round_id"],
                assignment_id=assignments[0]["assignment_id"],
                worker_final_sha256=valid_sha,
            )
            self.assertEqual(ingested["status"], "ingested")

            bad_payload = return_payload(assignments[1])
            del bad_payload["content"]
            bad_path = Path(assignments[1]["return_path"])
            bad_path.write_text(
                json.dumps(bad_payload, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            bad_sha = hashlib.sha256(bad_path.read_bytes()).hexdigest()
            quarantined = lifecycle.ingest_return(
                round_id=round_status["round_id"],
                assignment_id=assignments[1]["assignment_id"],
                worker_final_sha256=bad_sha,
            )
            self.assertEqual(quarantined["status"], "quarantined")
            final_status = lifecycle.round_status(round_status["round_id"])
            self.assertEqual(final_status["ingested_count"], 1)
            self.assertEqual(final_status["quarantined_count"], 1)
            self.assertFalse(final_status["round_closure_required"])
            self.assertIn(
                ingested["research_id"],
                {record["research_id"] for record in lifecycle.research_records()},
            )
            self.assertTrue(store.audit().current_ok, store.audit().errors)

    def test_v5_optional_research_adapters_remain_cumulative_and_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "v5-optional-adapters")
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {
                    "kind": "conjecture",
                    "claim": "Explore a bounded conjecture.",
                    "rationale": "Exercise retained optional adapters.",
                },
                actor="main",
            )

            ordinary = lifecycle.create_round(
                workers=1,
                research_ids=[source["research_id"]],
            )
            ordinary_card = store._read_json(
                Path(ordinary["assignments"][0]["task_card_path"])
            )
            self.assertIsNone(
                ordinary_card["mathematical_state"]["project_background"]
            )
            self.assertFalse((root / "PROJECT_BACKGROUND.md").exists())
            with store.v5_mutation_lock(command="work-unit-abort"):
                abort = store.reasoning_modes().abort_work_unit(
                    round_id=ordinary["round_id"],
                    actor="main",
                    reason="Explicitly cancel only this frozen work unit.",
                )
            self.assertEqual(
                abort["effect"],
                "reject_future_managed_work_for_this_frozen_unit",
            )
            with self.assertRaisesRegex(ValueError, "explicitly aborted"):
                lifecycle.preflight_return(
                    round_id=ordinary["round_id"],
                    assignment_id=ordinary["assignments"][0]["assignment_id"],
                )
            background_body = (
                "# Project background\n\n"
                "Legacy and abandoned rounds are nontruth context only.\n"
            )
            (root / "PROJECT_BACKGROUND.md").write_text(
                background_body,
                encoding="utf-8",
            )
            contextual = lifecycle.create_round(
                workers=1,
                research_ids=[source["research_id"]],
            )
            contextual_card = store._read_json(
                Path(contextual["assignments"][0]["task_card_path"])
            )
            background = contextual_card["mathematical_state"][
                "project_background"
            ]
            self.assertNotIn("body", background)
            self.assertEqual(
                background["source_sha256"],
                sha256_bytes(background_body.encode("utf-8")),
            )
            self.assertEqual(
                (root / background["snapshot_relpath"]).read_text(encoding="utf-8"),
                background_body,
            )

            event_id = lifecycle.novelty_record(
                {
                    "subject_kind": "memory",
                    "subject_id": source["research_id"],
                    "corpus": "bounded fixture corpus on 2026-07-28",
                    "query": "bounded conjecture",
                    "status": "unsearched",
                    "hits": [],
                },
                actor="literature-worker",
            )
            self.assertEqual(
                lifecycle.novelty_status(source["research_id"])[0]["event_id"],
                event_id,
            )

            repair = lifecycle.create_repair_round(source["research_id"])
            repair_record = lifecycle._research_record(repair["research_id"])
            self.assertEqual(repair_record["kind"], "repair")
            self.assertEqual(
                repair_record["related_research_ids"],
                [source["research_id"]],
            )
            self.assertEqual(
                lifecycle._research_record(source["research_id"]),
                source,
            )

            board = store.blackboard()
            space_id = next(
                node_id
                for node_id, node in board.nodes().items()
                if node["node_type"] == "space"
            )
            node = make_node(
                node_type="conjecture",
                logical_key="optional-adapter-conjecture",
                payload={"statement": "Promote this exploration to Research."},
                created_by_assignment_id="main",
            )
            query = {
                "seed_node_ids": [node["node_id"]],
                "direction": "both",
                "max_hops": 1,
                "edge_type_allowlist": ["*"],
                "node_type_allowlist": ["*"],
                "node_budget": 20,
                "edge_budget": 20,
            }
            with store.v5_mutation_lock(command="blackboard-promote-node"):
                board.add_node_with_placements(
                    node=node,
                    space_ids=[space_id],
                    actor="main",
                )
                board.reindex(apply=True, actor="main")
                snapshot = board.snapshot(query=query, actor="main")
                campaign_id = store.campaigns().create(
                    {
                        "name": "Optional adapters",
                        "objective": "Keep optional planning capabilities usable.",
                        "source_claim_ids": [],
                        "targets": [],
                        "constraints": ["No automatic Fact promotion."],
                        "stop_conditions": ["The bounded adapter test passes."],
                        "value_definition": "Prefer cumulative Research.",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                )
                promoted_id = store.campaigns().promote_blackboard_node(
                    node["node_id"],
                    {
                        "snapshot_id": snapshot["snapshot_id"],
                        "campaign_id": campaign_id,
                        "memory_kind": "conjecture",
                        "claim": "Promoted bounded conjecture.",
                        "rationale": "A user selected this exploration.",
                        "mode_suggestions": ["refute"],
                        "decision_profile": {
                            "burden": 0.2,
                            "impact": 0.8,
                            "information_value": 0.7,
                            "tractability": 0.8,
                        },
                        "blackboard_query": query,
                    },
                    actor="main",
                    memory_add=lambda payload, actor: lifecycle.add_research(
                        payload,
                        actor=actor,
                    )["research_id"],
                )
            promoted = lifecycle._research_record(promoted_id)
            self.assertEqual(
                promoted["metadata"]["origin_blackboard_node_id"],
                node["node_id"],
            )
            report = store.audit()
            self.assertEqual(report.novelty_entries, 1)
            self.assertTrue(report.current_ok, report.errors)

    def test_release_decision_and_gateway_admit_one_exact_fact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "v5-certification")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "The root claim holds."},
                actor="candidate-producer",
            )
            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The root claim holds.",
                proof="Direct proof of the root claim.",
            )
            release = lifecycle.candidate_release(
                self._release_payload(
                    facts=[fact], research_ids=[research["research_id"]]
                ),
                producer="candidate-producer",
            )
            self.assertEqual(store.fact_ids(), [])
            capsule = lifecycle.verifier_capsule(release["release_id"])
            self.assertNotIn("research", json.dumps(capsule).lower())
            with self.assertRaisesRegex(ValueError, "participated"):
                lifecycle.certification_record(
                    self._correct_decision_payload(
                        lifecycle,
                        release,
                        reviewer="candidate-producer",
                    )
                )
            decision = lifecycle.certification_record(
                self._correct_decision_payload(lifecycle, release)
            )
            marker = lifecycle.fact_admit(
                release_id=release["release_id"],
                decision_id=decision["decision_id"],
                gateway="independent-gateway",
            )
            self.assertEqual(marker["fact_ids"], [fact.fact_id])
            self.assertEqual(store.fact_ids(), [fact.fact_id])
            self.assertEqual(store.get_fact(fact.fact_id).statement, fact.statement)
            self.assertTrue(
                (store.interfaces_dir / f"{fact.fact_id}.json").is_file()
            )
            self.assertTrue(store.audit().current_ok, store.audit().errors)

    def test_paper_nodewise_release_binds_current_logic_audit_and_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "v5-paper-nodewise")
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
                "title": "Fixture paper",
                "version": "test-v1",
                "mime_type": "text/plain",
                "retrieved_at": "2026-07-28T00:00:00Z",
                "inspection_methods": [
                    "rendered_primary",
                    "text_extraction_secondary",
                ],
            }
            with store.v5_mutation_lock(command="paper-logic-init"):
                store.paper_logic().initialize(actor="main")
            logic_bundle = self._paper_logic_bundle(store=store, source=source)
            with store.v5_mutation_lock(command="paper-logic-freeze"):
                logic_revision, logic_frozen = self._freeze_paper_bundle(
                    store=store,
                    bundle=logic_bundle,
                    artifact=artifact,
                )
            logic_ids = logic_revision["local_id_map"]
            audit_bundle = self._paper_audit_bundle(
                store=store,
                source=source,
                base_snapshot_id=logic_frozen["snapshot_id"],
                target_id=logic_ids["c1"],
                evidence_id=logic_ids["s1"],
            )
            with store.v5_mutation_lock(command="paper-logic-freeze"):
                audit_revision, audit_frozen = self._freeze_paper_bundle(
                    store=store,
                    bundle=audit_bundle,
                    artifact=artifact,
                )
            audit_ids = audit_revision["local_id_map"]

            research = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Validate the fixture paper node by node.",
                },
                actor="paper-candidate-producer",
            )
            lemma = Fact(
                problem_id=store.project_id(),
                author="paper-candidate-producer",
                predecessors=[],
                statement="[CLAIM:LEMMA] The supporting lemma holds.",
                proof="Direct proof of the supporting lemma.",
            )
            use_anchor = f"[USE:{lemma.fact_id}:LEMMA:u1]"
            root_fact = Fact(
                problem_id=store.project_id(),
                author="paper-candidate-producer",
                predecessors=[lemma.fact_id],
                statement="[CLAIM:ROOT] The bounded paper theorem holds.",
                proof=f"Apply the supporting lemma {use_anchor}.",
                predecessor_uses=[
                    {
                        "fact_id": lemma.fact_id,
                        "clause_id": "LEMMA",
                        "use_anchor": use_anchor,
                        "used_conclusion": "The supporting lemma holds.",
                        "hypothesis_witnesses": [],
                        "convention_bridge": None,
                    }
                ],
            )
            payload = self._release_payload(
                facts=[lemma, root_fact],
                research_ids=[research["research_id"]],
                granularity="nodewise_proof_dag",
            )
            payload["artifacts"] = [
                {
                    "path": "paper.txt",
                    "sha256": artifact_sha,
                    "role": "paper_source",
                }
            ]
            payload["verification_plan"]["authorized_artifact_roles"] = [
                "paper_source"
            ]
            payload["verification_plan"]["required_checks"].extend(
                [
                    "paper_source_fidelity",
                    "paper_graph_structure",
                    "paper_audit",
                    "paper_target_coverage",
                ]
            )
            load_bearing = [logic_ids["c1"], logic_ids["c-head"]]
            payload["requested_assurance"] = {
                "validation_subject": {
                    "kind": "paper",
                    "subject_id": "fixture-paper",
                    "artifact_sha256": artifact_sha,
                    "load_bearing_node_ids": load_bearing,
                },
                "validation_granularity": "nodewise_proof_dag",
                "coverage": [
                    {
                        "paper_node_id": logic_ids["c1"],
                        "disposition": "fact_bundle_member",
                        "fact_id": lemma.fact_id,
                        "reason": "",
                    },
                    {
                        "paper_node_id": logic_ids["c-head"],
                        "disposition": "fact_bundle_member",
                        "fact_id": root_fact.fact_id,
                        "reason": "",
                    },
                ],
            }

            def paper_ref(
                frozen: dict[str, object],
                *,
                graph_kind: str,
                target_node_ids: list[str],
            ) -> dict[str, object]:
                manifest_path = (
                    store.paper_logic().snapshots_dir
                    / frozen["snapshot_id"]
                    / "manifest.json"
                )
                return {
                    "paper_id": "fixture-paper",
                    "snapshot_id": frozen["snapshot_id"],
                    "snapshot_sha256": sha256_bytes(manifest_path.read_bytes()),
                    "graph_kind": graph_kind,
                    "target_artifact_sha256": artifact_sha,
                    "target_node_ids": target_node_ids,
                }

            payload["paper_evidence_refs"] = [
                paper_ref(
                    logic_frozen,
                    graph_kind="logic",
                    target_node_ids=load_bearing,
                ),
                paper_ref(
                    audit_frozen,
                    graph_kind="audit",
                    target_node_ids=[audit_ids["finding"]],
                ),
            ]

            missing_coverage = copy.deepcopy(payload)
            missing_coverage["requested_assurance"]["coverage"].pop()
            with self.assertRaisesRegex(ValueError, "exactly cover"):
                lifecycle.candidate_release(
                    missing_coverage,
                    producer="paper-candidate-producer",
                )
            extra_coverage = copy.deepcopy(payload)
            extra_coverage["requested_assurance"]["coverage"].append(
                {
                    "paper_node_id": logic_ids["c2"],
                    "disposition": "source_only",
                    "fact_id": None,
                    "reason": "Deliberate N+1 coverage canary.",
                }
            )
            with self.assertRaisesRegex(ValueError, "exactly cover"):
                lifecycle.candidate_release(
                    extra_coverage,
                    producer="paper-candidate-producer",
                )
            unmapped_candidate = copy.deepcopy(payload)
            unmapped_candidate["requested_assurance"]["coverage"][1][
                "fact_id"
            ] = lemma.fact_id
            with self.assertRaisesRegex(ValueError, "map every Candidate Release Fact"):
                lifecycle.candidate_release(
                    unmapped_candidate,
                    producer="paper-candidate-producer",
                )

            wrong_artifact = copy.deepcopy(payload)
            wrong_artifact["requested_assurance"]["validation_subject"][
                "artifact_sha256"
            ] = "f" * 64
            with self.assertRaisesRegex(ValueError, "target/snapshot|source artifact"):
                lifecycle.candidate_release(
                    wrong_artifact,
                    producer="paper-candidate-producer",
                )

            unbound_node = copy.deepcopy(payload)
            unbound_node["paper_evidence_refs"][0]["target_node_ids"] = [
                logic_ids["c1"]
            ]
            with self.assertRaisesRegex(ValueError, "not bound by any EvidenceRef"):
                lifecycle.candidate_release(
                    unbound_node,
                    producer="paper-candidate-producer",
                )

            one_fact = Fact(
                problem_id=store.project_id(),
                author="paper-candidate-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] A monolithic paper claim holds.",
                proof="Direct monolithic proof.",
            )
            underspecified = copy.deepcopy(payload)
            underspecified["candidates"] = [one_fact.as_submission_dict()]
            underspecified["requested_assurance"]["coverage"] = [
                {
                    "paper_node_id": node_id,
                    "disposition": "fact_bundle_member",
                    "fact_id": one_fact.fact_id,
                    "reason": "",
                }
                for node_id in load_bearing
            ]
            with self.assertRaisesRegex(ValueError, "multiple candidates"):
                lifecycle.candidate_release(
                    underspecified,
                    producer="paper-candidate-producer",
                )

            release = lifecycle.candidate_release(
                payload,
                producer="paper-candidate-producer",
            )
            self.assertEqual(
                release["requested_assurance"]["validation_granularity"],
                "nodewise_proof_dag",
            )
            self.assertNotIn("paper_continuation_release_capsule", release)
            decision = lifecycle.certification_record(
                self._correct_decision_payload(lifecycle, release)
            )
            lifecycle.fact_admit(
                release_id=release["release_id"],
                decision_id=decision["decision_id"],
                gateway="independent-gateway",
            )
            self.assertEqual(set(store.fact_ids()), {lemma.fact_id, root_fact.fact_id})
            packet = build_v5_reader_packet(store)
            for fact_node in (
                node for node in packet["nodes"] if node["plane"] == "fact"
            ):
                self.assertNotIn("[CLAIM:", fact_node["summary"])
                self.assertIn("[CLAIM:", fact_node["formal"]["statement"])
            self.assertNotIn(
                "project-background",
                {node["id"] for node in packet["nodes"]},
            )
            self.assertEqual(
                {
                    node["plane"]
                    for node in packet["nodes"]
                }.intersection({"fact", "paper", "audit", "blackboard", "reader"}),
                {"fact", "paper", "audit", "blackboard", "reader"},
            )
            self.assertTrue(
                any(
                    node["provenance"]["source_status"].startswith(
                        "v5_candidate_release"
                    )
                    for node in packet["nodes"]
                )
            )
            rendered, build_meta = render_reader_html(packet)
            self.assertIn("chalxius-reader-html-20", rendered)
            self.assertEqual(
                build_meta["renderer_revision"],
                "chalxius-reader-html-20",
            )
            for node in packet["nodes"]:
                self.assertLessEqual(len(node["title"]), 64)
                self.assertTrue(
                    node["title"].endswith(
                        node["provenance"]["object_sha256"][:6]
                    )
                )
                self.assertNotIn(r"\(", node["title"])
                self.assertNotIn(r"\[", node["title"])
                self.assertNotIn("$$", node["title"])
                self.assertNotIn(r"\begin{", node["title"])
            (root / "PROJECT_BACKGROUND.md").write_text(
                "# Background\n\nUser-generated summary body.\n",
                encoding="utf-8",
            )
            packet_with_background = build_v5_reader_packet(store)
            self.assertIn(
                "project-background",
                {node["id"] for node in packet_with_background["nodes"]},
            )
            self.assertTrue(store.audit().current_ok, store.audit().errors)

    def test_paper_continuation_release_capsule_normal_flow(self) -> None:
        # Runtime-manifest identity has its own release-matrix probes.  This
        # behavioral probe isolates the continuation-capsule handoff while the
        # candidate tree is intentionally ahead of its final MANIFEST.
        with patch.object(
            V5LifecycleManager,
            "_validate_bound_runtime_binding",
            return_value=None,
        ):
            self.test_philosophy_paper_continuation_is_complete_atomic_and_current()

    def test_paper_continuation_release_capsule_tamper_fails_closed(self) -> None:
        original = PaperContinuationManager.prepare_release_capsule

        def tampered_prepare(
            manager: PaperContinuationManager, *args: object, **kwargs: object
        ) -> dict[str, object]:
            prepared = copy.deepcopy(original(manager, *args, **kwargs))
            prepared["capsule"]["status_proof"]["witness"][
                "head_sha256"
            ] = "0" * 64
            return prepared

        with patch.object(
            V5LifecycleManager,
            "_validate_bound_runtime_binding",
            return_value=None,
        ):
            with patch.object(
                PaperContinuationManager,
                "prepare_release_capsule",
                tampered_prepare,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "release capsule hash mismatch|release witness hash mismatch",
                ):
                    self.test_philosophy_paper_continuation_is_complete_atomic_and_current()

    def test_atomic_fact_dag_appears_all_or_none_and_revokes_cascade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "v5-atomic")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "Prove a two-node DAG."},
                actor="bundle-producer",
            )
            lemma = Fact(
                problem_id=store.project_id(),
                author="bundle-producer",
                predecessors=[],
                statement="[CLAIM:LEMMA] The supporting lemma holds.",
                proof="Proof of the supporting lemma.",
            )
            use_anchor = f"[USE:{lemma.fact_id}:LEMMA:u1]"
            root = Fact(
                problem_id=store.project_id(),
                author="bundle-producer",
                predecessors=[lemma.fact_id],
                statement="[CLAIM:ROOT] The dependent root holds.",
                proof=f"Apply the supporting lemma {use_anchor}.",
                predecessor_uses=[
                    {
                        "fact_id": lemma.fact_id,
                        "clause_id": "LEMMA",
                        "use_anchor": use_anchor,
                        "used_conclusion": "The supporting lemma holds.",
                        "hypothesis_witnesses": [],
                        "convention_bridge": None,
                    }
                ],
            )
            release = lifecycle.candidate_release(
                self._release_payload(
                    facts=[lemma, root],
                    research_ids=[research["research_id"]],
                    granularity="atomic_fact_dag",
                ),
                producer="bundle-producer",
            )
            self.assertEqual(store.fact_ids(), [])
            decision = lifecycle.certification_record(
                self._correct_decision_payload(lifecycle, release)
            )
            lifecycle.fact_admit(
                release_id=release["release_id"],
                decision_id=decision["decision_id"],
                gateway="independent-gateway",
            )
            self.assertEqual(set(store.fact_ids()), {lemma.fact_id, root.fact_id})
            revoked = lifecycle.revoke(
                lemma.fact_id,
                reason="Regression canary",
                actor="gateway",
            )
            self.assertEqual(set(revoked), {lemma.fact_id, root.fact_id})
            self.assertEqual(store.fact_ids(), [])
            self.assertTrue(store.audit().current_ok, store.audit().errors)

    def test_v5_fact_bundle_commands_are_lifecycle_compatibility_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "v5-bundle-alias")
            lemma = Fact(
                problem_id=store.project_id(),
                author="bundle-worker",
                predecessors=[],
                statement="[CLAIM:LEMMA] The compatibility lemma holds.",
                proof="Direct proof of the compatibility lemma.",
            )
            anchor = f"[USE:{lemma.fact_id}:LEMMA:u1]"
            theorem = Fact(
                problem_id=store.project_id(),
                author="bundle-worker",
                predecessors=[lemma.fact_id],
                statement="[CLAIM:THEOREM] The compatibility theorem holds.",
                proof=f"Apply the compatibility lemma {anchor}.",
                predecessor_uses=[
                    {
                        "fact_id": lemma.fact_id,
                        "clause_id": "LEMMA",
                        "use_anchor": anchor,
                        "used_conclusion": "The compatibility lemma holds.",
                        "hypothesis_witnesses": [],
                        "convention_bridge": None,
                    }
                ],
            )
            bundle_input = root / "bundle-input.json"
            bundle_input.write_text(
                json.dumps(
                    {
                        "schema_version": 4,
                        "policy_revision": "mathgraph-0.3.0",
                        "project_id": store.project_id(),
                        "facts": [
                            lemma.as_submission_dict(),
                            theorem.as_submission_dict(),
                        ],
                        "bundle_claim": "One atomic compatibility mini-DAG.",
                    }
                ),
                encoding="utf-8",
            )
            stdout = StringIO()
            with redirect_stdout(stdout), redirect_stderr(StringIO()):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "operator",
                        "fact-bundle-submit",
                        "--input",
                        str(bundle_input),
                        "--worker",
                        "bundle-worker",
                    ]
                )
            self.assertEqual(code, 0)
            submitted = json.loads(stdout.getvalue())
            release_id = submitted["release_id"]
            self.assertEqual(submitted["fact_bundle_id"], release_id)
            release = store.v5_lifecycle().release(release_id)
            self.assertEqual(
                release["requested_assurance"]["validation_granularity"],
                "atomic_fact_dag",
            )

            capsules = []
            for command, subject_id in (
                ("verifier-capsule", release_id),
                ("make-verifier-task", theorem.fact_id),
                ("make-bundle-verifier-task", release_id),
                ("fact-bundle-verifier-task", release_id),
            ):
                stdout = StringIO()
                with redirect_stdout(stdout), redirect_stderr(StringIO()):
                    code = cli_main(
                        [
                            "--root",
                            str(root),
                            "--role",
                            "operator",
                            command,
                            subject_id,
                        ]
                    )
                self.assertEqual(code, 0, command)
                capsules.append(json.loads(stdout.getvalue()))
            self.assertTrue(
                all(capsule == capsules[0] for capsule in capsules[1:])
            )

            decision_payload = self._correct_decision_payload(
                store.v5_lifecycle(), release, reviewer="bundle-verifier"
            )
            decision_input = root / "bundle-decision.json"
            decision_input.write_text(
                json.dumps(decision_payload), encoding="utf-8"
            )
            stdout = StringIO()
            with redirect_stdout(stdout), redirect_stderr(StringIO()):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "gateway",
                        "fact-bundle-record-review",
                        release_id,
                        "--input",
                        str(decision_input),
                    ]
                )
            self.assertEqual(code, 0)
            decision_id = json.loads(stdout.getvalue())["review_id"]
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "gateway",
                        "fact-bundle-admit",
                        release_id,
                        "--review-id",
                        decision_id,
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(set(store.fact_ids()), {lemma.fact_id, theorem.fact_id})

    def test_certification_panels_require_exact_counts_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "v5-panel-boundaries")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "Prove an exact panel DAG."},
                actor="panel-producer",
            )
            lemma = Fact(
                problem_id=store.project_id(),
                author="panel-producer",
                predecessors=[],
                statement="[CLAIM:LEMMA] The panel lemma holds.",
                proof="Direct proof of the panel lemma.",
            )
            use_anchor = f"[USE:{lemma.fact_id}:LEMMA:u1]"
            root_fact = Fact(
                problem_id=store.project_id(),
                author="panel-producer",
                predecessors=[lemma.fact_id],
                statement="[CLAIM:ROOT] The panel root holds.",
                proof=f"Apply the panel lemma {use_anchor}.",
                predecessor_uses=[
                    {
                        "fact_id": lemma.fact_id,
                        "clause_id": "LEMMA",
                        "use_anchor": use_anchor,
                        "used_conclusion": "The panel lemma holds.",
                        "hypothesis_witnesses": [],
                        "convention_bridge": None,
                    }
                ],
            )
            release_payload = self._release_payload(
                facts=[lemma, root_fact],
                research_ids=[research["research_id"]],
                granularity="atomic_fact_dag",
            )
            duplicate_plan = copy.deepcopy(release_payload)
            duplicate_plan["verification_plan"]["required_checks"].append(
                "mathematical"
            )
            with self.assertRaisesRegex(ValueError, "required checks are duplicated"):
                lifecycle.candidate_release(
                    duplicate_plan,
                    producer="panel-producer",
                )
            release = lifecycle.candidate_release(
                release_payload,
                producer="panel-producer",
            )
            correct = self._correct_decision_payload(lifecycle, release)

            missing_check = copy.deepcopy(correct)
            missing_check["check_results"].pop()
            with self.assertRaisesRegex(ValueError, "exactly cover required checks"):
                lifecycle.certification_record(missing_check)
            duplicate_check = copy.deepcopy(correct)
            duplicate_check["check_results"].append(
                copy.deepcopy(duplicate_check["check_results"][0])
            )
            with self.assertRaisesRegex(ValueError, "duplicate checks"):
                lifecycle.certification_record(duplicate_check)

            missing_candidate = copy.deepcopy(correct)
            missing_candidate["candidate_checks"].pop()
            with self.assertRaisesRegex(ValueError, "exactly cover release Facts"):
                lifecycle.certification_record(missing_candidate)
            duplicate_candidate = copy.deepcopy(correct)
            duplicate_candidate["candidate_checks"].append(
                copy.deepcopy(duplicate_candidate["candidate_checks"][0])
            )
            with self.assertRaisesRegex(ValueError, "duplicate Facts"):
                lifecycle.certification_record(duplicate_candidate)

            missing_edge = copy.deepcopy(correct)
            missing_edge["edge_checks"].pop()
            with self.assertRaisesRegex(ValueError, "exactly cover internal edges"):
                lifecycle.certification_record(missing_edge)
            duplicate_edge = copy.deepcopy(correct)
            duplicate_edge["edge_checks"].append(
                copy.deepcopy(duplicate_edge["edge_checks"][0])
            )
            with self.assertRaisesRegex(ValueError, "duplicate edges"):
                lifecycle.certification_record(duplicate_edge)

            decision = lifecycle.certification_record(correct)
            lifecycle.fact_admit(
                release_id=release["release_id"],
                decision_id=decision["decision_id"],
                gateway="independent-gateway",
            )
            self.assertEqual(set(store.fact_ids()), {lemma.fact_id, root_fact.fact_id})

    def test_v5_series_order_budget_rejects_xy_swap_undertruncation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "v5-series-budget")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Compute the Q3 residue with a sufficient Laurent order budget.",
                },
                actor="series-producer",
            )
            evidence_dir = store.root / "evidence"
            evidence_dir.mkdir()
            artifact_inputs = []
            artifact_refs = []
            expected_outputs = []
            for role, name, raw in (
                ("base-result", "q3-base.json", b'{"difference":"0"}\n'),
                (
                    "depth-extension",
                    "q3-depth-extension.json",
                    b'{"orders":{"omega11":4,"omega21":2},"difference":"0"}\n',
                ),
            ):
                source = evidence_dir / name
                source.write_bytes(raw)
                digest = sha256_bytes(raw)
                artifact_inputs.append(
                    {
                        "path": source.relative_to(store.root).as_posix(),
                        "sha256": digest,
                        "role": role,
                    }
                )
                artifact_refs.append(
                    {
                        "role": role,
                        "path": (
                            "candidate_releases/artifacts/by-hash/"
                            f"{digest}/{name}"
                        ),
                        "sha256": digest,
                    }
                )
                expected_outputs.append({"role": role, "sha256": digest})

            independence = {axis: "cross_checked" for axis in INDEPENDENCE_AXES}
            independence["truncation_method"] = "formally_derived"
            evidence = {
                "key": "q3-residue",
                "role": "load_bearing",
                "proof_anchor": "[COMP:q3-residue]",
                "artifact_refs": artifact_refs,
                "entrypoint_role": "base-result",
                "command": ["python3", "replay_q3.py"],
                "interpreter": {"implementation": "SageMath", "version": "10"},
                "arithmetic": "exact Laurent series over rationals",
                "algorithm_spec": (
                    "Extract [t^-1] from prefactor * omega11 * omega21."
                ),
                "truncation_certificate": {
                    "kind": "series_product_coefficient",
                    "statement": (
                        "Factor orders are derived from their lowest Laurent powers."
                    ),
                    "checked_orders": [0, 2, 4],
                    "limitations": [],
                    "target_power": -1,
                    "factors": [
                        {
                            "factor_id": "prefactor",
                            "lowest_power": 1,
                            "retained_through": None,
                        },
                        {
                            "factor_id": "omega11",
                            "lowest_power": -2,
                            "retained_through": 0,
                        },
                        {
                            "factor_id": "omega21",
                            "lowest_power": -4,
                            "retained_through": 0,
                        },
                    ],
                    "depth_extension": {
                        "artifact_role": "depth-extension",
                        "factor_orders": [
                            {"factor_id": "omega11", "retained_through": 4},
                            {"factor_id": "omega21", "retained_through": 2},
                        ],
                    },
                },
                "expected_outputs": expected_outputs,
                "replay_checks": [
                    "inspect_algorithm",
                    "execute",
                    "verify_order_budget",
                    "extend_truncation_depth",
                ],
                "independence_matrix": independence,
            }
            fact = Fact(
                problem_id=store.project_id(),
                author="series-producer",
                predecessors=[],
                statement="[CLAIM:Q3] The corrected Q3 difference vanishes.",
                proof=(
                    "The exact replay and derived order budget give zero. "
                    "[COMP:q3-residue]"
                ),
                computational_evidence=[evidence],
            )
            payload = self._release_payload(
                facts=[fact], research_ids=[research["research_id"]]
            )
            payload["artifacts"] = artifact_inputs
            payload["verification_plan"]["authorized_artifact_roles"] = [
                "base-result",
                "depth-extension",
            ]
            payload["verification_plan"]["required_checks"].append(
                "program_math_truncation"
            )

            with self.assertRaisesRegex(
                ValueError,
                r"omega11 through t\^0.*requires it through t\^2",
            ):
                lifecycle.candidate_release(
                    copy.deepcopy(payload), producer="series-producer"
                )

            payload["candidates"][0]["computational_evidence"][0][
                "truncation_certificate"
            ]["factors"][1]["retained_through"] = 2
            missing_check = copy.deepcopy(payload)
            missing_check["verification_plan"]["required_checks"].remove(
                "program_math_truncation"
            )
            with self.assertRaisesRegex(ValueError, "program_math_truncation"):
                lifecycle.candidate_release(
                    missing_check, producer="series-producer"
                )

            release = lifecycle.candidate_release(
                payload, producer="series-producer"
            )
            self.assertIn(
                "program_math_truncation",
                release["verification_plan"]["required_checks"],
            )

    def test_philosophy_paper_continuation_is_complete_atomic_and_current(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "v5-philosophy-paper-continuation")
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
                "title": "Philosophy fixture paper",
                "version": "test-v1",
                "mime_type": "text/plain",
                "retrieved_at": "2026-07-30T00:00:00Z",
                "inspection_methods": [
                    "rendered_primary",
                    "text_extraction_secondary",
                ],
            }
            with store.v5_mutation_lock(command="paper-logic-init"):
                store.paper_logic().initialize(actor="main")
            logic_bundle = self._paper_logic_bundle(store=store, source=source)
            logic_bundle["domain_profile"] = "philosophy"
            logic_bundle["nodes"].append(
                {
                    "local_id": "t-support",
                    "object_type": "paper_target",
                    "payload": {
                        "target_role": "supporting",
                        "claim_id": "c1",
                        "rationale": "The supporting burden must remain independently visible.",
                    },
                }
            )
            local_nodes = {
                str(item["local_id"]): item for item in logic_bundle["nodes"]
            }
            logic_bundle["edges"] = PaperLogicStore._expected_logic_edges(local_nodes)
            with store.v5_mutation_lock(command="paper-logic-freeze"):
                logic_revision, logic_frozen = self._freeze_paper_bundle(
                    store=store,
                    bundle=logic_bundle,
                    artifact=artifact,
                )
            logic_ids = logic_revision["local_id_map"]
            audit_bundle = self._paper_audit_bundle(
                store=store,
                source=source,
                base_snapshot_id=logic_frozen["snapshot_id"],
                target_id=logic_ids["c1"],
                evidence_id=logic_ids["s1"],
            )
            audit_bundle["domain_profile"] = "philosophy"
            with store.v5_mutation_lock(command="paper-logic-freeze"):
                audit_revision, audit_frozen = self._freeze_paper_bundle(
                    store=store,
                    bundle=audit_bundle,
                    artifact=artifact,
                )
            audit_ids = audit_revision["local_id_map"]

            continuation = lifecycle.paper_continuation()
            plan_status = continuation.create_plan(
                logic_frozen["snapshot_id"],
                {
                    "selection_mode": "all_targets",
                    "target_node_ids": [],
                    "objective": (
                        "Preserve every explicit philosophical burden, objection, and "
                        "failure surface through revised writing and Fact review."
                    ),
                    "source_artifact_sha256": artifact_sha,
                },
                actor="main",
            )
            self.assertEqual(plan_status["counts"]["total"], 2)
            self.assertEqual(plan_status["counts"]["frontier_materialized"], 2)
            self.assertEqual(plan_status["counts"]["unresolved"], 2)
            self.assertFalse(plan_status["adequacy_complete"])
            plan_id = plan_status["plan_id"]
            plan = continuation.plan(plan_id)

            research_ids = [
                item["research_id"]
                for item in plan_status["target_research_bindings"]
            ]
            self.assertTrue(
                all(
                    lifecycle._research_record(research_id)["metadata"][
                        "independent_adverse_required"
                    ]
                    is True
                    for research_id in research_ids
                )
            )
            round_status = lifecycle.create_round(
                workers=2,
                research_ids=research_ids,
            )
            primary_assignments = [
                item
                for item in round_status["assignments"]
                if item["assignment_role"] == "primary"
            ]
            self.assertEqual(len(primary_assignments), 2)
            self.assertGreaterEqual(
                len(round_status["independent_adverse_pairs"]), 1
            )
            result_ids: dict[str, str] = {}
            analysis_artifacts: list[dict[str, str]] = []
            for index, assignment in enumerate(primary_assignments, 1):
                card = json.loads(
                    Path(str(assignment["task_card_path"])).read_text(
                        encoding="utf-8"
                    )
                )
                scope = card["paper_continuation_scope"]
                self.assertEqual(scope["plan_id"], plan_id)
                self.assertEqual(
                    scope["required_analysis_fields"],
                    [
                        "issue",
                        "importance",
                        "burden_holder",
                        "plain_language_summary",
                        "technical_term_ledger",
                        "strongest_charitable_objection",
                        "response_or_revision",
                        "independent_failure_surfaces",
                        "writing_coverage",
                    ],
                )
                artifact_dir = root / assignment["artifact_dir_relpath"]
                artifact_dir.mkdir(parents=True, exist_ok=True)
                analysis_path = artifact_dir / "paper-target-analysis.json"
                analysis_bytes = (
                    json.dumps(
                        {
                            "target_node_id": scope["target_node_id"],
                            "issue": "Which bounded conclusion has been earned?",
                            "importance": "It controls a distinct inferential burden.",
                            "burden_holder": "The proponent bears the justificatory burden.",
                            "plain_language_summary": (
                                "This step says exactly what must be shown and no more."
                            ),
                            "technical_term_ledger": [],
                            "strongest_charitable_objection": (
                                "The premise may support less than the stated conclusion."
                            ),
                            "response_or_revision": (
                                "Retain only the exact bounded conclusion."
                            ),
                            "independent_failure_surfaces": [
                                f"fs-{index}"
                            ],
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("utf-8")
                analysis_path.write_bytes(analysis_bytes)
                analysis_sha = sha256_bytes(analysis_bytes)
                analysis_artifacts.append(
                    {
                        "path": analysis_path.relative_to(root).as_posix(),
                        "sha256": analysis_sha,
                        "role": "paper_target_analysis",
                    }
                )
                payload: dict[str, object] = {
                    "schema_version": 5,
                    "project_id": store.project_id(),
                    "round_id": round_status["round_id"],
                    "assignment_id": assignment["assignment_id"],
                    "worker_id": assignment["worker_id"],
                    "task_card_sha256": assignment["task_card_sha256"],
                    "blackboard_snapshot_sha256": assignment[
                        "blackboard_snapshot_sha256"
                    ],
                    "outcome": "insight",
                    "claim": "The exact target survives only with its stated burden.",
                    "content": "The source closure and adverse boundary were checked.",
                    "narrative": {
                        "rationale": "The target is independently challengeable.",
                        "summary": "One bounded target was retained.",
                        "intuition": "Keep separate burdens in separate graph nodes.",
                        "limitations": "No claim is made beyond this target closure.",
                    },
                    "artifacts": [analysis_artifacts[-1]],
                    "obligation_dispositions": [
                        {
                            "obligation_id": obligation["obligation_id"],
                            "status": "complete",
                            "witness_artifact_sha256s": [analysis_sha],
                            "rationale": "The exact analysis artifact discharges this obligation.",
                        }
                        for obligation in card["assurance_contract"]["obligations"]
                    ],
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
                if "adverse_routing" in card:
                    payload["attack_learning"] = None
                return_path = Path(str(assignment["return_path"]))
                return_path.write_text(
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    encoding="utf-8",
                )
                return_sha = sha256_bytes(return_path.read_bytes())
                receipt = lifecycle.ingest_return(
                    round_id=round_status["round_id"],
                    assignment_id=assignment["assignment_id"],
                    worker_final_sha256=return_sha,
                )
                self.assertNotEqual(receipt.get("status"), "quarantined", receipt)
                result_ids[scope["target_node_id"]] = receipt["research_id"]

            writing = root / "output" / "revised.md"
            writing.parent.mkdir(parents=True, exist_ok=True)
            writing.write_text(
                "# Revised\n\nThe support and conclusion remain separately auditable.\n",
                encoding="utf-8",
            )
            writing_sha = sha256_bytes(writing.read_bytes())
            disposition_ids: dict[str, str] = {}
            failure_surfaces: dict[str, str] = {}
            for index, target_id in enumerate(plan["target_node_ids"], 1):
                surface_id = f"fs-{index}"
                failure_surfaces[target_id] = surface_id
                disposition = continuation.record_disposition(
                    plan_id,
                    {
                        "target_node_id": target_id,
                        "result_research_id": result_ids[target_id],
                        "outcome": "retained",
                        "rationale": "The target survives within its exact source closure.",
                        "successor_research_ids": [],
                        "dialectical_analysis": {
                            "issue": "Whether this target is warranted.",
                            "importance": "It bears an independent part of the argument.",
                            "burden_holder": "The proponent bears the burden.",
                            "plain_language_summary": (
                                "This target states one reason that can stand or fail alone."
                            ),
                            "technical_term_ledger": [],
                            "strongest_charitable_objection": (
                                "The closure may establish only a weaker conclusion."
                            ),
                            "response_or_revision": (
                                "The wording is bounded to what the closure establishes."
                            ),
                            "independent_failure_surfaces": [
                                {
                                    "surface_id": surface_id,
                                    "statement": "The target can fail while its peer survives.",
                                    "why_independent": (
                                        "Its source closure and inferential burden are distinct."
                                    ),
                                    "resolution": "Retained after bounded revision.",
                                }
                            ],
                        },
                        "writing_coverage": {
                            "status": "covered",
                            "artifact_path": writing.relative_to(root).as_posix(),
                            "artifact_sha256": writing_sha,
                            "section_ids": [f"revised-target-{index}"],
                            "rationale": "The target is explicit in the revised argument.",
                        },
                        "supersedes_disposition_id": "",
                    },
                    actor="main",
                )
                disposition_ids[target_id] = disposition["disposition_id"]

            complete = continuation.status(plan_id)
            self.assertTrue(complete["adequacy_complete"])
            self.assertEqual(
                complete["counts"],
                {
                    "total": 2,
                    "frontier_materialized": 2,
                    "researched": 2,
                    "dispositioned": 2,
                    "unresolved": 0,
                    "successor_mapped": 2,
                    "revised_manuscript_covered": 2,
                },
            )

            lemma = Fact(
                problem_id=store.project_id(),
                author="paper-candidate-producer",
                predecessors=[],
                statement="[CLAIM:LEMMA] The supporting lemma holds.",
                proof="Direct proof of the supporting lemma.",
            )
            use_anchor = f"[USE:{lemma.fact_id}:LEMMA:u1]"
            root_fact = Fact(
                problem_id=store.project_id(),
                author="paper-candidate-producer",
                predecessors=[lemma.fact_id],
                statement="[CLAIM:ROOT] The bounded paper theorem holds.",
                proof=f"Apply the supporting lemma {use_anchor}.",
                predecessor_uses=[
                    {
                        "fact_id": lemma.fact_id,
                        "clause_id": "LEMMA",
                        "use_anchor": use_anchor,
                        "used_conclusion": "The supporting lemma holds.",
                        "hypothesis_witnesses": [],
                        "convention_bridge": None,
                        "conclusion_transport": [],
                    }
                ],
            )
            facts = [lemma, root_fact]
            payload = self._release_payload(
                facts=facts,
                research_ids=list(result_ids.values()),
                granularity="paper_target_closure",
            )
            payload["artifacts"] = [
                {
                    "path": artifact.relative_to(root).as_posix(),
                    "sha256": artifact_sha,
                    "role": "paper_source",
                },
                {
                    "path": writing.relative_to(root).as_posix(),
                    "sha256": writing_sha,
                    "role": "paper_revised_writing",
                },
                *analysis_artifacts,
            ]
            payload["verification_plan"]["authorized_artifact_roles"] = [
                "paper_source",
                "paper_revised_writing",
                "paper_target_analysis",
            ]
            payload["verification_plan"]["required_checks"].extend(
                [
                    "research_obligation_evidence",
                    "paper_source_fidelity",
                    "paper_graph_structure",
                    "paper_audit",
                    "paper_target_coverage",
                    "paper_continuation_adequacy",
                    "philosophy_semantic_atomicity",
                    "philosophy_plain_language_clarity",
                ]
            )
            load_bearing = sorted(
                {
                    *plan["selected_reconstruction_node_ids"],
                    *plan["selected_source_node_ids"],
                }
            )
            claim_to_fact = {
                logic_ids["c1"]: lemma.fact_id,
                logic_ids["c-head"]: root_fact.fact_id,
            }
            payload["requested_assurance"] = {
                "validation_subject": {
                    "kind": "paper",
                    "subject_id": "fixture-paper",
                    "artifact_sha256": artifact_sha,
                    "load_bearing_node_ids": load_bearing,
                },
                "validation_granularity": "paper_target_closure",
                "coverage": [
                    (
                        {
                            "paper_node_id": node_id,
                            "disposition": "fact_bundle_member",
                            "fact_id": claim_to_fact[node_id],
                            "reason": "",
                        }
                        if node_id in claim_to_fact
                        else {
                            "paper_node_id": node_id,
                            "disposition": (
                                "source_only"
                                if node_id in plan["selected_source_node_ids"]
                                else "audit_only"
                            ),
                            "fact_id": None,
                            "reason": "Bound to the exact closure without direct Fact promotion.",
                        }
                    )
                    for node_id in load_bearing
                ],
            }

            def paper_ref(
                frozen: dict[str, object],
                *,
                graph_kind: str,
                target_node_ids: list[str],
            ) -> dict[str, object]:
                manifest_path = (
                    store.paper_logic().snapshots_dir
                    / str(frozen["snapshot_id"])
                    / "manifest.json"
                )
                return {
                    "paper_id": "fixture-paper",
                    "snapshot_id": frozen["snapshot_id"],
                    "snapshot_sha256": sha256_bytes(manifest_path.read_bytes()),
                    "graph_kind": graph_kind,
                    "target_artifact_sha256": artifact_sha,
                    "target_node_ids": target_node_ids,
                }

            payload["paper_evidence_refs"] = [
                paper_ref(
                    logic_frozen,
                    graph_kind="logic",
                    target_node_ids=load_bearing,
                ),
                paper_ref(
                    audit_frozen,
                    graph_kind="audit",
                    target_node_ids=[audit_ids["finding"]],
                ),
            ]
            payload["paper_continuation_ref"] = {
                "contract_revision": PAPER_CONTINUATION_CONTRACT_REVISION,
                "plan_id": plan_id,
                "plan_record_sha256": plan["record_sha256"],
                "adequacy_receipt_sha256": complete["adequacy_receipt_sha256"],
                "disposition_ids": complete["current_disposition_ids"],
            }
            target_by_claim = {
                unit["target_claim_node_id"]: unit["target_node_id"]
                for unit in plan["work_units"]
            }
            fact_target = {
                lemma.fact_id: target_by_claim[logic_ids["c1"]],
                root_fact.fact_id: target_by_claim[logic_ids["c-head"]],
            }
            conjunct_id = {
                lemma.fact_id: "conj-lemma",
                root_fact.fact_id: "conj-root",
            }
            payload["philosophy_atomicity"] = {
                "contract_revision": PHILOSOPHY_ATOMICITY_CONTRACT_REVISION,
                "plan_id": plan_id,
                "fact_units": [
                    {
                        "fact_id": fact.fact_id,
                        "primary_conclusion": fact.statement,
                        "plain_language_paraphrase": (
                            "The supporting reason holds."
                            if fact.fact_id == lemma.fact_id
                            else "The paper's bounded conclusion follows."
                        ),
                        "source_target_node_ids": [fact_target[fact.fact_id]],
                        "conjunct_ids": [conjunct_id[fact.fact_id]],
                        "defeasible_condition_ids": [],
                        "decomposition_rationale": (
                            "This Fact carries one independently challengeable conclusion."
                        ),
                    }
                    for fact in facts
                ],
                "conjunct_inventory": [
                    {
                        "conjunct_id": conjunct_id[fact.fact_id],
                        "statement": fact.statement,
                        "represented_by_fact_id": fact.fact_id,
                        "failure_surface_ids": [
                            failure_surfaces[fact_target[fact.fact_id]]
                        ],
                        "independence_rationale": (
                            "Its failure can be localized without replacing the peer Fact."
                        ),
                    }
                    for fact in facts
                ],
                "clarity_review": {
                    "plain_language_abstract": (
                        "The supporting reason and the conclusion are checked separately, "
                        "so failure of one part cannot be hidden inside a broad slogan."
                    ),
                    "technical_term_ledger": [],
                },
            }

            theorem_escape = copy.deepcopy(payload)
            theorem_escape["requested_assurance"] = {
                "validation_subject": {
                    "kind": "theorem",
                    "subject_id": root_fact.fact_id,
                    "artifact_sha256": None,
                    "load_bearing_node_ids": [],
                },
                "validation_granularity": "atomic_fact_dag",
                "coverage": [],
            }
            with self.assertRaisesRegex(ValueError, "paper_target_closure"):
                lifecycle.candidate_release(
                    theorem_escape, producer="paper-candidate-producer"
                )

            hidden_conjunct = copy.deepcopy(payload)
            hidden_conjunct["philosophy_atomicity"]["fact_units"][0][
                "conjunct_ids"
            ].append("conj-hidden")
            with self.assertRaisesRegex(ValueError, "exactly one independently"):
                lifecycle.candidate_release(
                    hidden_conjunct, producer="paper-candidate-producer"
                )

            opaque_paraphrase = copy.deepcopy(payload)
            opaque_paraphrase["philosophy_atomicity"]["fact_units"][0][
                "plain_language_paraphrase"
            ] = "[CLAIM:OPAQUE] Protocol jargon replaces the explanation."
            with self.assertRaisesRegex(ValueError, "machine protocol anchors"):
                lifecycle.candidate_release(
                    opaque_paraphrase, producer="paper-candidate-producer"
                )

            unreviewed_term = copy.deepcopy(payload)
            unreviewed_term["philosophy_atomicity"]["clarity_review"][
                "technical_term_ledger"
            ] = [
                {
                    "term": "dialectical foreclosure",
                    "plain_definition": "Ending a live objection without answering it.",
                    "necessity": "Names the exact failure being tested.",
                }
            ]
            with self.assertRaisesRegex(ValueError, "introduce no unreviewed jargon"):
                lifecycle.candidate_release(
                    unreviewed_term, producer="paper-candidate-producer"
                )

            missing_writing_authority = copy.deepcopy(payload)
            missing_writing_authority["verification_plan"][
                "authorized_artifact_roles"
            ].remove("paper_revised_writing")
            with self.assertRaisesRegex(ValueError, "paper_revised_writing"):
                lifecycle.candidate_release(
                    missing_writing_authority,
                    producer="paper-candidate-producer",
                )

            release_evidence_calls: list[str] = []
            original_release_evidence = PaperContinuationManager.release_evidence

            def counted_release_evidence(
                manager: PaperContinuationManager,
                *args: object,
                **kwargs: object,
            ) -> dict[str, object]:
                release_evidence_calls.append(manager.store.project_id())
                return original_release_evidence(manager, *args, **kwargs)

            with patch.object(
                PaperContinuationManager,
                "release_evidence",
                counted_release_evidence,
            ):
                release = lifecycle.candidate_release(
                    payload, producer="paper-candidate-producer"
                )
                capsule = lifecycle.verifier_capsule(release["release_id"])
            self.assertEqual(len(release_evidence_calls), 1)
            self.assertIn("paper_continuation_ref", release)
            self.assertIn("paper_continuation_release_capsule", release)
            self.assertNotIn("paper_continuation_evidence", release)
            continuation_capsule = release[
                "paper_continuation_release_capsule"
            ]
            self.assertEqual(
                continuation_capsule["status_proof"]["mode"], "indexed"
            )
            self.assertEqual(
                continuation_capsule["candidate_interfaces"],
                release["candidate_interfaces"],
            )
            self.assertEqual(
                len(continuation_capsule["evidence"]["dispositions"]),
                2,
            )
            self.assertEqual(
                release["requested_assurance"]["validation_granularity"],
                "paper_target_closure",
            )
            self.assertEqual(
                capsule["paper_continuation_release_capsule"]["capsule_id"],
                continuation_capsule["capsule_id"],
            )
            self.assertIn(
                "independently reconstruct the conjunct inventory",
                capsule["instructions"]["paper_continuation_boundary"],
            )
            self.assertIn(
                "reject undefined or unnecessary jargon",
                capsule["instructions"]["paper_continuation_boundary"],
            )
            self.assertEqual(
                {
                    artifact["artifact_sha256"]
                    for artifact in capsule["authorized_artifacts"]
                    if artifact["role"] == "paper_revised_writing"
                },
                {writing_sha},
            )
            operation_files_before_retry = sorted(
                continuation.release_operations_dir.glob("pcro-*.json")
            )
            repeated_release = lifecycle.candidate_release(
                payload, producer="paper-candidate-producer"
            )
            self.assertEqual(repeated_release["release_id"], release["release_id"])
            self.assertEqual(
                repeated_release["paper_continuation_release_capsule"][
                    "capsule_id"
                ],
                continuation_capsule["capsule_id"],
            )
            self.assertEqual(
                sorted(continuation.release_operations_dir.glob("pcro-*.json")),
                operation_files_before_retry,
            )

            corrected_target = plan["target_node_ids"][0]
            corrected = continuation.record_disposition(
                plan_id,
                {
                    "target_node_id": corrected_target,
                    "result_research_id": result_ids[corrected_target],
                    "outcome": "retained",
                    "rationale": "The target survives after a more precise objection analysis.",
                    "successor_research_ids": [],
                    "dialectical_analysis": {
                        "issue": "Whether the narrowed target remains warranted.",
                        "importance": "It bears an independent part of the argument.",
                        "burden_holder": "The proponent bears the burden.",
                        "plain_language_summary": (
                            "The corrected target now says only what its reason supports."
                        ),
                        "technical_term_ledger": [],
                        "strongest_charitable_objection": (
                            "The conclusion could still overstate the source premise."
                        ),
                        "response_or_revision": (
                            "The corrected wording preserves only the supported scope."
                        ),
                        "independent_failure_surfaces": [
                            {
                                "surface_id": failure_surfaces[corrected_target],
                                "statement": "The target can fail while its peer survives.",
                                "why_independent": (
                                    "Its source closure and inferential burden are distinct."
                                ),
                                "resolution": "Retained after corrected scope analysis.",
                            }
                        ],
                    },
                    "writing_coverage": {
                        "status": "covered",
                        "artifact_path": writing.relative_to(root).as_posix(),
                        "artifact_sha256": writing_sha,
                        "section_ids": ["revised-corrected-target"],
                        "rationale": "The corrected target remains explicit in the revision.",
                    },
                    "supersedes_disposition_id": disposition_ids[corrected_target],
                },
                actor="main",
            )
            self.assertNotEqual(
                corrected["disposition_id"], disposition_ids[corrected_target]
            )
            self.assertEqual(
                lifecycle.release(release["release_id"])["release_id"],
                release["release_id"],
            )
            with self.assertRaisesRegex(ValueError, "stale or incomplete"):
                lifecycle.verifier_capsule(release["release_id"])

            refreshed = continuation.status(plan_id)
            fresh_payload = copy.deepcopy(payload)
            fresh_payload["paper_continuation_ref"] = {
                "contract_revision": PAPER_CONTINUATION_CONTRACT_REVISION,
                "plan_id": plan_id,
                "plan_record_sha256": plan["record_sha256"],
                "adequacy_receipt_sha256": refreshed["adequacy_receipt_sha256"],
                "disposition_ids": refreshed["current_disposition_ids"],
            }
            continuation._status_index.head_path.unlink()
            fresh_release = lifecycle.candidate_release(
                fresh_payload, producer="paper-candidate-producer"
            )
            fallback_proof = fresh_release[
                "paper_continuation_release_capsule"
            ]["status_proof"]
            self.assertEqual(fallback_proof["mode"], "full_validation_fallback")
            self.assertEqual(
                fallback_proof["receipt"]["fallback_exception_count"], 1
            )
            self.assertTrue(
                fallback_proof["receipt"]["phase_timings_ms"][
                    "full_validation"
                ]
                >= 0
            )
            repeated_fallback_release = lifecycle.candidate_release(
                fresh_payload, producer="paper-candidate-producer"
            )
            self.assertEqual(
                repeated_fallback_release["release_id"],
                fresh_release["release_id"],
            )
            self.assertEqual(
                repeated_fallback_release[
                    "paper_continuation_release_capsule"
                ]["capsule_id"],
                fresh_release["paper_continuation_release_capsule"][
                    "capsule_id"
                ],
            )
            decision = lifecycle.certification_record(
                self._correct_decision_payload(lifecycle, fresh_release)
            )
            lifecycle.fact_admit(
                release_id=fresh_release["release_id"],
                decision_id=decision["decision_id"],
                gateway="independent-gateway",
            )
            self.assertEqual(set(store.fact_ids()), {lemma.fact_id, root_fact.fact_id})
            continuation.rebuild_status_index()
            self.assertTrue(store.audit().current_ok, store.audit().errors)

    def test_candidate_release_exact_field_error_is_publicly_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "v5-public-release-contract")
            with self.assertRaisesRegex(
                ValueError,
                r"missing=.*bundle_claim.*schema=references/paper_input_contracts.md",
            ):
                store.v5_lifecycle().candidate_release(
                    {}, producer="public-contract-producer"
                )

    def test_public_v5_worker_return_template_and_diagnostics_are_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "v5"
            store = self._store(root, "v5-public-worker-return")
            lifecycle = store.v5_lifecycle()
            research = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "Check one public worker-return obligation.",
                    "obligations": [
                        {
                            "obligation_id": "obl-public-contract",
                            "description": "Record one bounded public-contract check.",
                            "required_artifact_roles": [],
                            "evidence_types": ["bounded_argument"],
                            "not_applicable_allowed": False,
                        }
                    ],
                },
                actor="main",
            )
            round_status = lifecycle.create_round(
                workers=1,
                research_ids=[research["research_id"]],
            )
            assignment = round_status["assignments"][0]
            card = json.loads(
                Path(str(assignment["task_card_path"])).read_text(encoding="utf-8")
            )
            skill_root = Path(__file__).resolve().parents[1]
            template = json.loads(
                (
                    skill_root
                    / "assets"
                    / "worker_return.v5.assurance-no-adverse.template.json"
                ).read_text(encoding="utf-8")
            )
            template.update(
                {
                    "project_id": store.project_id(),
                    "round_id": round_status["round_id"],
                    "assignment_id": assignment["assignment_id"],
                    "worker_id": assignment["worker_id"],
                    "task_card_sha256": assignment["task_card_sha256"],
                    "blackboard_snapshot_sha256": assignment[
                        "blackboard_snapshot_sha256"
                    ],
                    "artifacts": [],
                    "obligation_dispositions": [
                        {
                            "obligation_id": item["obligation_id"],
                            "status": "complete",
                            "witness_artifact_sha256s": [],
                            "rationale": (
                                "This public non-artifact obligation is complete."
                            ),
                        }
                        for item in card["assurance_contract"]["obligations"]
                    ],
                }
            )
            if "adverse_routing" in card:
                template["attack_learning"] = None
            draft = base / "worker-return-draft.json"
            draft.write_text(
                json.dumps(template, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            valid = lifecycle.preflight_return(
                round_id=round_status["round_id"],
                assignment_id=assignment["assignment_id"],
                input_path=draft,
            )
            self.assertTrue(valid["valid"])
            prompt = Path(str(assignment["prompt_path"])).read_text(encoding="utf-8")
            self.assertIn("references/v5_worker_return_contract.md", prompt)

            help_text = StringIO()
            with redirect_stdout(help_text), self.assertRaises(SystemExit) as help_exit:
                cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "worker",
                        "preflight-return",
                        "--help",
                    ]
                )
            self.assertEqual(help_exit.exception.code, 0)
            self.assertIn("references/v5_worker_return_contract.md", help_text.getvalue())

            bad_top = copy.deepcopy(template)
            del bad_top["claim"]
            bad_top["commentary"] = "not an allowed return field"
            draft.write_text(
                json.dumps(bad_top, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                r"missing=.*claim.*unknown=.*commentary.*v5_worker_return_contract.md",
            ):
                lifecycle.preflight_return(
                    round_id=round_status["round_id"],
                    assignment_id=assignment["assignment_id"],
                    input_path=draft,
                )

            bad_disposition = copy.deepcopy(template)
            del bad_disposition["obligation_dispositions"][0]["rationale"]
            bad_disposition["obligation_dispositions"][0]["note"] = "unknown"
            draft.write_text(
                json.dumps(bad_disposition, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                r"missing=.*rationale.*unknown=.*note.*v5_worker_return_contract.md",
            ):
                lifecycle.preflight_return(
                    round_id=round_status["round_id"],
                    assignment_id=assignment["assignment_id"],
                    input_path=draft,
                )


if __name__ == "__main__":
    unittest.main()
