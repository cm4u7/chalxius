from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable

from .model import Fact


class DependencyGraph:
    def __init__(self, facts: dict[str, Fact]) -> None:
        self.facts = facts
        self.predecessors = {
            fact_id: list(fact.predecessors) for fact_id, fact in facts.items()
        }
        self.successors: dict[str, list[str]] = defaultdict(list)
        for fact_id, predecessors in self.predecessors.items():
            for predecessor in predecessors:
                self.successors[predecessor].append(fact_id)
        for successors in self.successors.values():
            successors.sort()

    def missing_predecessors(self) -> list[tuple[str, str]]:
        return sorted(
            (fact_id, predecessor)
            for fact_id, predecessors in self.predecessors.items()
            for predecessor in predecessors
            if predecessor not in self.facts
        )

    def topological_order(self, subset: Iterable[str] | None = None) -> list[str]:
        selected = set(subset) if subset is not None else set(self.facts)
        indegree = {
            fact_id: sum(1 for pred in self.predecessors[fact_id] if pred in selected)
            for fact_id in selected
        }
        ready = deque(sorted(fact_id for fact_id, degree in indegree.items() if degree == 0))
        order: list[str] = []
        while ready:
            fact_id = ready.popleft()
            order.append(fact_id)
            for successor in self.successors.get(fact_id, []):
                if successor not in indegree:
                    continue
                indegree[successor] -= 1
                if indegree[successor] == 0:
                    ready.append(successor)
        if len(order) != len(selected):
            cycle_nodes = sorted(selected.difference(order))
            raise ValueError(f"dependency cycle involving: {', '.join(cycle_nodes[:12])}")
        return order

    def closure(self, targets: Iterable[str]) -> set[str]:
        selected: set[str] = set()
        stack = list(targets)
        while stack:
            fact_id = stack.pop()
            if fact_id in selected:
                continue
            if fact_id not in self.facts:
                raise KeyError(f"unknown fact: {fact_id}")
            selected.add(fact_id)
            stack.extend(self.predecessors[fact_id])
        return selected

    def descendants(self, roots: Iterable[str]) -> set[str]:
        selected: set[str] = set()
        stack = list(roots)
        while stack:
            fact_id = stack.pop()
            for successor in self.successors.get(fact_id, []):
                if successor not in selected:
                    selected.add(successor)
                    stack.append(successor)
        return selected

    def depths(self) -> dict[str, int]:
        depths: dict[str, int] = {}
        for fact_id in self.topological_order():
            pred_depths = [depths[pred] for pred in self.predecessors[fact_id]]
            depths[fact_id] = 0 if not pred_depths else 1 + max(pred_depths)
        return depths

