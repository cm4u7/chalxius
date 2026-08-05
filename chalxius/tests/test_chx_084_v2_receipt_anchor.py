"""Red-contract tests for CHX-084 receipt-as-anchor reuse.

Expected production API::

    mathgraph.runtime_cutover.validate_or_reuse_project_validation_anchor(
        anchor_path,
        expected_anchor_sha256,
        *,
        runtime_root,
        project_roots,
        archive_root,
        prior_runtime_binding,
        deep_audit_required,
        deep_project_validator,
    ) -> {"projects": ..., "runtime_bindings": ..., "validation_mode": ...}

The approved v2 anchor is one
``chalxius-cutover-project-validation-receipt-2`` object.  Its minimum reuse
surface is the exact project state, canonical terminal round map, validating
runtime identity, ``truth_effect=none``, ``project_effect=validation_only``,
and ``premise_eligible=false``.  Non-impacting reuse is local and structural:
it must launch no candidate subprocess.  Legacy anchors are accepted only
when the caller explicitly requires one deep audit.

These tests are intentionally red until that production API and v2 schema
exist.  They do not grant truth, evidence, Certification, Gateway, or Fact
authority to a cutover receipt.
"""

from __future__ import annotations

import copy
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from mathgraph import runtime_cutover
from mathgraph.contracts import sha256_bytes
from mathgraph.runtime_archive import runtime_binding_from_root


EXPECTED_API = "validate_or_reuse_project_validation_anchor"
V2_RECEIPT_REVISION = "chalxius-cutover-project-validation-receipt-2"


class CHX084V2ReceiptAnchorTests(unittest.TestCase):
    ROUND_IDS = (
        "round-20260101T000000Z-00000001",
        "round-20260101T000001Z-00000002",
    )

    def _api(self):
        api = getattr(runtime_cutover, EXPECTED_API, None)
        self.assertTrue(
            callable(api),
            f"expected production API mathgraph.runtime_cutover.{EXPECTED_API}",
        )
        return api

    @classmethod
    def _project(cls, base: Path) -> Path:
        project = base / "protected-project"
        for round_id in cls.ROUND_IDS:
            (project / "rounds" / round_id).mkdir(parents=True)
        return project.resolve()

    @classmethod
    def _terminal_states(cls) -> dict[str, str]:
        return {
            cls.ROUND_IDS[0]: "completed",
            cls.ROUND_IDS[1]: "aborted",
        }

    @staticmethod
    def _write_anchor(path: Path, payload: dict[str, object]) -> str:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return sha256_bytes(path.read_bytes())

    @staticmethod
    def _prior_runtime_binding(base: Path) -> dict[str, object]:
        runtime = base / "installed-runtime"
        runtime.mkdir()
        version = runtime / "VERSION"
        payload = runtime / "payload.txt"
        manifest = runtime / "MANIFEST.sha256"
        version.write_text("0.6.4\n", encoding="utf-8")
        payload.write_text("prior\n", encoding="utf-8")
        manifest.write_text(
            f"{sha256_bytes(version.read_bytes())}  VERSION\n"
            f"{sha256_bytes(payload.read_bytes())}  payload.txt\n",
            encoding="utf-8",
        )
        return runtime_binding_from_root(
            runtime,
            archive_root=base / "runtime-archive",
        )

    @classmethod
    def _legacy_anchor(
        cls,
        project: Path,
        prior_runtime_binding: dict[str, object],
    ) -> dict[str, object]:
        return {
            "captured_at": "2026-08-04T00:00:00Z",
            "installed_runtime_identity": prior_runtime_binding[
                "runtime_identity_sha256"
            ],
            "cutover": {
                "preflight_audit_current_ok": True,
                "postflight_audit_current_ok": True,
                "protected_project": str(project),
                "project_effect": "validation_only",
                "truth_effect": "none",
            },
        }

    @classmethod
    def _v2_anchor(
        cls,
        project: Path,
        prior_runtime_binding: dict[str, object],
    ) -> dict[str, object]:
        return {
            "schema_version": 1,
            "contract_revision": V2_RECEIPT_REVISION,
            "request_path": str(project.parent / "prior-request.json"),
            "request_sha256": "1" * 64,
            "candidate_root": str(project.parent / "prior-runtime"),
            "installed_root": str(project.parent / "prior-installed"),
            "archive_root": str(project.parent / "runtime-archive"),
            "candidate_manifest_sha256": prior_runtime_binding[
                "manifest_file_sha256"
            ],
            "candidate_runtime_identity": "a" * 64,
            "candidate_runtime_content_sha256": prior_runtime_binding[
                "runtime_content_sha256"
            ],
            "prior_runtime_identity": "4" * 64,
            "changed_runtime_paths": [],
            "deep_audit_required": True,
            "change_classification_rationale": "Exact prior deep-audit fixture.",
            "prior_audit_anchor": {
                "path": str(project.parent / "legacy-audit.json"),
                "sha256": "5" * 64,
                "captured_at": "2026-08-04T00:00:00Z",
                "anchor_kind": "legacy_current_ok_report",
                "contract_revision": "legacy_current_ok_report",
            },
            "release_validation_evidence": [
                {
                    "path": str(project.parent / "prior-release-matrix.json"),
                    "sha256": "6" * 64,
                }
            ],
            "projects": [
                {
                    "project_root": str(project),
                    "project_state": runtime_cutover._project_state_snapshot(project),
                    "round_states": cls._terminal_states(),
                    "audit_evidence_mode": "single_prevalidated_deep_audit",
                    "audit_current_ok": True,
                }
            ],
            "runtime_bindings": [],
            "anchor_contract_revision": "chalxius-prior-project-audit-anchor-2",
            "validation_mode": "single_deep_audit",
            "candidate_subprocess_count": 1,
            "project_effect": "validation_only",
            "truth_effect": "none",
            "premise_eligible": False,
        }

    @classmethod
    def _v2_reuse_anchor(
        cls,
        project: Path,
        prior_runtime_binding: dict[str, object],
        *,
        predecessor_path: Path,
        predecessor_sha256: str,
    ) -> dict[str, object]:
        receipt = copy.deepcopy(cls._v2_anchor(project, prior_runtime_binding))
        receipt["deep_audit_required"] = False
        receipt["change_classification_rationale"] = (
            "Exact prior v2 receipt ancestry reuse fixture."
        )
        receipt["prior_audit_anchor"] = {
            "path": str(predecessor_path),
            "sha256": predecessor_sha256,
            "captured_at": "2026-08-04T00:00:00Z",
            "anchor_kind": "exact_project_validation_receipt_v2",
            "contract_revision": V2_RECEIPT_REVISION,
        }
        projects = receipt["projects"]
        assert isinstance(projects, list)
        project_witness = projects[0]
        assert isinstance(project_witness, dict)
        project_witness["audit_evidence_mode"] = (
            "exact_prior_deep_audit_snapshot_reuse"
        )
        receipt["validation_mode"] = "exact_prior_receipt_reuse"
        receipt["candidate_subprocess_count"] = 0
        return receipt

    def _call(
        self,
        *,
        api,
        anchor_path: Path,
        anchor_sha256: str,
        base: Path,
        project: Path,
        prior_runtime_binding: dict[str, object],
        deep_audit_required: bool,
        deep_project_validator,
    ):
        runtime = base / "candidate-runtime"
        runtime.mkdir(exist_ok=True)
        archive = base / "runtime-archive"
        return api(
            anchor_path,
            anchor_sha256,
            runtime_root=runtime,
            project_roots=[project],
            archive_root=archive,
            prior_runtime_binding=prior_runtime_binding,
            deep_audit_required=deep_audit_required,
            deep_project_validator=deep_project_validator,
        )

    def test_nonimpacting_path_rejects_weak_legacy_anchor(self) -> None:
        api = self._api()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            project = self._project(base)
            prior_binding = self._prior_runtime_binding(base)
            anchor_path = base / "legacy-anchor.json"
            anchor_sha256 = self._write_anchor(
                anchor_path,
                self._legacy_anchor(project, prior_binding),
            )
            deep = Mock(side_effect=AssertionError("deep audit must not be implicit"))
            with patch.object(
                runtime_cutover,
                "_run_json_command",
                side_effect=AssertionError("legacy anchor must not launch bounded work"),
            ) as candidate_subprocess:
                with self.assertRaisesRegex(
                    ValueError,
                    "legacy.*non-impacting|non-impacting.*legacy",
                ):
                    self._call(
                        api=api,
                        anchor_path=anchor_path,
                        anchor_sha256=anchor_sha256,
                        base=base,
                        project=project,
                        prior_runtime_binding=prior_binding,
                        deep_audit_required=False,
                        deep_project_validator=deep,
                    )
            candidate_subprocess.assert_not_called()
            deep.assert_not_called()

    def test_exact_v2_receipt_reuses_with_zero_candidate_subprocess(self) -> None:
        api = self._api()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            project = self._project(base)
            prior_binding = self._prior_runtime_binding(base)
            anchor_path = base / "v2-anchor.json"
            anchor_sha256 = self._write_anchor(
                anchor_path,
                self._v2_anchor(project, prior_binding),
            )
            deep = Mock(side_effect=AssertionError("exact v2 reuse must not audit"))
            with patch.object(
                runtime_cutover,
                "_run_json_command",
                side_effect=AssertionError("exact v2 reuse must not spawn candidate"),
            ) as candidate_subprocess:
                result = self._call(
                    api=api,
                    anchor_path=anchor_path,
                    anchor_sha256=anchor_sha256,
                    base=base,
                    project=project,
                    prior_runtime_binding=prior_binding,
                    deep_audit_required=False,
                    deep_project_validator=deep,
                )
            candidate_subprocess.assert_not_called()
            deep.assert_not_called()
            self.assertEqual(
                result["validation_mode"],
                "exact_v2_project_validation_receipt_reuse",
            )
            self.assertEqual(
                result["projects"][0]["round_states"],
                self._terminal_states(),
            )
            self.assertEqual(result["candidate_subprocess_count"], 0)

    def test_reuse_ancestry_reaches_one_deep_audit_genesis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            project = self._project(base)
            prior_binding = self._prior_runtime_binding(base)

            deep_path = base / "deep-genesis.json"
            deep_sha256 = self._write_anchor(
                deep_path,
                self._v2_anchor(project, prior_binding),
            )
            first_path = base / "reuse-first.json"
            first_sha256 = self._write_anchor(
                first_path,
                self._v2_reuse_anchor(
                    project,
                    prior_binding,
                    predecessor_path=deep_path,
                    predecessor_sha256=deep_sha256,
                ),
            )
            second_path = base / "reuse-second.json"
            second_sha256 = self._write_anchor(
                second_path,
                self._v2_reuse_anchor(
                    project,
                    prior_binding,
                    predecessor_path=first_path,
                    predecessor_sha256=first_sha256,
                ),
            )

            deep = Mock(side_effect=AssertionError("ancestry reuse must not audit"))
            approved_reader = runtime_cutover._approved_json_file
            with (
                patch.object(
                    runtime_cutover,
                    "_approved_json_file",
                    wraps=approved_reader,
                ) as ancestry_reads,
                patch.object(
                    runtime_cutover,
                    "_run_json_command",
                    side_effect=AssertionError("ancestry reuse must not spawn"),
                ) as candidate_subprocess,
            ):
                result = self._call(
                    api=self._api(),
                    anchor_path=second_path,
                    anchor_sha256=second_sha256,
                    base=base,
                    project=project,
                    prior_runtime_binding=prior_binding,
                    deep_audit_required=False,
                    deep_project_validator=deep,
                )
            candidate_subprocess.assert_not_called()
            deep.assert_not_called()
            self.assertEqual(ancestry_reads.call_count, 3)
            self.assertEqual(result["candidate_subprocess_count"], 0)

    def test_reuse_ancestry_rejects_missing_or_tampered_predecessor(self) -> None:
        for case in ("missing", "tampered"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary).resolve()
                project = self._project(base)
                prior_binding = self._prior_runtime_binding(base)
                predecessor_path = base / "deep-genesis.json"
                if case == "missing":
                    predecessor_sha256 = "d" * 64
                else:
                    predecessor_sha256 = self._write_anchor(
                        predecessor_path,
                        self._v2_anchor(project, prior_binding),
                    )
                    predecessor_path.write_text(
                        predecessor_path.read_text(encoding="utf-8") + " ",
                        encoding="utf-8",
                    )
                reuse_path = base / "reuse.json"
                reuse_sha256 = self._write_anchor(
                    reuse_path,
                    self._v2_reuse_anchor(
                        project,
                        prior_binding,
                        predecessor_path=predecessor_path,
                        predecessor_sha256=predecessor_sha256,
                    ),
                )
                deep = Mock(side_effect=AssertionError("broken ancestry must not audit"))
                with patch.object(
                    runtime_cutover,
                    "_run_json_command",
                    side_effect=AssertionError("broken ancestry must not spawn"),
                ) as candidate_subprocess:
                    with self.assertRaises(ValueError):
                        self._call(
                            api=self._api(),
                            anchor_path=reuse_path,
                            anchor_sha256=reuse_sha256,
                            base=base,
                            project=project,
                            prior_runtime_binding=prior_binding,
                            deep_audit_required=False,
                            deep_project_validator=deep,
                        )
                candidate_subprocess.assert_not_called()
                deep.assert_not_called()

    def test_reuse_ancestry_rejects_legacy_predecessor_without_reading_it(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            project = self._project(base)
            prior_binding = self._prior_runtime_binding(base)
            legacy_path = base / "legacy.json"
            legacy_sha256 = self._write_anchor(
                legacy_path,
                self._legacy_anchor(project, prior_binding),
            )
            reuse = self._v2_reuse_anchor(
                project,
                prior_binding,
                predecessor_path=legacy_path,
                predecessor_sha256=legacy_sha256,
            )
            predecessor = reuse["prior_audit_anchor"]
            assert isinstance(predecessor, dict)
            predecessor["anchor_kind"] = "legacy_current_ok_report"
            predecessor["contract_revision"] = "legacy_current_ok_report"
            reuse_path = base / "reuse.json"
            reuse_sha256 = self._write_anchor(reuse_path, reuse)
            approved_reader = runtime_cutover._approved_json_file
            with patch.object(
                runtime_cutover,
                "_approved_json_file",
                wraps=approved_reader,
            ) as single_reader:
                with self.assertRaisesRegex(ValueError, "exact v2 predecessor"):
                    self._call(
                        api=self._api(),
                        anchor_path=reuse_path,
                        anchor_sha256=reuse_sha256,
                        base=base,
                        project=project,
                        prior_runtime_binding=prior_binding,
                        deep_audit_required=False,
                        deep_project_validator=Mock(),
                    )
            self.assertEqual(single_reader.call_count, 1)

    def test_reuse_ancestry_revalidates_nontruth_permissions_at_every_layer(
        self,
    ) -> None:
        for field, value in (
            ("project_effect", "mutation"),
            ("truth_effect", "fact_admission"),
            ("premise_eligible", True),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary).resolve()
                project = self._project(base)
                prior_binding = self._prior_runtime_binding(base)
                predecessor = self._v2_anchor(project, prior_binding)
                predecessor[field] = value
                predecessor_path = base / "deep-genesis.json"
                predecessor_sha256 = self._write_anchor(
                    predecessor_path,
                    predecessor,
                )
                reuse_path = base / "reuse.json"
                reuse_sha256 = self._write_anchor(
                    reuse_path,
                    self._v2_reuse_anchor(
                        project,
                        prior_binding,
                        predecessor_path=predecessor_path,
                        predecessor_sha256=predecessor_sha256,
                    ),
                )
                with self.assertRaises(ValueError):
                    self._call(
                        api=self._api(),
                        anchor_path=reuse_path,
                        anchor_sha256=reuse_sha256,
                        base=base,
                        project=project,
                        prior_runtime_binding=prior_binding,
                        deep_audit_required=False,
                        deep_project_validator=Mock(),
                    )

    def test_reuse_ancestry_requires_project_snapshot_and_round_continuity(
        self,
    ) -> None:
        def drift_root(receipt: dict[str, object], base: Path) -> None:
            projects = receipt["projects"]
            assert isinstance(projects, list)
            project = projects[0]
            assert isinstance(project, dict)
            other_root = str(base / "different-project")
            project["project_root"] = other_root
            state = project["project_state"]
            assert isinstance(state, dict)
            state["project_root"] = other_root

        def drift_snapshot(receipt: dict[str, object], _base: Path) -> None:
            projects = receipt["projects"]
            assert isinstance(projects, list)
            project = projects[0]
            assert isinstance(project, dict)
            state = project["project_state"]
            assert isinstance(state, dict)
            state["state_sha256"] = "0" * 64

        def drift_round_map(receipt: dict[str, object], _base: Path) -> None:
            projects = receipt["projects"]
            assert isinstance(projects, list)
            project = projects[0]
            assert isinstance(project, dict)
            states = project["round_states"]
            assert isinstance(states, dict)
            states[self.ROUND_IDS[0]] = "aborted"

        for label, mutate in (
            ("project_root", drift_root),
            ("project_snapshot", drift_snapshot),
            ("round_map", drift_round_map),
        ):
            with self.subTest(field=label), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary).resolve()
                project = self._project(base)
                prior_binding = self._prior_runtime_binding(base)
                predecessor = self._v2_anchor(project, prior_binding)
                mutate(predecessor, base)
                predecessor_path = base / "deep-genesis.json"
                predecessor_sha256 = self._write_anchor(
                    predecessor_path,
                    predecessor,
                )
                reuse_path = base / "reuse.json"
                reuse_sha256 = self._write_anchor(
                    reuse_path,
                    self._v2_reuse_anchor(
                        project,
                        prior_binding,
                        predecessor_path=predecessor_path,
                        predecessor_sha256=predecessor_sha256,
                    ),
                )
                with self.assertRaisesRegex(ValueError, "project lineage drifted"):
                    self._call(
                        api=self._api(),
                        anchor_path=reuse_path,
                        anchor_sha256=reuse_sha256,
                        base=base,
                        project=project,
                        prior_runtime_binding=prior_binding,
                        deep_audit_required=False,
                        deep_project_validator=Mock(),
                    )

    def test_reuse_ancestry_has_one_fixed_depth_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            project = self._project(base)
            prior_binding = self._prior_runtime_binding(base)
            current_path = base / "deep-genesis.json"
            current_sha256 = self._write_anchor(
                current_path,
                self._v2_anchor(project, prior_binding),
            )
            for index in range(runtime_cutover.MAX_PRIOR_RECEIPT_ANCESTRY_DEPTH):
                next_path = base / f"reuse-{index:02d}.json"
                next_sha256 = self._write_anchor(
                    next_path,
                    self._v2_reuse_anchor(
                        project,
                        prior_binding,
                        predecessor_path=current_path,
                        predecessor_sha256=current_sha256,
                    ),
                )
                current_path = next_path
                current_sha256 = next_sha256
            with self.assertRaisesRegex(ValueError, "depth bound"):
                self._call(
                    api=self._api(),
                    anchor_path=current_path,
                    anchor_sha256=current_sha256,
                    base=base,
                    project=project,
                    prior_runtime_binding=prior_binding,
                    deep_audit_required=False,
                    deep_project_validator=Mock(),
                )

    def test_reuse_ancestry_rejects_repeated_path_or_sha_before_reread(self) -> None:
        for repeated_identity in ("path", "sha256"):
            with (
                self.subTest(identity=repeated_identity),
                tempfile.TemporaryDirectory() as temporary,
            ):
                base = Path(temporary).resolve()
                project = self._project(base)
                prior_binding = self._prior_runtime_binding(base)
                top_path = base / "top-reuse.json"
                predecessor_path = base / "predecessor-reuse.json"
                top_path.touch()
                predecessor_path.touch()
                top_sha256 = "a" * 64
                predecessor_sha256 = "b" * 64
                repeated_path = (
                    top_path if repeated_identity == "path" else base / "third.json"
                )
                repeated_sha256 = (
                    "c" * 64 if repeated_identity == "path" else top_sha256
                )
                top_receipt = self._v2_reuse_anchor(
                    project,
                    prior_binding,
                    predecessor_path=predecessor_path,
                    predecessor_sha256=predecessor_sha256,
                )
                predecessor_receipt = self._v2_reuse_anchor(
                    project,
                    prior_binding,
                    predecessor_path=repeated_path,
                    predecessor_sha256=repeated_sha256,
                )
                reads: list[tuple[str, str]] = []

                def controlled_single_read(
                    value: Path | str,
                    expected_sha256: str | None,
                    *,
                    label: str,
                ):
                    del label
                    identity = (str(value), str(expected_sha256))
                    reads.append(identity)
                    if identity == (str(top_path), top_sha256):
                        return top_path, copy.deepcopy(top_receipt), top_sha256
                    if identity == (str(predecessor_path), predecessor_sha256):
                        return (
                            predecessor_path,
                            copy.deepcopy(predecessor_receipt),
                            predecessor_sha256,
                        )
                    raise AssertionError("repeated identity was read a second time")

                with patch.object(
                    runtime_cutover,
                    "_approved_json_file",
                    side_effect=controlled_single_read,
                ):
                    with self.assertRaisesRegex(ValueError, "repeats one path or SHA"):
                        self._call(
                            api=self._api(),
                            anchor_path=top_path,
                            anchor_sha256=top_sha256,
                            base=base,
                            project=project,
                            prior_runtime_binding=prior_binding,
                            deep_audit_required=False,
                            deep_project_validator=Mock(),
                        )
                self.assertEqual(
                    reads,
                    [
                        (str(top_path), top_sha256),
                        (str(predecessor_path), predecessor_sha256),
                    ],
                )

    def test_every_minimum_v2_reuse_field_is_fail_closed(self) -> None:
        api = self._api()

        def drift_project_state(receipt: dict[str, object]) -> None:
            projects = receipt["projects"]
            assert isinstance(projects, list)
            project = projects[0]
            assert isinstance(project, dict)
            state = project["project_state"]
            assert isinstance(state, dict)
            state["state_sha256"] = "0" * 64

        def drift_round_map(receipt: dict[str, object]) -> None:
            projects = receipt["projects"]
            assert isinstance(projects, list)
            project = projects[0]
            assert isinstance(project, dict)
            states = project["round_states"]
            assert isinstance(states, dict)
            states[self.ROUND_IDS[1]] = "active"

        cases = (
            ("project_state", drift_project_state),
            ("terminal_round_map", drift_round_map),
            (
                "runtime_content_identity",
                lambda receipt: receipt.__setitem__(
                    "candidate_runtime_content_sha256", "b" * 64
                ),
            ),
            (
                "runtime_manifest_identity",
                lambda receipt: receipt.__setitem__(
                    "candidate_manifest_sha256", "c" * 64
                ),
            ),
            (
                "truth_effect",
                lambda receipt: receipt.__setitem__("truth_effect", "fact_admission"),
            ),
            (
                "project_effect",
                lambda receipt: receipt.__setitem__("project_effect", "mutation"),
            ),
            (
                "premise_eligible",
                lambda receipt: receipt.__setitem__("premise_eligible", True),
            ),
        )
        for label, mutate in cases:
            with self.subTest(field=label), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary).resolve()
                project = self._project(base)
                prior_binding = self._prior_runtime_binding(base)
                receipt = copy.deepcopy(self._v2_anchor(project, prior_binding))
                mutate(receipt)
                anchor_path = base / "drifted-v2-anchor.json"
                anchor_sha256 = self._write_anchor(anchor_path, receipt)
                deep = Mock(
                    side_effect=AssertionError("v2 drift must not silently audit")
                )
                with patch.object(
                    runtime_cutover,
                    "_run_json_command",
                    side_effect=AssertionError("v2 drift must not spawn candidate"),
                ) as candidate_subprocess:
                    with self.assertRaises(ValueError):
                        self._call(
                            api=api,
                            anchor_path=anchor_path,
                            anchor_sha256=anchor_sha256,
                            base=base,
                            project=project,
                            prior_runtime_binding=prior_binding,
                            deep_audit_required=False,
                            deep_project_validator=deep,
                        )
                candidate_subprocess.assert_not_called()
                deep.assert_not_called()

    def test_deep_path_allows_legacy_anchor_and_calls_deep_validator_once(self) -> None:
        api = self._api()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            project = self._project(base)
            prior_binding = self._prior_runtime_binding(base)
            anchor_path = base / "legacy-anchor.json"
            anchor_sha256 = self._write_anchor(
                anchor_path,
                self._legacy_anchor(project, prior_binding),
            )
            deep_result = {
                "projects": [
                    {
                        "project_root": str(project),
                        "round_states": self._terminal_states(),
                        "audit_current_ok": True,
                    }
                ],
                "runtime_bindings": [],
                "candidate_subprocess_count": 1,
            }
            deep = Mock(return_value=deep_result)
            result = self._call(
                api=api,
                anchor_path=anchor_path,
                anchor_sha256=anchor_sha256,
                base=base,
                project=project,
                prior_runtime_binding=prior_binding,
                deep_audit_required=True,
                deep_project_validator=deep,
            )
            self.assertEqual(deep.call_count, 1)
            self.assertEqual(result["projects"], deep_result["projects"])

    def test_approved_json_hash_and_payload_come_from_one_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "approved.json"
            approved = {"safe": True}
            path.write_text(json.dumps(approved) + "\n", encoding="utf-8")
            expected_sha256 = sha256_bytes(path.read_bytes())
            with patch.object(
                runtime_cutover,
                "_read_json_file",
                side_effect=AssertionError("approved JSON must not be read twice"),
            ) as second_read:
                _, payload, actual = runtime_cutover._approved_json_file(
                    path,
                    expected_sha256,
                    label="single-read fixture",
                )
            second_read.assert_not_called()
            self.assertEqual(actual, expected_sha256)
            self.assertEqual(payload, approved)

    def test_v2_integer_fields_reject_booleans(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            project = self._project(base)
            prior_binding = self._prior_runtime_binding(base)
            fixture = self._v2_anchor(project, prior_binding)
            for field in ("schema_version", "candidate_subprocess_count"):
                with self.subTest(field=field):
                    receipt = copy.deepcopy(fixture)
                    receipt[field] = True
                    with self.assertRaises(ValueError):
                        runtime_cutover._validate_cutover_project_validation_receipt_payload(
                            receipt,
                            allow_legacy=False,
                        )

    def test_v2_semantic_and_provenance_fields_fail_closed(self) -> None:
        def mutate_nested(field: str, value: object):
            def mutate(receipt: dict[str, object]) -> None:
                anchor = receipt["prior_audit_anchor"]
                assert isinstance(anchor, dict)
                anchor[field] = value

            return mutate

        def mutate_project_mode(receipt: dict[str, object]) -> None:
            projects = receipt["projects"]
            assert isinstance(projects, list)
            project = projects[0]
            assert isinstance(project, dict)
            project["audit_evidence_mode"] = (
                "exact_prior_deep_audit_snapshot_reuse"
            )

        def mutate_snapshot_revision(receipt: dict[str, object]) -> None:
            projects = receipt["projects"]
            assert isinstance(projects, list)
            project = projects[0]
            assert isinstance(project, dict)
            state = project["project_state"]
            assert isinstance(state, dict)
            state["snapshot_revision"] = "stale-snapshot-policy"

        cases = (
            ("nested_path_type", mutate_nested("path", 7)),
            ("nested_sha", mutate_nested("sha256", "not-a-digest")),
            ("nested_kind", mutate_nested("anchor_kind", "unknown")),
            (
                "nested_revision_pair",
                mutate_nested("contract_revision", V2_RECEIPT_REVISION),
            ),
            (
                "future_timestamp",
                mutate_nested("captured_at", "2999-01-01T00:00:00Z"),
            ),
            (
                "runtime_identity_type",
                lambda receipt: receipt.__setitem__(
                    "candidate_runtime_identity", "not-a-digest"
                ),
            ),
            ("project_mode", mutate_project_mode),
            ("snapshot_revision", mutate_snapshot_revision),
            (
                "missing_release_provenance",
                lambda receipt: receipt.__setitem__(
                    "release_validation_evidence", []
                ),
            ),
        )
        for label, mutate in cases:
            with self.subTest(field=label), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary).resolve()
                project = self._project(base)
                prior_binding = self._prior_runtime_binding(base)
                receipt = copy.deepcopy(self._v2_anchor(project, prior_binding))
                mutate(receipt)
                path = base / "semantic-drift.json"
                digest = self._write_anchor(path, receipt)
                deep = Mock(side_effect=AssertionError("semantic drift must not audit"))
                with patch.object(
                    runtime_cutover,
                    "_run_json_command",
                    side_effect=AssertionError("semantic drift must fail locally"),
                ) as subprocess_call:
                    with self.assertRaises(ValueError):
                        self._call(
                            api=self._api(),
                            anchor_path=path,
                            anchor_sha256=digest,
                            base=base,
                            project=project,
                            prior_runtime_binding=prior_binding,
                            deep_audit_required=False,
                            deep_project_validator=deep,
                        )
                subprocess_call.assert_not_called()
                deep.assert_not_called()

    def test_approval_bearing_bounded_callback_is_not_public(self) -> None:
        self.assertNotIn(
            "bounded_project_validator",
            inspect.signature(
                runtime_cutover.validate_or_reuse_project_validation_anchor
            ).parameters,
        )
        self.assertNotIn(
            "bounded_project_validator",
            inspect.signature(
                runtime_cutover.build_cutover_project_validation_receipt
            ).parameters,
        )


if __name__ == "__main__":
    unittest.main()
