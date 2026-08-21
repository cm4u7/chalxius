from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from mathgraph.applicability import validate_external_refs_for_submission
from mathgraph.cli import build_parser, main
from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.elementary import validate_elementary_uses_for_submission
from mathgraph.graph import DependencyGraph
from mathgraph.markdown import (
    parse_fact_markdown,
    serialize_fact,
    validate_fact_round_trip,
)
from mathgraph.model import Fact, compute_fact_id
from mathgraph.orchestrator import (
    create_repair_round,
    create_round,
    create_verifier_assignment,
    ingest_return,
    round_status,
    validate_return,
)
from mathgraph.roles import allowed_commands
from mathgraph.store import MathGraphStore
from mathgraph.worker_returns import validate_worker_return


def review_fact(
    store: MathGraphStore,
    fact_id: str,
    *,
    verdict: str = "correct",
    reviewer: str = "fresh-test-verifier",
    critical_errors: list[str] | None = None,
    gaps: list[str] | None = None,
    repair_hints: list[str] | None = None,
) -> str:
    frozen = store.freeze_verification_packet(fact_id)
    path = store.record_review(
        {
            "fact_id": fact_id,
            "submission_sha256": frozen["submission_sha256"],
            "packet_sha256": frozen["packet_sha256"],
            "verdict": verdict,
            "critical_errors": critical_errors or [],
            "gaps": gaps or [],
            "repair_hints": repair_hints or [],
            "reviewer": reviewer,
        }
    )
    return path.stem


def accepted_fact(
    store: MathGraphStore,
    *,
    statement: str,
    proof: str,
    predecessors: list[str] | None = None,
    author: str = "test-worker",
    glossary: dict[str, str] | None = None,
    intuition: str = "",
) -> str:
    fact = Fact(
        problem_id=store.project_id(),
        author=author,
        predecessors=predecessors or [],
        statement=statement,
        proof=proof,
        glossary_introduces=glossary or {},
        intuition=intuition,
    )
    store.submit(fact, worker=author)
    review_id = review_fact(store, fact.fact_id)
    return store.admit(fact.fact_id, review_id=review_id, gateway="test-gateway")


def bound_return(
    manifest: dict[str, object],
    assignment: dict[str, str],
    *,
    outcome: str,
    **specific: object,
) -> dict[str, object]:
    payload = {
        "project_id": manifest["project_id"],
        "round_id": manifest["round_id"],
        "assignment_id": assignment["assignment_id"],
        "assignment_sha256": assignment["assignment_sha256"],
        "worker": assignment["worker_id"],
        "memory_id": assignment["memory_id"],
        "mode": assignment["mode"],
        "outcome": outcome,
        "notes": "bounded test return",
        **specific,
    }
    if outcome == "fact_submission" and "claim_relation" not in payload:
        payload["claim_relation"] = "proves"
    return payload


def source_audit_record(
    *,
    artifact_sha256: str,
    artifact_locator: str,
) -> dict[str, object]:
    core: dict[str, object] = {
        "artifact_sha256": artifact_sha256,
        "artifact_locator": artifact_locator,
        "checked_at": "2026-07-24",
        "issue_searches": [
            {
                "kind": "version_history",
                "query": "Primary source exact version history",
                "locator": "https://example.org/primary-source/versions",
                "finding": "Version 3 is the cited version; no statement drift was found.",
            },
            {
                "kind": "errata",
                "query": "Primary source exact title erratum correction",
                "locator": "https://example.org/primary-source/errata",
                "finding": "No applicable erratum was listed.",
            },
            {
                "kind": "retraction_or_counterexample",
                "query": "Primary source exact title retraction counterexample false",
                "locator": "https://example.org/primary-source/status",
                "finding": "No retraction or known counterexample was found.",
            },
        ],
        "unresolved_signals": [],
        "finding": "The source-level version and status checks found no unresolved signal.",
    }
    return {**core, "audit_sha256": sha256_json(core)}


def promote_ref_to_strict(ref: dict[str, object], trigger: str) -> None:
    audit = ref["critical_audit"]
    assert isinstance(audit, dict)
    audit["profile"] = "strict"
    audit["risk_triggers"] = [trigger]
    checks = audit["sanity_checks"]
    assert isinstance(checks, list)
    checks.extend(
        [
            {
                "kind": "boundary_or_toy_case",
                "status": "pass",
                "finding": "The base test object is consistent with the stated implication.",
            },
            {
                "kind": "statement_proof_consistency",
                "status": "pass",
                "finding": "The proof concludes exactly property P under H.",
            },
        ]
    )


def certified_result_ref(key: str = "SRC") -> dict[str, object]:
    statement_text = "Theorem 2.1. Every object X satisfying H has property P."
    artifact_sha256 = sha256_bytes(b"exact primary source artifact")
    artifact_locator = "https://example.org/primary-source/version-3.pdf"
    return {
        "key": key,
        "title": "Primary source",
        "url": "https://example.org/primary-source",
        "use_kind": "result",
        "cited_for": "The exact implication used in the test fact.",
        "source_evidence_version": 3,
        "source_trace": {
            "artifact_sha256": artifact_sha256,
            "artifact_locator": artifact_locator,
            "retrieved_at": "2026-07-24",
            "statement_locator": "Theorem 2.1, version 3, p. 7",
            "statement_text": statement_text,
            "statement_sha256": sha256_bytes(statement_text.encode("utf-8")),
            "inspection_methods": ["rendered_primary"],
        },
        "critical_audit": {
            "profile": "baseline",
            "risk_triggers": [],
            "sanity_checks": [
                {
                    "kind": "notation_and_binding",
                    "status": "pass",
                    "finding": "Every symbol in the statement is introduced.",
                },
                {
                    "kind": "type_and_domain",
                    "status": "pass",
                    "finding": "X and H have the same types in the statement and proof.",
                },
                {
                    "kind": "quantifiers_and_scope",
                    "status": "pass",
                    "finding": "The universal quantifier and ambient scope agree.",
                },
            ],
            "source_audit": source_audit_record(
                artifact_sha256=artifact_sha256,
                artifact_locator=artifact_locator,
            ),
            "source_audit_reuse": {
                "mode": "fresh",
                "reused_at": "2026-07-24",
                "origin": "current_submission",
            },
            "assessment": "as_stated",
            "issues": [],
            "justification": "The baseline theorem and source-level checks found no defect.",
            "proof_anchor": f"[CRIT:{key}:USE]",
        },
        "applicability": {
            "source_version": "version 3",
            "source_locator": "Theorem 2.1, version 3, p. 7",
            "source_scope": "Objects X satisfying hypothesis H.",
            "target_scope": "The test object X_0.",
            "source_conclusion": "Every such X has property P.",
            "used_conclusion": "X_0 has property P.",
            "hypothesis_map": [
                {
                    "source_hypothesis": "X satisfies H.",
                    "target_witness": "The proof checks H for X_0.",
                    "proof_anchor": f"[APP:{key}:H1]",
                }
            ],
            "convention_map": [
                {
                    "source_convention": "No material convention beyond ordinary equality.",
                    "target_convention": "The same convention is used in the target.",
                    "proof_anchor": f"[APP:{key}:C1]",
                }
            ],
            "transport_obligations": [],
            "exclusions_checked": ["The adjacent definitions and remarks were checked."],
            "strength_comparison": "exact",
            "verdict": "direct",
            "proof_anchor": f"[APP:{key}:USE]",
        },
    }


def certified_formula_ref(key: str = "FORMULA") -> dict[str, object]:
    ref = certified_result_ref(key)
    promote_ref_to_strict(ref, "formula_or_sign_sensitive")
    ref["use_kind"] = "formula"
    ref["cited_for"] = "The exact displayed formula, including its outer differential."
    artifact_sha256 = sha256_bytes(b"exact primary formula artifact")
    source_trace = ref["source_trace"]
    assert isinstance(source_trace, dict)
    source_trace["artifact_sha256"] = artifact_sha256
    audit = ref["critical_audit"]
    assert isinstance(audit, dict)
    audit["source_audit"] = source_audit_record(
        artifact_sha256=artifact_sha256,
        artifact_locator=str(source_trace["artifact_locator"]),
    )
    ref["source_fidelity"] = {
        "artifact_sha256": artifact_sha256,
        "inspection_methods": ["rendered_primary"],
        "load_bearing_tokens": ["outer d_z", "bracket scope", "minus sign"],
        "finding": "The rendered primary page places d_z outside the bracket.",
        "proof_anchor": f"[SRC:{key}:GLYPH]",
    }
    return ref


def elementary_use(
    key: str = "IFT1",
    category: str = "local_inverse_implicit",
) -> dict[str, object]:
    return {
        "key": key,
        "result": "Holomorphic inverse-function theorem at one point",
        "category": category,
        "hypothesis_witnesses": [
            "The proof displays a finite-dimensional holomorphic map and computes its Jacobian "
            "determinant at the base point to be 1."
        ],
        "used_conclusion": "A unique local holomorphic inverse germ exists.",
        "scope_limitations": [
            "Local germ only.",
            "No uniform parameter, continuation, or monodromy conclusion.",
        ],
        "reconstruction": (
            "Apply the finite-dimensional holomorphic inverse-function theorem to the displayed "
            "map at the point where the determinant is 1, then restrict to small neighborhoods."
        ),
        "proof_anchor": f"[ELM:{key}]",
    }


class ModelTests(unittest.TestCase):
    def test_content_id_is_order_and_whitespace_stable(self) -> None:
        first = compute_fact_id(
            problem_id="p",
            predecessors=["b", "a"],
            glossary_introduces={"y": "Y", "x": "X"},
            statement="A   statement\nwith spacing",
            proof="A proof",
        )
        second = compute_fact_id(
            problem_id="p",
            predecessors=["a", "b"],
            glossary_introduces={"x": "X", "y": "Y"},
            statement="A statement with spacing",
            proof="A   proof",
        )
        self.assertEqual(first, second)

    def test_markdown_round_trip_preserves_colons_and_internal_headings(self) -> None:
        fact = Fact(
            problem_id="p:family",
            author="worker:one",
            predecessors=[],
            statement="The disk exists.\n\n## Scope\nThis heading is part of the statement.",
            proof="Take the disk.\n\n## Lemma\nIts radius is positive.",
            glossary_introduces={"x:y": "The disk {t in C: |t|<delta}."},
            intuition="Local geometry.\n\n## Picture\nA small neighbourhood.",
            external_refs=[{"doi": "10.1/example", "scope": {"pages": [1, 2]}}],
            elementary_uses=[elementary_use()],
        )
        rendered = validate_fact_round_trip(fact)
        parsed = parse_fact_markdown(rendered)
        self.assertEqual(parsed.as_submission_dict(), fact.as_submission_dict())
        self.assertEqual(parsed.fact_id, fact.fact_id)

    def test_frontmatter_newline_is_rejected_before_submission(self) -> None:
        fact = Fact(
            problem_id="p",
            author="worker\ninjected: true",
            predecessors=[],
            statement="S",
            proof="P",
        )
        self.assertIn("author contains a newline", fact.validate())


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "project"
        self.store = MathGraphStore._for_legacy_workflow_fixture(self.root)
        self.store.initialize(project_id="test-problem", title="Test graph")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def candidate(
        self,
        *,
        statement: str = "Candidate.",
        proof: str = "Proof.",
        author: str = "worker",
        problem_id: str = "test-problem",
        predecessors: list[str] | None = None,
    ) -> Fact:
        return Fact(
            problem_id=problem_id,
            author=author,
            predecessors=predecessors or [],
            statement=statement,
            proof=proof,
        )

    def test_new_project_labels_container_and_workflow_versions(self) -> None:
        project = self.store.project()
        self.assertEqual(project["schema_version"], 2)
        self.assertEqual(project["workflow_evidence_version"], 3)
        project["workflow_evidence_version"] = 4
        self.store.project_path.write_text(json.dumps(project), encoding="utf-8")
        report = self.store.audit()
        self.assertFalse(report.ok)
        self.assertIn(
            "project workflow_evidence_version must be 3 when explicitly declared",
            report.workflow_errors,
        )

    def test_invalid_v4_acceptance_event_is_not_legacy_provenance(self) -> None:
        facts = []
        for index, evidence_version in enumerate((4, "4", 5, True)):
            fact = self.candidate(
                statement=f"Unprovenanced fixture {index} is visible.",
                proof="Fixture bytes only.",
            )
            facts.append(fact)
            self.store._write_bytes_once(
                self.store.fact_path(fact.fact_id),
                validate_fact_round_trip(fact).encode("utf-8"),
            )
            self.store._append_jsonl(
                self.store.verification_log,
                {
                    "event": "accepted",
                    "evidence_version": evidence_version,
                    "fact_id": fact.fact_id,
                    "event_id": "0" * 64,
                },
            )
        report = self.store.audit()
        self.assertFalse(report.current_ok)
        for fact in facts:
            self.assertIn(
                "verified fact has no admission/import provenance: "
                + fact.fact_id,
                report.workflow_errors,
            )
        self.assertEqual(
            sum(
                "unsupported evidence_version" in error
                for error in report.workflow_errors
            ),
            len(facts) - 1,
        )

    def test_verification_gate_hash_binding_state_and_closure(self) -> None:
        root = accepted_fact(self.store, statement="A.", proof="A is an axiom.")
        child_fact = self.candidate(
            statement="B.",
            proof=f"By fact {root}, B follows.",
            predecessors=[root],
        )
        self.store.submit(child_fact, worker="worker")
        frozen = self.store.freeze_verification_packet(child_fact.fact_id)
        with self.assertRaises(ValueError):
            self.store.admit(child_fact.fact_id, review_id="0" * 64)
        review_id = review_fact(self.store, child_fact.fact_id, reviewer="independent")
        child = self.store.admit(child_fact.fact_id, review_id=review_id)
        self.assertEqual(self.store.submission(child)["status"], "accepted")
        self.assertEqual(self.store.submission(child)["accepted_review_id"], review_id)
        self.assertEqual(frozen["packet_sha256"], self.store.review(review_id)["packet_sha256"])
        self.store.set_targets([child])
        self.assertEqual(self.store.closure([child]), [root, child])
        report = self.store.audit()
        self.assertTrue(report.ok, report.errors)
        self.assertEqual(report.target_closure, 2)

    def test_review_schema_is_strict_append_only_and_post_accept_frozen(self) -> None:
        fact = self.candidate()
        self.store.submit(fact, worker="worker")
        frozen = self.store.freeze_verification_packet(fact.fact_id)
        malformed = {
            "fact_id": fact.fact_id,
            "submission_sha256": frozen["submission_sha256"],
            "packet_sha256": frozen["packet_sha256"],
            "verdict": "correct",
            "critical_errors": [],
            "gaps": [],
            "repair_hints": [],
            "reviewer": {"reviewer_id": "independent"},
        }
        with self.assertRaisesRegex(ValueError, "reviewer must be a nonempty string"):
            self.store.record_review(malformed)
        malformed["reviewer"] = "worker"
        with self.assertRaisesRegex(ValueError, "independent"):
            self.store.record_review(malformed)
        review_id = review_fact(self.store, fact.fact_id, reviewer="independent")
        review_path = self.store.review_path(review_id)
        original = review_path.read_bytes()
        self.store.admit(fact.fact_id, review_id=review_id)
        with self.assertRaisesRegex(ValueError, "cannot be re-reviewed"):
            self.store.record_review(
                {
                    **malformed,
                    "reviewer": "second-verifier",
                    "verdict": "reject",
                    "critical_errors": ["new objection"],
                }
            )
        self.assertEqual(review_path.read_bytes(), original)
        self.assertTrue(self.store.audit().ok)

    def test_tampered_packet_blocks_admission_and_fails_workflow_audit(self) -> None:
        fact = self.candidate()
        self.store.submit(fact, worker="worker")
        review_id = review_fact(self.store, fact.fact_id, reviewer="independent")
        manifest = self.store.packet_manifest(fact.fact_id)
        packet_path = self.root / manifest["packet_relpath"]
        packet_path.write_text("tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "packet hash mismatch"):
            self.store.admit(fact.fact_id, review_id=review_id)
        report = self.store.audit()
        self.assertFalse(report.ok)
        self.assertTrue(report.workflow_errors)
        self.assertFalse(report.graph_errors)

    def test_fresh_verifier_task_contains_only_declared_packet_scope(self) -> None:
        declared = accepted_fact(
            self.store,
            statement="Declared premise: alpha.",
            proof="Axiom alpha.",
        )
        accepted_fact(
            self.store,
            statement="UNRELATED SECRET PREMISE: omega.",
            proof="Axiom omega.",
        )
        memory_id = self.store.memory_add(
            {
                "kind": "conjecture",
                "claim": "ASSIGNED RESEARCH CLAIM MUST ENTER PACKET",
            },
            actor="main",
        )
        self.store.memory_add(
            {
                "kind": "direction",
                "claim": "UNRELATED PRIVATE EXPLORATION MEMORY",
            },
            actor="main",
        )
        fact = self.candidate(
            statement="Conclusion from alpha.",
            proof=f"Use {declared}.",
            predecessors=[declared],
        )
        self.store.submit(fact, worker="worker", task_id=memory_id)
        task = create_verifier_assignment(self.store, fact.fact_id)
        packet = Path(task["packet_path"]).read_text(encoding="utf-8")
        self.assertIn("Declared premise: alpha", packet)
        self.assertNotIn("UNRELATED SECRET PREMISE", packet)
        self.assertIn("ASSIGNED RESEARCH CLAIM MUST ENTER PACKET", packet)
        self.assertNotIn("UNRELATED PRIVATE EXPLORATION MEMORY", packet)
        self.assertNotIn("--role worker search", packet)
        self.assertEqual(
            task["assigned_claim"],
            "ASSIGNED RESEARCH CLAIM MUST ENTER PACKET",
        )
        self.assertEqual(task["claim_relation"], "proves")
        self.assertEqual(task["spawn_contract"]["fork_turns"], "none")
        self.assertEqual(allowed_commands("verifier"), set())

    def test_external_result_requires_complete_applicability_certificate(self) -> None:
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The test object has property P.",
            proof="A bare citation is not a proof.",
            external_refs=[
                {
                    "key": "SRC",
                    "title": "Primary source",
                    "url": "https://example.org/primary-source",
                    "use_kind": "result",
                    "cited_for": "Property P.",
                }
            ],
        )
        with self.assertRaisesRegex(ValueError, "applicability must be an object"):
            self.store.submit(fact, worker="worker")
        self.assertFalse(self.store.submission_path(fact.fact_id).exists())

    def test_external_arxiv_source_must_pin_a_version(self) -> None:
        ref = certified_result_ref()
        ref.pop("url")
        ref["arxiv"] = "2604.25622"
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The test object has property P.",
            proof=(
                "Check H [APP:SRC:H1]. Match conventions [APP:SRC:C1]. "
                "Use P [APP:SRC:USE]."
            ),
            external_refs=[ref],
        )
        with self.assertRaisesRegex(ValueError, "arxiv must pin an explicit vN"):
            self.store.submit(fact, worker="worker")

    def test_new_external_result_requires_trace_and_critical_audit(self) -> None:
        ref = certified_result_ref()
        ref.pop("source_evidence_version")
        ref.pop("source_trace")
        ref.pop("critical_audit")
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The test object has property P.",
            proof=(
                "Check H [APP:SRC:H1]. Match conventions [APP:SRC:C1]. "
                "Use P [APP:SRC:USE]."
            ),
            external_refs=[ref],
        )
        with self.assertRaisesRegex(ValueError, "source_evidence_version must be 3"):
            self.store.submit(fact, worker="worker")

    def test_external_statement_transcription_hash_is_exact(self) -> None:
        ref = certified_result_ref()
        trace = ref["source_trace"]
        self.assertIsInstance(trace, dict)
        trace["statement_text"] = "Theorem 2.1. A changed transcription."
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The test object has property P.",
            proof=(
                "Check H [APP:SRC:H1]. Match conventions [APP:SRC:C1]. "
                "Use P [APP:SRC:USE]. Audit the source [CRIT:SRC:USE]."
            ),
            external_refs=[ref],
        )
        with self.assertRaisesRegex(ValueError, "statement_sha256 does not match"):
            self.store.submit(fact, worker="worker")

    def test_arxiv_trace_locator_must_pin_the_same_version(self) -> None:
        ref = certified_result_ref()
        ref.pop("url")
        ref["arxiv"] = "arXiv:2604.25622v3"
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The test object has property P.",
            proof=(
                "Check H [APP:SRC:H1]. Match conventions [APP:SRC:C1]. "
                "Use P [APP:SRC:USE]. Audit the source [CRIT:SRC:USE]."
            ),
            external_refs=[ref],
        )
        with self.assertRaisesRegex(ValueError, "must contain the exact versioned arXiv id"):
            self.store.submit(fact, worker="worker")

    def test_critical_audit_requires_all_fixed_checks_and_searches(self) -> None:
        ref = certified_result_ref()
        audit = ref["critical_audit"]
        self.assertIsInstance(audit, dict)
        source_audit = audit["source_audit"]
        self.assertIsInstance(source_audit, dict)
        searches = source_audit["issue_searches"]
        self.assertIsInstance(searches, list)
        source_audit["issue_searches"] = [
            item
            for item in searches
            if isinstance(item, dict) and item.get("kind") != "errata"
        ]
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The test object has property P.",
            proof=(
                "Check H [APP:SRC:H1]. Match conventions [APP:SRC:C1]. "
                "Use P [APP:SRC:USE]. Audit the source [CRIT:SRC:USE]."
            ),
            external_refs=[ref],
        )
        with self.assertRaisesRegex(ValueError, "issue_searches.*missing=.*errata"):
            self.store.submit(fact, worker="worker")

    def test_source_level_audit_is_reused_once_for_repeated_exact_artifact(self) -> None:
        first = certified_result_ref("SRC1")
        second = certified_result_ref("SRC2")
        second_audit = second["critical_audit"]
        self.assertIsInstance(second_audit, dict)
        second_audit["source_audit_reuse"] = {
            "mode": "reused",
            "reused_at": "2026-07-24",
            "origin": "external_ref:SRC1",
        }
        proof = (
            "Check H for the first use [APP:SRC1:H1], match conventions [APP:SRC1:C1], "
            "and apply P [APP:SRC1:USE] after its source audit [CRIT:SRC1:USE]. "
            "Check H for the second use [APP:SRC2:H1], match conventions [APP:SRC2:C1], "
            "and apply P again [APP:SRC2:USE] using the shared source audit "
            "[CRIT:SRC2:USE]."
        )
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="Both exact source items have been applied.",
            proof=proof,
            external_refs=[first, second],
        )
        self.store.submit(fact, worker="worker")

        duplicate_work = certified_result_ref("SRC2")
        bad_fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The repeated source audit was redundantly rerun.",
            proof=proof,
            external_refs=[certified_result_ref("SRC1"), duplicate_work],
        )
        with self.assertRaisesRegex(
            ValueError,
            "must reuse external_ref:SRC1",
        ):
            self.store.submit(bad_fact, worker="worker")

    def test_source_audit_reuse_window_and_hash_are_enforced(self) -> None:
        stale = certified_result_ref()
        stale_audit = stale["critical_audit"]
        self.assertIsInstance(stale_audit, dict)
        stale_audit["source_audit_reuse"] = {
            "mode": "reused",
            "reused_at": "2026-08-24",
            "origin": "fact:0123456789abcdef:SRC",
        }
        proof = (
            "Check H [APP:SRC:H1]. Match conventions [APP:SRC:C1]. "
            "Use P [APP:SRC:USE]. Audit the source [CRIT:SRC:USE]."
        )
        stale_fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The stale source audit is rejected.",
            proof=proof,
            external_refs=[stale],
        )
        with self.assertRaisesRegex(ValueError, "30-day source-audit reuse window"):
            self.store.submit(stale_fact, worker="worker")

        drifted = certified_result_ref()
        drifted_audit = drifted["critical_audit"]
        self.assertIsInstance(drifted_audit, dict)
        source_audit = drifted_audit["source_audit"]
        self.assertIsInstance(source_audit, dict)
        source_audit["finding"] = "Changed after the audit hash was computed."
        drifted_fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The changed source audit hash is rejected.",
            proof=proof,
            external_refs=[drifted],
        )
        with self.assertRaisesRegex(ValueError, "canonical source-audit record"):
            self.store.submit(drifted_fact, worker="worker")

        dangling = certified_result_ref()
        dangling_audit = dangling["critical_audit"]
        self.assertIsInstance(dangling_audit, dict)
        dangling_audit["source_audit_reuse"] = {
            "mode": "reused",
            "reused_at": "2026-07-24",
            "origin": "external_ref:NOT_PRESENT",
        }
        dangling_fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="A dangling in-submission source-audit reuse is rejected.",
            proof=proof,
            external_refs=[dangling],
        )
        with self.assertRaisesRegex(ValueError, "nonpreceding external_ref"):
            self.store.submit(dangling_fact, worker="worker")

    def test_formula_and_transport_risks_cannot_use_baseline_profile(self) -> None:
        formula = certified_formula_ref()
        formula_audit = formula["critical_audit"]
        self.assertIsInstance(formula_audit, dict)
        formula_audit["profile"] = "baseline"
        formula_audit["risk_triggers"] = []
        checks = formula_audit["sanity_checks"]
        self.assertIsInstance(checks, list)
        formula_audit["sanity_checks"] = checks[:3]
        formula_fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The formula has an outer differential.",
            proof=(
                "Check H [APP:FORMULA:H1]. Match conventions [APP:FORMULA:C1]. "
                "Use the formula [APP:FORMULA:USE]. Inspect exact glyphs "
                "[SRC:FORMULA:GLYPH]. Audit the source [CRIT:FORMULA:USE]."
            ),
            external_refs=[formula],
        )
        with self.assertRaisesRegex(ValueError, "formula use requires the strict profile"):
            self.store.submit(formula_fact, worker="worker")

        transported = certified_result_ref()
        applicability = transported["applicability"]
        self.assertIsInstance(applicability, dict)
        applicability["transport_obligations"] = [
            {
                "operation": "Pass to a limiting family.",
                "justification": "A separate argument is claimed.",
                "proof_anchor": "[APP:SRC:T1]",
            }
        ]
        transported_fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The transported conclusion holds.",
            proof=(
                "Check H [APP:SRC:H1]. Match conventions [APP:SRC:C1]. "
                "Justify the limit [APP:SRC:T1]. Use P [APP:SRC:USE]. "
                "Audit the source [CRIT:SRC:USE]."
            ),
            external_refs=[transported],
        )
        with self.assertRaisesRegex(
            ValueError,
            "bridged or transported source use requires the strict profile",
        ):
            self.store.submit(transported_fact, worker="worker")

    def test_formula_trace_and_glyph_hashes_must_agree(self) -> None:
        ref = certified_formula_ref()
        trace = ref["source_trace"]
        self.assertIsInstance(trace, dict)
        trace["artifact_sha256"] = sha256_bytes(b"different primary artifact")
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The formula has an outer differential.",
            proof=(
                "Check H [APP:FORMULA:H1]. Match conventions [APP:FORMULA:C1]. "
                "Use the formula [APP:FORMULA:USE]. Inspect exact glyphs "
                "[SRC:FORMULA:GLYPH]. Audit the source [CRIT:FORMULA:USE]."
            ),
            external_refs=[ref],
        )
        with self.assertRaisesRegex(ValueError, "must equal source_fidelity"):
            self.store.submit(fact, worker="worker")

    def test_unambiguous_minor_source_typo_is_explicit_and_bound(self) -> None:
        ref = certified_result_ref()
        promote_ref_to_strict(ref, "suspected_source_defect")
        audit = ref["critical_audit"]
        self.assertIsInstance(audit, dict)
        checks = audit["sanity_checks"]
        self.assertIsInstance(checks, list)
        notation_check = next(
            item
            for item in checks
            if isinstance(item, dict) and item.get("kind") == "notation_and_binding"
        )
        notation_check["status"] = "issue"
        notation_check["finding"] = (
            "The statement writes Y_0 once, while the definitions and proof use X_0."
        )
        audit["assessment"] = "minor_typo_corrected"
        audit["issues"] = [
            {
                "kind": "typo",
                "source_text": "Y_0 satisfies H.",
                "corrected_text": "X_0 satisfies H.",
                "evidence": (
                    "The immediately preceding definition and every proof occurrence use X_0."
                ),
                "impact": "non_semantic",
                "proof_anchor": "[CRIT:SRC:I1]",
            }
        ]
        audit["justification"] = (
            "The correction is uniquely forced by the local definition and does not change scope."
        )
        proof = (
            "Check H [APP:SRC:H1]. Match conventions [APP:SRC:C1]. "
            "Use P [APP:SRC:USE]. The fixed source checks are recorded [CRIT:SRC:USE]. "
            "Read the isolated Y_0 as X_0, forced by the definition and proof "
            "[CRIT:SRC:I1]."
        )
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The test object has property P.",
            proof=proof,
            external_refs=[ref],
        )
        self.store.submit(fact, worker="worker")
        packet = self.store.verification_packet(fact.fact_id)
        self.assertIn("minor_typo_corrected", packet)
        self.assertIn("Y_0 satisfies H.", packet)
        self.assertIn("[CRIT:SRC:I1]", packet)

    def test_exact_official_erratum_can_be_applied(self) -> None:
        ref = certified_result_ref()
        promote_ref_to_strict(ref, "official_correction")
        audit = ref["critical_audit"]
        self.assertIsInstance(audit, dict)
        checks = audit["sanity_checks"]
        self.assertIsInstance(checks, list)
        checks[-1]["status"] = "issue"
        checks[-1]["finding"] = (
            "The original proof concludes the corrected, narrower parameter range."
        )
        audit["assessment"] = "official_erratum_applied"
        audit["issues"] = [
            {
                "kind": "official_erratum",
                "source_text": "The parameter lies in the closed interval.",
                "corrected_text": "The parameter lies in the open interval.",
                "evidence": "The official erratum replaces the endpoint condition.",
                "impact": "material",
                "proof_anchor": "[CRIT:SRC:I1]",
                "correction_locator": "https://example.org/primary-source/erratum-v1.pdf",
                "correction_sha256": sha256_bytes(b"official erratum artifact"),
            }
        ]
        audit["justification"] = "The exact official erratum controls this source version."
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The test object has property P on the open interval.",
            proof=(
                "Check H [APP:SRC:H1]. Match conventions [APP:SRC:C1]. "
                "Use the corrected range [APP:SRC:USE]. Audit the source "
                "[CRIT:SRC:USE] and exact official erratum [CRIT:SRC:I1]."
            ),
            external_refs=[ref],
        )
        self.store.submit(fact, worker="worker")
        self.assertIn(
            "official_erratum_applied",
            self.store.verification_packet(fact.fact_id),
        )

    def test_applicability_only_certificate_remains_historical_readable(self) -> None:
        ref = certified_result_ref()
        ref.pop("source_evidence_version")
        ref.pop("source_trace")
        ref.pop("critical_audit")
        proof = (
            "Check H [APP:SRC:H1]. Match conventions [APP:SRC:C1]. "
            "Use P [APP:SRC:USE]."
        )
        validate_external_refs_for_submission([ref], proof)
        with self.assertRaisesRegex(ValueError, "source_evidence_version must be 3"):
            validate_external_refs_for_submission(
                [ref],
                proof,
                require_critical_audit=True,
            )

    def test_source_evidence_v2_remains_historical_readable(self) -> None:
        ref = certified_result_ref()
        ref["source_evidence_version"] = 2
        audit = ref["critical_audit"]
        self.assertIsInstance(audit, dict)
        source_audit = audit["source_audit"]
        self.assertIsInstance(source_audit, dict)
        checks = audit["sanity_checks"]
        self.assertIsInstance(checks, list)
        legacy_checks = [
            *checks,
            {
                "kind": "boundary_or_toy_case",
                "status": "pass",
                "finding": "The base test object is consistent.",
            },
            {
                "kind": "statement_proof_consistency",
                "status": "pass",
                "finding": "The proof concludes the literal statement.",
            },
        ]
        legacy_searches = [
            {**item, "checked_at": source_audit["checked_at"]}
            for item in source_audit["issue_searches"]
        ]
        ref["critical_audit"] = {
            "sanity_checks": legacy_checks,
            "issue_searches": legacy_searches,
            "assessment": audit["assessment"],
            "issues": audit["issues"],
            "justification": audit["justification"],
            "proof_anchor": audit["proof_anchor"],
        }
        proof = (
            "Check H [APP:SRC:H1]. Match conventions [APP:SRC:C1]. "
            "Use P [APP:SRC:USE]. Audit the source [CRIT:SRC:USE]."
        )
        validate_external_refs_for_submission([ref], proof)
        with self.assertRaisesRegex(ValueError, "source_evidence_version must be 3"):
            validate_external_refs_for_submission(
                [ref],
                proof,
                require_critical_audit=True,
            )

    def test_material_or_unresolved_source_defect_cannot_enter_submission(self) -> None:
        ref = certified_result_ref()
        audit = ref["critical_audit"]
        self.assertIsInstance(audit, dict)
        audit["assessment"] = "materially_uncertain"
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The test object has property P.",
            proof=(
                "Check H [APP:SRC:H1]. Match conventions [APP:SRC:C1]. "
                "Use P [APP:SRC:USE]. Audit the source [CRIT:SRC:USE]."
            ),
            external_refs=[ref],
        )
        with self.assertRaisesRegex(ValueError, "not admissible.*exploration memory"):
            self.store.submit(fact, worker="worker")

        typo_ref = certified_result_ref()
        promote_ref_to_strict(typo_ref, "suspected_source_defect")
        typo_audit = typo_ref["critical_audit"]
        self.assertIsInstance(typo_audit, dict)
        typo_checks = typo_audit["sanity_checks"]
        self.assertIsInstance(typo_checks, list)
        typo_checks[0]["status"] = "issue"
        typo_audit["assessment"] = "minor_typo_corrected"
        typo_audit["issues"] = [
            {
                "kind": "typo",
                "source_text": "P",
                "corrected_text": "Q",
                "evidence": "The proof appears to establish Q.",
                "impact": "material",
                "proof_anchor": "[CRIT:SRC:I1]",
            }
        ]
        material_fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The test object has property Q.",
            proof=(
                "Check H [APP:SRC:H1]. Match conventions [APP:SRC:C1]. "
                "Use Q [APP:SRC:USE]. Audit the source [CRIT:SRC:USE] "
                "and proposed correction [CRIT:SRC:I1]."
            ),
            external_refs=[typo_ref],
        )
        with self.assertRaisesRegex(ValueError, "only non_semantic typo"):
            self.store.submit(material_fact, worker="worker")

    def test_certified_external_result_is_bound_into_proof_and_packet(self) -> None:
        proof = (
            "The target satisfies H by direct calculation [APP:SRC:H1]. "
            "The source and target conventions agree [APP:SRC:C1]. "
            "The cited theorem therefore gives exactly P [APP:SRC:USE]. "
            "The source statement and reliability checks agree [CRIT:SRC:USE]."
        )
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The test object has property P.",
            proof=proof,
            external_refs=[certified_result_ref()],
        )
        self.store.submit(fact, worker="worker")
        task = create_verifier_assignment(self.store, fact.fact_id)
        packet = Path(task["packet_path"]).read_text(encoding="utf-8")
        self.assertIn("external-source applicability and critical-audit evidence", packet)
        self.assertIn("source_conclusion", packet)
        self.assertIn("source_trace", packet)
        self.assertIn("critical_audit", packet)
        self.assertIn("the baseline notation/binding", packet)
        self.assertIn("source_audit.audit_sha256", packet)
        self.assertIn("baseline-only group", packet)
        self.assertIn("version-history, erratum, and retraction/counterexample", packet)
        self.assertIn("uniquely forced, non-semantic", packet)
        self.assertIn("independently open only its exact", packet)
        self.assertIn("Words such as standard, classical, or well", packet)
        self.assertIn("elementary-result ledger", packet)
        self.assertIn("predecessor's statement as its complete reusable interface", packet)
        self.assertIn("check every scope restriction and hypothesis stated by that", packet)
        self.assertIn("Shared terminology is not a transport proof", packet)
        self.assertIn("exact primary-source locators", task["spawn_contract"]["task"])
        self.assertIn("predecessor statement as the complete reusable theorem interface", task["spawn_contract"]["task"])
        self.assertIn("map every scope restriction and hypothesis stated by each predecessor", task["spawn_contract"]["task"])
        self.assertIn("Track quantifier polarity", task["spawn_contract"]["task"])
        self.assertIn("Such a witness is not canonical", task["spawn_contract"]["task"])
        self.assertIn("irreducibility to nonseparating topology", task["spawn_contract"]["task"])
        self.assertIn("Verify each source_trace transcription and hash", task["spawn_contract"]["task"])
        self.assertIn("Group source status evidence", task["spawn_contract"]["task"])
        self.assertIn("baseline-only group", task["spawn_contract"]["task"])
        self.assertIn("Reject any ambiguous, material", task["spawn_contract"]["task"])

    def test_formula_source_requires_source_fidelity_and_glyph_anchor(self) -> None:
        ref = certified_formula_ref()
        ref.pop("source_fidelity")
        proof = (
            "Check H [APP:FORMULA:H1]. Match conventions [APP:FORMULA:C1]. "
            "Use the formula [APP:FORMULA:USE]. "
            "Audit the source statement [CRIT:FORMULA:USE]."
        )
        missing = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The formula has an outer differential.",
            proof=proof,
            external_refs=[ref],
        )
        with self.assertRaisesRegex(ValueError, "source_fidelity is required"):
            self.store.submit(missing, worker="worker")

        complete_ref = certified_formula_ref()
        complete = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The formula has an outer differential.",
            proof=proof + " Inspect the exact glyphs [SRC:FORMULA:GLYPH].",
            external_refs=[complete_ref],
        )
        with self.assertRaisesRegex(ValueError, "bound schema-v3 round"):
            self.store.submit(complete, worker="worker")

    def test_controlled_elementary_use_is_structured_bound_and_packet_visible(self) -> None:
        proof = (
            "For F(z)=z the Jacobian determinant at 0 is 1. Apply the local holomorphic "
            "inverse-function theorem [ELM:IFT1]."
        )
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The identity map has a local holomorphic inverse germ at zero.",
            proof=proof,
            elementary_uses=[elementary_use()],
        )
        self.store.submit(fact, worker="worker")
        submission = self.store.submission(fact.fact_id)
        self.assertEqual(submission["elementary_uses"], [elementary_use()])
        packet = self.store.verification_packet(fact.fact_id)
        self.assertIn("controlled elementary-result ledger", packet)
        self.assertIn("[ELM:IFT1]", packet)
        self.assertIn("mathematical eligibility decision", packet)
        tampered = self.store._read_json(self.store.submission_path(fact.fact_id))
        tampered["elementary_uses"][0]["used_conclusion"] = "A global inverse exists."
        self.store._write_json_atomic(
            self.store.submission_path(fact.fact_id),
            tampered,
        )
        report = self.store.audit()
        self.assertFalse(report.ok)
        self.assertTrue(
            any("submission hash mismatch" in error for error in report.workflow_errors)
        )

    def test_elementary_use_rejects_open_categories_and_unbound_anchors(self) -> None:
        proof = "Invoke a purported elementary step [ELM:WPT]."
        invalid_category = elementary_use("WPT", "weierstrass_preparation")
        with self.assertRaisesRegex(ValueError, "category must be one of"):
            validate_elementary_uses_for_submission([invalid_category], proof)

        missing_anchor = elementary_use()
        with self.assertRaisesRegex(ValueError, "ELM:IFT1.*found 0"):
            validate_elementary_uses_for_submission(
                [missing_anchor],
                "The anchor is absent.",
            )

    def test_certificate_missing_or_duplicate_proof_anchor_is_rejected(self) -> None:
        missing = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The test object has property P.",
            proof=(
                "The target satisfies H [APP:SRC:H1] and conventions agree "
                "[APP:SRC:C1]."
            ),
            external_refs=[certified_result_ref()],
        )
        with self.assertRaisesRegex(ValueError, "APP:SRC:USE.*found 0"):
            self.store.submit(missing, worker="worker")

        duplicate = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The test object has property P twice.",
            proof=(
                "Check H [APP:SRC:H1]. Use the result [APP:SRC:USE], "
                "with matching conventions [APP:SRC:C1], repeated [APP:SRC:USE]."
            ),
            external_refs=[certified_result_ref()],
        )
        with self.assertRaisesRegex(ValueError, "APP:SRC:USE.*found 2"):
            self.store.submit(duplicate, worker="worker")

    def test_bridged_external_use_requires_a_hashed_bridge(self) -> None:
        ref = certified_result_ref()
        applicability = ref["applicability"]
        self.assertIsInstance(applicability, dict)
        applicability["strength_comparison"] = "bridged"
        applicability["verdict"] = "bridged"
        fact = Fact(
            problem_id=self.store.project_id(),
            author="worker",
            predecessors=[],
            statement="The transported object has property P.",
            proof=(
                "Check H [APP:SRC:H1]. Match conventions [APP:SRC:C1]. "
                "Use P [APP:SRC:USE]."
            ),
            external_refs=[ref],
        )
        with self.assertRaisesRegex(ValueError, "bridge_statement must be a string"):
            self.store.submit(fact, worker="worker")

    def test_review_timestamp_and_acceptance_evidence_tamper_fail_audit(self) -> None:
        fact = self.candidate()
        self.store.submit(fact, worker="worker")
        rejected_id = review_fact(
            self.store,
            fact.fact_id,
            verdict="reject",
            reviewer="reject-verifier",
            gaps=["missing step"],
        )
        accepted_id = review_fact(
            self.store, fact.fact_id, reviewer="accept-verifier"
        )
        self.store.admit(fact.fact_id, review_id=accepted_id)

        review_path = self.store.review_path(accepted_id)
        review = self.store._read_json(review_path)
        review["reviewed_at"] = "tampered"
        self.store._write_json_atomic(review_path, review)
        first_report = self.store.audit()
        self.assertFalse(first_report.ok)
        self.assertTrue(
            any("record hash mismatch" in error for error in first_report.workflow_errors)
        )

        # Restore the immutable record, then make the acceptance point to a real
        # but rejecting review.  Audit must not mistake hash consistency for truth.
        review["record_sha256"] = sha256_json(
            {
                key: value
                for key, value in review.items()
                if key not in {"review_id", "record_sha256"}
            }
        )
        self.store._write_json_atomic(review_path, review)
        submission = self.store.submission(fact.fact_id)
        submission["accepted_review_id"] = rejected_id
        self.store._write_json_atomic(self.store.submission_path(fact.fact_id), submission)
        events = self.store._read_jsonl(self.store.verification_log)
        event = events[0]
        rejected = self.store.review(rejected_id)
        event["review_id"] = rejected_id
        event["reviewer"] = rejected["reviewer"]
        event["event_id"] = sha256_json(["accepted", fact.fact_id, rejected_id])
        self.store.verification_log.write_text(
            json.dumps(event, sort_keys=True) + "\n", encoding="utf-8"
        )
        second_report = self.store.audit()
        self.assertFalse(second_report.ok)
        self.assertTrue(
            any("non-clean review" in error for error in second_report.workflow_errors)
        )

    def test_reject_cannot_enter_truth(self) -> None:
        fact = self.candidate(statement="False claim.", proof="Unsupported.")
        self.store.submit(fact, worker="worker")
        review_id = review_fact(
            self.store,
            fact.fact_id,
            verdict="reject",
            reviewer="independent",
            critical_errors=["Unsupported implication."],
            repair_hints=["Prove the implication."],
        )
        with self.assertRaisesRegex(ValueError, "not pending"):
            self.store.admit(fact.fact_id, review_id=review_id)
        self.assertEqual(self.store.submission(fact.fact_id)["status"], "rejected")

    def test_later_rejection_blocks_an_older_correct_review(self) -> None:
        fact = self.candidate(statement="Debatable.", proof="Attempt.")
        self.store.submit(fact, worker="worker")
        older_correct = review_fact(
            self.store, fact.fact_id, reviewer="first-verifier"
        )
        review_fact(
            self.store,
            fact.fact_id,
            verdict="reject",
            reviewer="second-verifier",
            critical_errors=["fatal flaw"],
        )
        with self.assertRaisesRegex(ValueError, "not pending"):
            self.store.admit(fact.fact_id, review_id=older_correct)
        self.assertFalse(self.store.fact_path(fact.fact_id).exists())
        self.assertTrue(self.store.audit().ok)

    def test_project_isolation_for_submit_and_import(self) -> None:
        foreign = self.candidate(problem_id="other-problem")
        with self.assertRaisesRegex(ValueError, "does not match project"):
            self.store.submit(foreign, worker="worker")
        archive = Path(self.temporary.name) / "foreign.zip"
        with ZipFile(archive, "w") as zipped:
            zipped.writestr(
                f"foreign/fact_graph/facts/{foreign.fact_id}.md",
                serialize_fact(foreign),
            )
        with self.assertRaisesRegex(ValueError, "belongs to project"):
            self.store.import_danus_zip(archive)
        self.assertEqual(self.store.fact_ids(), [])

    def test_complex_round_trip_fact_can_be_admitted_and_audited(self) -> None:
        fact_id = accepted_fact(
            self.store,
            statement="S.\n\n## Scope\nAn internal heading.",
            proof="P.\n\n## Lemma\nStill proof text.",
            glossary={"x:y": "a:b"},
            intuition="I.\n\n## Picture\nStill intuition.",
        )
        self.assertEqual(self.store.get_fact(fact_id).fact_id, fact_id)
        self.assertTrue(self.store.audit().ok)
        reserved = self.candidate(
            statement="Safe statement.",
            proof="First part.\n\n## proof\nInjected duplicate reserved section.",
        )
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.store.submit(reserved, worker="worker")

    def test_cascade_revocation_removes_target_and_reopens_memory(self) -> None:
        root = accepted_fact(self.store, statement="A.", proof="Axiom.")
        child = accepted_fact(
            self.store,
            statement="B.",
            proof=f"Use {root}.",
            predecessors=[root],
        )
        memory_id = self.store.memory_add(
            {
                "kind": "conjecture",
                "claim": "Resolved by B.",
                "status": "resolved_by_fact",
                "resolution_fact_id": child,
            },
            actor="main",
        )
        self.store.set_targets([child])
        revoked = self.store.revoke(root, reason="bad axiom", actor="operator")
        self.assertEqual(set(revoked), {root, child})
        self.assertEqual(self.store.targets(), [])
        self.assertEqual(self.store.fact_ids(), [])
        self.assertEqual(self.store.memory_latest()[memory_id]["status"], "challenged")
        self.assertTrue(self.store.audit().ok, self.store.audit().errors)
        with self.assertRaisesRegex(ValueError, "was revoked"):
            self.store.admit(
                root,
                review_id=self.store.submission(root)["accepted_review_id"],
            )

    def test_memory_vocabulary_ids_and_fact_resolution_are_enforced(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported memory status"):
            self.store.memory_add(
                {"kind": "conjecture", "claim": "C", "status": "verified"},
                actor="main",
            )
        with self.assertRaisesRegex(ValueError, "generated internally"):
            self.store.memory_add(
                {"id": "a" * 12, "kind": "conjecture", "claim": "C"},
                actor="main",
            )
        memory_id = self.store.memory_add(
            {"kind": "conjecture", "claim": "C"}, actor="main"
        )
        with self.assertRaisesRegex(ValueError, "requires resolution_fact_id"):
            self.store.memory_update(
                memory_id, status="resolved_by_fact", actor="main"
            )

    def test_novelty_ledger_is_query_level_and_audited(self) -> None:
        memory_id = self.store.memory_add(
            {"kind": "conjecture", "claim": "A candidate rigidity statement."},
            actor="main",
        )
        event_id = self.store.novelty_record(
            {
                "subject_kind": "memory",
                "subject_id": memory_id,
                "corpus": "arXiv",
                "query": "\"rigidity\" \"topological recursion\"",
                "status": "no_exact_match_found",
                "hits": [
                    {
                        "title": "Related background",
                        "locator": "https://arxiv.org/abs/0000.00000v1",
                        "relation": "background",
                    }
                ],
                "notes": "No exact proposition in the inspected hits.",
            },
            actor="literature-worker",
        )
        records = self.store.novelty_status(memory_id)
        self.assertEqual(records[0]["event_id"], event_id)
        report = self.store.audit()
        self.assertTrue(report.ok, report.errors)
        self.assertEqual(report.novelty_entries, 1)
        with self.assertRaisesRegex(ValueError, "conflicts with an exact hit"):
            self.store.novelty_record(
                {
                    "subject_kind": "memory",
                    "subject_id": memory_id,
                    "corpus": "arXiv",
                    "query": "exact duplicate",
                    "status": "no_exact_match_found",
                    "hits": [
                        {
                            "title": "Exact theorem",
                            "locator": "https://example.org/exact",
                            "relation": "exact",
                        }
                    ],
                },
                actor="literature-worker",
            )

    def test_admission_retry_is_idempotent_and_audit_detects_state_tamper(self) -> None:
        fact = self.candidate()
        self.store.submit(fact, worker="worker")
        review_id = review_fact(self.store, fact.fact_id, reviewer="independent")
        self.store.admit(fact.fact_id, review_id=review_id)
        self.store.admit(fact.fact_id, review_id=review_id)
        events = [
            event
            for event in self.store._read_jsonl(self.store.verification_log)
            if event.get("fact_id") == fact.fact_id
        ]
        self.assertEqual(len(events), 1)
        submission = self.store.submission(fact.fact_id)
        submission["status"] = "pending_review"
        self.store._write_json_atomic(self.store.submission_path(fact.fact_id), submission)
        report = self.store.audit()
        self.assertFalse(report.ok)
        self.assertTrue(any("submission" in error for error in report.workflow_errors))

    def test_invalid_import_is_rejected_before_writing_facts(self) -> None:
        missing = "a" * 16
        fact = self.candidate(
            predecessors=[missing],
            statement="A claim with an absent premise.",
            proof=f"Use missing fact {missing}.",
        )
        archive = Path(self.temporary.name) / "invalid.zip"
        with ZipFile(archive, "w") as zipped:
            zipped.writestr(
                f"invalid/fact_graph/facts/{fact.fact_id}.md", serialize_fact(fact)
            )
            zipped.writestr("invalid/TARGET.md", fact.fact_id + "\n")
        with self.assertRaisesRegex(ValueError, "missing predecessors"):
            self.store.import_danus_zip(archive)
        self.assertEqual(self.store.fact_ids(), [])


class RoundWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = MathGraphStore._for_legacy_workflow_fixture(
            Path(self.temporary.name) / "project"
        )
        self.store.initialize(project_id="round-project", title="Round graph")
        self.root_fact = accepted_fact(self.store, statement="A.", proof="Axiom.")
        self.memory_id = self.store.memory_add(
            {
                "kind": "conjecture",
                "claim": "A implies a useful refinement.",
                "rationale": "Test the agent bridge.",
                "source": "/fixtures/local-primary.tex, Proposition 1",
                "dependencies": [self.root_fact],
                "priority": 0.9,
                "novelty": 0.7,
                "testability": 0.8,
                "risk": 0.2,
                "suggested_actions": ["prove directly"],
            },
            actor="main",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_round(self) -> tuple[dict[str, object], dict[str, str], Path]:
        manifest = create_round(
            self.store, workers=1, memory_ids=[self.memory_id]
        )
        self.assertTrue(Path(manifest["mgraph_path"]).name == "mgraph")
        assignment = manifest["assignments"][0]
        return_path = Path(assignment["return_path"])
        return manifest, assignment, return_path

    def test_explicit_low_score_memory_id_is_not_lost_to_frontier_truncation(self) -> None:
        for index in range(12):
            self.store.memory_add(
                {
                    "kind": "direction",
                    "claim": f"High-score automatic candidate {index}.",
                    "dependencies": [self.root_fact],
                    "priority": 1.0,
                    "novelty": 1.0,
                    "testability": 1.0,
                    "risk": 0.0,
                },
                actor="main",
            )
        selected = self.store.memory_add(
            {
                "kind": "direction",
                "claim": "Explicit low-score candidate must remain selectable.",
                "dependencies": [self.root_fact],
                "priority": 0.0,
                "novelty": 0.0,
                "testability": 0.0,
                "risk": 1.0,
            },
            actor="main",
        )
        manifest = create_round(self.store, workers=1, memory_ids=[selected])
        self.assertEqual(manifest["assignments"][0]["memory_id"], selected)

    def test_assignment_bound_fact_return_and_exactly_once_receipt(self) -> None:
        manifest, assignment, return_path = self.make_round()
        self.assertEqual(round_status(self.store, manifest["round_id"])["ready"], 1)
        prompt = Path(assignment["prompt_path"]).read_text(encoding="utf-8")
        self.assertIn("map all scope restrictions and", prompt)
        self.assertIn("Shared terminology is not a bridge", prompt)
        self.assertIn("explicit final handoff", prompt)
        self.assertIn("tiered external-source evidence v3", prompt)
        self.assertIn("hash that `source_audit`", prompt)
        self.assertIn('profile="strict"', prompt)
        self.assertIn("version-history, erratum", prompt)
        self.assertIn("[CRIT:...]", prompt)
        self.assertIn("/fixtures/local-primary.tex, Proposition 1", prompt)
        self.assertEqual(
            assignment["contract"]["source"],
            "/fixtures/local-primary.tex, Proposition 1",
        )
        payload = bound_return(
            manifest,
            assignment,
            outcome="fact_submission",
            statement="A has the useful refinement.",
            proof=f"By the construction in verified fact {self.root_fact}.",
            predecessors=[self.root_fact],
        )
        return_path.write_text(json.dumps(payload), encoding="utf-8")
        validated = validate_return(
            self.store,
            manifest["round_id"],
            assignment["assignment_id"],
        )
        self.assertEqual(validated["return_sha256"], sha256_bytes(return_path.read_bytes()))
        self.assertEqual(
            round_status(self.store, manifest["round_id"])["draft_present"], 1
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            ingest_return(
                self.store,
                manifest["round_id"],
                assignment["assignment_id"],
                worker_final_sha256="0" * 64,
            )
        self.assertFalse(return_path.with_suffix(".receipt.json").exists())
        receipt = ingest_return(
            self.store,
            manifest["round_id"],
            assignment["assignment_id"],
        )
        memory_events = self.store.memory_log.read_text(encoding="utf-8")
        replay = ingest_return(
            self.store,
            manifest["round_id"],
            assignment["assignment_id"],
        )
        self.assertEqual(replay, receipt)
        self.assertEqual(self.store.memory_log.read_text(encoding="utf-8"), memory_events)
        self.assertEqual(receipt["status"], "ingested")
        self.assertEqual(
            receipt["worker_final_sha256"], sha256_bytes(return_path.read_bytes())
        )
        self.assertTrue(receipt["return_locked"])
        self.assertEqual(return_path.stat().st_mode & 0o222, 0)
        self.assertEqual(
            self.store.submission(receipt["submission_id"])["assignment_id"],
            assignment["assignment_id"],
        )
        self.assertEqual(round_status(self.store, manifest["round_id"])["status"], "complete")
        self.assertTrue(self.store.audit().ok, self.store.audit().errors)
        payload["proof"] = "Edited after ingestion."
        with self.assertRaises(PermissionError):
            return_path.write_text(json.dumps(payload), encoding="utf-8")
        return_path.chmod(0o600)
        return_path.write_text(json.dumps(payload), encoding="utf-8")
        tampered_sha = sha256_bytes(return_path.read_bytes())
        tampered_report = self.store.audit()
        self.assertFalse(tampered_report.ok)
        self.assertTrue(tampered_report.workflow_errors)
        with self.assertRaisesRegex(ValueError, "changed after ingestion"):
            ingest_return(
                self.store,
                manifest["round_id"],
                assignment["assignment_id"],
                worker_final_sha256=tampered_sha,
            )

    def test_wrong_binding_has_no_effect(self) -> None:
        manifest, assignment, return_path = self.make_round()
        before = self.store.memory_log.read_bytes()
        payload = bound_return(
            manifest,
            assignment,
            outcome="dead_end",
            claim="No proof found.",
            method="Direct attack.",
            failure_mode="Missing estimate.",
            what_remains_open="Find the estimate.",
        )
        payload["memory_id"] = "f" * 12
        return_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "memory_id mismatch"):
            ingest_return(
                self.store,
                manifest["round_id"],
                assignment["assignment_id"],
                worker_final_sha256=sha256_bytes(return_path.read_bytes()),
            )
        self.assertEqual(self.store.memory_log.read_bytes(), before)
        self.assertFalse(return_path.with_suffix(".receipt.json").exists())

    def test_worker_bare_external_citation_is_rejected_before_ingestion(self) -> None:
        manifest, assignment, return_path = self.make_round()
        payload = bound_return(
            manifest,
            assignment,
            outcome="fact_submission",
            statement="A cited refinement.",
            proof="The source allegedly proves the refinement.",
            predecessors=[self.root_fact],
            external_refs=[
                {
                    "key": "SRC",
                    "title": "Primary source",
                    "url": "https://example.org/primary-source",
                    "use_kind": "result",
                    "cited_for": "The refinement.",
                }
            ],
        )
        return_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "applicability must be an object"):
            ingest_return(
                self.store,
                manifest["round_id"],
                assignment["assignment_id"],
                worker_final_sha256=sha256_bytes(return_path.read_bytes()),
            )
        self.assertFalse(return_path.with_suffix(".receipt.json").exists())
        self.assertEqual(len(list(self.store.submissions_dir.glob("*.json"))), 1)

    def test_schema_v2_return_remains_readable_without_current_certificate_fields(self) -> None:
        manifest, assignment, _ = self.make_round()
        legacy_manifest = dict(manifest)
        legacy_manifest["schema_version"] = 2
        payload = bound_return(
            legacy_manifest,
            assignment,
            outcome="fact_submission",
            statement="A historical cited refinement.",
            proof="The historical return used its then-current citation metadata.",
            predecessors=[self.root_fact],
            external_refs=[
                {
                    "title": "Historical primary source",
                    "doi": "10.1000/historical",
                }
            ],
        )
        payload.pop("claim_relation")
        outcome, artifacts = validate_worker_return(
            payload,
            assignment,
            legacy_manifest,
        )
        self.assertEqual(outcome, "fact_submission")
        self.assertEqual(artifacts, [])

    def test_formula_source_hash_must_bind_to_declared_round_artifact(self) -> None:
        manifest, assignment, return_path = self.make_round()
        proof = (
            "Check H [APP:FORMULA:H1]. Match conventions [APP:FORMULA:C1]. "
            "Use the formula [APP:FORMULA:USE]. Inspect exact glyphs "
            "[SRC:FORMULA:GLYPH]. Audit source reliability [CRIT:FORMULA:USE]."
        )
        payload = bound_return(
            manifest,
            assignment,
            outcome="fact_submission",
            statement="The cited formula has an outer differential.",
            proof=proof,
            predecessors=[self.root_fact],
            external_refs=[certified_formula_ref()],
            artifacts=[],
        )
        return_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not bound to a declared assignment artifact"):
            validate_return(
                self.store,
                manifest["round_id"],
                assignment["assignment_id"],
            )

        artifact_path = Path(assignment["artifact_dir_path"]) / "primary-formula.bin"
        artifact_path.write_bytes(b"exact primary formula artifact")
        payload["artifacts"] = [
            {
                "path": artifact_path.relative_to(self.store.root).as_posix(),
                "sha256": sha256_bytes(artifact_path.read_bytes()),
            }
        ]
        return_path.write_text(json.dumps(payload), encoding="utf-8")
        validated = validate_return(
            self.store,
            manifest["round_id"],
            assignment["assignment_id"],
        )
        self.assertEqual(validated["artifacts"], payload["artifacts"])
        receipt = ingest_return(
            self.store,
            manifest["round_id"],
            assignment["assignment_id"],
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        packet = self.store.verification_packet(receipt["submission_id"])
        self.assertIn("source_fidelity", packet)
        self.assertIn("critical_audit", packet)
        self.assertIn("[SRC:FORMULA:GLYPH]", packet)
        self.assertIn("[CRIT:FORMULA:USE]", packet)

    def test_counterexample_is_challenged_not_truth(self) -> None:
        manifest, assignment, return_path = self.make_round()
        payload = bound_return(
            manifest,
            assignment,
            outcome="counterexample",
            claim="The proposed refinement fails.",
            construction="Use parameter zero.",
            verification="Direct substitution contradicts the conclusion.",
        )
        return_path.write_text(json.dumps(payload), encoding="utf-8")
        receipt = ingest_return(
            self.store,
            manifest["round_id"],
            assignment["assignment_id"],
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        child = self.store.memory_latest()[receipt["memory_entry_id"]]
        self.assertEqual(child["kind"], "counterexample")
        self.assertEqual(child["status"], "challenged")
        self.assertNotEqual(child["status"], "verified")

    def test_counterexample_can_generate_two_branch_repair_round(self) -> None:
        manifest, assignment, return_path = self.make_round()
        payload = bound_return(
            manifest,
            assignment,
            outcome="counterexample",
            claim="The proposed refinement fails at parameter zero.",
            construction="Set the parameter to zero.",
            verification="The claimed nonzero term becomes zero.",
        )
        return_path.write_text(json.dumps(payload), encoding="utf-8")
        receipt = ingest_return(
            self.store,
            manifest["round_id"],
            assignment["assignment_id"],
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        repaired = create_repair_round(
            self.store,
            self.memory_id,
            trigger_memory_id=receipt["memory_entry_id"],
        )
        self.assertEqual(len(repaired["repair_memory_ids"]), 2)
        modes = [
            item["mode"] for item in repaired["round"]["assignments"]
        ]
        self.assertEqual(modes, ["prove", "refute"])
        latest = self.store.memory_latest()
        for repair_id in repaired["repair_memory_ids"]:
            self.assertEqual(latest[repair_id]["repair_of_memory_id"], self.memory_id)
            self.assertEqual(
                latest[repair_id]["trigger_memory_id"],
                receipt["memory_entry_id"],
            )
        self.assertTrue(self.store.audit().ok, self.store.audit().errors)

    def test_claim_relation_is_hash_bound_and_controls_memory_resolution(self) -> None:
        manifest, assignment, return_path = self.make_round()
        payload = bound_return(
            manifest,
            assignment,
            outcome="fact_submission",
            claim_relation="replaces",
            statement="A corrected useful refinement holds under an added hypothesis.",
            proof=f"Use verified fact {self.root_fact} and the added hypothesis.",
            predecessors=[self.root_fact],
        )
        return_path.write_text(json.dumps(payload), encoding="utf-8")
        receipt = ingest_return(
            self.store,
            manifest["round_id"],
            assignment["assignment_id"],
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        submission = self.store.submission(receipt["submission_id"])
        self.assertEqual(submission["claim_relation"], "replaces")
        packet = self.store.verification_packet(receipt["submission_id"])
        self.assertIn("Claim relation: `replaces`", packet)
        self.assertIn("A implies a useful refinement.", packet)
        review_id = review_fact(self.store, receipt["submission_id"])
        self.store.admit(receipt["submission_id"], review_id=review_id)
        resolved = self.store.memory_latest()[self.memory_id]
        self.assertEqual(resolved["status"], "replaced_by_fact")
        self.assertEqual(resolved["claim_relation"], "replaces")
        self.assertEqual(resolved["related_fact_id"], receipt["submission_id"])
        self.assertTrue(self.store.audit().ok, self.store.audit().errors)
        events = [
            json.loads(line)
            for line in self.store.memory_log.read_text(encoding="utf-8").splitlines()
        ]
        events[-1]["claim_relation"] = "proves"
        self.store.memory_log.write_text(
            "\n".join(json.dumps(event, sort_keys=True) for event in events) + "\n",
            encoding="utf-8",
        )
        tampered = self.store.audit()
        self.assertFalse(tampered.ok)
        self.assertTrue(
            any(
                "status/relation/fact semantics disagree" in error
                for error in tampered.workflow_errors
            )
        )

    def test_revocation_clears_nonresolving_claim_relation(self) -> None:
        manifest, assignment, return_path = self.make_round()
        payload = bound_return(
            manifest,
            assignment,
            outcome="fact_submission",
            claim_relation="weakens",
            statement="A nearby, strictly weaker statement holds.",
            proof=f"Use verified fact {self.root_fact}.",
            predecessors=[self.root_fact],
        )
        return_path.write_text(json.dumps(payload), encoding="utf-8")
        receipt = ingest_return(
            self.store,
            manifest["round_id"],
            assignment["assignment_id"],
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        fact_id = receipt["submission_id"]
        review_id = review_fact(self.store, fact_id)
        self.store.admit(fact_id, review_id=review_id)
        related = self.store.memory_latest()[self.memory_id]
        self.assertEqual(related["status"], "challenged")
        self.assertEqual(related["claim_relation"], "weakens")
        self.store.revoke(fact_id, reason="test revocation", actor="operator")
        reopened = self.store.memory_latest()[self.memory_id]
        self.assertEqual(reopened["status"], "challenged")
        self.assertIsNone(reopened["claim_relation"])
        self.assertIsNone(reopened["related_fact_id"])
        self.assertTrue(self.store.audit().ok, self.store.audit().errors)

    def test_undeclared_artifact_fails_exact_worker_validator(self) -> None:
        manifest, assignment, return_path = self.make_round()
        artifact_path = Path(assignment["artifact_dir_path"]) / "undeclared.txt"
        artifact_path.write_text("unbound evidence\n", encoding="utf-8")
        payload = bound_return(
            manifest,
            assignment,
            outcome="evidence",
            claim="A toy calculation.",
            method="Write one file.",
            result={"value": 1},
            artifacts=[],
            limitations="Evidence only.",
        )
        return_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "undeclared artifact"):
            validate_return(
                self.store,
                manifest["round_id"],
                assignment["assignment_id"],
            )
        with self.assertRaisesRegex(ValueError, "undeclared artifact"):
            ingest_return(
                self.store,
                manifest["round_id"],
                assignment["assignment_id"],
                worker_final_sha256=sha256_bytes(return_path.read_bytes()),
            )

    def test_artifact_size_budget_is_enforced_by_exact_validator(self) -> None:
        manifest, assignment, return_path = self.make_round()
        artifact_path = Path(assignment["artifact_dir_path"]) / "bounded.bin"
        artifact_path.write_bytes(b"123456789")
        payload = bound_return(
            manifest,
            assignment,
            outcome="evidence",
            claim="A bounded artifact.",
            method="Write exact bytes.",
            result={"bytes": 9},
            artifacts=[
                {
                    "path": artifact_path.relative_to(self.store.root).as_posix(),
                    "sha256": sha256_bytes(artifact_path.read_bytes()),
                }
            ],
            limitations="Evidence only.",
        )
        return_path.write_text(json.dumps(payload), encoding="utf-8")
        with patch("mathgraph.worker_returns.MAX_ARTIFACT_BYTES", 8):
            with self.assertRaisesRegex(ValueError, "per-file limit"):
                validate_return(
                    self.store,
                    manifest["round_id"],
                    assignment["assignment_id"],
                )

    def test_evidence_and_dead_end_outcomes_remain_nontruth(self) -> None:
        second_memory = self.store.memory_add(
            {
                "kind": "direction",
                "claim": "Try a deliberately incomplete method.",
                "dependencies": [self.root_fact],
            },
            actor="main",
        )
        manifest = create_round(
            self.store,
            workers=2,
            memory_ids=[self.memory_id, second_memory],
        )
        evidence_assignment, dead_assignment = manifest["assignments"]
        evidence_path = Path(evidence_assignment["return_path"])
        artifact_path = Path(evidence_assignment["artifact_dir_path"]) / "toy.json"
        artifact_path.write_text('{"value":"1/2"}\n', encoding="utf-8")
        evidence_path.write_text(
            json.dumps(
                bound_return(
                    manifest,
                    evidence_assignment,
                    outcome="evidence",
                    claim="A toy calculation supports the refinement.",
                    method="Exact substitution.",
                    result={"value": "1/2"},
                    artifacts=[
                        {
                            "path": artifact_path.relative_to(self.store.root).as_posix(),
                            "sha256": sha256_bytes(artifact_path.read_bytes()),
                        }
                    ],
                    limitations=["Evidence only."],
                )
            ),
            encoding="utf-8",
        )
        dead_path = Path(dead_assignment["return_path"])
        dead_path.write_text(
            json.dumps(
                bound_return(
                    manifest,
                    dead_assignment,
                    outcome="dead_end",
                    claim="The incomplete method stalls.",
                    method="Naive induction.",
                    failure_mode="No induction step.",
                    what_remains_open="Find a different invariant.",
                )
            ),
            encoding="utf-8",
        )
        evidence_receipt = ingest_return(
            self.store,
            manifest["round_id"],
            evidence_assignment["assignment_id"],
            worker_final_sha256=sha256_bytes(evidence_path.read_bytes()),
        )
        dead_receipt = ingest_return(
            self.store,
            manifest["round_id"],
            dead_assignment["assignment_id"],
            worker_final_sha256=sha256_bytes(dead_path.read_bytes()),
        )
        latest = self.store.memory_latest()
        self.assertEqual(latest[evidence_receipt["memory_entry_id"]]["status"], "supported")
        self.assertEqual(latest[dead_receipt["memory_entry_id"]]["status"], "dead_end")
        self.assertEqual(latest[self.memory_id]["status"], "open")
        self.assertEqual(latest[second_memory]["status"], "open")
        self.assertEqual(len(self.store.fact_ids()), 1)
        self.assertTrue(self.store.audit().ok, self.store.audit().errors)

    def test_replanning_same_frontier_has_a_fresh_round_id(self) -> None:
        first = create_round(
            self.store, workers=1, memory_ids=[self.memory_id]
        )
        second = create_round(
            self.store, workers=1, memory_ids=[self.memory_id]
        )
        self.assertNotEqual(first["round_id"], second["round_id"])
        self.assertTrue(self.store.audit().ok, self.store.audit().errors)

    def test_explicit_assignment_count_must_match_workers(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly equal"):
            create_round(
                self.store, workers=2, memory_ids=[self.memory_id]
            )


class GraphRoleAndCliTests(unittest.TestCase):
    def test_cycle_detection(self) -> None:
        a = Fact(
            fact_id="a" * 16,
            problem_id="p",
            author="x",
            predecessors=["b" * 16],
            statement="A",
            proof="A",
        )
        b = Fact(
            fact_id="b" * 16,
            problem_id="p",
            author="x",
            predecessors=["a" * 16],
            statement="B",
            proof="B",
        )
        graph = DependencyGraph({a.fact_id: a, b.fact_id: b})
        with self.assertRaisesRegex(ValueError, "dependency cycle"):
            graph.topological_order()

    def test_verifier_unknown_and_worker_roles_fail_closed(self) -> None:
        self.assertEqual(allowed_commands("verifier"), set())
        self.assertEqual(allowed_commands("typo-role"), set())
        self.assertNotIn("memory-add", allowed_commands("worker"))
        self.assertNotIn("record-review", allowed_commands("worker"))
        self.assertNotIn("admit", allowed_commands("worker"))

    def test_top_level_help_projects_explicit_role_without_changing_choices(
        self,
    ) -> None:
        output = StringIO()
        with (
            patch.dict(os.environ, {"MGRAPH_ROLE": "worker"}),
            redirect_stdout(output),
            self.assertRaises(SystemExit) as stopped,
        ):
            main(
                [
                    "--root",
                    "/tmp/help-only-project",
                    "--role",
                    "gateway",
                    "--help",
                ]
            )
        self.assertEqual(stopped.exception.code, 0)
        help_text = " ".join(output.getvalue().split())
        self.assertIn("certification-record", help_text)
        self.assertNotIn("candidate-release", help_text)
        self.assertNotIn("preflight-return", help_text)

        parser = build_parser(help_role="verifier")
        parsed = parser.parse_args(
            [
                "--root",
                "/tmp/help-only-project",
                "--role",
                "verifier",
                "status",
            ]
        )
        self.assertEqual(parsed.command, "status")
        with redirect_stderr(StringIO()):
            self.assertEqual(
                main(
                    [
                        "--root",
                        "/tmp/help-only-project",
                        "--role",
                        "verifier",
                        "status",
                    ]
                ),
                3,
            )

    def test_top_level_help_projects_environment_verifier_boundary(self) -> None:
        output = StringIO()
        with (
            patch.dict(os.environ, {"MGRAPH_ROLE": "verifier"}),
            redirect_stdout(output),
            self.assertRaises(SystemExit) as stopped,
        ):
            main(["--root", "/tmp/help-only-project", "--help"])
        self.assertEqual(stopped.exception.code, 0)
        help_text = " ".join(output.getvalue().split())
        self.assertIn("no project-shell commands", help_text)
        self.assertIn("external capsule", help_text)
        self.assertNotIn("certification-record", help_text)
        self.assertNotIn("paper-continuation-plan", help_text)

    def test_cli_requires_root_and_has_no_context_or_packet_output_option(self) -> None:
        parser = build_parser()
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["--role", "operator", "status"])
        with tempfile.TemporaryDirectory() as temporary:
            root = str(Path(temporary) / "project")
            with redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit):
                    parser.parse_args(
                        [
                            "--root",
                            root,
                            "--role",
                            "worker",
                            "context",
                            "a" * 16,
                            "--output",
                            "/tmp/escape",
                        ]
                    )
                with self.assertRaises(SystemExit):
                    parser.parse_args(
                        [
                            "--root",
                            root,
                            "--role",
                            "operator",
                            "packet",
                            "a" * 16,
                            "--output",
                            "/tmp/escape",
                        ]
                    )

    def test_cli_rejects_project_inside_skill_and_report_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill_root = Path(temporary) / "skill"
            nested = skill_root / "project"
            skill_root.mkdir()
            with patch.dict(os.environ, {"MGRAPH_SKILL_ROOT": str(skill_root)}):
                with redirect_stderr(StringIO()), redirect_stdout(StringIO()):
                    self.assertEqual(
                        main(
                            [
                                "--root",
                                str(nested),
                                "--role",
                                "operator",
                                "init",
                                "--project-id",
                                "p",
                                "--title",
                                "P",
                            ]
                        ),
                        2,
                    )
            external = Path(temporary) / "external-project"
            store = MathGraphStore._for_legacy_workflow_fixture(external)
            store.initialize(project_id="p", title="P")
            with self.assertRaisesRegex(ValueError, "unsafe report output"):
                store.report_output_path("../escape.md")
            outside = Path(temporary) / "outside"
            outside.mkdir()
            (store.reports_dir / "escape-link").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "escapes its root"):
                store.report_output_path("escape-link/report.md")


if __name__ == "__main__":
    unittest.main()
