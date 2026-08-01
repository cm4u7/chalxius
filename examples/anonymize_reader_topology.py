#!/usr/bin/env python3
"""Export a content-free Reader topology from a private Chalxius project.

The output keeps graph shape and a small allowlist of structural enums. Every
source identifier and every content-bearing Reader field is replaced by an
HMAC-SHA-256 value. With the default ephemeral key, the public identifiers
cannot be correlated with the private identifiers after this process exits.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


HEX64 = set("0123456789abcdef")
NAMESPACE = b"chalxius-public-topology-v1\0"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def is_hex64(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX64


def read_json(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"input must be a regular, non-symlink file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"input must be a regular, non-symlink file: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL row {line_number} is not an object: {path}")
        rows.append(value)
    return rows


def load_key(path: Path | None) -> tuple[bytes, str]:
    if path is None:
        return secrets.token_bytes(32), "ephemeral_discarded"
    if path.is_symlink() or not path.is_file():
        raise ValueError("--key-file must be a regular, non-symlink file")
    raw = path.read_bytes().strip()
    try:
        decoded = bytes.fromhex(raw.decode("ascii"))
    except (UnicodeDecodeError, ValueError):
        decoded = raw
    if len(decoded) < 32:
        raise ValueError("--key-file must contain at least 32 secret bytes")
    return decoded, "private_key_file"


class Anonymizer:
    def __init__(self, key: bytes) -> None:
        self.key = key
        self.node_keys: dict[str, str] = {}
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.edge_signatures: set[tuple[str, str, str]] = set()

    def opaque(self, kind: str, source_identifier: str) -> str:
        message = NAMESPACE + kind.encode("utf-8") + b"\0" + source_identifier.encode("utf-8")
        return hmac.new(self.key, message, hashlib.sha256).hexdigest()

    def add_node(
        self,
        *,
        source_key: str,
        plane: str,
        role: str,
        visual_status: str,
        layer: str,
        theme_id: str,
    ) -> str:
        if source_key in self.node_keys:
            return self.node_keys[source_key]
        node_id = self.opaque("node-id", source_key)
        content_hash = self.opaque("node-content", source_key)
        object_hash = self.opaque("node-object", source_key)
        snapshot_hash = self.opaque("node-snapshot", source_key)
        truth_status = {
            "fact": "historical_inactive",
            "paper": "historical_inactive",
            "audit": "historical_inactive",
            "blackboard": "historical_inactive",
            "learning": "historical_inactive",
            "reader": "reader_note",
        }[plane]
        source_status = (
            "presentation_only_anonymized"
            if plane == "reader"
            else "historical_anonymized"
        )
        node = {
            "id": node_id,
            "title": content_hash,
            "reader_role": role,
            "plane": plane,
            "visual_status": visual_status,
            "layer": layer,
            "theme_id": theme_id,
            "summary": content_hash,
            "intuition": content_hash,
            "importance": content_hash,
            "reasoning": content_hash,
            "prerequisites": [],
            "formal": {
                "hypotheses": [content_hash],
                "statement": content_hash,
                "proof": content_hash,
                "relations": [content_hash],
                "original_text": content_hash,
            },
            "provenance": {
                "source_plane": plane,
                "source_status": source_status,
                "truth_status": truth_status,
                "object_id": object_hash,
                "snapshot_id": snapshot_hash,
                "locator": self.opaque("node-locator", source_key),
                "object_sha256": object_hash,
                "original_text_sha256": sha256_text(content_hash),
                "replaces": [],
            },
        }
        self.node_keys[source_key] = node_id
        self.nodes.append(node)
        return node_id

    def add_edge(
        self,
        *,
        source_key: str,
        target_key: str,
        category: str,
        source_edge_key: str,
        weak: bool = False,
        layer: str = "knowledge",
    ) -> None:
        if source_key not in self.node_keys or target_key not in self.node_keys:
            return
        source = self.node_keys[source_key]
        target = self.node_keys[target_key]
        signature = (source, target, category)
        if source == target or signature in self.edge_signatures:
            return
        self.edge_signatures.add(signature)
        edge_id = self.opaque("edge-id", source_edge_key)
        relation_hash = self.opaque("edge-content", source_edge_key)
        object_hash = self.opaque("edge-object", source_edge_key)
        self.edges.append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "category": category,
                "relation": relation_hash,
                "exact_type": relation_hash,
                "weak": weak,
                "layer": layer,
                "provenance": {
                    "source_plane": "reader",
                    "source_status": "presentation_only_anonymized",
                    "truth_status": "reader_note",
                    "object_id": object_hash,
                    "snapshot_id": self.opaque("edge-snapshot", source_edge_key),
                    "locator": self.opaque("edge-locator", source_edge_key),
                    "object_sha256": object_hash,
                    "original_text_sha256": sha256_text(relation_hash),
                    "replaces": [],
                },
            }
        )


def private_packet_strings(packet: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for key in ("project_id", "title", "audience"):
        value = packet.get(key)
        if isinstance(value, str) and len(value) >= 8:
            values.add(value)
    for section_name in ("source_snapshot", "presentation", "audit"):
        section = packet.get(section_name, {})
        if isinstance(section, dict):
            for value in section.values():
                if isinstance(value, str) and len(value) >= 12:
                    values.add(value)
                elif isinstance(value, list):
                    values.update(item for item in value if isinstance(item, str) and len(item) >= 12)
    for theme in packet.get("themes", []):
        for key in ("id", "label", "description"):
            value = theme.get(key)
            if isinstance(value, str) and len(value) >= 8:
                values.add(value)
    for node in packet.get("nodes", []):
        for key in ("id", "title", "summary", "intuition", "importance", "reasoning"):
            value = node.get(key)
            if isinstance(value, str) and len(value) >= 8:
                values.add(value)
        formal = node.get("formal", {})
        if isinstance(formal, dict):
            for value in formal.values():
                if isinstance(value, str) and len(value) >= 12:
                    values.add(value)
                elif isinstance(value, list):
                    values.update(item for item in value if isinstance(item, str) and len(item) >= 12)
        provenance = node.get("provenance", {})
        if isinstance(provenance, dict):
            for key in ("object_id", "snapshot_id", "locator"):
                value = provenance.get(key)
                if isinstance(value, str) and len(value) >= 8:
                    values.add(value)
    for edge in packet.get("edges", []):
        for key in ("id", "relation", "exact_type"):
            value = edge.get(key)
            if isinstance(value, str) and len(value) >= 8:
                values.add(value)
    return values


def first_known_theme(
    candidates: Iterable[str | None],
    *,
    fact_themes: dict[str, str],
    memory_themes: dict[str, str],
) -> str | None:
    for candidate in candidates:
        if not candidate:
            continue
        if candidate in fact_themes:
            return fact_themes[candidate]
        if candidate in memory_themes:
            return memory_themes[candidate]
    return None


def finish_prerequisites(packet: dict[str, Any]) -> None:
    incoming: dict[str, list[str]] = {node["id"]: [] for node in packet["nodes"]}
    for edge in packet["edges"]:
        if edge["category"] == "prerequisite":
            incoming[edge["target"]].append(edge["source"])
    for node in packet["nodes"]:
        node["prerequisites"] = incoming[node["id"]]

    def ancestors(target: str) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()

        def visit(node_id: str) -> None:
            for predecessor in incoming[node_id]:
                visit(predecessor)
                if predecessor not in seen:
                    seen.add(predecessor)
                    ordered.append(predecessor)

        visit(target)
        return ordered

    packet["prerequisite_order"] = {
        target: ancestors(target) for target in packet["target_order"]
    }


def assert_public_packet(
    packet: dict[str, Any],
    *,
    private_strings: set[str],
    forbidden: list[str],
) -> None:
    for node in packet["nodes"]:
        hash_fields = [
            node["id"],
            node["title"],
            node["summary"],
            node["intuition"],
            node["importance"],
            node["reasoning"],
            *node["formal"]["hypotheses"],
            node["formal"]["statement"],
            node["formal"]["proof"],
            *node["formal"]["relations"],
            node["formal"]["original_text"],
            node["provenance"]["object_id"],
            node["provenance"]["snapshot_id"],
            node["provenance"]["locator"],
            node["provenance"]["object_sha256"],
            node["provenance"]["original_text_sha256"],
        ]
        if not all(is_hex64(value) for value in hash_fields):
            raise RuntimeError("public node contains a non-hash content field")
    for edge in packet["edges"]:
        hash_fields = [
            edge["id"],
            edge["source"],
            edge["target"],
            edge["relation"],
            edge["exact_type"],
            edge["provenance"]["object_id"],
            edge["provenance"]["snapshot_id"],
            edge["provenance"]["locator"],
            edge["provenance"]["object_sha256"],
            edge["provenance"]["original_text_sha256"],
        ]
        if not all(is_hex64(value) for value in hash_fields):
            raise RuntimeError("public edge contains a non-hash content field")
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    folded = serialized.casefold()
    leaked = sorted(value for value in private_strings if value and value in serialized)
    if leaked:
        raise RuntimeError(f"private source values survived anonymization: {len(leaked)}")
    matched_forbidden = [value for value in forbidden if value.casefold() in folded]
    if matched_forbidden:
        raise RuntimeError("a caller-supplied forbidden marker survived anonymization")


def build_packet(
    *,
    source_packet: dict[str, Any],
    project_root: Path,
    anonymizer: Anonymizer,
) -> dict[str, Any]:
    raw_themes = {theme["id"]: theme for theme in source_packet["themes"]}
    raw_theme_order = list(source_packet["theme_order"])
    public_theme_ids = {
        theme_id: "theme-" + anonymizer.opaque("theme-id", theme_id)[:32]
        for theme_id in raw_theme_order
    }
    if not public_theme_ids:
        raise ValueError("source packet has no themes")

    source_node_keys: dict[str, str] = {}
    fact_node_keys: dict[str, str] = {}
    fact_themes: dict[str, str] = {}
    for index, raw in enumerate(source_packet["nodes"]):
        raw_id = raw["id"]
        source_key = f"source-node:{index}:{raw_id}"
        source_node_keys[raw_id] = source_key
        plane = raw["plane"]
        if plane == "fact":
            fact_node_keys[raw_id] = source_key
            fact_themes[raw_id] = public_theme_ids[raw["theme_id"]]
        anonymizer.add_node(
            source_key=source_key,
            plane=plane,
            role=raw["reader_role"],
            visual_status=raw["visual_status"],
            layer=raw["layer"],
            theme_id=public_theme_ids[raw["theme_id"]],
        )

    for index, raw in enumerate(source_packet["edges"]):
        anonymizer.add_edge(
            source_key=source_node_keys[raw["source"]],
            target_key=source_node_keys[raw["target"]],
            category=raw["category"],
            source_edge_key=f"source-edge:{index}:{raw['id']}",
            weak=raw["weak"],
            layer=raw["layer"],
        )

    theme_ids = [public_theme_ids[item] for item in raw_theme_order]

    def fallback_theme(source_key: str) -> str:
        bucket = int(anonymizer.opaque("theme-bucket", source_key)[:8], 16)
        return theme_ids[bucket % len(theme_ids)]

    memory_path = project_root / "memory" / "global.jsonl"
    memory_rows = read_jsonl(memory_path) if memory_path.exists() else []
    memory_event_keys: dict[str, list[str]] = defaultdict(list)
    memory_themes: dict[str, str] = {}
    research_rows: list[tuple[dict[str, Any], str]] = []
    for index, row in enumerate(memory_rows):
        event_id = str(row.get("event_id") or f"row-{index}")
        stable_id = str(row.get("id") or event_id)
        source_key = f"research-event:{index}:{event_id}"
        candidates = [
            row.get("related_fact_id"),
            row.get("resolution_fact_id"),
            *(row.get("dependencies") or []),
        ]
        theme_id = first_known_theme(
            (str(value) if value is not None else None for value in candidates),
            fact_themes=fact_themes,
            memory_themes=memory_themes,
        ) or fallback_theme(source_key)
        anonymizer.add_node(
            source_key=source_key,
            plane="blackboard",
            role="explanation",
            visual_status="research",
            layer="knowledge",
            theme_id=theme_id,
        )
        if memory_event_keys[stable_id]:
            previous = memory_event_keys[stable_id][-1]
            anonymizer.add_edge(
                source_key=previous,
                target_key=source_key,
                category="repair",
                source_edge_key=f"memory-transition:{stable_id}:{index}",
            )
        memory_event_keys[stable_id].append(source_key)
        memory_themes[stable_id] = theme_id
        research_rows.append((row, source_key))

    for index, (row, target_key) in enumerate(research_rows):
        references: list[tuple[str, str]] = []
        for dependency in row.get("dependencies") or []:
            references.append((str(dependency), "support"))
        for field, category in (
            ("parent_memory_id", "support"),
            ("trigger_memory_id", "support"),
            ("repair_of_memory_id", "repair"),
            ("related_fact_id", "support"),
            ("resolution_fact_id", "repair"),
        ):
            value = row.get(field)
            if value:
                references.append((str(value), category))
        for reference_index, (reference, category) in enumerate(references):
            source_key = fact_node_keys.get(reference)
            if source_key is None and memory_event_keys.get(reference):
                source_key = memory_event_keys[reference][-1]
            if source_key is not None:
                anonymizer.add_edge(
                    source_key=source_key,
                    target_key=target_key,
                    category=category,
                    source_edge_key=f"memory-reference:{index}:{reference_index}",
                )

    round_keys: dict[str, str] = {}
    assignment_rounds: dict[str, str] = {}
    assignment_memories: dict[str, str] = {}
    for index, path in enumerate(sorted((project_root / "rounds").glob("*/round.json"))):
        value = read_json(path)
        round_id = str(value.get("round_id") or path.parent.name)
        source_key = f"round:{index}:{round_id}"
        assignments = value.get("assignments") or []
        candidate_memories = [str(item.get("memory_id")) for item in assignments if item.get("memory_id")]
        theme_id = first_known_theme(
            candidate_memories,
            fact_themes=fact_themes,
            memory_themes=memory_themes,
        ) or fallback_theme(source_key)
        anonymizer.add_node(
            source_key=source_key,
            plane="blackboard",
            role="definition",
            visual_status="research",
            layer="knowledge",
            theme_id=theme_id,
        )
        round_keys[round_id] = source_key
        for assignment_index, assignment in enumerate(assignments):
            assignment_id = assignment.get("assignment_id")
            if assignment_id:
                assignment_rounds[str(assignment_id)] = source_key
            memory_id = assignment.get("memory_id")
            if assignment_id and memory_id:
                assignment_memories[str(assignment_id)] = str(memory_id)
            if memory_id and memory_event_keys.get(str(memory_id)):
                anonymizer.add_edge(
                    source_key=memory_event_keys[str(memory_id)][-1],
                    target_key=source_key,
                    category="support",
                    source_edge_key=f"round-memory:{index}:{assignment_index}",
                )

    return_keys: dict[str, str] = {}
    for index, path in enumerate(sorted((project_root / "rounds").glob("*/returns/*.json"))):
        value = read_json(path)
        assignment_id = str(value.get("assignment_id") or f"return-{index}")
        round_id = str(value.get("round_id") or path.parents[1].name)
        source_key = f"return:{index}:{assignment_id}"
        memory_id = str(value.get("memory_id") or assignment_memories.get(assignment_id) or "")
        candidate_refs = [memory_id, *(str(item) for item in (value.get("predecessors") or []))]
        theme_id = first_known_theme(
            candidate_refs,
            fact_themes=fact_themes,
            memory_themes=memory_themes,
        ) or fallback_theme(source_key)
        anonymizer.add_node(
            source_key=source_key,
            plane="blackboard",
            role="result",
            visual_status="research",
            layer="knowledge",
            theme_id=theme_id,
        )
        return_keys[assignment_id] = source_key
        if round_id in round_keys:
            anonymizer.add_edge(
                source_key=round_keys[round_id],
                target_key=source_key,
                category="support",
                source_edge_key=f"round-return:{index}",
            )
        if memory_id in memory_event_keys:
            anonymizer.add_edge(
                source_key=memory_event_keys[memory_id][-1],
                target_key=source_key,
                category="support",
                source_edge_key=f"memory-return:{index}",
            )
        for predecessor_index, predecessor in enumerate(value.get("predecessors") or []):
            fact_key = fact_node_keys.get(str(predecessor))
            if fact_key:
                anonymizer.add_edge(
                    source_key=fact_key,
                    target_key=source_key,
                    category="support",
                    source_edge_key=f"fact-return:{index}:{predecessor_index}",
                )

    submission_keys_by_sha: dict[str, str] = {}
    for index, path in enumerate(sorted((project_root / "submissions").glob("*.json"))):
        value = read_json(path)
        submission_id = str(value.get("submission_id") or path.stem)
        assignment_id = str(value.get("assignment_id") or "")
        fact_id = str(value.get("fact_id") or "")
        round_id = str(value.get("round_id") or "")
        source_key = f"submission:{index}:{submission_id}"
        theme_id = fact_themes.get(fact_id) or fallback_theme(source_key)
        anonymizer.add_node(
            source_key=source_key,
            plane="blackboard",
            role="result",
            visual_status="research",
            layer="knowledge",
            theme_id=theme_id,
        )
        submission_sha = value.get("submission_sha256")
        if submission_sha:
            submission_keys_by_sha[str(submission_sha)] = source_key
        for label, linked_key in (
            ("return", return_keys.get(assignment_id)),
            ("round", round_keys.get(round_id) or assignment_rounds.get(assignment_id)),
        ):
            if linked_key:
                anonymizer.add_edge(
                    source_key=linked_key,
                    target_key=source_key,
                    category="support",
                    source_edge_key=f"{label}-submission:{index}",
                )
        for predecessor_index, predecessor in enumerate(value.get("predecessors") or []):
            fact_key = fact_node_keys.get(str(predecessor))
            if fact_key:
                anonymizer.add_edge(
                    source_key=fact_key,
                    target_key=source_key,
                    category="support",
                    source_edge_key=f"fact-submission:{index}:{predecessor_index}",
                )
        if fact_id in fact_node_keys:
            anonymizer.add_edge(
                source_key=source_key,
                target_key=fact_node_keys[fact_id],
                category="support",
                source_edge_key=f"submission-fact:{index}",
            )

    for index, path in enumerate(sorted((project_root / "reviews" / "by-id").glob("*.json"))):
        value = read_json(path)
        review_id = str(value.get("review_id") or path.stem)
        fact_id = str(value.get("fact_id") or "")
        source_key = f"review:{index}:{review_id}"
        theme_id = fact_themes.get(fact_id) or fallback_theme(source_key)
        anonymizer.add_node(
            source_key=source_key,
            plane="audit",
            role="result",
            visual_status="challenged",
            layer="knowledge",
            theme_id=theme_id,
        )
        submission_key = submission_keys_by_sha.get(str(value.get("submission_sha256") or ""))
        if submission_key:
            anonymizer.add_edge(
                source_key=submission_key,
                target_key=source_key,
                category="support",
                source_edge_key=f"submission-review:{index}",
            )
        if fact_id in fact_node_keys:
            anonymizer.add_edge(
                source_key=source_key,
                target_key=fact_node_keys[fact_id],
                category="support",
                source_edge_key=f"review-fact:{index}",
            )

    public_target_order = [
        anonymizer.node_keys[source_node_keys[target_id]]
        for target_id in source_packet["target_order"]
    ]
    themes: list[dict[str, Any]] = []
    for raw_theme_id in raw_theme_order:
        raw_theme = raw_themes[raw_theme_id]
        themes.append(
            {
                "id": public_theme_ids[raw_theme_id],
                "label": anonymizer.opaque("theme-label", raw_theme_id),
                "description": anonymizer.opaque("theme-description", raw_theme_id),
                "target_ids": [
                    anonymizer.node_keys[source_node_keys[target_id]]
                    for target_id in raw_theme["target_ids"]
                ],
            }
        )

    packet = {
        "schema_version": 1,
        "project_id": "anonymized-research-topology",
        "language": "en",
        "title": "Anonymized research topology",
        "audience": "Public demonstration of graph scale and Reader interaction",
        "source_snapshot": {
            "id": anonymizer.opaque("aggregate-snapshot-id", "private-source"),
            "sha256": anonymizer.opaque("aggregate-snapshot-digest", "private-source"),
            "description": "Content-free structural projection; all private identifiers were remapped with HMAC-SHA-256.",
        },
        "presentation": {
            "subtitle": "Real topology, opaque nodes, presentation only.",
            "introduction": "This graph preserves structural relationships from a real research run while withholding claims, formulas, sources, names, paths, and original identifiers.",
        },
        "audit": {
            "current_ok": True,
            "summary": "Privacy audit: node content is hash-only and the projection has truth_effect=none.",
            "warnings": [
                "Topology and structural enums are visible.",
                "No mathematical conclusion can be recovered or certified from this projection.",
            ],
            "unresolved": [],
        },
        "theme_order": theme_ids,
        "target_order": public_target_order,
        "prerequisite_order": {},
        "themes": themes,
        "nodes": anonymizer.nodes,
        "edges": anonymizer.edges,
    }
    finish_prerequisites(packet)
    return packet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reader-packet", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--key-file",
        type=Path,
        help="Private key file for repeatable mapping; omit to discard an ephemeral key.",
    )
    parser.add_argument(
        "--forbid",
        action="append",
        default=[],
        help="Case-insensitive marker that must not occur in the output; repeatable.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = args.project_root.expanduser().resolve()
    output = args.output.expanduser().resolve()
    reader_packet_path = args.reader_packet.expanduser().resolve()
    if not project_root.is_dir() or project_root.is_symlink():
        raise ValueError("--project-root must be a real directory")
    if output == project_root or project_root in output.parents:
        raise ValueError("refusing to write the anonymized artifact inside the source project")
    source_packet = read_json(reader_packet_path)
    key, key_mode = load_key(args.key_file.expanduser().resolve() if args.key_file else None)
    anonymizer = Anonymizer(key)
    packet = build_packet(
        source_packet=source_packet,
        project_root=project_root,
        anonymizer=anonymizer,
    )
    assert_public_packet(
        packet,
        private_strings=private_packet_strings(source_packet),
        forbidden=[str(project_root), str(reader_packet_path), *args.forbid],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(packet, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=output.parent,
        prefix=f".{output.name}.",
        delete=False,
    ) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, output)
    print(
        json.dumps(
            {
                "edges": len(packet["edges"]),
                "key_mode": key_mode,
                "nodes": len(packet["nodes"]),
                "output_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                "themes": len(packet["themes"]),
                "truth_effect": "none",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
