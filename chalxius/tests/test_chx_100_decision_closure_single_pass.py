"""CHX-100 red light for duplicated historical closure validation.

``V5LifecycleManager.release`` is the sealed Candidate Release validator: for
the relevant release families it reconstructs the historical Release, Paper,
and Fact closure.  One read-only ``decision(..., validate_bindings=True)``
currently calls it directly and then calls ``verifier_capsule``, which calls
the same release validator again.  The desired administrative contract is one
historical closure pass per decision verification.

This test intentionally fails on Chalxius 0.6.5.  It grants no truth,
Certification, Gateway, admission, or project-state authority.
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.v5_lifecycle import V5LifecycleManager, V5_POLICY_REVISION


class _ReadOnlyStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.fact_graph_dir = root / "fact_graph"

    def project_id(self) -> str:
        return "chx-100-single-pass"

    @staticmethod
    def _read_json(path: Path) -> dict[str, object]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("fixture JSON must contain one object")
        return payload


class CHX100DecisionClosureSinglePassTests(unittest.TestCase):
    @staticmethod
    def _tree_snapshot(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes())
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def test_one_decision_verification_reuses_one_historical_closure_result(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            store = _ReadOnlyStore(root)
            lifecycle = V5LifecycleManager(store)
            lifecycle.certification_decisions_dir.mkdir(parents=True)

            release_id = "release-" + "1" * 64
            release = {
                "release_id": release_id,
                "release_sha256": "2" * 64,
                "external_predecessors": [],
                "verification_plan": {
                    "authorized_artifact_roles": [],
                    "required_checks": [],
                },
                "artifacts": [],
                "candidates": [],
                "fact_ids": [],
                "root_fact_ids": [],
                "intermediate_fact_ids": [],
                "internal_edges": [],
                "requested_assurance": {
                    "contract_revision": "historical-fixture",
                },
                "paper_evidence_refs": [],
                "challenge_dispositions": [],
                "excluded_verifier_ids": [],
            }
            closure_output = {
                "release_sha256": release["release_sha256"],
                "paper_closure_sha256": "3" * 64,
                "fact_closure_sha256": "4" * 64,
                "project_effect": "none",
                "truth_effect": "none",
            }
            historical_closure_validator = Mock(return_value=closure_output)
            validation_outputs: list[dict[str, object]] = []

            def validated_release(requested_release_id: str) -> dict[str, object]:
                self.assertEqual(requested_release_id, release_id)
                validated = historical_closure_validator()
                validation_outputs.append(copy.deepcopy(validated))
                return copy.deepcopy(release)

            lifecycle.release = Mock(side_effect=validated_release)  # type: ignore[method-assign]
            lifecycle._require_current_paper_continuation_release = Mock(  # type: ignore[method-assign]
                return_value=None
            )

            # Construct the exact expected binding once, outside the measured
            # decision-verification operation, then reset every call counter.
            expected_capsule = lifecycle.verifier_capsule(release_id)
            lifecycle.release.reset_mock()
            lifecycle._require_current_paper_continuation_release.reset_mock()
            historical_closure_validator.reset_mock()
            validation_outputs.clear()

            semantic = {
                "schema_version": 5,
                "policy_revision": V5_POLICY_REVISION,
                "project_id": store.project_id(),
                "release_id": release_id,
                "release_sha256": release["release_sha256"],
                "capsule_sha256": expected_capsule["capsule_sha256"],
                "truth_effect": "none",
            }
            decision_sha256 = sha256_json(semantic)
            without_record_hash = {
                **semantic,
                "decision_id": "decision-" + decision_sha256,
                "decision_sha256": decision_sha256,
                "reviewed_at": "2026-08-04T00:00:00Z",
            }
            record = {
                **without_record_hash,
                "record_sha256": sha256_json(without_record_hash),
            }
            decision_path = lifecycle._decision_path(record["decision_id"])
            decision_path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            before = self._tree_snapshot(root)
            verified = lifecycle.decision(record["decision_id"], validate_bindings=True)
            after = self._tree_snapshot(root)

            # Both current passes produce the same nontruth validation result
            # and decision verification itself is state-neutral.
            self.assertEqual(verified, record)
            self.assertEqual(verified["truth_effect"], "none")
            self.assertEqual(before, after)
            self.assertTrue(validation_outputs)
            self.assertEqual(
                validation_outputs,
                [closure_output] * len(validation_outputs),
            )

            # RED on 0.6.5: decision() validates release once, then the real
            # verifier_capsule() validates that identical release a second time.
            self.assertEqual(
                historical_closure_validator.call_count,
                1,
                "one decision verification repeated the historical "
                "Release/Paper/Fact closure validation",
            )


if __name__ == "__main__":
    unittest.main()
