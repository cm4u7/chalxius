#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mathgraph.cli import main as cli_main  # noqa: E402
from mathgraph.applicability import validate_external_refs_for_submission  # noqa: E402
from mathgraph.blackboard import make_edge, make_node  # noqa: E402
from mathgraph.contracts import sha256_bytes, sha256_json  # noqa: E402
from mathgraph.elementary import validate_elementary_uses_for_submission  # noqa: E402
from mathgraph.event_ledger import (  # noqa: E402
    ExperimentEventIndexSession,
    ExperimentEventLedger,
)
from mathgraph.model import Fact  # noqa: E402
from mathgraph.orchestrator import (  # noqa: E402
    create_round,
    ingest_return,
    preflight_return,
    validate_return,
)
from mathgraph.paper_logic import PaperLogicStore  # noqa: E402
from mathgraph.paper_logic_contracts import (  # noqa: E402
    PAPER_LOGIC_FEATURE_REVISION,
    REVIEW_GLOBAL_CHECKS,
    scan_high_risk_operators,
)
from mathgraph.protocol import DEFAULT_HARD_CAPS  # noqa: E402
from mathgraph.reader_html import (  # noqa: E402
    export_reader_html,
    load_reader_packet,
    render_reader_html,
)
from mathgraph.roles import allowed_commands  # noqa: E402
from mathgraph.store import MathGraphStore  # noqa: E402


def review(
    store: MathGraphStore,
    fact_id: str,
    *,
    reviewer: str,
    verdict: str = "correct",
    errors: list[str] | None = None,
) -> str:
    frozen = store.freeze_verification_packet(fact_id)
    return store.record_review(
        {
            "fact_id": fact_id,
            "submission_sha256": frozen["submission_sha256"],
            "packet_sha256": frozen["packet_sha256"],
            "verdict": verdict,
            "critical_errors": errors or [],
            "gaps": [],
            "repair_hints": [],
            "reviewer": reviewer,
        }
    ).stem


def main() -> int:
    if allowed_commands("verifier") or allowed_commands("unknown-role"):
        raise RuntimeError("verifier or unknown role received project CLI capabilities")
    if "preflight-return" not in allowed_commands("worker") or any(
        "preflight-return" in allowed_commands(role)
        for role in ("main", "operator", "host", "gateway", "verifier")
    ):
        raise RuntimeError(
            "preflight-return must remain an exclusive worker capability"
        )
    for command in (
        "export-interpret-card",
        "lint-interpret-document",
        "export-reader-html",
    ):
        if any(
            command not in allowed_commands(role)
            for role in ("main", "operator")
        ) or any(
            command in allowed_commands(role)
            for role in ("worker", "verifier", "gateway", "host")
        ):
            raise RuntimeError(
                f"{command} must remain a main/operator-only capability"
            )
    paper_auditor = allowed_commands("paper-auditor")
    if (
        "paper-logic-record-review" not in paper_auditor
        or "paper-logic-query" not in paper_auditor
        or {
            "paper-logic-stage",
            "paper-logic-freeze",
            "paper-logic-project-blackboard",
        }.intersection(paper_auditor)
        or any(
            command.startswith("paper-logic-")
            for command in allowed_commands("worker")
        )
    ):
        raise RuntimeError("Paper Logic role capabilities crossed boundaries")

    skill_root = Path(__file__).resolve().parents[1]
    skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    skill_line_count = len(skill_text.splitlines())
    if skill_line_count >= 500:
        raise RuntimeError(
            f"SKILL.md must remain below 500 lines; found {skill_line_count}"
        )
    policy_paths = (
        skill_root / "SKILL.md",
        skill_root / "references" / "adoption_policy_v4.md",
        skill_root / "references" / "agent_protocol_v4.md",
        skill_root / "references" / "computational_verification_v4.md",
        skill_root / "references" / "campaigns_and_migration_v4.md",
        skill_root / "references" / "portable_deployment.md",
        skill_root / "references" / "multi_agent_adapter.md",
        skill_root / "references" / "architecture.md",
        skill_root / "references" / "blackboard_graph_v4.md",
        skill_root / "references" / "data_contracts.md",
        skill_root / "references" / "paper_logic_graph_v1.md",
        skill_root / "references" / "paper-reading-modes.md",
        skill_root / "references" / "math-grilling.md",
        skill_root / "references" / "fact-graph-grilling.md",
        skill_root / "references" / "portable_deployment.md",
        skill_root / "references" / "v0_4_release_traceability.md",
        skill_root / "references" / "unified_architecture.md",
        skill_root / "references" / "reasoning_modes.md",
        skill_root / "references" / "admission_contract.md",
        skill_root / "references" / "unified_learning_plane.md",
        skill_root / "references" / "reader_html_export.md",
        skill_root / "references" / "architecture-grilling.md",
        skill_root / "references" / "unified_release_traceability.md",
        skill_root / "assets" / "DEPLOY_PROMPT.txt",
        skill_root / "assets" / "AGENTS.routing.md",
        skill_root / "agents" / "openai.yaml",
        skill_root / "INHERITANCE.lock.json",
    )
    policy_texts = {
        path.relative_to(skill_root).as_posix(): path.read_text(
            encoding="utf-8"
        )
        for path in policy_paths
    }
    identity_requirements = {
        "SKILL.md": (
            "name: chalxius",
            "# Chalxius",
            "`chalxius` is the public skill name",
            "standalone `$grill-me` companion, called `Grill Me Code`",
            "`Chalxius Learner` is the canonical name",
            "Ordinary coding work does not activate it",
            "Reasoning profile and interaction surface are orthogonal",
            "export-reader-html",
            "PROJECT/visualizations/knowledge-map.html",
        ),
        "agents/openai.yaml": (
            'display_name: "Chalxius"',
            "$chalxius",
            "allow_implicit_invocation: true",
        ),
        "INHERITANCE.lock.json": (
            '"skill_name": "chalxius"',
            '"version": "0.3.2-code"',
            '"product_availability": "globally_injected"',
            '"semantic_activation": "explicit_programming_grill_or_socratic_intent_only"',
            '"graph_mount_capability": false',
            '"research_authority": false',
            '"renderer_revision": "chalxius-reader-html-11"',
            '"fixed_output": "visualizations/knowledge-map.html"',
            '"network_runtime": "disabled"',
        ),
        "references/reader_html_export.md": (
            "truth_effect=\"none\"",
            "PROJECT/visualizations/knowledge-map.html",
            "same semantic packet",
            "Fact-plane nodes",
            "There is no watcher, local storage, or graph writeback.",
            "PDF production is outside this feature",
        ),
        "references/unified_learning_plane.md": (
            "Chalxius Learner",
            "Chalxius Learner is off by default",
            "`deep` does not activate",
            "Standalone Grill Me 0.3.2-code",
            "globally available to routing",
            "cannot mount Fact, Paper, Audit, Blackboard, or",
            "`$chalxius`, not through standalone `$grill-me`",
        ),
        "references/architecture-grilling.md": (
            "compatibility-only routing note",
            "stays on the Chalxius",
            "does not activate a learner",
            "Ordinary Chalxius research does not activate Chalxius Learner",
            "does not activate Grill Me Code",
        ),
        "references/math-grilling.md": (
            "only after explicit academic-learning intent",
            "does not activate it by itself",
            "Learner off",
        ),
        "references/paper-reading-modes.md": (
            "only after explicit academic teaching",
            "ordinary Chalxius research",
            "never activates",
            "learner by itself",
        ),
        "references/fact-graph-grilling.md": (
            "only after the user explicitly requests academic teaching",
            "Do not activate Chalxius Learner for ordinary research",
            "mount a graph unless it materially improves",
        ),
        "assets/AGENTS.routing.md": (
            "Chalxius Learner（内部 Grill 学习器）",
            "Grill Me Code（外部编程辅助）",
            "普通研究、论文审计、系统能力测试或 Fact 准入不得自动启动它",
            "普通编码、实现、调试或代码审查任务不得自动启动它",
            "不同时启动二者",
        ),
    }
    missing_identity_markers = [
        f"{relative}: {marker}"
        for relative, markers in identity_requirements.items()
        for marker in markers
        if marker not in policy_texts[relative]
    ]
    if missing_identity_markers:
        raise RuntimeError(
            "missing Chalxius identity or companion-boundary markers: "
            + ", ".join(missing_identity_markers)
        )
    if "Start every paper-reading response" in policy_texts[
        "references/paper-reading-modes.md"
    ]:
        raise RuntimeError(
            "paper-reading modes still auto-activate the learner"
        )
    stale_public_names = [
        f"{relative}: {marker}"
        for relative, text in policy_texts.items()
        for marker in ("Chalk Nexus", "chalk-nexus")
        if marker in text
    ]
    if stale_public_names:
        raise RuntimeError(
            "stale pre-Chalxius public names: " + ", ".join(stale_public_names)
        )
    collaboration_policy = "\n".join(policy_texts.values())
    required_collaboration_markers = (
        "all currently callable clean-context worker slots",
        'score_role="priority_ordering_only"',
        "priority/load ordering",
        "barriered Blackboard pulse",
        "durable two-wave pulse",
        "independently repeated check",
        "active-interval union",
        "Exactly 1200 seconds does not trigger",
        "strictly greater than 1200 seconds",
        "experimental nature",
        "actual elapsed time and observed resources",
        "progress and latest checkpoint",
        "importance and continuation value",
        "impact of stopping",
        "Worker telemetry",
        "safety and integrity caps",
        "user-authorized V4 revision",
        "frozen legacy adoption binding",
        "cooperative evidence layer",
        "execution_profile",
        "future_work_units_only",
        "candidate_only_until_gate_satisfied",
        "mode-init",
        "legacy standalone",
        "nontruth learning plane",
        "host_task_scope_id",
        "archival-only",
        "expert-lint-receipts",
        "interpret-lint-receipts",
        "fails before",
        "pulse-abort",
        "pulse-dispatch",
        "--host-config",
        "preflight-return",
        "procedural_ready",
        "machine_verified_ready",
        "federation is disabled",
        "never sends SIGKILL",
        "managed work remains runnable",
        "current/history",
        "prepare_verifier_capsule.py",
        "Paper Logic",
        "exploration_challenges_audit",
        "repair from refutation",
        "profile_obligations",
        "profile-closure-status",
        "profile-closure-record",
        "workflow_readiness_only",
        "mixed_procedural_and_machine_verified",
        "source_ambiguity",
        "V1-V3",
    )
    missing_collaboration_markers = [
        marker
        for marker in required_collaboration_markers
        if marker not in collaboration_policy
    ]
    if missing_collaboration_markers:
        raise RuntimeError(
            "missing default parallel-blackboard policy markers: "
            + ", ".join(missing_collaboration_markers)
        )
    forbidden_collaboration_markers = (
        "about 20 minutes",
        "20 minutes or longer",
        "estimated above 300 seconds",
        "unknown-duration, or over-300s",
        "default two-or-three-worker",
        "begin with the smallest complementary panel",
        "Substantive Chalk work defaults to two clean-context workers",
        "Launch two complementary workers",
        "make a two-worker constructive",
        "active campaign as the durable task scope",
        "project plus active campaign",
        "derived from project and campaign",
        "branches expected to run about",
        "one pending main/operator decision",
        "one notice and one main/operator decision",
        "obtain one main/operator decision",
        "one notice and one decision",
        "decision_required",
    )
    stale_collaboration_markers = [
        f"{relative}: {marker}"
        for relative, text in policy_texts.items()
        for marker in forbidden_collaboration_markers
        if marker in text
    ]
    if stale_collaboration_markers:
        raise RuntimeError(
            "stale estimate-gated collaboration policy markers: "
            + ", ".join(stale_collaboration_markers)
        )
    current_routing_surfaces = (
        "SKILL.md",
        "references/adoption_policy_v4.md",
        "references/agent_protocol_v4.md",
        "references/campaigns_and_migration_v4.md",
        "references/portable_deployment.md",
        "references/architecture.md",
        "references/blackboard_graph_v4.md",
        "references/paper_logic_graph_v1.md",
        "references/paper-reading-modes.md",
        "assets/DEPLOY_PROMPT.txt",
    )
    forbidden_unified_routing_markers = (
        "substantive Chalk research " + "fills " + "every callable",
        "Substantive Chalk work " + "uses every callable",
        "Use this protocol only when `$mathgraph-chalk-version` is the sole",
        "Use `$mathgraph-chalk-version` as the only MathGraph skill",
        "Permit explicit or implicit invocation of $mathgraph-chalk-version",
        "External Grill Me overlay",
        "mount the Fact Graph only",
        "Substantive Chalk work fills every callable",
        "Substantive Chalk work uses every callable",
    )
    stale_unified_routing = [
        f"{relative}: {marker}"
        for relative in current_routing_surfaces
        for marker in forbidden_unified_routing_markers
        if marker in policy_texts[relative]
    ]
    if stale_unified_routing:
        raise RuntimeError(
            "current unified surfaces retain standalone routing rules: "
            + ", ".join(stale_unified_routing)
        )

    reader_packet = load_reader_packet(
        skill_root / "assets" / "reader_packet.v1.example.json",
        project_id="reader-demo",
    )
    reader_html_first, reader_meta_first = render_reader_html(reader_packet)
    reader_html_second, reader_meta_second = render_reader_html(reader_packet)
    reader_packet_sha256 = sha256_json(reader_packet)
    expected_reader_finalize = {
        "schema_version": 1,
        "status": "ready",
        "scope": "presentation_readiness_only",
        "source_snapshot_id": reader_packet["source_snapshot"]["id"],
        "source_snapshot_sha256": reader_packet["source_snapshot"]["sha256"],
        "sidebar_complete_count": len(reader_packet["nodes"]),
        "node_count": len(reader_packet["nodes"]),
        "packet_sha256": reader_packet_sha256,
        "truth_effect": "none",
    }
    if (
        reader_html_first != reader_html_second
        or reader_meta_first != reader_meta_second
        or "connect-src 'none'" not in reader_html_first
        or "@@CHALXIUS_" in reader_html_first
        or reader_meta_first.get("renderer_revision")
        != "chalxius-reader-html-11"
        or reader_meta_first.get("packet_sha256") != reader_packet_sha256
        or reader_meta_first.get("reader_finalize") != expected_reader_finalize
        or reader_meta_first.get("truth_effect") != "none"
        or reader_meta_first.get("network_runtime") != "disabled"
        or any(
            token not in reader_html_first
            for token in (
                "maximizeTargets",
                "maximizeAllCards",
                "maximizeNodePath",
                "toggleNodeMinimized",
                "directedClosureNodeIds",
                "minimizedNodeIds",
                "sizingUndoStack",
                "sizingRedoStack",
                "undoSizing",
                "redoSizing",
                "node-size-toggle",
                "selected-node-halo",
                "bindNodeSizeToggle",
                "hoveredCanvasNodeId",
                "hoveredControlNodeId",
                "scheduleNodeHoverSync",
                "nextHoveredId",
                "nodeSizeControlAnchor",
                "NODE_SIZE_CONTROL_X_RATIO = 0.29",
                "NODE_SIZE_CONTROL_Y_RATIO = 0.5",
                "NODE_SIZE_CONTROL_CARD_HEIGHT_RATIO = 0.45",
                "applyNodeSizingClasses",
                "bounds.x1 + (bounds.x2 - bounds.x1) * NODE_SIZE_CONTROL_X_RATIO",
                "bounds.y1 + (bounds.y2 - bounds.y1) * NODE_SIZE_CONTROL_Y_RATIO",
                "compact.height * cy.zoom() * NODE_SIZE_CONTROL_CARD_HEIGHT_RATIO",
                "transition.oldAnchor.x - newAnchor.x",
                "transition.oldAnchor.y - newAnchor.y",
                "transition.node.position(compensated)",
                "'text-max-width': 106, 'text-margin-x': 18",
                "'text-max-width': 102, 'text-margin-x': 18",
                "'text-max-width': 98, 'text-margin-x': 17",
                "'text-max-width': 92, 'text-margin-x': 17",
                "'text-justification': 'left'",
                "'arrow-scale': 1.65",
                "'mid-target-arrow-shape': 'triangle'",
                "syncSelectedNodeHalo",
                "drop-shadow",
                'id="undo-sizing-button"',
                'id="redo-sizing-button"',
                'id="reload-graph-button"',
                "window.location.reload()",
                '"reader_finalize":{',
                'data-appearance-scheme="faceted"',
                'data-appearance-scheme="plaques"',
                "selectedId",
            )
        )
        or reader_html_first.count('data-context-command="') != 2
        or reader_html_first.count('data-appearance-scheme="') != 2
        or any(
            token in reader_html_first
            for token in (
                "applyAllTargetsDisclosure",
                "applyAllCardsDisclosure",
                "applyNodeFocusDisclosure",
                "directedClosureEdgeIds",
                "toggleNodeSide",
                "setEdgeExpanded",
                "collapseNodeSide",
                "canvasEdgeIds",
                "canvasRootIds",
                "disclosurePreset",
                "edge-handle",
                "edge-stub-line",
                "node-side-control",
                "surfaceMode",
                "focusDomainEdgeIds",
                "focusEdgeIds",
                "enterFocusView",
                "exitFocusView",
                "bindNodeSizeToggleGesture",
                "NODE_SIZE_CONTROL_INSET",
                "NODE_SIZE_CONTROL_DRAG_THRESHOLD",
                "if (minimized) return center;",
                'data-dragging="yes"',
                "button.setPointerCapture",
                'id="back-to-overview-button"',
            )
        )
    ):
        raise RuntimeError(
            "deterministic offline reader HTML self-test failed"
        )
    size_toggle_start = reader_html_first.find("  function bindNodeSizeToggle(")
    size_toggle_end = reader_html_first.find(
        "\n  function ",
        size_toggle_start + len("  function bindNodeSizeToggle("),
    )
    size_toggle_source = (
        reader_html_first[size_toggle_start:size_toggle_end]
        if size_toggle_start >= 0 and size_toggle_end >= 0
        else ""
    )
    if not size_toggle_source or any(
        token in size_toggle_source
        for token in (
            "pointermove",
            "mousemove",
            "setPointerCapture",
            "state.pinned",
            ".position(",
            "suppressClick",
            "NODE_SIZE_CONTROL_DRAG_THRESHOLD",
        )
    ):
        raise RuntimeError(
            "reader size control must remain a click-only action, not a drag surface"
        )
    if (
        reader_html_first.count(
            "dom.reloadGraph.addEventListener('click', () => window.location.reload())"
        )
        != 1
    ):
        raise RuntimeError(
            "reader reload must remain one click-only browser refresh action"
        )
    for field in ("summary", "intuition", "importance", "reasoning"):
        for invalid in ("", " \t\r\n "):
            invalid_packet = json.loads(json.dumps(reader_packet))
            invalid_packet["nodes"][0][field] = invalid
            try:
                render_reader_html(invalid_packet)
            except ValueError as exc:
                if f"nodes[0].{field} must be nonempty" not in str(exc):
                    raise RuntimeError(
                        f"reader finalize rejected {field} for the wrong reason: {exc}"
                    ) from exc
            else:
                raise RuntimeError(
                    f"reader finalize accepted an empty or whitespace-only {field}"
                )

    minimum_zoom = 0.36
    control_x_ratio = 0.29
    control_y_ratio = 0.5
    control_height_ratio = 0.45
    reader_role_geometry = {
        "target": (78.0, 46.0, 254.0, 106.0, 18.0),
        "definition": (80.0, 44.0, 246.0, 102.0, 18.0),
        "result": (76.0, 44.0, 238.0, 98.0, 17.0),
        "explanation": (74.0, 44.0, 226.0, 92.0, 17.0),
    }
    for role, geometry in reader_role_geometry.items():
        compact_width, compact_height, full_width, text_max, text_margin = geometry
        control_size = max(
            11.0,
            min(20.0, compact_height * minimum_zoom * control_height_ratio),
        )
        rendered_width = compact_width * minimum_zoom
        rendered_height = compact_height * minimum_zoom
        compact_clearances = (
            rendered_width * control_x_ratio - control_size / 2,
            rendered_width * (1 - control_x_ratio) - control_size / 2,
            rendered_height * control_y_ratio - control_size / 2,
            rendered_height * (1 - control_y_ratio) - control_size / 2,
        )
        normal_control_size = max(
            11.0,
            min(20.0, compact_height * control_height_ratio),
        )
        label_gap = (
            full_width / 2
            + text_margin
            - text_max / 2
            - full_width * control_x_ratio
            - normal_control_size / 2
        )
        if min(compact_clearances) < 2.0 or label_gap < 8.0:
            raise RuntimeError(
                f"reader control or label geometry is unsafe for role {role}"
            )
        for zoom in (minimum_zoom, 1.0, 3.2):
            rendered_full_width = full_width * zoom
            rendered_control_size = max(
                11.0,
                min(20.0, compact_height * zoom * control_height_ratio),
            )
            control_left = (
                rendered_full_width * control_x_ratio
                - rendered_control_size / 2
            )
            label_right = (
                full_width / 2 + text_margin + text_max / 2
            ) * zoom
            content_center = (control_left + label_right) / 2
            content_bias_ratio = abs(
                content_center - rendered_full_width / 2
            ) / rendered_full_width
            if content_bias_ratio > 0.03:
                raise RuntimeError(
                    f"reader content balance is unsafe for role {role} "
                    f"at zoom {zoom}"
                )

    reader_surface_source = "\n".join(
        (skill_root / relative).read_text(encoding="utf-8")
        for relative in (
            "assets/reader_html_app.js",
            "assets/reader_html_template.html",
            "scripts/mathgraph/reader_html.py",
        )
    )
    if any(
        token in reader_surface_source
        for token in (
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
        )
    ):
        raise RuntimeError(
            "reader HTML must not add persistence, sidecar, or writeback surfaces"
        )
    with tempfile.TemporaryDirectory(prefix="mathgraph-reader-self-test-") as temporary:
        reader_root = Path(temporary) / "project"
        reader_store = MathGraphStore(reader_root)
        reader_store.initialize(
            project_id="reader-demo",
            title="Reader finalize smoke test",
            workflow_evidence_version=4,
            reasoning_mode="auto",
        )
        reader_packet_path = reader_root / "reader-packet.json"
        reader_packet_path.write_text(
            json.dumps(reader_packet, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        reader_receipt = export_reader_html(reader_store, reader_packet_path)
        reader_output = Path(reader_receipt["output"])
        reader_output_before = reader_output.read_bytes()
        invalid_replacement = json.loads(json.dumps(reader_packet))
        invalid_replacement["nodes"][0]["summary"] = " \t\r\n "
        reader_packet_path.write_text(
            json.dumps(invalid_replacement, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        try:
            export_reader_html(reader_store, reader_packet_path)
        except ValueError as exc:
            if "nodes[0].summary must be nonempty" not in str(exc):
                raise RuntimeError(
                    f"invalid reader replacement failed for the wrong reason: {exc}"
                ) from exc
        else:
            raise RuntimeError("invalid reader replacement unexpectedly exported")
        if (
            reader_output.read_bytes() != reader_output_before
            or reader_receipt.get("renderer_revision")
            != "chalxius-reader-html-11"
            or reader_receipt.get("reader_finalize") != expected_reader_finalize
        ):
            raise RuntimeError(
                "invalid reader replacement changed the fixed output or readiness receipt"
            )
    for legacy_trace in ("references/v0_4_release_traceability.md",):
        if "Legacy package history, not current routing" not in policy_texts[
            legacy_trace
        ]:
            raise RuntimeError(
                f"{legacy_trace} lacks the legacy-routing supersession banner"
            )
    surface_requirements = {
        "SKILL.md": (
            "all currently callable clean-context worker slots",
            "priority/load ordering",
            "strictly greater than",
            "host_task_scope_id",
            "mode-init",
            "candidate_only_until_gate_satisfied",
            "expert lint receipts",
            "interpret-lint-receipts",
            "mutually exclusive",
            "pulse-abort",
            "machine_verified_ready",
            "federation is deliberately disabled",
            "pulse-dispatch",
            "--host-config",
            "preflight-return",
            "prepare_verifier_capsule.py",
            "profile_obligations",
            "profile-closure-status",
            "profile-closure-record",
            "mixed_procedural_and_machine_verified",
            "workflow_readiness_only",
        ),
        "references/adoption_policy_v4.md": (
            "Unified supersession",
            "execution_profile",
            "status is `available`",
            "priority/load",
            "strictly greater than 1200 seconds",
            "host_task_scope_id",
            "archival-only",
            "expert-lint-receipts",
            "profile_obligations",
            "profile-closure-status",
            "workflow_readiness_only",
        ),
        "references/agent_protocol_v4.md": (
            "Unified supersession",
            "execution_profile",
            "every callable clean-context slot",
            "opt-in",
            "may order starts and load within the selected panel",
            "strictly greater than 1200",
            "host_task_scope_id",
            "archival-only",
            "report-blocker",
            "worker-final handoff",
            "managed work remains runnable",
            "pulse-abort",
            "pulse-dispatch",
            "--host-config",
            "preflight-return",
            "prepare_verifier_capsule.py",
            "profile_obligations",
            "profile-closure-record",
            "mixed_procedural_and_machine_verified",
        ),
        "references/multi_agent_adapter.md": (
            "all currently callable clean-context",
            "priority/load ordering",
            "strictly greater than 1200 seconds",
            "MATHGRAPH_HOST_TASK_SCOPE_ID",
            "procedural_ready",
            "machine_verified_ready",
            "Federation is disabled",
            "pulse-dispatch",
            "--host-config",
            "preflight-return",
        ),
        "references/data_contracts.md": (
            "preflight-return",
            "Paper Logic and Audit Graph evidence",
            "Unified round profile closure",
            "profile_obligations",
            "workflow_readiness_only",
        ),
        "references/paper_logic_graph_v1.md": (
            "paper_source",
            "paper_reconstruction",
            "paper_audit",
            "agent_exploration",
            "exploration_challenges_audit",
            "local repair",
            "refutes_exact_claim",
            "paper_logic_mirror",
        ),
        "assets/DEPLOY_PROMPT.txt": (
            "preflight-return",
            "execution_profile",
            "candidate_only_until_gate_satisfied",
            "profile_obligations",
            "profile-closure-record",
        ),
        "references/reasoning_modes.md": (
            "future_work_units_only",
            "candidate_only_until_gate_satisfied",
            "fast",
            "auto",
            "deep",
            "profile_obligations",
            "not_required",
            "workflow_readiness_only",
        ),
        "references/admission_contract.md": (
            "hash is independent of reasoning mode",
            "different fresh verifier",
        ),
        "references/unified_learning_plane.md": (
            "nontruth",
            "does not invoke a Grill",
        ),
    }
    missing_by_surface = [
        f"{relative}: {marker}"
        for relative, markers in surface_requirements.items()
        for marker in markers
        if marker not in policy_texts[relative]
    ]
    if missing_by_surface:
        raise RuntimeError(
            "policy surface is missing a binding marker: "
            + ", ".join(missing_by_surface)
        )

    with tempfile.TemporaryDirectory(prefix="mathgraph-self-test-") as temporary:
        temporary_root = Path(temporary)
        ledger_path = temporary_root / "event-ledger" / "events.jsonl"
        ledger = ExperimentEventLedger(ledger_path)
        ledger_semantic = {
            "schema_version": 1,
            "policy_revision": "mathgraph-0.3.0",
            "event": "heartbeat",
            "stage": "smoke",
            "latest_check": "event-index smoke",
        }
        ledger_event_id = sha256_json(ledger_semantic)
        ledger_event = {
            **ledger_semantic,
            "event_id": ledger_event_id,
        }

        def append_ledger_event_once(
            session: ExperimentEventIndexSession,
        ) -> None:
            if session.find(ledger_event_id) is None:
                session.append(ledger_event)

        ledger.mutate(append_ledger_event_once)
        ledger_before_replay = ledger_path.read_bytes()
        ledger.mutate(append_ledger_event_once)
        if (
            ledger_path.read_bytes() != ledger_before_replay
            or not ledger.index_path.is_file()
        ):
            raise RuntimeError("rebuildable event index is not idempotent")
        # Exercise read compatibility with one deliberately isolated legacy
        # fixture through the private identity-authorized fixture seam.
        store = MathGraphStore._for_legacy_workflow_fixture(
            temporary_root / "project"
        )
        store.initialize(
            project_id="smoke",
            title="Portable schema-v3 smoke test",
            workflow_evidence_version=3,
            reasoning_mode=None,
        )
        if store.project().get("workflow_evidence_version") != 3:
            raise RuntimeError("new project does not label workflow evidence schema v3")
        source_statement = "Theorem 1. For every smoke object, H implies P."
        applicability_proof = (
            "Check the source hypothesis [APP:SMOKE:H1]. "
            "Match the source convention [APP:SMOKE:C1]. "
            "Apply its exact conclusion [APP:SMOKE:USE]. "
            "Audit its statement and source reliability [CRIT:SMOKE:USE]."
        )
        source_artifact_sha256 = sha256_bytes(b"smoke primary artifact")
        source_artifact_locator = (
            "https://example.org/primary-source/version-1.pdf"
        )
        source_audit_core = {
            "artifact_sha256": source_artifact_sha256,
            "artifact_locator": source_artifact_locator,
            "checked_at": "2026-07-24",
            "issue_searches": [
                {
                    "kind": "version_history",
                    "query": "Applicability smoke source version history",
                    "locator": "https://example.org/primary-source/versions",
                    "finding": "No statement drift was found.",
                },
                {
                    "kind": "errata",
                    "query": "Applicability smoke source erratum correction",
                    "locator": "https://example.org/primary-source/errata",
                    "finding": "No applicable erratum was found.",
                },
                {
                    "kind": "retraction_or_counterexample",
                    "query": (
                        "Applicability smoke source retraction counterexample false"
                    ),
                    "locator": "https://example.org/primary-source/status",
                    "finding": "No retraction or counterexample was found.",
                },
            ],
            "unresolved_signals": [],
            "finding": "The source-level checks found no unresolved signal.",
        }
        validate_external_refs_for_submission(
            [
                {
                    "key": "SMOKE",
                    "title": "Applicability smoke source",
                    "url": "https://example.org/primary-source",
                    "use_kind": "result",
                    "cited_for": "The exact smoke implication.",
                    "source_evidence_version": 3,
                    "source_trace": {
                        "artifact_sha256": source_artifact_sha256,
                        "artifact_locator": source_artifact_locator,
                        "retrieved_at": "2026-07-24",
                        "statement_locator": "Theorem 1, version 1, p. 1",
                        "statement_text": source_statement,
                        "statement_sha256": sha256_bytes(
                            source_statement.encode("utf-8")
                        ),
                        "inspection_methods": ["rendered_primary"],
                    },
                    "critical_audit": {
                        "profile": "baseline",
                        "risk_triggers": [],
                        "sanity_checks": [
                            {
                                "kind": "notation_and_binding",
                                "status": "pass",
                                "finding": "All symbols are bound.",
                            },
                            {
                                "kind": "type_and_domain",
                                "status": "pass",
                                "finding": "The smoke object has the required type.",
                            },
                            {
                                "kind": "quantifiers_and_scope",
                                "status": "pass",
                                "finding": "The universal scope agrees with the proof.",
                            },
                        ],
                        "source_audit": {
                            **source_audit_core,
                            "audit_sha256": sha256_json(source_audit_core),
                        },
                        "source_audit_reuse": {
                            "mode": "fresh",
                            "reused_at": "2026-07-24",
                            "origin": "current_submission",
                        },
                        "assessment": "as_stated",
                        "issues": [],
                        "justification": "The baseline checks found no source defect.",
                        "proof_anchor": "[CRIT:SMOKE:USE]",
                    },
                    "applicability": {
                        "source_version": "version 1",
                        "source_locator": "Theorem 1, version 1, p. 1",
                        "source_scope": "Objects satisfying H.",
                        "target_scope": "The smoke object.",
                        "source_conclusion": "H implies P.",
                        "used_conclusion": "The smoke object has P.",
                        "hypothesis_map": [
                            {
                                "source_hypothesis": "H.",
                                "target_witness": "Direct check in the proof.",
                                "proof_anchor": "[APP:SMOKE:H1]",
                            }
                        ],
                        "convention_map": [
                            {
                                "source_convention": "Ordinary equality convention.",
                                "target_convention": "The same convention is used.",
                                "proof_anchor": "[APP:SMOKE:C1]",
                            }
                        ],
                        "transport_obligations": [],
                        "exclusions_checked": ["Adjacent definitions and remarks checked."],
                        "strength_comparison": "exact",
                        "verdict": "direct",
                        "proof_anchor": "[APP:SMOKE:USE]",
                    },
                }
            ],
            applicability_proof,
            require_critical_audit=True,
        )
        elementary_proof = (
            "The displayed Jacobian determinant equals 1, so the local holomorphic "
            "inverse-function theorem applies [ELM:SMOKE-IFT]."
        )
        validate_elementary_uses_for_submission(
            [
                {
                    "key": "SMOKE-IFT",
                    "result": "Holomorphic inverse-function theorem at one point",
                    "category": "local_inverse_implicit",
                    "hypothesis_witnesses": [
                        "The proof displays the holomorphic map and computes determinant 1."
                    ],
                    "used_conclusion": "A unique local holomorphic inverse germ exists.",
                    "scope_limitations": [
                        "Local germ only.",
                        "No family-uniform or monodromy conclusion.",
                    ],
                    "reconstruction": (
                        "Apply the finite-dimensional holomorphic inverse-function theorem at "
                        "the displayed point and restrict to sufficiently small neighborhoods."
                    ),
                    "proof_anchor": "[ELM:SMOKE-IFT]",
                }
            ],
            elementary_proof,
        )
        bare_citation = Fact(
            problem_id="smoke",
            author="worker",
            predecessors=[],
            statement="A bare citation should fail.",
            proof="Citation only.",
            external_refs=[
                {
                    "key": "BARE",
                    "title": "Uncertified source",
                    "url": "https://example.org/source",
                    "use_kind": "result",
                    "cited_for": "An unsupported step.",
                }
            ],
        )
        try:
            store.submit(bare_citation, worker="worker")
        except ValueError:
            pass
        else:
            raise RuntimeError("bare external citation passed the applicability gate")
        fact = Fact(
            problem_id="smoke",
            author="worker",
            predecessors=[],
            statement="For every integer n, n=n.",
            proof="This is reflexivity of equality.",
        )
        store.submit(fact, worker="worker")
        frozen = store.freeze_verification_packet(fact.fact_id)
        try:
            store.record_review(
                {
                    "fact_id": fact.fact_id,
                    "submission_sha256": frozen["submission_sha256"],
                    "packet_sha256": frozen["packet_sha256"],
                    "verdict": "correct",
                    "critical_errors": [],
                    "gaps": [],
                    "repair_hints": [],
                    "reviewer": "WORKER",
                }
            )
        except ValueError:
            pass
        else:
            raise RuntimeError("case-folded worker identity was allowed to self-review")
        review_id = review(store, fact.fact_id, reviewer="fresh-verifier")
        store.admit(fact.fact_id, review_id=review_id, gateway="smoke-gateway")
        store.admit(fact.fact_id, review_id=review_id, gateway="smoke-gateway")
        store.set_targets([fact.fact_id])

        stale = Fact(
            problem_id="smoke",
            author="second-worker",
            predecessors=[fact.fact_id],
            statement="Reflexivity has a second name.",
            proof=f"This is only a renaming of verified fact {fact.fact_id}.",
        )
        store.submit(stale, worker="second-worker")
        older_correct = review(store, stale.fact_id, reviewer="first-verifier")
        review(
            store,
            stale.fact_id,
            reviewer="adversarial-verifier",
            verdict="reject",
            errors=["The statement is not an atomic mathematical consequence."],
        )
        try:
            store.admit(stale.fact_id, review_id=older_correct)
        except ValueError:
            pass
        else:
            raise RuntimeError("an older clean review bypassed a later rejection")

        memory_id = store.memory_add(
            {
                "kind": "conjecture",
                "claim": "Use the smoke fact in one generated assignment.",
                "dependencies": [fact.fact_id],
                "suggested_actions": ["prove directly"],
            },
            actor="smoke-main",
        )
        manifest = create_round(store, workers=1, memory_ids=[memory_id])
        assignment = manifest["assignments"][0]
        if not Path(assignment["artifact_dir_path"]).is_dir():
            raise RuntimeError("schema-v3 assignment artifact directory is missing")
        return_path = Path(assignment["return_path"])
        return_path.write_text(
            json.dumps(
                {
                    "project_id": manifest["project_id"],
                    "round_id": manifest["round_id"],
                    "assignment_id": assignment["assignment_id"],
                    "assignment_sha256": assignment["assignment_sha256"],
                    "worker": assignment["worker_id"],
                    "memory_id": assignment["memory_id"],
                    "mode": assignment["mode"],
                    "outcome": "evidence",
                    "notes": "portable bound-return check",
                    "claim": "Reflexivity is reusable.",
                    "method": "Direct inspection.",
                    "result": {"value": True},
                    "artifacts": [],
                    "limitations": ["Evidence smoke test only."],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        validated = validate_return(
            store,
            manifest["round_id"],
            assignment["assignment_id"],
        )
        if validated["return_sha256"] != sha256_bytes(return_path.read_bytes()):
            raise RuntimeError("worker validate-return did not bind exact bytes")
        receipt = ingest_return(
            store,
            manifest["round_id"],
            assignment["assignment_id"],
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        replay = ingest_return(
            store,
            manifest["round_id"],
            assignment["assignment_id"],
            worker_final_sha256=sha256_bytes(return_path.read_bytes()),
        )
        if (
            receipt != replay
            or receipt.get("status") != "ingested"
            or receipt.get("schema_version") != 3
            or receipt.get("artifacts") != []
        ):
            raise RuntimeError("assignment-bound exactly-once ingestion failed")

        report = store.audit()
        if not report.ok or report.facts != 1 or report.target_closure != 1:
            raise RuntimeError(json.dumps(report.as_dict(), sort_keys=True))
        store.revoke(fact.fact_id, reason="smoke revocation", actor="smoke-gateway")
        try:
            store.admit(fact.fact_id, review_id=review_id, gateway="smoke-gateway")
        except ValueError:
            pass
        else:
            raise RuntimeError("revoked fact was re-admitted from stale state")

        old_skill_root = os.environ.get("MGRAPH_SKILL_ROOT")
        os.environ["MGRAPH_SKILL_ROOT"] = str(skill_root)
        try:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                code = cli_main(
                    [
                        "--root",
                        str(skill_root / "forbidden-project"),
                        "--role",
                        "operator",
                        "init",
                        "--project-id",
                        "forbidden",
                        "--title",
                        "Forbidden",
                    ]
                )
            if code == 0:
                raise RuntimeError("CLI allowed project state inside the skill")
        finally:
            if old_skill_root is None:
                os.environ.pop("MGRAPH_SKILL_ROOT", None)
            else:
                os.environ["MGRAPH_SKILL_ROOT"] = old_skill_root
        try:
            store.report_output_path("../escape.md")
        except ValueError:
            pass
        else:
            raise RuntimeError("report output escaped the project reports directory")

    with tempfile.TemporaryDirectory(prefix="mathgraph-v4-self-test-") as temporary:
        v4_root = Path(temporary) / "project"
        v4_store = MathGraphStore(v4_root)
        v4_store.initialize(
            project_id="v4-smoke",
            title="Portable schema-v4 round smoke test",
            workflow_evidence_version=4,
        )
        if v4_store.project().get("workflow_evidence_version") != 4:
            raise RuntimeError("explicit v4 project did not retain workflow version 4")
        paper_store = v4_store.paper_logic()
        paper_store.initialize(actor="self-test-main")
        paper_artifact = Path(temporary) / "paper-source.txt"
        paper_artifact_bytes = b"It does not follow."
        paper_artifact.write_bytes(paper_artifact_bytes)
        paper_text = paper_artifact_bytes.decode("utf-8")

        def paper_ledger(text: str) -> list[dict[str, object]]:
            return [
                {
                    "operator_id": f"op-{index}",
                    "token": item["token"],
                    "occurrence": item["occurrence"],
                    "kind": item["kind"],
                    "scope": "rendered sentence",
                    "disposition": "logical",
                    "depends_on": [],
                }
                for index, item in enumerate(
                    scan_high_risk_operators(text)
                )
            ]

        paper_nodes = [
            {
                "local_id": "s1",
                "object_type": "source_unit",
                "payload": {
                    "unit_kind": "sentence",
                    "order": 1,
                    "locator": {
                        "kind": "pdf",
                        "pdf_page_index": 0,
                        "printed_page_label": "1",
                        "region": "self-test sentence",
                    },
                    "text": paper_text,
                    "text_sha256": sha256_bytes(
                        paper_text.encode("utf-8")
                    ),
                    "speaker": "author",
                    "inspection_methods": ["rendered_primary"],
                    "render_sha256": sha256_bytes(b"self-test-render"),
                    "context_before": "",
                    "context_after": "",
                    "operator_ledger": paper_ledger(paper_text),
                },
            },
            {
                "local_id": "c1",
                "object_type": "claim",
                "payload": {
                    "representation_kind": "source_literal",
                    "attribution": "author",
                    "discourse_role": "premise",
                    "content_type": "conceptual",
                    "statement": paper_text,
                    "statement_sha256": sha256_bytes(
                        paper_text.encode("utf-8")
                    ),
                    "source_unit_ids": ["s1"],
                    "semantic_diff": "",
                    "modality": "asserted",
                    "scope_notes": "Self-test scope.",
                    "operator_ledger": paper_ledger(paper_text),
                    "definition_ids": [],
                    "parent_claim_id": "",
                },
            },
            {
                "local_id": "c2",
                "object_type": "claim",
                "payload": {
                    "representation_kind": "researcher_reconstruction",
                    "attribution": "researcher",
                    "discourse_role": "headline_conclusion",
                    "content_type": "conceptual",
                    "statement": "The bounded conclusion follows.",
                    "statement_sha256": sha256_bytes(
                        b"The bounded conclusion follows."
                    ),
                    "source_unit_ids": [],
                    "semantic_diff": (
                        "Explicit self-test reconstruction, not a quotation."
                    ),
                    "modality": "asserted",
                    "scope_notes": "Self-test scope.",
                    "operator_ledger": [],
                    "definition_ids": [],
                    "parent_claim_id": "",
                },
            },
            {
                "local_id": "i1",
                "object_type": "inference",
                "payload": {
                    "premise_ids": ["c1"],
                    "conclusion_id": "c2",
                    "inference_kind": "deductive",
                    "strength": "strict",
                    "authorial_status": "researcher_reconstructed",
                    "source_unit_ids": ["s1"],
                    "bridge_claim_ids": [],
                    "defeater_claim_ids": [],
                    "rationale": "Exercise exact ports and polarity.",
                },
            },
            {
                "local_id": "t1",
                "object_type": "paper_target",
                "payload": {
                    "target_role": "headline",
                    "claim_id": "c2",
                    "rationale": "Self-test headline.",
                },
            },
        ]
        paper_local_nodes = {
            item["local_id"]: item for item in paper_nodes
        }
        paper_bundle = {
            "schema_version": 1,
            "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
            "project_id": "v4-smoke",
            "paper_id": "self-test-paper",
            "graph_kind": "logic",
            "domain_profile": "philosophy",
            "builder": "paper-builder",
            "builder_context_id": "paper-builder-context",
            "source": {
                "artifact_sha256": sha256_bytes(paper_artifact_bytes),
                "artifact_locator": str(paper_artifact),
                "title": "Self-test paper",
                "version": "fixture-v1",
                "mime_type": "text/plain",
                "retrieved_at": "2026-07-26T00:00:00Z",
                "inspection_methods": ["rendered_primary"],
            },
            "base_snapshot_id": "",
            "supersedes_snapshot_id": "",
            "coverage": {
                "scope_kind": "bounded",
                "included_locators": ["pdf:0"],
                "excluded_locators": [],
                "units": [
                    {
                        "unit_id": "s1",
                        "classification": "argumentative",
                        "mapped_node_ids": [
                            "s1",
                            "c1",
                            "c2",
                            "i1",
                            "t1",
                        ],
                        "reason": "",
                    }
                ],
                "unresolved_load_bearing_units": [],
                "completeness_claim": "Complete for one bounded sentence.",
            },
            "nodes": paper_nodes,
            "edges": PaperLogicStore._expected_logic_edges(
                paper_local_nodes
            ),
        }
        paper_staged = paper_store.stage(
            paper_bundle,
            artifact_path=paper_artifact,
            actor="paper-builder",
        )
        paper_revision = paper_store.revision(
            paper_staged["revision_id"]
        )
        for index, profile in enumerate(
            paper_revision["required_review_profiles"],
            1,
        ):
            paper_store.record_review(
                {
                    "schema_version": 1,
                    "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
                    "project_id": "v4-smoke",
                    "revision_id": paper_revision["revision_id"],
                    "bundle_sha256": paper_revision["bundle_sha256"],
                    "profile": profile,
                    "verdict": "correct",
                    "reviewer": f"paper-reviewer-{index}",
                    "reviewer_context_id": (
                        f"paper-review-context-{index}"
                    ),
                    "fresh_context_contract": "fresh-context-v1",
                    "object_checks": [
                        {
                            "object_id": object_id,
                            "status": "pass",
                            "finding": "Self-test object check passed.",
                        }
                        for object_id in sorted(
                            paper_store._expected_review_object_ids(
                                paper_revision,
                                profile,
                            )
                        )
                    ],
                    "global_checks": [
                        {
                            "kind": kind,
                            "status": "pass",
                            "finding": "Self-test global check passed.",
                        }
                        for kind in sorted(REVIEW_GLOBAL_CHECKS[profile])
                    ],
                    "critical_errors": [],
                    "gaps": [],
                    "truth_effect": "none",
                }
            )
        paper_frozen = paper_store.freeze(
            paper_revision["revision_id"],
            actor="self-test-main",
        )
        paper_query = paper_store.query(
            paper_frozen["snapshot_id"],
            view="combined",
            query={
                "seed_ids": [],
                "direction": "both",
                "max_hops": 4,
                "node_budget": 32,
                "edge_budget": 64,
            },
        )
        if (
            paper_query["truth_effect"] != "none"
            or paper_query["omission"]["node_budget_hit"]
            or not paper_store.audit(blackboard=v4_store.blackboard())["ok"]
        ):
            raise RuntimeError("Paper Logic smoke failed")
        campaigns = v4_store.campaigns()

        def campaign_inventory() -> dict[str, str]:
            return {
                path.relative_to(campaigns.root).as_posix(): (
                    "directory"
                    if path.is_dir()
                    else sha256_bytes(path.read_bytes())
                )
                for path in sorted(campaigns.root.rglob("*"))
            }

        before_campaign_gate = campaign_inventory()
        try:
            campaigns.create(
                {
                    "name": "rejected-proof-target",
                    "objective": "Exercise the admitted-fact campaign gate.",
                    "source_claim_ids": [],
                    "targets": [
                        {
                            "role": "headline_proof",
                            "subject_kind": "fact",
                            "subject_id": "f" * 16,
                            "label": "Not admitted",
                        }
                    ],
                    "constraints": [],
                    "stop_conditions": [],
                    "value_definition": "Reject nontruth proof targets.",
                },
                actor="self-test",
                fact_exists=lambda _fact_id: False,
            )
        except ValueError as exc:
            if "not an active admitted fact" not in str(exc):
                raise
        else:
            raise RuntimeError("campaign creation bypassed the admitted-fact gate")
        if campaign_inventory() != before_campaign_gate:
            raise RuntimeError(
                "failed campaign creation left partial campaign state"
            )
        v4_memory_id = v4_store.memory_add(
            {
                "kind": "direction",
                "claim": "Check one exact toy case without promoting it to truth.",
                "rationale": "Exercise the v4 task-card and blackboard boundary.",
                "suggested_actions": ["compute one exact value"],
                "stop_conditions": ["Stop after one exact value is recorded."],
            },
            actor="v4-smoke-main",
        )
        v4_manifest = create_round(
            v4_store,
            workers=1,
            memory_ids=[v4_memory_id],
            mode="compute",
        )
        v4_assignment = v4_manifest["assignments"][0]
        v4_card_path = Path(v4_assignment["task_card_path"])
        v4_card = json.loads(v4_card_path.read_text(encoding="utf-8"))
        if v4_card.get("hard_caps") != DEFAULT_HARD_CAPS:
            raise RuntimeError(
                "v4 task card did not bind the fixed hard-cap profile"
            )
        pulse_store = v4_store.collaboration()
        pulse_plan = pulse_store.create_plan(
            wave1_commitments=[
                pulse_store.make_wave1_commitment(
                    round_id=v4_manifest["round_id"],
                    assignment_id=v4_assignment["assignment_id"],
                    criticality="core",
                )
            ],
            minimum_wave1_contributors=1,
            actor="v4-smoke-main",
        )
        v4_prompt_path = Path(v4_assignment["prompt_path"])
        if v4_prompt_path.stat().st_size >= 4096:
            raise RuntimeError("v4 compact worker prompt exceeded 4 KiB")
        root_space = v4_card["blackboard_view"]["write_space_ids"][0]
        evidence_node = make_node(
            node_type="computation_result",
            logical_key="v4-smoke-value",
            payload={"value": "1", "scope": "toy case only"},
            created_by_assignment_id=v4_card["assignment_id"],
        )
        placement = make_edge(
            edge_type="placed_in",
            source_node_id=evidence_node["node_id"],
            target_node_id=root_space,
            payload={},
            created_by_assignment_id=v4_card["assignment_id"],
        )
        v4_return_path = Path(v4_assignment["return_path"])
        v4_return_bytes = json.dumps(
            {
                "schema_version": 4,
                "policy_revision": "mathgraph-0.3.0",
                "protocol": "mathgraph-agent-v4",
                "project_id": v4_card["project_id"],
                "round_id": v4_card["round_id"],
                "assignment_id": v4_card["assignment_id"],
                "assignment_sha256": v4_card["assignment_sha256"],
                "task_card_sha256": sha256_bytes(
                    v4_card_path.read_bytes()
                ),
                "blackboard_snapshot_sha256": v4_card[
                    "blackboard_snapshot_sha256"
                ],
                "worker": v4_card["worker_id"],
                "memory_id": v4_card["memory_id"],
                "mode": v4_card["mode"],
                "outcome": "evidence",
                "obligation_ledger": [],
                "blackboard_graph_delta": {
                    "base_snapshot_id": v4_card["blackboard_view"][
                        "snapshot_id"
                    ],
                    "add_nodes": [evidence_node],
                    "add_edges": [placement],
                },
                "narrative_summary": (
                    "The exact value is exploration evidence, not an admitted fact."
                ),
                "claim": "The toy expression has value 1.",
                "method": "Exact evaluation.",
                "result": "The value is 1.",
                "artifacts": [],
                "limitations": ["One toy value proves no general statement."],
            },
            sort_keys=True,
        ).encode("utf-8")
        v4_draft_path = (
            Path(v4_assignment["work_dir_path"])
            / "self-test-return-draft.json"
        )
        v4_draft_path.write_bytes(v4_return_bytes)
        before_preflight = {
            path.relative_to(v4_root).as_posix(): path.read_bytes()
            for path in sorted(v4_root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }
        v4_preflight = preflight_return(
            v4_store,
            v4_manifest["round_id"],
            v4_assignment["assignment_id"],
            input_path=v4_draft_path,
        )
        after_preflight = {
            path.relative_to(v4_root).as_posix(): path.read_bytes()
            for path in sorted(v4_root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }
        if (
            before_preflight != after_preflight
            or v4_return_path.exists()
            or v4_preflight["return_sha256"]
            != sha256_bytes(v4_return_bytes)
        ):
            raise RuntimeError(
                "v4 return preflight was not an exact read-only dry run"
            )
        v4_return_path.write_bytes(v4_draft_path.read_bytes())
        v4_validated = validate_return(
            v4_store,
            v4_manifest["round_id"],
            v4_assignment["assignment_id"],
        )
        if (
            v4_validated["return_sha256"]
            != v4_preflight["return_sha256"]
        ):
            raise RuntimeError(
                "v4 preflight and canonical validation hashes differ"
            )
        v4_receipt = ingest_return(
            v4_store,
            v4_manifest["round_id"],
            v4_assignment["assignment_id"],
            worker_final_sha256=v4_validated["return_sha256"],
        )
        if (
            v4_receipt.get("schema_version") != 4
            or evidence_node["node_id"] not in v4_store.blackboard().nodes()
            or v4_store.fact_ids()
        ):
            raise RuntimeError("v4 evidence crossed the exploration/truth boundary")
        pulse_store.abort(
            pulse_plan["pulse_id"],
            failure_phase="self_test_terminal",
            reason=(
                "The portable smoke intentionally ends after Wave 1; "
                "preserve its core evidence without fabricating a review."
            ),
            actor="v4-smoke-main",
        )
        if pulse_store.status(pulse_plan["pulse_id"])["state"] != "aborted":
            raise RuntimeError("v4 pulse abort smoke did not reach terminal state")
        v4_report = v4_store.audit()
        if not v4_report.current_ok or not v4_report.history_clean:
            raise RuntimeError(json.dumps(v4_report.as_dict(), sort_keys=True))

    print(
        "SELF_TEST=PASS schema_v3=PASS schema_v4_round=PASS "
        "v4_blackboard=PASS admission_gate=PASS review_binding=PASS "
        "round_binding=PASS validate_return=PASS artifact_manifest=PASS "
        "applicability_gate=PASS critical_source_gate=PASS tiered_source_gate=PASS "
        "source_audit_hash=PASS elementary_gate=PASS "
        "audit=PASS revocation=PASS containment=PASS event_index=PASS "
        "parallel_blackboard_policy=PASS priority_ordering_policy=PASS "
        "actual_time_policy=PASS hard_caps=PASS pulse_abort=PASS "
        "preflight_return=PASS campaign_atomic_create=PASS "
        "paper_logic=PASS paper_review_gate=PASS "
        "reader_html=PASS skill_line_limit=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
