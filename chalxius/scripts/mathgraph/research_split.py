from __future__ import annotations

import re
from typing import Any

from .contracts import SHA256_RE, validate_memory_id


RESEARCH_SPLIT_OUTPUT_SHAPE = "research_split_batch"
RESEARCH_SPLIT_ARTIFACT_ROLE = "research_split_batch"
RESEARCH_SPLIT_BATCH_REVISION_V1 = "chalxius-research-split-batch-1"
RESEARCH_SPLIT_BATCH_REVISION = "chalxius-research-split-batch-2"
RESEARCH_SPLIT_COMMIT_REVISION_V1 = "chalxius-research-split-commit-1"
RESEARCH_SPLIT_COMMIT_REVISION = "chalxius-research-split-commit-2"
RESEARCH_SPLIT_MEMBER_REVISION = "chalxius-research-split-member-1"
RESEARCH_SPLIT_OWNER_REVISION_V1 = "chalxius-research-split-owner-1"
RESEARCH_SPLIT_OWNER_REVISION = "chalxius-research-split-owner-2"
RESEARCH_SPLIT_MAX_MEMBERS = 128

_SURFACE_KEY_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_CONSTRUCTIVE_OUTCOMES = frozenset({"proof", "evidence", "insight"})
RESEARCH_SPLIT_RELATION_TYPES = frozenset({"proof_dependency", "context"})
RESEARCH_SPLIT_RELATION_TARGET_SCOPES = frozenset(
    {"split_internal", "external_research"}
)


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

    base_fields = {
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
    if not isinstance(value, dict):
        raise ValueError("Research split-batch fields are not exact")
    revision = value.get("contract_revision")
    required = (
        base_fields
        if revision == RESEARCH_SPLIT_BATCH_REVISION_V1
        else base_fields
        | {
            "internal_relations",
            "external_relations",
            "relation_allocation_rationale",
        }
        if revision == RESEARCH_SPLIT_BATCH_REVISION
        else set()
    )
    if not required or set(value) != required:
        raise ValueError("Research split-batch fields are not exact")
    source_id = validate_memory_id(value.get("source_research_id"))
    source_sha = value.get("source_record_sha256")
    if (
        value.get("schema_version") != 1
        or revision
        not in {
            RESEARCH_SPLIT_BATCH_REVISION_V1,
            RESEARCH_SPLIT_BATCH_REVISION,
        }
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
    normalized = {
        "schema_version": 1,
        "contract_revision": revision,
        "source_research_id": source_id,
        "source_record_sha256": source_sha,
        "shared_assumptions": shared_assumptions,
        "members": members,
        "residual_open_material": residual_open,
        "abandoned_material": abandoned,
        "completeness_rationale": completeness_rationale,
        "truth_effect": "none",
    }
    if revision == RESEARCH_SPLIT_BATCH_REVISION_V1:
        return normalized

    relation_allocation_rationale = _text(
        value["relation_allocation_rationale"],
        "Research split relation-allocation rationale",
        cap=16_384,
    )
    internal_fields = {
        "from_surface_key",
        "to_surface_key",
        "relation_type",
        "label",
        "rationale",
    }
    external_fields = {
        "from_surface_key",
        "to_research_id",
        "relation_type",
        "label",
        "rationale",
    }
    internal_relations: list[dict[str, str]] = []
    external_relations: list[dict[str, str]] = []
    seen_relations: set[tuple[str, ...]] = set()
    raw_internal = value["internal_relations"]
    raw_external = value["external_relations"]
    if not isinstance(raw_internal, list) or len(raw_internal) > 512:
        raise ValueError("Research split internal relations are invalid")
    if not isinstance(raw_external, list) or len(raw_external) > 512:
        raise ValueError("Research split external relations are invalid")
    for index, relation in enumerate(raw_internal, 1):
        if not isinstance(relation, dict) or set(relation) != internal_fields:
            raise ValueError(
                f"Research split internal relation {index} fields are not exact"
            )
        from_key = relation["from_surface_key"]
        to_key = relation["to_surface_key"]
        relation_type = relation["relation_type"]
        if (
            from_key not in surface_keys
            or to_key not in surface_keys
            or from_key == to_key
            or relation_type not in RESEARCH_SPLIT_RELATION_TYPES
        ):
            raise ValueError("Research split internal relation is invalid")
        label = _text(
            relation["label"], "Research split relation label", cap=512
        )
        rationale = _text(
            relation["rationale"],
            "Research split relation rationale",
            cap=8_192,
        )
        key = ("surface", from_key, to_key, relation_type, label)
        if key in seen_relations:
            raise ValueError("Research split relation is duplicated")
        seen_relations.add(key)
        internal_relations.append(
            {
                "from_surface_key": from_key,
                "to_surface_key": to_key,
                "relation_type": relation_type,
                "label": label,
                "rationale": rationale,
            }
        )
    for index, relation in enumerate(raw_external, 1):
        if not isinstance(relation, dict) or set(relation) != external_fields:
            raise ValueError(
                f"Research split external relation {index} fields are not exact"
            )
        from_key = relation["from_surface_key"]
        to_research_id = validate_memory_id(relation["to_research_id"])
        relation_type = relation["relation_type"]
        if (
            from_key not in surface_keys
            or relation_type not in RESEARCH_SPLIT_RELATION_TYPES
        ):
            raise ValueError("Research split external relation is invalid")
        label = _text(
            relation["label"], "Research split relation label", cap=512
        )
        rationale = _text(
            relation["rationale"],
            "Research split relation rationale",
            cap=8_192,
        )
        key = (
            "research",
            from_key,
            to_research_id,
            relation_type,
            label,
        )
        if key in seen_relations:
            raise ValueError("Research split relation is duplicated")
        seen_relations.add(key)
        external_relations.append(
            {
                "from_surface_key": from_key,
                "to_research_id": to_research_id,
                "relation_type": relation_type,
                "label": label,
                "rationale": rationale,
            }
        )
    normalized["internal_relations"] = internal_relations
    normalized["external_relations"] = external_relations
    normalized["relation_allocation_rationale"] = (
        relation_allocation_rationale
    )
    return normalized


def validate_resolved_research_split_relations(
    value: Any,
    *,
    member_ids: set[str],
) -> list[dict[str, str]]:
    """Validate the worker-declared relation allocation after id resolution.

    These relations are Research navigation data, not certified proof edges.
    ``proof_dependency`` remains a proposal until a supervisor writes it into
    a statement interface.  ``context`` remains non-premise navigation data.
    """

    fields = {
        "from_research_id",
        "to_research_id",
        "relation_type",
        "target_scope",
        "label",
        "rationale",
    }
    if not isinstance(value, list) or len(value) > 1024:
        raise ValueError("Research split resolved relations are invalid")
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for index, relation in enumerate(value, 1):
        if not isinstance(relation, dict) or set(relation) != fields:
            raise ValueError(
                f"Research split resolved relation {index} fields are not exact"
            )
        from_id = validate_memory_id(relation["from_research_id"])
        to_id = validate_memory_id(relation["to_research_id"])
        relation_type = relation["relation_type"]
        target_scope = relation["target_scope"]
        if (
            from_id not in member_ids
            or relation_type not in RESEARCH_SPLIT_RELATION_TYPES
            or target_scope not in RESEARCH_SPLIT_RELATION_TARGET_SCOPES
            or (
                target_scope == "split_internal"
                and (to_id not in member_ids or to_id == from_id)
            )
            or (
                target_scope == "external_research"
                and to_id in member_ids
            )
        ):
            raise ValueError("Research split resolved relation is invalid")
        label = _text(
            relation["label"], "Research split relation label", cap=512
        )
        rationale = _text(
            relation["rationale"],
            "Research split relation rationale",
            cap=8_192,
        )
        key = (from_id, to_id, relation_type, target_scope, label)
        if key in seen:
            raise ValueError("Research split resolved relation is duplicated")
        seen.add(key)
        normalized.append(
            {
                "from_research_id": from_id,
                "to_research_id": to_id,
                "relation_type": relation_type,
                "target_scope": target_scope,
                "label": label,
                "rationale": rationale,
            }
        )
    return normalized
