#!/usr/bin/env python3
"""Public host wrapper for the neutral-verifier draft return gate."""

import sys


sys.dont_write_bytecode = True

from mathgraph.neutral_review_submission import main


if __name__ == "__main__":
    raise SystemExit(main())
