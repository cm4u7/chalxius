"""CHX-105/106: Experiment applicability uses a canonical validated binding."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import RoundInspectionContext
from mathgraph.v5_experiments import V5ExperimentManager


class _LifecycleStub:
    def __init__(self, round_dir: Path, assignments: list[dict[str, str]]) -> None:
        self.round_dir = round_dir
        self.manifest = {"assignments": assignments}
        self.round_calls = 0
        self.contexts: list[RoundInspectionContext] = []

    def _round_manifest(
        self,
        round_id: str,
        *,
        _inspection_context: RoundInspectionContext,
    ) -> tuple[Path, dict[str, object]]:
        self.round_calls += 1
        self.contexts.append(_inspection_context)
        if self.round_dir.name != round_id:
            raise ValueError("unexpected round")
        return self.round_dir, self.manifest

    @staticmethod
    def _assignment(
        manifest: dict[str, object], assignment_id: str
    ) -> dict[str, str]:
        matches = [
            item
            for item in manifest["assignments"]  # type: ignore[index]
            if item["assignment_id"] == assignment_id
        ]
        if len(matches) != 1:
            raise ValueError("unexpected assignment")
        return matches[0]


class CHX105ExperimentApplicabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="chx-105-experiment-applicability",
            title="Experiment applicability fixture",
            workflow_evidence_version=5,
        )
        self.round_id = "round-20260805T000000Z-abcdef12"
        self.round_dir = self.store.rounds_dir / self.round_id
        self.assignment_id = "a01-abcdef123456-prove"

    def _card(
        self,
        *,
        assignment_id: str | None = None,
        work_dir_relpath: str = "work-units/fixture",
    ) -> tuple[Path, dict[str, object], dict[str, str]]:
        assignment_id = assignment_id or self.assignment_id
        card_path = self.round_dir / "task-cards" / f"{assignment_id}.json"
        card_path.parent.mkdir(parents=True, exist_ok=True)
        card = {
            "round_id": self.round_id,
            "assignment_id": assignment_id,
            "artifact_capability": {"work_dir_relpath": work_dir_relpath},
        }
        card_path.write_text(
            json.dumps(card, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        assignment = {
            "assignment_id": assignment_id,
            "task_card_relpath": card_path.relative_to(self.root).as_posix(),
            "work_dir_relpath": work_dir_relpath,
        }
        return card_path, card, assignment

    def _manager(self) -> V5ExperimentManager:
        return V5ExperimentManager(
            self.store,
            mutation_lock=self.store.mutation_lock,
            read_lock=self.store.read_lock,
        )

    def _audit(
        self,
        assignments: list[dict[str, str]],
        *,
        inspection: RoundInspectionContext | None = None,
    ) -> tuple[dict[str, object], _LifecycleStub]:
        lifecycle = _LifecycleStub(self.round_dir, assignments)
        with patch.object(
            self.store,
            "v5_lifecycle",
            return_value=lifecycle,
        ):
            report = self._manager().audit_all(
                _inspection_context=inspection
            )
        return report, lifecycle

    def test_absent_experiment_root_uses_one_canonical_round_binding(self) -> None:
        _, _, assignment = self._card()
        report, lifecycle = self._audit([assignment])

        self.assertTrue(report["ok"])
        self.assertEqual(report["experiment_count"], 0)
        self.assertEqual(lifecycle.round_calls, 1)

    def test_present_experiment_root_uses_the_owning_context(self) -> None:
        _, _, assignment = self._card()
        (self.root / assignment["work_dir_relpath"] / "experiments").mkdir(
            parents=True
        )
        inspection = RoundInspectionContext()
        with patch.object(
            V5ExperimentManager,
            "_bind_task_card_view_from_assignment",
            autospec=True,
        ) as bind_view:
            report, lifecycle = self._audit(
                [assignment], inspection=inspection
            )

        self.assertTrue(report["ok"])
        self.assertEqual(report["experiment_count"], 0)
        self.assertEqual(lifecycle.round_calls, 1)
        self.assertEqual(lifecycle.contexts, [inspection])
        bind_view.assert_called_once()

    def test_raw_card_path_drift_cannot_hide_canonical_state(self) -> None:
        card_path, card, assignment = self._card()
        (self.root / assignment["work_dir_relpath"] / "experiments").mkdir(
            parents=True
        )
        card["artifact_capability"] = {
            "work_dir_relpath": "work-units/other"
        }
        card_path.write_text(
            json.dumps(card, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report, _ = self._audit([assignment])

        self.assertFalse(report["ok"])
        self.assertIn("differs from the frozen assignment", report["errors"][0])

    def test_internal_symlink_component_fails_closed(self) -> None:
        _, _, assignment = self._card(work_dir_relpath="work-units/link")
        real = self.root / "work-units/real"
        real.mkdir(parents=True)
        (real / "experiments").mkdir()
        (self.root / "work-units/link").symlink_to(real, target_is_directory=True)
        report, _ = self._audit([assignment])

        self.assertFalse(report["ok"])
        self.assertIn("traverses a symlink", report["errors"][0])

    def test_multiple_cards_in_one_round_validate_the_round_once(self) -> None:
        _, _, first = self._card()
        _, _, second = self._card(
            assignment_id="a02-fedcba654321-refute",
            work_dir_relpath="work-units/second",
        )
        report, lifecycle = self._audit([first, second])

        self.assertTrue(report["ok"])
        self.assertEqual(lifecycle.round_calls, 1)


if __name__ == "__main__":
    unittest.main()
