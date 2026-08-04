from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathgraph import runtime_cutover


class CHX084RuntimeCutoverBatchTests(unittest.TestCase):
    ROUND_IDS = (
        "round-20260101T000000Z-00000001",
        "round-20260101T000001Z-00000002",
        "round-20260101T000002Z-00000003",
    )

    @classmethod
    def _project(cls, root: Path) -> Path:
        project = root / "protected-project"
        for round_id in cls.ROUND_IDS:
            (project / "rounds" / round_id).mkdir(parents=True)
        return project.resolve()

    @classmethod
    def _terminal_states(cls) -> dict[str, str]:
        return {
            round_id: ("aborted" if index == 1 else "completed")
            for index, round_id in enumerate(cls.ROUND_IDS)
        }

    def test_deep_validation_uses_one_audit_batch_for_many_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            project = self._project(base)
            runtime = base / "candidate-runtime"
            runtime.mkdir()
            archive = base / "runtime-archive"
            round_states = self._terminal_states()

            with (
                patch.object(runtime_cutover, "_round_bindings", return_value=[]),
                patch.object(
                    runtime_cutover,
                    "_run_json_command",
                    return_value={
                        "current_ok": True,
                        "round_states": round_states,
                    },
                ) as run_json,
            ):
                result = runtime_cutover.validate_protected_projects(
                    runtime,
                    [project],
                    archive_root=archive,
                )

            self.assertEqual(run_json.call_count, 1)
            call = run_json.call_args
            self.assertEqual(
                call.args,
                (
                    runtime,
                    [
                        "--root",
                        str(project),
                        "--role",
                        "operator",
                        "audit",
                    ],
                ),
            )
            self.assertNotIn("round-status", call.args[1])
            self.assertEqual(call.kwargs["archive_root"], archive)
            self.assertEqual(
                call.kwargs["phase"],
                f"deep_project_audit:{project.name}",
            )
            self.assertEqual(result["projects"][0]["round_states"], round_states)
            self.assertTrue(result["projects"][0]["audit_current_ok"])
            self.assertEqual(result["candidate_subprocess_count"], 1)

    def test_bounded_validation_reuses_exact_snapshot_without_candidate_process(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            project = self._project(base)
            runtime = base / "candidate-runtime"
            runtime.mkdir()
            archive = base / "runtime-archive"
            round_states = self._terminal_states()
            snapshot = runtime_cutover._project_state_snapshot(project)
            prior_project = {
                "project_root": str(project),
                "project_state": snapshot,
                "round_states": round_states,
                "audit_evidence_mode": "single_prevalidated_deep_audit",
                "audit_current_ok": True,
            }

            with (
                patch.object(runtime_cutover, "_round_bindings", return_value=[]),
                patch.object(
                    runtime_cutover,
                    "_run_json_command",
                    side_effect=AssertionError(
                        "exact snapshot reuse must not launch candidate runtime"
                    ),
                ) as run_json,
            ):
                result = runtime_cutover.validate_protected_projects_bounded(
                    runtime,
                    [project],
                    archive_root=archive,
                    prior_audit_projects=[prior_project],
                    prior_audit_runtime_bindings=[],
                    project_snapshots={str(project): snapshot},
                )

            run_json.assert_not_called()
            self.assertEqual(result["projects"][0]["round_states"], round_states)
            self.assertEqual(result["candidate_subprocess_count"], 0)
            self.assertEqual(
                result["projects"][0]["audit_evidence_mode"],
                "exact_prior_deep_audit_snapshot_reuse",
            )

    def test_active_missing_and_extra_round_maps_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            project = self._project(base)
            runtime = base / "candidate-runtime"
            runtime.mkdir()
            archive = base / "runtime-archive"
            terminal = self._terminal_states()
            active = dict(terminal)
            active[self.ROUND_IDS[1]] = "active"
            missing = {
                round_id: state
                for round_id, state in terminal.items()
                if round_id != self.ROUND_IDS[1]
            }
            extra = {
                **terminal,
                "round-20260101T000003Z-00000004": "completed",
            }
            cases = (
                ("active", active, "not terminal"),
                ("missing", missing, "malformed or incomplete"),
                ("extra", extra, "malformed or incomplete"),
            )
            for label, round_states, message in cases:
                with self.subTest(validator="deep", case=label):
                    with (
                        patch.object(runtime_cutover, "_round_bindings", return_value=[]),
                        patch.object(
                            runtime_cutover,
                            "_run_json_command",
                            return_value={
                                "round_states": round_states,
                                "current_ok": True,
                            },
                        ) as run_json,
                    ):
                        with self.assertRaisesRegex(ValueError, message):
                            runtime_cutover.validate_protected_projects(
                                runtime,
                                [project],
                                archive_root=archive,
                            )
                    self.assertEqual(run_json.call_count, 1)

                with self.subTest(validator="bounded", case=label):
                    snapshot = runtime_cutover._project_state_snapshot(project)
                    prior_project = {
                        "project_root": str(project),
                        "project_state": snapshot,
                        "round_states": round_states,
                        "audit_evidence_mode": "single_prevalidated_deep_audit",
                        "audit_current_ok": True,
                    }
                    with patch.object(
                        runtime_cutover,
                        "_run_json_command",
                        side_effect=AssertionError("bounded rejection must stay local"),
                    ) as run_json:
                        with self.assertRaisesRegex(ValueError, "terminal witness drifted"):
                            runtime_cutover.validate_protected_projects_bounded(
                                runtime,
                                [project],
                                archive_root=archive,
                                prior_audit_projects=[prior_project],
                                prior_audit_runtime_bindings=[],
                                project_snapshots={str(project): snapshot},
                            )
                    run_json.assert_not_called()

    def test_runtime_command_timeout_reports_phase_and_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            runtime = base / "candidate-runtime"
            executable = runtime / "scripts" / "mgraph"
            executable.parent.mkdir(parents=True)
            executable.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            archive = base / "runtime-archive"
            phase = "deep_project_audit:protected-project"

            with patch.object(
                runtime_cutover.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(
                    cmd=[str(executable), "audit"],
                    timeout=17,
                ),
            ) as run:
                with self.assertRaisesRegex(
                    ValueError,
                    r"deep_project_audit:protected-project after 17 seconds",
                ) as raised:
                    runtime_cutover._run_json_command(
                        runtime,
                        ["audit"],
                        archive_root=archive,
                        phase=phase,
                        timeout_seconds=17,
                    )

            self.assertIsInstance(raised.exception.__cause__, subprocess.TimeoutExpired)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.kwargs["timeout"], 17)


if __name__ == "__main__":
    unittest.main()
