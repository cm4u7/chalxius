from __future__ import annotations

import json
import re

from .model import Fact


_SIMPLE_FIELD = re.compile(r"^(fact_id|problem_id|author):\s*(.*)$")
_GLOSSARY_LINE = re.compile(r"^\s{2}([^:]+):\s*(.*)$")
_RESERVED_HEADINGS = ("statement", "proof", "intuition")
_V4_OBJECT_LIST_FIELDS = (
    "predecessor_uses",
    "quantifier_ledger",
    "computational_evidence",
    "terminology",
)


def _decode_scalar(raw: str, field: str) -> str:
    value = raw.strip()
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON string for {field}: {exc}") from exc
        if not isinstance(parsed, str):
            raise ValueError(f"{field} must decode to a string")
        return parsed
    return value


def _parse_inline_list(raw: str, field: str) -> list[str]:
    value = raw.strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        if not (value.startswith("[") and value.endswith("]")):
            raise ValueError(f"invalid {field} list")
        parsed = [item.strip() for item in value[1:-1].split(",") if item.strip()]
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise ValueError(f"{field} must be a list of strings")
    return list(parsed)


def _extract_reserved_sections(lines: list[str]) -> dict[str, str]:
    positions: dict[str, list[int]] = {heading: [] for heading in _RESERVED_HEADINGS}
    for index, line in enumerate(lines):
        match = re.fullmatch(r"##\s+(statement|proof|intuition)\s*", line, re.IGNORECASE)
        if match:
            positions[match.group(1).lower()].append(index)
    for required in ("statement", "proof"):
        if len(positions[required]) != 1:
            raise ValueError(f"fact must contain exactly one ## {required} heading")
    if len(positions["intuition"]) > 1:
        raise ValueError("fact may contain at most one ## intuition heading")
    statement_index = positions["statement"][0]
    proof_index = positions["proof"][0]
    intuition_index = positions["intuition"][0] if positions["intuition"] else None
    if statement_index >= proof_index:
        raise ValueError("## statement must precede ## proof")
    if intuition_index is not None and proof_index >= intuition_index:
        raise ValueError("## intuition must follow ## proof")
    return {
        "statement": "\n".join(lines[statement_index + 1 : proof_index]).strip(),
        "proof": "\n".join(
            lines[proof_index + 1 : intuition_index if intuition_index is not None else len(lines)]
        ).strip(),
        "intuition": ""
        if intuition_index is None
        else "\n".join(lines[intuition_index + 1 :]).strip(),
    }


def extract_section(text: str, heading: str) -> str:
    """Extract one reserved fact section while preserving unrelated level-two headings."""

    if heading.lower() not in _RESERVED_HEADINGS:
        raise ValueError(f"unsupported fact section: {heading}")
    lines = text.splitlines()
    try:
        close = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise ValueError("fact file has no frontmatter terminator") from exc
    return _extract_reserved_sections(lines[close + 1 :])[heading.lower()]


def parse_fact_markdown(text: str) -> Fact:
    """Parse the small Danus-compatible Markdown schema without silent coercion."""

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("fact file does not start with YAML frontmatter")
    try:
        close = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise ValueError("fact file has no frontmatter terminator") from exc

    fields: dict[str, str] = {}
    predecessors: list[str] = []
    glossary: dict[str, str] = {}
    external_refs: list[dict[str, object]] = []
    elementary_uses: list[dict[str, object]] = []
    v4_object_lists: dict[str, list[dict[str, object]]] = {
        field: [] for field in _V4_OBJECT_LIST_FIELDS
    }
    convention_profile_ids: list[str] = []
    in_glossary = False

    for line in lines[1:close]:
        stripped = line.strip()
        simple = _SIMPLE_FIELD.match(stripped)
        if simple:
            fields[simple.group(1)] = _decode_scalar(simple.group(2), simple.group(1))
            in_glossary = False
            continue
        if stripped.startswith("predecessors:"):
            predecessors = _parse_inline_list(
                stripped[len("predecessors:") :].strip(), "predecessors"
            )
            in_glossary = False
            continue
        if stripped.startswith("glossary_introduces:"):
            raw = stripped[len("glossary_introduces:") :].strip()
            if not raw:
                in_glossary = True
            else:
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid glossary_introduces JSON: {exc}") from exc
                if not isinstance(parsed, dict) or any(
                    not isinstance(key, str) or not isinstance(value, str)
                    for key, value in parsed.items()
                ):
                    raise ValueError("glossary_introduces must map strings to strings")
                glossary = dict(parsed)
                in_glossary = False
            continue
        if stripped.startswith("external_refs:"):
            in_glossary = False
            raw = stripped[len("external_refs:") :].strip()
            try:
                parsed = json.loads(raw or "[]")
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid external_refs JSON: {exc}") from exc
            if not isinstance(parsed, list) or any(not isinstance(item, dict) for item in parsed):
                raise ValueError("external_refs must be a list of objects")
            external_refs = [dict(item) for item in parsed]
            continue
        if stripped.startswith("elementary_uses:"):
            in_glossary = False
            raw = stripped[len("elementary_uses:") :].strip()
            try:
                parsed = json.loads(raw or "[]")
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid elementary_uses JSON: {exc}") from exc
            if not isinstance(parsed, list) or any(not isinstance(item, dict) for item in parsed):
                raise ValueError("elementary_uses must be a list of objects")
            elementary_uses = [dict(item) for item in parsed]
            continue
        matched_v4_field = next(
            (
                field
                for field in _V4_OBJECT_LIST_FIELDS
                if stripped.startswith(field + ":")
            ),
            None,
        )
        if matched_v4_field is not None:
            in_glossary = False
            raw = stripped[len(matched_v4_field) + 1 :].strip()
            try:
                parsed = json.loads(raw or "[]")
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid {matched_v4_field} JSON: {exc}"
                ) from exc
            if not isinstance(parsed, list) or any(
                not isinstance(item, dict) for item in parsed
            ):
                raise ValueError(
                    f"{matched_v4_field} must be a list of objects"
                )
            v4_object_lists[matched_v4_field] = [dict(item) for item in parsed]
            continue
        if stripped.startswith("convention_profile_ids:"):
            in_glossary = False
            convention_profile_ids = _parse_inline_list(
                stripped[len("convention_profile_ids:") :].strip(),
                "convention_profile_ids",
            )
            continue
        if in_glossary:
            glossary_match = _GLOSSARY_LINE.match(line)
            if glossary_match:
                glossary[glossary_match.group(1).strip()] = glossary_match.group(2).strip()
                continue
            in_glossary = False
        if stripped:
            raise ValueError(f"unsupported frontmatter line: {line!r}")

    missing = [key for key in ("fact_id", "problem_id", "author") if not fields.get(key)]
    if missing:
        raise ValueError(f"missing frontmatter fields: {', '.join(missing)}")
    sections = _extract_reserved_sections(lines[close + 1 :])

    return Fact(
        fact_id=fields["fact_id"],
        problem_id=fields["problem_id"],
        author=fields["author"],
        predecessors=predecessors,
        glossary_introduces=glossary,
        external_refs=external_refs,
        elementary_uses=elementary_uses,
        predecessor_uses=v4_object_lists["predecessor_uses"],
        quantifier_ledger=v4_object_lists["quantifier_ledger"],
        convention_profile_ids=convention_profile_ids,
        computational_evidence=v4_object_lists["computational_evidence"],
        terminology=v4_object_lists["terminology"],
        statement=sections["statement"],
        proof=sections["proof"],
        intuition=sections["intuition"],
    )


def serialize_fact(fact: Fact) -> str:
    lines = [
        "---",
        f"fact_id: {fact.fact_id}",
        "problem_id: " + json.dumps(fact.problem_id, ensure_ascii=False),
        "author: " + json.dumps(fact.author, ensure_ascii=False),
        "predecessors: "
        + json.dumps(fact.predecessors, ensure_ascii=False, separators=(",", ":")),
        "glossary_introduces: "
        + json.dumps(
            fact.glossary_introduces,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
        "external_refs: "
        + json.dumps(
            fact.external_refs,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
        "elementary_uses: "
        + json.dumps(
            fact.elementary_uses,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
    ]
    if fact.predecessor_uses:
        lines.append(
            "predecessor_uses: "
            + json.dumps(
                fact.predecessor_uses,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    if fact.quantifier_ledger:
        lines.append(
            "quantifier_ledger: "
            + json.dumps(
                fact.quantifier_ledger,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    if fact.convention_profile_ids:
        lines.append(
            "convention_profile_ids: "
            + json.dumps(
                fact.convention_profile_ids,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    if fact.computational_evidence:
        lines.append(
            "computational_evidence: "
            + json.dumps(
                fact.computational_evidence,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    if fact.terminology:
        lines.append(
            "terminology: "
            + json.dumps(
                fact.terminology,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    lines.extend(
        [
            "---",
            "",
            "## statement",
            fact.statement.strip(),
            "",
            "## proof",
            fact.proof.strip(),
        ]
    )
    if fact.intuition.strip():
        lines.extend(["", "## intuition", fact.intuition.strip()])
    lines.append("")
    return "\n".join(lines)


def validate_fact_round_trip(fact: Fact) -> str:
    rendered = serialize_fact(fact)
    parsed = parse_fact_markdown(rendered)
    if parsed.as_submission_dict() != fact.as_submission_dict():
        raise ValueError("fact does not round-trip through the Markdown schema")
    if parsed.computed_id != fact.fact_id:
        raise ValueError("round-tripped fact does not preserve its content id")
    return rendered


def statement_snippet(text: str, limit: int = 180) -> str:
    statement = re.sub(r"\s+", " ", extract_section(text, "statement")).strip()
    if len(statement) <= limit:
        return statement
    return statement[: limit - 1].rstrip() + "…"
