from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.frontier_actions import _project_research_action
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import RoundInspectionContext


class FrontierActiveFix090Tests(unittest.TestCase):
    @staticmethod
    def _store(root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="chx-090-frontier",
            title="CHX 0.9.0 frontier active fix boundary",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _record(
        research_id: str,
        *,
        created_at: str,
        kind: str = "direction",
        relation: str = "investigates",
        related: list[str] | None = None,
        complete: bool = False,
    ) -> dict[str, object]:
        metadata: dict[str, object] = {}
        if complete:
            metadata["obligation_dispositions"] = [
                {
                    "obligation_id": "bounded-result",
                    "status": "complete",
                    "witness_artifact_sha256s": [],
                    "rationale": "The exact synthetic result is complete.",
                }
            ]
        return {
            "research_id": research_id,
            "created_at": created_at,
            "kind": kind,
            "status": "open",
            "claim": f"Synthetic claim {research_id}.",
            "relation": relation,
            "related_research_ids": related or [],
            "metadata": metadata,
        }

    def test_frontier_exposes_production_as_a_derived_action(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle = self._store(
                Path(temporary) / "project"
            ).v5_lifecycle()
            root = lifecycle.add_research(
                {"claim": "Resolve one genuinely unattempted objective."},
                actor="main",
            )

            frontier = lifecycle.frontier(limit=1)

            self.assertEqual(len(frontier), 1)
            self.assertEqual(frontier[0]["research_id"], root["research_id"])
            self.assertEqual(frontier[0]["next_action"], "production")
            self.assertEqual(
                frontier[0]["pending_reason"],
                "no_ingested_production_product",
            )
            self.assertEqual(
                frontier[0]["actionable_research_id"], root["research_id"]
            )

            decisions = lifecycle.frontier_decision_surface(limit=1)
            self.assertEqual(
                decisions["workflow_queue"][0]["action_class"],
                "research_development",
            )
            self.assertEqual(decisions["goal_coverage"], [])
            self.assertNotIn("record_sha256", decisions["workflow_queue"][0])
            self.assertNotIn("decision_factors", decisions["workflow_queue"][0])
            self.assertLess(
                len(json.dumps(decisions, sort_keys=True).encode("utf-8")),
                2_000,
            )

    def test_research_only_campaign_sync_does_not_scan_the_fact_graph(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")

            with store.v5_mutation_lock(command="campaign-create"):
                campaign_id = store.campaigns().create(
                    {
                        "name": "Research-only performance fixture",
                        "objective": "Track one exact Research boundary.",
                        "source_claim_ids": [],
                        "targets": [],
                        "constraints": [],
                        "stop_conditions": [],
                        "value_definition": "Prefer exact bounded progress.",
                    },
                    actor="main",
                    fact_exists=lambda _fact_id: False,
                )
                store.campaigns().activate(campaign_id, actor="main")

            with store.v5_mutation_lock(command="campaign-target-add"):
                with patch.object(
                    store,
                    "facts",
                    side_effect=AssertionError(
                        "an empty proof-target closure scanned every Fact"
                    ),
                ):
                    targets = store.sync_active_campaign_targets()

            self.assertEqual(targets, [])
            certificate = json.loads(
                (
                    store.reports_dir / "target-closure-certificate.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(certificate["targets"], [])
            self.assertEqual(certificate["closure"], [])
            self.assertEqual(certificate["fact_sha256"], {})

    def test_ingested_product_routes_to_supervision_not_duplicate_production(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle = self._store(
                Path(temporary) / "project"
            ).v5_lifecycle()
            root_id = "1" * 12
            product_id = "2" * 12
            round_id = "round-20260824T000000Z-00000001"
            bases = {
                root_id: self._record(
                    root_id, created_at="2026-08-24T00:00:00Z"
                ),
                product_id: self._record(
                    product_id,
                    created_at="2026-08-24T00:01:00Z",
                    kind="evidence",
                    related=[root_id],
                    complete=True,
                ),
            }
            inspection = RoundInspectionContext(
                completion_obligation_rounds={
                    root_id: [(round_id, "production")]
                },
                supervision_round_ids_by_production_round={},
            )
            status = {
                "assignments": [
                    {
                        "research_id": root_id,
                        "assignment_role": "primary",
                        "state": "ingested",
                        "research_product_id": product_id,
                    }
                ]
            }

            with patch.object(
                lifecycle, "_round_status_with_context", return_value=status
            ):
                action = _project_research_action(
                    lifecycle,
                    research_id=root_id,
                    bases=bases,
                    dispositions={},
                    route_staleness={},
                    inspection=inspection,
                )

            self.assertEqual(action["next_action"], "supervision")
            self.assertEqual(action["actionable_research_id"], product_id)
            self.assertEqual(action["actionable_round_id"], round_id)

    def test_live_supervision_precedes_pre_supervision_product_safety(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle = self._store(
                Path(temporary) / "project"
            ).v5_lifecycle()
            root_id = "a" * 12
            product_id = "b" * 12
            production_round = "round-20260825T000000Z-00000001"
            supervision_round = "round-20260825T000000Z-00000002"
            bases = {
                root_id: self._record(
                    root_id, created_at="2026-08-25T00:00:00Z"
                ),
                # No obligation dispositions: deliberately unsafe for a new
                # automatic supervision suggestion.
                product_id: self._record(
                    product_id,
                    created_at="2026-08-25T00:01:00Z",
                    kind="evidence",
                    related=[root_id],
                ),
            }
            inspection = RoundInspectionContext(
                completion_obligation_rounds={
                    root_id: [(production_round, "production")]
                },
                supervision_round_ids_by_production_round={
                    production_round: [supervision_round]
                },
            )

            def project(supervision_state: str) -> dict[str, object]:
                statuses = {
                    production_round: {
                        "assignments": [
                            {
                                "research_id": root_id,
                                "assignment_role": "primary",
                                "state": "ingested",
                                "research_product_id": product_id,
                            }
                        ]
                    },
                    supervision_round: {
                        "assignments": [{"state": supervision_state}]
                    },
                }
                with patch.object(
                    lifecycle,
                    "_round_status_with_context",
                    side_effect=lambda round_id, _context: statuses[round_id],
                ):
                    return _project_research_action(
                        lifecycle,
                        research_id=root_id,
                        bases=bases,
                        dispositions={},
                        route_staleness={},
                        inspection=inspection,
                    )

            awaiting = project("awaiting_return")
            self.assertEqual(awaiting["next_action"], "await_return")
            self.assertEqual(
                awaiting["pending_reason"], "supervision_round_in_flight"
            )
            returned = project("return_present")
            self.assertEqual(returned["next_action"], "ingest_return")
            self.assertEqual(
                returned["pending_reason"], "supervision_return_present"
            )
            completed = project("ingested")
            self.assertEqual(completed["next_action"], "main_reconciliation")
            self.assertEqual(
                completed["pending_reason"],
                "ingested_product_not_safe_for_automatic_routing",
            )

            no_supervision = RoundInspectionContext(
                completion_obligation_rounds={
                    root_id: [(production_round, "production")]
                },
                supervision_round_ids_by_production_round={},
            )
            with patch.object(
                lifecycle,
                "_round_status_with_context",
                return_value={
                    "assignments": [
                        {
                            "research_id": root_id,
                            "assignment_role": "primary",
                            "state": "ingested",
                            "research_product_id": product_id,
                        }
                    ]
                },
            ):
                action = _project_research_action(
                    lifecycle,
                    research_id=root_id,
                    bases=bases,
                    dispositions={},
                    route_staleness={},
                    inspection=no_supervision,
                )
            self.assertEqual(action["next_action"], "main_reconciliation")
            self.assertEqual(
                action["pending_reason"],
                "ingested_product_not_safe_for_automatic_routing",
            )

    def test_multiple_ingested_products_require_main_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle = self._store(
                Path(temporary) / "project"
            ).v5_lifecycle()
            root_id = "3" * 12
            first_product = "4" * 12
            second_product = "5" * 12
            first_round = "round-20260824T000000Z-00000002"
            second_round = "round-20260824T000000Z-00000003"
            bases = {
                root_id: self._record(
                    root_id, created_at="2026-08-24T00:00:00Z"
                ),
                first_product: self._record(
                    first_product,
                    created_at="2026-08-24T00:01:00Z",
                    kind="evidence",
                    related=[root_id],
                    complete=True,
                ),
                second_product: self._record(
                    second_product,
                    created_at="2026-08-24T00:02:00Z",
                    kind="evidence",
                    related=[root_id],
                    complete=True,
                ),
            }
            inspection = RoundInspectionContext(
                completion_obligation_rounds={
                    root_id: [
                        (first_round, "production"),
                        (second_round, "production"),
                    ]
                },
                supervision_round_ids_by_production_round={},
            )
            statuses = {
                first_round: {
                    "assignments": [
                        {
                            "research_id": root_id,
                            "assignment_role": "primary",
                            "state": "ingested",
                            "research_product_id": first_product,
                        }
                    ]
                },
                second_round: {
                    "assignments": [
                        {
                            "research_id": root_id,
                            "assignment_role": "primary",
                            "state": "ingested",
                            "research_product_id": second_product,
                        }
                    ]
                },
            }

            with patch.object(
                lifecycle,
                "_round_status_with_context",
                side_effect=lambda round_id, _context: statuses[round_id],
            ):
                action = _project_research_action(
                    lifecycle,
                    research_id=root_id,
                    bases=bases,
                    dispositions={},
                    route_staleness={},
                    inspection=inspection,
                )

            self.assertEqual(action["next_action"], "main_reconciliation")
            self.assertEqual(
                action["pending_reason"],
                "multiple_ingested_production_products",
            )
            self.assertEqual(
                set(action["actionable_research_ids"]),
                {root_id, first_product, second_product},
            )

    def test_historical_exact_links_are_visible_but_never_auto_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle = self._store(
                Path(temporary) / "project"
            ).v5_lifecycle()
            root_id = "6" * 12
            product_id = "7" * 12
            invalidator_id = "8" * 12
            repair_id = "9" * 12
            round_id = "round-20260824T000000Z-00000004"
            bases = {
                root_id: self._record(
                    root_id, created_at="2026-08-24T00:00:00Z"
                ),
                product_id: self._record(
                    product_id,
                    created_at="2026-08-24T00:01:00Z",
                    kind="evidence",
                    related=[root_id],
                    complete=True,
                ),
                invalidator_id: self._record(
                    invalidator_id,
                    created_at="2026-08-24T00:02:00Z",
                    kind="challenge",
                    related=[product_id],
                ),
                repair_id: self._record(
                    repair_id,
                    created_at="2026-08-24T00:03:00Z",
                    kind="repair",
                    relation="extends",
                    related=[root_id, product_id, invalidator_id],
                ),
            }
            inspection = RoundInspectionContext(
                completion_obligation_rounds={
                    root_id: [(round_id, "production")]
                },
                supervision_round_ids_by_production_round={},
            )
            status = {
                "assignments": [
                    {
                        "research_id": root_id,
                        "assignment_role": "primary",
                        "state": "ingested",
                        "research_product_id": product_id,
                    }
                ]
            }

            with patch.object(
                lifecycle, "_round_status_with_context", return_value=status
            ):
                action = _project_research_action(
                    lifecycle,
                    research_id=root_id,
                    bases=bases,
                    dispositions={},
                    route_staleness={product_id: [invalidator_id]},
                    inspection=inspection,
                )

            self.assertEqual(action["next_action"], "main_reconciliation")
            self.assertEqual(
                action["pending_reason"],
                "historical_or_ambiguous_repair_lineage",
            )
            self.assertEqual(action["actionable_research_id"], repair_id)


if __name__ == "__main__":
    unittest.main()
