from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable

from .adoption import feature_required, validate_adoption_binding
from .contracts import (
    FACT_BUNDLE_ID_RE,
    FACT_ID_RE,
    POLICY_REVISION_V4,
    SHA256_RE,
    contained_path,
    require_exact_keys,
    require_relative_path,
    require_string,
    sha256_bytes,
    sha256_json,
    validate_assignment_id,
    validate_bb_node_id,
    validate_fact_bundle_id,
    validate_fact_id,
    validate_round_id,
)
from .interfaces import (
    extract_statement_clauses,
    lint_quantifier_export,
    statement_only_packet_section,
    validate_quantifier_ledger,
    validate_statement_interface,
)
from .markdown import parse_fact_markdown, serialize_fact, validate_fact_round_trip
from .model import Fact


DOMAIN_CLAUSES = {
    "DOMAIN-BASE",
    "DOMAIN-POLES",
    "DOMAIN-ZEROS",
    "DOMAIN-RAMIFICATION",
    "DOMAIN-DISJOINTNESS",
    "DOMAIN-VITAL-POINTS",
    "DOMAIN-PARTNER-REGULARITY",
    "DOMAIN-SELFDUALITY",
    "DOMAIN-EXCLUSIONS",
}
TERMINOLOGY_ORIGINS = {
    "source",
    "standard",
    "local_shorthand",
    "legacy_unknown",
}
EXPORT_POLICIES = {"keep", "define", "replace", "forbid"}
EXPERT_AUDIENCES = {"expert", "advisor", "publication"}
LEGACY_ASSURANCE_LIMITATION = (
    "Admission assurance is inherited from workflow-evidence v3; "
    "this V4 export does not relabel the fact as V4-reviewed."
)
AI_DISCLOSURE_PLACEHOLDER = (
    "AI assistance: [complete disclosure before external release]"
)
CLAIM_CARD_FIELDS = {
    "schema_version",
    "policy_revision",
    "fact_id",
    "audience",
    "literal_source_claim",
    "researcher_variant",
    "variant_diff",
    "source_locator",
    "convention_profile",
    "admitted_conclusion",
    "admission_evidence_version",
    "assurance_label",
    "quantifier_ledger",
    "computation_independence_matrix",
    "limitations",
    "reproduction_bundle",
    "terminology",
    "AI-assistance disclosure",
    "claim_card_sha256",
}
EXPERT_LINT_RECEIPT_FIELDS = {
    "schema_version",
    "policy_revision",
    "linter_revision",
    "project_id",
    "receipt_relpath",
    "draft_sha256",
    "claim_card_bytes_sha256",
    "claim_card_sha256",
    "fact_id",
    "audience",
    "ok",
    "errors",
    "scope",
    "truth_effect",
    "lint_receipt_sha256",
}
EXPERT_LINTER_REVISION = "expert-communication-lint-v1"
EXPERT_LINT_SCOPE = (
    "terminology, claim identity, convention, quantifier ledger, "
    "limitations, source locator, and AI disclosure only; "
    "not mathematical correctness"
)
INTERPRET_CARD_KIND = "exploration_interpretation"
INTERPRET_TRUTH_BOUNDARY = (
    "candidate interpretation / not an admitted theorem"
)
INTERPRET_CARD_FIELDS = {
    "schema_version",
    "policy_revision",
    "card_kind",
    "project_id",
    "node_id",
    "node_content_sha256",
    "audience",
    "source_refs",
    "explains_refs",
    "domain_clause_refs",
    "convention_profile_ids",
    "mechanism_statement",
    "falsifiable_consequences",
    "known_failures",
    "remaining_gaps",
    "terminology",
    "truth_boundary",
    "AI-assistance disclosure",
    "interpret_card_sha256",
}
INTERPRET_LINT_RECEIPT_KIND = "interpretation_communication_lint"
INTERPRET_LINTER_REVISION = "interpretation-communication-lint-v1"
INTERPRET_COMMUNICATION_READINESS_REVISION = (
    "chalxius-interpret-communication-readiness-1"
)
INTERPRET_COMMUNICATION_PUBLICATION_REVISION = (
    "chalxius-interpret-communication-publication-1"
)
_INHERITED_CHALK_FIXTURE_AUTHORITY = object()
INTERPRET_LINT_SCOPE = (
    "mechanism identity, exact source/domain/convention references, "
    "falsifiable consequences, known failures, remaining gaps, "
    "terminology, exploration truth boundary, and AI disclosure only; "
    "not promotion, admission, or mathematical correctness"
)
INTERPRET_LINT_RECEIPT_FIELDS = {
    "schema_version",
    "policy_revision",
    "receipt_kind",
    "linter_revision",
    "project_id",
    "receipt_relpath",
    "interpret_card_relpath",
    "draft_sha256",
    "interpret_card_bytes_sha256",
    "interpret_card_sha256",
    "node_id",
    "node_content_sha256",
    "audience",
    "ok",
    "errors",
    "scope",
    "truth_effect",
    "lint_receipt_sha256",
}


def validate_domain_certificate_statement(statement: str) -> None:
    clauses = extract_statement_clauses(statement, require_v4=True)
    clause_ids = {item["clause_id"] for item in clauses}
    missing = DOMAIN_CLAUSES.difference(clause_ids)
    if missing:
        raise ValueError(
            "domain certificate is missing clauses: " + ", ".join(sorted(missing))
        )


def _validate_terminology_entries(
    entries: Any,
    *,
    proof: str | None,
) -> list[dict[str, Any]]:
    if not isinstance(entries, list) or any(not isinstance(item, dict) for item in entries):
        raise ValueError("terminology must be a list of objects")
    keys: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, 1):
        require_exact_keys(
            entry,
            required={
                "key",
                "term",
                "definition",
                "origin",
                "source_locator",
                "export_policy",
                "replacement",
                "proof_anchor",
            },
            label=f"terminology[{index}]",
        )
        key = require_string(entry, "key")
        if key in keys:
            raise ValueError("terminology keys must be unique")
        keys.add(key)
        require_string(entry, "term")
        require_string(entry, "definition")
        if require_string(entry, "origin") not in TERMINOLOGY_ORIGINS:
            raise ValueError("terminology origin is invalid")
        require_string(entry, "source_locator", allow_empty=True)
        policy = require_string(entry, "export_policy")
        if policy not in EXPORT_POLICIES:
            raise ValueError("terminology export_policy is invalid")
        replacement = require_string(
            entry,
            "replacement",
            allow_empty=(policy != "replace"),
        )
        if policy == "replace" and not replacement.strip():
            raise ValueError("replace terminology requires replacement text")
        anchor = require_string(entry, "proof_anchor")
        expected = f"[TERM:{key}]"
        if anchor != expected:
            raise ValueError(
                f"terminology proof anchor must be {expected}"
            )
        if proof is not None and proof.count(anchor) != 1:
            raise ValueError(
                f"terminology proof anchor {expected} must occur exactly once"
            )
        normalized.append(dict(entry))
    return normalized


def validate_terminology(
    entries: Any,
    *,
    proof: str,
) -> list[dict[str, Any]]:
    return _validate_terminology_entries(entries, proof=proof)


def _visible_text(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def _lint_terminology(
    visible_text: str,
    terminology: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    normalized_text = unicodedata.normalize("NFKC", visible_text).casefold()
    for entry in terminology:
        term = entry["term"]
        normalized_term = unicodedata.normalize("NFKC", term).casefold()
        term_position = normalized_text.find(normalized_term)
        policy = entry["export_policy"]
        if entry.get("origin") == "legacy_unknown":
            errors.append(f"legacy term requires manual classification: {term}")
        if policy == "forbid" and term_position >= 0:
            errors.append(f"forbidden or unclassified term appears: {term}")
        if policy == "replace" and term_position >= 0:
            errors.append(f"local shorthand was not replaced: {term}")
        if policy == "define" and term_position >= 0:
            definition_marker = unicodedata.normalize(
                "NFKC", entry["definition"]
            ).casefold()
            definition_position = normalized_text.find(definition_marker)
            if definition_position < 0 or definition_position > term_position:
                errors.append(f"term appears before its definition: {term}")
    return errors


def _lint_ai_disclosure(
    visible_text: str,
    disclosure: Any,
    *,
    label: str,
) -> list[str]:
    errors: list[str] = []
    if disclosure == AI_DISCLOSURE_PLACEHOLDER:
        matches = re.findall(
            (
                r"(?im)^[ \t]*(?:[-*][ \t]+|#{1,6}[ \t]+)?"
                r"AI assistance[ \t]*:[ \t]*(.+?)[ \t]*$"
            ),
            visible_text,
        )
        incomplete = {
            "",
            "none",
            "n/a",
            "todo",
            "tbd",
            "[complete disclosure before external release]",
        }
        if not matches or all(
            value.strip().casefold() in incomplete
            or len(value.strip()) < 20
            for value in matches
        ):
            errors.append(f"{label} requires a completed AI-assistance disclosure")
        if AI_DISCLOSURE_PLACEHOLDER in visible_text:
            errors.append(f"{label} retains the AI-assistance placeholder")
    elif (
        isinstance(disclosure, str)
        and disclosure
        and disclosure not in visible_text
    ):
        errors.append(f"{label} omits AI-assistance disclosure")
    return errors


def lint_expert_document(
    text: str,
    *,
    claim_card: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    visible_text = _visible_text(text)
    terminology = claim_card.get("terminology", [])
    errors.extend(_lint_terminology(visible_text, terminology))
    for required in (
        "literal_source_claim",
        "researcher_variant",
        "source_locator",
        "convention_profile",
        "admitted_conclusion",
    ):
        marker = claim_card.get(required)
        if (
            isinstance(marker, str)
            and marker
            and marker not in visible_text
        ):
            errors.append(f"expert document omits claim-card field: {required}")
    errors.extend(
        _lint_ai_disclosure(
            visible_text,
            claim_card.get("AI-assistance disclosure"),
            label="expert document",
        )
    )
    for limitation in claim_card.get("limitations", []):
        if (
            isinstance(limitation, str)
            and limitation
            and limitation not in visible_text
        ):
            errors.append(f"expert document omits limitation: {limitation}")
    errors.extend(
        lint_quantifier_export(
            visible_text,
            claim_card.get("quantifier_ledger", []),
        )
    )
    return errors


def validate_claim_card(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("claim card must be one object")
    require_exact_keys(
        payload,
        required=CLAIM_CARD_FIELDS,
        label="expert claim card",
    )
    if payload.get("schema_version") != 1:
        raise ValueError("claim card schema_version must be 1")
    if payload.get("policy_revision") != POLICY_REVISION_V4:
        raise ValueError("claim card policy_revision mismatch")
    validate_fact_id(require_string(payload, "fact_id"))
    if require_string(payload, "audience") not in EXPERT_AUDIENCES:
        raise ValueError("claim card audience is invalid")
    admission_version = payload.get("admission_evidence_version")
    if (
        isinstance(admission_version, bool)
        or not isinstance(admission_version, int)
        or admission_version not in {3, 4}
    ):
        raise ValueError(
            "claim card admission_evidence_version must be 3 or 4"
        )
    assurance_label = require_string(payload, "assurance_label")
    expected_assurance = (
        "v4-independent-review"
        if admission_version == 4
        else "legacy-v3-inherited"
    )
    if assurance_label != expected_assurance:
        raise ValueError("claim card assurance label/version mismatch")
    for key in (
        "literal_source_claim",
        "researcher_variant",
        "source_locator",
        "convention_profile",
        "admitted_conclusion",
        "AI-assistance disclosure",
    ):
        require_string(payload, key)
    for key in (
        "variant_diff",
        "quantifier_ledger",
        "computation_independence_matrix",
        "reproduction_bundle",
        "terminology",
    ):
        value = payload.get(key)
        if not isinstance(value, list) or any(
            not isinstance(item, dict) for item in value
        ):
            raise ValueError(f"claim card {key} must be a list of objects")
    limitations = payload.get("limitations")
    if not isinstance(limitations, list) or any(
        not isinstance(item, str) for item in limitations
    ):
        raise ValueError("claim card limitations must be a list of strings")
    if (
        admission_version == 3
        and LEGACY_ASSURANCE_LIMITATION not in limitations
    ):
        raise ValueError(
            "legacy claim card omits its inherited-assurance limitation"
        )
    expected_hash = sha256_json(
        {
            key: value
            for key, value in payload.items()
            if key != "claim_card_sha256"
        }
    )
    if payload.get("claim_card_sha256") != expected_hash:
        raise ValueError("claim card hash mismatch")
    return payload


def _claim_card_from_bytes(claim_card_bytes: bytes) -> dict[str, Any]:
    if not isinstance(claim_card_bytes, bytes):
        raise ValueError("claim_card_bytes must be exact bytes")
    try:
        payload = json.loads(claim_card_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "claim-card bytes must contain one UTF-8 JSON object"
        ) from exc
    return validate_claim_card(payload)


def build_expert_lint_receipt(
    *,
    project_id: str,
    receipt_relpath: str,
    draft_bytes: bytes,
    claim_card_bytes: bytes,
) -> dict[str, Any]:
    """Build deterministic communication-only lint evidence."""

    project_id = require_string({"project_id": project_id}, "project_id")
    receipt_relpath = require_relative_path(
        receipt_relpath,
        "receipt_relpath",
    ).as_posix()
    if not receipt_relpath.startswith(
        "reports/expert-lint-receipts/"
    ):
        raise ValueError(
            "expert lint receipt must be stored below "
            "reports/expert-lint-receipts/"
        )
    if not isinstance(draft_bytes, bytes):
        raise ValueError("draft_bytes must be exact bytes")
    try:
        draft_text = draft_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("expert draft must be UTF-8") from exc
    claim_card = _claim_card_from_bytes(claim_card_bytes)
    errors = lint_expert_document(
        draft_text,
        claim_card=claim_card,
    )
    semantic = {
        "schema_version": 1,
        "policy_revision": POLICY_REVISION_V4,
        "linter_revision": EXPERT_LINTER_REVISION,
        "project_id": project_id,
        "receipt_relpath": receipt_relpath,
        "draft_sha256": sha256_bytes(draft_bytes),
        "claim_card_bytes_sha256": sha256_bytes(
            claim_card_bytes
        ),
        "claim_card_sha256": claim_card["claim_card_sha256"],
        "fact_id": claim_card["fact_id"],
        "audience": claim_card["audience"],
        "ok": not errors,
        "errors": errors,
        "scope": EXPERT_LINT_SCOPE,
        "truth_effect": "communication_readiness_only",
    }
    return {
        **semantic,
        "lint_receipt_sha256": sha256_json(semantic),
    }


def validate_expert_lint_receipt(
    receipt: Any,
    *,
    draft_bytes: bytes | None = None,
    claim_card_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Validate receipt structure and, when supplied, the exact source bytes."""

    if not isinstance(receipt, dict):
        raise ValueError("expert lint receipt must be one object")
    require_exact_keys(
        receipt,
        required=EXPERT_LINT_RECEIPT_FIELDS,
        label="expert lint receipt",
    )
    if receipt.get("schema_version") != 1:
        raise ValueError("expert lint receipt schema_version must be 1")
    if receipt.get("policy_revision") != POLICY_REVISION_V4:
        raise ValueError("expert lint receipt policy_revision mismatch")
    if receipt.get("linter_revision") != EXPERT_LINTER_REVISION:
        raise ValueError("expert lint receipt linter_revision mismatch")
    require_string(receipt, "project_id")
    receipt_relpath = require_relative_path(
        require_string(receipt, "receipt_relpath"),
        "receipt_relpath",
    ).as_posix()
    if not receipt_relpath.startswith(
        "reports/expert-lint-receipts/"
    ):
        raise ValueError(
            "expert lint receipt path must remain below "
            "reports/expert-lint-receipts/"
        )
    for key in (
        "draft_sha256",
        "claim_card_bytes_sha256",
        "claim_card_sha256",
        "lint_receipt_sha256",
    ):
        value = require_string(receipt, key)
        if SHA256_RE.fullmatch(value) is None:
            raise ValueError(f"expert lint receipt {key} is invalid")
    validate_fact_id(require_string(receipt, "fact_id"))
    if require_string(receipt, "audience") not in EXPERT_AUDIENCES:
        raise ValueError("expert lint receipt audience is invalid")
    if not isinstance(receipt.get("ok"), bool):
        raise ValueError("expert lint receipt ok must be boolean")
    errors = receipt.get("errors")
    if not isinstance(errors, list) or any(
        not isinstance(item, str) for item in errors
    ):
        raise ValueError(
            "expert lint receipt errors must be a string list"
        )
    if receipt["ok"] != (not errors):
        raise ValueError("expert lint receipt ok/errors mismatch")
    if receipt.get("scope") != EXPERT_LINT_SCOPE:
        raise ValueError("expert lint receipt scope mismatch")
    if receipt.get("truth_effect") != "communication_readiness_only":
        raise ValueError("expert lint receipt truth boundary mismatch")
    semantic = {
        key: value
        for key, value in receipt.items()
        if key != "lint_receipt_sha256"
    }
    if receipt["lint_receipt_sha256"] != sha256_json(semantic):
        raise ValueError("expert lint receipt hash mismatch")

    claim_card: dict[str, Any] | None = None
    if claim_card_bytes is not None:
        claim_card = _claim_card_from_bytes(claim_card_bytes)
        if (
            receipt["claim_card_bytes_sha256"]
            != sha256_bytes(claim_card_bytes)
            or receipt["claim_card_sha256"]
            != claim_card["claim_card_sha256"]
            or receipt["fact_id"] != claim_card["fact_id"]
            or receipt["audience"] != claim_card["audience"]
        ):
            raise ValueError(
                "expert lint receipt claim-card bytes mismatch"
            )
    if draft_bytes is not None:
        if receipt["draft_sha256"] != sha256_bytes(draft_bytes):
            raise ValueError("expert lint receipt draft bytes mismatch")
        if claim_card is None:
            raise ValueError(
                "claim_card_bytes are required to revalidate draft bytes"
            )
        try:
            draft_text = draft_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("expert draft must be UTF-8") from exc
        recomputed = lint_expert_document(
            draft_text,
            claim_card=claim_card,
        )
        if recomputed != errors:
            raise ValueError(
                "expert lint receipt no longer matches linter output"
            )
    return receipt


def validate_expert_communication_readiness(
    *,
    adoption_binding: dict[str, Any],
    lint_receipt: dict[str, Any] | None,
    draft_bytes: bytes,
    claim_card_bytes: bytes,
) -> dict[str, Any]:
    """Consume a lint receipt without changing mathematical truth status."""

    validate_adoption_binding(adoption_binding)
    required = feature_required(
        adoption_binding,
        "terminology_export_lint",
    )
    if lint_receipt is None:
        if required:
            raise ValueError(
                "terminology_export_lint is required; a valid receipt "
                "must precede external communication"
            )
        return {
            "ready": True,
            "requirement": "not_required",
            "truth_effect": "none",
        }
    receipt = validate_expert_lint_receipt(
        lint_receipt,
        draft_bytes=draft_bytes,
        claim_card_bytes=claim_card_bytes,
    )
    if not receipt["ok"]:
        raise ValueError(
            "expert communication lint failed: "
            + "; ".join(receipt["errors"])
        )
    return {
        "ready": True,
        "requirement": "satisfied" if required else "validated_optional",
        "lint_receipt_sha256": receipt["lint_receipt_sha256"],
        "truth_effect": "none",
    }


def build_claim_card(
    *,
    fact: Fact,
    audience: str,
    literal_source_claim: str,
    researcher_variant: str,
    variant_diff: list[dict[str, Any]],
    source_locator: str,
    convention_profile: str,
    reproduction_bundle: list[dict[str, Any]],
    admission_evidence_version: int = 4,
    assurance_label: str = "v4-independent-review",
) -> dict[str, Any]:
    if audience not in EXPERT_AUDIENCES:
        raise ValueError("claim card audience must be expert, advisor, or publication")
    matrices = [
        {
            "key": entry["key"],
            "role": entry["role"],
            "independence_matrix": entry["independence_matrix"],
        }
        for entry in fact.computational_evidence
    ]
    limitations = sorted(
        {
            str(limitation)
            for entry in fact.computational_evidence
            for limitation in entry.get("truncation_certificate", {}).get(
                "limitations", []
            )
            if isinstance(limitation, str) and limitation
        }
    )
    if admission_evidence_version == 3:
        limitations = sorted(
            set(limitations).union({LEGACY_ASSURANCE_LIMITATION})
        )
    semantic = {
        "schema_version": 1,
        "policy_revision": POLICY_REVISION_V4,
        "fact_id": fact.fact_id,
        "audience": audience,
        "literal_source_claim": literal_source_claim,
        "researcher_variant": researcher_variant,
        "variant_diff": [dict(item) for item in variant_diff],
        "source_locator": source_locator,
        "convention_profile": convention_profile,
        "admitted_conclusion": fact.statement,
        "admission_evidence_version": admission_evidence_version,
        "assurance_label": assurance_label,
        "quantifier_ledger": [
            dict(item) for item in fact.quantifier_ledger
        ],
        "computation_independence_matrix": matrices,
        "limitations": limitations,
        "reproduction_bundle": [
            dict(item) for item in reproduction_bundle
        ],
        "terminology": [dict(item) for item in fact.terminology],
        "AI-assistance disclosure": (
            AI_DISCLOSURE_PLACEHOLDER
        ),
    }
    return validate_claim_card(
        {**semantic, "claim_card_sha256": sha256_json(semantic)}
    )


def validate_interpret_mechanism(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("interpret mechanism must be one object")
    require_exact_keys(
        payload,
        required={
            "explains_refs",
            "domain_clause_refs",
            "convention_profile_ids",
            "mechanism_statement",
            "falsifiable_consequences",
            "known_failures",
            "remaining_gaps",
            "truth_status",
        },
        optional={"terminology"},
        label="interpret mechanism",
    )
    for key in (
        "explains_refs",
        "domain_clause_refs",
        "convention_profile_ids",
        "known_failures",
        "remaining_gaps",
    ):
        if not isinstance(payload.get(key), list) or any(
            not isinstance(item, str) for item in payload[key]
        ):
            raise ValueError(f"interpret mechanism {key} must be a list of strings")
    require_string(payload, "mechanism_statement")
    consequences = payload.get("falsifiable_consequences")
    if not isinstance(consequences, list) or any(
        not isinstance(item, dict) for item in consequences
    ):
        raise ValueError("falsifiable_consequences must be a list of objects")
    if not consequences:
        raise ValueError(
            "interpret mechanism requires a falsifiable consequence or a dead_end outcome"
        )
    for index, consequence in enumerate(consequences, 1):
        require_exact_keys(
            consequence,
            required={"id", "statement", "suggested_mode"},
            label=f"falsifiable_consequences[{index}]",
        )
        require_string(consequence, "id")
        require_string(consequence, "statement")
        if require_string(consequence, "suggested_mode") not in {
            "prove",
            "refute",
            "compute",
            "literature",
            "interpret",
        }:
            raise ValueError("falsifiable consequence suggested_mode is invalid")
    if payload.get("truth_status") != "exploration":
        raise ValueError("interpret mechanism must remain exploration")
    _validate_terminology_entries(
        payload.get("terminology", []),
        proof=None,
    )
    return payload


def build_interpret_card(
    *,
    project_id: str,
    node: dict[str, Any],
    audience: str,
) -> dict[str, Any]:
    """Build a nontruth communication card from one immutable mechanism node."""

    project_id = require_string({"project_id": project_id}, "project_id")
    if audience not in EXPERT_AUDIENCES:
        raise ValueError(
            "interpret card audience must be expert, advisor, or publication"
        )
    if not isinstance(node, dict):
        raise ValueError("interpret card source node must be one object")
    node_id = validate_bb_node_id(require_string(node, "node_id"))
    if node.get("node_type") != "mechanism":
        raise ValueError("interpret card requires a mechanism node")
    if node.get("truth_status") != "exploration":
        raise ValueError("interpret card requires an exploration node")
    payload = validate_interpret_mechanism(node.get("payload"))
    source_refs = node.get("source_refs")
    if not isinstance(source_refs, list) or any(
        not isinstance(item, str) for item in source_refs
    ):
        raise ValueError("interpret card node source_refs must be strings")
    node_conventions = node.get("convention_profile_ids")
    if not isinstance(node_conventions, list) or any(
        not isinstance(item, str) for item in node_conventions
    ):
        raise ValueError(
            "interpret card node convention_profile_ids must be strings"
        )
    if node_conventions != payload["convention_profile_ids"]:
        raise ValueError(
            "interpret mechanism convention refs differ from the node binding"
        )
    semantic = {
        "schema_version": 1,
        "policy_revision": POLICY_REVISION_V4,
        "card_kind": INTERPRET_CARD_KIND,
        "project_id": project_id,
        "node_id": node_id,
        "node_content_sha256": sha256_json(node),
        "audience": audience,
        "source_refs": list(source_refs),
        "explains_refs": list(payload["explains_refs"]),
        "domain_clause_refs": list(payload["domain_clause_refs"]),
        "convention_profile_ids": list(
            payload["convention_profile_ids"]
        ),
        "mechanism_statement": payload["mechanism_statement"],
        "falsifiable_consequences": [
            dict(item) for item in payload["falsifiable_consequences"]
        ],
        "known_failures": list(payload["known_failures"]),
        "remaining_gaps": list(payload["remaining_gaps"]),
        "terminology": [
            dict(item) for item in payload.get("terminology", [])
        ],
        "truth_boundary": INTERPRET_TRUTH_BOUNDARY,
        "AI-assistance disclosure": AI_DISCLOSURE_PLACEHOLDER,
    }
    return validate_interpret_card(
        {
            **semantic,
            "interpret_card_sha256": sha256_json(semantic),
        }
    )


def validate_interpret_card(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("interpret card must be one object")
    require_exact_keys(
        payload,
        required=INTERPRET_CARD_FIELDS,
        label="interpret exploration card",
    )
    if payload.get("schema_version") != 1:
        raise ValueError("interpret card schema_version must be 1")
    if payload.get("policy_revision") != POLICY_REVISION_V4:
        raise ValueError("interpret card policy_revision mismatch")
    if payload.get("card_kind") != INTERPRET_CARD_KIND:
        raise ValueError("interpret card kind mismatch")
    require_string(payload, "project_id")
    validate_bb_node_id(require_string(payload, "node_id"))
    if SHA256_RE.fullmatch(
        require_string(payload, "node_content_sha256")
    ) is None:
        raise ValueError("interpret card node content hash is invalid")
    if require_string(payload, "audience") not in EXPERT_AUDIENCES:
        raise ValueError("interpret card audience is invalid")
    for key in (
        "source_refs",
        "explains_refs",
        "domain_clause_refs",
        "convention_profile_ids",
        "known_failures",
        "remaining_gaps",
    ):
        value = payload.get(key)
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            raise ValueError(f"interpret card {key} must be strings")
    require_string(payload, "mechanism_statement")
    consequences = payload.get("falsifiable_consequences")
    if not isinstance(consequences, list) or any(
        not isinstance(item, dict) for item in consequences
    ):
        raise ValueError(
            "interpret card falsifiable_consequences must be objects"
        )
    _validate_terminology_entries(payload.get("terminology"), proof=None)
    validate_interpret_mechanism(
        {
            "explains_refs": list(payload["explains_refs"]),
            "domain_clause_refs": list(payload["domain_clause_refs"]),
            "convention_profile_ids": list(
                payload["convention_profile_ids"]
            ),
            "mechanism_statement": payload["mechanism_statement"],
            "falsifiable_consequences": [
                dict(item) for item in consequences
            ],
            "known_failures": list(payload["known_failures"]),
            "remaining_gaps": list(payload["remaining_gaps"]),
            "truth_status": "exploration",
            "terminology": [
                dict(item) for item in payload["terminology"]
            ],
        }
    )
    if payload.get("truth_boundary") != INTERPRET_TRUTH_BOUNDARY:
        raise ValueError("interpret card truth boundary mismatch")
    require_string(payload, "AI-assistance disclosure")
    semantic = {
        key: value
        for key, value in payload.items()
        if key != "interpret_card_sha256"
    }
    if payload.get("interpret_card_sha256") != sha256_json(semantic):
        raise ValueError("interpret card hash mismatch")
    return payload


def _interpret_card_from_bytes(
    interpret_card_bytes: bytes,
) -> dict[str, Any]:
    if not isinstance(interpret_card_bytes, bytes):
        raise ValueError("interpret_card_bytes must be exact bytes")
    try:
        payload = json.loads(interpret_card_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "interpret-card bytes must contain one UTF-8 JSON object"
        ) from exc
    return validate_interpret_card(payload)


def lint_interpret_document(
    text: str,
    *,
    interpret_card: dict[str, Any],
) -> list[str]:
    """Lint visible interpretation prose without granting any truth effect."""

    card = validate_interpret_card(interpret_card)
    visible_text = _visible_text(text)
    errors = _lint_terminology(visible_text, card["terminology"])

    if card["mechanism_statement"] not in visible_text:
        errors.append(
            "interpret document omits exact mechanism statement"
        )
    for field in (
        "source_refs",
        "explains_refs",
        "domain_clause_refs",
        "convention_profile_ids",
    ):
        for reference in card[field]:
            if reference not in visible_text:
                errors.append(
                    f"interpret document omits {field} reference: {reference}"
                )
    for consequence in card["falsifiable_consequences"]:
        for key in ("id", "statement", "suggested_mode"):
            marker = consequence[key]
            if marker not in visible_text:
                errors.append(
                    "interpret document omits falsifiable consequence "
                    f"{consequence['id']} {key}: {marker}"
                )
    for failure in card["known_failures"]:
        if failure not in visible_text:
            errors.append(
                f"interpret document omits known failure: {failure}"
            )
    for gap in card["remaining_gaps"]:
        if gap not in visible_text:
            errors.append(
                f"interpret document omits remaining gap: {gap}"
            )
    if card["truth_boundary"] not in visible_text:
        errors.append(
            "interpret document omits exact exploration truth boundary"
        )
    errors.extend(
        _lint_ai_disclosure(
            visible_text,
            card["AI-assistance disclosure"],
            label="interpret document",
        )
    )
    return errors


def build_interpret_lint_receipt(
    *,
    project_id: str,
    receipt_relpath: str,
    interpret_card_relpath: str,
    draft_bytes: bytes,
    interpret_card_bytes: bytes,
) -> dict[str, Any]:
    project_id = require_string({"project_id": project_id}, "project_id")
    receipt_relpath = require_relative_path(
        receipt_relpath, "receipt_relpath"
    ).as_posix()
    if not receipt_relpath.startswith(
        "reports/interpret-lint-receipts/"
    ):
        raise ValueError(
            "interpret lint receipt must be stored below "
            "reports/interpret-lint-receipts/"
        )
    interpret_card_relpath = require_relative_path(
        interpret_card_relpath, "interpret_card_relpath"
    ).as_posix()
    if not interpret_card_relpath.startswith("reports/"):
        raise ValueError(
            "interpret card must be stored below project reports/"
        )
    if not isinstance(draft_bytes, bytes):
        raise ValueError("draft_bytes must be exact bytes")
    try:
        draft_text = draft_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("interpret draft must be UTF-8") from exc
    card = _interpret_card_from_bytes(interpret_card_bytes)
    if card["project_id"] != project_id:
        raise ValueError("interpret card belongs to another project")
    errors = lint_interpret_document(
        draft_text,
        interpret_card=card,
    )
    semantic = {
        "schema_version": 1,
        "policy_revision": POLICY_REVISION_V4,
        "receipt_kind": INTERPRET_LINT_RECEIPT_KIND,
        "linter_revision": INTERPRET_LINTER_REVISION,
        "project_id": project_id,
        "receipt_relpath": receipt_relpath,
        "interpret_card_relpath": interpret_card_relpath,
        "draft_sha256": sha256_bytes(draft_bytes),
        "interpret_card_bytes_sha256": sha256_bytes(
            interpret_card_bytes
        ),
        "interpret_card_sha256": card["interpret_card_sha256"],
        "node_id": card["node_id"],
        "node_content_sha256": card["node_content_sha256"],
        "audience": card["audience"],
        "ok": not errors,
        "errors": errors,
        "scope": INTERPRET_LINT_SCOPE,
        "truth_effect": "none",
    }
    return {
        **semantic,
        "lint_receipt_sha256": sha256_json(semantic),
    }


def validate_interpret_lint_receipt(
    receipt: Any,
    *,
    draft_bytes: bytes | None = None,
    interpret_card_bytes: bytes | None = None,
) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise ValueError("interpret lint receipt must be one object")
    require_exact_keys(
        receipt,
        required=INTERPRET_LINT_RECEIPT_FIELDS,
        label="interpret lint receipt",
    )
    if receipt.get("schema_version") != 1:
        raise ValueError("interpret lint receipt schema_version must be 1")
    if receipt.get("policy_revision") != POLICY_REVISION_V4:
        raise ValueError("interpret lint receipt policy_revision mismatch")
    if receipt.get("receipt_kind") != INTERPRET_LINT_RECEIPT_KIND:
        raise ValueError("interpret lint receipt kind mismatch")
    if receipt.get("linter_revision") != INTERPRET_LINTER_REVISION:
        raise ValueError("interpret lint receipt linter revision mismatch")
    require_string(receipt, "project_id")
    receipt_relpath = require_relative_path(
        require_string(receipt, "receipt_relpath"),
        "receipt_relpath",
    ).as_posix()
    if not receipt_relpath.startswith(
        "reports/interpret-lint-receipts/"
    ):
        raise ValueError(
            "interpret lint receipt path must remain below "
            "reports/interpret-lint-receipts/"
        )
    card_relpath = require_relative_path(
        require_string(receipt, "interpret_card_relpath"),
        "interpret_card_relpath",
    ).as_posix()
    if not card_relpath.startswith("reports/"):
        raise ValueError(
            "interpret lint receipt card path must remain below reports/"
        )
    for key in (
        "draft_sha256",
        "interpret_card_bytes_sha256",
        "interpret_card_sha256",
        "node_content_sha256",
        "lint_receipt_sha256",
    ):
        if SHA256_RE.fullmatch(require_string(receipt, key)) is None:
            raise ValueError(f"interpret lint receipt {key} is invalid")
    validate_bb_node_id(require_string(receipt, "node_id"))
    if require_string(receipt, "audience") not in EXPERT_AUDIENCES:
        raise ValueError("interpret lint receipt audience is invalid")
    if not isinstance(receipt.get("ok"), bool):
        raise ValueError("interpret lint receipt ok must be boolean")
    errors = receipt.get("errors")
    if not isinstance(errors, list) or any(
        not isinstance(item, str) for item in errors
    ):
        raise ValueError("interpret lint receipt errors must be strings")
    if receipt["ok"] != (not errors):
        raise ValueError("interpret lint receipt ok/errors mismatch")
    if receipt.get("scope") != INTERPRET_LINT_SCOPE:
        raise ValueError("interpret lint receipt scope mismatch")
    if receipt.get("truth_effect") != "none":
        raise ValueError("interpret lint receipt truth boundary mismatch")
    semantic = {
        key: value
        for key, value in receipt.items()
        if key != "lint_receipt_sha256"
    }
    if receipt["lint_receipt_sha256"] != sha256_json(semantic):
        raise ValueError("interpret lint receipt hash mismatch")

    card: dict[str, Any] | None = None
    if interpret_card_bytes is not None:
        card = _interpret_card_from_bytes(interpret_card_bytes)
        if (
            receipt["interpret_card_bytes_sha256"]
            != sha256_bytes(interpret_card_bytes)
            or receipt["interpret_card_sha256"]
            != card["interpret_card_sha256"]
            or receipt["project_id"] != card["project_id"]
            or receipt["node_id"] != card["node_id"]
            or receipt["node_content_sha256"]
            != card["node_content_sha256"]
            or receipt["audience"] != card["audience"]
        ):
            raise ValueError(
                "interpret lint receipt card bytes mismatch"
            )
    if draft_bytes is not None:
        if receipt["draft_sha256"] != sha256_bytes(draft_bytes):
            raise ValueError("interpret lint receipt draft bytes mismatch")
        if card is None:
            raise ValueError(
                "interpret_card_bytes are required to revalidate draft bytes"
            )
        try:
            draft_text = draft_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("interpret draft must be UTF-8") from exc
        recomputed = lint_interpret_document(
            draft_text,
            interpret_card=card,
        )
        if recomputed != errors:
            raise ValueError(
                "interpret lint receipt no longer matches linter output"
            )
    return receipt


def validate_interpret_communication_readiness(
    *,
    adoption_binding: dict[str, Any],
    lint_receipt: dict[str, Any] | None,
    draft_bytes: bytes,
    interpret_card_bytes: bytes,
) -> dict[str, Any]:
    """Consume current interpretation-lint evidence with no truth effect."""

    validate_adoption_binding(adoption_binding)
    required = feature_required(
        adoption_binding,
        "terminology_export_lint",
    )
    if lint_receipt is None:
        if required:
            raise ValueError(
                "terminology_export_lint is required; a valid "
                "interpretation receipt must precede communication"
            )
        semantic = {
            "revision": INTERPRET_COMMUNICATION_READINESS_REVISION,
            "ready": True,
            "requirement": "not_required",
            "truth_effect": "none",
        }
        return {**semantic, "readiness_sha256": sha256_json(semantic)}
    receipt = validate_interpret_lint_receipt(
        lint_receipt,
        draft_bytes=draft_bytes,
        interpret_card_bytes=interpret_card_bytes,
    )
    if not receipt["ok"]:
        raise ValueError(
            "interpret communication lint failed: "
            + "; ".join(receipt["errors"])
        )
    semantic = {
        "revision": INTERPRET_COMMUNICATION_READINESS_REVISION,
        "ready": True,
        "requirement": (
            "satisfied" if required else "validated_optional"
        ),
        "lint_receipt_sha256": receipt["lint_receipt_sha256"],
        "truth_effect": "none",
    }
    return {**semantic, "readiness_sha256": sha256_json(semantic)}


def validate_interpret_communication_readiness_result(
    value: Any,
) -> dict[str, Any]:
    """Validate the typed nontruth handoff consumed by publication."""

    if not isinstance(value, dict):
        raise ValueError("interpret communication readiness must be one object")
    requirement = value.get("requirement")
    fields = {
        "revision",
        "ready",
        "requirement",
        "truth_effect",
        "readiness_sha256",
    }
    if requirement in {"satisfied", "validated_optional"}:
        fields.add("lint_receipt_sha256")
    if set(value) != fields:
        raise ValueError("interpret communication readiness fields are not exact")
    if (
        value["revision"] != INTERPRET_COMMUNICATION_READINESS_REVISION
        or value["ready"] is not True
        or requirement
        not in {"not_required", "satisfied", "validated_optional"}
        or value["truth_effect"] != "none"
    ):
        raise ValueError("interpret communication readiness contract is invalid")
    if "lint_receipt_sha256" in value and (
        not isinstance(value["lint_receipt_sha256"], str)
        or SHA256_RE.fullmatch(value["lint_receipt_sha256"]) is None
    ):
        raise ValueError("interpret communication readiness lint binding is invalid")
    semantic = {
        key: item for key, item in value.items() if key != "readiness_sha256"
    }
    if value["readiness_sha256"] != sha256_json(semantic):
        raise ValueError("interpret communication readiness hash mismatch")
    return value


def publish_interpret_communication(
    *,
    store: Any,
    external_communication_requested: bool,
    adoption_binding: dict[str, Any] | None = None,
    lint_receipt: dict[str, Any] | None = None,
    draft_bytes: bytes | None = None,
    interpret_card_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Publish one interpretation only after consuming current readiness.

    The predicate-false branch is deliberately a zero-write internal path.
    The published artifact remains nontruth exposition and cannot create a
    Candidate Release, Certification decision, or Fact.
    """

    if not isinstance(external_communication_requested, bool):
        raise ValueError("external communication predicate must be boolean")
    if not external_communication_requested:
        semantic = {
            "revision": INTERPRET_COMMUNICATION_PUBLICATION_REVISION,
            "project_id": store.project_id(),
            "published": False,
            "reason": "internal_only",
            "write_effect": "none",
            "truth_effect": "none",
            "fact_admission_effect": "none",
        }
        return {**semantic, "publication_sha256": sha256_json(semantic)}
    if not isinstance(adoption_binding, dict):
        raise ValueError("interpret publication requires an adoption binding")
    if not isinstance(draft_bytes, bytes) or not isinstance(
        interpret_card_bytes, bytes
    ):
        raise ValueError("interpret publication requires exact draft and card bytes")

    readiness = validate_interpret_communication_readiness(
        adoption_binding=adoption_binding,
        lint_receipt=lint_receipt,
        draft_bytes=draft_bytes,
        interpret_card_bytes=interpret_card_bytes,
    )
    readiness = validate_interpret_communication_readiness_result(readiness)
    card = validate_interpret_card(
        json.loads(interpret_card_bytes.decode("utf-8"))
    )
    if card["project_id"] != store.project_id():
        raise ValueError("interpret publication card belongs to another project")
    semantic_binding = {
        "revision": INTERPRET_COMMUNICATION_PUBLICATION_REVISION,
        "project_id": store.project_id(),
        "node_id": card["node_id"],
        "audience": card["audience"],
        "draft_sha256": sha256_bytes(draft_bytes),
        "interpret_card_bytes_sha256": sha256_bytes(interpret_card_bytes),
        "interpret_card_sha256": card["interpret_card_sha256"],
        "readiness_sha256": readiness["readiness_sha256"],
        "truth_effect": "none",
        "fact_admission_effect": "none",
    }
    communication_id = "icm-" + sha256_json(semantic_binding)
    relative_document = f"interpret-communications/{communication_id}.md"
    relative_receipt = f"interpret-communications/{communication_id}.json"
    document_path = store.report_output_path(relative_document)
    receipt_path = store.report_output_path(relative_receipt)
    receipt_semantic = {
        **semantic_binding,
        "communication_id": communication_id,
        "published": True,
        "document_relpath": document_path.relative_to(store.root).as_posix(),
        "receipt_relpath": receipt_path.relative_to(store.root).as_posix(),
        "readiness": readiness,
        "write_effect": "communication_artifact_only",
    }
    receipt = {
        **receipt_semantic,
        "publication_sha256": sha256_json(receipt_semantic),
    }
    if document_path.exists():
        if document_path.is_symlink() or document_path.read_bytes() != draft_bytes:
            raise ValueError("interpret communication document collision")
    else:
        document_path.parent.mkdir(parents=True, exist_ok=True)
        store._write_bytes_atomic(document_path, draft_bytes)
    store._write_json_once(receipt_path, receipt)
    return receipt


class FactBundleStore:
    """All-or-nothing candidate mini-DAG storage.

    Bundle fact bytes are invisible until one valid ACCEPTED.json marker exists.
    """

    def __init__(
        self,
        project_root: Path | str,
        *,
        admission_authority: object | None = None,
        acceptance_validator: (
            Callable[[dict[str, Any], dict[str, Any]], Any] | None
        ) = None,
        _fixture_authority: object | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.root = self.project_root / "fact_graph" / "bundles"
        self._admission_authority = admission_authority
        self._inherited_chalk_fixture = (
            _fixture_authority is _INHERITED_CHALK_FIXTURE_AUTHORITY
        )
        self._acceptance_validator = acceptance_validator

    @classmethod
    def _for_inherited_chalk_fixture(
        cls,
        project_root: Path | str,
        *,
        acceptance_validator: (
            Callable[[dict[str, Any], dict[str, Any]], Any] | None
        ) = None,
    ) -> "FactBundleStore":
        return cls(
            project_root,
            acceptance_validator=acceptance_validator,
            _fixture_authority=_INHERITED_CHALK_FIXTURE_AUTHORITY,
        )

    def _require_mathgraph_authority(
        self,
        supplied: object | None,
        *,
        operation: str,
    ) -> None:
        if self._inherited_chalk_fixture:
            return
        if (
            self._admission_authority is None
            or supplied is not self._admission_authority
        ):
            raise ValueError(
                f"fact bundle {operation} requires MathGraphStore authority"
            )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"expected one JSON object in {path}")
        return payload

    @staticmethod
    def _write_once(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(path, flags, mode)
        except FileExistsError:
            if not path.is_file() or path.is_symlink() or path.read_bytes() != payload:
                raise ValueError(f"immutable fact bundle collision at {path}")
            return
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    @classmethod
    def _write_json_once(cls, path: Path, payload: dict[str, Any]) -> None:
        cls._write_once(
            path,
            (
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            ).encode("utf-8"),
        )

    @staticmethod
    def _topological_order(facts: dict[str, Fact]) -> list[str]:
        indegree = {fact_id: 0 for fact_id in facts}
        children: dict[str, set[str]] = {fact_id: set() for fact_id in facts}
        for fact_id, fact in facts.items():
            for predecessor in fact.predecessors:
                if predecessor in facts:
                    indegree[fact_id] += 1
                    children[predecessor].add(fact_id)
        ready = sorted(fact_id for fact_id, degree in indegree.items() if degree == 0)
        order: list[str] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for child in sorted(children[current]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
                    ready.sort()
        if len(order) != len(facts):
            raise ValueError("fact bundle internal predecessor graph has a cycle")
        return order

    @staticmethod
    def _validate_bound_provenance(
        payload: dict[str, Any],
    ) -> dict[str, str]:
        if not isinstance(payload, dict):
            raise ValueError("bound fact-bundle provenance must be an object")
        require_exact_keys(
            payload,
            required={
                "round_id",
                "assignment_id",
                "task_card_sha256",
                "return_sha256",
            },
            label="bound fact-bundle provenance",
        )
        round_id = validate_round_id(
            require_string(payload, "round_id")
        )
        assignment_id = validate_assignment_id(
            require_string(payload, "assignment_id")
        )
        for key in ("task_card_sha256", "return_sha256"):
            if SHA256_RE.fullmatch(require_string(payload, key)) is None:
                raise ValueError(
                    f"bound fact-bundle provenance {key} is invalid"
                )
        return {
            "round_id": round_id,
            "assignment_id": assignment_id,
            "task_card_sha256": payload["task_card_sha256"],
            "return_sha256": payload["return_sha256"],
        }

    def _prepare_submission(
        self,
        payload: dict[str, Any],
        *,
        worker: str,
        external_fact_exists: Callable[[str], bool],
        provenance: dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any], dict[str, Fact]]:
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
            label="fact bundle submission",
        )
        if payload.get("schema_version") != 4:
            raise ValueError("fact bundle schema_version must be 4")
        if payload.get("policy_revision") != POLICY_REVISION_V4:
            raise ValueError("fact bundle policy_revision mismatch")
        project_id = require_string(payload, "project_id")
        require_string(payload, "bundle_claim")
        fact_payloads = payload.get("facts")
        if not isinstance(fact_payloads, list) or not fact_payloads or any(
            not isinstance(item, dict) for item in fact_payloads
        ):
            raise ValueError("fact bundle facts must be a nonempty object list")
        normalized_provenance = (
            self._validate_bound_provenance(provenance)
            if provenance is not None
            else None
        )
        worker = require_string({"worker": worker}, "worker")
        if normalized_provenance is not None:
            if worker != normalized_provenance["assignment_id"]:
                raise ValueError(
                    "bound fact-bundle worker must equal assignment_id"
                )
            if len(fact_payloads) < 2:
                raise ValueError(
                    "bound fact-bundle submission requires at least two facts"
                )
        facts: dict[str, Fact] = {}
        for item in fact_payloads:
            fact = Fact.from_dict(item)
            if fact.problem_id != project_id:
                raise ValueError("fact bundle fact belongs to another project")
            if (
                normalized_provenance is not None
                and fact.author != worker
            ):
                raise ValueError(
                    "bound fact-bundle fact author must equal assignment worker"
                )
            errors = fact.validate()
            if errors:
                raise ValueError("; ".join(errors))
            if "[CLAIM:DOMAIN-" in fact.statement:
                validate_domain_certificate_statement(fact.statement)
            validate_fact_round_trip(fact)
            if fact.fact_id in facts:
                raise ValueError("fact bundle has a duplicate fact id")
            facts[fact.fact_id] = fact
        for fact in facts.values():
            for predecessor in fact.predecessors:
                if predecessor not in facts and not external_fact_exists(predecessor):
                    raise ValueError(
                        f"fact bundle predecessor is neither internal nor admitted: {predecessor}"
                    )
        order = self._topological_order(facts)
        manifest_body = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "project_id": project_id,
            "bundle_claim": payload["bundle_claim"],
            "worker": worker,
            "fact_ids": order,
            "fact_sha256": {
                fact_id: sha256_bytes(
                    validate_fact_round_trip(facts[fact_id]).encode("utf-8")
                )
                for fact_id in order
            },
            "internal_edges": sorted(
                [
                    [predecessor, fact_id]
                    for fact_id in order
                    for predecessor in facts[fact_id].predecessors
                    if predecessor in facts
                ]
            ),
        }
        if normalized_provenance is not None:
            manifest_body["provenance"] = normalized_provenance
        digest = sha256_json(manifest_body)
        bundle_id = "factbundle-" + digest
        supplied = payload.get("fact_bundle_id")
        if supplied is not None and supplied != bundle_id:
            raise ValueError("fact bundle id/hash mismatch")
        manifest = {
            **manifest_body,
            "fact_bundle_id": bundle_id,
            "manifest_sha256": digest,
        }
        return bundle_id, manifest, facts

    def validate_submission(
        self,
        payload: dict[str, Any],
        *,
        worker: str,
        external_fact_exists: Callable[[str], bool],
        provenance: dict[str, Any] | None = None,
    ) -> str:
        """Purely validate a bundle and return its prospective content id."""

        bundle_id, _, _ = self._prepare_submission(
            payload,
            worker=worker,
            external_fact_exists=external_fact_exists,
            provenance=provenance,
        )
        return bundle_id

    def submit(
        self,
        payload: dict[str, Any],
        *,
        worker: str,
        external_fact_exists: Callable[[str], bool],
        provenance: dict[str, Any] | None = None,
    ) -> str:
        bundle_id, manifest, facts = self._prepare_submission(
            payload,
            worker=worker,
            external_fact_exists=external_fact_exists,
            provenance=provenance,
        )
        directory = self.root / bundle_id
        manifest_path = directory / "manifest.json"
        fact_bytes = {
            fact_id: validate_fact_round_trip(facts[fact_id]).encode("utf-8")
            for fact_id in manifest["fact_ids"]
        }
        if manifest_path.exists():
            if (
                not directory.is_dir()
                or directory.is_symlink()
                or not manifest_path.is_file()
                or manifest_path.is_symlink()
                or self._read_json(manifest_path) != manifest
            ):
                raise ValueError("fact bundle id collision")
            for fact_id, expected in fact_bytes.items():
                path = directory / "facts" / f"{fact_id}.md"
                if (
                    not path.is_file()
                    or path.is_symlink()
                    or path.read_bytes() != expected
                ):
                    raise ValueError(
                        "immutable fact bundle candidate bytes mismatch"
                    )
            return bundle_id

        # The manifest is written last.  If a process dies while staging fact
        # bytes, a retry may complete the exact same content-addressed stage;
        # unexpected or changed bytes still fail closed.
        directory.mkdir(parents=True, exist_ok=True)
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError("fact bundle staging path is unsafe")
        expected_paths = {
            directory / "facts" / f"{fact_id}.md"
            for fact_id in manifest["fact_ids"]
        }
        actual_files = {
            path
            for path in directory.rglob("*")
            if path.is_file() or path.is_symlink()
        }
        if any(path.is_symlink() for path in actual_files):
            raise ValueError("fact bundle staging contains a symlink")
        unexpected = actual_files.difference(expected_paths)
        if unexpected:
            raise ValueError(
                "fact bundle staging contains unexpected files: "
                + ", ".join(
                    sorted(
                        path.relative_to(directory).as_posix()
                        for path in unexpected
                    )
                )
            )
        for fact_id in manifest["fact_ids"]:
            self._write_once(
                directory / "facts" / f"{fact_id}.md",
                fact_bytes[fact_id],
                mode=0o644,
            )
        self._write_json_once(manifest_path, manifest)
        return bundle_id

    def _validate_bound_ingestion_receipt(
        self,
        fact_bundle_id: str,
        provenance: dict[str, str],
    ) -> None:
        round_manifest_path = (
            self.project_root
            / "rounds"
            / provenance["round_id"]
            / "round.json"
        )
        if (
            not round_manifest_path.is_file()
            or round_manifest_path.is_symlink()
        ):
            raise ValueError(
                "bound fact-bundle round manifest is missing"
            )
        round_manifest = self._read_json(round_manifest_path)
        assignments = round_manifest.get("assignments")
        if not isinstance(assignments, list):
            raise ValueError(
                "bound fact-bundle round assignments are invalid"
            )
        matches = [
            assignment
            for assignment in assignments
            if isinstance(assignment, dict)
            and assignment.get("assignment_id")
            == provenance["assignment_id"]
        ]
        if len(matches) != 1:
            raise ValueError(
                "bound fact-bundle assignment provenance is unavailable"
            )
        assignment = matches[0]
        if (
            round_manifest.get("round_id") != provenance["round_id"]
            or assignment.get("worker_id")
            != provenance["assignment_id"]
            or assignment.get("task_card_sha256")
            != provenance["task_card_sha256"]
        ):
            raise ValueError(
                "bound fact-bundle round provenance mismatch"
            )
        return_path = contained_path(
            self.project_root,
            require_string(assignment, "return_relpath"),
            "bound fact-bundle return path",
        )
        receipt_path = return_path.with_suffix(".receipt.json")
        if not receipt_path.is_file() or receipt_path.is_symlink():
            raise ValueError(
                "bound fact bundle is not visible before its ingestion receipt"
            )
        receipt = self._read_json(receipt_path)
        from .protocol import validate_ingestion_receipt_v4

        validate_ingestion_receipt_v4(receipt)
        if (
            receipt.get("round_id") != provenance["round_id"]
            or receipt.get("assignment_id") != provenance["assignment_id"]
            or receipt.get("assignment_sha256")
            != assignment.get("assignment_sha256")
            or receipt.get("return_relpath")
            != assignment["return_relpath"]
            or receipt.get("task_card_sha256")
            != provenance["task_card_sha256"]
            or receipt.get("return_sha256") != provenance["return_sha256"]
            or receipt.get("outcome") != "fact_bundle_submission"
            or receipt.get("effect")
            != {
                "fact_bundle_id": fact_bundle_id,
                "status": "pending_bundle_review",
            }
        ):
            raise ValueError(
                "bound fact-bundle ingestion receipt provenance mismatch"
            )

    def manifest(self, fact_bundle_id: str) -> dict[str, Any]:
        fact_bundle_id = validate_fact_bundle_id(fact_bundle_id)
        path = self.root / fact_bundle_id / "manifest.json"
        if not path.exists():
            raise KeyError(f"unknown fact bundle: {fact_bundle_id}")
        manifest = self._read_json(path)
        require_exact_keys(
            manifest,
            required={
                "schema_version",
                "policy_revision",
                "project_id",
                "bundle_claim",
                "worker",
                "fact_ids",
                "fact_sha256",
                "internal_edges",
                "fact_bundle_id",
                "manifest_sha256",
            },
            optional={"provenance"},
            label="fact bundle manifest",
        )
        provenance = manifest.get("provenance")
        normalized_provenance = (
            self._validate_bound_provenance(provenance)
            if provenance is not None
            else None
        )
        body = {
            key: manifest[key]
            for key in (
                "schema_version",
                "policy_revision",
                "project_id",
                "bundle_claim",
                "worker",
                "fact_ids",
                "fact_sha256",
                "internal_edges",
            )
        }
        if normalized_provenance is not None:
            body["provenance"] = normalized_provenance
        if (
            manifest.get("fact_bundle_id") != fact_bundle_id
            or manifest.get("manifest_sha256") != sha256_json(body)
            or fact_bundle_id != "factbundle-" + sha256_json(body)
        ):
            raise ValueError("fact bundle manifest hash mismatch")
        for fact_id in manifest["fact_ids"]:
            path = self.root / fact_bundle_id / "facts" / f"{fact_id}.md"
            if sha256_bytes(path.read_bytes()) != manifest["fact_sha256"][fact_id]:
                raise ValueError("fact bundle candidate bytes were modified")
        if normalized_provenance is not None:
            self._validate_bound_ingestion_receipt(
                fact_bundle_id,
                normalized_provenance,
            )
        return manifest

    def verifier_task(
        self,
        fact_bundle_id: str,
        *,
        predecessor_packets: dict[str, dict[str, Any]] | None = None,
        _verification_authority: object | None = None,
    ) -> dict[str, Any]:
        self._require_mathgraph_authority(
            _verification_authority,
            operation="verifier construction",
        )
        manifest = self.manifest(fact_bundle_id)
        directory = self.root / fact_bundle_id
        facts = {
            fact_id: parse_fact_markdown(
                (
                    directory / "facts" / f"{fact_id}.md"
                ).read_text(encoding="utf-8")
            )
            for fact_id in manifest["fact_ids"]
        }
        external_predecessors = sorted(
            {
                predecessor
                for fact in facts.values()
                for predecessor in fact.predecessors
                if predecessor not in facts
            }
        )
        predecessor_packets = predecessor_packets or {}
        if set(predecessor_packets) != set(external_predecessors):
            raise ValueError(
                "fact bundle verifier predecessor interface set mismatch"
            )
        packet_lines = [
            "# Atomic MathGraph fact-bundle verification",
            "",
            manifest["bundle_claim"],
            "",
            "Use only this packet and the included admitted statement interfaces.",
            "No predecessor proof or exploration state is authorized.",
            "",
        ]
        interface_entries: list[dict[str, str]] = []
        for predecessor in external_predecessors:
            payload = predecessor_packets[predecessor]
            require_exact_keys(
                payload,
                required={"statement", "interface"},
                label="fact bundle predecessor packet",
            )
            statement = require_string(payload, "statement")
            interface = payload.get("interface")
            if not isinstance(interface, dict):
                raise ValueError(
                    "fact bundle predecessor interface must be an object"
                )
            validate_statement_interface(interface)
            if interface["fact_id"] != predecessor:
                raise ValueError(
                    "fact bundle predecessor interface id mismatch"
                )
            statement_sha256 = sha256_bytes(statement.encode("utf-8"))
            if interface["statement_sha256"] != statement_sha256:
                raise ValueError(
                    "fact bundle predecessor statement/interface mismatch"
                )
            packet_lines.append(
                statement_only_packet_section(
                    fact_id=predecessor,
                    statement=statement,
                    interface=interface,
                )
            )
            interface_entries.append(
                {
                    "fact_id": predecessor,
                    "statement_sha256": statement_sha256,
                    "interface_sha256": interface["interface_sha256"],
                }
            )
        for fact_id in manifest["fact_ids"]:
            packet_lines.extend(
                [
                    f"## Candidate fact `{fact_id}`",
                    "",
                    (directory / "facts" / f"{fact_id}.md").read_text(
                        encoding="utf-8"
                    ),
                    "",
                ]
            )
        packet = "\n".join(packet_lines).rstrip() + "\n"
        packet_path = directory / "packet.md"
        self._write_once(packet_path, packet.encode("utf-8"))
        for predecessor in external_predecessors:
            self._write_json_once(
                directory / "interfaces" / f"{predecessor}.json",
                predecessor_packets[predecessor]["interface"],
            )
        verification_semantic = {
            "schema_version": 1,
            "policy_revision": POLICY_REVISION_V4,
            "fact_bundle_id": fact_bundle_id,
            "fact_bundle_manifest_sha256": manifest[
                "manifest_sha256"
            ],
            "packet_sha256": sha256_bytes(packet.encode("utf-8")),
            "interfaces": interface_entries,
        }
        verification_manifest = {
            **verification_semantic,
            "verification_manifest_sha256": sha256_json(
                verification_semantic
            ),
        }
        self._write_json_once(
            directory / "verification_manifest.json",
            verification_manifest,
        )
        return {
            "fact_bundle_id": fact_bundle_id,
            "manifest_sha256": manifest["manifest_sha256"],
            "packet_sha256": verification_manifest["packet_sha256"],
            "verification_manifest_sha256": verification_manifest[
                "verification_manifest_sha256"
            ],
            "packet_path": str(packet_path),
            "review_return_path": str(directory / "review.return.json"),
            "fork_turns": "none",
        }

    def _validated_verification_package(
        self,
        fact_bundle_id: str,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        directory = self.root / fact_bundle_id
        path = directory / "verification_manifest.json"
        if not path.is_file() or path.is_symlink():
            raise ValueError(
                "fact bundle verification manifest is missing or not regular"
            )
        package = self._read_json(path)
        require_exact_keys(
            package,
            required={
                "schema_version",
                "policy_revision",
                "fact_bundle_id",
                "fact_bundle_manifest_sha256",
                "packet_sha256",
                "interfaces",
                "verification_manifest_sha256",
            },
            label="fact bundle verification manifest",
        )
        if package.get("schema_version") != 1:
            raise ValueError(
                "fact bundle verification manifest schema mismatch"
            )
        if package.get("policy_revision") != POLICY_REVISION_V4:
            raise ValueError(
                "fact bundle verification manifest policy mismatch"
            )
        if (
            package.get("fact_bundle_id") != fact_bundle_id
            or package.get("fact_bundle_manifest_sha256")
            != manifest["manifest_sha256"]
        ):
            raise ValueError(
                "fact bundle verification manifest binding mismatch"
            )
        semantic = {
            key: value
            for key, value in package.items()
            if key != "verification_manifest_sha256"
        }
        if package.get("verification_manifest_sha256") != sha256_json(
            semantic
        ):
            raise ValueError(
                "fact bundle verification manifest hash mismatch"
            )
        packet_sha256 = require_string(package, "packet_sha256")
        packet_path = directory / "packet.md"
        if (
            SHA256_RE.fullmatch(packet_sha256) is None
            or not packet_path.is_file()
            or packet_path.is_symlink()
            or sha256_bytes(packet_path.read_bytes()) != packet_sha256
        ):
            raise ValueError("fact bundle verifier packet hash mismatch")
        interfaces = package.get("interfaces")
        if not isinstance(interfaces, list) or any(
            not isinstance(item, dict) for item in interfaces
        ):
            raise ValueError(
                "fact bundle verification interfaces must be objects"
            )
        normalized: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in interfaces:
            require_exact_keys(
                item,
                required={
                    "fact_id",
                    "statement_sha256",
                    "interface_sha256",
                },
                label="fact bundle verification interface",
            )
            fact_id = validate_fact_id(require_string(item, "fact_id"))
            if fact_id in seen:
                raise ValueError(
                    "fact bundle verification repeats an interface"
                )
            seen.add(fact_id)
            interface_path = directory / "interfaces" / f"{fact_id}.json"
            if not interface_path.is_file() or interface_path.is_symlink():
                raise ValueError(
                    "fact bundle verification interface is missing"
                )
            interface = validate_statement_interface(
                self._read_json(interface_path)
            )
            if (
                interface["fact_id"] != fact_id
                or interface["statement_sha256"]
                != require_string(item, "statement_sha256")
                or interface["interface_sha256"]
                != require_string(item, "interface_sha256")
            ):
                raise ValueError(
                    "fact bundle verification interface binding mismatch"
                )
            normalized.append(dict(item))
        if normalized != sorted(
            normalized,
            key=lambda item: item["fact_id"],
        ):
            raise ValueError(
                "fact bundle verification interfaces are not ordered"
            )
        return package

    def record_review(
        self,
        fact_bundle_id: str,
        review: dict[str, Any],
        *,
        _verification_authority: object | None = None,
    ) -> str:
        self._require_mathgraph_authority(
            _verification_authority,
            operation="review recording",
        )
        manifest = self.manifest(fact_bundle_id)
        package = self._validated_verification_package(
            fact_bundle_id,
            manifest,
        )
        require_exact_keys(
            review,
            required={
                "fact_bundle_id",
                "manifest_sha256",
                "verification_manifest_sha256",
                "packet_sha256",
                "verdict",
                "findings",
                "reviewer",
            },
            label="fact bundle review",
        )
        if review.get("fact_bundle_id") != fact_bundle_id:
            raise ValueError("fact bundle review id mismatch")
        if review.get("manifest_sha256") != manifest["manifest_sha256"]:
            raise ValueError("fact bundle review manifest mismatch")
        if (
            review.get("verification_manifest_sha256")
            != package["verification_manifest_sha256"]
            or review.get("packet_sha256") != package["packet_sha256"]
        ):
            raise ValueError(
                "fact bundle review verification-package mismatch"
            )
        verdict = require_string(review, "verdict")
        if verdict not in {"correct", "reject"}:
            raise ValueError("fact bundle review verdict is invalid")
        findings = review.get("findings")
        if not isinstance(findings, list) or any(
            not isinstance(item, str) for item in findings
        ):
            raise ValueError("fact bundle review findings must be strings")
        if verdict == "correct" and findings:
            raise ValueError("correct fact bundle review cannot contain findings")
        if verdict == "reject" and not findings:
            raise ValueError("rejecting fact bundle review requires findings")
        reviewer = require_string(review, "reviewer")
        if reviewer.casefold() == manifest["worker"].casefold():
            raise ValueError("fact bundle reviewer must be independent")
        semantic = {
            "fact_bundle_id": fact_bundle_id,
            "manifest_sha256": manifest["manifest_sha256"],
            "verification_manifest_sha256": package[
                "verification_manifest_sha256"
            ],
            "packet_sha256": package["packet_sha256"],
            "verdict": verdict,
            "findings": findings,
            "reviewer": reviewer,
        }
        review_id = sha256_json(semantic)
        self._write_json_once(
            self.root / fact_bundle_id / "review.json",
            {**semantic, "review_id": review_id},
        )
        return review_id

    def _validated_review(
        self,
        fact_bundle_id: str,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        package = self._validated_verification_package(
            fact_bundle_id,
            manifest,
        )
        path = self.root / fact_bundle_id / "review.json"
        if not path.is_file() or path.is_symlink():
            raise ValueError("fact bundle review is missing or not regular")
        review = self._read_json(path)
        require_exact_keys(
            review,
            required={
                "fact_bundle_id",
                "manifest_sha256",
                "verification_manifest_sha256",
                "packet_sha256",
                "verdict",
                "findings",
                "reviewer",
                "review_id",
            },
            label="stored fact bundle review",
        )
        if review.get("fact_bundle_id") != fact_bundle_id:
            raise ValueError("fact bundle review id mismatch")
        if review.get("manifest_sha256") != manifest["manifest_sha256"]:
            raise ValueError("fact bundle review manifest mismatch")
        if (
            review.get("verification_manifest_sha256")
            != package["verification_manifest_sha256"]
            or review.get("packet_sha256") != package["packet_sha256"]
        ):
            raise ValueError(
                "fact bundle review verification-package mismatch"
            )
        verdict = require_string(review, "verdict")
        if verdict not in {"correct", "reject"}:
            raise ValueError("fact bundle review verdict is invalid")
        findings = review.get("findings")
        if not isinstance(findings, list) or any(
            not isinstance(item, str) for item in findings
        ):
            raise ValueError("fact bundle review findings must be strings")
        if verdict == "correct" and findings:
            raise ValueError("correct fact bundle review cannot contain findings")
        if verdict == "reject" and not findings:
            raise ValueError("rejecting fact bundle review requires findings")
        reviewer = require_string(review, "reviewer")
        if reviewer.casefold() == manifest["worker"].casefold():
            raise ValueError("fact bundle reviewer must be independent")
        semantic = {
            "fact_bundle_id": fact_bundle_id,
            "manifest_sha256": manifest["manifest_sha256"],
            "verification_manifest_sha256": package[
                "verification_manifest_sha256"
            ],
            "packet_sha256": package["packet_sha256"],
            "verdict": verdict,
            "findings": findings,
            "reviewer": reviewer,
        }
        if review.get("review_id") != sha256_json(semantic):
            raise ValueError("fact bundle review hash mismatch")
        return review

    def admit(
        self,
        fact_bundle_id: str,
        *,
        review_id: str,
        profile_closure: dict[str, str] | None = None,
        _admission_authority: object | None = None,
    ) -> dict[str, Any]:
        self._require_mathgraph_authority(
            _admission_authority,
            operation="admission",
        )
        manifest = self.manifest(fact_bundle_id)
        directory = self.root / fact_bundle_id
        review = self._validated_review(fact_bundle_id, manifest)
        if review.get("review_id") != review_id or SHA256_RE.fullmatch(review_id) is None:
            raise ValueError("fact bundle admission review mismatch")
        if review.get("verdict") != "correct" or review.get("findings"):
            raise ValueError("fact bundle admission requires a clean review")
        semantic = {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "fact_bundle_id": fact_bundle_id,
            "manifest_sha256": manifest["manifest_sha256"],
            "review_id": review_id,
            "fact_ids": manifest["fact_ids"],
            **(
                {
                    "profile_closure_id": require_string(
                        profile_closure, "profile_closure_id"
                    ),
                    "profile_closure_sha256": require_string(
                        profile_closure, "profile_closure_sha256"
                    ),
                }
                if profile_closure is not None
                else {}
            ),
        }
        if profile_closure is not None and any(
            SHA256_RE.fullmatch(semantic[key]) is None
            for key in (
                "profile_closure_sha256",
            )
        ):
            raise ValueError("fact bundle profile closure hash is invalid")
        marker = {**semantic, "acceptance_sha256": sha256_json(semantic)}
        self._write_json_once(directory / "ACCEPTED.json", marker)
        return marker

    def _validated_acceptance(
        self,
        fact_bundle_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        manifest = self.manifest(fact_bundle_id)
        directory = self.root / fact_bundle_id
        marker_path = directory / "ACCEPTED.json"
        if not marker_path.is_file() or marker_path.is_symlink():
            raise ValueError("fact bundle acceptance marker is missing or not regular")
        marker = self._read_json(marker_path)
        require_exact_keys(
            marker,
            required={
                "schema_version",
                "policy_revision",
                "fact_bundle_id",
                "manifest_sha256",
                "review_id",
                "fact_ids",
                "acceptance_sha256",
            },
            optional={"profile_closure_id", "profile_closure_sha256"},
            label="fact bundle acceptance marker",
        )
        semantic = {
            key: marker[key]
            for key in (
                "schema_version",
                "policy_revision",
                "fact_bundle_id",
                "manifest_sha256",
                "review_id",
                "fact_ids",
            )
        }
        if "profile_closure_id" in marker or "profile_closure_sha256" in marker:
            if not {
                "profile_closure_id",
                "profile_closure_sha256",
            }.issubset(marker):
                raise ValueError("fact bundle profile closure binding is incomplete")
            if (
                not require_string(marker, "profile_closure_id").startswith(
                    "profileclose-"
                )
                or SHA256_RE.fullmatch(
                    require_string(marker, "profile_closure_sha256")
                )
                is None
            ):
                raise ValueError("fact bundle profile closure binding is invalid")
            semantic.update(
                {
                    "profile_closure_id": marker["profile_closure_id"],
                    "profile_closure_sha256": marker[
                        "profile_closure_sha256"
                    ],
                }
            )
        if marker.get("schema_version") != 4:
            raise ValueError("fact bundle acceptance schema version mismatch")
        if marker.get("policy_revision") != POLICY_REVISION_V4:
            raise ValueError("fact bundle acceptance policy revision mismatch")
        if marker.get("fact_bundle_id") != fact_bundle_id:
            raise ValueError("fact bundle acceptance id mismatch")
        if marker.get("acceptance_sha256") != sha256_json(semantic):
            raise ValueError("fact bundle acceptance marker hash mismatch")
        if (
            marker.get("manifest_sha256") != manifest["manifest_sha256"]
            or marker.get("fact_ids") != manifest["fact_ids"]
        ):
            raise ValueError("fact bundle acceptance manifest mismatch")
        review = self._validated_review(fact_bundle_id, manifest)
        if review["review_id"] != marker["review_id"]:
            raise ValueError("fact bundle acceptance review mismatch")
        if review["verdict"] != "correct" or review["findings"]:
            raise ValueError("fact bundle acceptance review is not clean")
        return manifest, review, marker

    def _validate_active_visibility(
        self,
        manifest: dict[str, Any],
        marker: dict[str, Any],
    ) -> None:
        if self._acceptance_validator is not None:
            self._acceptance_validator(manifest, marker)
            return
        if self._inherited_chalk_fixture:
            return
        raise ValueError(
            "accepted fact bundle visibility requires MathGraphStore authority"
        )

    def accepted_fact_paths(
        self,
        *,
        excluded_fact_ids: set[str] | None = None,
        strict: bool = False,
    ) -> dict[str, Path]:
        excluded = set(excluded_fact_ids or set())
        visible: dict[str, Path] = {}
        for directory in sorted(self.root.glob("factbundle-*")):
            marker_path = directory / "ACCEPTED.json"
            if not marker_path.exists():
                continue
            try:
                manifest, _, marker = self._validated_acceptance(directory.name)
                self._validate_active_visibility(manifest, marker)
                candidate_paths = {
                    fact_id: directory / "facts" / f"{fact_id}.md"
                    for fact_id in manifest["fact_ids"]
                    if fact_id not in excluded
                }
                collisions = set(visible).intersection(candidate_paths)
                if collisions:
                    raise ValueError(
                        "accepted fact bundle id collision: "
                        + ", ".join(sorted(collisions))
                    )
                visible.update(candidate_paths)
            except Exception:
                if strict:
                    raise
        return visible

    def acceptance_for_fact(self, fact_id: str) -> dict[str, Any]:
        validate_fact_id(fact_id)
        matches: list[dict[str, Any]] = []
        for directory in sorted(self.root.glob("factbundle-*")):
            if not (directory / "ACCEPTED.json").exists():
                continue
            manifest, review, marker = self._validated_acceptance(directory.name)
            self._validate_active_visibility(manifest, marker)
            if fact_id in manifest["fact_ids"]:
                matches.append(
                    {
                        "manifest": manifest,
                        "review": review,
                        "marker": marker,
                    }
                )
        if not matches:
            raise KeyError(f"fact is not in an accepted bundle: {fact_id}")
        if len(matches) != 1:
            raise ValueError("fact appears in multiple accepted bundles")
        return matches[0]

    def audit(self) -> dict[str, Any]:
        errors: list[str] = []
        try:
            visible = self.accepted_fact_paths(strict=True)
        except Exception as exc:
            visible = {}
            errors.append(f"accepted fact bundle visibility: {exc}")
        bundles = 0
        accepted = 0
        for directory in sorted(self.root.glob("factbundle-*")):
            bundles += 1
            try:
                manifest = self.manifest(directory.name)
                package_paths = (
                    directory / "packet.md",
                    directory / "verification_manifest.json",
                )
                if any(path.exists() for path in package_paths):
                    if not all(path.exists() for path in package_paths):
                        raise ValueError(
                            "fact bundle verification package is partial"
                        )
                    self._validated_verification_package(
                        directory.name,
                        manifest,
                    )
                if (directory / "ACCEPTED.json").exists():
                    accepted += 1
                    self._validated_acceptance(directory.name)
                    for fact_id in manifest["fact_ids"]:
                        if fact_id not in visible:
                            raise ValueError("accepted bundle is not atomically visible")
            except Exception as exc:
                errors.append(f"{directory.name}: {exc}")
        return {
            "ok": not errors,
            "errors": errors,
            "bundles": bundles,
            "accepted_bundles": accepted,
            "visible_facts": len(visible),
        }
