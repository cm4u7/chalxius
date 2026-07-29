from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from mathgraph.cli import main as cli_main
from mathgraph.contracts import sha256_bytes
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
    def _learning(*, term: str = "uniform", instruction: str = "Attack silent witness replacement.") -> dict[str, object]:
        return {
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
            "route_rule": {
                "attack_family": "quantifier_witness",
                "trigger": {
                    "research_kinds": ["challenge"],
                    "claim_terms_any": [term],
                    "metadata_signals_any": ["quantifier_sensitive"],
                    "universal_refute": False,
                },
                "instruction": instruction,
                "false_positive_guards": [
                    "Do not demand one witness when the literal conclusion is pointwise."
                ],
                "scope_note": "Use when witness identity or uniformity is load-bearing.",
            },
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
    ) -> tuple[dict[str, object], dict[str, object]]:
        research = store.v5_lifecycle().add_research(
            {
                "kind": "challenge",
                "claim": claim,
                "logic_signals": ["quantifier_sensitive"],
            },
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

    def test_default_is_disabled_and_legacy_frozen_round_survives_later_enable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            self.assertFalse(store.adverse_routes().status()["enabled"])
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
            self.assertEqual(len(card["adverse_routing"]["baseline_rules"]), 8)
            self.assertEqual(card["adverse_routing"]["approved_rules"], [])

            report = store.adverse_routes().report(
                host_task_scope_id="host-adverse-task"
            )
            self.assertEqual(report["summary"]["worker_reported_success_count"], 1)
            self.assertEqual(report["summary"]["pending_user_decision_count"], 1)
            self.assertTrue(report["user_decision_required"])
            self.assertEqual(
                report["routing_change_policy"],
                "no_route_change_without_operator_decision",
            )
            self.assertEqual(report["truth_effect"], "none")
            self.assertNotIn("chx", json.dumps(report).casefold())

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
            self.assertIn("attack_learning fields are not exact", receipt["error"])
            self.assertEqual(store.adverse_routes().status()["case_count"], 0)

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
                    "action": "approve",
                    "reason": "Retain this reusable guarded pattern.",
                    "rule": None,
                },
                actor="user",
            )
            rule_id = str(decision["rule_id"])
            (store.adverse_routes().rules_dir / f"{rule_id}.json").unlink()
            with self.assertRaisesRegex(
                ValueError, "approved route decision is missing its immutable route rule"
            ):
                store.adverse_routes().status()

    def test_user_approval_changes_only_future_matching_task_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            store.adverse_routes().initialize(actor="operator", reason="Enable learning.")
            first_assignment, receipt = self._capture_one(store)
            proposal_id = str(receipt["route_proposal_id"])
            decision = store.adverse_routes().decide(
                proposal_id,
                {
                    "action": "approve",
                    "reason": "The pattern is reusable with its guard.",
                    "rule": None,
                },
                actor="user",
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

    def test_modified_approval_and_disablement_are_user_governed_and_future_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            store.adverse_routes().initialize(actor="operator", reason="Enable learning.")
            _, receipt = self._capture_one(store)
            modified = self._learning(
                term="canonical", instruction="Attack a canonical-witness upgrade."
            )["route_rule"]
            decision = store.adverse_routes().decide(
                str(receipt["route_proposal_id"]),
                {
                    "action": "approve_modified",
                    "reason": "Narrow the trigger before activation.",
                    "rule": modified,
                },
                actor="user",
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
                },
                actor="user",
            )
            self.assertEqual(store.adverse_routes().status()["active_rule_count"], 0)
            report = store.adverse_routes().report(
                host_task_scope_id="host-adverse-task"
            )
            self.assertEqual(report["attacks"][0]["proposal_status"], "reject")

    def test_only_operator_can_enable_decide_or_disable_routes(self) -> None:
        self.assertIn("attack-route-status", allowed_commands("main"))
        self.assertIn("attack-report", allowed_commands("main"))
        for command in (
            "attack-route-enable",
            "attack-route-decide",
            "attack-route-disable",
        ):
            self.assertIn(command, allowed_commands("operator"))
            self.assertNotIn(command, allowed_commands("main"))
            self.assertNotIn(command, allowed_commands("worker"))
            self.assertNotIn(command, allowed_commands("gateway"))

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
            self.assertEqual(report["attacks"], [])
            self.assertEqual(report["project_effect"], "report_only")


if __name__ == "__main__":
    unittest.main()
