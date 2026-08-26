from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import RoundInspectionContext


class TerminalFrontierContextTests(unittest.TestCase):
    @staticmethod
    def _store(root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="terminal-frontier-context",
            title="Terminal frontier context",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _campaign(store: MathGraphStore) -> str:
        with store.v5_mutation_lock(command="terminal-frontier-campaign"):
            return store.campaigns().create(
                {
                    "name": "Terminal frontier context",
                    "objective": "Keep exact workflow successors visible to Main.",
                    "source_claim_ids": [],
                    "targets": [],
                    "constraints": [],
                    "stop_conditions": [],
                    "value_definition": "Prefer nonduplicative current work.",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
            )

    @staticmethod
    def _research(
        store: MathGraphStore,
        label: str,
        *,
        campaign_id: str | None = None,
        content: str = "",
        artifacts: list[dict[str, str]] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "kind": "direction",
            "claim": f"Investigate {label}.",
            "content": content,
        }
        if campaign_id is not None:
            payload["campaign_id"] = campaign_id
        if artifacts is not None:
            payload["artifacts"] = artifacts
        return store.v5_lifecycle().add_research(payload, actor="main")

    def test_exact_literal_research_reference_freezes_record_and_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            artifact_path = store.root / "inputs" / "predecessor.md"
            artifact_path.parent.mkdir(parents=True)
            artifact_path.write_text(
                "Exact predecessor bytes for the new task.\n",
                encoding="utf-8",
            )
            artifact = {
                "path": artifact_path.relative_to(store.root).as_posix(),
                "sha256": sha256_bytes(artifact_path.read_bytes()),
                "role": "predecessor_theorem",
            }
            predecessor = self._research(
                store,
                "the exact predecessor",
                artifacts=[artifact],
            )
            predecessor_id = str(predecessor["research_id"])
            source = self._research(
                store,
                "one successor",
                content=(
                    f"Use Research {predecessor_id} as the exact load-bearing "
                    "predecessor."
                ),
            )

            planned = store.v5_lifecycle().create_production_round(
                workers=1,
                research_ids=[str(source["research_id"])],
            )
            assignment = planned["assignments"][0]
            card = json.loads(
                Path(str(assignment["task_card_path"])).read_text(
                    encoding="utf-8"
                )
            )
            state = card["mathematical_state"]
            self.assertEqual(
                state["research_reference_revision"],
                "chalxius-v5-exact-research-references-1",
            )
            self.assertEqual(
                state["literal_research_reference_ids"],
                [predecessor_id],
            )
            self.assertEqual(
                [item["research_id"] for item in state["research_context"]],
                [predecessor_id],
            )
            self.assertEqual(
                state["related_artifacts"],
                [
                    {
                        **artifact,
                        "role": f"{predecessor_id}:predecessor_theorem",
                        "source_research_id": predecessor_id,
                    }
                ],
            )

    def test_nonexistent_literal_token_does_not_create_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            source = self._research(
                store,
                "a token that is not a Research reference",
                content=(
                    "The checksum-like token deadbeefcafe does not name an "
                    "existing project Research record."
                ),
            )

            planned = store.v5_lifecycle().create_production_round(
                workers=1,
                research_ids=[str(source["research_id"])],
            )
            card = json.loads(
                Path(str(planned["assignments"][0]["task_card_path"])).read_text(
                    encoding="utf-8"
                )
            )
            state = card["mathematical_state"]
            self.assertEqual(state["literal_research_reference_ids"], [])
            self.assertEqual(state["research_context"], [])
            self.assertEqual(state["related_artifacts"], [])

    def test_literal_reference_binding_rejects_prose_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            predecessor = self._research(store, "the named predecessor")
            unrelated = self._research(store, "an unrelated record")
            source = self._research(
                store,
                "one exact successor",
                content=(
                    f"Use Research {predecessor['research_id']} as the exact "
                    "predecessor."
                ),
            )
            planned = store.v5_lifecycle().create_production_round(
                workers=1,
                research_ids=[str(source["research_id"])],
            )
            card = json.loads(
                Path(str(planned["assignments"][0]["task_card_path"])).read_text(
                    encoding="utf-8"
                )
            )
            card["mathematical_state"][
                "literal_research_reference_ids"
            ] = [str(unrelated["research_id"])]
            semantic = {
                key: value
                for key, value in card.items()
                if key != "task_card_semantic_sha256"
            }
            card["task_card_semantic_sha256"] = sha256_json(semantic)
            with self.assertRaisesRegex(ValueError, "drifted from source prose"):
                store.v5_lifecycle().validate_task_card(card)

    def test_campaign_projects_terminal_successors_of_attained_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            campaign_id = self._campaign(store)
            anchor = self._research(store, "anchor", campaign_id=campaign_id)
            active = self._research(store, "active head", campaign_id=campaign_id)
            attained = self._research(
                store,
                "attained root",
                campaign_id=campaign_id,
            )
            anchor_id = str(anchor["research_id"])
            active_id = str(active["research_id"])
            attained_id = str(attained["research_id"])
            product_id = "a" * 12
            plan_id = "b" * 12
            review_id = "c" * 12
            with store.v5_mutation_lock(command="terminal-frontier-checkpoint"):
                target_id = store.campaigns().target_add(
                    campaign_id,
                    {
                        "role": "research_goal",
                        "subject_kind": "research",
                        "subject_id": anchor_id,
                        "label": "Keep terminal successors visible",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                    research_exists=lambda item: item == anchor_id,
                )
                store.campaigns().update(
                    campaign_id,
                    {
                        "type": "note",
                        "payload": {
                            "kind": "campaign_frontier_head_checkpoint",
                            "generation": 1,
                            "supersedes_event_id": None,
                            "target_frontiers": [
                                {
                                    "target_id": target_id,
                                    "recovery_root_research_id": anchor_id,
                                    "active_heads": [
                                        {"research_id": active_id}
                                    ],
                                    "attained_checkpoints": [
                                        {"research_id": attained_id}
                                    ],
                                    "main_disposition": "Continue selectively.",
                                }
                            ],
                        },
                    },
                    actor="main",
                )

            bases = {
                item["research_id"]: item
                for item in lifecycle.research_envelopes()
            }
            bases[product_id] = {
                "research_id": product_id,
                "kind": "insight",
                "relation": "responds_to",
                "related_research_ids": [attained_id],
                "created_at": "2026-01-01T00:01:00+00:00",
                "status": "open",
                "metadata": {
                    "campaign_id": campaign_id,
                    "assignment_provenance": {
                        "adverse_assignment": False,
                        "work_mode": "prove",
                    },
                    "obligation_dispositions": [
                        {"status": "complete"}
                    ],
                },
            }
            bases[plan_id] = {
                "research_id": plan_id,
                "kind": "challenge",
                "relation": "challenges",
                "related_research_ids": [product_id],
                "created_at": "2026-01-01T00:02:00+00:00",
                "status": "open",
                "metadata": {
                    "campaign_id": campaign_id,
                    "research_supervision": {
                        "source_receipts": [
                            {"result_research_id": product_id}
                        ]
                    },
                },
            }
            bases[review_id] = {
                "research_id": review_id,
                "kind": "insight",
                "relation": "responds_to",
                "related_research_ids": [plan_id],
                "created_at": "2026-01-01T00:03:00+00:00",
                "status": "open",
                "metadata": {
                    "campaign_id": campaign_id,
                    "assignment_provenance": {
                        "adverse_assignment": True,
                        "work_mode": "refute",
                    },
                },
            }
            work_keys = {
                research_id: sha256_json(["work", research_id])
                for research_id in bases
            }
            workgroups = {
                work_key: [research_id]
                for research_id, work_key in work_keys.items()
            }
            active_key = work_keys[active_id]
            inspection = RoundInspectionContext(
                frontier_group_completions={
                    active_key: (
                        "pending",
                        None,
                        0,
                        sha256_json([]),
                    )
                },
                frontier_group_actions={
                    active_key: {
                        "next_action": "production",
                        "pending_reason": "no_ingested_production_product",
                        "actionable_research_id": active_id,
                        "actionable_round_id": None,
                        "actionable_research_ids": [active_id],
                    }
                },
            )
            with patch.object(
                lifecycle,
                "_frontier_structural_state_for_inspection",
                return_value=(bases, {}, {}, workgroups, work_keys),
            ):
                goal = lifecycle.campaign_goal_coverage(
                    campaign_id,
                    _inspection_context=inspection,
                )[0]

            self.assertEqual(
                goal["uncheckpointed_terminal_successor_research_ids"],
                [review_id],
            )
            summary = goal["attained_semantic_successors"][0]
            self.assertEqual(summary["attained_research_id"], attained_id)
            self.assertEqual(
                summary["production_product_research_ids"], [product_id]
            )
            self.assertEqual(
                summary["supervision_result_research_ids"], [review_id]
            )
            self.assertEqual(summary["terminal_research_ids"], [review_id])
            self.assertEqual(summary["selection_effect"], "none")


if __name__ == "__main__":
    unittest.main()
