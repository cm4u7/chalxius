from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mathgraph.cli import main as cli_main
from mathgraph.adverse_routing import (
    LEGACY_BASELINE_ATTACK_RULES,
    MAX_ACTIVE_ROUTE_RULES,
    MAX_SELECTED_RULES,
    validate_attack_learning,
    validate_attack_route_recommendation_report,
)
from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.roles import allowed_commands
from mathgraph.store import MathGraphStore


class AdverseRoutingEvolutionTests(unittest.TestCase):
    def _store(self, root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="adverse-routing-fixture",
            title="Adverse routing fixture",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _learning(
        *,
        term: str = "uniform",
        instruction: str = "Attack silent witness replacement.",
        result_kind: str = "surviving_counterexample",
        effect_kind: str = "claim_refuted",
    ) -> dict[str, object]:
        return {
            "schema_version": 3,
            "result_kind": result_kind,
            "attack_family": "quantifier_witness",
            "target_pattern": "A pointwise existential witness is treated as canonical and uniform.",
            "failure_mechanism": "The proof silently reuses one witness outside its quantified scope.",
            "premise_witnesses": ["For each parameter there is a locally valid witness."],
            "conclusion_failure_witness": "Two parameters require incompatible witnesses.",
            "reproduction_steps": [
                "Choose two parameters with disjoint valid-witness sets.",
                "Check every stated premise separately.",
                "Show that no single witness satisfies the claimed conclusion.",
            ],
            "success_boundary": "Refutes only the claimed uniform/canonical witness, not pointwise existence.",
            "value_effects": [
                {
                    "effect_kind": effect_kind,
                    "before": "The route silently required one uniform witness.",
                    "after": "The claim is either refuted or narrowed to explicit pointwise witnesses.",
                    "evidence": "The two-parameter construction isolates the load-bearing change.",
                }
            ],
        }

    @staticmethod
    def _main_rule(
        *, term: str = "uniform", instruction: str = "Attack witness scope changes."
    ) -> dict[str, object]:
        return {
            "attack_family": "quantifier_witness",
            "trigger": {
                "research_kinds": ["challenge"],
                "claim_terms_any": [term],
                "metadata_signals_any": ["quantifier_sensitive"],
                "universal_refute": False,
            },
            "instruction": instruction,
            "false_positive_guards": [
                "Accept explicitly pointwise conclusions."
            ],
            "scope_note": "Use when witness dependency is load-bearing.",
        }

    @staticmethod
    def _write_return(
        *,
        store: MathGraphStore,
        assignment: dict[str, object],
        outcome: str,
        attack_learning: dict[str, object] | None,
        extended: bool,
    ) -> str:
        card_path = Path(str(assignment["task_card_path"]))
        card = json.loads(card_path.read_text(encoding="utf-8"))
        payload: dict[str, object] = {
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
            "claim": "The proposed uniform conclusion fails.",
            "content": "A checked two-parameter witness construction refutes uniformity.",
            "narrative": {
                "rationale": "Stress-test witness identity.",
                "summary": "The witnesses cannot be chosen uniformly.",
                "intuition": "Local choices disagree.",
                "limitations": "Pointwise existence remains open.",
            },
            "artifacts": [],
        }
        if "assurance_contract" in card:
            payload.update(
                {
                    "obligation_dispositions": [
                        {
                            "obligation_id": item["obligation_id"],
                            "status": "complete",
                            "witness_artifact_sha256s": [],
                            "rationale": "No artifact-bearing obligation applies to this logical refutation fixture.",
                        }
                        for item in card["assurance_contract"]["obligations"]
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
            )
        if extended:
            payload["attack_learning"] = attack_learning
        return_path = store.root / str(card["return_contract"]["return_relpath"])
        return_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return sha256_bytes(return_path.read_bytes())

    def _counterexample_round(
        self,
        *,
        store: MathGraphStore,
        host_scope: str = "host-adverse-task",
        claim: str = "Stress-test the uniform witness claim.",
        adverse_domain_profile: str | None = None,
    ) -> tuple[dict[str, object], dict[str, object]]:
        payload: dict[str, object] = {
            "kind": "challenge",
            "claim": claim,
            "logic_signals": ["quantifier_sensitive"],
        }
        if adverse_domain_profile is not None:
            payload["adverse_domain_profile"] = adverse_domain_profile
        research = store.v5_lifecycle().add_research(
            payload,
            actor="main",
        )
        round_status = store.v5_lifecycle().create_round(
            workers=1,
            research_ids=[research["research_id"]],
            host_task_scope_id=host_scope,
        )
        assignment = dict(round_status["assignments"][0])
        assignment["round_id"] = round_status["round_id"]
        return research, assignment

    def _capture_one(self, store: MathGraphStore) -> tuple[dict[str, object], dict[str, object]]:
        _, assignment = self._counterexample_round(store=store)
        card = json.loads(Path(str(assignment["task_card_path"])).read_text(encoding="utf-8"))
        self.assertIn("adverse_routing", card)
        final_sha = self._write_return(
            store=store,
            assignment=assignment,
            outcome="counterexample",
            attack_learning=self._learning(),
            extended=True,
        )
        receipt = store.v5_lifecycle().ingest_return(
            round_id=str(assignment["round_id"]),
            assignment_id=str(assignment["assignment_id"]),
            worker_final_sha256=final_sha,
        )
        return assignment, receipt

    def test_default_reporting_preserves_a_legacy_frozen_round_without_backfill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            status = store.adverse_routes().status()
            self.assertTrue(status["enabled"])
            self.assertTrue(status["reporting_default"])
            self.assertFalse(status["state_materialized"])
            zero = store.adverse_routes().report(host_task_scope_id="read-only-zero")
            self.assertEqual(zero["attacks"], [])
            self.assertFalse(store.adverse_routes().contract_path.exists())
            with patch(
                "mathgraph.adverse_routing.AdverseRoutingManager.task_card_binding",
                return_value=None,
            ):
                _, assignment = self._counterexample_round(store=store)
            card = json.loads(Path(str(assignment["task_card_path"])).read_text(encoding="utf-8"))
            self.assertNotIn("adverse_routing", card)

            store.adverse_routes().initialize(actor="operator", reason="Explicit opt-in.")
            store.v5_lifecycle().validate_task_card(
                card, expected_path=Path(str(assignment["task_card_path"]))
            )
            final_sha = self._write_return(
                store=store,
                assignment=assignment,
                outcome="counterexample",
                attack_learning=None,
                extended=False,
            )
            receipt = store.v5_lifecycle().ingest_return(
                round_id=str(assignment["round_id"]),
                assignment_id=str(assignment["assignment_id"]),
                worker_final_sha256=final_sha,
            )
            self.assertEqual(receipt["effect"], "one_cumulative_research_entry")
            self.assertNotIn("attack_case_id", receipt)
            self.assertEqual(store.adverse_routes().status()["case_count"], 0)

    def test_earlier_workflow_project_cannot_be_mutated_by_opt_in_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = MathGraphStore(root)
            store.initialize(
                project_id="active-040-fixture",
                title="Active 0.4.0 workflow fixture",
                workflow_evidence_version=4,
            )
            self.assertFalse(store.adverse_routes().status()["enabled"])
            with self.assertRaisesRegex(ValueError, "V5-only"):
                store.adverse_routes().initialize(
                    actor="operator",
                    reason="Must not attach to an earlier workflow project.",
                )
            self.assertFalse(store.adverse_routes().contract_path.exists())

    def test_counterexample_creates_case_proposal_and_separate_attack_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            store.adverse_routes().initialize(actor="operator", reason="Enable learning.")
            assignment, receipt = self._capture_one(store)
            self.assertIn("attack_case_id", receipt)
            self.assertIn("route_proposal_id", receipt)
            card = json.loads(Path(str(assignment["task_card_path"])).read_text(encoding="utf-8"))
            self.assertEqual(len(card["adverse_routing"]["baseline_rules"]), 9)
            self.assertIn(
                "baseline_hidden_conjunct_split",
                {
                    item["rule_id"]
                    for item in card["adverse_routing"]["baseline_rules"]
                },
            )
            self.assertEqual(card["adverse_routing"]["approved_rules"], [])

            report = store.adverse_routes().report(
                host_task_scope_id="host-adverse-task"
            )
            self.assertEqual(report["summary"]["worker_reported_success_count"], 1)
            self.assertEqual(report["summary"]["pending_main_synthesis_count"], 1)
            self.assertFalse(report["user_decision_required"])
            self.assertEqual(
                report["routing_change_policy"],
                "no_route_change_without_main_synthesis",
            )
            self.assertEqual(report["truth_effect"], "none")
            self.assertNotIn("chx", json.dumps(report).casefold())

            concise = store.adverse_routes().recommendation_report(
                host_task_scope_id="host-adverse-task"
            )
            self.assertEqual(len(concise["recommendations"]), 1)
            self.assertEqual(
                concise["recommendations"][0]["main_disposition"],
                "synthesize_compress_or_reject",
            )
            self.assertEqual(
                concise["recommendations"][0]["what_it_checks"],
                "Checks whether quantifier order or witness dependence was changed without justification.",
            )
            serialized = json.dumps(concise, ensure_ascii=False)
            for omitted in (
                "failure_mechanism",
                "premise_witnesses",
                "reproduction_steps",
                "value_effects",
            ):
                self.assertNotIn(omitted, serialized)
            for omitted in ("assignments", "cards", "returns"):
                self.assertNotIn(omitted, concise)
            tampered = deepcopy(concise)
            tampered["recommendations"][0]["number"] = 2
            semantic = {
                key: value
                for key, value in tampered.items()
                if key != "report_sha256"
            }
            tampered["report_sha256"] = sha256_json(semantic)
            with self.assertRaisesRegex(ValueError, "item is invalid"):
                validate_attack_route_recommendation_report(tampered)

    def test_philosophy_baselines_require_an_explicit_validated_domain(self) -> None:
        philosophy_rule_ids = {
            "baseline_philosophy_plain_language_substitution",
            "baseline_philosophy_burden_charity_failure_surface",
            "baseline_philosophy_operator_scope_equivalence",
        }
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            with self.assertRaisesRegex(
                ValueError,
                "adverse_domain_profile must be mathematics, philosophy, or mixed",
            ):
                store.v5_lifecycle().add_research(
                    {
                        "kind": "challenge",
                        "claim": "Reject an ambiguous domain marker.",
                        "adverse_domain_profile": "philosophy-ish",
                    },
                    actor="main",
                )
            unmarked_research, unmarked = self._counterexample_round(
                store=store,
                host_scope="unmarked-philosophy-words",
                claim=(
                    "A philosophy argument mentions modality, burden, exceptions, "
                    "and ordinary language."
                ),
            )
            unmarked_card = json.loads(
                Path(str(unmarked["task_card_path"])).read_text(encoding="utf-8")
            )
            unmarked_ids = {
                item["rule_id"]
                for item in unmarked_card["adverse_routing"]["baseline_rules"]
            }
            self.assertIn("baseline_hidden_conjunct_split", unmarked_ids)
            self.assertTrue(philosophy_rule_ids.isdisjoint(unmarked_ids))
            self.assertFalse(
                unmarked_card["adverse_routing"]["scope_evidence"][
                    "philosophy_active"
                ]
            )
            self.assertEqual(
                unmarked_card["adverse_routing"]["scope_evidence"][
                    "domain_source"
                ],
                "none",
            )

            _, mathematical = self._counterexample_round(
                store=store,
                host_scope="explicit-mathematics-domain",
                claim="Test a mathematical claim containing modal and exception words.",
                adverse_domain_profile="mathematics",
            )
            mathematical_card = json.loads(
                Path(str(mathematical["task_card_path"])).read_text(
                    encoding="utf-8"
                )
            )
            mathematical_ids = {
                item["rule_id"]
                for item in mathematical_card["adverse_routing"]["baseline_rules"]
            }
            self.assertTrue(philosophy_rule_ids.isdisjoint(mathematical_ids))
            self.assertFalse(
                mathematical_card["adverse_routing"]["scope_evidence"][
                    "philosophy_active"
                ]
            )

            for profile in ("philosophy", "mixed"):
                with self.subTest(profile=profile):
                    research, assignment = self._counterexample_round(
                        store=store,
                        host_scope=f"{profile}-domain",
                        claim="Test an explicitly domain-bound argument.",
                        adverse_domain_profile=profile,
                    )
                    card = json.loads(
                        Path(str(assignment["task_card_path"])).read_text(
                            encoding="utf-8"
                        )
                    )
                    rule_ids = {
                        item["rule_id"]
                        for item in card["adverse_routing"]["baseline_rules"]
                    }
                    self.assertEqual(len(rule_ids), 12)
                    self.assertTrue(philosophy_rule_ids.issubset(rule_ids))
                    self.assertIn("baseline_hidden_conjunct_split", rule_ids)
                    self.assertTrue(
                        card["adverse_routing"]["scope_evidence"][
                            "philosophy_active"
                        ]
                    )
                    self.assertEqual(
                        card["adverse_routing"]["scope_evidence"][
                            "domain_profile"
                        ],
                        profile,
                    )
                    self.assertEqual(
                        card["adverse_routing"]["scope_evidence"][
                            "domain_source"
                        ],
                        "explicit_research_metadata",
                    )
                    rules_by_id = {
                        item["rule_id"]: item
                        for item in card["adverse_routing"]["baseline_rules"]
                    }
                    self.assertIn(
                        "ordinary-language",
                        rules_by_id[
                            "baseline_philosophy_plain_language_substitution"
                        ]["instruction"],
                    )
                    self.assertIn(
                        "strongest good-faith objection",
                        rules_by_id[
                            "baseline_philosophy_burden_charity_failure_surface"
                        ]["instruction"],
                    )
                    self.assertIn(
                        "quantifiers",
                        rules_by_id[
                            "baseline_philosophy_operator_scope_equivalence"
                        ]["instruction"],
                    )
                    store.adverse_routes().validate_task_card_binding(
                        card["adverse_routing"],
                        work_mode="refute",
                        related_artifacts=[],
                        entry=research,
                    )

            tampered = deepcopy(unmarked_card["adverse_routing"])
            tampered["scope_evidence"]["philosophy_active"] = True
            tampered["scope_evidence"]["domain_profile"] = "philosophy"
            tampered["scope_evidence"]["domain_source"] = (
                "explicit_research_metadata"
            )
            with self.assertRaisesRegex(
                ValueError, "philosophy scope drifted or was inferred from text"
            ):
                store.adverse_routes().validate_task_card_binding(
                    tampered,
                    work_mode="refute",
                    related_artifacts=[],
                    entry=unmarked_research,
                )

    def test_concise_report_deduplicates_attack_families(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            manager = store.adverse_routes()
            first_rule = self._main_rule(
                term="uniform",
                instruction="Attack silent uniform-witness replacement.",
            )
            second_rule = self._main_rule(
                term="canonical",
                instruction="Attack silent canonical-witness replacement.",
            )
            scope_id = "hosttask-" + "a" * 32
            state = {
                "cases": [
                    {
                        "case_id": "attack-case-" + "1" * 64,
                        "host_task_scope_id": scope_id,
                        "attack_result": "productive_challenge",
                        "attack_learning": {
                            "attack_family": "quantifier_witness",
                            "failure_mechanism": "A witness escaped its quantified scope.",
                            "success_boundary": "Only witness dependency is challenged.",
                        },
                    },
                    {
                        "case_id": "attack-case-" + "2" * 64,
                        "host_task_scope_id": scope_id,
                        "attack_result": "surviving_counterexample",
                        "attack_learning": {
                            "attack_family": "quantifier_witness",
                            "failure_mechanism": "A canonical witness was silently selected.",
                            "success_boundary": "Pointwise existence remains open.",
                        },
                    },
                ],
                "proposals": [
                    {
                        "case_id": "attack-case-" + "1" * 64,
                        "proposal_id": "route-proposal-" + "1" * 64,
                        "route_rule": first_rule,
                    },
                    {
                        "case_id": "attack-case-" + "2" * 64,
                        "proposal_id": "route-proposal-" + "2" * 64,
                        "route_rule": second_rule,
                    },
                ],
                "decisions": [],
                "rules": [],
                "disablements": [],
            }
            with patch.object(
                manager, "_validated_state", return_value=state
            ), patch.object(
                manager,
                "report",
                side_effect=AssertionError("concise report called forensic report"),
            ):
                concise = manager.recommendation_report(
                    host_task_scope_id=scope_id
                )
            self.assertEqual(concise["coverage_status"], "case-projection")
            self.assertFalse(concise["scope_complete"])
            self.assertEqual(len(concise["recommendations"]), 1)
            self.assertEqual(
                concise["recommendations"][0]["attack_type"],
                "quantifier_witness",
            )
            self.assertEqual(
                concise["recommendations"][0]["support_count"],
                2,
            )
            self.assertEqual(concise["omitted_pending_count"], 1)
            tampered = deepcopy(concise)
            tampered["recommendations"][0]["what_it_checks"] = (
                "Worker-controlled replacement text."
            )
            semantic = {
                key: value
                for key, value in tampered.items()
                if key != "report_sha256"
            }
            tampered["report_sha256"] = sha256_json(semantic)
            with self.assertRaisesRegex(ValueError, "item is invalid"):
                validate_attack_route_recommendation_report(tampered)

    def test_concise_report_omits_unreviewed_family_instead_of_leaking_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            manager = store.adverse_routes()
            unknown_rule = self._main_rule(
                term="opaque",
                instruction="SECRET TECHNICAL ATTACK MECHANISM",
            )
            unknown_rule["attack_family"] = "unreviewed_future_family"
            scope_id = "hosttask-" + "b" * 32
            state = {
                "cases": [
                    {
                        "case_id": "attack-case-" + "3" * 64,
                        "host_task_scope_id": scope_id,
                        "attack_result": "productive_challenge",
                        "attack_learning": {
                            "attack_family": "unreviewed_future_family",
                            "failure_mechanism": "SECRET TECHNICAL ATTACK MECHANISM",
                            "success_boundary": "Opaque boundary.",
                        },
                    }
                ],
                "proposals": [
                    {
                        "case_id": "attack-case-" + "3" * 64,
                        "proposal_id": "route-proposal-" + "3" * 64,
                        "route_rule": unknown_rule,
                    }
                ],
                "decisions": [],
                "rules": [],
                "disablements": [],
            }
            with patch.object(
                manager, "_validated_state", return_value=state
            ), patch.object(
                manager,
                "report",
                side_effect=AssertionError("concise report called forensic report"),
            ):
                concise = manager.recommendation_report(
                    host_task_scope_id=scope_id
                )
            self.assertEqual(concise["recommendations"], [])
            self.assertEqual(concise["pending_proposal_count"], 1)
            self.assertEqual(concise["omitted_pending_count"], 1)
            self.assertNotIn(
                "SECRET TECHNICAL ATTACK MECHANISM",
                json.dumps(concise, ensure_ascii=False),
            )

    def test_schema_three_frozen_baseline_remains_valid_without_backfill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            research, assignment = self._counterexample_round(store=store)
            card = json.loads(
                Path(str(assignment["task_card_path"])).read_text(encoding="utf-8")
            )
            frozen = deepcopy(card["adverse_routing"])
            frozen["schema_version"] = 3
            frozen["contract_revision"] = "chalxius-adverse-routing-evolution-2"
            frozen["selection_policy"] = "baseline_plus_user_approved_future_only"
            frozen["baseline_rules"] = list(LEGACY_BASELINE_ATTACK_RULES)
            frozen["baseline_rules_sha256"] = sha256_json(
                frozen["baseline_rules"]
            )
            frozen["learning_contract"] = {
                "counterexample_requires_attack_learning": True,
                "productive_challenge_learning": (
                    "structured_when_attack_forces_a_load_bearing_repair"
                ),
                "attack_learning_schema_version": 2,
                "reportable_result_kinds": [
                    "productive_challenge",
                    "surviving_counterexample",
                ],
                "proposal_activation": "user_decision_only",
                "attack_report": "required_at_host_task_completion",
                "truth_effect": "none",
            }
            for key in (
                "philosophy_active",
                "philosophy_activation",
                "domain_profile",
                "domain_source",
            ):
                frozen["scope_evidence"].pop(key)
            store.adverse_routes().validate_task_card_binding(
                frozen,
                work_mode="refute",
                related_artifacts=[],
                entry=research,
            )

    def test_extension_return_requires_exact_attack_learning_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            store.adverse_routes().initialize(actor="operator", reason="Enable learning.")
            _, assignment = self._counterexample_round(store=store)
            final_sha = self._write_return(
                store=store,
                assignment=assignment,
                outcome="counterexample",
                attack_learning=None,
                extended=True,
            )
            receipt = store.v5_lifecycle().ingest_return(
                round_id=str(assignment["round_id"]),
                assignment_id=str(assignment["assignment_id"]),
                worker_final_sha256=final_sha,
            )
            self.assertEqual(receipt["status"], "quarantined")
            self.assertIn("attack_learning must be an object", receipt["error"])
            self.assertEqual(store.adverse_routes().status()["case_count"], 0)

    def test_productive_challenge_creates_a_pending_rule_suggestion_without_refutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            _, assignment = self._counterexample_round(store=store)
            final_sha = self._write_return(
                store=store,
                assignment=assignment,
                outcome="evidence",
                attack_learning=self._learning(
                    result_kind="productive_challenge",
                    effect_kind="hypothesis_added",
                ),
                extended=True,
            )
            receipt = store.v5_lifecycle().ingest_return(
                round_id=str(assignment["round_id"]),
                assignment_id=str(assignment["assignment_id"]),
                worker_final_sha256=final_sha,
            )
            self.assertEqual(
                receipt["attack_evidence_status"],
                "worker_reported_productive_challenge_nontruth",
            )
            report = store.adverse_routes().report(
                host_task_scope_id="host-adverse-task"
            )
            self.assertEqual(report["summary"]["productive_challenge_count"], 1)
            self.assertEqual(report["summary"]["surviving_counterexample_count"], 0)
            self.assertEqual(report["attacks"][0]["attack_result"], "productive_challenge")
            self.assertEqual(report["attacks"][0]["proposal_status"], "pending_main_synthesis")
            self.assertEqual(store.adverse_routes().status()["active_rule_count"], 0)

    def test_state_rejects_tampered_or_incomplete_immutable_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            store.adverse_routes().initialize(actor="operator", reason="Enable learning.")
            _, receipt = self._capture_one(store)
            proposal_id = str(receipt["route_proposal_id"])
            proposal_path = store.adverse_routes().proposals_dir / f"{proposal_id}.json"
            proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
            proposal["proposal_status"] = "silently_activated"
            proposal_path.write_text(
                json.dumps(proposal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "semantic hash mismatch"):
                store.adverse_routes().status()

        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            store.adverse_routes().initialize(actor="operator", reason="Enable learning.")
            _, receipt = self._capture_one(store)
            proposal_id = str(receipt["route_proposal_id"])
            (store.adverse_routes().proposals_dir / f"{proposal_id}.json").unlink()
            with self.assertRaisesRegex(
                ValueError, "attack case is missing its immutable route proposal"
            ):
                store.adverse_routes().status()

        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            store.adverse_routes().initialize(actor="operator", reason="Enable learning.")
            _, receipt = self._capture_one(store)
            decision = store.adverse_routes().decide(
                str(receipt["route_proposal_id"]),
                {
                    "action": "approve_modified",
                    "reason": "Retain this reusable guarded pattern.",
                    "rule": self._main_rule(),
                    "governance": {
                        "abstraction_level": "mechanism",
                        "concrete_evidence_excluded": True,
                        "compression": "within_budget",
                    },
                },
                actor="main",
            )
            rule_id = str(decision["rule_id"])
            (store.adverse_routes().rules_dir / f"{rule_id}.json").unlink()
            with self.assertRaisesRegex(
                ValueError, "approved route decision is missing its immutable route rule"
            ):
                store.adverse_routes().status()

    def test_main_synthesis_changes_only_future_matching_task_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            store.adverse_routes().initialize(actor="operator", reason="Enable learning.")
            first_assignment, receipt = self._capture_one(store)
            proposal_id = str(receipt["route_proposal_id"])
            decision = store.adverse_routes().decide(
                proposal_id,
                {
                    "action": "approve_modified",
                    "reason": "The pattern is reusable with its guard.",
                    "rule": self._main_rule(),
                    "governance": {
                        "abstraction_level": "mechanism",
                        "concrete_evidence_excluded": True,
                        "compression": "within_budget",
                    },
                },
                actor="main",
            )
            self.assertIsNotNone(decision["rule_id"])

            old_card = json.loads(
                Path(str(first_assignment["task_card_path"])).read_text(encoding="utf-8")
            )
            self.assertEqual(old_card["adverse_routing"]["approved_rules"], [])
            store.v5_lifecycle().validate_task_card(
                old_card, expected_path=Path(str(first_assignment["task_card_path"]))
            )

            _, matching = self._counterexample_round(
                store=store,
                host_scope="future-host-task",
                claim="Stress-test another uniform witness claim.",
            )
            matching_card = json.loads(
                Path(str(matching["task_card_path"])).read_text(encoding="utf-8")
            )
            approved = matching_card["adverse_routing"]["approved_rules"]
            self.assertEqual([item["rule_id"] for item in approved], [decision["rule_id"]])

            _, nonmatching = self._counterexample_round(
                store=store,
                host_scope="nonmatching-host-task",
                claim="Stress-test a finite combinatorial claim.",
            )
            nonmatching_card = json.loads(
                Path(str(nonmatching["task_card_path"])).read_text(encoding="utf-8")
            )
            self.assertEqual(nonmatching_card["adverse_routing"]["approved_rules"], [])

    def test_main_synthesis_and_disablement_are_future_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            store.adverse_routes().initialize(actor="operator", reason="Enable learning.")
            _, receipt = self._capture_one(store)
            modified = self._main_rule(
                term="canonical", instruction="Attack a canonical-witness upgrade."
            )
            decision = store.adverse_routes().decide(
                str(receipt["route_proposal_id"]),
                {
                    "action": "approve_modified",
                    "reason": "Narrow the trigger before activation.",
                    "rule": modified,
                    "governance": {
                        "abstraction_level": "mechanism",
                        "concrete_evidence_excluded": True,
                        "compression": "compressed",
                    },
                },
                actor="main",
            )
            rule_id = str(decision["rule_id"])
            _, before_disable = self._counterexample_round(
                store=store,
                host_scope="before-disable",
                claim="Challenge the canonical witness conclusion.",
            )
            before_card = json.loads(
                Path(str(before_disable["task_card_path"])).read_text(encoding="utf-8")
            )
            self.assertEqual(
                [item["rule_id"] for item in before_card["adverse_routing"]["approved_rules"]],
                [rule_id],
            )

            store.adverse_routes().disable(
                rule_id,
                reason="User observed an overly broad route.",
                actor="user",
            )
            store.v5_lifecycle().validate_task_card(
                before_card, expected_path=Path(str(before_disable["task_card_path"]))
            )
            _, after_disable = self._counterexample_round(
                store=store,
                host_scope="after-disable",
                claim="Challenge another canonical witness conclusion.",
            )
            after_card = json.loads(
                Path(str(after_disable["task_card_path"])).read_text(encoding="utf-8")
            )
            self.assertEqual(after_card["adverse_routing"]["approved_rules"], [])

    def test_reject_keeps_route_unchanged_and_zero_report_is_still_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            store.adverse_routes().initialize(actor="operator", reason="Enable learning.")
            zero = store.adverse_routes().report(host_task_scope_id="empty-host-task")
            self.assertEqual(zero["attacks"], [])
            self.assertFalse(zero["user_decision_required"])

            _, receipt = self._capture_one(store)
            store.adverse_routes().decide(
                str(receipt["route_proposal_id"]),
                {
                    "action": "reject",
                    "reason": "The case is too task-specific.",
                    "rule": None,
                    "governance": None,
                },
                actor="main",
            )
            self.assertEqual(store.adverse_routes().status()["active_rule_count"], 0)
            report = store.adverse_routes().report(
                host_task_scope_id="host-adverse-task"
            )
            self.assertEqual(report["attacks"][0]["proposal_status"], "reject")

    def test_main_alone_decides_routes(self) -> None:
        self.assertIn("attack-route-status", allowed_commands("main"))
        self.assertIn("attack-report", allowed_commands("main"))
        for command in ("attack-route-enable", "attack-route-disable"):
            self.assertIn(command, allowed_commands("operator"))
            self.assertNotIn(command, allowed_commands("main"))
            self.assertNotIn(command, allowed_commands("worker"))
            self.assertNotIn(command, allowed_commands("gateway"))
        self.assertIn("attack-route-decide", allowed_commands("main"))
        self.assertNotIn("attack-route-decide", allowed_commands("operator"))

    def test_worker_report_has_no_route_rule_and_main_rule_is_hard_capped(self) -> None:
        report = self._learning()
        self.assertNotIn("route_rule", report)
        self.assertEqual(MAX_ACTIVE_ROUTE_RULES, 16)
        self.assertEqual(MAX_SELECTED_RULES, 16)

        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            store.adverse_routes().initialize(actor="operator", reason="Enable learning.")
            _, receipt = self._capture_one(store)
            oversized = self._main_rule(
                instruction="x" * 281,
            )
            with self.assertRaisesRegex(ValueError, "compress"):
                store.adverse_routes().decide(
                    str(receipt["route_proposal_id"]),
                    {
                        "action": "approve_modified",
                        "reason": "Reject an oversized persistent route.",
                        "rule": oversized,
                        "governance": {
                            "abstraction_level": "mechanism",
                            "concrete_evidence_excluded": True,
                            "compression": "compressed",
                        },
                    },
                    actor="main",
                )

    def test_current_internal_governance_prose_must_be_english(self) -> None:
        report = self._learning()
        report["failure_mechanism"] = "non-English " + "\u8fb9\u754c"
        with self.assertRaisesRegex(ValueError, "English internal prose"):
            validate_attack_learning(report, require_current=True)

        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            store.adverse_routes().initialize(
                actor="operator", reason="Enable reporting."
            )
            _, receipt = self._capture_one(store)
            rule = self._main_rule(
                instruction="Attack recursive " + "\u8fb9\u754c" + " conditions."
            )
            with self.assertRaisesRegex(ValueError, "English internal prose"):
                store.adverse_routes().decide(
                    str(receipt["route_proposal_id"]),
                    {
                        "action": "approve_modified",
                        "reason": "Reject non-English internal prose.",
                        "rule": rule,
                        "governance": {
                            "abstraction_level": "mechanism",
                            "concrete_evidence_excluded": True,
                            "compression": "within_budget",
                        },
                    },
                    actor="main",
                )

    def test_cli_keeps_mutation_operator_only_and_report_readable_by_main(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            self._store(root)

            denied_out = StringIO()
            denied_err = StringIO()
            with redirect_stdout(denied_out), redirect_stderr(denied_err):
                denied = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "main",
                        "attack-route-enable",
                        "--actor",
                        "main",
                        "--reason",
                        "Must be denied.",
                    ]
                )
            self.assertEqual(denied, 3)
            self.assertIn("not allowed", denied_err.getvalue())

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                enabled = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "operator",
                        "attack-route-enable",
                        "--actor",
                        "user",
                        "--reason",
                        "Explicit user opt-in.",
                    ]
                )
            self.assertEqual(enabled, 0)

            report_out = StringIO()
            with redirect_stdout(report_out), redirect_stderr(StringIO()):
                reported = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "main",
                        "attack-report",
                        "--host-task-scope-id",
                        "empty-cli-task",
                    ]
                )
            self.assertEqual(reported, 0)
            report = json.loads(report_out.getvalue())
            self.assertEqual(report["recommendations"], [])
            self.assertNotIn("attacks", report)
            self.assertEqual(report["project_effect"], "report_only")


if __name__ == "__main__":
    unittest.main()
