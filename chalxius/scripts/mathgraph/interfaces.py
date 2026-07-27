from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from .contracts import (
    FACT_ID_RE,
    POLICY_REVISION_V4,
    SHA256_RE,
    require_exact_keys,
    require_string,
    sha256_bytes,
    sha256_json,
    validate_fact_id,
)
from .model import Fact


CLAUSE_ANCHOR_RE = re.compile(r"\[CLAIM:([A-Za-z0-9][A-Za-z0-9_-]{0,63})\]")
QUANTIFIER_ANCHOR_RE = re.compile(r"\[Q:([A-Za-z0-9][A-Za-z0-9_-]{0,63})\]")
HYPOTHESIS_RE = re.compile(r"(?<![A-Za-z0-9_-])(H[0-9][A-Za-z0-9_-]*)(?![A-Za-z0-9_-])")
QUANTIFIER_KINDS = {
    "forall",
    "exists",
    "exists_unique",
    "choose",
    "outside_finite_set",
}
WITNESS_KINDS = {"exists", "exists_unique", "choose", "outside_finite_set"}


def extract_statement_clauses(
    statement: str,
    *,
    require_v4: bool,
) -> list[dict[str, Any]]:
    matches = list(CLAUSE_ANCHOR_RE.finditer(statement))
    if not matches:
        if require_v4:
            raise ValueError("new v4 fact requires at least one [CLAIM:*] statement anchor")
        return [
            {
                "clause_id": "legacy-full",
                "text": statement.strip(),
                "hypothesis_labels": sorted(set(HYPOTHESIS_RE.findall(statement))),
                "quantifier_ids": QUANTIFIER_ANCHOR_RE.findall(statement),
                "synthetic": True,
            }
        ]
    clause_ids = [match.group(1) for match in matches]
    if len(set(clause_ids)) != len(clause_ids):
        raise ValueError("statement clause anchors must be unique")
    clauses: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(statement)
        text = statement[match.end() : end].strip()
        if not text:
            raise ValueError(f"statement clause {match.group(1)} is empty")
        clauses.append(
            {
                "clause_id": match.group(1),
                "text": text,
                "hypothesis_labels": sorted(set(HYPOTHESIS_RE.findall(text))),
                "quantifier_ids": QUANTIFIER_ANCHOR_RE.findall(text),
                "synthetic": False,
            }
        )
    return clauses


def validate_quantifier_ledger(
    ledger: Any,
    *,
    statement: str,
    proof: str,
    clause_ids: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(ledger, list) or any(not isinstance(item, dict) for item in ledger):
        raise ValueError("quantifier_ledger must be a list of objects")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    statement_anchor_order = QUANTIFIER_ANCHOR_RE.findall(statement)
    for index, item in enumerate(ledger, 1):
        label = f"quantifier_ledger[{index}]"
        require_exact_keys(
            item,
            required={
                "id",
                "kind",
                "variable",
                "depends_on",
                "statement_anchor",
                "proof_witness_anchor",
                "scope_clause",
            },
            label=label,
        )
        quantifier_id = require_string(item, "id")
        if quantifier_id in seen:
            raise ValueError(f"duplicate quantifier id: {quantifier_id}")
        kind = require_string(item, "kind")
        if kind not in QUANTIFIER_KINDS:
            raise ValueError(f"{label}.kind is invalid")
        variable = require_string(item, "variable")
        dependencies = item.get("depends_on")
        if not isinstance(dependencies, list) or any(
            not isinstance(value, str) for value in dependencies
        ):
            raise ValueError(f"{label}.depends_on must be a list of ids")
        if quantifier_id in dependencies:
            raise ValueError("quantifier dependency cannot be self-referential")
        unknown_or_inner = [value for value in dependencies if value not in seen]
        if unknown_or_inner:
            raise ValueError(
                "quantifier dependencies must name earlier outer quantifiers: "
                + ", ".join(unknown_or_inner)
            )
        expected_statement_anchor = f"[Q:{quantifier_id}]"
        statement_anchor = require_string(item, "statement_anchor")
        if statement_anchor != expected_statement_anchor:
            raise ValueError(f"{label}.statement_anchor is noncanonical")
        if statement.count(statement_anchor) != 1:
            raise ValueError(
                f"quantifier statement anchor {statement_anchor} must occur exactly once"
            )
        witness_anchor = require_string(
            item, "proof_witness_anchor", allow_empty=(kind not in WITNESS_KINDS)
        )
        if kind in WITNESS_KINDS:
            expected_witness = f"[WIT:{quantifier_id}]"
            if witness_anchor != expected_witness or proof.count(witness_anchor) != 1:
                raise ValueError(
                    f"quantifier witness anchor {expected_witness} must occur exactly once"
                )
        elif witness_anchor and proof.count(witness_anchor) != 1:
            raise ValueError(
                f"quantifier proof anchor {witness_anchor} must occur exactly once"
            )
        scope_clause = require_string(item, "scope_clause")
        if scope_clause not in clause_ids:
            raise ValueError(f"{label}.scope_clause is unknown")
        seen.add(quantifier_id)
        normalized.append(
            {
                "id": quantifier_id,
                "kind": kind,
                "variable": variable,
                "depends_on": list(dependencies),
                "statement_anchor": statement_anchor,
                "proof_witness_anchor": witness_anchor,
                "scope_clause": scope_clause,
            }
        )
    if [item["id"] for item in normalized] != statement_anchor_order:
        raise ValueError("quantifier ledger order must match statement anchor order")
    return normalized


def build_statement_interface(
    *,
    fact: Fact,
    stored_fact_sha256: str,
    acceptance_event_sha256: str,
    admission_review_id: str,
    workflow_evidence_version: int,
) -> dict[str, Any]:
    if SHA256_RE.fullmatch(stored_fact_sha256) is None:
        raise ValueError("stored_fact_sha256 must be a full SHA-256")
    if SHA256_RE.fullmatch(acceptance_event_sha256) is None:
        raise ValueError("acceptance_event_sha256 must be a full SHA-256")
    if SHA256_RE.fullmatch(admission_review_id) is None:
        raise ValueError("admission_review_id must be a full SHA-256")
    clauses = extract_statement_clauses(
        fact.statement,
        require_v4=workflow_evidence_version >= 4,
    )
    ledger = validate_quantifier_ledger(
        getattr(fact, "quantifier_ledger", []),
        statement=fact.statement,
        proof=fact.proof,
        clause_ids={item["clause_id"] for item in clauses},
    )
    ledger_by_clause: dict[str, list[str]] = {}
    for item in ledger:
        ledger_by_clause.setdefault(item["scope_clause"], []).append(item["id"])
    for clause in clauses:
        if not clause["synthetic"]:
            clause["quantifier_ids"] = ledger_by_clause.get(
                clause["clause_id"], clause["quantifier_ids"]
            )
        clause.pop("synthetic", None)
    interface = {
        "schema_version": 4 if workflow_evidence_version >= 4 else 3,
        "policy_revision": (
            POLICY_REVISION_V4
            if workflow_evidence_version >= 4
            else "legacy-projection"
        ),
        "fact_id": fact.fact_id,
        "statement_sha256": sha256_bytes(fact.statement.encode("utf-8")),
        "stored_fact_sha256": stored_fact_sha256,
        "acceptance_event_sha256": acceptance_event_sha256,
        "admission_review_id": admission_review_id,
        "clauses": clauses,
        "glossary_introduces": fact.glossary_introduces,
    }
    interface["interface_sha256"] = sha256_json(interface)
    return interface


def validate_statement_interface(
    interface: dict[str, Any],
    *,
    active_fact_ids: set[str] | None = None,
) -> dict[str, Any]:
    require_exact_keys(
        interface,
        required={
            "schema_version",
            "policy_revision",
            "fact_id",
            "statement_sha256",
            "stored_fact_sha256",
            "acceptance_event_sha256",
            "admission_review_id",
            "clauses",
            "glossary_introduces",
            "interface_sha256",
        },
        label="statement interface",
    )
    fact_id = validate_fact_id(require_string(interface, "fact_id"))
    if active_fact_ids is not None and fact_id not in active_fact_ids:
        raise ValueError("revoked or inactive predecessor interface is not usable")
    for key in (
        "statement_sha256",
        "stored_fact_sha256",
        "acceptance_event_sha256",
        "admission_review_id",
        "interface_sha256",
    ):
        if SHA256_RE.fullmatch(require_string(interface, key)) is None:
            raise ValueError(f"statement interface {key} is invalid")
    expected_hash = sha256_json(
        {key: value for key, value in interface.items() if key != "interface_sha256"}
    )
    if interface["interface_sha256"] != expected_hash:
        raise ValueError("statement interface hash mismatch")
    clauses = interface.get("clauses")
    if not isinstance(clauses, list) or not clauses:
        raise ValueError("statement interface clauses must be nonempty")
    seen: set[str] = set()
    for index, clause in enumerate(clauses, 1):
        if not isinstance(clause, dict):
            raise ValueError(f"statement interface clause {index} is not an object")
        require_exact_keys(
            clause,
            required={
                "clause_id",
                "text",
                "hypothesis_labels",
                "quantifier_ids",
            },
            label=f"statement interface clauses[{index}]",
        )
        clause_id = require_string(clause, "clause_id")
        if clause_id in seen:
            raise ValueError("statement interface has duplicate clauses")
        seen.add(clause_id)
        require_string(clause, "text")
        for key in ("hypothesis_labels", "quantifier_ids"):
            if not isinstance(clause.get(key), list) or any(
                not isinstance(item, str) for item in clause[key]
            ):
                raise ValueError(f"statement interface clause {key} is invalid")
    return interface


def validate_predecessor_uses(
    uses: Any,
    *,
    predecessors: list[str],
    proof: str,
    interface_lookup: Callable[[str], dict[str, Any]],
    convention_profile_ids: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(uses, list) or any(not isinstance(item, dict) for item in uses):
        raise ValueError("predecessor_uses must be a list of objects")
    predecessor_set = set(predecessors)
    represented: set[str] = set()
    normalized: list[dict[str, Any]] = []
    anchors: set[str] = set()
    for index, item in enumerate(uses, 1):
        label = f"predecessor_uses[{index}]"
        require_exact_keys(
            item,
            required={
                "fact_id",
                "clause_id",
                "use_anchor",
                "used_conclusion",
                "hypothesis_witnesses",
                "convention_bridge",
            },
            label=label,
        )
        fact_id = validate_fact_id(require_string(item, "fact_id"))
        if fact_id not in predecessor_set:
            raise ValueError(f"{label}.fact_id is not a declared predecessor")
        interface = validate_statement_interface(interface_lookup(fact_id))
        clause_id = require_string(item, "clause_id")
        clauses = {
            clause["clause_id"]: clause for clause in interface["clauses"]
        }
        if clause_id not in clauses:
            raise ValueError(f"{label}.clause_id is not exported by the predecessor")
        anchor = require_string(item, "use_anchor")
        canonical_prefix = f"[USE:{fact_id}:{clause_id}:"
        if not anchor.startswith(canonical_prefix) or not anchor.endswith("]"):
            raise ValueError(f"{label}.use_anchor is noncanonical")
        if anchor in anchors or proof.count(anchor) != 1:
            raise ValueError(
                f"predecessor use anchor {anchor} must be unique and occur exactly once"
            )
        anchors.add(anchor)
        require_string(item, "used_conclusion")
        witnesses = item.get("hypothesis_witnesses")
        if not isinstance(witnesses, list) or any(
            not isinstance(witness, dict) for witness in witnesses
        ):
            raise ValueError(f"{label}.hypothesis_witnesses must be a list of objects")
        witness_by_hypothesis: dict[str, dict[str, Any]] = {}
        for witness_index, witness in enumerate(witnesses, 1):
            require_exact_keys(
                witness,
                required={"hypothesis", "witness", "proof_anchor"},
                label=f"{label}.hypothesis_witnesses[{witness_index}]",
            )
            hypothesis = require_string(witness, "hypothesis")
            require_string(witness, "witness")
            if require_string(witness, "proof_anchor") != anchor:
                raise ValueError(
                    f"{label} hypothesis witness must bind the same use anchor"
                )
            if hypothesis in witness_by_hypothesis:
                raise ValueError(f"{label} has a duplicate hypothesis witness")
            witness_by_hypothesis[hypothesis] = witness
        required_hypotheses = set(clauses[clause_id]["hypothesis_labels"])
        if set(witness_by_hypothesis) != required_hypotheses:
            missing = required_hypotheses.difference(witness_by_hypothesis)
            extra = set(witness_by_hypothesis).difference(required_hypotheses)
            raise ValueError(
                f"{label} hypothesis witnesses mismatch; "
                f"missing={sorted(missing)} extra={sorted(extra)}"
            )
        bridge = item.get("convention_bridge")
        if bridge is not None:
            if not isinstance(bridge, dict):
                raise ValueError(f"{label}.convention_bridge must be null or an object")
            require_exact_keys(
                bridge,
                required={
                    "from_convention_id",
                    "to_convention_id",
                    "kind",
                    "witness",
                    "proof_anchor",
                },
                label=f"{label}.convention_bridge",
            )
            for key in (
                "from_convention_id",
                "to_convention_id",
                "kind",
                "witness",
                "proof_anchor",
            ):
                require_string(bridge, key)
            if bridge["to_convention_id"] not in convention_profile_ids:
                raise ValueError(f"{label} bridge target is not a current convention")
            if proof.count(bridge["proof_anchor"]) != 1:
                raise ValueError(f"{label} convention bridge anchor is not exact-once")
        represented.add(fact_id)
        normalized.append(dict(item))
    if represented != predecessor_set:
        missing = predecessor_set.difference(represented)
        raise ValueError(
            "every predecessor requires at least one clause use: "
            + ", ".join(sorted(missing))
        )
    return normalized


def statement_only_packet_section(
    *,
    fact_id: str,
    statement: str,
    interface: dict[str, Any],
) -> str:
    validate_statement_interface(interface)
    if fact_id != interface["fact_id"]:
        raise ValueError("statement/interface fact id mismatch")
    return "\n".join(
        [
            f"## Admitted predecessor interface `{fact_id}`",
            "",
            "### Statement",
            "",
            statement.strip(),
            "",
            "### Clause interface",
            "",
            "```json",
            json.dumps(interface, ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
        ]
    )


def lint_quantifier_export(
    text: str,
    ledger: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    lowered = text.casefold()
    dependency_phrases = (
        "uniform",
        "canonical",
        "independent of",
        "same witness for all",
    )
    for item in ledger:
        if item.get("depends_on") and any(
            phrase in lowered for phrase in dependency_phrases
        ):
            errors.append(
                f"dependent witness {item.get('id')} cannot be exported as uniform/canonical"
            )
    return errors


def write_interface_once(path: Path, interface: dict[str, Any]) -> None:
    validate_statement_interface(interface)
    rendered = (
        json.dumps(interface, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = 0
    import os

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o644)
    except FileExistsError:
        if path.read_bytes() != rendered:
            raise ValueError(f"immutable statement interface collision at {path}")
        return
    with os.fdopen(fd, "wb") as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
