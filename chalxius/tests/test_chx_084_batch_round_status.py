from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mathgraph.cli import main as cli_main
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import V5LifecycleManager


class CHX084BatchRoundStatusTests(unittest.TestCase):
    def _store(self, root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="chx-084-batch-round-status",
            title="CHX-084 batch round status",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _plan_round(store: MathGraphStore, claim: str) -> dict[str, object]:
        lifecycle = store.v5_lifecycle()
        research = lifecycle.add_research(
            {"kind": "direction", "claim": claim},
            actor="main",
        )
        return lifecycle.create_round(
            workers=1,
            research_ids=[research["research_id"]],
        )

    @staticmethod
    def _abort_round(store: MathGraphStore, round_id: str) -> None:
        with store.v5_mutation_lock(command="work-unit-abort"):
            store.reasoning_modes().abort_work_unit(
                round_id=round_id,
                actor="main",
                reason="Freeze this fixture as terminal historical work.",
            )

    def test_round_statuses_has_canonical_states_equal_to_single_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            with patch.object(
                V5LifecycleManager,
                "_validate_bound_runtime_binding",
                return_value={},
            ):
                first = self._plan_round(store, "Keep the first fixture active.")
                second = self._plan_round(store, "Abort the second fixture.")
                second_id = str(second["round_id"])
                self._abort_round(store, second_id)

                lifecycle = store.v5_lifecycle()
                round_ids = [str(first["round_id"]), second_id]
                expected = {
                    round_id: lifecycle.round_status(round_id)["work_unit_state"]
                    for round_id in round_ids
                }

                batch = lifecycle.round_statuses()

            self.assertEqual(batch["round_states"], dict(sorted(expected.items())))
            self.assertEqual(
                list(batch["round_states"]),
                sorted(round_ids),
                "round_states must have deterministic canonical round-id order",
            )

    def test_round_status_all_cli_returns_the_authoritative_batch_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            store = self._store(root)
            with patch.object(
                V5LifecycleManager,
                "_validate_bound_runtime_binding",
                return_value={},
            ):
                planned = self._plan_round(
                    store, "Expose this round through the CLI."
                )
                round_id = str(planned["round_id"])

                stdout = StringIO()
                stderr = StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = cli_main(
                        [
                            "--root",
                            str(root),
                            "--role",
                            "main",
                            "round-status",
                            "--all",
                        ]
                    )

            self.assertEqual(code, 0, stderr.getvalue())
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["round_states"], {round_id: "active"})
            self.assertEqual(list(payload["round_states"]), [round_id])

    def test_batch_does_not_require_historical_runtime_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            with patch.object(
                V5LifecycleManager,
                "_validate_bound_runtime_binding",
                return_value={},
            ):
                planned = [
                    self._plan_round(
                        store, f"Historical runtime fixture {index}."
                    )
                    for index in range(2)
                ]
            for item in planned:
                self._abort_round(store, str(item["round_id"]))

            lifecycle = store.v5_lifecycle()
            with patch.object(
                V5LifecycleManager,
                "_validate_bound_runtime_binding",
                return_value={},
            ) as validator:
                batch = lifecycle.round_statuses()

            self.assertEqual(
                set(batch["round_states"].values()),
                {"aborted"},
            )
            self.assertEqual(
                validator.call_count,
                0,
                "historical runtime identity is diagnostic provenance only and "
                "must not gate direct graph operations",
            )

    def test_active_round_is_not_filtered_from_cutover_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            with patch.object(
                V5LifecycleManager,
                "_validate_bound_runtime_binding",
                return_value={},
            ):
                planned = self._plan_round(
                    store,
                    "Leave this fixture active so protected cutover must reject it.",
                )
                round_id = str(planned["round_id"])

                batch = store.v5_lifecycle().round_statuses()

            self.assertIn(round_id, batch["round_states"])
            self.assertEqual(batch["round_states"][round_id], "active")
            self.assertNotIn(
                batch["round_states"][round_id],
                {"aborted", "completed"},
            )


if __name__ == "__main__":
    unittest.main()
