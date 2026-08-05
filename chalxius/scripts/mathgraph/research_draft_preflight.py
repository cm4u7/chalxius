from __future__ import annotations

"""Cross-plane research-draft preflight and validated dependency receipts.

The receipt proves structural closure only.  It cannot replace fresh semantic
verification, a Certification Decision, or the Fact Gateway.
"""

import json
import re
from pathlib import Path
from typing import Any, Callable, Iterable

from .contracts import SHA256_RE, contained_path, sha256_bytes, sha256_json
from .interfaces import validate_statement_interface
from .research_draft import (
    AUTHORIZATION_ID_RE,
    LEGACY_RESEARCH_DRAFT_ADEQUACY_REVISION,
    LEGACY_RESEARCH_DRAFT_BATCH_REVISION,
    LEGACY_RESEARCH_DRAFT_PLAN_REVISION,
    MAPPING_RELATIONS,
    MATHEMATICAL_EXACT_OUTCOMES,
    RESEARCH_DRAFT_ADEQUACY_REVISION,
    RESEARCH_DRAFT_BATCH_REVISION,
    RESEARCH_DRAFT_PLAN_REVISION,
    validate_mathematical_refinement_dag,
)


LEGACY_ASSURANCE_REVISION = "chalxius-research-draft-assurance-1"
ASSURANCE_REVISION = "chalxius-research-draft-assurance-2"
PREFLIGHT_REVISION = "chalxius-research-draft-admission-preflight-1"
DEPENDENCY_RECEIPT_REVISION = "chalxius-validated-dependency-receipt-1"
PAPER_TRANSPORT_REVISION = "chalxius-paper-evidence-transport-closure-1"
RECEIPT_ID_RE = re.compile(r"vdr-[0-9a-f]{64}")
PREFLIGHT_ID_RE = re.compile(r"rdpf-[0-9a-f]{64}")
COMPONENT_ID_RE = re.compile(r"component-[A-Za-z0-9][A-Za-z0-9_.:-]{0,191}")


def _exact(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} fields are not exact")
    return value


def _text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    value = value.strip()
    if not allow_empty and not value:
        raise ValueError(f"{label} must be nonempty")
    return value


def _strings(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{label} must be a list of nonempty strings")
    result = [item.strip() for item in value]
    if nonempty and not result:
        raise ValueError(f"{label} must be nonempty")
    if len(result) != len(set(result)):
        raise ValueError(f"{label} contains duplicates")
    return sorted(result)


def research_draft_ref(
    *, plan: dict[str, Any], batch: dict[str, Any], adequacy_receipt: dict[str, Any]
) -> dict[str, Any]:
    revision_tuple = (
        plan.get("contract_revision"),
        batch.get("contract_revision"),
        adequacy_receipt.get("contract_revision"),
    )
    if (
        revision_tuple
        not in {
            (
                LEGACY_RESEARCH_DRAFT_PLAN_REVISION,
                LEGACY_RESEARCH_DRAFT_BATCH_REVISION,
                LEGACY_RESEARCH_DRAFT_ADEQUACY_REVISION,
            ),
            (
                RESEARCH_DRAFT_PLAN_REVISION,
                RESEARCH_DRAFT_BATCH_REVISION,
                RESEARCH_DRAFT_ADEQUACY_REVISION,
            ),
        }
        or batch.get("plan_id") != plan.get("plan_id")
        or adequacy_receipt.get("plan_id") != plan.get("plan_id")
        or adequacy_receipt.get("batch_id") != batch.get("batch_id")
        or adequacy_receipt.get("adequacy_complete") is not True
    ):
        raise ValueError("research-draft release reference inputs are inconsistent")
    return {
        "contract_revision": adequacy_receipt["contract_revision"],
        "plan_id": plan["plan_id"],
        "plan_record_sha256": plan["record_sha256"],
        "batch_id": batch["batch_id"],
        "batch_record_sha256": batch["record_sha256"],
        "adequacy_receipt_sha256": adequacy_receipt[
            "adequacy_receipt_sha256"
        ],
    }


def validate_research_draft_ref(
    ref: Any,
    *,
    plan: dict[str, Any],
    batch: dict[str, Any],
    adequacy_receipt: dict[str, Any],
) -> dict[str, Any]:
    _exact(
        ref,
        {
            "contract_revision",
            "plan_id",
            "plan_record_sha256",
            "batch_id",
            "batch_record_sha256",
            "adequacy_receipt_sha256",
        },
        "research-draft release ref",
    )
    expected = research_draft_ref(
        plan=plan, batch=batch, adequacy_receipt=adequacy_receipt
    )
    if ref != expected:
        raise ValueError("research-draft release ref is stale or incomplete")
    return ref


def _validate_stance_preservation(value: Any) -> dict[str, Any]:
    stance = _exact(
        value,
        {
            "policy",
            "declared_stance_sha256",
            "headline_target_ids",
            "headline_impacts",
            "major_revision_authorization_ids",
        },
        "research-draft stance preservation",
    )
    if stance["policy"] not in {
        "steelman_headline",
        "preserve_declared_stance",
        "allow_major_revision",
    }:
        raise ValueError("research-draft stance-preservation policy is invalid")
    declared_hash = _text(
        stance["declared_stance_sha256"], "declared stance SHA-256"
    )
    if SHA256_RE.fullmatch(declared_hash) is None:
        raise ValueError("declared stance SHA-256 is invalid")
    headline_ids = _strings(
        stance["headline_target_ids"], "stance headline target ids", nonempty=True
    )
    impacts = stance["headline_impacts"]
    if not isinstance(impacts, list):
        raise ValueError("stance headline impacts must be a list")
    normalized_impacts: list[dict[str, str]] = []
    impacted: set[str] = set()
    for item in impacts:
        _exact(
            item,
            {"target_node_id", "impact", "reason"},
            "stance headline impact",
        )
        target_id = _text(item["target_node_id"], "stance headline target")
        if target_id not in headline_ids or target_id in impacted:
            raise ValueError("stance headline impact target is invalid or duplicated")
        impacted.add(target_id)
        impact = item["impact"]
        if impact not in {
            "preserves_headline",
            "strengthens_headline",
            "narrows_headline",
            "reverses_headline",
            "withdraws_headline",
        }:
            raise ValueError("stance headline impact is invalid")
        normalized_impacts.append(
            {
                "target_node_id": target_id,
                "impact": impact,
                "reason": _text(item["reason"], "stance impact reason"),
            }
        )
    if impacted != set(headline_ids):
        raise ValueError("stance headline impacts are incomplete")
    authorization_ids = _strings(
        stance["major_revision_authorization_ids"],
        "stance authorization ids",
    )
    if any(AUTHORIZATION_ID_RE.fullmatch(item) is None for item in authorization_ids):
        raise ValueError("stance authorization id is invalid")
    major = any(
        item["impact"]
        in {"narrows_headline", "reverses_headline", "withdraws_headline"}
        for item in normalized_impacts
    )
    if major and not authorization_ids:
        raise ValueError("major research-draft stance revision lacks authorization")
    if not major and authorization_ids:
        raise ValueError(
            "non-major research-draft stance cannot claim a major-revision authorization"
        )
    return {
        "policy": stance["policy"],
        "declared_stance_sha256": declared_hash,
        "headline_target_ids": headline_ids,
        "headline_impacts": sorted(
            normalized_impacts, key=lambda item: item["target_node_id"]
        ),
        "major_revision_authorization_ids": authorization_ids,
    }


def _validate_mathematical_target_preservation(value: Any) -> dict[str, Any]:
    value = _exact(
        value,
        {
            "target_policy_sha256",
            "exact_target_root_sha256",
            "target_claim_ids",
            "hypothesis_claim_ids",
            "root_resolution_status",
            "root_resolution_evidence_ids",
            "original_target_open",
            "target_progress",
            "weakening_closes_exact_target",
        },
        "research-draft mathematical target preservation",
    )
    for field in ("target_policy_sha256", "exact_target_root_sha256"):
        if not isinstance(value[field], str) or SHA256_RE.fullmatch(value[field]) is None:
            raise ValueError(f"mathematical target preservation {field} is invalid")
    target_claim_ids = _strings(
        value["target_claim_ids"], "mathematical assurance target claim ids", nonempty=True
    )
    hypothesis_claim_ids = _strings(
        value["hypothesis_claim_ids"], "mathematical assurance hypothesis claim ids"
    )
    root_status = value["root_resolution_status"]
    if root_status not in MATHEMATICAL_EXACT_OUTCOMES:
        raise ValueError("mathematical assurance root resolution status is invalid")
    root_evidence = _strings(
        value["root_resolution_evidence_ids"], "mathematical assurance root evidence ids"
    )
    root_open = value["original_target_open"]
    if root_status in {"proved", "disproved"}:
        if not root_evidence or root_open is not False:
            raise ValueError("mathematical assurance may close the root only with exact evidence")
    elif root_open is not True:
        raise ValueError("unresolved mathematical assurance must keep the exact root open")
    if value["weakening_closes_exact_target"] is not False:
        raise ValueError("mathematical weakening cannot close the exact target")
    progress = value["target_progress"]
    if not isinstance(progress, list) or not progress:
        raise ValueError("mathematical assurance target progress must be target-total")
    normalized_progress: list[dict[str, Any]] = []
    seen_targets: set[str] = set()
    for item in progress:
        _exact(
            item,
            {
                "target_node_id",
                "progress_class",
                "refinement_dag_sha256",
            },
            "mathematical assurance target progress",
        )
        target_id = _text(item["target_node_id"], "mathematical assurance target node")
        if target_id in seen_targets:
            raise ValueError("mathematical assurance target progress is duplicated")
        seen_targets.add(target_id)
        if item["progress_class"] not in {
            "exact_target_resolved",
            "partial_verified_progress",
            "unresolved_with_obstruction",
        }:
            raise ValueError("mathematical assurance progress class is invalid")
        digest = item["refinement_dag_sha256"]
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            raise ValueError("mathematical assurance refinement DAG hash is invalid")
        normalized_progress.append(
            {
                "target_node_id": target_id,
                "progress_class": item["progress_class"],
                "refinement_dag_sha256": digest,
            }
        )
    return {
        "target_policy_sha256": value["target_policy_sha256"],
        "exact_target_root_sha256": value["exact_target_root_sha256"],
        "target_claim_ids": target_claim_ids,
        "hypothesis_claim_ids": hypothesis_claim_ids,
        "root_resolution_status": root_status,
        "root_resolution_evidence_ids": root_evidence,
        "original_target_open": root_open,
        "target_progress": sorted(
            normalized_progress, key=lambda item: item["target_node_id"]
        ),
        "weakening_closes_exact_target": False,
    }


def _validate_domain_target_preservation(value: Any) -> dict[str, Any]:
    value = _exact(
        value,
        {"adapter", "target_policy_sha256", "target_outcomes"},
        "research-draft domain target preservation",
    )
    if value["adapter"] not in {"empirical_target", "mixed_target"}:
        raise ValueError("research-draft domain target adapter is invalid")
    digest = value["target_policy_sha256"]
    if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
        raise ValueError("research-draft domain target policy hash is invalid")
    if not isinstance(value["target_outcomes"], list) or not value["target_outcomes"]:
        raise ValueError("research-draft domain target outcomes must be target-total")
    return {
        "adapter": value["adapter"],
        "target_policy_sha256": digest,
        "target_outcomes": value["target_outcomes"],
    }


def validate_research_draft_assurance(
    assurance: Any,
    *,
    candidate_facts: dict[str, Any],
    internal_edges: list[list[str]],
) -> dict[str, Any]:
    common_fields = {
        "contract_revision",
        "validation_subject",
        "validation_granularity",
        "paper_node_dispositions",
        "paper_fact_mappings",
        "component_inventory",
    }
    if not isinstance(assurance, dict):
        raise ValueError("research-draft assurance fields are not exact")
    revision = assurance.get("contract_revision")
    domain_fields = {
        field
        for field in (
            "stance_preservation",
            "mathematical_target_preservation",
            "domain_target_preservation",
        )
        if field in assurance
    }
    if revision == LEGACY_ASSURANCE_REVISION:
        if domain_fields != {"stance_preservation"}:
            raise ValueError("legacy research-draft assurance requires stance preservation")
        domain_field = "stance_preservation"
    elif revision == ASSURANCE_REVISION:
        if len(domain_fields) != 1:
            raise ValueError("current research-draft assurance requires exactly one domain adapter")
        domain_field = next(iter(domain_fields))
    else:
        raise ValueError("research-draft assurance revision is invalid")
    fields = {*common_fields, domain_field}
    assurance = _exact(assurance, fields, "research-draft assurance")
    subject = _exact(
        assurance["validation_subject"],
        {"kind", "subject_id", "artifact_sha256", "load_bearing_node_ids"},
        "research-draft validation subject",
    )
    if subject["kind"] != "paper":
        raise ValueError("research_draft can only use validation_subject.kind=paper")
    subject_id = _text(subject["subject_id"], "research-draft subject id")
    artifact_sha256 = _text(
        subject["artifact_sha256"], "research-draft source artifact SHA-256"
    )
    if SHA256_RE.fullmatch(artifact_sha256) is None:
        raise ValueError("research-draft source artifact hash is invalid")
    load_bearing = _strings(
        subject["load_bearing_node_ids"],
        "research-draft load-bearing nodes",
        nonempty=True,
    )
    if assurance["validation_granularity"] != "paper_target_closure":
        raise ValueError("research_draft requires paper_target_closure granularity")
    dispositions = assurance["paper_node_dispositions"]
    if not isinstance(dispositions, list):
        raise ValueError("paper_node_dispositions must be a list")
    normalized_dispositions: list[dict[str, str]] = []
    disposed: set[str] = set()
    for item in dispositions:
        _exact(
            item,
            {"paper_node_id", "disposition", "reason"},
            "research-draft Paper-node disposition",
        )
        node_id = _text(item["paper_node_id"], "Paper-node disposition id")
        if node_id in disposed:
            raise ValueError("research-draft Paper-node disposition is duplicated")
        disposed.add(node_id)
        disposition = item["disposition"]
        if disposition not in {
            "represented",
            "retained_as_source",
            "repaired",
            "excluded_with_reason",
        }:
            raise ValueError("research-draft Paper-node disposition is invalid")
        reason = _text(item["reason"], "Paper-node disposition reason")
        normalized_dispositions.append(
            {"paper_node_id": node_id, "disposition": disposition, "reason": reason}
        )
    if disposed != set(load_bearing):
        raise ValueError(
            "research-draft Paper-node dispositions do not cover the exact closure"
        )
    mappings = assurance["paper_fact_mappings"]
    if not isinstance(mappings, list):
        raise ValueError("paper_fact_mappings must be a list")
    normalized_mappings: list[dict[str, Any]] = []
    mapped_facts: set[str] = set()
    seen_mappings: set[tuple[str, str, str]] = set()
    for item in mappings:
        _exact(
            item,
            {"paper_node_id", "fact_id", "relation_kind", "edge_ids", "reason"},
            "research-draft Paper-Fact mapping",
        )
        node_id = _text(item["paper_node_id"], "Paper-Fact mapping node")
        fact_id = _text(item["fact_id"], "Paper-Fact mapping Fact")
        relation = item["relation_kind"]
        if node_id not in disposed or fact_id not in candidate_facts:
            raise ValueError("research-draft Paper-Fact mapping endpoint is unknown")
        if relation not in MAPPING_RELATIONS:
            raise ValueError("research-draft Paper-Fact mapping relation is invalid")
        edge_ids = _strings(
            item["edge_ids"], "research-draft mapping edge ids", nonempty=True
        )
        key = (node_id, fact_id, relation)
        if key in seen_mappings:
            raise ValueError("research-draft Paper-Fact mapping is duplicated")
        seen_mappings.add(key)
        mapped_facts.add(fact_id)
        normalized_mappings.append(
            {
                "paper_node_id": node_id,
                "fact_id": fact_id,
                "relation_kind": relation,
                "edge_ids": edge_ids,
                "reason": _text(item["reason"], "Paper-Fact mapping reason"),
            }
        )
    if mapped_facts != set(candidate_facts):
        raise ValueError("research-draft Paper-Fact mappings leave Candidate Facts orphaned")
    components = assurance["component_inventory"]
    if not isinstance(components, list):
        raise ValueError("research-draft component inventory must be a list")
    normalized_components: list[dict[str, Any]] = []
    represented_facts: set[str] = set()
    component_ids: set[str] = set()
    for item in components:
        _exact(
            item,
            {
                "component_id",
                "fact_id",
                "statement",
                "statement_sha256",
                "source_component_refs",
                "failure_surface_uids",
                "independence_rationale",
            },
            "research-draft component inventory item",
        )
        component_id = _text(item["component_id"], "Candidate component id")
        if COMPONENT_ID_RE.fullmatch(component_id) is None or component_id in component_ids:
            raise ValueError("research-draft Candidate component id is invalid or duplicated")
        component_ids.add(component_id)
        fact_id = _text(item["fact_id"], "Candidate component Fact id")
        if fact_id not in candidate_facts or fact_id in represented_facts:
            raise ValueError("each Candidate Fact must represent exactly one component")
        represented_facts.add(fact_id)
        statement = _text(item["statement"], "Candidate component statement")
        fact_statement = candidate_facts[fact_id].statement.strip()
        if statement != fact_statement:
            raise ValueError("Candidate component statement must equal its exact Fact statement")
        statement_sha = _text(item["statement_sha256"], "Candidate component statement hash")
        if statement_sha != sha256_bytes(statement.encode("utf-8")):
            raise ValueError("Candidate component statement hash mismatch")
        source_refs = item["source_component_refs"]
        if not isinstance(source_refs, list) or not source_refs:
            raise ValueError("Candidate component requires source proposition references")
        normalized_refs: list[dict[str, str]] = []
        ref_keys: set[tuple[str, str]] = set()
        for ref in source_refs:
            _exact(
                ref,
                {"source_node_id", "source_component_id", "exact_span_sha256"},
                "source proposition component reference",
            )
            source_node_id = _text(ref["source_node_id"], "source proposition node")
            source_component_id = _text(
                ref["source_component_id"], "source proposition component id"
            )
            span_sha = _text(ref["exact_span_sha256"], "source proposition span hash")
            if SHA256_RE.fullmatch(span_sha) is None:
                raise ValueError("source proposition span hash is invalid")
            key = (source_node_id, source_component_id)
            if key in ref_keys:
                raise ValueError("source proposition component reference is duplicated")
            ref_keys.add(key)
            normalized_refs.append(
                {
                    "source_node_id": source_node_id,
                    "source_component_id": source_component_id,
                    "exact_span_sha256": span_sha,
                }
            )
        surfaces = _strings(
            item["failure_surface_uids"],
            "Candidate component failure surfaces",
            nonempty=True,
        )
        normalized_components.append(
            {
                "component_id": component_id,
                "fact_id": fact_id,
                "statement": statement,
                "statement_sha256": statement_sha,
                "source_component_refs": sorted(
                    normalized_refs,
                    key=lambda ref: (ref["source_node_id"], ref["source_component_id"]),
                ),
                "failure_surface_uids": surfaces,
                "independence_rationale": _text(
                    item["independence_rationale"],
                    "Candidate component independence rationale",
                ),
            }
        )
    if represented_facts != set(candidate_facts):
        raise ValueError("research-draft component inventory is not Candidate-total")
    if domain_field == "stance_preservation":
        normalized_domain = _validate_stance_preservation(assurance[domain_field])
    elif domain_field == "mathematical_target_preservation":
        normalized_domain = _validate_mathematical_target_preservation(
            assurance[domain_field]
        )
    else:
        normalized_domain = _validate_domain_target_preservation(
            assurance[domain_field]
        )
    result = {
        "contract_revision": revision,
        "validation_subject": {
            "kind": "paper",
            "subject_id": subject_id,
            "artifact_sha256": artifact_sha256,
            "load_bearing_node_ids": load_bearing,
        },
        "validation_granularity": "paper_target_closure",
        "paper_node_dispositions": sorted(
            normalized_dispositions, key=lambda item: item["paper_node_id"]
        ),
        "paper_fact_mappings": sorted(
            normalized_mappings,
            key=lambda item: (
                item["paper_node_id"],
                item["fact_id"],
                item["relation_kind"],
            ),
        ),
        "component_inventory": sorted(
            normalized_components, key=lambda item: item["component_id"]
        ),
    }
    result[domain_field] = normalized_domain
    return result


def derive_paper_transport_closure(
    store: Any, refs: list[dict[str, Any]]
) -> dict[str, Any]:
    paper = store.paper_logic()
    members: dict[tuple[str, str], dict[str, Any]] = {}

    def add(path: Path, role: str, snapshot_id: str) -> None:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Paper transport member is missing or unsafe: {path}")
        raw = path.read_bytes()
        relpath = path.relative_to(store.root).as_posix()
        digest = sha256_bytes(raw)
        key = (relpath, role)
        record = {
            "source_relpath": relpath,
            "artifact_sha256": digest,
            "role": role,
            "snapshot_ids": [snapshot_id],
            "size_bytes": len(raw),
        }
        previous = members.get(key)
        if previous is not None:
            if {
                key: value
                for key, value in previous.items()
                if key != "snapshot_ids"
            } != {
                key: value
                for key, value in record.items()
                if key != "snapshot_ids"
            }:
                raise ValueError("Paper transport member identity collision")
            previous["snapshot_ids"] = sorted(
                {*previous["snapshot_ids"], snapshot_id}
            )
        else:
            members[key] = record

    visited_snapshots: set[str] = set()

    def visit(snapshot_id: str) -> None:
        if snapshot_id in visited_snapshots:
            return
        visited_snapshots.add(snapshot_id)
        directory = paper.snapshots_dir / snapshot_id
        manifest_path = directory / "manifest.json"
        add(manifest_path, "paper_snapshot_manifest", snapshot_id)
        add(directory / "nodes.jsonl", "paper_snapshot_nodes", snapshot_id)
        add(directory / "edges.jsonl", "paper_snapshot_edges", snapshot_id)
        manifest = paper.snapshot_manifest(snapshot_id)
        for revision_id in manifest["revision_ids"]:
            add(
                paper.revisions_dir / f"{revision_id}.json",
                "paper_revision_record",
                snapshot_id,
            )
        for review_id in manifest["review_ids"]:
            add(
                paper.reviews_dir / f"{review_id}.json",
                "paper_review_record",
                snapshot_id,
            )
        transaction_id = manifest["transaction_id"]
        add(
            paper.transactions_dir / f"{transaction_id}.json",
            "paper_transaction_record",
            snapshot_id,
        )
        for artifact in manifest["source_artifacts"]:
            add(
                contained_path(
                    store.root,
                    artifact["artifact_relpath"],
                    "Paper transport source artifact",
                ),
                "paper_source_artifact",
                snapshot_id,
            )
        base = manifest.get("base_snapshot_id")
        if base:
            visit(base)

    for ref in refs:
        snapshot_id = _text(ref.get("snapshot_id"), "Paper EvidenceRef snapshot id")
        visit(snapshot_id)
    semantic = {
        "schema_version": 1,
        "contract_revision": PAPER_TRANSPORT_REVISION,
        "snapshot_ids": sorted(visited_snapshots),
        "members": sorted(
            members.values(),
            key=lambda item: (item["source_relpath"], item["role"]),
        ),
        "off_project_reconstructable": True,
        "truth_effect": "none",
    }
    return {**semantic, "closure_sha256": sha256_json(semantic)}


def validate_transport_artifacts(
    closure: dict[str, Any],
    artifacts: list[dict[str, Any]],
    *,
    authorized_roles: Iterable[str],
) -> None:
    declared = {
        (item.get("sha256") or item.get("artifact_sha256"), item.get("role"))
        for item in artifacts
    }
    required = {
        (item["artifact_sha256"], item["role"])
        for item in closure["members"]
    }
    missing = sorted(required.difference(declared))
    if missing:
        raise ValueError(
            "Candidate Release lacks Paper EvidenceRef transport members: "
            + ", ".join(f"{role}:{digest}" for digest, role in missing)
        )
    unauthorized = sorted(
        role for _, role in required if role not in set(authorized_roles)
    )
    if unauthorized:
        raise ValueError(
            "Paper EvidenceRef transport roles are not verifier-authorized: "
            + ", ".join(sorted(set(unauthorized)))
        )


def _source_component_inventory(
    *, nodes: dict[str, dict[str, Any]]
) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for node_id, node in nodes.items():
        if node.get("object_type") != "source_unit":
            continue
        inventory = node.get("payload", {}).get("proposition_inventory")
        if inventory is None:
            continue
        if not isinstance(inventory, list):
            raise ValueError("Paper source proposition inventory is malformed")
        for component in inventory:
            key = (node_id, component.get("component_id"))
            if key in result:
                raise ValueError("Paper source proposition component identity is duplicated")
            result[key] = component
    return result


def build_dependency_receipt(
    dependencies: list[dict[str, Any]],
    *,
    validation_subject_sha256: str,
) -> dict[str, Any]:
    if SHA256_RE.fullmatch(validation_subject_sha256) is None:
        raise ValueError("dependency receipt validation-subject hash is invalid")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in dependencies:
        _exact(
            item,
            {
                "dependency_id",
                "kind",
                "relpath_or_null",
                "semantic_sha256_or_null",
                "file_sha256_or_null",
                "invalidation_key",
            },
            "validated dependency",
        )
        dependency_id = _text(item["dependency_id"], "validated dependency id")
        if dependency_id in seen:
            raise ValueError("validated dependency id is duplicated")
        seen.add(dependency_id)
        relpath = item["relpath_or_null"]
        if relpath is not None:
            relpath = _text(relpath, "validated dependency path")
        semantic_hash = item["semantic_sha256_or_null"]
        file_hash = item["file_sha256_or_null"]
        if semantic_hash is not None and (
            not isinstance(semantic_hash, str)
            or SHA256_RE.fullmatch(semantic_hash) is None
        ):
            raise ValueError("validated dependency semantic hash is invalid")
        if file_hash is not None and (
            not isinstance(file_hash, str) or SHA256_RE.fullmatch(file_hash) is None
        ):
            raise ValueError("validated dependency file hash is invalid")
        if semantic_hash is None and file_hash is None:
            raise ValueError("validated dependency requires a semantic or file hash")
        invalidation_key = _text(
            item["invalidation_key"], "validated dependency invalidation key"
        )
        expected_key = sha256_json(
            {
                "dependency_id": dependency_id,
                "kind": item["kind"],
                "relpath_or_null": relpath,
                "semantic_sha256_or_null": semantic_hash,
                "file_sha256_or_null": file_hash,
            }
        )
        if invalidation_key != expected_key:
            raise ValueError("validated dependency invalidation key mismatch")
        normalized.append(
            {
                "dependency_id": dependency_id,
                "kind": _text(item["kind"], "validated dependency kind"),
                "relpath_or_null": relpath,
                "semantic_sha256_or_null": semantic_hash,
                "file_sha256_or_null": file_hash,
                "invalidation_key": invalidation_key,
            }
        )
    semantic = {
        "schema_version": 1,
        "contract_revision": DEPENDENCY_RECEIPT_REVISION,
        "validation_subject_sha256": validation_subject_sha256,
        "dependencies": sorted(normalized, key=lambda item: item["dependency_id"]),
        "validation_mode": "deep_once_then_keyed_reuse",
        "truth_effect": "none",
    }
    receipt_sha = sha256_json(semantic)
    record = {
        **semantic,
        "receipt_id": "vdr-" + receipt_sha,
        "receipt_sha256": receipt_sha,
    }
    record["record_sha256"] = sha256_json(record)
    return record


def validate_dependency_receipt(
    receipt: Any,
    *,
    project_root: Path,
    changed_dependency_ids: set[str] | None = None,
    semantic_resolver: Callable[[dict[str, Any]], str | None] | None = None,
) -> dict[str, Any]:
    fields = {
        "schema_version",
        "contract_revision",
        "validation_subject_sha256",
        "dependencies",
        "validation_mode",
        "truth_effect",
        "receipt_id",
        "receipt_sha256",
        "record_sha256",
    }
    receipt = _exact(receipt, fields, "validated dependency receipt")
    semantic = {
        key: value
        for key, value in receipt.items()
        if key not in {"receipt_id", "receipt_sha256", "record_sha256"}
    }
    receipt_sha = sha256_json(semantic)
    if (
        receipt["schema_version"] != 1
        or receipt["contract_revision"] != DEPENDENCY_RECEIPT_REVISION
        or receipt["receipt_id"] != "vdr-" + receipt_sha
        or receipt["receipt_sha256"] != receipt_sha
        or receipt["record_sha256"]
        != sha256_json({key: value for key, value in receipt.items() if key != "record_sha256"})
        or receipt["truth_effect"] != "none"
    ):
        raise ValueError("validated dependency receipt binding is invalid")
    dependencies = receipt["dependencies"]
    if not isinstance(dependencies, list):
        raise ValueError("validated dependency receipt dependencies must be a list")
    selected = (
        dependencies
        if changed_dependency_ids is None
        else [
            item
            for item in dependencies
            if item.get("dependency_id") in changed_dependency_ids
        ]
    )
    if changed_dependency_ids is not None and {
        item.get("dependency_id") for item in selected
    } != changed_dependency_ids:
        raise ValueError("changed dependency set names an unknown receipt dependency")
    checked: list[str] = []
    for item in selected:
        relpath = item["relpath_or_null"]
        if relpath is not None:
            path = contained_path(project_root, relpath, "validated dependency")
            if path.is_symlink() or not path.is_file():
                raise ValueError("validated dependency file is missing or unsafe")
            if item["file_sha256_or_null"] != sha256_bytes(path.read_bytes()):
                raise ValueError("validated dependency file key changed")
        if item["semantic_sha256_or_null"] is not None and semantic_resolver is not None:
            if semantic_resolver(item) != item["semantic_sha256_or_null"]:
                raise ValueError("validated dependency semantic key changed")
        checked.append(item["dependency_id"])
    return {
        "receipt_id": receipt["receipt_id"],
        "checked_dependency_ids": sorted(checked),
        "reuse_mode": (
            "sealed_record_only"
            if changed_dependency_ids == set()
            else "changed_dependencies_only"
            if changed_dependency_ids is not None
            else "explicit_deep_replay"
        ),
        "truth_effect": "none",
    }


def dependency(
    *,
    dependency_id: str,
    kind: str,
    relpath: str | None,
    semantic_sha256: str | None,
    file_sha256: str | None,
) -> dict[str, Any]:
    semantic = {
        "dependency_id": dependency_id,
        "kind": kind,
        "relpath_or_null": relpath,
        "semantic_sha256_or_null": semantic_sha256,
        "file_sha256_or_null": file_sha256,
    }
    return {**semantic, "invalidation_key": sha256_json(semantic)}


def research_draft_admission_preflight(
    *,
    store: Any,
    plan: dict[str, Any],
    batch: dict[str, Any],
    adequacy_receipt: dict[str, Any],
    release_ref: dict[str, Any],
    assurance: dict[str, Any],
    candidate_facts: dict[str, Any],
    candidate_fact_file_sha256: dict[str, str],
    candidate_interfaces: list[dict[str, Any]],
    internal_edges: list[list[str]],
    external_predecessor_ids: list[str],
    research_bindings: list[dict[str, str]],
    paper_evidence_refs: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    authorized_artifact_roles: list[str],
    active_fact_file_sha256: Callable[[str], str],
    revoked_fact_ids: set[str],
) -> dict[str, Any]:
    validate_research_draft_ref(
        release_ref,
        plan=plan,
        batch=batch,
        adequacy_receipt=adequacy_receipt,
    )
    if plan["source_role"] != "research_draft":
        raise ValueError("research-draft preflight source role is invalid")
    normalized_assurance = validate_research_draft_assurance(
        assurance,
        candidate_facts=candidate_facts,
        internal_edges=internal_edges,
    )
    subject = normalized_assurance["validation_subject"]
    expected_load_bearing = {
        *plan["selected_reconstruction_node_ids"],
        *plan["selected_source_node_ids"],
    }
    if (
        subject["subject_id"] != plan["paper_id"]
        or subject["artifact_sha256"] != plan["source_artifact_sha256"]
        or set(subject["load_bearing_node_ids"]) != expected_load_bearing
    ):
        raise ValueError("research-draft assurance does not bind the complete Paper closure")
    batch_targets = {item["target_node_id"] for item in batch["entries"]}
    if batch_targets != set(plan["target_node_ids"]):
        raise ValueError("research-draft batch/plan target set drifted")
    required_research_ids = {
        research_id
        for entry in batch["entries"]
        for research_id in entry["research_record_ids"]
    }
    bound_research_ids = {binding["research_id"] for binding in research_bindings}
    if not required_research_ids.issubset(bound_research_ids):
        raise ValueError(
            "Candidate Release omits Research records used by the disposition batch"
        )
    current_plan = plan.get("contract_revision") == RESEARCH_DRAFT_PLAN_REVISION
    profile = plan["domain_profile"]
    if not current_plan or profile == "philosophy":
        if "stance_preservation" not in normalized_assurance:
            raise ValueError("philosophy research-draft assurance lacks stance preservation")
        stance = normalized_assurance["stance_preservation"]
        stance_policy = plan["stance_policy"]
        if (
            stance["policy"] != stance_policy["policy"]
            or stance["declared_stance_sha256"]
            != sha256_bytes(stance_policy["declared_stance"].encode("utf-8"))
            or set(stance["headline_target_ids"])
            != set(stance_policy["headline_target_ids"])
        ):
            raise ValueError("research-draft stance preservation drifted from the plan")
        batch_impacts = {
            item["target_node_id"]: item["stance_impact"]
            for item in batch["entries"]
            if item["target_node_id"] in stance_policy["headline_target_ids"]
        }
        assurance_impacts = {
            item["target_node_id"]: item["impact"]
            for item in stance["headline_impacts"]
        }
        if batch_impacts != assurance_impacts:
            raise ValueError("research-draft stance impacts drifted across planes")
        batch_authorization_ids = sorted(
            entry["major_revision_authorization"]["decision_id"]
            for entry in batch["entries"]
            if entry["major_revision_authorization"] is not None
        )
        if batch_authorization_ids != stance["major_revision_authorization_ids"]:
            raise ValueError(
                "research-draft assurance does not bind the exact batch authorization decisions"
            )
    elif profile == "mathematics":
        if "stance_preservation" in normalized_assurance:
            raise ValueError("mathematics cannot use the philosophy stance adapter")
        target_assurance = normalized_assurance.get(
            "mathematical_target_preservation"
        )
        if target_assurance is None:
            raise ValueError("mathematics requires exact-target preservation assurance")
        progress_rows = []
        root_hashes: set[str] = set()
        root_statuses: set[str] = set()
        root_evidence: set[tuple[str, ...]] = set()
        root_open_values: set[bool] = set()
        for entry in batch["entries"]:
            progress = validate_mathematical_refinement_dag(
                entry["mathematical_progress"],
                target_policy=plan["mathematical_target_policy"],
            )
            root_hashes.add(sha256_json(progress["root_target"]))
            root_statuses.add(progress["root_target"]["resolution_status"])
            root_evidence.add(tuple(progress["root_target"]["resolution_evidence_ids"]))
            root_open_values.add(progress["root_target"]["original_target_open"])
            progress_rows.append(
                {
                    "target_node_id": entry["target_node_id"],
                    "progress_class": progress["progress_class"],
                    "refinement_dag_sha256": progress["refinement_dag_sha256"],
                }
            )
        if not (
            len(root_hashes)
            == len(root_statuses)
            == len(root_evidence)
            == len(root_open_values)
            == 1
        ):
            raise ValueError("mathematical disposition batch has inconsistent exact target status")
        expected_target_assurance = {
            "target_policy_sha256": sha256_json(plan["mathematical_target_policy"]),
            "exact_target_root_sha256": next(iter(root_hashes)),
            "target_claim_ids": plan["mathematical_target_policy"]["target_claim_ids"],
            "hypothesis_claim_ids": plan["mathematical_target_policy"][
                "hypothesis_claim_ids"
            ],
            "root_resolution_status": next(iter(root_statuses)),
            "root_resolution_evidence_ids": list(next(iter(root_evidence))),
            "original_target_open": next(iter(root_open_values)),
            "target_progress": sorted(
                progress_rows, key=lambda item: item["target_node_id"]
            ),
            "weakening_closes_exact_target": False,
        }
        if target_assurance != expected_target_assurance:
            raise ValueError("mathematical target/refinement assurance drifted across planes")
    else:
        domain_assurance = normalized_assurance.get("domain_target_preservation")
        expected_adapter = "empirical_target" if profile == "empirical" else "mixed_target"
        if (
            domain_assurance is None
            or domain_assurance["adapter"] != expected_adapter
            or domain_assurance["target_policy_sha256"]
            != sha256_json(plan["domain_target_policy"])
        ):
            raise ValueError("research-draft domain target assurance drifted from the plan")
    paper = store.paper_logic()
    logic_nodes, logic_edges = paper.snapshot_objects(plan["snapshot_id"])
    source_components = _source_component_inventory(nodes=logic_nodes)
    referenced_components: set[tuple[str, str]] = set()
    component_ids: set[str] = set()
    available_surfaces = {
        surface["surface_uid"]: surface
        for entry in batch["entries"]
        for surface in entry["failure_surfaces"]
    }
    assurance_disposition_by_node = {
        item["paper_node_id"]: item["disposition"]
        for item in normalized_assurance["paper_node_dispositions"]
    }
    disposition_projection = {
        "retained": {"represented", "retained_as_source"},
        "repaired": {"repaired"},
        "replaced": {"repaired"},
        "rejected": {"excluded_with_reason"},
        "out_of_scope": {"excluded_with_reason"},
    }
    for entry in batch["entries"]:
        if assurance_disposition_by_node.get(entry["target_node_id"]) not in (
            disposition_projection[entry["node_disposition"]]
        ):
            raise ValueError(
                "research-draft node disposition drifted between batch and assurance"
            )
    mapping_keys = {
        (item["paper_node_id"], item["fact_id"], item["relation_kind"])
        for item in normalized_assurance["paper_fact_mappings"]
    }
    required_mapping_keys = {
        (entry["target_node_id"], mapping["successor_id"], mapping["relation_kind"])
        for entry in batch["entries"]
        for mapping in entry["successor_mappings"]
    }
    if any(fact_id not in candidate_facts for _, fact_id, _ in required_mapping_keys):
        raise ValueError(
            "research-draft disposition successor is not a Candidate Fact"
        )
    if not required_mapping_keys.issubset(mapping_keys):
        raise ValueError(
            "research-draft assurance omits disposition-to-Fact successor mappings"
        )
    mapped_nodes = {node_id for node_id, _, _ in mapping_keys}
    required_mapped_nodes = {
        node_id
        for node_id, disposition in assurance_disposition_by_node.items()
        if disposition != "excluded_with_reason"
    }
    if not required_mapped_nodes.issubset(mapped_nodes):
        raise ValueError(
            "research-draft assurance leaves a retained Paper node without a Fact mapping"
        )
    for component in normalized_assurance["component_inventory"]:
        component_ids.add(component["component_id"])
        if not set(component["failure_surface_uids"]).issubset(available_surfaces):
            raise ValueError("Candidate component cites an unavailable qualified failure surface")
        for surface_uid in component["failure_surface_uids"]:
            surface = available_surfaces[surface_uid]
            if surface["component_id"] != component["component_id"]:
                raise ValueError(
                    "Candidate component/failure-surface identity drifted"
                )
            if (
                surface["target_node_id"],
                component["fact_id"],
            ) not in {(node_id, fact_id) for node_id, fact_id, _ in mapping_keys}:
                raise ValueError(
                    "Candidate failure surface is not connected through a Paper-Fact mapping"
                )
        for ref in component["source_component_refs"]:
            key = (ref["source_node_id"], ref["source_component_id"])
            source = source_components.get(key)
            if source is None:
                raise ValueError("Candidate component cites an unknown source proposition")
            if source["exact_span"]["text_sha256"] != ref["exact_span_sha256"]:
                raise ValueError("Candidate source proposition span hash drifted")
            if source["disposition"] != "represented":
                raise ValueError("Candidate component cites a nonrepresented source proposition")
            referenced_components.add(key)
            if (ref["source_node_id"], component["fact_id"]) not in {
                (node_id, fact_id) for node_id, fact_id, _ in mapping_keys
            }:
                raise ValueError(
                    "Candidate source proposition is not connected to its Fact mapping"
                )
    required_source_components = {
        key
        for key, item in source_components.items()
        if item["disposition"] == "represented"
        and item["challengeability"] == "independently_challengeable"
    }
    if not required_source_components.issubset(referenced_components):
        missing = sorted(required_source_components.difference(referenced_components))
        raise ValueError(f"Candidate component inventory omits source propositions: {missing}")
    if any(
        mapping["fact_id"] not in candidate_facts
        for mapping in normalized_assurance["paper_fact_mappings"]
    ):
        raise ValueError("research-draft mapping references an unknown Candidate Fact")
    exact_logic_edge_ids = set(logic_edges)
    for mapping in normalized_assurance["paper_fact_mappings"]:
        if not set(mapping["edge_ids"]).issubset(exact_logic_edge_ids):
            raise ValueError("research-draft Paper-Fact mapping edge drifted")
        if any(
            mapping["paper_node_id"]
            not in {
                logic_edges[edge_id]["source_id"],
                logic_edges[edge_id]["target_id"],
            }
            for edge_id in mapping["edge_ids"]
        ):
            raise ValueError(
                "research-draft Paper-Fact mapping cites a nonincident Paper edge"
            )
    if any(fact_id in revoked_fact_ids for fact_id in external_predecessor_ids):
        raise ValueError("research-draft Candidate inherits revoked Fact authority")
    for fact_id in external_predecessor_ids:
        active_fact_file_sha256(fact_id)
    interface_by_fact: dict[str, dict[str, Any]] = {}
    for interface in candidate_interfaces:
        validated_interface = validate_statement_interface(interface)
        if validated_interface.get("schema_version") != 6:
            raise ValueError(
                "research-draft Candidate requires a language-neutral schema-6 interface"
            )
        fact_id = validated_interface["fact_id"]
        if fact_id in interface_by_fact:
            raise ValueError("research-draft Candidate interface is duplicated")
        interface_by_fact[fact_id] = validated_interface
    if set(interface_by_fact) != set(candidate_facts):
        raise ValueError("research-draft Candidate interface coverage is incomplete")
    component_by_fact = {
        item["fact_id"]: item
        for item in normalized_assurance["component_inventory"]
    }
    source_operator_kind = {"modal": "modality"}
    for fact_id, interface in interface_by_fact.items():
        clauses = interface["clauses"]
        if len(clauses) != 1:
            raise ValueError(
                "research-draft Candidate Fact must expose exactly one semantic component; "
                "compound conclusions require an explicit mini-DAG"
            )
        semantic = clauses[0]["semantic_contract"]
        component = component_by_fact[fact_id]
        if semantic["domain_profile"] != plan["domain_profile"]:
            raise ValueError(
                "research-draft Candidate semantic interface changes the Paper domain profile"
            )
        if semantic["component_id"] != component["component_id"]:
            raise ValueError(
                "research-draft Candidate semantic component identity drifts from atomicity assurance"
            )
        expected_source_component_ids = {
            item["source_component_id"]
            for item in component["source_component_refs"]
        }
        if set(semantic["source_component_ids"]) != expected_source_component_ids:
            raise ValueError(
                "research-draft Candidate semantic interface/source proposition binding drifted"
            )
        expected_failure_mode_ids = {
            available_surfaces[surface_uid]["surface_id"]
            for surface_uid in component["failure_surface_uids"]
        }
        if set(semantic["failure_mode_ids"]) != expected_failure_mode_ids:
            raise ValueError(
                "research-draft Candidate semantic interface/failure-surface binding drifted"
            )
        required_operators: set[tuple[str, str, str]] = set()
        required_qualifiers: set[tuple[str, str, str]] = set()
        for ref in component["source_component_refs"]:
            source = source_components[
                (ref["source_node_id"], ref["source_component_id"])
            ]
            required_operators.update(
                {
                    (
                        source_operator_kind.get(operator["kind"], operator["kind"]),
                        operator["token"].casefold(),
                        operator["scope"],
                    )
                    for operator in source["operator_ledger"]
                    if operator["disposition"] != "non_logical"
                }
            )
            required_qualifiers.update(
                {
                    (
                        qualifier["kind"],
                        qualifier["value"].casefold(),
                        qualifier["scope"],
                    )
                    for qualifier in source["qualifiers"]
                }
            )
        interface_operators = {
            (
                operator["kind"],
                operator["value"].casefold(),
                operator["scope"],
            )
            for operator in semantic["operators"]
        }
        interface_qualifiers = {
            (
                qualifier["kind"],
                qualifier["value"].casefold(),
                qualifier["scope"],
            )
            for qualifier in semantic["qualifiers"]
        }
        if not required_operators.issubset(interface_operators):
            raise ValueError(
                "research-draft Candidate semantic interface drops a source operator"
            )
        if not required_qualifiers.issubset(interface_qualifiers):
            raise ValueError(
                "research-draft Candidate semantic interface drops a source qualifier"
            )
    transport = derive_paper_transport_closure(store, paper_evidence_refs)
    matching_logic_refs = [
        ref
        for ref in paper_evidence_refs
        if ref["graph_kind"] == "logic"
        and ref["snapshot_id"] == plan["snapshot_id"]
    ]
    if (
        len(matching_logic_refs) != 1
        or set(matching_logic_refs[0]["target_node_ids"])
        != expected_load_bearing
    ):
        raise ValueError(
            "research-draft preflight lacks the exact planned Logic closure EvidenceRef"
        )
    validate_transport_artifacts(
        transport, artifacts, authorized_roles=authorized_artifact_roles
    )
    authorized_role_set = set(authorized_artifact_roles)
    sealed_writing_hashes = {
        artifact.get("sha256") or artifact.get("artifact_sha256")
        for artifact in artifacts
        if artifact.get("role") == "paper_revised_writing"
        and artifact.get("role") in authorized_role_set
    }
    required_writing_hashes = {
        entry["writing_coverage"]["artifact_sha256"]
        for entry in batch["entries"]
    }
    if not required_writing_hashes.issubset(sealed_writing_hashes):
        raise ValueError(
            "research-draft release does not seal and authorize every revised writing artifact"
        )
    dependencies: list[dict[str, Any]] = []
    for binding in research_bindings:
        dependencies.append(
            dependency(
                dependency_id=f"research:{binding['research_id']}",
                kind="research_record",
                relpath=None,
                semantic_sha256=binding["record_sha256"],
                file_sha256=None,
            )
        )
    dependencies.extend(
        [
            dependency(
                dependency_id=f"research-draft-plan:{plan['plan_id']}",
                kind="research_draft_plan",
                relpath=None,
                semantic_sha256=plan["record_sha256"],
                file_sha256=None,
            ),
            dependency(
                dependency_id=f"research-draft-batch:{batch['batch_id']}",
                kind="research_draft_batch",
                relpath=None,
                semantic_sha256=batch["record_sha256"],
                file_sha256=None,
            ),
            dependency(
                dependency_id=f"paper-transport:{transport['closure_sha256']}",
                kind="paper_evidence_transport_closure",
                relpath=None,
                semantic_sha256=transport["closure_sha256"],
                file_sha256=None,
            ),
        ]
    )
    for member in transport["members"]:
        dependencies.append(
            dependency(
                dependency_id=(
                    f"paper-member:{member['role']}:"
                    f"{','.join(member['snapshot_ids'])}:{member['artifact_sha256']}"
                ),
                kind=member["role"],
                relpath=member["source_relpath"],
                semantic_sha256=None,
                file_sha256=member["artifact_sha256"],
            )
        )
    for fact_id in sorted(candidate_facts):
        dependencies.extend(
            [
                dependency(
                    dependency_id=f"candidate-fact:{fact_id}",
                    kind="candidate_fact",
                    relpath=None,
                    semantic_sha256=sha256_json({"fact_id": fact_id}),
                    file_sha256=candidate_fact_file_sha256[fact_id],
                ),
                dependency(
                    dependency_id=f"candidate-interface:{fact_id}",
                    kind="candidate_interface",
                    relpath=None,
                    semantic_sha256=sha256_json(interface_by_fact[fact_id]),
                    file_sha256=None,
                ),
            ]
        )
    for fact_id in sorted(external_predecessor_ids):
        predecessor_path = store.active_fact_path(fact_id)
        dependencies.append(
            dependency(
                dependency_id=f"active-predecessor:{fact_id}",
                kind="active_fact_lineage",
                relpath=predecessor_path.relative_to(store.root).as_posix(),
                semantic_sha256=sha256_json({"fact_id": fact_id}),
                file_sha256=active_fact_file_sha256(fact_id),
            )
        )
    for artifact in artifacts:
        digest = artifact.get("sha256") or artifact.get("artifact_sha256")
        role = artifact.get("role")
        sealed_relpath = artifact.get("path") or artifact.get("sealed_relpath")
        dependencies.append(
            dependency(
                dependency_id=f"release-artifact:{role}:{digest}",
                kind="candidate_artifact",
                relpath=sealed_relpath,
                semantic_sha256=sha256_json({"role": role, "sha256": digest}),
                file_sha256=digest,
            )
        )
    continuity_checks = (
        {"stance_preservation": "pass"}
        if not current_plan or profile == "philosophy"
        else {"mathematical_target_and_refinement_continuity": "pass"}
        if profile == "mathematics"
        else {"domain_target_continuity": "pass"}
    )
    preflight_semantic = {
        "schema_version": 1,
        "contract_revision": PREFLIGHT_REVISION,
        "project_id": store.project_id(),
        "plan_id": plan["plan_id"],
        "batch_id": batch["batch_id"],
        "paper_id": plan["paper_id"],
        "target_node_ids": plan["target_node_ids"],
        "load_bearing_node_ids": sorted(expected_load_bearing),
        "candidate_fact_ids": sorted(candidate_facts),
        "internal_edges": sorted(internal_edges),
        "external_predecessor_ids": sorted(external_predecessor_ids),
        "component_ids": sorted(component_ids),
        "paper_transport_closure_sha256": transport["closure_sha256"],
        "checks": {
            "source_role_research_draft": "pass",
            "paper_target_and_closure_exact": "pass",
            "source_proposition_totality": "pass",
            "node_disposition_fact_mapping_separated": "pass",
            "semantic_component_atomicity": "pass",
            "qualified_failure_surfaces": "pass",
            **continuity_checks,
            "language_neutral_interfaces": "pass",
            "paper_evidence_transport_closure": "pass",
            "revised_writing_transport_closure": "pass",
            "revoked_authority_exclusion": "pass",
        },
        "structural_status": "PASS",
        "review_status": "pending_fresh_semantic_verification",
        "gateway_status": "not_admitted",
        "truth_effect": "none",
    }
    preflight_id = "rdpf-" + sha256_json(preflight_semantic)
    preflight = {
        **preflight_semantic,
        "preflight_id": preflight_id,
        "preflight_sha256": preflight_id.removeprefix("rdpf-"),
    }
    receipt = build_dependency_receipt(
        dependencies,
        validation_subject_sha256=preflight["preflight_sha256"],
    )
    return {
        "preflight": preflight,
        "validated_dependency_receipt": receipt,
        "paper_transport_closure": transport,
        "normalized_assurance": normalized_assurance,
    }
