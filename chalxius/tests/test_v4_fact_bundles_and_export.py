from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mathgraph.fact_bundles import (
    DOMAIN_CLAUSES,
    FactBundleStore,
    build_claim_card,
    lint_expert_document,
    validate_domain_certificate_statement,
    validate_interpret_mechanism,
    validate_terminology,
)
from mathgraph.model import Fact
from mathgraph.store import MathGraphStore


class V4FactBundleAndExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore._for_inherited_chalk_fixture(
            self.root
        )
        self.store.initialize(
            project_id="v4-fact-bundle",
            title="V4 fact bundle",
            workflow_evidence_version=4,
            reasoning_mode=None,
        )
        self.bundles = self.store.fact_bundles()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _facts(self) -> tuple[Fact, Fact]:
        first = Fact(
            problem_id="v4-fact-bundle",
            author="worker",
            predecessors=[],
            statement="[CLAIM:A] First lemma.",
            proof="Direct proof.",
        )
        second = Fact(
            problem_id="v4-fact-bundle",
            author="worker",
            predecessors=[first.fact_id],
            statement="[CLAIM:B] Second lemma.",
            proof="Use the first lemma.",
        )
        return first, second

    def _submit(self) -> str:
        first, second = self._facts()
        return self.bundles.submit(
            {
                "schema_version": 4,
                "policy_revision": "mathgraph-0.3.0",
                "project_id": "v4-fact-bundle",
                "facts": [
                    first.as_submission_dict(),
                    second.as_submission_dict(),
                ],
                "bundle_claim": "The two lemmas form one atomic mini-DAG.",
            },
            worker="worker",
            external_fact_exists=lambda _fact_id: False,
        )

    def _record_clean_review(self, bundle_id: str) -> str:
        manifest = self.bundles.manifest(bundle_id)
        task = self.store.fact_bundle_verifier_task(bundle_id)
        return self.bundles.record_review(
            bundle_id,
            {
                "fact_bundle_id": bundle_id,
                "manifest_sha256": manifest["manifest_sha256"],
                "verification_manifest_sha256": task[
                    "verification_manifest_sha256"
                ],
                "packet_sha256": task["packet_sha256"],
                "verdict": "correct",
                "findings": [],
                "reviewer": "fresh-verifier",
            },
        )

    def test_fact_bundle_is_invisible_before_accept_marker(self) -> None:
        bundle_id = self._submit()
        self.assertEqual(self.bundles.accepted_fact_paths(), {})
        self.assertFalse(
            (self.bundles.root / bundle_id / "ACCEPTED.json").exists()
        )

    def test_fact_bundle_becomes_visible_all_at_once(self) -> None:
        bundle_id = self._submit()
        manifest = self.bundles.manifest(bundle_id)
        review_id = self._record_clean_review(bundle_id)
        marker = self.store.admit_fact_bundle(
            bundle_id,
            review_id=review_id,
        )
        visible = self.bundles.accepted_fact_paths()
        self.assertEqual(set(visible), set(manifest["fact_ids"]))
        self.assertEqual(marker["fact_ids"], manifest["fact_ids"])
        self.assertEqual(set(self.store.fact_ids()), set(manifest["fact_ids"]))

    def test_fact_bundle_cycle_is_rejected(self) -> None:
        first, second = self._facts()
        # Exercise the mini-DAG gate directly: construction of a valid
        # content-addressed cyclic bundle is intentionally impossible.
        first.predecessors = [second.fact_id]
        second.predecessors = [first.fact_id]
        with self.assertRaisesRegex(ValueError, "cycle"):
            FactBundleStore._topological_order(
                {first.fact_id: first, second.fact_id: second}
            )

    def test_partial_fact_bundle_crash_has_zero_visible_facts(self) -> None:
        bundle_id = self._submit()
        marker = self.bundles.root / bundle_id / "ACCEPTED.json"
        marker.write_text('{"incomplete": true}\n')
        self.assertEqual(self.bundles.accepted_fact_paths(), {})
        self.assertFalse(self.bundles.audit()["ok"])
        self.assertEqual(self.store.fact_ids(), [])

    def test_fact_bundle_main_graph_search_context_closure_targets_and_revoke(self) -> None:
        first, second = self._facts()
        bundle_id = self._submit()
        manifest = self.bundles.manifest(bundle_id)
        review_id = self._record_clean_review(bundle_id)
        self.store.admit_fact_bundle(bundle_id, review_id=review_id)
        self.assertEqual(
            self.store.closure([second.fact_id]),
            [first.fact_id, second.fact_id],
        )
        self.assertEqual(
            self.store.search("Second lemma")[0]["fact_id"],
            second.fact_id,
        )
        context = self.store.bounded_context(second.fact_id)
        self.assertIn(first.fact_id, context)
        self.assertIn(second.fact_id, context)
        campaign_id = self.store.campaigns().active()
        assert campaign_id is not None
        self.store.campaigns().target_add(
            campaign_id,
            {
                "role": "headline_proof",
                "subject_kind": "fact",
                "subject_id": second.fact_id,
                "label": "Atomic bundle target",
            },
            actor="main",
            fact_exists=lambda fact_id: fact_id in self.store.fact_ids(),
        )
        self.store.sync_active_campaign_targets(
            campaign_id=campaign_id
        )
        candidate_paths = {
            fact_id: path
            for fact_id, path in self.bundles.accepted_fact_paths().items()
        }
        revoked = self.store.revoke(
            first.fact_id,
            reason="The atomic root was challenged.",
            actor="operator",
        )
        self.assertEqual(set(revoked), {first.fact_id, second.fact_id})
        self.assertEqual(self.store.fact_ids(), [])
        self.assertEqual(self.store.targets(), [])
        for fact_id, path in candidate_paths.items():
            self.assertTrue(path.exists(), fact_id)
        report = self.store.audit()
        self.assertTrue(report.current_ok, report.errors)

    def test_atomic_verifier_packet_includes_external_statement_not_proof(
        self,
    ) -> None:
        admitted_bundle = self._submit()
        review_id = self._record_clean_review(admitted_bundle)
        self.store.admit_fact_bundle(
            admitted_bundle,
            review_id=review_id,
        )
        predecessor, _ = self._facts()
        candidate = Fact(
            problem_id="v4-fact-bundle",
            author="second-worker",
            predecessors=[predecessor.fact_id],
            statement="[CLAIM:EXTERNAL] External predecessor consequence.",
            proof="Use only the admitted predecessor statement.",
        )
        bundle_id = self.bundles.submit(
            {
                "schema_version": 4,
                "policy_revision": "mathgraph-0.3.0",
                "project_id": "v4-fact-bundle",
                "facts": [candidate.as_submission_dict()],
                "bundle_claim": "Exercise external predecessor packaging.",
            },
            worker="second-worker",
            external_fact_exists=lambda fact_id: (
                fact_id in self.store.fact_ids()
            ),
        )
        task = self.store.fact_bundle_verifier_task(bundle_id)
        packet = Path(task["packet_path"]).read_text(encoding="utf-8")
        self.assertIn(predecessor.statement, packet)
        self.assertNotIn(predecessor.proof, packet)
        self.assertTrue(
            (
                self.bundles.root
                / bundle_id
                / "interfaces"
                / f"{predecessor.fact_id}.json"
            ).is_file()
        )

    def test_atomic_review_binds_untampered_verifier_packet(self) -> None:
        bundle_id = self._submit()
        manifest = self.bundles.manifest(bundle_id)
        task = self.store.fact_bundle_verifier_task(bundle_id)
        Path(task["packet_path"]).write_text(
            "tampered packet\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "packet hash"):
            self.bundles.record_review(
                bundle_id,
                {
                    "fact_bundle_id": bundle_id,
                    "manifest_sha256": manifest["manifest_sha256"],
                    "verification_manifest_sha256": task[
                        "verification_manifest_sha256"
                    ],
                    "packet_sha256": task["packet_sha256"],
                    "verdict": "correct",
                    "findings": [],
                    "reviewer": "fresh-verifier",
                },
            )
        self.assertFalse(
            (self.bundles.root / bundle_id / "ACCEPTED.json").exists()
        )
        self.assertFalse(self.bundles.audit()["ok"])

    def test_domain_certificate_reuse_requires_admitted_fact(self) -> None:
        missing = "1" * 16
        fact = Fact(
            problem_id="v4-fact-bundle",
            author="worker",
            predecessors=[missing],
            statement="[CLAIM:D] Domain consequence.",
            proof="Uses a domain certificate.",
        )
        with self.assertRaisesRegex(ValueError, "neither internal nor admitted"):
            self.bundles.submit(
                {
                    "schema_version": 4,
                    "policy_revision": "mathgraph-0.3.0",
                    "project_id": "v4-fact-bundle",
                    "facts": [fact.as_submission_dict()],
                    "bundle_claim": "Invalid domain reuse.",
                },
                worker="worker",
                external_fact_exists=lambda _fact_id: False,
            )

    def test_domain_certificate_has_vital_point_and_partner_regularity_clauses(self) -> None:
        statement = "\n".join(
            f"[CLAIM:{clause}] Verified {clause}."
            for clause in sorted(DOMAIN_CLAUSES)
        )
        validate_domain_certificate_statement(statement)
        incomplete = statement.replace(
            "[CLAIM:DOMAIN-VITAL-POINTS]",
            "[CLAIM:REMOVED-VITAL]",
        )
        with self.assertRaisesRegex(ValueError, "DOMAIN-VITAL-POINTS"):
            validate_domain_certificate_statement(incomplete)

    def _terminology(self) -> list[dict]:
        return [
            {
                "key": "cap",
                "term": "cold cap",
                "definition": "a local regularization contribution",
                "origin": "local_shorthand",
                "source_locator": "",
                "export_policy": "replace",
                "replacement": "local regularization contribution",
                "proof_anchor": "[TERM:cap]",
            }
        ]

    def test_expert_export_replaces_local_shorthand(self) -> None:
        terminology = validate_terminology(
            self._terminology(),
            proof="We define the term here. [TERM:cap]",
        )
        claim_card = {
            "terminology": terminology,
            "literal_source_claim": "Literal claim",
            "convention_profile": "Convention C",
            "admitted_conclusion": "Conclusion",
            "AI-assistance disclosure": "AI-assisted",
        }
        bad = (
            "Literal claim Convention C Conclusion AI-assisted. "
            "The cold cap vanishes."
        )
        self.assertTrue(lint_expert_document(bad, claim_card=claim_card))
        good = (
            "Literal claim. Convention C. Conclusion. AI-assisted. "
            "The local regularization contribution vanishes."
        )
        self.assertEqual(
            lint_expert_document(good, claim_card=claim_card),
            [],
        )
        self.assertTrue(
            lint_expert_document(
                good.replace(
                    "local regularization contribution",
                    "Cold Cap",
                ),
                claim_card=claim_card,
            )
        )

    def test_expert_lint_rejects_hidden_fields_and_ai_placeholder(
        self,
    ) -> None:
        fact = Fact(
            problem_id="v4-fact-bundle",
            author="worker",
            predecessors=[],
            statement="[CLAIM:EXPORT] Exported conclusion.",
            proof="Direct.",
        )
        card = build_claim_card(
            fact=fact,
            audience="advisor",
            literal_source_claim="Literal source claim.",
            researcher_variant="No researcher variant.",
            variant_diff=[],
            source_locator="Primary source v1.",
            convention_profile="Convention C.",
            reproduction_bundle=[],
        )
        required = [
            card["literal_source_claim"],
            card["researcher_variant"],
            card["source_locator"],
            card["convention_profile"],
            card["admitted_conclusion"],
            card["AI-assistance disclosure"],
        ]
        hidden = (
            "Advisor summary with no assurance fields.\n<!-- "
            + " | ".join(required)
            + " -->"
        )
        hidden_errors = lint_expert_document(
            hidden,
            claim_card=card,
        )
        self.assertGreaterEqual(len(hidden_errors), 6)

        placeholder = "\n".join(required)
        placeholder_errors = lint_expert_document(
            placeholder,
            claim_card=card,
        )
        self.assertTrue(
            any("placeholder" in error for error in placeholder_errors)
        )
        completed = "\n".join(required[:-1]) + (
            "\nAI assistance: AI tools assisted drafting and protocol "
            "checks; the named verifier independently reviewed the claims."
        )
        self.assertEqual(
            lint_expert_document(completed, claim_card=card),
            [],
        )

    def test_expert_export_fails_on_forbidden_or_legacy_unknown_term(self) -> None:
        entries = self._terminology()
        entries[0] = {
            **entries[0],
            "origin": "legacy_unknown",
            "export_policy": "forbid",
            "replacement": "",
        }
        terminology = validate_terminology(
            entries,
            proof="[TERM:cap]",
        )
        errors = lint_expert_document(
            "cold cap",
            claim_card={"terminology": terminology},
        )
        self.assertTrue(errors)

    def test_expert_document_linter_preserves_claim_convention_and_disclosure(self) -> None:
        card = {
            "terminology": [],
            "literal_source_claim": "Literal v1",
            "convention_profile": "Convention X",
            "admitted_conclusion": "Admitted theorem",
            "AI-assistance disclosure": "AI-assisted",
        }
        errors = lint_expert_document(
            "Admitted theorem only.",
            claim_card=card,
        )
        self.assertEqual(len(errors), 3)

    def test_claim_card_distinguishes_literal_and_researcher_variant(self) -> None:
        registry = self.store.claims()
        convention_id = registry.add_convention(
            {
                "theory": "toy signed coefficient",
                "source_version": "arXiv:2601.00001v1",
                "source_artifact_sha256": "a" * 64,
                "authority": "literal_source",
                "dimensions": {"coefficient_sign": "source literal"},
            },
            actor="operator",
        )
        literal_id = registry.add_claim(
            {
                "kind": "published_literal",
                "title": "Literal negative-sign claim",
                "statement": "The exact coefficient is -1.",
                "source": {
                    "title": "Toy signed source",
                    "version": "arXiv:2601.00001v1",
                    "artifact_sha256": "b" * 64,
                    "locator": "Equation (1)",
                    "retrieved_at": "2026-07-25",
                },
                "convention_profile_id": convention_id,
                "authority": "literal_source",
            },
            actor="operator",
        )
        variant_id = registry.create_variant(
            literal_id,
            {
                "title": "Researcher positive-sign variant",
                "statement": "Under the researcher convention, the coefficient is +1.",
                "variant_diff": [
                    {
                        "field": "coefficient_sign",
                        "from": "-1",
                        "to": "+1",
                        "authority": "researcher_defined",
                    }
                ],
            },
            actor="researcher",
        )
        literal = registry.show_claim(literal_id)
        variant = registry.show_claim(variant_id)
        self.assertEqual(variant["parent_claim_id"], literal_id)
        self.assertNotEqual(
            literal["statement_sha256"],
            variant["statement_sha256"],
        )

        fact = Fact(
            problem_id="signed-variant-export",
            author="worker",
            predecessors=[],
            statement="[CLAIM:MAIN] The researcher convention gives +1.",
            proof="Direct convention transport.",
        )
        card = build_claim_card(
            fact=fact,
            audience="expert",
            literal_source_claim=literal["statement"],
            researcher_variant=variant["statement"],
            variant_diff=variant["variant_diff"],
            source_locator=literal["source"]["locator"],
            convention_profile=(
                f"{convention_id}: coefficient_sign=source literal"
            ),
            reproduction_bundle=[],
        )
        mixed_document = "\n".join(
            [
                card["researcher_variant"],
                card["source_locator"],
                card["convention_profile"],
                card["admitted_conclusion"],
                "AI assistance: AI assisted protocol checking and drafting.",
            ]
        )
        self.assertIn(
            "expert document omits claim-card field: literal_source_claim",
            lint_expert_document(mixed_document, claim_card=card),
        )
        correct_document = "\n".join(
            [
                card["literal_source_claim"],
                card["researcher_variant"],
                card["source_locator"],
                card["convention_profile"],
                card["admitted_conclusion"],
                "AI assistance: AI assisted protocol checking and drafting.",
            ]
        )
        self.assertEqual(
            lint_expert_document(correct_document, claim_card=card),
            [],
        )

    def test_interpret_mode_requires_falsifiable_consequence_or_dead_end(self) -> None:
        mechanism = {
            "explains_refs": ["claim-1"],
            "domain_clause_refs": ["DOMAIN-BASE"],
            "convention_profile_ids": [],
            "mechanism_statement": "A cancellation mechanism may operate.",
            "falsifiable_consequences": [],
            "known_failures": [],
            "remaining_gaps": ["coefficient"],
            "truth_status": "exploration",
        }
        with self.assertRaisesRegex(ValueError, "falsifiable"):
            validate_interpret_mechanism(mechanism)
        mechanism["falsifiable_consequences"] = [
            {
                "id": "P1",
                "statement": "The coefficient vanishes in genus two.",
                "suggested_mode": "compute",
            }
        ]
        self.assertEqual(
            validate_interpret_mechanism(mechanism)["truth_status"],
            "exploration",
        )

    def test_interpret_mechanism_remains_exploration_until_separate_fact_admission(self) -> None:
        mechanism = {
            "explains_refs": [],
            "domain_clause_refs": [],
            "convention_profile_ids": [],
            "mechanism_statement": "Candidate mechanism.",
            "falsifiable_consequences": [
                {
                    "id": "P",
                    "statement": "Testable prediction.",
                    "suggested_mode": "refute",
                }
            ],
            "known_failures": [],
            "remaining_gaps": [],
            "truth_status": "admitted",
        }
        with self.assertRaisesRegex(ValueError, "exploration"):
            validate_interpret_mechanism(mechanism)
        self.assertEqual(self.store.fact_ids(), [])


if __name__ == "__main__":
    unittest.main()
