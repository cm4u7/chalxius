"""Local, verifier-gated mathematical fact-graph engine."""

import sys
import importlib.util
import os


# The installed skill is a source runtime; importing it must not leave a new
# package cache in the manifest-bound tree.  Package bytecode is decided after
# this module returns, so remove only this exact interpreter cache after
# disabling all later writes.  A protected installation simply keeps any
# pre-existing cache because unlinking fails closed; no semantic project state
# is changed.
sys.dont_write_bytecode = True
_self_cache = importlib.util.cache_from_source(__file__)
try:
    os.unlink(_self_cache)
except OSError:
    pass
try:
    os.rmdir(os.path.dirname(_self_cache))
except OSError:
    pass

from .model import Fact, compute_fact_id
from .store import MathGraphStore

__all__ = ["Fact", "MathGraphStore", "compute_fact_id"]
