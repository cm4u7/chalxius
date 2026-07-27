from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import mathgraph.fact_bundles as expert_policy
from mathgraph.adoption import (
    _legacy_estimate_gated_adoption_plan,
    build_adoption_plan,
    compact_adoption_binding,
)
from mathgraph.cli import main as cli_main
from mathgraph.computations import (
    ExperimentManager,
    validate_required_experiment_receipt,
)
from mathgraph.contracts import (
    POLICY_REVISION_V4,
    sha256_bytes,
    sha256_json,
)
from mathgraph.fact_bundles import build_claim_card
from mathgraph.model import Fact
from mathgraph.orchestrator import create_round
from mathgraph.protocol import validate_task_card
from mathgraph.store import MathGraphStore
from mathgraph.worker_returns import validate_worker_return


LEGACY_ACTIVE_REJECTION = (
    r"(?i)historical.*estimate.*read.?only.*replan.*current policy"
)


def workload_profile(
    *,
    audience: str = "internal",
    activity: str = "computation",
    wall_seconds: int | None = 301,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy_revision": POLICY_REVISION_V4,
        "activity": activity,
        "audience": audience,
        "computation": {
            "role": "corroborative",
            "estimated_wall_seconds": wall_seconds,
            "stage_count": 1,
            "resume_required": False,
        },
        "fact_output": {
            "candidate_count": 1,
            "internal_dependency_count": 0,
            "atomic_visibility_required": False,
        },
        "semantics": {
            "source_claim": False,
            "convention_sensitive": False,
            "quantifier_sensitive": False,
            "terminology_sensitive": False,
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> bytes:
    rendered = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(rendered)
    return rendered


def file_inventory(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


class ExpertLintReceiptClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="expert-policy-closure",
            title="Expert policy closure",
            workflow_evidence_version=4,
        )
        fact = Fact(
            problem_id="expert-policy-closure",
            author="worker",
            predecessors=[],
            statement="[CLAIM:MAIN] Exact receipt theorem.",
            proof="Proof.",
        )
        self.card = build_claim_card(
            fact=fact,
            audience="expert",
            literal_source_claim="Literal exact source claim.",
            researcher_variant="Exact researcher variant.",
            variant_diff=[],
            source_locator="Theorem 4.2",
            convention_profile="conv-exact: residue_orientation=positive",
            reproduction_bundle=[],
        )
        self.card_path = self.root / "claim-card.json"
        self.card_bytes = write_json(self.card_path, self.card)
        self.draft_bytes = (
            "\n".join(
                [
                    self.card["literal_source_claim"],
                    self.card["researcher_variant"],
                    self.card["source_locator"],
                    self.card["convention_profile"],
                    self.card["admitted_conclusion"],
                    "AI assistance: AI assisted drafting and protocol checks.",
                ]
            )
            + "\n"
        ).encode("utf-8")
        self.draft_path = self.root / "expert.md"
        self.draft_path.write_bytes(self.draft_bytes)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _api(self, name: str) -> Callable[..., dict[str, Any]]:
        function = getattr(expert_policy, name, None)
        self.assertTrue(
            callable(function),
            f"mathgraph.fact_bundles must expose {name}",
        )
        return function

    def _lint(
        self,
        *,
        document_path: Path,
        receipt_output: str | None,
    ) -> tuple[int, str, str]:
        command = [
            "--root",
            str(self.root),
            "--role",
            "main",
            "lint-expert-document",
            "--input",
            str(document_path),
            "--claim-card",
            str(self.card_path),
        ]
        if receipt_output is not None:
            command.extend(["--receipt-output", receipt_output])
        output = io.StringIO()
        error = io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            try:
                status = cli_main(command)
            except SystemExit as exc:
                self.fail(
                    "lint-expert-document must accept the receipt persistence "
                    f"contract; argparse exited with {exc.code}"
                )
        return status, output.getvalue(), error.getvalue()

    def test_lint_receipt_is_persisted_write_once_and_validates_exact_bytes(
        self,
    ) -> None:
        relative = (
            "reports/expert-lint-receipts/explicit-receipt.json"
        )
        receipt_path = self.root / relative
        status, output, error = self._lint(
            document_path=self.draft_path,
            receipt_output=relative,
        )
        self.assertEqual(status, 0, error)
        self.assertTrue(receipt_path.is_file())
        receipt_bytes = receipt_path.read_bytes()
        receipt = json.loads(receipt_bytes)
        self.assertEqual(json.loads(output), receipt)
        self.assertTrue(receipt["ok"])
        self.assertEqual(receipt["errors"], [])
        self.assertEqual(receipt["project_id"], self.store.project_id())
        self.assertEqual(receipt["audience"], "expert")
        self.assertEqual(
            receipt["draft_sha256"],
            sha256_bytes(self.draft_bytes),
        )
        self.assertEqual(
            receipt["claim_card_bytes_sha256"],
            sha256_bytes(self.card_bytes),
        )
        self.assertEqual(
            receipt["claim_card_sha256"],
            self.card["claim_card_sha256"],
        )
        self.assertTrue(receipt["linter_revision"])
        semantic = {
            key: value
            for key, value in receipt.items()
            if key != "lint_receipt_sha256"
        }
        self.assertEqual(
            receipt["lint_receipt_sha256"],
            sha256_json(semantic),
        )

        validate_receipt = self._api("validate_expert_lint_receipt")
        validated = validate_receipt(
            receipt,
            draft_bytes=self.draft_bytes,
            claim_card_bytes=self.card_bytes,
        )
        self.assertEqual(
            validated["lint_receipt_sha256"],
            receipt["lint_receipt_sha256"],
        )

        replay_status, replay_output, replay_error = self._lint(
            document_path=self.draft_path,
            receipt_output=relative,
        )
        self.assertEqual(replay_status, 0, replay_error)
        self.assertEqual(json.loads(replay_output), receipt)
        self.assertEqual(receipt_path.read_bytes(), receipt_bytes)

        self.draft_path.write_bytes(self.draft_bytes + b"Additional note.\n")
        collision_status, _, collision_error = self._lint(
            document_path=self.draft_path,
            receipt_output=relative,
        )
        self.assertEqual(collision_status, 2)
        self.assertRegex(
            collision_error,
            r"(?i)immutable|write.?once|collision",
        )
        self.assertEqual(receipt_path.read_bytes(), receipt_bytes)

        with self.assertRaisesRegex(ValueError, r"(?i)draft|input|hash"):
            validate_receipt(
                receipt,
                draft_bytes=self.draft_bytes + b"\n",
                claim_card_bytes=self.card_bytes,
            )
        reformatted_card_bytes = json.dumps(
            self.card,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        self.assertNotEqual(reformatted_card_bytes, self.card_bytes)
        with self.assertRaisesRegex(
            ValueError,
            r"(?i)claim.card.*bytes|claim.card.*hash",
        ):
            validate_receipt(
                receipt,
                draft_bytes=self.draft_bytes,
                claim_card_bytes=reformatted_card_bytes,
            )

    def test_lint_without_output_uses_one_deterministic_default_receipt(
        self,
    ) -> None:
        status, output, error = self._lint(
            document_path=self.draft_path,
            receipt_output=None,
        )
        self.assertEqual(status, 0, error)
        receipt = json.loads(output)
        receipt_directory = (
            self.root / "reports" / "expert-lint-receipts"
        )
        receipt_files = sorted(receipt_directory.glob("*.json"))
        self.assertEqual(len(receipt_files), 1)
        first_path = receipt_files[0]
        first_bytes = first_path.read_bytes()
        self.assertEqual(json.loads(first_bytes), receipt)

        replay_status, replay_output, replay_error = self._lint(
            document_path=self.draft_path,
            receipt_output=None,
        )
        self.assertEqual(replay_status, 0, replay_error)
        self.assertEqual(json.loads(replay_output), receipt)
        self.assertEqual(
            sorted(receipt_directory.glob("*.json")),
            [first_path],
        )
        self.assertEqual(first_path.read_bytes(), first_bytes)

    def test_required_export_lint_rejects_missing_failed_and_stale_receipts(
        self,
    ) -> None:
        readiness = self._api(
            "validate_expert_communication_readiness"
        )
        adoption_binding = compact_adoption_binding(
            build_adoption_plan(
                workload_profile(
                    audience="expert",
                    activity="export",
                    wall_seconds=0,
                )
            )
        )
        self.assertEqual(
            adoption_binding["feature_statuses"][
                "terminology_export_lint"
            ],
            "required",
        )

        with self.assertRaisesRegex(
            ValueError,
            (
                r"(?i)lint receipt.*required|missing.*lint receipt|"
                r"terminology_export_lint.*required.*valid receipt"
            ),
        ):
            readiness(
                adoption_binding=adoption_binding,
                lint_receipt=None,
                draft_bytes=self.draft_bytes,
                claim_card_bytes=self.card_bytes,
            )

        failed_path = self.root / "failed.md"
        failed_bytes = b"AI assistance: AI assisted drafting.\n"
        failed_path.write_bytes(failed_bytes)
        failed_status, failed_output, failed_error = self._lint(
            document_path=failed_path,
            receipt_output=(
                "reports/expert-lint-receipts/failed-receipt.json"
            ),
        )
        self.assertEqual(failed_status, 2, failed_error)
        failed_receipt = json.loads(failed_output)
        self.assertFalse(failed_receipt["ok"])
        self.assertTrue(failed_receipt["errors"])
        with self.assertRaisesRegex(
            ValueError,
            r"(?i)failed|errors|not ready",
        ):
            readiness(
                adoption_binding=adoption_binding,
                lint_receipt=failed_receipt,
                draft_bytes=failed_bytes,
                claim_card_bytes=self.card_bytes,
            )

        valid_status, valid_output, valid_error = self._lint(
            document_path=self.draft_path,
            receipt_output=(
                "reports/expert-lint-receipts/valid-receipt.json"
            ),
        )
        self.assertEqual(valid_status, 0, valid_error)
        valid_receipt = json.loads(valid_output)
        with self.assertRaisesRegex(
            ValueError,
            r"(?i)stale|draft|input|hash",
        ):
            readiness(
                adoption_binding=adoption_binding,
                lint_receipt=valid_receipt,
                draft_bytes=self.draft_bytes + b"\n",
                claim_card_bytes=self.card_bytes,
            )

        ready = readiness(
            adoption_binding=adoption_binding,
            lint_receipt=valid_receipt,
            draft_bytes=self.draft_bytes,
            claim_card_bytes=self.card_bytes,
        )
        self.assertTrue(ready["ready"])
        self.assertEqual(
            ready["lint_receipt_sha256"],
            valid_receipt["lint_receipt_sha256"],
        )


class LegacyEstimatePolicyExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="legacy-estimate-execution",
            title="Legacy estimate execution",
            workflow_evidence_version=4,
        )
        self.profile = workload_profile()
        memory_id = self.store.memory_add(
            {
                "kind": "computation",
                "claim": "Exercise a frozen legacy estimate binding.",
                "suggested_actions": ["compute"],
                "workload_profile": self.profile,
            },
            actor="main",
        )
        planned = create_round(
            self.store,
            workers=1,
            memory_ids=[memory_id],
            host_task_scope_id="legacy-estimate-policy-test",
        )
        self.round_id = planned["round_id"]
        self.manifest_path = (
            self.root / "rounds" / self.round_id / "round.json"
        )
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        assignment = manifest["assignments"][0]
        self.card_path = self.root / assignment["task_card_relpath"]
        card = json.loads(self.card_path.read_text(encoding="utf-8"))

        legacy_plan = _legacy_estimate_gated_adoption_plan(self.profile)
        legacy_binding = compact_adoption_binding(
            legacy_plan,
            allow_legacy_estimate_policy=True,
        )
        self.assertEqual(
            legacy_binding["feature_statuses"]["experiment_checkpoint"],
            "required",
        )
        self.assertEqual(
            card["adoption_plan"]["feature_statuses"][
                "experiment_checkpoint"
            ],
            "available",
        )

        contract = deepcopy(assignment["contract"])
        contract["adoption_plan_sha256"] = legacy_binding["plan_sha256"]
        assignment_sha256 = sha256_json(contract)
        card["adoption_plan"] = legacy_binding
        card["assignment_sha256"] = assignment_sha256
        card_bytes = write_json(self.card_path, card)
        assignment["contract"] = contract
        assignment["assignment_sha256"] = assignment_sha256
        assignment["task_card_sha256"] = sha256_bytes(card_bytes)
        write_json(self.manifest_path, manifest)

        self.card = json.loads(self.card_path.read_text(encoding="utf-8"))
        self.manifest = json.loads(
            self.manifest_path.read_text(encoding="utf-8")
        )
        self.assignment = self.manifest["assignments"][0]
        self.manager = ExperimentManager(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _experiment_manifest() -> dict[str, Any]:
        return {
            "objective": "Compute one exact value.",
            "command": ["python3", "run.py"],
            "environment": {
                "implementation": "CPython",
                "version": "3",
            },
            "cost_model": {
                "dominant_operation": "integer addition",
                "estimated_cost": 301,
                "expected_memory": "unknown",
                "parallelism": "host-selected",
                "complexity_model": {
                    "parameters": {"n": 1},
                    "asymptotic_time": "unknown",
                    "asymptotic_space": "unknown",
                    "estimated_operation_count": None,
                    "estimate_basis": "historical advisory estimate",
                    "intermediate_object_estimates": [],
                },
            },
            "stages": ["exact"],
            "escalation_ladder": [
                {
                    "stage_id": "exact",
                    "arithmetic": "integer",
                    "advance_condition": "exact output exists",
                }
            ],
            "checkpoint_policy": "stage boundary",
            "resume_contract": {
                "checkpoint_format": "json",
                "resume_command": ["python3", "run.py", "--resume"],
                "compatibility_fields": ["python"],
                "deterministic_replay_required": True,
            },
            "truth_status": "exploration",
        }

    @staticmethod
    def _observation() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "observation_id": "legacy-active-observation",
            "measurement_method": "host_monotonic_active_intervals_union",
            "active_intervals": [
                {
                    "clock_epoch": "host-epoch",
                    "lease_id": "legacy-worker",
                    "start_ns": 0,
                    "end_ns": 1,
                }
            ],
            "actual_resources": {
                "cpu_seconds": 0,
                "peak_rss_bytes": 0,
            },
            "experimental_nature": "Historical fixture.",
            "progress": "No active execution is authorized.",
            "latest_checkpoint": "",
            "importance_and_continuation_value": "Historical parsing only.",
            "stopping_impact": "No active work may start.",
        }

    def test_legacy_estimate_binding_remains_historically_parseable(
        self,
    ) -> None:
        self.assertEqual(
            validate_task_card(
                self.card,
                allow_legacy_adoption=True,
            ),
            self.card,
        )
        with self.assertRaisesRegex(
            ValueError,
            "deterministic V4 policy",
        ):
            validate_task_card(self.card)

    def test_legacy_estimate_binding_cannot_start_active_experiment(
        self,
    ) -> None:
        before = file_inventory(self.root)
        with self.assertRaisesRegex(ValueError, LEGACY_ACTIVE_REJECTION):
            self.manager.start(
                task_card=self.card,
                manifest=self._experiment_manifest(),
            )
        self.assertEqual(file_inventory(self.root), before)

    def test_legacy_estimate_binding_cannot_record_active_observation(
        self,
    ) -> None:
        before = file_inventory(self.root)
        with self.assertRaisesRegex(ValueError, LEGACY_ACTIVE_REJECTION):
            self.manager.observe(
                task_card=self.card,
                payload=self._observation(),
                actor_role="main",
            )
        self.assertEqual(file_inventory(self.root), before)

    def test_legacy_estimate_binding_cannot_validate_active_return(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, LEGACY_ACTIVE_REJECTION):
            validate_worker_return(
                {},
                self.assignment,
                self.manifest,
                project_root=self.root,
            )

    def test_legacy_estimate_binding_cannot_satisfy_active_receipt_gate(
        self,
    ) -> None:
        before = file_inventory(self.root)
        with self.assertRaisesRegex(ValueError, LEGACY_ACTIVE_REJECTION):
            validate_required_experiment_receipt(
                project_root=self.root,
                task_card=self.card,
                artifacts=[],
            )
        self.assertEqual(file_inventory(self.root), before)


class CurrentEstimatePolicyExecutionTests(unittest.TestCase):
    def test_current_single_stage_301s_needs_no_experiment_receipt(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            store = MathGraphStore(root)
            store.initialize(
                project_id="current-estimate-execution",
                title="Current estimate execution",
                workflow_evidence_version=4,
            )
            memory_id = store.memory_add(
                {
                    "kind": "computation",
                    "claim": "Run one non-resumable exact stage.",
                    "suggested_actions": ["compute"],
                    "workload_profile": workload_profile(),
                },
                actor="main",
            )
            planned = create_round(
                store,
                workers=1,
                memory_ids=[memory_id],
                host_task_scope_id="current-estimate-policy-test",
            )
            card = json.loads(
                Path(
                    planned["assignments"][0]["task_card_path"]
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                card["adoption_plan"]["feature_statuses"][
                    "experiment_checkpoint"
                ],
                "available",
            )
            validate_required_experiment_receipt(
                project_root=root,
                task_card=card,
                artifacts=[],
            )


if __name__ == "__main__":
    unittest.main()
