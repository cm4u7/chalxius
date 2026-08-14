from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.contracts import sha256_bytes
from mathgraph.interfaces import SEMANTIC_INTERFACE_REVISION
from mathgraph.model import Fact
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import V5_ASSURANCE_CONTRACT_REVISION


class CandidatePreflightWorkEliminationTests(unittest.TestCase):
    def _store(self, root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="candidate-preflight-work-elimination",
            title="Candidate preflight work elimination",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _fact(project_id: str) -> Fact:
        return Fact(
            problem_id=project_id,
            author="candidate-producer",
            predecessors=[],
            statement="[CLAIM:ROOT] The bounded claim holds.",
            proof="Direct proof.",
        )

    @staticmethod
    def _payload(fact: Fact, granularity: str) -> dict[str, object]:
        return {
            "schema_version": 5,
            "bundle_claim": fact.statement,
            "candidates": [fact.as_submission_dict()],
            "research_entry_ids": ["a" * 12],
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
                "validation_granularity": granularity,
                "coverage": [],
            },
            "challenge_dispositions": [],
            "paper_evidence_refs": [],
            "adverse_actor_ids": [],
        }

    def test_singleton_atomic_shape_fails_before_research_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            payload = self._payload(
                self._fact(store.project_id()), "atomic_fact_dag"
            )
            with patch.object(
                lifecycle,
                "_inspection_research_record",
                side_effect=AssertionError("global Research replay began"),
            ) as research_lookup:
                with self.assertRaisesRegex(
                    ValueError,
                    "atomic_fact_dag requires multiple candidates and an internal edge",
                ):
                    lifecycle.candidate_release(
                        payload,
                        producer="candidate-producer",
                        preflight_only=True,
                    )
            research_lookup.assert_not_called()

    def test_valid_singleton_shape_continues_to_authoritative_research_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            payload = self._payload(
                self._fact(store.project_id()), "monolithic_theorem"
            )
            with patch.object(
                lifecycle,
                "_research_record_envelope",
                side_effect=KeyError("Research envelope lookup reached"),
            ) as envelope_lookup:
                with self.assertRaisesRegex(
                    KeyError, "Research envelope lookup reached"
                ):
                    lifecycle.candidate_release(
                        payload,
                        producer="candidate-producer",
                        preflight_only=True,
                    )
            envelope_lookup.assert_called_once()

    def test_multi_claim_candidate_fails_before_research_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement=(
                    "[CLAIM:ROOT] The root theorem holds.\n\n"
                    "[CLAIM:COROLLARY] A separable corollary also holds."
                ),
                proof="Prove the theorem and then the separable corollary.",
            )
            payload = self._payload(fact, "monolithic_theorem")
            with patch.object(
                lifecycle,
                "_research_record_envelope",
                side_effect=AssertionError("Research replay began"),
            ) as envelope_lookup:
                with self.assertRaisesRegex(
                    ValueError,
                    "exactly one semantic conclusion atom",
                ):
                    lifecycle.candidate_release(
                        payload,
                        producer="candidate-producer",
                        preflight_only=True,
                    )
            envelope_lookup.assert_not_called()

    def test_explicit_semantic_interface_keeps_one_conclusion_with_premise_clause(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            premise = "[HYP:H1] Assume the bounded premise."
            conclusion = "Under H1, the bounded conclusion holds."
            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement=(
                    f"[CLAIM:PREMISE] {premise}\n\n"
                    f"[CLAIM:CONCLUSION] {conclusion}"
                ),
                proof="Use H1 to obtain the bounded conclusion.",
                semantic_interface=[
                    {
                        "interface_revision": SEMANTIC_INTERFACE_REVISION,
                        "domain_profile": "mathematics",
                        "clause_id": "PREMISE",
                        "component_id": "component-premise",
                        "component_kind": "premise",
                        "statement": premise,
                        "statement_sha256": sha256_bytes(premise.encode("utf-8")),
                        "operators": [],
                        "hypotheses": [
                            {
                                "hypothesis_id": "H1",
                                "statement": "Assume the bounded premise.",
                                "modality": "assumed",
                                "quantifier_scope": "the fixed object",
                                "temporal_scope": "the proof instance",
                                "applicability_scope": "the bounded conclusion",
                            }
                        ],
                        "typed_objects": [],
                        "qualifiers": [],
                        "comparison": None,
                        "source_component_ids": [],
                        "failure_mode_ids": [],
                    },
                    {
                        "interface_revision": SEMANTIC_INTERFACE_REVISION,
                        "domain_profile": "mathematics",
                        "clause_id": "CONCLUSION",
                        "component_id": "component-conclusion",
                        "component_kind": "conclusion",
                        "statement": conclusion,
                        "statement_sha256": sha256_bytes(conclusion.encode("utf-8")),
                        "operators": [
                            {
                                "operator_id": "op-conditional",
                                "kind": "conditional",
                                "value": "under H1",
                                "scope": "the bounded conclusion",
                                "depends_on": [],
                            }
                        ],
                        "hypotheses": [
                            {
                                "hypothesis_id": "H1",
                                "statement": "Assume the bounded premise.",
                                "modality": "assumed",
                                "quantifier_scope": "the fixed object",
                                "temporal_scope": "the proof instance",
                                "applicability_scope": "the bounded conclusion",
                            }
                        ],
                        "typed_objects": [],
                        "qualifiers": [],
                        "comparison": None,
                        "source_component_ids": ["component-premise"],
                        "failure_mode_ids": [],
                    },
                ],
            )
            payload = self._payload(fact, "monolithic_theorem")
            with patch.object(
                lifecycle,
                "_research_record_envelope",
                side_effect=KeyError("Research envelope lookup reached"),
            ) as envelope_lookup:
                with self.assertRaisesRegex(
                    KeyError,
                    "Research envelope lookup reached",
                ):
                    lifecycle.candidate_release(
                        payload,
                        producer="candidate-producer",
                        preflight_only=True,
                    )
            envelope_lookup.assert_called_once()

    def test_manual_research_never_inventories_supervision_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            manual_record = {
                "research_id": "b" * 12,
                "metadata": {},
            }
            with patch.object(
                lifecycle,
                "_round_manifest",
                side_effect=AssertionError("historical round inventory began"),
            ) as round_lookup:
                self.assertEqual(
                    lifecycle._required_supervision_results_for_candidate(
                        [manual_record]
                    ),
                    set(),
                )
            round_lookup.assert_not_called()

    @staticmethod
    def _current_research(lifecycle: object) -> dict[str, object]:
        return lifecycle.add_research(  # type: ignore[attr-defined]
            {
                "kind": "direction",
                "status": "open",
                "claim": "The bounded conditional Candidate is ready for review.",
                "content": "The exact Candidate statement is the review target.",
                "rationale": "Exercise the early statement-interface boundary.",
                "source": "",
                "artifacts": [],
                "source_dependent": False,
                "route_invalidations": [],
                "logic_signals": [],
                "obligation_dispositions": [],
                "computation_manifest": [],
                "research_assurance": {"scope": "bounded theorem"},
            },
            actor="researcher",
            assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
        )

    def test_missing_premise_anchor_fails_before_full_research_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            research = self._current_research(lifecycle)
            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement=(
                    "[CLAIM:ROOT] If the bounded premise holds, then the "
                    "conclusion holds."
                ),
                proof="Apply the bounded premise.",
            )
            payload = self._payload(fact, "monolithic_theorem")
            payload["research_entry_ids"] = [research["research_id"]]
            with patch.object(
                lifecycle,
                "_inspection_research_record",
                side_effect=AssertionError("full Research replay began"),
            ) as research_lookup:
                with self.assertRaisesRegex(
                    ValueError,
                    "must export explicit .* premise anchors",
                ):
                    lifecycle.candidate_release(
                        payload,
                        producer="candidate-producer",
                        preflight_only=True,
                    )
            research_lookup.assert_not_called()

    def test_language_neutral_interface_passes_early_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            research = self._current_research(lifecycle)
            clause = (
                "If the bounded premise holds, then the conclusion holds."
            )
            semantic_interface = [
                {
                    "interface_revision": SEMANTIC_INTERFACE_REVISION,
                    "domain_profile": "mathematics",
                    "clause_id": "ROOT",
                    "component_id": "component-root",
                    "component_kind": "conclusion",
                    "statement": clause,
                    "statement_sha256": sha256_bytes(
                        clause.encode("utf-8")
                    ),
                    "operators": [
                        {
                            "operator_id": "op-conditional",
                            "kind": "conditional",
                            "value": "if-then",
                            "scope": "the exact bounded clause",
                            "depends_on": [],
                        }
                    ],
                    "hypotheses": [
                        {
                            "hypothesis_id": "H1",
                            "statement": "The bounded premise holds.",
                            "modality": "assumed",
                            "quantifier_scope": "the fixed object",
                            "temporal_scope": "the proof instance",
                            "applicability_scope": "the exact bounded clause",
                        }
                    ],
                    "typed_objects": [],
                    "qualifiers": [],
                    "comparison": None,
                    "source_component_ids": [],
                    "failure_mode_ids": [],
                }
            ]
            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement=f"[CLAIM:ROOT] {clause}",
                proof="Apply the bounded premise.",
                semantic_interface=semantic_interface,
            )
            payload = self._payload(fact, "monolithic_theorem")
            payload["research_entry_ids"] = [research["research_id"]]
            with patch.object(
                lifecycle,
                "_inspection_research_record",
                side_effect=KeyError("authoritative Research lookup reached"),
            ) as research_lookup:
                with self.assertRaisesRegex(
                    KeyError, "authoritative Research lookup reached"
                ):
                    lifecycle.candidate_release(
                        payload,
                        producer="candidate-producer",
                        preflight_only=True,
                    )
            research_lookup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
