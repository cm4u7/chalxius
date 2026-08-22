"""Focused CHX-003 regressions for prospective source assurance."""

from __future__ import annotations

from copy import deepcopy
import unittest

from mathgraph.contracts import sha256_bytes
from mathgraph.v5_assurance import (
    build_assurance_contract,
    validate_return_assurance,
)
from mathgraph.v5_lifecycle import V5LifecycleManager


class Chx089SourceAssuranceTests(unittest.TestCase):
    @staticmethod
    def _blank_assurance() -> dict[str, list[object]]:
        return {
            "source_uses": [],
            "route_invalidations": [],
            "extremal_cases": [],
            "claim_strength": [],
            "contour_substitutions": [],
            "claimed_structures": [],
            "program_math_alignments": [],
        }

    def test_source_assurance_structural_activation_positive(self) -> None:
        primary_sha = sha256_bytes(b"primary source")
        cases = [
            (
                "literature mode",
                {"claim": "Literature task.", "metadata": {}},
                [],
                "literature",
                [],
                {"source_use_required"},
            ),
            (
                "source dependent metadata",
                {
                    "claim": "Source-dependent proof.",
                    "metadata": {"source_dependent": True},
                },
                [],
                "prove",
                [],
                {"source_use_required"},
            ),
            (
                "primary plus source evidence",
                {"claim": "Primary-source theorem.", "metadata": {}},
                [
                    {
                        "obligation_id": "source-obligation",
                        "description": "Use the primary theorem.",
                        "evidence_types": ["primary+source"],
                    }
                ],
                "prove",
                [],
                {"source_use_required"},
            ),
            (
                "theorem plus locator evidence",
                {"claim": "Located theorem.", "metadata": {}},
                [
                    {
                        "obligation_id": "locator-obligation",
                        "description": "Locate the theorem.",
                        "evidence_types": ["theorem+locator"],
                    }
                ],
                "prove",
                [],
                {"source_use_required", "source_applicability_required"},
            ),
            (
                "applicability role",
                {"claim": "Check applicability.", "metadata": {}},
                [
                    {
                        "obligation_id": "applicability-obligation",
                        "description": "Check the hypotheses.",
                        "required_artifact_roles": ["theorem_applicability"],
                        "evidence_types": ["bounded_argument"],
                    }
                ],
                "prove",
                [],
                {"source_use_required", "source_applicability_required"},
            ),
            (
                "exact primary capability",
                {"claim": "Use frozen source bytes.", "metadata": {}},
                [],
                "prove",
                [
                    {
                        "path": "sources/paper.tex",
                        "role": "paper-primary.tex",
                        "sha256": primary_sha,
                    }
                ],
                {"source_use_required"},
            ),
        ]
        for label, entry, obligations, work_mode, related_artifacts, expected in cases:
            with self.subTest(label=label):
                contract = build_assurance_contract(
                    entry=entry,
                    obligations=obligations,
                    work_mode=work_mode,
                    related_artifacts=related_artifacts,
                )
                self.assertTrue(expected.issubset(set(contract["risk_signals"])))

    def test_source_assurance_structural_activation_predicate_false(self) -> None:
        invalid_sha = "g" * 64
        ordinary = build_assurance_contract(
            entry={"claim": "Internal argument.", "metadata": {}},
            obligations=[
                {
                    "obligation_id": "internal-proof",
                    "description": "Prove the internal lemma.",
                    "required_artifact_roles": ["proof_report"],
                    "evidence_types": ["bounded_argument"],
                }
            ],
            work_mode="prove",
            related_artifacts=[
                {
                    "path": "work/primary.txt",
                    "role": "primarysource",
                    "sha256": sha256_bytes(b"not a standalone role token"),
                },
                {
                    "path": "work/invalid-primary.txt",
                    "role": "primary_source",
                    "sha256": invalid_sha,
                },
                {
                    "path": "",
                    "role": "another_primary_source",
                    "sha256": sha256_bytes(b"missing path capability"),
                },
            ],
        )
        self.assertFalse(
            {"source_use_required", "source_applicability_required"}.intersection(
                ordinary["risk_signals"]
            )
        )

        computation = build_assurance_contract(
            entry={"claim": "Run an internal computation.", "metadata": {}},
            obligations=[
                {
                    "obligation_id": "program-source",
                    "description": "Return the program source.",
                    "required_artifact_roles": [
                        "computation_source",
                        "executable_source",
                        "program_source",
                        "source_code",
                    ],
                    "evidence_types": ["executable_source"],
                }
            ],
            work_mode="compute",
            related_artifacts=[],
        )
        self.assertNotIn("source_use_required", computation["risk_signals"])
        self.assertNotIn(
            "source_applicability_required", computation["risk_signals"]
        )

    def test_primary_capability_role_tokens_match_lifecycle_extraction(self) -> None:
        plus_sha = sha256_bytes(b"plus-delimited primary")
        space_sha = sha256_bytes(b"space-delimited primary")
        concatenated_sha = sha256_bytes(b"not a standalone primary token")
        related_artifacts = [
            {
                "path": "sources/plus.pdf",
                "role": "paper+primary+source",
                "sha256": plus_sha,
            },
            {
                "path": "sources/space.tex",
                "role": "paper primary tex",
                "sha256": space_sha,
            },
            {
                "path": "sources/concatenated.txt",
                "role": "paper_primarysource",
                "sha256": concatenated_sha,
            },
        ]
        contract = build_assurance_contract(
            entry={"claim": "Use frozen capabilities.", "metadata": {}},
            obligations=[],
            work_mode="prove",
            related_artifacts=related_artifacts,
        )
        self.assertIn("source_use_required", contract["risk_signals"])
        card = {"mathematical_state": {"related_artifacts": related_artifacts}}
        self.assertEqual(
            V5LifecycleManager._task_primary_source_sha256s(card),
            {plus_sha, space_sha},
        )

    def test_source_assurance_structural_activation_tamper(self) -> None:
        primary_sha = sha256_bytes(b"frozen primary")
        source_report_sha = sha256_bytes(b"source dossier")
        applicability_sha = sha256_bytes(b"applicability map")
        contract = build_assurance_contract(
            entry={"claim": "Use and transport two source results.", "metadata": {}},
            obligations=[
                {
                    "obligation_id": "source-obligation",
                    "description": "Bind the primary result.",
                    "required_artifact_roles": ["source_dossier"],
                    "evidence_types": ["primary_source"],
                },
                {
                    "obligation_id": "applicability-obligation",
                    "description": "Check theorem hypotheses.",
                    "required_artifact_roles": ["theorem_applicability"],
                    "evidence_types": ["theorem_locator"],
                },
            ],
            work_mode="prove",
            related_artifacts=[
                {
                    "path": "sources/primary.pdf",
                    "role": "primary_source",
                    "sha256": primary_sha,
                }
            ],
        )
        artifacts = [
            {
                "path": "source-dossier.md",
                "role": "source_dossier",
                "sha256": source_report_sha,
            },
            {
                "path": "applicability.md",
                "role": "theorem_applicability",
                "sha256": applicability_sha,
            },
        ]
        payload: dict[str, object] = {
            "outcome": "proof",
            "obligation_dispositions": [
                {
                    "obligation_id": "source-obligation",
                    "status": "complete",
                    "witness_artifact_sha256s": [source_report_sha],
                    "rationale": "The source dossier is complete.",
                },
                {
                    "obligation_id": "applicability-obligation",
                    "status": "complete",
                    "witness_artifact_sha256s": [applicability_sha],
                    "rationale": "The hypothesis map is complete.",
                },
            ],
            "computation_manifest": None,
            "research_assurance": self._blank_assurance(),
        }
        payload["research_assurance"]["source_uses"] = [  # type: ignore[index]
            {
                "source_key": "source-obligation",
                "use_kind": "result",
                "source_strength": "fixed_object",
                "target_strength": "fixed_object",
                "source_artifact_sha256": primary_sha,
                "toy_check_artifact_sha256": None,
                "bridge_artifact_sha256s": [source_report_sha],
            },
            {
                "source_key": "applicability-obligation",
                "use_kind": "result",
                "source_strength": "fixed_object",
                "target_strength": "fixed_object",
                "source_artifact_sha256": primary_sha,
                "toy_check_artifact_sha256": None,
                "bridge_artifact_sha256s": [applicability_sha],
            },
        ]
        validate_return_assurance(
            payload=payload,
            contract=contract,
            artifacts=artifacts,
            task_primary_source_sha256s={primary_sha},
        )

        empty = deepcopy(payload)
        empty["research_assurance"]["source_uses"] = []  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "nonempty source_uses"):
            validate_return_assurance(
                payload=empty,
                contract=contract,
                artifacts=artifacts,
                task_primary_source_sha256s={primary_sha},
            )

        missing_key = deepcopy(payload)
        missing_key["research_assurance"]["source_uses"] = [  # type: ignore[index]
            payload["research_assurance"]["source_uses"][0]  # type: ignore[index]
        ]
        with self.assertRaisesRegex(ValueError, "exact source_key"):
            validate_return_assurance(
                payload=missing_key,
                contract=contract,
                artifacts=artifacts,
                task_primary_source_sha256s={primary_sha},
            )

        missing_required_witness = deepcopy(payload)
        missing_required_witness["research_assurance"]["source_uses"][1][  # type: ignore[index]
            "bridge_artifact_sha256s"
        ] = []
        with self.assertRaisesRegex(ValueError, "required-role witnesses"):
            validate_return_assurance(
                payload=missing_required_witness,
                contract=contract,
                artifacts=artifacts,
                task_primary_source_sha256s={primary_sha},
            )

        unbound_source = deepcopy(payload)
        unbound_source["research_assurance"]["source_uses"][0][  # type: ignore[index]
            "source_artifact_sha256"
        ] = sha256_bytes(b"unbound")
        with self.assertRaisesRegex(ValueError, "not bound"):
            validate_return_assurance(
                payload=unbound_source,
                contract=contract,
                artifacts=artifacts,
                task_primary_source_sha256s={primary_sha},
            )

    def test_frozen_empty_risk_signal_contract_remains_readable(self) -> None:
        contract = build_assurance_contract(
            entry={"claim": "Historical literature card.", "metadata": {}},
            obligations=[],
            work_mode="literature",
            related_artifacts=[],
        )
        self.assertIn("source_use_required", contract["risk_signals"])
        contract["risk_signals"] = []
        payload = {
            "outcome": "insight",
            "obligation_dispositions": [],
            "computation_manifest": None,
            "research_assurance": self._blank_assurance(),
        }
        validate_return_assurance(
            payload=payload,
            contract=contract,
            artifacts=[],
        )

    def test_source_assurance_rejects_unbound_declared_witness_without_required_roles(
        self,
    ) -> None:
        primary_sha = sha256_bytes(b"primary theorem bytes")
        extra_witness_sha = sha256_bytes(b"declared but source-unbound witness")
        contract = build_assurance_contract(
            entry={"claim": "Apply a primary theorem.", "metadata": {}},
            obligations=[
                {
                    "obligation_id": "source-obligation",
                    "description": "Apply the primary theorem.",
                    "required_artifact_roles": [],
                    "evidence_types": ["primary source"],
                }
            ],
            work_mode="prove",
            related_artifacts=[
                {
                    "path": "sources/theorem.pdf",
                    "role": "paper+primary+source",
                    "sha256": primary_sha,
                }
            ],
        )
        payload = {
            "outcome": "proof",
            "obligation_dispositions": [
                {
                    "obligation_id": "source-obligation",
                    "status": "complete",
                    "witness_artifact_sha256s": [extra_witness_sha],
                    "rationale": "The declared witness supports the application.",
                }
            ],
            "computation_manifest": None,
            "research_assurance": self._blank_assurance(),
        }
        payload["research_assurance"]["source_uses"] = [
            {
                "source_key": "source-obligation",
                "use_kind": "result",
                "source_strength": "fixed_object",
                "target_strength": "fixed_object",
                "source_artifact_sha256": primary_sha,
                "toy_check_artifact_sha256": None,
                "bridge_artifact_sha256s": [],
            }
        ]
        artifacts = [
            {
                "path": "extra-witness.md",
                "role": "supporting_report",
                "sha256": extra_witness_sha,
            }
        ]
        with self.assertRaisesRegex(ValueError, "declared disposition witnesses"):
            validate_return_assurance(
                payload=payload,
                contract=contract,
                artifacts=artifacts,
                task_primary_source_sha256s={primary_sha},
            )


if __name__ == "__main__":
    unittest.main()
