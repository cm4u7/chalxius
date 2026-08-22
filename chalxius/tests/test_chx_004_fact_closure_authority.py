"""CHX-004: typed closure reconstruction must receive exact closure authority."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import RoundInspectionContext


class CHX004FactClosureAuthorityTests(unittest.TestCase):
    @staticmethod
    def _store(root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="chx-104-fact-closure-authority",
            title="Typed Fact closure authority fixture",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _record(
        target_id: str,
        *,
        evidence_types: list[str],
    ) -> dict[str, object]:
        return {
            "research_id": "c" * 12,
            "dependencies": [target_id],
            "metadata": {
                "logic_signals": ["fact_closure_reconstruction"],
                "obligations": [
                    {
                        "obligation_id": "obl-closure-authority",
                        "description": "Classify the exact target closure.",
                        "required_artifact_roles": ["closure_map"],
                        "evidence_types": evidence_types,
                        "not_applicable_allowed": False,
                    }
                ]
            },
        }

    def test_typed_closure_evidence_expands_only_active_dependency_ancestry(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            store = self._store(root)
            lifecycle = store.v5_lifecycle()
            target_id = "a" * 16
            predecessor_id = "b" * 16
            target_path = root / "target.md"
            predecessor_path = root / "predecessor.md"
            target_path.write_text("target fixture\n", encoding="utf-8")
            predecessor_path.write_text("predecessor fixture\n", encoding="utf-8")
            active_paths = {
                target_id: target_path,
                predecessor_id: predecessor_path,
            }

            def parsed(text: str) -> SimpleNamespace:
                if text == "target fixture\n":
                    return SimpleNamespace(
                        fact_id=target_id,
                        predecessors=[predecessor_id],
                    )
                if text == "predecessor fixture\n":
                    return SimpleNamespace(
                        fact_id=predecessor_id,
                        predecessors=[],
                    )
                raise AssertionError("unexpected Fact bytes")

            def interface(
                fact_id: str,
                *,
                materialize: bool,
                _inspection_context: RoundInspectionContext,
            ) -> dict[str, str]:
                self.assertFalse(materialize)
                return {"fact_id": fact_id, "interface": "fixture"}

            with (
                patch.object(
                    lifecycle,
                    "active_fact_paths",
                    return_value=active_paths,
                ),
                patch.object(
                    lifecycle,
                    "revoked_fact_ids",
                    return_value=set(),
                ),
                patch(
                    "mathgraph.v5_lifecycle.parse_fact_markdown",
                    side_effect=parsed,
                ) as parse_fact,
                patch.object(
                    store,
                    "statement_interface",
                    side_effect=interface,
                ),
            ):
                snapshot = lifecycle._task_authority_snapshot(
                    self._record(
                        target_id,
                        evidence_types=["fact_closure_reconstruction"],
                    ),
                    _inspection_context=RoundInspectionContext(),
                )

            self.assertEqual(
                [item["fact_id"] for item in snapshot["fact_bindings"]],
                [target_id, predecessor_id],
            )
            self.assertEqual(parse_fact.call_count, 2)

    def test_ordinary_obligation_retains_direct_reference_only_authority(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            store = self._store(root)
            lifecycle = store.v5_lifecycle()
            target_id = "a" * 16
            target_path = root / "target.md"
            target_path.write_text("target fixture\n", encoding="utf-8")
            interface = {
                "fact_id": target_id,
                "interface": "fixture",
            }

            with (
                patch.object(
                    lifecycle,
                    "active_fact_paths",
                    side_effect=AssertionError(
                        "ordinary authority opened the broad Fact projection"
                    ),
                ) as active_fact_paths,
                patch.object(
                    lifecycle,
                    "_active_fact_premise_bindings",
                    return_value={
                        target_id: {
                            "path": target_path,
                            "statement_interface": interface,
                        }
                    },
                ) as premise_bindings,
                patch(
                    "mathgraph.v5_lifecycle.parse_fact_markdown",
                    side_effect=AssertionError(
                        "ordinary authority must not reconstruct a closure"
                    ),
                ) as parse_fact,
                patch.object(
                    store,
                    "statement_interface",
                    side_effect=AssertionError(
                        "ordinary authority reopened the broad interface reader"
                    ),
                ) as statement_interface,
            ):
                inspection = RoundInspectionContext()
                snapshot = lifecycle._task_authority_snapshot(
                    self._record(
                        target_id,
                        evidence_types=["bounded_argument"],
                    ),
                    _inspection_context=inspection,
                )

            premise_bindings.assert_called_once_with(
                {target_id},
                _inspection_context=inspection,
            )
            active_fact_paths.assert_not_called()
            statement_interface.assert_not_called()
            parse_fact.assert_not_called()
            self.assertEqual(
                [item["fact_id"] for item in snapshot["fact_bindings"]],
                [target_id],
            )

    def test_typed_closure_rejects_non_active_root_before_dispatch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary).resolve())
            lifecycle = store.v5_lifecycle()
            target_id = "a" * 16

            with (
                patch.object(lifecycle, "active_fact_paths", return_value={}),
                patch.object(
                    lifecycle,
                    "revoked_fact_ids",
                    return_value={target_id},
                ),
                patch(
                    "mathgraph.v5_lifecycle.parse_fact_markdown",
                ) as parse_fact,
                patch.object(store, "statement_interface") as interface,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "Fact-closure authority root is not active",
                ):
                    lifecycle._task_authority_snapshot(
                        self._record(
                            target_id,
                            evidence_types=["fact_closure_reconstruction"],
                        ),
                        _inspection_context=RoundInspectionContext(),
                    )

            parse_fact.assert_not_called()
            interface.assert_not_called()

    def test_typed_closure_rejects_non_active_predecessor(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            store = self._store(root)
            lifecycle = store.v5_lifecycle()
            target_id = "a" * 16
            predecessor_id = "b" * 16
            target_path = root / "target.md"
            target_path.write_text("target fixture\n", encoding="utf-8")

            with (
                patch.object(
                    lifecycle,
                    "active_fact_paths",
                    return_value={target_id: target_path},
                ),
                patch.object(
                    lifecycle,
                    "revoked_fact_ids",
                    return_value={predecessor_id},
                ),
                patch(
                    "mathgraph.v5_lifecycle.parse_fact_markdown",
                    return_value=SimpleNamespace(
                        fact_id=target_id,
                        predecessors=[predecessor_id],
                    ),
                ),
                patch.object(store, "statement_interface") as interface,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "Fact-closure authority predecessor is not active",
                ):
                    lifecycle._task_authority_snapshot(
                        self._record(
                            target_id,
                            evidence_types=["fact_closure_reconstruction"],
                        ),
                        _inspection_context=RoundInspectionContext(),
                    )

            interface.assert_not_called()


if __name__ == "__main__":
    unittest.main()
