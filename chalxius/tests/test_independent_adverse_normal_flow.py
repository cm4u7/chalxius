from __future__ import annotations

import json
import os
import tempfile
import unittest
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mathgraph.adverse_routing import (
    build_paired_proof_philosophy_attack_handoff,
    validate_host_scope_attack_report,
    validate_independent_adverse_pair,
)
from mathgraph.cli import main as cli_main
from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.protocol import normalize_host_task_scope_id
from mathgraph.store import MathGraphStore


class IndependentAdverseNormalFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        # Runtime-manifest integrity has its own release tests.  This focused
        # suite remains runnable while several agents edit one candidate tree.
        self.runtime_patch = patch(
            "mathgraph.v5_lifecycle.V5LifecycleManager._validate_bound_runtime_binding",
            return_value=None,
        )
        self.runtime_patch.start()
        self.addCleanup(self.runtime_patch.stop)

    @staticmethod
    def _store(root: Path, project_id: str) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id=project_id,
            title="Independent adverse normal flow",
            workflow_evidence_version=5,
        )
        return store

    @staticmethod
    def _research(
        store: MathGraphStore,
        *,
        kind: str = "proof_attempt",
        domain: str = "mathematics",
        required: bool | None = True,
    ) -> dict:
        payload: dict[str, object] = {
            "kind": kind,
            "claim": "Establish or delimit the exact load-bearing target.",
            "adverse_domain_profile": domain,
        }
        if required is not None:
            payload["independent_adverse_required"] = required
        return store.v5_lifecycle().add_research(payload, actor="main")

    @staticmethod
    def _roles(planned: dict) -> tuple[list[dict], list[dict]]:
        primary = [
            item
            for item in planned["assignments"]
            if item["assignment_role"] == "primary"
        ]
        adverse = [
            item
            for item in planned["assignments"]
            if item["assignment_role"] == "paired_adverse"
        ]
        return primary, adverse

    @staticmethod
    def _cli(root: Path, role: str, *args: str) -> tuple[int, dict | None, str]:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli_main(
                ["--root", str(root), "--role", role, *args]
            )
        payload = json.loads(stdout.getvalue()) if stdout.getvalue().strip() else None
        return code, payload, stderr.getvalue()

    @staticmethod
    def _write_no_attack_return(store: MathGraphStore, assignment: dict) -> str:
        card_path = Path(assignment["task_card_path"])
        card = json.loads(card_path.read_text(encoding="utf-8"))
        payload = {
            "schema_version": 5,
            "project_id": store.project_id(),
            "round_id": card["round_id"],
            "assignment_id": assignment["assignment_id"],
            "worker_id": assignment["worker_id"],
            "task_card_sha256": assignment["task_card_sha256"],
            "blackboard_snapshot_sha256": assignment[
                "blackboard_snapshot_sha256"
            ],
            "outcome": "evidence",
            "claim": "The bounded attack found no surviving counterexample.",
            "content": (
                "Every frozen baseline attack was attempted inside the assigned "
                "boundary; no load-bearing repair survived the checks."
            ),
            "narrative": {
                "rationale": "Record a bounded zero-attack result.",
                "summary": "No surviving attack was found.",
                "intuition": "The tested failure surfaces remained closed.",
                "limitations": "This remains nontruth Research, not certification.",
            },
            "artifacts": [],
            "attack_learning": None,
            "obligation_dispositions": [
                {
                    "obligation_id": item["obligation_id"],
                    "status": "complete",
                    "witness_artifact_sha256s": [],
                    "rationale": "The direct logical attack requires no artifact.",
                }
                for item in card["assurance_contract"]["obligations"]
            ],
            "computation_manifest": None,
            "research_assurance": {
                "source_uses": [],
                "route_invalidations": [],
                "extremal_cases": [],
                "claim_strength": [],
                "contour_substitutions": [],
                "claimed_structures": [],
                "program_math_alignments": [],
            },
        }
        return_path = store.root / card["return_contract"]["return_relpath"]
        return_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return sha256_bytes(return_path.read_bytes())

    def test_philosophy_primary_gets_distinct_rule_bound_adverse_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "paired-philosophy")
            research = self._research(store, domain="philosophy")
            planned = store.v5_lifecycle().create_round(
                workers=1,
                mode="prove",
                research_ids=[research["research_id"]],
                host_task_scope_id="philosophy-scope",
            )
            primary, adverse = self._roles(planned)
            self.assertEqual(planned["primary_worker_count"], 1)
            self.assertEqual((len(primary), len(adverse)), (1, 1))
            self.assertEqual(len(planned["independent_adverse_pairs"]), 1)
            self.assertEqual(primary[0]["research_id"], adverse[0]["research_id"])
            self.assertNotEqual(primary[0]["worker_id"], adverse[0]["worker_id"])
            self.assertNotEqual(
                primary[0]["worker_context_id"],
                adverse[0]["worker_context_id"],
            )
            adverse_card = json.loads(
                Path(adverse[0]["task_card_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(adverse_card["work_mode"], "refute")
            self.assertTrue(
                adverse_card["control_plane"]["independent_adverse_pair"][
                    "shared_context_forbidden"
                ]
            )
            rule_ids = {
                item["rule_id"]
                for item in adverse_card["adverse_routing"]["baseline_rules"]
            }
            self.assertIn(
                "baseline_philosophy_plain_language_substitution", rule_ids
            )

    def test_math_proof_uses_same_pair_without_philosophy_stance_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "paired-math")
            research = self._research(store, domain="mathematics")
            planned = store.v5_lifecycle().create_round(
                workers=1,
                mode="prove",
                research_ids=[research["research_id"]],
            )
            _, adverse = self._roles(planned)
            self.assertEqual(len(adverse), 1)
            card = json.loads(
                Path(adverse[0]["task_card_path"]).read_text(encoding="utf-8")
            )
            rule_ids = {
                item["rule_id"]
                for item in card["adverse_routing"]["baseline_rules"]
            }
            self.assertNotIn(
                "baseline_philosophy_plain_language_substitution", rule_ids
            )
            self.assertEqual(
                card["adverse_routing"]["scope_evidence"]["domain_profile"],
                "mathematics",
            )

    def test_false_predicate_and_existing_refute_or_challenge_do_not_double(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "paired-predicate")
            false_research = self._research(store, required=False)
            false_plan = store.v5_lifecycle().create_round(
                workers=1,
                mode="prove",
                research_ids=[false_research["research_id"]],
            )
            self.assertEqual(len(false_plan["assignments"]), 1)
            self.assertEqual(false_plan["independent_adverse_pairs"], [])

            refute_research = self._research(store)
            refute_plan = store.v5_lifecycle().create_round(
                workers=1,
                mode="refute",
                research_ids=[refute_research["research_id"]],
            )
            self.assertEqual(len(refute_plan["assignments"]), 1)
            self.assertEqual(refute_plan["independent_adverse_pairs"], [])

            challenge = self._research(store, kind="challenge")
            challenge_plan = store.v5_lifecycle().create_round(
                workers=1,
                mode="prove",
                research_ids=[challenge["research_id"]],
            )
            self.assertEqual(len(challenge_plan["assignments"]), 1)
            self.assertEqual(challenge_plan["independent_adverse_pairs"], [])

    def test_scope_uses_environment_first_and_local_fallback_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "paired-scope")
            research = self._research(store, required=False)
            with patch.dict(
                os.environ,
                {"MATHGRAPH_HOST_TASK_SCOPE_ID": "environment-task"},
                clear=False,
            ):
                environment_plan = store.v5_lifecycle().create_round(
                    workers=1,
                    mode="prove",
                    research_ids=[research["research_id"]],
                )
            self.assertEqual(
                environment_plan["host_task_scope_id"],
                normalize_host_task_scope_id(
                    "environment-task", workflow_evidence_version=5
                ),
            )
            with patch.dict(
                os.environ,
                {"MATHGRAPH_HOST_TASK_SCOPE_ID": "", "CODEX_THREAD_ID": ""},
                clear=False,
            ):
                first = store.v5_lifecycle().create_round(
                    workers=1,
                    mode="prove",
                    research_ids=[research["research_id"]],
                )
                second = store.v5_lifecycle().create_round(
                    workers=1,
                    mode="prove",
                    research_ids=[research["research_id"]],
                )
            self.assertEqual(first["host_task_scope_id"], second["host_task_scope_id"])
            self.assertRegex(first["host_task_scope_id"], r"^hosttask-[0-9a-f]{32}$")
            self.assertTrue(
                all(
                    item["host_task_scope_id"] == first["host_task_scope_id"]
                    for item in first["assignments"]
                )
            )

    def test_attack_report_predicate_false_is_explicitly_not_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "paired-report-not-required")
            research = self._research(store, required=False)
            planned = store.v5_lifecycle().create_round(
                workers=1,
                mode="prove",
                research_ids=[research["research_id"]],
                host_task_scope_id="not-required-scope",
            )
            report = store.adverse_routes().report(
                host_task_scope_id=planned["host_task_scope_id"]
            )
            self.assertEqual(report["coverage_status"], "not-required")
            self.assertTrue(report["scope_complete"])
            self.assertEqual(report["paired_adverse_coverage"], [])
            self.assertEqual(report["attacks"], [])
            self.assertEqual(
                report["zero_attack_interpretation"],
                "no_independent_adverse_dispatch_required_in_scope",
            )

    def test_zero_attack_report_requires_complete_pair_return(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "paired-zero")
            research = self._research(store)
            planned = store.v5_lifecycle().create_round(
                workers=1,
                mode="prove",
                research_ids=[research["research_id"]],
                host_task_scope_id="zero-attack-scope",
            )
            _, adverse = self._roles(planned)
            pending = store.adverse_routes().report(
                host_task_scope_id="zero-attack-scope"
            )
            self.assertEqual(pending["coverage_status"], "pending")
            self.assertFalse(pending["scope_complete"])
            self.assertEqual(pending["attacks"], [])
            self.assertEqual(
                pending["zero_attack_interpretation"],
                "zero_cases_does_not_establish_completed_dispatch",
            )

            final_sha = self._write_no_attack_return(store, adverse[0])
            receipt = store.v5_lifecycle().ingest_return(
                round_id=planned["round_id"],
                assignment_id=adverse[0]["assignment_id"],
                worker_final_sha256=final_sha,
            )
            self.assertEqual(receipt["status"], "ingested")
            complete = store.adverse_routes().report(
                host_task_scope_id="zero-attack-scope"
            )
            self.assertEqual(
                complete["coverage_status"],
                "dispatched-no-surviving-attack",
            )
            self.assertTrue(complete["scope_complete"])
            self.assertEqual(complete["attacks"], [])
            self.assertEqual(len(complete["rounds"]), 1)
            self.assertEqual(len(complete["cards"]), 2)
            self.assertEqual(len(complete["returns"]), 2)

            tampered = deepcopy(complete)
            tampered["scope_complete"] = False
            semantic = {
                key: value
                for key, value in tampered.items()
                if key != "report_sha256"
            }
            tampered["report_sha256"] = sha256_json(semantic)
            with self.assertRaisesRegex(ValueError, "completion projection"):
                validate_host_scope_attack_report(tampered)

    def test_public_plan_round_and_attack_report_reach_the_normal_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "paired-cli-normal-flow")
            research = self._research(store, domain="philosophy")
            with patch.dict(
                os.environ,
                {"MATHGRAPH_HOST_TASK_SCOPE_ID": "", "CODEX_THREAD_ID": ""},
                clear=False,
            ):
                code, planned, error = self._cli(
                    root,
                    "main",
                    "plan-round",
                    "--workers",
                    "1",
                    "--mode",
                    "prove",
                    "--memory-id",
                    research["research_id"],
                )
            self.assertEqual(code, 0, error)
            self.assertIsInstance(planned, dict)
            assert planned is not None
            self.assertEqual(planned["primary_worker_count"], 1)
            self.assertEqual(len(planned["assignments"]), 2)
            adverse = next(
                item
                for item in planned["assignments"]
                if item["assignment_role"] == "paired_adverse"
            )
            prompt = Path(adverse["prompt_path"]).read_text(encoding="utf-8")
            self.assertIn("Do not receive, reuse, summarize, or share", prompt)

            code, report, error = self._cli(
                root,
                "main",
                "attack-report",
                "--host-task-scope-id",
                planned["host_task_scope_id"],
            )
            self.assertEqual(code, 0, error)
            self.assertIsInstance(report, dict)
            assert report is not None
            self.assertEqual(report["coverage_status"], "pending")
            self.assertEqual(len(report["rounds"]), 1)
            self.assertEqual(len(report["assignments"]), 2)
            self.assertEqual(len(report["cards"]), 2)
            self.assertEqual(len(report["returns"]), 2)

    def test_attack_report_tamper_is_rejected_after_hash_recomputation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "paired-report-tamper")
            report = store.adverse_routes().report(
                host_task_scope_id="undispatched-tamper-scope"
            )
            self.assertEqual(report["coverage_status"], "missing-dispatch")
            tampered = deepcopy(report)
            tampered["scope_complete"] = True
            semantic = {
                key: value
                for key, value in tampered.items()
                if key != "report_sha256"
            }
            tampered["report_sha256"] = sha256_json(semantic)
            with self.assertRaisesRegex(ValueError, "completion projection"):
                validate_host_scope_attack_report(tampered)

            research = self._research(store)
            planned = store.v5_lifecycle().create_round(
                workers=1,
                mode="prove",
                research_ids=[research["research_id"]],
                host_task_scope_id="paired-tamper-scope",
            )
            scoped = store.adverse_routes().report(
                host_task_scope_id=planned["host_task_scope_id"]
            )
            mixed = deepcopy(scoped)
            mixed["paired_adverse_coverage"][0]["host_task_scope_id"] = (
                "hosttask-" + "f" * 32
            )
            mixed_semantic = {
                key: value for key, value in mixed.items() if key != "report_sha256"
            }
            mixed["report_sha256"] = sha256_json(mixed_semantic)
            with self.assertRaisesRegex(ValueError, "mixed scope"):
                validate_host_scope_attack_report(mixed)

    def test_independent_pair_tamper_is_rejected(self) -> None:
        handoff = build_paired_proof_philosophy_attack_handoff(
            research_id="a" * 12,
            round_id="round-20260804T120000Z-1234abcd",
            primary_assignment_id="a01-aaaaaaaaaaaa-prove",
            adverse_assignment_id="a02-aaaaaaaaaaaa-refute",
        )
        tampered_pair = deepcopy(handoff["pair"])
        tampered_pair["adverse_context_id"] = tampered_pair[
            "primary_context_id"
        ]
        semantic = {
            key: value
            for key, value in tampered_pair.items()
            if key not in {"pair_id", "pair_sha256"}
        }
        tampered_pair["pair_id"] = "adverse-pair-" + sha256_json(semantic)
        without_hash = {
            key: value
            for key, value in tampered_pair.items()
            if key != "pair_sha256"
        }
        tampered_pair["pair_sha256"] = sha256_json(without_hash)
        with self.assertRaisesRegex(ValueError, "pair contract"):
            validate_independent_adverse_pair(tampered_pair)


if __name__ == "__main__":
    unittest.main()
