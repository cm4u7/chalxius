from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from mathgraph.cli import _authorized_fact_evidence_inventory
from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.model import Fact
from mathgraph.roles import allowed_commands
from tests import test_v5_lifecycle as v5_tests


PAPER_LIBRARY_CLI = Path(__file__).resolve().parents[1] / "scripts" / "paperlib"


class EvidencePlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.helper = v5_tests.V5LifecycleTests()

    def initialize_library(self, root: Path) -> None:
        completed = subprocess.run(
            [
                str(PAPER_LIBRARY_CLI),
                "init",
                "--root",
                str(root),
                "--library-id",
                "evidence-tests",
                "--name",
                "Evidence tests",
            ],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def library_environment(self, root: Path) -> dict[str, str]:
        return {
            "CHALXIUS_EVIDENCE_LIBRARY_ROOT": str(root),
            "CHALXIUS_EVIDENCE_LIBRARY_CLI": str(PAPER_LIBRARY_CLI),
        }

    def verify_library(self, root: Path) -> dict[str, object]:
        completed = subprocess.run(
            [str(PAPER_LIBRARY_CLI), "verify", "--root", str(root)],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_reviewed_paper_freeze_auto_archives_exact_pdf_or_leaves_durable_outbox(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            unconfigured = self.helper._store(base / "unconfigured", "UNCONFIGURED")
            text_artifact = unconfigured.root / "paper.txt"
            text_artifact.write_text(
                "The supporting lemma holds.\n"
                "The root theorem follows from the supporting lemma.\n",
                encoding="utf-8",
            )
            text_source = {
                "artifact_sha256": sha256_bytes(text_artifact.read_bytes()),
                "artifact_locator": str(text_artifact),
                "title": "Text-only fixture",
                "version": "v1",
                "mime_type": "text/plain",
                "retrieved_at": "2026-07-29T00:00:00Z",
                "inspection_methods": ["rendered_primary", "text_extraction_secondary"],
            }
            with unconfigured.v5_mutation_lock(command="paper-logic-init"):
                unconfigured.paper_logic().initialize(actor="main")
            with unconfigured.v5_mutation_lock(command="paper-logic-freeze"):
                _, frozen = self.helper._freeze_paper_bundle(
                    store=unconfigured,
                    bundle=self.helper._paper_logic_bundle(
                        store=unconfigured, source=text_source
                    ),
                    artifact=text_artifact,
                )
            self.assertEqual(frozen["evidence_sync"]["status"], "pending_unconfigured")
            self.assertTrue(Path(frozen["evidence_sync"]["outbox_path"]).is_file())
            self.assertTrue(
                unconfigured.paper_logic().snapshot_manifest(frozen["snapshot_id"])
            )

            library_root = base / "library"
            self.initialize_library(library_root)
            with patch.dict(
                os.environ,
                self.library_environment(library_root),
                clear=False,
            ):
                configured = self.helper._store(base / "configured", "CONFIGURED")
                pdf = configured.root / "paper.pdf"
                pdf.write_bytes(
                    b"%PDF-1.4\n"
                    b"The supporting lemma holds.\n"
                    b"The root theorem follows from the supporting lemma.\n"
                    b"%%EOF\n"
                )
                source = {
                    "artifact_sha256": sha256_bytes(pdf.read_bytes()),
                    "artifact_locator": str(pdf),
                    "title": "Exact PDF fixture",
                    "version": "v1",
                    "mime_type": "application/pdf",
                    "retrieved_at": "2026-07-29T00:00:00Z",
                    "inspection_methods": [
                        "rendered_primary",
                        "text_extraction_secondary",
                    ],
                }
                with configured.v5_mutation_lock(command="paper-logic-init"):
                    configured.paper_logic().initialize(actor="main")
                with configured.v5_mutation_lock(command="paper-logic-freeze"):
                    _, archived = self.helper._freeze_paper_bundle(
                        store=configured,
                        bundle=self.helper._paper_logic_bundle(
                            store=configured, source=source
                        ),
                        artifact=pdf,
                    )
                self.assertEqual(archived["evidence_sync"]["status"], "synced")
                self.assertTrue(Path(archived["evidence_sync"]["receipt_path"]).is_file())
                status = configured.evidence().status()
                self.assertEqual(status["synced_snapshot_count"], 1)
                self.assertEqual(status["pending_request_ids"], [])
                verification = self.verify_library(library_root)
                self.assertEqual(verification["evidence_items"], 1)
                self.assertEqual(verification["paper_evidence_attestations"], 1)

    def test_explicit_fact_import_verified_bridge_and_correction_impact(self) -> None:
        self.assertNotIn("evidence-import-fact-graph", allowed_commands("main"))
        self.assertIn("evidence-import-fact-graph", allowed_commands("operator"))
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            library_root = base / "library"
            self.initialize_library(library_root)
            with patch.dict(
                os.environ,
                self.library_environment(library_root),
                clear=False,
            ):
                source = self.helper._store(base / "source", "SOURCE-PROJECT")
                source_lifecycle = source.v5_lifecycle()
                source_research = source_lifecycle.add_research(
                    {"kind": "proof_attempt", "claim": "The source theorem holds."},
                    actor="source-producer",
                )
                source_fact = Fact(
                    problem_id=source.project_id(),
                    author="source-producer",
                    predecessors=[],
                    statement="[CLAIM:SOURCE] The source theorem holds.",
                    proof="Direct source proof.",
                )
                source_release = source_lifecycle.candidate_release(
                    self.helper._release_payload(
                        facts=[source_fact],
                        research_ids=[source_research["research_id"]],
                    ),
                    producer="source-producer",
                )
                source_decision = source_lifecycle.certification_record(
                    self.helper._correct_decision_payload(
                        source_lifecycle, source_release, reviewer="source-verifier"
                    )
                )
                source_lifecycle.fact_admit(
                    release_id=source_release["release_id"],
                    decision_id=source_decision["decision_id"],
                    gateway="source-gateway",
                )

                destination = self.helper._store(
                    base / "destination", "DESTINATION-PROJECT"
                )
                inventory = _authorized_fact_evidence_inventory(
                    destination, str(source.root)
                )
                imported = destination.evidence().import_fact_graph(
                    source_root=str(source.root),
                    inventory=inventory,
                    actor="operator",
                    reason="The user explicitly requested this exact Fact Graph as Evidence.",
                )
                self.assertFalse(imported["cross_project_fact_authority"])
                self.assertEqual(destination.fact_ids(), [])

                selection = {
                    "schema_version": 1,
                    "destination_project_id": destination.project_id(),
                    "items": [
                        {
                            "evidence_id": imported["evidence_id"],
                            "node_ids": [],
                            "fact_ids": [source_fact.fact_id],
                        }
                    ],
                    "target_claim": "The destination theorem uses the selected source result.",
                    "rationale": "Exact source Fact chosen for independent destination review.",
                }
                selection_path = destination.root / "evidence" / "selection.json"
                selection_path.parent.mkdir(parents=True, exist_ok=True)
                selection_path.write_text(json.dumps(selection) + "\n", encoding="utf-8")
                bridge_path = destination.root / "evidence" / "prepared-bridge.json"
                prepared = destination.evidence().prepare_bridge(
                    selection_path=str(selection_path),
                    actor="main",
                    reason="Prepare a nontruth source capsule for a fresh verifier.",
                    output_path=str(bridge_path),
                )
                self.assertTrue(destination.evidence().bridge_check(prepared["bridge_id"])["current"])

                destination_lifecycle = destination.v5_lifecycle()
                destination_research = destination_lifecycle.add_research(
                    {
                        "kind": "proof_attempt",
                        "claim": "The destination theorem holds after independent reconstruction.",
                    },
                    actor="destination-producer",
                )
                destination_fact = Fact(
                    problem_id=destination.project_id(),
                    author="destination-producer",
                    predecessors=[],
                    statement="[CLAIM:DESTINATION] The destination theorem holds.",
                    proof="Independent reconstruction using the sealed source context.",
                )
                payload = self.helper._release_payload(
                    facts=[destination_fact],
                    research_ids=[destination_research["research_id"]],
                )
                bridge_sha = sha256_bytes(bridge_path.read_bytes())
                payload["artifacts"] = [
                    {
                        "path": bridge_path.relative_to(destination.root).as_posix(),
                        "sha256": bridge_sha,
                        "role": "evidence_bridge_capsule",
                    }
                ]
                payload["verification_plan"]["authorized_artifact_roles"] = [
                    "evidence_bridge_capsule"
                ]
                payload["verification_plan"]["required_checks"].append(
                    "evidence_bridge_current"
                )
                payload["evidence_bridge_refs"] = [
                    {
                        "bridge_id": prepared["bridge_id"],
                        "bridge_artifact_sha256": bridge_sha,
                    }
                ]
                release = destination_lifecycle.candidate_release(
                    payload, producer="destination-producer"
                )
                capsule = destination_lifecycle.verifier_capsule(release["release_id"])
                self.assertEqual(
                    capsule["evidence_bridge_refs"][0]["bridge_id"],
                    prepared["bridge_id"],
                )
                decision = destination_lifecycle.certification_record(
                    self.helper._correct_decision_payload(
                        destination_lifecycle, release, reviewer="destination-verifier"
                    )
                )
                destination_lifecycle.fact_admit(
                    release_id=release["release_id"],
                    decision_id=decision["decision_id"],
                    gateway="destination-gateway",
                )

                third = self.helper._store(base / "third", "THIRD-PROJECT")
                destination_inventory = _authorized_fact_evidence_inventory(
                    third, str(destination.root)
                )
                derived = third.evidence().import_fact_graph(
                    source_root=str(destination.root),
                    inventory=destination_inventory,
                    actor="operator",
                    reason=(
                        "The user explicitly requested the destination Fact Graph as "
                        "Evidence while retaining its upstream Evidence lineage."
                    ),
                )
                derived_results = third.evidence().query(
                    query=derived["evidence_id"],
                    limit=10,
                    include_inactive=True,
                )["results"]
                self.assertEqual(len(derived_results), 1)
                self.assertEqual(
                    derived_results[0]["source"]["upstream_evidence_ids"],
                    [imported["evidence_id"]],
                )

                derived_selection = {
                    "schema_version": 1,
                    "destination_project_id": third.project_id(),
                    "items": [
                        {
                            "evidence_id": derived["evidence_id"],
                            "node_ids": [],
                            "fact_ids": [destination_fact.fact_id],
                        }
                    ],
                    "target_claim": "A third theorem considers the derived destination Fact.",
                    "rationale": "Exercise transitive Evidence correction propagation.",
                }
                derived_selection_path = third.root / "evidence" / "selection.json"
                derived_selection_path.parent.mkdir(parents=True, exist_ok=True)
                derived_selection_path.write_text(
                    json.dumps(derived_selection) + "\n", encoding="utf-8"
                )
                derived_bridge_path = third.root / "evidence" / "prepared-bridge.json"
                derived_prepared = third.evidence().prepare_bridge(
                    selection_path=str(derived_selection_path),
                    actor="main",
                    reason="Prepare the derived Evidence for a future fresh verifier.",
                    output_path=str(derived_bridge_path),
                )
                self.assertTrue(
                    third.evidence().bridge_check(derived_prepared["bridge_id"])[
                        "current"
                    ]
                )

                marked = destination.evidence().mark(
                    evidence_id=imported["evidence_id"],
                    status="challenged",
                    actor="operator",
                    reason="A later source audit found a potentially load-bearing error.",
                    replacement_evidence_ids=[],
                    supersedes_disposition_ids=[],
                    artifact="",
                )
                self.assertEqual(
                    marked["affected_evidence_ids"],
                    sorted([imported["evidence_id"], derived["evidence_id"]]),
                )
                self.assertEqual(
                    {
                        (item["bridge_id"], item["destination_project_id"])
                        for item in marked["affected_bridges"]
                    },
                    {
                        (prepared["bridge_id"], destination.project_id()),
                        (derived_prepared["bridge_id"], third.project_id()),
                    },
                )
                self.assertIn(
                    destination_fact.fact_id,
                    marked["local_impact"][
                        "admitted_fact_ids_requiring_operator_review"
                    ],
                )
                self.assertEqual(destination.fact_ids(), [destination_fact.fact_id])
                self.assertEqual(
                    destination_lifecycle.release(release["release_id"])["release_id"],
                    release["release_id"],
                )
                with self.assertRaisesRegex(ValueError, "stale"):
                    destination_lifecycle.verifier_capsule(release["release_id"])
                with self.assertRaisesRegex(ValueError, "stale"):
                    third.evidence().bridge_check(derived_prepared["bridge_id"])
                derived_after = third.evidence().query(
                    query=derived["evidence_id"],
                    limit=10,
                    include_inactive=True,
                )["results"]
                self.assertEqual(derived_after[0]["status"], "stale_source")
                self.assertEqual(
                    derived_after[0]["stale_upstream_evidence_ids"],
                    [imported["evidence_id"]],
                )
                self.assertEqual(
                    third.evidence().query(
                        query=derived["evidence_id"],
                        limit=10,
                        include_inactive=False,
                    )["results"],
                    [],
                )
                impact = destination.evidence().impact_report(
                    evidence_id=imported["evidence_id"]
                )
                self.assertFalse(impact["automatic_fact_revocation"])
                self.assertEqual(
                    impact["admitted_fact_ids_requiring_operator_review"],
                    [destination_fact.fact_id],
                )
                verification = self.verify_library(library_root)
                self.assertEqual(verification["fact_evidence_capsules"], 2)
                self.assertEqual(verification["bridge_capsules"], 2)

                derived_record_path = (
                    library_root
                    / "records"
                    / "evidence_items"
                    / "by-id"
                    / f"{derived['evidence_id']}.json"
                )
                derived_record = json.loads(
                    derived_record_path.read_text(encoding="utf-8")
                )
                inconsistent_payload = {
                    key: value
                    for key, value in derived_record.items()
                    if key not in {"object_id", "record_sha256"}
                }
                inconsistent_payload["source"] = {
                    **inconsistent_payload["source"],
                    "upstream_evidence_ids": [],
                }

                def content_hash(value: object) -> str:
                    return sha256_bytes(
                        json.dumps(
                            value,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    )

                inconsistent_id = "evd-" + content_hash(inconsistent_payload)
                inconsistent_core = {
                    **inconsistent_payload,
                    "object_id": inconsistent_id,
                }
                inconsistent_record = {
                    **inconsistent_core,
                    "record_sha256": content_hash(inconsistent_core),
                }
                inconsistent_path = derived_record_path.with_name(
                    f"{inconsistent_id}.json"
                )
                inconsistent_path.write_text(
                    json.dumps(
                        inconsistent_record,
                        ensure_ascii=False,
                        sort_keys=True,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                inconsistent_verify = subprocess.run(
                    [
                        str(PAPER_LIBRARY_CLI),
                        "verify",
                        "--root",
                        str(library_root),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                self.assertNotEqual(inconsistent_verify.returncode, 0)
                self.assertIn(
                    "stored upstream dependency binding mismatch",
                    inconsistent_verify.stderr,
                )

    def test_old_runtime_bound_round_does_not_block_fact_evidence_bridge(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            library_root = base / "library"
            self.initialize_library(library_root)
            with patch.dict(
                os.environ,
                self.library_environment(library_root),
                clear=False,
            ):
                source = self.helper._store(base / "source", "OLD-V5-SOURCE")
                lifecycle = source.v5_lifecycle()
                research = lifecycle.add_research(
                    {
                        "kind": "proof_attempt",
                        "claim": "The old-runtime source theorem holds.",
                    },
                    actor="source-producer",
                )
                fact = Fact(
                    problem_id=source.project_id(),
                    author="source-producer",
                    predecessors=[],
                    statement="[CLAIM:OLD] The old-runtime source theorem holds.",
                    proof="Exact source proof preserved across runtime upgrades.",
                )
                release = lifecycle.candidate_release(
                    self.helper._release_payload(
                        facts=[fact],
                        research_ids=[research["research_id"]],
                    ),
                    producer="source-producer",
                )
                decision = lifecycle.certification_record(
                    self.helper._correct_decision_payload(
                        lifecycle, release, reviewer="source-verifier"
                    )
                )
                lifecycle.fact_admit(
                    release_id=release["release_id"],
                    decision_id=decision["decision_id"],
                    gateway="source-gateway",
                )

                frozen_root = base / "frozen-chalxius-0.4.4"
                frozen_root.mkdir()
                frozen_version = frozen_root / "VERSION"
                frozen_payload = frozen_root / "runtime_payload.txt"
                frozen_manifest = frozen_root / "MANIFEST.sha256"
                frozen_version.write_text("0.4.4\n", encoding="utf-8")
                frozen_payload.write_text(
                    "frozen fixture payload\n", encoding="utf-8"
                )
                frozen_manifest.write_text(
                    f"{sha256_bytes(frozen_version.read_bytes())}  VERSION\n"
                    f"{sha256_bytes(frozen_payload.read_bytes())}  runtime_payload.txt\n",
                    encoding="utf-8",
                )
                legacy_semantic = {
                    "schema_version": 1,
                    "skill_root": str(frozen_root),
                    "skill_version": "0.4.4",
                    "version_file_sha256": sha256_bytes(
                        frozen_version.read_bytes()
                    ),
                    "manifest_file_sha256": sha256_bytes(
                        frozen_manifest.read_bytes()
                    ),
                    "worker_ledger_contract": (
                        "exact_task_card_runtime_binding_required"
                    ),
                }
                legacy_binding = {
                    **legacy_semantic,
                    "runtime_identity_sha256": sha256_json(legacy_semantic),
                }
                with patch.object(
                    type(lifecycle),
                    "_runtime_binding",
                    return_value=legacy_binding,
                ):
                    lifecycle.create_round(
                        workers=1,
                        research_ids=[research["research_id"]],
                    )

                self.assertFalse(source.audit().current_ok)
                destination = self.helper._store(
                    base / "destination", "OLD-V5-DESTINATION"
                )
                inventory = _authorized_fact_evidence_inventory(
                    destination, str(source.root)
                )
                self.assertTrue(inventory["source_audit"]["current_ok"])
                self.assertEqual(
                    inventory["source_audit_scope"],
                    "active_v5_fact_authority_only",
                )
                self.assertEqual(
                    inventory["source_audit"]["active_fact_ids"],
                    [fact.fact_id],
                )
                imported = destination.evidence().import_fact_graph(
                    source_root=str(source.root),
                    inventory=inventory,
                    actor="operator",
                    reason=(
                        "The user explicitly requested this older V5 Fact Graph "
                        "as Evidence without reopening its frozen work."
                    ),
                )
                self.assertEqual(
                    imported["source_audit_scope"],
                    "active_v5_fact_authority_only",
                )
                selection = {
                    "schema_version": 1,
                    "destination_project_id": destination.project_id(),
                    "items": [
                        {
                            "evidence_id": imported["evidence_id"],
                            "node_ids": [],
                            "fact_ids": [fact.fact_id],
                        }
                    ],
                    "target_claim": "A future claim may consult the old V5 Fact.",
                    "rationale": "Exercise version-independent Evidence retrieval.",
                }
                selection_path = destination.root / "evidence" / "selection.json"
                selection_path.parent.mkdir(parents=True, exist_ok=True)
                selection_path.write_text(
                    json.dumps(selection) + "\n", encoding="utf-8"
                )
                prepared = destination.evidence().prepare_bridge(
                    selection_path=str(selection_path),
                    actor="main",
                    reason="Prepare a nontruth compatibility bridge.",
                    output_path=str(
                        destination.root / "evidence" / "prepared-bridge.json"
                    ),
                )
                self.assertTrue(
                    destination.evidence().bridge_check(prepared["bridge_id"])[
                        "current"
                    ]
                )
                indexed = subprocess.run(
                    [
                        str(PAPER_LIBRARY_CLI),
                        "index",
                        "--root",
                        str(library_root),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                self.assertEqual(indexed.returncode, 0, indexed.stderr)
                verification = self.verify_library(library_root)
                self.assertEqual(verification["evidence_items"], 1)
                self.assertEqual(verification["bridge_capsules"], 1)
                self.assertEqual(destination.fact_ids(), [])

    def test_fact_evidence_truth_audit_rejects_missing_acceptance_event(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = self.helper._store(base / "source", "BROKEN-V5-SOURCE")
            lifecycle = source.v5_lifecycle()
            research = lifecycle.add_research(
                {"kind": "proof_attempt", "claim": "The source claim holds."},
                actor="source-producer",
            )
            fact = Fact(
                problem_id=source.project_id(),
                author="source-producer",
                predecessors=[],
                statement="[CLAIM:BROKEN] The source claim holds.",
                proof="Source proof.",
            )
            release = lifecycle.candidate_release(
                self.helper._release_payload(
                    facts=[fact], research_ids=[research["research_id"]]
                ),
                producer="source-producer",
            )
            decision = lifecycle.certification_record(
                self.helper._correct_decision_payload(
                    lifecycle, release, reviewer="source-verifier"
                )
            )
            lifecycle.fact_admit(
                release_id=release["release_id"],
                decision_id=decision["decision_id"],
                gateway="source-gateway",
            )
            source.verification_log.write_text("", encoding="utf-8")
            destination = self.helper._store(
                base / "destination", "BROKEN-V5-DESTINATION"
            )
            with self.assertRaisesRegex(ValueError, "acceptance event"):
                _authorized_fact_evidence_inventory(
                    destination, str(source.root)
                )
            self.assertFalse((destination.root / "evidence").exists())


if __name__ == "__main__":
    unittest.main()
