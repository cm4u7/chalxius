from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import random
import tempfile
import unittest
from pathlib import Path

from mathgraph.paper_logic_contracts import (
    validate_inference,
    validate_operator_ledger,
    validate_source_unit,
)
from mathgraph.paper_research_pipeline import (
    EVIDENCE_GATE_REVISION,
    PaperPipelineError,
    build_ordered_paper_frontier,
    build_pipeline_receipt,
    materialize_native_research_draft_successor,
    normalize_delta_receipt,
    normalize_pdf_layout,
    sha256_bytes,
    sha256_json,
    stable_identity_merge,
    validate_atomic_paper_dag,
    validate_evidence_receipt,
    validate_ordered_paper_frontier,
    validate_paper_graph_semantics,
    validate_successor_receipt,
    verify_evidence_registry,
)
from mathgraph.paper_research_reliability import (
    MUTATION_CATEGORIES,
    run_paper_research_reliability_matrix,
)


_PUBLIC_PIPELINE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "paper_research_pipeline.py"
)
_PUBLIC_PIPELINE_SPEC = importlib.util.spec_from_file_location(
    "chalxius_public_paper_research_pipeline", _PUBLIC_PIPELINE_PATH
)
assert _PUBLIC_PIPELINE_SPEC is not None and _PUBLIC_PIPELINE_SPEC.loader is not None
_PUBLIC_PIPELINE = importlib.util.module_from_spec(_PUBLIC_PIPELINE_SPEC)
_PUBLIC_PIPELINE_SPEC.loader.exec_module(_PUBLIC_PIPELINE)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _graph(source_text: str = "Source premise.") -> dict:
    component = {
        "component_id": "pc-1",
        "exact_span": {
            "start": 0,
            "end": len(source_text),
            "text": source_text,
            "text_sha256": _sha(source_text),
        },
        "mapped_node_ids": ["p1"],
        "disposition": "represented",
        "reason": "",
        "composition_witness": "single exact span",
    }
    nodes = [
        {
            "local_id": "s1",
            "object_type": "source_unit",
            "payload": {"text": source_text, "proposition_inventory": [component]},
        },
        {
            "local_id": "p1",
            "object_type": "claim",
            "payload": {
                "statement": "P1",
                "statement_sha256": _sha("P1"),
                "discourse_role": "premise",
                "modality": "asserted",
                "content_type": "conceptual",
            },
        },
        {
            "local_id": "p2",
            "object_type": "claim",
            "payload": {
                "statement": "P2",
                "statement_sha256": _sha("P2"),
                "discourse_role": "premise",
                "modality": "asserted",
                "content_type": "empirical",
            },
        },
        {
            "local_id": "c1",
            "object_type": "claim",
            "payload": {
                "statement": "C",
                "statement_sha256": _sha("C"),
                "discourse_role": "headline_conclusion",
                "modality": "conditional",
                "content_type": "normative",
            },
        },
        {
            "local_id": "i1",
            "object_type": "inference",
            "payload": {
                "premise_ids": ["p1", "p2"],
                "bridge_claim_ids": [],
                "defeater_claim_ids": [],
                "conclusion_id": "c1",
                "inference_kind": "normative_bridge",
                "strength": "defeasible",
            },
        },
        {
            "local_id": "t1",
            "object_type": "paper_target",
            "payload": {"claim_id": "c1", "target_role": "headline"},
        },
    ]
    return {
        "schema_version": 1,
        "feature_revision": "paper-logic-1",
        "project_id": "paper-pipeline-fixture",
        "paper_id": "draft-1",
        "graph_kind": "logic",
        "domain_profile": "philosophy",
        "builder": "fixture",
        "builder_context_id": "fixture-context",
        "source": {
            "artifact_sha256": "0" * 64,
            "artifact_locator": "draft.txt",
            "title": "Draft",
            "version": "1",
            "mime_type": "text/plain",
            "retrieved_at": "2026-08-02T00:00:00Z",
        },
        "source_role": "research_draft",
        "base_snapshot_id": "",
        "supersedes_snapshot_id": "",
        "coverage": {
            "scope_kind": "full_artifact",
            "units": ["s1"],
            "included_locators": ["draft.txt"],
            "excluded_locators": [],
            "unresolved_load_bearing_units": [],
            "completeness_claim": "fixture complete",
        },
        "nodes": nodes,
        "edges": [
            {
                "source": "__source__",
                "target": "s1",
                "relation_type": "contains",
                "payload": {"order": 0},
            },
            {"source": "p1", "target": "s1", "relation_type": "anchors", "payload": {}},
            {"source": "p1", "target": "i1", "relation_type": "premise_of", "payload": {"position": 0}},
            {"source": "p2", "target": "i1", "relation_type": "premise_of", "payload": {"position": 1}},
            {"source": "i1", "target": "c1", "relation_type": "concludes", "payload": {}},
            {"source": "t1", "target": "c1", "relation_type": "targets", "payload": {"role": "headline"}},
        ],
    }


def _dag() -> dict:
    def row(claim_id: str, statement: str, predecessors: list[str]) -> dict:
        return {
            "claim_id": claim_id,
            "paper_claim_id": claim_id,
            "inherited_paper_object_ids": [claim_id],
            "statement": statement,
            "statement_sha256": _sha(statement),
            "predecessor_ids": predecessors,
            "independent_failure_surface": f"Independent failure of {claim_id}",
            "truth_effect": "none_until_gateway_admission",
        }

    return {
        "schema_version": 1,
        "project_id": "paper-pipeline-fixture",
        "paper_id": "draft-1",
        "source_role": "research_draft",
        "validation_subject": {
            "kind": "paper",
            "paper_id": "draft-1",
            "source_role": "research_draft",
        },
        "nodes": [row("p1", "P1", []), row("p2", "P2", []), row("c1", "C", ["p1", "p2"])],
        "dependency_edges": [
            {"source_claim_id": "p1", "target_claim_id": "c1"},
            {"source_claim_id": "p2", "target_claim_id": "c1"},
        ],
        "topological_order": ["p1", "p2", "c1"],
    }


def _continuity(domain_profile: str = "philosophy") -> dict:
    common = {
        "schema_version": 1,
        "contract_revision": "chalxius-research-continuity-1",
        "domain_profile": domain_profile,
        "required_claim_ids": ["c1"],
        "forbidden_claim_ids": [],
        "target_revision_authorized": False,
    }
    if domain_profile == "philosophy":
        return {
            **common,
            "continuity_mode": "argumentative_stance",
            "declared_target": "Preserve the conditional restorative stance.",
            "permitted_resolution_statuses": ["preserved", "strengthened"],
            "domain_invariants": {
                "headline_claim_ids": ["c1"],
                "argumentative_direction": "conditional_restorative_defense",
            },
        }
    if domain_profile == "mathematics":
        return {
            **common,
            "continuity_mode": "mathematical_target",
            "declared_target": "Determine whether C follows from P1 and P2.",
            "permitted_resolution_statuses": [
                "proved",
                "disproved",
                "unresolved_with_obstruction",
            ],
            "domain_invariants": {
                "target_claim_ids": ["c1"],
                "hypothesis_claim_ids": ["p1", "p2"],
                "quantifier_scope_claim_ids": [],
            },
        }
    if domain_profile == "empirical":
        return {
            **common,
            "continuity_mode": "empirical_target",
            "declared_target": "Estimate the declared effect without changing scope.",
            "permitted_resolution_statuses": [
                "supported",
                "disconfirmed",
                "inconclusive",
            ],
            "domain_invariants": {
                "target_claim_ids": ["c1"],
                "research_question": "Does the exposure change the outcome?",
                "estimand": "average treatment effect",
                "population": "declared study population",
                "exposure_or_intervention": "declared intervention",
                "outcome": "declared outcome",
                "scope": "declared design and follow-up window",
            },
        }
    return {
        **common,
        "continuity_mode": "mixed_target",
        "declared_target": "Resolve the declared mixed-domain target componentwise.",
        "permitted_resolution_statuses": [
            "componentwise_resolved",
            "partially_resolved",
            "unresolved_with_obstruction",
        ],
        "domain_invariants": {
            "target_claim_ids": ["c1"],
            "component_modes": ["argumentative_stance", "empirical_target"],
        },
    }


def _mathematical_progress() -> dict:
    target = "Determine whether C follows from P1 and P2."
    domain = "All objects in the exact declared class."
    target_policy = {
        "contract_revision": "chalxius-mathematical-target-policy-1",
        "exact_target_statement": target,
        "exact_target_statement_sha256": _sha(target),
        "target_claim_ids": ["c1"],
        "hypothesis_claim_ids": ["p1", "p2"],
        "domain_bindings": [
            {
                "binding_id": "domain-main",
                "exact_domain": domain,
                "exact_domain_sha256": _sha(domain),
                "source_claim_ids": ["p1", "p2"],
            }
        ],
        "quantifier_bindings": [],
        "permitted_exact_target_outcomes": [
            "proved",
            "disproved",
            "unresolved_with_obstruction",
        ],
        "target_revision_requires_operator_authorization": True,
        "partial_progress_policy": "typed_refinement_dag_keeps_exact_target_open",
    }
    added = "Additional compactness hypothesis H."
    weak_statement = "Under P1, P2, and H, conclusion C holds."
    refinement = {
        "schema_version": 1,
        "contract_revision": "chalxius-mathematical-refinement-dag-1",
        "root_target": {
            "root_id": "exact-target-root",
            "exact_target_statement_sha256": _sha(target),
            "target_claim_ids": ["c1"],
            "hypothesis_claim_ids": ["p1", "p2"],
            "domain_bindings_sha256": sha256_json(target_policy["domain_bindings"]),
            "quantifier_bindings_sha256": sha256_json([]),
            "resolution_status": "unresolved_with_obstruction",
            "resolution_evidence_ids": [],
            "obstruction": "The proof uses H, which is absent from the exact target.",
            "original_target_open": True,
        },
        "nodes": [
            {
                "node_id": "weak-with-H",
                "node_type": "added_hypothesis_theorem",
                "statement": weak_statement,
                "statement_sha256": _sha(weak_statement),
                "resolution_status": "proved",
                "evidence_ids": ["proof-weak-with-H"],
                "obstruction": "",
                "logical_relation_to_original": "stronger_hypotheses_than_original",
                "refinement_mapping_relation": "weakened_from",
                "candidate_fact_id_or_null": "a" * 16,
                "hypothesis_deltas": [
                    {
                        "dimension": "hypothesis",
                        "binding_id": "hypothesis-H",
                        "before": "",
                        "before_sha256": _sha(""),
                        "after": added,
                        "after_sha256": _sha(added),
                        "change_type": "added",
                        "rationale": "H is exactly the additional sufficient hypothesis.",
                    }
                ],
                "domain_deltas": [],
                "quantifier_deltas": [],
                "conclusion_strength_deltas": [],
                "remaining_gap_to_exact_target": "Remove H without weakening C.",
                "truth_effect": "none",
            }
        ],
        "edges": [
            {
                "parent_id": "exact-target-root",
                "child_id": "weak-with-H",
                "relation": "refines_toward_exact_target",
            }
        ],
        "topological_order": ["exact-target-root", "weak-with-H"],
        "truth_effect": "none",
    }
    return {"target_policy": target_policy, "refinement_dag": refinement}


def _synthetic_evidence_receipt(frontier_id: str) -> dict:
    semantic = {
        "schema_version": 1,
        "contract_revision": EVIDENCE_GATE_REVISION,
        "paper_frontier_id": frontier_id,
        "counts": {"sources": 1, "claims": 1, "substantive_claims": 1},
        "sources": [{"source_key": "fixture", "payload_sha256": "1" * 64}],
        "claims": [
            {
                "claim_id": "fixture-evidence",
                "support_kind": "direct_text",
                "witness_sha256": "2" * 64,
            }
        ],
        "normalization_profile": "corroborated-layout-dehyphen-v2",
        "authority_boundary": {
            "truth_effect": "none",
            "paper_authority_effect": "none",
            "fact_effect": "none",
        },
    }
    return {
        **semantic,
        "evidence_receipt_id": "pev-" + sha256_json(semantic),
    }


class PaperResearchPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._project_temporary = tempfile.TemporaryDirectory()
        self.project_root = Path(self._project_temporary.name)

    def tearDown(self) -> None:
        self._project_temporary.cleanup()

    def test_frontier_preserves_premise_order_and_rejects_position_drift(self) -> None:
        graph = _graph()
        frontier = build_ordered_paper_frontier(graph, headline_claim_ids=["c1"])
        self.assertEqual(frontier["inference_frontier"][0]["premise_ids"], ["p1", "p2"])
        self.assertEqual(frontier["counts"]["work_units"], 4)
        validate_ordered_paper_frontier(graph, frontier)

        mutated = copy.deepcopy(graph)
        premise_edges = [
            edge for edge in mutated["edges"] if edge["relation_type"] == "premise_of"
        ]
        premise_edges[0]["payload"]["position"] = 1
        premise_edges[1]["payload"]["position"] = 0
        with self.assertRaisesRegex(PaperPipelineError, "premise edge order"):
            validate_paper_graph_semantics(mutated)

    def test_permutation_mutation_matrix_fails_closed(self) -> None:
        graph = _graph()
        rng = random.Random(7319)
        for _ in range(80):
            mutated = copy.deepcopy(graph)
            inference = next(
                node for node in mutated["nodes"] if node["local_id"] == "i1"
            )
            rng.shuffle(inference["payload"]["premise_ids"])
            if inference["payload"]["premise_ids"] == ["p1", "p2"]:
                continue
            with self.assertRaises(PaperPipelineError):
                validate_paper_graph_semantics(mutated)

    def test_represented_component_requires_mapping_and_composition_witness(self) -> None:
        graph = _graph()
        component = graph["nodes"][0]["payload"]["proposition_inventory"][0]
        component["mapped_node_ids"] = []
        with self.assertRaisesRegex(PaperPipelineError, "represented without graph mapping"):
            validate_paper_graph_semantics(graph)
        graph = _graph()
        graph["nodes"][0]["payload"]["proposition_inventory"][0]["composition_witness"] = ""
        with self.assertRaisesRegex(PaperPipelineError, "composition witness"):
            validate_paper_graph_semantics(graph)

    def test_component_hierarchy_is_optional_but_cycles_fail(self) -> None:
        graph = _graph()
        inventory = graph["nodes"][0]["payload"]["proposition_inventory"]
        parent = copy.deepcopy(inventory[0])
        parent["component_id"] = "pc-parent"
        parent["mapped_node_ids"] = ["p1"]
        inventory[0]["parent_component_id"] = "pc-parent"
        inventory.append(parent)
        self.assertEqual(validate_paper_graph_semantics(graph)["hierarchy_links"], 1)
        parent["parent_component_id"] = "pc-1"
        with self.assertRaisesRegex(PaperPipelineError, "hierarchy cycle"):
            validate_paper_graph_semantics(graph)

    def test_inherited_pipeline_is_domain_general_across_draft_profiles(self) -> None:
        for domain_profile in ("philosophy", "mathematics", "empirical", "mixed"):
            with self.subTest(domain_profile=domain_profile):
                graph = _graph()
                graph["domain_profile"] = domain_profile
                frontier = build_ordered_paper_frontier(
                    graph, headline_claim_ids=["c1"]
                )
                self.assertEqual(frontier["counts"]["claims"], 3)
                bundle, receipt = materialize_native_research_draft_successor(
                    graph,
                    actor="main",
                    builder_context_id=f"domain-{domain_profile}",
                    activation_record={
                        "activation_policy": "prospective_only",
                        "source_role": "research_draft",
                        "authority_effect": "none",
                        "truth_effect": "none",
                    },
                    project_root=self.project_root,
                )
                self.assertEqual(bundle["domain_profile"], domain_profile)
                self.assertEqual(receipt["truth_effect"], "none")

    def test_mathematics_preserves_target_and_allows_proof_or_disproof(self) -> None:
        graph = _graph()
        graph["domain_profile"] = "mathematics"
        frontier = build_ordered_paper_frontier(graph, headline_claim_ids=["c1"])
        status = validate_atomic_paper_dag(
            graph=graph,
            frontier=frontier,
            dag=_dag(),
            continuity_contract=_continuity("mathematics"),
        )
        continuity = status["research_continuity"]
        self.assertEqual(continuity["continuity_mode"], "mathematical_target")
        self.assertEqual(
            set(continuity["permitted_resolution_statuses"]),
            {"proved", "disproved", "unresolved_with_obstruction"},
        )
        self.assertNotIn("declared_stance_sha256", status)

        philosophy = _continuity("philosophy")
        with self.assertRaisesRegex(PaperPipelineError, "domain/profile substitution"):
            validate_atomic_paper_dag(
                graph=graph,
                frontier=frontier,
                dag=_dag(),
                continuity_contract=philosophy,
            )

        changed_target = _continuity("mathematics")
        changed_target["domain_invariants"]["target_claim_ids"] = ["p1"]
        with self.assertRaisesRegex(PaperPipelineError, "outside required claim closure"):
            validate_atomic_paper_dag(
                graph=graph,
                frontier=frontier,
                dag=_dag(),
                continuity_contract=changed_target,
            )

    def test_public_mathematics_preflight_keeps_weaker_result_non_closing(self) -> None:
        graph = _graph()
        graph["domain_profile"] = "mathematics"
        frontier = build_ordered_paper_frontier(graph, headline_claim_ids=["c1"])
        receipt = _PUBLIC_PIPELINE.build_cli_pipeline_receipt(
            graph=graph,
            frontier=frontier,
            dag=_dag(),
            continuity_contract=_continuity("mathematics"),
            mathematical_progress=_mathematical_progress(),
            evidence_receipt=None,
            successor_receipt=None,
        )
        progress = receipt["domain_progress_binding"]
        self.assertEqual(
            receipt["contract_revision"],
            _PUBLIC_PIPELINE.CLI_PIPELINE_RECEIPT_REVISION,
        )
        self.assertTrue(progress["original_target_open"])
        self.assertEqual(progress["progress_class"], "partial_verified_progress")
        self.assertFalse(progress["weakening_closes_exact_target"])
        self.assertFalse(progress["stance_preservation_required"])
        self.assertTrue(receipt["native_pipeline_receipt_id"].startswith("ppr-"))

    def test_public_mathematics_preflight_requires_progress_and_rejects_wrong_domain(self) -> None:
        graph = _graph()
        graph["domain_profile"] = "mathematics"
        with self.assertRaisesRegex(ValueError, "requires an exact target"):
            _PUBLIC_PIPELINE.build_cli_pipeline_receipt(
                graph=graph,
                frontier=build_ordered_paper_frontier(
                    graph, headline_claim_ids=["c1"]
                ),
                dag=_dag(),
                continuity_contract=_continuity("mathematics"),
                mathematical_progress=None,
                evidence_receipt=None,
                successor_receipt=None,
            )

        philosophy = _graph()
        with self.assertRaisesRegex(ValueError, "not applicable"):
            _PUBLIC_PIPELINE.build_cli_pipeline_receipt(
                graph=philosophy,
                frontier=build_ordered_paper_frontier(
                    philosophy, headline_claim_ids=["c1"]
                ),
                dag=_dag(),
                continuity_contract=_continuity("philosophy"),
                mathematical_progress=_mathematical_progress(),
                evidence_receipt=None,
                successor_receipt=None,
            )

    def test_mathematical_progress_tamper_matrix_fails_closed(self) -> None:
        graph = _graph()
        graph["domain_profile"] = "mathematics"
        continuity = _continuity("mathematics")
        for label, mutate, expected in (
            (
                "weak-result-closes-root",
                lambda value: value["refinement_dag"]["root_target"].update(
                    {"original_target_open": False}
                ),
                "must stay open",
            ),
            (
                "target-substitution",
                lambda value: value["target_policy"].update(
                    {
                        "exact_target_statement": "Resolve a different theorem.",
                        "exact_target_statement_sha256": _sha(
                            "Resolve a different theorem."
                        ),
                    }
                ),
                "drifts from research continuity",
            ),
            (
                "delta-hash-drift",
                lambda value: value["refinement_dag"]["nodes"][0][
                    "hypothesis_deltas"
                ][0].update({"after_sha256": "0" * 64}),
                "SHA-256 drifted",
            ),
        ):
            with self.subTest(label=label):
                progress = _mathematical_progress()
                mutate(progress)
                with self.assertRaisesRegex(ValueError, expected):
                    _PUBLIC_PIPELINE.validate_mathematical_progress_input(
                        graph=graph,
                        dag=_dag(),
                        continuity_contract=continuity,
                        progress_input=progress,
                    )

    def test_normalized_mathematical_refinement_is_revalidatable_and_tamper_evident(self) -> None:
        progress = _mathematical_progress()
        policy = _PUBLIC_PIPELINE.validate_mathematical_target_policy(
            progress["target_policy"],
            available_claim_ids={"p1", "p2", "c1"},
            exact_target_claim_ids={"c1"},
        )
        normalized = _PUBLIC_PIPELINE.validate_mathematical_refinement_dag(
            progress["refinement_dag"], target_policy=policy
        )
        self.assertEqual(
            _PUBLIC_PIPELINE.validate_mathematical_refinement_dag(
                normalized, target_policy=policy
            ),
            normalized,
        )
        normalized["progress_class"] = "exact_target_resolved"
        with self.assertRaisesRegex(ValueError, "summary drifted"):
            _PUBLIC_PIPELINE.validate_mathematical_refinement_dag(
                normalized, target_policy=policy
            )

    def test_reliability_matrix_is_domain_general_and_kills_every_mutation(self) -> None:
        for domain_profile in ("philosophy", "mathematics", "empirical", "mixed"):
            with self.subTest(domain_profile=domain_profile):
                graph = _graph()
                graph["domain_profile"] = domain_profile
                frontier = build_ordered_paper_frontier(
                    graph, headline_claim_ids=["c1"]
                )
                _, successor_receipt = materialize_native_research_draft_successor(
                    graph,
                    actor="main",
                    builder_context_id=f"matrix-{domain_profile}",
                    activation_record={
                        "activation_policy": "prospective_only",
                        "source_role": "research_draft",
                        "authority_effect": "none",
                        "truth_effect": "none",
                    },
                    project_root=self.project_root,
                )
                report = run_paper_research_reliability_matrix(
                    graph=graph,
                    frontier=frontier,
                    dag=_dag(),
                    continuity_contract=_continuity(domain_profile),
                    evidence_receipt=_synthetic_evidence_receipt(
                        frontier["frontier_id"]
                    ),
                    successor_receipt=successor_receipt,
                    mutations=60,
                    seed=7319,
                )
                self.assertTrue(report["ok"])
                self.assertEqual(report["mutations_killed"], 60)
                self.assertEqual(set(report["category_results"]), set(MUTATION_CATEGORIES))

    def test_native_successor_is_copy_on_write_and_hashes_all_dropped_metadata(self) -> None:
        graph = _graph()
        graph["semantic_overlay"] = {"edge_ids": ["e1"], "truth_effect": "none"}
        original = copy.deepcopy(graph)
        bundle, receipt = materialize_native_research_draft_successor(
            graph,
            actor="main",
            builder_context_id="successor-fixture",
            activation_record={
                "activation_policy": "prospective_only",
                "source_role": "research_draft",
                "authority_effect": "none",
                "truth_effect": "none",
            },
            project_root=self.project_root,
        )
        self.assertEqual(graph, original)
        self.assertEqual(
            [node["local_id"] for node in bundle["nodes"]],
            [node["local_id"] for node in graph["nodes"]],
        )
        self.assertEqual(bundle["edges"], graph["edges"])
        self.assertEqual(bundle["source_role"], "research_draft")
        source = next(node for node in bundle["nodes"] if node["local_id"] == "s1")
        component = source["payload"]["proposition_inventory"][0]
        self.assertEqual(component["component_level"], "atom")
        self.assertEqual(component["partition_path"], ["s1", "pc-1"])
        inference = next(node for node in bundle["nodes"] if node["local_id"] == "i1")
        self.assertEqual(inference["payload"]["semantic_operation"], "normative_bridge")
        self.assertIn("semantic_overlay", receipt["dropped_non_native_top_level_metadata"])
        self.assertGreater(
            receipt["source_component_and_inference_materialization"]["transformed_node_count"],
            0,
        )
        self.assertFalse(receipt["historical_rewrite"])
        self.assertFalse(receipt["inherited_fact_authority"])

    def test_native_successor_materializes_source_occurrences_outside_operator_ledger(self) -> None:
        graph = _graph("Possibly source premise.")
        graph["nodes"][0]["payload"]["operator_ledger"] = []
        component = graph["nodes"][0]["payload"]["proposition_inventory"][0]
        component["composition_witness"] += (
            '\nCHX-038 source-total occurrence dispositions: '
            '[{"end": 8, "kind": "modality", "start": 0, "token": "Possibly"}]'
        )
        bundle, receipt = materialize_native_research_draft_successor(
            graph,
            actor="main",
            builder_context_id="successor-occurrence-fixture",
            activation_record={
                "activation_policy": "prospective_only",
                "source_role": "research_draft",
                "authority_effect": "none",
                "truth_effect": "none",
            },
            project_root=self.project_root,
        )
        source = next(node for node in bundle["nodes"] if node["local_id"] == "s1")
        self.assertEqual(source["payload"]["operator_ledger"], [])
        self.assertEqual(
            source["payload"]["source_occurrence_ledger"][0]["token"],
            "Possibly",
        )
        self.assertEqual(
            receipt["source_component_and_inference_materialization"]
            ["source_occurrence_record_count"],
            1,
        )

    def test_source_occurrence_ledger_is_exact_and_tamper_evident(self) -> None:
        text = "plain source"
        payload = {
            "unit_kind": "sentence",
            "order": 0,
            "locator": {
                "kind": "other",
                "pdf_page_index": -1,
                "printed_page_label": "",
                "region": "fixture:1",
            },
            "text": text,
            "text_sha256": _sha(text),
            "speaker": "author",
            "inspection_methods": ["plain_text"],
            "render_sha256": "",
            "context_before": "",
            "context_after": "",
            "operator_ledger": [],
            "source_occurrence_ledger": [
                {
                    "occurrence_id": "occ-plain",
                    "token": "plain",
                    "start": 0,
                    "end": 5,
                    "kind": "discourse_marker",
                    "disposition": "context_only",
                    "scope": "Exact unit-local occurrence only.",
                }
            ],
        }
        self.assertEqual(validate_source_unit(payload, "source-fixture"), payload)
        mutated = copy.deepcopy(payload)
        mutated["source_occurrence_ledger"][0]["end"] = 6
        with self.assertRaisesRegex(ValueError, "exact source-unit occurrence"):
            validate_source_unit(mutated, "source-fixture")

    def test_semantic_operation_cannot_masquerade_as_normative_bridge(self) -> None:
        normative = {
            "premise_ids": ["p1", "bridge-1"],
            "conclusion_id": "c1",
            "inference_kind": "normative_bridge",
            "strength": "defeasible",
            "authorial_status": "researcher_reconstructed",
            "source_unit_ids": [],
            "bridge_claim_ids": ["bridge-1"],
            "defeater_claim_ids": [],
            "rationale": "Explicit normative bridge fixture.",
            "semantic_operation": "relation_materialization",
        }
        with self.assertRaisesRegex(ValueError, "retain its semantic operation"):
            validate_inference(normative, "inference-fixture")
        relabelled = copy.deepcopy(normative)
        relabelled["inference_kind"] = "causal"
        relabelled["bridge_claim_ids"] = []
        relabelled["premise_ids"] = ["p1"]
        relabelled["semantic_operation"] = "normative_bridge"
        with self.assertRaisesRegex(ValueError, "acquire normative-bridge authority"):
            validate_inference(relabelled, "inference-fixture")

    def test_stable_identity_merge_rejects_semantic_collision(self) -> None:
        base = [{"id": "x", "value": 1}]
        self.assertEqual(stable_identity_merge(base, base, identity_field="id"), base)
        with self.assertRaisesRegex(PaperPipelineError, "semantic drift"):
            stable_identity_merge(base, [{"id": "x", "value": 2}], identity_field="id")

    def test_delta_dialects_normalize_to_one_ir(self) -> None:
        first = normalize_delta_receipt(
            {
                "delta_id": "d1",
                "base_binding": "b1",
                "added_node_ids": ["n1"],
                "retired_node_ids": ["n0"],
                "added_edge_ids": ["e1"],
                "identity_redirects": {"n0": "n1"},
            }
        )
        second = normalize_delta_receipt(
            {
                "receipt_id": "d1",
                "base_snapshot_id": "b1",
                "fresh_node_spec_ids": ["n1"],
                "removed_active_node_lineage": ["n0"],
                "declared_new_edge_ids": ["e1"],
                "node_id_map": {"n0": "n1"},
            }
        )
        for key in (
            "delta_id",
            "base_binding",
            "added_node_ids",
            "retired_node_ids",
            "added_edge_ids",
            "identity_redirects",
        ):
            self.assertEqual(first[key], second[key])

    def test_pdf_normalization_preserves_inline_compounds(self) -> None:
        text = "well-being remains; trans-\nformative choice"
        self.assertEqual(
            normalize_pdf_layout(text),
            "well-being remains; transformative choice",
        )
        gapped = "trans -\nformative"
        self.assertEqual(normalize_pdf_layout(gapped, "trans-\nformative"), "transformative")
        self.assertEqual(normalize_pdf_layout("A-\nHeading"), "A-\nHeading")

    def test_open_world_operator_is_exactly_anchored_as_other(self) -> None:
        ledger = [
            {
                "operator_id": "op-1",
                "token": "provided that",
                "occurrence": 0,
                "kind": "other",
                "scope": "producer-observed conditional surface",
                "disposition": "logical",
                "depends_on": [],
            }
        ]
        self.assertEqual(
            validate_operator_ledger(
                ledger, text="provided that P, Q", label="open-world"
            )[0]["kind"],
            "other",
        )
        bad = copy.deepcopy(ledger)
        bad[0]["occurrence"] = 1
        with self.assertRaisesRegex(ValueError, "unanchored surface"):
            validate_operator_ledger(bad, text="provided that P, Q", label="open-world")

    def test_evidence_identity_witness_and_support_review_gate(self) -> None:
        graph = _graph()
        frontier = build_ordered_paper_frontier(graph, headline_claim_ids=["c1"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identity = {
                "message": {
                    "title": ["Exact Work"],
                    "DOI": "10.1000/exact",
                    "author": [{"given": "A", "family": "Scholar"}],
                    "issued": {"date-parts": [[2024]]},
                }
            }
            identity_path = root / "identity.json"
            identity_path.write_text(json.dumps(identity), encoding="utf-8")
            payload_path = root / "paper.txt"
            payload_path.write_text("The retained witness supports P1.", encoding="utf-8")
            registry = {
                "schema_version": 1,
                "registry_kind": "literature_identity_and_claim_support",
                "sources": [
                    {
                        "source_key": "exact",
                        "expected_identity": {
                            "title": "Exact Work",
                            "doi": "10.1000/exact",
                            "authors": ["A Scholar"],
                            "year": 2024,
                        },
                        "identity_record": {
                            "path": "identity.json",
                            "sha256": sha256_bytes(identity_path.read_bytes()),
                            "adapter": "crossref_message",
                        },
                        "substantive_payload": {
                            "path": "paper.txt",
                            "sha256": sha256_bytes(payload_path.read_bytes()),
                            "access_sufficiency": "full_text",
                        },
                        "claims": [
                            {
                                "claim_id": "ev-1",
                                "support_kind": "direct_text",
                                "paper_object_ids": ["p1"],
                                "locator": {"kind": "document", "value": "whole"},
                                "witness": "retained witness supports P1",
                                "support_review": {
                                    "status": "passed",
                                    "reviewer": "independent-source-review",
                                    "scope_note": "Only the bounded proposition.",
                                },
                            }
                        ],
                    }
                ],
            }
            evidence_receipt = verify_evidence_registry(
                project_root=root, registry=registry, frontier=frontier
            )
            self.assertEqual(
                evidence_receipt["contract_revision"], EVIDENCE_GATE_REVISION
            )
            self.assertEqual(evidence_receipt["counts"]["substantive_claims"], 1)
            evidence_status = validate_evidence_receipt(
                evidence_receipt, paper_frontier_id=frontier["frontier_id"]
            )
            self.assertEqual(
                evidence_status["receipt_id"],
                evidence_receipt["evidence_receipt_id"],
            )
            mutated = copy.deepcopy(registry)
            mutated["sources"][0]["claims"][0]["support_review"]["status"] = "pending"
            with self.assertRaisesRegex(PaperPipelineError, "review not passed"):
                verify_evidence_registry(
                    project_root=root, registry=mutated, frontier=frontier
                )

            _, successor_receipt = materialize_native_research_draft_successor(
                graph,
                actor="main",
                builder_context_id="receipt-integrity-fixture",
                activation_record={
                    "activation_policy": "prospective_only",
                    "source_role": "research_draft",
                    "authority_effect": "none",
                    "truth_effect": "none",
                },
                project_root=self.project_root,
            )
            graph_status = validate_paper_graph_semantics(graph)
            validate_successor_receipt(
                successor_receipt,
                source_graph_canonical_sha256=graph_status["graph_canonical_sha256"],
                source_graph=graph,
            )
            pipeline = build_pipeline_receipt(
                graph=graph,
                frontier=frontier,
                dag=_dag(),
                continuity_contract=_continuity(),
                evidence_receipt=evidence_receipt,
                successor_receipt=successor_receipt,
            )
            self.assertEqual(
                pipeline["evidence_receipt_canonical_sha256"],
                evidence_status["canonical_sha256"],
            )

            stale_evidence = copy.deepcopy(evidence_receipt)
            stale_evidence["counts"]["sources"] += 999
            with self.assertRaisesRegex(PaperPipelineError, "evidence receipt id drifted"):
                build_pipeline_receipt(
                    graph=graph,
                    frontier=frontier,
                    dag=_dag(),
                    continuity_contract=_continuity(),
                    evidence_receipt=stale_evidence,
                    successor_receipt=successor_receipt,
                )
            stale_successor = copy.deepcopy(successor_receipt)
            stale_successor["source_component_and_inference_materialization"][
                "hierarchy_atom_count"
            ] += 999
            with self.assertRaisesRegex(
                PaperPipelineError, "native successor receipt id drifted"
            ):
                build_pipeline_receipt(
                    graph=graph,
                    frontier=frontier,
                    dag=_dag(),
                    continuity_contract=_continuity(),
                    evidence_receipt=evidence_receipt,
                    successor_receipt=stale_successor,
                )
            unknown_field = copy.deepcopy(evidence_receipt)
            unknown_field["unreviewed_extension"] = True
            with self.assertRaisesRegex(PaperPipelineError, "field set drifted"):
                validate_evidence_receipt(
                    unknown_field, paper_frontier_id=frontier["frontier_id"]
                )

    def test_atomic_preflight_rejects_theorem_escape_and_target_loss(self) -> None:
        graph = _graph()
        frontier = build_ordered_paper_frontier(graph, headline_claim_ids=["c1"])
        status = validate_atomic_paper_dag(
            graph=graph,
            frontier=frontier,
            dag=_dag(),
            continuity_contract=_continuity(),
        )
        self.assertEqual(status["counts"]["atomic_claims"], 3)
        theorem = _dag()
        theorem["validation_subject"]["kind"] = "theorem"
        with self.assertRaisesRegex(PaperPipelineError, "theorem mode"):
            validate_atomic_paper_dag(
                graph=graph,
                frontier=frontier,
                dag=theorem,
                continuity_contract=_continuity(),
            )
        continuity = _continuity()
        continuity["required_claim_ids"] = ["lost-headline"]
        with self.assertRaisesRegex(PaperPipelineError, "research-target"):
            validate_atomic_paper_dag(
                graph=graph,
                frontier=frontier,
                dag=_dag(),
                continuity_contract=continuity,
            )

    def test_pipeline_receipt_keeps_native_gateway_boundary(self) -> None:
        graph = _graph()
        frontier = build_ordered_paper_frontier(graph, headline_claim_ids=["c1"])
        receipt = build_pipeline_receipt(
            graph=graph,
            frontier=frontier,
            dag=_dag(),
            continuity_contract=_continuity(),
        )
        self.assertTrue(receipt["authority_boundary"]["native_gateway_still_required"])
        self.assertNotIn("l3_l4_limited_restoration", receipt)

    def test_public_successor_example_covers_every_required_parser_option(self) -> None:
        parser = _PUBLIC_PIPELINE._parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(getattr(action, "choices", None), dict)
            and "successor" in action.choices
        )
        successor = subparsers.choices["successor"]
        required_options = {
            option
            for action in successor._actions
            if action.required
            for option in action.option_strings
            if option.startswith("--")
        }
        guide = (
            Path(__file__).resolve().parents[1]
            / "references"
            / "paper_research_pipeline.md"
        ).read_text(encoding="utf-8")
        marker = 'python3 -B "$PIPELINE" successor \\\n'
        self.assertIn(marker, guide)
        example = marker + guide.split(marker, 1)[1].split(
            'python3 -B "$PIPELINE"', 1
        )[0]
        self.assertEqual(
            sorted(option for option in required_options if option not in example),
            [],
        )

    def test_large_chain_frontier_is_iterative_and_topology_total(self) -> None:
        size = 700
        graph = _graph()
        graph["nodes"] = []
        graph["edges"] = []
        for index in range(size):
            claim_id = f"c{index:04d}"
            statement = f"Claim {index}"
            graph["nodes"].append(
                {
                    "local_id": claim_id,
                    "object_type": "claim",
                    "payload": {
                        "statement": statement,
                        "statement_sha256": _sha(statement),
                        "discourse_role": "premise" if index else "background",
                        "modality": "asserted",
                        "content_type": "conceptual",
                    },
                }
            )
            if index:
                inference_id = f"i{index:04d}"
                graph["nodes"].append(
                    {
                        "local_id": inference_id,
                        "object_type": "inference",
                        "payload": {
                            "premise_ids": [f"c{index - 1:04d}"],
                            "bridge_claim_ids": [],
                            "defeater_claim_ids": [],
                            "conclusion_id": claim_id,
                            "inference_kind": "other",
                            "strength": "defeasible",
                        },
                    }
                )
                graph["edges"].extend(
                    [
                        {
                            "source": f"c{index - 1:04d}",
                            "target": inference_id,
                            "relation_type": "premise_of",
                            "payload": {"position": 0},
                        },
                        {
                            "source": inference_id,
                            "target": claim_id,
                            "relation_type": "concludes",
                            "payload": {},
                        },
                    ]
                )
        frontier = build_ordered_paper_frontier(
            graph, headline_claim_ids=[f"c{size - 1:04d}"]
        )
        self.assertEqual(frontier["counts"]["claims"], size)
        self.assertEqual(frontier["counts"]["inferences"], size - 1)
        self.assertEqual(frontier["counts"]["work_units"], 2 * size - 1)


if __name__ == "__main__":
    unittest.main()
