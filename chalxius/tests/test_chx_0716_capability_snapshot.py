"""CHX-038: bound schema-v2 Repair bytes without capping ordinary evidence."""

from __future__ import annotations

import hashlib
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mathgraph.v5_lifecycle as v5_lifecycle_module
from mathgraph.contracts import sha256_json
from mathgraph.store import MathGraphStore
from mathgraph.v5_lifecycle import (
    RoundInspectionContext,
    V5_MAX_REPAIR_INPUT_CAPABILITIES,
    V5_MAX_REPAIR_INPUT_CAPABILITY_BYTES,
    V5_REPAIR_INPUT_CAPABILITY_REVISION,
    V5_ASSURANCE_CONTRACT_REVISION,
)
from mathgraph.v5_assurance import V5_LEGACY_ASSURANCE_CONTRACT_REVISION


class CHX0716CapabilitySnapshotTests(unittest.TestCase):
    def _store(self, root: Path) -> MathGraphStore:
        store = MathGraphStore(root / "project")
        store.initialize(
            project_id="chx-0716-capability-snapshot",
            title="CHX-016 capability snapshot",
            workflow_evidence_version=5,
        )
        return store

    def test_one_command_snapshot_reads_identical_capability_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            path = store.root / "input.bin"
            raw = b"immutable capability bytes\n"
            path.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            lifecycle = store.v5_lifecycle()
            context = RoundInspectionContext()
            original = lifecycle._read_regular_bytes_once
            with patch.object(
                lifecycle,
                "_read_regular_bytes_once",
                wraps=original,
            ) as read_once:
                first = lifecycle._repair_capability_bytes(
                    path,
                    digest,
                    label="test capability",
                    _inspection_context=context,
                )
                second = lifecycle._repair_capability_bytes(
                    path,
                    digest,
                    label="test capability",
                    _inspection_context=context,
                )
            self.assertEqual(first, raw)
            self.assertIs(second, first)
            self.assertEqual(read_once.call_count, 1)
            self.assertEqual(context.repair_capability_total_bytes, len(raw))

    def test_fresh_boundary_rechecks_bytes_without_the_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            path = store.root / "input.bin"
            first = b"first capability bytes\n"
            second = b"second capability bytes\n"
            path.write_bytes(first)
            first_digest = hashlib.sha256(first).hexdigest()
            lifecycle = store.v5_lifecycle()
            context = RoundInspectionContext()
            lifecycle._repair_capability_bytes(
                path,
                first_digest,
                label="test capability",
                _inspection_context=context,
            )
            path.write_bytes(second)
            with self.assertRaisesRegex(ValueError, "bytes/hash mismatch"):
                lifecycle._repair_capability_bytes(
                    path,
                    first_digest,
                    label="test capability",
                )

    def test_aggregate_cap_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            path = store.root / "input.bin"
            raw = b"x" * (V5_MAX_REPAIR_INPUT_CAPABILITY_BYTES + 1)
            path.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            with self.assertRaisesRegex(ValueError, "64 MiB aggregate cap"):
                store.v5_lifecycle()._repair_capability_bytes(
                    path,
                    digest,
                    label="oversized capability",
                    _inspection_context=RoundInspectionContext(),
                )

    def test_project_wide_ordinary_artifacts_do_not_consume_repair_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            first_path = store.root / "ordinary-a.txt"
            second_path = store.root / "ordinary-b.txt"
            first = b"abcdef"
            second = b"ghijkl"
            first_path.write_bytes(first)
            second_path.write_bytes(second)
            ordinary = {
                "research_id": "ordinary",
                "metadata": {
                    "assurance_contract_revision": V5_ASSURANCE_CONTRACT_REVISION,
                    "artifacts": [
                        {
                            "path": first_path.relative_to(store.root).as_posix(),
                            "sha256": hashlib.sha256(first).hexdigest(),
                            "role": "first",
                        },
                        {
                            "path": second_path.relative_to(store.root).as_posix(),
                            "sha256": hashlib.sha256(second).hexdigest(),
                            "role": "second",
                        },
                    ],
                },
            }
            with patch.object(
                v5_lifecycle_module,
                "V5_MAX_REPAIR_INPUT_CAPABILITY_BYTES",
                10,
            ):
                context = RoundInspectionContext()
                typed = store.v5_lifecycle()._typed_research_artifacts(
                    ordinary,
                    _inspection_context=context,
                )
            self.assertEqual(len(typed), 2)
            self.assertEqual(context.repair_capability_total_bytes, 0)

    def test_exact_legacy_artifacts_are_capabilities_by_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            path = store.root / "legacy-source.pdf"
            raw = b"frozen legacy source bytes\n"
            path.write_bytes(raw)
            research = store.v5_lifecycle().add_research(
                {
                    "kind": "literature",
                    "claim": "Read one exact historical source capability.",
                    "artifacts": [
                        {
                            "path": path.relative_to(store.root).as_posix(),
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "role": "primary_source",
                        }
                    ],
                    "source_dependent": True,
                },
                actor="main",
                assurance_contract_revision=(
                    V5_LEGACY_ASSURANCE_CONTRACT_REVISION
                ),
            )

            planned = store.v5_lifecycle().create_production_round(
                workers=1,
                mode="literature",
                research_ids=[research["research_id"]],
                host_task_scope_id="legacy-exact-capability-host",
            )
            card = Path(planned["assignments"][0]["task_card_path"])
            related = json.loads(card.read_text(encoding="utf-8"))[
                "mathematical_state"
            ]["related_artifacts"]
            self.assertEqual(
                [item["path"] for item in related],
                ["legacy-source.pdf"],
            )

    def test_ordinary_artifacts_remain_fail_closed_for_hash_and_symlink_drift(
        self,
    ) -> None:
        for mutation in ("hash", "symlink"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                store = self._store(Path(temporary))
                path = store.root / "ordinary.txt"
                raw = b"trusted ordinary bytes\n"
                path.write_bytes(raw)
                ordinary = {
                    "research_id": "ordinary",
                    "metadata": {
                        "assurance_contract_revision": (
                            V5_ASSURANCE_CONTRACT_REVISION
                        ),
                        "artifacts": [
                            {
                                "path": path.relative_to(store.root).as_posix(),
                                "sha256": hashlib.sha256(raw).hexdigest(),
                                "role": "source",
                            }
                        ],
                    },
                }
                if mutation == "hash":
                    path.write_bytes(b"drifted ordinary bytes\n")
                else:
                    target = store.root / "ordinary-target.txt"
                    target.write_bytes(raw)
                    path.unlink()
                    path.symlink_to(target.name)
                with self.assertRaisesRegex(
                    ValueError, "Research capability artifact drifted"
                ):
                    store.v5_lifecycle()._typed_research_artifacts(
                        ordinary,
                        _inspection_context=RoundInspectionContext(),
                    )

    def test_ordinary_artifact_accepts_metadata_only_localization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            path = store.root / "ordinary-localized.txt"
            raw = b"content-addressed ordinary bytes\n"
            path.write_bytes(raw)
            ordinary = {
                "research_id": "ordinary-localized",
                "metadata": {
                    "assurance_contract_revision": V5_ASSURANCE_CONTRACT_REVISION,
                    "artifacts": [
                        {
                            "path": path.relative_to(store.root).as_posix(),
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "role": "source",
                        }
                    ],
                },
            }
            original_read = v5_lifecycle_module.os.read
            localized = False

            def localizing_read(descriptor: int, size: int) -> bytes:
                nonlocal localized
                chunk = original_read(descriptor, size)
                if chunk and not localized:
                    localized = True
                    metadata = path.stat()
                    os.utime(
                        path,
                        ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 1_000_000),
                    )
                return chunk

            with patch.object(
                v5_lifecycle_module.os,
                "read",
                side_effect=localizing_read,
            ):
                typed = store.v5_lifecycle()._typed_research_artifacts(
                    ordinary,
                    _inspection_context=RoundInspectionContext(),
                )
            self.assertTrue(localized)
            self.assertEqual(typed[0]["sha256"], hashlib.sha256(raw).hexdigest())

    def test_independent_repair_budgets_share_one_command_read_snapshot(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            first_path = store.root / "first-repair-input.bin"
            second_path = store.root / "second-repair-input.bin"
            first_raw = b"abcdef"
            second_raw = b"ghijkl"
            first_path.write_bytes(first_raw)
            second_path.write_bytes(second_raw)
            symlink_path = store.root / "linked-repair-input.bin"
            symlink_path.symlink_to(first_path.name)
            first_capability = {
                "path": first_path.relative_to(store.root).as_posix(),
                "sha256": hashlib.sha256(first_raw).hexdigest(),
                "role": "first",
            }
            second_capability = {
                "path": second_path.relative_to(store.root).as_posix(),
                "sha256": hashlib.sha256(second_raw).hexdigest(),
                "role": "second",
            }

            def repair_record(
                research_id: str,
                capabilities: list[dict[str, str]],
            ) -> dict[str, object]:
                manifest_semantic = {
                    "revision": V5_REPAIR_INPUT_CAPABILITY_REVISION,
                    "source_research_id": research_id,
                    "trigger_research_id": None,
                    "input_capabilities": copy.deepcopy(capabilities),
                    "selection_policy": (
                        "direct_research_plus_one_verified_assignment_or_source_receipt_hop"
                    ),
                    "max_capabilities": V5_MAX_REPAIR_INPUT_CAPABILITIES,
                    "truth_effect": "none",
                }
                manifest = {
                    **manifest_semantic,
                    "manifest_sha256": sha256_json(manifest_semantic),
                }
                return {
                    "research_id": research_id,
                    "kind": "repair",
                    "relation": "repairs",
                    "metadata": {
                        "assurance_contract_revision": (
                            V5_ASSURANCE_CONTRACT_REVISION
                        ),
                        "repair_input_capability_manifest": manifest,
                        "repair_spec": {
                            "schema_version": 2,
                            "input_capabilities": copy.deepcopy(capabilities),
                        },
                        "source_dependent": True,
                        "artifacts": copy.deepcopy(capabilities),
                    },
                }

            first = repair_record("a" * 12, [first_capability])
            repeated = repair_record("b" * 12, [first_capability])
            second = repair_record("c" * 12, [second_capability])
            combined = repair_record(
                "d" * 12,
                [first_capability, second_capability],
            )
            conflicting = repair_record(
                "e" * 12,
                [
                    {
                        **first_capability,
                        "sha256": hashlib.sha256(b"other bytes").hexdigest(),
                    }
                ],
            )
            symlinked = repair_record(
                "f" * 12,
                [
                    {
                        **first_capability,
                        "path": symlink_path.relative_to(store.root).as_posix(),
                    }
                ],
            )
            lifecycle = store.v5_lifecycle()
            shared_command_context = RoundInspectionContext()
            with patch.object(
                v5_lifecycle_module,
                "V5_MAX_REPAIR_INPUT_CAPABILITY_BYTES",
                10,
            ), patch.object(
                lifecycle,
                "_read_regular_bytes_once",
                wraps=lifecycle._read_regular_bytes_once,
            ) as read_once:
                self.assertEqual(
                    len(
                        lifecycle._typed_research_artifacts(
                            first,
                            _inspection_context=shared_command_context,
                        )
                    ),
                    1,
                )
                self.assertEqual(
                    len(
                        lifecycle._typed_research_artifacts(
                            repeated,
                            _inspection_context=shared_command_context,
                        )
                    ),
                    1,
                )
                self.assertEqual(
                    len(
                        lifecycle._typed_research_artifacts(
                            second,
                            _inspection_context=shared_command_context,
                        )
                    ),
                    1,
                )
                self.assertEqual(
                    shared_command_context.repair_capability_total_bytes,
                    0,
                )
                self.assertEqual(read_once.call_count, 2)
                with self.assertRaisesRegex(
                    ValueError,
                    "Research capability artifact drifted",
                ):
                    lifecycle._typed_research_artifacts(
                        combined,
                        _inspection_context=shared_command_context,
                    )
                self.assertEqual(read_once.call_count, 2)
                with self.assertRaisesRegex(
                    ValueError,
                    "Research capability artifact drifted",
                ):
                    lifecycle._typed_research_artifacts(
                        conflicting,
                        _inspection_context=shared_command_context,
                    )
                self.assertEqual(read_once.call_count, 2)

                second_path.write_bytes(b"tamper")
                with self.assertRaisesRegex(
                    ValueError,
                    "Research capability artifact drifted",
                ):
                    lifecycle._typed_research_artifacts(
                        second,
                        _inspection_context=RoundInspectionContext(),
                    )
                with self.assertRaisesRegex(
                    ValueError,
                    "Research capability artifact drifted",
                ):
                    lifecycle._typed_research_artifacts(
                        symlinked,
                        _inspection_context=RoundInspectionContext(),
                    )

    def test_repair_artifacts_still_consume_the_bounded_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            path = store.root / "repair-input.bin"
            raw = b"01234567890"
            path.write_bytes(raw)
            capability = {
                "path": path.relative_to(store.root).as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "role": "repair-input",
            }
            manifest_semantic = {
                "revision": V5_REPAIR_INPUT_CAPABILITY_REVISION,
                "source_research_id": "a" * 12,
                "trigger_research_id": None,
                "input_capabilities": [copy.deepcopy(capability)],
                "selection_policy": (
                    "direct_research_plus_one_verified_assignment_or_source_receipt_hop"
                ),
                "max_capabilities": V5_MAX_REPAIR_INPUT_CAPABILITIES,
                "truth_effect": "none",
            }
            manifest = {
                **manifest_semantic,
                "manifest_sha256": sha256_json(manifest_semantic),
            }
            repair = {
                "research_id": "repair",
                "kind": "repair",
                "relation": "repairs",
                "metadata": {
                    "assurance_contract_revision": V5_ASSURANCE_CONTRACT_REVISION,
                    "repair_input_capability_manifest": manifest,
                    "repair_spec": {
                        "schema_version": 2,
                        "input_capabilities": [copy.deepcopy(capability)],
                    },
                    "source_dependent": True,
                    "artifacts": [copy.deepcopy(capability)],
                },
            }
            with patch.object(
                v5_lifecycle_module,
                "V5_MAX_REPAIR_INPUT_CAPABILITY_BYTES",
                10,
            ):
                with self.assertRaisesRegex(
                    ValueError, "Research capability artifact drifted"
                ):
                    store.v5_lifecycle()._typed_research_artifacts(
                        repair,
                        _inspection_context=RoundInspectionContext(),
                    )

    def test_schema_v1_repair_manifest_does_not_consume_schema_v2_budget(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store(Path(temporary))
            path = store.root / "legacy-repair-input.bin"
            raw = b"01234567890"
            path.write_bytes(raw)
            capability = {
                "path": path.relative_to(store.root).as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "role": "legacy-repair-input",
            }
            manifest_semantic = {
                "revision": V5_REPAIR_INPUT_CAPABILITY_REVISION,
                "source_research_id": "a" * 12,
                "trigger_research_id": None,
                "input_capabilities": [copy.deepcopy(capability)],
                "selection_policy": (
                    "direct_research_plus_one_verified_assignment_or_source_receipt_hop"
                ),
                "max_capabilities": V5_MAX_REPAIR_INPUT_CAPABILITIES,
                "truth_effect": "none",
            }
            manifest = {
                **manifest_semantic,
                "manifest_sha256": sha256_json(manifest_semantic),
            }
            repair = {
                "research_id": "legacy-repair",
                "kind": "repair",
                "relation": "repairs",
                "metadata": {
                    "assurance_contract_revision": V5_ASSURANCE_CONTRACT_REVISION,
                    "repair_input_capability_manifest": manifest,
                    "repair_spec": {"schema_version": 1},
                    "source_dependent": True,
                    "artifacts": [copy.deepcopy(capability)],
                },
            }
            context = RoundInspectionContext()
            with patch.object(
                v5_lifecycle_module,
                "V5_MAX_REPAIR_INPUT_CAPABILITY_BYTES",
                10,
            ):
                typed = store.v5_lifecycle()._typed_research_artifacts(
                    repair,
                    _inspection_context=context,
                )
            self.assertEqual(len(typed), 1)
            self.assertEqual(context.repair_capability_total_bytes, 0)


if __name__ == "__main__":
    unittest.main()
