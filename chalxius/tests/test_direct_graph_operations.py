"""Focused regressions for direct Fact and primary-source graph operations."""

from __future__ import annotations

import unittest

from mathgraph.contracts import sha256_bytes
from mathgraph.v5_assurance import (
    build_assurance_contract,
    validate_return_assurance,
)
from mathgraph.v5_lifecycle import V5LifecycleManager


class DirectGraphOperationTests(unittest.TestCase):
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

    @classmethod
    def _fixture(
        cls,
    ) -> tuple[dict[str, object], dict[str, object], list[dict[str, str]]]:
        contract = build_assurance_contract(
            entry={"claim": "Use one exact primary source.", "metadata": {}},
            obligations=[],
            work_mode="literature",
            related_artifacts=[],
        )
        payload: dict[str, object] = {
            "outcome": "insight",
            "obligation_dispositions": [],
            "computation_manifest": None,
            "research_assurance": cls._blank_assurance(),
        }
        artifacts = [
            {
                "path": "analysis.md",
                "role": "analytic_bridge_report",
                "sha256": sha256_bytes(b"analytic bridge"),
            },
            {
                "path": "toy.txt",
                "role": "toy_check",
                "sha256": sha256_bytes(b"toy check"),
            },
        ]
        return contract, payload, artifacts

    def test_task_card_primary_source_needs_no_returned_byte_copy(self) -> None:
        contract, payload, artifacts = self._fixture()
        primary_sha = sha256_bytes(b"frozen primary source")
        payload["research_assurance"]["source_uses"] = [  # type: ignore[index]
            {
                "source_key": "SOURCE-THEOREM",
                "use_kind": "result",
                "source_strength": "fixed_object",
                "target_strength": "fixed_object",
                "source_artifact_sha256": primary_sha,
                "toy_check_artifact_sha256": None,
                "bridge_artifact_sha256s": [],
            }
        ]

        validate_return_assurance(
            payload=payload,
            contract=contract,
            artifacts=artifacts,
            task_primary_source_sha256s={primary_sha},
        )

    def test_existing_returned_source_remains_valid_with_primary_capability(self) -> None:
        contract, payload, artifacts = self._fixture()
        primary_sha = sha256_bytes(b"frozen primary source")
        payload["research_assurance"]["source_uses"] = [  # type: ignore[index]
            {
                "source_key": "SOURCE-THEOREM",
                "use_kind": "result",
                "source_strength": "fixed_object",
                "target_strength": "fixed_object",
                "source_artifact_sha256": artifacts[0]["sha256"],
                "toy_check_artifact_sha256": None,
                "bridge_artifact_sha256s": [],
            }
        ]

        validate_return_assurance(
            payload=payload,
            contract=contract,
            artifacts=artifacts,
            task_primary_source_sha256s={primary_sha},
        )

    def test_toy_and_bridge_witnesses_remain_return_artifact_bound(self) -> None:
        contract, payload, artifacts = self._fixture()
        primary_sha = sha256_bytes(b"frozen primary source")
        payload["research_assurance"]["source_uses"] = [  # type: ignore[index]
            {
                "source_key": "SOURCE-FORMULA",
                "use_kind": "formula",
                "source_strength": "fixed_object",
                "target_strength": "relative_family",
                "source_artifact_sha256": primary_sha,
                "toy_check_artifact_sha256": primary_sha,
                "bridge_artifact_sha256s": [primary_sha],
            }
        ]

        with self.assertRaisesRegex(ValueError, "artifact-bound toy check"):
            validate_return_assurance(
                payload=payload,
                contract=contract,
                artifacts=artifacts,
                task_primary_source_sha256s={primary_sha},
            )
        payload["research_assurance"]["source_uses"][0][  # type: ignore[index]
            "toy_check_artifact_sha256"
        ] = artifacts[1]["sha256"]
        with self.assertRaisesRegex(ValueError, "source bridge is not artifact-bound"):
            validate_return_assurance(
                payload=payload,
                contract=contract,
                artifacts=artifacts,
                task_primary_source_sha256s={primary_sha},
            )

    def test_only_explicit_primary_roles_activate_direct_source_binding(self) -> None:
        primary_sha = sha256_bytes(b"primary")
        analytic_sha = sha256_bytes(b"analysis")
        card = {
            "mathematical_state": {
                "related_artifacts": [
                    {
                        "path": "source.tex",
                        "sha256": primary_sha,
                        "role": "abc123:dendroscopy_primary_tex",
                        "source_research_id": "abc123abc123",
                    },
                    {
                        "path": "analysis.md",
                        "sha256": analytic_sha,
                        "role": "abc123:physical_source_native_analysis",
                        "source_research_id": "abc123abc123",
                    },
                ]
            }
        }

        self.assertEqual(
            V5LifecycleManager._task_primary_source_sha256s(card),
            {primary_sha},
        )


if __name__ == "__main__":
    unittest.main()
