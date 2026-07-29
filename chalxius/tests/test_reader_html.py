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
        self.assertIn("deterministic_compact_radial_core_layers", first)
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
        self.assertEqual(first_meta["renderer_revision"], "chalxius-reader-html-17")
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
        geometry_score = javascript_function_source(html, "layoutGeometryScore")
        crossing_comparison = javascript_function_source(html, "crossingScoreIsBetter")
        compact_coordinates = javascript_function_source(html, "compactRadialCoordinates")
        canonical_positions = javascript_function_source(html, "applyCanonicalPositions")
        core_ranks = javascript_function_source(html, "coreDistanceRanks")
        radial_radii = javascript_function_source(html, "radialRingRadii")
        radial_coordinates = javascript_function_source(html, "radialLayoutCoordinates")
        layout_footprint = javascript_function_source(html, "layoutNodeFootprint")
        self.assertIn("const CROSSING_REDUCTION_SWEEPS = 8", html)
        self.assertIn("const CROSSING_REDUCTION_EDGE_LIMIT = 1200", html)
        self.assertIn("const CROSSING_REFINEMENT_PASSES = 2", html)
        self.assertIn("const CROSSING_REFINEMENT_CANDIDATE_LIMIT = 48", html)
        self.assertIn("edgeWeight", crossing_reduction)
        self.assertIn("weightedVectorX", crossing_reduction)
        self.assertIn("weightedVectorY", crossing_reduction)
        self.assertIn("circularPosition", crossing_reduction)
        self.assertIn("towardLowerRanks", crossing_reduction)
        self.assertIn("packetIndex", crossing_reduction)
        self.assertIn("layoutGeometryScore", crossing_score)
        self.assertIn("radialLayoutCoordinates(groups)", crossing_score)
        self.assertIn("properCrossing", geometry_score)
        self.assertIn("segments.length > CROSSING_REDUCTION_EDGE_LIMIT", geometry_score)
        self.assertIn("maximumEdgeLength", geometry_score)
        self.assertIn("totalEdgeLength", geometry_score)
        self.assertIn("collisionCount", geometry_score)
        self.assertIn("minimumEdgeClearance", geometry_score)
        self.assertIn("edgeClearanceViolationCount", geometry_score)
        self.assertIn("RADIAL_VISIBLE_EDGE_GAP", geometry_score)
        self.assertIn("'crossings'", crossing_comparison)
        self.assertIn("'collisionCount'", crossing_comparison)
        self.assertIn("'maximumEdgeLength'", crossing_comparison)
        self.assertIn("'weightedEdgeLength'", crossing_comparison)
        self.assertIn("restoreGroupOrder(groups, bestOrder)", crossing_reduction)
        self.assertIn("refinementCandidates < CROSSING_REFINEMENT_CANDIDATE_LIMIT", crossing_reduction)
        self.assertIn("const nextIndex = (index + 1) % ids.length", crossing_reduction)
        self.assertIn("if (considerCurrentOrder())", crossing_reduction)
        self.assertIn("baselineCrossings", crossing_reduction)
        self.assertIn("reduceEdgeCrossings(groups, ranks)", canonical_positions)
        self.assertIn("layoutBaselineCrossings", canonical_positions)
        self.assertIn("layoutFinalCrossings", canonical_positions)
        self.assertIn("const ranks = coreDistanceRanks()", canonical_positions)
        self.assertIn("const compactLayout = compactRadialCoordinates(groups, ranks)", canonical_positions)
        self.assertIn("layoutFinalMaximumEdgeLength", canonical_positions)
        self.assertIn("layoutFinalTotalEdgeLength", canonical_positions)
        self.assertIn("layoutMinimumEdgeClearance", canonical_positions)
        self.assertIn("layoutEdgeClearanceViolations", canonical_positions)
        self.assertIn("RADIAL_THEME_MIN_RADIUS", canonical_positions)
        self.assertIn("packet.target_order", core_ranks)
        self.assertIn("ranks.set(targetId, 0)", core_ranks)
        self.assertIn("neighbors.get(edge.source).push(edge.target)", core_ranks)
        self.assertIn("RADIAL_TARGET_MIN_RADIUS", radial_radii)
        self.assertIn("RADIAL_FIRST_RING_SPACING", radial_radii)
        self.assertIn("RADIAL_OUTER_RING_SPACING", radial_radii)
        self.assertIn("RADIAL_NODE_ARC_SPACING", radial_radii)
        self.assertIn("layoutNodeFootprint", radial_radii)
        self.assertIn("previousMaximumHalfWidth", radial_radii)
        self.assertIn("currentMaximumHalfWidth", radial_radii)
        self.assertIn("maximumHeight + RADIAL_VISIBLE_EDGE_GAP + RADIAL_LAYOUT_SPACING_MARGIN", radial_radii)
        self.assertIn("state.minimizedNodeIds.has(nodeId)", layout_footprint)
        self.assertIn("COMPACT_LAYOUT_NODE_FOOTPRINTS", layout_footprint)
        self.assertIn("FULL_LAYOUT_NODE_FOOTPRINTS", layout_footprint)
        self.assertIn("const RADIAL_VISIBLE_EDGE_GAP = 72", html)
        self.assertIn("const RADIAL_LAYOUT_SPACING_MARGIN = 12", html)
        self.assertIn("definition: {width: 246, height: 110}", html)
        self.assertIn("result: {width: 238, height: 106}", html)
        self.assertIn("explanation: {width: 226, height: 102}", html)
        self.assertIn("RADIAL_RING_PHASE", radial_coordinates)
        self.assertIn("rank * RADIAL_RING_PHASE", radial_coordinates)
        self.assertIn("phaseVectorX", radial_coordinates)
        self.assertIn("desiredBaseAngle", radial_coordinates)
        self.assertIn("Math.cos(angle) * radius", radial_coordinates)
        self.assertIn("Math.sin(angle) * radius", radial_coordinates)
        self.assertIn("RADIAL_RELAXATION_ITERATIONS", compact_coordinates)
        self.assertIn("RADIAL_RING_REPULSION", compact_coordinates)
        self.assertIn("RADIAL_REFINEMENT_BLEND_FACTORS", compact_coordinates)
        self.assertIn("candidateScore.crossings > baselineScore.crossings", compact_coordinates)
        self.assertIn("candidateScore.collisionCount > baselineScore.collisionCount", compact_coordinates)
        self.assertIn("candidateScore.edgeClearanceViolationCount", compact_coordinates)
        self.assertIn("candidateScore.minimumEdgeClearance", compact_coordinates)
        self.assertIn("candidateScore.totalEdgeLength > baselineScore.totalEdgeLength", compact_coordinates)
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
    def test_compact_radial_layout_preserves_crossings_and_shortens_edges(self) -> None:
        html, _ = render_reader_html(example_packet())
        function_names = (
            "cloneGroupOrder",
            "restoreGroupOrder",
            "layoutNodeFootprint",
            "radialRingRadii",
            "wrapLayoutAngle",
            "radialLayoutCoordinates",
            "layoutCollisionRadius",
            "layoutNodeBoundaryExtent",
            "layoutNodeBoundaryGap",
            "layoutGeometryScore",
            "layoutCrossingScore",
            "crossingScoreIsBetter",
            "reduceEdgeCrossings",
            "compactRadialCoordinates",
        )
        functions = "\n".join(
            javascript_function_source(html, name).strip() for name in function_names
        )
        fixtures = [
            {
                "name": "simple-crossing",
                "nodes": ["a", "b", "c", "x", "y", "z"],
                "ranks": {"a": 0, "b": 0, "c": 0, "x": 1, "y": 1, "z": 1},
                "groups": [[0, ["a", "b", "c"]], [1, ["x", "y", "z"]]],
                "edges": [
                    {"source": "x", "target": "c", "category": "prerequisite"},
                    {"source": "y", "target": "a", "category": "prerequisite"},
                    {"source": "z", "target": "b", "category": "prerequisite"},
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
const CROSSING_REFINEMENT_PASSES = 2;
const CROSSING_REFINEMENT_CANDIDATE_LIMIT = 48;
const RADIAL_START_ANGLE = Math.PI;
const RADIAL_RING_PHASE = Math.PI * (3 - Math.sqrt(5));
const RADIAL_TARGET_MIN_RADIUS = 170;
const RADIAL_FIRST_RING_SPACING = 236;
const RADIAL_OUTER_RING_SPACING = 158;
const RADIAL_TARGET_ARC_SPACING = 330;
const RADIAL_NODE_ARC_SPACING = 176;
const RADIAL_VISIBLE_EDGE_GAP = 72;
const RADIAL_LAYOUT_SPACING_MARGIN = 12;
const RADIAL_RELAXATION_ITERATIONS = 72;
const RADIAL_RELAXATION_NODE_LIMIT = 320;
const RADIAL_RELAXATION_START_STEP = 0.14;
const RADIAL_RELAXATION_END_STEP = 0.025;
const RADIAL_SEED_TETHER = 0.032;
const RADIAL_RING_REPULSION = 1.7;
const RADIAL_REFINEMENT_BLEND_FACTORS = Object.freeze([1, 0.8, 0.6, 0.4, 0.2]);
const FULL_LAYOUT_NODE_FOOTPRINTS = Object.freeze({{
  target: {{width: 254, height: 118}},
  definition: {{width: 246, height: 110}},
  result: {{width: 238, height: 106}},
  explanation: {{width: 226, height: 102}}
}});
const COMPACT_LAYOUT_NODE_FOOTPRINTS = Object.freeze({{
  target: {{width: 78, height: 46}},
  definition: {{width: 80, height: 44}},
  result: {{width: 76, height: 44}},
  explanation: {{width: 74, height: 44}}
}});
let packet;
let readerNodeIds;
let nodeById;
let state;
{functions}
const fixtures = {json.dumps(fixtures, separators=(",", ":"))};
const results = fixtures.map((fixture) => {{
  packet = {{edges: fixture.edges}};
  readerNodeIds = fixture.nodes;
  nodeById = new Map(fixture.nodes.map((nodeId, packetIndex) => [nodeId, {{
    packetIndex,
    reader_role: fixture.ranks[nodeId] === 0 ? 'target' : 'definition'
  }}]));
  state = {{minimizedNodeIds: new Set()}};
  const ranks = new Map(Object.entries(fixture.ranks).map(([nodeId, rank]) => [nodeId, rank]));
  const groups = new Map(fixture.groups.map(([rank, nodeIds]) => [rank, [...nodeIds]]));
  const crossing = reduceEdgeCrossings(groups, ranks);
  const compact = compactRadialCoordinates(groups, ranks);
  return {{
    name: fixture.name,
    ...crossing,
    compactionEvaluated: compact.evaluated,
    compactionBlend: compact.acceptedBlend,
    compactBaselineCrossings: compact.baselineScore.crossings,
    compactFinalCrossings: compact.finalScore.crossings,
    baselineCollisionCount: compact.baselineScore.collisionCount,
    finalCollisionCount: compact.finalScore.collisionCount,
    baselineMinimumEdgeClearance: compact.baselineScore.minimumEdgeClearance,
    finalMinimumEdgeClearance: compact.finalScore.minimumEdgeClearance,
    baselineEdgeClearanceViolationCount: compact.baselineScore.edgeClearanceViolationCount,
    finalEdgeClearanceViolationCount: compact.finalScore.edgeClearanceViolationCount,
    baselineMaximumEdgeLength: compact.baselineScore.maximumEdgeLength,
    finalMaximumEdgeLength: compact.finalScore.maximumEdgeLength,
    baselineTotalEdgeLength: compact.baselineScore.totalEdgeLength,
    finalTotalEdgeLength: compact.finalScore.totalEdgeLength
  }};
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
        for result in results.values():
            self.assertTrue(result["evaluated"])
            self.assertLessEqual(result["finalCrossings"], result["baselineCrossings"])
            self.assertLessEqual(result["refinementCandidates"], 48)
            self.assertTrue(result["compactionEvaluated"])
            self.assertLessEqual(
                result["compactFinalCrossings"], result["compactBaselineCrossings"]
            )
            self.assertLessEqual(
                result["finalCollisionCount"], result["baselineCollisionCount"]
            )
            self.assertLessEqual(
                result["finalEdgeClearanceViolationCount"],
                result["baselineEdgeClearanceViolationCount"],
            )
            self.assertGreaterEqual(result["finalMinimumEdgeClearance"], 72 - 1e-6)
            self.assertLessEqual(
                result["finalMaximumEdgeLength"], result["baselineMaximumEdgeLength"]
            )
            self.assertLessEqual(
                result["finalTotalEdgeLength"], result["baselineTotalEdgeLength"]
            )
        self.assertTrue(
            any(
                result["compactionBlend"] > 0
                and (
                    result["finalMaximumEdgeLength"]
                    < result["baselineMaximumEdgeLength"] - 1e-6
                    or result["finalTotalEdgeLength"]
                    < result["baselineTotalEdgeLength"] - 1e-6
                )
                for result in results.values()
            )
        )

    def test_revision_thirteen_box_selection_and_group_movement_contract_is_embedded(self) -> None:
        html, _ = render_reader_html(example_packet())
        pointer_intent = javascript_function_source(html, "bindPointerIntent")
        batch_detail = javascript_function_source(html, "showBatchSelectionDetail")
        selection_restore = javascript_function_source(html, "restoreCanvasSelection")
        dynamic_forces = javascript_function_source(html, "applyDynamicForces")
        dynamic_schedule = javascript_function_source(html, "scheduleDynamicForces")
        dynamic_cancel = javascript_function_source(html, "cancelScheduledDynamicForces")
        trackpad_navigation = javascript_function_source(html, "bindTrackpadNavigation")

        self.assertIn("userPanningEnabled: false", html)
        self.assertIn("boxSelectionEnabled: false", html)
        self.assertIn("selectionType: 'additive'", html)
        self.assertIn("'selection-box-color': '#ffe58a'", html)
        self.assertIn("'selection-box-opacity': 0.12", html)
        self.assertIn("'box-selection': 'overlap'", html)
        self.assertIn('id="box-selection-marquee"', html)
        self.assertIn('id="box-selection-halo-layer"', html)
        self.assertIn("const selectedNodesInRectangle", pointer_intent)
        self.assertIn("node.renderedBoundingBox", pointer_intent)
        self.assertIn("const overlaps = box.x2 >= selection.x1", pointer_intent)
        self.assertIn("commitSelection(", pointer_intent)
        self.assertIn("showBatchSelectionDetail(combinedIds)", pointer_intent)
        self.assertIn("state.boxSelectedNodeIds = new Set(combinedIds)", pointer_intent)
        self.assertIn("state.selectedNodeIds = new Set(selectedIds)", batch_detail)
        self.assertIn("restoreCanvasSelection()", batch_detail)
        self.assertIn("批量移动", batch_detail)
        self.assertIn("Group move", batch_detail)
        self.assertIn("state.selectedNodeIds", selection_restore)
        self.assertIn("element.select()", selection_restore)
        self.assertIn("element.addClass('box-selected')", selection_restore)
        self.assertIn("function syncBoxSelectionHalos()", html)
        self.assertIn("rgba(127, 221, 137, 0.58)", html)
        self.assertIn("data-box-selected", html)
        self.assertIn("event.pointerType === 'mouse'", pointer_intent)
        self.assertIn("event.shiftKey || event.altKey || event.ctrlKey || event.metaKey", pointer_intent)
        self.assertIn("cy.boxSelectionEnabled(false)", pointer_intent)
        self.assertIn("cy.userPanningEnabled(true)", pointer_intent)
        self.assertIn("cy.userPanningEnabled(false)", pointer_intent)
        self.assertNotIn("cy.boxSelectionEnabled(true)", pointer_intent)
        self.assertIn("window.addEventListener('pointermove'", pointer_intent)
        self.assertNotIn("event.stopImmediatePropagation()", pointer_intent)
        self.assertIn("if (!selectionGesture.moved) return", pointer_intent)
        self.assertIn("if (completedGesture.moved && event.type === 'pointerup')", pointer_intent)
        self.assertIn("state.boxSelectionAdditive", pointer_intent)
        self.assertIn("cy.on('grab', 'node'", html)
        self.assertIn("cy.on('drag', 'node'", html)
        self.assertIn("cy.on('dragfree', 'node'", html)
        self.assertIn("state.groupDrag", html)
        self.assertIn("state.pinned.set(nodeId, {...movedNode.position()})", html)
        self.assertIn("lastMovedSelectionCount", html)
        self.assertIn("DYNAMIC_FORCE_NODE_LIMIT = 240", html)
        self.assertNotIn("DYNAMIC_FORCE_DRAG_PASSES", html)
        self.assertIn("DYNAMIC_FORCE_SETTLE_PASSES = 14", html)
        self.assertIn("DYNAMIC_ATTRACTION_TARGET_GAP = 116", html)
        self.assertIn("PINCH_ZOOM_SENSITIVITY = 0.008", html)
        self.assertIn("if (event.ctrlKey)", trackpad_navigation)
        self.assertIn("event.preventDefault()", trackpad_navigation)
        self.assertIn("event.stopPropagation()", trackpad_navigation)
        self.assertIn("cy.minZoom()", trackpad_navigation)
        self.assertIn("cy.maxZoom()", trackpad_navigation)
        self.assertIn("cy.zoom({level, renderedPosition})", trackpad_navigation)
        self.assertIn("lastZoomInput = 'trackpad-pinch'", trackpad_navigation)
        self.assertNotIn("if (event.ctrlKey) return", trackpad_navigation)
        self.assertIn("RADIAL_VISIBLE_EDGE_GAP", dynamic_forces)
        self.assertIn("dynamicBoundaryExtent", dynamic_forces)
        self.assertIn("DYNAMIC_REPULSION_STRENGTH", dynamic_forces)
        self.assertIn("DYNAMIC_ATTRACTION_STRENGTH", dynamic_forces)
        self.assertNotIn("state.pinned.set(nodeId, next)", dynamic_forces)
        self.assertIn("forceNeighborhood", dynamic_forces)
        self.assertIn("dynamicRadialMemoryDisplacement", dynamic_forces)
        self.assertIn("dynamicLayoutModel", dynamic_forces)
        self.assertIn("requestAnimationFrame", dynamic_schedule)
        self.assertIn("cancelAnimationFrame", dynamic_cancel)
        self.assertIn("cancelScheduledDynamicForces()", html)
        self.assertNotIn("scheduleDynamicForces(fixedIds", html)
        self.assertIn("'drag-release'", html)
        self.assertIn("cancelScheduledDynamicForces();\n      const anchor", html)
        self.assertIn("scheduleDynamicForces(\n      delta.anchorNodeIds", html)
        self.assertIn("左键框选", html)
        self.assertIn("radial-memory constraints", html)

    def test_revision_seventeen_uses_compact_identity_and_complete_math_typesetting(self) -> None:
        packet = example_packet()
        packet["nodes"][0]["title"] = (
            r"\[\sum_{n=0}^{\infty} a_n\] " + "very-long-title " * 300
        ).strip()
        html, metadata = render_reader_html(packet)
        identity_label = javascript_function_source(html, "nodeIdentityLabel")
        identity_text = javascript_function_source(html, "nodeIdentityText")
        display_label = javascript_function_source(html, "nodeDisplayLabel")
        tooltip = javascript_function_source(html, "showNodeNameTooltip")
        detail_typeset = javascript_function_source(html, "typesetDetail")

        self.assertEqual(metadata["renderer_revision"], "chalxius-reader-html-17")
        self.assertIn("object_sha256.slice(0, 6)", identity_label)
        self.assertIn("roleLabel(node.reader_role)", identity_label)
        self.assertIn("planeLabel(node.plane)", identity_label)
        self.assertNotIn("node.title", identity_label)
        self.assertIn("nodeIdentityLabel(node)", identity_text)
        self.assertIn("nodeIdentityLabel(node)", display_label)
        self.assertIn("nodeIdentityText(node)", tooltip)
        self.assertNotIn("node.title", tooltip)
        self.assertIn("dom.detailTitle", detail_typeset)
        self.assertIn("dom.detailReadable", detail_typeset)
        self.assertIn("dom.detailFormal", detail_typeset)
        self.assertIn("inlineMath: [['\\\\(', '\\\\)'], ['$', '$']]", html)
        self.assertIn("displayMath: [['\\\\[', '\\\\]'], ['$$', '$$']]", html)
        self.assertIn("processEscapes: true", html)
        self.assertIn("processEnvironments: true", html)
        self.assertIn("white-space: nowrap", html)
        self.assertIn("text-overflow: ellipsis", html)
        self.assertIn("selected cards remain anchors", html)
        self.assertIn("the rest of the layout stays fixed", html)
        self.assertNotIn("Local repel/pull while dragging", html)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for trackpad input QA")
    def test_revision_fourteen_trackpad_pinch_zooms_around_pointer(self) -> None:
        html, _ = render_reader_html(example_packet())
        trackpad_navigation = javascript_function_source(html, "bindTrackpadNavigation")
        harness = f"""
const PINCH_ZOOM_SENSITIVITY = 0.008;
let wheelHandler = null;
let currentZoom = 1;
let zoomCommand = null;
let panCommand = null;
const graph = {{
  clientWidth: 800,
  clientHeight: 600,
  contains: () => true,
  getBoundingClientRect: () => ({{left: 100, top: 50}})
}};
const dom = {{
  canvasStage: {{
    addEventListener: (name, handler) => {{
      if (name === 'wheel') wheelHandler = handler;
    }}
  }},
  cy: {{dataset: {{}}}}
}};
const cy = {{
  container: () => graph,
  minZoom: () => 0.36,
  maxZoom: () => 3.2,
  zoom: (value) => {{
    if (value === undefined) return currentZoom;
    zoomCommand = value;
    currentZoom = value.level;
  }},
  panBy: (value) => {{ panCommand = value; }}
}};
const closeNodeContextMenu = () => {{}};
const window = {{requestAnimationFrame: (callback) => {{ callback(); return 1; }}}};
{trackpad_navigation}
bindTrackpadNavigation();
const pinch = {{
  target: graph,
  ctrlKey: true,
  clientX: 500,
  clientY: 360,
  deltaX: 0,
  deltaY: -40,
  deltaMode: 0,
  prevented: false,
  stopped: false,
  preventDefault() {{ this.prevented = true; }},
  stopPropagation() {{ this.stopped = true; }}
}};
wheelHandler(pinch);
const pinchResult = {{
  prevented: pinch.prevented,
  stopped: pinch.stopped,
  level: currentZoom,
  renderedPosition: zoomCommand.renderedPosition,
  source: dom.cy.dataset.lastZoomInput,
  panCommand
}};
panCommand = null;
const pan = {{
  target: graph,
  ctrlKey: false,
  deltaX: 7,
  deltaY: 11,
  deltaMode: 0,
  preventDefault() {{}},
  stopPropagation() {{}}
}};
wheelHandler(pan);
process.stdout.write(JSON.stringify({{pinchResult, panCommand}}));
"""
        completed = subprocess.run(
            [shutil.which("node"), "-e", harness],
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(completed.stdout)
        self.assertTrue(result["pinchResult"]["prevented"])
        self.assertTrue(result["pinchResult"]["stopped"])
        self.assertGreater(result["pinchResult"]["level"], 1)
        self.assertEqual(
            result["pinchResult"]["renderedPosition"], {"x": 400, "y": 310}
        )
        self.assertEqual(result["pinchResult"]["source"], "trackpad-pinch")
        self.assertIsNone(result["pinchResult"]["panCommand"])
        self.assertEqual(result["panCommand"], {"x": -7, "y": -11})

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for sizing convergence QA")
    def test_revision_fifteen_card_sizing_runs_anchored_fourteen_pass_convergence(self) -> None:
        html, _ = render_reader_html(example_packet())
        sizing_convergence = javascript_function_source(html, "scheduleSizingConvergence")
        commit = javascript_function_source(html, "commitSizing")
        apply_delta = javascript_function_source(html, "applySizingDelta")
        toggle = javascript_function_source(html, "toggleNodeMinimized")
        node_path = javascript_function_source(html, "maximizeNodePath")
        theme_path = javascript_function_source(html, "maximizeThemePath")
        direction = javascript_function_source(html, "maximizeDirection")
        boundary_extent = javascript_function_source(html, "dynamicBoundaryExtent")
        radial_memory = javascript_function_source(html, "dynamicRadialMemoryDisplacement")
        dynamic_forces = javascript_function_source(html, "applyDynamicForces")

        self.assertIn("const changedNodeIds = new Set([...delta.added, ...delta.removed])", sizing_convergence)
        self.assertIn("delta.anchorNodeIds || []", sizing_convergence)
        self.assertIn("DYNAMIC_FORCE_SETTLE_PASSES", sizing_convergence)
        self.assertIn("changedNodeIds", sizing_convergence)
        self.assertIn("'sizing'", sizing_convergence)
        self.assertIn("anchorNodeIds: [...new Set(anchorNodeIds || [])]", commit)
        self.assertIn("scheduleSizingConvergence(delta)", commit)
        self.assertIn("scheduleSizingConvergence(delta)", apply_delta)
        self.assertIn("commitSizing(next, `toggle:${nodeId}`, [nodeId])", toggle)
        self.assertIn("commitSizing(next, `complete-path:${nodeId}`, [nodeId])", node_path)
        self.assertIn("[`reader-theme:${themeId}`]", theme_path)
        self.assertIn("commitSizing(next, `${direction}:${nodeId}`, [nodeId])", direction)
        self.assertIn("const remainingPasses = passes - pass", dynamic_forces)
        self.assertIn("clearanceDeficit / remainingPasses", dynamic_forces)
        self.assertIn("if (!applied) continue", dynamic_forces)
        self.assertIn("dynamicForceExecutedPasses", dynamic_forces)
        self.assertIn("dynamicForceReason", dynamic_forces)
        self.assertIn("forceNeighborhood", dynamic_forces)
        self.assertIn("clearanceConstrained", dynamic_forces)
        self.assertIn("dynamicRadialMemoryDisplacement", dynamic_forces)

        harness = f"""
const RADIAL_VISIBLE_EDGE_GAP = 72;
const RADIAL_RING_PHASE = Math.PI * (3 - Math.sqrt(5));
const DYNAMIC_FORCE_SETTLE_PASSES = 14;
const DYNAMIC_FORCE_NODE_LIMIT = 240;
const DYNAMIC_FORCE_MAX_STEP = 14;
const DYNAMIC_REPULSION_STRENGTH = 0.42;
const DYNAMIC_ATTRACTION_STRENGTH = 0.026;
const DYNAMIC_ATTRACTION_TARGET_GAP = 116;
const DYNAMIC_RADIAL_TETHER_STRENGTH = 0.085;
const DYNAMIC_TANGENTIAL_TETHER_STRENGTH = 0.055;
const DYNAMIC_TETHER_MAX_STEP = 4;
let controlSyncCount = 0;
const scheduleNodeControlSync = () => {{ controlSyncCount += 1; }};
const wrapLayoutAngle = (angle) => Math.atan2(Math.sin(angle), Math.cos(angle));
function makeNode(id, x, width, height) {{
  let current = {{x, y: 0}};
  return {{
    id: () => id,
    hasClass: () => false,
    position(next) {{
      if (next === undefined) return {{...current}};
      current = {{...next}};
      return this;
    }},
    boundingBox: () => ({{w: width, h: height}})
  }};
}}
const anchor = makeNode('anchor', 0, 254, 118);
const neighbor = makeNode('neighbor', 230, 246, 110);
const nodes = [anchor, neighbor];
const canonicalPositionByNodeId = new Map([
  ['anchor', {{x: 0, y: 0}}],
  ['neighbor', {{x: 322, y: 0}}]
]);
const cy = {{
  nodes: () => nodes,
  edges: () => [],
  batch: (callback) => callback()
}};
const state = {{pinned: new Map()}};
const dom = {{cy: {{dataset: {{}}}}}};
{boundary_extent}
{radial_memory}
{dynamic_forces}
const beforeAnchor = anchor.position();
const beforeNeighbor = neighbor.position();
const moved = applyDynamicForces(['anchor'], 14, ['anchor'], 'sizing');
const afterAnchor = anchor.position();
const afterNeighbor = neighbor.position();
const finalGap = afterNeighbor.x - afterAnchor.x - 254 / 2 - 246 / 2;
process.stdout.write(JSON.stringify({{
  beforeAnchor,
  afterAnchor,
  beforeNeighbor,
  afterNeighbor,
  finalGap,
  moved,
  controlSyncCount,
  pinnedNeighbor: state.pinned.get('neighbor') || null,
  dataset: dom.cy.dataset
}}));
"""
        completed = subprocess.run(
            [shutil.which("node"), "-e", harness],
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(result["beforeAnchor"], result["afterAnchor"])
        self.assertGreater(result["afterNeighbor"]["x"], result["beforeNeighbor"]["x"])
        self.assertGreaterEqual(result["finalGap"], 72 - 1e-6)
        self.assertEqual(result["moved"], 1)
        self.assertEqual(result["controlSyncCount"], 1)
        self.assertIsNone(result["pinnedNeighbor"])
        self.assertEqual(result["dataset"]["dynamicForceFixedCount"], "1")
        self.assertEqual(result["dataset"]["dynamicForceSeedCount"], "1")
        self.assertEqual(result["dataset"]["dynamicForceRequestedPasses"], "14")
        self.assertEqual(result["dataset"]["dynamicForceExecutedPasses"], "14")
        self.assertEqual(result["dataset"]["dynamicForceReason"], "sizing")
        self.assertEqual(
            result["dataset"]["dynamicLayoutModel"],
            "localized-radial-memory-equilibrium",
        )

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
        self.assertIn("state.pinned.set(nodeId, {...movedNode.position()})", html)
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
        self.assertEqual(first["renderer_revision"], "chalxius-reader-html-17")
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
