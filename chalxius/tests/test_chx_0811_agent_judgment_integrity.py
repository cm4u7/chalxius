from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class AgentJudgmentIntegrity0811Tests(unittest.TestCase):
    def test_historical_release_contract_remains_declared(self) -> None:
        traceability = _read("references/v5_release_traceability.md")
        self.assertIn("Candidate version: `0.8.11`", traceability)
        self.assertIn("Agent Judgment Integrity", traceability)
        lock = json.loads(_read("INHERITANCE.lock.json"))
        surface = lock["v5_research_cycle_surface"]
        self.assertIn("artifact_silence_alone_is_not_failure", surface["main_worker_recovery_policy"])
        self.assertIn("fresh_whole_successor", surface["cow_supervision_review_policy"])
        self.assertIn("never_adversarial", surface["phx_supervision_boundary"])

    def test_main_uses_visible_evidence_without_a_liveness_mechanism(self) -> None:
        skill = _read("SKILL.md")
        adapter = _read("references/multi_agent_adapter.md")
        protocol = _read("references/agent_protocol_v4.md")
        architecture = _read("references/unified_architecture.md")
        production = _read("references/v5_production_worker_bootstrap.md")
        supervision = _read("references/v5_supervisor_worker_bootstrap.md")
        combined = " ".join(
            "\n".join((skill, adapter, protocol, architecture, production, supervision)).split()
        )
        for marker in (
            "Artifact silence alone is not failure",
            "context compaction",
            "bounded startup reading",
            "deep reasoning",
            "fresh ordinary host status",
            "explicit disconnect/error",
            "sustained total nonresponse",
            "corroborated by more than artifact silence",
        ):
            self.assertIn(marker, combined)
        for excluded in (
            "no timer",
            "heartbeat",
            "watcher",
            "recovery state",
            "gate",
        ):
            self.assertIn(excluded, combined)
        self.assertIn("live-but-unproductive", adapter)
        self.assertIn("not itself loss evidence", production)
        self.assertIn("not itself a repeated status-only milestone", supervision)
        self.assertIn("or evidence of failure", supervision)

    def test_cow_supervision_is_fresh_complete_and_scope_bounded(self) -> None:
        skill = _read("SKILL.md")
        contract = _read("references/v5_supervisor_worker_bootstrap.md")
        modes = _read("references/reasoning_modes.md")
        combined = " ".join("\n".join((skill, contract, modes)).split())
        for marker in (
            "new complete product",
            "mandatory but non-exhaustive attack seeds",
            "not a defect allowlist",
            "whole successor",
            "assigned scope",
            "repair-induced",
            "cross-component",
            "PHX constrains architecture",
            "never narrows",
        ):
            self.assertIn(marker, combined)

if __name__ == "__main__":
    unittest.main()
