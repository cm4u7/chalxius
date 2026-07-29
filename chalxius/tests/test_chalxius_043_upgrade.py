from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from mathgraph.adoption import workload_profile_for_entry
from mathgraph.applicability import validate_external_refs_for_submission
from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.decision_preflight import validate_decision_against_capsule
from mathgraph.interfaces import (
    build_statement_interface,
    extract_geometric_objects,
    validate_predecessor_uses,
)
from mathgraph.model import Fact
from mathgraph.proof_lineage import statement_projection_sha256
from mathgraph.store import MathGraphStore
from mathgraph.v5_assurance import (
    V5_ASSURANCE_CONTRACT_REVISION,
    build_assurance_contract,
    validate_return_assurance,
)
from mathgraph.verifier_capsule import prepare_verifier_capsule
from tests.test_mathgraph import certified_result_ref


BASE_RELEASE_CHECKS = {
    "mathematical",
    "typing",
    "scope",
    "source_and_applicability",
    "predecessor_interfaces",
    "computation_replay",
    "challenge_dispositions",
    "assurance_scope",
}


class Chalxius043UpgradeTests(unittest.TestCase):
    def _store(self, root: Path, project_id: str = "upgrade-043") -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id=project_id,
            title="Chalxius 0.4.3 upgrade fixture",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _blank_research_assurance() -> dict[str, object]:
        return {
            "source_uses": [],
            "route_invalidations": [],
            "extremal_cases": [],
            "claim_strength": [],
            "contour_substitutions": [],
            "claimed_structures": [],
            "program_math_alignments": [],
        }

    @staticmethod
    def _source_v4_fixture(
        key: str = "SRC",
    ) -> tuple[dict[str, object], str, set[str]]:
        source_bytes = b"complete primary theorem bytes"
        source_sha = sha256_bytes(source_bytes)
        source_locator = "https://example.org/primary/theorem-v4.pdf"
        source_hypothesis = "X satisfies H."
        conclusion = "Every such X has property P."
        statement_text = (
            "Theorem 2.1. Hypothesis: X satisfies H. "
            "Conclusion: Every such X has property P."
        )

        response_hashes = {
            kind: sha256_bytes(f"frozen {kind} response".encode("utf-8"))
            for kind in (
                "version_history",
                "errata",
                "retraction_or_counterexample",
            )
        }
        issue_searches = []
        for kind, suffix, polarity in (
            (
                "version_history",
                "versions",
                "positive_version_or_erratum",
            ),
            ("errata", "errata", "negative_status_search"),
            (
                "retraction_or_counterexample",
                "status",
                "negative_status_search",
            ),
        ):
            issue_searches.append(
                {
                    "kind": kind,
                    "query": f"exact {kind} query",
                    "endpoint": f"https://example.org/api/{suffix}",
                    "locator": f"https://example.org/audit/{suffix}",
                    "queried_at": "2026-07-28T16:00:00Z",
                    "evidence_polarity": polarity,
                    "response_status": "200 OK",
                    "evidence_mode": "frozen_response",
                    "response_artifact_sha256": response_hashes[kind],
                    "live_query_capability": None,
                    "freshness_policy": "frozen on the Candidate date",
                    "finding": f"The exact {kind} query found no unresolved signal.",
                }
            )
        audit_core: dict[str, object] = {
            "artifact_sha256": source_sha,
            "artifact_locator": source_locator,
            "checked_at": "2026-07-28",
            "issue_searches": issue_searches,
            "unresolved_signals": [],
            "finding": "No unresolved version, erratum, or counterexample signal was found.",
        }
        source_audit = {**audit_core, "audit_sha256": sha256_json(audit_core)}

        applicability: dict[str, object] = {
            "source_version": "version 4, 2026-07-28",
            "source_locator": "Theorem 2.1, complete statement",
            "source_scope": "Objects X satisfying H.",
            "target_scope": "The same class of objects X satisfying H.",
            "source_conclusion": conclusion,
            "used_conclusion": conclusion,
            "hypothesis_map": [
                {
                    "source_hypothesis": source_hypothesis,
                    "target_witness": "The proof checks H for the target X.",
                    "source_coverage_id": "H1",
                    "proof_anchor": f"[APP:{key}:H1]",
                }
            ],
            "convention_map": [
                {
                    "source_convention": "The source writes the object as X.",
                    "target_convention": "The target writes the same object as X.",
                    "conversion_kind": "notation",
                    "proof_anchor": f"[APP:{key}:C1]",
                }
            ],
            "transport_obligations": [],
            "conclusion_map": [
                {
                    "conclusion_id": "R1",
                    "source_conclusion_span": conclusion,
                    "source_conclusion_span_sha256": sha256_bytes(
                        conclusion.encode("utf-8")
                    ),
                    "source_object_type": "object satisfying H",
                    "target_object_type": "object satisfying H",
                    "target_proof_anchor": f"[APP:{key}:R1]",
                    "transport_id": None,
                }
            ],
            "exclusions_checked": [
                "Adjacent definitions and exclusions were checked in the frozen source."
            ],
            "strength_comparison": "exact",
            "verdict": "direct",
            "proof_anchor": f"[APP:{key}:USE]",
        }

        def coverage(
            coverage_id: str,
            coverage_kind: str,
            applicability_text: str,
            span: str,
        ) -> dict[str, str]:
            return {
                "coverage_id": coverage_id,
                "coverage_kind": coverage_kind,
                "applicability_sha256": sha256_bytes(
                    applicability_text.encode("utf-8")
                ),
                "statement_span": span,
                "statement_span_sha256": sha256_bytes(span.encode("utf-8")),
            }

        ref: dict[str, object] = {
            "key": key,
            "title": "Complete primary theorem",
            "url": source_locator,
            "use_kind": "result",
            "cited_for": "The exact complete implication used by the proof.",
            "source_evidence_version": 4,
            "source_trace": {
                "artifact_sha256": source_sha,
                "artifact_locator": source_locator,
                "retrieved_at": "2026-07-28",
                "transcription_kind": "complete_statement_transcription",
                "statement_text": statement_text,
                "statement_sha256": sha256_bytes(statement_text.encode("utf-8")),
                "inspection_methods": ["rendered_primary"],
                "statement_coverage": [
                    coverage("H1", "source_hypothesis", source_hypothesis, source_hypothesis),
                    coverage(
                        "source_conclusion",
                        "source_conclusion",
                        conclusion,
                        conclusion,
                    ),
                    coverage(
                        "used_conclusion",
                        "used_conclusion",
                        conclusion,
                        conclusion,
                    ),
                ],
            },
            "critical_audit": {
                "profile": "baseline",
                "risk_triggers": [],
                "sanity_checks": [
                    {
                        "kind": "notation_and_binding",
                        "status": "pass",
                        "finding": "Every symbol is bound.",
                    },
                    {
                        "kind": "type_and_domain",
                        "status": "pass",
                        "finding": "The source and target object types agree.",
                    },
                    {
                        "kind": "quantifiers_and_scope",
                        "status": "pass",
                        "finding": "The universal scope is preserved.",
                    },
                ],
                "source_audit": source_audit,
                "source_audit_reuse": {
                    "mode": "fresh",
                    "reused_at": "2026-07-28",
                    "origin": "current_submission",
                },
                "assessment": "as_stated",
                "issues": [],
                "justification": "The structured source checks found no defect.",
                "proof_anchor": f"[CRIT:{key}:USE]",
                "status_summary": {
                    "pass": 3,
                    "issue": 0,
                    "fail": 0,
                    "not_applicable": 0,
                    "summary": "pass=3;issue=0;fail=0;not_applicable=0",
                },
            },
            "applicability": applicability,
        }
        proof = " ".join(
            (
                f"[APP:{key}:USE]",
                f"[APP:{key}:H1]",
                f"[APP:{key}:C1]",
                f"[APP:{key}:R1]",
                f"[CRIT:{key}:USE]",
            )
        )
        return ref, proof, {source_sha, *response_hashes.values()}

    def _assurance_fixture(
        self,
        logic_signals: list[str],
    ) -> tuple[
        dict[str, object],
        dict[str, object],
        list[dict[str, str]],
        dict[str, str],
    ]:
        roles = (
            "source",
            "toy",
            "bridge",
            "case",
            "domain",
            "forward",
            "inverse",
            "multiplicity",
            "negative",
        )
        hashes = {
            role: sha256_bytes(f"assurance fixture {role}".encode("utf-8"))
            for role in roles
        }
        artifacts = [
            {"name": f"{role}.txt", "role": role, "sha256": digest}
            for role, digest in hashes.items()
        ]
        contract = build_assurance_contract(
            entry={
                "claim": "Bounded assurance fixture.",
                "metadata": {"logic_signals": logic_signals},
            },
            obligations=[],
            work_mode="prove",
            related_artifacts=[],
        )
        payload: dict[str, object] = {
            "outcome": "insight",
            "obligation_dispositions": [],
            "computation_manifest": None,
            "research_assurance": self._blank_research_assurance(),
        }
        return contract, payload, artifacts, hashes

    def _write_noncomputational_return(
        self,
        store: MathGraphStore,
        assignment: dict[str, object],
        *,
        outcome: str = "insight",
        claim: str = "A bounded Research contribution is ready.",
    ) -> str:
        card = json.loads(
            Path(str(assignment["task_card_path"])).read_text(encoding="utf-8")
        )
        payload = {
            "schema_version": 5,
            "project_id": store.project_id(),
            "round_id": assignment["round_id"],
            "assignment_id": assignment["assignment_id"],
            "worker_id": assignment["worker_id"],
            "task_card_sha256": assignment["task_card_sha256"],
            "blackboard_snapshot_sha256": assignment[
                "blackboard_snapshot_sha256"
            ],
            "outcome": outcome,
            "claim": claim,
            "content": "The bounded Research argument is recorded as nontruth evidence.",
            "narrative": {
                "rationale": "Prepare a prospective Candidate input.",
                "summary": "Bounded Research result.",
                "intuition": "The task is deliberately small.",
                "limitations": "No Fact is created by this return.",
            },
            "artifacts": [],
            "obligation_dispositions": [
                {
                    "obligation_id": item["obligation_id"],
                    "status": "complete",
                    "witness_artifact_sha256s": [],
                    "rationale": "This non-computational fixture has no artifact role.",
                }
                for item in card["assurance_contract"]["obligations"]
            ],
            "computation_manifest": None,
            "research_assurance": self._blank_research_assurance(),
        }
        return_path = Path(str(assignment["return_path"]))
        return_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return sha256_bytes(return_path.read_bytes())

    @staticmethod
    def _release_payload(
        *,
        fact: Fact,
        research_id: str,
        required_checks: set[str] | None = None,
        successor_contracts: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": 5,
            "bundle_claim": fact.statement,
            "candidates": [fact.as_submission_dict()],
            "research_entry_ids": [research_id],
            "claim_relation": "proves",
            "artifacts": [],
            "verification_plan": {
                "mode": "closed_capsule",
                "authorized_artifact_roles": [],
                "required_checks": sorted(required_checks or BASE_RELEASE_CHECKS),
            },
            "requested_assurance": {
                "validation_subject": {
                    "kind": "theorem",
                    "subject_id": "bounded-theorem",
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
        if successor_contracts is not None:
            payload["successor_contracts"] = successor_contracts
        return payload

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
                {"check_id": item, "status": "pass", "findings": []}
                for item in capsule["required_checks"]
            ],
            "candidate_checks": [
                {"fact_id": item, "verdict": "correct", "findings": []}
                for item in capsule["fact_ids"]
            ],
            "edge_checks": [
                {
                    "predecessor_fact_id": edge[0],
                    "fact_id": edge[1],
                    "verdict": "correct",
                    "findings": [],
                }
                for edge in capsule["internal_edges"]
            ],
            "assurance_matrix": lifecycle._expected_assurance_matrix(release),
            "reviewer": "fresh-verifier-043",
            "host_attestation": {
                "host": "isolated-test-host",
                "agent_id": "fresh-verifier-043",
                "isolation": "fresh_context",
                "fork_turns": "none",
                "allowed_capsule_sha256": capsule["capsule_sha256"],
            },
        }

    def test_program_math_review_is_typed_gated_and_prioritized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", "program-math")
            store.adverse_routes().initialize(
                actor="operator",
                reason="Explicitly enable adverse Research review.",
            )
            workload = workload_profile_for_entry(
                {"kind": "computation", "suggested_actions": ["compute"]}
            )
            source = store.v5_lifecycle().add_research(
                {
                    "kind": "computation",
                    "claim": "Compute the coefficient from the displayed recurrence.",
                    "workload_profile": workload,
                },
                actor="main",
            )
            round_status = store.v5_lifecycle().create_round(
                workers=1,
                research_ids=[source["research_id"]],
                host_task_scope_id="program-math-host",
            )
            assignment = dict(round_status["assignments"][0])
            assignment["round_id"] = round_status["round_id"]
            card_path = Path(str(assignment["task_card_path"]))
            card_before = card_path.read_bytes()
            card = json.loads(card_before)
            self.assertEqual(card["work_mode"], "compute")
            self.assertNotIn("adverse_routing", card)
            self.assertTrue(card["assurance_contract"]["program_math_contract"]["required"])
            self.assertIn(
                "program_math_semantic_alignment",
                card["assurance_contract"]["risk_signals"],
            )

            artifact_dir = store.root / str(assignment["artifact_dir_relpath"])
            artifact_dir.mkdir(parents=True, exist_ok=True)
            source_path = artifact_dir / "program.py"
            output_path = artifact_dir / "output.json"
            witness_path = artifact_dir / "semantic-witness.json"
            independent_path = artifact_dir / "metamorphic-check.json"
            source_path.write_text(
                "# FORMULA_STAGE_1\nresult = sum(range(4))\n",
                encoding="utf-8",
            )
            output_path.write_text('{"result":6}\n', encoding="utf-8")
            witness_path.write_text(
                '{"domain":"0<=i<4","representation":"integer","order":"exact"}\n',
                encoding="utf-8",
            )
            independent_path.write_text(
                '{"metamorphic":"sum(0..3)=sum(0..2)+3","status":"pass"}\n',
                encoding="utf-8",
            )

            def artifact(path: Path, role: str) -> dict[str, str]:
                return {
                    "path": path.relative_to(store.root).as_posix(),
                    "sha256": sha256_bytes(path.read_bytes()),
                    "role": role,
                }

            artifacts = [
                artifact(source_path, "computation_source"),
                artifact(output_path, "computation_output"),
                artifact(witness_path, "semantic_witness"),
                artifact(independent_path, "independent_check"),
            ]
            hashes = {item["role"]: item["sha256"] for item in artifacts}
            obligation = card["assurance_contract"]["obligations"][0]
            formula = "c_3 = sum_{i=0}^{3} i"
            payload = {
                "schema_version": 5,
                "project_id": store.project_id(),
                "round_id": round_status["round_id"],
                "assignment_id": assignment["assignment_id"],
                "worker_id": assignment["worker_id"],
                "task_card_sha256": assignment["task_card_sha256"],
                "blackboard_snapshot_sha256": assignment[
                    "blackboard_snapshot_sha256"
                ],
                "outcome": "evidence",
                "claim": "The exact coefficient is 6.",
                "content": "The formula-code-output chain is recorded with exact witnesses.",
                "narrative": {
                    "rationale": "Exercise the semantic-alignment boundary.",
                    "summary": "Exact small coefficient.",
                    "intuition": "A finite sum provides a transparent fixture.",
                    "limitations": "This Research result is not a Fact.",
                },
                "artifacts": artifacts,
                "obligation_dispositions": [
                    {
                        "obligation_id": obligation["obligation_id"],
                        "status": "complete",
                        "witness_artifact_sha256s": [
                            hashes["computation_source"],
                            hashes["computation_output"],
                        ],
                        "rationale": "Exact source and output bytes are bound.",
                    }
                ],
                "computation_manifest": {
                    "stage_count": 1,
                    "entries": [
                        {
                            "obligation_id": obligation["obligation_id"],
                            "source_artifact_sha256": hashes[
                                "computation_source"
                            ],
                            "output_artifact_sha256": hashes[
                                "computation_output"
                            ],
                            "command": ["python3", "program.py"],
                            "runtime": {
                                "implementation": "CPython",
                                "version": "3.13",
                            },
                            "role": "supporting",
                            "manual_contract": "The loop implements the finite mathematical sum.",
                        }
                    ],
                },
                "research_assurance": {
                    **self._blank_research_assurance(),
                    "program_math_alignments": [
                        {
                            "stage_index": 1,
                            "obligation_id": obligation["obligation_id"],
                            "formula_projection": {
                                "formula_literal": formula,
                                "formula_sha256": sha256_json(formula),
                                "source_locator": "fixture recurrence, displayed formula",
                                "code_artifact_sha256": hashes[
                                    "computation_source"
                                ],
                                "code_anchor": "FORMULA_STAGE_1",
                                "sign_and_convention_map": [
                                    "inclusive mathematical upper bound 3 maps to Python range(4)"
                                ],
                            },
                            "domain_projection": {
                                "mathematical_domain": "integers i with 0 <= i <= 3",
                                "code_iteration_domain": "range(4)",
                                "boundary_cases": ["i=0", "i=3", "empty-prefix"],
                                "witness_artifact_sha256": hashes[
                                    "semantic_witness"
                                ],
                            },
                            "representation_projection": {
                                "mathematical_objects": ["integer coefficient"],
                                "code_types": ["Python int"],
                                "identity_and_multiplicity_policy": "Each index occurs exactly once.",
                                "witness_artifact_sha256": hashes[
                                    "semantic_witness"
                                ],
                            },
                            "approximation_budget": {
                                "mode": "exact",
                                "required_order": None,
                                "implemented_order": None,
                                "precision_or_error_bound": "Exact integer arithmetic; zero approximation error.",
                                "derivation_artifact_sha256": hashes[
                                    "semantic_witness"
                                ],
                            },
                            "output_interpretation": {
                                "output_artifact_sha256": hashes[
                                    "computation_output"
                                ],
                                "claimed_quantity": "coefficient c_3",
                                "units_and_conventions": "dimensionless, positive-sum convention",
                            },
                            "independent_checks": [
                                {
                                    "kind": "metamorphic_relation",
                                    "artifact_sha256": hashes[
                                        "independent_check"
                                    ],
                                    "finding": "Adding the endpoint 3 raises the prefix sum by 3.",
                                }
                            ],
                        }
                    ],
                },
            }
            return_path = Path(str(assignment["return_path"]))
            insufficient = copy.deepcopy(payload)
            insufficient["research_assurance"]["program_math_alignments"][0][
                "approximation_budget"
            ].update(
                {
                    "mode": "truncated",
                    "required_order": 5,
                    "implemented_order": 3,
                }
            )
            return_path.write_text(
                json.dumps(
                    insufficient,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "truncation order is insufficient"):
                store.v5_lifecycle().preflight_return(
                    round_id=round_status["round_id"],
                    assignment_id=assignment["assignment_id"],
                    input_path=return_path,
                )
            return_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            receipt = store.v5_lifecycle().ingest_return(
                round_id=round_status["round_id"],
                assignment_id=assignment["assignment_id"],
                worker_final_sha256=sha256_bytes(return_path.read_bytes()),
            )
            self.assertEqual(receipt["status"], "ingested")
            review_id = receipt["program_math_review_research_id"]
            self.assertEqual(card_before, card_path.read_bytes())
            self.assertEqual(store.v5_lifecycle().frontier(limit=1)[0]["research_id"], review_id)

            review_round = store.v5_lifecycle().create_round(
                workers=1,
                research_ids=[review_id],
                host_task_scope_id="program-math-host",
            )
            review_card = json.loads(
                Path(str(review_round["assignments"][0]["task_card_path"])).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(review_card["work_mode"], "refute")
            self.assertTrue(
                review_card["adverse_routing"]["scope_evidence"]["active"]
            )
            self.assertIn(
                "baseline_program_math_semantic_alignment",
                {
                    item["rule_id"]
                    for item in review_card["adverse_routing"]["baseline_rules"]
                },
            )
            self.assertNotIn("chx-", json.dumps(review_card).casefold())

            ordinary = store.v5_lifecycle().add_research(
                {
                    "kind": "challenge",
                    "claim": "Challenge a statement that merely mentions code.",
                },
                actor="main",
            )
            ordinary_round = store.v5_lifecycle().create_round(
                workers=1,
                research_ids=[ordinary["research_id"]],
            )
            ordinary_card = json.loads(
                Path(str(ordinary_round["assignments"][0]["task_card_path"])).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                len(ordinary_card["adverse_routing"]["baseline_rules"]), 8
            )
            self.assertFalse(
                ordinary_card["adverse_routing"]["scope_evidence"]["active"]
            )

    def test_v5_frontier_uses_four_dimensions_but_explicit_ids_remain_schedulable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", "v5-scoring")
            lifecycle = store.v5_lifecycle()
            low = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "Low-scored but still valid branch.",
                    "decision_profile": {
                        "impact": 0.0,
                        "information_value": 0.0,
                        "tractability": 0.0,
                        "burden": 1.0,
                    },
                },
                actor="main",
            )
            legacy = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "Legacy eight-metric branch.",
                    "priority": 0.8,
                    "novelty": 0.7,
                    "testability": 0.9,
                    "risk": 0.2,
                    "target_relevance": 0.9,
                    "decisiveness": 0.8,
                    "information_gain": 0.9,
                    "estimated_cost": 0.2,
                },
                actor="main",
            )
            high = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "High-scored future branch.",
                    "decision_profile": {
                        "impact": 1.0,
                        "information_value": 1.0,
                        "tractability": 1.0,
                        "burden": 0.0,
                    },
                },
                actor="main",
            )
            frontier = lifecycle.frontier(limit=10)
            self.assertEqual(frontier[0]["research_id"], high["research_id"])
            self.assertEqual(frontier[-1]["research_id"], low["research_id"])
            self.assertTrue(all(item["score_role"] == "priority_ordering_only" for item in frontier))
            legacy_record = lifecycle._research_record(legacy["research_id"])
            self.assertIn("priority", legacy_record["metadata"])
            self.assertNotIn("decision_profile", legacy_record["metadata"])

            explicit = lifecycle.create_round(
                workers=1,
                research_ids=[low["research_id"]],
            )
            self.assertEqual(
                explicit["assignments"][0]["research_id"], low["research_id"]
            )
            card_path = Path(str(explicit["assignments"][0]["task_card_path"]))
            frozen = card_path.read_bytes()
            lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "A still newer high-scored branch.",
                    "decision_profile": {
                        "impact": 1.0,
                        "information_value": 1.0,
                        "tractability": 1.0,
                        "burden": 0.0,
                    },
                },
                actor="main",
            )
            lifecycle.validate_task_card(
                json.loads(frozen), expected_path=card_path
            )
            self.assertEqual(frozen, card_path.read_bytes())

    def test_interface_only_successor_preserves_proof_and_capsule_separates_diffs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project", "proof-lineage")
            lifecycle = store.v5_lifecycle()
            predecessor_research = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "Prepare the original theorem."},
                actor="main",
            )
            predecessor = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement="[CLAIM:COLLAR] If H1, then the collar estimate holds.",
                proof=(
                    "Bound all cold factors on the chosen collar.\n\n"
                    "Inventory every stable pole of the full hot integrand before "
                    "deforming the contour."
                ),
            )
            predecessor_release = lifecycle.candidate_release(
                self._release_payload(
                    fact=predecessor,
                    research_id=predecessor_research["research_id"],
                ),
                producer="candidate-producer",
            )
            predecessor_decision = lifecycle.certification_record(
                self._correct_decision(lifecycle, predecessor_release)
            )
            lifecycle.fact_admit(
                release_id=predecessor_release["release_id"],
                decision_id=predecessor_decision["decision_id"],
                gateway="independent-gateway",
            )

            source = lifecycle.add_research(
                {
                    "kind": "repair",
                    "claim": "Add an explicit hypothesis label without rewriting the proof.",
                },
                actor="main",
            )
            round_status = lifecycle.create_round(
                workers=1,
                research_ids=[source["research_id"]],
            )
            assignment = dict(round_status["assignments"][0])
            assignment["round_id"] = round_status["round_id"]
            final_sha = self._write_noncomputational_return(
                store,
                assignment,
                claim="The labeled copy-on-write successor is ready.",
            )
            receipt = lifecycle.ingest_return(
                round_id=round_status["round_id"],
                assignment_id=assignment["assignment_id"],
                worker_final_sha256=final_sha,
            )
            self.assertEqual(receipt["status"], "ingested")
            successor = Fact(
                problem_id=store.project_id(),
                author=predecessor.author,
                predecessors=list(predecessor.predecessors),
                statement=(
                    "[CLAIM:COLLAR] [HYP:H1] If H1, then the collar estimate holds."
                ),
                proof=predecessor.proof,
            )
            predecessor_path = store.active_fact_path(predecessor.fact_id)
            contract = {
                "mode": "interface_only_successor",
                "predecessor_fact_id": predecessor.fact_id,
                "successor_fact_id": successor.fact_id,
                "predecessor_fact_sha256": sha256_bytes(
                    predecessor_path.read_bytes()
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
            required = {
                *BASE_RELEASE_CHECKS,
                "research_obligation_evidence",
                "proof_lineage_conservation",
            }
            weakened = copy.deepcopy(successor)
            weakened.proof = "Bound the cold factors and deform the contour."
            weakened.fact_id = weakened.computed_id
            weak_contract = copy.deepcopy(contract)
            weak_contract["successor_fact_id"] = weakened.fact_id
            weak_contract["successor_proof_sha256"] = sha256_bytes(
                weakened.proof.encode("utf-8")
            )
            with self.assertRaisesRegex(
                ValueError, "outside the statement/interface|proof bytes"
            ):
                lifecycle.candidate_release(
                    self._release_payload(
                        fact=weakened,
                        research_id=receipt["research_id"],
                        required_checks=required,
                        successor_contracts=[weak_contract],
                    ),
                    producer="candidate-producer",
                    preflight_only=True,
                )

            release = lifecycle.candidate_release(
                self._release_payload(
                    fact=successor,
                    research_id=receipt["research_id"],
                    required_checks=required,
                    successor_contracts=[contract],
                ),
                producer="candidate-producer",
            )
            self.assertFalse(
                release["successor_contracts"][0]["proof_diff"]["changed"]
            )
            capsule = lifecycle.verifier_capsule(release["release_id"])
            self.assertEqual(
                capsule["proof_diff_policy"]["display"],
                "statement_and_proof_diffs_separately",
            )
            self.assertEqual(
                capsule["successor_predecessor_packets"][0]["proof"],
                predecessor.proof,
            )

    def test_conditional_interface_and_geometric_stage_transport_fail_closed(self) -> None:
        fact = Fact(
            problem_id="interface-fixture",
            author="worker",
            predecessors=[],
            statement="[CLAIM:C] If H1, then the conclusion holds.",
            proof="Direct argument.",
        )
        digest = "0" * 64
        with self.assertRaisesRegex(ValueError, "explicit.*premise anchors"):
            build_statement_interface(
                fact=fact,
                stored_fact_sha256=digest,
                acceptance_event_sha256=digest,
                admission_review_id=digest,
                workflow_evidence_version=5,
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )

        source = Fact(
            problem_id="interface-fixture",
            author="worker",
            predecessors=[],
            statement=(
                "[CLAIM:G] The cycle "
                "[GEO:A;kind=cycle;stage=capped;ambient=C0;space=H_1;genus=h] "
                "is distinguished."
            ),
            proof="Direct geometric construction.",
        )
        source_interface = build_statement_interface(
            fact=source,
            stored_fact_sha256=digest,
            acceptance_event_sha256=digest,
            admission_review_id=digest,
            workflow_evidence_version=5,
            assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
        )
        target_statement = (
            "[CLAIM:T] The cycle "
            "[GEO:B;kind=cycle;stage=resewn;ambient=Cp;space=H_1;genus=h+1] "
            "is distinguished."
        )
        target_objects = extract_geometric_objects(target_statement)
        proof = f"[USE:{source.fact_id}:G:u] Apply the source. [TR:A] Reseaming identifies the cycles."
        use = {
            "fact_id": source.fact_id,
            "clause_id": "G",
            "use_anchor": f"[USE:{source.fact_id}:G:u]",
            "used_conclusion": "The source cycle is distinguished.",
            "hypothesis_witnesses": [],
            "convention_bridge": None,
            "conclusion_transport": [
                {
                    "source_object_id": "A",
                    "target_object_id": "B",
                    "operation": "identity",
                    "proof_anchor": f"[USE:{source.fact_id}:G:u]",
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "identity requires identical stage"):
            validate_predecessor_uses(
                [use],
                predecessors=[source.fact_id],
                proof=proof,
                interface_lookup=lambda _: source_interface,
                convention_profile_ids=[],
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
                target_typed_objects=target_objects,
            )
        use["conclusion_transport"][0] = {
            "source_object_id": "A",
            "target_object_id": "B",
            "operation": "resewing",
            "proof_anchor": "[TR:A]",
        }
        validate_predecessor_uses(
            [use],
            predecessors=[source.fact_id],
            proof=proof,
            interface_lookup=lambda _: source_interface,
            convention_profile_ids=[],
            assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            target_typed_objects=target_objects,
        )

    def test_source_v4_closes_status_coverage_query_and_transport_bypasses(self) -> None:
        ref, proof, artifact_hashes = self._source_v4_fixture()
        validate_external_refs_for_submission(
            [ref],
            proof,
            require_critical_audit=True,
            required_source_evidence_version=4,
            artifact_hashes=artifact_hashes,
        )

        incomplete = copy.deepcopy(ref)
        incomplete["source_trace"]["statement_coverage"] = [
            item
            for item in incomplete["source_trace"]["statement_coverage"]
            if item["coverage_id"] != "H1"
        ]
        with self.assertRaisesRegex(ValueError, "statement_coverage is incomplete"):
            validate_external_refs_for_submission(
                [incomplete],
                proof,
                require_critical_audit=True,
                required_source_evidence_version=4,
                artifact_hashes=artifact_hashes,
            )

        missing_query_bytes = set(artifact_hashes)
        missing_query_bytes.remove(
            ref["critical_audit"]["source_audit"]["issue_searches"][0][
                "response_artifact_sha256"
            ]
        )
        with self.assertRaisesRegex(ValueError, "authorized Candidate artifact"):
            validate_external_refs_for_submission(
                [ref],
                proof,
                require_critical_audit=True,
                required_source_evidence_version=4,
                artifact_hashes=missing_query_bytes,
            )

        transported_without_proof = copy.deepcopy(ref)
        transported_without_proof["applicability"]["conclusion_map"][0][
            "target_object_type"
        ] = "relative family of objects"
        with self.assertRaisesRegex(ValueError, "transport_id is required"):
            validate_external_refs_for_submission(
                [transported_without_proof],
                proof,
                require_critical_audit=True,
                required_source_evidence_version=4,
                artifact_hashes=artifact_hashes,
            )

        smuggled_bridge = copy.deepcopy(ref)
        smuggled_bridge["applicability"]["convention_map"][0][
            "target_convention"
        ] = "The separated space duality equals ordinary duality."
        with self.assertRaisesRegex(ValueError, "mathematical bridge"):
            validate_external_refs_for_submission(
                [smuggled_bridge],
                proof,
                require_critical_audit=True,
                required_source_evidence_version=4,
                artifact_hashes=artifact_hashes,
            )

        contradictory = copy.deepcopy(ref)
        audit = contradictory["critical_audit"]
        audit["profile"] = "strict"
        audit["risk_triggers"] = ["suspected_source_defect"]
        audit["sanity_checks"].extend(
            [
                {
                    "kind": "boundary_or_toy_case",
                    "status": "pass",
                    "finding": "The boundary case is stable.",
                },
                {
                    "kind": "statement_proof_consistency",
                    "status": "pass",
                    "finding": "The statement and proof have the same conclusion.",
                },
            ]
        )
        audit["sanity_checks"][0]["status"] = "issue"
        audit["assessment"] = "minor_typo_corrected"
        audit["issues"] = [
            {
                "kind": "typo",
                "source_text": "property P",
                "corrected_text": "property P (corrected notation)",
                "evidence": "The complete frozen page resolves the notation.",
                "impact": "non_semantic",
                "proof_anchor": "[CRIT:SRC:ISSUE1]",
            }
        ]
        audit["justification"] = "All checks pass."
        audit["status_summary"] = {
            "pass": 4,
            "issue": 1,
            "fail": 0,
            "not_applicable": 0,
            "summary": "pass=4;issue=1;fail=0;not_applicable=0",
        }
        proof_with_issue = proof + " [CRIT:SRC:ISSUE1]"
        with self.assertRaisesRegex(ValueError, "narrative contradicts"):
            validate_external_refs_for_submission(
                [contradictory],
                proof_with_issue,
                require_critical_audit=True,
                required_source_evidence_version=4,
                artifact_hashes=artifact_hashes,
            )

        failed = copy.deepcopy(contradictory)
        failed_audit = failed["critical_audit"]
        failed_audit["sanity_checks"][0]["status"] = "fail"
        failed_audit["justification"] = "One structured source check fails."
        failed_audit["status_summary"] = {
            "pass": 4,
            "issue": 0,
            "fail": 1,
            "not_applicable": 0,
            "summary": "pass=4;issue=0;fail=1;not_applicable=0",
        }
        with self.assertRaisesRegex(ValueError, "structured failed source check"):
            validate_external_refs_for_submission(
                [failed],
                proof_with_issue,
                require_critical_audit=True,
                required_source_evidence_version=4,
                artifact_hashes=artifact_hashes,
            )

        first = certified_result_ref("A")
        second = certified_result_ref("B")
        first["source_trace"]["statement_locator"] = "wrong A locator"
        second["source_trace"]["statement_locator"] = "wrong B locator"
        with self.assertRaises(ValueError) as mismatch:
            validate_external_refs_for_submission([first, second], "unused")
        message = str(mismatch.exception)
        self.assertIn("/external_refs/0", message)
        self.assertIn("/external_refs/1", message)

    def test_research_assurance_closes_formula_topology_contour_and_structure_gaps(self) -> None:
        contract, payload, artifacts, hashes = self._assurance_fixture(
            ["formula_use"]
        )
        with self.assertRaisesRegex(ValueError, "formula source-use"):
            validate_return_assurance(
                payload=payload,
                contract=contract,
                artifacts=artifacts,
            )
        payload["research_assurance"]["source_uses"] = [
            {
                "source_key": "F",
                "use_kind": "formula",
                "source_strength": "fixed_object",
                "target_strength": "fixed_object",
                "source_artifact_sha256": hashes["source"],
                "toy_check_artifact_sha256": hashes["toy"],
                "bridge_artifact_sha256s": [],
            }
        ]
        validate_return_assurance(
            payload=payload,
            contract=contract,
            artifacts=artifacts,
        )

        bridge_contract, bridge_payload, bridge_artifacts, bridge_hashes = (
            self._assurance_fixture(["fixed_to_family"])
        )
        bridge_payload["research_assurance"]["source_uses"] = [
            {
                "source_key": "R",
                "use_kind": "result",
                "source_strength": "fixed_object",
                "target_strength": "relative_family",
                "source_artifact_sha256": bridge_hashes["source"],
                "toy_check_artifact_sha256": None,
                "bridge_artifact_sha256s": [],
            }
        ]
        with self.assertRaisesRegex(ValueError, "requires a bridge artifact"):
            validate_return_assurance(
                payload=bridge_payload,
                contract=bridge_contract,
                artifacts=bridge_artifacts,
            )
        bridge_payload["research_assurance"]["source_uses"][0][
            "bridge_artifact_sha256s"
        ] = [bridge_hashes["bridge"]]
        validate_return_assurance(
            payload=bridge_payload,
            contract=bridge_contract,
            artifacts=bridge_artifacts,
        )

        topology_contract, topology_payload, topology_artifacts, _ = (
            self._assurance_fixture(["topology"])
        )
        with self.assertRaisesRegex(ValueError, "omits extremal cases"):
            validate_return_assurance(
                payload=topology_payload,
                contract=topology_contract,
                artifacts=topology_artifacts,
            )
        topology_payload["research_assurance"]["extremal_cases"] = [
            {
                "case_id": case_id,
                "status": "pass",
                "witness_artifact_sha256s": [],
                "finding": f"The {case_id} case was checked explicitly.",
            }
            for case_id in (
                "genus_zero_left",
                "genus_zero_right",
                "both_positive_genus",
                "empty_inherited_cycles",
                "disc_bounding_cycle",
            )
        ]
        topology_payload["research_assurance"]["claim_strength"] = [
            {
                "claim_id": "twist",
                "claimed_strength": "essential Dehn twist",
                "downstream_required_strength": "essential Dehn twist",
                "comparison": "equal",
                "disposition": "retained",
                "rationale": "The downstream theorem uses exactly this strength.",
            }
        ]
        validate_return_assurance(
            payload=topology_payload,
            contract=topology_contract,
            artifacts=topology_artifacts,
        )

        contour_contract, contour_payload, contour_artifacts, _ = (
            self._assurance_fixture(["moving_poles"])
        )
        contour = {
            "source_contour": "C_0",
            "target_contour": "C_t",
            "swept_region": "The annulus swept for 0 <= t <= epsilon.",
            "poles": [
                {
                    "pole_id": "distinguished",
                    "multiplicity": 1,
                    "parameter_behavior": "Remains near the marked point.",
                    "disposition": "distinguished",
                },
                {
                    "pole_id": "hidden",
                    "multiplicity": 1,
                    "parameter_behavior": "Moves into the swept annulus.",
                    "disposition": "retained_additional_residue",
                },
            ],
            "crossed_pole_ids": ["hidden"],
            "uniform_noncollision_witness": "A uniform chart controls the marked pole.",
            "residue_accounting": "distinguished_is_complete_enclosed_sum",
            "degeneration_test": {
                "family": "t -> 0",
                "boundary_behavior": "Bounded on the outer boundary.",
                "interior_zero_behavior": "The hidden pole enters the interior.",
                "result": "The hidden residue must be retained.",
            },
        }
        contour_payload["research_assurance"]["contour_substitutions"] = [contour]
        with self.assertRaisesRegex(ValueError, "crossing or retaining additional poles"):
            validate_return_assurance(
                payload=contour_payload,
                contract=contour_contract,
                artifacts=contour_artifacts,
            )
        contour["residue_accounting"] = "all_additional_residues_retained"
        validate_return_assurance(
            payload=contour_payload,
            contract=contour_contract,
            artifacts=contour_artifacts,
        )

        structure_contract, structure_payload, structure_artifacts, structure_hashes = (
            self._assurance_fixture(["claimed_involution"])
        )
        with self.assertRaisesRegex(ValueError, "constructor record"):
            validate_return_assurance(
                payload=structure_payload,
                contract=structure_contract,
                artifacts=structure_artifacts,
            )
        structure_payload["research_assurance"]["claimed_structures"] = [
            {
                "kind": "involution",
                "domain_artifact_sha256": structure_hashes["domain"],
                "forward_map_artifact_sha256": structure_hashes["forward"],
                "inverse_map_artifact_sha256": structure_hashes["inverse"],
                "multiplicity_artifact_sha256": structure_hashes["multiplicity"],
                "negative_control_artifact_sha256": structure_hashes["negative"],
                "typed_record_fields": ["occurrence_identity", "multiplicity"],
                "automorphism_controls": [
                    "Retain orbit identity before comparing numerical values."
                ],
                "value_free": True,
            }
        ]
        validate_return_assurance(
            payload=structure_payload,
            contract=structure_contract,
            artifacts=structure_artifacts,
        )

    def test_v5_neutral_capsule_materializer_and_decision_preflight_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root / "project", "neutral-capsule")
            lifecycle = store.v5_lifecycle()
            source = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "Prepare a bounded theorem."},
                actor="main",
            )
            round_status = lifecycle.create_round(
                workers=1,
                research_ids=[source["research_id"]],
            )
            assignment = dict(round_status["assignments"][0])
            assignment["round_id"] = round_status["round_id"]
            final_sha = self._write_noncomputational_return(store, assignment)
            receipt = lifecycle.ingest_return(
                round_id=round_status["round_id"],
                assignment_id=assignment["assignment_id"],
                worker_final_sha256=final_sha,
            )
            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement="[CLAIM:B] The bounded theorem holds.",
                proof="A direct bounded argument proves the statement.",
            )
            release = lifecycle.candidate_release(
                self._release_payload(
                    fact=fact,
                    research_id=receipt["research_id"],
                    required_checks={
                        *BASE_RELEASE_CHECKS,
                        "research_obligation_evidence",
                    },
                ),
                producer="candidate-producer",
            )

            capsule_root = root / "neutral-capsule"
            materialized = prepare_verifier_capsule(
                project_root=store.root,
                release_id=release["release_id"],
                capsule_root=capsule_root,
            )
            for expected in (
                capsule_root / "input" / "capsule.json",
                capsule_root / "input" / "decision-template.json",
                capsule_root / "host" / "validate_decision.py",
                capsule_root / "host" / "transport-manifest.json",
                Path(materialized["host_capability_path"]),
            ):
                self.assertTrue(expected.is_file())

            capsule = json.loads(
                (capsule_root / "input" / "capsule.json").read_text(
                    encoding="utf-8"
                )
            )
            decision = self._correct_decision(lifecycle, release)
            result = validate_decision_against_capsule(decision, capsule)
            self.assertTrue(result["valid"])
            review_path = Path(materialized["review_return_path"])
            review_path.write_text(
                json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )

            malformed = copy.deepcopy(decision)
            malformed["check_results"][0]["check"] = malformed["check_results"][0].pop(
                "check_id"
            )
            with self.assertRaisesRegex(ValueError, "/check_results/0"):
                validate_decision_against_capsule(malformed, capsule)

            existing_empty = root / "existing-empty"
            existing_empty.mkdir()
            os.chmod(existing_empty, 0o700)
            second = prepare_verifier_capsule(
                project_root=store.root,
                capsule_id=capsule["capsule_id"],
                capsule_root=existing_empty,
            )
            self.assertTrue(Path(second["decision_validator_path"]).is_file())

            nonempty = root / "nonempty"
            nonempty.mkdir()
            os.chmod(nonempty, 0o700)
            (nonempty / "keep.txt").write_text("occupied", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be empty"):
                prepare_verifier_capsule(
                    project_root=store.root,
                    release_id=release["release_id"],
                    capsule_root=nonempty,
                )

            forged = copy.deepcopy(capsule)
            forged["authorized_artifacts"].append(
                {
                    "artifact_sha256": "0" * 64,
                    "name": "unauthorized.txt",
                    "role": "unauthorized",
                    "sealed_relpath": "governance/unauthorized.txt",
                }
            )
            semantic = {
                key: value
                for key, value in forged.items()
                if key not in {"capsule_id", "capsule_sha256"}
            }
            forged_sha = sha256_json(semantic)
            forged["capsule_sha256"] = forged_sha
            forged["capsule_id"] = "capsule-" + forged_sha
            forged_path = root / "forged-capsule.json"
            forged_path.write_text(
                json.dumps(forged, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "does not exactly equal"):
                prepare_verifier_capsule(
                    project_root=store.root,
                    capsule_json=forged_path,
                    capsule_root=root / "forged-output",
                )


if __name__ == "__main__":
    unittest.main()
