from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from mathgraph.cli import _command_requires_mutation_lock, build_parser
from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.markdown import validate_fact_round_trip
from mathgraph.model import Fact
from mathgraph.store import MathGraphStore
from mathgraph.v5_assurance import V5_ASSURANCE_CONTRACT_REVISION


class BoundedHandoff0714Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime_patch = patch(
            "mathgraph.v5_lifecycle.V5LifecycleManager._validate_bound_runtime_binding",
            side_effect=lambda value, **_: value,
        )
        self.runtime_patch.start()
        self.addCleanup(self.runtime_patch.stop)

    @staticmethod
    def _store(root: Path) -> MathGraphStore:
        store = MathGraphStore(root)
        store.initialize(
            project_id="chx-0714-bounded-handoff",
            title="CHX 0.7.14 bounded handoff",
            workflow_evidence_version=5,
        )
        return store

    def test_candidate_adverse_prompt_uses_dedicated_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            fact = Fact(
                problem_id=store.project_id(),
                author="producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The exact bounded target holds.",
                proof="Direct proof.",
            )
            raw = validate_fact_round_trip(fact).encode("utf-8")
            path = store.root / "candidate.md"
            path.write_bytes(raw)
            target = lifecycle.add_research(
                {
                    "kind": "synthesis",
                    "claim": "Attack the exact canonical Candidate Fact.",
                    "independent_adverse_required": True,
                    "artifacts": [
                        {
                            "path": "candidate.md",
                            "sha256": sha256_bytes(raw),
                            "role": "candidate_fact",
                        }
                    ],
                },
                actor="main",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            planned = lifecycle.plan_candidate_adverse_round(
                target["research_id"],
                host_task_scope_id="candidate-adverse-compact-route",
            )
            prompt = Path(planned["assignments"][0]["prompt_path"]).read_text(
                encoding="utf-8"
            )
            self.assertIn(
                "references/v5_candidate_adverse_worker_bootstrap.md", prompt
            )
            self.assertNotIn("references/v5_production_worker_bootstrap.md", prompt)

    def test_prepare_candidate_adverse_target_is_one_main_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            fact = Fact(
                problem_id=store.project_id(),
                author="producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The prepared target holds.",
                proof="Direct proof.",
            )
            raw = validate_fact_round_trip(fact).encode("utf-8")
            path = store.root / "candidate.md"
            path.write_bytes(raw)
            selected = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Establish the selected mathematical result.",
                },
                actor="main-synthesis",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            supervision = lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "The bounded supervision result is clean.",
                    "relation": "challenges",
                    "related_research_ids": [selected["research_id"]],
                },
                actor="supervisor",
            )
            with patch.object(
                lifecycle,
                "_required_supervision_results_for_candidate",
                return_value={supervision["research_id"]},
            ):
                original_adverse = lifecycle._research_is_adverse_assignment

                def supervised_only(record: dict) -> bool:
                    if record.get("research_id") == supervision["research_id"]:
                        return True
                    return original_adverse(record)

                with patch.object(
                    lifecycle,
                    "_research_is_adverse_assignment",
                    side_effect=supervised_only,
                ):
                    prepared = lifecycle.prepare_candidate_adverse_target(
                        selected["research_id"],
                        candidate_fact_path="candidate.md",
                    )
            record = lifecycle._research_record(prepared["research_id"])
            self.assertTrue(record["metadata"]["independent_adverse_required"])
            self.assertEqual(
                set(record["related_research_ids"]),
                {selected["research_id"], supervision["research_id"]},
            )
            self.assertEqual(
                prepared["selected_research_id"], selected["research_id"]
            )
            self.assertEqual(
                prepared["supervision_research_ids"],
                [supervision["research_id"]],
            )
            self.assertEqual(record["metadata"]["artifacts"][0]["sha256"], sha256_bytes(raw))
            planned = lifecycle.plan_candidate_adverse_round(
                prepared["research_id"],
                host_task_scope_id="prepared-candidate-adverse-target",
            )
            self.assertEqual(planned["assignments"][0]["work_mode"], "refute")

            tampered_path = store.root / "noncanonical-candidate.md"
            tampered_path.write_text(
                "not canonical Fact Markdown\n", encoding="utf-8"
            )
            tampered = lifecycle.add_research(
                {
                    "kind": "synthesis",
                    "claim": "Prepared target with noncanonical Fact bytes.",
                    "relation": "prepares_candidate_from",
                    "related_research_ids": [
                        selected["research_id"],
                        supervision["research_id"],
                    ],
                    "independent_adverse_required": True,
                    "artifacts": [
                        {
                            "path": "noncanonical-candidate.md",
                            "sha256": sha256_bytes(tampered_path.read_bytes()),
                            "role": "candidate_fact",
                        }
                    ],
                },
                actor="main",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            with self.assertRaisesRegex(ValueError, "candidate_fact artifact is invalid"):
                lifecycle.plan_candidate_adverse_round(
                    tampered["research_id"],
                    host_task_scope_id="tampered-prepared-candidate-target",
                )

    def test_frontier_fully_validates_only_returned_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            records = [
                lifecycle.add_research(
                    {"kind": "direction", "claim": f"Branch {index}."},
                    actor="main",
                )
                for index in range(8)
            ]
            original = lifecycle._inspection_research_record
            calls: list[str] = []

            def counted(research_id: str, context: object) -> dict:
                calls.append(research_id)
                return original(research_id, context)

            with patch.object(
                lifecycle, "_inspection_research_record", side_effect=counted
            ):
                visible = lifecycle.frontier(limit=2)
            self.assertEqual(len(visible), 2)
            self.assertEqual(calls, [])
            self.assertNotIn("metadata", visible[0])

            with patch.object(
                lifecycle, "_inspection_research_record", side_effect=counted
            ):
                executable = lifecycle.frontier(
                    limit=2,
                    _execution_records=True,
                )
            self.assertEqual(
                set(calls),
                {item["research_id"] for item in executable},
            )
            self.assertLess(len(calls), len(records))

    def test_unselected_component_ancestor_uses_structural_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            ancestor = lifecycle.add_research(
                {"kind": "direction", "claim": "Shared old premise."},
                actor="main",
            )
            selected = lifecycle.add_research(
                {
                    "kind": "direction",
                    "claim": "Selected descendant.",
                    "relation": "supports",
                    "related_research_ids": [ancestor["research_id"]],
                },
                actor="main",
            )
            assignment = {
                "assignment_id": f"a01-{selected['research_id']}-prove",
                "research_id": selected["research_id"],
            }
            with patch.object(
                lifecycle,
                "_inspection_research_record",
                side_effect=AssertionError("unselected ancestor was fully replayed"),
            ):
                components = lifecycle._build_logical_supervision_components(
                    assignments=[assignment],
                    source_records={selected["research_id"]: selected},
                )
            self.assertEqual(len(components), 1)

    def test_certification_owns_narrow_lock_and_reads_stay_unlocked(self) -> None:
        parser = build_parser()
        frontier = parser.parse_args(
            ["--root", "/tmp/project", "--role", "main", "frontier"]
        )
        certification = parser.parse_args(
            [
                "--root",
                "/tmp/project",
                "--role",
                "gateway",
                "certification-record",
                "--input",
                "decision.json",
            ]
        )
        mutation = Namespace(command="memory-add")
        self.assertFalse(_command_requires_mutation_lock(frontier))
        self.assertFalse(_command_requires_mutation_lock(certification))
        self.assertTrue(_command_requires_mutation_lock(mutation))

    def test_repair_carries_exact_source_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            source_path = store.root / "source.pdf"
            source_path.write_bytes(b"exact source bytes")
            source = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Source-bound result.",
                    "source_dependent": True,
                    "artifacts": [
                        {
                            "path": "source.pdf",
                            "sha256": sha256_bytes(source_path.read_bytes()),
                            "role": "primary_source",
                        }
                    ],
                },
                actor="producer",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            with patch.object(
                lifecycle,
                "create_production_round",
                return_value={"round_id": "round-20260813T000000Z-00000000"},
            ):
                repair = lifecycle.create_repair_round(source["research_id"])
            record = lifecycle._research_record(repair["research_id"])
            self.assertTrue(record["metadata"]["source_dependent"])
            self.assertEqual(record["metadata"]["artifacts"], source["metadata"]["artifacts"])

    def test_supervisor_inherits_attacked_source_capabilities_and_fact_premise(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            premise_research = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "Prove the premise."},
                actor="premise-producer",
            )
            premise = Fact(
                problem_id=store.project_id(),
                author="premise-producer",
                predecessors=[],
                statement="[CLAIM:ROOT] The frozen premise holds.",
                proof="Direct proof.",
            )
            release_payload = {
                "schema_version": 5,
                "bundle_claim": premise.statement,
                "candidates": [premise.as_submission_dict()],
                "research_entry_ids": [premise_research["research_id"]],
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
                        "subject_id": premise.fact_id,
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
            release = lifecycle.candidate_release(
                release_payload, producer="premise-producer"
            )
            capsule = lifecycle.verifier_capsule(release["release_id"])
            reviewer = "fresh-verifier"
            decision_payload = {
                "schema_version": 5,
                "release_id": release["release_id"],
                "release_sha256": release["release_sha256"],
                "capsule_sha256": capsule["capsule_sha256"],
                "verdict": "correct",
                "findings": [],
                "check_results": [
                    {"check_id": value, "status": "pass", "findings": []}
                    for value in capsule["required_checks"]
                ],
                "candidate_checks": [
                    {
                        "fact_id": premise.fact_id,
                        "verdict": "correct",
                        "findings": [],
                    }
                ],
                "edge_checks": [],
                "assurance_matrix": lifecycle._expected_assurance_matrix(release),
                "reviewer": reviewer,
                "host_attestation": {
                    "host": "test-host",
                    "agent_id": reviewer,
                    "isolation": "fresh_context",
                    "fork_turns": "none",
                    "allowed_capsule_sha256": capsule["capsule_sha256"],
                },
            }
            decision = lifecycle.certification_record(decision_payload)
            lifecycle.fact_admit(
                release_id=release["release_id"],
                decision_id=decision["decision_id"],
                gateway="test-gateway",
            )

            source_path = store.root / "primary-source.pdf"
            source_path.write_bytes(b"version-pinned primary source")
            source_artifacts = []
            for source_key, filename, payload in (
                ("HKR", "hkr-primary.pdf", b"HKR primary bytes"),
                ("BLR", "blr-primary.pdf", b"BLR primary bytes"),
                ("DML", "dml-primary.pdf", b"DML primary bytes"),
            ):
                source_file = store.root / filename
                source_file.write_bytes(payload)
                source_artifacts.append(
                    {
                        "source_key": source_key,
                        "artifact_path": filename,
                        "artifact_sha256": sha256_bytes(payload),
                    }
                )
            source_evidence_path = store.root / "source-evidence.json"
            source_evidence_raw = json.dumps(
                {
                    "schema_version": 1,
                    "ledger_kind": "structured_source_evidence",
                    "source_artifacts": source_artifacts,
                },
                sort_keys=True,
            ).encode("utf-8")
            source_evidence_path.write_bytes(source_evidence_raw)
            target = lifecycle.add_research(
                {
                    "kind": "literature",
                    "claim": "Apply the admitted premise to the frozen source.",
                    "dependencies": [premise.fact_id],
                    "source_dependent": True,
                    "artifacts": [
                        {
                            "path": "primary-source.pdf",
                            "sha256": sha256_bytes(source_path.read_bytes()),
                            "role": "primary_source",
                        },
                        {
                            "path": "source-evidence.json",
                            "sha256": sha256_bytes(source_evidence_raw),
                            "role": "source_evidence",
                        },
                    ],
                },
                actor="main",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            production = lifecycle.create_production_round(
                workers=1,
                mode="literature",
                research_ids=[target["research_id"]],
                host_task_scope_id="supervised-authority-source",
            )
            assignment = production["assignments"][0]
            card = json.loads(Path(assignment["task_card_path"]).read_text())
            return_payload = {
                "schema_version": 5,
                "project_id": store.project_id(),
                "round_id": production["round_id"],
                "assignment_id": assignment["assignment_id"],
                "worker_id": assignment["worker_id"],
                "task_card_sha256": assignment["task_card_sha256"],
                "blackboard_snapshot_sha256": assignment[
                    "blackboard_snapshot_sha256"
                ],
                "outcome": "evidence",
                "claim": "The bounded source use was checked.",
                "content": "The exact source remains inside the stated scope.",
                "narrative": {
                    "rationale": "Exercise supervisor capability closure.",
                    "summary": "Bounded evidence.",
                    "intuition": "The supervisor needs the same premise and bytes.",
                    "limitations": "Nontruth Research only.",
                },
                "artifacts": [],
                "obligation_dispositions": [],
                "computation_manifest": None,
                "research_assurance": {
                    "source_uses": [
                        {
                            "source_key": "frozen-primary-source",
                            "use_kind": "result",
                            "source_strength": "fixed_object",
                            "target_strength": "fixed_object",
                            "source_artifact_sha256": sha256_bytes(
                                source_path.read_bytes()
                            ),
                            "toy_check_artifact_sha256": None,
                            "bridge_artifact_sha256s": [],
                        }
                    ],
                    "route_invalidations": [],
                    "extremal_cases": [],
                    "claim_strength": [],
                    "contour_substitutions": [],
                    "claimed_structures": [],
                    "program_math_alignments": [],
                },
            }
            if "adverse_routing" in card:
                return_payload["attack_learning"] = None
            return_path = Path(assignment["return_path"])
            return_path.write_text(json.dumps(return_payload, sort_keys=True))
            production_receipt = lifecycle.ingest_return(
                round_id=production["round_id"],
                assignment_id=assignment["assignment_id"],
                worker_final_sha256=sha256_bytes(return_path.read_bytes()),
            )
            with patch.object(
                lifecycle,
                "_task_card_skill_version_at_least",
                return_value=True,
            ):
                supervision = lifecycle.create_supervision_round(
                    production["round_id"],
                    supervisor_scopes=["source_scope"],
                    host_task_scope_id="supervised-authority-review",
                )
            supervisor_card = json.loads(
                Path(supervision["assignments"][0]["task_card_path"]).read_text()
            )
            dossier = supervisor_card["mathematical_state"][
                "source_research_dossier"
            ]
            closure = dossier["metadata"]["supervised_production_authority"]
            self.assertEqual(closure[0]["active_fact_ids"], [premise.fact_id])
            self.assertEqual(dossier["dependencies"], [premise.fact_id])
            paths = {
                item["path"]
                for item in supervisor_card["mathematical_state"][
                    "related_artifacts"
                ]
            }
            self.assertIn("primary-source.pdf", paths)
            self.assertIn("source-evidence.json", paths)
            self.assertEqual(
                {
                    "hkr-primary.pdf",
                    "blr-primary.pdf",
                    "dml-primary.pdf",
                }.intersection(paths),
                {
                    "hkr-primary.pdf",
                    "blr-primary.pdf",
                    "dml-primary.pdf",
                },
            )
            self.assertTrue(
                {
                    item["artifact_sha256"]
                    for item in source_artifacts
                }.issubset(
                    lifecycle._task_primary_source_sha256s(supervisor_card)
                )
            )
            self.assertIn(assignment["task_card_relpath"], paths)

            source_review_assignment = supervision["assignments"][0]
            review_artifact_dir = (
                store.root / source_review_assignment["artifact_dir_relpath"]
            )
            review_artifact_dir.mkdir(parents=True, exist_ok=True)
            review_report_path = review_artifact_dir / "source-review.md"
            review_report_path.write_text(
                "The exact primary source use is clean.\n",
                encoding="utf-8",
            )
            review_report = {
                "path": str(review_report_path.relative_to(store.root)),
                "sha256": sha256_bytes(review_report_path.read_bytes()),
                "role": "research_supervision_report",
            }
            review_payload = {
                "schema_version": 5,
                "project_id": store.project_id(),
                "round_id": supervision["round_id"],
                "assignment_id": source_review_assignment["assignment_id"],
                "worker_id": source_review_assignment["worker_id"],
                "task_card_sha256": source_review_assignment[
                    "task_card_sha256"
                ],
                "blackboard_snapshot_sha256": source_review_assignment[
                    "blackboard_snapshot_sha256"
                ],
                "outcome": "challenge",
                "claim": "The exact primary source use has no bounded defect.",
                "content": "The review checked the exact cited source bytes.",
                "narrative": {
                    "rationale": "Preserve a completed source review downstream.",
                    "summary": "The exact source use is clean.",
                    "intuition": "A later reviewer should see this review and source.",
                    "limitations": "Nontruth Research only.",
                },
                "artifacts": [review_report],
                "obligation_dispositions": [
                    {
                        "obligation_id": obligation["obligation_id"],
                        "status": "complete",
                        "witness_artifact_sha256s": [review_report["sha256"]],
                        "rationale": "The exact source review is hash-bound.",
                    }
                    for obligation in supervisor_card["assurance_contract"][
                        "obligations"
                    ]
                ],
                "computation_manifest": None,
                "research_assurance": {
                    "source_uses": [
                        {
                            "source_key": "frozen-primary-source-review",
                            "use_kind": "result",
                            "source_strength": "fixed_object",
                            "target_strength": "fixed_object",
                            "source_artifact_sha256": sha256_bytes(
                                source_path.read_bytes()
                            ),
                            "toy_check_artifact_sha256": None,
                            "bridge_artifact_sha256s": [review_report["sha256"]],
                        }
                    ],
                    "route_invalidations": [],
                    "extremal_cases": [],
                    "claim_strength": [],
                    "contour_substitutions": [],
                    "claimed_structures": [],
                    "program_math_alignments": [],
                },
            }
            if "adverse_routing" in supervisor_card:
                review_payload["attack_learning"] = None
            review_return_path = Path(source_review_assignment["return_path"])
            review_return_path.write_text(
                json.dumps(review_payload, sort_keys=True),
                encoding="utf-8",
            )
            source_review_receipt = lifecycle.ingest_return(
                round_id=supervision["round_id"],
                assignment_id=source_review_assignment["assignment_id"],
                worker_final_sha256=sha256_bytes(
                    review_return_path.read_bytes()
                ),
            )

            literature_continuation = lifecycle.add_research(
                {
                    "kind": "literature",
                    "claim": (
                        "Use exactly the primary bytes accepted by the prior "
                        "source-scope review."
                    ),
                    "relation": "uses",
                    "related_research_ids": [
                        source_review_receipt["research_id"]
                    ],
                },
                actor="main",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            source_review_record = lifecycle._research_record(
                source_review_receipt["research_id"]
            )
            original_read_json = store._read_json

            def reject_task_card_reread(path: Path) -> dict:
                if Path(path) == Path(source_review_assignment["task_card_path"]):
                    raise AssertionError(
                        "authorization reread unhashed task-card bytes"
                    )
                return original_read_json(path)

            with patch.object(
                store,
                "_read_json",
                side_effect=reject_task_card_reread,
            ):
                direct_capabilities = (
                    lifecycle._exact_source_review_capabilities(
                        source_review_record
                    )
                )
            self.assertEqual(
                [item["sha256"] for item in direct_capabilities],
                [sha256_bytes(source_path.read_bytes())],
            )
            used_source_raw = source_path.read_bytes()
            source_path.write_bytes(b"drifted reviewed primary source")
            try:
                with self.assertRaisesRegex(
                    ValueError,
                    "source-review primary capability bytes/hash mismatch",
                ):
                    lifecycle._exact_source_review_capabilities(
                        source_review_record
                    )
            finally:
                source_path.write_bytes(used_source_raw)

            # Unused primary bytes on the old review card confer no authority
            # and therefore cannot become a liveness requirement for this
            # continuation.  Remove them during planning and restore the test
            # fixture afterward for the later independent supervision checks.
            unused_source_files = {
                store.root / item["artifact_path"]: (
                    store.root / item["artifact_path"]
                ).read_bytes()
                for item in source_artifacts
            }
            for path in unused_source_files:
                path.unlink()
            try:
                literature_round = lifecycle.create_production_round(
                    workers=1,
                    mode="literature",
                    research_ids=[literature_continuation["research_id"]],
                    host_task_scope_id="source-review-capability-continuation",
                )
            finally:
                for path, payload in unused_source_files.items():
                    path.write_bytes(payload)
            literature_card = json.loads(
                Path(
                    literature_round["assignments"][0]["task_card_path"]
                ).read_text()
            )
            literature_artifacts = literature_card["mathematical_state"][
                "related_artifacts"
            ]
            literature_paths = {item["path"] for item in literature_artifacts}
            self.assertIn("primary-source.pdf", literature_paths)
            self.assertIn(
                review_report["sha256"],
                {item["sha256"] for item in literature_artifacts},
            )
            self.assertIn(
                sha256_bytes(source_path.read_bytes()),
                lifecycle._task_primary_source_sha256s(literature_card),
            )
            self.assertFalse(
                {
                    "hkr-primary.pdf",
                    "blr-primary.pdf",
                    "dml-primary.pdf",
                }.intersection(literature_paths)
            )

            # A proof task may retain the completed source review as readable
            # provenance without reopening its primary bytes as a planning
            # capability.  Only a source-dependent or literature task owns
            # that source-use boundary.
            non_source_continuation = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Use only the reviewed mathematical conclusion.",
                    "relation": "uses",
                    "related_research_ids": [
                        source_review_receipt["research_id"]
                    ],
                    "source_dependent": False,
                },
                actor="main",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            used_source_raw = source_path.read_bytes()
            source_path.unlink()
            try:
                non_source_round = lifecycle.create_production_round(
                    workers=1,
                    mode="prove",
                    research_ids=[non_source_continuation["research_id"]],
                    host_task_scope_id="non-source-review-provenance",
                )
            finally:
                source_path.write_bytes(used_source_raw)
            non_source_card = json.loads(
                Path(
                    non_source_round["assignments"][0]["task_card_path"]
                ).read_text()
            )
            self.assertNotIn(
                sha256_bytes(source_path.read_bytes()),
                lifecycle._task_primary_source_sha256s(non_source_card),
            )

            downstream = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Use the reviewed result in one downstream component.",
                    "relation": "uses",
                    "related_research_ids": [production_receipt["research_id"]],
                },
                actor="main",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            downstream_round = lifecycle.create_production_round(
                workers=1,
                mode="prove",
                research_ids=[downstream["research_id"]],
                host_task_scope_id="source-continuity-production",
            )
            downstream_assignment = downstream_round["assignments"][0]
            downstream_card = json.loads(
                Path(downstream_assignment["task_card_path"]).read_text()
            )
            downstream_payload = {
                "schema_version": 5,
                "project_id": store.project_id(),
                "round_id": downstream_round["round_id"],
                "assignment_id": downstream_assignment["assignment_id"],
                "worker_id": downstream_assignment["worker_id"],
                "task_card_sha256": downstream_assignment["task_card_sha256"],
                "blackboard_snapshot_sha256": downstream_assignment[
                    "blackboard_snapshot_sha256"
                ],
                "outcome": "proof",
                "claim": "The downstream bounded consequence holds.",
                "content": "This fixture tests exact workflow provenance only.",
                "narrative": {
                    "rationale": "Exercise downstream source continuity.",
                    "summary": "One downstream product is complete.",
                    "intuition": "The source review remains useful context.",
                    "limitations": "Nontruth Research only.",
                },
                "artifacts": [],
                "obligation_dispositions": [],
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
            if "adverse_routing" in downstream_card:
                downstream_payload["attack_learning"] = None
            downstream_return_path = Path(downstream_assignment["return_path"])
            downstream_return_path.write_text(
                json.dumps(downstream_payload, sort_keys=True),
                encoding="utf-8",
            )
            lifecycle.ingest_return(
                round_id=downstream_round["round_id"],
                assignment_id=downstream_assignment["assignment_id"],
                worker_final_sha256=sha256_bytes(
                    downstream_return_path.read_bytes()
                ),
            )
            exact_source_projection = (
                lifecycle._exact_source_review_capabilities
            )

            def reject_recursive_historical_review(
                record: dict,
                *,
                _inspection_context=None,
            ) -> list[dict[str, str]]:
                if (
                    record["research_id"]
                    == source_review_receipt["research_id"]
                ):
                    raise AssertionError(
                        "current source supervisor recursively reopened an "
                        "old review instead of using its frozen source closure"
                    )
                return exact_source_projection(
                    record,
                    _inspection_context=_inspection_context,
                )

            with patch.object(
                lifecycle,
                "_task_card_skill_version_at_least",
                return_value=True,
            ), patch.object(
                lifecycle,
                "_exact_source_review_capabilities",
                side_effect=reject_recursive_historical_review,
            ):
                downstream_supervision = lifecycle.create_supervision_round(
                    downstream_round["round_id"],
                    supervisor_scopes=["source_scope"],
                    host_task_scope_id="source-continuity-review",
                )
            downstream_supervisor_card = json.loads(
                Path(
                    downstream_supervision["assignments"][0]["task_card_path"]
                ).read_text()
            )
            downstream_dossier = downstream_supervisor_card[
                "mathematical_state"
            ]["source_research_dossier"]
            self.assertIn(
                source_review_receipt["research_id"],
                downstream_dossier["related_research_ids"],
            )
            downstream_paths = {
                item["path"]
                for item in downstream_supervisor_card["mathematical_state"][
                    "related_artifacts"
                ]
            }
            self.assertIn("primary-source.pdf", downstream_paths)
            self.assertIn(
                review_report["sha256"],
                {
                    item["sha256"]
                    for item in downstream_supervisor_card[
                        "mathematical_state"
                    ]["related_artifacts"]
                },
            )
            self.assertFalse(
                {
                    "hkr-primary.pdf",
                    "blr-primary.pdf",
                    "dml-primary.pdf",
                }.intersection(downstream_paths)
            )

    def test_direct_related_source_avoids_historical_review_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            source_path = store.root / "current-primary-source.pdf"
            source_path.write_bytes(b"current exact primary source")
            direct_product = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "The current product freezes the source bytes.",
                    "artifacts": [
                        {
                            "path": str(source_path.relative_to(store.root)),
                            "sha256": sha256_bytes(source_path.read_bytes()),
                            "role": "primary_source_current_product",
                        }
                    ],
                },
                actor="worker",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            historical_review = lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "An older source review remains useful context.",
                    "relation": "reviews",
                    "related_research_ids": [direct_product["research_id"]],
                },
                actor="supervisor",
            )
            boundary_path = store.root / "current-boundary.md"
            boundary_path.write_text(
                "Use the directly related frozen source product.\n",
                encoding="utf-8",
            )
            continuation = lifecycle.add_research(
                {
                    "kind": "literature",
                    "claim": "Continue from the exact current source closure.",
                    "relation": "extends",
                    "related_research_ids": [
                        historical_review["research_id"],
                        direct_product["research_id"],
                    ],
                    "source_dependent": True,
                    "artifacts": [
                        {
                            "path": str(boundary_path.relative_to(store.root)),
                            "sha256": sha256_bytes(boundary_path.read_bytes()),
                            "role": "current_source_activation_boundary",
                        }
                    ],
                },
                actor="main",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            exact_projection = lifecycle._exact_source_review_capabilities

            def reject_historical_review_replay(
                record: dict,
                *,
                _inspection_context=None,
            ) -> list[dict[str, str]]:
                if record["research_id"] == historical_review["research_id"]:
                    raise AssertionError(
                        "a directly bound current source was replaced by "
                        "historical review replay"
                    )
                return exact_projection(
                    record,
                    _inspection_context=_inspection_context,
                )

            with patch.object(
                lifecycle,
                "_exact_source_review_capabilities",
                side_effect=reject_historical_review_replay,
            ):
                planned = lifecycle.create_production_round(
                    workers=1,
                    mode="literature",
                    research_ids=[continuation["research_id"]],
                    host_task_scope_id="direct-related-source-closure",
                )
            card = json.loads(
                Path(planned["assignments"][0]["task_card_path"]).read_text()
            )
            self.assertIn(
                sha256_bytes(source_path.read_bytes()),
                lifecycle._task_primary_source_sha256s(card),
            )
            self.assertIn(
                historical_review["research_id"],
                card["mathematical_state"]["source_research_dossier"][
                    "related_research_ids"
                ],
            )

    def test_dual_scope_proof_assignment_does_not_transmit_source_capability(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            source_component_sha256 = "1" * 64
            source_receipts = [{"receipt": "exact-production-receipt"}]
            cycle = {
                "revision": "chalxius-v5-two-subround-research-2",
                "subround": "supervision",
                "source_round_id": "round-20260901T000000Z-11111111",
                "source_round_manifest_sha256": "2" * 64,
                "source_receipts_sha256": sha256_json(source_receipts),
                "source_component_id": (
                    "component-" + source_component_sha256[:16]
                ),
                "source_component_sha256": source_component_sha256,
                "supervisor_scopes": ["proof_logic", "source_scope"],
                "computation_policy": "core_code_review_before_formal_execution",
                "repair_policy": "copy_on_write_next_research_cycle",
                "pulse_policy": "not_used",
                "truth_effect": "none",
            }
            round_id = "round-20260901T000001Z-22222222"
            assignment_id = "a01-aaaaaaaaaaaa-refute"
            round_dir = store.rounds_dir / round_id
            task_cards_dir = round_dir / "task-cards"
            assignments_dir = round_dir / "assignments"
            task_cards_dir.mkdir(parents=True)
            assignments_dir.mkdir()
            binding = {
                "revision": "chalxius-v5-research-supervision-2",
                "supervisor_scope": "proof_logic",
                "source_round_id": cycle["source_round_id"],
                "source_round_manifest_sha256": cycle[
                    "source_round_manifest_sha256"
                ],
                "source_receipts": source_receipts,
                "source_receipts_sha256": cycle["source_receipts_sha256"],
                "source_component_id": cycle["source_component_id"],
                "source_component_sha256": cycle["source_component_sha256"],
                "review_policy": "attack_exact_production_outputs",
                "repair_policy": "copy_on_write_next_research_cycle",
                "pulse_policy": "not_used",
                "truth_effect": "none",
            }
            card = {
                "schema_version": 5,
                "project_id": store.project_id(),
                "round_id": round_id,
                "assignment_id": assignment_id,
                "worker_id": assignment_id,
                "research_id": "cccccccccccc",
                "work_mode": "refute",
                "research_cycle": cycle,
                "mathematical_state": {
                    "related_artifacts": [],
                    "authority_snapshot": {"capabilities": []},
                    "source_research_dossier": {
                        "metadata": {
                            "research_supervision": binding,
                            "artifacts": [],
                        }
                    },
                },
            }
            card["task_card_semantic_sha256"] = sha256_json(card)
            card_raw = json.dumps(card, sort_keys=True).encode("utf-8")
            task_card_path = task_cards_dir / f"{assignment_id}.json"
            task_card_path.write_bytes(card_raw)
            task_card_sha256 = sha256_bytes(card_raw)
            assignment = {
                "assignment_id": assignment_id,
                "worker_id": assignment_id,
                "research_id": card["research_id"],
                "work_mode": "refute",
                "task_card_relpath": str(task_card_path.relative_to(store.root)),
                "task_card_sha256": task_card_sha256,
            }
            assignment["assignment_sha256"] = sha256_json(assignment)
            (assignments_dir / f"{assignment_id}.json").write_text(
                json.dumps(assignment, sort_keys=True),
                encoding="utf-8",
            )

            manifest = {
                "schema_version": 5,
                "project_id": store.project_id(),
                "round_id": round_id,
                "research_cycle": cycle,
                "assignments": [assignment],
            }
            manifest["manifest_sha256"] = sha256_json(manifest)
            (round_dir / "round.json").write_text(
                json.dumps(manifest, sort_keys=True),
                encoding="utf-8",
            )

            record = {
                "research_id": "aaaaaaaaaaaa",
                "metadata": {
                    # proof_logic owns theorem application and may therefore
                    # cite source bytes without becoming a source review.
                    "source_uses": [
                        {"source_artifact_sha256": "4" * 64}
                    ],
                    "assignment_provenance": {
                        "round_id": round_id,
                        "assignment_id": assignment_id,
                        "task_card_sha256": task_card_sha256,
                        "work_mode": assignment["work_mode"],
                        "worker_id": assignment["worker_id"],
                    },
                    "task_binding": {
                        "round_id": round_id,
                        "assignment_id": assignment_id,
                        "task_card_sha256": task_card_sha256,
                        "return_sha256": "3" * 64,
                    },
                },
            }
            self.assertEqual(
                lifecycle._exact_source_review_capabilities(record),
                [],
            )
            proof_planner = {
                "claim": "Review the proof only.",
                "content": "",
                "rationale": "",
                "source": "",
                "metadata": {
                    "source_dependent": False,
                    "research_supervision": binding,
                    "artifacts": [],
                },
            }
            self.assertEqual(
                lifecycle._source_capability_projection_policy(
                    proof_planner,
                    mode="refute",
                    research_cycle=cycle,
                ),
                (False, False),
            )
            source_binding = dict(binding)
            source_binding["supervisor_scope"] = "source_scope"
            source_planner = {
                "claim": "Review the frozen source closure.",
                "content": "",
                "rationale": "",
                "source": "",
                "metadata": {
                    "source_dependent": True,
                    "research_supervision": source_binding,
                    "artifacts": [
                        {
                            "path": "primary-source.pdf",
                            "sha256": "4" * 64,
                            "role": "primary_source",
                        }
                    ],
                },
            }
            self.assertEqual(
                lifecycle._source_capability_projection_policy(
                    source_planner,
                    mode="refute",
                    research_cycle=cycle,
                ),
                (True, False),
            )

    def test_structured_source_evidence_requires_all_declared_primary_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            declared = []
            for source_key, filename, payload in (
                ("HKR", "hkr.pdf", b"HKR"),
                ("BLR", "blr.pdf", b"BLR"),
                ("DML", "dml.pdf", b"DML"),
            ):
                path = store.root / filename
                path.write_bytes(payload)
                declared.append(
                    {
                        "source_key": source_key,
                        "artifact_path": filename,
                        "artifact_sha256": sha256_bytes(payload),
                    }
                )
            evidence = store.root / "evidence.json"
            evidence.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_artifacts": declared,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            card = {
                "mathematical_state": {
                    "related_artifacts": [
                        {
                            "path": "evidence.json",
                            "sha256": sha256_bytes(evidence.read_bytes()),
                            "role": "source_evidence",
                        }
                    ]
                }
            }
            capabilities = lifecycle._structured_source_evidence_capabilities_from_card(
                card=card,
                origin="source-scope",
            )
            self.assertEqual(
                {item["path"] for item in capabilities},
                {"hkr.pdf", "blr.pdf", "dml.pdf"},
            )
            (store.root / "blr.pdf").unlink()
            with self.assertRaisesRegex(
                ValueError,
                "structured source-evidence source artifact",
            ):
                lifecycle._structured_source_evidence_capabilities_from_card(
                    card=card,
                    origin="source-scope",
                )

    def test_structured_source_evidence_normalizes_frozen_field_spellings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            payload = b"historical source bytes"
            authorized = store.root / "authorized.pdf"
            returned = store.root / "returned.pdf"
            path_variant = store.root / "path-variant.pdf"
            authorized.write_bytes(payload)
            returned.write_bytes(payload)
            path_variant.write_bytes(payload)
            digest = sha256_bytes(payload)
            evidence = store.root / "evidence.json"
            evidence.write_text(
                json.dumps(
                    {
                        "source_artifacts": [
                            {
                                "source_key": "HISTORICAL",
                                "card_authorized_path": "authorized.pdf",
                                "returned_copy_path": "returned.pdf",
                                "artifact_sha256": digest,
                            },
                            {
                                "source_key": "PATH_VARIANT",
                                "path": "path-variant.pdf",
                                "sha256": digest,
                            },
                        ]
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            card = {
                "mathematical_state": {
                    "related_artifacts": [
                        {
                            "path": "evidence.json",
                            "sha256": sha256_bytes(evidence.read_bytes()),
                            "role": "source_evidence",
                        }
                    ]
                }
            }
            capabilities = lifecycle._structured_source_evidence_capabilities_from_card(
                card=card,
                origin="source-scope",
            )
            self.assertEqual(
                {item["path"] for item in capabilities},
                {"returned.pdf", "path-variant.pdf"},
            )

    def test_structured_source_evidence_skips_locator_only_and_rejects_path_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary) / "project")
            lifecycle = store.v5_lifecycle()
            authorized = store.root / "authorized.pdf"
            returned = store.root / "returned.pdf"
            authorized.write_bytes(b"source bytes")
            returned.write_bytes(b"drifted bytes")
            digest = sha256_bytes(authorized.read_bytes())

            def card_for(source_item: dict[str, str]) -> dict[str, object]:
                evidence = store.root / "evidence.json"
                evidence.write_text(
                    json.dumps({"source_artifacts": [source_item]}, sort_keys=True),
                    encoding="utf-8",
                )
                return {
                    "mathematical_state": {
                        "related_artifacts": [
                            {
                                "path": "evidence.json",
                                "sha256": sha256_bytes(evidence.read_bytes()),
                                "role": "source_evidence",
                            }
                        ]
                    }
                }

            with self.assertRaisesRegex(ValueError, "bytes/hash mismatch"):
                lifecycle._structured_source_evidence_capabilities_from_card(
                    card=card_for(
                        {
                            "source_key": "DRIFT",
                            "card_authorized_path": "authorized.pdf",
                            "returned_copy_path": "returned.pdf",
                            "artifact_sha256": digest,
                        }
                    ),
                    origin="source-scope",
                )
            self.assertEqual(
                lifecycle._structured_source_evidence_capabilities_from_card(
                    card=card_for(
                        {
                            "source_key": "LOCATOR_ONLY",
                            "locator": "Appendix A",
                            "artifact_sha256": digest,
                        }
                    ),
                    origin="source-scope",
                ),
                [],
            )


if __name__ == "__main__":
    unittest.main()
