"""Regression contract for one V5 active-Fact reconstruction per inspection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from mathgraph.contracts import sha256_bytes
from mathgraph.markdown import serialize_fact
from mathgraph.model import Fact
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import RoundInspectionContext


class CHX100ActiveFactInspectionContextTests(unittest.TestCase):
    @staticmethod
    def _tree_snapshot(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes())
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def test_store_fact_read_apis_share_one_v5_active_fact_reconstruction(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "project"
            store = MathGraphStore(root)
            store.initialize(
                project_id="chx-100-active-fact-cache",
                title="Active Fact inspection cache fixture",
                workflow_evidence_version=5,
            )
            facts = [
                Fact(
                    problem_id=store.project_id(),
                    author="fixture",
                    predecessors=[],
                    statement=f"[CLAIM:CACHE_{index}] Cached Fact {index} holds.",
                    proof=f"Fixture proof {index}.",
                )
                for index in range(3)
            ]
            fixture_dir = root / "inspection-fixtures"
            fixture_dir.mkdir()
            active_paths: dict[str, Path] = {}
            active_facts: dict[str, Fact] = {}
            for fact in facts:
                path = fixture_dir / f"{fact.fact_id}.md"
                path.write_text(serialize_fact(fact), encoding="utf-8")
                active_paths[fact.fact_id] = path
                active_facts[fact.fact_id] = fact

            lifecycle = store.v5_lifecycle()
            lineage_reconstruction = Mock(
                return_value=(active_facts, active_paths)
            )
            lineage_validation = Mock(return_value=None)
            lifecycle._lineage_snapshot = lineage_reconstruction  # type: ignore[method-assign]
            lifecycle._validate_lineage_snapshot = lineage_validation  # type: ignore[method-assign]
            inspection = RoundInspectionContext()
            before = self._tree_snapshot(root)

            with patch.object(store, "v5_lifecycle", return_value=lifecycle):
                observed_facts = store.facts(_inspection_context=inspection)
                observed_ids = store.fact_ids(_inspection_context=inspection)
                observed_individual = {
                    fact_id: store.get_fact(
                        fact_id,
                        _inspection_context=inspection,
                    )
                    for fact_id in observed_ids
                }

            after = self._tree_snapshot(root)
            self.assertEqual(observed_facts, active_facts)
            self.assertEqual(observed_ids, sorted(active_facts))
            self.assertEqual(observed_individual, active_facts)
            self.assertEqual(inspection.active_fact_paths, active_paths)
            self.assertEqual(inspection.active_facts, active_facts)
            self.assertEqual(before, after)

            # The active-Fact path map is derived by _lineage_snapshot.  Three
            # Facts and three public read APIs in one inspection still permit
            # exactly one such reconstruction and one validation.
            self.assertEqual(lineage_reconstruction.call_count, 1)
            self.assertEqual(lineage_validation.call_count, 1)

    def test_reentrant_validation_uses_one_provisional_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "project"
            store = MathGraphStore(root)
            store.initialize(
                project_id="chx-008-reentrant-active-fact",
                title="Reentrant active Fact validation fixture",
                workflow_evidence_version=5,
            )
            fact = Fact(
                problem_id=store.project_id(),
                author="fixture",
                predecessors=[],
                statement="[CLAIM:ROOT] The reentrant Fact holds.",
                proof="Fixture proof.",
            )
            fixture_dir = root / "inspection-fixtures"
            fixture_dir.mkdir()
            fact_path = fixture_dir / f"{fact.fact_id}.md"
            fact_path.write_text(serialize_fact(fact), encoding="utf-8")
            facts = {fact.fact_id: fact}
            paths = {fact.fact_id: fact_path}
            lifecycle = store.v5_lifecycle()
            inspection = RoundInspectionContext()
            provisional = Mock(return_value=(facts, paths))

            def reconstruct(*, _inspection_context: RoundInspectionContext):
                nested = lifecycle.active_fact_paths(
                    _inspection_context=_inspection_context
                )
                self.assertEqual(nested, paths)
                return facts, paths

            lifecycle._lineage_snapshot = reconstruct  # type: ignore[method-assign]
            lifecycle._provisional_active_fact_snapshot = provisional  # type: ignore[method-assign]
            lifecycle._validate_lineage_snapshot = Mock(return_value=None)  # type: ignore[method-assign]

            observed = lifecycle.active_fact_paths(
                _inspection_context=inspection
            )
            self.assertEqual(observed, paths)
            self.assertEqual(provisional.call_count, 1)
            self.assertFalse(inspection.active_fact_validation_in_progress)
            self.assertEqual(inspection.active_facts, facts)

    def test_provisional_projection_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "project"
            store = MathGraphStore(root)
            store.initialize(
                project_id="chx-008-projection-mismatch",
                title="Active Fact mismatch fixture",
                workflow_evidence_version=5,
            )
            fact = Fact(
                problem_id=store.project_id(),
                author="fixture",
                predecessors=[],
                statement="[CLAIM:ROOT] The validated Fact holds.",
                proof="Fixture proof.",
            )
            fixture_dir = root / "inspection-fixtures"
            fixture_dir.mkdir()
            fact_path = fixture_dir / f"{fact.fact_id}.md"
            fact_path.write_text(serialize_fact(fact), encoding="utf-8")
            facts = {fact.fact_id: fact}
            paths = {fact.fact_id: fact_path}
            lifecycle = store.v5_lifecycle()
            inspection = RoundInspectionContext()

            def reconstruct(*, _inspection_context: RoundInspectionContext):
                lifecycle.active_fact_paths(
                    _inspection_context=_inspection_context
                )
                return facts, paths

            lifecycle._lineage_snapshot = reconstruct  # type: ignore[method-assign]
            lifecycle._provisional_active_fact_snapshot = Mock(  # type: ignore[method-assign]
                return_value=({}, {})
            )
            lifecycle._validate_lineage_snapshot = Mock(return_value=None)  # type: ignore[method-assign]

            with self.assertRaisesRegex(
                ValueError,
                "provisional active-Fact paths drifted",
            ):
                lifecycle.active_fact_paths(
                    _inspection_context=inspection
                )
            self.assertIsNone(inspection.active_fact_paths)
            self.assertIsNone(inspection.active_facts)
            self.assertFalse(inspection.active_fact_validation_in_progress)

    def test_approved_computation_replay_keeps_one_inspection_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "project"
            store = MathGraphStore(root)
            store.initialize(
                project_id="chx-008-computation-context",
                title="Computation authority inspection context fixture",
                workflow_evidence_version=5,
            )
            lifecycle = store.v5_lifecycle()
            inspection = RoundInspectionContext()
            payload = {
                "revision": "chalxius-v5-approved-computation-execution-1",
                "design_round_id": "round-20260101T000000Z-00000000",
                "design_round_manifest_sha256": "a" * 64,
                "design_assignment_id": "a01-000000000000-compute",
                "design_task_card_sha256": "b" * 64,
                "design_return_sha256": "c" * 64,
                "design_research_id": "d" * 12,
                "design_record_sha256": "e" * 64,
                "design_artifacts": [],
                "supervision_round_id": "round-20260101T000001Z-00000000",
                "supervision_round_manifest_sha256": "f" * 64,
                "supervision_assignment_id": "a01-111111111111-refute",
                "supervision_task_card_sha256": "1" * 64,
                "supervision_return_sha256": "2" * 64,
                "supervision_research_id": "3" * 12,
                "supervision_record_sha256": "4" * 64,
                "disposition_research_id": "5" * 12,
                "disposition_record_sha256": "6" * 64,
                "disposition_status": "resolved_no_obstruction",
                "execution_policy": "execute_exact_supervised_source_and_dependencies",
                "repair_policy": "changed_code_requires_new_production_and_supervision",
                "pulse_policy": "not_used",
                "truth_effect": "none",
            }
            observed: list[RoundInspectionContext | None] = []

            def stop_after_first_round(
                round_id: str,
                *,
                _inspection_context: RoundInspectionContext | None = None,
            ) -> tuple[Path, dict[str, object]]:
                observed.append(_inspection_context)
                raise RuntimeError("context observed")

            with patch.object(
                lifecycle,
                "_round_manifest",
                side_effect=stop_after_first_round,
            ):
                with self.assertRaisesRegex(RuntimeError, "context observed"):
                    lifecycle._validate_approved_computation_execution_binding(
                        payload,
                        _inspection_context=inspection,
                    )
            self.assertEqual(observed, [inspection])


if __name__ == "__main__":
    unittest.main()
