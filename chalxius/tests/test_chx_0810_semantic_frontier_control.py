from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SemanticFrontierControl0810Tests(unittest.TestCase):
    def test_named_frontier_search_is_a_main_instruction(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        protocol = (ROOT / "references" / "agent_protocol_v4.md").read_text(
            encoding="utf-8"
        )
        architecture = (
            ROOT / "references" / "unified_architecture.md"
        ).read_text(encoding="utf-8")

        for document in (skill, protocol, architecture):
            normalized = " ".join(document.split())
            self.assertIn("bounded exact Research search", normalized)
            self.assertIn("completed production", normalized)
            self.assertIn("repair", normalized)
            self.assertIn("supervision", normalized)
            self.assertIn("related_research_ids", normalized)

        normalized_skill = " ".join(skill.split())
        normalized_protocol = " ".join(protocol.split())
        self.assertIn("and choose `related_research_ids`", normalized_skill)
        self.assertIn("no automatic selection/expansion", normalized_skill)
        self.assertIn("not automatic expansion", normalized_protocol)

    def test_release_contract_excludes_a_new_mechanism_or_gate(self) -> None:
        self.assertEqual(
            (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
            "0.8.10",
        )
        lock = json.loads(
            (ROOT / "INHERITANCE.lock.json").read_text(encoding="utf-8")
        )
        self.assertEqual(lock["version"], "0.8.10")
        self.assertEqual(lock["release_codename"], "Semantic Frontier Control")
        contract = lock["candidate_admission_efficiency_surface"]
        semantic = contract["named_frontier_semantic_selection"]
        for excluded in (
            "without_automatic_expansion",
            "index",
            "receipt",
            "state",
            "scheduler",
            "gate",
        ):
            self.assertIn(excluded, semantic)
        self.assertFalse(contract["persistent_cache"])
        self.assertEqual(contract["candidate_effect"], "none_until_existing_candidate_release_command")
        self.assertEqual(contract["fact_effect"], "none")
        self.assertEqual(contract["truth_effect"], "none")


if __name__ == "__main__":
    unittest.main()
