from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from mathgraph.blackboard import make_node
from mathgraph.contracts import sha256_bytes
from mathgraph.paper_logic import PaperLogicStore
from mathgraph.paper_logic_contracts import (
    PAPER_LOGIC_FEATURE_REVISION,
    REVIEW_GLOBAL_CHECKS,
    scan_high_risk_operators,
    validate_definition,
    validate_formula,
    validate_impact_assessment,
)
from mathgraph.roles import allowed_commands
from mathgraph.store import MathGraphStore


def operator_ledger(text: str) -> list[dict]:
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


class PaperLogicGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="paper-logic-tests",
            title="Paper Logic tests",
            workflow_evidence_version=4,
        )
        self.paper = self.store.paper_logic()
        self.paper.initialize(actor="main")
        self.artifact = self.root / "paper.txt"
        self.artifact_bytes = (
            b"It does not meet the criterion.\n"
            b"It does tell us whether impairment is relevant.\n"
        )
        self.artifact.write_bytes(self.artifact_bytes)
        self.source = {
            "artifact_sha256": sha256_bytes(self.artifact_bytes),
            "artifact_locator": str(self.artifact),
            "title": "Fixture paper",
            "version": "test-v1",
            "mime_type": "text/plain",
            "retrieved_at": "2026-07-26T00:00:00Z",
            "inspection_methods": ["rendered_primary", "text_extraction_secondary"],
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _source_unit(local_id: str, text: str, order: int) -> dict:
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
                "render_sha256": sha256_bytes(
                    f"render-{order}".encode("utf-8")
                ),
                "context_before": "",
                "context_after": "",
                "operator_ledger": operator_ledger(text),
            },
        }

    @staticmethod
    def _claim(
        local_id: str,
        statement: str,
        *,
        source_unit_id: str = "",
        role: str = "premise",
    ) -> dict:
        literal = bool(source_unit_id)
        return {
            "local_id": local_id,
            "object_type": "claim",
            "payload": {
                "representation_kind": (
                    "source_literal"
                    if literal
                    else "researcher_reconstruction"
                ),
                "attribution": "author" if literal else "researcher",
                "discourse_role": role,
                "content_type": "conceptual",
                "statement": statement,
                "statement_sha256": sha256_bytes(
                    statement.encode("utf-8")
                ),
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
                "operator_ledger": operator_ledger(statement),
                "definition_ids": [],
                "parent_claim_id": "",
            },
        }

    def _logic_bundle(
        self,
        *,
        domain_profile: str = "philosophy",
        sentences: list[str] | None = None,
        supersedes_snapshot_id: str = "",
        builder: str = "builder",
        builder_context_id: str = "builder-context",
    ) -> dict:
        sentences = sentences or [
            "It does not meet the criterion.",
            "It does tell us whether impairment is relevant.",
        ]
        nodes: list[dict] = []
        premise_ids: list[str] = []
        coverage_units: list[dict] = []
        for index, sentence in enumerate(sentences, 1):
            source_id = f"s{index}"
            claim_id = f"c{index}"
            nodes.append(self._source_unit(source_id, sentence, index))
            nodes.append(
                self._claim(
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
                self._claim(
                    "c-head",
                    "The reconstructed conclusion follows.",
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
                        "source_unit_ids": [
                            f"s{index}"
                            for index in range(1, len(sentences) + 1)
                        ],
                        "bridge_claim_ids": [],
                        "defeater_claim_ids": [],
                        "rationale": (
                            "The fixture exposes premise completeness and "
                            "polarity tracking."
                        ),
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
        local_nodes = {item["local_id"]: item for item in nodes}
        return {
            "schema_version": 1,
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "project_id": self.store.project_id(),
            "paper_id": "fixture-paper",
            "graph_kind": "logic",
            "domain_profile": domain_profile,
            "builder": builder,
            "builder_context_id": builder_context_id,
            "source": copy.deepcopy(self.source),
            "base_snapshot_id": "",
            "supersedes_snapshot_id": supersedes_snapshot_id,
            "coverage": {
                "scope_kind": "bounded",
                "included_locators": ["pdf:0"],
                "excluded_locators": [],
                "units": coverage_units,
                "unresolved_load_bearing_units": [],
                "completeness_claim": (
                    "Complete for the two-sentence bounded fixture."
                ),
            },
            "nodes": nodes,
            "edges": PaperLogicStore._expected_logic_edges(local_nodes),
        }

    def _audit_bundle(
        self,
        *,
        base_snapshot_id: str,
        nodes: list[dict],
        domain_profile: str = "philosophy",
        supersedes_snapshot_id: str = "",
        builder: str = "audit-builder",
        builder_context_id: str = "audit-builder-context",
    ) -> dict:
        local_nodes = {item["local_id"]: item for item in nodes}
        return {
            "schema_version": 1,
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "project_id": self.store.project_id(),
            "paper_id": "fixture-paper",
            "graph_kind": "audit",
            "domain_profile": domain_profile,
            "builder": builder,
            "builder_context_id": builder_context_id,
            "source": copy.deepcopy(self.source),
            "base_snapshot_id": base_snapshot_id,
            "supersedes_snapshot_id": supersedes_snapshot_id,
            "coverage": {
                "scope_kind": "audit_subset",
                "included_locators": ["fixture:audit"],
                "excluded_locators": [],
                "units": [
                    {
                        "unit_id": "audit-scope",
                        "classification": "audit_target",
                        "mapped_node_ids": sorted(local_nodes),
                        "reason": "",
                    }
                ],
                "unresolved_load_bearing_units": [],
                "completeness_claim": (
                    "Complete only for the explicitly selected audit target."
                ),
            },
            "nodes": nodes,
            "edges": PaperLogicStore._expected_audit_edges(local_nodes),
        }

    def _stage_review_freeze(
        self,
        bundle: dict,
        *,
        artifact: Path | None = None,
    ) -> tuple[dict, dict]:
        staged = self.paper.stage(
            bundle,
            artifact_path=artifact or self.artifact,
            actor=bundle["builder"],
        )
        revision = self.paper.revision(staged["revision_id"])
        for index, profile in enumerate(
            revision["required_review_profiles"], 1
        ):
            object_ids = self.paper._expected_review_object_ids(
                revision,
                profile,
            )
            self.paper.record_review(
                {
                    "schema_version": 1,
                    "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
                    "project_id": self.store.project_id(),
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
        frozen = self.paper.freeze(
            revision["revision_id"],
            actor="main",
        )
        return revision, frozen

    @staticmethod
    def _finding(
        *,
        target_id: str,
        evidence_id: str,
        excerpt: str,
        compared_text: str,
    ) -> dict:
        return {
            "local_id": "finding",
            "object_type": "audit_finding",
            "payload": {
                "finding_kind": "negation_or_polarity",
                "severity": "critical",
                "status": "corroborated",
                "target_id": target_id,
                "claim": "The target's polarity was reconstructed incorrectly.",
                "rationale": "The exact rendered sentence controls the polarity.",
                "evidence_unit_ids": [evidence_id],
                "observed_excerpt": excerpt,
                "compared_text": compared_text,
                "load_bearing_tokens": ["not"],
            },
        }

    @staticmethod
    def _counterexample(
        *,
        target_id: str,
        premise_ids: list[str],
        nontriviality: str = "substantive",
    ) -> dict:
        return {
            "local_id": "counterexample",
            "object_type": "counterexample",
            "payload": {
                "target_id": target_id,
                "construction": "A fully specified interpretation and case.",
                "premise_witnesses": [
                    {
                        "premise_id": premise_id,
                        "status": "satisfied",
                        "witness": f"Witness for {premise_id}.",
                    }
                    for premise_id in premise_ids
                ],
                "conclusion_failure": {
                    "status": "fails",
                    "witness": "The exact conclusion is false in the case.",
                },
                "interpretation_preserved": True,
                "interpretation_notes": (
                    "Every load-bearing term keeps the target interpretation."
                ),
                "nontriviality": nontriviality,
                "evidence": ["reproducible-case:fixture-1"],
                "provisional_logical_effect": (
                    "refutes_exact_representation"
                ),
            },
        }

    def test_absent_paper_store_is_backward_compatible(self) -> None:
        other = Path(self.temporary.name) / "legacy"
        legacy = MathGraphStore(other)
        legacy.initialize(
            project_id="legacy-v4",
            title="Legacy V4",
            workflow_evidence_version=4,
        )
        report = legacy.audit()
        self.assertTrue(report.ok)
        self.assertEqual(report.paper_source_nodes, 0)
        self.assertFalse(legacy.paper_logic().audit()["present"])

    def test_defeaters_are_typed_edges_and_must_reference_claims(self) -> None:
        bundle = self._logic_bundle()
        bundle["nodes"].append(
            self._claim(
                "c-defeater",
                "A represented condition defeats this inference.",
                role="background",
            )
        )
        inference = next(
            item
            for item in bundle["nodes"]
            if item["local_id"] == "i-head"
        )
        inference["payload"]["strength"] = "defeasible"
        inference["payload"]["defeater_claim_ids"] = ["c-defeater"]
        local_nodes = {item["local_id"]: item for item in bundle["nodes"]}
        bundle["edges"] = PaperLogicStore._expected_logic_edges(local_nodes)
        defeat_edge = next(
            edge
            for edge in bundle["edges"]
            if edge["relation_type"] == "defeats"
        )
        self.assertEqual(defeat_edge["source"], "c-defeater")
        self.assertEqual(defeat_edge["target"], "i-head")
        staged = self.paper.stage(
            bundle,
            artifact_path=self.artifact,
            actor=bundle["builder"],
        )
        revision = self.paper.revision(staged["revision_id"])
        stored_edges = [
            self.paper._read_json(
                self.paper._edge_path(entry["object_id"])
            )
            for entry in revision["edge_entries"]
        ]
        self.assertTrue(
            any(edge["relation_type"] == "defeats" for edge in stored_edges)
        )

        invalid = copy.deepcopy(bundle)
        invalid_inference = next(
            item
            for item in invalid["nodes"]
            if item["local_id"] == "i-head"
        )
        invalid_inference["payload"]["defeater_claim_ids"] = ["missing"]
        invalid_nodes = {
            item["local_id"]: item for item in invalid["nodes"]
        }
        invalid["edges"] = PaperLogicStore._expected_logic_edges(invalid_nodes)
        with self.assertRaisesRegex(ValueError, "unknown defeater claim"):
            self.paper.stage(
                invalid,
                artifact_path=self.artifact,
                actor=invalid["builder"],
            )

    def test_independent_subthesis_may_end_at_supporting_target(self) -> None:
        bundle = self._logic_bundle()
        bundle["nodes"].extend(
            [
                self._claim(
                    "c-independent",
                    "An independent bounded subthesis.",
                    role="intermediate_conclusion",
                ),
                {
                    "local_id": "t-independent",
                    "object_type": "paper_target",
                    "payload": {
                        "target_role": "supporting",
                        "claim_id": "c-independent",
                        "rationale": (
                            "The subthesis is argumentative but independent "
                            "of the headline route."
                        ),
                    },
                },
            ]
        )
        local_nodes = {item["local_id"]: item for item in bundle["nodes"]}
        bundle["edges"] = PaperLogicStore._expected_logic_edges(local_nodes)
        staged = self.paper.stage(
            bundle,
            artifact_path=self.artifact,
            actor=bundle["builder"],
        )
        self.assertEqual(staged["status"], "staged_nontruth")

        no_supporting_target = copy.deepcopy(bundle)
        no_supporting_target["nodes"] = [
            item
            for item in no_supporting_target["nodes"]
            if item["local_id"] != "t-independent"
        ]
        no_supporting_nodes = {
            item["local_id"]: item
            for item in no_supporting_target["nodes"]
        }
        no_supporting_target["edges"] = (
            PaperLogicStore._expected_logic_edges(no_supporting_nodes)
        )
        with self.assertRaisesRegex(ValueError, "declared paper target"):
            self.paper.stage(
                no_supporting_target,
                artifact_path=self.artifact,
                actor=no_supporting_target["builder"],
            )

    def test_operator_ledger_rejects_omitted_not(self) -> None:
        bundle = self._logic_bundle(sentences=["It does not tell us."])
        source_unit = next(
            item
            for item in bundle["nodes"]
            if item["object_type"] == "source_unit"
        )
        source_unit["payload"]["operator_ledger"] = []
        with self.assertRaisesRegex(ValueError, "operator ledger misses"):
            self.paper.stage(
                bundle,
                artifact_path=self.artifact,
                actor=bundle["builder"],
            )

    def test_literal_claim_cannot_silently_drop_not(self) -> None:
        bundle = self._logic_bundle(sentences=["It does not tell us."])
        claim = next(
            item
            for item in bundle["nodes"]
            if item["object_type"] == "claim"
            and item["local_id"] == "c1"
        )
        claim["payload"]["statement"] = "It does tell us."
        claim["payload"]["statement_sha256"] = sha256_bytes(
            b"It does tell us."
        )
        claim["payload"]["operator_ledger"] = operator_ledger(
            "It does tell us."
        )
        with self.assertRaisesRegex(ValueError, "not an exact source substring"):
            self.paper.stage(
                bundle,
                artifact_path=self.artifact,
                actor=bundle["builder"],
            )

    def test_researcher_reconstruction_cannot_be_attributed_to_author(self) -> None:
        definition = {
            "representation_kind": "researcher_reconstruction",
            "attribution": "author",
            "definition_kind": "contested",
            "term": "capacity",
            "definiens": "A graph-builder reconstruction of capacity.",
            "source_unit_ids": [],
            "semantic_diff": "This formulation is not a source quotation.",
            "scope_notes": "Fixture only.",
            "operator_ledger": operator_ledger(
                "capacity: A graph-builder reconstruction of capacity."
            ),
        }
        with self.assertRaisesRegex(
            ValueError,
            "must be attributed to researcher",
        ):
            validate_definition(definition, "definition")

        formula = {
            "representation_kind": "researcher_reconstruction",
            "attribution": "author",
            "expression": "P -> Q",
            "expression_sha256": sha256_bytes(b"P -> Q"),
            "source_unit_ids": [],
            "semantic_diff": "This symbolic form is reconstructed.",
            "scope_notes": "Fixture only.",
            "glyph_ledger": [
                {
                    "token": "P",
                    "role": "premise",
                    "finding": "Researcher-assigned symbol.",
                },
                {
                    "token": "->",
                    "role": "conditional",
                    "finding": "Researcher-assigned connective.",
                },
                {
                    "token": "Q",
                    "role": "conclusion",
                    "finding": "Researcher-assigned symbol.",
                },
            ],
        }
        with self.assertRaisesRegex(
            ValueError,
            "must be attributed to researcher",
        ):
            validate_formula(formula, "formula")

    def test_fresh_independent_reviews_gate_freezing(self) -> None:
        bundle = self._logic_bundle()
        staged = self.paper.stage(
            bundle,
            artifact_path=self.artifact,
            actor=bundle["builder"],
        )
        with self.assertRaisesRegex(ValueError, "lacks correct"):
            self.paper.freeze(staged["revision_id"], actor="main")
        _, frozen = self._stage_review_freeze(bundle)
        result = self.paper.query(
            frozen["snapshot_id"],
            view="combined",
            query={
                "seed_ids": [],
                "direction": "both",
                "max_hops": 8,
                "node_budget": 64,
                "edge_budget": 128,
            },
        )
        self.assertFalse(result["omission"]["node_budget_hit"])
        self.assertTrue(
            {node["plane"] for node in result["nodes"]}
            >= {"paper_source", "paper_reconstruction"}
        )
        self.assertEqual(result["truth_effect"], "none")

    def test_glannon_style_wrong_sentence_target_is_rejected(self) -> None:
        revision, frozen = self._stage_review_freeze(
            self._logic_bundle()
        )
        ids = revision["local_id_map"]
        wrong = self._finding(
            target_id=ids["c1"],
            evidence_id=ids["s2"],
            excerpt="It does tell us whether impairment is relevant.",
            compared_text="It does not meet the criterion.",
        )
        bundle = self._audit_bundle(
            base_snapshot_id=frozen["snapshot_id"],
            nodes=[wrong],
        )
        with self.assertRaisesRegex(
            ValueError,
            "evidence is not anchored to the exact target",
        ):
            self.paper.stage(
                bundle,
                artifact_path=self.artifact,
                actor=bundle["builder"],
            )

    def test_exact_mathematical_counterexample_requires_all_premises(self) -> None:
        revision, frozen = self._stage_review_freeze(
            self._logic_bundle(domain_profile="mathematics")
        )
        ids = revision["local_id_map"]
        counterexample = self._counterexample(
            target_id=ids["c-head"],
            premise_ids=[ids["c1"]],
        )
        impact = {
            "local_id": "impact",
            "object_type": "impact_assessment",
            "payload": {
                "challenge_id": "counterexample",
                "repair_id": "",
                "domain_profile": "mathematics",
                "logical_effect": "refutes_exact_representation",
                "dialectical_effect": "refutes_exact_claim",
                "core_target_id": ids["c-head"],
                "core_preservation": "not_preserved",
                "repair_cost": "none",
                "evidence_strength": "demonstrated",
                "justification": "The exact inference fails.",
            },
        }
        incomplete = self._audit_bundle(
            base_snapshot_id=frozen["snapshot_id"],
            nodes=[counterexample, impact],
            domain_profile="mathematics",
        )
        with self.assertRaisesRegex(ValueError, "every premise"):
            self.paper.stage(
                incomplete,
                artifact_path=self.artifact,
                actor=incomplete["builder"],
            )
        counterexample["payload"]["premise_witnesses"].append(
            {
                "premise_id": ids["c2"],
                "status": "satisfied",
                "witness": "Witness for the second premise.",
            }
        )
        complete = self._audit_bundle(
            base_snapshot_id=frozen["snapshot_id"],
            nodes=[counterexample, impact],
            domain_profile="mathematics",
        )
        staged = self.paper.stage(
            complete,
            artifact_path=self.artifact,
            actor=complete["builder"],
        )
        self.assertEqual(staged["status"], "staged_nontruth")

    def test_philosophy_separates_local_repair_from_refutation(self) -> None:
        valid_local_repair = {
            "challenge_id": "counterexample",
            "repair_id": "repair",
            "domain_profile": "philosophy",
            "logical_effect": "refutes_exact_representation",
            "dialectical_effect": "local_repair",
            "core_target_id": "prn-" + "a" * 64,
            "core_preservation": "preserved",
            "repair_cost": "local",
            "evidence_strength": "demonstrated",
            "justification": (
                "The literal variant fails, while a bounded repair preserves "
                "the paper's core thesis."
            ),
        }
        validate_impact_assessment(
            valid_local_repair,
            "impact",
            domain_profile="philosophy",
        )
        inflated = dict(valid_local_repair)
        inflated.update(
            {
                "repair_id": "",
                "dialectical_effect": "refutes_core",
            }
        )
        with self.assertRaisesRegex(ValueError, "refutes_core"):
            validate_impact_assessment(
                inflated,
                "impact",
                domain_profile="philosophy",
            )

    def test_trivial_philosophy_counterexample_cannot_be_inflated(self) -> None:
        revision, frozen = self._stage_review_freeze(
            self._logic_bundle()
        )
        ids = revision["local_id_map"]
        counterexample = self._counterexample(
            target_id=ids["c-head"],
            premise_ids=[ids["c1"], ids["c2"]],
            nontriviality="trivial",
        )
        impact = {
            "local_id": "impact",
            "object_type": "impact_assessment",
            "payload": {
                "challenge_id": "counterexample",
                "repair_id": "",
                "domain_profile": "philosophy",
                "logical_effect": "refutes_exact_representation",
                "dialectical_effect": "refutes_core",
                "core_target_id": ids["c-head"],
                "core_preservation": "not_preserved",
                "repair_cost": "none",
                "evidence_strength": "demonstrated",
                "justification": "Inflated on purpose for the regression test.",
            },
        }
        bundle = self._audit_bundle(
            base_snapshot_id=frozen["snapshot_id"],
            nodes=[counterexample, impact],
        )
        with self.assertRaisesRegex(ValueError, "trivial counterexample"):
            self.paper.stage(
                bundle,
                artifact_path=self.artifact,
                actor=bundle["builder"],
            )

    def test_audit_error_is_corrected_by_new_snapshot_not_mutation(self) -> None:
        logic_revision, logic_frozen = self._stage_review_freeze(
            self._logic_bundle()
        )
        logic_ids = logic_revision["local_id_map"]
        original = self._finding(
            target_id=logic_ids["c1"],
            evidence_id=logic_ids["s1"],
            excerpt="It does not meet the criterion.",
            compared_text="It does meet the criterion.",
        )
        first_revision, first_frozen = self._stage_review_freeze(
            self._audit_bundle(
                base_snapshot_id=logic_frozen["snapshot_id"],
                nodes=[original],
            )
        )
        old_finding_id = first_revision["local_id_map"]["finding"]
        replacement = self._finding(
            target_id=logic_ids["c2"],
            evidence_id=logic_ids["s2"],
            excerpt="It does tell us whether impairment is relevant.",
            compared_text="It does not tell us whether impairment is relevant.",
        )
        replacement["local_id"] = "replacement"
        challenge = {
            "local_id": "challenge",
            "object_type": "audit_challenge",
            "payload": {
                "target_audit_id": old_finding_id,
                "claim": "The earlier audit targeted the wrong sentence.",
                "evidence": ["paper-source-unit:s2"],
                "status": "corroborated",
                "rationale": "The two sentences have distinct anchors.",
            },
        }
        disposition = {
            "local_id": "disposition",
            "object_type": "audit_disposition",
            "payload": {
                "target_audit_id": old_finding_id,
                "challenge_ids": ["challenge"],
                "disposition": "corrected",
                "replacement_ids": ["replacement"],
                "rationale": "Retain history and supersede the wrong finding.",
            },
        }
        corrected_revision, corrected_frozen = self._stage_review_freeze(
            self._audit_bundle(
                base_snapshot_id=first_frozen["snapshot_id"],
                nodes=[replacement, challenge, disposition],
                supersedes_snapshot_id=first_frozen["snapshot_id"],
                builder="correction-builder",
                builder_context_id="correction-context",
            )
        )
        old_manifest = self.paper.snapshot_manifest(
            first_frozen["snapshot_id"]
        )
        new_manifest = self.paper.snapshot_manifest(
            corrected_frozen["snapshot_id"]
        )
        self.assertIn(old_finding_id, old_manifest["current_audit_node_ids"])
        self.assertIn(old_finding_id, new_manifest["inactive_audit_node_ids"])
        self.assertNotIn(old_finding_id, new_manifest["current_audit_node_ids"])
        self.assertIn(
            corrected_revision["local_id_map"]["replacement"],
            new_manifest["current_audit_node_ids"],
        )
        self.assertIn(
            first_frozen["snapshot_id"],
            self.paper.status()["superseded_snapshot_ids"],
        )
        audit_report = self.paper.audit(
            blackboard=self.store.blackboard()
        )
        self.assertTrue(audit_report["ok"])
        self.assertFalse(
            any("is stale" in warning for warning in audit_report["warnings"])
        )

    def test_profile_closure_rejects_superseded_paper_snapshots_and_stale_audit_base(
        self,
    ) -> None:
        logic_revision, first_logic = self._stage_review_freeze(
            self._logic_bundle()
        )
        ids = logic_revision["local_id_map"]
        finding = self._finding(
            target_id=ids["c1"],
            evidence_id=ids["s1"],
            excerpt="It does not meet the criterion.",
            compared_text="It does meet the criterion.",
        )
        _, audit = self._stage_review_freeze(
            self._audit_bundle(
                base_snapshot_id=first_logic["snapshot_id"],
                nodes=[finding],
            )
        )
        _, second_logic = self._stage_review_freeze(
            self._logic_bundle(
                supersedes_snapshot_id=first_logic["snapshot_id"],
                builder="replacement-builder",
                builder_context_id="replacement-context",
            )
        )
        assignment_id = "a01-paper-logic"
        view = {
            "assignments": {
                assignment_id: {
                    "feature_statuses": {
                        "paper_logic_graph": "required",
                        "paper_audit_graph": "required",
                    }
                }
            },
            "assignment_contexts": {
                assignment_id: {
                    "source_artifact_sha256": self.source["artifact_sha256"]
                }
            },
        }
        manager = self.store.profile_closures()
        with self.assertRaisesRegex(ValueError, "stale or superseded"):
            manager._paper_snapshot_binding(
                {
                    "feature": "paper_logic_graph",
                    "evidence_kind": "reviewed_paper_snapshots",
                    "snapshots": [
                        {
                            "snapshot_id": first_logic["snapshot_id"],
                            "covered_assignment_ids": [assignment_id],
                        }
                    ],
                },
                feature="paper_logic_graph",
                view=view,
            )
        current = manager._paper_snapshot_binding(
            {
                "feature": "paper_logic_graph",
                "evidence_kind": "reviewed_paper_snapshots",
                "snapshots": [
                    {
                        "snapshot_id": second_logic["snapshot_id"],
                        "covered_assignment_ids": [assignment_id],
                    }
                ],
            },
            feature="paper_logic_graph",
            view=view,
        )
        self.assertEqual(
            current["snapshots"][0]["snapshot_id"], second_logic["snapshot_id"]
        )
        with self.assertRaisesRegex(ValueError, "logic base was superseded"):
            manager._paper_snapshot_binding(
                {
                    "feature": "paper_audit_graph",
                    "evidence_kind": "reviewed_paper_snapshots",
                    "snapshots": [
                        {
                            "snapshot_id": audit["snapshot_id"],
                            "covered_assignment_ids": [assignment_id],
                        }
                    ],
                },
                feature="paper_audit_graph",
                view=view,
            )

    def test_full_fidelity_blackboard_projection_is_reserved(self) -> None:
        _, frozen = self._stage_review_freeze(self._logic_bundle())
        board = self.store.blackboard()
        space_id = next(
            node_id
            for node_id, node in board.nodes().items()
            if node["node_type"] == "space"
        )
        projection = self.paper.project_to_blackboard(
            {
                "paper_snapshot_id": frozen["snapshot_id"],
                "view": "combined",
                "query": {
                    "seed_ids": [],
                    "direction": "both",
                    "max_hops": 8,
                    "node_budget": 64,
                    "edge_budget": 128,
                },
                "blackboard_space_id": space_id,
                "projection_mode": "full_fidelity",
                "name": "fixture-paper-sandbox",
            },
            actor="main",
            blackboard=board,
        )
        self.assertTrue(projection["node_map"])
        mirror_id = next(iter(projection["node_map"].values()))
        mirror = board.show(mirror_id)
        self.assertEqual(mirror["node_type"], "paper_logic_mirror")
        self.assertEqual(mirror["truth_status"], "exploration")
        with self.assertRaisesRegex(ValueError, "governed projection"):
            board.add_objects(
                nodes=[mirror],
                edges=[],
                actor="main",
            )
        mirror_query = {
            "seed_node_ids": [mirror_id],
            "direction": "both",
            "max_hops": 1,
            "edge_type_allowlist": ["*"],
            "node_type_allowlist": ["*"],
            "node_budget": 16,
            "edge_budget": 32,
        }
        mirror_snapshot = board.snapshot(
            query=mirror_query,
            actor="main",
        )
        campaign_id = self.store.campaigns().active()
        assert campaign_id is not None
        with self.assertRaisesRegex(ValueError, "cannot be promoted"):
            self.store.campaigns().promote_blackboard_node(
                mirror_id,
                {
                    "snapshot_id": mirror_snapshot["snapshot_id"],
                    "campaign_id": campaign_id,
                    "memory_kind": "conjecture",
                    "claim": "Attempt to promote a mirror.",
                    "rationale": "This should fail closed.",
                    "mode_suggestions": ["interpret"],
                    "blackboard_query": mirror_query,
                    "decision_profile": {
                        "impact": 0.5,
                        "information_value": 0.5,
                        "tractability": 0.5,
                        "burden": 0.5,
                    },
                },
                actor="main",
                memory_add=lambda payload, actor: "unreachable",
            )
        self.assertTrue(
            self.paper.audit(blackboard=board)["ok"]
        )

    def test_agent_can_challenge_audit_through_snapshot_bound_bridge(self) -> None:
        logic_revision, logic_frozen = self._stage_review_freeze(
            self._logic_bundle()
        )
        logic_ids = logic_revision["local_id_map"]
        audit_revision, audit_frozen = self._stage_review_freeze(
            self._audit_bundle(
                base_snapshot_id=logic_frozen["snapshot_id"],
                nodes=[
                    self._finding(
                        target_id=logic_ids["c1"],
                        evidence_id=logic_ids["s1"],
                        excerpt="It does not meet the criterion.",
                        compared_text="It does meet the criterion.",
                    )
                ],
            )
        )
        board = self.store.blackboard()
        space_id = next(
            node_id
            for node_id, node in board.nodes().items()
            if node["node_type"] == "space"
        )
        challenge = make_node(
            node_type="note",
            logical_key="audit-challenge-note",
            payload={"text": "Recheck the exact audit target."},
            created_by_assignment_id="main",
        )
        board.add_node_with_placements(
            node=challenge,
            space_ids=[space_id],
            actor="main",
        )
        board_snapshot = board.snapshot(
            query={
                "seed_node_ids": [challenge["node_id"]],
                "direction": "both",
                "max_hops": 1,
                "edge_type_allowlist": ["*"],
                "node_type_allowlist": ["*"],
                "node_budget": 16,
                "edge_budget": 32,
            },
            actor="main",
        )
        bridge = self.paper.link_exploration(
            {
                "paper_snapshot_id": audit_frozen["snapshot_id"],
                "paper_object_id": audit_revision["local_id_map"]["finding"],
                "blackboard_snapshot_id": board_snapshot["snapshot_id"],
                "blackboard_object_id": challenge["node_id"],
                "relation": "exploration_challenges_audit",
                "rationale": "Agent exploration found a target-binding concern.",
            },
            actor="main",
            blackboard=board,
        )
        self.assertEqual(bridge["truth_effect"], "none")
        self.assertTrue(self.paper.audit(blackboard=board)["ok"])

    def test_roles_keep_worker_out_and_auditor_read_only(self) -> None:
        self.assertNotIn("paper-logic-query", allowed_commands("worker"))
        auditor = allowed_commands("paper-auditor")
        self.assertIn("paper-logic-query", auditor)
        self.assertIn("paper-logic-record-review", auditor)
        self.assertNotIn("paper-logic-stage", auditor)
        self.assertNotIn("paper-logic-project-blackboard", auditor)
        self.assertIn("paper-logic-project-blackboard", allowed_commands("main"))


if __name__ == "__main__":
    unittest.main()
