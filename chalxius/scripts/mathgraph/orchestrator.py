from __future__ import annotations

import json
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adoption import (
    build_adoption_plan,
    compact_adoption_binding,
    feature_required,
    workload_profile_for_entry,
)
from .blackboard import make_node
from .contracts import (
    ASSIGNMENT_ID_RE,
    MEMORY_ID_RE,
    POLICY_REVISION_V4,
    ROUND_ID_RE,
    SHA256_RE,
    WORK_MODES as CONTRACT_WORK_MODES,
    contained_path,
    require_exact_keys,
    require_string,
    sha256_bytes,
    sha256_json,
    validate_assignment_id,
    validate_memory_id,
    validate_round_id,
)
from .model import Fact
from .protocol import (
    DEFAULT_BUDGETS,
    DEFAULT_HARD_CAPS,
    compact_worker_prompt,
    normalize_host_task_scope_id,
    seal_ingestion_receipt_v4,
    validate_ingestion_receipt_v4,
    validate_task_card,
)
from .store import MathGraphStore, _json_hash, utc_now
from .worker_returns import (
    fact_bundle_payload_from_return,
    validate_formula_artifact_bindings,
    validate_worker_return,
)
from .modes import (
    build_round_profile_obligations,
    validate_mode_binding_fields,
)


WORK_MODES = CONTRACT_WORK_MODES


def _mode_for(entry: dict[str, Any], index: int) -> str:
    text = " ".join(entry.get("suggested_actions", [])).lower()
    for mode in WORK_MODES:
        if mode in text:
            return mode
    kind = str(entry.get("kind", ""))
    if kind == "computation":
        return "compute"
    if kind == "literature":
        return "literature"
    if kind == "counterexample":
        return "refute"
    return WORK_MODES[index % len(WORK_MODES)]


def _assignment_contract(
    *,
    store: MathGraphStore,
    entry: dict[str, Any],
    round_id: str,
    assignment_id: str,
    mode: str,
    return_relpath: str,
    artifact_dir_relpath: str,
) -> dict[str, Any]:
    return {
        "project_id": store.project_id(),
        "round_id": round_id,
        "assignment_id": assignment_id,
        "memory_id": entry["id"],
        "mode": mode,
        "worker_id": assignment_id,
        "claim": entry.get("claim", ""),
        "rationale": entry.get("rationale", ""),
        "source": entry.get("source", ""),
        "dependencies": entry.get("dependencies", []),
        "return_relpath": return_relpath,
        "artifact_dir_relpath": artifact_dir_relpath,
    }


def _create_round_v3(
    store: MathGraphStore,
    *,
    workers: int,
    mode: str = "auto",
    memory_ids: list[str] | None = None,
) -> dict[str, Any]:
    if workers < 1:
        raise ValueError("workers must be positive")
    if mode != "auto" and mode not in WORK_MODES:
        raise ValueError(f"unsupported work mode: {mode}")
    if memory_ids:
        memory_ids = [validate_memory_id(item) for item in memory_ids]
        if len(set(memory_ids)) != len(memory_ids):
            raise ValueError("requested memory ids must be unique")
        if workers != len(memory_ids):
            raise ValueError(
                "--workers must exactly equal the number of explicit --memory-id values"
            )
    # Explicit memory ids are a user-selected frontier, not a score-based sample.
    # Search the complete active memory set before filtering; otherwise a ready low-score
    # entry can be falsely rejected merely because it fell outside the automatic top-3w window.
    frontier_limit = (
        max(len(store.memory_latest()), workers)
        if memory_ids
        else max(workers * 3, workers)
    )
    frontier = store.frontier(limit=frontier_limit)
    if memory_ids:
        requested = set(memory_ids)
        frontier = [entry for entry in frontier if entry["id"] in requested]
        missing = requested.difference(entry["id"] for entry in frontier)
        if missing:
            raise ValueError("not active frontier entries: " + ", ".join(sorted(missing)))
        by_id = {entry["id"]: entry for entry in frontier}
        selected = [by_id[item] for item in memory_ids]
    else:
        selected = frontier[:workers]
    if len(selected) != workers:
        raise ValueError(
            f"requested {workers} workers but only {len(selected)} active entries are available"
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    round_id = f"round-{stamp}-{_json_hash([[entry['id'] for entry in selected], time.time_ns()], 8)}"
    validate_round_id(round_id)
    round_dir = store.rounds_dir / round_id
    assignments_dir = round_dir / "assignments"
    returns_dir = round_dir / "returns"
    artifacts_dir = round_dir / "artifacts"
    with store.mutation_lock():
        assignments_dir.mkdir(parents=True, exist_ok=False)
        returns_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        assignments: list[dict[str, Any]] = []
        round_mode_binding: dict[str, Any] | None = None
        execution_profile_hashes: dict[str, str] = {}
        for index, entry in enumerate(selected, 1):
            work_mode = mode if mode != "auto" else _mode_for(entry, index - 1)
            assignment_id = f"a{index:02d}-{entry['id']}-{work_mode}"
            validate_assignment_id(assignment_id)
            prompt_relpath = f"assignments/{assignment_id}.md"
            return_relpath = f"returns/{assignment_id}.json"
            artifact_dir_relpath = f"rounds/{round_id}/artifacts/{assignment_id}"
            (artifacts_dir / assignment_id).mkdir(parents=True, exist_ok=False)
            contract = _assignment_contract(
                store=store,
                entry=entry,
                round_id=round_id,
                assignment_id=assignment_id,
                mode=work_mode,
                return_relpath=return_relpath,
                artifact_dir_relpath=artifact_dir_relpath,
            )
            assignment_sha = sha256_json(contract)
            prompt = render_worker_prompt(
                store,
                entry=entry,
                round_id=round_id,
                assignment_id=assignment_id,
                mode=work_mode,
                return_relpath=return_relpath,
                artifact_dir_relpath=artifact_dir_relpath,
                assignment_sha256=assignment_sha,
            )
            prompt_path = assignments_dir / f"{assignment_id}.md"
            prompt_bytes = prompt.encode("utf-8")
            store._write_bytes_once(prompt_path, prompt_bytes)
            assignments.append(
                {
                    "assignment_id": assignment_id,
                    "memory_id": entry["id"],
                    "mode": work_mode,
                    "worker_id": assignment_id,
                    "prompt_relpath": prompt_relpath,
                    "return_relpath": return_relpath,
                    "artifact_dir_relpath": artifact_dir_relpath,
                    "assignment_sha256": assignment_sha,
                    "prompt_sha256": sha256_bytes(prompt_bytes),
                    "contract": contract,
                }
            )

        manifest = {
            "schema_version": 3,
            "project_id": store.project_id(),
            "round_id": round_id,
            "created_at": utc_now(),
            "assignments": assignments,
        }
        store._write_json_once(round_dir / "round.json", manifest)

    result = deepcopy(manifest)
    result["mgraph_path"] = str(Path(__file__).resolve().parents[1] / "mgraph")
    for assignment in result["assignments"]:
        assignment["prompt_path"] = str(
            contained_path(round_dir, assignment["prompt_relpath"], "prompt_relpath")
        )
        assignment["return_path"] = str(
            contained_path(round_dir, assignment["return_relpath"], "return_relpath")
        )
        assignment["artifact_dir_path"] = str(
            contained_path(
                store.root,
                assignment["artifact_dir_relpath"],
                "artifact_dir_relpath",
            )
        )
    return result


def _v4_round_snapshot(store: MathGraphStore, selected: list[dict[str, Any]]) -> dict[str, Any]:
    blackboard = store.blackboard()
    nodes = blackboard.nodes()
    spaces = sorted(
        node_id
        for node_id, node in nodes.items()
        if node.get("node_type") == "space"
    )
    if not spaces:
        raise ValueError("v4 planning requires an initialized blackboard space")
    promoted_entries = [
        entry
        for entry in selected
        if isinstance(entry.get("origin_blackboard_node_id"), str)
    ]
    bound_queries: list[dict[str, Any]] = []
    for entry in promoted_entries:
        node_id = entry["origin_blackboard_node_id"]
        if node_id not in nodes:
            raise ValueError("promoted blackboard origin is no longer visible")
        query_value = entry.get("blackboard_query")
        if not isinstance(query_value, dict):
            raise ValueError("promoted memory lacks its blackboard query")
        query = deepcopy(query_value)
        blackboard.validate_query(query)
        if entry.get("blackboard_query_sha256") != sha256_json(query):
            raise ValueError("promoted memory blackboard query hash mismatch")
        node_hash = sha256_bytes(
            json.dumps(
                nodes[node_id],
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        if entry.get("origin_blackboard_node_sha256") != node_hash:
            raise ValueError("promoted memory blackboard node hash mismatch")
        if node_id not in query["seed_node_ids"]:
            raise ValueError("promoted memory query does not seed its origin node")
        bound_queries.append(query)
    if len(bound_queries) == 1:
        query = bound_queries[0]
    elif bound_queries:
        edge_allowlists = [
            set(item["edge_type_allowlist"]) for item in bound_queries
        ]
        node_allowlists = [
            set(item["node_type_allowlist"]) for item in bound_queries
        ]
        query = {
            "seed_node_ids": sorted(
                {
                    seed
                    for item in bound_queries
                    for seed in item["seed_node_ids"]
                }
            ),
            "direction": (
                bound_queries[0]["direction"]
                if len({item["direction"] for item in bound_queries}) == 1
                else "both"
            ),
            "max_hops": max(item["max_hops"] for item in bound_queries),
            "edge_type_allowlist": (
                ["*"]
                if any("*" in item for item in edge_allowlists)
                else sorted(set().union(*edge_allowlists))
            ),
            "node_type_allowlist": (
                ["*"]
                if any("*" in item for item in node_allowlists)
                else sorted(set().union(*node_allowlists))
            ),
            "node_budget": sum(
                item["node_budget"] for item in bound_queries
            ),
            "edge_budget": sum(
                item["edge_budget"] for item in bound_queries
            ),
        }
        blackboard.validate_query(query)
    else:
        query = {
            "seed_node_ids": [spaces[0]],
            "direction": "both",
            "max_hops": 3,
            "edge_type_allowlist": ["*"],
            "node_type_allowlist": ["*"],
            "node_budget": 256,
            "edge_budget": 512,
        }
    return blackboard.snapshot(query=query, actor="orchestrator")


def _v4_input_interfaces(
    store: MathGraphStore,
    entry: dict[str, Any],
) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    for fact_id in entry.get("dependencies", []):
        interface = store.statement_interface(fact_id)
        clause_ids = [item["clause_id"] for item in interface["clauses"]]
        hypotheses = sorted(
            {
                hypothesis
                for clause in interface["clauses"]
                for hypothesis in clause.get("hypothesis_labels", [])
            }
        )
        inputs.append(
            {
                "fact_id": fact_id,
                "clauses": clause_ids,
                "required_hypotheses": hypotheses,
            }
        )
    return inputs


def _create_round_v4(
    store: MathGraphStore,
    *,
    workers: int,
    mode: str = "auto",
    memory_ids: list[str] | None = None,
    host_task_scope_id: str | None = None,
) -> dict[str, Any]:
    if workers < 1:
        raise ValueError("workers must be positive")
    if mode != "auto" and mode not in WORK_MODES:
        raise ValueError(f"unsupported work mode: {mode}")
    if memory_ids:
        memory_ids = [validate_memory_id(item) for item in memory_ids]
        if len(set(memory_ids)) != len(memory_ids):
            raise ValueError("requested memory ids must be unique")
        if workers != len(memory_ids):
            raise ValueError(
                "--workers must exactly equal the number of explicit --memory-id values"
            )
    frontier_limit = (
        max(len(store.memory_latest()), workers)
        if memory_ids
        else max(workers * 3, workers)
    )
    frontier = store.frontier(limit=frontier_limit)
    if memory_ids:
        by_id = {entry["id"]: entry for entry in frontier}
        missing = sorted(set(memory_ids).difference(by_id))
        if missing:
            raise ValueError("not active frontier entries: " + ", ".join(missing))
        selected = [by_id[item] for item in memory_ids]
    else:
        selected = frontier[:workers]
    if len(selected) != workers:
        raise ValueError(
            f"requested {workers} workers but only {len(selected)} active entries are available"
        )

    campaign_id = store.campaigns().active()
    if campaign_id is None:
        raise ValueError("v4 planning requires an active campaign")
    campaign = store.campaigns().status(campaign_id)
    for source_claim_id in campaign.get("source_claim_ids", []):
        store.claims().show_claim(source_claim_id)
    normalized_host_task_scope_id = normalize_host_task_scope_id(
        host_task_scope_id,
        workflow_evidence_version=4,
    )
    if normalized_host_task_scope_id is None:
        raise RuntimeError("V4 host task scope normalization returned null")
    snapshot = _v4_round_snapshot(store, selected)
    snapshot_nodes, _ = store.blackboard().snapshot_objects(
        snapshot["snapshot_id"]
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    round_id = (
        f"round-{stamp}-"
        f"{_json_hash([[entry['id'] for entry in selected], time.time_ns()], 8)}"
    )
    validate_round_id(round_id)
    round_dir = store.rounds_dir / round_id
    assignments_dir = round_dir / "assignments"
    task_cards_dir = round_dir / "task-cards"
    returns_dir = round_dir / "returns"
    artifacts_dir = round_dir / "artifacts"
    work_dir = round_dir / "work"

    with store.mutation_lock():
        for directory in (
            assignments_dir,
            task_cards_dir,
            returns_dir,
            artifacts_dir,
            work_dir,
        ):
            directory.mkdir(parents=True, exist_ok=directory != assignments_dir)
        campaign_snapshot_relpath = (
            f"rounds/{round_id}/campaign.snapshot.json"
        )
        campaign_snapshot_path = store.root / campaign_snapshot_relpath
        store._write_json_once(campaign_snapshot_path, campaign)
        campaign_snapshot_sha256 = sha256_bytes(
            campaign_snapshot_path.read_bytes()
        )
        assignments: list[dict[str, Any]] = []
        round_mode_binding: dict[str, Any] | None = None
        execution_profile_hashes: dict[str, str] = {}
        execution_profiles: dict[str, dict[str, Any]] = {}
        for index, entry in enumerate(selected, 1):
            work_mode = mode if mode != "auto" else _mode_for(entry, index - 1)
            assignment_id = f"a{index:02d}-{entry['id']}-{work_mode}"
            validate_assignment_id(assignment_id)
            prompt_relpath = f"assignments/{assignment_id}.md"
            project_prompt_relpath = f"rounds/{round_id}/{prompt_relpath}"
            task_card_relpath = f"rounds/{round_id}/task-cards/{assignment_id}.json"
            return_relpath = f"rounds/{round_id}/returns/{assignment_id}.json"
            artifact_dir_relpath = f"rounds/{round_id}/artifacts/{assignment_id}"
            work_dir_relpath = f"rounds/{round_id}/work/{assignment_id}"
            (artifacts_dir / assignment_id).mkdir(parents=True, exist_ok=False)
            (work_dir / assignment_id).mkdir(parents=True, exist_ok=False)
            source_claim_id = entry.get("source_claim_id")
            if not isinstance(source_claim_id, str):
                source_claim_id = None
            full_adoption_plan = build_adoption_plan(
                workload_profile_for_entry(entry)
            )
            adoption_plan = compact_adoption_binding(full_adoption_plan)
            verification_plan = dict(
                entry.get(
                    "verification_plan",
                    {
                        "mode": "closed_packet",
                        "authorized_artifact_roles": [],
                        "required_checks": [
                            "mathematical",
                            "scope",
                            "typing",
                        ],
                    },
                )
            )
            if (
                feature_required(adoption_plan, "artifact_replay")
                and verification_plan.get("mode") != "artifact_replay"
            ):
                reasoning_mode = store.reasoning_modes().status().get(
                    "reasoning_mode",
                    "uninitialized",
                )
                raise ValueError(
                    "blocked_requires_mode_switch_or_external_evidence: "
                    f"{reasoning_mode} reasoning mode cannot waive the "
                    f"artifact_replay admission gate for memory {entry['id']}; "
                    "provision replay evidence (or switch mode to allocate the "
                    "needed research work) and replan"
                )
            mode_binding = store.reasoning_modes().binding_for_new_work_unit(
                adoption_binding=adoption_plan,
            )
            if round_mode_binding is None:
                round_mode_binding = {
                    key: mode_binding[key]
                    for key in (
                        "reasoning_mode",
                        "reasoning_mode_event_id",
                        "reasoning_mode_policy_sha256",
                        "fact_admission_contract_sha256",
                    )
                }
            elif any(
                mode_binding[key] != round_mode_binding[key]
                for key in round_mode_binding
            ):
                raise RuntimeError(
                    "reasoning mode changed while a frozen round was being planned"
                )
            execution_profile_hashes[assignment_id] = mode_binding[
                "execution_profile"
            ]["execution_profile_sha256"]
            execution_profiles[assignment_id] = mode_binding[
                "execution_profile"
            ]
            contract = {
                "schema_version": 4,
                "policy_revision": POLICY_REVISION_V4,
                "project_id": store.project_id(),
                "round_id": round_id,
                "assignment_id": assignment_id,
                "memory_id": entry["id"],
                "mode": work_mode,
                "worker_id": assignment_id,
                "campaign_id": campaign_id,
                "host_task_scope_id": normalized_host_task_scope_id,
                "campaign_snapshot_relpath": campaign_snapshot_relpath,
                "campaign_snapshot_sha256": campaign_snapshot_sha256,
                "source_claim_id": source_claim_id,
                "blackboard_snapshot_id": snapshot["snapshot_id"],
                "adoption_plan_sha256": adoption_plan["plan_sha256"],
                "return_relpath": return_relpath,
                "artifact_dir_relpath": artifact_dir_relpath,
                "work_dir_relpath": work_dir_relpath,
                **mode_binding,
            }
            assignment_sha = sha256_json(contract)
            write_spaces = sorted(
                {
                    node_id
                    for node_id, node in store.blackboard().nodes().items()
                    if node.get("node_type") == "space"
                }
            )
            requested_write_spaces = entry.get(
                "blackboard_write_space_ids"
            )
            if requested_write_spaces is not None:
                write_spaces = sorted(requested_write_spaces)
            cross_space_endpoint_node_ids = sorted(
                entry.get(
                    "blackboard_cross_space_endpoint_node_ids",
                    [],
                )
            )
            if any(
                node_id not in snapshot_nodes
                for node_id in [
                    *write_spaces,
                    *cross_space_endpoint_node_ids,
                ]
            ):
                raise ValueError(
                    "blackboard task capability is absent from the frozen "
                    "snapshot"
                )
            task_card = {
                "schema_version": 4,
                "policy_revision": POLICY_REVISION_V4,
                "protocol": "mathgraph-agent-v4",
                "project_id": store.project_id(),
                "round_id": round_id,
                "assignment_id": assignment_id,
                "assignment_sha256": assignment_sha,
                "memory_id": entry["id"],
                "worker_id": assignment_id,
                "mode": work_mode,
                "campaign_id": campaign_id,
                "host_task_scope_id": normalized_host_task_scope_id,
                "campaign_snapshot_relpath": campaign_snapshot_relpath,
                "campaign_snapshot_sha256": campaign_snapshot_sha256,
                "source_claim_id": source_claim_id,
                "goal_relation": entry.get("goal_relation", "proves"),
                "goal_statement": entry.get("claim", ""),
                "rationale_summary": entry.get("rationale", ""),
                "convention_profile_ids": list(
                    entry.get("convention_profile_ids", [])
                ),
                "inputs": _v4_input_interfaces(store, entry),
                "obligations": list(entry.get("obligations", [])),
                "verification_plan": verification_plan,
                "adoption_plan": adoption_plan,
                "budgets": {
                    **DEFAULT_BUDGETS,
                    **dict(entry.get("budgets", {})),
                    "max_wall_seconds": 0,
                },
                # Safety caps are a release profile, not a task priority knob.
                # Keeping one immutable profile prevents same-scope rounds from
                # silently changing enforcement authority through memory data.
                "hard_caps": dict(DEFAULT_HARD_CAPS),
                "stop_conditions": list(
                    entry.get("stop_conditions", campaign["stop_conditions"])
                ),
                "blackboard_view": {
                    "snapshot_id": snapshot["snapshot_id"],
                    "seed_node_ids": store.blackboard()
                    .snapshot_manifest(snapshot["snapshot_id"])["seed_node_ids"],
                    "read_space_ids": sorted(
                        node_id
                        for node_id, node in snapshot_nodes.items()
                        if node.get("node_type") == "space"
                    ),
                    "write_space_ids": write_spaces,
                    "cross_space_endpoint_node_ids": (
                        cross_space_endpoint_node_ids
                    ),
                    "allow_create_space": False,
                    "query_sha256": snapshot["query_sha256"],
                },
                "blackboard_snapshot_sha256": snapshot["snapshot_sha256"],
                "return_relpath": return_relpath,
                "artifact_dir_relpath": artifact_dir_relpath,
                "work_dir_relpath": work_dir_relpath,
                **mode_binding,
            }
            validate_mode_binding_fields(
                task_card,
                adoption_binding=adoption_plan,
            )
            validate_task_card(task_card)
            task_card_path = store.root / task_card_relpath
            store._write_json_once(task_card_path, task_card)
            task_card_sha = sha256_bytes(task_card_path.read_bytes())
            prompt = compact_worker_prompt(
                task_card_path=task_card_relpath,
                protocol_reference_path=(
                    "references/agent_protocol_v4.md"
                ),
                mgraph_path=str(Path(__file__).resolve().parents[1] / "mgraph"),
            )
            prompt_bytes = prompt.encode("utf-8")
            store._write_bytes_once(
                store.root / f"rounds/{round_id}/{prompt_relpath}",
                prompt_bytes,
            )
            assignments.append(
                {
                    "assignment_id": assignment_id,
                    "memory_id": entry["id"],
                    "mode": work_mode,
                    "worker_id": assignment_id,
                    "prompt_relpath": project_prompt_relpath,
                    "return_relpath": return_relpath,
                    "artifact_dir_relpath": artifact_dir_relpath,
                    "work_dir_relpath": work_dir_relpath,
                    "task_card_relpath": task_card_relpath,
                    "assignment_sha256": assignment_sha,
                    "prompt_sha256": sha256_bytes(prompt_bytes),
                    "task_card_sha256": task_card_sha,
                    "contract": contract,
                }
            )
        if round_mode_binding is None:
            raise RuntimeError("v4 round planning produced no mode binding")
        manifest = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "project_id": store.project_id(),
            "round_id": round_id,
            "created_at": utc_now(),
            "blackboard_snapshot_id": snapshot["snapshot_id"],
            "blackboard_snapshot_sha256": snapshot["snapshot_sha256"],
            **round_mode_binding,
            "execution_profile": execution_profile_hashes,
            "profile_obligations": build_round_profile_obligations(
                execution_profiles
            ),
            "assignments": assignments,
        }
        store._write_json_once(round_dir / "round.json", manifest)

    result = deepcopy(manifest)
    result["mgraph_path"] = str(Path(__file__).resolve().parents[1] / "mgraph")
    for assignment in result["assignments"]:
        for key in (
            "prompt_relpath",
            "return_relpath",
            "artifact_dir_relpath",
            "work_dir_relpath",
            "task_card_relpath",
        ):
            assignment[key.removesuffix("_relpath") + "_path"] = str(
                contained_path(store.root, assignment[key], key)
            )
    return result


def create_round(
    store: MathGraphStore,
    *,
    workers: int,
    mode: str = "auto",
    memory_ids: list[str] | None = None,
    host_task_scope_id: str | None = None,
) -> dict[str, Any]:
    if store.workflow_evidence_version() >= 4:
        return _create_round_v4(
            store,
            workers=workers,
            mode=mode,
            memory_ids=memory_ids,
            host_task_scope_id=host_task_scope_id,
        )
    return _create_round_v3(
        store,
        workers=workers,
        mode=mode,
        memory_ids=memory_ids,
    )


def render_worker_prompt(
    store: MathGraphStore,
    *,
    entry: dict[str, Any],
    round_id: str,
    assignment_id: str,
    mode: str,
    return_relpath: str,
    artifact_dir_relpath: str,
    assignment_sha256: str,
) -> str:
    dependency_lines = [
        f"- `{fact_id}`: `fact_graph/facts/{fact_id}.md`"
        for fact_id in entry.get("dependencies", [])
    ] or ["- none"]
    mode_instruction = {
        "prove": "Try to prove a precise atomic claim. Search for counterexamples before committing.",
        "refute": "Actively seek a counterexample or missing hypothesis. A rigorous obstruction is valuable.",
        "compute": "Build a reproducible experiment and keep evidence distinct from proof.",
        "literature": "Use primary sources and distinguish theorem scope from inference.",
    }[mode]
    search_command = '"$MGRAPH" --root "$PROJECT_ROOT" --role worker search "QUERY"'
    project_return = f"rounds/{round_id}/{return_relpath}"
    validate_command = (
        f'"$MGRAPH" --root "$PROJECT_ROOT" --role worker validate-return '
        f"{round_id} {assignment_id}"
    )
    return f"""# MathGraph worker assignment

Round: `{round_id}`  
Assignment: `{assignment_id}`  
Mode: `{mode}`  
Assignment SHA-256: `{assignment_sha256}`

You are a proof-search worker, not the verifier or orchestrator. Work on one atomic output.
Treat the directory four levels above this assignment file as `PROJECT_ROOT`. The host must set
`MGRAPH` to the deployed `scripts/mgraph` wrapper (or the repository wrapper).

## Research claim

{entry.get('claim', '')}

## Rationale

{entry.get('rationale', '')}

## Research source / locator

{entry.get('source', '') or '- none supplied'}

## Mode instruction

{mode_instruction}

## Verified dependencies

{chr(10).join(dependency_lines)}

You may search the verified graph with:

```bash
{search_command}
```

Do not treat global memory, another worker draft, or the research claim as verified mathematics.
If you use an existing fact, cite its exact 16-hex id and only the statement proved there.
For every predecessor use, identify an entailing statement clause and map all scope restrictions and
hypotheses in that clause to the present objects. Shared terminology is not a bridge across ambient
categories; prove every such transport in this submission or do not use the clause.

## Required return contract

Write exactly one JSON object to this project-relative path:

`{project_return}`

You may additionally create reproducibility/source-inspection artifacts only below:

`{artifact_dir_relpath}`

Every artifact must be declared by project-relative `path` and exact SHA-256 in the return. Do not
write anywhere else in the project. An assignment may declare at most 256 files, each at most
16 MiB and at most 64 MiB in total.

Every return must contain these exact binding fields:

```json
{{
  "project_id": {json.dumps(store.project_id())},
  "round_id": {json.dumps(round_id)},
  "assignment_id": {json.dumps(assignment_id)},
  "assignment_sha256": {json.dumps(assignment_sha256)},
  "worker": {json.dumps(assignment_id)},
  "memory_id": {json.dumps(entry['id'])},
  "mode": {json.dumps(mode)},
  "outcome": "fact_submission | counterexample | evidence | dead_end",
  "notes": "limits and checks"
}}
```

Outcome-specific fields:

1. `fact_submission`: `statement`, `proof`, `predecessors`, and optionally
   `glossary_introduces`, `external_refs`, `elementary_uses`, `intuition`, `artifacts`. It must also
   contain
   `claim_relation`, exactly one of `proves`, `refutes`, `strengthens`, `weakens`, `replaces`, or
   `unrelated`, describing the submitted statement's logical relation to the assigned research
   claim. If any external source supports an inference,
   `external_refs` must contain the External Theorem Applicability Certificate described in
   `references/external_theorem_applicability.md` under the skill root (the parent of the `scripts`
   directory containing `MGRAPH`); copy every certificate `[APP:...]`
   anchor exactly once into the proof next to the corresponding scope, witness, convention,
   transport, or bridge argument. Use one certificate per exact labeled source item and delta
   conclusion; split distinct uses of one paper into distinct keys. Bibliography-only metadata is
   rejected. Every new source item must use tiered external-source evidence v3 from
   `references/external_source_reliability.md`: bind the exact primary artifact SHA-256, versioned
   artifact locator, retrieval date, exact result locator, statement transcription and its SHA-256;
   then always perform the notation/binding, type/domain, and quantifier/scope checks. Run the
   version-history, erratum, and retraction/counterexample searches once per exact source artifact,
   hash that `source_audit`, and reuse it for other results from the same bytes for at most 30 days.
   Use `profile="baseline"` only for issue-free direct non-formula uses. Use `profile="strict"` and
   also run boundary/toy-case plus statement/proof-consistency checks for formulas, signs or
   coefficients, bridge/transport or degeneration, target-critical results, any source conflict,
   suspected typo, official correction, or failed cheap check. Bind the assessment and every
   correction with unique `[CRIT:...]` proof anchors. Admit only an unchanged source statement, a
   uniquely forced non-semantic typo correction, or an exact official erratum. Keep ambiguous, material,
   contradicted, retracted, or unresolved source claims in exploration memory; never silently repair
   them. A `use_kind="formula"` item additionally requires the source-glyph fidelity record
   described there: hash the exact primary artifact, inspect source TeX or a rendered primary page,
   enumerate every load-bearing token/sign/bracket/operator, and bind one `[SRC:...]` anchor into
   the proof. Plain PDF text extraction is never sufficient. The same artifact SHA-256 must occur in
   the return's declared `artifacts` list and its bytes must be below this assignment's artifact
   directory.
   A named result that is not externally attributed may omit a source certificate only through the
   controlled elementary-result exemption in `references/elementary_result_exemption.md`. Return
   one exact `elementary_uses` entry per such invocation and copy its `[ELM:KEY]` anchor exactly once
   into the proof. The closed whitelist covers only fixed/local textbook steps with explicit
   hypothesis witnesses, scope limitations, and a packet-reconstructible check. It does not cover
   Weierstrass preparation, parameter-uniform or degenerating-family assertions, plumbing,
   topology/monodromy, global Riemann-surface normalization, topological recursion, or any external
   formula/sign/coefficient/normalization. The adjectives standard, classical, and well known are
   never sufficient by themselves.
2. `counterexample`: `claim`, `construction`, `verification`, and optional `artifacts`.
3. `evidence`: `claim`, `method`, `result`, `artifacts`, `limitations`.
4. `dead_end`: `claim`, `method`, `failure_mode`, `what_remains_open`, and optional `artifacts`.

For schema v3, `artifacts` is a list of objects, never a list of bare strings:

```json
[
  {{
    "path": "{artifact_dir_relpath}/example.ext",
    "sha256": "64 lowercase hex characters"
  }}
]
```

Do not edit the verified fact graph, reviews, packets, manifests, or receipts. After the final edit,
run the exact ingestion-schema validator:

```bash
{validate_command}
```

Use the returned `return_sha256` in your explicit final handoff, then do not edit the return or its
declared artifacts again.
File existence alone is only a draft signal and does not authorize ingestion.
"""


def _round_manifest(store: MathGraphStore, round_id: str) -> tuple[Path, dict[str, Any]]:
    validate_round_id(round_id)
    round_dir = store.rounds_dir / round_id
    manifest_path = round_dir / "round.json"
    if not manifest_path.exists():
        raise KeyError(f"unknown round: {round_id}")
    manifest = store._read_json(manifest_path)
    if manifest.get("schema_version") not in {2, 3, 4}:
        raise ValueError("unsupported legacy round is read-only")
    if (
        manifest.get("schema_version") == 4
        and manifest.get("policy_revision") != POLICY_REVISION_V4
    ):
        raise ValueError("v4 round policy revision mismatch")
    if manifest.get("round_id") != round_id:
        raise ValueError("round manifest id mismatch")
    if manifest.get("project_id") != store.project_id():
        raise ValueError("round belongs to another project")
    return round_dir, manifest


def _round_bound_path(
    store: MathGraphStore,
    round_dir: Path,
    manifest: dict[str, Any],
    relative: str,
    label: str,
) -> Path:
    base = store.root if manifest.get("schema_version") == 4 else round_dir
    return contained_path(base, relative, label)


def _assignment(
    manifest: dict[str, Any], assignment_id: str
) -> dict[str, Any]:
    validate_assignment_id(assignment_id)
    matches = [
        item
        for item in manifest.get("assignments", [])
        if item.get("assignment_id") == assignment_id
    ]
    if len(matches) != 1:
        raise KeyError(f"unknown or duplicate assignment: {assignment_id}")
    assignment = matches[0]
    schema_version = manifest.get("schema_version")
    version_fields = {"artifact_dir_relpath"} if schema_version >= 3 else set()
    if schema_version == 4:
        version_fields |= {
            "work_dir_relpath",
            "task_card_relpath",
            "task_card_sha256",
        }
    require_exact_keys(
        assignment,
        required={
            "assignment_id",
            "memory_id",
            "mode",
            "worker_id",
            "prompt_relpath",
            "return_relpath",
            "assignment_sha256",
            "prompt_sha256",
            "contract",
        }
        | version_fields,
        label="round assignment",
    )
    contract = assignment.get("contract")
    if not isinstance(contract, dict):
        raise ValueError("round assignment contract must be an object")
    if sha256_json(contract) != assignment["assignment_sha256"]:
        raise ValueError("round assignment contract hash mismatch")
    contract_fields = {
        "project_id",
        "round_id",
        "assignment_id",
        "memory_id",
        "mode",
        "worker_id",
        "return_relpath",
    }
    if schema_version >= 3:
        contract_fields.add("artifact_dir_relpath")
    if schema_version == 4:
        contract_fields.add("work_dir_relpath")
    for key in sorted(contract_fields):
        expected = manifest.get(key) if key in {"project_id", "round_id"} else assignment.get(key)
        if contract.get(key) != expected:
            raise ValueError(f"round assignment contract {key} mismatch")
    if schema_version == 4 and "reasoning_mode" in manifest:
        for key in (
            "reasoning_mode",
            "reasoning_mode_event_id",
            "reasoning_mode_policy_sha256",
            "fact_admission_contract_sha256",
        ):
            if contract.get(key) != manifest.get(key):
                raise ValueError(
                    f"round assignment contract {key} mismatch"
                )
        expected_profile_hash = manifest.get("execution_profile", {}).get(
            assignment_id
        )
        if contract.get("execution_profile", {}).get(
            "execution_profile_sha256"
        ) != expected_profile_hash:
            raise ValueError(
                "round assignment contract execution-profile mismatch"
            )
    return assignment


def round_status(store: MathGraphStore, round_id: str) -> dict[str, Any]:
    round_dir, manifest = _round_manifest(store, round_id)
    states: list[dict[str, str]] = []
    for assignment in manifest["assignments"]:
        return_path = _round_bound_path(
            store,
            round_dir,
            manifest,
            assignment["return_relpath"],
            "return_relpath",
        )
        receipt_path = return_path.with_suffix(".receipt.json")
        if receipt_path.exists():
            receipt = store._read_json(receipt_path)
            state = "ingested" if receipt.get("status") == "ingested" else "ingesting"
        elif return_path.exists():
            state = "draft_present"
        else:
            state = "ready"
        states.append({"assignment_id": assignment["assignment_id"], "state": state})
    if all(item["state"] == "ingested" for item in states):
        overall = "complete"
    elif any(item["state"] != "ready" for item in states):
        overall = "in_progress"
    else:
        overall = "ready"
    counts = {
        state: sum(1 for item in states if item["state"] == state)
        for state in ("ready", "draft_present", "ingesting", "ingested")
    }
    return {
        "round_id": round_id,
        "status": overall,
        "assignments": states,
        **counts,
        "total": len(states),
    }


def _return_validation_context(
    store: MathGraphStore,
    round_id: str,
    assignment_id: str,
) -> tuple[Path, dict[str, Any], dict[str, Any], Path]:
    round_dir, manifest = _round_manifest(store, round_id)
    assignment = _assignment(manifest, assignment_id)
    return_path = _round_bound_path(
        store,
        round_dir,
        manifest,
        assignment["return_relpath"],
        "return_relpath",
    )
    prompt_path = _round_bound_path(
        store,
        round_dir,
        manifest,
        assignment["prompt_relpath"],
        "prompt_relpath",
    )
    if not prompt_path.is_file() or prompt_path.is_symlink():
        raise ValueError("assignment prompt is missing or not a regular file")
    if sha256_bytes(prompt_path.read_bytes()) != assignment["prompt_sha256"]:
        raise ValueError("assignment prompt was modified")
    return round_dir, manifest, assignment, return_path


def _validate_return_bytes(
    store: MathGraphStore,
    *,
    round_id: str,
    assignment_id: str,
    manifest: dict[str, Any],
    assignment: dict[str, Any],
    canonical_return_path: Path,
    raw: bytes,
) -> dict[str, Any]:
    """Run the one semantic validator shared by preflight, validate, and ingest."""

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "worker return must be one UTF-8 JSON object"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("worker return must be one JSON object")
    outcome, artifacts = validate_worker_return(
        payload,
        assignment,
        manifest,
        project_root=store.root,
        interface_lookup=(
            (
                lambda fact_id: store.statement_interface(
                    fact_id,
                    materialize=False,
                )
            )
            if manifest["schema_version"] == 4
            else None
        ),
    )
    if manifest["schema_version"] >= 3 and outcome == "fact_submission":
        validate_formula_artifact_bindings(payload, artifacts)
    return_sha = sha256_bytes(raw)
    fact_bundle_id: str | None = None
    if manifest["schema_version"] == 4:
        task_card = store._read_json(
            contained_path(
                store.root,
                assignment["task_card_relpath"],
                "task card path",
            )
        )
        # Worker validation must preflight the same registry, endpoint,
        # capability, cycle, placement, and budget checks that ingestion runs.
        # Otherwise an invalid graph delta can be reported as final and fail
        # only after the worker context has gone away.
        store.blackboard().validate_delta(
            delta=payload["blackboard_graph_delta"],
            task_card=task_card,
            return_sha256=return_sha,
            defer_visibility=True,
            allow_legacy_adoption=True,
        )
        if not canonical_return_path.with_suffix(
            ".receipt.json"
        ).exists():
            store.collaboration().preflight_review_delta(
                task_card=task_card,
                delta=payload["blackboard_graph_delta"],
                artifacts=artifacts,
            )
        if outcome == "fact_bundle_submission":
            active_fact_ids = set(store.fact_ids())
            fact_bundle_id = store.fact_bundles().validate_submission(
                fact_bundle_payload_from_return(payload),
                worker=assignment["worker_id"],
                external_fact_exists=(
                    lambda fact_id: fact_id in active_fact_ids
                ),
                provenance={
                    "round_id": round_id,
                    "assignment_id": assignment_id,
                    "task_card_sha256": payload["task_card_sha256"],
                    "return_sha256": return_sha,
                },
            )
    result = {
        "schema_version": manifest["schema_version"],
        "project_id": manifest["project_id"],
        "round_id": round_id,
        "assignment_id": assignment_id,
        "outcome": outcome,
        "return_path": str(canonical_return_path),
        "return_sha256": return_sha,
        "artifacts": artifacts,
    }
    if fact_bundle_id is not None:
        result["fact_bundle_id"] = fact_bundle_id
    return result


def validate_return(
    store: MathGraphStore,
    round_id: str,
    assignment_id: str,
) -> dict[str, Any]:
    """Dry-run the exact canonical return checks used by ingestion."""

    store.reasoning_modes().require_work_unit_active(round_id)

    _, manifest, assignment, return_path = (
        _return_validation_context(
            store,
            round_id,
            assignment_id,
        )
    )
    if not return_path.is_file() or return_path.is_symlink():
        raise FileNotFoundError(return_path)
    return _validate_return_bytes(
        store,
        round_id=round_id,
        assignment_id=assignment_id,
        manifest=manifest,
        assignment=assignment,
        canonical_return_path=return_path,
        raw=return_path.read_bytes(),
    )


def preflight_return(
    store: MathGraphStore,
    round_id: str,
    assignment_id: str,
    *,
    input_path: Path | str,
) -> dict[str, Any]:
    """Validate mutable V4 draft bytes before the canonical return exists."""

    store.reasoning_modes().require_work_unit_active(round_id)

    round_dir, manifest, assignment, return_path = (
        _return_validation_context(
            store,
            round_id,
            assignment_id,
        )
    )
    if manifest.get("schema_version") != 4:
        raise ValueError(
            "preflight-return is available only for workflow-evidence v4"
        )
    receipt_path = return_path.with_suffix(".receipt.json")
    if (
        return_path.exists()
        or return_path.is_symlink()
        or receipt_path.exists()
        or receipt_path.is_symlink()
    ):
        raise ValueError(
            "preflight-return requires an absent canonical return and "
            "ingestion receipt"
        )

    supplied = Path(input_path).expanduser()
    if not supplied.is_absolute():
        supplied = Path.cwd() / supplied
    if supplied.is_symlink() or not supplied.is_file():
        raise ValueError(
            "preflight-return input is missing or not a regular file"
        )
    draft_path = supplied.resolve()
    work_dir = _round_bound_path(
        store,
        round_dir,
        manifest,
        assignment["work_dir_relpath"],
        "work_dir_relpath",
    )
    if (
        not work_dir.is_dir()
        or work_dir.is_symlink()
        or (
            draft_path.parent != work_dir
            and work_dir not in draft_path.parents
        )
    ):
        raise ValueError(
            "preflight-return input must be below the assignment work "
            "directory"
        )
    result = _validate_return_bytes(
        store,
        round_id=round_id,
        assignment_id=assignment_id,
        manifest=manifest,
        assignment=assignment,
        canonical_return_path=return_path,
        raw=draft_path.read_bytes(),
    )
    return {
        **result,
        "input_path": str(draft_path),
        "canonical_return_path": str(return_path),
        "status": "preflight_passed",
    }


def _apply_ingestion_memory_effect(
    store: MathGraphStore,
    *,
    payload: dict[str, Any],
    manifest: dict[str, Any],
    assignment: dict[str, Any],
    return_sha: str,
    effect: dict[str, Any],
) -> None:
    """Apply replay-safe exploration effects after the visibility marker."""

    outcome = payload["outcome"]
    memory_id = validate_memory_id(assignment["memory_id"])
    assignment_id = assignment["assignment_id"]
    if outcome in {"fact_submission", "fact_bundle_submission"}:
        if outcome == "fact_bundle_submission":
            subject = f"fact bundle {effect['fact_bundle_id']}"
        else:
            subject = f"submission {effect['submission_id']}"
        store.memory_update(
            memory_id,
            status="verifying",
            actor="orchestrator",
            note=(
                f"{subject} awaits independent verification"
            ),
            event_id=_json_hash(
                ["return-verifying", assignment_id, return_sha], 24
            ),
        )
        return

    kind = {
        "counterexample": "counterexample",
        "evidence": "computation",
        "dead_end": "dead_end",
    }[outcome]
    child_status = {
        "counterexample": "challenged",
        "evidence": "supported",
        "dead_end": "dead_end",
    }[outcome]
    detail = {
        key: value
        for key, value in payload.items()
        if key
        not in {
            "schema_version",
            "policy_revision",
            "protocol",
            "project_id",
            "round_id",
            "assignment_id",
            "assignment_sha256",
            "task_card_sha256",
            "blackboard_snapshot_sha256",
            "worker",
            "memory_id",
            "mode",
            "outcome",
            "claim",
            "obligation_ledger",
            "blackboard_graph_delta",
            "narrative_summary",
        }
    }
    source = assignment["return_relpath"]
    if manifest.get("schema_version") != 4:
        source = (
            f"rounds/{manifest['round_id']}/"
            f"{assignment['return_relpath']}"
        )
    store.memory_add(
        {
            "kind": kind,
            "status": child_status,
            "claim": str(payload.get("claim", "")).strip(),
            "rationale": json.dumps(
                detail, ensure_ascii=False, sort_keys=True
            ),
            "source": source,
            "priority": 0.6,
            "novelty": 0.5,
            "testability": 0.8,
            "risk": 0.4,
            "parent_memory_id": memory_id,
        },
        actor=assignment["worker_id"],
        entry_id=effect["memory_entry_id"],
    )
    parent_status = "challenged" if outcome == "counterexample" else "open"
    store.memory_update(
        memory_id,
        status=parent_status,
        actor="orchestrator",
        note=(
            f"worker returned {outcome}; "
            f"see memory {effect['memory_entry_id']}"
        ),
        event_id=_json_hash(
            ["return-parent", assignment_id, return_sha], 24
        ),
    )


def ingest_return(
    store: MathGraphStore,
    round_id: str,
    assignment_id: str,
    *,
    worker_final_sha256: str,
) -> dict[str, Any]:
    """Ingest one canonical return inside its complete pulse transaction.

    A matching worker-final hash establishes that the canonical bytes are the
    handoff being ingested.  Only failures after that identity check can
    become durable core-failure evidence.  Mutable draft preflight and the
    read-only canonical validator never enter this path.
    """

    if not isinstance(worker_final_sha256, str) or SHA256_RE.fullmatch(
        worker_final_sha256
    ) is None:
        raise ValueError(
            "worker_final_sha256 must be 64 lowercase hex characters"
        )
    with store.mutation_lock():
        store.reasoning_modes().require_work_unit_active(round_id)
        pulse = store.collaboration()
        pulse.require_ingest_allowed(
            round_id=round_id,
            assignment_id=assignment_id,
        )
        _, manifest, _, return_path = (
            _return_validation_context(
                store,
                round_id,
                assignment_id,
            )
        )
        if not return_path.is_file() or return_path.is_symlink():
            raise FileNotFoundError(return_path)
        raw = return_path.read_bytes()
        return_sha256 = sha256_bytes(raw)
        if worker_final_sha256 != return_sha256:
            raise ValueError(
                "worker final SHA-256 does not match the current return "
                "bytes; wait for an explicit final handoff or repair the "
                "un-ingested draft"
            )
        receipt_path = return_path.with_suffix(".receipt.json")
        try:
            return _ingest_return_locked(
                store,
                round_id,
                assignment_id,
                worker_final_sha256=worker_final_sha256,
            )
        except Exception as exc:
            if (
                manifest.get("schema_version") == 4
                and not receipt_path.exists()
                and not receipt_path.is_symlink()
            ):
                try:
                    recorded = pulse.record_core_ingest_failure(
                        round_id=round_id,
                        assignment_id=assignment_id,
                        return_sha256=return_sha256,
                        worker_final_sha256=worker_final_sha256,
                        error_class=type(exc).__name__,
                        error_message=(
                            str(exc) or type(exc).__name__
                        ),
                        actor="main",
                    )
                except Exception as evidence_exc:
                    raise RuntimeError(
                        f"{exc}; additionally failed to persist the "
                        "core-ingest failure/abort transaction: "
                        f"{evidence_exc}"
                    ) from exc
                if recorded:
                    try:
                        return_path.chmod(
                            return_path.stat().st_mode & ~0o222
                        )
                    except OSError:
                        # The hash-bound failure and abort remain the
                        # cooperative terminal evidence; audit will report
                        # later byte disappearance or replacement.
                        pass
            raise


def _ingest_return_locked(
    store: MathGraphStore,
    round_id: str,
    assignment_id: str,
    *,
    worker_final_sha256: str,
) -> dict[str, Any]:
    if not isinstance(worker_final_sha256, str) or SHA256_RE.fullmatch(
        worker_final_sha256
    ) is None:
        raise ValueError("worker_final_sha256 must be 64 lowercase hex characters")
    validated = validate_return(store, round_id, assignment_id)
    round_dir, manifest = _round_manifest(store, round_id)
    assignment = _assignment(manifest, assignment_id)
    return_path = Path(validated["return_path"])
    receipt_path = return_path.with_suffix(".receipt.json")
    raw = return_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    return_sha = validated["return_sha256"]
    if worker_final_sha256 != return_sha:
        raise ValueError(
            "worker final SHA-256 does not match the current return bytes; "
            "wait for an explicit final handoff or repair the un-ingested draft"
        )
    if receipt_path.exists():
        receipt = store._read_json(receipt_path)
        if manifest.get("schema_version") == 4:
            validate_ingestion_receipt_v4(receipt)
        if receipt.get("return_sha256") != return_sha:
            raise ValueError("worker return changed after ingestion")
        if receipt.get("assignment_id") != assignment_id:
            raise ValueError("receipt belongs to another assignment")
        recorded_final_sha = receipt.get("worker_final_sha256")
        if recorded_final_sha is not None and recorded_final_sha != worker_final_sha256:
            raise ValueError("worker final SHA-256 differs from the ingest receipt")
        if manifest.get("schema_version") >= 3 and receipt.get("artifacts") != validated["artifacts"]:
            raise ValueError("declared artifacts changed after ingestion")
        if manifest.get("schema_version") == 4:
            for key, value in receipt["effect"].items():
                if key == "status":
                    continue
                if receipt.get(key) != value:
                    raise ValueError(
                        "v4 ingestion receipt flattened effect mismatch"
                    )
            _apply_ingestion_memory_effect(
                store,
                payload=payload,
                manifest=manifest,
                assignment=assignment,
                return_sha=return_sha,
                effect=receipt["effect"],
            )
            store.blackboard().reindex(
                apply=True,
                actor="orchestrator",
            )
        if receipt.get("return_locked") is True:
            return_path.chmod(return_path.stat().st_mode & ~0o222)
            for artifact in validated["artifacts"]:
                artifact_path = contained_path(store.root, artifact["path"], "artifact path")
                artifact_path.chmod(artifact_path.stat().st_mode & ~0o222)
        return receipt
    outcome = validated["outcome"]
    memory_id = validate_memory_id(assignment["memory_id"])
    effect: dict[str, Any]
    with store.mutation_lock():
        task_card: dict[str, Any] | None = None
        if manifest.get("schema_version") == 4:
            task_card = store._read_json(
                contained_path(
                    store.root,
                    assignment["task_card_relpath"],
                    "task card path",
                )
            )
            # Complete every graph/capability/cycle check before any
            # submission or exploration effect is staged.
            store.blackboard().validate_delta(
                delta=payload["blackboard_graph_delta"],
                task_card=task_card,
                return_sha256=return_sha,
                defer_visibility=True,
                allow_legacy_adoption=True,
            )
            store.collaboration().preflight_review_delta(
                task_card=task_card,
                delta=payload["blackboard_graph_delta"],
                artifacts=validated["artifacts"],
            )
        if outcome == "fact_submission":
            claim_relation = (
                payload["claim_relation"]
                if manifest.get("schema_version") >= 3
                else "proves"
            )
            fact = Fact(
                problem_id=manifest["project_id"],
                author=assignment["worker_id"],
                predecessors=list(payload["predecessors"]),
                glossary_introduces=dict(payload.get("glossary_introduces", {})),
                external_refs=[dict(item) for item in payload.get("external_refs", [])],
                elementary_uses=[
                    dict(item) for item in payload.get("elementary_uses", [])
                ],
                statement=payload["statement"],
                proof=payload["proof"],
                intuition=payload.get("intuition", ""),
                predecessor_uses=[
                    dict(item) for item in payload.get("predecessor_uses", [])
                ],
                quantifier_ledger=[
                    dict(item) for item in payload.get("quantifier_ledger", [])
                ],
                convention_profile_ids=list(
                    payload.get("convention_profile_ids", [])
                ),
                computational_evidence=[
                    dict(item)
                    for item in payload.get("computational_evidence", [])
                ],
                terminology=[
                    dict(item) for item in payload.get("terminology", [])
                ],
            )
            fact_id = store.submit(
                fact,
                worker=assignment["worker_id"],
                task_id=memory_id,
                round_id=round_id,
                assignment_id=assignment_id,
                claim_relation=claim_relation,
                task_card_sha256=(
                    payload.get("task_card_sha256", "")
                    if manifest.get("schema_version") == 4
                    else ""
                ),
                blackboard_snapshot_sha256=(
                    payload.get("blackboard_snapshot_sha256", "")
                    if manifest.get("schema_version") == 4
                    else ""
                ),
                artifacts=validated["artifacts"],
                verification_plan=(
                    store._read_json(
                        contained_path(
                            store.root,
                            assignment["task_card_relpath"],
                            "task card path",
                        )
                    )["verification_plan"]
                    if manifest.get("schema_version") == 4
                    else None
                ),
            )
            effect = {"submission_id": fact_id, "status": "pending_review"}
        elif outcome == "fact_bundle_submission":
            active_fact_ids = set(store.fact_ids())
            fact_bundle_id = store.fact_bundles().submit(
                fact_bundle_payload_from_return(payload),
                worker=assignment["worker_id"],
                external_fact_exists=(
                    lambda fact_id: fact_id in active_fact_ids
                ),
                provenance={
                    "round_id": round_id,
                    "assignment_id": assignment_id,
                    "task_card_sha256": payload["task_card_sha256"],
                    "return_sha256": return_sha,
                },
            )
            if fact_bundle_id != validated.get("fact_bundle_id"):
                raise ValueError(
                    "fact-bundle dry-run and ingestion ids differ"
                )
            effect = {
                "fact_bundle_id": fact_bundle_id,
                "status": "pending_bundle_review",
            }
        else:
            entry_id = _json_hash([assignment_id, return_sha, outcome], 12)
            effect = {
                "memory_entry_id": entry_id,
                "status": "recorded_not_truth",
            }
            if outcome == "counterexample":
                effect["repair_ready"] = True
                effect["repair_command"] = (
                    f"plan-repair-round {memory_id} --trigger-memory-id {entry_id}"
                )
        if manifest.get("schema_version") != 4:
            _apply_ingestion_memory_effect(
                store,
                payload=payload,
                manifest=manifest,
                assignment=assignment,
                return_sha=return_sha,
                effect=effect,
            )
        blackboard_effect: dict[str, Any] = {}
        if manifest.get("schema_version") == 4:
            assert task_card is not None
            merge_receipt = store.blackboard().merge_delta(
                delta=payload["blackboard_graph_delta"],
                task_card=task_card,
                return_sha256=return_sha,
                defer_visibility=True,
                allow_legacy_adoption=True,
            )
            blackboard_effect = {
                "blackboard_transaction_id": merge_receipt["transaction_id"],
                "blackboard_node_ids": merge_receipt["node_ids"],
                "blackboard_edge_ids": merge_receipt["edge_ids"],
            }
        receipt = {
            "schema_version": manifest["schema_version"],
            "project_id": manifest["project_id"],
            "round_id": round_id,
            "assignment_id": assignment_id,
            "assignment_sha256": assignment["assignment_sha256"],
            "return_relpath": assignment["return_relpath"],
            "return_sha256": return_sha,
            "worker_final_sha256": worker_final_sha256,
            "return_locked": True,
            "outcome": outcome,
            **(
                {"task_card_sha256": payload["task_card_sha256"]}
                if outcome == "fact_bundle_submission"
                else {}
            ),
            **(
                {"artifacts": validated["artifacts"]}
                if manifest.get("schema_version") >= 3
                else {}
            ),
            **effect,
            **blackboard_effect,
            "status": "ingested",
            "ingested_at": utc_now(),
        }
        if manifest.get("schema_version") == 4:
            receipt = seal_ingestion_receipt_v4(
                {
                    **receipt,
                    "policy_revision": POLICY_REVISION_V4,
                    "effect": effect,
                }
            )
        store._write_json_once(receipt_path, receipt)
        if manifest.get("schema_version") == 4:
            _apply_ingestion_memory_effect(
                store,
                payload=payload,
                manifest=manifest,
                assignment=assignment,
                return_sha=return_sha,
                effect=effect,
            )
            store.blackboard().reindex(
                apply=True,
                actor="orchestrator",
            )
        return_path.chmod(return_path.stat().st_mode & ~0o222)
        for artifact in validated["artifacts"]:
            artifact_path = contained_path(store.root, artifact["path"], "artifact path")
            artifact_path.chmod(artifact_path.stat().st_mode & ~0o222)
        return receipt


def create_repair_round(
    store: MathGraphStore,
    memory_id: str,
    *,
    trigger_memory_id: str | None = None,
) -> dict[str, Any]:
    """Create the minimal-repair and strongest-defensible branches in one bound round."""

    memory_id = validate_memory_id(memory_id)
    memory = store.memory_latest()
    original = memory.get(memory_id)
    if original is None:
        raise KeyError(f"unknown memory entry: {memory_id}")
    trigger: dict[str, Any] | None = None
    if trigger_memory_id is not None:
        trigger_memory_id = validate_memory_id(trigger_memory_id)
        trigger = memory.get(trigger_memory_id)
        if trigger is None:
            raise KeyError(f"unknown trigger memory entry: {trigger_memory_id}")
        parent = trigger.get("parent_memory_id")
        if parent not in {None, memory_id}:
            raise ValueError("trigger memory belongs to another parent claim")
    else:
        candidates = [
            entry
            for entry in memory.values()
            if entry.get("parent_memory_id") == memory_id
            and entry.get("kind") in {"counterexample", "obstacle", "dead_end"}
        ]
        if candidates:
            trigger = candidates[-1]
            trigger_memory_id = str(trigger["id"])
    if trigger is None and original.get("status") != "challenged":
        raise ValueError(
            "repair planning requires a challenged claim or an explicit trigger memory"
        )
    challenge = (
        f"{trigger.get('claim', '')}\n{trigger.get('rationale', '')}".strip()
        if trigger is not None
        else str(original.get("note", "")).strip()
    )
    original_claim = str(original.get("claim", "")).strip()
    dependencies = list(original.get("dependencies", []))
    if store.workflow_evidence_version() >= 4:
        blackboard = store.blackboard()
        project_space = next(
            node_id
            for node_id, node in blackboard.nodes().items()
            if node["node_type"] == "space"
        )
        context_node = make_node(
            node_type="conflict",
            logical_key=(
                f"repair-context:{memory_id}:"
                f"{trigger_memory_id or 'status-challenge'}"
            ),
            payload={
                "repair_of_memory_id": memory_id,
                "original_claim": original_claim,
                "trigger_memory_id": trigger_memory_id,
                "challenge": challenge or "unspecified",
            },
            truth_status="challenged",
            convention_profile_ids=list(
                original.get("convention_profile_ids", [])
            ),
            source_refs=[
                f"memory:{memory_id}",
                *(
                    [f"memory:{trigger_memory_id}"]
                    if trigger_memory_id
                    else []
                ),
            ],
            created_by_assignment_id="orchestrator",
        )
        blackboard.add_node_with_placements(
            node=context_node,
            space_ids=[project_space],
            actor="orchestrator",
        )
        blackboard.reindex(apply=True, actor="orchestrator")
        query = {
            "seed_node_ids": [context_node["node_id"]],
            "direction": "both",
            "max_hops": 1,
            "edge_type_allowlist": ["placed_in"],
            "node_type_allowlist": ["*"],
            "node_budget": 32,
            "edge_budget": 64,
        }
        snapshot = blackboard.snapshot(query=query, actor="orchestrator")
        node_hash = sha256_bytes(
            json.dumps(
                context_node,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        failed_obligations = list(
            trigger.get("failed_obligation_ids", [])
            if trigger is not None
            else []
        )
        obligation_ids = [
            str(item.get("id"))
            for item in original.get("obligations", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        preserve_obligations = sorted(
            set(obligation_ids).difference(failed_obligations)
        )
        decision_profile = dict(
            original.get(
                "decision_profile",
                {
                    "burden": 0.5,
                    "impact": 0.5,
                    "information_value": 0.5,
                    "tractability": 0.5,
                },
            )
        )
        common_v4 = {
            "dependencies": dependencies,
            "decision_profile": decision_profile,
            "tags": sorted(
                set([*original.get("tags", []), "automatic-repair"])
            ),
            "repair_of_memory_id": memory_id,
            "trigger_memory_id": trigger_memory_id or "",
            "campaign_id": original.get("campaign_id"),
            "source_claim_id": original.get("source_claim_id"),
            "convention_profile_ids": list(
                original.get("convention_profile_ids", [])
            ),
            "stop_conditions": list(original.get("stop_conditions", [])),
            "origin_blackboard_node_id": context_node["node_id"],
            "origin_blackboard_snapshot_id": snapshot["snapshot_id"],
            "origin_blackboard_node_sha256": node_hash,
            "blackboard_query_sha256": sha256_json(query),
            "blackboard_query": query,
            "promotion_task_sha256": sha256_json(
                {
                    "repair_of_memory_id": memory_id,
                    "trigger_memory_id": trigger_memory_id,
                    "snapshot_id": snapshot["snapshot_id"],
                }
            ),
            "failed_obligation_ids": failed_obligations,
            "preserve_obligation_ids": preserve_obligations,
        }
        minimal_id = store.memory_add(
            {
                **common_v4,
                "kind": "conjecture",
                "claim": (
                    f"Repair memory {memory_id} from trigger "
                    f"{trigger_memory_id or 'status-challenge'} using mode minimal."
                ),
                "rationale": (
                    "Use the exact original and challenge bytes in the bound "
                    "repair-context snapshot; change the fewest load-bearing fields."
                ),
                "suggested_actions": ["prove"],
                "source": f"repair:{memory_id}:{trigger_memory_id or 'status'}",
                "repair_mode": "minimal",
            },
            actor="orchestrator",
        )
        strongest_id = store.memory_add(
            {
                **common_v4,
                "kind": "direction",
                "claim": (
                    f"Repair memory {memory_id} from trigger "
                    f"{trigger_memory_id or 'status-challenge'} using mode "
                    "strongest_defensible."
                ),
                "rationale": (
                    "Use the exact original and challenge bytes in the bound "
                    "repair-context snapshot; characterize the strongest surviving claim."
                ),
                "suggested_actions": ["refute", "prove"],
                "source": f"repair:{memory_id}:{trigger_memory_id or 'status'}",
                "repair_mode": "strongest_defensible",
            },
            actor="orchestrator",
        )
        planned = create_round(
            store,
            workers=2,
            mode="auto",
            memory_ids=[minimal_id, strongest_id],
        )
        return {
            "repair_of_memory_id": memory_id,
            "trigger_memory_id": trigger_memory_id,
            "repair_memory_ids": [minimal_id, strongest_id],
            "repair_context_node_id": context_node["node_id"],
            "repair_context_snapshot_id": snapshot["snapshot_id"],
            "round": planned,
        }

    common = {
        "dependencies": dependencies,
        "priority": max(float(original.get("priority", 0.5)), 0.7),
        "novelty": float(original.get("novelty", 0.5)),
        "testability": max(float(original.get("testability", 0.5)), 0.8),
        "risk": float(original.get("risk", 0.5)),
        "tags": sorted(set([*original.get("tags", []), "automatic-repair"])),
        "repair_of_memory_id": memory_id,
        "trigger_memory_id": trigger_memory_id or "",
    }
    minimal_id = store.memory_add(
        {
            **common,
            "kind": "conjecture",
            "claim": (
                "Minimal repair task. Starting from the original claim below, use the challenge "
                "to change the fewest load-bearing symbols, hypotheses, domains, or quantifiers. "
                "State one precise corrected proposition and prove or refute it.\n\n"
                f"ORIGINAL:\n{original_claim}\n\nCHALLENGE:\n{challenge or 'unspecified'}"
            ),
            "rationale": "Automatically generated minimal-repair branch.",
            "suggested_actions": ["prove the minimal corrected claim"],
            "source": f"repair:{memory_id}",
        },
        actor="orchestrator",
    )
    strongest_id = store.memory_add(
        {
            **common,
            "kind": "direction",
            "claim": (
                "Strongest defensible replacement task. Starting from the original claim and "
                "challenge below, characterize the maximal natural class that survives. Attack "
                "overstrong variants, minimize counterexamples, and return the strongest atomic "
                "statement justified by proof.\n\n"
                f"ORIGINAL:\n{original_claim}\n\nCHALLENGE:\n{challenge or 'unspecified'}"
            ),
            "rationale": "Automatically generated strengthening/replacement branch.",
            "suggested_actions": ["refute overstrong variants before proposing a replacement"],
            "source": f"repair:{memory_id}",
        },
        actor="orchestrator",
    )
    planned = create_round(
        store,
        workers=2,
        mode="auto",
        memory_ids=[minimal_id, strongest_id],
    )
    return {
        "repair_of_memory_id": memory_id,
        "trigger_memory_id": trigger_memory_id,
        "repair_memory_ids": [minimal_id, strongest_id],
        "round": planned,
    }


def create_verifier_assignment(
    store: MathGraphStore,
    fact_id: str,
    *,
    authorized_artifacts: list[dict[str, str]] | None = None,
    supersedes_bundle_id: str | None = None,
    prior_review_id: str | None = None,
) -> dict[str, Any]:
    submission = store.submission(fact_id)
    if submission.get("evidence_version") == 4:
        frozen = store.freeze_verification_bundle(
            fact_id,
            authorized_artifacts=authorized_artifacts,
            supersedes_bundle_id=supersedes_bundle_id,
            prior_review_id=prior_review_id,
        )
        return {
            "fact_id": fact_id,
            "submission_sha256": frozen["submission_sha256"],
            "bundle_id": frozen["bundle_id"],
            "bundle_sha256": frozen["bundle_sha256"],
            "bundle_path": frozen["bundle_path"],
            "review_return_path": frozen["review_return_path"],
            "spawn_contract": {
                "fork_turns": "none",
                "capability": frozen["capability"],
                "task": (
                    "Use only bundle_path and verify its hash equals bundle_sha256. "
                    "Do not invoke a project CLI, inspect live project state, search the "
                    "project, or read any byte outside the frozen bundle. Review every "
                    "statement, proof step, predecessor statement interface, source "
                    "obligation, computation, and bundle capability. Write exactly one "
                    "schema_version 4 JSON review to review_return_path. A correct review "
                    "has findings=[] and dispositions every finding from earlier reviews; "
                    "a rejection uses structured severity/class findings. Attest "
                    "isolation=fresh_context, fork_turns=none, and this exact bundle hash."
                ),
            },
        }
    frozen = store.freeze_verification_packet(fact_id)
    return {
        "fact_id": fact_id,
        "submission_sha256": frozen["submission_sha256"],
        "packet_sha256": frozen["packet_sha256"],
        "packet_path": frozen["packet_path"],
        "review_return_path": frozen["review_return_path"],
        "assigned_claim": submission.get("assigned_claim", ""),
        "claim_relation": submission.get("claim_relation", "legacy-unspecified"),
        "spawn_contract": {
            "fork_turns": "none",
            "task": (
                "Read packet_path. Do not use project search/show, exploration memory, broad "
                "literature search, secondary summaries, or any other project fact. When the "
                "packet contains external-source applicability evidence, independently open only "
                "the exact primary-source locators listed in that evidence and check the cited "
                "version, statement, every hypothesis, conventions, exclusions, conclusion "
                "strength, and transport or bridge steps. If the exact source is unavailable or "
                "any applicability obligation is unverified, use verdict reject and name the gap. "
                "Verify each source_trace transcription and hash, hashing identical source bytes "
                "once per distinct artifact SHA-256. Repeat notation/binding, type/domain, and "
                "quantifier/scope checks for every item. Group source status evidence by "
                "source_audit.audit_sha256: recompute the audit hash, check its exact-artifact "
                "binding and at-most-30-day reuse provenance, and inspect the three stored "
                "version-history, erratum, and retraction/counterexample locators once per group. "
                "For a baseline-only group, independently repeat at least one unpredictable current "
                "status query. If any item is strict, repeat all three searches and also repeat "
                "boundary/toy-case plus statement/proof-consistency checks for each strict item. "
                "Formula/sign-sensitive use, bridge/transport or degeneration, target-critical use, "
                "any correction, conflict, failed cheap check, or suspicious signal requires strict "
                "treatment. Reject or escalate a misclassified baseline item. Accept a typo "
                "correction only if it is uniquely forced, non-semantic, "
                "does not strengthen the source, and has a [CRIT:...] proof anchor. Verify an "
                "official erratum by its exact locator and artifact hash. Reject any ambiguous, "
                "material, contradicted, retracted, or unresolved source claim; never repair it "
                "silently or substitute a replacement theorem. "
                "For every formula source, also check its source_fidelity record against source "
                "TeX or the rendered primary page, including every declared operator, bracket, "
                "sign, derivative, subscript, and superscript; text extraction alone is invalid. "
                "Check that the submitted claim_relation is logically correct relative to the "
                "assigned research claim printed in the packet; a false proves/refutes/"
                "strengthens/weakens/replaces label is a review gap. "
                "Inventory every external attribution used in the proof and reject if any such "
                "logical source use has no certificate, even when external_refs is empty. "
                "For a non-attributed named result, accept an exemption only when it is declared "
                "in elementary_uses, belongs to the closed whitelist, has explicit hypothesis "
                "witnesses and scope limitations, and its reconstruction can be checked from the "
                "packet. Reject any elementary ledger entry that imports Weierstrass preparation, "
                "family-uniformity or degeneration, plumbing/topology/monodromy, a global "
                "Riemann-surface theorem, topological recursion, or an external formula, sign, "
                "coefficient, or normalization. Words standard, classical, or well known alone "
                "provide no exemption. "
                "Treat each predecessor statement as the complete reusable theorem interface; "
                "reject any coefficient, estimate, side condition, or lemma imported only from "
                "a predecessor proof unless the current submission proves it independently. "
                "Also map every scope restriction and hypothesis stated by each predecessor to "
                "a current witness; shared terminology does not justify an ambient-category "
                "change, which requires an explicit bridge in the submission. "
                "Track quantifier polarity and the identity of every existentially chosen "
                "exceptional set, neighborhood, coordinate, marking, branch, orientation, or "
                "normalization. Such a witness is not canonical: reject inferred membership, "
                "silent witness replacement, or specialization unless the proof shows that the "
                "replacement retains every literal guarantee. Require explicit bridges from "
                "irreducibility to nonseparating topology, branch count to genus, genus to a "
                "complete A-system, and geometric orientation to the exact model coordinate. "
                "Write exactly one strict JSON review to review_return_path, copying fact_id, "
                "submission_sha256, and packet_sha256 from this contract. Do not modify any "
                "other file."
            ),
        },
    }
