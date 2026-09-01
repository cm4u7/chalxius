from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from mathgraph.frontier_actions import _project_research_action
from mathgraph.v5_lifecycle import RoundInspectionContext


class DirectProductFrontierCHX110Tests(unittest.TestCase):
    root_id = "1" * 12
    product_id = "2" * 12
    plan_id = "3" * 12
    review_id = "4" * 12
    production_round = "round-20260831T000000Z-00000001"
    supervision_round = "round-20260831T000000Z-00000002"
    production_assignment = "a01-production-prove"
    supervision_assignment = "a01-supervision-refute"

    def record(
        self,
        research_id: str,
        *,
        metadata: dict | None = None,
        related: list[str] | None = None,
        kind: str = "direction",
        relation: str = "investigates",
    ) -> dict:
        return {
            "research_id": research_id,
            "created_at": f"2026-08-31T00:00:0{len(related or [])}Z",
            "kind": kind,
            "status": "open",
            "claim": f"Claim {research_id}",
            "relation": relation,
            "related_research_ids": related or [],
            "metadata": metadata or {},
        }

    def fixtures(self) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
        product_provenance = {
            "adverse_assignment": False,
            "assignment_id": self.production_assignment,
            "round_id": self.production_round,
            "task_card_sha256": "a" * 64,
            "work_mode": "prove",
            "worker_id": self.production_assignment,
            "writer_lease_id": "lease-production",
        }
        review_provenance = {
            "adverse_assignment": True,
            "assignment_id": self.supervision_assignment,
            "round_id": self.supervision_round,
            "task_card_sha256": "b" * 64,
            "work_mode": "refute",
            "worker_id": self.supervision_assignment,
            "writer_lease_id": "lease-supervision",
        }
        bases = {
            self.root_id: self.record(self.root_id),
            self.product_id: self.record(
                self.product_id,
                metadata={"assignment_provenance": product_provenance},
                related=[self.root_id],
                kind="insight",
                relation="arbitrary_product_label",
            ),
            self.plan_id: self.record(
                self.plan_id,
                metadata={
                    "research_supervision": {
                        "source_round_id": self.production_round,
                        "source_receipts": [
                            {"result_research_id": self.product_id}
                        ],
                    }
                },
                related=[self.product_id],
                kind="challenge",
            ),
            self.review_id: self.record(
                self.review_id,
                metadata={"assignment_provenance": review_provenance},
                related=[self.plan_id],
                kind="insight",
                relation="arbitrary_review_label",
            ),
        }
        production_manifest = {
            "research_cycle": {"subround": "production"},
            "assignments": [
                {
                    "assignment_id": self.production_assignment,
                    "assignment_role": "primary",
                    "research_id": self.root_id,
                    "task_card_sha256": "a" * 64,
                    "work_mode": "prove",
                    "worker_id": self.production_assignment,
                    "writer_lease_id": "lease-production",
                }
            ],
        }
        supervision_manifest = {
            "research_cycle": {
                "subround": "supervision",
                "source_round_id": self.production_round,
            },
            "assignments": [
                {
                    "assignment_id": self.supervision_assignment,
                    "assignment_role": "primary",
                    "research_id": self.plan_id,
                    "task_card_sha256": "b" * 64,
                    "work_mode": "refute",
                    "worker_id": self.supervision_assignment,
                    "writer_lease_id": "lease-supervision",
                }
            ],
        }
        statuses = {
            self.production_round: {
                "assignments": [
                    {
                        **production_manifest["assignments"][0],
                        "state": "ingested",
                        "research_product_id": self.product_id,
                    }
                ]
            },
            self.supervision_round: {
                "assignments": [
                    {
                        **supervision_manifest["assignments"][0],
                        "state": "ingested",
                        "research_product_id": self.review_id,
                    }
                ]
            },
        }
        return bases, {
            self.production_round: production_manifest,
            self.supervision_round: supervision_manifest,
        }, statuses

    def lifecycle(self, bases, manifests, statuses, coverage):
        def round_manifest(round_id, _inspection_context=None):
            return Path(round_id), manifests[round_id]

        def round_status(round_id, inspection):
            return statuses[round_id]

        return SimpleNamespace(
            _round_manifest=round_manifest,
            _round_status_with_context=round_status,
            _frontier_completion_product_is_safe=lambda **kwargs: True,
            _candidate_supervision_scope_coverage=lambda products, _inspection_context=None: coverage,
            _inspection_research_record=lambda research_id, inspection: bases[research_id],
        )

    def inspection(self, *, supervised: bool) -> RoundInspectionContext:
        return RoundInspectionContext(
            completion_obligation_rounds={
                self.root_id: [(self.production_round, "production")]
            },
            supervision_round_ids_by_production_round=(
                {self.production_round: [self.supervision_round]}
                if supervised
                else {}
            ),
        )

    def test_direct_ingested_product_reuses_root_projection(self) -> None:
        bases, manifests, statuses = self.fixtures()
        coverage = [
            {
                "scope": "proof_logic",
                "state": "missing",
                "result_research_ids": [],
                "pending_round_ids": [],
                "unsafe_round_ids": [],
            }
        ]
        lifecycle = self.lifecycle(bases, manifests, statuses, coverage)
        inspection = self.inspection(supervised=False)

        direct = _project_research_action(
            lifecycle,
            research_id=self.product_id,
            bases=bases,
            dispositions={},
            route_staleness={},
            inspection=inspection,
        )
        root = _project_research_action(
            lifecycle,
            research_id=self.root_id,
            bases=bases,
            dispositions={},
            route_staleness={},
            inspection=inspection,
            preferred_production_round_id=self.production_round,
        )

        self.assertEqual(direct, root)
        self.assertEqual(direct["next_action"], "supervision")
        self.assertNotEqual(
            direct["pending_reason"], "no_ingested_production_product"
        )

    def test_direct_supervision_result_follows_source_round(self) -> None:
        bases, manifests, statuses = self.fixtures()
        coverage = [
            {
                "scope": "proof_logic",
                "state": "completed",
                "result_research_ids": [self.review_id],
                "pending_round_ids": [],
                "unsafe_round_ids": [],
            }
        ]
        lifecycle = self.lifecycle(bases, manifests, statuses, coverage)
        inspection = self.inspection(supervised=True)

        direct = _project_research_action(
            lifecycle,
            research_id=self.review_id,
            bases=bases,
            dispositions={},
            route_staleness={},
            inspection=inspection,
        )

        self.assertEqual(direct["next_action"], "main_reconciliation")
        self.assertEqual(
            direct["pending_reason"],
            "clean_supervision_not_reflected_in_automatic_completion",
        )
        self.assertNotEqual(
            direct["pending_reason"], "no_ingested_production_product"
        )

    def test_provenance_mismatch_reconciles_instead_of_reproducing(self) -> None:
        bases, manifests, statuses = self.fixtures()
        statuses[self.production_round]["assignments"][0][
            "research_product_id"
        ] = "f" * 12
        lifecycle = self.lifecycle(bases, manifests, statuses, [])

        action = _project_research_action(
            lifecycle,
            research_id=self.product_id,
            bases=bases,
            dispositions={},
            route_staleness={},
            inspection=self.inspection(supervised=False),
        )

        self.assertEqual(action["next_action"], "main_reconciliation")
        self.assertEqual(
            action["pending_reason"],
            "assignment_product_provenance_mismatch",
        )

    def test_names_and_relations_without_provenance_do_not_classify_role(self) -> None:
        bases, manifests, statuses = self.fixtures()
        unlabeled_id = "5" * 12
        bases[unlabeled_id] = self.record(
            unlabeled_id,
            kind="insight",
            relation="responds_to",
            related=[self.product_id],
        )
        lifecycle = self.lifecycle(bases, manifests, statuses, [])
        inspection = self.inspection(supervised=False)
        inspection.completion_obligation_rounds[unlabeled_id] = []

        action = _project_research_action(
            lifecycle,
            research_id=unlabeled_id,
            bases=bases,
            dispositions={},
            route_staleness={},
            inspection=inspection,
        )

        self.assertEqual(action["next_action"], "production")
        self.assertEqual(
            action["pending_reason"], "no_ingested_production_product"
        )


if __name__ == "__main__":
    unittest.main()
