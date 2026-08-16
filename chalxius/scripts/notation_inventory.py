#!/usr/bin/env python3
"""Print a conservative first-occurrence inventory of notation in Markdown math.

This is a review aid, not a semantic proof that every symbol is defined.  It is
deliberately standard-library-only so the portable MathGraph skill can run it
before a fresh reader performs the notation-closure audit.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.dont_write_bytecode = True


CONTROL_WORDS = {
    "begin",
    "big",
    "bigg",
    "biggl",
    "biggr",
    "Big",
    "Bigg",
    "Biggl",
    "Biggr",
    "Bigl",
    "Bigr",
    "binom",
    "boxed",
    "cdot",
    "cdots",
    "cong",
    "dfrac",
    "displaystyle",
    "dots",
    "end",
    "ge",
    "geq",
    "hspace",
    "in",
    "left",
    "le",
    "leq",
    "longleftarrow",
    "longrightarrow",
    "mapsto",
    "mid",
    "ne",
    "neq",
    "notin",
    "operatorname",
    "overline",
    "qquad",
    "quad",
    "right",
    "rm",
    "setminus",
    "sim",
    "simeq",
    "sqrt",
    "substack",
    "subset",
    "subseteq",
    "supset",
    "supseteq",
    "text",
    "textbf",
    "textit",
    "tfrac",
    "times",
    "to",
    "underbrace",
    "widehat",
}

STANDARD_ATOMS = {
    "d",
    "e",
    "i",
    "id",
    "lim",
    "log",
    "max",
    "min",
    "mod",
    "Res",
    "sin",
    "cos",
    "sup",
}

SUFFIX_ATOM = r"(?:\{[^{}]*\}|\\[A-Za-z]+|[A-Za-z0-9+-])"
SUFFIX = rf"(?:\s*[_^]{SUFFIX_ATOM})*"
COMMAND_PATTERN = re.compile(rf"\\([A-Za-z]+)({SUFFIX})")
LETTER_PATTERN = re.compile(
    r"(?<![A-Za-z\\])([A-Za-z](?:(?:[_^](?:\{[^{}]*\}|[A-Za-z0-9+-]))+)?)(?![A-Za-z])"
)
WRAPPED_PATTERN = re.compile(
    r"\\(mathcal|mathbb|mathbf|mathrm|operatorname|widehat|bar|overline)"
    rf"\s*\{{([^{{}}]+)\}}({SUFFIX})"
)
STYLED_LETTER_PATTERN = re.compile(
    rf"\\(mathcal|mathbb|mathbf|mathrm)\s+([A-Za-z])({SUFFIX})"
)
INLINE_MATH_PATTERN = re.compile(r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$(?!\$)")
PAREN_MATH_PATTERN = re.compile(r"\\\((.+?)\\\)")
BRACKET_MATH_PATTERN = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)


@dataclass(frozen=True)
class Occurrence:
    line: int
    snippet: str


def normalize_suffix(suffix: str) -> str:
    return re.sub(r"\s+", "", suffix)


def math_fragments(lines: list[str], start_line: int = 1):
    # Bracket displays routinely span several Markdown lines.  Scan them over
    # the whole selected suffix first; the line-by-line expression below
    # intentionally handles only inline \(...\), so no fragment is duplicated.
    selected = "\n".join(lines[start_line - 1 :])
    for match in BRACKET_MATH_PATTERN.finditer(selected):
        line = start_line + selected.count("\n", 0, match.start())
        yield line, match.group(1)

    in_display = False
    display_start = 0
    display_parts: list[str] = []
    for number, line in enumerate(lines, 1):
        if number < start_line:
            continue
        remaining = line
        while "$$" in remaining:
            before, remaining = remaining.split("$$", 1)
            if in_display:
                display_parts.append(before)
                yield display_start, " ".join(display_parts)
                display_parts = []
                in_display = False
            else:
                for match in INLINE_MATH_PATTERN.finditer(before):
                    yield number, match.group(1)
                for match in PAREN_MATH_PATTERN.finditer(before):
                    yield number, match.group(1)
                display_start = number
                display_parts = []
                in_display = True
        if in_display:
            display_parts.append(remaining)
        else:
            for match in INLINE_MATH_PATTERN.finditer(remaining):
                yield number, match.group(1)
            for match in PAREN_MATH_PATTERN.finditer(remaining):
                yield number, match.group(1)
    if in_display and display_parts:
        yield display_start, " ".join(display_parts)


def extract_symbols(fragment: str) -> set[str]:
    symbols: set[str] = set()
    masked = fragment

    for match in WRAPPED_PATTERN.finditer(fragment):
        wrapper, body, suffix = match.groups()
        body = re.sub(r"\s+", "", body)
        if body and not body.startswith("text"):
            symbols.add(f"\\{wrapper}{{{body}}}{normalize_suffix(suffix)}")

    for match in STYLED_LETTER_PATTERN.finditer(fragment):
        wrapper, body, suffix = match.groups()
        symbols.add(f"\\{wrapper}{{{body}}}{normalize_suffix(suffix)}")

    for match in COMMAND_PATTERN.finditer(masked):
        command, suffix = match.groups()
        if command in CONTROL_WORDS:
            continue
        symbol = f"\\{command}{normalize_suffix(suffix)}"
        symbols.add(symbol)

    stripped = re.sub(r"\\[A-Za-z]+", " ", masked)
    stripped = re.sub(r"\\.", " ", stripped)
    for match in LETTER_PATTERN.finditer(stripped):
        symbol = normalize_suffix(match.group(1))
        if symbol in STANDARD_ATOMS:
            continue
        symbols.add(symbol)
    return symbols


def inventory(markdown: str, *, start_line: int = 1) -> list[dict[str, object]]:
    lines = markdown.splitlines()
    first: dict[str, Occurrence] = {}
    counts: Counter[str] = Counter()
    for line, fragment in math_fragments(lines, start_line=start_line):
        snippet = re.sub(r"\s+", " ", fragment).strip()
        if len(snippet) > 180:
            snippet = snippet[:177] + "..."
        for symbol in extract_symbols(fragment):
            counts[symbol] += 1
            first.setdefault(symbol, Occurrence(line=line, snippet=snippet))
    return [
        {
            "symbol": symbol,
            "first_line": occurrence.line,
            "occurrences": counts[symbol],
            "first_snippet": occurrence.snippet,
        }
        for symbol, occurrence in sorted(
            first.items(), key=lambda item: (item[1].line, item[0])
        )
    ]


def heading_start(markdown: str, heading: str | None) -> int:
    if not heading:
        return 1
    for line_number, line in enumerate(markdown.splitlines(), 1):
        if line.lstrip().startswith("#") and heading.casefold() in line.casefold():
            return line_number
    raise ValueError(f"heading not found: {heading}")


def markdown_report(path: Path, start_line: int, items: list[dict[str, object]]) -> str:
    rows = [
        "# Notation first-occurrence inventory",
        "",
        f"Source: `{path}`",
        f"Scan starts at line: `{start_line}`",
        "",
        "> Mechanical candidate list only. A fresh reader must still decide whether each",
        "> symbol is standard, defined before use, correctly typed, and collision-free.",
        "",
        "| Symbol | First line | Count | First mathematical context |",
        "|---|---:|---:|---|",
    ]
    for item in items:
        symbol = str(item["symbol"]).replace("|", "\\|")
        snippet = str(item["first_snippet"]).replace("|", "\\|")
        rows.append(
            f"| `${symbol}` | {item['first_line']} | {item['occurrences']} | `${snippet}` |"
        )
    return "\n".join(rows) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=Path)
    parser.add_argument(
        "--from-heading",
        help="Start at the first Markdown heading containing this text (case-insensitive).",
    )
    parser.add_argument(
        "--format", choices=("markdown", "json"), default="markdown"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        source = args.markdown.read_text(encoding="utf-8")
        start = heading_start(source, args.from_heading)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"notation-inventory: {error}", file=sys.stderr)
        return 2
    items = inventory(source, start_line=start)
    if args.format == "json":
        print(
            json.dumps(
                {
                    "source": str(args.markdown.resolve()),
                    "start_line": start,
                    "symbols": items,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(markdown_report(args.markdown, start, items), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
