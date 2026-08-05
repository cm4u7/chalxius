from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.store import MathGraphStore


class V5ExperimentTests(unittest.TestCase):
    def test_v5_task_local_experiment_replays_resumes_and_finalizes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = MathGraphStore(root)
            store.initialize(
                project_id="v5-experiment",
                title="V5 task-local experiment",
                workflow_evidence_version=5,
            )
            research = store.v5_lifecycle().add_research(
                {"kind": "computation", "claim": "Compute one exact value."},
                actor="main",
            )
            round_status = store.v5_lifecycle().create_round(
                workers=1,
                research_ids=[research["research_id"]],
                mode="compute",
            )
            assignment = round_status["assignments"][0]
            card = json.loads(
                Path(assignment["task_card_path"]).read_text(encoding="utf-8")
            )
            manifest = {
                "objective": "Compute the exact integer two.",
                "command": ["python3", "run.py"],
                "environment": {"implementation": "CPython", "version": "3"},
                "cost_model": {
                    "dominant_operation": "integer addition",
                    "estimated_cost": 1,
                    "expected_memory": "constant",
                    "parallelism": "none",
                    "complexity_model": {
                        "parameters": {"n": 1},
                        "asymptotic_time": "O(n)",
                        "asymptotic_space": "O(1)",
                        "estimated_operation_count": 1,
                        "estimate_basis": "one exact addition",
                        "intermediate_object_estimates": [],
                    },
                },
                "stages": ["exact"],
                "escalation_ladder": [
                    {
                        "stage_id": "exact",
                        "arithmetic": "integer",
                        "advance_condition": "stop after exact output",
                    }
                ],
                "checkpoint_policy": "after the exact stage",
                "resume_contract": {
                    "checkpoint_format": "json",
                    "resume_command": ["python3", "run.py", "--resume"],
                    "compatibility_fields": ["python"],
                    "deterministic_replay_required": True,
                },
                "truth_status": "exploration",
            }
            with store.v5_mutation_lock(command="experiment-start"):
                started = store.experiments().start(
                    task_card=card, manifest=manifest
                )
            directory = Path(started["directory"])
            result = directory / "result.json"
            result.write_text('{"value":2}\n', encoding="utf-8")
            with store.v5_mutation_lock(command="experiment-event"):
                store.experiments().event(
                    task_card=card,
                    experiment_id=started["experiment_id"],
                    payload={
                        "event": "stage_completed",
                        "stage": "exact",
                        "advance_condition_disposition": "exact output obtained",
                        "actual_intermediate_object_counts": [
                            {"object_kind": "integer", "count": 1}
                        ],
                    },
                )
            with store.v5_mutation_lock(command="experiment-observe"):
                notice = store.experiments().observe(
                    task_card=card,
                    actor_role="main",
                    payload={
                        "schema_version": 1,
                        "observation_id": "v5-observation-crossing",
                        "measurement_method": (
                            "host_monotonic_active_intervals_union"
                        ),
                        "active_intervals": [
                            {
                                "clock_epoch": "v5-host-epoch",
                                "lease_id": "v5-main",
                                "start_ns": 0,
                                "end_ns": 2_000_000_000_000,
                            }
                        ],
                        "actual_resources": {
                            "cpu_seconds": "host-observed",
                            "peak_rss_bytes": "host-observed",
                        },
                        "experimental_nature": (
                            "Exploratory mathematical computation."
                        ),
                        "progress": "Exact output obtained.",
                        "latest_checkpoint": "",
                        "importance_and_continuation_value": (
                            "The result checks one bounded exact value."
                        ),
                        "stopping_impact": (
                            "Stopping preserves completed checkpoints."
                        ),
                    },
                )
            self.assertEqual(notice["event"], "continuation_notice")
            with store.v5_mutation_lock(command="experiment-decision"):
                acknowledgement = store.experiments().decision(
                    task_card=card,
                    actor_role="main",
                    payload={
                        "schema_version": 1,
                        "decision_id": "v5-decision-1",
                        "notice_id": notice["notice_id"],
                        "decision": "continue",
                        "authority_kind": "user",
                        "authority_reference": "v5-host-ui-receipt",
                        "reason": "Finish the already bounded exact replay.",
                    },
                )
            self.assertEqual(acknowledgement["state"], "acknowledged")
            checkpoint = directory / "checkpoints" / "exact.json"
            checkpoint.write_text('{"value":2}\n', encoding="utf-8")
            compatibility_hash = sha256_json({"python": "3"})
            with store.v5_mutation_lock(command="experiment-event"):
                checkpoint_event_id = store.experiments().event(
                    task_card=card,
                    experiment_id=started["experiment_id"],
                    payload={
                        "event": "checkpoint",
                        "stage": "exact",
                        "checkpoint_path": "checkpoints/exact.json",
                        "checkpoint_sha256": sha256_bytes(
                            checkpoint.read_bytes()
                        ),
                        "checkpoint_bytes": checkpoint.stat().st_size,
                        "completed_stage": "exact",
                        "checkpoint_format_version": "1",
                        "resume_compatibility_hash": compatibility_hash,
                    },
                )
            with store.v5_mutation_lock(command="experiment-resume"):
                resumed = store.experiments().resume(
                    task_card=card,
                    experiment_id=started["experiment_id"],
                    checkpoint_event_id=checkpoint_event_id,
                    current_compatibility={"python": "3"},
                )
            self.assertEqual(resumed["status"], "resumed")
            with store.v5_mutation_lock(command="experiment-finalize"):
                receipt = store.experiments().finalize(
                    task_card=card,
                    experiment_id=started["experiment_id"],
                    selected_paths=["result.json"],
                )
            self.assertEqual(receipt["schema_version"], 5)
            self.assertEqual(receipt["truth_effect"], "none")
            self.assertTrue(Path(receipt["selected_outputs"][0]["path"]).is_relative_to(Path("rounds")))
            status = store.experiments().status(
                task_card=card, experiment_id=started["experiment_id"]
            )
            self.assertEqual(status["status"], "finalized")
            experiment_audit = store.experiments().audit_all()
            self.assertTrue(experiment_audit["ok"], experiment_audit["errors"])
            self.assertTrue(store.audit().current_ok, store.audit().errors)

            with store.v5_mutation_lock(command="work-unit-abort"):
                store.reasoning_modes().abort_work_unit(
                    round_id=round_status["round_id"],
                    actor="operator",
                    reason="Freeze the completed experiment fixture.",
                )
            before_retry = {
                path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes())
                for path in root.rglob("*")
                if path.is_file()
            }
            with self.assertRaisesRegex(ValueError, "explicitly aborted"):
                with store.v5_mutation_lock(command="experiment-finalize"):
                    store.experiments().finalize(
                        task_card=card,
                        experiment_id=started["experiment_id"],
                        selected_paths=["result.json"],
                    )
            self.assertEqual(
                before_retry,
                {
                    path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes())
                    for path in root.rglob("*")
                    if path.is_file()
                },
            )


if __name__ == "__main__":
    unittest.main()
