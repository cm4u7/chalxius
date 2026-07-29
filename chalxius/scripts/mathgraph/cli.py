from __future__ import annotations

import argparse
import json
import os
import re
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from .adoption import build_adoption_plan
from .fact_bundles import (
    build_expert_lint_receipt,
    build_interpret_lint_receipt,
    validate_claim_card,
    validate_interpret_card,
)
from .graph import DependencyGraph
from .migration import upgrade_stable_project_copy
from .model import Fact
from .orchestrator import (
    WORK_MODES,
    create_repair_round,
    create_round,
    create_verifier_assignment,
    ingest_return,
    preflight_return,
    round_status,
    validate_return,
)
from .contracts import (
    CLAIM_RELATIONS,
    POLICY_REVISION_V4,
    contained_path,
    require_exact_keys,
    require_string,
    sha256_bytes,
    sha256_json,
)
from .blackboard import make_edge, make_node
from .collaboration import FRESH_CONTEXT_CONTRACT_V1
from .roles import (
    KNOWN_ROLES,
    V4_BOUND_WORKER_QUERY_COMMANDS,
    allowed_bound_worker_queries_for_workflow,
    allowed_commands,
    allowed_commands_for_workflow,
)
from .store import MathGraphStore
from .modes import REASONING_MODES
from .reader_html import export_reader_html, export_reader_payload
from .v5_reader import build_v5_reader_packet
from .v5_assurance import (
    V5_ASSURANCE_CONTRACT_REVISION,
    V5_LEGACY_ASSURANCE_CONTRACT_REVISION,
)


V5_COMPATIBILITY_MUTATION_COMMANDS = {
    "fact-bundle-submit": "candidate-release",
    "fact-bundle-record-review": "certification-record",
    "fact-bundle-admit": "fact-admit",
}


def _json_file(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected one JSON object in {path}")
    return payload


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _v5_fact_bundle_release(
    store: MathGraphStore,
    payload: dict[str, Any],
    *,
    worker: str,
) -> dict[str, Any]:
    """Map the V4 FactBundle convenience surface to one V5 release."""

    require_exact_keys(
        payload,
        required={
            "schema_version",
            "policy_revision",
            "project_id",
            "facts",
            "bundle_claim",
        },
        optional={"fact_bundle_id"},
        label="V5 FactBundle compatibility input",
    )
    if (
        payload.get("schema_version") != 4
        or payload.get("policy_revision") != POLICY_REVISION_V4
        or payload.get("project_id") != store.project_id()
    ):
        raise ValueError("V5 FactBundle compatibility input has wrong schema/project")
    bundle_claim = require_string(payload, "bundle_claim")
    fact_payloads = payload.get("facts")
    if (
        not isinstance(fact_payloads, list)
        or len(fact_payloads) < 2
        or any(not isinstance(item, dict) for item in fact_payloads)
    ):
        raise ValueError("V5 FactBundle compatibility requires at least two Facts")
    facts = [Fact.from_dict(item) for item in fact_payloads]
    fact_ids = {fact.fact_id for fact in facts}
    internal_edges = [
        [predecessor, fact.fact_id]
        for fact in facts
        for predecessor in fact.predecessors
        if predecessor in fact_ids
    ]
    if not internal_edges:
        raise ValueError(
            "V5 atomic FactBundle requires an internal predecessor edge; "
            "release independent Facts separately"
        )
    if any(fact.computational_evidence for fact in facts):
        raise ValueError(
            "FactBundle compatibility input cannot bind computation artifacts; "
            "use candidate-release for load-bearing computation"
        )
    lifecycle = store.v5_lifecycle()
    research = lifecycle.add_research(
        {
            "kind": "proof_attempt",
            "claim": bundle_claim,
            "content": "Atomic FactBundle compatibility submission: "
            + ", ".join(sorted(fact_ids)),
            "bundle_input_schema": 4,
            "legacy_fact_bundle_id": payload.get("fact_bundle_id"),
        },
        actor=worker,
    )
    return lifecycle.candidate_release(
        {
            "schema_version": 5,
            "bundle_claim": bundle_claim,
            "candidates": [fact.as_submission_dict() for fact in facts],
            "research_entry_ids": [research["research_id"]],
            "claim_relation": "proves",
            "artifacts": [],
            "verification_plan": {
                "mode": "closed_capsule",
                "authorized_artifact_roles": [],
                "required_checks": [
                    "mathematical",
                    "typing",
                    "scope",
                    "source_and_applicability",
                    "predecessor_interfaces",
                    "computation_replay",
                    "challenge_dispositions",
                    "assurance_scope",
                ],
            },
            "requested_assurance": {
                "validation_subject": {
                    "kind": "theorem",
                    "subject_id": facts[-1].fact_id,
                    "artifact_sha256": None,
                    "load_bearing_node_ids": [],
                },
                "validation_granularity": "atomic_fact_dag",
                "coverage": [],
            },
            "challenge_dispositions": [],
            "paper_evidence_refs": [],
            "adverse_actor_ids": [],
        },
        producer=worker,
    )


def _strict_frozen_worker_task_card(
    store: MathGraphStore,
    task_card_path: str | None,
) -> dict[str, Any]:
    """Load bytes that exactly match one task card in its frozen round."""

    if task_card_path is None:
        raise ValueError("bound worker query requires --task-card")
    supplied_path = Path(task_card_path).expanduser()
    if supplied_path.is_symlink() or not supplied_path.is_file():
        raise ValueError("bound worker task card is missing or unsafe")
    supplied_bytes = supplied_path.read_bytes()
    try:
        task_card = json.loads(supplied_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("bound worker task card is not valid UTF-8 JSON") from exc
    if not isinstance(task_card, dict):
        raise ValueError("bound worker task card must be one JSON object")

    if task_card.get("schema_version") == 5:
        store.v5_lifecycle().validate_task_card(
            task_card,
            expected_path=supplied_path,
        )
        round_path = (
            store.rounds_dir
            / task_card["round_id"]
            / "round.json"
        )
        manifest = _json_file(str(round_path))
        matches = [
            assignment
            for assignment in manifest.get("assignments", [])
            if isinstance(assignment, dict)
            and assignment.get("assignment_id")
            == task_card["assignment_id"]
        ]
        if len(matches) != 1:
            raise ValueError(
                "bound V5 worker task card assignment is not uniquely frozen"
            )
        assignment = matches[0]
        frozen_path = contained_path(
            store.root,
            require_string(assignment, "task_card_relpath"),
            "bound V5 worker frozen task card path",
        )
        if (
            frozen_path.is_symlink()
            or not frozen_path.is_file()
            or frozen_path.read_bytes() != supplied_bytes
            or sha256_bytes(supplied_bytes)
            != assignment.get("task_card_sha256")
        ):
            raise ValueError(
                "bound V5 worker task card bytes differ from the frozen card"
            )
        return task_card

    # Reuse the experiment layer's full project/round/assignment/hash binding.
    # The additional raw-byte comparison below is stricter than object equality:
    # a reformatted or copied-and-edited card is not the frozen capability.
    store.experiments()._validate_bound_task_card(task_card)
    round_path = (
        store.rounds_dir
        / require_string(task_card, "round_id")
        / "round.json"
    )
    round_manifest = _json_file(str(round_path))
    assignments = round_manifest.get("assignments")
    if not isinstance(assignments, list):
        raise ValueError("bound worker round assignments are invalid")
    matches = [
        assignment
        for assignment in assignments
        if isinstance(assignment, dict)
        and assignment.get("assignment_id") == task_card["assignment_id"]
    ]
    if len(matches) != 1:
        raise ValueError("bound worker task card assignment is not uniquely frozen")
    frozen_path = contained_path(
        store.root,
        require_string(matches[0], "task_card_relpath"),
        "bound worker frozen task card path",
    )
    if (
        frozen_path.is_symlink()
        or not frozen_path.is_file()
        or frozen_path.read_bytes() != supplied_bytes
    ):
        raise ValueError("bound worker task card bytes differ from the frozen round card")
    return task_card


def _authorize_bound_worker_query(
    store: MathGraphStore,
    args: argparse.Namespace,
) -> None:
    if (
        args.role != "worker"
        or args.command not in V4_BOUND_WORKER_QUERY_COMMANDS
    ):
        return
    task_card = _strict_frozen_worker_task_card(
        store,
        getattr(args, "task_card", None),
    )
    if args.command == "claim-show":
        allowed_id = task_card["source_claim_id"]
        requested_id = args.claim_id
        authorized = isinstance(allowed_id, str) and requested_id == allowed_id
    elif args.command == "convention-show":
        requested_id = args.convention_id
        authorized = requested_id in task_card["convention_profile_ids"]
    elif args.command == "campaign-status":
        requested_id = args.campaign_id
        if requested_id is None:
            raise ValueError(
                "bound worker campaign-status requires an explicit campaign_id"
            )
        authorized = requested_id == task_card["campaign_id"]
        if authorized:
            if (
                "campaign_snapshot_relpath" not in task_card
                or "campaign_snapshot_sha256" not in task_card
            ):
                raise ValueError(
                    "bound worker campaign-status requires a frozen "
                    "campaign snapshot"
                )
            snapshot_path = contained_path(
                store.root,
                task_card["campaign_snapshot_relpath"],
                "bound worker campaign snapshot path",
            )
            if (
                snapshot_path.is_symlink()
                or not snapshot_path.is_file()
                or sha256_bytes(snapshot_path.read_bytes())
                != task_card["campaign_snapshot_sha256"]
            ):
                raise ValueError(
                    "bound worker campaign snapshot bytes/hash mismatch"
                )
            frozen_campaign = _json_file(str(snapshot_path))
            if frozen_campaign.get("campaign_id") != requested_id:
                raise ValueError(
                    "bound worker campaign snapshot id mismatch"
                )
            args.bound_campaign_status = frozen_campaign
    elif args.command == "blackboard-show":
        requested_id = args.object_id
        nodes, edges = store.blackboard().snapshot_objects(
            task_card["blackboard_view"]["snapshot_id"]
        )
        authorized = requested_id in nodes or requested_id in edges
        if authorized:
            args.bound_snapshot_object = (
                nodes.get(requested_id) or edges[requested_id]
            )
    else:
        requested_id = args.snapshot_id
        authorized = (
            requested_id == task_card["blackboard_view"]["snapshot_id"]
        )
    if not authorized:
        raise ValueError(
            f"{args.command} id is not authorized by the frozen task card"
        )


READ_ONLY_COMMANDS = {
    "status",
    "audit",
    "show",
    "search",
    "closure",
    "context",
    "targets",
    "frontier",
    "adoption-plan",
    "round-status",
    "profile-closure-status",
    "preflight-return",
    "validate-return",
    "novelty-status",
    "claim-show",
    "convention-show",
    "campaign-status",
    "blackboard-show",
    "blackboard-query",
    "blackboard-snapshot-query",
    "pulse-status",
    "pulse-audit",
    "experiment-status",
    "paper-logic-status",
    "paper-logic-show",
    "paper-logic-query",
    "paper-logic-audit",
    "verifier-capsule",
    "candidate-release-check",
    "certification-decision-check",
    "make-bundle-verifier-task",
    "fact-bundle-verifier-task",
    "mode-status",
    "attack-route-status",
    "attack-report",
    "fact-graph-inventory",
    "fact-graph-append-target",
}


def _command_requires_mutation_lock(args: argparse.Namespace) -> bool:
    """Serialize every project mutation exposed by the CLI.

    Subsystems share files and projections, so locking only an individual
    JSONL append is insufficient.  Copy migration is excluded because its
    destination must not exist before the staging transaction begins.
    """

    if args.command == "upgrade-project-copy":
        return False
    if args.command == "upgrade-workflow" and args.dry_run:
        return False
    if args.command == "ingest-return":
        # The orchestrator owns one complete validation/effect/pulse-failure
        # transaction so CLI exceptions cannot escape outside its lock.
        return False
    if args.command == "blackboard-reindex":
        return bool(args.apply)
    return args.command not in READ_ONLY_COMMANDS


def _mermaid(store: MathGraphStore, target: str = "") -> str:
    facts = store.facts()
    graph = DependencyGraph(facts)
    selected = graph.closure([target]) if target else set(facts)
    targets = set(store.targets())
    lines = ["flowchart TD"]
    for fact_id in graph.topological_order(selected):
        statement = re.sub(r"\s+", " ", facts[fact_id].statement).strip()
        label = statement[:68].replace('"', "'")
        lines.append(f'  f{fact_id}["{fact_id}<br/>{label}"]')
        if fact_id in targets:
            lines.append(f"  class f{fact_id} target")
    for fact_id in selected:
        for predecessor in graph.predecessors[fact_id]:
            if predecessor in selected:
                lines.append(f"  f{predecessor} --> f{fact_id}")
    lines.extend(
        [
            "  classDef target fill:#7c3aed,color:#fff,stroke:#4c1d95,stroke-width:3px",
            "  classDef default fill:#f8fafc,color:#0f172a,stroke:#94a3b8",
        ]
    )
    return "\n".join(lines) + "\n"


def _authorized_fact_graph_inventory(
    current_store: MathGraphStore,
    source_root_value: str,
) -> dict[str, Any]:
    source_root = Path(source_root_value).expanduser()
    if source_root.is_symlink():
        raise ValueError("Fact Graph inventory source root must not be a symlink")
    source_root = source_root.resolve()
    if not source_root.is_dir():
        raise ValueError("Fact Graph inventory source root is not a directory")
    source_store = MathGraphStore(source_root)
    if source_store.workflow_evidence_version() != 5:
        raise ValueError("Fact Graph inventory currently requires a V5 source project")
    lifecycle = source_store.v5_lifecycle()
    active_paths = lifecycle.active_fact_paths()
    active_facts: list[dict[str, Any]] = []
    for fact_id, path in sorted(active_paths.items()):
        release_id = path.parent.parent.name
        marker, admitted_paths = lifecycle._validated_admission(release_id)
        if fact_id not in admitted_paths:
            raise ValueError("Fact Graph inventory admission/path binding drifted")
        release = lifecycle.release(release_id)
        decision = lifecycle.decision(marker["decision_id"])
        interface = source_store.statement_interface(fact_id, materialize=False)
        active_facts.append(
            {
                "fact_id": fact_id,
                "fact_sha256": sha256_bytes(path.read_bytes()),
                "interface_sha256": interface["interface_sha256"],
                "interface_schema_version": interface["schema_version"],
                "release_id": release_id,
                "release_sha256": release["release_sha256"],
                "decision_id": decision["decision_id"],
                "decision_sha256": decision["decision_sha256"],
                "gateway": marker["gateway"],
                "acceptance_id": marker["acceptance_id"],
            }
        )
    source_project_id = source_store.project_id()
    current_project_id = current_store.project_id()
    audit = lifecycle.audit().as_dict()
    admitted_release_ids = sorted(
        {item["release_id"] for item in active_facts}
    )
    all_release_ids = sorted(
        path.stem
        for path in lifecycle.candidate_releases_dir.glob("release-*.json")
        if path.is_file() and not path.is_symlink()
    )
    return {
        "schema_version": 1,
        "authorization": "explicit_user_cli_read_only",
        "source_root": str(source_root),
        "source_project_id": source_project_id,
        "current_project_id": current_project_id,
        "project_id_compatibility": (
            "same_project_append_compatible"
            if source_project_id == current_project_id
            else "different_project_no_fact_authority_transfer"
        ),
        "active_fact_count": len(active_facts),
        "active_facts": active_facts,
        "revoked_fact_ids": sorted(lifecycle.revoked_fact_ids()),
        "unadmitted_or_inactive_release_ids": sorted(
            set(all_release_ids).difference(admitted_release_ids)
        ),
        "source_audit": {
            key: audit[key]
            for key in (
                "current_ok",
                "history_clean",
                "facts",
                "edges",
                "errors",
                "trust_debt",
            )
        },
        "available_actions": [
            "read_only_lineage_reference_no_authority",
            "select_this_exact_project_as_future_append_target",
        ],
        "automatic_inheritance": False,
        "federation": False,
        "truth_effect": "none",
        "project_effect": "none",
    }


def _authorized_fact_graph_append_target(
    current_store: MathGraphStore,
    *,
    source_root: str,
    expected_project_id: str,
) -> dict[str, Any]:
    inventory = _authorized_fact_graph_inventory(current_store, source_root)
    if inventory["source_project_id"] != expected_project_id:
        raise ValueError("append-target expected project id does not match source")
    audit = inventory["source_audit"]
    if not audit["current_ok"] or not audit["history_clean"]:
        raise ValueError("append target must have a clean current and historical audit")
    return {
        "schema_version": 1,
        "authorization": "explicit_user_cli_append_target_selection",
        "append_target_root": inventory["source_root"],
        "append_target_project_id": inventory["source_project_id"],
        "active_fact_ids": [
            item["fact_id"] for item in inventory["active_facts"]
        ],
        "current_root_unchanged": True,
        "cross_project_fact_import": False,
        "automatic_inheritance": False,
        "federation": False,
        "next_step": "run future lifecycle commands with --root append_target_root",
        "truth_effect": "none",
        "project_effect": "none",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mgraph",
        description=(
            "Source-bound paper audit, verifier-gated fact graph, and "
            "multi-agent research bridge"
        ),
    )
    parser.add_argument(
        "--root",
        required=True,
        help="explicit project store directory (never defaults inside the skill)",
    )
    parser.add_argument(
        "--host-config",
        help=(
            "explicit cooperative host-adapter JSON; otherwise "
            "PROJECT/host_adapter.json is used when present"
        ),
    )
    role_from_environment = os.environ.get("MGRAPH_ROLE")
    parser.add_argument(
        "--role",
        default=role_from_environment,
        required=role_from_environment is None,
        choices=KNOWN_ROLES,
        help=(
            "operator, main, host, worker, paper-auditor, verifier, or gateway"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init")
    p.add_argument("--project-id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument(
        "--workflow-version",
        type=int,
        default=5,
        choices=(4, 5),
    )
    p.add_argument(
        "--reasoning-mode",
        default="auto",
        choices=REASONING_MODES,
    )

    p = sub.add_parser("mode-init")
    p.add_argument("--mode", default="auto", choices=REASONING_MODES)
    p.add_argument("--actor", required=True)
    p.add_argument("--reason", required=True)

    sub.add_parser("mode-status")

    p = sub.add_parser("mode-switch")
    p.add_argument("--to", required=True, choices=REASONING_MODES)
    p.add_argument("--actor", required=True)
    p.add_argument("--reason", required=True)

    p = sub.add_parser("work-unit-abort")
    p.add_argument("round_id")
    p.add_argument("--actor", required=True)
    p.add_argument("--reason", required=True)

    sub.add_parser("status")
    p = sub.add_parser("audit")
    p.add_argument("--strict-history", action="store_true")

    p = sub.add_parser("upgrade-workflow")
    p.add_argument("--to", type=int, required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--actor", default="")
    p.add_argument(
        "--confirm-isolated-copy",
        action="store_true",
        help=(
            "required for low-level apply; prefer upgrade-project-copy "
            "for stable inheritance"
        ),
    )

    p = sub.add_parser("upgrade-project-copy")
    p.add_argument("--source", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--actor", default="")

    p = sub.add_parser("show")
    p.add_argument("fact_id")

    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)

    p = sub.add_parser("closure")
    p.add_argument("fact_ids", nargs="+")

    p = sub.add_parser("context")
    p.add_argument("fact_id")
    p.add_argument("--max-nodes", type=int, default=20)

    sub.add_parser("targets")

    p = sub.add_parser("set-targets")
    p.add_argument("fact_ids", nargs="*")

    p = sub.add_parser("submit")
    p.add_argument("--input", required=True)
    p.add_argument("--worker", required=True)
    p.add_argument("--task-id", default="")
    p.add_argument(
        "--claim-relation",
        default="proves",
        choices=sorted(CLAIM_RELATIONS),
    )

    p = sub.add_parser("packet")
    p.add_argument("fact_id")

    p = sub.add_parser("record-review")
    p.add_argument("--input", required=True)

    p = sub.add_parser("admit")
    p.add_argument("fact_id")
    p.add_argument("--review-id", required=True)
    p.add_argument("--gateway", default="local-gateway")

    p = sub.add_parser("revoke")
    p.add_argument("fact_id")
    p.add_argument("--reason", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("candidate-release")
    p.add_argument("--input", required=True)
    p.add_argument("--producer", required=True)

    p = sub.add_parser("candidate-release-check")
    p.add_argument("--input", required=True)
    p.add_argument("--producer", required=True)

    p = sub.add_parser("verifier-capsule")
    p.add_argument("release_id")

    p = sub.add_parser("certification-record")
    p.add_argument("--input", required=True)

    p = sub.add_parser("certification-decision-check")
    p.add_argument("--input", required=True)

    p = sub.add_parser("fact-admit")
    p.add_argument("release_id")
    p.add_argument("--decision-id", required=True)
    p.add_argument("--gateway", required=True)

    p = sub.add_parser("memory-add")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)
    p.add_argument(
        "--current-assurance",
        action="store_true",
        help=(
            "require project-relative path/SHA-256/role source capabilities; "
            "legacy remains the compatibility default"
        ),
    )

    p = sub.add_parser("memory-update")
    p.add_argument("entry_id")
    p.add_argument("--status", required=True)
    p.add_argument("--actor", required=True)
    p.add_argument("--note", default="")
    p.add_argument("--resolution-fact-id")
    p.add_argument("--claim-relation", choices=sorted(CLAIM_RELATIONS))
    p.add_argument("--related-fact-id")

    p = sub.add_parser("frontier")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--campaign")
    p.add_argument("--all-active", action="store_true")
    p.add_argument("--no-collapse-repairs", action="store_true")
    p.add_argument("--history", action="store_true")

    p = sub.add_parser("adoption-plan")
    p.add_argument("--input", required=True)

    p = sub.add_parser("plan-round")
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--mode", default="auto", choices=("auto", *WORK_MODES))
    p.add_argument("--memory-id", action="append", dest="memory_ids")
    p.add_argument(
        "--host-task-scope-id",
        help=(
            "stable host task/thread identifier; defaults to "
            "MATHGRAPH_HOST_TASK_SCOPE_ID or CODEX_THREAD_ID"
        ),
    )
    p.add_argument(
        "--background-chunk-id",
        action="append",
        dest="background_chunk_ids",
        help=(
            "exact chunk id from project-background-index; repeat to bind an "
            "explicit Main-planner selection into new V5 cards"
        ),
    )
    sub.add_parser("project-background-index")
    p = sub.add_parser("project-background-read")
    p.add_argument("chunk_id")
    p.add_argument("--task-card")

    p = sub.add_parser("fact-graph-inventory")
    p.add_argument("--source-root", required=True)

    p = sub.add_parser("fact-graph-append-target")
    p.add_argument("--source-root", required=True)
    p.add_argument("--expected-project-id", required=True)
    p = sub.add_parser("round-status")
    p.add_argument("round_id")

    p = sub.add_parser("profile-closure-status")
    p.add_argument("round_id")

    p = sub.add_parser("profile-closure-record")
    p.add_argument("round_id")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("preflight-return")
    p.add_argument("round_id")
    p.add_argument("assignment_id")
    p.add_argument("--input", required=True)

    p = sub.add_parser("validate-return")
    p.add_argument("round_id")
    p.add_argument("assignment_id")

    p = sub.add_parser("ingest-return")
    p.add_argument("round_id")
    p.add_argument("assignment_id")
    p.add_argument(
        "--worker-final-sha256",
        required=True,
        help="SHA-256 reported in the worker's explicit final handoff",
    )

    p = sub.add_parser("attack-route-enable")
    p.add_argument("--actor", required=True)
    p.add_argument("--reason", required=True)

    sub.add_parser("attack-route-status")

    p = sub.add_parser("attack-report")
    p.add_argument("--host-task-scope-id", required=True)

    p = sub.add_parser("attack-route-decide")
    p.add_argument("proposal_id")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("attack-route-disable")
    p.add_argument("rule_id")
    p.add_argument("--reason", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("make-verifier-task")
    p.add_argument("fact_id")
    p.add_argument(
        "--authorized-artifact",
        action="append",
        default=None,
        metavar="KEY:ROLE",
    )
    p.add_argument("--supersedes-bundle-id")
    p.add_argument("--prior-review-id")

    p = sub.add_parser("plan-repair-round")
    p.add_argument("memory_id")
    p.add_argument("--trigger-memory-id")
    p = sub.add_parser("novelty-record")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("novelty-status")
    p.add_argument("subject_id")

    p = sub.add_parser("export-mermaid")
    p.add_argument("--target", default="")
    p.add_argument("--output", required=True)

    p = sub.add_parser(
        "export-reader-html",
        help=(
            "deterministically overwrite "
            "PROJECT/visualizations/knowledge-map.html from a validated "
            "nontruth reader packet"
        ),
    )
    reader_source = p.add_mutually_exclusive_group(required=True)
    reader_source.add_argument(
        "--packet",
        help="UTF-8 reader-packet JSON prepared by the Chalxius host step",
    )
    reader_source.add_argument(
        "--v5-projection",
        action="store_true",
        help="deterministically project the current V5 project into packet v1",
    )
    p = sub.add_parser("import-danus")
    p.add_argument("archive")

    p = sub.add_parser("claim-add")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("claim-variant")
    p.add_argument("parent_claim_id")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("claim-show")
    p.add_argument("claim_id")
    p.add_argument("--task-card")

    p = sub.add_parser("convention-add")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("convention-show")
    p.add_argument("convention_id")
    p.add_argument("--task-card")

    p = sub.add_parser("campaign-create")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("campaign-activate")
    p.add_argument("campaign_id")
    p.add_argument("--actor", required=True)

    p = sub.add_parser("campaign-update")
    p.add_argument("campaign_id")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("campaign-status")
    p.add_argument("campaign_id", nargs="?")
    p.add_argument("--task-card")

    p = sub.add_parser("campaign-target-add")
    p.add_argument("campaign_id")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("campaign-target-archive")
    p.add_argument("campaign_id")
    p.add_argument("target_id")
    p.add_argument("--reason", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("blackboard-type-register")
    p.add_argument("--kind", required=True, choices=("node", "edge"))
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("blackboard-space-create")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("blackboard-node-add")
    p.add_argument("--input", required=True)
    p.add_argument("--space", action="append", dest="space_ids", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("blackboard-edge-add")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("blackboard-show")
    p.add_argument("object_id")
    p.add_argument("--task-card")

    p = sub.add_parser("blackboard-query")
    p.add_argument("--input", required=True)

    p = sub.add_parser("blackboard-snapshot")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("blackboard-snapshot-query")
    p.add_argument("snapshot_id")
    p.add_argument("--input", required=True)
    p.add_argument("--task-card")

    p = sub.add_parser("blackboard-reindex")
    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--apply", action="store_true")
    p.add_argument("--actor", default="")

    p = sub.add_parser("blackboard-promote-node")
    p.add_argument("node_id")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("paper-logic-init")
    p.add_argument("--actor", required=True)

    p = sub.add_parser("paper-logic-stage")
    p.add_argument("--input", required=True)
    p.add_argument("--artifact", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("paper-logic-record-review")
    p.add_argument("--input", required=True)

    p = sub.add_parser("paper-logic-freeze")
    p.add_argument("revision_id")
    p.add_argument("--actor", required=True)

    p = sub.add_parser("paper-logic-status")
    p.add_argument("revision_id", nargs="?", default="")

    p = sub.add_parser("paper-logic-show")
    p.add_argument("object_id")
    p.add_argument("--snapshot", default="")

    p = sub.add_parser("paper-logic-query")
    p.add_argument("snapshot_id")
    p.add_argument(
        "--view",
        required=True,
        choices=(
            "source",
            "reconstruction",
            "audit",
            "current_audit",
            "combined",
        ),
    )
    p.add_argument("--input", required=True)

    p = sub.add_parser("paper-logic-link-exploration")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    p = sub.add_parser("paper-logic-project-blackboard")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", required=True)

    sub.add_parser("paper-logic-audit")

    p = sub.add_parser("pulse-plan")
    p.add_argument("--input", required=True)
    p.add_argument("--actor", default="main")

    p = sub.add_parser("pulse-barrier")
    p.add_argument("pulse_id")
    p.add_argument("--after-snapshot-id", required=True)
    p.add_argument("--input", required=True)
    p.add_argument("--actor", default="main")

    p = sub.add_parser("pulse-void")
    p.add_argument("pulse_id")
    p.add_argument("commitment_id")
    p.add_argument("--reason", required=True)
    p.add_argument("--actor", default="operator")

    p = sub.add_parser("pulse-abort")
    p.add_argument("pulse_id")
    p.add_argument("--failure-phase", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--actor", default="main")

    p = sub.add_parser("pulse-dispatch")
    p.add_argument("pulse_id")
    p.add_argument("commitment_id")
    p.add_argument("--issuer", required=True)
    p.add_argument("--host-context-id", required=True)
    p.add_argument("--agent-identity", required=True)
    p.add_argument(
        "--fresh-context-contract",
        required=True,
        choices=("fresh-context-v1",),
    )

    p = sub.add_parser("pulse-close")
    p.add_argument("pulse_id")
    p.add_argument("--actor", default="main")

    p = sub.add_parser("pulse-status")
    p.add_argument("pulse_id")

    p = sub.add_parser("pulse-audit")
    p.add_argument("pulse_id", nargs="?")

    p = sub.add_parser("experiment-start")
    p.add_argument("--task-card", required=True)
    p.add_argument("--input", required=True)

    p = sub.add_parser("experiment-event")
    p.add_argument("experiment_id")
    p.add_argument("--task-card", required=True)
    p.add_argument("--input", required=True)

    p = sub.add_parser("experiment-observe")
    p.add_argument("--task-card", required=True)
    p.add_argument("--input", required=True)

    p = sub.add_parser("experiment-decision")
    p.add_argument("--task-card", required=True)
    p.add_argument("--input", required=True)

    p = sub.add_parser("experiment-resume")
    p.add_argument("experiment_id")
    p.add_argument("--task-card", required=True)
    p.add_argument("--checkpoint-event-id", required=True)
    p.add_argument("--compatibility", required=True)

    p = sub.add_parser("experiment-status")
    p.add_argument("experiment_id")
    p.add_argument("--task-card", required=True)

    p = sub.add_parser("experiment-finalize")
    p.add_argument("experiment_id")
    p.add_argument("--task-card", required=True)
    p.add_argument("--select", action="append", required=True)

    p = sub.add_parser("fact-bundle-submit")
    p.add_argument("--input", required=True)
    p.add_argument("--worker", required=True)

    for command in (
        "make-bundle-verifier-task",
        "fact-bundle-verifier-task",
    ):
        p = sub.add_parser(command)
        p.add_argument("fact_bundle_id")

    p = sub.add_parser("fact-bundle-record-review")
    p.add_argument("fact_bundle_id")
    p.add_argument("--input", required=True)

    p = sub.add_parser("fact-bundle-admit")
    p.add_argument("fact_bundle_id")
    p.add_argument("--review-id", required=True)

    p = sub.add_parser("export-claim-card")
    p.add_argument("fact_id")
    p.add_argument(
        "--audience",
        required=True,
        choices=("expert", "advisor", "publication"),
    )
    p.add_argument("--output", required=True)

    p = sub.add_parser("lint-expert-document")
    p.add_argument("--input", required=True)
    p.add_argument("--claim-card", required=True)
    p.add_argument(
        "--receipt-output",
        help=(
            "write-once project report path; defaults to a deterministic "
            "reports/expert-lint-receipts entry"
        ),
    )

    p = sub.add_parser("export-interpret-card")
    p.add_argument("node_id")
    p.add_argument(
        "--audience",
        required=True,
        choices=("expert", "advisor", "publication"),
    )
    p.add_argument("--output", required=True)

    p = sub.add_parser("lint-interpret-document")
    p.add_argument("--input", required=True)
    p.add_argument("--interpret-card", required=True)
    p.add_argument(
        "--receipt-output",
        help=(
            "write-once project report path; defaults to a deterministic "
            "reports/interpret-lint-receipts entry"
        ),
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    potential_bound_worker_query = (
        args.role == "worker"
        and args.command in V4_BOUND_WORKER_QUERY_COMMANDS
    )
    if (
        args.command not in allowed_commands(args.role)
        and not potential_bound_worker_query
    ):
        print(
            f"role {args.role!r} is not allowed to run {args.command!r}; "
            "unknown roles fail closed to no permissions",
            file=sys.stderr,
        )
        return 3
    stack = ExitStack()
    try:
        root = Path(args.root).expanduser().resolve()
        skill_root_raw = os.environ.get("MGRAPH_SKILL_ROOT")
        if skill_root_raw:
            skill_root = Path(skill_root_raw).expanduser().resolve()
            if root == skill_root or skill_root in root.parents:
                raise ValueError(
                    "project root must be outside the installed skill/deployment directory"
                )
        store = MathGraphStore(
            root,
            host_config_path=args.host_config,
        )
        if (
            store.project_path.exists()
            and store.workflow_evidence_version() >= 4
            and _command_requires_mutation_lock(args)
            and args.command not in {"mode-init", "upgrade-workflow"}
            and not store.reasoning_modes().is_initialized()
        ):
            raise ValueError(
                "legacy Chalk V4 project is read-only in the unified engine; "
                "run mode-init explicitly before any new write"
            )
        if args.role == "worker" and args.command != "init":
            workflow_version = store.workflow_evidence_version()
            worker_commands = allowed_commands_for_workflow(
                args.role,
                workflow_version,
            ) | allowed_bound_worker_queries_for_workflow(
                args.role,
                workflow_version,
            )
            if args.command not in worker_commands:
                print(
                    f"role {args.role!r} is not allowed to run "
                    f"{args.command!r} in this workflow-evidence version",
                    file=sys.stderr,
                )
                return 3
            _authorize_bound_worker_query(store, args)
        if (
            args.command == "upgrade-workflow"
            and not args.dry_run
            and not args.confirm_isolated_copy
        ):
            raise ValueError(
                "low-level workflow apply requires "
                "--confirm-isolated-copy; prefer upgrade-project-copy"
            )
        if _command_requires_mutation_lock(args):
            if (
                store.project_path.exists()
                and store.workflow_evidence_version() == 5
            ):
                stack.enter_context(
                    store.v5_mutation_lock(
                        command=V5_COMPATIBILITY_MUTATION_COMMANDS.get(
                            args.command, args.command
                        )
                    )
                )
            else:
                stack.enter_context(store.mutation_lock())
        if args.command == "init":
            store.initialize(
                project_id=args.project_id,
                title=args.title,
                description=args.description,
                workflow_evidence_version=args.workflow_version,
                reasoning_mode=args.reasoning_mode,
            )
            result = {
                "project": store.project(),
                "reasoning_mode": store.reasoning_modes().status(),
            }
            if store.workflow_evidence_version() == 5:
                result["lifecycle"] = store.v5_lifecycle().status()
            _print_json(result)
        elif args.command == "mode-init":
            _print_json(
                store.reasoning_modes().initialize(
                    reasoning_mode=args.mode,
                    actor=args.actor,
                    reason=args.reason,
                    source_kind="legacy_chalk_v4_upgrade",
                )
            )
        elif args.command == "mode-status":
            _print_json(store.reasoning_modes().status())
        elif args.command == "mode-switch":
            _print_json(
                store.reasoning_modes().switch(
                    to_mode=args.to,
                    actor=args.actor,
                    reason=args.reason,
                )
            )
        elif args.command == "work-unit-abort":
            _print_json(
                store.reasoning_modes().abort_work_unit(
                    round_id=args.round_id,
                    actor=args.actor,
                    reason=args.reason,
                )
            )
        elif args.command == "status":
            workflow_version = store.workflow_evidence_version()
            result = {
                "project": store.project(),
                "reasoning_mode": store.reasoning_modes().status(),
                "audit": store.audit().as_dict(),
                "targets": store.targets(),
                "frontier": (
                    store.v5_lifecycle().frontier(limit=5)
                    if workflow_version == 5
                    else store.frontier(limit=5)
                ),
            }
            if workflow_version == 5:
                result["lifecycle"] = store.v5_lifecycle().status()
            _print_json(result)
        elif args.command == "audit":
            report = store.audit()
            _print_json(report.as_dict())
            return (
                0
                if report.ok
                and (not args.strict_history or report.history_clean)
                else 2
            )
        elif args.command == "upgrade-workflow":
            if not args.dry_run and not args.confirm_isolated_copy:
                raise ValueError(
                    "low-level workflow apply requires "
                    "--confirm-isolated-copy; prefer upgrade-project-copy"
                )
            _print_json(
                store.upgrade_workflow(
                    to_version=args.to,
                    dry_run=args.dry_run,
                    actor=args.actor,
                )
            )
        elif args.command == "upgrade-project-copy":
            _print_json(
                upgrade_stable_project_copy(
                    source=args.source,
                    destination=root,
                    actor=args.actor,
                    dry_run=args.dry_run,
                )
            )
        elif args.command == "show":
            print(store.get_raw_fact(args.fact_id), end="")
        elif args.command == "search":
            _print_json(store.search(args.query, limit=args.limit))
        elif args.command == "closure":
            _print_json({"facts": store.closure(args.fact_ids)})
        elif args.command == "context":
            rendered = store.bounded_context(args.fact_id, max_nodes=args.max_nodes)
            print(rendered, end="")
        elif args.command == "targets":
            _print_json({"targets": store.targets()})
        elif args.command == "set-targets":
            store.set_targets(args.fact_ids)
            _print_json({"targets": store.targets()})
        elif args.command == "submit":
            fact = Fact.from_dict(_json_file(args.input))
            if store.workflow_evidence_version() == 5:
                lifecycle = store.v5_lifecycle()
                if args.task_id:
                    research_id = args.task_id
                    lifecycle._research_record(research_id)
                else:
                    research = lifecycle.add_research(
                        {
                            "kind": "proof_attempt",
                            "claim": fact.statement,
                            "content": fact.proof,
                            "dependencies": fact.predecessors,
                        },
                        actor=args.worker,
                    )
                    research_id = research["research_id"]
                release = lifecycle.candidate_release(
                    {
                        "schema_version": 5,
                        "bundle_claim": fact.statement,
                        "candidates": [fact.as_submission_dict()],
                        "research_entry_ids": [research_id],
                        "claim_relation": args.claim_relation,
                        "artifacts": [],
                        "verification_plan": {
                            "mode": "closed_capsule",
                            "authorized_artifact_roles": [],
                            "required_checks": [
                                "mathematical",
                                "typing",
                                "scope",
                                "source_and_applicability",
                                "predecessor_interfaces",
                                "computation_replay",
                                "challenge_dispositions",
                                "assurance_scope",
                            ],
                        },
                        "requested_assurance": {
                            "validation_subject": {
                                "kind": "theorem",
                                "subject_id": fact.fact_id,
                                "artifact_sha256": None,
                                "load_bearing_node_ids": [],
                            },
                            "validation_granularity": "monolithic_theorem",
                            "coverage": [],
                        },
                        "challenge_dispositions": [],
                        "paper_evidence_refs": [],
                        "adverse_actor_ids": [],
                    },
                    producer=args.worker,
                )
                _print_json(
                    {
                        "submission_id": fact.fact_id,
                        "release_id": release["release_id"],
                        "status": "candidate_released",
                    }
                )
            else:
                fact_id = store.submit(
                    fact,
                    worker=args.worker,
                    task_id=args.task_id,
                    claim_relation=args.claim_relation,
                )
                _print_json(
                    {"submission_id": fact_id, "status": "pending_review"}
                )
        elif args.command == "packet":
            if store.workflow_evidence_version() == 5:
                release = store.v5_lifecycle().release_for_fact(args.fact_id)
                _print_json(
                    store.v5_lifecycle().verifier_capsule(
                        release["release_id"]
                    )
                )
            else:
                packet = store.verification_packet(args.fact_id)
                print(packet, end="")
        elif args.command == "record-review":
            if store.workflow_evidence_version() == 5:
                decision = store.v5_lifecycle().certification_record(
                    _json_file(args.input)
                )
                _print_json(
                    {
                        "review_id": decision["decision_id"],
                        "decision_id": decision["decision_id"],
                        "release_id": decision["release_id"],
                        "verdict": decision["verdict"],
                        "clean": decision["verdict"] == "correct",
                        "status": "recorded",
                    }
                )
            else:
                path = store.record_review(_json_file(args.input))
                recorded = store.review(path.stem)
                clean = recorded["verdict"] == "correct" and (
                    not recorded.get("findings", [])
                    if recorded.get("schema_version") == 4
                    else not recorded["critical_errors"] and not recorded["gaps"]
                )
                _print_json(
                    {
                        "review_id": path.stem,
                        "review": str(path),
                        "fact_id": recorded["fact_id"],
                        "verdict": recorded["verdict"],
                        "clean": clean,
                        "status": "recorded",
                    }
                )
        elif args.command == "admit":
            if store.workflow_evidence_version() == 5:
                release = store.v5_lifecycle().release_for_fact(args.fact_id)
                marker = store.v5_lifecycle().fact_admit(
                    release_id=release["release_id"],
                    decision_id=args.review_id,
                    gateway=args.gateway,
                )
                _print_json(
                    {
                        "fact_id": args.fact_id,
                        "fact_ids": marker["fact_ids"],
                        "acceptance_id": marker["acceptance_id"],
                        "status": "accepted",
                    }
                )
            else:
                fact_id = store.admit(
                    args.fact_id,
                    review_id=args.review_id,
                    gateway=args.gateway,
                )
                _print_json({"fact_id": fact_id, "status": "accepted"})
        elif args.command == "revoke":
            if store.workflow_evidence_version() == 5:
                revoked = store.v5_lifecycle().revoke(
                    args.fact_id, reason=args.reason, actor=args.actor
                )
            else:
                revoked = store.revoke(
                    args.fact_id, reason=args.reason, actor=args.actor
                )
            _print_json({"revoked": revoked})
        elif args.command == "candidate-release":
            release = store.v5_lifecycle().candidate_release(
                _json_file(args.input), producer=args.producer
            )
            _print_json(
                {
                    "release_id": release["release_id"],
                    "release_sha256": release["release_sha256"],
                    "fact_ids": release["fact_ids"],
                    "status": "sealed_nontruth",
                }
            )
        elif args.command == "candidate-release-check":
            _print_json(
                store.v5_lifecycle().candidate_release(
                    _json_file(args.input),
                    producer=args.producer,
                    preflight_only=True,
                )
            )
        elif args.command == "verifier-capsule":
            _print_json(store.v5_lifecycle().verifier_capsule(args.release_id))
        elif args.command == "certification-record":
            decision = store.v5_lifecycle().certification_record(
                _json_file(args.input)
            )
            _print_json(
                {
                    "decision_id": decision["decision_id"],
                    "release_id": decision["release_id"],
                    "verdict": decision["verdict"],
                    "status": "recorded",
                }
            )
        elif args.command == "certification-decision-check":
            _print_json(
                store.v5_lifecycle().certification_record(
                    _json_file(args.input),
                    preflight_only=True,
                )
            )
        elif args.command == "fact-admit":
            marker = store.v5_lifecycle().fact_admit(
                release_id=args.release_id,
                decision_id=args.decision_id,
                gateway=args.gateway,
            )
            _print_json(
                {
                    "acceptance_id": marker["acceptance_id"],
                    "fact_ids": marker["fact_ids"],
                    "status": "accepted",
                }
            )
        elif args.command == "memory-add":
            if store.workflow_evidence_version() == 5:
                record = store.v5_lifecycle().add_research(
                    _json_file(args.input),
                    actor=args.actor,
                    assurance_contract_revision=(
                        V5_ASSURANCE_CONTRACT_REVISION
                        if args.current_assurance
                        else V5_LEGACY_ASSURANCE_CONTRACT_REVISION
                    ),
                )
                _print_json(
                    {
                        "memory_id": record["research_id"],
                        "research_id": record["research_id"],
                        "status": record["status"],
                    }
                )
            else:
                entry_id = store.memory_add(
                    _json_file(args.input), actor=args.actor
                )
                _print_json({"memory_id": entry_id})
        elif args.command == "memory-update":
            if store.workflow_evidence_version() == 5:
                disposition = store.v5_lifecycle().update_research(
                    args.entry_id,
                    status=args.status,
                    actor=args.actor,
                    note=args.note,
                    resolution_fact_id=args.resolution_fact_id,
                    claim_relation=args.claim_relation,
                    related_fact_id=args.related_fact_id,
                )
                _print_json(
                    {
                        "memory_id": args.entry_id,
                        "research_id": args.entry_id,
                        "status": args.status,
                        "disposition_id": disposition["research_id"],
                    }
                )
            else:
                store.memory_update(
                    args.entry_id,
                    status=args.status,
                    actor=args.actor,
                    note=args.note,
                    resolution_fact_id=args.resolution_fact_id,
                    claim_relation=args.claim_relation,
                    related_fact_id=args.related_fact_id,
                )
                _print_json(
                    {"memory_id": args.entry_id, "status": args.status}
                )
        elif args.command == "frontier":
            if store.workflow_evidence_version() == 5:
                _print_json(
                    store.v5_lifecycle().frontier(
                        limit=args.limit,
                        include_history=args.history,
                    )
                )
            else:
                _print_json(
                    store.frontier(
                        limit=args.limit,
                        campaign_id=args.campaign,
                        actionable=not args.all_active,
                        collapse_repairs=not args.no_collapse_repairs,
                        include_history=args.history,
                    )
                )
        elif args.command == "adoption-plan":
            _print_json(build_adoption_plan(_json_file(args.input)))
        elif args.command == "plan-round":
            if store.workflow_evidence_version() == 5:
                _print_json(
                    store.v5_lifecycle().create_round(
                        workers=args.workers,
                        mode=args.mode,
                        research_ids=args.memory_ids,
                        host_task_scope_id=args.host_task_scope_id,
                        background_chunk_ids=args.background_chunk_ids,
                    )
                )
            else:
                if args.background_chunk_ids:
                    raise ValueError(
                        "background chunk selection is available only for V5 planning"
                    )
                _print_json(
                    create_round(
                        store,
                        workers=args.workers,
                        mode=args.mode,
                        memory_ids=args.memory_ids,
                        host_task_scope_id=args.host_task_scope_id,
                    )
                )
        elif args.command == "project-background-index":
            if store.workflow_evidence_version() != 5:
                raise ValueError("project-background-index requires a V5 project")
            if args.role not in {"main", "operator"}:
                raise ValueError(
                    "project-background-index requires main or operator role"
                )
            _print_json(store.v5_lifecycle().project_background_index())
        elif args.command == "project-background-read":
            if store.workflow_evidence_version() != 5:
                raise ValueError("project-background-read requires a V5 project")
            if args.task_card is None:
                if args.role not in {"main", "operator"}:
                    raise ValueError(
                        "a worker project-background-read requires --task-card"
                    )
                _print_json(
                    store.v5_lifecycle().current_project_background_chunk(
                        args.chunk_id
                    )
                )
            else:
                if args.role not in {"worker", "main", "operator"}:
                    raise ValueError("role may not read a frozen background chunk")
                card = _strict_frozen_worker_task_card(store, args.task_card)
                _print_json(
                    store.v5_lifecycle().project_background_chunk(
                        card=card,
                        chunk_id=args.chunk_id,
                    )
                )
        elif args.command == "fact-graph-inventory":
            _print_json(
                _authorized_fact_graph_inventory(store, args.source_root)
            )
        elif args.command == "fact-graph-append-target":
            _print_json(
                _authorized_fact_graph_append_target(
                    store,
                    source_root=args.source_root,
                    expected_project_id=args.expected_project_id,
                )
            )
        elif args.command == "round-status":
            if store.workflow_evidence_version() == 5:
                _print_json(store.v5_lifecycle().round_status(args.round_id))
            else:
                _print_json(round_status(store, args.round_id))
        elif args.command == "profile-closure-status":
            if store.workflow_evidence_version() == 5:
                _print_json(
                    store.v5_lifecycle().process_readiness_status(
                        args.round_id
                    )
                )
            else:
                _print_json(store.profile_closures().status(args.round_id))
        elif args.command == "profile-closure-record":
            if store.workflow_evidence_version() == 5:
                _print_json(
                    store.v5_lifecycle().record_process_readiness(
                        args.round_id,
                        _json_file(args.input),
                        actor=args.actor,
                    )
                )
            else:
                _print_json(
                    store.profile_closures().record(
                        args.round_id,
                        _json_file(args.input),
                        actor=args.actor,
                    )
                )
        elif args.command == "preflight-return":
            if store.workflow_evidence_version() == 5:
                _print_json(
                    store.v5_lifecycle().preflight_return(
                        round_id=args.round_id,
                        assignment_id=args.assignment_id,
                        input_path=Path(args.input),
                    )
                )
            else:
                _print_json(
                    preflight_return(
                        store,
                        args.round_id,
                        args.assignment_id,
                        input_path=args.input,
                    )
                )
        elif args.command == "validate-return":
            if store.workflow_evidence_version() == 5:
                _print_json(
                    store.v5_lifecycle().preflight_return(
                        round_id=args.round_id,
                        assignment_id=args.assignment_id,
                    )
                )
            else:
                _print_json(
                    validate_return(store, args.round_id, args.assignment_id)
                )
        elif args.command == "ingest-return":
            if store.workflow_evidence_version() == 5:
                _print_json(
                    store.v5_lifecycle().ingest_return(
                        round_id=args.round_id,
                        assignment_id=args.assignment_id,
                        worker_final_sha256=args.worker_final_sha256,
                    )
                )
            else:
                _print_json(
                    ingest_return(
                        store,
                        args.round_id,
                        args.assignment_id,
                        worker_final_sha256=args.worker_final_sha256,
                    )
                )
        elif args.command == "attack-route-enable":
            _print_json(
                store.adverse_routes().initialize(
                    actor=args.actor,
                    reason=args.reason,
                )
            )
        elif args.command == "attack-route-status":
            _print_json(store.adverse_routes().status())
        elif args.command == "attack-report":
            _print_json(
                store.adverse_routes().report(
                    host_task_scope_id=args.host_task_scope_id
                )
            )
        elif args.command == "attack-route-decide":
            _print_json(
                store.adverse_routes().decide(
                    args.proposal_id,
                    _json_file(args.input),
                    actor=args.actor,
                )
            )
        elif args.command == "attack-route-disable":
            _print_json(
                store.adverse_routes().disable(
                    args.rule_id,
                    reason=args.reason,
                    actor=args.actor,
                )
            )
        elif args.command == "make-verifier-task":
            if store.workflow_evidence_version() == 5:
                release = store.v5_lifecycle().release_for_fact(args.fact_id)
                capsule = store.v5_lifecycle().verifier_capsule(
                    release["release_id"]
                )
                if args.authorized_artifact is not None:
                    requested_roles = {
                        item.split(":", 1)[1]
                        for item in args.authorized_artifact
                        if ":" in item and item.split(":", 1)[1]
                    }
                    actual_roles = {
                        item["role"] for item in capsule["authorized_artifacts"]
                    }
                    if requested_roles != actual_roles:
                        raise ValueError(
                            "V5 verifier artifact roles are sealed by Candidate Release"
                        )
                _print_json(capsule)
            else:
                authorized_artifacts = None
                if args.authorized_artifact is not None:
                    authorized_artifacts = []
                    for item in args.authorized_artifact:
                        if ":" not in item:
                            raise ValueError(
                                "--authorized-artifact must be KEY:ROLE"
                            )
                        key, role = item.split(":", 1)
                        if not key or not role:
                            raise ValueError(
                                "--authorized-artifact must be KEY:ROLE"
                            )
                        authorized_artifacts.append(
                            {"key": key, "role": role}
                        )
                _print_json(
                    create_verifier_assignment(
                        store,
                        args.fact_id,
                        authorized_artifacts=authorized_artifacts,
                        supersedes_bundle_id=args.supersedes_bundle_id,
                        prior_review_id=args.prior_review_id,
                    )
                )
        elif args.command == "plan-repair-round":
            if store.workflow_evidence_version() == 5:
                _print_json(
                    store.v5_lifecycle().create_repair_round(
                        args.memory_id,
                        trigger_research_id=args.trigger_memory_id,
                    )
                )
            else:
                _print_json(
                    create_repair_round(
                        store,
                        args.memory_id,
                        trigger_memory_id=args.trigger_memory_id,
                    )
                )
        elif args.command == "novelty-record":
            if store.workflow_evidence_version() == 5:
                event_id = store.v5_lifecycle().novelty_record(
                    _json_file(args.input),
                    actor=args.actor,
                )
            else:
                event_id = store.novelty_record(
                    _json_file(args.input),
                    actor=args.actor,
                )
            _print_json({"event_id": event_id, "status": "recorded"})
        elif args.command == "novelty-status":
            records = (
                store.v5_lifecycle().novelty_status(args.subject_id)
                if store.workflow_evidence_version() == 5
                else store.novelty_status(args.subject_id)
            )
            _print_json(
                {
                    "subject_id": args.subject_id,
                    "records": records,
                }
            )
        elif args.command == "export-mermaid":
            output = store.report_output_path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(_mermaid(store, target=args.target), encoding="utf-8")
            _print_json({"output": str(output)})
        elif args.command == "export-reader-html":
            if args.v5_projection:
                _print_json(
                    export_reader_payload(
                        store,
                        build_v5_reader_packet(
                        store,
                        ),
                    )
                )
            else:
                _print_json(export_reader_html(store, args.packet))
        elif args.command == "import-danus":
            _print_json(store.import_danus_zip(args.archive))
        elif args.command == "claim-add":
            claim_id = store.claims().add_claim(
                _json_file(args.input),
                actor=args.actor,
            )
            _print_json({"claim_id": claim_id, "status": "recorded"})
        elif args.command == "claim-variant":
            claim_id = store.claims().create_variant(
                args.parent_claim_id,
                _json_file(args.input),
                actor=args.actor,
            )
            _print_json({"claim_id": claim_id, "status": "recorded"})
        elif args.command == "claim-show":
            _print_json(store.claims().show_claim(args.claim_id))
        elif args.command == "convention-add":
            convention_id = store.claims().add_convention(
                _json_file(args.input),
                actor=args.actor,
            )
            _print_json(
                {"convention_id": convention_id, "status": "recorded"}
            )
        elif args.command == "convention-show":
            _print_json(
                store.claims().show_convention(args.convention_id)
            )
        elif args.command == "campaign-create":
            admitted_fact_ids = set(store.fact_ids())
            campaign_id = store.campaigns().create(
                _json_file(args.input),
                actor=args.actor,
                fact_exists=admitted_fact_ids.__contains__,
            )
            _print_json(
                {"campaign_id": campaign_id, "status": "recorded"}
            )
        elif args.command == "campaign-activate":
            campaigns = store.campaigns()
            campaigns.activate(args.campaign_id, actor=args.actor)
            targets = store.sync_active_campaign_targets(
                campaign_id=args.campaign_id,
            )
            _print_json(
                {
                    "campaign_id": args.campaign_id,
                    "status": "active",
                    "targets": targets,
                }
            )
        elif args.command == "campaign-update":
            event_id = store.campaigns().update(
                args.campaign_id,
                _json_file(args.input),
                actor=args.actor,
            )
            _print_json({"event_id": event_id, "status": "recorded"})
        elif args.command == "campaign-status":
            if args.role == "worker":
                _print_json(args.bound_campaign_status)
            else:
                campaign_id = args.campaign_id or store.campaigns().active()
                if campaign_id is None:
                    raise ValueError("there is no active campaign")
                _print_json(store.campaigns().status(campaign_id))
        elif args.command == "campaign-target-add":
            campaigns = store.campaigns()
            target_id = campaigns.target_add(
                args.campaign_id,
                _json_file(args.input),
                actor=args.actor,
                fact_exists=lambda fact_id: (
                    fact_id in set(store.fact_ids())
                ),
            )
            if campaigns.active() == args.campaign_id:
                store.sync_active_campaign_targets(
                    campaign_id=args.campaign_id
                )
            _print_json({"target_id": target_id, "status": "recorded"})
        elif args.command == "campaign-target-archive":
            campaigns = store.campaigns()
            campaigns.target_archive(
                args.campaign_id,
                args.target_id,
                reason=args.reason,
                actor=args.actor,
            )
            if campaigns.active() == args.campaign_id:
                store.sync_active_campaign_targets(
                    campaign_id=args.campaign_id
                )
            _print_json(
                {"target_id": args.target_id, "status": "archived"}
            )
        elif args.command == "blackboard-type-register":
            registry_id = store.blackboard().register_type(
                kind=args.kind,
                definition=_json_file(args.input),
                actor=args.actor,
            )
            _print_json(
                {"registry_id": registry_id, "status": "recorded"}
            )
        elif args.command == "blackboard-space-create":
            payload = _json_file(args.input)
            space_id = store.blackboard().create_space(
                name=str(payload.get("name", "")),
                scope=str(payload.get("scope", "")),
                actor=args.actor,
                parent_space_id=payload.get("parent_space_id"),
                overlaps_with=payload.get("overlaps_with"),
            )
            store.blackboard().reindex(apply=True, actor=args.actor)
            _print_json({"space_id": space_id, "status": "recorded"})
        elif args.command == "blackboard-node-add":
            payload = _json_file(args.input)
            node = (
                payload
                if "node_id" in payload
                else make_node(
                    node_type=str(payload.get("node_type", "")),
                    logical_key=str(payload.get("logical_key", "")),
                    payload=dict(payload.get("payload", {})),
                    truth_status=str(
                        payload.get("truth_status", "exploration")
                    ),
                    convention_profile_ids=list(
                        payload.get("convention_profile_ids", [])
                    ),
                    source_refs=list(payload.get("source_refs", [])),
                    type_version=int(payload.get("type_version", 1)),
                    created_by_assignment_id=args.actor,
                )
            )
            receipt = store.blackboard().add_node_with_placements(
                node=node,
                space_ids=args.space_ids,
                actor=args.actor,
            )
            store.blackboard().reindex(apply=True, actor=args.actor)
            _print_json(receipt)
        elif args.command == "blackboard-edge-add":
            payload = _json_file(args.input)
            edge = (
                payload
                if "edge_id" in payload
                else make_edge(
                    edge_type=str(payload.get("edge_type", "")),
                    source_node_id=str(
                        payload.get("source_node_id", "")
                    ),
                    target_node_id=str(
                        payload.get("target_node_id", "")
                    ),
                    payload=dict(payload.get("payload", {})),
                    type_version=int(payload.get("type_version", 1)),
                    created_by_assignment_id=args.actor,
                )
            )
            receipt = store.blackboard().add_objects(
                nodes=[],
                edges=[edge],
                actor=args.actor,
            )
            store.blackboard().reindex(apply=True, actor=args.actor)
            _print_json(receipt)
        elif args.command == "blackboard-show":
            _print_json(
                args.bound_snapshot_object
                if args.role == "worker"
                else store.blackboard().show(args.object_id)
            )
        elif args.command == "blackboard-query":
            _print_json(store.blackboard().query(_json_file(args.input)))
        elif args.command == "blackboard-snapshot":
            _print_json(
                store.blackboard().snapshot(
                    query=_json_file(args.input),
                    actor=args.actor,
                )
            )
        elif args.command == "blackboard-snapshot-query":
            _print_json(
                store.blackboard().snapshot_query(
                    snapshot_id=args.snapshot_id,
                    query=_json_file(args.input),
                )
            )
        elif args.command == "blackboard-reindex":
            if args.apply and args.role != "operator":
                raise ValueError(
                    "blackboard reindex --apply requires the operator role"
                )
            _print_json(
                store.blackboard().reindex(
                    apply=args.apply,
                    actor=args.actor,
                )
            )
        elif args.command == "blackboard-promote-node":
            workflow_version = store.workflow_evidence_version()

            def add_promoted_research(
                payload: dict[str, Any],
                actor: str,
            ) -> str:
                if workflow_version == 5:
                    return store.v5_lifecycle().add_research(
                        payload,
                        actor=actor,
                    )["research_id"]
                return store.memory_add(payload, actor=actor)

            memory_id = store.campaigns().promote_blackboard_node(
                args.node_id,
                _json_file(args.input),
                actor=args.actor,
                memory_add=add_promoted_research,
            )
            result = {"memory_id": memory_id, "status": "promoted"}
            if workflow_version == 5:
                result["research_id"] = memory_id
            _print_json(result)
        elif args.command == "paper-logic-init":
            _print_json(
                store.paper_logic().initialize(actor=args.actor)
            )
        elif args.command == "paper-logic-stage":
            _print_json(
                store.paper_logic().stage(
                    _json_file(args.input),
                    artifact_path=args.artifact,
                    actor=args.actor,
                )
            )
        elif args.command == "paper-logic-record-review":
            _print_json(
                store.paper_logic().record_review(
                    _json_file(args.input)
                )
            )
        elif args.command == "paper-logic-freeze":
            _print_json(
                store.paper_logic().freeze(
                    args.revision_id,
                    actor=args.actor,
                )
            )
        elif args.command == "paper-logic-status":
            _print_json(
                store.paper_logic().status(args.revision_id)
            )
        elif args.command == "paper-logic-show":
            _print_json(
                store.paper_logic().show(
                    args.object_id,
                    snapshot_id=args.snapshot,
                )
            )
        elif args.command == "paper-logic-query":
            _print_json(
                store.paper_logic().query(
                    args.snapshot_id,
                    view=args.view,
                    query=_json_file(args.input),
                )
            )
        elif args.command == "paper-logic-link-exploration":
            _print_json(
                store.paper_logic().link_exploration(
                    _json_file(args.input),
                    actor=args.actor,
                    blackboard=store.blackboard(),
                )
            )
        elif args.command == "paper-logic-project-blackboard":
            _print_json(
                store.paper_logic().project_to_blackboard(
                    _json_file(args.input),
                    actor=args.actor,
                    blackboard=store.blackboard(),
                )
            )
        elif args.command == "paper-logic-audit":
            report = store.paper_logic().audit(
                blackboard=store.blackboard()
            )
            _print_json(report)
            return 0 if report["ok"] else 2
        elif args.command == "pulse-plan":
            payload = _json_file(args.input)
            require_exact_keys(
                payload,
                required={"wave1_assignments"},
                optional={"minimum_wave1_contributors"},
                label="pulse plan input",
            )
            assignments = payload["wave1_assignments"]
            if (
                not isinstance(assignments, list)
                or not assignments
                or any(not isinstance(item, dict) for item in assignments)
            ):
                raise ValueError(
                    "pulse plan wave1_assignments must be nonempty objects"
                )
            pulse = store.collaboration()
            commitments = []
            for item in assignments:
                require_exact_keys(
                    item,
                    required={"round_id", "assignment_id"},
                    optional={"criticality", "minimum_peer_nodes"},
                    label="pulse wave-1 assignment",
                )
                commitments.append(
                    pulse.make_wave1_commitment(
                        round_id=require_string(item, "round_id"),
                        assignment_id=require_string(
                            item, "assignment_id"
                        ),
                        criticality=str(
                            item.get("criticality", "core")
                        ),
                        minimum_peer_nodes=int(
                            item.get("minimum_peer_nodes", 1)
                        ),
                    )
                )
            _print_json(
                pulse.create_plan(
                    wave1_commitments=commitments,
                    minimum_wave1_contributors=int(
                        payload.get(
                            "minimum_wave1_contributors",
                            min(2, len(commitments)),
                        )
                    ),
                    actor=args.actor,
                )
            )
        elif args.command == "pulse-barrier":
            payload = _json_file(args.input)
            require_exact_keys(
                payload,
                required={"review_assignments"},
                label="pulse barrier input",
            )
            assignments = payload["review_assignments"]
            if (
                not isinstance(assignments, list)
                or not assignments
                or any(not isinstance(item, dict) for item in assignments)
            ):
                raise ValueError(
                    "pulse barrier review_assignments must be nonempty objects"
                )
            pulse = store.collaboration()
            commitments = []
            for item in assignments:
                require_exact_keys(
                    item,
                    required={
                        "round_id",
                        "assignment_id",
                        "peer_node_id",
                    },
                    optional={
                        "criticality",
                        "allowed_edge_types",
                        "peer_project_id",
                    },
                    label="pulse cross-review assignment",
                )
                allowed = item.get("allowed_edge_types")
                if allowed is not None and (
                    not isinstance(allowed, list)
                    or any(not isinstance(value, str) for value in allowed)
                ):
                    raise ValueError(
                        "pulse allowed_edge_types must be strings"
                    )
                commitments.append(
                    pulse.make_review_commitment(
                        pulse_id=args.pulse_id,
                        round_id=require_string(item, "round_id"),
                        assignment_id=require_string(
                            item, "assignment_id"
                        ),
                        peer_node_id=require_string(
                            item, "peer_node_id"
                        ),
                        criticality=str(
                            item.get("criticality", "core")
                        ),
                        allowed_edge_types=allowed,
                        peer_project_id=item.get("peer_project_id"),
                    )
                )
            _print_json(
                pulse.derive_barrier(
                    args.pulse_id,
                    after_snapshot_id=args.after_snapshot_id,
                    review_commitments=commitments,
                    actor=args.actor,
                )
            )
        elif args.command == "pulse-void":
            _print_json(
                store.collaboration().void_optional(
                    args.pulse_id,
                    args.commitment_id,
                    reason=args.reason,
                    actor=args.actor,
                )
            )
        elif args.command == "pulse-abort":
            _print_json(
                store.collaboration().abort(
                    args.pulse_id,
                    failure_phase=args.failure_phase,
                    reason=args.reason,
                    actor=args.actor,
                )
            )
        elif args.command == "pulse-dispatch":
            _print_json(
                store.collaboration().record_host_dispatch(
                    args.pulse_id,
                    args.commitment_id,
                    issuer=args.issuer,
                    host_context_id=args.host_context_id,
                    agent_identity=args.agent_identity,
                    fresh_context_contract=(
                        dict(FRESH_CONTEXT_CONTRACT_V1)
                    ),
                )
            )
        elif args.command == "pulse-close":
            _print_json(
                store.collaboration().derive_closure(
                    args.pulse_id,
                    actor=args.actor,
                )
            )
        elif args.command == "pulse-status":
            _print_json(
                store.collaboration().status(args.pulse_id)
            )
        elif args.command == "pulse-audit":
            _print_json(
                store.collaboration().audit(args.pulse_id)
            )
        elif args.command == "experiment-start":
            _print_json(
                store.experiments().start(
                    task_card=_json_file(args.task_card),
                    manifest=_json_file(args.input),
                )
            )
        elif args.command == "experiment-event":
            event_id = store.experiments().event(
                task_card=_json_file(args.task_card),
                experiment_id=args.experiment_id,
                payload=_json_file(args.input),
            )
            _print_json({"event_id": event_id, "status": "recorded"})
        elif args.command == "experiment-observe":
            _print_json(
                store.experiments().observe(
                    task_card=_json_file(args.task_card),
                    payload=_json_file(args.input),
                    actor_role=args.role,
                )
            )
        elif args.command == "experiment-decision":
            _print_json(
                store.experiments().decision(
                    task_card=_json_file(args.task_card),
                    payload=_json_file(args.input),
                    actor_role=args.role,
                )
            )
        elif args.command == "experiment-resume":
            _print_json(
                store.experiments().resume(
                    task_card=_json_file(args.task_card),
                    experiment_id=args.experiment_id,
                    checkpoint_event_id=args.checkpoint_event_id,
                    current_compatibility=_json_file(args.compatibility),
                )
            )
        elif args.command == "experiment-status":
            _print_json(
                store.experiments().status(
                    task_card=_json_file(args.task_card),
                    experiment_id=args.experiment_id,
                )
            )
        elif args.command == "experiment-finalize":
            _print_json(
                store.experiments().finalize(
                    task_card=_json_file(args.task_card),
                    experiment_id=args.experiment_id,
                    selected_paths=args.select,
                )
            )
        elif args.command == "fact-bundle-submit":
            if store.workflow_evidence_version() == 5:
                release = _v5_fact_bundle_release(
                    store, _json_file(args.input), worker=args.worker
                )
                fact_bundle_id = release["release_id"]
                status = "sealed_nontruth"
            else:
                fact_bundle_id = store.fact_bundles().submit(
                    _json_file(args.input),
                    worker=args.worker,
                    external_fact_exists=lambda fact_id: (
                        fact_id in set(store.fact_ids())
                    ),
                )
                status = "pending_review"
            result = {"fact_bundle_id": fact_bundle_id, "status": status}
            if store.workflow_evidence_version() == 5:
                result["release_id"] = fact_bundle_id
            _print_json(result)
        elif args.command in {
            "make-bundle-verifier-task",
            "fact-bundle-verifier-task",
        }:
            if store.workflow_evidence_version() == 5:
                _print_json(
                    store.v5_lifecycle().verifier_capsule(args.fact_bundle_id)
                )
            else:
                _print_json(
                    store.fact_bundle_verifier_task(args.fact_bundle_id)
                )
        elif args.command == "fact-bundle-record-review":
            if store.workflow_evidence_version() == 5:
                decision = store.v5_lifecycle().certification_record(
                    _json_file(args.input)
                )
                if decision["release_id"] != args.fact_bundle_id:
                    raise ValueError(
                        "FactBundle compatibility decision targets another release"
                    )
                review_id = decision["decision_id"]
            else:
                review_id = store.record_fact_bundle_review(
                    args.fact_bundle_id,
                    _json_file(args.input),
                )
            _print_json({"review_id": review_id, "status": "recorded"})
        elif args.command == "fact-bundle-admit":
            if store.workflow_evidence_version() == 5:
                _print_json(
                    store.v5_lifecycle().fact_admit(
                        release_id=args.fact_bundle_id,
                        decision_id=args.review_id,
                        gateway=args.role,
                    )
                )
            else:
                _print_json(
                    store.admit_fact_bundle(
                        args.fact_bundle_id,
                        review_id=args.review_id,
                    )
                )
        elif args.command == "export-claim-card":
            card = store.claim_card(args.fact_id, audience=args.audience)
            relative_output = args.output
            if relative_output.startswith("reports/"):
                relative_output = relative_output[len("reports/") :]
            output = store.report_output_path(relative_output)
            output.parent.mkdir(parents=True, exist_ok=True)
            store._write_json_atomic(output, card)
            _print_json(
                {
                    "fact_id": args.fact_id,
                    "claim_card_sha256": card["claim_card_sha256"],
                    "output": str(output),
                    "status": "exported",
                }
            )
        elif args.command == "lint-expert-document":
            claim_card_path = Path(args.claim_card)
            claim_card_bytes = claim_card_path.read_bytes()
            card = validate_claim_card(
                json.loads(claim_card_bytes.decode("utf-8"))
            )
            input_bytes = Path(args.input).read_bytes()
            key = sha256_json(
                {
                    "project_id": store.project_id(),
                    "draft_sha256": sha256_bytes(input_bytes),
                    "claim_card_bytes_sha256": sha256_bytes(
                        claim_card_bytes
                    ),
                    "claim_card_sha256": card[
                        "claim_card_sha256"
                    ],
                }
            )
            relative_output = (
                args.receipt_output
                or f"expert-lint-receipts/{key}.json"
            )
            if relative_output.startswith("reports/"):
                relative_output = relative_output[len("reports/") :]
            output = store.report_output_path(relative_output)
            receipt = build_expert_lint_receipt(
                project_id=store.project_id(),
                receipt_relpath=output.relative_to(
                    store.root
                ).as_posix(),
                draft_bytes=input_bytes,
                claim_card_bytes=claim_card_bytes,
            )
            store._write_json_once(output, receipt)
            _print_json(receipt)
            return 0 if receipt["ok"] else 2
        elif args.command == "export-interpret-card":
            card = store.interpret_card(
                args.node_id,
                audience=args.audience,
            )
            relative_output = args.output
            if relative_output.startswith("reports/"):
                relative_output = relative_output[len("reports/") :]
            output = store.report_output_path(relative_output)
            store._write_json_once(output, card)
            _print_json(
                {
                    "node_id": args.node_id,
                    "interpret_card_sha256": card[
                        "interpret_card_sha256"
                    ],
                    "output": str(output),
                    "status": "exported",
                    "truth_effect": "none",
                }
            )
        elif args.command == "lint-interpret-document":
            card_path = Path(args.interpret_card).resolve()
            try:
                card_relpath = card_path.relative_to(store.root).as_posix()
            except ValueError as exc:
                raise ValueError(
                    "interpret card must be stored below the current project"
                ) from exc
            if not card_relpath.startswith("reports/"):
                raise ValueError(
                    "interpret card must be stored below project reports/"
                )
            card_bytes = card_path.read_bytes()
            card = validate_interpret_card(
                json.loads(card_bytes.decode("utf-8"))
            )
            if card["project_id"] != store.project_id():
                raise ValueError(
                    "interpret card belongs to another project"
                )
            input_bytes = Path(args.input).read_bytes()
            key = sha256_json(
                {
                    "project_id": store.project_id(),
                    "draft_sha256": sha256_bytes(input_bytes),
                    "interpret_card_bytes_sha256": sha256_bytes(
                        card_bytes
                    ),
                    "interpret_card_sha256": card[
                        "interpret_card_sha256"
                    ],
                }
            )
            relative_output = (
                args.receipt_output
                or f"interpret-lint-receipts/{key}.json"
            )
            if relative_output.startswith("reports/"):
                relative_output = relative_output[len("reports/") :]
            output = store.report_output_path(relative_output)
            receipt = build_interpret_lint_receipt(
                project_id=store.project_id(),
                receipt_relpath=output.relative_to(
                    store.root
                ).as_posix(),
                interpret_card_relpath=card_relpath,
                draft_bytes=input_bytes,
                interpret_card_bytes=card_bytes,
            )
            store._write_json_once(output, receipt)
            _print_json(receipt)
            return 0 if receipt["ok"] else 2
        else:
            raise AssertionError(args.command)
    except (KeyError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        stack.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
