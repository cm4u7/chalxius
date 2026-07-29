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
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--bundle-sha256")
    selector.add_argument("--release-id")
    selector.add_argument("--capsule-id")
    selector.add_argument("--capsule-json", type=Path)
    parser.add_argument("--capsule-root", type=Path, required=True)
    args = parser.parse_args()
    result = prepare_verifier_capsule(
        project_root=args.project_root,
        bundle_sha256=args.bundle_sha256,
        release_id=args.release_id,
        capsule_id=args.capsule_id,
        capsule_json=args.capsule_json,
        capsule_root=args.capsule_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
