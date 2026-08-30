from __future__ import annotations

import re
from typing import Any

from .contracts import SHA256_RE, validate_memory_id


RESEARCH_SPLIT_OUTPUT_SHAPE = "research_split_batch"
RESEARCH_SPLIT_ARTIFACT_ROLE = "research_split_batch"
RESEARCH_SPLIT_BATCH_REVISION = "chalxius-research-split-batch-1"
RESEARCH_SPLIT_COMMIT_REVISION = "chalxius-research-split-commit-1"
RESEARCH_SPLIT_MEMBER_REVISION = "chalxius-research-split-member-1"
RESEARCH_SPLIT_OWNER_REVISION = "chalxius-research-split-owner-1"
RESEARCH_SPLIT_MAX_MEMBERS = 128

_SURFACE_KEY_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_CONSTRUCTIVE_OUTCOMES = frozenset({"proof", "evidence", "insight"})


def _text(value: Any, label: str, *, cap: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    if "\x00" in value or len(value) > cap:
        raise ValueError(f"{label} is unsafe or exceeds its cap")
    return value


def _text_list(
    value: Any,
    label: str,
    *,
    maximum: int = RESEARCH_SPLIT_MAX_MEMBERS,
) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) > maximum
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise ValueError(f"{label} must be a bounded list of nonempty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} contains duplicates")
    return list(value)


def validate_research_split_batch(
    value: Any,
    *,
    source_research: dict[str, Any],
) -> dict[str, Any]:
    """Validate one worker-chosen, finite semantic split.

    Main does not predict the number of successors.  The worker declares the
    complete actual membership once, and ingestion commits that membership as
    one batch only after every successor Research record has been published.
    """

    required = {
        "schema_version",
        "contract_revision",
        "source_research_id",
        "source_record_sha256",
        "shared_assumptions",
        "members",
        "residual_open_material",
        "abandoned_material",
        "completeness_rationale",
        "truth_effect",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("Research split-batch fields are not exact")
    source_id = validate_memory_id(value.get("source_research_id"))
    source_sha = value.get("source_record_sha256")
    if (
        value.get("schema_version") != 1
        or value.get("contract_revision") != RESEARCH_SPLIT_BATCH_REVISION
        or value.get("truth_effect") != "none"
        or source_id != source_research.get("research_id")
        or not isinstance(source_sha, str)
        or SHA256_RE.fullmatch(source_sha) is None
        or source_sha != source_research.get("record_sha256")
    ):
        raise ValueError("Research split-batch source binding is invalid")
    shared_assumptions = _text_list(
        value["shared_assumptions"], "Research split shared assumptions"
    )
    residual_open = _text_list(
        value["residual_open_material"], "Research split residual material"
    )
    abandoned = _text_list(
        value["abandoned_material"], "Research split abandoned material"
    )
    completeness_rationale = _text(
        value["completeness_rationale"],
        "Research split completeness rationale",
        cap=16_384,
    )
    raw_members = value["members"]
    if (
        not isinstance(raw_members, list)
        or not 2 <= len(raw_members) <= RESEARCH_SPLIT_MAX_MEMBERS
    ):
        raise ValueError(
            "Research split batch must contain two to "
            f"{RESEARCH_SPLIT_MAX_MEMBERS} members"
        )
    members: list[dict[str, Any]] = []
    surface_keys: set[str] = set()
    claims: set[str] = set()
    member_fields = {
        "surface_key",
        "outcome",
        "claim",
        "content",
        "rationale",
        "source_material_disposition",
        "limitations",
    }
    for index, raw in enumerate(raw_members, 1):
        if not isinstance(raw, dict) or set(raw) != member_fields:
            raise ValueError(
                f"Research split member {index} fields are not exact"
            )
        surface_key = raw["surface_key"]
        if (
            not isinstance(surface_key, str)
            or _SURFACE_KEY_RE.fullmatch(surface_key) is None
            or surface_key in surface_keys
        ):
            raise ValueError("Research split surface key is invalid or duplicated")
        outcome = raw["outcome"]
        if outcome not in _CONSTRUCTIVE_OUTCOMES:
            raise ValueError(
                "Research split members must be constructive; a counterexample, "
                "challenge, or dead end belongs in the ordinary return outcome"
            )
        claim = _text(raw["claim"], "Research split member claim", cap=16_384)
        if claim in claims:
            raise ValueError("Research split member claims must be distinct")
        content = _text(
            raw["content"], "Research split member content", cap=256 * 1_024
        )
        rationale = _text(
            raw["rationale"], "Research split member rationale", cap=16_384
        )
        source_disposition = _text(
            raw["source_material_disposition"],
            "Research split source-material disposition",
            cap=16_384,
        )
        limitations = _text_list(
            raw["limitations"], "Research split member limitations"
        )
        surface_keys.add(surface_key)
        claims.add(claim)
        members.append(
            {
                "surface_key": surface_key,
                "outcome": outcome,
                "claim": claim,
                "content": content,
                "rationale": rationale,
                "source_material_disposition": source_disposition,
                "limitations": limitations,
            }
        )
    return {
        "schema_version": 1,
        "contract_revision": RESEARCH_SPLIT_BATCH_REVISION,
        "source_research_id": source_id,
        "source_record_sha256": source_sha,
        "shared_assumptions": shared_assumptions,
        "members": members,
        "residual_open_material": residual_open,
        "abandoned_material": abandoned,
        "completeness_rationale": completeness_rationale,
        "truth_effect": "none",
    }
