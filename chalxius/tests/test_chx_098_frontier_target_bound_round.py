from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mathgraph.contracts import sha256_bytes
from mathgraph.store import MathGraphStore


class FrontierTargetBoundRoundTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "project"
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="frontier-target-bound-round",
            title="Frontier target-bound round",
            workflow_evidence_version=5,
        )
        with self.store.v5_mutation_lock(command="target-bound-fixture"):
            self.campaign_id = self.store.campaigns().create(
                {
                    "name": "Target-bound frontier",
                    "objective": "Keep current physical work ahead of history.",
                    "source_claim_ids": [],
                    "targets": [],
                    "constraints": [],
                    "stop_conditions": [],
                    "value_definition": "Prefer exact current work.",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
            )
        self.root_id = self._research("root")
        with self.store.v5_mutation_lock(command="target-bound-fixture"):
            self.target_id = self.store.campaigns().target_add(
                self.campaign_id,
                {
                    "role": "research_goal",
                    "subject_kind": "research",
                    "subject_id": self.root_id,
                    "label": "Resolve the target-bound route",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
                research_exists=lambda item: item == self.root_id,
            )
            self.store.campaigns().activate(self.campaign_id, actor="main")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _blank_assurance() -> dict[str, list[object]]:
        return {
            "source_uses": [],
            "route_invalidations": [],
            "extremal_cases": [],
            "claim_strength": [],
            "contour_substitutions": [],
            "claimed_structures": [],
            "program_math_alignments": [],
        }

    def _research(self, label: str) -> str:
        return self.store.v5_lifecycle().add_research(
            {
                "kind": "direction",
                "campaign_id": self.campaign_id,
                "claim": f"Claim {label}",
                "content": f"Content {label}",
                "rationale": f"Rationale {label}",
                "decision_profile": {
                    "impact": 0.8,
                    "information_value": 0.8,
                    "tractability": 0.7,
                    "burden": 0.2,
                },
            },
            actor="main",
        )["research_id"]

    def _ingest(self, planned: dict[str, object], label: str) -> str:
        lifecycle = self.store.v5_lifecycle()
        assignment = planned["assignments"][0]
        assert isinstance(assignment, dict)
        card_path = Path(str(assignment["task_card_path"]))
        card = json.loads(card_path.read_text(encoding="utf-8"))
        artifact_dir = self.root / str(assignment["artifact_dir_relpath"])
        artifact_dir.mkdir(parents=True, exist_ok=True)
        report_path = artifact_dir / f"worker-report-{label}.md"
        report_path.write_text(
            f"Bounded nontruth Research output for {label}.\n",
            encoding="utf-8",
        )
        report = {
            "path": report_path.relative_to(self.root).as_posix(),
            "sha256": sha256_bytes(report_path.read_bytes()),
            "role": "research_report",
        }
        payload = {
            "schema_version": 5,
            "project_id": self.store.project_id(),
            "round_id": planned["round_id"],
            "assignment_id": assignment["assignment_id"],
            "worker_id": assignment["worker_id"],
            "task_card_sha256": assignment["task_card_sha256"],
            "blackboard_snapshot_sha256": assignment[
                "blackboard_snapshot_sha256"
            ],
            "outcome": "proof",
            "claim": f"Exact {label} output is ready for supervision.",
            "content": "This fixture changes no Candidate or Fact authority.",
            "narrative": {
                "rationale": "Freeze one exact component.",
                "summary": "One assignment is complete.",
                "intuition": "History remains distinct from current work.",
                "limitations": "This is nontruth Research only.",
            },
            "artifacts": [report],
            "obligation_dispositions": [
                {
                    "obligation_id": obligation["obligation_id"],
                    "status": "complete",
                    "witness_artifact_sha256s": [report["sha256"]],
                    "rationale": "The exact report is hash-bound.",
                }
                for obligation in card["assurance_contract"]["obligations"]
            ],
            "computation_manifest": None,
            "research_assurance": self._blank_assurance(),
        }
        return_path = Path(str(assignment["return_path"]))
        return_path.write_text(
            json.dumps(payload, sort_keys=True), encoding="utf-8"
        )
        receipt = lifecycle.ingest_return(
            round_id=str(planned["round_id"]),
            assignment_id=str(assignment["assignment_id"]),
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        self.assertEqual(receipt["status"], "ingested", receipt)
        return str(receipt["research_id"])

    def _plan(
        self,
        research_ids: list[str],
        *,
        target_bound: bool,
        host_scope: str,
    ) -> dict[str, object]:
        return self.store.v5_lifecycle().create_production_round(
            workers=len(research_ids),
            research_ids=research_ids,
            campaign_id=self.campaign_id,
            frontier_target_id=self.target_id if target_bound else None,
            host_task_scope_id=host_scope,
        )

    def _goal(self) -> dict[str, object]:
        return self.store.v5_lifecycle().frontier_decision_surface(
            campaign_id=self.campaign_id,
            limit=1,
        )["goal_coverage"][0]

    def test_current_production_reuse_beats_completed_historical_workgroup(
        self,
    ) -> None:
        historical = self._plan(
            [self.root_id],
            target_bound=False,
            host_scope="historical-production",
        )
        self._ingest(historical, "historical")

        current = self._plan(
            [self.root_id],
            target_bound=True,
            host_scope="current-production",
        )
        goal = self._goal()

        self.assertEqual(goal["coverage_status"], "in_flight")
        self.assertEqual(goal["next_action"], "await_return")
        self.assertEqual(goal["why_now"], "production_round_in_flight")
        self.assertEqual(goal["actionable_round_id"], current["round_id"])
        self.assertNotEqual(goal["actionable_round_id"], historical["round_id"])

    def test_current_supervision_beats_older_production_history(self) -> None:
        historical = self._plan(
            [self.root_id],
            target_bound=False,
            host_scope="historical-production",
        )
        self._ingest(historical, "historical")
        current = self._plan(
            [self.root_id],
            target_bound=True,
            host_scope="current-production",
        )
        self._ingest(current, "current")
        supervision = self.store.v5_lifecycle().create_supervision_round(
            str(current["round_id"]),
            supervisor_scopes=["proof_logic"],
            host_task_scope_id="current-supervision",
        )

        goal = self._goal()

        self.assertEqual(goal["coverage_status"], "in_flight")
        self.assertEqual(goal["next_action"], "await_return")
        self.assertEqual(goal["why_now"], "supervision_round_in_flight")
        self.assertEqual(
            goal["actionable_round_id"], supervision["round_id"]
        )
        self.assertNotEqual(goal["actionable_round_id"], historical["round_id"])

    def test_multihead_round_survives_explicit_named_head_retirement(self) -> None:
        second_id = self._research("second")
        current = self._plan(
            [self.root_id, second_id],
            target_bound=True,
            host_scope="multihead-production",
        )

        goal = self._goal()
        self.assertEqual(
            goal["active_head_research_ids"], [self.root_id, second_id]
        )
        self.assertEqual(len(goal["active_head_actions"]), 2)
        self.assertEqual(
            {
                action["actionable_round_id"]
                for action in goal["active_head_actions"]
            },
            {current["round_id"]},
        )

        self.store.v5_lifecycle().reconcile_campaign_frontier(
            self.campaign_id,
            {
                "kind": "campaign_frontier_update",
                "target_id": self.target_id,
                "attention_updates": [
                    {
                        "operation": "retire_active_head",
                        "research_id": self.root_id,
                        "disposition": "superseded",
                    }
                ],
            },
        )
        overridden = self._goal()
        self.assertEqual(overridden["active_head_research_ids"], [second_id])
        self.assertEqual(len(overridden["active_head_actions"]), 1)
        self.assertEqual(overridden["coverage_status"], "in_flight")
        self.assertEqual(
            overridden["actionable_round_id"], current["round_id"]
        )


if __name__ == "__main__":
    unittest.main()
