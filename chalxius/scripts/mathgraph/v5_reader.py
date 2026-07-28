from __future__ import annotations

import json
import re
from typing import Any

from .contracts import sha256_bytes, sha256_json
from .graph import DependencyGraph
from .reader_html import MAX_EDGES, MAX_NODES, validate_reader_packet


def _one_line(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return re.sub(r"\s+", " ", value).strip()
    return fallback


def _exact_text(value: Any) -> str:
    text = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return text if text else "{}"


def _reader_id(prefix: str, *parts: Any) -> str:
    return f"{prefix}-{sha256_json(list(parts))[:24]}"


def _provenance(
    *,
    plane: str,
    source_status: str,
    truth_status: str,
    object_id: str,
    snapshot_id: str,
    locator: str,
    object_sha256: str,
    original_text: str,
    replaces: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source_plane": plane,
        "source_status": source_status,
        "truth_status": truth_status,
        "object_id": object_id,
        "snapshot_id": snapshot_id,
        "locator": locator,
        "object_sha256": object_sha256,
        "original_text_sha256": sha256_bytes(original_text.encode("utf-8")),
        "replaces": list(replaces or []),
    }


def _node(
    *,
    node_id: str,
    title: str,
    reader_role: str,
    plane: str,
    visual_status: str,
    layer: str,
    theme_id: str,
    summary: str,
    intuition: str,
    importance: str,
    reasoning: str,
    statement: str,
    proof: str,
    relations: list[str],
    original_text: str,
    provenance: dict[str, Any],
    prerequisites: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "title": _one_line(title, node_id),
        "reader_role": reader_role,
        "plane": plane,
        "visual_status": visual_status,
        "layer": layer,
        "theme_id": theme_id,
        "summary": summary or "No summary was recorded.",
        "intuition": intuition or "No separate intuition was recorded.",
        "importance": importance or "Visible in the frozen V5 project projection.",
        "reasoning": reasoning or "Consult the exact bound source object.",
        "prerequisites": list(prerequisites or []),
        "formal": {
            "hypotheses": [],
            "statement": statement,
            "proof": proof,
            "relations": relations,
            "original_text": original_text,
        },
        "provenance": provenance,
    }


def _edge(
    *,
    source: str,
    target: str,
    category: str,
    relation: str,
    exact_type: str,
    weak: bool,
    layer: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    semantic = [
        source,
        target,
        category,
        relation,
        exact_type,
        layer,
        provenance["snapshot_id"],
        provenance["object_id"],
        provenance["object_sha256"],
    ]
    return {
        "id": _reader_id("edge", *semantic),
        "source": source,
        "target": target,
        "category": category,
        "relation": _one_line(relation, exact_type),
        "exact_type": _one_line(exact_type, "related"),
        "weak": weak,
        "layer": layer,
        "provenance": provenance,
    }


def _research_visual_status(record: dict[str, Any]) -> str:
    if record["kind"] in {"challenge", "counterexample", "obstacle"}:
        return "challenged"
    if record["status"] in {"open", "supported", "verifying", "challenged"}:
        return "research"
    return "inactive"


def build_v5_reader_packet(store: Any) -> dict[str, Any]:
    """Project V5 state into the unchanged Reader packet-v1 contract.

    Research, releases, and decisions are explicitly represented as Reader
    projection nodes with nontruth labels.  Only active V5 Facts occupy the
    Fact plane and knowledge prerequisite graph.
    """

    if store.workflow_evidence_version() != 5:
        raise ValueError("the V5 Reader adapter requires a V5 project")
    lifecycle = store.v5_lifecycle()
    facts = store.facts()
    if not facts:
        raise ValueError(
            "V5 Reader projection requires at least one admitted Fact target; "
            "Research cannot be relabeled as knowledge"
        )
    targets = [item for item in store.targets() if item in facts]
    if not targets:
        depended_on = {
            predecessor
            for fact in facts.values()
            for predecessor in fact.predecessors
        }
        targets = sorted(set(facts).difference(depended_on)) or sorted(facts)[-1:]

    project = store.project()
    theme_id = "theme-v5-project"
    inventory: dict[str, Any] = {
        "workflow_evidence_version": 5,
        "project_id": store.project_id(),
        "facts": [],
        "research": [],
        "candidate_releases": [],
        "certification_decisions": [],
        "paper_snapshots": [],
        "blackboard": {"nodes": [], "edges": []},
        "project_background": None,
    }
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    fact_node_ids = {fact_id: f"fact-{fact_id}" for fact_id in facts}

    for fact_id in sorted(facts):
        fact = facts[fact_id]
        path = store.active_fact_path(fact_id)
        object_sha = sha256_bytes(path.read_bytes())
        locator = path.relative_to(store.root).as_posix()
        inventory["facts"].append([fact_id, object_sha])
        statement = fact.statement
        node_id = fact_node_ids[fact_id]
        predecessors = [fact_node_ids[item] for item in fact.predecessors]
        nodes.append(
            _node(
                node_id=node_id,
                title=statement,
                reader_role="target" if fact_id in targets else "result",
                plane="fact",
                visual_status="current",
                layer="knowledge",
                theme_id=theme_id,
                summary=statement,
                intuition=fact.intuition,
                importance=(
                    "Admitted V5 Fact and selected Reader target."
                    if fact_id in targets
                    else "Admitted V5 Fact in the target dependency graph."
                ),
                reasoning="Use only through its admitted predecessor interface.",
                statement=statement,
                proof=fact.proof,
                relations=[f"Depends on Fact {item}." for item in fact.predecessors],
                original_text=statement,
                prerequisites=predecessors,
                provenance=_provenance(
                    plane="fact",
                    source_status="v5_admitted_fact",
                    truth_status="admitted_fact",
                    object_id=fact_id,
                    snapshot_id="pending-v5-snapshot",
                    locator=locator,
                    object_sha256=object_sha,
                    original_text=statement,
                ),
            )
        )
        for predecessor in fact.predecessors:
            relation = f"Fact {predecessor} is a direct prerequisite of {fact_id}."
            edges.append(
                _edge(
                    source=fact_node_ids[predecessor],
                    target=node_id,
                    category="prerequisite",
                    relation=relation,
                    exact_type="fact_predecessor",
                    weak=False,
                    layer="knowledge",
                    provenance=_provenance(
                        plane="fact",
                        source_status="v5_admitted_fact_edge",
                        truth_status="admitted_fact",
                        object_id=f"{predecessor}->{fact_id}",
                        snapshot_id="pending-v5-snapshot",
                        locator=locator,
                        object_sha256=sha256_json(
                            ["fact_predecessor", predecessor, fact_id]
                        ),
                        original_text=relation,
                    ),
                )
            )

    research_records = lifecycle.research_records()
    research_node_ids = {
        item["research_id"]: f"research-{item['research_id']}"
        for item in research_records
    }
    for record in research_records:
        research_id = record["research_id"]
        original_text = record["claim"] + "\n\n" + record["content"]
        inventory["research"].append([research_id, record["record_sha256"]])
        replaces = (
            record["related_research_ids"]
            if record["relation"] in {"replaces", "disposes"}
            else []
        )
        nodes.append(
            _node(
                node_id=research_node_ids[research_id],
                title=record["claim"],
                reader_role="explanation",
                plane="reader",
                visual_status=_research_visual_status(record),
                layer="research",
                theme_id=theme_id,
                summary=record["claim"],
                intuition=record["rationale"],
                importance="Cumulative V5 Research; it has no Fact authority.",
                reasoning="Retain this contribution and its exact relation to prior Research.",
                statement=record["claim"],
                proof=record["content"],
                relations=(
                    [
                        f"{record['relation']} Research {item}."
                        for item in record["related_research_ids"]
                    ]
                    if record["relation"]
                    else []
                ),
                original_text=original_text,
                provenance=_provenance(
                    plane="reader",
                    source_status=(
                        f"v5_research:{record['kind']}:{record['status']}"
                    ),
                    truth_status="reader_note",
                    object_id=research_id,
                    snapshot_id="pending-v5-snapshot",
                    locator=f"research/entries/by-id/{research_id}.json",
                    object_sha256=record["record_sha256"],
                    original_text=original_text,
                    replaces=replaces,
                ),
            )
        )
        for related_id in record["related_research_ids"]:
            if record["kind"] in {"challenge", "counterexample", "obstacle"}:
                source = research_node_ids[research_id]
                target = research_node_ids[related_id]
                category = "conflict"
            else:
                source = research_node_ids[related_id]
                target = research_node_ids[research_id]
                category = "repair" if record["kind"] in {"repair", "disposition"} else "support"
            relation = record["relation"] or "related"
            edges.append(
                _edge(
                    source=source,
                    target=target,
                    category=category,
                    relation=relation,
                    exact_type=f"research_{relation}",
                    weak=True,
                    layer="research",
                    provenance=_provenance(
                        plane="reader",
                        source_status="v5_research_relation",
                        truth_status="reader_note",
                        object_id=f"{research_id}:{related_id}",
                        snapshot_id="pending-v5-snapshot",
                        locator=f"research/entries/by-id/{research_id}.json",
                        object_sha256=sha256_json(
                            [record["record_sha256"], related_id, relation]
                        ),
                        original_text=relation,
                    ),
                )
            )

    releases = lifecycle.releases()
    release_node_ids = {
        item["release_id"]: _reader_id("release", item["release_id"])
        for item in releases
    }
    decisions = lifecycle.decisions()
    decisions_by_release = {item["release_id"]: item for item in decisions}
    for release in releases:
        release_id = release["release_id"]
        decision = decisions_by_release.get(release_id)
        inventory["candidate_releases"].append(
            [release_id, release["record_sha256"]]
        )
        original_text = release["bundle_claim"]
        visual_status = (
            "challenged"
            if decision is not None and decision["verdict"] == "reject"
            else "research"
        )
        nodes.append(
            _node(
                node_id=release_node_ids[release_id],
                title=f"Candidate Release: {release['bundle_claim']}",
                reader_role="result",
                plane="reader",
                visual_status=visual_status,
                layer="research",
                theme_id=theme_id,
                summary=release["bundle_claim"],
                intuition="A sealed nontruth candidate awaiting or carrying certification evidence.",
                importance="Shows the exact boundary between Research and Fact admission.",
                reasoning="Do not use as a premise unless its candidate Fact is separately admitted.",
                statement=release["bundle_claim"],
                proof="Sealed Candidate Release; see its exact candidate records.",
                relations=[
                    f"Binds Research {item['research_id']}."
                    for item in release["research_bindings"]
                ],
                original_text=original_text,
                provenance=_provenance(
                    plane="reader",
                    source_status="v5_candidate_release_sealed_nontruth",
                    truth_status="reader_note",
                    object_id=release_id,
                    snapshot_id="pending-v5-snapshot",
                    locator=f"candidate_releases/by-id/{release_id}.json",
                    object_sha256=release["record_sha256"],
                    original_text=original_text,
                ),
            )
        )
        for binding in release["research_bindings"]:
            research_id = binding["research_id"]
            relation = "Research contribution is sealed into this Candidate Release."
            edges.append(
                _edge(
                    source=research_node_ids[research_id],
                    target=release_node_ids[release_id],
                    category="support",
                    relation=relation,
                    exact_type="candidate_research_binding",
                    weak=True,
                    layer="research",
                    provenance=_provenance(
                        plane="reader",
                        source_status="v5_candidate_binding",
                        truth_status="reader_note",
                        object_id=f"{release_id}:{research_id}",
                        snapshot_id="pending-v5-snapshot",
                        locator=f"candidate_releases/by-id/{release_id}.json",
                        object_sha256=sha256_json([release_id, binding]),
                        original_text=relation,
                    ),
                )
            )

    for decision in decisions:
        decision_id = decision["decision_id"]
        inventory["certification_decisions"].append(
            [decision_id, decision["record_sha256"]]
        )
        node_id = _reader_id("decision", decision_id)
        finding_text = "; ".join(
            item.get("description", "") for item in decision["findings"]
        )
        original_text = finding_text or f"Certification verdict: {decision['verdict']}"
        nodes.append(
            _node(
                node_id=node_id,
                title=f"Certification Decision: {decision['verdict']}",
                reader_role="explanation",
                plane="reader",
                visual_status=(
                    "challenged" if decision["verdict"] == "reject" else "current"
                ),
                layer="research",
                theme_id=theme_id,
                summary=f"Immutable certification verdict: {decision['verdict']}.",
                intuition=finding_text,
                importance="Certification evidence only; admission remains a separate gateway transition.",
                reasoning="Read against the exact sealed Candidate Release and capsule.",
                statement=f"Verdict: {decision['verdict']}",
                proof=finding_text,
                relations=[f"Decides Candidate Release {decision['release_id']}."],
                original_text=original_text,
                provenance=_provenance(
                    plane="reader",
                    source_status=f"v5_certification_decision:{decision['verdict']}",
                    truth_status="reader_note",
                    object_id=decision_id,
                    snapshot_id="pending-v5-snapshot",
                    locator=f"certification/decisions/by-id/{decision_id}.json",
                    object_sha256=decision["record_sha256"],
                    original_text=original_text,
                ),
            )
        )
        relation = f"Certification verdict is {decision['verdict']}."
        if decision["verdict"] == "reject":
            source, target, category = (
                node_id,
                release_node_ids[decision["release_id"]],
                "conflict",
            )
        else:
            source, target, category = (
                release_node_ids[decision["release_id"]],
                node_id,
                "support",
            )
        edges.append(
            _edge(
                source=source,
                target=target,
                category=category,
                relation=relation,
                exact_type="certifies" if category == "support" else "rejects",
                weak=True,
                layer="research",
                provenance=_provenance(
                    plane="reader",
                    source_status="v5_certification_relation",
                    truth_status="reader_note",
                    object_id=f"{decision_id}:{decision['release_id']}",
                    snapshot_id="pending-v5-snapshot",
                    locator=f"certification/decisions/by-id/{decision_id}.json",
                    object_sha256=sha256_json(
                        [decision["record_sha256"], decision["release_id"]]
                    ),
                    original_text=relation,
                ),
            )
        )

    paper = store.paper_logic()
    paper_status = paper.status()
    current_paper = set(paper_status["current_snapshot_ids"])
    all_paper = sorted(
        current_paper.union(paper_status["superseded_snapshot_ids"])
    )
    for paper_snapshot_id in all_paper:
        manifest = paper.snapshot_manifest(paper_snapshot_id)
        paper_nodes, paper_edges = paper.snapshot_objects(paper_snapshot_id)
        graph_kind = manifest["graph_kind"]
        plane = "audit" if graph_kind == "audit" else "paper"
        truth_status = "audit_evidence" if plane == "audit" else "interpretation"
        inventory["paper_snapshots"].append(
            [paper_snapshot_id, sha256_json(manifest)]
        )
        mapped = {
            object_id: _reader_id("paper", paper_snapshot_id, object_id)
            for object_id in paper_nodes
        }
        for object_id, paper_node in sorted(paper_nodes.items()):
            original_text = _exact_text(paper_node)
            object_type = paper_node["object_type"]
            payload = paper_node["payload"]
            statement = _one_line(
                payload.get("statement") or payload.get("text") or payload.get("claim"),
                f"Paper {object_type} {object_id}",
            )
            nodes.append(
                _node(
                    node_id=mapped[object_id],
                    title=statement,
                    reader_role=(
                        "definition"
                        if object_type in {"source_unit", "definition"}
                        else "explanation" if plane == "audit" else "result"
                    ),
                    plane=plane,
                    visual_status=(
                        "current" if paper_snapshot_id in current_paper else "inactive"
                    ),
                    layer="research" if plane == "audit" else "knowledge",
                    theme_id=theme_id,
                    summary=statement,
                    intuition="Exact Paper Logic/Audit projection; no Fact authority.",
                    importance=f"Preserves the native {graph_kind} graph object.",
                    reasoning="Follow the exact snapshot relation and source locator.",
                    statement=statement,
                    proof=original_text,
                    relations=[],
                    original_text=original_text,
                    provenance=_provenance(
                        plane=plane,
                        source_status=(
                            f"paper_{graph_kind}:"
                            + ("current" if paper_snapshot_id in current_paper else "superseded")
                        ),
                        truth_status=truth_status,
                        object_id=object_id,
                        snapshot_id=paper_snapshot_id,
                        locator=f"paper_logic/snapshots/{paper_snapshot_id}/nodes.jsonl",
                        object_sha256=sha256_json(paper_node),
                        original_text=original_text,
                        replaces=(
                            [manifest["supersedes_snapshot_id"]]
                            if manifest["supersedes_snapshot_id"]
                            else []
                        ),
                    ),
                )
            )
        for object_id, paper_edge in sorted(paper_edges.items()):
            relation_type = paper_edge["relation_type"]
            category = (
                "conflict"
                if any(token in relation_type for token in ("challenge", "counter", "defeat"))
                else "repair"
                if any(token in relation_type for token in ("repair", "correct", "replace"))
                else "support"
            )
            relation = f"Paper relation: {relation_type}."
            edges.append(
                _edge(
                    source=mapped[paper_edge["source_id"]],
                    target=mapped[paper_edge["target_id"]],
                    category=category,
                    relation=relation,
                    exact_type=relation_type,
                    weak=True,
                    layer="research" if plane == "audit" else "knowledge",
                    provenance=_provenance(
                        plane=plane,
                        source_status=f"paper_{graph_kind}_relation",
                        truth_status=truth_status,
                        object_id=object_id,
                        snapshot_id=paper_snapshot_id,
                        locator=f"paper_logic/snapshots/{paper_snapshot_id}/edges.jsonl",
                        object_sha256=sha256_json(paper_edge),
                        original_text=relation,
                    ),
                )
            )

    board = store.blackboard()
    board_nodes = board.nodes()
    board_edges = board.edges()
    bb_mapped = {
        object_id: _reader_id("blackboard", object_id)
        for object_id in board_nodes
    }
    for object_id, bb_node in sorted(board_nodes.items()):
        original_text = _exact_text(bb_node)
        inventory["blackboard"]["nodes"].append(
            [object_id, sha256_json(bb_node)]
        )
        title = _one_line(
            bb_node.get("logical_key"), f"Blackboard {bb_node['node_type']}"
        )
        truth = bb_node.get("truth_status", "exploration")
        nodes.append(
            _node(
                node_id=bb_mapped[object_id],
                title=title,
                reader_role=(
                    "definition" if bb_node["node_type"] == "definition" else "explanation"
                ),
                plane="blackboard",
                visual_status=(
                    "challenged"
                    if truth in {"challenged", "blocked"}
                    else "research"
                ),
                layer="research",
                theme_id=theme_id,
                summary=title,
                intuition=_exact_text(bb_node.get("payload", {})),
                importance="Typed cumulative Blackboard exploration.",
                reasoning="This is nontruth exploration and cannot promote itself to Fact.",
                statement=title,
                proof=_exact_text(bb_node.get("payload", {})),
                relations=[],
                original_text=original_text,
                provenance=_provenance(
                    plane="blackboard",
                    source_status=f"blackboard:{bb_node['node_type']}:{truth}",
                    truth_status="exploration",
                    object_id=object_id,
                    snapshot_id="pending-v5-snapshot",
                    locator=f"blackboard/nodes/by-id/{object_id}.json",
                    object_sha256=sha256_json(bb_node),
                    original_text=original_text,
                ),
            )
        )
    for object_id, bb_edge in sorted(board_edges.items()):
        inventory["blackboard"]["edges"].append(
            [object_id, sha256_json(bb_edge)]
        )
        edge_type = bb_edge["edge_type"]
        category = (
            "conflict"
            if edge_type in {"challenges", "blocks", "fails_on"}
            else "repair"
            if edge_type in {"refines", "supersedes", "resolves", "closes"}
            else "support"
        )
        relation = f"Blackboard relation: {edge_type}."
        edges.append(
            _edge(
                source=bb_mapped[bb_edge["source_node_id"]],
                target=bb_mapped[bb_edge["target_node_id"]],
                category=category,
                relation=relation,
                exact_type=edge_type,
                weak=True,
                layer="research",
                provenance=_provenance(
                    plane="blackboard",
                    source_status="blackboard_relation",
                    truth_status="exploration",
                    object_id=object_id,
                    snapshot_id="pending-v5-snapshot",
                    locator=f"blackboard/edges/by-id/{object_id}.json",
                    object_sha256=sha256_json(bb_edge),
                    original_text=relation,
                ),
            )
        )

    background = lifecycle._project_background_binding()
    if background is not None:
        inventory["project_background"] = background["sha256"]
        body = background["body"]
        nodes.append(
            _node(
                node_id="project-background",
                title="Project background",
                reader_role="explanation",
                plane="reader",
                visual_status="research",
                layer="research",
                theme_id=theme_id,
                summary="One user-generated project background summary.",
                intuition=body,
                importance="Makes legacy and abandoned work readable without inheriting authority.",
                reasoning="For load-bearing use, return to the exact cited source.",
                statement="Project background is nontruth context only.",
                proof=body,
                relations=[],
                original_text=body,
                provenance=_provenance(
                    plane="reader",
                    source_status="project_background:default_if_present",
                    truth_status="reader_note",
                    object_id="PROJECT_BACKGROUND.md",
                    snapshot_id="pending-v5-snapshot",
                    locator="PROJECT_BACKGROUND.md",
                    object_sha256=background["sha256"],
                    original_text=body,
                ),
            )
        )

    if len(nodes) > MAX_NODES or len(edges) > MAX_EDGES:
        raise ValueError(
            "V5 projection exceeds the unchanged Reader packet-v1 limits; "
            "refine project scope instead of silently truncating"
        )
    snapshot_sha = sha256_json(inventory)
    snapshot_id = f"v5-reader-{snapshot_sha[:16]}"
    for node in nodes:
        if node["provenance"]["snapshot_id"] == "pending-v5-snapshot":
            node["provenance"]["snapshot_id"] = snapshot_id
    for edge in edges:
        if edge["provenance"]["snapshot_id"] == "pending-v5-snapshot":
            edge["provenance"]["snapshot_id"] = snapshot_id

    graph = DependencyGraph(facts)
    topological = graph.topological_order()
    prerequisite_order = {
        fact_node_ids[target]: [
            fact_node_ids[item]
            for item in topological
            if item in graph.closure([target]) and item != target
        ]
        for target in targets
    }
    audit = store.audit()
    packet = {
        "schema_version": 1,
        "project_id": store.project_id(),
        "language": "en",
        "title": _one_line(project.get("title"), "Chalxius V5 knowledge map"),
        "audience": "A mathematically mature reader inspecting exact V5 authority boundaries",
        "source_snapshot": {
            "id": snapshot_id,
            "sha256": snapshot_sha,
            "description": (
                "Deterministic V5 projection of Fact, Research, Certification, "
                "Paper/Audit, Blackboard, and default-if-present background views."
            ),
        },
        "presentation": {
            "subtitle": "Fact authority and nontruth research remain visibly separate.",
            "introduction": (
                "This offline Reader is a deterministic presentation projection. "
                "Only nodes in the Fact plane labeled admitted_fact are premises."
            ),
        },
        "audit": {
            "current_ok": audit.current_ok,
            "summary": (
                "The V5 project audit is clean."
                if audit.current_ok
                else "The V5 project audit reports unresolved errors."
            ),
            "warnings": list(audit.warnings),
            "unresolved": list(audit.errors),
        },
        "theme_order": [theme_id],
        "target_order": [fact_node_ids[item] for item in targets],
        "prerequisite_order": prerequisite_order,
        "themes": [
            {
                "id": theme_id,
                "label": "V5 project",
                "description": "Admitted targets with visible nontruth research context.",
                "target_ids": [fact_node_ids[item] for item in targets],
            }
        ],
        "nodes": nodes,
        "edges": edges,
    }
    return validate_reader_packet(packet, project_id=store.project_id())
