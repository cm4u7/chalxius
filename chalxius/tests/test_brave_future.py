from __future__ import annotations

import ast
import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from mathgraph.brave_future import (
    BF_BLOCKAGE_REVISION,
    BF_DECISION_REVISION,
    BF_GOAL_INTAKE_REVISION,
    BF_PLANNING_SNAPSHOT_LEGACY_REVISION,
    BF_PLANNING_SNAPSHOT_REVISION,
    BF_REPAIR_CONTRACT_REVISION,
    _SNAPSHOT_SEMANTIC_FIELDS,
    _FIXED_POLICY,
    _sealed_record,
    _validate_planning_snapshot,
)
from mathgraph.contracts import sha256_json
from mathgraph.cli import build_parser, main as cli_main
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

    def test_planning_snapshot_v2_writer_and_exact_v1_reader(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store)
            self._research(store, campaign_id, "Keep one exact planning route.")
            manager = store.brave_future()
            manager.enable(
                campaign_id=campaign_id,
                policy=self._policy(campaign_id),
                actor="operator",
            )
            policy_status = manager.policy_store.status(campaign_id)

            current = manager.snapshot_builder.preview(
                campaign_id=campaign_id,
                policy_status=policy_status,
            )
            self.assertEqual(current["revision"], BF_PLANNING_SNAPSHOT_REVISION)
            self.assertIsInstance(current["research_manifest"], dict)
            self.assertTrue(manager.snapshot_builder.revalidate(current, policy_status))

            legacy = manager.snapshot_builder.preview(
                campaign_id=campaign_id,
                policy_status=policy_status,
                revision=BF_PLANNING_SNAPSHOT_LEGACY_REVISION,
            )
            self.assertEqual(
                legacy["revision"], BF_PLANNING_SNAPSHOT_LEGACY_REVISION
            )
            for key in (
                "research_manifest",
                "disposition_heads",
                "repair_lineage_manifest",
                "program_math_projection",
            ):
                self.assertIsInstance(legacy[key], list)
            self.assertEqual(_validate_planning_snapshot(legacy), legacy)
            self.assertTrue(manager.snapshot_builder.revalidate(legacy, policy_status))

            mixed_semantic = {
                key: legacy[key] for key in _SNAPSHOT_SEMANTIC_FIELDS
            }
            mixed_semantic["research_manifest"] = current["research_manifest"]
            mixed = _sealed_record(
                mixed_semantic,
                id_key="planning_snapshot_id",
                prefix="bfps-",
                created_at=legacy["created_at"],
            )
            with self.assertRaisesRegex(ValueError, "exact list"):
                _validate_planning_snapshot(mixed)

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
            self.assertIn("research-goal-intake", allowed_commands("operator"))
            self.assertNotIn("research-goal-intake", allowed_commands("main"))
            self.assertNotIn("brave-future-enable", allowed_commands("main"))
            self.assertNotIn("campaign-reassess-decide", allowed_commands("main"))
            for role in ("worker", "host", "gateway", "paper-auditor"):
                self.assertNotIn("campaign-reassess", allowed_commands(role))
                self.assertNotIn("brave-future-enable", allowed_commands(role))

    def test_auto_goal_intake_creates_exact_campaign_enables_bf1_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            manager = store.brave_future()
            objective = "Strengthen the draft without changing its exact thesis."
            result = manager.intake_research_goal(
                goal_input={
                    "revision": BF_GOAL_INTAKE_REVISION,
                    "objective": objective,
                },
                actor="user",
            )
            self.assertTrue(result["campaign_created"])
            self.assertEqual(result["objective"], objective)
            self.assertEqual(
                result["campaign_resolution"], "created_from_exact_user_goal"
            )
            self.assertIsNone(store.campaigns().active())
            self.assertFalse(result["active_campaign_pointer_used"])
            self.assertFalse(result["fuzzy_objective_matching"])
            self.assertTrue(result["research_scope"]["bind_future_research"])
            self.assertFalse(
                result["research_scope"]["rebind_existing_untagged_research"]
            )
            self.assertTrue(
                manager.status(result["campaign_id"])["enabled"]
            )
            self.assertEqual(
                result["bf1"]["frontier_projection"]["entries"], []
            )
            self.assertEqual(
                result["bf2_bf3_state"],
                "awaiting_existing_exact_blockage_evidence_gate",
            )
            self.assertFalse(result["automatic_plan"])
            self.assertFalse(result["automatic_dispatch"])
            self.assertEqual(result["research_write_effect"], "none")
            self.assertEqual(store.fact_ids(), [])
            self.assertEqual(store.v5_lifecycle().research_records(), [])
            self.assertEqual(list(store.rounds_dir.iterdir()), [])

    def test_deep_goal_intake_creates_exact_campaign_enables_bf1_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = MathGraphStore(Path(temporary) / "project")
            store.initialize(
                project_id="bf-deep-goal",
                title="Deep goal fixture",
                workflow_evidence_version=5,
                reasoning_mode="deep",
            )
            result = store.brave_future().intake_research_goal(
                goal_input={
                    "revision": BF_GOAL_INTAKE_REVISION,
                    "objective": "Strengthen the inherited Paper Graph in deep mode.",
                },
                actor="user",
            )
            self.assertEqual(result["reasoning_mode"], "deep")
            self.assertEqual(
                result["trigger"], "explicit_user_research_goal_under_deep"
            )
            self.assertTrue(result["campaign_created"])
            self.assertTrue(result["research_scope"]["bind_future_research"])
            self.assertFalse(
                result["research_scope"]["rebind_existing_untagged_research"]
            )
            self.assertTrue(store.brave_future().status(result["campaign_id"])["enabled"])
            self.assertEqual(
                result["bf2_bf3_state"],
                "awaiting_existing_exact_blockage_evidence_gate",
            )
            self.assertFalse(result["automatic_plan"])
            self.assertFalse(result["automatic_dispatch"])
            self.assertEqual(result["research_write_effect"], "none")
            self.assertEqual(store.v5_lifecycle().research_records(), [])
            self.assertEqual(store.fact_ids(), [])
            self.assertEqual(list(store.rounds_dir.iterdir()), [])

    def test_auto_goal_intake_is_lexically_exact_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            manager = store.brave_future()
            first = manager.intake_research_goal(
                goal_input={
                    "revision": BF_GOAL_INTAKE_REVISION,
                    "objective": "Test Cafe\u0301   scope.",
                },
                actor="user",
            )
            second = manager.intake_research_goal(
                goal_input={
                    "revision": BF_GOAL_INTAKE_REVISION,
                    "objective": "  Test Caf\u00e9 scope.  ",
                },
                actor="user",
            )
            self.assertEqual(first["campaign_id"], second["campaign_id"])
            self.assertFalse(second["campaign_created"])
            self.assertEqual(
                second["campaign_resolution"], "exact_objective_reused"
            )
            self.assertTrue(second["brave_future_activation"]["idempotent"])
            distinct = manager.intake_research_goal(
                goal_input={
                    "revision": BF_GOAL_INTAKE_REVISION,
                    "objective": "Test Caf\u00e9",
                },
                actor="user",
            )
            self.assertNotEqual(first["campaign_id"], distinct["campaign_id"])
            self.assertEqual(len(store.campaigns().campaign_ids()), 2)
            self.assertEqual(manager.status(first["campaign_id"])["event_count"], 1)

    def test_goal_intake_ignores_active_pointer_and_exposes_future_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            unrelated = self._campaign(store, "Unrelated")
            with store.v5_mutation_lock(command="bf-goal-active-fixture"):
                store.campaigns().activate(unrelated, actor="operator")
            manager = store.brave_future()
            result = manager.intake_research_goal(
                goal_input={
                    "revision": BF_GOAL_INTAKE_REVISION,
                    "objective": "Investigate a distinct exact objective.",
                },
                actor="user",
            )
            self.assertNotEqual(result["campaign_id"], unrelated)
            self.assertEqual(store.campaigns().active(), unrelated)
            research = self._research(
                store,
                result["campaign_id"],
                "One branch bound by the returned internal scope.",
            )
            repeated = manager.intake_research_goal(
                goal_input={
                    "revision": BF_GOAL_INTAKE_REVISION,
                    "objective": "Investigate a distinct exact objective.",
                },
                actor="user",
            )
            self.assertEqual(
                [
                    item["research_id"]
                    for item in repeated["bf1"]["frontier_projection"]["entries"]
                ],
                [research["research_id"]],
            )

    def test_goal_intake_ambiguity_nonauto_and_disablement_fail_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            objective = "One duplicated exact objective."
            with store.v5_mutation_lock(command="bf-goal-duplicate-fixture"):
                for label in ("one", "two"):
                    store.campaigns().create(
                        {
                            "name": label,
                            "objective": objective,
                            "source_claim_ids": [],
                            "targets": [],
                            "constraints": [],
                            "stop_conditions": [],
                            "value_definition": "Keep the objective exact.",
                        },
                        actor="operator",
                        fact_exists=lambda _fact_id: False,
                    )
            before = self._inventory(store.root)
            with self.assertRaisesRegex(ValueError, "multiple exact Campaigns"):
                store.brave_future().intake_research_goal(
                    goal_input={
                        "revision": BF_GOAL_INTAKE_REVISION,
                        "objective": objective,
                    },
                    actor="user",
                )
            self.assertEqual(before, self._inventory(store.root))

        with tempfile.TemporaryDirectory() as temporary:
            store = MathGraphStore(Path(temporary) / "project")
            store.initialize(
                project_id="bf-fast-goal",
                title="Fast goal fixture",
                workflow_evidence_version=5,
                reasoning_mode="fast",
            )
            before = self._inventory(store.root)
            with self.assertRaisesRegex(
                ValueError, "requires reasoning_mode=auto or reasoning_mode=deep"
            ):
                store.brave_future().intake_research_goal(
                    goal_input={
                        "revision": BF_GOAL_INTAKE_REVISION,
                        "objective": "A fast-mode objective.",
                    },
                    actor="user",
                )
            self.assertEqual(before, self._inventory(store.root))

        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            manager = store.brave_future()
            goal = {
                "revision": BF_GOAL_INTAKE_REVISION,
                "objective": "An explicitly disabled recovery objective.",
            }
            first = manager.intake_research_goal(goal_input=goal, actor="user")
            manager.disable(
                campaign_id=first["campaign_id"],
                actor="operator",
                reason="The user disabled advisory recovery.",
            )
            before = self._inventory(store.root)
            with self.assertRaisesRegex(ValueError, "cannot override.*disablement"):
                manager.intake_research_goal(goal_input=goal, actor="user")
            self.assertEqual(before, self._inventory(store.root))

    def test_goal_intake_cli_needs_objective_but_no_campaign_jargon(self) -> None:
        stdout = StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as raised:
            build_parser().parse_args(["research-goal-intake", "--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("exact objective", stdout.getvalue())
        self.assertIn("no Campaign id is required", stdout.getvalue())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            self._store(root)
            goal_path = Path(temporary) / "goal.json"
            goal_path.write_text(
                json.dumps(
                    {
                        "revision": BF_GOAL_INTAKE_REVISION,
                        "objective": "Route this stated goal without Campaign jargon.",
                    }
                ),
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "operator",
                        "research-goal-intake",
                        "--input",
                        str(goal_path),
                        "--actor",
                        "user",
                    ]
                )
            self.assertEqual(code, 0, stderr.getvalue())
            result = json.loads(stdout.getvalue())
            self.assertTrue(result["campaign_created"])
            before = self._inventory(root)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                denied = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "main",
                        "research-goal-intake",
                        "--input",
                        str(goal_path),
                        "--actor",
                        "user",
                    ]
                )
            self.assertEqual(denied, 3)
            self.assertIn("not allowed", stderr.getvalue())
            self.assertEqual(before, self._inventory(root))

    def test_goal_intake_preflights_corrupt_bf_chain_before_campaign_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            manager = store.brave_future()
            first = manager.intake_research_goal(
                goal_input={
                    "revision": BF_GOAL_INTAKE_REVISION,
                    "objective": "Seed one valid advisory chain.",
                },
                actor="user",
            )
            activation_path = (
                store.root
                / "governance"
                / "brave-future"
                / "activation-events.jsonl"
            )
            activation_path.write_bytes(activation_path.read_bytes() + b"{}\n")
            before = self._inventory(store.root)
            campaign_ids = store.campaigns().campaign_ids()
            with self.assertRaisesRegex(ValueError, "fields are not exact"):
                manager.intake_research_goal(
                    goal_input={
                        "revision": BF_GOAL_INTAKE_REVISION,
                        "objective": "A distinct objective must not be published.",
                    },
                    actor="user",
                )
            self.assertEqual(before, self._inventory(store.root))
            self.assertEqual(store.campaigns().campaign_ids(), campaign_ids)
            self.assertIn(first["campaign_id"], campaign_ids)

    def test_goal_intake_internal_scope_reaches_bf2_bf3_after_real_blockage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            manager = store.brave_future()
            goal = {
                "revision": BF_GOAL_INTAKE_REVISION,
                "objective": "Recover from a real bounded method blockage.",
            }
            intake = manager.intake_research_goal(goal_input=goal, actor="user")
            campaign_id = intake["campaign_id"]
            root = self._research(
                store,
                campaign_id,
                "The direct route is the current target.",
            )
            self._research(
                store,
                campaign_id,
                "A sibling route remains available.",
                relation="supports",
                related_research_ids=[root["research_id"]],
            )
            round_status, assignment, receipt = self._ingested_attempt(
                store, campaign_id, root["research_id"]
            )
            refreshed = manager.intake_research_goal(goal_input=goal, actor="user")
            blockage = self._blockage(
                campaign_id=refreshed["campaign_id"],
                planning_snapshot_id=refreshed["bf1"]["planning_snapshot"][
                    "planning_snapshot_id"
                ],
                target_research_id=root["research_id"],
                round_status=round_status,
                assignment=assignment,
                result_research_id=receipt["research_id"],
            )
            dry = manager.reassess(
                campaign_id=refreshed["campaign_id"],
                blockage_input=blockage,
                dry_run=True,
            )
            persisted = manager.reassess(
                campaign_id=refreshed["campaign_id"],
                blockage_input=blockage,
                dry_run=False,
            )
            self.assertEqual(dry["write_effect"], "none")
            self.assertEqual(
                persisted["write_effect"], "one_atomic_sidecar_transaction"
            )
            self.assertEqual(persisted["plan_effect"], "none")
            self.assertEqual(persisted["dispatch_effect"], "none")
            self.assertEqual(store.fact_ids(), [])

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
