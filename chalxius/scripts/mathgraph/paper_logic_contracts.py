from __future__ import annotations

import re
from typing import Any

from .contracts import (
    SHA256_RE,
    require_exact_keys,
    require_string,
    sha256_bytes,
    sha256_json,
)


PAPER_LOGIC_FEATURE_REVISION = "paper-logic-1"
PAPER_LOGIC_TRUTH_BOUNDARY = (
    "Paper Logic and Audit Graph objects are nontruth evidence. "
    "Only independently admitted Fact Graph facts are proof premises."
)

PAPER_PLANES = {
    "paper_source",
    "paper_reconstruction",
    "paper_audit",
}
PAPER_SOURCE_TYPES = {"source_artifact", "source_unit"}
PAPER_RECONSTRUCTION_TYPES = {
    "claim",
    "definition",
    "formula",
    "inference",
    "paper_target",
}
PAPER_AUDIT_TYPES = {
    "audit_finding",
    "counterexample",
    "repair_proposal",
    "impact_assessment",
    "audit_challenge",
    "audit_disposition",
}
PAPER_OBJECT_TYPES = (
    PAPER_SOURCE_TYPES | PAPER_RECONSTRUCTION_TYPES | PAPER_AUDIT_TYPES
)

PAPER_NODE_ID_RE = re.compile(r"(?:psn|prn|pan)-[0-9a-f]{64}")
PAPER_EDGE_ID_RE = re.compile(r"(?:pse|pre|pae)-[0-9a-f]{64}")
PAPER_OBJECT_ID_RE = re.compile(
    r"(?:psn|prn|pan|pse|pre|pae)-[0-9a-f]{64}"
)
PAPER_REVISION_ID_RE = re.compile(r"plr-[0-9a-f]{64}")
PAPER_REVIEW_ID_RE = re.compile(r"plv-[0-9a-f]{64}")
PAPER_TRANSACTION_ID_RE = re.compile(r"plt-[0-9a-f]{64}")
PAPER_SNAPSHOT_ID_RE = re.compile(r"pls-[0-9a-f]{64}")
PAPER_BRIDGE_ID_RE = re.compile(r"plb-[0-9a-f]{64}")
PAPER_PROJECTION_ID_RE = re.compile(r"plp-[0-9a-f]{64}")

LOCAL_ID_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}")

DOMAIN_PROFILES = {"philosophy", "mathematics", "mixed"}
GRAPH_KINDS = {"logic", "audit"}
REPRESENTATION_KINDS = {
    "source_literal",
    "source_paraphrase",
    "researcher_reconstruction",
    "local_emendation",
    "official_erratum",
}
ATTRIBUTIONS = {
    "author",
    "cited_author",
    "interlocutor",
    "objection",
    "editor",
    "researcher",
}
DISCOURSE_ROLES = {
    "premise",
    "intermediate_conclusion",
    "headline_conclusion",
    "theorem",
    "lemma",
    "objection",
    "reply",
    "evidence",
    "background",
}
CONTENT_TYPES = {
    "empirical",
    "conceptual",
    "normative",
    "definitional",
    "methodological",
    "metalinguistic",
    "mathematical",
}
MODALITIES = {
    "asserted",
    "possible",
    "necessary",
    "defeasible",
    "normative",
    "conditional",
    "interrogative",
}
INFERENCE_KINDS = {
    "deductive",
    "inductive",
    "abductive",
    "analogical",
    "default_presumption",
    "burden_shift",
    "conceptual_bridge",
    "normative_bridge",
    "causal",
    "mathematical_derivation",
    "definition_expansion",
    "case_split",
    "proof_by_contradiction",
    "other",
}
INFERENCE_STRENGTHS = {"strict", "defeasible"}
AUTHORIAL_STATUSES = {
    "explicit",
    "enthymematic",
    "researcher_reconstructed",
}

PAPER_RELATION_TYPES = {
    "contains",
    "anchors",
    "premise_of",
    "concludes",
    "uses_definition",
    "variant_of",
    "defeats",
    "targets",
    "audits",
    "evidence_for",
    "counterexample_targets",
    "repairs",
    "responds_to",
    "assesses",
    "challenges_audit",
    "disposes",
    "supersedes_audit",
}

REVIEW_PROFILES_BY_GRAPH_KIND = {
    "logic": ("source_fidelity", "graph_structure"),
    "audit": ("target_binding", "audit_reasoning"),
}
REVIEW_GLOBAL_CHECKS = {
    "source_fidelity": {
        "artifact_hash",
        "span_alignment",
        "transcription",
        "attribution",
        "operator_ledger",
        "formula_glyphs",
    },
    "graph_structure": {
        "endpoint_direction",
        "premise_completeness",
        "inference_kind",
        "origin_separation",
        "headline_reachability",
        "coverage",
    },
    "target_binding": {
        "exact_target",
        "evidence_anchor",
        "graph_version",
        "representation_identity",
    },
    "audit_reasoning": {
        "objection_strength",
        "counterexample_validity",
        "repair_vs_refutation",
        "domain_profile_boundary",
        "evidence_proportionality",
    },
}

PHILOSOPHY_DIALECTICAL_EFFECTS = {
    "clarification_only",
    "trivial_exception",
    "local_repair",
    "scope_revision",
    "substantive_revision",
    "refutes_variant",
    "refutes_core",
    "indeterminate",
}
MATHEMATICS_DIALECTICAL_EFFECTS = {
    "not_a_counterexample",
    "refutes_exact_claim",
    "corrected_statement_candidate",
    "indeterminate",
}
LOGICAL_EFFECTS = {
    "no_refutation",
    "refutes_exact_representation",
    "indeterminate",
}

BRIDGE_RELATIONS = {
    "exploration_prompted_by_source",
    "exploration_checks_reconstruction",
    "audit_supported_by_exploration",
    "exploration_challenges_audit",
    "audit_challenges_exploration",
}

_HIGH_RISK_TOKEN_SPECS = (
    ("only if", "conditional"),
    ("if and only if", "conditional"),
    ("for every", "quantifier"),
    ("for all", "quantifier"),
    ("there exists", "quantifier"),
    ("does not", "negation"),
    ("do not", "negation"),
    ("cannot", "modal"),
    ("must not", "negation"),
    ("not", "negation"),
    ("no", "negation"),
    ("never", "negation"),
    ("without", "negation"),
    ("unless", "conditional"),
    ("only", "conditional"),
    ("all", "quantifier"),
    ("every", "quantifier"),
    ("some", "quantifier"),
    ("exists", "quantifier"),
    ("may", "modal"),
    ("might", "modal"),
    ("must", "modal"),
    ("can", "modal"),
    ("ought", "normative"),
    ("should", "normative"),
    ("if", "conditional"),
    ("所有", "quantifier"),
    ("每个", "quantifier"),
    ("存在", "quantifier"),
    ("不", "negation"),
    ("无", "negation"),
    ("可能", "modal"),
    ("必须", "modal"),
    ("应当", "normative"),
    ("如果", "conditional"),
    ("除非", "conditional"),
    ("∀", "quantifier"),
    ("∃", "quantifier"),
    ("≤", "comparator"),
    ("≥", "comparator"),
    ("≠", "comparator"),
    ("<", "comparator"),
    (">", "comparator"),
)


def _id(prefix: str, payload: dict[str, Any], key: str) -> str:
    semantic = {name: value for name, value in payload.items() if name != key}
    return prefix + sha256_json(semantic)


def validate_paper_node_id(value: str) -> str:
    if not isinstance(value, str) or PAPER_NODE_ID_RE.fullmatch(value) is None:
        raise ValueError(f"invalid paper node id: {value!r}")
    return value


def validate_paper_edge_id(value: str) -> str:
    if not isinstance(value, str) or PAPER_EDGE_ID_RE.fullmatch(value) is None:
        raise ValueError(f"invalid paper edge id: {value!r}")
    return value


def validate_paper_object_id(value: str) -> str:
    if not isinstance(value, str) or PAPER_OBJECT_ID_RE.fullmatch(value) is None:
        raise ValueError(f"invalid paper object id: {value!r}")
    return value


def validate_paper_revision_id(value: str) -> str:
    if not isinstance(value, str) or PAPER_REVISION_ID_RE.fullmatch(value) is None:
        raise ValueError(f"invalid paper revision id: {value!r}")
    return value


def validate_paper_review_id(value: str) -> str:
    if not isinstance(value, str) or PAPER_REVIEW_ID_RE.fullmatch(value) is None:
        raise ValueError(f"invalid paper review id: {value!r}")
    return value


def validate_paper_transaction_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or PAPER_TRANSACTION_ID_RE.fullmatch(value) is None
    ):
        raise ValueError(f"invalid paper transaction id: {value!r}")
    return value


def validate_paper_snapshot_id(value: str) -> str:
    if not isinstance(value, str) or PAPER_SNAPSHOT_ID_RE.fullmatch(value) is None:
        raise ValueError(f"invalid paper snapshot id: {value!r}")
    return value


def validate_local_id(value: str) -> str:
    if not isinstance(value, str) or LOCAL_ID_RE.fullmatch(value) is None:
        raise ValueError(f"invalid paper local id: {value!r}")
    if value == "__source__":
        raise ValueError("__source__ is reserved for the exact source artifact")
    return value


def _require_sha256(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if allow_empty and value == "":
        return ""
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{label} must be a full lowercase SHA-256")
    return value


def _require_string_list(
    value: Any,
    label: str,
    *,
    nonempty: bool = False,
) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a list of strings")
    if nonempty and not value:
        raise ValueError(f"{label} must be nonempty")
    if any(not item.strip() for item in value):
        raise ValueError(f"{label} must contain nonempty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must not contain duplicates")
    return list(value)


def _validate_enum(value: Any, allowed: set[str], label: str) -> str:
    if value not in allowed:
        raise ValueError(f"{label} is invalid: {value!r}")
    return str(value)


def scan_high_risk_operators(text: str) -> list[dict[str, Any]]:
    """Return deterministic surface operators that require a disposition.

    Longer English phrases consume their spans first, so ``does not`` is one
    load-bearing item rather than a second, overlapping ``not`` item.
    """

    if not isinstance(text, str):
        raise ValueError("operator scan text must be a string")
    occupied: set[int] = set()
    raw: list[tuple[int, int, str, str]] = []
    for token, kind in _HIGH_RISK_TOKEN_SPECS:
        if token.isascii() and token[0].isalnum():
            pattern = re.compile(
                rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])",
                re.IGNORECASE,
            )
        else:
            pattern = re.compile(re.escape(token))
        for match in pattern.finditer(text):
            positions = set(range(match.start(), match.end()))
            if positions.intersection(occupied):
                continue
            occupied.update(positions)
            raw.append((match.start(), match.end(), match.group(0), kind))
    raw.sort(key=lambda item: (item[0], item[1], item[2].casefold()))
    counts: dict[str, int] = {}
    result: list[dict[str, Any]] = []
    for start, end, surface, kind in raw:
        key = surface.casefold()
        occurrence = counts.get(key, 0)
        counts[key] = occurrence + 1
        result.append(
            {
                "token": surface,
                "occurrence": occurrence,
                "kind": kind,
                "start": start,
                "end": end,
            }
        )
    return result


def validate_operator_ledger(
    ledger: Any,
    *,
    text: str,
    label: str,
) -> list[dict[str, Any]]:
    if not isinstance(ledger, list) or any(not isinstance(item, dict) for item in ledger):
        raise ValueError(f"{label} operator_ledger must be a list of objects")
    normalized: list[dict[str, Any]] = []
    ids: set[str] = set()
    surface_entries: dict[tuple[str, int], dict[str, Any]] = {}
    for item in ledger:
        require_exact_keys(
            item,
            required={
                "operator_id",
                "token",
                "occurrence",
                "kind",
                "scope",
                "disposition",
                "depends_on",
            },
            label=f"{label} operator ledger entry",
        )
        operator_id = require_string(item, "operator_id")
        if operator_id in ids:
            raise ValueError(f"{label} has duplicate operator_id {operator_id}")
        ids.add(operator_id)
        token = require_string(item, "token")
        occurrence = item["occurrence"]
        if (
            isinstance(occurrence, bool)
            or not isinstance(occurrence, int)
            or occurrence < 0
        ):
            raise ValueError(f"{label} operator occurrence must be nonnegative")
        kind = _validate_enum(
            item["kind"],
            {
                "negation",
                "quantifier",
                "modal",
                "conditional",
                "comparator",
                "normative",
            },
            f"{label} operator kind",
        )
        require_string(item, "scope")
        disposition = _validate_enum(
            item["disposition"],
            {"logical", "non_logical", "implicit"},
            f"{label} operator disposition",
        )
        depends_on = _require_string_list(
            item["depends_on"],
            f"{label} operator depends_on",
        )
        if disposition == "implicit":
            if token != "<implicit>":
                raise ValueError(
                    f"{label} implicit operator token must be <implicit>"
                )
        else:
            key = (token.casefold(), occurrence)
            if key in surface_entries:
                raise ValueError(
                    f"{label} duplicates surface operator {token!r} occurrence "
                    f"{occurrence}"
                )
            surface_entries[key] = item
        normalized.append(
            {
                **item,
                "kind": kind,
                "disposition": disposition,
                "depends_on": depends_on,
            }
        )
    for item in normalized:
        unknown = set(item["depends_on"]).difference(ids)
        if unknown:
            raise ValueError(
                f"{label} operator dependency is unknown: "
                + ", ".join(sorted(unknown))
            )
        if item["operator_id"] in item["depends_on"]:
            raise ValueError(f"{label} operator depends on itself")
    graph = {
        item["operator_id"]: set(item["depends_on"]) for item in normalized
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(operator_id: str) -> None:
        if operator_id in visiting:
            raise ValueError(f"{label} operator dependency cycle")
        if operator_id in visited:
            return
        visiting.add(operator_id)
        for dependency in graph[operator_id]:
            visit(dependency)
        visiting.remove(operator_id)
        visited.add(operator_id)

    for operator_id in sorted(graph):
        visit(operator_id)
    scanned = scan_high_risk_operators(text)
    scanned_keys = {
        (item["token"].casefold(), item["occurrence"]): item for item in scanned
    }
    missing = sorted(set(scanned_keys).difference(surface_entries))
    extra = sorted(set(surface_entries).difference(scanned_keys))
    if missing:
        rendered = ", ".join(f"{token}[{index}]" for token, index in missing)
        raise ValueError(f"{label} operator ledger misses: {rendered}")
    if extra:
        rendered = ", ".join(f"{token}[{index}]" for token, index in extra)
        raise ValueError(
            f"{label} operator ledger has unanchored surface entries: {rendered}"
        )
    for key, scanned_item in scanned_keys.items():
        if surface_entries[key]["kind"] != scanned_item["kind"]:
            raise ValueError(
                f"{label} operator kind mismatch for "
                f"{scanned_item['token']!r} occurrence {scanned_item['occurrence']}"
            )
    return normalized


def validate_source(payload: dict[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        payload,
        required={
            "artifact_sha256",
            "artifact_locator",
            "title",
            "version",
            "mime_type",
            "retrieved_at",
            "inspection_methods",
        },
        label="paper source",
    )
    _require_sha256(payload["artifact_sha256"], "paper source artifact_sha256")
    for key in ("artifact_locator", "title", "version", "mime_type", "retrieved_at"):
        require_string(payload, key)
    methods = _require_string_list(
        payload["inspection_methods"],
        "paper source inspection_methods",
        nonempty=True,
    )
    if not {"rendered_primary", "source_tex"}.intersection(methods):
        raise ValueError(
            "paper source requires rendered_primary or source_tex inspection"
        )
    return payload


def _validate_locator(locator: Any, label: str) -> dict[str, Any]:
    if not isinstance(locator, dict):
        raise ValueError(f"{label} locator must be an object")
    require_exact_keys(
        locator,
        required={
            "kind",
            "pdf_page_index",
            "printed_page_label",
            "region",
        },
        label=f"{label} locator",
    )
    _validate_enum(
        locator["kind"],
        {"pdf", "tex", "html", "other"},
        f"{label} locator kind",
    )
    page = locator["pdf_page_index"]
    if isinstance(page, bool) or not isinstance(page, int) or page < -1:
        raise ValueError(f"{label} pdf_page_index must be -1 or nonnegative")
    require_string(locator, "printed_page_label", allow_empty=True)
    require_string(locator, "region")
    if locator["kind"] == "pdf" and page < 0:
        raise ValueError(f"{label} PDF locator needs a nonnegative page index")
    return locator


def validate_source_unit(payload: dict[str, Any], label: str) -> dict[str, Any]:
    require_exact_keys(
        payload,
        required={
            "unit_kind",
            "order",
            "locator",
            "text",
            "text_sha256",
            "speaker",
            "inspection_methods",
            "render_sha256",
            "context_before",
            "context_after",
            "operator_ledger",
        },
        label=label,
    )
    _validate_enum(
        payload["unit_kind"],
        {"section", "paragraph", "sentence", "formula", "footnote", "table"},
        f"{label} unit_kind",
    )
    order = payload["order"]
    if isinstance(order, bool) or not isinstance(order, int) or order < 0:
        raise ValueError(f"{label} order must be nonnegative")
    _validate_locator(payload["locator"], label)
    text = require_string(payload, "text")
    if payload["text_sha256"] != sha256_bytes(text.encode("utf-8")):
        raise ValueError(f"{label} text_sha256 mismatch")
    _validate_enum(
        payload["speaker"],
        {
            "author",
            "quoted_source",
            "interlocutor",
            "objection",
            "editor",
            "other",
        },
        f"{label} speaker",
    )
    methods = _require_string_list(
        payload["inspection_methods"],
        f"{label} inspection_methods",
        nonempty=True,
    )
    render_hash = _require_sha256(
        payload["render_sha256"],
        f"{label} render_sha256",
        allow_empty=True,
    )
    require_string(payload, "context_before", allow_empty=True)
    require_string(payload, "context_after", allow_empty=True)
    validate_operator_ledger(
        payload["operator_ledger"],
        text=text,
        label=label,
    )
    if scan_high_risk_operators(text):
        if not {"rendered_primary", "source_tex"}.intersection(methods):
            raise ValueError(
                f"{label} is operator-sensitive and needs rendered-primary "
                "or source-TeX inspection"
            )
        if not render_hash:
            raise ValueError(
                f"{label} is operator-sensitive and needs render_sha256"
            )
    return payload


def validate_claim(payload: dict[str, Any], label: str) -> dict[str, Any]:
    require_exact_keys(
        payload,
        required={
            "representation_kind",
            "attribution",
            "discourse_role",
            "content_type",
            "statement",
            "statement_sha256",
            "source_unit_ids",
            "semantic_diff",
            "modality",
            "scope_notes",
            "operator_ledger",
            "definition_ids",
            "parent_claim_id",
        },
        label=label,
    )
    representation = _validate_enum(
        payload["representation_kind"],
        REPRESENTATION_KINDS,
        f"{label} representation_kind",
    )
    attribution = _validate_enum(
        payload["attribution"], ATTRIBUTIONS, f"{label} attribution"
    )
    _validate_enum(
        payload["discourse_role"], DISCOURSE_ROLES, f"{label} discourse_role"
    )
    _validate_enum(payload["content_type"], CONTENT_TYPES, f"{label} content_type")
    statement = require_string(payload, "statement")
    if payload["statement_sha256"] != sha256_bytes(statement.encode("utf-8")):
        raise ValueError(f"{label} statement_sha256 mismatch")
    source_units = _require_string_list(
        payload["source_unit_ids"],
        f"{label} source_unit_ids",
    )
    semantic_diff = require_string(payload, "semantic_diff", allow_empty=True)
    _validate_enum(payload["modality"], MODALITIES, f"{label} modality")
    require_string(payload, "scope_notes")
    validate_operator_ledger(
        payload["operator_ledger"],
        text=statement,
        label=label,
    )
    _require_string_list(payload["definition_ids"], f"{label} definition_ids")
    parent = require_string(payload, "parent_claim_id", allow_empty=True)
    if representation == "source_literal":
        if not source_units:
            raise ValueError(f"{label} source_literal needs source_unit_ids")
        if semantic_diff or parent:
            raise ValueError(
                f"{label} source_literal cannot have semantic_diff or parent"
            )
        if attribution == "researcher":
            raise ValueError(
                f"{label} source_literal cannot be attributed to researcher"
            )
    elif representation in {
        "source_paraphrase",
        "researcher_reconstruction",
        "local_emendation",
    }:
        if not semantic_diff:
            raise ValueError(f"{label} nonliteral claim needs semantic_diff")
    if representation == "local_emendation" and not parent:
        raise ValueError(f"{label} local_emendation needs parent_claim_id")
    if (
        representation == "local_emendation"
        and attribution not in {"researcher", "editor"}
    ):
        raise ValueError(
            f"{label} local_emendation must be attributed to a researcher "
            "or editor, not silently to the source author"
        )
    if representation == "official_erratum" and not parent:
        raise ValueError(f"{label} official_erratum needs parent_claim_id")
    if representation == "researcher_reconstruction" and attribution != "researcher":
        raise ValueError(
            f"{label} researcher reconstruction must be attributed to researcher"
        )
    return payload


def validate_definition(payload: dict[str, Any], label: str) -> dict[str, Any]:
    require_exact_keys(
        payload,
        required={
            "representation_kind",
            "attribution",
            "definition_kind",
            "term",
            "definiens",
            "source_unit_ids",
            "semantic_diff",
            "scope_notes",
            "operator_ledger",
        },
        label=label,
    )
    representation = _validate_enum(
        payload["representation_kind"],
        REPRESENTATION_KINDS,
        f"{label} representation_kind",
    )
    attribution = _validate_enum(
        payload["attribution"], ATTRIBUTIONS, f"{label} attribution"
    )
    _validate_enum(
        payload["definition_kind"],
        {"stipulative", "lexical", "mathematical", "operational", "contested"},
        f"{label} definition_kind",
    )
    term = require_string(payload, "term")
    definiens = require_string(payload, "definiens")
    source_units = _require_string_list(
        payload["source_unit_ids"],
        f"{label} source_unit_ids",
    )
    semantic_diff = require_string(payload, "semantic_diff", allow_empty=True)
    require_string(payload, "scope_notes")
    validate_operator_ledger(
        payload["operator_ledger"],
        text=f"{term}: {definiens}",
        label=label,
    )
    if representation == "source_literal":
        if not source_units or semantic_diff:
            raise ValueError(
                f"{label} literal definition needs sources and no semantic_diff"
            )
    elif not semantic_diff:
        raise ValueError(f"{label} nonliteral definition needs semantic_diff")
    if representation == "researcher_reconstruction" and attribution != "researcher":
        raise ValueError(
            f"{label} researcher reconstruction must be attributed to researcher"
        )
    if (
        representation == "local_emendation"
        and attribution not in {"researcher", "editor"}
    ):
        raise ValueError(
            f"{label} local_emendation must be attributed to a researcher "
            "or editor, not silently to the source author"
        )
    return payload


def validate_formula(payload: dict[str, Any], label: str) -> dict[str, Any]:
    require_exact_keys(
        payload,
        required={
            "representation_kind",
            "attribution",
            "expression",
            "expression_sha256",
            "source_unit_ids",
            "semantic_diff",
            "scope_notes",
            "glyph_ledger",
        },
        label=label,
    )
    representation = _validate_enum(
        payload["representation_kind"],
        REPRESENTATION_KINDS,
        f"{label} representation_kind",
    )
    attribution = _validate_enum(
        payload["attribution"], ATTRIBUTIONS, f"{label} attribution"
    )
    expression = require_string(payload, "expression")
    if payload["expression_sha256"] != sha256_bytes(expression.encode("utf-8")):
        raise ValueError(f"{label} expression_sha256 mismatch")
    source_units = _require_string_list(
        payload["source_unit_ids"],
        f"{label} source_unit_ids",
    )
    semantic_diff = require_string(payload, "semantic_diff", allow_empty=True)
    require_string(payload, "scope_notes")
    glyphs = payload["glyph_ledger"]
    if not isinstance(glyphs, list) or not glyphs or any(
        not isinstance(item, dict) for item in glyphs
    ):
        raise ValueError(f"{label} glyph_ledger must be nonempty objects")
    for glyph in glyphs:
        require_exact_keys(
            glyph,
            required={"token", "role", "finding"},
            label=f"{label} glyph",
        )
        for key in ("token", "role", "finding"):
            require_string(glyph, key)
    if representation == "source_literal":
        if not source_units or semantic_diff:
            raise ValueError(
                f"{label} literal formula needs sources and no semantic_diff"
            )
    elif not semantic_diff:
        raise ValueError(f"{label} nonliteral formula needs semantic_diff")
    if representation == "researcher_reconstruction" and attribution != "researcher":
        raise ValueError(
            f"{label} researcher reconstruction must be attributed to researcher"
        )
    if (
        representation == "local_emendation"
        and attribution not in {"researcher", "editor"}
    ):
        raise ValueError(
            f"{label} local_emendation must be attributed to a researcher "
            "or editor, not silently to the source author"
        )
    return payload


def validate_inference(payload: dict[str, Any], label: str) -> dict[str, Any]:
    require_exact_keys(
        payload,
        required={
            "premise_ids",
            "conclusion_id",
            "inference_kind",
            "strength",
            "authorial_status",
            "source_unit_ids",
            "bridge_claim_ids",
            "defeater_claim_ids",
            "rationale",
        },
        label=label,
    )
    premises = _require_string_list(
        payload["premise_ids"], f"{label} premise_ids", nonempty=True
    )
    conclusion = require_string(payload, "conclusion_id")
    if conclusion in premises:
        raise ValueError(f"{label} conclusion cannot also be a premise")
    kind = _validate_enum(
        payload["inference_kind"], INFERENCE_KINDS, f"{label} inference_kind"
    )
    strength = _validate_enum(
        payload["strength"], INFERENCE_STRENGTHS, f"{label} strength"
    )
    authorial = _validate_enum(
        payload["authorial_status"],
        AUTHORIAL_STATUSES,
        f"{label} authorial_status",
    )
    source_units = _require_string_list(
        payload["source_unit_ids"], f"{label} source_unit_ids"
    )
    bridge_ids = _require_string_list(
        payload["bridge_claim_ids"], f"{label} bridge_claim_ids"
    )
    defeater_ids = _require_string_list(
        payload["defeater_claim_ids"], f"{label} defeater_claim_ids"
    )
    require_string(payload, "rationale")
    if authorial == "explicit" and not source_units:
        raise ValueError(f"{label} explicit inference needs source units")
    if kind in {"default_presumption", "burden_shift", "analogical"}:
        if strength != "defeasible":
            raise ValueError(f"{label} {kind} inference must be defeasible")
    if kind in {"normative_bridge", "conceptual_bridge"} and not bridge_ids:
        raise ValueError(f"{label} bridge inference needs bridge_claim_ids")
    if not set(bridge_ids).issubset(premises):
        raise ValueError(f"{label} bridge claims must be explicit premises")
    if set(defeater_ids).intersection(premises):
        raise ValueError(f"{label} defeaters cannot also be premises")
    if conclusion in defeater_ids:
        raise ValueError(f"{label} conclusion cannot defeat its own inference")
    return payload


def validate_paper_target(payload: dict[str, Any], label: str) -> dict[str, Any]:
    require_exact_keys(
        payload,
        required={"target_role", "claim_id", "rationale"},
        label=label,
    )
    _validate_enum(
        payload["target_role"], {"headline", "supporting"}, f"{label} target_role"
    )
    require_string(payload, "claim_id")
    require_string(payload, "rationale")
    return payload


def validate_audit_finding(payload: dict[str, Any], label: str) -> dict[str, Any]:
    require_exact_keys(
        payload,
        required={
            "finding_kind",
            "severity",
            "status",
            "target_id",
            "claim",
            "rationale",
            "evidence_unit_ids",
            "observed_excerpt",
            "compared_text",
            "load_bearing_tokens",
        },
        label=label,
    )
    _validate_enum(
        payload["finding_kind"],
        {
            "source_misread",
            "negation_or_polarity",
            "quantifier_scope",
            "modality",
            "attribution",
            "formula_glyph",
            "missing_premise",
            "invalid_inference",
            "equivocation",
            "unsupported_bridge",
            "scope_overreach",
            "circularity",
            "definition_gap",
            "coverage_gap",
            "other",
        },
        f"{label} finding_kind",
    )
    _validate_enum(
        payload["severity"],
        {"minor", "material", "critical"},
        f"{label} severity",
    )
    _validate_enum(
        payload["status"],
        {"open", "corroborated", "challenged", "resolved", "indeterminate"},
        f"{label} status",
    )
    validate_paper_node_id(require_string(payload, "target_id"))
    require_string(payload, "claim")
    require_string(payload, "rationale")
    evidence = _require_string_list(
        payload["evidence_unit_ids"],
        f"{label} evidence_unit_ids",
    )
    excerpt = require_string(payload, "observed_excerpt", allow_empty=True)
    require_string(payload, "compared_text", allow_empty=True)
    tokens = _require_string_list(
        payload["load_bearing_tokens"],
        f"{label} load_bearing_tokens",
    )
    if payload["finding_kind"] in {
        "source_misread",
        "negation_or_polarity",
        "quantifier_scope",
        "modality",
        "attribution",
        "formula_glyph",
    }:
        if not evidence or not excerpt or not tokens:
            raise ValueError(
                f"{label} source-sensitive finding needs evidence, exact excerpt, "
                "and load-bearing tokens"
            )
    return payload


def _validate_witnesses(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{label} must be a list of objects")
    seen: set[str] = set()
    for item in value:
        require_exact_keys(
            item,
            required={"premise_id", "status", "witness"},
            label=f"{label} entry",
        )
        premise_id = require_string(item, "premise_id")
        if premise_id in seen:
            raise ValueError(f"{label} duplicates premise {premise_id}")
        seen.add(premise_id)
        _validate_enum(
            item["status"],
            {"satisfied", "not_satisfied", "uncertain"},
            f"{label} status",
        )
        require_string(item, "witness")
    return value


def validate_counterexample(payload: dict[str, Any], label: str) -> dict[str, Any]:
    require_exact_keys(
        payload,
        required={
            "target_id",
            "construction",
            "premise_witnesses",
            "conclusion_failure",
            "interpretation_preserved",
            "interpretation_notes",
            "nontriviality",
            "evidence",
            "provisional_logical_effect",
        },
        label=label,
    )
    validate_paper_node_id(require_string(payload, "target_id"))
    require_string(payload, "construction")
    witnesses = _validate_witnesses(
        payload["premise_witnesses"], f"{label} premise_witnesses"
    )
    failure = payload["conclusion_failure"]
    if not isinstance(failure, dict):
        raise ValueError(f"{label} conclusion_failure must be an object")
    require_exact_keys(
        failure,
        required={"status", "witness"},
        label=f"{label} conclusion_failure",
    )
    _validate_enum(
        failure["status"],
        {"fails", "does_not_fail", "uncertain"},
        f"{label} conclusion_failure status",
    )
    require_string(failure, "witness")
    if not isinstance(payload["interpretation_preserved"], bool):
        raise ValueError(f"{label} interpretation_preserved must be boolean")
    require_string(payload, "interpretation_notes")
    _validate_enum(
        payload["nontriviality"],
        {"trivial", "substantive", "contested"},
        f"{label} nontriviality",
    )
    evidence = _require_string_list(payload["evidence"], f"{label} evidence")
    effect = _validate_enum(
        payload["provisional_logical_effect"],
        LOGICAL_EFFECTS,
        f"{label} provisional_logical_effect",
    )
    can_refute = (
        all(item["status"] == "satisfied" for item in witnesses)
        and failure["status"] == "fails"
        and payload["interpretation_preserved"]
        and bool(evidence)
    )
    if effect == "refutes_exact_representation" and not can_refute:
        raise ValueError(
            f"{label} cannot claim exact refutation without satisfied premises, "
            "a conclusion-failure witness, preserved interpretation, and evidence"
        )
    if effect == "no_refutation" and can_refute:
        raise ValueError(
            f"{label} mechanically demonstrates exact refutation but labels none"
        )
    return payload


def validate_repair_proposal(payload: dict[str, Any], label: str) -> dict[str, Any]:
    require_exact_keys(
        payload,
        required={
            "target_id",
            "addresses_ids",
            "repair_kind",
            "changes",
            "core_preservation",
            "ad_hoc_risk",
            "new_statement",
            "justification",
        },
        label=label,
    )
    validate_paper_node_id(require_string(payload, "target_id"))
    _require_string_list(
        payload["addresses_ids"], f"{label} addresses_ids", nonempty=True
    )
    _validate_enum(
        payload["repair_kind"],
        {
            "define_term",
            "add_premise",
            "narrow_scope",
            "weaken_conclusion",
            "correct_typo",
            "replace_claim",
            "other",
        },
        f"{label} repair_kind",
    )
    changes = payload["changes"]
    if not isinstance(changes, list) or not changes or any(
        not isinstance(item, dict) for item in changes
    ):
        raise ValueError(f"{label} changes must be nonempty objects")
    for change in changes:
        require_exact_keys(
            change,
            required={"field", "before", "after", "rationale"},
            label=f"{label} change",
        )
        for key in ("field", "before", "after", "rationale"):
            require_string(change, key, allow_empty=(key in {"before", "after"}))
        if change["before"] == change["after"]:
            raise ValueError(f"{label} change must have a semantic difference")
    _validate_enum(
        payload["core_preservation"],
        {"preserved", "not_preserved", "indeterminate"},
        f"{label} core_preservation",
    )
    _validate_enum(
        payload["ad_hoc_risk"],
        {"low", "medium", "high"},
        f"{label} ad_hoc_risk",
    )
    require_string(payload, "new_statement")
    require_string(payload, "justification")
    return payload


def validate_impact_assessment(
    payload: dict[str, Any],
    label: str,
    *,
    domain_profile: str,
) -> dict[str, Any]:
    require_exact_keys(
        payload,
        required={
            "challenge_id",
            "repair_id",
            "domain_profile",
            "logical_effect",
            "dialectical_effect",
            "core_target_id",
            "core_preservation",
            "repair_cost",
            "evidence_strength",
            "justification",
        },
        label=label,
    )
    require_string(payload, "challenge_id")
    repair_id = require_string(payload, "repair_id", allow_empty=True)
    if payload["domain_profile"] != domain_profile:
        raise ValueError(f"{label} domain_profile mismatches the graph")
    logical = _validate_enum(
        payload["logical_effect"], LOGICAL_EFFECTS, f"{label} logical_effect"
    )
    if domain_profile == "philosophy":
        dialectical = _validate_enum(
            payload["dialectical_effect"],
            PHILOSOPHY_DIALECTICAL_EFFECTS,
            f"{label} dialectical_effect",
        )
    elif domain_profile == "mathematics":
        dialectical = _validate_enum(
            payload["dialectical_effect"],
            MATHEMATICS_DIALECTICAL_EFFECTS,
            f"{label} dialectical_effect",
        )
    else:
        dialectical = require_string(payload, "dialectical_effect")
    validate_paper_node_id(require_string(payload, "core_target_id"))
    preservation = _validate_enum(
        payload["core_preservation"],
        {"preserved", "not_preserved", "indeterminate"},
        f"{label} core_preservation",
    )
    cost = _validate_enum(
        payload["repair_cost"],
        {"none", "local", "substantive", "replacement", "indeterminate"},
        f"{label} repair_cost",
    )
    evidence = _validate_enum(
        payload["evidence_strength"],
        {"demonstrated", "supported", "speculative"},
        f"{label} evidence_strength",
    )
    require_string(payload, "justification")
    if domain_profile == "philosophy":
        if dialectical == "local_repair":
            if not repair_id or preservation != "preserved" or cost != "local":
                raise ValueError(
                    f"{label} local_repair needs a local, core-preserving repair"
                )
        if dialectical == "refutes_core":
            if (
                logical != "refutes_exact_representation"
                or preservation != "not_preserved"
                or evidence != "demonstrated"
                or cost not in {"replacement", "none"}
            ):
                raise ValueError(
                    f"{label} refutes_core requires demonstrated exact refutation "
                    "and no core-preserving repair"
                )
        if dialectical == "refutes_variant" and logical != (
            "refutes_exact_representation"
        ):
            raise ValueError(
                f"{label} refutes_variant requires exact-representation refutation"
            )
    elif domain_profile == "mathematics":
        if dialectical == "refutes_exact_claim" and (
            logical != "refutes_exact_representation"
            or evidence != "demonstrated"
        ):
            raise ValueError(
                f"{label} mathematical exact refutation needs a demonstrated "
                "counterexample to the exact claim"
            )
        if dialectical == "not_a_counterexample" and logical == (
            "refutes_exact_representation"
        ):
            raise ValueError(
                f"{label} mathematical effect contradicts exact refutation"
            )
    return payload


def validate_audit_challenge(payload: dict[str, Any], label: str) -> dict[str, Any]:
    require_exact_keys(
        payload,
        required={
            "target_audit_id",
            "claim",
            "evidence",
            "status",
            "rationale",
        },
        label=label,
    )
    target = validate_paper_node_id(
        require_string(payload, "target_audit_id")
    )
    if not target.startswith("pan-"):
        raise ValueError(f"{label} must target a paper_audit node")
    require_string(payload, "claim")
    _require_string_list(
        payload["evidence"], f"{label} evidence", nonempty=True
    )
    _validate_enum(
        payload["status"],
        {"open", "corroborated", "challenged", "resolved", "indeterminate"},
        f"{label} status",
    )
    require_string(payload, "rationale")
    return payload


def validate_audit_disposition(
    payload: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    require_exact_keys(
        payload,
        required={
            "target_audit_id",
            "challenge_ids",
            "disposition",
            "replacement_ids",
            "rationale",
        },
        label=label,
    )
    target = validate_paper_node_id(
        require_string(payload, "target_audit_id")
    )
    if not target.startswith("pan-"):
        raise ValueError(f"{label} must dispose a paper_audit node")
    _require_string_list(
        payload["challenge_ids"],
        f"{label} challenge_ids",
        nonempty=True,
    )
    disposition = _validate_enum(
        payload["disposition"],
        {"upheld", "narrowed", "corrected", "withdrawn", "unresolved"},
        f"{label} disposition",
    )
    replacements = _require_string_list(
        payload["replacement_ids"], f"{label} replacement_ids"
    )
    if disposition in {"narrowed", "corrected"} and not replacements:
        raise ValueError(
            f"{label} {disposition} disposition needs replacement_ids"
        )
    if disposition in {"upheld", "withdrawn", "unresolved"} and replacements:
        raise ValueError(
            f"{label} {disposition} disposition cannot name replacements"
        )
    require_string(payload, "rationale")
    return payload


def validate_local_node(
    node: dict[str, Any],
    *,
    graph_kind: str,
    domain_profile: str,
) -> dict[str, Any]:
    require_exact_keys(
        node,
        required={"local_id", "object_type", "payload"},
        label="paper local node",
    )
    local_id = validate_local_id(node["local_id"])
    object_type = _validate_enum(
        node["object_type"], PAPER_OBJECT_TYPES, "paper local node object_type"
    )
    payload = node["payload"]
    if not isinstance(payload, dict):
        raise ValueError(f"paper node {local_id} payload must be an object")
    if graph_kind == "logic" and object_type not in (
        {"source_unit"} | PAPER_RECONSTRUCTION_TYPES
    ):
        raise ValueError(
            f"logic graph cannot contain paper node type {object_type}"
        )
    if graph_kind == "audit" and object_type not in PAPER_AUDIT_TYPES:
        raise ValueError(
            f"audit graph cannot contain paper node type {object_type}"
        )
    label = f"paper node {local_id}"
    if object_type == "source_unit":
        validate_source_unit(payload, label)
    elif object_type == "claim":
        validate_claim(payload, label)
    elif object_type == "definition":
        validate_definition(payload, label)
    elif object_type == "formula":
        validate_formula(payload, label)
    elif object_type == "inference":
        validate_inference(payload, label)
    elif object_type == "paper_target":
        validate_paper_target(payload, label)
    elif object_type == "audit_finding":
        validate_audit_finding(payload, label)
    elif object_type == "counterexample":
        validate_counterexample(payload, label)
    elif object_type == "repair_proposal":
        validate_repair_proposal(payload, label)
    elif object_type == "impact_assessment":
        validate_impact_assessment(
            payload,
            label,
            domain_profile=domain_profile,
        )
    elif object_type == "audit_challenge":
        validate_audit_challenge(payload, label)
    elif object_type == "audit_disposition":
        validate_audit_disposition(payload, label)
    return node


def make_paper_node(
    *,
    project_id: str,
    paper_id: str,
    plane: str,
    object_type: str,
    logical_key: str,
    payload: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    _validate_enum(plane, PAPER_PLANES, "paper node plane")
    expected_plane = (
        "paper_source"
        if object_type in PAPER_SOURCE_TYPES
        else (
            "paper_reconstruction"
            if object_type in PAPER_RECONSTRUCTION_TYPES
            else "paper_audit"
        )
    )
    if plane != expected_plane:
        raise ValueError(
            f"paper node type {object_type} belongs to {expected_plane}, not {plane}"
        )
    prefix = {
        "paper_source": "psn-",
        "paper_reconstruction": "prn-",
        "paper_audit": "pan-",
    }[plane]
    node = {
        "schema_version": 1,
        "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
        "project_id": project_id,
        "paper_id": paper_id,
        "plane": plane,
        "object_type": object_type,
        "logical_key": logical_key,
        "payload": payload,
        "provenance": provenance,
        "truth_effect": "none",
    }
    node["object_id"] = _id(prefix, node, "object_id")
    return node


def validate_paper_node(node: dict[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        node,
        required={
            "schema_version",
            "feature_revision",
            "project_id",
            "paper_id",
            "plane",
            "object_type",
            "logical_key",
            "payload",
            "provenance",
            "truth_effect",
            "object_id",
        },
        label="paper node",
    )
    if node["schema_version"] != 1:
        raise ValueError("paper node schema_version must be 1")
    if node["feature_revision"] != PAPER_LOGIC_FEATURE_REVISION:
        raise ValueError("paper node feature_revision mismatch")
    for key in ("project_id", "paper_id", "logical_key"):
        require_string(node, key)
    plane = _validate_enum(node["plane"], PAPER_PLANES, "paper node plane")
    object_type = _validate_enum(
        node["object_type"], PAPER_OBJECT_TYPES, "paper node object_type"
    )
    expected_plane = (
        "paper_source"
        if object_type in PAPER_SOURCE_TYPES
        else (
            "paper_reconstruction"
            if object_type in PAPER_RECONSTRUCTION_TYPES
            else "paper_audit"
        )
    )
    if plane != expected_plane:
        raise ValueError("paper node type/plane mismatch")
    if not isinstance(node["payload"], dict) or not isinstance(
        node["provenance"], dict
    ):
        raise ValueError("paper node payload/provenance must be objects")
    if node["truth_effect"] != "none":
        raise ValueError("paper node truth_effect must be none")
    object_id = validate_paper_node_id(node["object_id"])
    prefix = {
        "paper_source": "psn-",
        "paper_reconstruction": "prn-",
        "paper_audit": "pan-",
    }[plane]
    if object_id != _id(prefix, node, "object_id"):
        raise ValueError("paper node id/hash mismatch")
    return node


def make_paper_edge(
    *,
    project_id: str,
    paper_id: str,
    plane: str,
    relation_type: str,
    source_id: str,
    target_id: str,
    payload: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    _validate_enum(plane, PAPER_PLANES, "paper edge plane")
    _validate_enum(
        relation_type, PAPER_RELATION_TYPES, "paper edge relation_type"
    )
    validate_paper_node_id(source_id)
    validate_paper_node_id(target_id)
    if source_id == target_id:
        raise ValueError("paper edge cannot be a self edge")
    prefix = {
        "paper_source": "pse-",
        "paper_reconstruction": "pre-",
        "paper_audit": "pae-",
    }[plane]
    edge = {
        "schema_version": 1,
        "feature_revision": PAPER_LOGIC_FEATURE_REVISION,
        "project_id": project_id,
        "paper_id": paper_id,
        "plane": plane,
        "relation_type": relation_type,
        "source_id": source_id,
        "target_id": target_id,
        "payload": payload,
        "provenance": provenance,
        "truth_effect": "none",
    }
    edge["object_id"] = _id(prefix, edge, "object_id")
    return edge


def validate_paper_edge(edge: dict[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        edge,
        required={
            "schema_version",
            "feature_revision",
            "project_id",
            "paper_id",
            "plane",
            "relation_type",
            "source_id",
            "target_id",
            "payload",
            "provenance",
            "truth_effect",
            "object_id",
        },
        label="paper edge",
    )
    if edge["schema_version"] != 1:
        raise ValueError("paper edge schema_version must be 1")
    if edge["feature_revision"] != PAPER_LOGIC_FEATURE_REVISION:
        raise ValueError("paper edge feature_revision mismatch")
    for key in ("project_id", "paper_id"):
        require_string(edge, key)
    plane = _validate_enum(edge["plane"], PAPER_PLANES, "paper edge plane")
    _validate_enum(
        edge["relation_type"], PAPER_RELATION_TYPES, "paper edge relation_type"
    )
    source = validate_paper_node_id(edge["source_id"])
    target = validate_paper_node_id(edge["target_id"])
    if source == target:
        raise ValueError("paper edge cannot be a self edge")
    if not isinstance(edge["payload"], dict) or not isinstance(
        edge["provenance"], dict
    ):
        raise ValueError("paper edge payload/provenance must be objects")
    if edge["truth_effect"] != "none":
        raise ValueError("paper edge truth_effect must be none")
    object_id = validate_paper_edge_id(edge["object_id"])
    prefix = {
        "paper_source": "pse-",
        "paper_reconstruction": "pre-",
        "paper_audit": "pae-",
    }[plane]
    if object_id != _id(prefix, edge, "object_id"):
        raise ValueError("paper edge id/hash mismatch")
    return edge
