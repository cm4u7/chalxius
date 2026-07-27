from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from mathgraph.adoption import (
    _legacy_estimate_gated_adoption_plan,
    build_adoption_plan,
    compact_adoption_binding,
    validate_adoption_binding,
    validate_adoption_plan,
)
from mathgraph.campaigns import (
    COMPACT_SCORE_ROLE,
    COMPACT_SCORE_MODEL,
    actionable_score,
    decision_factors,
)
from mathgraph.cli import main as cli_main
from mathgraph.contracts import POLICY_REVISION_V4, sha256_json
from mathgraph.computations import validate_required_experiment_receipt
from mathgraph.fact_bundles import (
    build_claim_card,
    lint_expert_document,
    validate_claim_card,
)
from mathgraph.markdown import validate_fact_round_trip
from mathgraph.model import Fact
from mathgraph.orchestrator import create_round
from mathgraph.protocol import validate_task_card
from mathgraph.roles import allowed_commands, allowed_commands_for_workflow
from mathgraph.store import MathGraphStore


def workload_profile(
    *,
    audience: str = "internal",
    activity: str = "proof",
    computation_role: str = "none",
    wall_seconds: int | None = 0,
    stages: int = 0,
    resume: bool = False,
    candidates: int = 1,
    internal_edges: int = 0,
    atomic: bool = False,
    source_claim: bool = False,
    convention: bool = False,
    quantifier: bool = False,
    terminology: bool = False,
) -> dict:
    return {
        "schema_version": 1,
        "policy_revision": POLICY_REVISION_V4,
        "activity": activity,
        "audience": audience,
        "computation": {
            "role": computation_role,
            "estimated_wall_seconds": wall_seconds,
            "stage_count": stages,
            "resume_required": resume,
        },
        "fact_output": {
            "candidate_count": candidates,
            "internal_dependency_count": internal_edges,
            "atomic_visibility_required": atomic,
        },
        "semantics": {
            "source_claim": source_claim,
            "convention_sensitive": convention,
            "quantifier_sensitive": quantifier,
            "terminology_sensitive": terminology,
        },
    }


class V4AdoptionPolicyTests(unittest.TestCase):
    def test_three_plane_protocol_is_always_required(self) -> None:
        plan = build_adoption_plan(workload_profile())
        self.assertEqual(
            plan["communication_protocol"],
            {
                "control_plane": "required_compact_nontruth",
                "mathematical_state_plane": "required_typed_truth_boundary",
                "narrative_plane": "required_nontruth",
                "same_round_visibility": "frozen_snapshot_only",
            },
        )
        validate_adoption_plan(plan)
        tampered = json.loads(json.dumps(plan))
        tampered["communication_protocol"]["narrative_plane"] = "optional"
        with self.assertRaisesRegex(ValueError, "deterministic V4 policy"):
            validate_adoption_plan(tampered)

    def test_legacy_estimate_gate_requires_explicit_frozen_replay(self) -> None:
        profile = workload_profile(
            activity="computation",
            computation_role="corroborative",
            wall_seconds=301,
            stages=1,
            resume=False,
        )
        current = build_adoption_plan(profile)
        legacy = _legacy_estimate_gated_adoption_plan(profile)
        self.assertEqual(
            current["features"]["experiment_checkpoint"]["status"],
            "available",
        )
        self.assertEqual(
            legacy["features"]["experiment_checkpoint"]["status"],
            "required",
        )
        with self.assertRaisesRegex(ValueError, "deterministic V4 policy"):
            validate_adoption_plan(legacy)
        validate_adoption_plan(
            legacy,
            allow_legacy_estimate_policy=True,
        )
        legacy_binding = compact_adoption_binding(
            legacy,
            allow_legacy_estimate_policy=True,
        )
        with self.assertRaisesRegex(ValueError, "deterministic V4 policy"):
            validate_adoption_binding(legacy_binding)
        validate_adoption_binding(
            legacy_binding,
            allow_legacy_estimate_policy=True,
        )

    def test_small_exact_computation_does_not_force_experiment(self) -> None:
        plan = build_adoption_plan(
            workload_profile(
                activity="computation",
                computation_role="corroborative",
                wall_seconds=120,
                stages=1,
            )
        )
        self.assertEqual(
            plan["features"]["experiment_checkpoint"]["status"],
            "available",
        )
        self.assertEqual(
            plan["features"]["artifact_replay"]["status"],
            "available",
        )

    def test_unknown_or_huge_estimate_does_not_change_adoption(self) -> None:
        decisions = []
        for wall_seconds in (120, 301, 10**9, None):
            with self.subTest(wall_seconds=wall_seconds):
                plan = build_adoption_plan(
                    workload_profile(
                        activity="computation",
                        computation_role="corroborative",
                        wall_seconds=wall_seconds,
                        stages=1,
                        resume=False,
                    )
                )
                self.assertEqual(
                    plan["features"]["experiment_checkpoint"]["status"],
                    "available",
                )
                decisions.append(
                    {
                        "features": plan["features"],
                        "replan_triggers": plan["replan_triggers"],
                    }
                )
        self.assertTrue(all(item == decisions[0] for item in decisions[1:]))

    def test_multistage_or_resume_required_forces_experiment(self) -> None:
        profiles = [
            workload_profile(
                activity="computation",
                computation_role="corroborative",
                wall_seconds=None,
                stages=2,
            ),
            workload_profile(
                activity="computation",
                computation_role="corroborative",
                wall_seconds=10**9,
                stages=1,
                resume=True,
            ),
        ]
        for profile in profiles:
            with self.subTest(profile=profile):
                plan = build_adoption_plan(profile)
                self.assertEqual(
                    plan["features"]["experiment_checkpoint"]["status"],
                    "required",
                )

    def test_load_bearing_computation_forces_artifact_replay(self) -> None:
        plan = build_adoption_plan(
            workload_profile(
                activity="computation",
                computation_role="load_bearing",
                wall_seconds=30,
                stages=1,
            )
        )
        self.assertEqual(
            plan["features"]["artifact_replay"]["status"],
            "required",
        )
        self.assertEqual(
            plan["features"]["experiment_checkpoint"]["status"],
            "available",
        )

    def test_fact_bundle_and_export_triggers_are_conditional_mandates(self) -> None:
        plan = build_adoption_plan(
            workload_profile(
                audience="advisor",
                activity="export",
                candidates=3,
                internal_edges=2,
                source_claim=True,
                convention=True,
                quantifier=True,
                terminology=True,
            )
        )
        for feature in (
            "atomic_fact_bundle",
            "terminology_export_lint",
            "source_claim_gate",
            "convention_gate",
            "quantifier_gate",
        ):
            self.assertEqual(
                plan["features"][feature]["status"],
                "required",
            )

    def test_multiple_independent_facts_do_not_force_atomic_bundle(self) -> None:
        plan = build_adoption_plan(
            workload_profile(candidates=3, internal_edges=0, atomic=False)
        )
        self.assertEqual(
            plan["features"]["atomic_fact_bundle"]["status"],
            "available",
        )


class V4CompactFrontierTests(unittest.TestCase):
    def test_direct_four_factor_profile_is_monotone_and_cost_sensitive(self) -> None:
        base = {
            "decision_profile": {
                "impact": 0.9,
                "information_value": 0.8,
                "tractability": 0.8,
                "burden": 0.2,
            }
        }
        expensive = {
            "decision_profile": {
                **base["decision_profile"],
                "burden": 0.8,
            }
        }
        self.assertGreater(
            actionable_score(base, readiness=1.0),
            actionable_score(expensive, readiness=1.0),
        )
        self.assertEqual(COMPACT_SCORE_ROLE, "priority_ordering_only")
        self.assertNotIn("score_role", base)
        self.assertNotIn("score_role", expensive)
        factors = decision_factors(base, readiness=0.4)
        self.assertEqual(factors["feasibility"], 0.6)

    def test_legacy_eight_metrics_project_without_rewrite(self) -> None:
        legacy = {
            "priority": 0.8,
            "target_relevance": 1.0,
            "decisiveness": 0.7,
            "information_gain": 0.6,
            "novelty": 0.2,
            "testability": 0.9,
            "estimated_cost": 0.3,
            "risk": 0.4,
        }
        factors = decision_factors(legacy, readiness=1.0)
        self.assertEqual(factors["impact"], 0.9)
        self.assertEqual(factors["feasibility"], 0.95)
        self.assertEqual(factors["burden"], 0.34)

    def test_memory_accepts_four_factors_and_rejects_mixed_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MathGraphStore(directory)
            store.initialize(
                project_id="compact-frontier",
                title="Compact frontier",
                workflow_evidence_version=4,
            )
            profile = {
                "impact": 0.8,
                "information_value": 0.7,
                "tractability": 0.9,
                "burden": 0.2,
            }
            memory_id = store.memory_add(
                {
                    "kind": "direction",
                    "claim": "Use four factors.",
                    "decision_profile": profile,
                },
                actor="main",
            )
            entry = store.memory_latest()[memory_id]
            self.assertEqual(entry["decision_profile"], profile)
            self.assertEqual(entry["score_model"], COMPACT_SCORE_MODEL)
            self.assertNotIn("priority", entry)
            with self.assertRaisesRegex(ValueError, "cannot mix"):
                store.memory_add(
                    {
                        "kind": "direction",
                        "claim": "Ambiguous score input.",
                        "decision_profile": profile,
                        "priority": 0.5,
                    },
                    actor="main",
                )

    def test_new_v4_memory_defaults_to_neutral_four_factor_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MathGraphStore(directory)
            store.initialize(
                project_id="compact-frontier-default",
                title="Compact frontier default",
                workflow_evidence_version=4,
            )
            memory_id = store.memory_add(
                {
                    "kind": "direction",
                    "claim": "Use a neutral compact profile when not yet scored.",
                },
                actor="main",
            )
            entry = store.memory_latest()[memory_id]
            self.assertEqual(
                entry["decision_profile"],
                {
                    "burden": 0.5,
                    "impact": 0.5,
                    "information_value": 0.5,
                    "tractability": 0.5,
                },
            )
            for field in (
                "priority",
                "target_relevance",
                "decisiveness",
                "information_gain",
                "testability",
                "novelty",
                "risk",
                "estimated_cost",
            ):
                self.assertNotIn(field, entry)

    def test_low_score_explicit_memory_remains_schedulable_and_reports_role(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MathGraphStore(directory)
            store.initialize(
                project_id="ordering-only-frontier",
                title="Ordering-only frontier",
                workflow_evidence_version=4,
            )
            high_id = store.memory_add(
                {
                    "kind": "direction",
                    "claim": "High priority direction.",
                    "decision_profile": {
                        "impact": 1.0,
                        "information_value": 1.0,
                        "tractability": 1.0,
                        "burden": 0.0,
                    },
                },
                actor="main",
            )
            low_id = store.memory_add(
                {
                    "kind": "direction",
                    "claim": "Low priority but still eligible direction.",
                    "decision_profile": {
                        "impact": 0.0,
                        "information_value": 0.0,
                        "tractability": 0.0,
                        "burden": 1.0,
                    },
                },
                actor="main",
            )
            frontiers = [
                store.frontier(limit=10),
                store.frontier(
                    limit=10,
                    actionable=False,
                    collapse_repairs=False,
                ),
                store.frontier(
                    limit=10,
                    actionable=False,
                    collapse_repairs=False,
                    include_history=True,
                ),
            ]
            frontier = frontiers[0]
            by_id = {entry["id"]: entry for entry in frontier}
            self.assertLess(by_id[low_id]["score"], by_id[high_id]["score"])
            for projection in frontiers:
                self.assertTrue(
                    all(
                        entry["score_role"] == COMPACT_SCORE_ROLE
                        for entry in projection
                    )
                )
            planned = create_round(
                store,
                workers=1,
                memory_ids=[low_id],
            )
            self.assertEqual(
                planned["assignments"][0]["memory_id"],
                low_id,
            )
            self.assertEqual(store.memory_latest()[low_id]["status"], "open")


class V4TaskCardPolicyBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="adoption-task-card",
            title="Adoption task card",
            workflow_evidence_version=4,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_task_card_and_assignment_bind_same_adoption_plan(self) -> None:
        memory_id = self.store.memory_add(
            {
                "kind": "direction",
                "claim": "Bind the formal adoption policy.",
                "workload_profile": workload_profile(
                    source_claim=False,
                    convention=False,
                ),
            },
            actor="main",
        )
        planned = create_round(
            self.store,
            workers=1,
            memory_ids=[memory_id],
        )
        assignment = planned["assignments"][0]
        card = json.loads(
            Path(assignment["task_card_path"]).read_text(encoding="utf-8")
        )
        validate_task_card(card)
        self.assertEqual(
            assignment["contract"]["adoption_plan_sha256"],
            card["adoption_plan"]["plan_sha256"],
        )

    def test_load_bearing_profile_cannot_hide_closed_packet_plan(self) -> None:
        profile = workload_profile(
            activity="computation",
            computation_role="load_bearing",
            wall_seconds=20,
            stages=1,
        )
        closed_packet_id = self.store.memory_add(
            {
                "kind": "computation",
                "claim": (
                    "Find an exact computation-backed counterexample to "
                    "the proposed value 11."
                ),
                "workload_profile": profile,
            },
            actor="main",
        )
        with self.assertRaisesRegex(ValueError, "artifact_replay"):
            create_round(
                self.store,
                workers=1,
                memory_ids=[closed_packet_id],
            )

        replay_id = self.store.memory_add(
            {
                "kind": "computation",
                "claim": (
                    "Find an exact computation-backed counterexample to "
                    "the proposed value 11, with replay bytes."
                ),
                "workload_profile": profile,
                "verification_plan": {
                    "mode": "artifact_replay",
                    "authorized_artifact_roles": [
                        "entrypoint",
                        "stdout",
                    ],
                    "required_checks": [
                        "execute",
                        "compare_exact_output",
                    ],
                },
            },
            actor="main",
        )
        planned = create_round(
            self.store,
            workers=1,
            memory_ids=[replay_id],
        )
        assignment = planned["assignments"][0]
        card = json.loads(
            Path(assignment["task_card_path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(
            card["adoption_plan"]["feature_statuses"]["artifact_replay"],
            "required",
        )
        self.assertEqual(
            card["verification_plan"]["mode"],
            "artifact_replay",
        )

    def test_required_experiment_cannot_finish_without_final_receipt(self) -> None:
        memory_id = self.store.memory_add(
            {
                "kind": "computation",
                "claim": "A long staged computation.",
                "workload_profile": workload_profile(
                    activity="computation",
                    computation_role="corroborative",
                    wall_seconds=900,
                    stages=2,
                    resume=True,
                ),
            },
            actor="main",
        )
        planned = create_round(
            self.store,
            workers=1,
            memory_ids=[memory_id],
        )
        card = json.loads(
            Path(planned["assignments"][0]["task_card_path"]).read_text(
                encoding="utf-8"
            )
        )
        with self.assertRaisesRegex(ValueError, "finalized experiment receipt"):
            validate_required_experiment_receipt(
                project_root=self.root,
                task_card=card,
                artifacts=[],
            )

    def test_v4_worker_cli_cannot_query_live_project_state(self) -> None:
        error = io.StringIO()
        with redirect_stderr(error):
            status = cli_main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "worker",
                    "search",
                    "anything",
                ]
            )
        self.assertEqual(status, 3)
        self.assertIn("not allowed", error.getvalue())


class V4ClaimCardTests(unittest.TestCase):
    def test_formal_claim_card_is_hash_bound_and_lintable(self) -> None:
        fact = Fact(
            problem_id="claim-card",
            author="worker",
            predecessors=[],
            statement="[CLAIM:MAIN] Admitted theorem.",
            proof="Proof.",
        )
        card = build_claim_card(
            fact=fact,
            audience="expert",
            literal_source_claim="Literal source theorem.",
            researcher_variant="Restricted researcher theorem.",
            variant_diff=[
                {
                    "field": "domain",
                    "from": "all curves",
                    "to": "genus zero",
                    "authority": "researcher_defined",
                }
            ],
            source_locator="Definition 2.1",
            convention_profile="conv-test: sign=positive",
            reproduction_bundle=[],
        )
        validate_claim_card(card)
        text = "\n".join(
            [
                card["literal_source_claim"],
                card["researcher_variant"],
                card["source_locator"],
                card["convention_profile"],
                card["admitted_conclusion"],
                (
                    "AI assistance: AI tools assisted drafting and protocol "
                    "checks; an independent verifier reviewed the claims."
                ),
            ]
        )
        self.assertEqual(
            lint_expert_document(text, claim_card=card),
            [],
        )
        tampered = {**card, "admitted_conclusion": "Different theorem."}
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate_claim_card(tampered)

    def test_define_policy_accepts_definition_as_first_occurrence(self) -> None:
        fact = Fact(
            problem_id="claim-card-definition",
            author="worker",
            predecessors=[],
            statement="[CLAIM:MAIN] Defined theorem.",
            proof="Proof. [TERM:chalk]",
            terminology=[
                {
                    "key": "chalk",
                    "term": "chalk locus",
                    "definition": "chalk locus means the selected component",
                    "origin": "local_shorthand",
                    "source_locator": "",
                    "export_policy": "define",
                    "replacement": "",
                    "proof_anchor": "[TERM:chalk]",
                }
            ],
        )
        card = build_claim_card(
            fact=fact,
            audience="advisor",
            literal_source_claim="Literal claim.",
            researcher_variant="Researcher variant.",
            variant_diff=[],
            source_locator="Theorem 1",
            convention_profile="conv-test",
            reproduction_bundle=[],
        )
        text = "\n".join(
            [
                "chalk locus means the selected component.",
                card["literal_source_claim"],
                card["researcher_variant"],
                card["source_locator"],
                card["convention_profile"],
                card["admitted_conclusion"],
                (
                    "AI assistance: AI tools assisted drafting and protocol "
                    "checks; an independent verifier reviewed the claims."
                ),
            ]
        )
        self.assertEqual(lint_expert_document(text, claim_card=card), [])

    def test_expert_lint_cli_emits_content_bound_receipt(self) -> None:
        fact = Fact(
            problem_id="expert-lint-receipt",
            author="worker",
            predecessors=[],
            statement="[CLAIM:MAIN] Receipt-bound theorem.",
            proof="Proof.",
        )
        card = build_claim_card(
            fact=fact,
            audience="expert",
            literal_source_claim="Literal receipt claim.",
            researcher_variant="Receipt variant.",
            variant_diff=[],
            source_locator="Theorem 7",
            convention_profile="conv-receipt",
            reproduction_bundle=[],
        )
        text = "\n".join(
            [
                card["literal_source_claim"],
                card["researcher_variant"],
                card["source_locator"],
                card["convention_profile"],
                card["admitted_conclusion"],
                "AI assistance: AI assisted protocol checking.",
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            MathGraphStore(root).initialize(
                project_id="expert-lint-receipt",
                title="Expert lint receipt",
                workflow_evidence_version=4,
            )
            document_path = root / "expert.md"
            claim_card_path = root / "claim-card.json"
            document_path.write_text(text, encoding="utf-8")
            claim_card_path.write_text(
                json.dumps(card, ensure_ascii=False),
                encoding="utf-8",
            )
            output = io.StringIO()
            with redirect_stdout(output):
                status = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "main",
                        "lint-expert-document",
                        "--input",
                        str(document_path),
                        "--claim-card",
                        str(claim_card_path),
                    ]
                )
            self.assertEqual(status, 0)
            receipt = json.loads(output.getvalue())
            self.assertTrue(receipt["ok"])
            self.assertIn("quantifier ledger", receipt["scope"])
            semantic = {
                key: value
                for key, value in receipt.items()
                if key != "lint_receipt_sha256"
            }
            self.assertEqual(
                receipt["lint_receipt_sha256"],
                sha256_json(semantic),
            )

    def test_store_exports_claim_card_from_fact_truth_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MathGraphStore(directory)
            store.initialize(
                project_id="claim-card-store",
                title="Claim card store",
                workflow_evidence_version=4,
            )
            fact = Fact(
                problem_id="claim-card-store",
                author="worker",
                predecessors=[],
                statement="[CLAIM:MAIN] Stored admitted theorem.",
                proof="Proof.",
            )
            store._write_bytes_once(
                store.fact_path(fact.fact_id),
                validate_fact_round_trip(fact).encode("utf-8"),
            )
            card = store.claim_card(fact.fact_id, audience="publication")
            self.assertEqual(card["fact_id"], fact.fact_id)
            self.assertEqual(card["admitted_conclusion"], fact.statement)
            validate_claim_card(card)

    def test_preflight_and_export_commands_are_not_worker_capabilities(self) -> None:
        main = allowed_commands("main")
        worker = allowed_commands("worker")
        verifier = allowed_commands("verifier")
        for command in (
            "adoption-plan",
            "export-claim-card",
            "lint-expert-document",
        ):
            self.assertIn(command, main)
            self.assertNotIn(command, worker)
            self.assertNotIn(command, verifier)

    def test_v4_worker_has_only_bound_return_and_experiment_capabilities(
        self,
    ) -> None:
        v3_worker = allowed_commands_for_workflow("worker", 3)
        v4_worker = allowed_commands_for_workflow("worker", 4)
        self.assertIn("search", v3_worker)
        self.assertNotIn("search", v4_worker)
        self.assertNotIn("show", v4_worker)
        self.assertNotIn("context", v4_worker)
        self.assertNotIn("frontier", v4_worker)
        self.assertEqual(
            v4_worker,
            {
                "preflight-return",
                "validate-return",
                "experiment-start",
                "experiment-event",
                "experiment-resume",
                "experiment-status",
                "experiment-finalize",
            },
        )


if __name__ == "__main__":
    unittest.main()
