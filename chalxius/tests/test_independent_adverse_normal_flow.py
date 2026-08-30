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
from mathgraph.markdown import validate_fact_round_trip
from mathgraph.model import Fact
from mathgraph.protocol import normalize_host_task_scope_id
from mathgraph.roles import allowed_commands
from mathgraph.runtime_archive import validate_runtime_binding
from mathgraph.store import MathGraphStore
from mathgraph.v5_assurance import V5_ASSURANCE_CONTRACT_REVISION


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
    def _write_candidate_fact(
        store: MathGraphStore,
        path: Path,
        *,
        claim_id: str,
    ) -> bytes:
        fact = Fact(
            problem_id=store.project_id(),
            author="candidate-producer",
            predecessors=[],
            statement=f"[CLAIM:{claim_id}] The exact Candidate target holds.",
            proof="Direct proof over the frozen Candidate boundary.",
        )
        raw = validate_fact_round_trip(fact).encode("utf-8")
        path.write_bytes(raw)
        return raw

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
        if "adverse_routing" in card:
            payload["attack_learning"] = None
        return_path = store.root / card["return_contract"]["return_relpath"]
        return_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return sha256_bytes(return_path.read_bytes())

    @staticmethod
    def _frozen_102_runtime_binding(current: dict) -> dict:
        """Freeze a coherent 1.0.2 decoder identity without a host dependency."""

        binding = deepcopy(current)
        binding["skill_version"] = "1.0.2"
        binding["version_file_sha256"] = sha256_bytes(b"1.0.2\n")
        content_semantic = {
            "schema_version": 1,
            "skill_version": binding["skill_version"],
            "version_file_sha256": binding["version_file_sha256"],
            "manifest_file_sha256": binding["manifest_file_sha256"],
        }
        binding["runtime_content_sha256"] = sha256_json(content_semantic)
        archive_root = Path(binding["historical_archive_root"])
        binding["historical_archive_root"] = str(
            archive_root.parent / binding["runtime_content_sha256"]
        )
        semantic = {
            key: value
            for key, value in binding.items()
            if key != "runtime_identity_sha256"
        }
        binding["runtime_identity_sha256"] = sha256_json(semantic)
        return validate_runtime_binding(binding)

    def _freeze_legacy_102_paired_round(
        self,
        store: MathGraphStore,
        research: dict,
    ) -> tuple[str, dict, dict]:
        """Build frozen legacy bytes without invoking prospective pair allocation."""

        lifecycle = store.v5_lifecycle()
        primary_status = lifecycle.create_round(
            workers=1,
            mode="prove",
            research_ids=[research["research_id"]],
            host_task_scope_id="frozen-102-pair",
        )
        refute_status = lifecycle.create_round(
            workers=1,
            mode="refute",
            research_ids=[research["research_id"]],
            host_task_scope_id="frozen-102-refute-template",
        )
        round_id = primary_status["round_id"]
        round_dir = store.rounds_dir / round_id
        manifest_path = round_dir / "round.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        primary_assignment = deepcopy(manifest["assignments"][0])
        primary_assignment_id = primary_assignment["assignment_id"]
        adverse_assignment_id = f"a02-{research['research_id']}-refute"
        handoff = build_paired_proof_philosophy_attack_handoff(
            research_id=research["research_id"],
            round_id=round_id,
            primary_assignment_id=primary_assignment_id,
            adverse_assignment_id=adverse_assignment_id,
        )

        primary_card_path = store.root / primary_assignment["task_card_relpath"]
        primary_card = json.loads(primary_card_path.read_text(encoding="utf-8"))
        runtime_binding = self._frozen_102_runtime_binding(
            primary_card["runtime_binding"]
        )
        primary_card["runtime_binding"] = runtime_binding
        primary_card["context_selection"]["mode"] = (
            lifecycle._legacy_mode_selection(
                research,
                requested_mode="prove",
                index=0,
                adverse_routing_enabled=True,
            )
        )
        primary_card["context_selection"]["context_selection_sha256"] = (
            sha256_json(
                {
                    key: value
                    for key, value in primary_card[
                        "context_selection"
                    ].items()
                    if key != "context_selection_sha256"
                }
            )
        )
        primary_card["control_plane"]["worker_context_id"] = handoff[
            "primary_binding"
        ]["worker_context_id"]
        primary_card["control_plane"]["independent_adverse_pair"] = handoff[
            "primary_binding"
        ]
        primary_semantic = {
            key: value
            for key, value in primary_card.items()
            if key != "task_card_semantic_sha256"
        }
        primary_card["task_card_semantic_sha256"] = sha256_json(
            primary_semantic
        )

        refute_round_dir = store.rounds_dir / refute_status["round_id"]
        refute_manifest = json.loads(
            (refute_round_dir / "round.json").read_text(encoding="utf-8")
        )
        refute_assignment = refute_manifest["assignments"][0]
        adverse_card = json.loads(
            (
                refute_round_dir
                / "task-cards"
                / f"{refute_assignment['assignment_id']}.json"
            ).read_text(encoding="utf-8")
        )
        adverse_card["runtime_binding"] = runtime_binding
        adverse_card["context_selection"]["mode"] = (
            lifecycle._legacy_mode_selection(
                research,
                requested_mode="refute",
                index=1,
                adverse_routing_enabled=True,
            )
        )
        adverse_card["context_selection"]["context_selection_sha256"] = (
            sha256_json(
                {
                    key: value
                    for key, value in adverse_card[
                        "context_selection"
                    ].items()
                    if key != "context_selection_sha256"
                }
            )
        )
        adverse_card["round_id"] = round_id
        adverse_card["assignment_id"] = adverse_assignment_id
        adverse_card["worker_id"] = adverse_assignment_id
        adverse_card["control_plane"].update(
            {
                "prompt_relpath": (
                    f"rounds/{round_id}/assignments/"
                    f"{adverse_assignment_id}.md"
                ),
                "host_task_scope_id": manifest["host_task_scope_id"],
                "worker_context_id": handoff["adverse_binding"][
                    "worker_context_id"
                ],
                "assignment_role": "paired_adverse",
                "independent_adverse_pair": handoff["adverse_binding"],
            }
        )
        adverse_card["artifact_capability"].update(
            {
                "artifact_dir_relpath": (
                    f"rounds/{round_id}/artifacts/{adverse_assignment_id}"
                ),
                "work_dir_relpath": (
                    f"rounds/{round_id}/work/{adverse_assignment_id}"
                ),
            }
        )
        adverse_card["return_contract"]["return_relpath"] = (
            f"rounds/{round_id}/returns/{adverse_assignment_id}.json"
        )
        routes = store.adverse_routes()
        self.assertFalse(routes.root.exists())
        # Reconstruct only the immutable historical card projection.  The
        # retired state materializer is intercepted so fixture construction
        # cannot re-enable the prospective learning plane.
        with patch.object(routes, "_materialize_state", return_value=None):
            adverse_binding = routes.task_card_binding(
                entry=research,
                work_mode="refute",
                related_artifacts=adverse_card["mathematical_state"][
                    "related_artifacts"
                ],
            )
        self.assertIsNotNone(adverse_binding)
        adverse_card["adverse_routing"] = adverse_binding
        adverse_semantic = {
            key: value
            for key, value in adverse_card.items()
            if key != "task_card_semantic_sha256"
        }
        adverse_card["task_card_semantic_sha256"] = sha256_json(
            adverse_semantic
        )

        def publish_card_and_prompt(card: dict, path: Path) -> tuple[str, str]:
            path.write_text(
                json.dumps(card, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            task_card_sha256 = sha256_bytes(path.read_bytes())
            prompt_path = store.root / card["control_plane"]["prompt_relpath"]
            prompt_path.write_text(
                lifecycle._compact_prompt(
                    card=card,
                    task_card_sha256=task_card_sha256,
                ),
                encoding="utf-8",
            )
            return task_card_sha256, sha256_bytes(prompt_path.read_bytes())

        primary_task_sha, primary_prompt_sha = publish_card_and_prompt(
            primary_card,
            primary_card_path,
        )
        adverse_card_path = round_dir / "task-cards" / (
            f"{adverse_assignment_id}.json"
        )
        adverse_task_sha, adverse_prompt_sha = publish_card_and_prompt(
            adverse_card,
            adverse_card_path,
        )

        primary_assignment.update(
            {
                "task_card_sha256": primary_task_sha,
                "prompt_sha256": primary_prompt_sha,
                "worker_context_id": handoff["primary_binding"][
                    "worker_context_id"
                ],
                "independent_adverse_pair": handoff["primary_binding"],
            }
        )
        primary_assignment["writer_lease_id"] = lifecycle._writer_lease_id(
            round_id=round_id,
            assignment_id=primary_assignment_id,
            task_card_sha256=primary_task_sha,
            worker_context_id=primary_assignment["worker_context_id"],
            host_task_scope_id=manifest["host_task_scope_id"],
        )
        primary_assignment["assignment_sha256"] = sha256_json(
            {
                key: value
                for key, value in primary_assignment.items()
                if key != "assignment_sha256"
            }
        )

        adverse_assignment = deepcopy(refute_assignment)
        adverse_assignment.update(
            {
                "assignment_id": adverse_assignment_id,
                "research_id": research["research_id"],
                "worker_id": adverse_assignment_id,
                "work_mode": "refute",
                "prompt_relpath": adverse_card["control_plane"][
                    "prompt_relpath"
                ],
                "prompt_sha256": adverse_prompt_sha,
                "task_card_relpath": (
                    f"rounds/{round_id}/task-cards/"
                    f"{adverse_assignment_id}.json"
                ),
                "task_card_sha256": adverse_task_sha,
                "return_relpath": adverse_card["return_contract"][
                    "return_relpath"
                ],
                "artifact_dir_relpath": adverse_card[
                    "artifact_capability"
                ]["artifact_dir_relpath"],
                "work_dir_relpath": adverse_card["artifact_capability"][
                    "work_dir_relpath"
                ],
                "blackboard_snapshot_id": manifest[
                    "blackboard_snapshot_id"
                ],
                "blackboard_snapshot_sha256": manifest[
                    "blackboard_snapshot_sha256"
                ],
                "host_task_scope_id": manifest["host_task_scope_id"],
                "worker_context_id": handoff["adverse_binding"][
                    "worker_context_id"
                ],
                "assignment_role": "paired_adverse",
                "independent_adverse_pair": handoff["adverse_binding"],
            }
        )
        adverse_assignment["writer_lease_id"] = lifecycle._writer_lease_id(
            round_id=round_id,
            assignment_id=adverse_assignment_id,
            task_card_sha256=adverse_task_sha,
            worker_context_id=adverse_assignment["worker_context_id"],
            host_task_scope_id=manifest["host_task_scope_id"],
        )
        adverse_assignment["assignment_sha256"] = sha256_json(
            {
                key: value
                for key, value in adverse_assignment.items()
                if key != "assignment_sha256"
            }
        )
        for assignment in (primary_assignment, adverse_assignment):
            sidecar_path = (
                round_dir
                / "assignments"
                / f"{assignment['assignment_id']}.json"
            )
            sidecar_path.write_text(
                json.dumps(
                    assignment,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
        (round_dir / "artifacts" / adverse_assignment_id).mkdir()
        (round_dir / "work" / adverse_assignment_id).mkdir()
        manifest["independent_adverse_pairs"] = [handoff["pair"]]
        manifest["assignments"] = [
            primary_assignment,
            adverse_assignment,
        ]
        manifest["manifest_sha256"] = sha256_json(
            {
                key: value
                for key, value in manifest.items()
                if key != "manifest_sha256"
            }
        )
        manifest_path.write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        self.assertFalse(routes.root.exists())
        return round_id, handoff, adverse_card

    def test_current_philosophy_production_does_not_allocate_adverse_pair(self) -> None:
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
            self.assertEqual((len(primary), len(adverse)), (1, 0))
            self.assertEqual(planned["independent_adverse_pairs"], [])
            primary_card = json.loads(
                Path(primary[0]["task_card_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(primary_card["work_mode"], "prove")
            self.assertIsNone(
                primary_card["control_plane"]["independent_adverse_pair"]
            )
            self.assertNotIn("adverse_routing", primary_card)

    def test_current_math_production_does_not_allocate_adverse_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "paired-math")
            research = self._research(store, domain="mathematics")
            planned = store.v5_lifecycle().create_round(
                workers=1,
                mode="prove",
                research_ids=[research["research_id"]],
            )
            primary, adverse = self._roles(planned)
            self.assertEqual((len(primary), len(adverse)), (1, 0))
            self.assertEqual(planned["independent_adverse_pairs"], [])
            card = json.loads(
                Path(primary[0]["task_card_path"]).read_text(encoding="utf-8")
            )
            self.assertIsNone(
                card["control_plane"]["independent_adverse_pair"]
            )
            self.assertNotIn("adverse_routing", card)

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

    def test_frozen_102_paired_round_decodes_tamper_without_backfill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "frozen-102-pair")
            research = self._research(store)
            round_id, handoff, adverse_card = (
                self._freeze_legacy_102_paired_round(store, research)
            )
            routes = store.adverse_routes()
            self.assertFalse(routes.root.exists())
            decoded = store.v5_lifecycle().round_status(round_id)
            primary, adverse = self._roles(decoded)
            self.assertEqual((len(primary), len(adverse)), (1, 1))
            self.assertEqual(decoded["independent_adverse_pairs"], [handoff["pair"]])
            self.assertEqual(
                adverse_card["runtime_binding"]["skill_version"],
                "1.0.2",
            )
            self.assertIn("adverse_routing", adverse_card)
            self.assertFalse(routes.root.exists())

            tampered = deepcopy(adverse_card)
            tampered["control_plane"]["independent_adverse_pair"][
                "worker_context_id"
            ] = handoff["primary_binding"]["worker_context_id"]
            tampered["task_card_semantic_sha256"] = sha256_json(
                {
                    key: value
                    for key, value in tampered.items()
                    if key != "task_card_semantic_sha256"
                }
            )
            with self.assertRaisesRegex(ValueError, "pair binding drifted"):
                store.v5_lifecycle().validate_task_card(
                    tampered,
                    historical_runtime=True,
                )
            self.assertFalse(routes.root.exists())

    def test_candidate_release_fails_before_expensive_work_without_fresh_adverse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "fresh-adverse-fast-fail")
            lifecycle = store.v5_lifecycle()
            research = self._research(store, required=True)
            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The exact bounded target holds.",
                proof="Direct bounded proof.",
            )
            payload = {
                "schema_version": 5,
                "bundle_claim": fact.statement,
                "candidates": [fact.as_submission_dict()],
                "research_entry_ids": [research["research_id"]],
                "claim_relation": "proves",
                "artifacts": [],
                "verification_plan": {
                    "mode": "closed_capsule",
                    "authorized_artifact_roles": [],
                    "required_checks": [
                        "mathematical",
                        "typing",
                        "scope",
                        "source_and_applicability",
                        "predecessor_interfaces",
                        "computation_replay",
                        "challenge_dispositions",
                        "assurance_scope",
                    ],
                },
                "requested_assurance": {
                    "validation_subject": {
                        "kind": "theorem",
                        "subject_id": fact.fact_id,
                        "artifact_sha256": None,
                        "load_bearing_node_ids": [],
                    },
                    "validation_granularity": "monolithic_theorem",
                    "coverage": [],
                },
                "challenge_dispositions": [],
                "paper_evidence_refs": [],
                "adverse_actor_ids": [],
            }
            with patch.object(
                lifecycle,
                "_normalize_artifacts",
                side_effect=AssertionError("expensive release work was reached"),
            ) as expensive:
                with self.assertRaisesRegex(ValueError, "fresh_adverse_missing"):
                    lifecycle.candidate_release(
                        payload,
                        producer="candidate-producer",
                        preflight_only=True,
                    )
            expensive.assert_not_called()

    def test_fresh_adverse_ignores_unselected_marked_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "fresh-adverse-scope")
            lifecycle = store.v5_lifecycle()
            records = {
                "selected": {
                    "research_id": "selected",
                    "kind": "proof_attempt",
                    "metadata": {"independent_adverse_required": False},
                    "related_research_ids": ["remote-ancestor"],
                },
                "remote-ancestor": {
                    "research_id": "remote-ancestor",
                    "kind": "proof_attempt",
                    "metadata": {"independent_adverse_required": True},
                    "related_research_ids": [],
                },
            }
            with patch.object(
                lifecycle, "_lightweight_research_records", return_value=records
            ):
                readiness = lifecycle._fresh_adverse_readiness(
                    research_ids=["selected"],
                    candidate_fact_bindings=[{"fact_id": "f", "fact_sha256": "a" * 64}],
                    challenge_dispositions=[],
                    adverse_actor_ids=[],
                    producer="candidate-producer",
                )
            self.assertEqual(readiness["status"], "not_required")
            self.assertEqual(readiness["required_target_research_ids"], [])

    def test_fresh_adverse_keeps_only_maximal_selected_marked_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "fresh-adverse-maximal")
            lifecycle = store.v5_lifecycle()
            records = {
                "ancestor": {
                    "research_id": "ancestor",
                    "kind": "proof_attempt",
                    "metadata": {"independent_adverse_required": True},
                    "related_research_ids": [],
                },
                "descendant": {
                    "research_id": "descendant",
                    "kind": "proof_attempt",
                    "metadata": {"independent_adverse_required": True},
                    "related_research_ids": ["ancestor"],
                },
                "adverse": {
                    "research_id": "adverse",
                    "kind": "counterexample",
                    "metadata": {},
                    "related_research_ids": ["descendant"],
                    "relation": "responds_to",
                    "created_at": "2026-08-19T00:00:00Z",
                    "actor": "independent-adverse-worker",
                    "_adverse": True,
                },
            }

            def is_adverse(record: dict) -> bool:
                return bool(record.get("_adverse"))

            binding = {
                "target_research_id": "descendant",
                "adverse_research_id": "adverse",
                "adverse_worker_id": "independent-adverse-worker",
                "round_id": "round-test",
                "assignment_id": "assignment-test",
                "task_card_sha256": "b" * 64,
                "return_sha256": "c" * 64,
                "receipt_id": None,
                "host_task_scope_id": "hosttask-test",
                "worker_context_id": "context-test",
            }
            with (
                patch.object(
                    lifecycle, "_lightweight_research_records", return_value=records
                ),
                patch.object(
                    lifecycle, "_research_is_adverse_assignment", side_effect=is_adverse
                ),
                patch.object(
                    lifecycle,
                    "_lightweight_adverse_assignment_binding",
                    return_value=binding,
                ),
            ):
                readiness = lifecycle._fresh_adverse_readiness(
                    research_ids=["ancestor", "descendant"],
                    candidate_fact_bindings=[{"fact_id": "f", "fact_sha256": "a" * 64}],
                    challenge_dispositions=[
                        {
                            "research_id": "adverse",
                            "disposition": "nonblocking_with_reason",
                            "rationale": "The direct adverse result is retained for verifier adjudication.",
                        }
                    ],
                    adverse_actor_ids=["independent-adverse-worker"],
                    producer="candidate-producer",
                )
            self.assertEqual(
                readiness["required_target_research_ids"], ["descendant"]
            )
            self.assertEqual(
                readiness["adverse_bindings"][0]["target_research_id"], "descendant"
            )

    def test_candidate_release_accepts_only_exact_candidate_bound_refute(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "v5", "fresh-adverse-exact")
            lifecycle = store.v5_lifecycle()
            fact = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The exact attacked target holds.",
                proof="Direct proof over the frozen boundary.",
            )
            fact_raw = validate_fact_round_trip(fact).encode("utf-8")
            fact_path = store.root / "candidate-fact.md"
            fact_path.write_bytes(fact_raw)
            fact_sha256 = sha256_bytes(fact_raw)
            research = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Establish the exact attacked target.",
                    "independent_adverse_required": True,
                    "artifacts": [
                        {
                            "path": "candidate-fact.md",
                            "sha256": fact_sha256,
                            "role": "candidate_fact",
                        }
                    ],
                },
                actor="candidate-researcher",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            planned = lifecycle.create_round(
                workers=1,
                mode="refute",
                research_ids=[research["research_id"]],
                host_task_scope_id="fresh-adverse-exact",
            )
            assignment = planned["assignments"][0]
            return_sha = self._write_no_attack_return(store, assignment)
            receipt = lifecycle.ingest_return(
                round_id=planned["round_id"],
                assignment_id=assignment["assignment_id"],
                worker_final_sha256=return_sha,
            )
            # The Research product is the reusable lineage boundary.  The
            # derived worker receipt is only a workflow marker and may be
            # missing after an interrupted publication.
            Path(str(assignment["return_path"])).with_suffix(
                ".receipt.json"
            ).unlink(missing_ok=True)

            payload = {
                "schema_version": 5,
                "bundle_claim": fact.statement,
                "candidates": [fact.as_submission_dict()],
                "research_entry_ids": [research["research_id"]],
                "claim_relation": "proves",
                "artifacts": [
                    {
                        "path": "candidate-fact.md",
                        "sha256": fact_sha256,
                        "role": "candidate_fact",
                    }
                ],
                "verification_plan": {
                    "mode": "closed_capsule",
                    "authorized_artifact_roles": ["candidate_fact"],
                    "required_checks": [
                        "mathematical",
                        "typing",
                        "scope",
                        "source_and_applicability",
                        "predecessor_interfaces",
                        "computation_replay",
                        "challenge_dispositions",
                        "assurance_scope",
                        "research_obligation_evidence",
                    ],
                },
                "requested_assurance": {
                    "validation_subject": {
                        "kind": "theorem",
                        "subject_id": fact.fact_id,
                        "artifact_sha256": None,
                        "load_bearing_node_ids": [],
                    },
                    "validation_granularity": "monolithic_theorem",
                    "coverage": [],
                },
                "challenge_dispositions": [
                    {
                        "research_id": receipt["research_id"],
                        "disposition": "nonblocking_with_reason",
                        "rationale": (
                            "The frozen verifier must independently adjudicate "
                            "the bounded zero-attack return."
                        ),
                    }
                ],
                "paper_evidence_refs": [],
                "adverse_actor_ids": [assignment["worker_id"]],
            }
            preflight = lifecycle.candidate_release(
                payload,
                producer="candidate-producer",
                preflight_only=True,
            )
            self.assertEqual(
                preflight["fresh_adverse_readiness"]["status"],
                "ready",
            )
            self.assertEqual(
                preflight["fresh_adverse_readiness"][
                    "required_target_research_ids"
                ],
                [research["research_id"]],
            )

            changed = Fact(
                problem_id=store.project_id(),
                author="candidate-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] A changed unattacked target holds.",
                proof="A different proof.",
            )
            changed_payload = deepcopy(payload)
            changed_payload["bundle_claim"] = changed.statement
            changed_payload["candidates"] = [changed.as_submission_dict()]
            changed_payload["requested_assurance"]["validation_subject"][
                "subject_id"
            ] = changed.fact_id
            with patch.object(
                lifecycle,
                "_normalize_artifacts",
                side_effect=AssertionError("expensive release work was reached"),
            ) as expensive:
                with self.assertRaisesRegex(ValueError, "fresh_adverse_missing"):
                    lifecycle.candidate_release(
                        changed_payload,
                        producer="candidate-producer",
                        preflight_only=True,
                    )
            expensive.assert_not_called()

    def test_public_candidate_adverse_planner_is_exact_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "candidate-adverse-planner")
            lifecycle = store.v5_lifecycle()
            fact_path = root / "candidate-fact.md"
            self._write_candidate_fact(
                store, fact_path, claim_id="CANDIDATE_ADVERSE_PLANNER"
            )
            research = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Attack the exact Candidate Fact before packaging.",
                    "independent_adverse_required": True,
                    "artifacts": [
                        {
                            "path": "candidate-fact.md",
                            "sha256": sha256_bytes(fact_path.read_bytes()),
                            "role": "candidate_fact",
                        }
                    ],
                },
                actor="candidate-producer",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            code, first, error = self._cli(
                root,
                "main",
                "plan-candidate-adverse",
                research["research_id"],
                "--host-task-scope-id",
                "candidate-adverse-planner",
            )
            self.assertEqual(code, 0, error)
            assert first is not None
            self.assertEqual(len(first["assignments"]), 1)
            self.assertEqual(first["assignments"][0]["work_mode"], "refute")
            self.assertIsNone(first.get("research_cycle"))

            code, second, error = self._cli(
                root,
                "main",
                "plan-candidate-adverse",
                research["research_id"],
                "--host-task-scope-id",
                "candidate-adverse-planner",
            )
            self.assertEqual(code, 0, error)
            assert second is not None
            self.assertEqual(second["round_id"], first["round_id"])

            code, rejected, error = self._cli(
                root,
                "main",
                "plan-candidate-adverse",
                research["research_id"],
                "--host-task-scope-id",
                "different-candidate-adverse-scope",
            )
            self.assertEqual(code, 2)
            self.assertIsNone(rejected)
            self.assertIn("different host scope", error)

            ordinary = self._research(store, required=True)
            code, rejected, error = self._cli(
                root,
                "main",
                "plan-candidate-adverse",
                ordinary["research_id"],
            )
            self.assertEqual(code, 2)
            self.assertIsNone(rejected)
            self.assertIn("exactly one candidate_fact", error)

            code, rejected, error = self._cli(
                root,
                "worker",
                "plan-candidate-adverse",
                research["research_id"],
            )
            self.assertEqual(code, 3)
            self.assertIsNone(rejected)
            self.assertIn("not allowed", error)

            stale_path = root / "stale-candidate-fact.md"
            self._write_candidate_fact(
                store, stale_path, claim_id="STALE_CANDIDATE_ADVERSE"
            )
            stale_target = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "A stale Candidate target.",
                    "independent_adverse_required": True,
                    "artifacts": [
                        {
                            "path": "stale-candidate-fact.md",
                            "sha256": sha256_bytes(stale_path.read_bytes()),
                            "role": "candidate_fact",
                        }
                    ],
                },
                actor="candidate-producer",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "The stale Candidate target is invalid.",
                    "relation": "challenges",
                    "related_research_ids": [stale_target["research_id"]],
                    "route_invalidations": [stale_target["research_id"]],
                },
                actor="supervisor",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            code, rejected, error = self._cli(
                root,
                "main",
                "plan-candidate-adverse",
                stale_target["research_id"],
            )
            self.assertEqual(code, 2)
            self.assertIsNone(rejected)
            self.assertIn("is stale", error)

    def test_candidate_adverse_retry_skips_aborted_pre_cutover_card(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "candidate-adverse-aborted-cutover")
            lifecycle = store.v5_lifecycle()
            fact_path = root / "candidate-fact.md"
            self._write_candidate_fact(
                store, fact_path, claim_id="CANDIDATE_ADVERSE_ABORTED"
            )
            research = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Retry the exact Candidate Fact after a cutover.",
                    "independent_adverse_required": True,
                    "artifacts": [
                        {
                            "path": "candidate-fact.md",
                            "sha256": sha256_bytes(fact_path.read_bytes()),
                            "role": "candidate_fact",
                        }
                    ],
                },
                actor="candidate-producer",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            first = lifecycle.plan_candidate_adverse_round(
                research["research_id"],
                host_task_scope_id="candidate-adverse-aborted-cutover",
            )
            with store.v5_mutation_lock(command="work-unit-abort"):
                store.reasoning_modes().abort_work_unit(
                    round_id=first["round_id"],
                    actor="main",
                    reason="Simulate a runtime cutover before exact retry.",
                )
            original_round_manifest = lifecycle._round_manifest

            def fail_on_aborted_round(round_id: str, **kwargs: object) -> object:
                if round_id == first["round_id"]:
                    raise AssertionError(
                        "aborted pre-cutover round was reconstructed as active"
                    )
                return original_round_manifest(round_id, **kwargs)

            with patch.object(
                lifecycle,
                "_round_manifest",
                side_effect=fail_on_aborted_round,
            ):
                second = lifecycle.plan_candidate_adverse_round(
                    research["research_id"],
                    host_task_scope_id="candidate-adverse-aborted-cutover",
                )
            self.assertNotEqual(second["round_id"], first["round_id"])
            self.assertEqual(second["work_unit_state"], "active")
            self.assertEqual(second["assignments"][0]["work_mode"], "refute")

    def test_candidate_adverse_active_retry_still_reconstructs_bound_card(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "candidate-adverse-active-retry")
            lifecycle = store.v5_lifecycle()
            fact_path = root / "candidate-fact.md"
            self._write_candidate_fact(
                store, fact_path, claim_id="CANDIDATE_ADVERSE_ACTIVE"
            )
            research = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Keep an active exact adverse retry strict.",
                    "independent_adverse_required": True,
                    "artifacts": [
                        {
                            "path": "candidate-fact.md",
                            "sha256": sha256_bytes(fact_path.read_bytes()),
                            "role": "candidate_fact",
                        }
                    ],
                },
                actor="candidate-producer",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            first = lifecycle.plan_candidate_adverse_round(
                research["research_id"],
                host_task_scope_id="candidate-adverse-active-retry",
            )
            original_round_manifest = lifecycle._round_manifest

            def reject_active_round(round_id: str, **kwargs: object) -> object:
                if round_id == first["round_id"]:
                    raise ValueError("active retry card was reconstructed")
                return original_round_manifest(round_id, **kwargs)

            with patch.object(
                lifecycle,
                "_round_manifest",
                side_effect=reject_active_round,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "active retry card was reconstructed",
                ):
                    lifecycle.plan_candidate_adverse_round(
                        research["research_id"],
                        host_task_scope_id="candidate-adverse-active-retry",
                    )

    def test_public_plan_round_keeps_refute_out_and_report_cli_retired(self) -> None:
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
            self.assertEqual(len(planned["assignments"]), 1)
            self.assertEqual(planned["independent_adverse_pairs"], [])
            primary = planned["assignments"][0]
            self.assertEqual(primary["assignment_role"], "primary")
            self.assertNotEqual(primary["work_mode"], "refute")
            prompt = Path(primary["prompt_path"]).read_text(encoding="utf-8")
            self.assertIn("This is Research subround 1", prompt)
            self.assertNotIn("attack-report", allowed_commands("main"))

    def test_public_production_rejects_explicit_or_auto_refute(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "v5"
            store = self._store(root, "production-refute-rejected")
            proof = self._research(store, required=False)
            code, payload, error = self._cli(
                root,
                "main",
                "plan-round",
                "--workers",
                "1",
                "--mode",
                "refute",
                "--memory-id",
                proof["research_id"],
            )
            self.assertEqual(code, 2)
            self.assertIsNone(payload)
            self.assertIn("reserved for subround-2 supervision", error)

            challenge = self._research(
                store,
                kind="challenge",
                required=False,
            )
            code, payload, error = self._cli(
                root,
                "main",
                "plan-round",
                "--workers",
                "1",
                "--memory-id",
                challenge["research_id"],
            )
            self.assertEqual(code, 2)
            self.assertIsNone(payload)
            self.assertIn("production selection contains refute Research", error)
            self.assertEqual(list(store.rounds_dir.glob("round-*")), [])

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
