"""Local, verifier-gated mathematical fact-graph engine."""

from .model import Fact, compute_fact_id
from .store import MathGraphStore

__all__ = ["Fact", "MathGraphStore", "compute_fact_id"]

