from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from mathgraph.model import Fact
from mathgraph.orchestrator import (
    create_round,
    create_verifier_assignment,
    ingest_return,
    validate_return,
)
from mathgraph.protocol import (
    seal_ingestion_receipt_v4,
    validate_ingestion_receipt_v4,
)
from mathgraph.store import MathGraphStore


POLICY_REVISION = "mathgraph-0.3.0"


class V4ReleaseRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MathGraphStore._for_inherited_chalk_fixture(
            self.root
        )
        self.store.initialize(
            project_id="v4-release-regressions",
            title="V4 release regressions",
            workflow_evidence_version=4,
            reasoning_mode=None,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _planned_round(
        self,
        *,
        mode: str = "prove",
        kind: str = "direction",
        dependencies: list[str] | None = None,
    ) -> dict[str, Any]:
        if not self.store.reasoning_modes().status()["initialized"]:
            self.store.reasoning_modes().initialize(
                reasoning_mode="auto",
                actor="operator",
                reason="Enter the managed unified round fixture.",
                source_kind="legacy_chalk_v4_upgrade",
            )
        memory_id = self.store.memory_add(
            {
                "kind": kind,
                "claim": f"Exercise the {mode} release boundary.",
                "rationale": "Release-regression fixture.",
                "suggested_actions": [mode],
                "dependencies": list(dependencies or []),
            },
            actor="main",
        )
        return create_round(
            self.store,
            workers=1,
            mode=mode,
            memory_ids=[memory_id],
        )

    @staticmethod
    def _card_and_return_path(
        planned: dict[str, Any],
    ) -> tuple[dict[str, Any], Path, Path]:
        assignment = planned["assignments"][0]
        card_path = Path(assignment["task_card_path"])
        card = json.loads(card_path.read_text(encoding="utf-8"))
        return card, card_path, Path(assignment["return_path"])

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _file_inventory(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }

    def _fact_return(
        self,
        planned: dict[str, Any],
        *,
        predecessors: list[str] | None = None,
        predecessor_uses: list[dict[str, Any]] | None = None,
        proof: str = "Both sides are definitionally identical.",
    ) -> tuple[dict[str, Any], dict[str, Any], Path]:
        card, card_path, return_path = self._card_and_return_path(
            planned
        )
        payload = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION,
            "protocol": "mathgraph-agent-v4",
            "project_id": card["project_id"],
            "round_id": card["round_id"],
            "assignment_id": card["assignment_id"],
            "assignment_sha256": card["assignment_sha256"],
            "task_card_sha256": hashlib.sha256(
                card_path.read_bytes()
            ).hexdigest(),
            "blackboard_snapshot_sha256": card[
                "blackboard_snapshot_sha256"
            ],
            "worker": card["worker_id"],
            "memory_id": card["memory_id"],
            "mode": card["mode"],
            "outcome": "fact_submission",
            "obligation_ledger": [],
            "blackboard_graph_delta": {
                "base_snapshot_id": card["blackboard_view"][
                    "snapshot_id"
                ],
                "add_nodes": [],
                "add_edges": [],
            },
            "narrative_summary": "Release-regression fact.",
            "claim_relation": "proves",
            "statement": "[CLAIM:CHILD] The child identity holds.",
            "proof": proof,
            "predecessors": list(predecessors or []),
            "predecessor_uses": list(predecessor_uses or []),
            "quantifier_ledger": [],
            "convention_profile_ids": [],
            "computational_evidence": [],
            "terminology": [],
            "glossary_introduces": {},
            "external_refs": [],
            "elementary_uses": [],
            "intuition": "",
            "artifacts": [],
        }
        return payload, card, return_path

    def _admit_predecessor(self) -> str:
        fact = Fact(
            problem_id=self.store.project_id(),
            author="predecessor-worker",
            predecessors=[],
            statement=(
                "[CLAIM:PREDECESSOR] "
                "The predecessor identity holds."
            ),
            proof="Both sides are definitionally identical.",
        )
        fact_id = self.store.submit(
            fact,
            worker="predecessor-worker",
        )
        verifier = create_verifier_assignment(self.store, fact_id)
        review_path = self.store.record_review(
            {
                "schema_version": 4,
                "policy_revision": POLICY_REVISION,
                "fact_id": fact_id,
                "submission_sha256": verifier["submission_sha256"],
                "bundle_sha256": verifier["bundle_sha256"],
                "verdict": "correct",
                "findings": [],
                "prior_review_dispositions": [],
                "reviewer": "fresh-release-regression-verifier",
                "host_attestation": {
                    "host": "unittest",
                    "agent_id": (
                        "fresh-release-regression-verifier"
                    ),
                    "isolation": "fresh_context",
                    "fork_turns": "none",
                    "allowed_bundle_sha256": verifier[
                        "bundle_sha256"
                    ],
                },
            }
        )
        self.store.admit(
            fact_id,
            review_id=review_path.stem,
            gateway="release-regression-gateway",
        )
        return fact_id

    def test_validate_return_does_not_materialize_missing_interface(
        self,
    ) -> None:
        predecessor_id = self._admit_predecessor()
        interface = self.store.statement_interface(predecessor_id)
        clause = interface["clauses"][0]
        planned = self._planned_round(
            dependencies=[predecessor_id],
        )
        anchor = (
            f"[USE:{predecessor_id}:"
            f"{clause['clause_id']}:release-regression]"
        )
        payload, card, return_path = self._fact_return(
            planned,
            predecessors=[predecessor_id],
            predecessor_uses=[
                {
                    "fact_id": predecessor_id,
                    "clause_id": clause["clause_id"],
                    "use_anchor": anchor,
                    "used_conclusion": clause["text"],
                    "hypothesis_witnesses": [],
                    "convention_bridge": None,
                }
            ],
            proof=f"Apply the admitted interface. {anchor}",
        )
        self._write_json(return_path, payload)

        interface_path = (
            self.store.interfaces_dir / f"{predecessor_id}.json"
        )
        self.assertTrue(interface_path.is_file())
        interface_path.unlink()
        before = self._file_inventory(self.root)

        validated = validate_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
        )

        self.assertEqual(validated["outcome"], "fact_submission")
        self.assertEqual(before, self._file_inventory(self.root))
        self.assertFalse(
            interface_path.exists(),
            "validate-return must reconstruct a missing interface "
            "in memory without materializing a projection",
        )

    def test_different_clock_epochs_use_one_physical_interval_union(
        self,
    ) -> None:
        planned = self._planned_round(
            mode="compute",
            kind="computation",
        )
        card, _, _ = self._card_and_return_path(planned)
        observed = self.store.experiments().observe(
            task_card=card,
            actor_role="main",
            payload={
                "schema_version": 1,
                "observation_id": "obs-cross-epoch-overlap",
                "measurement_method": (
                    "host_monotonic_active_intervals_union"
                ),
                "active_intervals": [
                    {
                        "clock_epoch": "host-epoch-a",
                        "lease_id": "worker-a",
                        "start_ns": 0,
                        "end_ns": 900_000_000_000,
                    },
                    {
                        "clock_epoch": "host-epoch-b",
                        "lease_id": "worker-b",
                        "start_ns": 300_000_000_000,
                        "end_ns": 1_000_000_000_000,
                    },
                ],
                "actual_resources": {
                    "cpu_seconds": "host-observed",
                    "peak_rss_bytes": "host-observed",
                },
                "experimental_nature": (
                    "Exploratory mathematical computation."
                ),
                "progress": "Two overlapping worker leases are active.",
                "latest_checkpoint": "",
                "importance_and_continuation_value": (
                    "The result tests the task-clock union."
                ),
                "stopping_impact": (
                    "Stopping preserves completed checkpoints."
                ),
            },
        )
        self.assertEqual(
            {
                "actual_cumulative_task_seconds": observed[
                    "actual_cumulative_task_seconds"
                ],
                "event": observed["event"],
                "state": observed["state"],
            },
            {
                "actual_cumulative_task_seconds": 1000,
                "event": "observation",
                "state": "pre_threshold",
            },
        )

    def test_foreign_project_receipt_is_invalid_and_not_visible(
        self,
    ) -> None:
        planned = self._planned_round()
        payload, card, return_path = self._fact_return(planned)
        self._write_json(return_path, payload)
        validated = validate_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
        )
        receipt = ingest_return(
            self.store,
            planned["round_id"],
            card["assignment_id"],
            worker_final_sha256=validated["return_sha256"],
        )
        fact_id = receipt["submission_id"]
        self.assertEqual(
            self.store.submission(fact_id)["fact_id"],
            fact_id,
        )

        receipt_path = return_path.with_suffix(".receipt.json")
        foreign_receipt = {
            key: value
            for key, value in receipt.items()
            if key != "ingestion_sha256"
        }
        foreign_receipt["project_id"] = "foreign-v4-project"
        foreign_receipt = seal_ingestion_receipt_v4(
            foreign_receipt
        )
        validate_ingestion_receipt_v4(foreign_receipt)
        self._write_json(receipt_path, foreign_receipt)

        try:
            self.store.submission(fact_id)
        except (KeyError, ValueError):
            visibility = "hidden"
        else:
            visibility = "visible"
        report = self.store.audit()
        self.assertEqual(
            {
                "audit_current_ok": report.current_ok,
                "submission_visibility": visibility,
            },
            {
                "audit_current_ok": False,
                "submission_visibility": "hidden",
            },
            msg=f"audit errors: {report.errors}",
        )


if __name__ == "__main__":
    unittest.main()
