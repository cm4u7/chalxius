from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

from mathgraph.model import Fact
from mathgraph.contracts import sha256_json
from mathgraph.neutral_review_submission import (
    formal_return_neutral_review,
    load_formally_returned_review,
    neutral_review_handoff_status,
    preflight_neutral_review_draft,
    submit_neutral_review,
)
from mathgraph.store import MathGraphStore
from mathgraph.verifier_capsule import prepare_verifier_capsule


class NeutralReviewSubmissionTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[
        MathGraphStore,
        object,
        dict[str, object],
        dict[str, object],
        Path,
        dict[str, object],
    ]:
        store = MathGraphStore(root / "project")
        store.initialize(
            project_id="neutral-review-submission",
            title="Neutral review submission",
            workflow_evidence_version=5,
        )
        lifecycle = store.v5_lifecycle()
        research = lifecycle.add_research(
            {"kind": "proof_attempt", "claim": "The bounded claim holds."},
            actor="candidate-producer",
        )
        fact = Fact(
            problem_id=store.project_id(),
            author="candidate-producer",
            predecessors=[],
            statement="[CLAIM:ROOT] The bounded claim holds.",
            proof="A bounded direct argument proves the claim.",
        )
        release = lifecycle.candidate_release(
            {
                "schema_version": 5,
                "bundle_claim": fact.statement,
                "candidates": [fact.as_submission_dict()],
                "research_entry_ids": [research["research_id"]],
                "claim_relation": "proves",
                "artifacts": [],
                "verification_plan": {
                    "mode": "closed_capsule",
                    "authorized_artifact_roles": [],
                    "required_checks": [
                        "mathematical",
                        "typing",
                        "scope",
                        "source_and_applicability",
                        "predecessor_interfaces",
                        "computation_replay",
                        "challenge_dispositions",
                        "assurance_scope",
                    ],
                },
                "requested_assurance": {
                    "validation_subject": {
                        "kind": "theorem",
                        "subject_id": fact.fact_id,
                        "artifact_sha256": None,
                        "load_bearing_node_ids": [],
                    },
                    "validation_granularity": "monolithic_theorem",
                    "coverage": [],
                },
                "challenge_dispositions": [],
                "paper_evidence_refs": [],
                "adverse_actor_ids": [],
            },
            producer="candidate-producer",
        )
        capsule_root = root / "neutral-capsule"
        materialized = prepare_verifier_capsule(
            project_root=store.root,
            release_id=release["release_id"],
            capsule_root=capsule_root,
        )
        capsule = lifecycle.verifier_capsule(release["release_id"])
        reviewer = "fresh-neutral-verifier"
        decision = {
            "schema_version": 5,
            "release_id": release["release_id"],
            "release_sha256": release["release_sha256"],
            "capsule_sha256": capsule["capsule_sha256"],
            "verdict": "correct",
            "findings": [],
            "check_results": [
                {"check_id": check, "status": "pass", "findings": []}
                for check in capsule["required_checks"]
            ],
            "candidate_checks": [
                {"fact_id": fact_id, "verdict": "correct", "findings": []}
                for fact_id in release["fact_ids"]
            ],
            "edge_checks": [],
            "assurance_matrix": lifecycle._expected_assurance_matrix(release),
            "reviewer": reviewer,
            "host_attestation": {
                "host": "host-controlled-return-test",
                "agent_id": reviewer,
                "isolation": "fresh_context",
                "fork_turns": "none",
                "allowed_capsule_sha256": capsule["capsule_sha256"],
            },
        }
        return store, lifecycle, release, materialized, capsule_root, decision

    @staticmethod
    def _write_draft(path: Path, decision: dict[str, object]) -> bytes:
        raw = (
            json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return raw

    def test_positive_host_path_exposes_all_stages_and_formal_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            (
                store,
                lifecycle,
                release,
                materialized,
                capsule_root,
                decision,
            ) = self._fixture(Path(temporary))
            draft_path = Path(materialized["review_draft_path"])
            expected_raw = self._write_draft(draft_path, decision)
            self.assertEqual(
                neutral_review_handoff_status(capsule_root)["status"],
                "draft_written",
            )

            preflight = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(materialized["review_submission_path"]),
                    "--capsule-root",
                    str(capsule_root),
                    "--preflight-only",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stdout)
            self.assertEqual(json.loads(preflight.stdout)["status"], "preflight_passed")
            self.assertEqual(
                neutral_review_handoff_status(capsule_root)["status"],
                "preflight_passed",
            )
            self.assertEqual(lifecycle.decisions(), [])
            self.assertEqual(store.fact_ids(), [])

            # Model a host interruption after complete canonical bytes became
            # visible but before the formal-return receipt was published.  The
            # receipt remains the visibility switch and a retry finishes the
            # same immutable handoff.
            formal_path = Path(materialized["review_return_path"])
            formal_path.write_bytes(expected_raw)
            os.chmod(formal_path, 0o400)
            self.assertEqual(
                neutral_review_handoff_status(capsule_root)["status"],
                "preflight_passed",
            )

            returned = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(materialized["review_submission_path"]),
                    "--capsule-root",
                    str(capsule_root),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(returned.returncode, 0, returned.stdout)
            success = json.loads(returned.stdout)
            self.assertEqual(success["status"], "formally_returned")
            self.assertEqual(formal_path.read_bytes(), expected_raw)
            self.assertEqual(stat.S_IMODE(formal_path.stat().st_mode), 0o400)
            loaded = load_formally_returned_review(capsule_root)
            self.assertEqual(loaded["review"], decision)
            self.assertEqual(loaded["receipt"]["receipt_id"], success["receipt_id"])
            self.assertEqual(
                submit_neutral_review(capsule_root)["receipt_id"],
                success["receipt_id"],
            )
            self.assertEqual(lifecycle.decisions(), [])

            recorded = lifecycle.certification_record(loaded["review"])
            admitted = lifecycle.fact_admit(
                release_id=release["release_id"],
                decision_id=recorded["decision_id"],
                gateway="independent-gateway",
            )
            self.assertEqual(admitted["fact_ids"], release["fact_ids"])
            audit = store.audit()
            self.assertTrue(audit.current_ok, audit.errors)

    def test_predicate_false_missing_draft_has_no_authority_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store, lifecycle, _, _, capsule_root, _ = self._fixture(Path(temporary))
            before = {
                "decisions": lifecycle.decisions(),
                "facts": store.fact_ids(),
                "admissions": sorted(lifecycle.admissions_dir.rglob("*")),
            }
            status = neutral_review_handoff_status(capsule_root)
            self.assertEqual(status["status"], "draft_written")
            self.assertFalse(status["draft_present"])
            self.assertEqual(status["activation"], "predicate_false")
            result = submit_neutral_review(capsule_root, preflight_only=True)
            self.assertFalse(result["draft_present"])
            self.assertEqual(result["authority_effects"], {
                "candidate": 0,
                "certification": 0,
                "gateway": 0,
                "fact": 0,
            })
            self.assertFalse((capsule_root / "output" / "handoff").exists())
            self.assertEqual(lifecycle.decisions(), before["decisions"])
            self.assertEqual(store.fact_ids(), before["facts"])
            self.assertEqual(
                sorted(lifecycle.admissions_dir.rglob("*")),
                before["admissions"],
            )

    def test_historical_v5_release_keeps_legacy_direct_return_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, lifecycle, release, _, _, _ = self._fixture(Path(temporary))
            current = lifecycle.store._read_json(
                lifecycle._release_path(release["release_id"])
            )
            semantic = {
                key: value
                for key, value in current.items()
                if key
                not in {
                    "release_id",
                    "release_sha256",
                    "created_at",
                    "record_sha256",
                    "neutral_review_submission_revision",
                }
            }
            legacy_sha = sha256_json(semantic)
            legacy_id = "release-" + legacy_sha
            without_hash = {
                **semantic,
                "release_id": legacy_id,
                "release_sha256": legacy_sha,
                "created_at": current["created_at"],
            }
            legacy = {
                **without_hash,
                "record_sha256": sha256_json(without_hash),
            }
            lifecycle.store._write_json_once(
                lifecycle._release_path(legacy_id),
                legacy,
            )
            capsule = lifecycle.verifier_capsule(legacy_id)
            self.assertNotIn("neutral_review_submission_revision", capsule)
            self.assertNotIn(
                "host_submission_program",
                capsule.get("decision_return", {}),
            )
            legacy_root = Path(temporary) / "legacy-v5-neutral-capsule"
            materialized = prepare_verifier_capsule(
                project_root=lifecycle.store.root,
                release_id=legacy_id,
                capsule_root=legacy_root,
            )
            self.assertEqual(materialized["schema_version"], 2)
            self.assertEqual(
                materialized["allowed_write_relpaths"],
                ["output/review.json"],
            )
            self.assertNotIn("review_draft_path", materialized)
            self.assertNotIn("review_submission_path", materialized)
            self.assertFalse((legacy_root / "host" / "submit_review.py").exists())

    def test_invalid_enum_is_quarantined_and_tamper_retry_fails_closed_then_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            (
                store,
                lifecycle,
                _,
                materialized,
                capsule_root,
                decision,
            ) = self._fixture(Path(temporary))
            draft_path = Path(materialized["review_draft_path"])
            invalid = copy.deepcopy(decision)
            invalid["verdict"] = "approved"
            invalid_raw = self._write_draft(draft_path, invalid)
            failed = submit_neutral_review(capsule_root)
            self.assertEqual(failed["status"], "preflight_failed")
            diagnostic = failed["diagnostics"][0]
            self.assertEqual(diagnostic["json_pointer"], "/verdict")
            self.assertEqual(diagnostic["allowed_values"], ["correct", "reject"])
            quarantine = capsule_root / failed["quarantine_draft_relpath"]
            self.assertEqual(quarantine.read_bytes(), invalid_raw)
            self.assertFalse(draft_path.exists())
            self.assertFalse(Path(materialized["review_return_path"]).exists())
            self.assertEqual(lifecycle.decisions(), [])
            self.assertEqual(store.fact_ids(), [])

            self._write_draft(draft_path, decision)
            passed = preflight_neutral_review_draft(capsule_root)
            self.assertEqual(passed["status"], "preflight_passed")
            receipt_path = (
                capsule_root
                / "output"
                / "handoff"
                / f"{passed['receipt_id']}.json"
            )
            original_receipt = receipt_path.read_bytes()
            tampered = json.loads(original_receipt)
            tampered["validation"]["verdict"] = "reject"
            os.chmod(receipt_path, 0o600)
            receipt_path.write_text(
                json.dumps(tampered, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            os.chmod(receipt_path, 0o400)
            with self.assertRaisesRegex(ValueError, "receipt identity"):
                formal_return_neutral_review(capsule_root)
            self.assertFalse(Path(materialized["review_return_path"]).exists())
            self.assertEqual(lifecycle.decisions(), [])
            self.assertEqual(store.fact_ids(), [])

            os.chmod(receipt_path, 0o600)
            receipt_path.write_bytes(original_receipt)
            os.chmod(receipt_path, 0o400)
            recovered = submit_neutral_review(capsule_root)
            self.assertEqual(recovered["status"], "formally_returned")
            self.assertEqual(
                load_formally_returned_review(capsule_root)["receipt"]["receipt_id"],
                recovered["receipt_id"],
            )


if __name__ == "__main__":
    unittest.main()
