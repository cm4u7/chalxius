"""CHX-102: every aggregate subaudit must retain its owning context."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from mathgraph.paper_continuation import PaperContinuationManager
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import RoundInspectionContext


class CHX102NoveltyAuditContextTests(unittest.TestCase):
    def test_novelty_subaudit_threads_one_context_to_all_subject_readers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            store = MathGraphStore(root)
            store.initialize(
                project_id="chx-102-novelty-context",
                title="Novelty audit context fixture",
                workflow_evidence_version=5,
            )
            lifecycle = store.v5_lifecycle()
            inspection = RoundInspectionContext()

            with (
                patch.object(store, "fact_ids", return_value=[]) as fact_ids,
                patch.object(
                    lifecycle,
                    "revoked_fact_ids",
                    return_value=set(),
                ) as revoked_fact_ids,
                patch.object(
                    lifecycle,
                    "research_records",
                    return_value=[],
                ) as research_records,
            ):
                self.assertEqual(
                    lifecycle._audit_novelty(
                        _inspection_context=inspection
                    ),
                    [],
                )

            fact_ids.assert_called_once_with(
                _inspection_context=inspection
            )
            revoked_fact_ids.assert_called_once_with(
                _inspection_context=inspection
            )
            research_records.assert_called_once_with(
                _inspection_context=inspection
            )

    def test_complete_audit_supplies_an_owning_context_to_novelty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            store = MathGraphStore(root)
            store.initialize(
                project_id="chx-102-aggregate-context",
                title="Aggregate audit context fixture",
                workflow_evidence_version=5,
            )
            lifecycle = store.v5_lifecycle()
            novelty_audit = Mock(return_value=[])
            lifecycle._audit_novelty = novelty_audit  # type: ignore[method-assign]

            lifecycle.audit()

            novelty_audit.assert_called_once()
            supplied = novelty_audit.call_args.kwargs.get(
                "_inspection_context"
            )
            self.assertIsInstance(supplied, RoundInspectionContext)

    def test_paper_scope_reuses_the_owning_continuation_manager(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = MathGraphStore(Path(temporary).resolve())
            store.initialize(
                project_id="chx-102-paper-scope",
                title="Paper scope context fixture",
                workflow_evidence_version=5,
            )
            lifecycle = store.v5_lifecycle()
            inspection = RoundInspectionContext()
            record = {"research_id": "memory-" + "4" * 64}
            continuation = Mock()
            continuation.scope_for_research.return_value = None

            with patch.object(
                lifecycle,
                "paper_continuation",
                return_value=continuation,
            ) as manager_factory:
                self.assertIsNone(
                    lifecycle._inspection_paper_continuation_scope(
                        record,
                        inspection,
                    )
                )

            manager_factory.assert_called_once_with(
                _inspection_context=inspection
            )
            continuation.scope_for_research.assert_called_once_with(
                record,
                _plan_cache=inspection.paper_continuation_plans,
            )

    def test_managed_disposition_keeps_context_through_round_validation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = MathGraphStore(Path(temporary).resolve())
            store.initialize(
                project_id="chx-102-managed-result",
                title="Managed result context fixture",
                workflow_evidence_version=5,
            )
            lifecycle = store.v5_lifecycle()
            inspection = RoundInspectionContext()
            continuation = PaperContinuationManager(
                lifecycle,
                _inspection_context=inspection,
            )
            result = {
                "research_id": "memory-" + "5" * 64,
                "metadata": {
                    "worker_outcome": "evidence",
                    "assignment_provenance": {
                        "round_id": "round-20260805T000000Z-abcdef12",
                        "assignment_id": "a01-abcdef123456-prove",
                    },
                },
            }
            round_dir = store.rounds_dir / result["metadata"][
                "assignment_provenance"
            ]["round_id"]
            manifest = {
                "round_id": result["metadata"]["assignment_provenance"][
                    "round_id"
                ],
                "assignments": [],
            }
            assignment = {
                "assignment_id": result["metadata"]["assignment_provenance"][
                    "assignment_id"
                ]
            }

            with (
                patch.object(
                    lifecycle,
                    "_research_is_adverse_assignment",
                    return_value=False,
                ),
                patch.object(
                    lifecycle,
                    "_round_manifest",
                    return_value=(round_dir, manifest),
                ) as round_manifest,
                patch.object(
                    lifecycle,
                    "_assignment",
                    return_value=assignment,
                ),
                patch.object(
                    lifecycle,
                    "_research_product_for_assignment",
                    return_value=(result, None),
                ) as research_product,
            ):
                continuation._validate_managed_result(result)

            round_manifest.assert_called_once_with(
                result["metadata"]["assignment_provenance"]["round_id"],
                _inspection_context=inspection,
            )
            research_product.assert_called_once_with(
                round_dir=round_dir,
                manifest=manifest,
                assignment=assignment,
                _inspection_context=inspection,
            )


if __name__ == "__main__":
    unittest.main()
