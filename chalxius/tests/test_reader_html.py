from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path

from mathgraph.cli import build_parser, main
from mathgraph.contracts import canonical_json_bytes, sha256_bytes
from mathgraph.reader_html import (
    FIXED_OUTPUT_RELPATH,
    export_reader_html,
    load_reader_packet,
    render_reader_html,
    validate_reader_packet,
)
from mathgraph.roles import allowed_commands
from mathgraph.store import MathGraphStore


SKILL_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PACKET = SKILL_ROOT / "assets" / "reader_packet.v1.example.json"


class _DependencyCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[tuple[str, str, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        for key, value in attrs:
            if key in {"src", "href"} and value is not None:
                self.references.append((tag, key, value))


def example_packet() -> dict:
    return json.loads(EXAMPLE_PACKET.read_text(encoding="utf-8"))


def write_packet(root: Path, payload: dict, name: str = "packet.json") -> Path:
    path = root / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def javascript_function_source(rendered_html: str, name: str) -> str:
    marker = f"  function {name}("
    start = rendered_html.find(marker)
    if start < 0:
        raise AssertionError(f"missing embedded JavaScript function: {name}")
    end = rendered_html.find("\n  function ", start + len(marker))
    return rendered_html[start:] if end < 0 else rendered_html[start:end]


class ReaderPacketValidationTests(unittest.TestCase):
    def test_example_packet_is_valid_and_preserves_explicit_orders(self) -> None:
        packet = load_reader_packet(EXAMPLE_PACKET, project_id="reader-demo")
        self.assertEqual(
            packet["theme_order"],
            ["theme-foundations", "theme-applications"],
        )
        self.assertEqual(
            packet["target_order"],
            ["target-main", "target-application"],
        )
        self.assertEqual(
            packet["prerequisite_order"]["target-main"],
            ["def-surface", "result-local"],
        )

    def test_identity_mismatch_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            load_reader_packet(EXAMPLE_PACKET, project_id="another-project")

    def test_dangling_edge_fails(self) -> None:
        packet = example_packet()
        packet["edges"][0]["source"] = "missing-node"
        with self.assertRaisesRegex(ValueError, "dangling"):
            validate_reader_packet(packet)

    def test_prerequisite_cycle_fails(self) -> None:
        packet = example_packet()
        packet["edges"].append(
            {
                **copy.deepcopy(packet["edges"][0]),
                "id": "edge-cycle",
                "source": "target-main",
                "target": "def-surface",
            }
        )
        packet["nodes"][0]["prerequisites"] = ["target-main"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_reader_packet(packet)

    def test_target_and_theme_order_cannot_conflict(self) -> None:
        packet = example_packet()
        packet["target_order"].reverse()
        with self.assertRaisesRegex(ValueError, "concatenated"):
            validate_reader_packet(packet)

    def test_prerequisite_order_must_cover_exact_ancestors(self) -> None:
        packet = example_packet()
        packet["prerequisite_order"]["target-main"] = ["result-local"]
        with self.assertRaisesRegex(ValueError, "prerequisite ancestors"):
            validate_reader_packet(packet)

    def test_exact_original_text_hash_is_enforced(self) -> None:
        packet = example_packet()
        packet["nodes"][0]["formal"]["original_text"] += " changed"
        with self.assertRaisesRegex(ValueError, "does not bind exact text"):
            validate_reader_packet(packet)

    def test_candidate_cannot_be_presented_as_fact(self) -> None:
        packet = example_packet()
        node = next(item for item in packet["nodes"] if item["plane"] == "fact")
        node["provenance"]["source_status"] = "open_candidate"
        with self.assertRaisesRegex(ValueError, "cannot label"):
            validate_reader_packet(packet)

    def test_nonfact_plane_cannot_receive_fact_authority(self) -> None:
        packet = example_packet()
        node = packet["nodes"][0]
        node["provenance"]["truth_status"] = "admitted_fact"
        with self.assertRaisesRegex(ValueError, "must be one of"):
            validate_reader_packet(packet)

    def test_reader_finalize_sidebar_fields_must_be_nonempty(self) -> None:
        for field in ("summary", "intuition", "importance", "reasoning"):
            for invalid in ("", " \t\r\n "):
                with self.subTest(field=field, invalid=repr(invalid)):
                    packet = example_packet()
                    packet["nodes"][0][field] = invalid
                    with self.assertRaisesRegex(
                        ValueError,
                        rf"nodes\[0\]\.{field} must be nonempty",
                    ):
                        validate_reader_packet(packet)

    def test_cross_plane_native_snapshots_are_preserved_and_hash_bound(self) -> None:
        packet = example_packet()
        aggregate_snapshot = copy.deepcopy(packet["source_snapshot"])
        paper_node = next(node for node in packet["nodes"] if node["id"] == "paper-claim")
        audit_edge = next(edge for edge in packet["edges"] if edge["id"] == "edge-audit-paper")
        paper_node["provenance"]["snapshot_id"] = "paper-native-snapshot-v7"
        audit_edge["provenance"]["snapshot_id"] = "audit-native-snapshot-v3"

        validated = validate_reader_packet(packet)
        self.assertEqual(validated["source_snapshot"], aggregate_snapshot)
        self.assertEqual(
            paper_node["provenance"]["snapshot_id"],
            "paper-native-snapshot-v7",
        )
        self.assertEqual(
            audit_edge["provenance"]["snapshot_id"],
            "audit-native-snapshot-v3",
        )

        html, first_meta = render_reader_html(packet)
        self.assertIn("paper-native-snapshot-v7", html)
        self.assertIn("audit-native-snapshot-v3", html)
        self.assertEqual(
            first_meta["reader_finalize"]["source_snapshot_id"],
            aggregate_snapshot["id"],
        )
        self.assertEqual(
            first_meta["reader_finalize"]["source_snapshot_sha256"],
            aggregate_snapshot["sha256"],
        )

        changed = copy.deepcopy(packet)
        changed_audit_edge = next(
            edge for edge in changed["edges"] if edge["id"] == "edge-audit-paper"
        )
        changed_audit_edge["provenance"]["snapshot_id"] = "audit-native-snapshot-v4"
        _, changed_meta = render_reader_html(changed)
        self.assertEqual(changed["source_snapshot"], aggregate_snapshot)
        self.assertNotEqual(first_meta["packet_sha256"], changed_meta["packet_sha256"])

    def test_duplicate_json_key_fails_before_semantic_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "duplicate.json"
            path.write_text(
                '{"schema_version":1,"schema_version":1}\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                load_reader_packet(path)


class ReaderHtmlRenderTests(unittest.TestCase):
    def test_render_is_byte_deterministic_and_self_contained(self) -> None:
        packet = example_packet()
        first, first_meta = render_reader_html(packet)
        second, second_meta = render_reader_html(copy.deepcopy(packet))
        self.assertEqual(first, second)
        self.assertEqual(first_meta, second_meta)
        self.assertIn("deterministic_ranked_barycenter", first)
        self.assertIn("connect-src 'none'", first)
        self.assertIn('id="overview-button"', first)
        self.assertIn('id="all-cards-button"', first)
        self.assertIn('id="layer-menu-button"', first)
        self.assertIn('id="learning-toggle"', first)
        self.assertIn('id="reader-toggle"', first)
        self.assertIn("调整详情栏宽度", first)
        self.assertIn("Resize detail panel", first)
        self.assertIn('data-locale-choice="zh"', first)
        self.assertIn('data-locale-choice="en"', first)
        self.assertIn("previousNestedDisclosure", first)
        self.assertIn("button.isConnected", first)
        self.assertIn("copyIdleZh", first)
        self.assertIn("ensureGraphContentVisible", first)
        self.assertIn("正文字号", first)
        self.assertIn('id="node-control-layer"', first)
        self.assertIn('id="node-context-menu"', first)
        self.assertEqual(first.count('data-context-command="'), 2)
        self.assertIn('data-context-command="maximize-upstream"', first)
        self.assertIn('data-context-command="maximize-downstream"', first)
        self.assertNotIn('data-context-command="complete-path"', first)
        self.assertNotIn('data-context-command="collapse-upstream"', first)
        self.assertNotIn('data-context-command="collapse-downstream"', first)
        self.assertIn('id="undo-sizing-button"', first)
        self.assertIn('id="redo-sizing-button"', first)
        self.assertIn('id="reload-graph-button"', first)
        self.assertEqual(first.count('data-appearance-scheme="'), 2)
        self.assertIn('data-appearance-scheme="faceted"', first)
        self.assertIn('data-appearance-scheme="plaques"', first)
        self.assertIn("cxttap", first)
        self.assertIn("bindTrackpadNavigation", first)
        self.assertIn("cy.panBy", first)
        self.assertIn("minimizedNodeIds", first)
        self.assertIn("sizingUndoStack", first)
        self.assertIn("sizingRedoStack", first)
        self.assertIn("maximizeTargets", first)
        self.assertIn("maximizeAllCards", first)
        self.assertIn("maximizeNodePath", first)
        self.assertIn("toggleNodeMinimized", first)
        self.assertIn("undoSizing", first)
        self.assertIn("redoSizing", first)
        self.assertIn("applyAppearanceScheme", first)
        self.assertIn("selectedId", first)
        for legacy_token in (
            "canvasEdgeIds",
            "canvasRootIds",
            "disclosurePreset",
            "applyAllTargetsDisclosure",
            "applyAllCardsDisclosure",
            "applyNodeFocusDisclosure",
            "directedClosureEdgeIds",
            "toggleNodeSide",
            "setEdgeExpanded",
            "collapseNodeSide",
            "surfaceMode",
            "focusDomainEdgeIds",
            "focusEdgeIds",
            "enterFocusView",
            "exitFocusView",
            "viewMode",
            "localRoot",
            "revealedEdges",
            "localPositions",
            "ensureLocalView",
            "startLocalView",
            "edge-handle",
            "edge-stub-line",
            "node-side-control",
        ):
            self.assertNotIn(legacy_token, first)
        self.assertIn("node-size-toggle", first)
        self.assertIn("node-name-tooltip", first)
        self.assertIn("node.minimized", first)
        self.assertIn("--moonlight: #ffe58a", first)
        self.assertIn("selector: 'node:selected'", first)
        self.assertIn("'outline-color': '#ffe58a'", first)
        self.assertIn('id="selected-node-halo"', first)
        self.assertIn("drop-shadow", first)
        self.assertNotIn("'underlay-color': '#ffe58a'", first)
        self.assertIn("function renderedNodeBox(node)", first)
        self.assertIn("node.renderedOuterWidth()", first)
        self.assertIn("node.renderedOuterHeight()", first)
        self.assertIn('selector: \'edge[layer = "research"]\'', first)
        self.assertIn("'line-dash-pattern': [10, 6]", first)
        self.assertIn("upstream", first)
        self.assertIn("downstream", first)
        self.assertNotIn("Focus prerequisite path", first)
        self.assertNotIn("Expand one level", first)
        self.assertNotIn("Show full path", first)
        self.assertNotIn("Collapse one level", first)
        self.assertIn("reader-grouping", first)
        self.assertIn("Research process", first)
        self.assertIn("Contextual links", first)
        self.assertIn("Exact original text", first)
        self.assertIn("target-arrow-shape': 'tee'", first)
        self.assertNotIn("@@CHALXIUS_", first)
        self.assertNotIn('class="header-state"', first)
        self.assertEqual(first_meta["renderer_revision"], "chalxius-reader-html-12")
        expected_packet_sha256 = sha256_bytes(canonical_json_bytes(packet))
        self.assertEqual(first_meta["packet_sha256"], expected_packet_sha256)
        self.assertEqual(
            first_meta["reader_finalize"],
            {
                "schema_version": 1,
                "status": "ready",
                "scope": "presentation_readiness_only",
                "source_snapshot_id": packet["source_snapshot"]["id"],
                "source_snapshot_sha256": packet["source_snapshot"]["sha256"],
                "sidebar_complete_count": len(packet["nodes"]),
                "node_count": len(packet["nodes"]),
                "packet_sha256": expected_packet_sha256,
                "truth_effect": "none",
            },
        )
        self.assertIn('"reader_finalize":{', first)
        self.assertEqual(first_meta["assets"]["tabler_icons"]["version"], "3.45.0")
        self.assertEqual(first_meta["assets"]["tabler_icons"]["license"], "MIT")
        self.assertEqual(len(first_meta["assets"]["tabler_icons"]["source_sha256"]), 15)

        collector = _DependencyCollector()
        collector.feed(first)
        self.assertTrue(collector.references)
        self.assertIn(("a", "href", "#map-detail"), collector.references)
        self.assertIn(("use", "href", "#reader-icon-search"), collector.references)
        self.assertIn(("use", "href", "#reader-icon-refresh"), collector.references)
        self.assertTrue(
            all(reference.startswith("#") for _, _, reference in collector.references)
        )

    def test_revision_eleven_global_node_sizing_contract_is_embedded(self) -> None:
        html, _ = render_reader_html(example_packet())
        all_targets = javascript_function_source(html, "maximizeTargets")
        all_cards = javascript_function_source(html, "maximizeAllCards")
        node_path = javascript_function_source(html, "maximizeNodePath")
        closure = javascript_function_source(html, "directedClosureNodeIds")
        incident = javascript_function_source(html, "incidentEdges")
        commit = javascript_function_source(html, "commitSizing")
        undo = javascript_function_source(html, "undoSizing")
        redo = javascript_function_source(html, "redoSizing")
        visibility = javascript_function_source(html, "setVisibility")

        self.assertIn("state.minimizedNodeIds", all_targets)
        self.assertIn("const targets = new Set(eligibleTargetIds())", all_targets)
        self.assertIn("if (targets.has(nodeId)) next.delete(nodeId)", all_targets)
        self.assertIn("commitSizing", all_targets)
        self.assertIn("state.minimizedNodeIds", all_cards)
        self.assertIn("commitSizing", all_cards)
        for global_action in (all_targets, all_cards):
            self.assertNotIn("state.selectedId = null", global_action)
            self.assertNotIn("state.pinned.clear()", global_action)
            self.assertNotIn("applyCanonicalPositions", global_action)
            self.assertNotIn(".position(", global_action)

        self.assertIn("directedClosureNodeIds(nodeId, 'upstream')", node_path)
        self.assertIn("directedClosureNodeIds(nodeId, 'downstream')", node_path)
        self.assertIn("commitSizing", node_path)
        self.assertIn("showNodeDetail(nodeId)", node_path)
        self.assertIn("incidentEdges(current, direction)", closure)
        self.assertIn("incomingEdgesByNode.get(nodeId)", incident)
        self.assertIn("outgoingEdgesByNode.get(nodeId)", incident)
        self.assertIn("const result = new Set([nodeId])", closure)
        self.assertIn("result.has(neighborId)", closure)
        self.assertIn("state.sizingUndoStack", commit)
        self.assertIn("state.sizingRedoStack", commit)
        self.assertIn("state.sizingUndoStack", undo)
        self.assertIn("state.sizingRedoStack", undo)
        self.assertIn("state.sizingUndoStack", redo)
        self.assertIn("state.sizingRedoStack", redo)
        self.assertIn("state.sizingRedoStack.length = 0", commit)
        self.assertIn("if (sameSet(state.minimizedNodeIds, next)) return false", commit)

        controls = javascript_function_source(html, "renderNodeControls")
        self.assertIn("node-size-toggle", controls)
        self.assertIn("state.minimizedNodeIds.has(node.id)", controls)
        self.assertIn("bindNodeSizeToggle(button, node.id)", controls)
        self.assertIn("svgIcon(minimized ? 'expand' : 'collapse')", controls)
        self.assertEqual(
            controls.count("button.append(svgIcon(minimized ? 'expand' : 'collapse'))"),
            1,
        )
        self.assertNotIn("appearanceScheme", controls)
        self.assertNotIn("button.append(svgIcon('expand'))", controls)
        self.assertNotIn("direction", controls)
        self.assertNotIn("edge-handle", controls)

        self.assertIn("for (const edge of packet.edges)", visibility)
        self.assertIn("edgeEligible(edge)", visibility)
        self.assertNotIn("activeEdgeIds", visibility)
        self.assertNotIn("canvasEdgeIds", visibility)
        self.assertIn("cy.on('dbltap'", html)
        self.assertIn("maximizeNodePath(event.target.id())", html)
        self.assertEqual(html.count("maximizeNodePath("), 2)
        self.assertIn("maximizeThemePath(event.target.data('themeId'))", html)
        theme_path = javascript_function_source(html, "maximizeThemePath")
        self.assertIn("theme.target_ids.filter(nodeEligible)", theme_path)
        self.assertIn("directedClosureNodeIds(targetId, 'upstream')", theme_path)
        self.assertIn("directedClosureNodeIds(targetId, 'downstream')", theme_path)
        self.assertEqual(theme_path.count("commitSizing("), 1)
        self.assertIn("showThemeDetail(themeId)", theme_path)
        self.assertNotIn("reader-grouping", theme_path)
        self.assertNotIn('id="back-to-overview-button"', html)

        grouping_style_start = html.index('selector: \'edge[kind = "reader-grouping"]\'')
        grouping_style_end = html.index("selector: 'edge.compact-edge'", grouping_style_start)
        grouping_style = html[grouping_style_start:grouping_style_end]
        self.assertIn("'curve-style': 'bezier'", grouping_style)
        self.assertNotIn("'curve-style': 'taxi'", grouping_style)
        self.assertNotIn("'taxi-direction'", grouping_style)
        self.assertNotIn("'taxi-turn'", grouping_style)
        self.assertIn("'line-style': 'dashed'", grouping_style)
        self.assertIn("'target-arrow-shape': 'none'", grouping_style)

        crossing_reduction = javascript_function_source(html, "reduceEdgeCrossings")
        crossing_score = javascript_function_source(html, "layoutCrossingScore")
        crossing_comparison = javascript_function_source(html, "crossingScoreIsBetter")
        canonical_positions = javascript_function_source(html, "applyCanonicalPositions")
        self.assertIn("const CROSSING_REDUCTION_SWEEPS = 8", html)
        self.assertIn("const CROSSING_REDUCTION_EDGE_LIMIT = 1200", html)
        self.assertIn("edgeWeight", crossing_reduction)
        self.assertIn("weightedPosition", crossing_reduction)
        self.assertIn("towardLowerRanks", crossing_reduction)
        self.assertIn("packetIndex", crossing_reduction)
        self.assertIn("properCrossing", crossing_score)
        self.assertIn("segments.length > CROSSING_REDUCTION_EDGE_LIMIT", crossing_score)
        self.assertIn("candidate.crossings < incumbent.crossings", crossing_comparison)
        self.assertIn("restoreGroupOrder(groups, bestOrder)", crossing_reduction)
        self.assertIn("baselineCrossings", crossing_reduction)
        self.assertIn("reduceEdgeCrossings(groups, ranks)", canonical_positions)
        self.assertIn("layoutBaselineCrossings", canonical_positions)
        self.assertIn("layoutFinalCrossings", canonical_positions)
        self.assertNotIn("state.minimizedNodeIds", crossing_reduction)

        self.assertIn('.detail-panel mjx-container[jax="SVG"] { font-size: 1.08em; }', html)
        self.assertIn('.detail-panel mjx-container[jax="SVG"] > svg {', html)
        self.assertIn("width: auto", html)
        self.assertIn("height: auto", html)
        self.assertIn("font: 0.82em/1.55", html)
        self.assertNotIn("font: 0.73rem/1.5", html)

        context = javascript_function_source(html, "runContextCommand")
        self.assertIn("maximizeDirection(nodeId, 'upstream')", context)
        self.assertIn("maximizeDirection(nodeId, 'downstream')", context)
        self.assertNotIn("collapse", context)

        layer_refresh = javascript_function_source(html, "refreshForLayerChange")
        self.assertIn("refreshSurface({preserveViewport: true})", layer_refresh)
        self.assertNotIn("commitSizing", layer_refresh)
        self.assertNotIn("minimizedNodeIds =", layer_refresh)
        self.assertIn("document.activeElement.isContentEditable", html)
        self.assertIn("if (event.shiftKey) redoSizing()", html)
        self.assertIn("else undoSizing()", html)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for Reader layout behavior QA")
    def test_ranked_crossing_reduction_improves_or_preserves_baseline(self) -> None:
        html, _ = render_reader_html(example_packet())
        function_names = (
            "cloneGroupOrder",
            "restoreGroupOrder",
            "layoutCrossingScore",
            "crossingScoreIsBetter",
            "reduceEdgeCrossings",
        )
        functions = "\n".join(
            javascript_function_source(html, name).strip() for name in function_names
        )
        fixtures = [
            {
                "name": "simple-crossing",
                "nodes": ["a", "b", "c", "d"],
                "ranks": {"a": 0, "b": 0, "c": 1, "d": 1},
                "groups": [[0, ["a", "b"]], [1, ["c", "d"]]],
                "edges": [
                    {"source": "a", "target": "d", "category": "prerequisite"},
                    {"source": "b", "target": "c", "category": "prerequisite"},
                ],
            },
            {
                "name": "xy-public-regression-shape",
                "nodes": [
                    "research-question",
                    "legacy-graph",
                    "verification-pattern",
                    "revocation-history",
                    "current-audit-gap",
                    "author-confirmation",
                    "target-boundary",
                    "target-potential",
                    "prospective-planes",
                    "prospective-reader",
                ],
                "ranks": {
                    "research-question": 0,
                    "legacy-graph": 1,
                    "verification-pattern": 2,
                    "revocation-history": 0,
                    "current-audit-gap": 0,
                    "author-confirmation": 0,
                    "target-boundary": 1,
                    "target-potential": 3,
                    "prospective-planes": 0,
                    "prospective-reader": 0,
                },
                "groups": [
                    [
                        0,
                        [
                            "research-question",
                            "revocation-history",
                            "current-audit-gap",
                            "author-confirmation",
                            "prospective-planes",
                            "prospective-reader",
                        ],
                    ],
                    [1, ["legacy-graph", "target-boundary"]],
                    [2, ["verification-pattern"]],
                    [3, ["target-potential"]],
                ],
                "edges": [
                    {"source": "research-question", "target": "legacy-graph", "category": "prerequisite"},
                    {"source": "legacy-graph", "target": "verification-pattern", "category": "prerequisite"},
                    {"source": "current-audit-gap", "target": "target-boundary", "category": "prerequisite"},
                    {"source": "author-confirmation", "target": "target-boundary", "category": "prerequisite"},
                    {"source": "verification-pattern", "target": "target-potential", "category": "prerequisite"},
                    {"source": "revocation-history", "target": "target-potential", "category": "prerequisite"},
                    {"source": "target-boundary", "target": "target-potential", "category": "prerequisite"},
                    {"source": "current-audit-gap", "target": "legacy-graph", "category": "conflict"},
                    {"source": "prospective-planes", "target": "target-potential", "category": "repair"},
                    {"source": "prospective-reader", "target": "target-potential", "category": "support"},
                ],
            },
        ]
        harness = f"""
const CROSSING_REDUCTION_SWEEPS = 8;
const CROSSING_REDUCTION_EDGE_LIMIT = 1200;
let packet;
let readerNodeIds;
let nodeById;
{functions}
const fixtures = {json.dumps(fixtures, separators=(",", ":"))};
const results = fixtures.map((fixture) => {{
  packet = {{edges: fixture.edges}};
  readerNodeIds = fixture.nodes;
  nodeById = new Map(fixture.nodes.map((nodeId, packetIndex) => [nodeId, {{packetIndex}}]));
  const ranks = new Map(Object.entries(fixture.ranks).map(([nodeId, rank]) => [nodeId, rank]));
  const groups = new Map(fixture.groups.map(([rank, nodeIds]) => [rank, [...nodeIds]]));
  return {{name: fixture.name, ...reduceEdgeCrossings(groups, ranks)}};
}});
process.stdout.write(JSON.stringify(results));
"""
        completed = subprocess.run(
            [shutil.which("node"), "-e", harness],
            check=True,
            capture_output=True,
            text=True,
        )
        results = {item["name"]: item for item in json.loads(completed.stdout)}
        self.assertEqual(results["simple-crossing"]["baselineCrossings"], 1)
        self.assertEqual(results["simple-crossing"]["finalCrossings"], 0)
        self.assertEqual(results["xy-public-regression-shape"]["baselineCrossings"], 1)
        self.assertEqual(results["xy-public-regression-shape"]["finalCrossings"], 1)
        for result in results.values():
            self.assertTrue(result["evaluated"])
            self.assertLessEqual(result["finalCrossings"], result["baselineCrossings"])

    def test_revision_eleven_click_anchor_halo_and_plaque_contract_is_embedded(self) -> None:
        html, _ = render_reader_html(example_packet())
        anchor = javascript_function_source(html, "nodeSizeControlAnchor")
        control_size = javascript_function_source(html, "nodeSizeControlSize")
        binding = javascript_function_source(html, "bindNodeSizeToggle")
        sizing = javascript_function_source(html, "applyNodeSizingClasses")
        controls = javascript_function_source(html, "syncNodeControls")
        control_render = javascript_function_source(html, "renderNodeControls")
        hover_sync = javascript_function_source(html, "scheduleNodeHoverSync")
        halo = javascript_function_source(html, "syncSelectedNodeHalo")

        self.assertIn("const NODE_SIZE_CONTROL_X_RATIO = 0.29", html)
        self.assertIn("const NODE_SIZE_CONTROL_Y_RATIO = 0.5", html)
        self.assertIn("const NODE_SIZE_CONTROL_CARD_HEIGHT_RATIO = 0.45", html)
        self.assertIn(
            "bounds.x1 + (bounds.x2 - bounds.x1) * NODE_SIZE_CONTROL_X_RATIO",
            anchor,
        )
        self.assertIn(
            "bounds.y1 + (bounds.y2 - bounds.y1) * NODE_SIZE_CONTROL_Y_RATIO",
            anchor,
        )
        self.assertNotIn("minimized", anchor)
        self.assertNotIn("NODE_SIZE_CONTROL_INSET", html)
        self.assertIn(
            "compact.height * cy.zoom() * NODE_SIZE_CONTROL_CARD_HEIGHT_RATIO",
            control_size,
        )
        self.assertNotIn("button.addEventListener('pointerdown'", binding)
        self.assertNotIn("button.addEventListener('mousedown'", binding)
        self.assertIn("button.addEventListener('click'", binding)
        self.assertIn("event.preventDefault()", binding)
        self.assertIn("event.stopPropagation()", binding)
        self.assertIn("toggleNodeMinimized(nodeId)", binding)
        self.assertIn("state.hoveredControlNodeId = node.id", control_render)
        self.assertIn("scheduleNodeHoverSync()", control_render)
        self.assertIn("showNodeNameTooltip(node.id)", control_render)
        self.assertIn("state.hoveredCanvasNodeId", hover_sync)
        self.assertIn("state.hoveredControlNodeId", hover_sync)
        self.assertIn("state.hoveredNodeId = nextHoveredId", hover_sync)
        self.assertIn("updateEdgeDensity()", hover_sync)
        self.assertIn("showNodeNameTooltip(nextHoveredId)", hover_sync)
        self.assertIn("hideNodeNameTooltip()", hover_sync)
        self.assertIn("cy.on('mouseover', 'node[kind = \"reader-node\"]'", html)
        self.assertIn("cy.on('mouseout', 'node[kind = \"reader-node\"]'", html)
        for forbidden_button_drag_token in (
            "pointermove",
            "mousemove",
            "setPointerCapture",
            "state.pinned",
            ".position(",
            "suppressClick",
            "NODE_SIZE_CONTROL_DRAG_THRESHOLD",
        ):
            self.assertNotIn(forbidden_button_drag_token, binding)
        self.assertNotIn("bindNodeSizeToggleGesture", html)
        self.assertNotIn("NODE_SIZE_CONTROL_DRAG_THRESHOLD", html)
        self.assertNotIn('data-dragging="yes"', html)
        self.assertNotIn("cursor: grab;", html)
        self.assertNotIn("cursor: grabbing;", html)
        self.assertIn("cursor: pointer;", html)
        self.assertIn("touch-action: manipulation", html)
        self.assertIn("oldAnchor: nodeSizeControlAnchor(node)", sizing)
        self.assertIn("transition.oldAnchor.x - newAnchor.x", sizing)
        self.assertIn("transition.oldAnchor.y - newAnchor.y", sizing)
        self.assertIn("transition.node.position(compensated)", sizing)
        self.assertNotIn("animate(", sizing)
        self.assertIn("cy.on('dragfree', 'node'", html)
        self.assertIn("state.pinned.set(node.id(), {...node.position()})", html)
        self.assertIn("nodeSizeControlSize(node)", controls)
        self.assertIn("nodeSizeControlAnchor(node)", controls)
        self.assertIn("minZoom: NODE_CONTROL_SAFE_MIN_ZOOM", html)
        self.assertIn("const NODE_CONTROL_SAFE_MIN_ZOOM = 0.36", html)
        self.assertIn("'arrow-scale': 1.65", html)
        self.assertIn("'mid-target-arrow-shape': 'triangle'", html)
        self.assertIn("'mid-target-arrow-shape': 'vee'", html)
        self.assertIn("'mid-target-arrow-shape': 'diamond'", html)
        self.assertIn("'mid-target-arrow-shape': 'tee'", html)
        self.assertIn("'mid-target-arrow-shape': 'none'", html)
        self.assertNotIn("preferredX = minimized", controls)
        self.assertIn("syncSelectedNodeHalo()", controls)
        self.assertIn("state.appearanceScheme", halo)
        self.assertIn("nodeData.reader_role", halo)
        self.assertIn("dom.selectedNodeHalo.hidden = false", halo)
        self.assertIn('id="selected-node-halo"', html)
        self.assertIn("pointer-events: none", html)
        self.assertIn("drop-shadow", html)
        self.assertIn("clip-path: polygon", html)
        self.assertNotIn("'underlay-color': '#ffe58a'", html)
        self.assertNotIn("'border-style': 'double'", html)
        self.assertIn("'border-opacity': 0.34", html)
        self.assertIn("'outline-opacity': 0.92", html)
        self.assertIn("node.shape-plaques.minimized", html)

    def test_revision_eleven_label_balance_and_control_geometry_are_safe(self) -> None:
        html, _ = render_reader_html(example_packet())
        self.assertIn("'text-justification': 'left'", html)
        self.assertEqual(html.count("'text-justification': 'left'"), 1)
        minimum_zoom = 0.36
        maximum_zoom = 3.2
        x_ratio = 0.29
        y_ratio = 0.5
        height_ratio = 0.45
        minimum_control = 11.0
        maximum_control = 20.0
        maximum_content_bias_ratio = 0.03
        role_geometry = {
            "target": {
                "compact": (78.0, 46.0),
                "full": (236.0 + 18.0, 100.0 + 18.0),
                "text_max": 106.0,
                "text_margin": 18.0,
            },
            "definition": {
                "compact": (80.0, 44.0),
                "full": (228.0 + 18.0, 92.0 + 18.0),
                "text_max": 102.0,
                "text_margin": 18.0,
            },
            "result": {
                "compact": (76.0, 44.0),
                "full": (220.0 + 18.0, 88.0 + 18.0),
                "text_max": 98.0,
                "text_margin": 17.0,
            },
            "explanation": {
                "compact": (74.0, 44.0),
                "full": (208.0 + 18.0, 84.0 + 18.0),
                "text_max": 92.0,
                "text_margin": 17.0,
            },
        }
        for role, geometry in role_geometry.items():
            compact_width, compact_height = geometry["compact"]
            control_size = max(
                minimum_control,
                min(
                    maximum_control,
                    compact_height * minimum_zoom * height_ratio,
                ),
            )
            rendered_width = compact_width * minimum_zoom
            rendered_height = compact_height * minimum_zoom
            anchor_x = rendered_width * x_ratio
            anchor_y = rendered_height * y_ratio
            for appearance in ("faceted", "plaques"):
                with self.subTest(role=role, appearance=appearance):
                    self.assertIn(
                        f'node.shape-{appearance}[role = "{role}"]',
                        html,
                    )
                    self.assertGreaterEqual(anchor_x - control_size / 2, 2.0)
                    self.assertGreaterEqual(
                        rendered_width - anchor_x - control_size / 2,
                        2.0,
                    )
                    self.assertGreaterEqual(anchor_y - control_size / 2, 2.0)
                    self.assertGreaterEqual(
                        rendered_height - anchor_y - control_size / 2,
                        2.0,
                    )

            full_width, _ = geometry["full"]
            normal_control_size = max(
                minimum_control,
                min(maximum_control, compact_height * height_ratio),
            )
            control_right = full_width * x_ratio + normal_control_size / 2
            label_left = (
                full_width / 2
                + geometry["text_margin"]
                - geometry["text_max"] / 2
            )
            self.assertGreaterEqual(label_left - control_right, 8.0)
            for zoom in (minimum_zoom, 1.0, maximum_zoom):
                rendered_full_width = full_width * zoom
                rendered_control_size = max(
                    minimum_control,
                    min(
                        maximum_control,
                        compact_height * zoom * height_ratio,
                    ),
                )
                control_left = (
                    rendered_full_width * x_ratio
                    - rendered_control_size / 2
                )
                label_right = (
                    full_width / 2
                    + geometry["text_margin"]
                    + geometry["text_max"] / 2
                ) * zoom
                content_center = (control_left + label_right) / 2
                content_bias_ratio = abs(
                    content_center - rendered_full_width / 2
                ) / rendered_full_width
                self.assertLessEqual(
                    content_bias_ratio,
                    maximum_content_bias_ratio,
                )
            self.assertIn(
                f"'text-max-width': {int(geometry['text_max'])}, "
                f"'text-margin-x': {int(geometry['text_margin'])}",
                html,
            )

    def test_revision_eleven_reload_is_click_only_and_offline(self) -> None:
        html, _ = render_reader_html(example_packet())
        binding = javascript_function_source(html, "bindEvents")
        self.assertIn('id="reload-graph-button"', html)
        self.assertEqual(
            binding.count("dom.reloadGraph.addEventListener('click'"),
            1,
        )
        self.assertIn(
            "dom.reloadGraph.addEventListener('click', () => window.location.reload())",
            binding,
        )
        self.assertNotIn("fetch(", binding)
        self.assertNotIn("XMLHttpRequest", binding)
        self.assertNotIn("WebSocket", binding)
        self.assertNotIn("EventSource", binding)

    def test_revision_eleven_reader_has_no_persistence_or_writeback_surface(self) -> None:
        source = "\n".join(
            (SKILL_ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                "assets/reader_html_app.js",
                "assets/reader_html_template.html",
                "scripts/mathgraph/reader_html.py",
            )
        )
        for forbidden in (
            "localStorage",
            "sessionStorage",
            "indexedDB",
            "showSaveFilePicker",
            "showDirectoryPicker",
            "FileSystemWritableFileStream",
            "sendBeacon",
            "XMLHttpRequest",
            "WebSocket",
            "EventSource",
            "fetch(",
            "createObjectURL",
            "showOpenFilePicker",
            'download="',
        ):
            self.assertNotIn(forbidden, source)

    def test_embedded_packet_cannot_break_out_of_script_element(self) -> None:
        packet = example_packet()
        packet["title"] = "</script><script>window.PWNED=true</script>"
        text = "</script><script>window.PWNED=true</script>"
        packet["nodes"][0]["formal"]["original_text"] = text
        packet["nodes"][0]["provenance"]["original_text_sha256"] = sha256_bytes(
            text.encode("utf-8")
        )
        html, _ = render_reader_html(packet)
        self.assertNotIn("<script>window.PWNED=true</script>", html)
        self.assertIn("\\u003c/script\\u003e", html)

    def test_warnings_and_unresolved_items_do_not_block_rendering(self) -> None:
        packet = example_packet()
        self.assertFalse(packet["audit"]["current_ok"])
        html, _ = render_reader_html(packet)
        self.assertIn(packet["audit"]["summary"], html)


class ReaderHtmlExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "project"
        self.store = MathGraphStore(self.root)
        self.store.initialize(
            project_id="reader-demo",
            title="Reader demo",
            workflow_evidence_version=4,
            reasoning_mode="auto",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_export_uses_one_fixed_overwritten_output(self) -> None:
        packet_path = write_packet(self.root, example_packet())
        first = export_reader_html(self.store, packet_path)
        output = Path(first["output"])
        first_bytes = output.read_bytes()
        second = export_reader_html(self.store, packet_path)
        self.assertEqual(first["output"], second["output"])
        self.assertEqual(first["html_sha256"], second["html_sha256"])
        self.assertEqual(first_bytes, output.read_bytes())
        self.assertEqual(
            output,
            (self.root / FIXED_OUTPUT_RELPATH).resolve(),
        )
        self.assertEqual(
            [path.resolve() for path in (self.root / "visualizations").iterdir()],
            [output],
        )
        self.assertEqual(first["truth_effect"], "none")
        self.assertEqual(first["network_runtime"], "disabled")
        self.assertEqual(first["renderer_revision"], "chalxius-reader-html-12")
        self.assertEqual(first["reader_finalize"]["status"], "ready")
        self.assertEqual(first["reader_finalize"]["scope"], "presentation_readiness_only")
        self.assertEqual(
            first["reader_finalize"]["sidebar_complete_count"],
            first["reader_finalize"]["node_count"],
        )
        self.assertEqual(
            first["reader_finalize"]["packet_sha256"],
            first["packet_sha256"],
        )

    def test_invalid_replacement_leaves_fixed_output_unchanged(self) -> None:
        packet_path = write_packet(self.root, example_packet())
        receipt = export_reader_html(self.store, packet_path)
        output = Path(receipt["output"])
        original = output.read_bytes()

        invalid = example_packet()
        invalid["nodes"][0]["summary"] = " \t\r\n "
        write_packet(self.root, invalid)
        with self.assertRaisesRegex(ValueError, r"nodes\[0\]\.summary must be nonempty"):
            export_reader_html(self.store, packet_path)

        self.assertEqual(output.read_bytes(), original)
        self.assertEqual(sha256_bytes(output.read_bytes()), receipt["html_sha256"])

    def test_export_rejects_symlink_output_directory(self) -> None:
        packet_path = write_packet(self.root, example_packet())
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        (self.root / "visualizations").symlink_to(
            outside,
            target_is_directory=True,
        )
        with self.assertRaisesRegex(ValueError, "may not be a symlink"):
            export_reader_html(self.store, packet_path)

    def test_cli_command_is_main_operator_only_and_has_fixed_output(self) -> None:
        for role in ("main", "operator"):
            self.assertIn("export-reader-html", allowed_commands(role))
        for role in ("worker", "verifier", "gateway", "host", "paper-auditor"):
            self.assertNotIn("export-reader-html", allowed_commands(role))

        args = build_parser().parse_args(
            [
                "--root",
                str(self.root),
                "--role",
                "main",
                "export-reader-html",
                "--packet",
                str(EXAMPLE_PACKET),
            ]
        )
        self.assertEqual(args.command, "export-reader-html")
        self.assertFalse(hasattr(args, "output"))
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(
                [
                    "--root",
                    str(self.root),
                    "--role",
                    "main",
                    "export-reader-html",
                    "--packet",
                    str(EXAMPLE_PACKET),
                ]
            )
        self.assertEqual(code, 0, stderr.getvalue())
        receipt = json.loads(stdout.getvalue())
        self.assertEqual(
            receipt["output"],
            str((self.root / FIXED_OUTPUT_RELPATH).resolve()),
        )
        self.assertTrue((self.root / FIXED_OUTPUT_RELPATH).is_file())


if __name__ == "__main__":
    unittest.main()
