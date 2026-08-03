#!/usr/bin/env python3
"""Build one approved, reusable protected-project cutover validation receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

from mathgraph.runtime_cutover import build_cutover_project_validation_receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--installed-root", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--expected-request-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    receipt = build_cutover_project_validation_receipt(
        candidate_root=args.candidate_root,
        installed_root=args.installed_root,
        archive_root=args.archive_root,
        request_path=args.request,
        expected_request_sha256=args.expected_request_sha256,
        output_path=args.output,
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
