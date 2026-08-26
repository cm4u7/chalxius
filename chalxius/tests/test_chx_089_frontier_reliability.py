from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import RoundInspectionContext


class FrontierReliability089Tests(unittest.TestCase):
    @staticmethod
    def _store(root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="chx-089-frontier",
            title="CHX 0.8.9 frontier reliability",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _campaign(store: MathGraphStore, label: str) -> str:
        with store.v5_mutation_lock(command="chx-089-campaign"):
            return store.campaigns().create(
                {
                    "name": label,
                    "objective": "Expose one exact bounded research frontier.",
                    "source_claim_ids": [],
                    "targets": [],
                    "constraints": ["No truth effect."],
                    "stop_conditions": ["Return control to Main."],
                    "value_definition": "Prefer exact reusable progress.",
                },
                actor="main",
                fact_exists=lambda _fact_id: False,
            )

    def _duplicate_roots(
        self,
        store: MathGraphStore,
        campaign_id: str,
    ) -> tuple[dict[str, object], dict[str, object]]:
        lifecycle = store.v5_lifecycle()
        context_a = lifecycle.add_research(
            {"claim": "Historical context A."}, actor="main-a"
        )
        semantic = {
            "kind": "direction",
            "status": "open",
            "claim": "Resolve the same exact local frontier objective.",
            "content": "Use the same hypotheses and output contract.",
            "rationale": "This objective is executable as written.",
            "source": "Frozen source slice S.",
            "relation": "investigates",
            "campaign_id": campaign_id,
            "future_exact_work_semantics": {"parameter": "alpha"},
            "artifacts": [],
            "obligations": [
                {
                    "obligation_id": "exact-objective",
                    "description": "Return the exact bounded result.",
                    "required_artifact_roles": [],
                    "evidence_types": ["bounded_argument"],
                    "not_applicable_allowed": False,
                }
            ],
        }
        first = lifecycle.add_research(
            {
                **semantic,
                "provider": "historical-main-a",
                "related_research_ids": [context_a["research_id"]],
            },
            actor="main-a",
        )
        second = lifecycle.add_research(
            {
                **semantic,
                "provider": "historical-main-b",
                "related_research_ids": [context_a["research_id"]],
            },
            actor="main-b",
        )
        return first, second

    def test_exact_workgroup_completion_is_shared_by_frontier_views(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store, "Exact duplicate closure")
            lifecycle = store.v5_lifecycle()
            first, second = self._duplicate_roots(store, campaign_id)

            completed = {second["research_id"]: "completed_production"}
            with patch.object(
                lifecycle,
                "_validated_completed_research_obligation_statuses",
                return_value=completed,
            ):
                actionable = lifecycle.frontier(
                    campaign_id=campaign_id,
                    limit=10,
                )
                history = lifecycle.frontier(
                    campaign_id=campaign_id,
                    include_history=True,
                    limit=10,
                )

            duplicate_ids = {first["research_id"], second["research_id"]}
            self.assertTrue(
                duplicate_ids.isdisjoint(
                    {item["research_id"] for item in actionable}
                )
            )
            by_id = {item["research_id"]: item for item in history}
            self.assertEqual(
                by_id[first["research_id"]]["work_key_sha256"],
                by_id[second["research_id"]]["work_key_sha256"],
            )
            for research_id in duplicate_ids:
                self.assertEqual(
                    by_id[research_id]["work_completion_status"],
                    "completed_production",
                )
            lifecycle.update_research(
                second["research_id"],
                status="resolved_by_evidence",
                actor="main",
                note="The supervised work is positively resolved.",
            )
            with patch.object(
                lifecycle,
                "_validated_completed_research_obligation_statuses",
                return_value=completed,
            ):
                positively_resolved = lifecycle.frontier(
                    campaign_id=campaign_id,
                    limit=10,
                )
            self.assertTrue(
                duplicate_ids.isdisjoint(
                    {item["research_id"] for item in positively_resolved}
                )
            )
            lifecycle.update_research(
                second["research_id"],
                status="challenged",
                actor="main",
                note="A later exact defect reopens the work.",
            )
            with patch.object(
                lifecycle,
                "_validated_completed_research_obligation_statuses",
                return_value=completed,
            ):
                challenged = lifecycle.frontier(
                    campaign_id=campaign_id,
                    limit=10,
                )
            self.assertIn(
                first["research_id"],
                {item["research_id"] for item in challenged},
            )
            lifecycle.update_research(
                second["research_id"],
                status="resolved_by_evidence",
                actor="main",
                note="The exact defect was resolved.",
            )
            lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "Invalidate only the completed historical duplicate.",
                    "campaign_id": campaign_id,
                    "route_invalidations": [second["research_id"]],
                },
                actor="main",
            )
            with patch.object(
                lifecycle,
                "_validated_completed_research_obligation_statuses",
                return_value=completed,
            ):
                reopened = lifecycle.frontier(
                    campaign_id=campaign_id,
                    limit=10,
                )
            self.assertIn(
                first["research_id"],
                {item["research_id"] for item in reopened},
            )

    def test_work_key_semantic_predicate_false_and_requested_limit_bounds_projection(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store, "Bounded frontier")
            lifecycle = store.v5_lifecycle()
            first, second = self._duplicate_roots(store, campaign_id)
            records = {
                item["research_id"]: item
                for item in lifecycle.research_envelopes()
            }
            base = records[first["research_id"]]
            twin = records[second["research_id"]]
            key = lifecycle._frontier_work_key(base)
            self.assertEqual(key, lifecycle._frontier_work_key(twin))

            variants: list[dict[str, object]] = []
            dependency_variant = copy.deepcopy(base)
            dependency_variant["dependencies"] = ["1" * 16]
            variants.append(dependency_variant)
            artifact_variant = copy.deepcopy(base)
            artifact_variant["metadata"]["artifacts"] = [
                {
                    "path": "artifacts/exact.md",
                    "sha256": "2" * 64,
                    "role": "research_report",
                }
            ]
            variants.append(artifact_variant)
            campaign_variant = copy.deepcopy(base)
            campaign_variant["metadata"]["campaign_id"] = "campaign-" + "3" * 12
            variants.append(campaign_variant)
            obligation_variant = copy.deepcopy(base)
            obligation_variant["metadata"]["obligations"][0][
                "description"
            ] = "A mathematically different obligation."
            variants.append(obligation_variant)
            future_semantic_variant = copy.deepcopy(base)
            future_semantic_variant["metadata"]["future_exact_work_semantics"] = {
                "parameter": "beta"
            }
            variants.append(future_semantic_variant)
            related_input_variant = copy.deepcopy(base)
            related_input_variant["related_research_ids"] = []
            variants.append(related_input_variant)
            for variant in variants:
                self.assertNotEqual(key, lifecycle._frontier_work_key(variant))

            bulky_artifacts = [
                {
                    "path": f"artifacts/unrelated-{index:03d}.md",
                    "sha256": f"{index + 10:064x}",
                    "role": "research_report",
                }
                for index in range(100)
            ]
            for index in range(12):
                lifecycle.add_research(
                    {
                        "claim": f"Bounded independent route {index:02d}.",
                        "campaign_id": campaign_id,
                        "artifacts": bulky_artifacts,
                    },
                    actor=f"main-{index}",
                )
            compact = lifecycle.frontier(
                campaign_id=campaign_id,
                limit=3,
            )
            self.assertEqual(len(compact), 3)
            self.assertTrue(all("metadata" not in item for item in compact))
            encoded = json.dumps(compact, sort_keys=True)
            self.assertNotIn("unrelated-099.md", encoded)
            self.assertLess(len(encoded.encode()), 16_000)


    def test_zero_target_skips_fact_inventory_and_exact_target_tamper_fails(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            campaign_id = self._campaign(store, "Zero proof targets")
            lifecycle = store.v5_lifecycle()
            with patch.object(
                store,
                "fact_ids",
                side_effect=AssertionError("broad Fact inventory must not run"),
            ) as fact_ids, patch.object(
                lifecycle,
                "_active_fact_premise_bindings",
                side_effect=AssertionError("zero proof targets need no Fact binding"),
            ) as exact_bindings:
                lifecycle._campaign_snapshot_for_planning(
                    campaign_id,
                    _inspection_context=RoundInspectionContext(),
                )
            fact_ids.assert_not_called()
            exact_bindings.assert_not_called()

            target_ids = ["1" * 16, "2" * 16]
            status = store.campaigns().status(campaign_id)
            status["targets"] = {
                f"target-{index}": {
                    "target_id": f"target-{index}",
                    "role": "headline_proof" if index == 1 else "supporting_proof",
                    "status": "active",
                    "subject_kind": "fact",
                    "subject_id": fact_id,
                    "label": f"Exact proof target {index}",
                }
                for index, fact_id in enumerate(target_ids, 1)
            }
            with patch(
                "mathgraph.campaigns.CampaignStore.status",
                return_value=status,
            ), patch.object(
                lifecycle,
                "_active_fact_premise_bindings",
                return_value={fact_id: {} for fact_id in target_ids},
            ) as exact_bindings:
                lifecycle._campaign_snapshot_for_planning(
                    campaign_id,
                    _inspection_context=RoundInspectionContext(),
                )
            self.assertEqual(exact_bindings.call_count, 1)
            self.assertEqual(exact_bindings.call_args.args[0], sorted(target_ids))
            with patch(
                "mathgraph.campaigns.CampaignStore.status",
                return_value=status,
            ), patch.object(
                lifecycle,
                "_active_fact_premise_bindings",
                side_effect=ValueError("tampered exact target"),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "active proof targets are not exact admitted Facts",
                ):
                    lifecycle._campaign_snapshot_for_planning(
                        campaign_id,
                        _inspection_context=RoundInspectionContext(),
                    )


    def test_source_assurance_prompt_names_exact_structured_obligations(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle = self._store(
                Path(temporary) / "project"
            ).v5_lifecycle()
            prompt = lifecycle._compact_prompt(
                card={
                    "round_id": "round-20260822T000000Z-00000000",
                    "assignment_id": "a01-000000000000-prove",
                    "work_mode": "prove",
                    "narrative_plane": {"claim": "Use one exact source."},
                    "return_contract": {
                        "return_relpath": "worker_returns/a01.json"
                    },
                    "assurance_contract": {
                        "risk_signals": ["source_use_required"],
                        "obligations": [
                            {
                                "obligation_id": "obl-source",
                                "evidence_types": ["primary_source"],
                                "required_artifact_roles": [],
                            },
                            {
                                "obligation_id": "obl-applicability",
                                "evidence_types": ["applicability"],
                                "required_artifact_roles": [],
                            },
                        ],
                    },
                },
                task_card_sha256="0" * 64,
            )
            self.assertIn(
                "Structured source obligation ids: "
                "obl-source, obl-applicability",
                prompt,
            )
            self.assertIn(
                "Structured applicability obligation ids: obl-applicability",
                prompt,
            )
            self.assertIn(
                "bind every witness declared by a completed obligation "
                "disposition",
                prompt,
            )
            self.assertIn('"bridge_artifact_sha256s": []', prompt)


if __name__ == "__main__":
    unittest.main()
