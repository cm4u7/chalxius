#!/usr/bin/env python3
"""Build the public, sanitized Chalxius Reader case demonstrations."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPOSITORY = Path(__file__).resolve().parents[1]
MGRAPH = REPOSITORY / "chalxius" / "scripts" / "mgraph"
PACKET_DIRECTORY = REPOSITORY / "examples" / "reader-packets"
CASE_DIRECTORY = REPOSITORY / "docs" / "cases"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def provenance(
    *,
    plane: str,
    source_status: str,
    truth_status: str,
    object_id: str,
    snapshot_id: str,
    locator: str,
    original_text: str,
) -> dict[str, Any]:
    object_digest = sha256_bytes(
        canonical_bytes({"id": object_id, "text": original_text})
    )
    return {
        "source_plane": plane,
        "source_status": source_status,
        "truth_status": truth_status,
        "object_id": object_id,
        "snapshot_id": snapshot_id,
        "locator": locator,
        "object_sha256": object_digest,
        "original_text_sha256": sha256_bytes(original_text.encode("utf-8")),
        "replaces": [],
    }


def node(
    *,
    case_slug: str,
    snapshot_id: str,
    node_id: str,
    title: str,
    role: str,
    plane: str,
    visual_status: str,
    layer: str,
    theme_id: str,
    summary: str,
    intuition: str,
    importance: str,
    reasoning: str,
    original_text: str,
    source_status: str,
    truth_status: str,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "title": title,
        "reader_role": role,
        "plane": plane,
        "visual_status": visual_status,
        "layer": layer,
        "theme_id": theme_id,
        "summary": summary,
        "intuition": intuition,
        "importance": importance,
        "reasoning": reasoning,
        "prerequisites": [],
        "formal": {
            "hypotheses": ["Read this node only within the stated public case boundary."],
            "statement": original_text,
            "proof": "This is a hash-bound public case summary, not a proof or a new authority object.",
            "relations": ["Its plane and truth-status labels determine its authority."],
            "original_text": original_text,
        },
        "provenance": provenance(
            plane=plane,
            source_status=source_status,
            truth_status=truth_status,
            object_id=f"public-case:{case_slug}:{node_id}",
            snapshot_id=snapshot_id,
            locator=f"docs/cases/{case_slug}.source.md; public summary node {node_id}",
            original_text=original_text,
        ),
    }


def edge(
    *,
    case_slug: str,
    snapshot_id: str,
    edge_id: str,
    source: str,
    target: str,
    category: str,
    relation: str,
    exact_type: str,
    weak: bool = False,
    layer: str = "knowledge",
) -> dict[str, Any]:
    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "category": category,
        "relation": relation,
        "exact_type": exact_type,
        "weak": weak,
        "layer": layer,
        "provenance": provenance(
            plane="reader",
            source_status="presentation_only_relation",
            truth_status="reader_note",
            object_id=f"public-case:{case_slug}:{edge_id}",
            snapshot_id=snapshot_id,
            locator=f"docs/cases/{case_slug}.source.md; presentation relation {edge_id}",
            original_text=relation,
        ),
    }


def finish_packet(packet: dict[str, Any]) -> dict[str, Any]:
    incoming: dict[str, list[str]] = {item["id"]: [] for item in packet["nodes"]}
    for item in packet["edges"]:
        if item["category"] == "prerequisite":
            incoming[item["target"]].append(item["source"])
    for item in packet["nodes"]:
        item["prerequisites"] = incoming[item["id"]]

    def ancestors(target_id: str) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()

        def visit(node_id: str) -> None:
            for predecessor in incoming[node_id]:
                visit(predecessor)
                if predecessor not in seen:
                    seen.add(predecessor)
                    ordered.append(predecessor)

        visit(target_id)
        return ordered

    packet["prerequisite_order"] = {
        target_id: ancestors(target_id) for target_id in packet["target_order"]
    }
    return packet


def philosophy_packet(source_digest: str) -> dict[str, Any]:
    case_slug = "philosophy"
    snapshot_id = "public-philosophy-workflow-v1"
    theme_id = "theme-philosophy-workflow"
    n = lambda **kwargs: node(
        case_slug=case_slug,
        snapshot_id=snapshot_id,
        theme_id=theme_id,
        **kwargs,
    )
    e = lambda **kwargs: edge(
        case_slug=case_slug,
        snapshot_id=snapshot_id,
        **kwargs,
    )
    nodes = [
        n(
            node_id="paper-source",
            title="Frozen source anchors",
            role="definition",
            plane="paper",
            visual_status="current",
            layer="knowledge",
            summary="Exact source passages remain separate from every interpretation.",
            intuition="The system first preserves what the publication says before asking what it means.",
            importance="A later criticism can then point to a stable source instead of a moving paraphrase.",
            reasoning="Source authority is evidence of wording and context, not automatic proof of the paper's conclusion.",
            original_text="The audited workflow preserved 17 frozen source nodes as source authority.",
            source_status="current_source_summary",
            truth_status="source_authority",
        ),
        n(
            node_id="paper-reconstruction",
            title="Bounded argument map",
            role="result",
            plane="paper",
            visual_status="current",
            layer="knowledge",
            summary="A reconstruction makes claims and inferential links explicit while remaining interpretation.",
            intuition="It is a transparent reading of the paper, not a silent replacement for the paper.",
            importance="Typed reconstruction makes omissions, ambiguities, and disagreements inspectable.",
            reasoning="The audited snapshot contained 40 reconstruction nodes and retained rejected revisions as history.",
            original_text="The public case records a bounded reconstruction, not a uniquely correct interpretation.",
            source_status="current_reconstruction_summary",
            truth_status="interpretation",
        ),
        n(
            node_id="audit-review",
            title="Independent dual review",
            role="result",
            plane="audit",
            visual_status="current",
            layer="knowledge",
            summary="The accepted revision required separate source-fidelity and graph-structure review.",
            intuition="One reviewer checks faithfulness to the source; another checks whether the map itself is coherent.",
            importance="A polished reconstruction cannot approve itself.",
            reasoning="The two reviews bind different failure modes and preserve their decisions independently.",
            original_text="The current reconstruction revision was accepted only after both designated reviews passed.",
            source_status="reviewed_audit_summary",
            truth_status="audit_evidence",
        ),
        n(
            node_id="audit-history",
            title="Correctable audit history",
            role="explanation",
            plane="audit",
            visual_status="current",
            layer="knowledge",
            summary="Rejected, superseded, and repaired audit states remain inspectable.",
            intuition="Correction adds a traceable next state instead of erasing the earlier mistake.",
            importance="Readers can distinguish the current view from the path that produced it.",
            reasoning="Append-only replacement prevents a later repair from rewriting the historical record.",
            original_text="The audited artifact retained 16 historical audit nodes and explicit replacement relations.",
            source_status="historical_audit_summary",
            truth_status="audit_evidence",
        ),
        n(
            node_id="target-reconstruction",
            title="Source-bound reconstruction",
            role="target",
            plane="paper",
            visual_status="current",
            layer="knowledge",
            summary="Chalxius can make a philosophical argument readable without merging source and interpretation.",
            intuition="A reader can inspect the argument and still see which parts came from the publication and which parts were reconstructed.",
            importance="This supports rigorous reading without pretending that a graph settles the philosophy.",
            reasoning="Frozen source anchors, explicit reconstruction, and independent review jointly support this workflow claim.",
            original_text="This case demonstrates source-bound reconstruction workflow, not philosophical truth.",
            source_status="public_case_reconstruction",
            truth_status="interpretation",
        ),
        n(
            node_id="fact-boundary",
            title="Zero admitted Facts",
            role="definition",
            plane="audit",
            visual_status="current",
            layer="knowledge",
            summary="The audited Fact Graph contained zero admitted Facts and zero candidates.",
            intuition="Useful analysis can remain useful without being promoted into trusted premises.",
            importance="This is positive evidence that authority did not leak between planes.",
            reasoning="A clean workflow audit checks structure and policy; it does not certify a philosophical proposition.",
            original_text="No philosophical claim from this case was admitted as a Chalxius Fact.",
            source_status="fact_boundary_audit",
            truth_status="audit_evidence",
        ),
        n(
            node_id="target-authority",
            title="Authority-safe exploration",
            role="target",
            plane="audit",
            visual_status="current",
            layer="knowledge",
            summary="Audit, exploration, teaching, and presentation remain nontruth activities unless a separate admission succeeds.",
            intuition="The system can help people think without granting every useful note the power of a premise.",
            importance="That boundary is the central safety property of the philosophy workflow.",
            reasoning="The read-only audit passed while the Fact Graph remained empty and the learning mount prohibited writeback.",
            original_text="The demonstrated capability is authority separation across the audited workflow.",
            source_status="reviewed_audit_conclusion",
            truth_status="audit_evidence",
        ),
        n(
            node_id="blackboard-exploration",
            title="Frozen Blackboard",
            role="explanation",
            plane="blackboard",
            visual_status="research",
            layer="research",
            summary="Exploratory questions and challenges live in a separate frozen workspace.",
            intuition="Researchers can try objections without editing the source or declaring victory.",
            importance="Speculation stays useful and reversible.",
            reasoning="Mirror nodes retain bindings to their source snapshots while agent notes remain exploration only.",
            original_text="Blackboard projection preserved endpoints without acquiring Paper or Fact authority.",
            source_status="frozen_exploration_summary",
            truth_status="exploration",
        ),
        n(
            node_id="learner-overlay",
            title="Read-only learning overlay",
            role="explanation",
            plane="learning",
            visual_status="research",
            layer="research",
            summary="A learning overlay can teach from frozen research snapshots without writing back.",
            intuition="Teaching state is about what a learner has practiced, not what research has proved.",
            importance="Pedagogical usefulness does not weaken provenance or admission boundaries.",
            reasoning="The verified mount prohibited research-runtime invocation, truth inheritance, and source writeback.",
            original_text="The learning overlay retained nontruth status and began with zero mastery evidence.",
            source_status="frozen_learning_summary",
            truth_status="learning",
        ),
    ]
    edges = [
        e(edge_id="edge-source-reconstruction", source="paper-source", target="paper-reconstruction", category="prerequisite", relation="The reconstruction is bound to frozen source anchors.", exact_type="source_bounds_interpretation"),
        e(edge_id="edge-reconstruction-review", source="paper-reconstruction", target="audit-review", category="prerequisite", relation="Independent review evaluates the bounded reconstruction.", exact_type="requires_independent_review"),
        e(edge_id="edge-reconstruction-history", source="paper-reconstruction", target="audit-history", category="prerequisite", relation="Correction history records revisions of the reconstruction.", exact_type="records_revision_history"),
        e(edge_id="edge-review-target", source="audit-review", target="target-reconstruction", category="prerequisite", relation="Dual review supports the bounded workflow claim.", exact_type="review_supports_workflow"),
        e(edge_id="edge-history-target", source="audit-history", target="target-reconstruction", category="prerequisite", relation="Traceable correction history supports the workflow claim.", exact_type="history_supports_workflow"),
        e(edge_id="edge-reconstruction-authority", source="target-reconstruction", target="target-authority", category="prerequisite", relation="Authority-safe exploration builds on source-bound reconstruction.", exact_type="workflow_precedes_boundary"),
        e(edge_id="edge-fact-authority", source="fact-boundary", target="target-authority", category="prerequisite", relation="The empty Fact Graph establishes the tested non-leakage boundary.", exact_type="audit_boundary"),
        e(edge_id="edge-history-repair", source="audit-history", target="paper-reconstruction", category="repair", relation="Accepted corrections replace rather than erase prior reconstruction states.", exact_type="append_only_repair", layer="research"),
        e(edge_id="edge-blackboard-authority", source="blackboard-exploration", target="target-authority", category="support", relation="Frozen exploration illustrates nontruth reasoning without source mutation.", exact_type="exploration_support", weak=True, layer="research"),
        e(edge_id="edge-learning-authority", source="learner-overlay", target="target-authority", category="support", relation="The read-only learning mount illustrates nontruth teaching.", exact_type="learning_support", weak=True, layer="research"),
    ]
    return finish_packet({
        "schema_version": 1,
        "project_id": "public-philosophy-case",
        "language": "en",
        "title": "Philosophy workflow: reconstruction without authority leakage",
        "audience": "Readers with no prior knowledge of Chalxius or knowledge graphs",
        "source_snapshot": {
            "id": snapshot_id,
            "sha256": source_digest,
            "description": "An anonymized public summary bound to a read-only audit of a private philosophy workflow.",
        },
        "presentation": {
            "subtitle": "Two workflow conclusions, with research and learning context available as optional layers.",
            "introduction": "This interactive map demonstrates separation of source, interpretation, audit, exploration, and learning authority. It does not prove a philosophical conclusion and admits no Fact.",
        },
        "audit": {
            "current_ok": True,
            "summary": "The audited artifact passed current read-only structural and workflow checks; that result is workflow evidence only.",
            "warnings": ["The underlying artifact predates current unified-write activation and remains read-only."],
            "unresolved": [],
        },
        "theme_order": [theme_id],
        "target_order": ["target-reconstruction", "target-authority"],
        "prerequisite_order": {},
        "themes": [{
            "id": theme_id,
            "label": "Philosophy workflow",
            "description": "A source-bound reconstruction followed by an authority-separation result.",
            "target_ids": ["target-reconstruction", "target-authority"],
        }],
        "nodes": nodes,
        "edges": edges,
    })


def xy_swap_packet(source_digest: str) -> dict[str, Any]:
    case_slug = "xy-swap-potential"
    snapshot_id = "public-xy-swap-potential-v1"
    theme_id = "theme-xy-swap-potential"
    n = lambda **kwargs: node(
        case_slug=case_slug,
        snapshot_id=snapshot_id,
        theme_id=theme_id,
        **kwargs,
    )
    e = lambda **kwargs: edge(
        case_slug=case_slug,
        snapshot_id=snapshot_id,
        **kwargs,
    )
    nodes = [
        n(
            node_id="research-question",
            title="x-y interchange question",
            role="definition",
            plane="blackboard",
            visual_status="research",
            layer="knowledge",
            summary="The archive studies what may change when the two coordinate functions of a spectral curve are exchanged.",
            intuition="Treat the coordinate swap as a research question, not as an assumed symmetry.",
            importance="The distinction prevents the demonstration from disclosing or endorsing an unpublished conclusion.",
            reasoning="The public case names only the research domain and withholds the private mathematical result.",
            original_text="The public scope concerns exchanging \\(x\\) and \\(y\\) in a topological-recursion research question.",
            source_status="bounded_research_question",
            truth_status="exploration",
        ),
        n(
            node_id="legacy-graph",
            title="Predecessor Fact Graph",
            role="result",
            plane="blackboard",
            visual_status="research",
            layer="knowledge",
            summary="A predecessor workflow recorded 53 active legacy Facts, 95 edges, and a 21-target closure.",
            intuition="The archive is substantial enough to test migration questions, but age alone does not grant current certification.",
            importance="It supplies observed workflow evidence without being relabelled as a Chalxius 0.3.5 project.",
            reasoning="The counts come from a read-only audit; legacy admissions retain only their recorded historical assurance.",
            original_text="The predecessor archive contained 53 active legacy Facts, 95 dependency edges, and 21 targets at the audited snapshot.",
            source_status="legacy_observation",
            truth_status="exploration",
        ),
        n(
            node_id="verification-pattern",
            title="Packet-bound review pattern",
            role="result",
            plane="blackboard",
            visual_status="research",
            layer="knowledge",
            summary="The predecessor used frozen submissions, independent review, and replayable computational evidence.",
            intuition="A reviewer should inspect the exact artifact that a later decision cites.",
            importance="This pattern is why the archive is a plausible migration candidate rather than a bare folder of notes.",
            reasoning="Observed receipts bind candidate material and review state, but do not satisfy every newer requirement.",
            original_text="The predecessor workflow used packet-bound review and replayable computation without current Chalxius recertification.",
            source_status="legacy_observation",
            truth_status="exploration",
        ),
        n(
            node_id="revocation-history",
            title="Explicit revocation",
            role="explanation",
            plane="audit",
            visual_status="current",
            layer="knowledge",
            summary="One legacy Fact was explicitly revoked after later review exposed an overstatement.",
            intuition="Correction preserved the old record while removing its active authority.",
            importance="The archive demonstrates that a graph can remember error without continuing to trust it.",
            reasoning="The public case reports the existence of the revocation but does not disclose the revoked proposition.",
            original_text="The audited predecessor history contains one explicit revocation with preserved provenance.",
            source_status="legacy_audit_observation",
            truth_status="audit_evidence",
        ),
        n(
            node_id="current-audit-gap",
            title="Current audit gap",
            role="result",
            plane="audit",
            visual_status="challenged",
            layer="knowledge",
            summary="The predecessor does not pass the current Chalxius workflow audit.",
            intuition="A clean dependency shape is not enough when newer source-evidence requirements are missing.",
            importance="This blocks any claim that the archive is already a validated Chalxius deployment.",
            reasoning="Thirteen legacy rounds fail the newer source-evidence contract and inherited warnings remain.",
            original_text="Current audit status is not PASS; migration and source-evidence repair would be required.",
            source_status="current_audit_blocker",
            truth_status="audit_evidence",
        ),
        n(
            node_id="author-confirmation",
            title="Author confirmation pending",
            role="explanation",
            plane="audit",
            visual_status="challenged",
            layer="knowledge",
            summary="The relevant authors have not confirmed this case framing.",
            intuition="A plausible technical application is not the same as external acknowledgement or endorsement.",
            importance="The public description must remain explicitly hypothetical.",
            reasoning="No confirmation artifact or reply was present in the audited archive.",
            original_text="This potential application has not been confirmed by the relevant authors.",
            source_status="external_confirmation_absent",
            truth_status="audit_evidence",
        ),
        n(
            node_id="target-boundary",
            title="Adoption blockers",
            role="target",
            plane="audit",
            visual_status="challenged",
            layer="knowledge",
            summary="Current audit failure and absent author confirmation block a demonstrated-case claim.",
            intuition="Before asking what Chalxius could show, first state what has not yet happened.",
            importance="This target keeps every screenshot and link honest even when read out of context.",
            reasoning="Both blockers are independently necessary boundaries for this public example.",
            original_text="The x-y archive is not a current validated or author-confirmed Chalxius case.",
            source_status="public_boundary_audit",
            truth_status="audit_evidence",
        ),
        n(
            node_id="target-potential",
            title="Potential Chalxius application",
            role="target",
            plane="blackboard",
            visual_status="research",
            layer="knowledge",
            summary="The predecessor suggests a future Chalxius workflow for source, computation, review, correction, and presentation.",
            intuition="The archive is a design candidate: it shows where Chalxius might help, not that the migration has succeeded.",
            importance="It provides a realistic research shape while preserving uncertainty and external-confirmation boundaries.",
            reasoning="Observed graph and review practices support plausibility; the explicit blockers prevent promotion to a demonstrated case.",
            original_text="The archive is a potential application only and would require a separate current-format migration and review.",
            source_status="prospective_exploration",
            truth_status="exploration",
        ),
        n(
            node_id="prospective-planes",
            title="Prospective plane separation",
            role="explanation",
            plane="reader",
            visual_status="research",
            layer="research",
            summary="A future migration could separate source reconstruction, audit, exploration, Facts, and Reader presentation.",
            intuition="Each artifact would keep the authority of the process that created it.",
            importance="This is the main architectural reason the archive may fit Chalxius.",
            reasoning="No current-format Paper or Blackboard store was found, so this remains a design projection.",
            original_text="Paper, Audit, Blackboard, and Reader use are prospective for this case.",
            source_status="presentation_only",
            truth_status="reader_note",
        ),
        n(
            node_id="prospective-reader",
            title="Prospective Reader export",
            role="explanation",
            plane="reader",
            visual_status="research",
            layer="research",
            summary="A future Reader could present a migrated, finalized packet as one offline HTML file.",
            intuition="Presentation would become easier to inspect without becoming a new source of truth.",
            importance="This is useful for communication only after migration and sidebar summaries are prepared.",
            reasoning="The predecessor archive contained no Chalxius Reader packet or generated Reader HTML.",
            original_text="No Chalxius Reader export was found; this node describes only a future possibility.",
            source_status="presentation_only",
            truth_status="reader_note",
        ),
    ]
    edges = [
        e(edge_id="edge-question-legacy", source="research-question", target="legacy-graph", category="prerequisite", relation="The predecessor graph organizes work on the bounded research question.", exact_type="research_scope"),
        e(edge_id="edge-legacy-pattern", source="legacy-graph", target="verification-pattern", category="prerequisite", relation="The graph was paired with a packet-bound review pattern.", exact_type="legacy_workflow"),
        e(edge_id="edge-audit-boundary", source="current-audit-gap", target="target-boundary", category="prerequisite", relation="Current audit failure is an adoption blocker.", exact_type="blocks_current_claim"),
        e(edge_id="edge-confirmation-boundary", source="author-confirmation", target="target-boundary", category="prerequisite", relation="Absent author confirmation is an external-status blocker.", exact_type="blocks_confirmation_claim"),
        e(edge_id="edge-pattern-potential", source="verification-pattern", target="target-potential", category="prerequisite", relation="Observed review structure makes a future application plausible.", exact_type="supports_potential_fit"),
        e(edge_id="edge-revocation-potential", source="revocation-history", target="target-potential", category="prerequisite", relation="Explicit correction history makes a future migration worth evaluating.", exact_type="supports_correctable_workflow"),
        e(edge_id="edge-boundary-potential", source="target-boundary", target="target-potential", category="prerequisite", relation="The potential claim is valid only with its blockers attached.", exact_type="scope_guard"),
        e(edge_id="edge-audit-legacy", source="current-audit-gap", target="legacy-graph", category="conflict", relation="Newer source-evidence requirements challenge legacy certification.", exact_type="legacy_assurance_gap", layer="research"),
        e(edge_id="edge-planes-potential", source="prospective-planes", target="target-potential", category="repair", relation="A current-format migration could repair authority separation.", exact_type="prospective_migration", weak=True, layer="research"),
        e(edge_id="edge-reader-potential", source="prospective-reader", target="target-potential", category="support", relation="A finalized offline Reader could later present the migrated graph.", exact_type="prospective_presentation", weak=True, layer="research"),
    ]
    return finish_packet({
        "schema_version": 1,
        "project_id": "public-xy-swap-potential-case",
        "language": "en",
        "title": "Potential application: x-y interchange research",
        "audience": "Readers with no prior knowledge of Chalxius, topological recursion, or the predecessor archive",
        "source_snapshot": {
            "id": snapshot_id,
            "sha256": source_digest,
            "description": "A sanitized public summary of a read-only predecessor-archive audit.",
        },
        "presentation": {
            "subtitle": "Read the blockers first; then inspect why the archive may still be a useful future migration candidate.",
            "introduction": "Potential application only. This archive is neither a current validated Chalxius project nor an author-confirmed case, and this page does not disclose or certify its mathematical conclusion.",
        },
        "audit": {
            "current_ok": False,
            "summary": "The predecessor graph is internally structured, but the current Chalxius workflow audit is not PASS.",
            "warnings": [
                "Thirteen legacy rounds fail newer source-evidence requirements.",
                "The relevant authors have not confirmed this case framing.",
                "No current-format Paper, Blackboard, or Reader artifact was found.",
            ],
            "unresolved": [
                "Migrate only by an explicit current-format workflow.",
                "Repair source evidence and obtain fresh review before any new admission claim.",
                "Keep external author confirmation separate from technical validation.",
            ],
        },
        "theme_order": [theme_id],
        "target_order": ["target-boundary", "target-potential"],
        "prerequisite_order": {},
        "themes": [{
            "id": theme_id,
            "label": "Potential research application",
            "description": "A guarded view: current blockers followed by a prospective Chalxius workflow.",
            "target_ids": ["target-boundary", "target-potential"],
        }],
        "nodes": nodes,
        "edges": edges,
    })


CASES = {
    "philosophy": philosophy_packet,
    "xy-swap-potential": xy_swap_packet,
}

PREBUILT_CASES = ("anonymized-research-topology",)


def export_once(packet_path: Path, packet: dict[str, Any]) -> bytes:
    with tempfile.TemporaryDirectory(prefix="chalxius-public-case-") as temporary:
        project = Path(temporary) / "project"
        subprocess.run(
            [
                str(MGRAPH),
                "--root",
                str(project),
                "--role",
                "operator",
                "init",
                "--project-id",
                packet["project_id"],
                "--title",
                packet["title"],
                "--description",
                "Temporary deterministic public Reader build project",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        receipt = subprocess.run(
            [
                str(MGRAPH),
                "--root",
                str(project),
                "--role",
                "main",
                "export-reader-html",
                "--packet",
                str(packet_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        metadata = json.loads(receipt.stdout)
        if metadata["truth_effect"] != "none":
            raise RuntimeError("Reader export unexpectedly changed truth authority")
        if metadata["reader_finalize"]["status"] != "ready":
            raise RuntimeError("Reader Finalize did not pass")
        return (project / "visualizations" / "knowledge-map.html").read_bytes()


def main() -> None:
    PACKET_DIRECTORY.mkdir(parents=True, exist_ok=True)
    CASE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for slug, packet_builder in CASES.items():
        source_path = CASE_DIRECTORY / f"{slug}.source.md"
        source_digest = sha256_bytes(source_path.read_bytes())
        packet = packet_builder(source_digest)
        packet_path = PACKET_DIRECTORY / f"{slug}.json"
        packet_path.write_text(
            json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        first = export_once(packet_path, packet)
        second = export_once(packet_path, packet)
        if first != second:
            raise RuntimeError(f"nondeterministic Reader output for {slug}")
        output_path = CASE_DIRECTORY / f"{slug}.html"
        output_path.write_bytes(first)
        print(
            json.dumps(
                {
                    "case": slug,
                    "packet_sha256": sha256_bytes(canonical_bytes(packet)),
                    "html_sha256": sha256_bytes(first),
                    "output": output_path.relative_to(REPOSITORY).as_posix(),
                },
                sort_keys=True,
            )
        )
    for slug in PREBUILT_CASES:
        packet_path = PACKET_DIRECTORY / f"{slug}.json"
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        first = export_once(packet_path, packet)
        second = export_once(packet_path, packet)
        if first != second:
            raise RuntimeError(f"nondeterministic Reader output for {slug}")
        output_path = CASE_DIRECTORY / f"{slug}.html"
        output_path.write_bytes(first)
        print(
            json.dumps(
                {
                    "case": slug,
                    "packet_sha256": sha256_bytes(canonical_bytes(packet)),
                    "html_sha256": sha256_bytes(first),
                    "nodes": len(packet["nodes"]),
                    "edges": len(packet["edges"]),
                    "output": output_path.relative_to(REPOSITORY).as_posix(),
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
