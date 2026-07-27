from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adoption import feature_required, uses_legacy_estimate_policy
from .applicability import validate_external_refs_for_submission
from .blackboard import BlackboardStore
from .contracts import (
    CLAIM_RELATIONS,
    SHA256_RE,
    contained_path,
    require_exact_keys,
    require_relative_path,
    require_string,
    sha256_bytes,
    sha256_json,
)
from .elementary import validate_elementary_uses_for_submission
from .computations import (
    ExperimentManager,
    validate_computational_evidence,
    validate_required_experiment_receipt,
)
from .fact_bundles import (
    FactBundleStore,
    validate_domain_certificate_statement,
    validate_interpret_mechanism,
    validate_terminology,
)
from .interfaces import (
    build_statement_interface,
    extract_statement_clauses,
    validate_predecessor_uses,
    validate_quantifier_ledger,
)
from .model import Fact
from .protocol import validate_task_card, validate_worker_return_v4


COMMON_RETURN_FIELDS = {
    "project_id",
    "round_id",
    "assignment_id",
    "assignment_sha256",
    "worker",
    "memory_id",
    "mode",
    "outcome",
    "notes",
}

OUTCOMES = {"fact_submission", "counterexample", "evidence", "dead_end"}
MAX_ARTIFACT_FILES = 256
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_TOTAL_BYTES = 64 * 1024 * 1024


def _validate_common_return(
    payload: dict[str, Any],
    assignment: dict[str, Any],
    manifest: dict[str, Any],
) -> str:
    for key, expected in (
        ("project_id", manifest["project_id"]),
        ("round_id", manifest["round_id"]),
        ("assignment_id", assignment["assignment_id"]),
        ("assignment_sha256", assignment["assignment_sha256"]),
        ("worker", assignment["worker_id"]),
        ("memory_id", assignment["memory_id"]),
        ("mode", assignment["mode"]),
    ):
        value = require_string(payload, key)
        if value != expected:
            raise ValueError(f"worker return {key} mismatch")
    outcome = require_string(payload, "outcome")
    if outcome not in OUTCOMES:
        raise ValueError(f"unsupported worker outcome: {outcome}")
    require_string(payload, "notes", allow_empty=True)
    return outcome


def _validate_v3_artifacts(
    payload: dict[str, Any],
    assignment: dict[str, Any],
    *,
    project_root: Path | None,
) -> list[dict[str, str]]:
    artifacts = payload.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("artifacts must be a list of {path, sha256} objects")
    if len(artifacts) > MAX_ARTIFACT_FILES:
        raise ValueError(
            f"artifact count exceeds the {MAX_ARTIFACT_FILES}-file assignment limit"
        )
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    total_bytes = 0
    artifact_dir_value = require_string(assignment, "artifact_dir_relpath")
    artifact_dir_rel = require_relative_path(
        artifact_dir_value, "assignment artifact_dir_relpath"
    )
    for index, item in enumerate(artifacts, 1):
        label = f"artifacts[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} must be an object")
        require_exact_keys(item, required={"path", "sha256"}, label=label)
        relative = require_string(item, "path")
        rel = require_relative_path(relative, f"{label}.path")
        digest = require_string(item, "sha256")
        if SHA256_RE.fullmatch(digest) is None:
            raise ValueError(f"{label}.sha256 must be 64 lowercase hex characters")
        if rel.as_posix() in seen:
            raise ValueError(f"duplicate artifact path: {rel.as_posix()}")
        seen.add(rel.as_posix())
        if rel == artifact_dir_rel or not rel.is_relative_to(artifact_dir_rel):
            raise ValueError(
                f"{label}.path must be below designated artifact directory "
                f"{artifact_dir_rel.as_posix()}"
            )
        if project_root is not None:
            path = contained_path(project_root, rel.as_posix(), f"{label}.path")
            artifact_dir = contained_path(
                project_root,
                artifact_dir_rel.as_posix(),
                "assignment artifact_dir_relpath",
            )
            if path.parent != artifact_dir and artifact_dir not in path.parents:
                raise ValueError(f"{label}.path escapes the designated artifact directory")
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"{label}.path is missing or not a regular file")
            artifact_bytes = path.stat().st_size
            if artifact_bytes > MAX_ARTIFACT_BYTES:
                raise ValueError(
                    f"{label}.path exceeds the {MAX_ARTIFACT_BYTES}-byte per-file limit"
                )
            total_bytes += artifact_bytes
            if total_bytes > MAX_ARTIFACT_TOTAL_BYTES:
                raise ValueError(
                    "declared artifacts exceed the "
                    f"{MAX_ARTIFACT_TOTAL_BYTES}-byte assignment limit"
                )
            if sha256_bytes(path.read_bytes()) != digest:
                raise ValueError(f"{label}.sha256 does not match artifact bytes")
        normalized.append({"path": rel.as_posix(), "sha256": digest})
    if project_root is not None:
        artifact_dir = contained_path(
            project_root,
            artifact_dir_rel.as_posix(),
            "assignment artifact_dir_relpath",
        )
        if not artifact_dir.is_dir() or artifact_dir.is_symlink():
            raise ValueError("designated artifact directory is missing or not regular")
        declared = {
            contained_path(project_root, item["path"], "artifact path")
            for item in normalized
        }
        actual = {
            path
            for path in artifact_dir.rglob("*")
            if path.is_file() or path.is_symlink()
        }
        if len(actual) > MAX_ARTIFACT_FILES:
            raise ValueError(
                f"artifact directory exceeds the {MAX_ARTIFACT_FILES}-file assignment limit"
            )
        if any(path.is_symlink() for path in actual):
            raise ValueError("artifact directory contains a symlink")
        unexpected = actual.difference(declared)
        if unexpected:
            raise ValueError(
                "undeclared artifact files: "
                + ", ".join(
                    sorted(
                        path.relative_to(artifact_dir).as_posix()
                        for path in unexpected
                    )
                )
            )
        if declared.difference(actual):
            raise ValueError("declared artifact file is missing")
    return normalized


def fact_bundle_payload_from_return(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Project a bound return onto the ordinary bundle submission schema."""

    return {
        "schema_version": payload["schema_version"],
        "policy_revision": payload["policy_revision"],
        "project_id": payload["project_id"],
        "facts": [dict(item) for item in payload["facts"]],
        "bundle_claim": payload["bundle_claim"],
    }


def _validate_interpret_return(
    payload: dict[str, Any],
    *,
    task_card: dict[str, Any],
    outcome: str,
    project_root: Path,
) -> None:
    if task_card["mode"] != "interpret":
        return
    mechanisms = [
        node
        for node in payload["blackboard_graph_delta"]["add_nodes"]
        if node.get("node_type") == "mechanism"
    ]
    if outcome != "dead_end" and not mechanisms:
        raise ValueError(
            "non-dead-end interpret return requires a mechanism node"
        )
    snapshot_nodes, snapshot_edges = BlackboardStore(
        project_root
    ).snapshot_objects(task_card["blackboard_view"]["snapshot_id"])
    authorized_refs = set(snapshot_nodes).union(snapshot_edges)
    required_conventions = set(task_card["convention_profile_ids"])
    source_claim_id = task_card.get("source_claim_id")
    for node in mechanisms:
        mechanism = node.get("payload")
        if not isinstance(mechanism, dict):
            raise ValueError("interpret mechanism node payload must be an object")
        validate_interpret_mechanism(mechanism)
        explains_refs = set(mechanism["explains_refs"])
        if not explains_refs or not explains_refs.issubset(authorized_refs):
            raise ValueError(
                "interpret mechanism explains_refs must name objects in "
                "the frozen blackboard snapshot"
            )
        mechanism_conventions = set(
            mechanism["convention_profile_ids"]
        )
        node_conventions = set(node["convention_profile_ids"])
        if (
            mechanism_conventions != required_conventions
            or node_conventions != required_conventions
        ):
            raise ValueError(
                "interpret mechanism convention profiles must exactly "
                "match the task card"
            )
        if (
            source_claim_id is not None
            and source_claim_id not in node["source_refs"]
        ):
            raise ValueError(
                "interpret mechanism must bind the task source_claim_id "
                "in node source_refs"
            )


def _validate_v4_fact_semantics(
    fact: Fact,
    *,
    artifacts: list[dict[str, str]],
    task_card: dict[str, Any],
    interface_lookup: Any,
) -> None:
    refs = fact.external_refs
    validate_external_refs_for_submission(
        refs,
        fact.proof,
        require_formula_fidelity=True,
        require_critical_audit=True,
    )
    validate_elementary_uses_for_submission(
        fact.elementary_uses,
        fact.proof,
    )
    clauses = extract_statement_clauses(
        fact.statement,
        require_v4=True,
    )
    if "[CLAIM:DOMAIN-" in fact.statement:
        validate_domain_certificate_statement(fact.statement)
    validate_quantifier_ledger(
        fact.quantifier_ledger,
        statement=fact.statement,
        proof=fact.proof,
        clause_ids={item["clause_id"] for item in clauses},
    )
    if (
        feature_required(
            task_card["adoption_plan"],
            "quantifier_gate",
            allow_legacy_estimate_policy=True,
        )
        and not fact.quantifier_ledger
    ):
        raise ValueError(
            "quantifier_gate requires a nonempty fact quantifier_ledger"
        )
    validate_predecessor_uses(
        fact.predecessor_uses,
        predecessors=fact.predecessors,
        proof=fact.proof,
        interface_lookup=interface_lookup,
        convention_profile_ids=fact.convention_profile_ids,
    )
    validate_computational_evidence(
        fact.computational_evidence,
        proof=fact.proof,
        artifacts=artifacts,
        verification_plan=task_card["verification_plan"],
    )
    validate_terminology(
        fact.terminology,
        proof=fact.proof,
    )
    validate_formula_artifact_bindings(
        fact.as_submission_dict(),
        artifacts,
    )


def _validate_v4_fact_bundle(
    payload: dict[str, Any],
    *,
    assignment: dict[str, Any],
    task_card: dict[str, Any],
    project_root: Path,
    artifacts: list[dict[str, str]],
    interface_lookup: Any,
) -> None:
    bundle_payload = fact_bundle_payload_from_return(payload)

    def external_fact_exists(fact_id: str) -> bool:
        if interface_lookup is None:
            return False
        try:
            interface_lookup(fact_id)
        except (KeyError, ValueError, FileNotFoundError):
            return False
        return True

    FactBundleStore(project_root).validate_submission(
        bundle_payload,
        worker=assignment["worker_id"],
        external_fact_exists=external_fact_exists,
    )
    facts = {
        fact.fact_id: fact
        for fact in (
            Fact.from_dict(item) for item in bundle_payload["facts"]
        )
    }
    # These interfaces exist only to validate clause-level uses inside the
    # candidate mini-DAG. They are never persisted or exposed as admitted
    # predecessor interfaces.
    internal_interfaces = {
        fact_id: build_statement_interface(
            fact=fact,
            stored_fact_sha256=sha256_json(fact.as_submission_dict()),
            acceptance_event_sha256=sha256_json(
                ["pending-bundle-candidate", fact_id, "acceptance"]
            ),
            admission_review_id=sha256_json(
                ["pending-bundle-candidate", fact_id, "review"]
            ),
            workflow_evidence_version=4,
        )
        for fact_id, fact in facts.items()
    }

    def bundle_interface_lookup(fact_id: str) -> dict[str, Any]:
        if fact_id in internal_interfaces:
            return internal_interfaces[fact_id]
        if interface_lookup is None:
            raise KeyError(fact_id)
        return interface_lookup(fact_id)

    for fact in facts.values():
        _validate_v4_fact_semantics(
            fact,
            artifacts=artifacts,
            task_card=task_card,
            interface_lookup=bundle_interface_lookup,
        )


def validate_worker_return(
    payload: dict[str, Any],
    assignment: dict[str, Any],
    manifest: dict[str, Any],
    *,
    project_root: Path | None = None,
    historical_policy: bool = False,
    interface_lookup: Any = None,
) -> tuple[str, list[dict[str, str]]]:
    """Validate the exact schema used by both dry-run validation and ingestion."""

    schema_version = manifest.get("schema_version")
    if schema_version not in {2, 3, 4}:
        raise ValueError(f"unsupported round schema_version: {schema_version!r}")
    if schema_version == 4:
        if project_root is None:
            raise ValueError("v4 worker return validation requires project_root")
        task_card_relpath = require_string(assignment, "task_card_relpath")
        task_card_path = contained_path(
            project_root,
            task_card_relpath,
            "assignment task_card_relpath",
        )
        if not task_card_path.is_file() or task_card_path.is_symlink():
            raise ValueError("v4 task card is missing or not a regular file")
        task_card = json.loads(task_card_path.read_text(encoding="utf-8"))
        if not isinstance(task_card, dict):
            raise ValueError("v4 task card must be one JSON object")
        ExperimentManager(project_root)._validate_bound_task_card(
            task_card,
            allow_historical_estimate_policy=historical_policy,
        )
        historical_estimate_policy = uses_legacy_estimate_policy(
            task_card["adoption_plan"]
        )
        task_card_sha = sha256_bytes(task_card_path.read_bytes())
        if task_card_sha != assignment.get("task_card_sha256"):
            raise ValueError("v4 task card hash mismatch")
        if payload.get("task_card_sha256") != task_card_sha:
            raise ValueError("v4 worker return task card hash mismatch")
        outcome = validate_worker_return_v4(
            payload,
            task_card=task_card,
            allow_legacy_adoption=True,
        )
        artifacts = _validate_v3_artifacts(
            payload,
            assignment,
            project_root=project_root,
        )
        if not historical_estimate_policy:
            validate_required_experiment_receipt(
                project_root=project_root,
                task_card=task_card,
                artifacts=artifacts,
            )
        _validate_interpret_return(
            payload,
            task_card=task_card,
            outcome=outcome,
            project_root=project_root,
        )
        if outcome == "fact_submission":
            refs = payload.get("external_refs", [])
            validate_external_refs_for_submission(
                refs,
                payload["proof"],
                require_formula_fidelity=True,
                require_critical_audit=True,
            )
            validate_elementary_uses_for_submission(
                payload.get("elementary_uses", []),
                payload["proof"],
            )
            clauses = extract_statement_clauses(
                payload["statement"],
                require_v4=True,
            )
            if "[CLAIM:DOMAIN-" in payload["statement"]:
                validate_domain_certificate_statement(
                    payload["statement"]
                )
            validate_quantifier_ledger(
                payload["quantifier_ledger"],
                statement=payload["statement"],
                proof=payload["proof"],
                clause_ids={item["clause_id"] for item in clauses},
            )
            if (
                feature_required(
                    task_card["adoption_plan"],
                    "quantifier_gate",
                    allow_legacy_estimate_policy=True,
                )
                and not payload["quantifier_ledger"]
            ):
                raise ValueError(
                    "quantifier_gate requires a nonempty fact "
                    "quantifier_ledger"
                )
            if interface_lookup is not None:
                validate_predecessor_uses(
                    payload["predecessor_uses"],
                    predecessors=payload["predecessors"],
                    proof=payload["proof"],
                    interface_lookup=interface_lookup,
                    convention_profile_ids=payload[
                        "convention_profile_ids"
                    ],
                )
            validate_computational_evidence(
                payload["computational_evidence"],
                proof=payload["proof"],
                artifacts=artifacts,
                verification_plan=task_card["verification_plan"],
            )
            validate_terminology(
                payload["terminology"],
                proof=payload["proof"],
            )
            validate_formula_artifact_bindings(payload, artifacts)
        elif outcome == "fact_bundle_submission":
            _validate_v4_fact_bundle(
                payload,
                assignment=assignment,
                task_card=task_card,
                project_root=project_root,
                artifacts=artifacts,
                interface_lookup=interface_lookup,
            )
        return outcome, artifacts
    common = set(COMMON_RETURN_FIELDS)
    outcome = _validate_common_return(payload, assignment, manifest)
    artifact_optional = {"artifacts"} if schema_version >= 3 else set()

    if outcome == "fact_submission":
        required = common | {"statement", "proof", "predecessors"}
        optional = {"glossary_introduces", "external_refs", "intuition"} | artifact_optional
        if schema_version >= 3:
            required.add("claim_relation")
            optional.add("elementary_uses")
        require_exact_keys(
            payload,
            required=required,
            optional=optional,
            label="fact submission return",
        )
        require_string(payload, "statement")
        require_string(payload, "proof")
        predecessors = payload.get("predecessors")
        if not isinstance(predecessors, list) or any(
            not isinstance(item, str) for item in predecessors
        ):
            raise ValueError("predecessors must be a list of strings")
        glossary = payload.get("glossary_introduces", {})
        if not isinstance(glossary, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in glossary.items()
        ):
            raise ValueError("glossary_introduces must map strings to strings")
        refs = payload.get("external_refs", [])
        if not isinstance(refs, list) or any(not isinstance(item, dict) for item in refs):
            raise ValueError("external_refs must be a list of objects")
        if schema_version >= 3:
            validate_external_refs_for_submission(
                refs,
                payload["proof"],
                require_formula_fidelity=not historical_policy,
                require_critical_audit=not historical_policy,
            )
            validate_elementary_uses_for_submission(
                payload.get("elementary_uses", []),
                payload["proof"],
            )
        if not isinstance(payload.get("intuition", ""), str):
            raise ValueError("intuition must be a string")
        if schema_version >= 3:
            relation = require_string(payload, "claim_relation")
            if relation not in CLAIM_RELATIONS:
                raise ValueError(
                    "claim_relation must be one of: "
                    + ", ".join(sorted(CLAIM_RELATIONS))
                )
    elif outcome == "counterexample":
        require_exact_keys(
            payload,
            required=common | {"claim", "construction", "verification"},
            optional=artifact_optional,
            label="counterexample return",
        )
        for key in ("claim", "construction", "verification"):
            require_string(payload, key)
    elif outcome == "evidence":
        require_exact_keys(
            payload,
            required=common
            | {"claim", "method", "result", "artifacts", "limitations"},
            label="evidence return",
        )
        require_string(payload, "claim")
        require_string(payload, "method")
        if payload.get("result") is None:
            raise ValueError("result must not be null")
        limitations = payload.get("limitations")
        if not isinstance(limitations, str) and (
            not isinstance(limitations, list)
            or any(not isinstance(item, str) for item in limitations)
        ):
            raise ValueError("limitations must be a string or list of strings")
        if schema_version == 2 and (
            not isinstance(payload.get("artifacts"), list)
            or any(not isinstance(item, str) for item in payload["artifacts"])
        ):
            raise ValueError("artifacts must be a list of strings")
    else:
        require_exact_keys(
            payload,
            required=common | {"claim", "method", "failure_mode", "what_remains_open"},
            optional=artifact_optional,
            label="dead-end return",
        )
        for key in ("claim", "method", "failure_mode", "what_remains_open"):
            require_string(payload, key)

    artifacts = (
        _validate_v3_artifacts(payload, assignment, project_root=project_root)
        if schema_version >= 3
        else []
    )
    return outcome, artifacts


def validate_formula_artifact_bindings(
    payload: dict[str, Any],
    artifacts: list[dict[str, str]],
) -> None:
    """Bind every formula fidelity hash to a validated assignment artifact.

    Call this for active schema-v3 validate/ingest operations. Historical round
    audit deliberately uses only ``validate_worker_return`` so evidence created
    before this policy remains readable rather than being retroactively failed.
    """

    declared_hashes = {item["sha256"] for item in artifacts}
    for ref in payload.get("external_refs", []):
        if ref.get("use_kind") != "formula":
            continue
        fidelity = ref["source_fidelity"]
        required_hash = fidelity["artifact_sha256"]
        if required_hash not in declared_hashes:
            raise ValueError(
                "formula source_fidelity artifact_sha256 for "
                f"{ref['key']} is not bound to a declared assignment artifact"
            )
