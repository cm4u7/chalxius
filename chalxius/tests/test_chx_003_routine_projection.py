from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mathgraph.cli import (
    _project_routine_v5_plan_result,
    build_parser,
    main as cli_main,
)
from mathgraph.roles import allowed_commands, allowed_commands_for_workflow
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import V5LifecycleManager


class Chx003RoutineProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        base = Path(self.temporary.name)
        self.v4_root = base / "v4"
        self.v5_root = base / "v5"
        self.v4 = MathGraphStore(self.v4_root)
        self.v4.initialize(
            project_id="chx-003-v4",
            title="CHX-003 V4 help compatibility",
            workflow_evidence_version=4,
        )
        self.v5 = MathGraphStore(self.v5_root)
        self.v5.initialize(
            project_id="chx-003-v5",
            title="CHX-003 routine projection",
            workflow_evidence_version=5,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _help(root: Path, role: str) -> str:
        output = StringIO()
        with redirect_stdout(output), unittest.TestCase().assertRaises(
            SystemExit
        ) as stopped:
            cli_main(
                [
                    "--root",
                    str(root),
                    "--role",
                    role,
                    "--help",
                ]
            )
        if stopped.exception.code != 0:
            raise AssertionError("top-level help did not exit successfully")
        return output.getvalue()

    @staticmethod
    def _run(root: Path, *arguments: str) -> tuple[int, dict, str]:
        output = StringIO()
        errors = StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = cli_main(
                ["--root", str(root), "--role", "main", *arguments]
            )
        payload = json.loads(output.getvalue()) if output.getvalue() else {}
        return code, payload, errors.getvalue()

    def test_v5_routine_help_hides_pulse_without_removing_capability(self) -> None:
        v5_main_help = self._help(self.v5_root, "main")
        for command in (
            "pulse-plan",
            "pulse-barrier",
            "pulse-void",
            "pulse-abort",
            "pulse-close",
            "pulse-status",
            "pulse-audit",
        ):
            self.assertNotIn(command, v5_main_help)

        v5_host_help = self._help(self.v5_root, "host")
        for command in ("pulse-dispatch", "pulse-status", "pulse-audit"):
            self.assertNotIn(command, v5_host_help)
        self.assertIn("verification-status", v5_host_help)

        v4_main_help = self._help(self.v4_root, "main")
        for command in (
            "pulse-plan",
            "pulse-barrier",
            "pulse-void",
            "pulse-abort",
            "pulse-close",
            "pulse-status",
            "pulse-audit",
        ):
            self.assertIn(command, v4_main_help)
        v4_host_help = self._help(self.v4_root, "host")
        for command in ("pulse-dispatch", "pulse-status", "pulse-audit"):
            self.assertIn(command, v4_host_help)

        for command in (
            "pulse-barrier",
            "pulse-void",
            "pulse-abort",
            "pulse-close",
            "pulse-status",
            "pulse-audit",
        ):
            self.assertIn(command, allowed_commands("main"))
        for command in ("pulse-dispatch", "pulse-status", "pulse-audit"):
            self.assertIn(
                command,
                allowed_commands_for_workflow("host", 5),
            )
        parsed = build_parser(
            help_role="main",
            help_workflow_evidence_version=5,
        ).parse_args(
            [
                "--root",
                str(self.v5_root),
                "--role",
                "main",
                "pulse-status",
                "bbpulse-existing-record",
            ]
        )
        self.assertEqual(parsed.command, "pulse-status")

    def test_plan_round_projects_only_inactive_routine_fields(self) -> None:
        research = self.v5.v5_lifecycle().add_research(
            {
                "kind": "proof_attempt",
                "claim": "Test the explicit CHX-003 routine projection.",
            },
            actor="main",
        )
        code, planned, errors = self._run(
            self.v5_root,
            "plan-round",
            "--workers",
            "1",
            "--memory-id",
            research["research_id"],
        )
        self.assertEqual(code, 0, errors)
        for key in (
            "blackboard_snapshot_id",
            "blackboard_snapshot_sha256",
            "independent_adverse_pairs",
            "frozen_aborted_count",
            "abort_id",
            "work_unit_abort",
            "round_closure_required",
        ):
            self.assertNotIn(key, planned)
        self.assertNotIn("pulse_policy", planned["research_cycle"])
        self.assertIsNone(planned["research_cycle"]["source_round_id"])
        self.assertEqual(planned["research_cycle"]["supervisor_scopes"], [])

        assignment = planned["assignments"][0]
        for key in (
            "blackboard_snapshot_id",
            "blackboard_snapshot_sha256",
            "independent_adverse_pair",
            "terminal_source_diagnostics",
            "terminalized_lease_marker",
        ):
            self.assertNotIn(key, assignment)
        self.assertIn("terminal_seal_revision", assignment)
        self.assertIn("writer_lease_id", assignment)

        round_id = planned["round_id"]
        manifest = self.v5._read_json(
            self.v5_root / "rounds" / round_id / "round.json"
        )
        self.assertIsNone(manifest["blackboard_snapshot_id"])
        self.assertIsNone(manifest["blackboard_snapshot_sha256"])
        self.assertEqual(manifest["independent_adverse_pairs"], [])
        self.assertEqual(manifest["research_cycle"]["pulse_policy"], "not_used")

        code, exact, errors = self._run(
            self.v5_root,
            "round-status",
            round_id,
        )
        self.assertEqual(code, 0, errors)
        self.assertIsNone(exact["blackboard_snapshot_id"])
        self.assertEqual(exact["independent_adverse_pairs"], [])
        self.assertEqual(exact["research_cycle"]["pulse_policy"], "not_used")
        self.assertEqual(exact["frozen_aborted_count"], 0)
        self.assertIsNone(exact["abort_id"])
        self.assertIsNone(exact["work_unit_abort"])
        self.assertFalse(exact["round_closure_required"])
        self.assertEqual(
            exact["assignments"][0]["terminal_source_diagnostics"], []
        )
        self.assertIsNone(
            exact["assignments"][0]["terminalized_lease_marker"]
        )

        expected_all = self.v5.v5_lifecycle().round_statuses()
        code, all_status, errors = self._run(
            self.v5_root,
            "round-status",
            "--all",
        )
        self.assertEqual(code, 0, errors)
        self.assertEqual(all_status, expected_all)

    def test_explicit_blackboard_and_abnormal_signals_remain_visible(self) -> None:
        space_id = next(
            node_id
            for node_id, node in self.v5.blackboard().current_nodes().items()
            if node["node_type"] == "space"
        )
        research = self.v5.v5_lifecycle().add_research(
            {
                "kind": "proof_attempt",
                "claim": "Use an explicit Blackboard workspace.",
                "blackboard_write_space_ids": [space_id],
            },
            actor="main",
        )
        code, planned, errors = self._run(
            self.v5_root,
            "plan-round",
            "--workers",
            "1",
            "--memory-id",
            research["research_id"],
        )
        self.assertEqual(code, 0, errors)
        self.assertIsNotNone(planned["blackboard_snapshot_id"])
        self.assertIsNotNone(planned["blackboard_snapshot_sha256"])
        self.assertEqual(
            planned["assignments"][0]["blackboard_snapshot_id"],
            planned["blackboard_snapshot_id"],
        )

        visible = {
            "pulse_policy": "historical_active",
            "blackboard_snapshot_id": "bbs-explicit",
            "blackboard_snapshot_sha256": "a" * 64,
            "blackboard_view": {
                "snapshot_id": "bbs-explicit",
                "snapshot_sha256": "a" * 64,
            },
            "abort_id": "abort-current",
            "work_unit_abort": {"reason": "explicit Main cancellation"},
            "frozen_aborted_count": 1,
            "independent_adverse_pair": {"pair_id": "pair-current"},
            "independent_adverse_pairs": [{"pair_id": "pair-current"}],
            "terminal_source_diagnostics": ["terminal:return:bytes_drifted"],
            "terminalized_lease_marker": "invalid",
            "round_closure_required": True,
            "unrelated_null": None,
            "unrelated_empty_list": [],
        }
        self.assertEqual(
            _project_routine_v5_plan_result(copy.deepcopy(visible)),
            visible,
        )

    def test_supervision_handler_uses_the_same_explicit_projector(self) -> None:
        inactive = {
            "round_id": "round-" + "b" * 16,
            "blackboard_snapshot_id": None,
            "blackboard_snapshot_sha256": None,
            "research_cycle": {
                "pulse_policy": "not_used",
                "source_component_id": None,
                "supervisor_scopes": [],
            },
            "independent_adverse_pairs": [],
            "abort_id": None,
            "work_unit_abort": None,
            "frozen_aborted_count": 0,
            "round_closure_required": False,
            "assignments": [
                {
                    "independent_adverse_pair": None,
                    "terminal_source_diagnostics": [],
                    "terminalized_lease_marker": "valid",
                    "unrelated_null": None,
                    "unrelated_empty_list": [],
                }
            ],
        }
        with patch.object(
            V5LifecycleManager,
            "create_supervision_round",
            return_value=copy.deepcopy(inactive),
        ):
            code, projected, errors = self._run(
                self.v5_root,
                "plan-supervision-round",
                "round-" + "a" * 16,
            )
        self.assertEqual(code, 0, errors)
        self.assertNotIn("blackboard_snapshot_id", projected)
        self.assertNotIn("pulse_policy", projected["research_cycle"])
        self.assertNotIn("abort_id", projected)
        self.assertNotIn("independent_adverse_pairs", projected)
        self.assertNotIn("round_closure_required", projected)
        assignment = projected["assignments"][0]
        self.assertNotIn("terminal_source_diagnostics", assignment)
        self.assertNotIn("terminalized_lease_marker", assignment)
        self.assertIsNone(assignment["unrelated_null"])
        self.assertEqual(assignment["unrelated_empty_list"], [])


if __name__ == "__main__":
    unittest.main()
