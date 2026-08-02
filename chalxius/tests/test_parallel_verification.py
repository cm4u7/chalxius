from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timezone

from mathgraph import parallel_verification as pv


NOW = datetime(2026, 8, 2, 6, 0, tzinfo=timezone.utc)


def _encodepoint(point: tuple[int, int]) -> bytes:
    x, y = point
    raw = bytearray(y.to_bytes(32, "little"))
    raw[31] |= (x & 1) << 7
    return bytes(raw)


def _key_and_signer(seed: bytes):
    digest = hashlib.sha512(seed).digest()
    scalar = int.from_bytes(
        bytes([digest[0] & 248]) + digest[1:31] + bytes([(digest[31] & 63) | 64]),
        "little",
    )
    public = _encodepoint(pv._scalarmult(pv._B, scalar))
    prefix = digest[32:]

    def sign(message: bytes) -> bytes:
        nonce = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % pv._L
        encoded_r = _encodepoint(pv._scalarmult(pv._B, nonce))
        challenge = int.from_bytes(
            hashlib.sha512(encoded_r + public + message).digest(), "little"
        ) % pv._L
        scalar_s = (nonce + challenge * scalar) % pv._L
        return encoded_r + scalar_s.to_bytes(32, "little")

    return public, sign


class ParallelVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.signers: dict[str, object] = {}
        self.trusted_keys: dict[str, dict[str, object]] = {}

        def register(
            *,
            seed_byte: int,
            key_role: str,
            principal_id: str,
            reviewer_role: str | None = None,
            host_context: str | None = None,
            trust_domain: str,
        ) -> str:
            public, signer = _key_and_signer(bytes([seed_byte]) * 32)
            record = pv.build_trusted_key_record(
                project_id="parallel-verification-fixture",
                key_role=key_role,
                public_key_hex=public.hex(),
                principal_id=principal_id,
                reviewer_role_or_null=reviewer_role,
                host_context_id_or_null=host_context,
                trust_domain_id=trust_domain,
                registered_by="operator",
            )
            self.trusted_keys[record["key_id"]] = record
            self.signers[record["key_id"]] = signer
            return record["key_id"]

        self.planner_key_id = register(
            seed_byte=90,
            key_role="planner",
            principal_id="planner-operator",
            trust_domain="operator-control",
        )
        self.host_key_ids = [
            register(
                seed_byte=index,
                key_role="host",
                principal_id=f"host-{index}",
                host_context=f"host-context-{name}",
                trust_domain=f"trust-{name}",
            )
            for index, name in ((1, "a"), (2, "b"))
        ]
        self.reviewer_key_ids = [
            register(
                seed_byte=index + 10,
                key_role="reviewer",
                principal_id=f"reviewer-{name}",
                reviewer_role="atomicity_reviewer",
                trust_domain=f"review-{name}",
            )
            for index, name in ((1, "a"), (2, "b"))
        ]
        self.subject = {
            "namespace": "failure_surface",
            "object_id": "fs-1",
            "object_semantic_sha256_or_null": "1" * 64,
            "object_file_sha256_or_null": None,
            "use_anchors": ["target-1:component-1"],
            "required_artifact_refs": ["artifact-source-1"],
            "dependency_ref_ids": ["component-1"],
            "risk_class": "high",
        }
        register = pv.derive_obligation_register([self.subject])
        self.obligation_id = register["obligations"][0]["obligation_id"]
        base = {
            "reviewer_role": "atomicity_reviewer",
            "obligation_ids": [self.obligation_id],
            "subject_ids": ["fs-1"],
            "relation_ids": [],
            "boundary_stub_ids": [],
            "context_budget": 4096,
            "closure_complete": True,
            "cutoff_profile_id": "semantic_full",
        }
        self.assignments = [
            {
                **base,
                "slot_id": "slot-primary-fs1",
                "slot_role": "primary",
                "principal_id": "reviewer-a",
                "host_context_id": "host-context-a",
                "trust_domain_id": "trust-a",
                "host_key_id": self.host_key_ids[0],
                "reviewer_key_id": self.reviewer_key_ids[0],
            },
            {
                **base,
                "slot_id": "slot-overlap-fs1",
                "slot_role": "overlap",
                "principal_id": "reviewer-b",
                "host_context_id": "host-context-b",
                "trust_domain_id": "trust-b",
                "host_key_id": self.host_key_ids[1],
                "reviewer_key_id": self.reviewer_key_ids[1],
            },
        ]
        self.plan = pv.build_work_plan(
            release_semantic_sha256="2" * 64,
            release_file_sha256="3" * 64,
            capsule_semantic_sha256="4" * 64,
            capsule_file_sha256="5" * 64,
            subjects=[self.subject],
            relations=[],
            assignments=self.assignments,
        )
        plan_body = pv.prepare_work_plan_attestation(self.plan)
        planner_key = self.trusted_keys[self.planner_key_id]
        planner_projection = {
            **plan_body,
            "key_id": self.planner_key_id,
            "scope": f"plan:{self.plan['plan_id']}",
            "key_role": planner_key["key_role"],
            "principal_id": planner_key["principal_id"],
            "trust_domain_id": planner_key["trust_domain_id"],
        }
        planner_signature = self.signers[self.planner_key_id](
            pv.jcs_bytes(planner_projection)
        )
        self.signed_plan = pv.build_signed_work_plan(
            plan=self.plan,
            planner_attestation={
                "algorithm": "Ed25519",
                "key_id": self.planner_key_id,
                "signature_hex": planner_signature.hex(),
                "scope": f"plan:{self.plan['plan_id']}",
            },
            trusted_keys=self.trusted_keys,
        )

    @staticmethod
    def _attestation(
        body: dict[str, object],
        *,
        scope: str,
        nonce: str,
        key: dict[str, object],
        signer,
    ) -> dict[str, object]:
        fields = {
            "nonce": nonce,
            "scope": scope,
            "issued_at": "2026-08-02T05:59:00Z",
            "expires_at": "2026-08-02T06:10:00Z",
            "result_visibility": "blind_to_peers",
            "key_id": key["key_id"],
        }
        projection = {
            **body,
            **fields,
            "key_role": key["key_role"],
            "principal_id": key["principal_id"],
            "reviewer_role_or_null": key["reviewer_role_or_null"],
            "host_context_id_or_null": key["host_context_id_or_null"],
            "trust_domain_id": key["trust_domain_id"],
        }
        signature = signer(pv.jcs_bytes(projection))
        return {
            "algorithm": "Ed25519",
            "key_id": fields["key_id"],
            "signature_hex": signature.hex(),
            "nonce": nonce,
            "scope": scope,
            "issued_at": fields["issued_at"],
            "expires_at": fields["expires_at"],
            "result_visibility": fields["result_visibility"],
        }

    def _packet(self, assignment: dict[str, object], index: int) -> dict[str, object]:
        prepared = pv.prepare_dispatch_packet(
            signed_plan=self.signed_plan,
            slot_id=assignment["slot_id"],
            trusted_keys=self.trusted_keys,
        )
        key = self.trusted_keys[assignment["host_key_id"]]
        attestation = self._attestation(
            prepared["attestation_body"],
            scope=f"dispatch:{self.plan['plan_id']}:{assignment['slot_id']}",
            nonce=f"dispatch-nonce-{index}",
            key=key,
            signer=self.signers[key["key_id"]],
        )
        return pv.build_dispatch_packet(
            signed_plan=self.signed_plan,
            slot_id=assignment["slot_id"],
            host_attestation=attestation,
            trusted_keys=self.trusted_keys,
            now=NOW,
        )

    def _receipt(
        self,
        packet: dict[str, object],
        assignment: dict[str, object],
        index: int,
        *,
        status: str = "supported",
    ) -> dict[str, object]:
        results = [
            {
                "obligation_id": self.obligation_id,
                "status": status,
                "finding_ids": ([f"finding-{index}"] if status == "reject" else []),
                "proof_anchor_ids": ([f"proof-{index}"] if status == "supported" else []),
                "not_applicable_witness_or_null": None,
            }
        ]
        subject_hashes = [
            {
                "object_id": "fs-1",
                "semantic_sha256_or_null": "1" * 64,
                "file_sha256_or_null": None,
            }
        ]
        prepared = pv.prepare_machine_receipt(
            signed_plan=self.signed_plan,
            packet=packet,
            obligation_results=results,
            subject_hashes=subject_hashes,
            conflicts=[],
            new_obligations=[],
            trusted_keys=self.trusted_keys,
            now=NOW,
        )
        key = self.trusted_keys[assignment["reviewer_key_id"]]
        attestation = self._attestation(
            prepared["attestation_body"],
            scope=f"result:{self.plan['plan_id']}:{assignment['slot_id']}",
            nonce=f"result-nonce-{index}",
            key=key,
            signer=self.signers[key["key_id"]],
        )
        return pv.build_machine_receipt(
            signed_plan=self.signed_plan,
            packet=packet,
            obligation_results=results,
            subject_hashes=subject_hashes,
            conflicts=[],
            new_obligations=[],
            reviewer_attestation=attestation,
            trusted_keys=self.trusted_keys,
            now=NOW,
        )

    def test_plan_before_dispatch_machine_receipts_and_mechanical_aggregate(self) -> None:
        packets = [
            self._packet(assignment, index)
            for index, assignment in enumerate(self.assignments, 1)
        ]
        receipts = [
            self._receipt(packet, assignment, index)
            for index, (packet, assignment) in enumerate(
                zip(packets, self.assignments), 1
            )
        ]
        aggregate = pv.aggregate_receipts(
            signed_plan=self.signed_plan,
            packets=packets,
            receipts=receipts,
            trusted_keys=self.trusted_keys,
            now=NOW,
        )
        self.assertTrue(aggregate["aggregate_eligible_for_decision"])
        self.assertFalse(aggregate["semantic_inference_performed"])
        self.assertNotIn("globally_admissible", aggregate)
        self.assertEqual(
            pv.validate_aggregate(
                aggregate,
                signed_plan=self.signed_plan,
                trusted_keys=self.trusted_keys,
            ),
            aggregate,
        )

    def test_one_valid_reject_is_monotone_and_blocks_aggregate(self) -> None:
        packets = [
            self._packet(assignment, index)
            for index, assignment in enumerate(self.assignments, 1)
        ]
        receipts = [
            self._receipt(packets[0], self.assignments[0], 1, status="reject"),
            self._receipt(packets[1], self.assignments[1], 2),
        ]
        aggregate = pv.aggregate_receipts(
            signed_plan=self.signed_plan,
            packets=packets,
            receipts=receipts,
            trusted_keys=self.trusted_keys,
            now=NOW,
        )
        self.assertFalse(aggregate["aggregate_eligible_for_decision"])
        self.assertEqual(len(aggregate["rejects"]), 1)

    def test_tampered_host_signature_fails_closed(self) -> None:
        packet = self._packet(self.assignments[0], 1)
        receipt = self._receipt(packet, self.assignments[0], 1)
        tampered = {
            **receipt,
            "reviewer_attestation": dict(receipt["reviewer_attestation"]),
        }
        signature = tampered["reviewer_attestation"]["signature_hex"]
        replacement = "0" if signature[-1] != "0" else "1"
        tampered["reviewer_attestation"]["signature_hex"] = (
            signature[:-1] + replacement
        )
        with self.assertRaisesRegex(ValueError, "signature"):
            pv.validate_receipt(
                tampered,
                signed_plan=self.signed_plan,
                packet=packet,
                trusted_keys=self.trusted_keys,
                now=NOW,
            )

    def test_identity_public_key_and_zero_signature_are_rejected(self) -> None:
        identity = bytes([1]) + bytes(31)
        zero_signature = identity + bytes(32)
        self.assertFalse(pv.verify_ed25519(identity, b"arbitrary", zero_signature))
        with self.assertRaisesRegex(ValueError, "identity|prime-order"):
            pv.build_trusted_key_record(
                project_id="parallel-verification-fixture",
                key_role="planner",
                public_key_hex=identity.hex(),
                principal_id="attacker",
                reviewer_role_or_null=None,
                host_context_id_or_null=None,
                trust_domain_id="attacker-domain",
                registered_by="operator",
            )

    def test_registry_rejects_one_public_key_under_multiple_identities(self) -> None:
        public, _ = _key_and_signer(bytes([77]) * 32)
        planner = pv.build_trusted_key_record(
            project_id="parallel-verification-fixture",
            key_role="planner",
            public_key_hex=public.hex(),
            principal_id="alias-planner",
            reviewer_role_or_null=None,
            host_context_id_or_null=None,
            trust_domain_id="alias-control",
            registered_by="operator",
        )
        host = pv.build_trusted_key_record(
            project_id="parallel-verification-fixture",
            key_role="host",
            public_key_hex=public.hex(),
            principal_id="alias-host",
            reviewer_role_or_null=None,
            host_context_id_or_null="alias-host-context",
            trust_domain_id="alias-host-domain",
            registered_by="operator",
        )
        with self.assertRaisesRegex(ValueError, "aliases one Ed25519 public key"):
            pv.validate_trusted_key_registry(
                {planner["key_id"]: planner, host["key_id"]: host},
                project_id="parallel-verification-fixture",
            )

    def test_attestations_cannot_supply_their_own_public_key_or_peer_visibility(self) -> None:
        planner = self.trusted_keys[self.planner_key_id]
        body = pv.prepare_work_plan_attestation(self.plan)
        projection = {
            **body,
            "key_id": self.planner_key_id,
            "scope": f"plan:{self.plan['plan_id']}",
            "key_role": planner["key_role"],
            "principal_id": planner["principal_id"],
            "trust_domain_id": planner["trust_domain_id"],
        }
        signature = self.signers[self.planner_key_id](pv.jcs_bytes(projection))
        self_supplied = {
            "algorithm": "Ed25519",
            "key_id": self.planner_key_id,
            "public_key_hex": planner["public_key_hex"],
            "signature_hex": signature.hex(),
            "scope": f"plan:{self.plan['plan_id']}",
        }
        with self.assertRaisesRegex(ValueError, "fields are not exact"):
            pv.build_signed_work_plan(
                plan=self.plan,
                planner_attestation=self_supplied,
                trusted_keys=self.trusted_keys,
            )

        prepared = pv.prepare_dispatch_packet(
            signed_plan=self.signed_plan,
            slot_id=self.assignments[0]["slot_id"],
            trusted_keys=self.trusted_keys,
        )
        key = self.trusted_keys[self.assignments[0]["host_key_id"]]
        visible_fields = {
            "nonce": "visible-result-probe",
            "scope": (
                f"dispatch:{self.plan['plan_id']}:"
                f"{self.assignments[0]['slot_id']}"
            ),
            "issued_at": "2026-08-02T05:59:00Z",
            "expires_at": "2026-08-02T06:10:00Z",
            "result_visibility": "peer_results_visible",
            "key_id": key["key_id"],
        }
        visible_projection = {
            **prepared["attestation_body"],
            **visible_fields,
            "key_role": key["key_role"],
            "principal_id": key["principal_id"],
            "reviewer_role_or_null": key["reviewer_role_or_null"],
            "host_context_id_or_null": key["host_context_id_or_null"],
            "trust_domain_id": key["trust_domain_id"],
        }
        visible = {
            "algorithm": "Ed25519",
            "key_id": key["key_id"],
            "signature_hex": self.signers[key["key_id"]](
                pv.jcs_bytes(visible_projection)
            ).hex(),
            **{
                field: visible_fields[field]
                for field in (
                    "nonce",
                    "scope",
                    "issued_at",
                    "expires_at",
                    "result_visibility",
                )
            },
        }
        with self.assertRaisesRegex(ValueError, "blind to peer results"):
            pv.build_dispatch_packet(
                signed_plan=self.signed_plan,
                slot_id=self.assignments[0]["slot_id"],
                host_attestation=visible,
                trusted_keys=self.trusted_keys,
                now=NOW,
            )

    def test_compound_role_and_missing_overlap_fail_before_dispatch(self) -> None:
        compound = [dict(item) for item in self.assignments]
        compound[0]["reviewer_role"] = "atomicity_reviewer_and_seam_reviewer"
        with self.assertRaisesRegex(ValueError, "compound"):
            pv.build_work_plan(
                release_semantic_sha256="2" * 64,
                release_file_sha256="3" * 64,
                capsule_semantic_sha256="4" * 64,
                capsule_file_sha256="5" * 64,
                subjects=[self.subject],
                relations=[],
                assignments=compound,
            )
        with self.assertRaisesRegex(ValueError, "overlap"):
            pv.build_work_plan(
                release_semantic_sha256="2" * 64,
                release_file_sha256="3" * 64,
                capsule_semantic_sha256="4" * 64,
                capsule_file_sha256="5" * 64,
                subjects=[self.subject],
                relations=[],
                assignments=self.assignments[:1],
            )

    def test_canonicalization_and_relation_direction_fail_closed(self) -> None:
        self.assertEqual(pv.jcs_bytes({"é": "é"}), pv.jcs_bytes({"e\u0301": "e\u0301"}))
        with self.assertRaisesRegex(ValueError, "safe-integer"):
            pv.jcs_bytes({"n": pv.SAFE_INTEGER + 1})
        relation = {
            "relation_id": "r1",
            "relation_kind": "supports_or_depends_on",
            "source_ref": "a",
            "target_ref": "b",
            "traversal_purpose": "implementation_choice",
            "exact_use_anchor_or_null": None,
            "relation_semantic_sha256_or_null": None,
        }
        with self.assertRaisesRegex(ValueError, "selector"):
            pv.build_work_plan(
                release_semantic_sha256="2" * 64,
                release_file_sha256="3" * 64,
                capsule_semantic_sha256="4" * 64,
                capsule_file_sha256="5" * 64,
                subjects=[self.subject],
                relations=[relation],
                assignments=self.assignments,
            )


if __name__ == "__main__":
    unittest.main()
