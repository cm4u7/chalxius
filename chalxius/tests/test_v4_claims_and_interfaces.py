from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from mathgraph.claims import ClaimRegistry
from mathgraph.interfaces import (
    build_statement_interface,
    extract_statement_clauses,
    lint_quantifier_export,
    validate_predecessor_uses,
    validate_quantifier_ledger,
    validate_statement_interface,
)
from mathgraph.markdown import serialize_fact
from mathgraph.model import Fact
from mathgraph.store import MathGraphStore


class V4ClaimsAndInterfacesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="v4-claims",
            title="V4 claims",
            workflow_evidence_version=4,
        )
        self.registry = ClaimRegistry(self.root)
        self.convention_id = self.registry.add_convention(
            {
                "theory": "topological recursion",
                "source_version": "arXiv:2401.00001v2",
                "source_artifact_sha256": "a" * 64,
                "authority": "literal_source",
                "dimensions": {
                    "B_normalization": "A-normalized",
                    "residue_orientation": "positive",
                },
            },
            actor="operator",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _literal(self) -> dict:
        return {
            "kind": "published_literal",
            "title": "Literal source claim",
            "statement": "For every admissible curve, P holds.",
            "source": {
                "title": "Source paper",
                "version": "arXiv:2401.00001v2",
                "artifact_sha256": "b" * 64,
                "locator": "Theorem 1.2",
                "retrieved_at": "2026-07-24",
            },
            "convention_profile_id": self.convention_id,
            "authority": "literal_source",
        }

    def test_published_claim_requires_versioned_source_and_statement_hash(self) -> None:
        claim_id = self.registry.add_claim(self._literal(), actor="operator")
        claim = self.registry.show_claim(claim_id)
        self.assertEqual(
            claim["statement_sha256"],
            hashlib.sha256(claim["statement"].encode()).hexdigest(),
        )
        invalid = self._literal()
        invalid["source"] = {**invalid["source"], "version": "arXiv:2401.00001"}
        with self.assertRaisesRegex(ValueError, "exact source version"):
            self.registry.add_claim(invalid, actor="operator")

    def test_refuting_published_campaign_claim_requires_exact_source_binding(
        self,
    ) -> None:
        claim_id = self.registry.add_claim(self._literal(), actor="operator")
        campaign_id = self.store.campaigns().create(
            {
                "name": "published-refutation",
                "objective": "Test the literal published claim.",
                "source_claim_ids": [claim_id],
                "targets": [],
                "constraints": [],
                "stop_conditions": ["Stop on a decisive counterexample."],
                "value_definition": "Resolve the published claim.",
            },
            actor="operator",
        )
        self.store.campaigns().activate(campaign_id, actor="operator")
        with self.assertRaisesRegex(ValueError, "requires source_claim_id"):
            self.store.memory_add(
                {
                    "kind": "direction",
                    "claim": "Try to refute the published claim.",
                    "goal_relation": "refutes",
                    "campaign_id": campaign_id,
                },
                actor="main",
            )
        memory_id = self.store.memory_add(
            {
                "kind": "direction",
                "claim": "Try to refute the exact published claim.",
                "goal_relation": "refutes",
                "campaign_id": campaign_id,
                "source_claim_id": claim_id,
            },
            actor="main",
        )
        self.assertEqual(
            self.store.memory_latest()[memory_id]["source_claim_id"],
            claim_id,
        )

    def test_researcher_variant_requires_parent_and_nonempty_diff(self) -> None:
        parent = self.registry.add_claim(self._literal(), actor="operator")
        variant = self.registry.create_variant(
            parent,
            {
                "title": "Restricted variant",
                "statement": "For genus zero curves, P holds.",
                "variant_diff": [
                    {
                        "field": "domain",
                        "from": "every admissible curve",
                        "to": "genus zero curves",
                        "authority": "researcher_defined",
                    }
                ],
            },
            actor="researcher",
        )
        self.assertEqual(
            self.registry.show_claim(variant)["parent_claim_id"],
            parent,
        )
        with self.assertRaisesRegex(ValueError, "nonempty variant_diff"):
            self.registry.create_variant(
                parent,
                {"statement": "A variant", "variant_diff": []},
                actor="researcher",
            )

    def test_researcher_variant_is_not_author_confirmed_by_default(self) -> None:
        parent = self.registry.add_claim(self._literal(), actor="operator")
        variant = self.registry.create_variant(
            parent,
            {
                "statement": "A defensible restricted claim.",
                "variant_diff": [
                    {
                        "field": "scope",
                        "from": "all",
                        "to": "restricted",
                        "authority": "researcher_defined",
                    }
                ],
            },
            actor="researcher",
        )
        self.assertFalse(self.registry.show_claim(variant)["author_confirmed"])

    def test_new_fact_requires_statement_clause_anchor(self) -> None:
        with self.assertRaisesRegex(ValueError, r"\[CLAIM"):
            extract_statement_clauses("Unanchored theorem.", require_v4=True)
        clauses = extract_statement_clauses(
            "[CLAIM:MAIN] Anchored theorem.",
            require_v4=True,
        )
        self.assertEqual(clauses[0]["clause_id"], "MAIN")

    def test_legacy_fact_exports_only_legacy_full_clause(self) -> None:
        fact = Fact(
            problem_id="v4-claims",
            author="legacy",
            predecessors=[],
            statement="Legacy theorem.",
            proof="Legacy proof.",
        )
        interface = build_statement_interface(
            fact=fact,
            stored_fact_sha256="1" * 64,
            acceptance_event_sha256="2" * 64,
            admission_review_id="3" * 64,
            workflow_evidence_version=3,
        )
        self.assertEqual(
            [item["clause_id"] for item in interface["clauses"]],
            ["legacy-full"],
        )

    def test_quantifier_dependency_dag_rejects_cycle(self) -> None:
        statement = (
            "[CLAIM:C] [Q:a] For every a, [Q:b] choose b(a), "
            "[Q:c] choose c(b)."
        )
        proof = "[WIT:b] choose b. [WIT:c] choose c."
        ledger = [
            {
                "id": "a",
                "kind": "forall",
                "variable": "a",
                "depends_on": [],
                "statement_anchor": "[Q:a]",
                "proof_witness_anchor": "",
                "scope_clause": "C",
            },
            {
                "id": "b",
                "kind": "choose",
                "variable": "b",
                "depends_on": ["c"],
                "statement_anchor": "[Q:b]",
                "proof_witness_anchor": "[WIT:b]",
                "scope_clause": "C",
            },
            {
                "id": "c",
                "kind": "choose",
                "variable": "c",
                "depends_on": ["b"],
                "statement_anchor": "[Q:c]",
                "proof_witness_anchor": "[WIT:c]",
                "scope_clause": "C",
            },
        ]
        with self.assertRaisesRegex(ValueError, "earlier outer"):
            validate_quantifier_ledger(
                ledger,
                statement=statement,
                proof=proof,
                clause_ids={"C"},
            )

    def test_quantifier_anchor_order_must_match_ledger(self) -> None:
        statement = "[CLAIM:C] [Q:a] For all a, [Q:b] there exists b."
        proof = "[WIT:b] pick b."
        ledger = [
            {
                "id": "b",
                "kind": "exists",
                "variable": "b",
                "depends_on": [],
                "statement_anchor": "[Q:b]",
                "proof_witness_anchor": "[WIT:b]",
                "scope_clause": "C",
            },
            {
                "id": "a",
                "kind": "forall",
                "variable": "a",
                "depends_on": [],
                "statement_anchor": "[Q:a]",
                "proof_witness_anchor": "",
                "scope_clause": "C",
            },
        ]
        with self.assertRaisesRegex(ValueError, "order"):
            validate_quantifier_ledger(
                ledger,
                statement=statement,
                proof=proof,
                clause_ids={"C"},
            )

    def test_existential_witness_dependency_is_preserved(self) -> None:
        statement = "[CLAIM:C] [Q:a] For all a, [Q:b] choose b(a)."
        proof = "[WIT:b] choose b after a."
        ledger = [
            {
                "id": "a",
                "kind": "forall",
                "variable": "a",
                "depends_on": [],
                "statement_anchor": "[Q:a]",
                "proof_witness_anchor": "",
                "scope_clause": "C",
            },
            {
                "id": "b",
                "kind": "choose",
                "variable": "b",
                "depends_on": ["a"],
                "statement_anchor": "[Q:b]",
                "proof_witness_anchor": "[WIT:b]",
                "scope_clause": "C",
            },
        ]
        normalized = validate_quantifier_ledger(
            ledger,
            statement=statement,
            proof=proof,
            clause_ids={"C"},
        )
        self.assertEqual(normalized[1]["depends_on"], ["a"])

    def test_expert_export_cannot_turn_dependent_witness_into_uniform_witness(self) -> None:
        errors = lint_quantifier_export(
            "There is a uniform witness.",
            [{"id": "b", "depends_on": ["a"]}],
        )
        self.assertTrue(errors)

    def test_predecessor_use_requires_exact_clause_and_hypothesis_witnesses(self) -> None:
        predecessor = Fact(
            problem_id="v4-claims",
            author="author",
            predecessors=[],
            statement="[CLAIM:LOCAL] Assuming H1, conclusion K holds.",
            proof="Proof.",
        )
        interface = build_statement_interface(
            fact=predecessor,
            stored_fact_sha256="1" * 64,
            acceptance_event_sha256="2" * 64,
            admission_review_id="3" * 64,
            workflow_evidence_version=4,
        )
        anchor = f"[USE:{predecessor.fact_id}:LOCAL:u1]"
        proof = f"Apply the predecessor here {anchor}."
        valid = [
            {
                "fact_id": predecessor.fact_id,
                "clause_id": "LOCAL",
                "use_anchor": anchor,
                "used_conclusion": "K",
                "hypothesis_witnesses": [
                    {
                        "hypothesis": "H1",
                        "witness": "the current H1",
                        "proof_anchor": anchor,
                    }
                ],
                "convention_bridge": None,
            }
        ]
        self.assertEqual(
            validate_predecessor_uses(
                valid,
                predecessors=[predecessor.fact_id],
                proof=proof,
                interface_lookup=lambda _fact_id: interface,
                convention_profile_ids=[],
            ),
            valid,
        )
        invalid = [dict(valid[0], hypothesis_witnesses=[])]
        with self.assertRaisesRegex(ValueError, "witnesses mismatch"):
            validate_predecessor_uses(
                invalid,
                predecessors=[predecessor.fact_id],
                proof=proof,
                interface_lookup=lambda _fact_id: interface,
                convention_profile_ids=[],
            )

    def test_convention_mismatch_requires_explicit_bridge(self) -> None:
        predecessor = Fact(
            problem_id="v4-claims",
            author="author",
            predecessors=[],
            statement="[CLAIM:C] Conclusion.",
            proof="Proof.",
        )
        interface = build_statement_interface(
            fact=predecessor,
            stored_fact_sha256="1" * 64,
            acceptance_event_sha256="2" * 64,
            admission_review_id="3" * 64,
            workflow_evidence_version=4,
        )
        anchor = f"[USE:{predecessor.fact_id}:C:u]"
        bridge_anchor = "[BRIDGE:conv]"
        use = {
            "fact_id": predecessor.fact_id,
            "clause_id": "C",
            "use_anchor": anchor,
            "used_conclusion": "Conclusion",
            "hypothesis_witnesses": [],
            "convention_bridge": {
                "from_convention_id": "conv-" + "1" * 16,
                "to_convention_id": self.convention_id,
                "kind": "sign conversion",
                "witness": "direct calculation",
                "proof_anchor": bridge_anchor,
            },
        }
        with self.assertRaisesRegex(ValueError, "bridge target"):
            validate_predecessor_uses(
                [use],
                predecessors=[predecessor.fact_id],
                proof=f"{anchor} {bridge_anchor}",
                interface_lookup=lambda _fact_id: interface,
                convention_profile_ids=[],
            )
        validate_predecessor_uses(
            [use],
            predecessors=[predecessor.fact_id],
            proof=f"{anchor} {bridge_anchor}",
            interface_lookup=lambda _fact_id: interface,
            convention_profile_ids=[self.convention_id],
        )

    def test_predecessor_interface_binds_active_acceptance_event_and_review(self) -> None:
        fact = Fact(
            problem_id="v4-claims",
            author="import",
            predecessors=[],
            statement="Legacy imported statement.",
            proof="Legacy imported proof.",
        )
        path = self.store.facts_dir / f"{fact.fact_id}.md"
        path.write_text(serialize_fact(fact), encoding="utf-8")
        interface = self.store.statement_interface(fact.fact_id)
        self.assertEqual(
            interface["stored_fact_sha256"],
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        self.assertEqual(len(interface["acceptance_event_sha256"]), 64)
        self.assertEqual(len(interface["admission_review_id"]), 64)

    def test_revoked_predecessor_interface_cannot_enter_new_bundle(self) -> None:
        interface = {
            "schema_version": 3,
            "policy_revision": "legacy-projection",
            "fact_id": "1" * 16,
            "statement_sha256": "2" * 64,
            "stored_fact_sha256": "3" * 64,
            "acceptance_event_sha256": "4" * 64,
            "admission_review_id": "5" * 64,
            "clauses": [
                {
                    "clause_id": "legacy-full",
                    "text": "statement",
                    "hypothesis_labels": [],
                    "quantifier_ids": [],
                }
            ],
            "glossary_introduces": {},
        }
        from mathgraph.contracts import sha256_json

        interface["interface_sha256"] = sha256_json(interface)
        with self.assertRaisesRegex(ValueError, "inactive"):
            validate_statement_interface(interface, active_fact_ids=set())


if __name__ == "__main__":
    unittest.main()
