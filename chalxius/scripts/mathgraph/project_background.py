from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .contracts import contained_path, sha256_bytes, sha256_json


PROJECT_BACKGROUND_FILENAME = "PROJECT_BACKGROUND.md"
MAX_PROJECT_BACKGROUND_BYTES = 256 * 1024
BACKGROUND_CHUNK_MAX_BYTES = 8 * 1024
BACKGROUND_INDEX_REVISION = "chalxius-v5-project-background-index-1"
BACKGROUND_BINDING_REVISION = "chalxius-v5-project-background-binding-2"
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")


def read_project_background(project_root: Path) -> bytes | None:
    """Read the optional source file without ever generating or refreshing it."""

    path = project_root / PROJECT_BACKGROUND_FILENAME
    if path.is_symlink():
        raise ValueError("PROJECT_BACKGROUND.md may not be a symlink")
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(
            "PROJECT_BACKGROUND.md must be a regular file; summary generation "
            "is never automatic"
        )
    raw = path.read_bytes()
    if len(raw) > MAX_PROJECT_BACKGROUND_BYTES:
        raise ValueError("PROJECT_BACKGROUND.md exceeds the 256 KiB source limit")
    try:
        body = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("PROJECT_BACKGROUND.md must be UTF-8") from exc
    if not body.strip():
        raise ValueError("PROJECT_BACKGROUND.md must have a nonempty body")
    return raw


def _line_count(raw: bytes) -> int:
    return raw.count(b"\n") + (0 if raw.endswith(b"\n") else 1)


def _heading_events(raw: bytes) -> list[tuple[int, list[str]]]:
    events: list[tuple[int, list[str]]] = []
    path: list[str] = []
    offset = 0
    for raw_line in raw.splitlines(keepends=True):
        line = raw_line.decode("utf-8").rstrip("\r\n")
        match = _HEADING_RE.fullmatch(line)
        if match is not None:
            level = len(match.group(1))
            title = match.group(2).strip()
            bounded = title if len(title) <= 160 else title[:157] + "..."
            path = [*path[: level - 1], bounded]
            events.append((offset, list(path)))
        offset += len(raw_line)
    return events


def _chunk_end(raw: bytes, start: int) -> int:
    hard_end = min(start + BACKGROUND_CHUNK_MAX_BYTES, len(raw))
    if hard_end == len(raw):
        return hard_end
    newline = raw.rfind(b"\n", start + 1, hard_end + 1)
    if newline >= start + BACKGROUND_CHUNK_MAX_BYTES // 2:
        return newline + 1
    end = hard_end
    while end > start:
        try:
            raw[start:end].decode("utf-8")
        except UnicodeDecodeError:
            end -= 1
            continue
        return end
    raise ValueError("PROJECT_BACKGROUND.md cannot be split at a UTF-8 boundary")


def build_background_index(raw: bytes) -> dict[str, Any]:
    """Build a complete exact-byte index; no generated semantic summary is used."""

    raw.decode("utf-8")
    source_sha256 = sha256_bytes(raw)
    heading_events = _heading_events(raw)
    chunks: list[dict[str, Any]] = []
    start = 0
    heading_index = 0
    heading_path: list[str] = []
    while start < len(raw):
        while (
            heading_index < len(heading_events)
            and heading_events[heading_index][0] <= start
        ):
            heading_path = heading_events[heading_index][1]
            heading_index += 1
        end = _chunk_end(raw, start)
        chunk = raw[start:end]
        chunk_sha256 = sha256_bytes(chunk)
        line_start = raw.count(b"\n", 0, start) + 1
        line_end = raw.count(b"\n", 0, max(start, end - 1)) + 1
        identity = {
            "source_sha256": source_sha256,
            "byte_start": start,
            "byte_end_exclusive": end,
            "chunk_sha256": chunk_sha256,
        }
        chunks.append(
            {
                "chunk_id": "bgc-" + sha256_json(identity),
                "byte_start": start,
                "byte_end_exclusive": end,
                "byte_length": len(chunk),
                "line_start": line_start,
                "line_end": line_end,
                "heading_path": list(heading_path),
                "sha256": chunk_sha256,
            }
        )
        start = end
    semantic = {
        "revision": BACKGROUND_INDEX_REVISION,
        "source_sha256": source_sha256,
        "source_byte_length": len(raw),
        "source_line_count": _line_count(raw),
        "chunk_max_bytes": BACKGROUND_CHUNK_MAX_BYTES,
        "chunks": chunks,
        "coverage_receipt": {
            "partition": "complete_exact_byte_partition",
            "covered_byte_count": len(raw),
            "omitted_byte_count": 0,
            "chunk_count": len(chunks),
        },
    }
    return {**semantic, "index_sha256": sha256_json(semantic)}


def current_background_index(project_root: Path) -> dict[str, Any] | None:
    raw = read_project_background(project_root)
    if raw is None:
        return None
    index = build_background_index(raw)
    return {
        "source_relpath": PROJECT_BACKGROUND_FILENAME,
        "source_sha256": index["source_sha256"],
        "source_byte_length": index["source_byte_length"],
        "source_line_count": index["source_line_count"],
        "index": index,
        "truth_effect": "nontruth_background_only",
        "load_bearing_rule": "return_to_exact_cited_source",
    }


def build_frozen_background_binding(
    *,
    raw: bytes,
    snapshot_relpath: str,
    selected_chunk_ids: list[str],
) -> dict[str, Any]:
    index = build_background_index(raw)
    all_ids = [item["chunk_id"] for item in index["chunks"]]
    if len(set(selected_chunk_ids)) != len(selected_chunk_ids):
        raise ValueError("background chunk selection contains duplicates")
    unknown = sorted(set(selected_chunk_ids).difference(all_ids))
    if unknown:
        raise ValueError(
            "background chunk selection contains unknown ids: " + ", ".join(unknown)
        )
    selected = sorted(selected_chunk_ids)
    selection_semantic = {
        "compiler_role": "v5_main_planner",
        "policy": (
            "explicit_planner_chunk_selection"
            if selected
            else "index_only_exact_chunks_on_demand"
        ),
        "selected_chunk_ids": selected,
        "unselected_chunk_count": len(all_ids) - len(selected),
        "all_unselected_chunks_retrievable": True,
        "omission_effect": "nontruth_context_only",
    }
    selection = {
        **selection_semantic,
        "selection_sha256": sha256_json(selection_semantic),
    }
    return {
        "binding_revision": BACKGROUND_BINDING_REVISION,
        "read_policy": "index_by_default_exact_chunks_on_demand",
        "source_relpath": PROJECT_BACKGROUND_FILENAME,
        "source_sha256": index["source_sha256"],
        "source_byte_length": index["source_byte_length"],
        "source_line_count": index["source_line_count"],
        "snapshot_relpath": snapshot_relpath,
        "snapshot_sha256": index["source_sha256"],
        "index": index,
        "selection_receipt": selection,
        "rehydration_rule": "reread_index_and_exact_chunks_after_context_compaction",
        "truth_effect": "nontruth_background_only",
        "load_bearing_rule": "return_to_exact_cited_source",
    }


def validate_frozen_background_binding(
    project_root: Path,
    binding: Any,
    *,
    expected_snapshot_relpath: str,
) -> dict[str, Any]:
    required = {
        "binding_revision",
        "read_policy",
        "source_relpath",
        "source_sha256",
        "source_byte_length",
        "source_line_count",
        "snapshot_relpath",
        "snapshot_sha256",
        "index",
        "selection_receipt",
        "rehydration_rule",
        "truth_effect",
        "load_bearing_rule",
    }
    if not isinstance(binding, dict) or set(binding) != required:
        raise ValueError("V5 indexed project-background binding fields are not exact")
    if (
        binding["binding_revision"] != BACKGROUND_BINDING_REVISION
        or binding["read_policy"] != "index_by_default_exact_chunks_on_demand"
        or binding["source_relpath"] != PROJECT_BACKGROUND_FILENAME
        or binding["snapshot_relpath"] != expected_snapshot_relpath
        or binding["rehydration_rule"]
        != "reread_index_and_exact_chunks_after_context_compaction"
        or binding["truth_effect"] != "nontruth_background_only"
        or binding["load_bearing_rule"] != "return_to_exact_cited_source"
    ):
        raise ValueError("V5 indexed project-background binding is invalid")
    snapshot_path = contained_path(
        project_root,
        binding["snapshot_relpath"],
        "V5 frozen project-background snapshot",
    )
    if snapshot_path.is_symlink() or not snapshot_path.is_file():
        raise ValueError("V5 frozen project-background snapshot is missing or unsafe")
    raw = snapshot_path.read_bytes()
    if sha256_bytes(raw) != binding["snapshot_sha256"]:
        raise ValueError("V5 frozen project-background snapshot drifted")
    selection_receipt = binding["selection_receipt"]
    if not isinstance(selection_receipt, dict):
        raise ValueError("V5 background selection receipt must be an object")
    selected = selection_receipt.get("selected_chunk_ids")
    if not isinstance(selected, list) or any(not isinstance(item, str) for item in selected):
        raise ValueError("V5 background selection receipt is invalid")
    expected = build_frozen_background_binding(
        raw=raw,
        snapshot_relpath=expected_snapshot_relpath,
        selected_chunk_ids=selected,
    )
    if binding != expected:
        raise ValueError("V5 indexed project-background binding drifted")
    return binding


def background_chunk_from_binding(
    project_root: Path,
    binding: dict[str, Any],
    *,
    chunk_id: str,
) -> dict[str, Any]:
    chunks = {
        item["chunk_id"]: item
        for item in binding["index"]["chunks"]
        if isinstance(item, dict) and isinstance(item.get("chunk_id"), str)
    }
    if chunk_id not in chunks:
        raise KeyError(f"unknown frozen project-background chunk: {chunk_id}")
    entry = chunks[chunk_id]
    path = contained_path(
        project_root,
        binding["snapshot_relpath"],
        "V5 frozen project-background snapshot",
    )
    raw = path.read_bytes()
    chunk = raw[entry["byte_start"] : entry["byte_end_exclusive"]]
    if len(chunk) != entry["byte_length"] or sha256_bytes(chunk) != entry["sha256"]:
        raise ValueError("V5 frozen project-background chunk drifted")
    return {
        **entry,
        "source_sha256": binding["source_sha256"],
        "content": chunk.decode("utf-8"),
        "rehydration_effect": "restores_exact_nontruth_context_only",
        "truth_effect": "none",
    }
