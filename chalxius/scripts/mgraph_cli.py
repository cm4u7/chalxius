#!/usr/bin/env python3

import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

_launcher = Path(__file__).resolve()
for _parent in _launcher.parents:
    if (_parent / "SKILL.md").is_file():
        os.environ.setdefault("MGRAPH_SKILL_ROOT", str(_parent))
        break

from mathgraph.cli import main

raise SystemExit(main())
