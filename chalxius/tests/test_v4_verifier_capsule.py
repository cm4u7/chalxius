from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mathgraph.contracts import sha256_bytes, sha256_json
from mathgraph.verifier_capsule import prepare_verifier_capsule


class VerifierCapsuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        packet = b"# Frozen packet\n\nCheck the toy statement.\n"
        body = {
            "schema_version": 4,
            "policy_revision": "mathgraph-0.3.0",
            "fact_id": "0123456789abcdef",
            "submission_sha256": "1" * 64,
            "packet_sha256": sha256_bytes(packet),
            "verification_mode": "closed_packet",
            "supersedes_bundle_id": None,
            "bundle_reason": "initial",
            "interfaces": [],
            "artifacts": [],
            "verification_plan": {
                "mode": "closed_packet",
                "authorized_artifact_roles": [],
                "required_checks": ["mathematical"],
            },
        }
        self.bundle_sha = sha256_json(body)
        self.bundle = (
            self.project
            / "verification_queue"
            / "bundles"
            / "by-hash"
            / self.bundle_sha
        )
        self.bundle.mkdir(parents=True)
        (self.bundle / "packet.md").write_bytes(packet)
        manifest = {
            **body,
            "bundle_id": "bundle-" + self.bundle_sha,
            "bundle_sha256": self.bundle_sha,
        }
        (self.bundle / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_capsule_contains_only_verified_input_and_separate_host_receipt(
        self,
    ) -> None:
        capsule = (self.base / "neutral" / "review-1").resolve()
        result = prepare_verifier_capsule(
            project_root=self.project,
            bundle_sha256=self.bundle_sha,
            capsule_root=capsule,
        )
        self.assertEqual(
            {
                path.relative_to(capsule).as_posix()
                for path in capsule.rglob("*")
                if path.is_file()
            },
            {
                "host/capability.json",
                "input/manifest.json",
                "input/packet.md",
            },
        )
        self.assertEqual(
            result["allowed_read_paths"],
            [
                str(capsule / "input" / "manifest.json"),
                str(capsule / "input" / "packet.md"),
            ],
        )
        self.assertEqual(
            result["review_return_path"],
            str(capsule / "output" / "review.json"),
        )
        self.assertIn(
            "not an OS filesystem sandbox",
            result["enforcement_boundary"],
        )

    def test_capsule_rejects_project_local_or_existing_destination(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the project"):
            prepare_verifier_capsule(
                project_root=self.project,
                bundle_sha256=self.bundle_sha,
                capsule_root=self.project / "capsule",
            )
        existing = self.base / "existing"
        existing.mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            prepare_verifier_capsule(
                project_root=self.project,
                bundle_sha256=self.bundle_sha,
                capsule_root=existing,
            )

    def test_capsule_rejects_unauthorized_bundle_bytes(self) -> None:
        (self.bundle / "extra.txt").write_text("not authorized\n")
        with self.assertRaisesRegex(ValueError, "unauthorized bytes"):
            prepare_verifier_capsule(
                project_root=self.project,
                bundle_sha256=self.bundle_sha,
                capsule_root=self.base / "neutral-extra",
            )


if __name__ == "__main__":
    unittest.main()
