from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import paper_library as library  # noqa: E402


class PaperLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.repo = self.base / "library"
        self.chalxius = self.base / "chalxius"
        self.chalxius.mkdir()
        (self.chalxius / "VERSION").write_text("0.4.4\n", encoding="utf-8")
        (self.chalxius / "MANIFEST.sha256").write_text(
            "0" * 64 + "  VERSION\n", encoding="utf-8"
        )
        (self.chalxius / "INHERITANCE.lock.json").write_text(
            "{}\n", encoding="utf-8"
        )
        self.pdf = self.base / "paper.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\n% exact test artifact\n%%EOF\n")
        self.graph = self.base / "project" / "paper_logic"
        (self.graph / "snapshots" / "by-id" / ("pls-" + "a" * 64)).mkdir(
            parents=True
        )
        (self.graph / "store.json").write_text(
            json.dumps(
                {
                    "feature_revision": "paper-logic-1",
                    "project_id": "TEST-PROJECT",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.graph / "node.json").write_text('{"claim":"A"}\n', encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_command(self, *arguments: str) -> None:
        code = library.main(list(arguments))
        self.assertEqual(code, 0)

    def initialize(self) -> None:
        self.run_command(
            "init",
            "--root",
            str(self.repo),
            "--library-id",
            "test-zotero",
            "--name",
            "Test Library",
        )

    def add_chain(self) -> tuple[str, str, str]:
        self.initialize()
        paper_args = library.parser().parse_args(
            [
                "paper-add",
                "--root",
                str(self.repo),
                "--zotero-library-id",
                "test-zotero",
                "--zotero-item-key",
                "ABCD1234",
                "--citekey",
                "author2026",
                "--title",
                "A test paper",
                "--author",
                "A. Author",
            ]
        )
        paper = paper_args.function(paper_args)
        version_args = library.parser().parse_args(
            [
                "version-add",
                "--root",
                str(self.repo),
                "--paper-id",
                paper["paper_id"],
                "--label",
                "arxiv-v2",
                "--kind",
                "arxiv",
                "--pdf",
                str(self.pdf),
                "--source-locator",
                "https://arxiv.org/pdf/0000.00000v2",
                "--arxiv-id",
                "0000.00000v2",
                "--retrieved-at",
                "2026-07-29",
            ]
        )
        version = version_args.function(version_args)
        graph_args = library.parser().parse_args(
            [
                "graph-add",
                "--root",
                str(self.repo),
                "--paper-id",
                paper["paper_id"],
                "--version-id",
                version["version_id"],
                "--graph-root",
                str(self.graph),
                "--graph-kind",
                "paper_logic_audit",
                "--chalxius-root",
                str(self.chalxius),
            ]
        )
        graph = graph_args.function(graph_args)
        return paper["paper_id"], version["version_id"], graph["graph_id"]

    def add_reviewed_paper_evidence(self) -> tuple[str, str, str]:
        paper_id, version_id, _ = self.add_chain()
        snapshot_id = "pls-" + "a" * 64
        graph_args = library.parser().parse_args(
            [
                "graph-add",
                "--root",
                str(self.repo),
                "--paper-id",
                paper_id,
                "--version-id",
                version_id,
                "--graph-root",
                str(self.graph),
                "--graph-kind",
                "paper_logic",
                "--chalxius-root",
                str(self.chalxius),
                "--source-project-id",
                "TEST-PROJECT",
                "--snapshot-id",
                snapshot_id,
            ]
        )
        graph_result = graph_args.function(graph_args)
        graph = graph_result["record"]
        audit = {"ok": True, "errors": [], "warnings": []}
        attestation = {
            "schema_version": 1,
            "contract_revision": library.EVIDENCE_ATTESTATION_REVISION,
            "graph_id": graph["object_id"],
            "graph_tree_sha256": graph["tree"]["sha256"],
            "paper_snapshot_id": snapshot_id,
            "snapshot_manifest_sha256": "b" * 64,
            "snapshot_graph_kind": "logic",
            "source_role": "external_reference",
            "material_uses": library.PAPER_EVIDENCE_MATERIAL_USES,
            "source_project_id": "TEST-PROJECT",
            "pdf_sha256": graph["pdf_sha256"],
            "node_ids": ["node-a", "node-b"],
            "review_ids": ["review-1", "review-2"],
            "review_profiles": ["graph_structure", "source_fidelity"],
            "paper_logic_audit": audit,
            "paper_logic_audit_sha256": library.object_hash(audit),
            "truth_effect": "none",
        }
        attestation_path = self.base / "paper-evidence-attestation.json"
        attestation_path.write_text(
            json.dumps(attestation, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        evidence_args = library.parser().parse_args(
            [
                "evidence-paper-add",
                "--root",
                str(self.repo),
                "--graph-id",
                graph["object_id"],
                "--attestation",
                str(attestation_path),
                "--sync-mode",
                "automatic_after_reviewed_freeze",
            ]
        )
        evidence = evidence_args.function(evidence_args)
        return graph["object_id"], evidence["evidence_id"], snapshot_id

    def test_full_capture_index_context_and_verify(self) -> None:
        paper_id, version_id, graph_id = self.add_chain()
        correction_file = self.base / "correction.md"
        correction_file.write_text("Narrow the audit conclusion.\n", encoding="utf-8")
        self.run_command(
            "correction-add",
            "--root",
            str(self.repo),
            "--paper-id",
            paper_id,
            "--version-id",
            version_id,
            "--graph-id",
            graph_id,
            "--kind",
            "audit_correction",
            "--status",
            "proposed",
            "--summary",
            "Narrow the audit conclusion.",
            "--artifact",
            str(correction_file),
        )
        self.run_command("index", "--root", str(self.repo))
        capsule = self.base / "capsule.json"
        self.run_command(
            "context-export",
            "--root",
            str(self.repo),
            "--graph-id",
            graph_id,
            "--output",
            str(capsule),
        )
        self.run_command("verify", "--root", str(self.repo))
        context = json.loads(capsule.read_text(encoding="utf-8"))
        self.assertFalse(context["premise_eligible"])
        self.assertEqual(context["truth_effect"], "none")
        self.assertEqual(context["graphs"][0]["chalxius"]["version"], "0.4.4")

    def test_ids_are_idempotent_and_events_do_not_duplicate(self) -> None:
        paper_id, version_id, graph_id = self.add_chain()
        first_count = len(library.load_events(self.repo))
        paper_id_2, version_id_2, graph_id_2 = self.add_chain()
        second_count = len(library.load_events(self.repo))
        self.assertEqual((paper_id, version_id, graph_id), (paper_id_2, version_id_2, graph_id_2))
        self.assertEqual(first_count, second_count)

    def test_tampered_pdf_fails_verification(self) -> None:
        _, version_id, _ = self.add_chain()
        version = library.get_record(self.repo, "versions", version_id)
        stored_pdf = self.repo / version["pdf"]["path"]
        stored_pdf.write_bytes(b"%PDF-1.4\nchanged\n")
        args = library.parser().parse_args(["verify", "--root", str(self.repo)])
        with self.assertRaises(library.LibraryError):
            args.function(args)

    def test_stable_zotero_identity_rejects_conflicting_rewrite(self) -> None:
        self.initialize()
        original = library.parser().parse_args(
            [
                "paper-add",
                "--root",
                str(self.repo),
                "--zotero-library-id",
                "test-zotero",
                "--zotero-item-key",
                "ABCD1234",
                "--title",
                "Original title",
            ]
        )
        first = original.function(original)
        conflicting = library.parser().parse_args(
            [
                "paper-add",
                "--root",
                str(self.repo),
                "--zotero-library-id",
                "test-zotero",
                "--zotero-item-key",
                "ABCD1234",
                "--title",
                "Silently rewritten title",
            ]
        )
        with self.assertRaises(library.LibraryError):
            conflicting.function(conflicting)
        self.assertTrue(
            library.record_path(self.repo, "papers", first["paper_id"]).is_file()
        )

    def test_zotero_snapshot_is_explicit_external_ingress(self) -> None:
        self.initialize()
        source = self.base / "zotero-export.json"
        source.write_text(
            json.dumps({"items": [{"id": "A"}, {"id": "B"}]}) + "\n",
            encoding="utf-8",
        )
        record_root = self.repo / "records" / "zotero_exports"
        self.assertFalse(record_root.exists())
        arguments = library.parser().parse_args(
            [
                "zotero-snapshot",
                "--root",
                str(self.repo),
                "--library-id",
                "test-zotero",
                "--input",
                str(source),
                "--format",
                "zotero-json",
            ]
        )
        result = arguments.function(arguments)
        self.assertEqual(result["record"]["item_count"], 2)
        self.assertEqual(result["record"]["truth_effect"], "none")
        self.assertTrue(record_root.is_dir())

    def test_native_arxiv_identity_does_not_require_zotero(self) -> None:
        self.initialize()
        first_args = library.parser().parse_args(
            [
                "paper-add",
                "--root",
                str(self.repo),
                "--arxiv-id",
                "arXiv:2604.25622v3",
                "--title",
                "Native identity paper",
                "--author",
                "N. Author",
            ]
        )
        first = first_args.function(first_args)
        second_args = library.parser().parse_args(
            [
                "paper-add",
                "--root",
                str(self.repo),
                "--identity-scheme",
                "arxiv",
                "--identity-key",
                "https://arxiv.org/abs/2604.25622",
                "--arxiv-id",
                "2604.25622",
                "--title",
                "Native identity paper",
                "--author",
                "N. Author",
            ]
        )
        second = second_args.function(second_args)
        self.assertEqual(first["paper_id"], second["paper_id"])
        self.assertEqual(first["record"]["identity"]["canonical"], "arxiv:2604.25622")
        self.assertEqual(first["record"]["zotero"]["item_key"], "")

    def test_arxiv_update_detection_and_sqlite_index(self) -> None:
        paper_id, _, graph_id = self.add_chain()
        atom = self.base / "arxiv.atom"
        atom.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>https://export.arxiv.org/api/query?id_list=0000.00000</id>
  <updated>2026-07-29T00:00:00Z</updated>
  <entry>
    <id>http://arxiv.org/abs/0000.00000v3</id>
    <updated>2026-07-28T12:00:00Z</updated>
    <published>2026-07-01T12:00:00Z</published>
    <title>A test paper, revised</title>
    <summary>Exact revised abstract.</summary>
    <author><name>A. Author</name></author>
    <link href="https://arxiv.org/abs/0000.00000v3" rel="alternate" type="text/html"/>
    <link title="pdf" href="https://arxiv.org/pdf/0000.00000v3" rel="related" type="application/pdf"/>
  </entry>
</feed>
""",
            encoding="utf-8",
        )
        args = library.parser().parse_args(
            [
                "arxiv-check",
                "--root",
                str(self.repo),
                "--paper-id",
                paper_id,
                "--arxiv-id",
                "0000.00000",
                "--input-atom",
                str(atom),
                "--response-locator",
                "https://export.arxiv.org/api/query?id_list=0000.00000",
                "--checked-at",
                "2026-07-29T00:00:00Z",
            ]
        )
        result = args.function(args)
        self.assertEqual(result["status_counts"], {"new_version_available": 1})
        capsule = self.base / "arxiv-context.json"
        context_args = library.parser().parse_args(
            [
                "context-export",
                "--root",
                str(self.repo),
                "--graph-id",
                graph_id,
                "--output",
                str(capsule),
            ]
        )
        context_args.function(context_args)
        context = json.loads(capsule.read_text(encoding="utf-8"))
        self.assertEqual(
            context["latest_source_checks"][0]["status"],
            "new_version_available",
        )
        self.run_command("index", "--root", str(self.repo))
        self.run_command("verify", "--root", str(self.repo))
        database = self.repo / "index" / "library.sqlite3"
        connection = sqlite3.connect(database)
        try:
            row = connection.execute(
                "SELECT observed_arxiv_id, status, is_latest FROM source_checks"
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(row, ("0000.00000v3", "new_version_available", 1))

    def test_arxiv_capture_is_explicit_and_keeps_version_lineage(self) -> None:
        paper_id, version_id, _ = self.add_chain()
        args = library.parser().parse_args(
            [
                "arxiv-capture",
                "--root",
                str(self.repo),
                "--paper-id",
                paper_id,
                "--arxiv-id",
                "0000.00000v3",
                "--pdf",
                str(self.pdf),
                "--retrieved-at",
                "2026-07-29",
            ]
        )
        result = args.function(args)
        self.assertFalse(result["downloaded"])
        self.assertEqual(result["record"]["supersedes_version_ids"], [version_id])
        catalog = library.build_catalog(self.repo)
        versions = catalog["entries"][0]["versions"]
        current = [version for version in versions if version["current"]]
        self.assertEqual([version["identifiers"]["arxiv_id"] for version in current], ["0000.00000v3"])

    def test_graph_must_bind_the_exact_version_pdf_hash(self) -> None:
        _, _, graph_id = self.add_chain()
        graph = library.get_record(self.repo, "graphs", graph_id)
        invalid_payload = library.record_payload(graph)
        invalid_payload["pdf_sha256"] = "f" * 64
        library.write_record(
            self.repo,
            "graphs",
            invalid_payload,
            "paper_graph_captured",
        )
        with self.assertRaises(library.LibraryError):
            library.validate_references(self.repo)

    def test_empty_directories_are_preserved_and_symlinks_rejected(self) -> None:
        _, _, graph_id = self.add_chain()
        graph = library.get_record(self.repo, "graphs", graph_id)
        captured = self.repo / graph["tree"]["path"] / "files"
        self.assertTrue(
            (captured / "snapshots" / "by-id" / ("pls-" + "a" * 64)).is_dir()
        )
        linked = self.base / "linked-graph"
        linked.symlink_to(self.graph, target_is_directory=True)
        with self.assertRaises(library.LibraryError):
            library.store_graph_tree(self.repo, linked)

    def test_reviewed_paper_evidence_bridge_is_copy_on_write_and_stales_on_challenge(
        self,
    ) -> None:
        _, evidence_id, _ = self.add_reviewed_paper_evidence()
        selection = {
            "schema_version": 1,
            "destination_project_id": "DESTINATION",
            "items": [
                {
                    "evidence_id": evidence_id,
                    "node_ids": ["node-a"],
                    "fact_ids": [],
                }
            ],
            "target_claim": "Use the exact selected paper node as source context.",
            "rationale": "The node is load-bearing for a fresh destination proof.",
        }
        selection_path = self.base / "bridge-selection.json"
        selection_path.write_text(json.dumps(selection) + "\n", encoding="utf-8")
        bridge_path = self.base / "bridge.json"
        prepare_args = library.parser().parse_args(
            [
                "bridge-prepare",
                "--root",
                str(self.repo),
                "--destination-project-id",
                "DESTINATION",
                "--selection",
                str(selection_path),
                "--actor",
                "operator",
                "--reason",
                "Explicit bridge selection for a destination proof.",
                "--output",
                str(bridge_path),
            ]
        )
        prepared = prepare_args.function(prepare_args)
        query_args = library.parser().parse_args(
            [
                "evidence-query",
                "--root",
                str(self.repo),
                "--query",
                "test paper",
            ]
        )
        queried = query_args.function(query_args)
        self.assertEqual([item["evidence_id"] for item in queried["results"]], [evidence_id])
        check_args = library.parser().parse_args(
            [
                "bridge-check",
                "--root",
                str(self.repo),
                "--bridge-id",
                prepared["bridge_id"],
            ]
        )
        self.assertTrue(check_args.function(check_args)["current"])

        invalid_selection = copy.deepcopy(selection)
        invalid_selection["items"][0]["node_ids"] = ["not-attested"]
        selection_path.write_text(
            json.dumps(invalid_selection) + "\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(library.LibraryError, "unattested"):
            prepare_args.function(prepare_args)

        disposition_args = library.parser().parse_args(
            [
                "evidence-disposition-add",
                "--root",
                str(self.repo),
                "--evidence-id",
                evidence_id,
                "--status",
                "challenged",
                "--reason",
                "A later audit found a load-bearing reconstruction error.",
                "--actor",
                "operator",
            ]
        )
        disposition = disposition_args.function(disposition_args)
        self.assertEqual(
            disposition["affected_bridges"],
            [
                {
                    "bridge_id": prepared["bridge_id"],
                    "destination_project_id": "DESTINATION",
                }
            ],
        )
        with self.assertRaisesRegex(library.LibraryError, "stale"):
            check_args.function(check_args)
        self.assertEqual(query_args.function(query_args)["results"], [])
        query_args.include_inactive = True
        self.assertEqual(
            [item["status"] for item in query_args.function(query_args)["results"]],
            ["challenged"],
        )
        self.run_command("index", "--root", str(self.repo))
        self.run_command("verify", "--root", str(self.repo))

    def test_external_fact_evidence_binds_every_lineage_object_and_rejects_tampering(
        self,
    ) -> None:
        self.initialize()
        fact_id = "FACT-TEST"
        fact_raw = b"# Fact TEST\n\nExact admitted bytes.\n"
        fact_sha = hashlib.sha256(fact_raw).hexdigest()
        interface_core = {
            "schema_version": 5,
            "fact_id": fact_id,
            "policy_revision": "fixture",
        }
        interface = {
            **interface_core,
            "interface_sha256": library.object_hash(interface_core),
        }
        release = {
            "project_id": "SOURCE",
            "release_id": "release-test",
            "release_sha256": "1" * 64,
            "fact_ids": [fact_id],
            "candidates": [{"fact_id": fact_id, "fact_sha256": fact_sha}],
        }
        decision = {
            "project_id": "SOURCE",
            "decision_id": "decision-test",
            "decision_sha256": "2" * 64,
            "release_id": "release-test",
            "release_sha256": "1" * 64,
            "verdict": "correct",
        }
        admission = {
            "project_id": "SOURCE",
            "acceptance_id": "acceptance-test",
            "release_id": "release-test",
            "release_sha256": "1" * 64,
            "decision_id": "decision-test",
            "decision_sha256": "2" * 64,
            "gateway": "source-gateway",
            "fact_ids": [fact_id],
        }

        def encoded(role: str, object_id: str, raw: bytes) -> dict[str, str]:
            return {
                "role": role,
                "object_id": object_id,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes_base64": base64.b64encode(raw).decode("ascii"),
            }

        def json_raw(value: dict[str, object]) -> bytes:
            return library.canonical_bytes(value) + b"\n"

        core = {
            "schema_version": 1,
            "contract_revision": library.FACT_EVIDENCE_CAPSULE_REVISION,
            "source_project_id": "SOURCE",
            "source_root_locator": "/frozen/source",
            "source_audit": {
                "current_ok": True,
                "history_clean": True,
                "errors": [],
            },
            "active_facts": [
                {
                    "fact_id": fact_id,
                    "fact_sha256": fact_sha,
                    "interface_sha256": interface["interface_sha256"],
                    "interface_schema_version": 5,
                    "release_id": "release-test",
                    "release_sha256": "1" * 64,
                    "decision_id": "decision-test",
                    "decision_sha256": "2" * 64,
                    "gateway": "source-gateway",
                    "acceptance_id": "acceptance-test",
                }
            ],
            "revoked_fact_ids": [],
            "objects": [
                encoded("fact", fact_id, fact_raw),
                encoded("release", "release-test", json_raw(release)),
                encoded("decision", "decision-test", json_raw(decision)),
                encoded("admission", "acceptance-test", json_raw(admission)),
                encoded("interface", fact_id, json_raw(interface)),
            ],
            "runtime": {"version": "fixture"},
            "truth_effect": "none",
            "premise_eligible": False,
        }
        capsule = {**core, "capsule_id": "efc-" + library.object_hash(core)}
        capsule_path = self.base / "fact-evidence.json"
        capsule_path.write_text(json.dumps(capsule) + "\n", encoding="utf-8")
        add_args = library.parser().parse_args(
            [
                "evidence-fact-add",
                "--root",
                str(self.repo),
                "--capsule",
                str(capsule_path),
                "--actor",
                "operator",
                "--reason",
                "Explicit user-requested import.",
            ]
        )
        result = add_args.function(add_args)
        self.assertEqual(result["record"]["sync_mode"], "explicit_user_fact_graph_bridge")

        _, paper_evidence_id, _ = self.add_reviewed_paper_evidence()
        association_args = library.parser().parse_args(
            [
                "evidence-association-add",
                "--root",
                str(self.repo),
                "--destination-project-id",
                "DESTINATION",
                "--paper-evidence-id",
                paper_evidence_id,
                "--fact-evidence-id",
                result["evidence_id"],
                "--fact-id",
                fact_id,
                "--actor",
                "operator",
                "--reason",
                "Explicit exact-member navigation fixture.",
            ]
        )
        associated = association_args.function(association_args)
        event_count = len(library.load_events(self.repo))
        duplicate_association = association_args.function(association_args)
        self.assertEqual(
            duplicate_association["association_id"], associated["association_id"]
        )
        self.assertEqual(len(library.load_events(self.repo)), event_count)
        association_query = library.parser().parse_args(
            [
                "evidence-query",
                "--root",
                str(self.repo),
                "--query",
                associated["association_id"],
                "--associations-only",
            ]
        )
        queried_association = association_query.function(association_query)
        self.assertEqual(queried_association["results"], [])
        self.assertEqual(
            [
                item["association_id"]
                for item in queried_association["association_results"]
            ],
            [associated["association_id"]],
        )
        association_query.associations_only = False
        linked_evidence = association_query.function(association_query)["results"]
        self.assertEqual(len(linked_evidence), 2)
        self.assertTrue(
            all(
                item["association_ids"] == [associated["association_id"]]
                for item in linked_evidence
            )
        )

        scoped_core = copy.deepcopy(core)
        scoped_core["source_audit"] = {
            "schema_version": 1,
            "contract_revision": library.FACT_EVIDENCE_SOURCE_AUDIT_REVISION,
            "scope": "active_v5_fact_authority_only",
            "source_runtime_policy": (
                "independent_of_frozen_nontruth_workflow_runtime"
            ),
            "workflow_evidence_version": 5,
            "current_ok": True,
            "history_clean": True,
            "facts": 1,
            "active_fact_ids": [fact_id],
            "errors": [],
            "truth_effect": "none",
            "project_effect": "none",
        }
        scoped = {
            **scoped_core,
            "capsule_id": "efc-" + library.object_hash(scoped_core),
        }
        library.validate_fact_evidence_capsule(scoped)
        mismatched_audit_core = copy.deepcopy(scoped_core)
        mismatched_audit_core["source_audit"]["active_fact_ids"] = []
        mismatched_audit = {
            **mismatched_audit_core,
            "capsule_id": "efc-" + library.object_hash(mismatched_audit_core),
        }
        with self.assertRaisesRegex(library.LibraryError, "Fact set"):
            library.validate_fact_evidence_capsule(mismatched_audit)

        tampered_core = copy.deepcopy(core)
        changed_raw = fact_raw + b"changed\n"
        changed_sha = hashlib.sha256(changed_raw).hexdigest()
        tampered_core["active_facts"][0]["fact_sha256"] = changed_sha
        tampered_core["objects"][0] = encoded("fact", fact_id, changed_raw)
        tampered = {
            **tampered_core,
            "capsule_id": "efc-" + library.object_hash(tampered_core),
        }
        capsule_path.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(library.LibraryError, "release binding"):
            add_args.function(add_args)
        self.run_command("index", "--root", str(self.repo))
        self.run_command("verify", "--root", str(self.repo))
        database = sqlite3.connect(self.repo / "index" / "library.sqlite3")
        try:
            association_row = database.execute(
                "SELECT association_id, paper_evidence_id, fact_evidence_id "
                "FROM evidence_associations"
            ).fetchone()
        finally:
            database.close()
        self.assertEqual(
            association_row,
            (
                associated["association_id"],
                paper_evidence_id,
                result["evidence_id"],
            ),
        )


if __name__ == "__main__":
    unittest.main()
