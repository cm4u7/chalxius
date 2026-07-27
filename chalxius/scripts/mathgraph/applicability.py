from __future__ import annotations

import re
from datetime import date
from typing import Any

from .contracts import (
    SHA256_RE,
    require_exact_keys,
    require_string,
    sha256_bytes,
    sha256_json,
)


USE_KINDS = {"result", "definition", "formula"}
STRENGTH_COMPARISONS = {"exact", "source_stronger", "bridged"}
APPLICABILITY_VERDICTS = {"direct", "bridged"}
STABLE_SOURCE_FIELDS = {"doi", "arxiv", "url", "isbn", "mr", "zbmath"}
SOURCE_EVIDENCE_VERSION = 3
LEGACY_SOURCE_EVIDENCE_VERSIONS = {2}
SOURCE_AUDIT_REUSE_DAYS = 30
_ARXIV_VERSION_RE = re.compile(
    r"(?:arXiv:)?(?:[A-Za-z-]+(?:\.[A-Za-z-]+)?/[0-9]{7}|[0-9]{4}\.[0-9]{4,5})v[0-9]+"
)
_VAGUE_VERSIONS = {"current", "latest", "unknown", "unspecified", "n/a", "na"}
_ABSOLUTE_SOURCE_LOCATOR_RE = re.compile(
    r"(?:https?://|doi:|isbn:|mr:|zbmath:).+",
    re.IGNORECASE,
)

_CERTIFICATE_REQUIRED = {
    "source_version",
    "source_locator",
    "source_scope",
    "target_scope",
    "source_conclusion",
    "used_conclusion",
    "hypothesis_map",
    "convention_map",
    "transport_obligations",
    "exclusions_checked",
    "strength_comparison",
    "verdict",
    "proof_anchor",
}
_CERTIFICATE_OPTIONAL = {"bridge_statement", "bridge_proof_anchor"}
_SOURCE_FIDELITY_REQUIRED = {
    "artifact_sha256",
    "inspection_methods",
    "load_bearing_tokens",
    "finding",
    "proof_anchor",
}
_SOURCE_TRACE_REQUIRED = {
    "artifact_sha256",
    "artifact_locator",
    "retrieved_at",
    "statement_locator",
    "statement_text",
    "statement_sha256",
    "inspection_methods",
}
_CRITICAL_AUDIT_V2_REQUIRED = {
    "sanity_checks",
    "issue_searches",
    "assessment",
    "issues",
    "justification",
    "proof_anchor",
}
_CRITICAL_AUDIT_REQUIRED = {
    "profile",
    "risk_triggers",
    "sanity_checks",
    "source_audit",
    "source_audit_reuse",
    "assessment",
    "issues",
    "justification",
    "proof_anchor",
}
_SANITY_CHECK_KINDS = {
    "notation_and_binding",
    "type_and_domain",
    "quantifiers_and_scope",
    "boundary_or_toy_case",
    "statement_proof_consistency",
}
_BASELINE_SANITY_CHECK_KINDS = {
    "notation_and_binding",
    "type_and_domain",
    "quantifiers_and_scope",
}
_SANITY_STATUSES = {"pass", "issue", "not_applicable"}
_ISSUE_SEARCH_KINDS = {
    "version_history",
    "errata",
    "retraction_or_counterexample",
}
_CRITICAL_PROFILES = {"baseline", "strict"}
_RISK_TRIGGERS = {
    "formula_or_sign_sensitive",
    "version_or_text_conflict",
    "suspected_source_defect",
    "official_correction",
    "applicability_bridge_or_transport",
    "boundary_or_toy_case_concern",
    "statement_proof_tension",
    "target_critical",
    "degeneration_or_limit",
    "verifier_escalation",
}
_SOURCE_AUDIT_REQUIRED = {
    "artifact_sha256",
    "artifact_locator",
    "checked_at",
    "issue_searches",
    "unresolved_signals",
    "finding",
    "audit_sha256",
}
_SOURCE_AUDIT_REUSE_REQUIRED = {"mode", "reused_at", "origin"}
_SOURCE_AUDIT_REUSE_MODES = {"fresh", "reused"}
_CRITICAL_ASSESSMENTS = {
    "as_stated",
    "minor_typo_corrected",
    "official_erratum_applied",
}
_CRITICAL_ISSUE_KINDS = {"typo", "official_erratum"}
_CRITICAL_IMPACTS = {"non_semantic", "narrows_only", "material"}
_CRITICAL_ISSUE_REQUIRED = {
    "kind",
    "source_text",
    "corrected_text",
    "evidence",
    "impact",
    "proof_anchor",
}
_CRITICAL_ISSUE_OPTIONAL = {"correction_locator", "correction_sha256"}
_HIGH_FIDELITY_METHODS = {"source_tex", "rendered_primary"}


def _require_nonempty_string_list(
    payload: dict[str, Any], key: str, *, label: str
) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label}.{key} must be a nonempty list of strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{label}.{key} must be a nonempty list of strings")
    return value


def _require_string_list(
    payload: dict[str, Any], key: str, *, label: str
) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{label}.{key} must be a list of nonempty strings")
    return value


def _require_object_list(
    payload: dict[str, Any], key: str, *, label: str, allow_empty: bool
) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list) or (not allow_empty and not value):
        qualifier = "a list" if allow_empty else "a nonempty list"
        raise ValueError(f"{label}.{key} must be {qualifier} of objects")
    if any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{label}.{key} must be a list of objects")
    return value


def _validate_anchor(anchor: str, *, source_key: str, label: str) -> str:
    pattern = re.compile(rf"\[APP:{re.escape(source_key)}:[A-Za-z0-9._-]+\]")
    if pattern.fullmatch(anchor) is None:
        raise ValueError(
            f"{label} must have form [APP:{source_key}:LABEL] with an ASCII label"
        )
    return anchor


def _validate_critical_anchor(anchor: str, *, source_key: str, label: str) -> str:
    pattern = re.compile(rf"\[CRIT:{re.escape(source_key)}:[A-Za-z0-9._-]+\]")
    if pattern.fullmatch(anchor) is None:
        raise ValueError(
            f"{label} must have form [CRIT:{source_key}:LABEL] with an ASCII label"
        )
    return anchor


def _require_iso_date(payload: dict[str, Any], key: str, *, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{key} must be an ISO date YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label}.{key} must be an ISO date YYYY-MM-DD") from exc
    if value != parsed.isoformat():
        raise ValueError(f"{label}.{key} must be an ISO date YYYY-MM-DD")
    return value


def _require_absolute_locator(
    payload: dict[str, Any], key: str, *, label: str
) -> str:
    value = payload.get(key)
    if (
        not isinstance(value, str)
        or not value.strip()
        or _ABSOLUTE_SOURCE_LOCATOR_RE.fullmatch(value.strip()) is None
    ):
        raise ValueError(
            f"{label}.{key} must be an absolute primary-source or search-result locator"
        )
    return value


def _validate_source_fidelity(
    payload: Any,
    *,
    source_key: str,
    proof: str,
    label: str,
) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object")
    require_exact_keys(
        payload,
        required=_SOURCE_FIDELITY_REQUIRED,
        label=label,
    )
    digest = require_string(payload, "artifact_sha256")
    if SHA256_RE.fullmatch(digest) is None:
        raise ValueError(f"{label}.artifact_sha256 must be a full lowercase SHA-256")
    methods = _require_nonempty_string_list(payload, "inspection_methods", label=label)
    if not _HIGH_FIDELITY_METHODS.intersection(methods):
        raise ValueError(
            f"{label}.inspection_methods must include source_tex or rendered_primary; "
            "plain text extraction alone is not source-faithful"
        )
    _require_nonempty_string_list(payload, "load_bearing_tokens", label=label)
    require_string(payload, "finding")
    anchor = require_string(payload, "proof_anchor")
    pattern = re.compile(rf"\[SRC:{re.escape(source_key)}:[A-Za-z0-9._-]+\]")
    if pattern.fullmatch(anchor) is None:
        raise ValueError(
            f"{label}.proof_anchor must have form [SRC:{source_key}:LABEL]"
        )
    occurrences = proof.count(anchor)
    if occurrences != 1:
        raise ValueError(
            f"source-fidelity proof anchor {anchor} must occur exactly once in proof; "
            f"found {occurrences}"
        )


def _validate_source_trace(
    payload: Any,
    *,
    source_key: str,
    arxiv: str | None,
    source_locator: str,
    source_fidelity: Any,
    label: str,
) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object")
    require_exact_keys(payload, required=_SOURCE_TRACE_REQUIRED, label=label)
    digest = require_string(payload, "artifact_sha256")
    if SHA256_RE.fullmatch(digest) is None:
        raise ValueError(f"{label}.artifact_sha256 must be a full lowercase SHA-256")
    artifact_locator = _require_absolute_locator(
        payload,
        "artifact_locator",
        label=label,
    )
    _require_iso_date(payload, "retrieved_at", label=label)
    statement_locator = require_string(payload, "statement_locator")
    if statement_locator != source_locator:
        raise ValueError(
            f"{label}.statement_locator must exactly equal applicability.source_locator"
        )
    statement_text = require_string(payload, "statement_text")
    statement_digest = require_string(payload, "statement_sha256")
    if SHA256_RE.fullmatch(statement_digest) is None:
        raise ValueError(f"{label}.statement_sha256 must be a full lowercase SHA-256")
    computed = sha256_bytes(statement_text.encode("utf-8"))
    if statement_digest != computed:
        raise ValueError(
            f"{label}.statement_sha256 does not match the exact UTF-8 statement_text"
        )
    methods = _require_nonempty_string_list(payload, "inspection_methods", label=label)
    if not _HIGH_FIDELITY_METHODS.intersection(methods):
        raise ValueError(
            f"{label}.inspection_methods must include source_tex or rendered_primary"
        )
    if arxiv is not None:
        normalized_arxiv = arxiv.removeprefix("arXiv:")
        if normalized_arxiv not in artifact_locator:
            raise ValueError(
                f"{label}.artifact_locator must contain the exact versioned arXiv id "
                f"{normalized_arxiv}"
            )
    if source_fidelity is not None:
        fidelity_digest = source_fidelity.get("artifact_sha256")
        if fidelity_digest != digest:
            raise ValueError(
                f"{label}.artifact_sha256 must equal source_fidelity.artifact_sha256"
            )


def _validate_critical_audit_v2(
    payload: Any,
    *,
    source_key: str,
    use_kind: str,
    label: str,
    sanity_kinds: set[str] | None = None,
) -> list[str]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object")
    require_exact_keys(payload, required=_CRITICAL_AUDIT_V2_REQUIRED, label=label)
    required_sanity_kinds = sanity_kinds or _SANITY_CHECK_KINDS

    sanity_checks = _require_object_list(
        payload,
        "sanity_checks",
        label=label,
        allow_empty=False,
    )
    seen_sanity: set[str] = set()
    issue_status_count = 0
    for index, check in enumerate(sanity_checks, 1):
        check_label = f"{label}.sanity_checks[{index}]"
        require_exact_keys(
            check,
            required={"kind", "status", "finding"},
            label=check_label,
        )
        kind = require_string(check, "kind")
        if kind not in required_sanity_kinds:
            raise ValueError(
                f"{check_label}.kind must be one of: "
                + ", ".join(sorted(required_sanity_kinds))
            )
        if kind in seen_sanity:
            raise ValueError(f"{label}.sanity_checks has duplicate kind {kind}")
        seen_sanity.add(kind)
        status = require_string(check, "status")
        if status not in _SANITY_STATUSES:
            raise ValueError(
                f"{check_label}.status must be one of: "
                + ", ".join(sorted(_SANITY_STATUSES))
            )
        require_string(check, "finding")
        if status == "issue":
            issue_status_count += 1
        if (
            use_kind == "result"
            and kind != "boundary_or_toy_case"
            and status == "not_applicable"
        ):
            raise ValueError(
                f"{check_label}.status cannot be not_applicable for a result use; "
                "only boundary_or_toy_case may be inapplicable with a concrete reason"
            )
    if seen_sanity != required_sanity_kinds:
        missing = sorted(required_sanity_kinds.difference(seen_sanity))
        extra = sorted(seen_sanity.difference(required_sanity_kinds))
        raise ValueError(
            f"{label}.sanity_checks must contain each required kind exactly once; "
            f"missing={missing}, extra={extra}"
        )

    issue_searches = _require_object_list(
        payload,
        "issue_searches",
        label=label,
        allow_empty=False,
    )
    seen_searches: set[str] = set()
    for index, search in enumerate(issue_searches, 1):
        search_label = f"{label}.issue_searches[{index}]"
        require_exact_keys(
            search,
            required={"kind", "checked_at", "query", "locator", "finding"},
            label=search_label,
        )
        kind = require_string(search, "kind")
        if kind not in _ISSUE_SEARCH_KINDS:
            raise ValueError(
                f"{search_label}.kind must be one of: "
                + ", ".join(sorted(_ISSUE_SEARCH_KINDS))
            )
        if kind in seen_searches:
            raise ValueError(f"{label}.issue_searches has duplicate kind {kind}")
        seen_searches.add(kind)
        _require_iso_date(search, "checked_at", label=search_label)
        require_string(search, "query")
        _require_absolute_locator(search, "locator", label=search_label)
        require_string(search, "finding")
    if seen_searches != _ISSUE_SEARCH_KINDS:
        missing = sorted(_ISSUE_SEARCH_KINDS.difference(seen_searches))
        extra = sorted(seen_searches.difference(_ISSUE_SEARCH_KINDS))
        raise ValueError(
            f"{label}.issue_searches must contain each required kind exactly once; "
            f"missing={missing}, extra={extra}"
        )

    assessment = require_string(payload, "assessment")
    if assessment not in _CRITICAL_ASSESSMENTS:
        raise ValueError(
            f"{label}.assessment is not admissible; use one of "
            + ", ".join(sorted(_CRITICAL_ASSESSMENTS))
            + " or keep the source use in exploration memory"
        )
    issues = _require_object_list(
        payload,
        "issues",
        label=label,
        allow_empty=True,
    )
    anchors = [
        _validate_critical_anchor(
            require_string(payload, "proof_anchor"),
            source_key=source_key,
            label=f"{label}.proof_anchor",
        )
    ]
    issue_kinds: list[str] = []
    issue_impacts: list[str] = []
    for index, issue in enumerate(issues, 1):
        issue_label = f"{label}.issues[{index}]"
        require_exact_keys(
            issue,
            required=_CRITICAL_ISSUE_REQUIRED,
            optional=_CRITICAL_ISSUE_OPTIONAL,
            label=issue_label,
        )
        kind = require_string(issue, "kind")
        if kind not in _CRITICAL_ISSUE_KINDS:
            raise ValueError(
                f"{issue_label}.kind must be one of: "
                + ", ".join(sorted(_CRITICAL_ISSUE_KINDS))
            )
        issue_kinds.append(kind)
        for key in ("source_text", "corrected_text", "evidence"):
            require_string(issue, key)
        if str(issue["source_text"]).strip() == str(issue["corrected_text"]).strip():
            raise ValueError(
                f"{issue_label}.corrected_text must differ from source_text"
            )
        impact = require_string(issue, "impact")
        if impact not in _CRITICAL_IMPACTS:
            raise ValueError(
                f"{issue_label}.impact must be one of: "
                + ", ".join(sorted(_CRITICAL_IMPACTS))
            )
        issue_impacts.append(impact)
        issue_anchor = _validate_critical_anchor(
            require_string(issue, "proof_anchor"),
            source_key=source_key,
            label=f"{issue_label}.proof_anchor",
        )
        anchors.append(issue_anchor)
        correction_locator = issue.get("correction_locator")
        correction_sha = issue.get("correction_sha256")
        if kind == "official_erratum":
            _require_absolute_locator(
                issue,
                "correction_locator",
                label=issue_label,
            )
            correction_sha = require_string(issue, "correction_sha256")
            if SHA256_RE.fullmatch(correction_sha) is None:
                raise ValueError(
                    f"{issue_label}.correction_sha256 must be a full lowercase SHA-256"
                )
        elif correction_locator is not None or correction_sha is not None:
            if correction_locator is None or correction_sha is None:
                raise ValueError(
                    f"{issue_label}.correction_locator and correction_sha256 "
                    "must be supplied together"
                )
            _require_absolute_locator(
                issue,
                "correction_locator",
                label=issue_label,
            )
            if (
                not isinstance(correction_sha, str)
                or SHA256_RE.fullmatch(correction_sha) is None
            ):
                raise ValueError(
                    f"{issue_label}.correction_sha256 must be a full lowercase SHA-256"
                )

    require_string(payload, "justification")
    if assessment == "as_stated":
        if issues or issue_status_count:
            raise ValueError(
                f"{label}.assessment as_stated requires no declared issue or failed sanity check"
            )
    else:
        if not issues or issue_status_count == 0:
            raise ValueError(
                f"{label}.assessment {assessment} requires a declared issue and an issue sanity check"
            )
    if assessment == "minor_typo_corrected" and (
        any(kind != "typo" for kind in issue_kinds)
        or any(impact != "non_semantic" for impact in issue_impacts)
    ):
        raise ValueError(
            f"{label}.minor_typo_corrected permits only non_semantic typo issues"
        )
    if assessment == "official_erratum_applied" and "official_erratum" not in issue_kinds:
        raise ValueError(
            f"{label}.official_erratum_applied requires an official_erratum issue"
        )

    return anchors


def _validate_source_audit(
    payload: Any,
    *,
    source_trace: dict[str, Any],
    label: str,
) -> tuple[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object")
    require_exact_keys(payload, required=_SOURCE_AUDIT_REQUIRED, label=label)

    artifact_sha256 = require_string(payload, "artifact_sha256")
    if SHA256_RE.fullmatch(artifact_sha256) is None:
        raise ValueError(f"{label}.artifact_sha256 must be a full lowercase SHA-256")
    if artifact_sha256 != source_trace.get("artifact_sha256"):
        raise ValueError(
            f"{label}.artifact_sha256 must equal source_trace.artifact_sha256"
        )
    artifact_locator = _require_absolute_locator(
        payload,
        "artifact_locator",
        label=label,
    )
    if artifact_locator != source_trace.get("artifact_locator"):
        raise ValueError(
            f"{label}.artifact_locator must exactly equal source_trace.artifact_locator"
        )

    checked_at = _require_iso_date(payload, "checked_at", label=label)
    retrieved_at = source_trace.get("retrieved_at")
    if (
        isinstance(retrieved_at, str)
        and date.fromisoformat(checked_at) < date.fromisoformat(retrieved_at)
    ):
        raise ValueError(f"{label}.checked_at cannot predate source_trace.retrieved_at")

    issue_searches = _require_object_list(
        payload,
        "issue_searches",
        label=label,
        allow_empty=False,
    )
    seen_searches: set[str] = set()
    for index, search in enumerate(issue_searches, 1):
        search_label = f"{label}.issue_searches[{index}]"
        require_exact_keys(
            search,
            required={"kind", "query", "locator", "finding"},
            label=search_label,
        )
        kind = require_string(search, "kind")
        if kind not in _ISSUE_SEARCH_KINDS:
            raise ValueError(
                f"{search_label}.kind must be one of: "
                + ", ".join(sorted(_ISSUE_SEARCH_KINDS))
            )
        if kind in seen_searches:
            raise ValueError(f"{label}.issue_searches has duplicate kind {kind}")
        seen_searches.add(kind)
        require_string(search, "query")
        _require_absolute_locator(search, "locator", label=search_label)
        require_string(search, "finding")
    if seen_searches != _ISSUE_SEARCH_KINDS:
        missing = sorted(_ISSUE_SEARCH_KINDS.difference(seen_searches))
        extra = sorted(seen_searches.difference(_ISSUE_SEARCH_KINDS))
        raise ValueError(
            f"{label}.issue_searches must contain each source-level search exactly once; "
            f"missing={missing}, extra={extra}"
        )

    unresolved_signals = _require_string_list(
        payload,
        "unresolved_signals",
        label=label,
    )
    if unresolved_signals:
        raise ValueError(
            f"{label}.unresolved_signals must be empty before source use; "
            "keep unresolved source status in exploration memory"
        )
    require_string(payload, "finding")

    audit_sha256 = require_string(payload, "audit_sha256")
    if SHA256_RE.fullmatch(audit_sha256) is None:
        raise ValueError(f"{label}.audit_sha256 must be a full lowercase SHA-256")
    core = {
        key: payload[key]
        for key in sorted(_SOURCE_AUDIT_REQUIRED.difference({"audit_sha256"}))
    }
    computed = sha256_json(core)
    if audit_sha256 != computed:
        raise ValueError(
            f"{label}.audit_sha256 does not match the canonical source-audit record"
        )
    return audit_sha256, core


def _validate_source_audit_reuse(
    payload: Any,
    *,
    source_audit: dict[str, Any],
    label: str,
) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object")
    require_exact_keys(payload, required=_SOURCE_AUDIT_REUSE_REQUIRED, label=label)
    mode = require_string(payload, "mode")
    if mode not in _SOURCE_AUDIT_REUSE_MODES:
        raise ValueError(
            f"{label}.mode must be one of: "
            + ", ".join(sorted(_SOURCE_AUDIT_REUSE_MODES))
        )
    reused_at = _require_iso_date(payload, "reused_at", label=label)
    origin = require_string(payload, "origin")
    checked_at = date.fromisoformat(str(source_audit["checked_at"]))
    reused_date = date.fromisoformat(reused_at)
    age_days = (reused_date - checked_at).days
    if age_days < 0:
        raise ValueError(f"{label}.reused_at cannot predate source_audit.checked_at")
    if age_days > SOURCE_AUDIT_REUSE_DAYS:
        raise ValueError(
            f"{label} exceeds the {SOURCE_AUDIT_REUSE_DAYS}-day source-audit reuse window"
        )
    if mode == "fresh":
        if origin != "current_submission" or age_days != 0:
            raise ValueError(
                f"{label} fresh evidence requires origin=current_submission and "
                "reused_at equal to source_audit.checked_at"
            )
    elif re.fullmatch(
        r"(?:external_ref:[A-Za-z0-9._-]+|fact:[0-9a-f]{16}:[A-Za-z0-9._-]+)",
        origin,
    ) is None:
        raise ValueError(
            f"{label}.origin for reused evidence must be external_ref:KEY or fact:FACT_ID:KEY"
        )
    return mode, origin


def _validate_critical_audit(
    payload: Any,
    *,
    source_key: str,
    use_kind: str,
    certificate: dict[str, Any],
    source_trace: dict[str, Any],
    label: str,
) -> tuple[list[str], str, dict[str, Any], str, str]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object")
    require_exact_keys(payload, required=_CRITICAL_AUDIT_REQUIRED, label=label)

    profile = require_string(payload, "profile")
    if profile not in _CRITICAL_PROFILES:
        raise ValueError(
            f"{label}.profile must be one of: "
            + ", ".join(sorted(_CRITICAL_PROFILES))
        )
    risk_triggers = _require_string_list(payload, "risk_triggers", label=label)
    if len(set(risk_triggers)) != len(risk_triggers):
        raise ValueError(f"{label}.risk_triggers must not contain duplicates")
    unknown_triggers = sorted(set(risk_triggers).difference(_RISK_TRIGGERS))
    if unknown_triggers:
        raise ValueError(
            f"{label}.risk_triggers contains unknown values: "
            + ", ".join(unknown_triggers)
        )

    source_audit_payload = payload.get("source_audit")
    audit_sha256, audit_core = _validate_source_audit(
        source_audit_payload,
        source_trace=source_trace,
        label=f"{label}.source_audit",
    )
    assert isinstance(source_audit_payload, dict)
    reuse_mode, reuse_origin = _validate_source_audit_reuse(
        payload.get("source_audit_reuse"),
        source_audit=source_audit_payload,
        label=f"{label}.source_audit_reuse",
    )

    sanity_kinds = (
        _BASELINE_SANITY_CHECK_KINDS
        if profile == "baseline"
        else _SANITY_CHECK_KINDS
    )
    issue_searches_v2 = [
        {
            **search,
            "checked_at": source_audit_payload["checked_at"],
        }
        for search in source_audit_payload["issue_searches"]
    ]
    compatibility_payload = {
        "sanity_checks": payload["sanity_checks"],
        "issue_searches": issue_searches_v2,
        "assessment": payload["assessment"],
        "issues": payload["issues"],
        "justification": payload["justification"],
        "proof_anchor": payload["proof_anchor"],
    }
    anchors = _validate_critical_audit_v2(
        compatibility_payload,
        source_key=source_key,
        use_kind=use_kind,
        label=label,
        sanity_kinds=sanity_kinds,
    )

    assessment = str(payload["assessment"])
    issues = payload["issues"]
    transport_obligations = certificate.get("transport_obligations", [])
    bridged = certificate.get("verdict") == "bridged" or bool(transport_obligations)
    if profile == "baseline":
        if risk_triggers:
            raise ValueError(f"{label}.baseline profile requires empty risk_triggers")
        if use_kind == "formula":
            raise ValueError(f"{label}.formula use requires the strict profile")
        if bridged:
            raise ValueError(
                f"{label}.bridged or transported source use requires the strict profile"
            )
        if assessment != "as_stated" or issues:
            raise ValueError(
                f"{label}.baseline profile permits only an issue-free as_stated source"
            )
    elif not risk_triggers:
        raise ValueError(f"{label}.strict profile requires at least one risk trigger")

    trigger_set = set(risk_triggers)
    if use_kind == "formula" and "formula_or_sign_sensitive" not in trigger_set:
        raise ValueError(
            f"{label}.formula use must declare risk trigger formula_or_sign_sensitive"
        )
    if bridged and "applicability_bridge_or_transport" not in trigger_set:
        raise ValueError(
            f"{label}.bridged or transported use must declare risk trigger "
            "applicability_bridge_or_transport"
        )
    if assessment == "minor_typo_corrected" and "suspected_source_defect" not in trigger_set:
        raise ValueError(
            f"{label}.minor typo correction must declare risk trigger "
            "suspected_source_defect"
        )
    if assessment == "official_erratum_applied" and "official_correction" not in trigger_set:
        raise ValueError(
            f"{label}.official erratum must declare risk trigger official_correction"
        )

    return anchors, audit_sha256, audit_core, reuse_mode, reuse_origin


def _validate_mapping_entries(
    certificate: dict[str, Any],
    *,
    field: str,
    required: set[str],
    source_key: str,
    label: str,
    allow_empty: bool,
) -> list[str]:
    entries = _require_object_list(
        certificate, field, label=label, allow_empty=allow_empty
    )
    anchors: list[str] = []
    for index, entry in enumerate(entries, 1):
        entry_label = f"{label}.{field}[{index}]"
        require_exact_keys(entry, required=required, label=entry_label)
        for key in sorted(required.difference({"proof_anchor"})):
            require_string(entry, key)
        anchor = _validate_anchor(
            require_string(entry, "proof_anchor"),
            source_key=source_key,
            label=f"{entry_label}.proof_anchor",
        )
        anchors.append(anchor)
    return anchors


def validate_external_refs_for_submission(
    external_refs: list[dict[str, Any]],
    proof: str,
    *,
    require_formula_fidelity: bool = False,
    require_critical_audit: bool = False,
) -> None:
    """Validate external-source applicability evidence for a new submission.

    New submissions call this with both strict gates enabled. Audits may omit
    ``require_critical_audit`` for historical applicability-only or source-evidence-v2
    certificates; any legacy evidence that is present is still validated. This preserves historical
    readability while requiring new citations to use source-evidence v3: a lightweight baseline
    profile, strict risk escalation, and one hash-bound source-level status audit per exact artifact.
    """

    if not isinstance(external_refs, list) or any(
        not isinstance(item, dict) for item in external_refs
    ):
        raise ValueError("external_refs must be a list of objects")

    seen_keys: set[str] = set()
    seen_anchors: set[str] = set()
    source_audits_by_artifact: dict[str, tuple[str, dict[str, Any], str]] = {}
    for index, ref in enumerate(external_refs, 1):
        label = f"external_refs[{index}]"
        source_key = require_string(ref, "key")
        if re.fullmatch(r"[A-Za-z0-9._-]+", source_key) is None:
            raise ValueError(f"{label}.key must contain only ASCII letters, digits, dot, _ or -")
        if source_key in seen_keys:
            raise ValueError(f"duplicate external source key: {source_key}")
        seen_keys.add(source_key)

        require_string(ref, "title")
        require_string(ref, "cited_for")
        use_kind = require_string(ref, "use_kind")
        if use_kind not in USE_KINDS:
            raise ValueError(
                f"{label}.use_kind must be one of: {', '.join(sorted(USE_KINDS))}"
            )
        source_fidelity = ref.get("source_fidelity")
        if require_formula_fidelity and use_kind == "formula" and source_fidelity is None:
            raise ValueError(
                f"{label}.source_fidelity is required for formula use in workflow schema v3"
            )
        if source_fidelity is not None:
            _validate_source_fidelity(
                source_fidelity,
                source_key=source_key,
                proof=proof,
                label=f"{label}.source_fidelity",
            )
        if not any(
            isinstance(ref.get(field), str) and str(ref[field]).strip()
            for field in STABLE_SOURCE_FIELDS
        ):
            raise ValueError(
                f"{label} needs a stable primary-source identifier: "
                + ", ".join(sorted(STABLE_SOURCE_FIELDS))
            )
        arxiv = ref.get("arxiv")
        if isinstance(arxiv, str) and _ARXIV_VERSION_RE.fullmatch(arxiv.strip()) is None:
            raise ValueError(f"{label}.arxiv must pin an explicit vN source version")

        source_evidence_version = ref.get("source_evidence_version")
        reliability_fields = {
            "source_evidence_version",
            "source_trace",
            "critical_audit",
        }
        has_reliability_field = any(field in ref for field in reliability_fields)

        certificate = ref.get("applicability")
        if not isinstance(certificate, dict):
            raise ValueError(f"{label}.applicability must be an object")
        require_exact_keys(
            certificate,
            required=_CERTIFICATE_REQUIRED,
            optional=_CERTIFICATE_OPTIONAL,
            label=f"{label}.applicability",
        )
        for key in (
            "source_version",
            "source_locator",
            "source_scope",
            "target_scope",
            "source_conclusion",
            "used_conclusion",
        ):
            require_string(certificate, key)
        if str(certificate["source_version"]).strip().casefold() in _VAGUE_VERSIONS:
            raise ValueError(f"{label}.applicability.source_version must be exact, not vague")

        strength = require_string(certificate, "strength_comparison")
        if strength not in STRENGTH_COMPARISONS:
            raise ValueError(
                f"{label}.applicability.strength_comparison must be one of: "
                + ", ".join(sorted(STRENGTH_COMPARISONS))
            )
        verdict = require_string(certificate, "verdict")
        if verdict not in APPLICABILITY_VERDICTS:
            raise ValueError(
                f"{label}.applicability.verdict must be one of: "
                + ", ".join(sorted(APPLICABILITY_VERDICTS))
            )
        if (strength == "bridged") != (verdict == "bridged"):
            raise ValueError(
                f"{label}.applicability bridge verdict and strength comparison disagree"
            )

        anchors = [
            _validate_anchor(
                require_string(certificate, "proof_anchor"),
                source_key=source_key,
                label=f"{label}.applicability.proof_anchor",
            )
        ]
        anchors.extend(
            _validate_mapping_entries(
                certificate,
                field="hypothesis_map",
                required={"source_hypothesis", "target_witness", "proof_anchor"},
                source_key=source_key,
                label=f"{label}.applicability",
                allow_empty=False,
            )
        )
        anchors.extend(
            _validate_mapping_entries(
                certificate,
                field="convention_map",
                required={"source_convention", "target_convention", "proof_anchor"},
                source_key=source_key,
                label=f"{label}.applicability",
                allow_empty=False,
            )
        )
        anchors.extend(
            _validate_mapping_entries(
                certificate,
                field="transport_obligations",
                required={"operation", "justification", "proof_anchor"},
                source_key=source_key,
                label=f"{label}.applicability",
                allow_empty=True,
            )
        )
        _require_nonempty_string_list(
            certificate,
            "exclusions_checked",
            label=f"{label}.applicability",
        )

        if verdict == "bridged":
            require_string(certificate, "bridge_statement")
            bridge_anchor = _validate_anchor(
                require_string(certificate, "bridge_proof_anchor"),
                source_key=source_key,
                label=f"{label}.applicability.bridge_proof_anchor",
            )
            anchors.append(bridge_anchor)
        elif "bridge_statement" in certificate or "bridge_proof_anchor" in certificate:
            raise ValueError(
                f"{label}.applicability bridge fields are allowed only for a bridged use"
            )

        valid_source_evidence_version = (
            type(source_evidence_version) is int
            and source_evidence_version == SOURCE_EVIDENCE_VERSION
        )
        valid_legacy_source_evidence_version = (
            type(source_evidence_version) is int
            and source_evidence_version in LEGACY_SOURCE_EVIDENCE_VERSIONS
        )
        if require_critical_audit and not valid_source_evidence_version:
            raise ValueError(
                f"{label}.source_evidence_version must be {SOURCE_EVIDENCE_VERSION} "
                "for a new external source use"
            )
        if has_reliability_field and not (
            valid_source_evidence_version or valid_legacy_source_evidence_version
        ):
            raise ValueError(
                f"{label}.source_evidence_version must be {SOURCE_EVIDENCE_VERSION} "
                f"or a supported historical version "
                "when source_trace or critical_audit is present"
            )

        if valid_source_evidence_version or valid_legacy_source_evidence_version:
            _validate_source_trace(
                ref.get("source_trace"),
                source_key=source_key,
                arxiv=arxiv if isinstance(arxiv, str) else None,
                source_locator=str(certificate["source_locator"]),
                source_fidelity=source_fidelity,
                label=f"{label}.source_trace",
            )
            source_trace = ref.get("source_trace")
            assert isinstance(source_trace, dict)
            if valid_source_evidence_version:
                (
                    critical_anchors,
                    audit_sha256,
                    audit_core,
                    reuse_mode,
                    reuse_origin,
                ) = _validate_critical_audit(
                    ref.get("critical_audit"),
                    source_key=source_key,
                    use_kind=use_kind,
                    certificate=certificate,
                    source_trace=source_trace,
                    label=f"{label}.critical_audit",
                )
                anchors.extend(critical_anchors)
                artifact_sha256 = str(source_trace["artifact_sha256"])
                prior_audit = source_audits_by_artifact.get(artifact_sha256)
                if prior_audit is None:
                    if reuse_mode == "reused" and reuse_origin.startswith("external_ref:"):
                        raise ValueError(
                            f"{label}.critical_audit.source_audit_reuse cannot cite a "
                            "nonpreceding external_ref for this exact source artifact"
                        )
                    source_audits_by_artifact[artifact_sha256] = (
                        audit_sha256,
                        audit_core,
                        source_key,
                    )
                else:
                    prior_sha256, prior_core, prior_key = prior_audit
                    if audit_sha256 != prior_sha256 or audit_core != prior_core:
                        raise ValueError(
                            f"{label} repeats artifact {artifact_sha256} with a different "
                            "source-level audit; reuse the first exact source audit"
                        )
                    if reuse_mode != "reused" or reuse_origin != f"external_ref:{prior_key}":
                        raise ValueError(
                            f"{label}.critical_audit.source_audit_reuse must reuse "
                            f"external_ref:{prior_key} for the repeated exact source artifact"
                        )
            else:
                anchors.extend(
                    _validate_critical_audit_v2(
                        ref.get("critical_audit"),
                        source_key=source_key,
                        use_kind=use_kind,
                        label=f"{label}.critical_audit",
                    )
                )

        for anchor in anchors:
            if anchor in seen_anchors:
                raise ValueError(f"duplicate applicability proof anchor: {anchor}")
            seen_anchors.add(anchor)
            occurrences = proof.count(anchor)
            if occurrences != 1:
                anchor_kind = (
                    "critical-audit" if anchor.startswith("[CRIT:") else "applicability"
                )
                raise ValueError(
                    f"{anchor_kind} proof anchor {anchor} must occur exactly once in proof; "
                    f"found {occurrences}"
                )
