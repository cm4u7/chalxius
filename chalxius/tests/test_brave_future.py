from __future__ import annotations

import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from mathgraph.brave_future import (
    BF_BLOCKAGE_REVISION,
    BF_DECISION_REVISION,
    BF_REPAIR_CONTRACT_REVISION,
    _FIXED_POLICY,
)
from mathgraph.contracts import sha256_json
from mathgraph.roles import allowed_commands
from mathgraph.store import MathGraphStore
from mathgraph.v5_assurance import V5_ASSURANCE_CONTRACT_REVISION


class BraveFutureTests(unittest.TestCase):
    @staticmethod
    def _store(root: Path, project_id: str = "bf-fixture") -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id=project_id,
            title="Brave Future fixture",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _campaign(store: MathGraphStore, name: str = "BF") -> str:
        with store.v5_mutation_lock(command="bf-test-campaign"):
            return store.campaigns().create(
                {
                    "name": name,
                    "objective": "Exercise bounded advisory recovery.",
                    "source_claim_ids": [],
                    "targets": [],
                    "constraints": ["No truth effect."],
                    "stop_conditions": ["Return to Operator review."],
                    "value_definition": "Prefer exact reusable information.",
                },
                actor="operator",
                fact_exists=lambda _fact_id: False,
            )

    @staticmethod
    def _policy(campaign_id: str) -> dict[str, object]:
        return {**_FIXED_POLICY, "campaign_id": campaign_id}

    @staticmethod
    def _research(
        store: MathGraphStore,
        campaign_id: str,
        claim: str,
        *,
        kind: str = "direction",
        **metadata: object,
    ) -> dict[str, object]:
        return store.v5_lifecycle().add_research(
            {
                "kind": kind,
                "claim": claim,
                "campaign_id": campaign_id,
                "artifacts": [],
                "source_dependent": False,
                **metadata,
            },
            actor="main",
            assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
        )

    @staticmethod
    def _inventory(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*")
            if path.is_file()
        }

    def _ingested_attempt(
        self,
        store: MathGraphStore,
        campaign_id: str,
        source_research_id: str,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        lifecycle = store.v5_lifecycle()
        round_status = lifecycle.create_round(
            workers=1,
            research_ids=[source_research_id],
            campaign_id=campaign_id,
        )
        assignment = round_status["assignments"][0]
        card = json.loads(
            Path(assignment["task_card_path"]).read_text(encoding="utf-8")
        )
        payload: dict[str, object] = {
            "schema_version": 5,
            "project_id": store.project_id(),
            "round_id": round_status["round_id"],
            "assignment_id": assignment["assignment_id"],
            "worker_id": assignment["worker_id"],
            "task_card_sha256": assignment["task_card_sha256"],
            "blackboard_snapshot_sha256": assignment[
                "blackboard_snapshot_sha256"
            ],
            "outcome": "insight",
            "claim": "The direct method is exhausted on the remaining case.",
            "content": "A local obstruction survives and a sibling route remains available.",
            "narrative": {
                "rationale": "Repeating the same method would add no information.",
                "summary": "One exact route blockage.",
                "intuition": "Change route instead of extending the failed branch.",
                "limitations": "One explicit obligation remains open.",
            },
            "artifacts": [],
        }
        if "assurance_contract" in card:
            payload.update(
                {
                    "obligation_dispositions": [],
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
        if "adverse_routing" in card:
            payload["attack_learning"] = None
        return_path = Path(assignment["return_path"])
        return_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        receipt = lifecycle.ingest_return(
            round_id=round_status["round_id"],
            assignment_id=assignment["assignment_id"],
            worker_final_sha256=hashlib.sha256(return_path.read_bytes()).hexdigest(),
        )
        result = lifecycle._research_record(receipt["research_id"])
        self.assertEqual(result["metadata"]["campaign_id"], campaign_id)
        return round_status, assignment, receipt

    @staticmethod
    def _blockage(
        *,
        campaign_id: str,
        planning_snapshot_id: str,
        target_research_id: str,
        round_status: dict[str, object],
        assignment: dict[str, object],
        result_research_id: str,
    ) -> dict[str, object]:
        return {
            "revision": BF_BLOCKAGE_REVISION,
            "campaign_id": campaign_id,
            "target_research_id": target_research_id,
            "blocked_route_research_ids": [target_research_id],
            "blocker_class": "method_exhaustion",
            "method_family": "direct_proof",
            "method_descriptor_sha256": sha256_json({"method": "direct_proof"}),
            "attempts": [
                {
                    "round_id": round_status["round_id"],
                    "assignment_id": assignment["assignment_id"],
                    "task_card_sha256": assignment["task_card_sha256"],
                    "result_research_ids": [result_research_id],
                    "result": "method_exhausted",
                }
            ],
            "information_gained_research_ids": [result_research_id],
            "remaining_obligation_keys": ["O-REMAINING"],
            "mechanical_extension_failure": (
                "The same direct method cannot distinguish the remaining cases."
            ),
            "operator_constraints": [],
            "planning_snapshot_id": planning_snapshot_id,
            "created_by": "main",
            "truth_effect": "none",
            "fact_admission_effect": "none",
        }

    def test_absent_or_disabled_sidecar_preserves_legacy_frontier_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store)
            self._research(store, campaign_id, "Keep the stable route visible.")
            lifecycle = store.v5_lifecycle()
            before_frontier = lifecycle.frontier(
                campaign_id=campaign_id, include_history=True, limit=20
            )
            before_inventory = self._inventory(store.root)
            manager = store.brave_future()
            self.assertFalse(manager.status(campaign_id)["enabled"])
            self.assertEqual(before_inventory, self._inventory(store.root))
            self.assertFalse((store.root / "governance" / "brave-future").exists())
            with self.assertRaisesRegex(ValueError, "disabled"):
                manager.frontier(campaign_id=campaign_id)

            manager.enable(
                campaign_id=campaign_id,
                policy=self._policy(campaign_id),
                actor="operator",
            )
            self.assertEqual(
                before_frontier,
                lifecycle.frontier(
                    campaign_id=campaign_id, include_history=True, limit=20
                ),
            )
            self.assertFalse(
                (store.root / "governance" / "brave-future" / "ACTIVE").exists()
            )
            manager.disable(
                campaign_id=campaign_id,
                actor="operator",
                reason="Return to stable planning.",
            )
            self.assertEqual(
                before_frontier,
                lifecycle.frontier(
                    campaign_id=campaign_id, include_history=True, limit=20
                ),
            )

    def test_policy_and_role_boundaries_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store)
            manager = store.brave_future()
            bad_policy = self._policy(campaign_id)
            bad_policy["autonomy_level"] = "plan_one"
            with self.assertRaisesRegex(ValueError, "advisory"):
                manager.enable(
                    campaign_id=campaign_id,
                    policy=bad_policy,
                    actor="operator",
                )
            self.assertIn("campaign-reassess", allowed_commands("main"))
            self.assertIn("brave-future-status", allowed_commands("main"))
            self.assertNotIn("brave-future-enable", allowed_commands("main"))
            self.assertNotIn("campaign-reassess-decide", allowed_commands("main"))
            for role in ("worker", "host", "gateway", "paper-auditor"):
                self.assertNotIn("campaign-reassess", allowed_commands(role))
                self.assertNotIn("brave-future-enable", allowed_commands(role))

    def test_l4_collapses_only_complete_typed_repair_and_preserves_invalidator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store)
            root = self._research(
                store,
                campaign_id,
                "Repair the root route.",
                obligations=[{"obligation_id": "O-SCOPE"}],
            )
            legacy = self._research(
                store,
                campaign_id,
                "A legacy repair note.",
                kind="repair",
                relation="repairs",
                related_research_ids=[root["research_id"]],
                repair_of_research_id=root["research_id"],
            )
            strict = self._research(
                store,
                campaign_id,
                "A typed complete replacement.",
                kind="repair",
                relation="repairs",
                related_research_ids=[root["research_id"]],
                brave_future_repair_contract={
                    "repair_contract_revision": BF_REPAIR_CONTRACT_REVISION,
                    "strategy": "replacement",
                    "predecessor_research_ids": [root["research_id"]],
                    "method_family": "local_model",
                    "method_descriptor_sha256": sha256_json(
                        {"method": "local_model"}
                    ),
                    "coverage": [
                        {
                            "predecessor_research_id": root["research_id"],
                            "obligation_key": "O-SCOPE",
                            "outcome": "preserved",
                            "supporting_research_ids": [],
                        }
                    ],
                    "residual_obligations": [],
                    "inherited_invalidator_ids": [],
                    "disposed_invalidator_ids": [],
                    "source_capability_hashes": [],
                    "created_under_snapshot_id": None,
                },
            )
            manager = store.brave_future()
            manager.enable(
                campaign_id=campaign_id,
                policy=self._policy(campaign_id),
                actor="operator",
            )
            projection = manager.frontier(campaign_id=campaign_id)[
                "frontier_projection"
            ]
            self.assertEqual(
                projection["collapse_map"][root["research_id"]],
                [strict["research_id"]],
            )
            self.assertIn(legacy["research_id"], projection["failed_repairs"])
            self.assertNotIn(
                root["research_id"],
                {item["research_id"] for item in projection["entries"]},
            )

            challenge = self._research(
                store,
                campaign_id,
                "A surviving counterexample invalidates the old root.",
                kind="challenge",
                relation="challenges",
                related_research_ids=[root["research_id"]],
                route_invalidations=[root["research_id"]],
            )
            projection = manager.frontier(campaign_id=campaign_id)[
                "frontier_projection"
            ]
            self.assertNotIn(root["research_id"], projection["collapse_map"])
            reasons = projection["residual_surface"][root["research_id"]]
            self.assertTrue(any(challenge["research_id"] in item for item in reasons))
            self.assertIn(
                root["research_id"],
                {item["research_id"] for item in projection["entries"]},
            )

    def test_real_attempt_dry_run_atomic_advisory_and_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store)
            root = self._research(store, campaign_id, "The direct route may fail.")
            sibling = self._research(
                store,
                campaign_id,
                "Use the already recorded sibling source route.",
                kind="literature",
                relation="supports",
                related_research_ids=[root["research_id"]],
            )
            round_status, assignment, receipt = self._ingested_attempt(
                store, campaign_id, root["research_id"]
            )
            manager = store.brave_future()
            manager.enable(
                campaign_id=campaign_id,
                policy=self._policy(campaign_id),
                actor="operator",
            )
            frontier = manager.frontier(campaign_id=campaign_id)
            blockage = self._blockage(
                campaign_id=campaign_id,
                planning_snapshot_id=frontier["planning_snapshot"][
                    "planning_snapshot_id"
                ],
                target_research_id=root["research_id"],
                round_status=round_status,
                assignment=assignment,
                result_research_id=receipt["research_id"],
            )
            before = self._inventory(store.root)
            research_count = len(store.v5_lifecycle().research_records())
            round_paths = sorted(store.rounds_dir.iterdir())
            facts = store.fact_ids()
            dry = manager.reassess(
                campaign_id=campaign_id,
                blockage_input=blockage,
                dry_run=True,
            )
            self.assertEqual(before, self._inventory(store.root))
            self.assertEqual(dry["reassessment"]["plan_effect"], "none")
            self.assertEqual(dry["reassessment"]["dispatch_effect"], "none")
            self.assertEqual(dry["reassessment"]["recommended_action"], "switch_sibling_route")
            self.assertIn(
                sibling["research_id"],
                {item["research_id"] for item in dry["reassessment"]["shortlist"]},
            )

            persisted = manager.reassess(
                campaign_id=campaign_id,
                blockage_input=blockage,
                dry_run=False,
            )
            self.assertEqual(persisted["write_effect"], "one_atomic_sidecar_transaction")
            self.assertEqual(persisted["plan_effect"], "none")
            self.assertEqual(persisted["dispatch_effect"], "none")
            self.assertEqual(len(store.v5_lifecycle().research_records()), research_count)
            self.assertEqual(sorted(store.rounds_dir.iterdir()), round_paths)
            self.assertEqual(store.fact_ids(), facts)
            after_persist = self._inventory(store.root)
            repeated = manager.reassess(
                campaign_id=campaign_id,
                blockage_input=blockage,
                dry_run=False,
            )
            self.assertTrue(repeated["parked"])
            self.assertEqual(repeated["write_effect"], "none")
            self.assertEqual(after_persist, self._inventory(store.root))
            self.assertEqual(manager.status(campaign_id)["reassessment_count"], 1)

            decision = manager.decide(
                persisted["reassessment_id"],
                decision={
                    "revision": BF_DECISION_REVISION,
                    "action": "select",
                    "selected_research_ids": [sibling["research_id"]],
                    "modified_proposal": None,
                    "reason": "Retain this route for a later explicit planning decision.",
                },
                actor="operator",
            )
            self.assertEqual(decision["plan_effect"], "none")
            self.assertEqual(decision["dispatch_effect"], "none")
            self.assertEqual(sorted(store.rounds_dir.iterdir()), round_paths)
            self.assertTrue(manager.audit()["ok"])

    def test_corrupt_sidecar_fails_bf_audit_without_changing_fact_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store)
            root = self._research(store, campaign_id, "Blocked route.")
            self._research(
                store,
                campaign_id,
                "Sibling route.",
                relation="supports",
                related_research_ids=[root["research_id"]],
            )
            round_status, assignment, receipt = self._ingested_attempt(
                store, campaign_id, root["research_id"]
            )
            manager = store.brave_future()
            manager.enable(
                campaign_id=campaign_id,
                policy=self._policy(campaign_id),
                actor="operator",
            )
            frontier = manager.frontier(campaign_id=campaign_id)
            blockage = self._blockage(
                campaign_id=campaign_id,
                planning_snapshot_id=frontier["planning_snapshot"][
                    "planning_snapshot_id"
                ],
                target_research_id=root["research_id"],
                round_status=round_status,
                assignment=assignment,
                result_research_id=receipt["research_id"],
            )
            persisted = manager.reassess(
                campaign_id=campaign_id,
                blockage_input=blockage,
                dry_run=False,
            )
            fact_audit_before = store.v5_lifecycle().fact_evidence_audit()
            stable_audit_before = store.audit().as_dict()
            transaction = store.root / persisted["transaction_relpath"]
            reassessment_path = transaction / "reassessment.json"
            corrupted = json.loads(reassessment_path.read_text(encoding="utf-8"))
            corrupted["plan_effect"] = "plan_one"
            reassessment_path.write_text(
                json.dumps(corrupted, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(manager.audit()["ok"])
            self.assertEqual(
                fact_audit_before, store.v5_lifecycle().fact_evidence_audit()
            )
            stable_audit_after = store.audit().as_dict()
            self.assertEqual(
                stable_audit_before["current_ok"], stable_audit_after["current_ok"]
            )
            self.assertEqual(
                stable_audit_before["facts"], stable_audit_after["facts"]
            )

    def test_blackboard_preview_is_zero_write_and_matches_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            board = store.blackboard()
            space_id = next(iter(board.current_nodes()))
            query = {
                "seed_node_ids": [space_id],
                "direction": "both",
                "max_hops": 1,
                "edge_type_allowlist": ["*"],
                "node_type_allowlist": ["*"],
                "node_budget": 16,
                "edge_budget": 16,
            }
            before = self._inventory(store.root)
            preview = board.preview_snapshot(query=query)
            self.assertEqual(before, self._inventory(store.root))
            with store.v5_mutation_lock(command="bf-test-blackboard-publish"):
                published = board.snapshot(query=query, actor="main")
            self.assertEqual(preview["snapshot_id"], published["snapshot_id"])
            self.assertEqual(preview["snapshot_sha256"], published["snapshot_sha256"])

    def test_module_has_no_planning_dispatch_truth_or_active_pointer_call_seam(self) -> None:
        """Keep the advisory sidecar mechanically outside every authority path."""

        source_path = Path(__file__).resolve().parents[1] / "scripts" / "mathgraph" / "brave_future.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        forbidden_calls = {
            "active",
            "create_round",
            "create_repair_round",
            "plan_round",
            "dispatch",
            "pulse_dispatch",
            "candidate_release",
            "certification_record",
            "fact_admit",
            "admit",
        }
        observed = sorted(
            {
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else node.func.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and (
                    isinstance(node.func, ast.Attribute)
                    or isinstance(node.func, ast.Name)
                )
                and (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                )
                in forbidden_calls
            }
        )
        self.assertEqual(observed, [])


if __name__ == "__main__":
    unittest.main()
