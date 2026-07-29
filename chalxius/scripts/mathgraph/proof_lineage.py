from __future__ import annotations

import difflib
import re
from typing import Any, Callable

from .contracts import SHA256_RE, sha256_bytes
from .model import Fact, normalize_text


INTERFACE_ONLY_SUCCESSOR = "interface_only_successor"
INTERFACE_SUCCESSOR_WITH_PROOF_REWRITE = (
    "interface_successor_with_proof_rewrite"
)
SUCCESSOR_MODES = {
    INTERFACE_ONLY_SUCCESSOR,
    INTERFACE_SUCCESSOR_WITH_PROOF_REWRITE,
}

_INTERFACE_ANCHOR_RE = re.compile(
    r"\[HYP:H[0-9][A-Za-z0-9_-]*\]|\[GEO:[^\]\n]+\]"
)


def _text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        qualifier = "a string" if allow_empty else "a nonempty string"
        raise ValueError(f"{label} must be {qualifier}")
    return value if allow_empty else value.strip()


def _exact(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} fields are not exact")
    return value


def statement_without_interface_anchors(statement: str) -> str:
    return normalize_text(_INTERFACE_ANCHOR_RE.sub(" ", statement))


def statement_projection_sha256(statement: str) -> str:
    return sha256_bytes(
        statement_without_interface_anchors(statement).encode("utf-8")
    )


def proof_units(proof: str) -> list[dict[str, str]]:
    units = [item.strip() for item in re.split(r"\n\s*\n", proof) if item.strip()]
    return [
        {
            "unit_id": f"proof-unit-{index:04d}",
            "unit_sha256": sha256_bytes(unit.encode("utf-8")),
            "text": unit,
        }
        for index, unit in enumerate(units, 1)
    ]


def _logical_payload_without_interface_text(fact: Fact, *, rewrite: bool) -> dict[str, Any]:
    payload = fact.as_submission_dict()
    excluded = {"fact_id", "statement"}
    if rewrite:
        excluded.add("proof")
    return {key: value for key, value in payload.items() if key not in excluded}


def _unified_diff(before: str, after: str, *, before_name: str, after_name: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=before_name,
            tofile=after_name,
            lineterm="\n",
        )
    )


def _validate_one(
    raw: Any,
    *,
    candidates: dict[str, Fact],
    active_fact: Callable[[str], Fact],
    active_fact_sha256: Callable[[str], str],
) -> dict[str, Any]:
    contract = _exact(
        raw,
        {
            "mode",
            "predecessor_fact_id",
            "successor_fact_id",
            "predecessor_fact_sha256",
            "predecessor_proof_sha256",
            "successor_proof_sha256",
            "statement_projection",
            "proof_unit_conservation",
        },
        "successor contract",
    )
    mode = _text(contract["mode"], "successor mode")
    if mode not in SUCCESSOR_MODES:
        raise ValueError("successor mode is invalid")
    predecessor_id = _text(
        contract["predecessor_fact_id"], "successor predecessor Fact id"
    )
    successor_id = _text(
        contract["successor_fact_id"], "successor Candidate Fact id"
    )
    if successor_id not in candidates:
        raise ValueError("successor contract names an unknown Candidate Fact")
    predecessor = active_fact(predecessor_id)
    successor = candidates[successor_id]
    expected_predecessor_fact_sha = active_fact_sha256(predecessor_id)
    expected_predecessor_proof_sha = sha256_bytes(
        predecessor.proof.encode("utf-8")
    )
    expected_successor_proof_sha = sha256_bytes(successor.proof.encode("utf-8"))
    for field, expected in (
        ("predecessor_fact_sha256", expected_predecessor_fact_sha),
        ("predecessor_proof_sha256", expected_predecessor_proof_sha),
        ("successor_proof_sha256", expected_successor_proof_sha),
    ):
        supplied = contract[field]
        if not isinstance(supplied, str) or SHA256_RE.fullmatch(supplied) is None:
            raise ValueError(f"successor contract {field} is invalid")
        if supplied != expected:
            raise ValueError(f"successor contract {field} does not bind exact bytes")
    projection = _exact(
        contract["statement_projection"],
        {
            "mode",
            "predecessor_without_interface_sha256",
            "successor_without_interface_sha256",
        },
        "successor statement projection",
    )
    predecessor_projection = statement_projection_sha256(predecessor.statement)
    successor_projection = statement_projection_sha256(successor.statement)
    if (
        projection["mode"] != "remove_only_hypothesis_and_geometric_interface_anchors"
        or projection["predecessor_without_interface_sha256"]
        != predecessor_projection
        or projection["successor_without_interface_sha256"]
        != successor_projection
        or predecessor_projection != successor_projection
    ):
        raise ValueError(
            "successor statement differs by more than explicit interface anchors"
        )
    if predecessor.statement == successor.statement:
        raise ValueError("successor contract requires an actual interface change")
    rewrite = mode == INTERFACE_SUCCESSOR_WITH_PROOF_REWRITE
    if _logical_payload_without_interface_text(
        predecessor, rewrite=rewrite
    ) != _logical_payload_without_interface_text(successor, rewrite=rewrite):
        raise ValueError(
            "interface successor changes fields outside the statement/interface"
            + (" and declared proof rewrite" if rewrite else "")
        )
    conservation = contract["proof_unit_conservation"]
    if not isinstance(conservation, list) or any(
        not isinstance(item, dict) for item in conservation
    ):
        raise ValueError("proof_unit_conservation must be a list of objects")
    if mode == INTERFACE_ONLY_SUCCESSOR:
        if predecessor.proof.encode("utf-8") != successor.proof.encode("utf-8"):
            raise ValueError(
                "interface_only_successor must preserve predecessor proof bytes exactly"
            )
        if conservation:
            raise ValueError(
                "interface_only_successor uses byte identity and requires an empty conservation map"
            )
    else:
        if predecessor.proof.encode("utf-8") == successor.proof.encode("utf-8"):
            raise ValueError(
                "proof-rewrite successor must use interface_only_successor when proof bytes match"
            )
        expected_units = {
            item["unit_sha256"]: item for item in proof_units(predecessor.proof)
        }
        actual_units: dict[str, dict[str, str]] = {}
        for index, item in enumerate(conservation, 1):
            _exact(
                item,
                {
                    "predecessor_unit_sha256",
                    "successor_anchor",
                    "disposition",
                    "justification",
                },
                f"proof_unit_conservation[{index}]",
            )
            unit_sha = _text(
                item["predecessor_unit_sha256"],
                f"proof_unit_conservation[{index}].predecessor_unit_sha256",
            )
            if (
                SHA256_RE.fullmatch(unit_sha) is None
                or unit_sha not in expected_units
                or unit_sha in actual_units
            ):
                raise ValueError(
                    "proof-unit conservation contains an unknown or duplicate predecessor unit"
                )
            disposition = _text(
                item["disposition"],
                f"proof_unit_conservation[{index}].disposition",
            )
            if disposition not in {
                "preserved",
                "reproved",
                "pruned_with_justification",
            }:
                raise ValueError("proof-unit conservation disposition is invalid")
            anchor = _text(
                item["successor_anchor"],
                f"proof_unit_conservation[{index}].successor_anchor",
                allow_empty=True,
            )
            justification = _text(
                item["justification"],
                f"proof_unit_conservation[{index}].justification",
            )
            if disposition == "pruned_with_justification":
                if anchor:
                    raise ValueError("a pruned predecessor proof unit must use an empty anchor")
            elif not anchor or successor.proof.count(anchor) != 1:
                raise ValueError(
                    "a preserved or reproved predecessor unit needs one exact successor anchor"
                )
            actual_units[unit_sha] = {
                "predecessor_unit_sha256": unit_sha,
                "successor_anchor": anchor,
                "disposition": disposition,
                "justification": justification,
            }
        if set(actual_units) != set(expected_units):
            raise ValueError(
                "proof-unit conservation does not exactly cover every predecessor proof unit; "
                f"missing={sorted(set(expected_units).difference(actual_units))}"
            )

    return {
        "mode": mode,
        "predecessor_fact_id": predecessor_id,
        "successor_fact_id": successor_id,
        "predecessor_fact_sha256": expected_predecessor_fact_sha,
        "predecessor_proof_sha256": expected_predecessor_proof_sha,
        "successor_proof_sha256": expected_successor_proof_sha,
        "statement_projection": {
            "mode": "remove_only_hypothesis_and_geometric_interface_anchors",
            "predecessor_without_interface_sha256": predecessor_projection,
            "successor_without_interface_sha256": successor_projection,
        },
        "proof_unit_conservation": list(conservation),
        "statement_diff": {
            "changed": predecessor.statement != successor.statement,
            "unified_diff": _unified_diff(
                predecessor.statement,
                successor.statement,
                before_name=f"{predecessor_id}:statement",
                after_name=f"{successor_id}:statement",
            ),
        },
        "proof_diff": {
            "changed": predecessor.proof != successor.proof,
            "unified_diff": _unified_diff(
                predecessor.proof,
                successor.proof,
                before_name=f"{predecessor_id}:proof",
                after_name=f"{successor_id}:proof",
            ),
        },
        "truth_effect": "none_until_fresh_verification_and_gateway_admission",
    }


def validate_successor_contracts(
    value: Any,
    *,
    candidates: dict[str, Fact],
    active_facts: dict[str, Fact],
    active_fact_sha256: Callable[[str], str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("successor_contracts must be a list of objects")
    normalized: list[dict[str, Any]] = []
    seen_successors: set[str] = set()

    def lookup(fact_id: str) -> Fact:
        if fact_id not in active_facts:
            raise ValueError("successor contract predecessor is not an active Fact")
        return active_facts[fact_id]

    for raw in value:
        item = _validate_one(
            raw,
            candidates=candidates,
            active_fact=lookup,
            active_fact_sha256=active_fact_sha256,
        )
        if item["successor_fact_id"] in seen_successors:
            raise ValueError("a Candidate Fact has duplicate successor contracts")
        seen_successors.add(item["successor_fact_id"])
        normalized.append(item)

    label_only_candidates: dict[str, list[str]] = {}
    for successor_id, successor in candidates.items():
        successor_projection = statement_projection_sha256(successor.statement)
        matches = [
            predecessor_id
            for predecessor_id, predecessor in active_facts.items()
            if predecessor.problem_id == successor.problem_id
            and predecessor_id != successor_id
            and statement_projection_sha256(predecessor.statement)
            == successor_projection
        ]
        if matches:
            label_only_candidates[successor_id] = sorted(matches)
    missing = sorted(set(label_only_candidates).difference(seen_successors))
    if missing:
        details = ", ".join(
            f"{successor_id} matches {label_only_candidates[successor_id]}"
            for successor_id in missing
        )
        raise ValueError(
            "interface-labeled Candidate successors require an explicit copy-on-write "
            f"successor contract: {details}"
        )
    normalized.sort(key=lambda item: item["successor_fact_id"])
    return normalized

