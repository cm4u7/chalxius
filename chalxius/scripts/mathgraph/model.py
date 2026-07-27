from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from .contracts import FACT_ID_RE


def normalize_text(text: str) -> str:
    """Whitespace-stable canonical form used for content addressing."""

    return re.sub(r"\s+", " ", text or "").strip()


def compute_fact_id(
    *,
    problem_id: str,
    predecessors: list[str],
    glossary_introduces: dict[str, str],
    statement: str,
    proof: str,
) -> str:
    """Return the 16-hex content id used by Danus.

    Bibliographic metadata and intuition are deliberately excluded: they can be
    repaired without changing the logical node or breaking every downstream id.
    """

    body = {
        "problem_id": problem_id,
        "predecessors": sorted(predecessors),
        "glossary_introduces": dict(
            sorted((str(key), str(value)) for key, value in glossary_introduces.items())
        ),
        "statement": normalize_text(statement),
        "proof": normalize_text(proof),
    }
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:16]


@dataclass(slots=True)
class Fact:
    problem_id: str
    author: str
    predecessors: list[str]
    statement: str
    proof: str
    glossary_introduces: dict[str, str] = field(default_factory=dict)
    intuition: str = ""
    external_refs: list[dict[str, Any]] = field(default_factory=list)
    elementary_uses: list[dict[str, Any]] = field(default_factory=list)
    predecessor_uses: list[dict[str, Any]] = field(default_factory=list)
    quantifier_ledger: list[dict[str, Any]] = field(default_factory=list)
    convention_profile_ids: list[str] = field(default_factory=list)
    computational_evidence: list[dict[str, Any]] = field(default_factory=list)
    terminology: list[dict[str, Any]] = field(default_factory=list)
    fact_id: str = ""

    def __post_init__(self) -> None:
        self.predecessors = sorted(dict.fromkeys(self.predecessors))
        self.glossary_introduces = {
            str(key): str(value) for key, value in self.glossary_introduces.items()
        }
        if not self.fact_id:
            self.fact_id = self.computed_id

    @property
    def computed_id(self) -> str:
        return compute_fact_id(
            problem_id=self.problem_id,
            predecessors=self.predecessors,
            glossary_introduces=self.glossary_introduces,
            statement=self.statement,
            proof=self.proof,
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if FACT_ID_RE.fullmatch(self.fact_id) is None:
            errors.append(f"invalid fact_id: {self.fact_id!r}")
        if self.fact_id != self.computed_id:
            errors.append(
                f"content id mismatch: stored={self.fact_id} computed={self.computed_id}"
            )
        if not self.problem_id.strip():
            errors.append("problem_id is empty")
        if "\n" in self.problem_id or "\r" in self.problem_id:
            errors.append("problem_id contains a newline")
        if not self.author.strip():
            errors.append("author is empty")
        if "\n" in self.author or "\r" in self.author:
            errors.append("author contains a newline")
        if not self.statement.strip():
            errors.append("statement is empty")
        if not self.proof.strip():
            errors.append("proof is empty")
        if self.fact_id in self.predecessors:
            errors.append("fact depends on itself")
        return errors

    def as_submission_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "problem_id": self.problem_id,
            "author": self.author,
            "predecessors": self.predecessors,
            "glossary_introduces": self.glossary_introduces,
            "external_refs": self.external_refs,
            "elementary_uses": self.elementary_uses,
            "predecessor_uses": self.predecessor_uses,
            "quantifier_ledger": self.quantifier_ledger,
            "convention_profile_ids": self.convention_profile_ids,
            "computational_evidence": self.computational_evidence,
            "terminology": self.terminology,
            "statement": self.statement,
            "proof": self.proof,
            "intuition": self.intuition,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Fact":
        if not isinstance(payload, dict):
            raise ValueError("fact payload must be one JSON object")
        for key in ("problem_id", "author", "statement", "proof"):
            if not isinstance(payload.get(key), str):
                raise ValueError(f"fact field {key} must be a string")
        fact_id = payload.get("fact_id", "")
        if not isinstance(fact_id, str):
            raise ValueError("fact field fact_id must be a string")
        predecessors = payload.get("predecessors", [])
        if not isinstance(predecessors, list) or any(
            not isinstance(item, str) for item in predecessors
        ):
            raise ValueError("fact field predecessors must be a list of strings")
        glossary = payload.get("glossary_introduces", {})
        if not isinstance(glossary, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in glossary.items()
        ):
            raise ValueError("fact field glossary_introduces must map strings to strings")
        external_refs = payload.get("external_refs", [])
        if not isinstance(external_refs, list) or any(
            not isinstance(item, dict) for item in external_refs
        ):
            raise ValueError("fact field external_refs must be a list of objects")
        elementary_uses = payload.get("elementary_uses", [])
        if not isinstance(elementary_uses, list) or any(
            not isinstance(item, dict) for item in elementary_uses
        ):
            raise ValueError("fact field elementary_uses must be a list of objects")
        predecessor_uses = payload.get("predecessor_uses", [])
        if not isinstance(predecessor_uses, list) or any(
            not isinstance(item, dict) for item in predecessor_uses
        ):
            raise ValueError("fact field predecessor_uses must be a list of objects")
        quantifier_ledger = payload.get("quantifier_ledger", [])
        if not isinstance(quantifier_ledger, list) or any(
            not isinstance(item, dict) for item in quantifier_ledger
        ):
            raise ValueError("fact field quantifier_ledger must be a list of objects")
        convention_profile_ids = payload.get("convention_profile_ids", [])
        if not isinstance(convention_profile_ids, list) or any(
            not isinstance(item, str) for item in convention_profile_ids
        ):
            raise ValueError("fact field convention_profile_ids must be a list of strings")
        computational_evidence = payload.get("computational_evidence", [])
        if not isinstance(computational_evidence, list) or any(
            not isinstance(item, dict) for item in computational_evidence
        ):
            raise ValueError(
                "fact field computational_evidence must be a list of objects"
            )
        terminology = payload.get("terminology", [])
        if not isinstance(terminology, list) or any(
            not isinstance(item, dict) for item in terminology
        ):
            raise ValueError("fact field terminology must be a list of objects")
        intuition = payload.get("intuition", "")
        if not isinstance(intuition, str):
            raise ValueError("fact field intuition must be a string")
        return cls(
            fact_id=fact_id,
            problem_id=payload["problem_id"],
            author=payload["author"],
            predecessors=list(predecessors),
            glossary_introduces=dict(glossary),
            external_refs=[dict(item) for item in external_refs],
            elementary_uses=[dict(item) for item in elementary_uses],
            predecessor_uses=[dict(item) for item in predecessor_uses],
            quantifier_ledger=[dict(item) for item in quantifier_ledger],
            convention_profile_ids=list(convention_profile_ids),
            computational_evidence=[
                dict(item) for item in computational_evidence
            ],
            terminology=[dict(item) for item in terminology],
            statement=payload["statement"],
            proof=payload["proof"],
            intuition=intuition,
        )


@dataclass(slots=True)
class AuditReport:
    facts: int = 0
    edges: int = 0
    targets: int = 0
    target_closure: int = 0
    max_depth: int = 0
    candidates: int = 0
    memory_entries: int = 0
    novelty_entries: int = 0
    graph_errors: list[str] = field(default_factory=list)
    workflow_errors: list[str] = field(default_factory=list)
    blackboard_graph_errors: list[str] = field(default_factory=list)
    blackboard_graph_warnings: list[str] = field(default_factory=list)
    paper_logic_errors: list[str] = field(default_factory=list)
    paper_logic_warnings: list[str] = field(default_factory=list)
    paper_source_nodes: int = 0
    paper_reconstruction_nodes: int = 0
    paper_audit_nodes: int = 0
    historical_workflow_warnings: list[str] = field(default_factory=list)
    trust_debt: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def current_ok(self) -> bool:
        return self.ok

    @property
    def history_clean(self) -> bool:
        return not self.historical_workflow_warnings and not self.trust_debt

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "current_ok": self.current_ok,
            "history_clean": self.history_clean,
            "facts": self.facts,
            "edges": self.edges,
            "targets": self.targets,
            "target_closure": self.target_closure,
            "max_depth": self.max_depth,
            "candidates": self.candidates,
            "memory_entries": self.memory_entries,
            "novelty_entries": self.novelty_entries,
            "graph_errors": self.graph_errors,
            "workflow_errors": self.workflow_errors,
            "current_workflow_errors": self.workflow_errors,
            "blackboard_graph_errors": self.blackboard_graph_errors,
            "blackboard_graph_warnings": self.blackboard_graph_warnings,
            "paper_logic_errors": self.paper_logic_errors,
            "paper_logic_warnings": self.paper_logic_warnings,
            "paper_source_nodes": self.paper_source_nodes,
            "paper_reconstruction_nodes": self.paper_reconstruction_nodes,
            "paper_audit_nodes": self.paper_audit_nodes,
            "historical_workflow_warnings": self.historical_workflow_warnings,
            "trust_debt": self.trust_debt,
            "errors": self.errors,
            "warnings": self.warnings,
        }
