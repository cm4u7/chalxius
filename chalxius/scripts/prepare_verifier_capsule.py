#!/usr/bin/env python3
"""Prepare an externally located, exact-byte fresh-verifier capsule."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mathgraph.verifier_capsule import prepare_verifier_capsule


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--capsule-root", type=Path, required=True)
    args = parser.parse_args()
    result = prepare_verifier_capsule(
        project_root=args.project_root,
        bundle_sha256=args.bundle_sha256,
        capsule_root=args.capsule_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
