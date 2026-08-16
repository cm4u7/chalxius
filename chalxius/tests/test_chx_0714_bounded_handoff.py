from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from mathgraph.cli import _command_requires_mutation_lock, build_parser
from mathgraph.contracts import sha256_bytes
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
            production = lifecycle.add_research(
                {
                    "kind": "proof_attempt",
                    "claim": "Produce the exact Candidate Fact.",
                    "artifacts": [
                        {
                            "path": "candidate.md",
                            "sha256": sha256_bytes(raw),
                            "role": "candidate_fact",
                        }
                    ],
                },
                actor="producer",
                assurance_contract_revision=V5_ASSURANCE_CONTRACT_REVISION,
            )
            supervision = lifecycle.add_research(
                {
                    "kind": "challenge",
                    "claim": "The bounded supervision result is clean.",
                    "relation": "challenges",
                    "related_research_ids": [production["research_id"]],
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
                        production["research_id"]
                    )
            record = lifecycle._research_record(prepared["research_id"])
            self.assertTrue(record["metadata"]["independent_adverse_required"])
            self.assertEqual(
                set(record["related_research_ids"]),
                {production["research_id"], supervision["research_id"]},
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
                        production["research_id"],
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
            self.assertEqual(set(calls), {item["research_id"] for item in visible})
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
        base = ["--root", "/tmp/project", "--role", "main"]
        frontier = parser.parse_args([*base, "frontier"])
        certification = parser.parse_args(
            [*base, "certification-record", "--input", "decision.json"]
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
                return_payload["attack_learning"] = None
            return_path = Path(assignment["return_path"])
            return_path.write_text(json.dumps(return_payload, sort_keys=True))
            lifecycle.ingest_return(
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
            self.assertIn(assignment["task_card_relpath"], paths)

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


if __name__ == "__main__":
    unittest.main()
