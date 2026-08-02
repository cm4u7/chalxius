#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mathgraph.runtime_archive import (
    archive_runtime,
    read_json_file_nofollow,
    runtime_binding_from_root,
    validate_runtime_binding,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Archive one exact Chalxius runtime for historical task-card reads."
    )
    parser.add_argument("--source-root", required=True)
    parser.add_argument(
        "--archive-root",
        help=(
            "Host-managed archive root outside skill discovery; defaults to the "
            "current runtime's Codex host archive root."
        ),
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--task-card")
    source.add_argument("--binding-input")
    parser.add_argument(
        "--bound-skill-root",
        help="Original task-card skill_root; defaults to --source-root.",
    )
    parser.add_argument("--expected-runtime-identity")
    return parser


def _binding(args: argparse.Namespace) -> dict[str, object]:
    if args.task_card:
        card = read_json_file_nofollow(
            Path(args.task_card), label="Chalxius archive task card"
        )
        if not isinstance(card, dict) or "runtime_binding" not in card:
            raise ValueError("task card has no runtime_binding")
        return validate_runtime_binding(card["runtime_binding"])
    if args.binding_input:
        return validate_runtime_binding(
            read_json_file_nofollow(
                Path(args.binding_input),
                label="Chalxius archive runtime-binding input",
            )
        )
    return runtime_binding_from_root(
        Path(args.source_root),
        bound_skill_root=(
            Path(args.bound_skill_root) if args.bound_skill_root else None
        ),
        archive_root=(Path(args.archive_root) if args.archive_root else None),
    )


def main() -> int:
    args = _parser().parse_args()
    binding = _binding(args)
    if args.bound_skill_root and binding["skill_root"] != str(Path(args.bound_skill_root)):
        raise ValueError("supplied bound skill root disagrees with runtime binding")
    if (
        args.expected_runtime_identity
        and binding["runtime_identity_sha256"] != args.expected_runtime_identity
    ):
        raise ValueError("runtime identity differs from --expected-runtime-identity")
    receipt = archive_runtime(
        Path(args.source_root),
        binding,
        archive_root=(Path(args.archive_root) if args.archive_root else None),
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
