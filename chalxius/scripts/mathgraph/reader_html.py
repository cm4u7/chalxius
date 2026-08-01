from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .contracts import (
    canonical_json_bytes,
    contained_path,
    require_exact_keys,
    sha256_bytes,
)


READER_PACKET_SCHEMA_VERSION = 1
RENDERER_REVISION = "chalxius-reader-html-20"
FIXED_OUTPUT_RELPATH = "visualizations/knowledge-map.html"
MAX_PACKET_BYTES = 16 * 1024 * 1024
MAX_NODES = 5_000
MAX_EDGES = 20_000
MAX_TEXT_CHARS = 2_000_000

_SAFE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_THEME_ID_RE = re.compile(r"theme-[a-z0-9][a-z0-9-]{0,62}")

_READER_ROLES = {"target", "definition", "result", "explanation"}
_PLANES = {"fact", "paper", "audit", "blackboard", "learning", "reader"}
_VISUAL_STATUSES = {"current", "research", "challenged", "inactive"}
_LAYERS = {"knowledge", "research"}
_EDGE_CATEGORIES = {"prerequisite", "support", "repair", "conflict"}

_TRUTH_STATUSES_BY_PLANE = {
    "fact": {"admitted_fact", "historical_inactive"},
    "paper": {"source_authority", "interpretation", "historical_inactive"},
    "audit": {"audit_evidence", "historical_inactive"},
    "blackboard": {"exploration", "historical_inactive"},
    "learning": {"learning", "historical_inactive"},
    "reader": {"reader_note"},
}
_NONFACT_SOURCE_STATUS_TOKENS = {
    "candidate",
    "pending",
    "exploration",
    "open",
    "verifying",
    "challenged",
}

_ASSETS = {
    "template": "reader_html_template.html",
    "style": "reader_html.css",
    "app": "reader_html_app.js",
    "cytoscape": "vendor/cytoscape-3.34.0.min.js",
    "mathjax": "vendor/mathjax-3.2.2-tex-svg.js",
}

_TABLER_ICON_VERSION = "3.45.0"
_TABLER_ICONS = {
    "context": "adjustments-horizontal.svg",
    "copy": "copy.svg",
    "collapse": "square-minus.svg",
    "expand": "square-plus.svg",
    "file": "file-description.svg",
    "focus": "focus-2.svg",
    "info": "info-circle.svg",
    "move": "arrows-move.svg",
    "overview": "layout-dashboard.svg",
    "path": "route.svg",
    "refresh": "refresh.svg",
    "reset": "restore.svg",
    "search": "search.svg",
    "undo": "arrow-back-up.svg",
    "redo": "arrow-forward-up.svg",
}
_SVG_VIEWBOX_RE = re.compile(r"[0-9. -]+")


def _object_pairs_without_duplicates(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"reader packet contains duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"reader packet contains non-finite JSON number: {value}")


def _as_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _as_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _string(
    value: Any,
    label: str,
    *,
    allow_empty: bool = False,
    one_line: bool = False,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{label} must be nonempty")
    if len(value) > MAX_TEXT_CHARS:
        raise ValueError(f"{label} exceeds the reader-packet text limit")
    if one_line and ("\n" in value or "\r" in value):
        raise ValueError(f"{label} must be one line")
    return value


def _string_list(
    value: Any,
    label: str,
    *,
    allow_empty_items: bool = False,
) -> list[str]:
    items = _as_list(value, label)
    return [
        _string(
            item,
            f"{label}[{index}]",
            allow_empty=allow_empty_items,
        )
        for index, item in enumerate(items)
    ]


def _unique(items: list[str], label: str) -> None:
    if len(items) != len(set(items)):
        raise ValueError(f"{label} must not contain duplicates")


def _safe_id(value: Any, label: str) -> str:
    identifier = _string(value, label, one_line=True)
    if _SAFE_ID_RE.fullmatch(identifier) is None:
        raise ValueError(f"{label} has an unsafe identifier: {identifier!r}")
    return identifier


def _theme_id(value: Any, label: str) -> str:
    identifier = _string(value, label, one_line=True)
    if _THEME_ID_RE.fullmatch(identifier) is None:
        raise ValueError(f"{label} has an invalid theme id: {identifier!r}")
    return identifier


def _sha256(value: Any, label: str) -> str:
    digest = _string(value, label, one_line=True)
    if _SHA256_RE.fullmatch(digest) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 value")
    return digest


def _enum(value: Any, allowed: set[str], label: str) -> str:
    selected = _string(value, label, one_line=True)
    if selected not in allowed:
        raise ValueError(
            f"{label} must be one of: {', '.join(sorted(allowed))}"
        )
    return selected


def _validate_provenance(
    value: Any,
    label: str,
    *,
    expected_plane: str | None = None,
    original_text: str | None = None,
) -> dict[str, Any]:
    provenance = _as_object(value, label)
    require_exact_keys(
        provenance,
        required={
            "source_plane",
            "source_status",
            "truth_status",
            "object_id",
            "snapshot_id",
            "locator",
            "object_sha256",
            "original_text_sha256",
            "replaces",
        },
        label=label,
    )
    plane = _enum(provenance["source_plane"], _PLANES, f"{label}.source_plane")
    if expected_plane is not None and plane != expected_plane:
        raise ValueError(f"{label}.source_plane does not match the node plane")
    _string(provenance["source_status"], f"{label}.source_status", one_line=True)
    _enum(
        provenance["truth_status"],
        _TRUTH_STATUSES_BY_PLANE[plane],
        f"{label}.truth_status",
    )
    _string(provenance["object_id"], f"{label}.object_id", one_line=True)
    _string(provenance["snapshot_id"], f"{label}.snapshot_id", one_line=True)
    _string(provenance["locator"], f"{label}.locator", one_line=True)
    _sha256(provenance["object_sha256"], f"{label}.object_sha256")
    text_sha256 = _sha256(
        provenance["original_text_sha256"],
        f"{label}.original_text_sha256",
    )
    _string_list(provenance["replaces"], f"{label}.replaces")
    if original_text is not None:
        actual = sha256_bytes(original_text.encode("utf-8"))
        if text_sha256 != actual:
            raise ValueError(f"{label}.original_text_sha256 does not bind exact text")
    return provenance


def _validate_formal(value: Any, label: str) -> dict[str, Any]:
    formal = _as_object(value, label)
    require_exact_keys(
        formal,
        required={"hypotheses", "statement", "proof", "relations", "original_text"},
        label=label,
    )
    _string_list(formal["hypotheses"], f"{label}.hypotheses")
    _string(formal["statement"], f"{label}.statement", allow_empty=True)
    _string(formal["proof"], f"{label}.proof", allow_empty=True)
    _string_list(formal["relations"], f"{label}.relations")
    _string(formal["original_text"], f"{label}.original_text")
    return formal


def _validate_node(value: Any, index: int) -> dict[str, Any]:
    label = f"nodes[{index}]"
    node = _as_object(value, label)
    require_exact_keys(
        node,
        required={
            "id",
            "title",
            "reader_role",
            "plane",
            "visual_status",
            "layer",
            "theme_id",
            "summary",
            "intuition",
            "importance",
            "reasoning",
            "prerequisites",
            "formal",
            "provenance",
        },
        label=label,
    )
    _safe_id(node["id"], f"{label}.id")
    _string(node["title"], f"{label}.title", one_line=True)
    _enum(node["reader_role"], _READER_ROLES, f"{label}.reader_role")
    plane = _enum(node["plane"], _PLANES, f"{label}.plane")
    _enum(node["visual_status"], _VISUAL_STATUSES, f"{label}.visual_status")
    _enum(node["layer"], _LAYERS, f"{label}.layer")
    _theme_id(node["theme_id"], f"{label}.theme_id")
    _string(node["summary"], f"{label}.summary")
    _string(node["intuition"], f"{label}.intuition")
    _string(node["importance"], f"{label}.importance")
    _string(node["reasoning"], f"{label}.reasoning")
    prerequisites = _string_list(
        node["prerequisites"], f"{label}.prerequisites"
    )
    for item_index, item in enumerate(prerequisites):
        _safe_id(item, f"{label}.prerequisites[{item_index}]")
    _unique(prerequisites, f"{label}.prerequisites")
    formal = _validate_formal(node["formal"], f"{label}.formal")
    provenance = _validate_provenance(
        node["provenance"],
        f"{label}.provenance",
        expected_plane=plane,
        original_text=formal["original_text"],
    )
    source_status_tokens = set(
        re.findall(r"[a-z0-9]+", provenance["source_status"].casefold())
    )
    if plane == "fact" and source_status_tokens.intersection(
        _NONFACT_SOURCE_STATUS_TOKENS
    ):
        raise ValueError(
            f"{label} cannot label {provenance['source_status']!r} as Fact"
        )
    if plane != "fact" and provenance["truth_status"] == "admitted_fact":
        raise ValueError(f"{label} cannot give a non-Fact node Fact authority")
    if node["reader_role"] == "target" and node["layer"] != "knowledge":
        raise ValueError(f"{label} target nodes must be in the knowledge layer")
    return node


def _validate_edge(value: Any, index: int) -> dict[str, Any]:
    label = f"edges[{index}]"
    edge = _as_object(value, label)
    require_exact_keys(
        edge,
        required={
            "id",
            "source",
            "target",
            "category",
            "relation",
            "exact_type",
            "weak",
            "layer",
            "provenance",
        },
        label=label,
    )
    _safe_id(edge["id"], f"{label}.id")
    _safe_id(edge["source"], f"{label}.source")
    _safe_id(edge["target"], f"{label}.target")
    category = _enum(edge["category"], _EDGE_CATEGORIES, f"{label}.category")
    _string(edge["relation"], f"{label}.relation", one_line=True)
    _string(edge["exact_type"], f"{label}.exact_type", one_line=True)
    if not isinstance(edge["weak"], bool):
        raise ValueError(f"{label}.weak must be a boolean")
    layer = _enum(edge["layer"], _LAYERS, f"{label}.layer")
    _validate_provenance(edge["provenance"], f"{label}.provenance")
    if category == "prerequisite" and (edge["weak"] or layer != "knowledge"):
        raise ValueError(
            f"{label} prerequisite edges must be strong knowledge-layer edges"
        )
    return edge


def _validate_source_snapshot(value: Any) -> dict[str, Any]:
    snapshot = _as_object(value, "source_snapshot")
    require_exact_keys(
        snapshot,
        required={"id", "sha256", "description"},
        label="source_snapshot",
    )
    _string(snapshot["id"], "source_snapshot.id", one_line=True)
    _sha256(snapshot["sha256"], "source_snapshot.sha256")
    _string(snapshot["description"], "source_snapshot.description")
    return snapshot


def _validate_presentation(value: Any) -> dict[str, Any]:
    presentation = _as_object(value, "presentation")
    require_exact_keys(
        presentation,
        required={"subtitle", "introduction"},
        label="presentation",
    )
    _string(presentation["subtitle"], "presentation.subtitle", allow_empty=True)
    _string(presentation["introduction"], "presentation.introduction")
    return presentation


def _validate_audit(value: Any) -> dict[str, Any]:
    audit = _as_object(value, "audit")
    require_exact_keys(
        audit,
        required={"current_ok", "summary", "warnings", "unresolved"},
        label="audit",
    )
    if not isinstance(audit["current_ok"], bool):
        raise ValueError("audit.current_ok must be a boolean")
    _string(audit["summary"], "audit.summary")
    _string_list(audit["warnings"], "audit.warnings")
    _string_list(audit["unresolved"], "audit.unresolved")
    return audit


def _prerequisite_ancestors(
    target: str,
    predecessors: dict[str, list[str]],
) -> set[str]:
    found: set[str] = set()
    pending = list(predecessors[target])
    while pending:
        node_id = pending.pop()
        if node_id in found:
            continue
        found.add(node_id)
        pending.extend(predecessors[node_id])
    return found


def _reject_prerequisite_cycle(predecessors: dict[str, list[str]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ValueError("reader packet prerequisite graph contains a cycle")
        if node_id in visited:
            return
        visiting.add(node_id)
        for predecessor in predecessors[node_id]:
            visit(predecessor)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in predecessors:
        visit(node_id)


def validate_reader_packet(
    payload: Any,
    *,
    project_id: str | None = None,
) -> dict[str, Any]:
    packet = _as_object(payload, "reader packet")
    require_exact_keys(
        packet,
        required={
            "schema_version",
            "project_id",
            "language",
            "title",
            "audience",
            "source_snapshot",
            "presentation",
            "audit",
            "theme_order",
            "target_order",
            "prerequisite_order",
            "themes",
            "nodes",
            "edges",
        },
        label="reader packet",
    )
    if packet["schema_version"] != READER_PACKET_SCHEMA_VERSION:
        raise ValueError(
            f"reader packet schema_version must be {READER_PACKET_SCHEMA_VERSION}"
        )
    packet_project_id = _string(packet["project_id"], "project_id", one_line=True)
    if project_id is not None and packet_project_id != project_id:
        raise ValueError(
            "reader packet project identity mismatch: "
            f"packet={packet_project_id!r} project={project_id!r}"
        )
    if packet["language"] != "en":
        raise ValueError("reader packet language must be 'en'")
    _string(packet["title"], "title", one_line=True)
    _string(packet["audience"], "audience", one_line=True)
    _validate_source_snapshot(packet["source_snapshot"])
    _validate_presentation(packet["presentation"])
    _validate_audit(packet["audit"])

    raw_nodes = _as_list(packet["nodes"], "nodes")
    raw_edges = _as_list(packet["edges"], "edges")
    if not raw_nodes:
        raise ValueError("reader packet must contain at least one node")
    if len(raw_nodes) > MAX_NODES:
        raise ValueError(f"reader packet exceeds the {MAX_NODES}-node limit")
    if len(raw_edges) > MAX_EDGES:
        raise ValueError(f"reader packet exceeds the {MAX_EDGES}-edge limit")
    nodes = [_validate_node(value, index) for index, value in enumerate(raw_nodes)]
    edges = [_validate_edge(value, index) for index, value in enumerate(raw_edges)]
    node_ids = [node["id"] for node in nodes]
    edge_ids = [edge["id"] for edge in edges]
    _unique(node_ids, "node ids")
    _unique(edge_ids, "edge ids")
    if set(node_ids).intersection(edge_ids):
        raise ValueError("reader packet node and edge ids must not collide")
    node_by_id = {node["id"]: node for node in nodes}

    predecessors = {node_id: [] for node_id in node_ids}
    for edge in edges:
        if edge["source"] not in node_by_id or edge["target"] not in node_by_id:
            raise ValueError(
                f"edge {edge['id']!r} has a dangling source or target endpoint"
            )
        source_node = node_by_id[edge["source"]]
        target_node = node_by_id[edge["target"]]
        if edge["layer"] == "knowledge" and (
            source_node["layer"] != "knowledge"
            or target_node["layer"] != "knowledge"
        ):
            raise ValueError(
                f"edge {edge['id']!r} cannot label a research endpoint as knowledge"
            )
        if edge["category"] == "prerequisite":
            predecessors[edge["target"]].append(edge["source"])
    for node in nodes:
        direct = predecessors[node["id"]]
        if node["prerequisites"] != direct:
            raise ValueError(
                f"node {node['id']!r} prerequisites must exactly match incoming "
                "prerequisite edges in edge order"
            )
    _reject_prerequisite_cycle(predecessors)

    raw_themes = _as_list(packet["themes"], "themes")
    if not raw_themes:
        raise ValueError("reader packet must contain at least one theme")
    themes: list[dict[str, Any]] = []
    for index, value in enumerate(raw_themes):
        label = f"themes[{index}]"
        theme = _as_object(value, label)
        require_exact_keys(
            theme,
            required={"id", "label", "description", "target_ids"},
            label=label,
        )
        _theme_id(theme["id"], f"{label}.id")
        _string(theme["label"], f"{label}.label", one_line=True)
        _string(theme["description"], f"{label}.description", allow_empty=True)
        target_ids = _string_list(theme["target_ids"], f"{label}.target_ids")
        for item_index, item in enumerate(target_ids):
            _safe_id(item, f"{label}.target_ids[{item_index}]")
        _unique(target_ids, f"{label}.target_ids")
        if not target_ids:
            raise ValueError(f"{label} must contain at least one target")
        themes.append(theme)
    theme_ids = [theme["id"] for theme in themes]
    _unique(theme_ids, "theme ids")
    theme_by_id = {theme["id"]: theme for theme in themes}
    for node in nodes:
        if node["theme_id"] not in theme_by_id:
            raise ValueError(
                f"node {node['id']!r} references an unknown theme"
            )

    theme_order = _string_list(packet["theme_order"], "theme_order")
    for index, item in enumerate(theme_order):
        _theme_id(item, f"theme_order[{index}]")
    _unique(theme_order, "theme_order")
    if set(theme_order) != set(theme_ids):
        raise ValueError("theme_order must contain every theme id exactly once")

    target_order = _string_list(packet["target_order"], "target_order")
    for index, item in enumerate(target_order):
        _safe_id(item, f"target_order[{index}]")
    _unique(target_order, "target_order")
    target_nodes = {
        node["id"] for node in nodes if node["reader_role"] == "target"
    }
    if not target_order or set(target_order) != target_nodes:
        raise ValueError("target_order must contain every target node exactly once")
    grouped_target_order = [
        target_id
        for theme_id in theme_order
        for target_id in theme_by_id[theme_id]["target_ids"]
    ]
    if grouped_target_order != target_order:
        raise ValueError(
            "target_order must equal theme target_ids concatenated in theme_order"
        )
    for theme in themes:
        for target_id in theme["target_ids"]:
            if target_id not in target_nodes:
                raise ValueError(
                    f"theme {theme['id']!r} references a non-target node"
                )
            if node_by_id[target_id]["theme_id"] != theme["id"]:
                raise ValueError(
                    f"target {target_id!r} is assigned to a conflicting theme"
                )

    prerequisite_order = _as_object(
        packet["prerequisite_order"], "prerequisite_order"
    )
    if set(prerequisite_order) != set(target_order):
        raise ValueError(
            "prerequisite_order must have exactly one entry for every target"
        )
    for target_id in target_order:
        order = _string_list(
            prerequisite_order[target_id],
            f"prerequisite_order.{target_id}",
        )
        for index, item in enumerate(order):
            _safe_id(item, f"prerequisite_order.{target_id}[{index}]")
        _unique(order, f"prerequisite_order.{target_id}")
        ancestors = _prerequisite_ancestors(target_id, predecessors)
        if set(order) != ancestors:
            raise ValueError(
                f"prerequisite_order.{target_id} must contain exactly the "
                "target's prerequisite ancestors"
            )
        if any(node_by_id[node_id]["layer"] != "knowledge" for node_id in order):
            raise ValueError(
                f"prerequisite_order.{target_id} may contain only knowledge nodes"
            )

    return packet


def load_reader_packet(
    path: Path | str,
    *,
    project_id: str | None = None,
) -> dict[str, Any]:
    packet_path = Path(path).expanduser()
    if packet_path.is_symlink() or not packet_path.is_file():
        raise ValueError("reader packet must be a regular, non-symlink file")
    raw = packet_path.read_bytes()
    if len(raw) > MAX_PACKET_BYTES:
        raise ValueError("reader packet exceeds the 16 MiB input limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("reader packet must be UTF-8 JSON") from exc
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_object_pairs_without_duplicates,
            parse_constant=_reject_nonfinite,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"reader packet is not valid JSON: {exc.msg}") from exc
    return validate_reader_packet(payload, project_id=project_id)


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _asset_text(name: str) -> str:
    path = _skill_root() / "assets" / _ASSETS[name]
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"reader renderer asset is missing or unsafe: {path}")
    return path.read_text(encoding="utf-8")


def _tabler_icon_sprite() -> tuple[str, dict[str, str]]:
    icon_root = (
        _skill_root()
        / "assets"
        / "vendor"
        / f"tabler-icons-{_TABLER_ICON_VERSION}"
    )
    symbols: list[str] = []
    source_hashes: dict[str, str] = {}
    for icon_id, filename in _TABLER_ICONS.items():
        path = icon_root / filename
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"reader icon asset is missing or unsafe: {path}")
        source = path.read_text(encoding="utf-8")
        source_hashes[icon_id] = sha256_bytes(source.encode("utf-8"))
        match = re.fullmatch(
            r'\s*<svg\b[^>]*\bviewBox="([^"]+)"[^>]*>(.*)</svg>\s*',
            source,
            flags=re.DOTALL,
        )
        if match is None or _SVG_VIEWBOX_RE.fullmatch(match.group(1)) is None:
            raise ValueError(f"reader icon asset has unexpected SVG structure: {path}")
        body = match.group(2).strip()
        lowered = body.lower()
        if any(token in lowered for token in ("<script", "<style", "<image", "href=")):
            raise ValueError(f"reader icon asset contains disallowed SVG content: {path}")
        symbols.append(
            f'<symbol id="reader-icon-{icon_id}" viewBox="{match.group(1)}" '
            'fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">\n'
            f'{body}\n</symbol>'
        )
    return "\n".join(symbols), source_hashes


def _inline_script(source: str) -> str:
    # A literal closing script tag would terminate the containing HTML element.
    # Escaping the slash is JavaScript-equivalent and keeps vendored code inline.
    return re.sub(r"</script", r"<\\/script", source, flags=re.IGNORECASE)


def _script_json(payload: Any) -> str:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        text.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_reader_html(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    packet = validate_reader_packet(payload)
    packet_sha256 = sha256_bytes(canonical_json_bytes(packet))
    reader_finalize = {
        "schema_version": 1,
        "status": "ready",
        "scope": "presentation_readiness_only",
        "source_snapshot_id": packet["source_snapshot"]["id"],
        "source_snapshot_sha256": packet["source_snapshot"]["sha256"],
        "sidebar_complete_count": len(packet["nodes"]),
        "node_count": len(packet["nodes"]),
        "packet_sha256": packet_sha256,
        "truth_effect": "none",
    }
    cytoscape_source = _asset_text("cytoscape")
    mathjax_source = _asset_text("mathjax")
    tabler_sprite, tabler_source_hashes = _tabler_icon_sprite()
    build_meta = {
        "renderer_revision": RENDERER_REVISION,
        "packet_sha256": packet_sha256,
        "truth_effect": "none",
        "layout": "deterministic_theme_multicenter_orbit_fields",
        "network_runtime": "disabled",
        "reader_finalize": reader_finalize,
        "assets": {
            "cytoscape": {
                "version": "3.34.0",
                "sha256": sha256_bytes(cytoscape_source.encode("utf-8")),
            },
            "mathjax": {
                "version": "3.2.2",
                "bundle": "tex-svg",
                "sha256": sha256_bytes(mathjax_source.encode("utf-8")),
            },
            "tabler_icons": {
                "version": _TABLER_ICON_VERSION,
                "license": "MIT",
                "sprite_sha256": sha256_bytes(tabler_sprite.encode("utf-8")),
                "source_sha256": tabler_source_hashes,
            },
        },
    }
    replacements = {
        "@@CHALXIUS_READER_STYLE@@": _asset_text("style"),
        "@@CHALXIUS_TABLER_SPRITE@@": tabler_sprite,
        "@@CHALXIUS_CYTOSCAPE_JS@@": _inline_script(cytoscape_source),
        "@@CHALXIUS_MATHJAX_JS@@": _inline_script(mathjax_source),
        "@@CHALXIUS_READER_PACKET@@": _script_json(packet),
        "@@CHALXIUS_BUILD_META@@": _script_json(build_meta),
        "@@CHALXIUS_READER_APP@@": _inline_script(_asset_text("app")),
    }
    html = _asset_text("template")
    for marker, value in replacements.items():
        if html.count(marker) != 1:
            raise ValueError(f"reader renderer template marker drift: {marker}")
        html = html.replace(marker, value)
    if not html.endswith("\n"):
        html += "\n"
    return html, build_meta


def _fixed_output_path(root: Path) -> Path:
    raw_directory = root / "visualizations"
    raw_output = raw_directory / "knowledge-map.html"
    if raw_directory.is_symlink() or raw_output.is_symlink():
        raise ValueError("reader visualization output path may not be a symlink")
    if raw_directory.exists() and not raw_directory.is_dir():
        raise ValueError("PROJECT/visualizations must be a directory")
    if raw_output.exists() and not raw_output.is_file():
        raise ValueError("fixed reader visualization output must be a regular file")
    return contained_path(root, FIXED_OUTPUT_RELPATH, "reader visualization output")


def export_reader_payload(store: Any, payload: dict[str, Any]) -> dict[str, Any]:
    packet = validate_reader_packet(payload, project_id=store.project_id())
    html, build_meta = render_reader_html(packet)
    output = _fixed_output_path(store.root)
    with store.mutation_lock():
        # Repeat symlink/type checks while holding the cooperative project lock.
        output = _fixed_output_path(store.root)
        store._write_text_atomic(output, html, mode=0o600)
    return {
        "schema_version": 1,
        "project_id": store.project_id(),
        "output": str(output),
        "overwrite_policy": "fixed_replace",
        "renderer_revision": RENDERER_REVISION,
        "packet_sha256": build_meta["packet_sha256"],
        "html_sha256": sha256_bytes(html.encode("utf-8")),
        "node_count": len(packet["nodes"]),
        "edge_count": len(packet["edges"]),
        "target_count": len(packet["target_order"]),
        "truth_effect": "none",
        "network_runtime": "disabled",
        "reader_finalize": build_meta["reader_finalize"],
    }


def export_reader_html(store: Any, packet_path: Path | str) -> dict[str, Any]:
    packet = load_reader_packet(packet_path, project_id=store.project_id())
    return export_reader_payload(store, packet)
