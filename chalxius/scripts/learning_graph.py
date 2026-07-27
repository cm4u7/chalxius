#!/usr/bin/env python3
"""Build and validate the unified lightweight nontruth learning plane.

The tool is a standard-library, static local-file consumer. It can mount frozen
Fact Graph artifacts, including legacy-compatible inputs, and immutable
Chalxius Paper or Blackboard snapshots. It never invokes a research runtime,
builds a research graph, audits a proof, admits a fact, or writes back to a
mounted source.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import deque
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = {1, SCHEMA_VERSION}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HASH_ID = re.compile(r"^[0-9a-f]{16,64}$")
PAPER_SNAPSHOT_ID = re.compile(r"^pls-[0-9a-f]{64}$")
BLACKBOARD_SNAPSHOT_ID = re.compile(r"^bbs-[0-9a-f]{64}$")
PAPER_PLANES = {"paper_source", "paper_reconstruction", "paper_audit"}
STATUSES = {
    "untested",
    "weak",
    "developing",
    "reconstructable",
    "transfer-ready",
    "blocked",
}
COVERAGE = {
    "unseen",
    "located",
    "read",
    "taught-unchecked",
    "reviewed",
}
PEDAGOGY_KIND_TO_RELATION = {
    "lesson": "teaches",
    "worked-example": "teaches",
    "misconception-repair": "repairs",
    "proof-discussion": "discusses_validity_of",
    "route-comparison": "contrasts_with",
}
SOURCE_IDENTITY_KINDS = {
    "source_fact_artifact_sha256",
    "paper_snapshot_object_binding_sha256",
    "blackboard_snapshot_node_binding_sha256",
}
FOREIGN_IDENTITY_KINDS = {
    "paper_snapshot_object_binding_sha256",
    "blackboard_snapshot_node_binding_sha256",
    "blackboard_boundary_stub_binding_sha256",
}
PAPER_TRUTH_STATUS = {
    "paper_source": "source-bound-nontruth",
    "paper_reconstruction": "reviewed-reconstruction-nontruth",
    "paper_audit": "reviewed-audit-nontruth",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def parse_predecessors(raw: str, path: Path) -> list[str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        if not (raw.startswith("[") and raw.endswith("]")):
            raise ValueError(
                f"{path}: predecessors must be a JSON list or a YAML flow list "
                "of hash IDs"
            )
        inner = raw[1:-1].strip()
        parsed = (
            []
            if not inner
            else [item.strip().strip("\"'") for item in inner.split(",")]
        )

    if not isinstance(parsed, list) or not all(
        isinstance(item, str) and HASH_ID.fullmatch(item) for item in parsed
    ):
        raise ValueError(
            f"{path}: predecessors must contain only 16- to 64-digit lowercase "
            "hexadecimal fact IDs"
        )
    return parsed


def parse_fact(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: missing frontmatter opener")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration as exc:
        raise ValueError(f"{path}: missing frontmatter closer") from exc

    fact_id: str | None = None
    predecessors: list[str] = []
    for line in lines[1:end]:
        if line.startswith("fact_id:"):
            fact_id = line.split(":", 1)[1].strip().strip("\"'")
        elif line.startswith("predecessors:"):
            predecessors = parse_predecessors(line.split(":", 1)[1].strip(), path)

    if not fact_id:
        fact_id = path.stem
    if fact_id != path.stem:
        raise ValueError(
            f"{path}: frontmatter fact_id {fact_id!r} differs from filename"
        )

    preview = ""
    for index, line in enumerate(lines):
        if line.strip() == "## statement":
            for candidate in lines[index + 1 :]:
                if candidate.strip():
                    preview = candidate.strip()
                    break
            break

    return {
        "fact_id": fact_id,
        "predecessors": predecessors,
        "statement_preview": preview[:500],
    }


def find_certificate(root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    candidates = [
        root / "reports" / "target-closure-certificate.json",
        root / "reports" / "final" / "target-closure-certificate.json",
    ]
    for path in candidates:
        if path.is_file():
            return path, load_json(path)
    return None, None


def read_targets(root: Path, certificate: dict[str, Any] | None) -> list[str]:
    if certificate is not None:
        values = certificate.get("targets", [])
        if isinstance(values, list) and all(isinstance(item, str) for item in values):
            return values
    path = root / "TARGETS.txt"
    if not path.is_file():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def snapshot_fact_source(root_arg: str) -> dict[str, Any]:
    requested_root = Path(root_arg).expanduser().resolve()
    if requested_root.name == "fact_graph" and (requested_root / "facts").is_dir():
        root = requested_root.parent
        facts_dir = requested_root / "facts"
    else:
        root = requested_root
        facts_dir = root / "fact_graph" / "facts"
    if not facts_dir.is_dir():
        raise ValueError(
            f"{requested_root}: expected a project root containing "
            "fact_graph/facts or the fact_graph directory itself"
        )

    certificate_path, certificate = find_certificate(root)
    certified_hashes: dict[str, str] = {}
    if certificate is not None:
        candidate = certificate.get("fact_sha256", {})
        if not isinstance(candidate, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in candidate.items()
        ):
            raise ValueError(f"{certificate_path}: invalid fact_sha256 mapping")
        certified_hashes = candidate

    facts: list[dict[str, Any]] = []
    id_to_hash: dict[str, str] = {}
    for path in sorted(facts_dir.glob("*.md")):
        parsed = parse_fact(path)
        actual_hash = file_sha256(path)
        fact_id = parsed["fact_id"]
        expected_hash = certified_hashes.get(fact_id)
        if expected_hash is not None and actual_hash != expected_hash:
            raise ValueError(
                f"{path}: certificate mismatch, expected {expected_hash}, "
                f"found {actual_hash}"
            )
        id_to_hash[fact_id] = actual_hash
        facts.append(
            {
                **parsed,
                "artifact_sha256": actual_hash,
                "relative_path": str(path.relative_to(root)),
                "certificate_bound": expected_hash is not None,
            }
        )

    unknown_predecessors: list[dict[str, str]] = []
    for fact in facts:
        for predecessor in fact["predecessors"]:
            if predecessor not in id_to_hash:
                unknown_predecessors.append(
                    {"fact_id": fact["fact_id"], "predecessor": predecessor}
                )
    if unknown_predecessors:
        raise ValueError(
            "source graph has unknown predecessors: "
            + json.dumps(unknown_predecessors, ensure_ascii=False)
        )

    project_path = root / "project.json"
    project_hash = file_sha256(project_path) if project_path.is_file() else None
    project_id = None
    if project_path.is_file():
        project_id = load_json(project_path).get("project_id")

    targets = read_targets(root, certificate)
    unknown_targets = [target for target in targets if target not in id_to_hash]
    if unknown_targets:
        raise ValueError(f"{root}: unknown target IDs {unknown_targets}")

    graph_fingerprint = canonical_sha256(
        {
            "project_json_sha256": project_hash,
            "facts": {fact["fact_id"]: fact["artifact_sha256"] for fact in facts},
            "targets": targets,
        }
    )
    return {
        "source_kind": "fact_graph",
        "source_root": str(root),
        "project_id": project_id,
        "project_json_sha256": project_hash,
        "certificate_path": (
            str(certificate_path.relative_to(root)) if certificate_path else None
        ),
        "certificate_sha256": (
            file_sha256(certificate_path) if certificate_path else None
        ),
        "graph_fingerprint": graph_fingerprint,
        "facts": facts,
        "id_to_hash": id_to_hash,
        "targets": targets,
        "selection": {},
    }


def snapshot_source(root_arg: str) -> dict[str, Any]:
    """Backward-compatible name for the frozen Fact Graph adapter."""

    return snapshot_fact_source(root_arg)


def load_bound_jsonl(
    path: Path,
    entries: Any,
    *,
    entry_id_field: str,
    object_id_field: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if not isinstance(entries, list):
        raise ValueError(f"{path.parent / 'manifest.json'}: entries must be a list")
    expected: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{path.parent / 'manifest.json'}: invalid entry")
        object_id = entry.get(entry_id_field)
        digest = entry.get("sha256")
        if not isinstance(object_id, str) or not isinstance(digest, str):
            raise ValueError(f"{path.parent / 'manifest.json'}: malformed entry")
        if object_id in expected:
            raise ValueError(f"{path.parent / 'manifest.json'}: duplicate {object_id}")
        if not HEX64.fullmatch(digest):
            raise ValueError(f"{path.parent / 'manifest.json'}: invalid hash for {object_id}")
        expected[object_id] = digest

    if not path.is_file():
        raise ValueError(f"missing frozen snapshot member: {path}")
    objects: list[dict[str, Any]] = []
    actual_ids: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"{path}:{number}: blank JSONL line")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{number}: expected a JSON object")
        object_id = value.get(object_id_field)
        if not isinstance(object_id, str) or not object_id:
            raise ValueError(f"{path}:{number}: missing {object_id_field}")
        if object_id in actual_ids:
            raise ValueError(f"{path}:{number}: duplicate {object_id}")
        actual_ids.add(object_id)
        actual_hash = canonical_sha256(value)
        expected_hash = expected.get(object_id)
        if expected_hash is None:
            raise ValueError(f"{path}:{number}: unmanifested object {object_id}")
        if actual_hash != expected_hash:
            raise ValueError(
                f"{path}:{number}: object drift for {object_id}, expected "
                f"{expected_hash}, found {actual_hash}"
            )
        objects.append(value)
    missing = sorted(set(expected) - actual_ids)
    if missing:
        raise ValueError(f"{path}: manifest objects missing from JSONL: {missing}")
    return objects, expected


def resolve_frozen_snapshot(
    root_arg: str, snapshot_id: str, *, source_kind: str
) -> Path:
    requested = Path(root_arg).expanduser().resolve()
    if source_kind == "paper_graph":
        pattern = PAPER_SNAPSHOT_ID
        candidates = [
            requested,
            requested / "paper_logic" / "snapshots" / "by-id" / snapshot_id,
            requested / "snapshots" / "by-id" / snapshot_id,
            requested / "by-id" / snapshot_id,
        ]
    elif source_kind == "blackboard":
        pattern = BLACKBOARD_SNAPSHOT_ID
        candidates = [
            requested,
            requested / "blackboard" / "snapshots" / "by-hash" / snapshot_id,
            requested / "snapshots" / "by-hash" / snapshot_id,
            requested / "by-hash" / snapshot_id,
        ]
    else:
        raise ValueError(f"unsupported frozen snapshot kind {source_kind!r}")
    if not pattern.fullmatch(snapshot_id):
        raise ValueError(f"invalid {source_kind} snapshot id {snapshot_id!r}")
    for candidate in candidates:
        if candidate.name == snapshot_id and (candidate / "manifest.json").is_file():
            return candidate
    raise ValueError(
        f"{requested}: cannot resolve immutable {snapshot_id} snapshot directory"
    )


def snapshot_project_root(snapshot_dir: Path, store_name: str) -> Path:
    try:
        if snapshot_dir.parents[2].name == store_name:
            return snapshot_dir.parents[3]
    except IndexError:
        pass
    return snapshot_dir


def select_snapshot_subgraph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    node_id_field: str,
    source_field: str,
    target_field: str,
    eligible_ids: set[str],
    seed_ids: Iterable[str],
    radius: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if radius < 0:
        raise ValueError("radius must be nonnegative")
    seeds = sorted(set(seed_ids))
    unknown = [seed for seed in seeds if seed not in eligible_ids]
    if unknown:
        raise ValueError(f"seed IDs are missing or excluded by filters: {unknown}")
    selected_ids = set(eligible_ids)
    if seeds:
        adjacency: dict[str, set[str]] = {node_id: set() for node_id in eligible_ids}
        for edge in edges:
            source = edge.get(source_field)
            target = edge.get(target_field)
            if source in eligible_ids and target in eligible_ids:
                adjacency[source].add(target)
                adjacency[target].add(source)
        selected_ids = set(seeds)
        frontier = deque((seed, 0) for seed in seeds)
        while frontier:
            node_id, depth = frontier.popleft()
            if depth >= radius:
                continue
            for neighbor in sorted(adjacency[node_id]):
                if neighbor not in selected_ids:
                    selected_ids.add(neighbor)
                    frontier.append((neighbor, depth + 1))
    selected_nodes = [
        node for node in nodes if node.get(node_id_field) in selected_ids
    ]
    selected_edges = [
        edge
        for edge in edges
        if edge.get(source_field) in selected_ids
        and edge.get(target_field) in selected_ids
    ]
    return selected_nodes, selected_edges


def preview_object(value: dict[str, Any]) -> str:
    payload = value.get("payload")
    candidates: list[Any] = []
    if isinstance(payload, dict):
        for field in (
            "claim",
            "statement",
            "text",
            "observed_excerpt",
            "compared_text",
            "definiens",
            "summary",
            "note",
            "content",
            "question",
        ):
            candidates.append(payload.get(field))
        paper_object = payload.get("paper_object")
        if isinstance(paper_object, dict):
            candidates.append(paper_object.get("logical_key"))
            nested = paper_object.get("payload")
            if isinstance(nested, dict):
                for field in ("claim", "statement", "text", "definiens"):
                    candidates.append(nested.get(field))
    candidates.extend([value.get("logical_key"), value.get("object_type"), value.get("node_type")])
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return " ".join(candidate.split())[:500]
    return json.dumps(value, ensure_ascii=False, sort_keys=True)[:500]


def snapshot_paper_source(
    root_arg: str,
    snapshot_id: str,
    *,
    include_planes: Iterable[str] | None = None,
    current_audit_only: bool = False,
    seed_ids: Iterable[str] = (),
    radius: int = 1,
) -> dict[str, Any]:
    snapshot_dir = resolve_frozen_snapshot(
        root_arg, snapshot_id, source_kind="paper_graph"
    )
    manifest_path = snapshot_dir / "manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("snapshot_id") != snapshot_id:
        raise ValueError(f"{manifest_path}: snapshot_id mismatch")
    if manifest.get("truth_effect") != "none":
        raise ValueError(f"{manifest_path}: paper snapshot must have truth_effect none")
    nodes, node_hashes = load_bound_jsonl(
        snapshot_dir / "nodes.jsonl",
        manifest.get("node_entries"),
        entry_id_field="object_id",
        object_id_field="object_id",
    )
    edges, edge_hashes = load_bound_jsonl(
        snapshot_dir / "edges.jsonl",
        manifest.get("edge_entries"),
        entry_id_field="object_id",
        object_id_field="object_id",
    )
    node_ids = set(node_hashes)
    for node in nodes:
        if node.get("truth_effect") != "none":
            raise ValueError(
                f"{snapshot_dir}: paper node {node.get('object_id')} changes truth"
            )
        if node.get("plane") not in PAPER_PLANES:
            raise ValueError(
                f"{snapshot_dir}: unsupported paper plane {node.get('plane')!r}"
            )
    for edge in edges:
        if edge.get("truth_effect") != "none":
            raise ValueError(
                f"{snapshot_dir}: paper edge {edge.get('object_id')} changes truth"
            )
        if edge.get("source_id") not in node_ids or edge.get("target_id") not in node_ids:
            raise ValueError(
                f"{snapshot_dir}: dangling paper edge {edge.get('object_id')}"
            )

    current_ids = set(manifest.get("current_audit_node_ids", []))
    inactive_ids = set(manifest.get("inactive_audit_node_ids", []))
    if current_ids & inactive_ids:
        raise ValueError(f"{manifest_path}: current and inactive audit sets overlap")
    audit_ids = {
        node["object_id"] for node in nodes if node.get("plane") == "paper_audit"
    }
    if not current_ids <= audit_ids or not inactive_ids <= audit_ids:
        raise ValueError(f"{manifest_path}: audit-state IDs are not audit nodes")

    planes = set(include_planes or PAPER_PLANES)
    if not planes or not planes <= PAPER_PLANES:
        raise ValueError(f"invalid paper plane filter: {sorted(planes)}")
    eligible = {
        node["object_id"]
        for node in nodes
        if node["plane"] in planes
        and not (
            current_audit_only
            and node["plane"] == "paper_audit"
            and node["object_id"] not in current_ids
        )
    }
    selected_nodes, selected_edges = select_snapshot_subgraph(
        nodes,
        edges,
        node_id_field="object_id",
        source_field="source_id",
        target_field="target_id",
        eligible_ids=eligible,
        seed_ids=seed_ids,
        radius=radius,
    )
    selected_ids = {node["object_id"] for node in selected_nodes}
    selection = {
        "include_planes": sorted(planes),
        "current_audit_only": current_audit_only,
        "seed_ids": sorted(set(seed_ids)),
        "radius": radius,
    }
    manifest_hash = file_sha256(manifest_path)
    graph_fingerprint = canonical_sha256(
        {
            "source_kind": "paper_graph",
            "snapshot_id": snapshot_id,
            "manifest_sha256": manifest_hash,
            "selection": selection,
            "selected_node_ids": sorted(selected_ids),
            "selected_edge_ids": sorted(edge["object_id"] for edge in selected_edges),
        }
    )
    adapted_nodes = []
    for node in selected_nodes:
        node_id = node["object_id"]
        audit_state = "not-applicable"
        if node["plane"] == "paper_audit":
            if node_id in current_ids:
                audit_state = "current"
            elif node_id in inactive_ids:
                audit_state = "inactive"
            else:
                audit_state = "unclassified"
        adapted_nodes.append(
            {
                "source_object_id": node_id,
                "object_sha256": node_hashes[node_id],
                "source_object": node,
                "statement_preview": preview_object(node),
                "truth_status": PAPER_TRUTH_STATUS[node["plane"]],
                "source_metadata": {
                    "plane": node["plane"],
                    "object_type": node.get("object_type"),
                    "logical_key": node.get("logical_key"),
                    "audit_state": audit_state,
                },
            }
        )
    adapted_edges = [
        {
            "source_edge_id": edge["object_id"],
            "edge_sha256": edge_hashes[edge["object_id"]],
            "from_source_id": edge["source_id"],
            "to_source_id": edge["target_id"],
            "relation": edge.get("relation_type"),
            "source_edge": edge,
        }
        for edge in selected_edges
    ]
    targets = [
        {
            "source_object_id": node["object_id"],
            "target_role": node.get("payload", {}).get("target_role", "paper-target"),
        }
        for node in selected_nodes
        if node.get("object_type") == "paper_target"
    ]
    project_root = snapshot_project_root(snapshot_dir, "paper_logic")
    return {
        "source_kind": "paper_graph",
        "source_root": str(project_root),
        "snapshot_dir": str(snapshot_dir),
        "snapshot_id": snapshot_id,
        "project_id": manifest.get("project_id"),
        "paper_id": manifest.get("paper_id"),
        "manifest_sha256": manifest_hash,
        "graph_fingerprint": graph_fingerprint,
        "selection": selection,
        "nodes": adapted_nodes,
        "edges": adapted_edges,
        "targets": targets,
        "total_node_count": len(nodes),
        "total_edge_count": len(edges),
        "mounted_node_count": len(adapted_nodes),
        "mounted_edge_count": len(adapted_edges),
    }


def snapshot_blackboard_source(
    root_arg: str,
    snapshot_id: str,
    *,
    include_node_types: Iterable[str] = (),
    seed_ids: Iterable[str] = (),
    radius: int = 1,
) -> dict[str, Any]:
    snapshot_dir = resolve_frozen_snapshot(
        root_arg, snapshot_id, source_kind="blackboard"
    )
    manifest_path = snapshot_dir / "manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("snapshot_id") != snapshot_id:
        raise ValueError(f"{manifest_path}: snapshot_id mismatch")
    nodes, node_hashes = load_bound_jsonl(
        snapshot_dir / "nodes.jsonl",
        manifest.get("node_entries"),
        entry_id_field="node_id",
        object_id_field="node_id",
    )
    edges, edge_hashes = load_bound_jsonl(
        snapshot_dir / "edges.jsonl",
        manifest.get("edge_entries"),
        entry_id_field="edge_id",
        object_id_field="edge_id",
    )
    node_ids = set(node_hashes)
    for node in nodes:
        if node.get("truth_status") != "exploration":
            raise ValueError(
                f"{snapshot_dir}: Blackboard node {node.get('node_id')} is not exploration"
            )
    omission_receipt = manifest.get("omission_receipt", {})
    if not isinstance(omission_receipt, dict):
        raise ValueError(f"{manifest_path}: omission_receipt must be an object")
    declared_boundary = set(omission_receipt.get("boundary_node_ids", []))
    external_ids = {
        endpoint
        for edge in edges
        for endpoint in (edge.get("source_node_id"), edge.get("target_node_id"))
        if endpoint not in node_ids
    }
    if not all(isinstance(node_id, str) for node_id in external_ids):
        raise ValueError(f"{snapshot_dir}: Blackboard edge has a missing endpoint id")
    if not external_ids <= declared_boundary:
        raise ValueError(
            f"{manifest_path}: undeclared boundary endpoints "
            f"{sorted(external_ids - declared_boundary)}"
        )
    omitted_count = omission_receipt.get("omitted_node_count", 0)
    if external_ids and omitted_count < len(external_ids):
        raise ValueError(
            f"{manifest_path}: omission receipt understates boundary endpoints"
        )

    node_types = sorted(set(include_node_types))
    eligible = {
        node["node_id"]
        for node in nodes
        if not node_types or node.get("node_type") in node_types
    }
    selected_nodes, selected_edges = select_snapshot_subgraph(
        nodes,
        edges,
        node_id_field="node_id",
        source_field="source_node_id",
        target_field="target_node_id",
        eligible_ids=eligible,
        seed_ids=seed_ids,
        radius=radius,
    )
    selected_actual_ids = {node["node_id"] for node in selected_nodes}
    boundary_edges = [
        edge
        for edge in edges
        if (
            edge.get("source_node_id") in selected_actual_ids
            and edge.get("target_node_id") in external_ids
        )
        or (
            edge.get("target_node_id") in selected_actual_ids
            and edge.get("source_node_id") in external_ids
        )
    ]
    selected_edge_ids = {edge["edge_id"] for edge in selected_edges}
    selected_edges.extend(
        edge for edge in boundary_edges if edge["edge_id"] not in selected_edge_ids
    )
    selected_external_ids = {
        endpoint
        for edge in selected_edges
        for endpoint in (edge["source_node_id"], edge["target_node_id"])
        if endpoint in external_ids
    }
    selected_ids = selected_actual_ids | selected_external_ids
    selection = {
        "include_node_types": node_types,
        "seed_ids": sorted(set(seed_ids)),
        "radius": radius,
    }
    manifest_hash = file_sha256(manifest_path)
    graph_fingerprint = canonical_sha256(
        {
            "source_kind": "blackboard",
            "snapshot_id": snapshot_id,
            "manifest_sha256": manifest_hash,
            "selection": selection,
            "selected_node_ids": sorted(selected_ids),
            "selected_edge_ids": sorted(edge["edge_id"] for edge in selected_edges),
        }
    )
    adapted_nodes = [
        {
            "binding_kind": "snapshot-object",
            "source_object_id": node["node_id"],
            "object_sha256": node_hashes[node["node_id"]],
            "source_object": node,
            "statement_preview": preview_object(node),
            "truth_status": "exploration-nontruth",
            "source_metadata": {
                "node_type": node.get("node_type"),
                "logical_key": node.get("logical_key"),
                "truth_status_at_source": node.get("truth_status"),
            },
        }
        for node in selected_nodes
    ]
    omission_receipt_sha256 = canonical_sha256(omission_receipt)
    for node_id in sorted(selected_external_ids):
        stub_object = {
            "node_id": node_id,
            "omitted_from_snapshot": snapshot_id,
            "omission_receipt_sha256": omission_receipt_sha256,
            "source_payload_available": False,
        }
        adapted_nodes.append(
            {
                "binding_kind": "omitted-boundary-stub",
                "identity_kind": "blackboard_boundary_stub_binding_sha256",
                "source_object_id": node_id,
                "object_sha256": canonical_sha256(stub_object),
                "source_object": stub_object,
                "statement_preview": (
                    f"Omitted Blackboard boundary node {node_id}; source payload "
                    "is not present in this bounded snapshot."
                ),
                "truth_status": "omitted-boundary-nontruth",
                "source_metadata": {
                    "node_type": "omitted_boundary_stub",
                    "logical_key": None,
                    "truth_status_at_source": "unknown-omitted",
                    "omission_receipt_sha256": omission_receipt_sha256,
                },
            }
        )
    adapted_edges = [
        {
            "source_edge_id": edge["edge_id"],
            "edge_sha256": edge_hashes[edge["edge_id"]],
            "from_source_id": edge["source_node_id"],
            "to_source_id": edge["target_node_id"],
            "relation": edge.get("edge_type"),
            "source_edge": edge,
        }
        for edge in selected_edges
    ]
    targets = [
        {"source_object_id": node_id, "target_role": "blackboard-seed"}
        for node_id in manifest.get("seed_node_ids", [])
        if node_id in selected_ids
    ]
    project_root = snapshot_project_root(snapshot_dir, "blackboard")
    return {
        "source_kind": "blackboard",
        "source_root": str(project_root),
        "snapshot_dir": str(snapshot_dir),
        "snapshot_id": snapshot_id,
        "project_id": None,
        "manifest_sha256": manifest_hash,
        "query_sha256": manifest.get("query_sha256"),
        "omission_receipt": omission_receipt,
        "omission_receipt_sha256": omission_receipt_sha256,
        "graph_fingerprint": graph_fingerprint,
        "selection": selection,
        "nodes": adapted_nodes,
        "edges": adapted_edges,
        "targets": targets,
        "total_node_count": len(nodes),
        "total_edge_count": len(edges),
        "mounted_node_count": len(adapted_nodes),
        "mounted_edge_count": len(adapted_edges),
        "boundary_stub_count": len(selected_external_ids),
    }


def empty_learning_graph() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "graph_family": "mathgraph-unified-nontruth-learning-plane",
        "identity_policy": {
            "native_fact_key": "exact source fact artifact SHA-256",
            "foreign_anchor_key": (
                "canonical SHA-256 of source kind, frozen snapshot id, object id, "
                "and exact object SHA-256"
            ),
            "source_aliases": "preserved verbatim but never used alone as identity",
            "learning_evidence": "separately content-addressed canonical JSON events",
            "teaching_coverage": "separate from testing mastery and evidence",
        },
        "interop_policy": {
            "protocol": "unified-static-snapshot-mount-v1",
            "runtime_owner": "none-static-consumer",
            "native_graph_family": "fact_graph",
            "legacy_input_compatibility": "danus-fact-graph-read-only",
            "allowed_foreign_sources": ["chalk-paper-snapshot", "chalk-blackboard-snapshot"],
            "source_requirements": "immutable manifest-bound local snapshot",
            "truth_inheritance": "forbidden",
            "writeback": "forbidden",
            "research_runtime_invocation": "forbidden",
            "pedagogy_review_level": "lightweight-learning-overlay-only",
        },
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "sources": {},
        "nodes": {},
        "edges": [],
        "targets": [],
        "source_concern_events": {},
        "source_id_index": {},
        "source_alias_index": {},
        "source_alias_collisions": {},
        "short_id_collisions": {},
    }


def learning_state() -> dict[str, Any]:
    return {
        "coverage": "unseen",
        "last_taught_at": None,
        "teaching_events": [],
        "mastery": 0,
        "status": "untested",
        "last_evidence_at": None,
        "next_due_review": None,
        "evidence": [],
    }


def foreign_identity_payload(source_kind: str, snapshot_id: str, node: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source_kind": source_kind,
        "snapshot_id": snapshot_id,
        "binding_kind": node.get("binding_kind", "snapshot-object"),
        "object_id": node["source_object_id"],
        "object_sha256": node["object_sha256"],
    }


def rebuild_indexes(graph: dict[str, Any]) -> None:
    aliases: dict[str, set[str]] = {}
    short_facts: dict[str, set[str]] = {}
    source_id_index: dict[str, str] = {}
    for node_hash, node in graph["nodes"].items():
        for fact_id in node.get("source_fact_ids", []):
            aliases.setdefault(fact_id, set()).add(node_hash)
            short_facts.setdefault(fact_id, set()).add(node_hash)
        for object_id in node.get("source_object_ids", []):
            aliases.setdefault(object_id, set()).add(node_hash)
        for ref in node.get("source_refs", []):
            fingerprint = ref.get("graph_fingerprint")
            alias = ref.get("source_fact_id") or ref.get("source_object_id")
            if isinstance(fingerprint, str) and isinstance(alias, str):
                source_id_index[f"{fingerprint}:{alias}"] = node_hash
    graph["source_id_index"] = source_id_index
    graph["source_alias_index"] = {
        alias: sorted(hashes) for alias, hashes in sorted(aliases.items())
    }
    graph["source_alias_collisions"] = {
        alias: sorted(hashes)
        for alias, hashes in sorted(aliases.items())
        if len(hashes) > 1
    }
    graph["short_id_collisions"] = {
        alias: sorted(hashes)
        for alias, hashes in sorted(short_facts.items())
        if len(hashes) > 1
    }


def source_record(snapshot: dict[str, Any]) -> dict[str, Any]:
    if snapshot["source_kind"] == "fact_graph":
        return {
            "source_kind": "fact_graph",
            "graph_fingerprint": snapshot["graph_fingerprint"],
            "source_root": snapshot["source_root"],
            "project_id": snapshot["project_id"],
            "project_json_sha256": snapshot["project_json_sha256"],
            "certificate_path": snapshot["certificate_path"],
            "certificate_sha256": snapshot["certificate_sha256"],
            "selection": {},
            "imported_at": utc_now(),
        }
    return {
        "source_kind": snapshot["source_kind"],
        "graph_fingerprint": snapshot["graph_fingerprint"],
        "source_root": snapshot["source_root"],
        "snapshot_dir": snapshot["snapshot_dir"],
        "snapshot_id": snapshot["snapshot_id"],
        "project_id": snapshot.get("project_id"),
        "manifest_sha256": snapshot["manifest_sha256"],
        "selection": snapshot["selection"],
        "total_node_count": snapshot["total_node_count"],
        "total_edge_count": snapshot["total_edge_count"],
        "mounted_node_count": snapshot["mounted_node_count"],
        "mounted_edge_count": snapshot["mounted_edge_count"],
        "boundary_stub_count": snapshot.get("boundary_stub_count", 0),
        "omission_receipt_sha256": snapshot.get("omission_receipt_sha256"),
        "imported_at": utc_now(),
    }


def merge_snapshot(graph: dict[str, Any], snapshot: dict[str, Any]) -> None:
    fingerprint = snapshot["graph_fingerprint"]
    if fingerprint in graph["sources"]:
        return
    source_kind = snapshot["source_kind"]
    graph["sources"][fingerprint] = source_record(snapshot)

    if source_kind == "fact_graph":
        for fact in snapshot["facts"]:
            node_hash = fact["artifact_sha256"]
            if not HEX64.fullmatch(node_hash):
                raise ValueError(f"invalid source fact hash {node_hash!r}")
            node = graph["nodes"].setdefault(
                node_hash,
                {
                    "node_hash": node_hash,
                    "identity_kind": "source_fact_artifact_sha256",
                    "anchor_kind": "fact_graph",
                    "source_fact_ids": [],
                    "source_object_ids": [],
                    "source_refs": [],
                    "statement_preview": fact["statement_preview"],
                    "truth_status": "admitted",
                    "learning": learning_state(),
                },
            )
            if node.get("identity_kind") != "source_fact_artifact_sha256":
                raise ValueError(f"identity collision at source fact hash {node_hash}")
            if fact["fact_id"] not in node["source_fact_ids"]:
                node["source_fact_ids"].append(fact["fact_id"])
                node["source_fact_ids"].sort()
            if fact["fact_id"] not in node["source_object_ids"]:
                node["source_object_ids"].append(fact["fact_id"])
                node["source_object_ids"].sort()
            ref = {
                "source_kind": "fact_graph",
                "graph_fingerprint": fingerprint,
                "source_root": snapshot["source_root"],
                "source_fact_id": fact["fact_id"],
                "relative_path": fact["relative_path"],
                "artifact_sha256": node_hash,
                "certificate_bound": fact["certificate_bound"],
            }
            if ref not in node["source_refs"]:
                node["source_refs"].append(ref)
    else:
        for source_node in snapshot["nodes"]:
            identity_kind = source_node.get("identity_kind") or (
                "paper_snapshot_object_binding_sha256"
                if source_kind == "paper_graph"
                else "blackboard_snapshot_node_binding_sha256"
            )
            anchor_kind = (
                "paper_graph"
                if source_kind == "paper_graph"
                else (
                    "blackboard_boundary"
                    if identity_kind == "blackboard_boundary_stub_binding_sha256"
                    else "blackboard"
                )
            )
            identity_payload = foreign_identity_payload(
                source_kind, snapshot["snapshot_id"], source_node
            )
            node_hash = canonical_sha256(identity_payload)
            existing = graph["nodes"].get(node_hash)
            if existing is None:
                graph["nodes"][node_hash] = {
                    "node_hash": node_hash,
                    "identity_kind": identity_kind,
                    "identity_payload": identity_payload,
                    "anchor_kind": anchor_kind,
                    "source_fact_ids": [],
                    "source_object_ids": [source_node["source_object_id"]],
                    "source_refs": [],
                    "source_object": source_node["source_object"],
                    "source_metadata": source_node["source_metadata"],
                    "statement_preview": source_node["statement_preview"],
                    "truth_status": source_node["truth_status"],
                    "learning": learning_state(),
                }
                existing = graph["nodes"][node_hash]
            if (
                existing.get("identity_kind") != identity_kind
                or existing.get("identity_payload") != identity_payload
                or existing.get("source_object") != source_node["source_object"]
            ):
                raise ValueError(f"foreign anchor identity collision at {node_hash}")
            ref = {
                "source_kind": source_kind,
                "graph_fingerprint": fingerprint,
                "source_root": snapshot["source_root"],
                "snapshot_dir": snapshot["snapshot_dir"],
                "snapshot_id": snapshot["snapshot_id"],
                "source_object_id": source_node["source_object_id"],
                "object_sha256": source_node["object_sha256"],
                "manifest_sha256": snapshot["manifest_sha256"],
                "binding_kind": source_node.get("binding_kind", "snapshot-object"),
            }
            if ref not in existing["source_refs"]:
                existing["source_refs"].append(ref)

    existing_edges = {
        (
            edge.get("from"),
            edge.get("to"),
            edge.get("relation"),
            edge.get("source_kind"),
            edge.get("source_snapshot_id"),
            edge.get("source_edge_id"),
            edge.get("source_graph"),
        )
        for edge in graph["edges"]
    }
    if source_kind == "fact_graph":
        for fact in snapshot["facts"]:
            child_hash = fact["artifact_sha256"]
            for predecessor in fact["predecessors"]:
                edge = {
                    "from": child_hash,
                    "to": snapshot["id_to_hash"][predecessor],
                    "relation": "requires",
                    "source_kind": "fact_graph",
                    "source_graph": fingerprint,
                }
                key = (
                    edge["from"], edge["to"], edge["relation"], edge["source_kind"],
                    None, None, edge["source_graph"]
                )
                if key not in existing_edges:
                    graph["edges"].append(edge)
                    existing_edges.add(key)
    else:
        id_to_hash = {
            node["source_object_id"]: canonical_sha256(
                foreign_identity_payload(source_kind, snapshot["snapshot_id"], node)
            )
            for node in snapshot["nodes"]
        }
        for source_edge in snapshot["edges"]:
            edge = {
                "from": id_to_hash[source_edge["from_source_id"]],
                "to": id_to_hash[source_edge["to_source_id"]],
                "relation": source_edge["relation"],
                "source_kind": source_kind,
                "source_graph": fingerprint,
                "source_snapshot_id": snapshot["snapshot_id"],
                "source_edge_id": source_edge["source_edge_id"],
                "source_edge_sha256": source_edge["edge_sha256"],
                "source_edge": source_edge["source_edge"],
            }
            key = (
                edge["from"], edge["to"], edge["relation"], edge["source_kind"],
                edge["source_snapshot_id"], edge["source_edge_id"], edge["source_graph"]
            )
            if key not in existing_edges:
                graph["edges"].append(edge)
                existing_edges.add(key)

    existing_targets = {
        (entry.get("source_graph"), entry.get("source_object_id") or entry.get("source_fact_id"))
        for entry in graph["targets"]
    }
    if source_kind == "fact_graph":
        for target in snapshot["targets"]:
            key = (fingerprint, target)
            if key not in existing_targets:
                graph["targets"].append(
                    {
                        "source_kind": "fact_graph",
                        "source_graph": fingerprint,
                        "source_fact_id": target,
                        "source_object_id": target,
                        "node_hash": snapshot["id_to_hash"][target],
                        "target_role": "fact-target",
                    }
                )
                existing_targets.add(key)
    else:
        lookup = {
            node["source_object_id"]: canonical_sha256(
                foreign_identity_payload(source_kind, snapshot["snapshot_id"], node)
            )
            for node in snapshot["nodes"]
        }
        for target in snapshot["targets"]:
            source_id = target["source_object_id"]
            key = (fingerprint, source_id)
            if key not in existing_targets:
                graph["targets"].append(
                    {
                        "source_kind": source_kind,
                        "source_graph": fingerprint,
                        "source_snapshot_id": snapshot["snapshot_id"],
                        "source_object_id": source_id,
                        "node_hash": lookup[source_id],
                        "target_role": target["target_role"],
                    }
                )
                existing_targets.add(key)

    rebuild_indexes(graph)
    graph["updated_at"] = utc_now()


def seal_graph(graph: dict[str, Any]) -> dict[str, Any]:
    sealed = copy.deepcopy(graph)
    sealed.pop("learning_graph_sha256", None)
    sealed["learning_graph_sha256"] = canonical_sha256(sealed)
    return sealed


def verify_seal(graph: dict[str, Any]) -> None:
    expected = graph.get("learning_graph_sha256")
    if not isinstance(expected, str):
        raise ValueError("learning graph has no learning_graph_sha256")
    unsealed = copy.deepcopy(graph)
    unsealed.pop("learning_graph_sha256", None)
    actual = canonical_sha256(unsealed)
    if actual != expected:
        raise ValueError(
            f"learning graph hash mismatch: expected {expected}, found {actual}"
        )


def atomic_write_json(path: Path, value: dict[str, Any], *, refuse_exists: bool) -> None:
    path = path.expanduser().resolve()
    if refuse_exists and path.exists():
        raise FileExistsError(f"{path}: output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def migrate_v1(graph: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(graph)
    migrated.pop("learning_graph_sha256", None)
    migrated["schema_version"] = SCHEMA_VERSION
    policy = empty_learning_graph()
    migrated["graph_family"] = policy["graph_family"]
    migrated["identity_policy"] = policy["identity_policy"]
    migrated["interop_policy"] = policy["interop_policy"]
    for fingerprint, source in migrated.get("sources", {}).items():
        source.setdefault("source_kind", "fact_graph")
        source.setdefault("graph_fingerprint", fingerprint)
        source.setdefault("selection", {})
    for node in migrated.get("nodes", {}).values():
        if node.get("identity_kind") == "source_fact_artifact_sha256":
            node.setdefault("anchor_kind", "fact_graph")
            node.setdefault("source_object_ids", list(node.get("source_fact_ids", [])))
            for ref in node.get("source_refs", []):
                ref.setdefault("source_kind", "fact_graph")
                if "source_fact_id" in ref:
                    ref.setdefault("source_object_id", ref["source_fact_id"])
        elif node.get("identity_kind") == "pedagogical_content_sha256":
            node.setdefault("anchor_kind", "pedagogical")
            node.setdefault("source_object_ids", [])
    for edge in migrated.get("edges", []):
        if edge.get("source_graph") is not None:
            edge.setdefault("source_kind", "fact_graph")
    for target in migrated.get("targets", []):
        target.setdefault("source_kind", "fact_graph")
        if "source_fact_id" in target:
            target.setdefault("source_object_id", target["source_fact_id"])
        target.setdefault("target_role", "fact-target")
    migrated.setdefault("source_alias_index", {})
    migrated.setdefault("source_alias_collisions", {})
    migrated.setdefault("source_concern_events", {})
    rebuild_indexes(migrated)
    return seal_graph(migrated)


def migrate_legacy_v2_family(graph: dict[str, Any]) -> dict[str, Any]:
    """Rename a verified Grill-era overlay without changing learning evidence."""

    migrated = copy.deepcopy(graph)
    migrated.pop("learning_graph_sha256", None)
    policy = empty_learning_graph()
    migrated["graph_family"] = policy["graph_family"]
    migrated["identity_policy"] = policy["identity_policy"]
    migrated["interop_policy"] = policy["interop_policy"]
    migrated["updated_at"] = utc_now()
    rebuild_indexes(migrated)
    return seal_graph(migrated)


def load_learning_graph(path: Path) -> dict[str, Any]:
    graph = load_json(path)
    version = graph.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(f"{path}: unsupported schema_version {version!r}")
    verify_seal(graph)
    if version == 1:
        return migrate_v1(graph)
    if graph.get("graph_family") == "danus-compatible-learning-overlay":
        return migrate_legacy_v2_family(graph)
    return graph


def resnapshot_source(source: dict[str, Any]) -> dict[str, Any]:
    source_kind = source.get("source_kind")
    if source_kind == "fact_graph":
        return snapshot_fact_source(source["source_root"])
    selection = source.get("selection", {})
    if source_kind == "paper_graph":
        return snapshot_paper_source(
            source["snapshot_dir"],
            source["snapshot_id"],
            include_planes=selection.get("include_planes"),
            current_audit_only=bool(selection.get("current_audit_only")),
            seed_ids=selection.get("seed_ids", []),
            radius=int(selection.get("radius", 1)),
        )
    if source_kind == "blackboard":
        return snapshot_blackboard_source(
            source["snapshot_dir"],
            source["snapshot_id"],
            include_node_types=selection.get("include_node_types", []),
            seed_ids=selection.get("seed_ids", []),
            radius=int(selection.get("radius", 1)),
        )
    raise ValueError(f"unsupported mounted source kind {source_kind!r}")


def verify_graph(graph: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if graph.get("graph_family") != "mathgraph-unified-nontruth-learning-plane":
        errors.append("invalid or missing graph_family")
    interop = graph.get("interop_policy", {})
    if interop.get("truth_inheritance") != "forbidden":
        errors.append("foreign truth inheritance must remain forbidden")
    if interop.get("writeback") != "forbidden":
        errors.append("source writeback must remain forbidden")

    for fingerprint, source in graph.get("sources", {}).items():
        if source.get("graph_fingerprint") != fingerprint:
            errors.append(f"source fingerprint key mismatch: {fingerprint}")
            continue
        try:
            fresh = resnapshot_source(source)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"source drift check failed for {fingerprint}: {exc}")
            continue
        if fresh.get("graph_fingerprint") != fingerprint:
            errors.append(
                f"mounted source drift for {fingerprint}: found "
                f"{fresh.get('graph_fingerprint')}"
            )

    for key, node in graph.get("nodes", {}).items():
        if key != node.get("node_hash") or not HEX64.fullmatch(key):
            errors.append(f"node key mismatch or invalid hash: {key}")
        identity_kind = node.get("identity_kind")
        if identity_kind == "pedagogical_content_sha256":
            content = node.get("pedagogical_content")
            if not isinstance(content, dict) or canonical_sha256(content) != key:
                errors.append(f"invalid pedagogical content hash under node {key}")
            if node.get("truth_status") != "pedagogical-not-a-fact":
                errors.append(f"pedagogical node has invalid truth status: {key}")
        elif identity_kind == "source_fact_artifact_sha256":
            if node.get("truth_status") != "admitted":
                errors.append(f"source fact has invalid truth status: {key}")
        elif identity_kind in FOREIGN_IDENTITY_KINDS:
            identity_payload = node.get("identity_payload")
            if not isinstance(identity_payload, dict) or canonical_sha256(identity_payload) != key:
                errors.append(f"invalid foreign binding hash under node {key}")
            source_object = node.get("source_object")
            if not isinstance(source_object, dict):
                errors.append(f"missing foreign source object under node {key}")
            elif isinstance(identity_payload, dict):
                if canonical_sha256(source_object) != identity_payload.get("object_sha256"):
                    errors.append(f"foreign source object drift under node {key}")
            if identity_kind == "paper_snapshot_object_binding_sha256":
                plane = node.get("source_metadata", {}).get("plane")
                if node.get("truth_status") != PAPER_TRUTH_STATUS.get(plane):
                    errors.append(f"paper anchor has invalid truth status: {key}")
            elif identity_kind == "blackboard_snapshot_node_binding_sha256" and node.get(
                "truth_status"
            ) != "exploration-nontruth":
                errors.append(f"Blackboard anchor has invalid truth status: {key}")
            elif identity_kind == "blackboard_boundary_stub_binding_sha256":
                if node.get("truth_status") != "omitted-boundary-nontruth":
                    errors.append(f"Blackboard boundary has invalid truth status: {key}")
                state = node.get("learning", {})
                if (
                    state.get("coverage") != "unseen"
                    or state.get("mastery") != 0
                    or state.get("status") != "untested"
                    or state.get("teaching_events")
                    or state.get("evidence")
                ):
                    errors.append(f"omitted boundary node carries learning evidence: {key}")
        else:
            errors.append(f"unsupported identity kind under node {key}")

        for source_ref in node.get("source_refs", []):
            if source_ref.get("graph_fingerprint") not in graph.get("sources", {}):
                errors.append(f"unknown mounted source under node {key}")
            if source_ref.get("source_kind") == "fact_graph":
                source_path = Path(source_ref["source_root"]) / source_ref["relative_path"]
                if not source_path.is_file():
                    errors.append(f"missing source fact: {source_path}")
                else:
                    actual = file_sha256(source_path)
                    if actual != source_ref.get("artifact_sha256") or actual != key:
                        errors.append(
                            f"stale source fact: {source_path}, expected {key}, found {actual}"
                        )
        state = node.get("learning", {})
        coverage = state.get("coverage", "unseen")
        if coverage not in COVERAGE:
            errors.append(f"invalid coverage {coverage!r} under node {key}")
        if state.get("status") not in STATUSES:
            errors.append(f"invalid mastery status under node {key}")
        mastery = state.get("mastery")
        if not isinstance(mastery, int) or not 0 <= mastery <= 5:
            errors.append(f"invalid mastery under node {key}")
        for event in state.get("evidence", []):
            recorded = event.get("evidence_sha256")
            payload = copy.deepcopy(event)
            payload.pop("evidence_sha256", None)
            if recorded != canonical_sha256(payload):
                errors.append(f"invalid evidence hash under node {key}")
        for event in state.get("teaching_events", []):
            recorded = event.get("teaching_event_sha256")
            payload = copy.deepcopy(event)
            payload.pop("teaching_event_sha256", None)
            if recorded != canonical_sha256(payload):
                errors.append(f"invalid teaching-event hash under node {key}")
            forbidden = {"mastery", "status", "error_class"} & set(event)
            if forbidden:
                errors.append(
                    f"teaching event changes testing fields under node {key}: "
                    f"{sorted(forbidden)}"
                )

    node_keys = set(graph.get("nodes", {}))
    opened_concerns: set[str] = set()
    for event_id, event in graph.get("source_concern_events", {}).items():
        payload = copy.deepcopy(event)
        recorded = payload.pop("concern_event_sha256", None)
        if event_id != recorded or canonical_sha256(payload) != event_id:
            errors.append(f"invalid source-concern event hash: {event_id}")
            continue
        if event.get("event_type") == "opened":
            opened_concerns.add(event_id)
            node = graph.get("nodes", {}).get(event.get("node_hash"))
            if node is None or node.get("identity_kind") not in SOURCE_IDENTITY_KINDS:
                errors.append(f"source concern has invalid anchor: {event_id}")
            if event.get("severity") not in {"minor", "material", "blocking"}:
                errors.append(f"source concern has invalid severity: {event_id}")
        elif event.get("event_type") == "resolved":
            if event.get("concern_id") not in graph.get("source_concern_events", {}):
                errors.append(f"source concern resolution has unknown concern: {event_id}")
            replacement = event.get("replacement_node_hash")
            if replacement is not None and replacement not in node_keys:
                errors.append(f"source concern resolution has unknown replacement: {event_id}")
        else:
            errors.append(f"source concern has invalid event type: {event_id}")
    edge_keys = set()
    for edge in graph.get("edges", []):
        if edge.get("from") not in node_keys or edge.get("to") not in node_keys:
            errors.append(f"dangling edge: {edge}")
        edge_keys.add((edge.get("from"), edge.get("to"), edge.get("relation")))
        source_edge = edge.get("source_edge")
        if source_edge is not None:
            if not isinstance(source_edge, dict) or canonical_sha256(source_edge) != edge.get(
                "source_edge_sha256"
            ):
                errors.append(f"invalid mounted source edge {edge.get('source_edge_id')}")

    for key, node in graph.get("nodes", {}).items():
        if node.get("identity_kind") != "pedagogical_content_sha256":
            continue
        content = node.get("pedagogical_content", {})
        kind = content.get("pedagogy_kind")
        relation = PEDAGOGY_KIND_TO_RELATION.get(kind)
        if relation is None:
            errors.append(f"unsupported pedagogical kind under node {key}")
            continue
        anchors = content.get("anchor_node_hashes")
        if anchors is None:
            anchors = content.get("anchor_fact_hashes", [])
        for anchor in anchors:
            anchor_node = graph.get("nodes", {}).get(anchor)
            if anchor_node is None:
                errors.append(f"missing pedagogical anchor {anchor} under node {key}")
            elif anchor_node.get("identity_kind") not in SOURCE_IDENTITY_KINDS:
                errors.append(f"non-source pedagogical anchor {anchor} under node {key}")
            if (key, anchor, relation) not in edge_keys:
                errors.append(
                    f"missing {relation} edge from pedagogical node {key} to {anchor}"
                )

    expected = copy.deepcopy(graph)
    expected.pop("learning_graph_sha256", None)
    rebuild_indexes(expected)
    for field in (
        "source_id_index",
        "source_alias_index",
        "source_alias_collisions",
        "short_id_collisions",
    ):
        if expected.get(field) != graph.get(field):
            errors.append(f"stale derived index: {field}")
    return errors


def cmd_init(args: argparse.Namespace) -> None:
    graph = empty_learning_graph()
    merge_snapshot(graph, snapshot_fact_source(args.source_root))
    atomic_write_json(Path(args.output), seal_graph(graph), refuse_exists=True)
    print_summary(graph)


def cmd_import(args: argparse.Namespace) -> None:
    path = Path(args.graph)
    graph = load_learning_graph(path)
    graph.pop("learning_graph_sha256", None)
    merge_snapshot(graph, snapshot_fact_source(args.source_root))
    atomic_write_json(path, seal_graph(graph), refuse_exists=False)
    print_summary(graph)


def mount_target(args: argparse.Namespace, snapshot: dict[str, Any]) -> None:
    if args.output:
        path = Path(args.output)
        graph = empty_learning_graph()
        refuse_exists = True
    else:
        path = Path(args.graph)
        graph = load_learning_graph(path)
        graph.pop("learning_graph_sha256", None)
        refuse_exists = False
    merge_snapshot(graph, snapshot)
    atomic_write_json(path, seal_graph(graph), refuse_exists=refuse_exists)
    print_summary(graph)


def cmd_mount_paper(args: argparse.Namespace) -> None:
    mount_target(
        args,
        snapshot_paper_source(
            args.source_root,
            args.snapshot_id,
            include_planes=args.include_plane,
            current_audit_only=args.current_audit_only,
            seed_ids=args.seed_object_id,
            radius=args.radius,
        ),
    )


def cmd_mount_blackboard(args: argparse.Namespace) -> None:
    mount_target(
        args,
        snapshot_blackboard_source(
            args.source_root,
            args.snapshot_id,
            include_node_types=args.include_node_type,
            seed_ids=args.seed_node_id,
            radius=args.radius,
        ),
    )


def resolve_node(graph: dict[str, Any], node_ref: str) -> tuple[str, dict[str, Any]]:
    normalized = node_ref.lower()
    if HEX64.fullmatch(normalized) and normalized in graph["nodes"]:
        return normalized, graph["nodes"][normalized]
    matches = graph.get("source_alias_index", {}).get(node_ref, [])
    if len(matches) == 1:
        node_hash = matches[0]
        return node_hash, graph["nodes"][node_hash]
    if len(matches) > 1:
        raise ValueError(f"ambiguous source alias {node_ref!r}: {matches}")
    raise ValueError(f"unknown learning node or source alias {node_ref!r}")


def require_source_anchor(
    graph: dict[str, Any], node_ref: str
) -> tuple[str, dict[str, Any]]:
    node_hash, node = resolve_node(graph, node_ref)
    if node.get("identity_kind") not in SOURCE_IDENTITY_KINDS:
        raise ValueError(f"{node_ref!r} identifies pedagogy, not a source anchor")
    return node_hash, node


def require_learnable_node(
    graph: dict[str, Any], node_ref: str
) -> tuple[str, dict[str, Any]]:
    node_hash, node = resolve_node(graph, node_ref)
    if node.get("identity_kind") == "blackboard_boundary_stub_binding_sha256":
        raise ValueError(
            f"{node_ref!r} is an omitted boundary stub with no teachable payload"
        )
    return node_hash, node


def selected_node_arg(args: argparse.Namespace) -> str:
    return args.node if getattr(args, "node", None) else args.fact_hash


def active_source_concerns(
    graph: dict[str, Any], node_hash: str | None = None
) -> list[tuple[str, dict[str, Any]]]:
    events = graph.get("source_concern_events", {})
    resolved = {
        event.get("concern_id")
        for event in events.values()
        if event.get("event_type") == "resolved"
    }
    return [
        (event_id, event)
        for event_id, event in events.items()
        if event.get("event_type") == "opened"
        and event_id not in resolved
        and (node_hash is None or event.get("node_hash") == node_hash)
    ]


def warn_or_block_on_source_concern(
    graph: dict[str, Any], node_hash: str, *, operation: str
) -> None:
    active = active_source_concerns(graph, node_hash)
    blocking = [event_id for event_id, event in active if event.get("severity") == "blocking"]
    if blocking and operation == "teach":
        raise ValueError(
            f"source anchor has unresolved blocking concerns {blocking}; mount a "
            "corrected snapshot or resolve the concern before teaching from it"
        )
    notable = [
        event_id
        for event_id, event in active
        if event.get("severity") in {"material", "blocking"}
    ]
    if notable:
        print(
            f"warning: {operation} concerns understanding, not source validity; "
            f"active source concerns={notable}",
            file=sys.stderr,
        )


def cmd_teach(args: argparse.Namespace) -> None:
    path = Path(args.graph)
    graph = load_learning_graph(path)
    graph.pop("learning_graph_sha256", None)
    node_hash, node = require_learnable_node(graph, selected_node_arg(args))
    if (
        node.get("source_metadata", {}).get("audit_state") == "inactive"
        and not getattr(args, "allow_inactive_source", False)
    ):
        raise ValueError(
            "inactive historical Audit node requires --allow-inactive-source; "
            "prefer its current superseding node for ordinary teaching"
        )
    warn_or_block_on_source_concern(graph, node_hash, operation="teach")
    if args.coverage not in COVERAGE:
        raise ValueError(f"unsupported coverage {args.coverage!r}")
    event = {
        "recorded_at": utc_now(),
        "coverage": args.coverage,
        "note": args.note,
        "source_locator": args.source_locator,
    }
    event["teaching_event_sha256"] = canonical_sha256(event)
    state = node["learning"]
    state.setdefault("teaching_events", []).append(event)
    state["coverage"] = args.coverage
    state["last_taught_at"] = event["recorded_at"]
    graph["updated_at"] = utc_now()
    atomic_write_json(path, seal_graph(graph), refuse_exists=False)
    print(json.dumps({"node_hash": node_hash, "teaching_event_sha256": event["teaching_event_sha256"]}))


def cmd_add_teaching_node(args: argparse.Namespace) -> None:
    path = Path(args.graph)
    graph = load_learning_graph(path)
    graph.pop("learning_graph_sha256", None)
    title = args.title.strip()
    summary = args.summary.strip()
    if not title or not summary:
        raise ValueError("title and summary must be nonempty")
    raw_anchors = list(args.anchor_node or []) + list(args.anchor_fact_hash or [])
    if not raw_anchors:
        raise ValueError("at least one --anchor-node is required")
    anchor_hashes = sorted(
        {require_source_anchor(graph, node_ref)[0] for node_ref in raw_anchors}
    )
    content = {
        "pedagogy_kind": args.kind,
        "title": title,
        "summary": summary,
        "source_locator": args.source_locator,
        "anchor_node_hashes": anchor_hashes,
    }
    node_hash = canonical_sha256(content)
    existing = graph["nodes"].get(node_hash)
    if existing is not None:
        if (
            existing.get("identity_kind") != "pedagogical_content_sha256"
            or existing.get("pedagogical_content") != content
        ):
            raise ValueError(f"content hash collision at {node_hash}")
        print(node_hash)
        return

    recorded_at = utc_now()
    teaching_event = {
        "recorded_at": recorded_at,
        "coverage": "taught-unchecked",
        "note": summary,
        "source_locator": args.source_locator,
    }
    teaching_event["teaching_event_sha256"] = canonical_sha256(teaching_event)
    state = learning_state()
    state["coverage"] = "taught-unchecked"
    state["last_taught_at"] = recorded_at
    state["teaching_events"].append(teaching_event)
    graph["nodes"][node_hash] = {
        "node_hash": node_hash,
        "identity_kind": "pedagogical_content_sha256",
        "anchor_kind": "pedagogical",
        "pedagogical_content": content,
        "source_fact_ids": [],
        "source_object_ids": [],
        "source_refs": [],
        "statement_preview": title,
        "truth_status": "pedagogical-not-a-fact",
        "created_at": recorded_at,
        "learning": state,
    }
    relation = PEDAGOGY_KIND_TO_RELATION[args.kind]
    for anchor_hash in anchor_hashes:
        graph["edges"].append(
            {
                "from": node_hash,
                "to": anchor_hash,
                "relation": relation,
                "source_kind": "pedagogical",
                "source_graph": None,
            }
        )
    rebuild_indexes(graph)
    graph["updated_at"] = recorded_at
    atomic_write_json(path, seal_graph(graph), refuse_exists=False)
    print(node_hash)


def cmd_record(args: argparse.Namespace) -> None:
    path = Path(args.graph)
    graph = load_learning_graph(path)
    graph.pop("learning_graph_sha256", None)
    node_hash, node = require_learnable_node(graph, selected_node_arg(args))
    warn_or_block_on_source_concern(graph, node_hash, operation="record-mastery")
    if args.status not in STATUSES:
        raise ValueError(f"unsupported status {args.status!r}")
    event = {
        "recorded_at": utc_now(),
        "mastery": args.mastery,
        "status": args.status,
        "hint_level": args.hint_level,
        "error_class": args.error_class,
        "evidence": args.evidence,
        "due_review": args.due_review,
        "mode": "testing",
    }
    event["evidence_sha256"] = canonical_sha256(event)
    state = node["learning"]
    state["mastery"] = args.mastery
    state["status"] = args.status
    state["last_evidence_at"] = event["recorded_at"]
    state["next_due_review"] = args.due_review
    state["evidence"].append(event)
    graph["updated_at"] = utc_now()
    atomic_write_json(path, seal_graph(graph), refuse_exists=False)
    print(json.dumps({"node_hash": node_hash, "evidence_sha256": event["evidence_sha256"]}))


def cmd_record_source_concern(args: argparse.Namespace) -> None:
    path = Path(args.graph)
    graph = load_learning_graph(path)
    graph.pop("learning_graph_sha256", None)
    node_hash, _ = require_source_anchor(graph, args.node)
    description = args.description.strip()
    if not description:
        raise ValueError("source concern description must be nonempty")
    event = {
        "event_type": "opened",
        "recorded_at": utc_now(),
        "node_hash": node_hash,
        "concern_kind": args.kind,
        "severity": args.severity,
        "description": description,
        "truth_effect": "none",
        "source_writeback": "none",
    }
    event_id = canonical_sha256(event)
    event["concern_event_sha256"] = event_id
    graph.setdefault("source_concern_events", {})[event_id] = event
    graph["updated_at"] = utc_now()
    atomic_write_json(path, seal_graph(graph), refuse_exists=False)
    print(event_id)


def cmd_resolve_source_concern(args: argparse.Namespace) -> None:
    path = Path(args.graph)
    graph = load_learning_graph(path)
    graph.pop("learning_graph_sha256", None)
    concern = graph.get("source_concern_events", {}).get(args.concern_id)
    if concern is None or concern.get("event_type") != "opened":
        raise ValueError(f"unknown opened source concern {args.concern_id!r}")
    if not any(
        event.get("event_type") == "resolved"
        and event.get("concern_id") == args.concern_id
        for event in graph.get("source_concern_events", {}).values()
    ):
        replacement_hash = None
        if args.replacement_node:
            replacement_hash, _ = require_source_anchor(graph, args.replacement_node)
        if args.resolution in {"superseded-snapshot", "corrected-source"} and replacement_hash is None:
            raise ValueError(
                f"resolution {args.resolution!r} requires --replacement-node"
            )
        note = args.note.strip()
        if not note:
            raise ValueError("resolution note must be nonempty")
        event = {
            "event_type": "resolved",
            "recorded_at": utc_now(),
            "concern_id": args.concern_id,
            "resolution_kind": args.resolution,
            "note": note,
            "replacement_node_hash": replacement_hash,
            "external_receipt": args.external_receipt,
            "truth_effect": "none",
            "source_writeback": "none",
        }
        event_id = canonical_sha256(event)
        event["concern_event_sha256"] = event_id
        graph["source_concern_events"][event_id] = event
        graph["updated_at"] = utc_now()
        atomic_write_json(path, seal_graph(graph), refuse_exists=False)
        print(event_id)
        return
    raise ValueError(f"source concern {args.concern_id!r} is already resolved")


def context_subgraph(
    graph: dict[str, Any], root_hash: str, *, radius: int, max_nodes: int
) -> dict[str, Any]:
    if radius < 0:
        raise ValueError("radius must be nonnegative")
    if max_nodes < 1:
        raise ValueError("max_nodes must be positive")
    adjacency: dict[str, set[str]] = {node_hash: set() for node_hash in graph["nodes"]}
    for edge in graph["edges"]:
        adjacency[edge["from"]].add(edge["to"])
        adjacency[edge["to"]].add(edge["from"])
    distances = {root_hash: 0}
    queue = deque([root_hash])
    while queue:
        node_hash = queue.popleft()
        if distances[node_hash] >= radius:
            continue
        for neighbor in sorted(adjacency[node_hash]):
            if neighbor not in distances:
                distances[neighbor] = distances[node_hash] + 1
                queue.append(neighbor)
    ordered = sorted(distances, key=lambda key: (distances[key], key))
    chosen = ordered[:max_nodes]
    chosen_set = set(chosen)
    edges = [
        edge
        for edge in graph["edges"]
        if edge["from"] in chosen_set and edge["to"] in chosen_set
    ]
    return {
        "root_node_hash": root_hash,
        "radius": radius,
        "max_nodes": max_nodes,
        "nodes": {node_hash: graph["nodes"][node_hash] for node_hash in chosen},
        "edges": edges,
        "omission_receipt": {
            "reachable_node_count": len(ordered),
            "returned_node_count": len(chosen),
            "omitted_node_count": len(ordered) - len(chosen),
            "truncated": len(ordered) > len(chosen),
        },
    }


def cmd_context(args: argparse.Namespace) -> None:
    graph = load_learning_graph(Path(args.graph))
    node_hash, _ = resolve_node(graph, args.node)
    print(
        json.dumps(
            context_subgraph(
                graph, node_hash, radius=args.radius, max_nodes=args.max_nodes
            ),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )


def cmd_verify(args: argparse.Namespace) -> None:
    graph = load_learning_graph(Path(args.graph))
    errors = verify_graph(graph)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        raise SystemExit(1)
    print(
        f"ok nodes={len(graph['nodes'])} edges={len(graph['edges'])} "
        f"sources={len(graph['sources'])}"
    )


def print_summary(graph: dict[str, Any]) -> None:
    mastery_counts: dict[str, int] = {}
    coverage_counts: dict[str, int] = {}
    identity_counts: dict[str, int] = {}
    source_kind_counts: dict[str, int] = {}
    truth_status_counts: dict[str, int] = {}
    for source in graph["sources"].values():
        kind = source.get("source_kind", "unknown")
        source_kind_counts[kind] = source_kind_counts.get(kind, 0) + 1
    for node in graph["nodes"].values():
        score = str(node["learning"]["mastery"])
        mastery_counts[score] = mastery_counts.get(score, 0) + 1
        coverage = node["learning"].get("coverage", "unseen")
        coverage_counts[coverage] = coverage_counts.get(coverage, 0) + 1
        identity_kind = node.get("identity_kind", "unknown")
        identity_counts[identity_kind] = identity_counts.get(identity_kind, 0) + 1
        truth_status = node.get("truth_status", "unknown")
        truth_status_counts[truth_status] = truth_status_counts.get(truth_status, 0) + 1
    print(
        json.dumps(
            {
                "schema_version": graph.get("schema_version"),
                "graph_family": graph.get("graph_family"),
                "sources": len(graph["sources"]),
                "source_kind_counts": source_kind_counts,
                "nodes": len(graph["nodes"]),
                "edges": len(graph["edges"]),
                "targets": len(graph["targets"]),
                "active_source_concerns": len(active_source_concerns(graph)),
                "source_alias_collisions": len(graph.get("source_alias_collisions", {})),
                "short_id_collisions": len(graph["short_id_collisions"]),
                "mastery_counts": mastery_counts,
                "coverage_counts": coverage_counts,
                "identity_counts": identity_counts,
                "truth_status_counts": truth_status_counts,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def cmd_summary(args: argparse.Namespace) -> None:
    print_summary(load_learning_graph(Path(args.graph)))


def add_mount_destination(parser: argparse.ArgumentParser) -> None:
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--output", help="create a new learning overlay")
    destination.add_argument("--graph", help="mount into an existing learning overlay")


def add_learning_node_selector(parser: argparse.ArgumentParser) -> None:
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument(
        "--node", help="learning node hash or an unambiguous source object alias"
    )
    selector.add_argument(
        "--fact-hash",
        help="legacy alias for --node; retained for existing Fact Graph workflows",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create the unified lightweight nontruth learning plane, binding frozen "
            "Fact, Paper, and Blackboard artifacts without inheriting truth or "
            "invoking a research runtime."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="create from a frozen Fact Graph (legacy Danus-compatible inputs accepted)",
    )
    init_parser.add_argument(
        "--source-root",
        required=True,
        help="source project root or its fact_graph directory",
    )
    init_parser.add_argument("--output", required=True)
    init_parser.set_defaults(func=cmd_init)

    import_parser = subparsers.add_parser(
        "import",
        help="add another frozen Fact Graph (legacy Danus-compatible inputs accepted)",
    )
    import_parser.add_argument(
        "--source-root",
        required=True,
        help="source project root or its fact_graph directory",
    )
    import_parser.add_argument("--graph", required=True)
    import_parser.set_defaults(func=cmd_import)

    paper_parser = subparsers.add_parser(
        "mount-paper", help="read-only mount of an immutable Chalxius pls snapshot"
    )
    paper_parser.add_argument("--source-root", required=True)
    paper_parser.add_argument("--snapshot-id", required=True)
    add_mount_destination(paper_parser)
    paper_parser.add_argument(
        "--include-plane",
        action="append",
        choices=sorted(PAPER_PLANES),
        help="repeat to mount selected planes; default is all three",
    )
    paper_parser.add_argument("--current-audit-only", action="store_true")
    paper_parser.add_argument("--seed-object-id", action="append", default=[])
    paper_parser.add_argument("--radius", type=int, default=1)
    paper_parser.set_defaults(func=cmd_mount_paper)

    blackboard_parser = subparsers.add_parser(
        "mount-blackboard", help="read-only mount of an immutable Chalxius bbs snapshot"
    )
    blackboard_parser.add_argument("--source-root", required=True)
    blackboard_parser.add_argument("--snapshot-id", required=True)
    add_mount_destination(blackboard_parser)
    blackboard_parser.add_argument("--include-node-type", action="append", default=[])
    blackboard_parser.add_argument("--seed-node-id", action="append", default=[])
    blackboard_parser.add_argument("--radius", type=int, default=1)
    blackboard_parser.set_defaults(func=cmd_mount_blackboard)

    teach_parser = subparsers.add_parser(
        "teach", help="record coverage only; never changes testing mastery"
    )
    teach_parser.add_argument("--graph", required=True)
    add_learning_node_selector(teach_parser)
    teach_parser.add_argument(
        "--coverage", required=True, choices=sorted(COVERAGE - {"unseen"})
    )
    teach_parser.add_argument("--note", required=True)
    teach_parser.add_argument("--source-locator")
    teach_parser.add_argument(
        "--allow-inactive-source",
        action="store_true",
        help="explicitly teach an inactive historical Audit node as history",
    )
    teach_parser.set_defaults(func=cmd_teach)

    teaching_node_parser = subparsers.add_parser(
        "add-teaching-node",
        help="add lightweight pedagogy linked to one or more source anchors",
    )
    teaching_node_parser.add_argument("--graph", required=True)
    teaching_node_parser.add_argument(
        "--kind", required=True, choices=sorted(PEDAGOGY_KIND_TO_RELATION)
    )
    teaching_node_parser.add_argument("--title", required=True)
    teaching_node_parser.add_argument("--summary", required=True)
    teaching_node_parser.add_argument("--source-locator")
    teaching_node_parser.add_argument(
        "--anchor-node",
        action="append",
        help="repeat for Fact, Paper, or Blackboard source anchors",
    )
    teaching_node_parser.add_argument(
        "--anchor-fact-hash",
        action="append",
        help="legacy alias for --anchor-node",
    )
    teaching_node_parser.set_defaults(func=cmd_add_teaching_node)

    record_parser = subparsers.add_parser(
        "record", help="record evidence from an explicitly declared testing turn"
    )
    record_parser.add_argument("--graph", required=True)
    add_learning_node_selector(record_parser)
    record_parser.add_argument("--mastery", required=True, type=int, choices=range(6))
    record_parser.add_argument("--status", required=True, choices=sorted(STATUSES))
    record_parser.add_argument("--evidence", required=True)
    record_parser.add_argument("--hint-level", type=int, choices=range(5), default=0)
    record_parser.add_argument("--error-class")
    record_parser.add_argument("--due-review")
    record_parser.set_defaults(func=cmd_record)

    concern_parser = subparsers.add_parser(
        "record-source-concern",
        help="record a lightweight concern without repairing or writing to the source graph",
    )
    concern_parser.add_argument("--graph", required=True)
    concern_parser.add_argument("--node", required=True)
    concern_parser.add_argument(
        "--kind",
        required=True,
        choices=[
            "misread",
            "misconstructed-node",
            "misconstructed-edge",
            "scope-error",
            "unsupported-inference",
            "source-drift",
            "omitted-context",
            "other",
        ],
    )
    concern_parser.add_argument(
        "--severity", required=True, choices=["minor", "material", "blocking"]
    )
    concern_parser.add_argument("--description", required=True)
    concern_parser.set_defaults(func=cmd_record_source_concern)

    resolve_parser = subparsers.add_parser(
        "resolve-source-concern",
        help="close a concern after a separate source-graph decision or replacement mount",
    )
    resolve_parser.add_argument("--graph", required=True)
    resolve_parser.add_argument("--concern-id", required=True)
    resolve_parser.add_argument(
        "--resolution",
        required=True,
        choices=[
            "superseded-snapshot",
            "corrected-source",
            "dismissed-after-review",
            "accepted-limitation",
        ],
    )
    resolve_parser.add_argument("--note", required=True)
    resolve_parser.add_argument("--replacement-node")
    resolve_parser.add_argument("--external-receipt")
    resolve_parser.set_defaults(func=cmd_resolve_source_concern)

    context_parser = subparsers.add_parser(
        "context", help="print a bounded neighborhood for teaching or planning"
    )
    context_parser.add_argument("--graph", required=True)
    context_parser.add_argument("--node", required=True)
    context_parser.add_argument("--radius", type=int, default=1)
    context_parser.add_argument("--max-nodes", type=int, default=100)
    context_parser.set_defaults(func=cmd_context)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--graph", required=True)
    verify_parser.set_defaults(func=cmd_verify)

    summary_parser = subparsers.add_parser("summary")
    summary_parser.add_argument("--graph", required=True)
    summary_parser.set_defaults(func=cmd_summary)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
