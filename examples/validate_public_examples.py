#!/usr/bin/env python3
"""Validate public Reader packets and the hash-only showcase privacy boundary."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "chalxius" / "scripts"))

from mathgraph.reader_html import load_reader_packet  # noqa: E402


PACKETS = REPOSITORY / "examples" / "reader-packets"
CASES = REPOSITORY / "docs" / "cases"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PRIVATE_MARKERS = (
    "/users/",
    "/home/",
    "documents/",
)


def require_hash(value: str, label: str) -> None:
    if HEX64.fullmatch(value) is None:
        raise RuntimeError(f"{label} is not an opaque SHA-256 value")


def validate_anonymized(packet: dict[str, object], html: str) -> None:
    nodes = packet["nodes"]
    edges = packet["edges"]
    if len(nodes) < 150 or len(edges) < 300:
        raise RuntimeError("anonymized showcase no longer exercises a large graph")
    for index, node in enumerate(nodes):
        fields = [
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
        for field_index, value in enumerate(fields):
            require_hash(value, f"nodes[{index}].hash_fields[{field_index}]")
    for index, edge in enumerate(edges):
        for field in (
            "id",
            "source",
            "target",
            "relation",
            "exact_type",
        ):
            require_hash(edge[field], f"edges[{index}].{field}")
        for field in (
            "object_id",
            "snapshot_id",
            "locator",
            "object_sha256",
            "original_text_sha256",
        ):
            require_hash(edge["provenance"][field], f"edges[{index}].provenance.{field}")
    combined = (json.dumps(packet, ensure_ascii=False) + html).casefold()
    leaked = [marker for marker in PRIVATE_MARKERS if marker in combined]
    if leaked:
        raise RuntimeError(f"private marker found in public showcase: {leaked}")


def main() -> None:
    results: list[dict[str, object]] = []
    for packet_path in sorted(PACKETS.glob("*.json")):
        packet = load_reader_packet(packet_path)
        slug = packet_path.stem
        html_path = CASES / f"{slug}.html"
        if not html_path.is_file() or html_path.is_symlink():
            raise RuntimeError(f"missing public Reader HTML for {slug}")
        html = html_path.read_text(encoding="utf-8")
        if slug == "anonymized-research-topology":
            validate_anonymized(packet, html)
        results.append(
            {
                "case": slug,
                "edges": len(packet["edges"]),
                "nodes": len(packet["nodes"]),
                "status": "pass",
            }
        )
    print(json.dumps({"cases": results, "status": "pass"}, sort_keys=True))


if __name__ == "__main__":
    main()
