from __future__ import annotations

import importlib.util
import inspect
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path

from mathgraph.adoption import (
    build_adoption_plan,
    compact_adoption_binding,
    validate_workload_profile,
)
from mathgraph.contracts import POLICY_REVISION_V4, sha256_json
from mathgraph.cli import main as cli_main
from mathgraph.fact_bundles import FactBundleStore
from mathgraph.migration import project_tree_snapshot
from mathgraph.modes import (
    EXPLORATION_FEATURES,
    FACT_ADMISSION_CONTRACT_SHA256,
    MODE_POLICY_SHA256,
    build_execution_profile,
    validate_mode_binding_fields,
)
from mathgraph.model import Fact
from mathgraph.orchestrator import (
    create_round,
    create_verifier_assignment,
    validate_return,
)
from mathgraph.store import MathGraphStore
from mathgraph.verification_bundles import VerificationBundleStore


LEARNING_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "learning_graph.py"
)
LEARNING_SPEC = importlib.util.spec_from_file_location(
    "unified_learning_graph",
    LEARNING_SCRIPT,
)
assert LEARNING_SPEC is not None and LEARNING_SPEC.loader is not None
learning_graph = importlib.util.module_from_spec(LEARNING_SPEC)
LEARNING_SPEC.loader.exec_module(learning_graph)


def workload_profile(
    *,
    activity: str = "proof",
    audience: str = "internal",
    computation_role: str = "none",
    stages: int = 0,
    candidates: int = 1,
    internal_edges: int = 0,
    atomic: bool = False,
    source: bool = False,
    convention: bool = False,
    quantifier: bool = False,
    terminology: bool = False,
    ambiguity: bool | None = None,
) -> dict:
    profile = {
        "schema_version": 1,
        "policy_revision": POLICY_REVISION_V4,
        "activity": activity,
        "audience": audience,
        "computation": {
            "role": computation_role,
            "estimated_wall_seconds": 0,
            "stage_count": stages,
            "resume_required": False,
        },
        "fact_output": {
            "candidate_count": candidates,
            "internal_dependency_count": internal_edges,
            "atomic_visibility_required": atomic,
        },
        "semantics": {
            "source_claim": source,
            "convention_sensitive": convention,
            "quantifier_sensitive": quantifier,
            "terminology_sensitive": terminology,
        },
    }
    if ambiguity is not None:
        profile["semantics"]["source_ambiguity"] = ambiguity
    return profile


def adoption_binding(profile: dict) -> dict:
    return compact_adoption_binding(build_adoption_plan(profile))


class UnifiedReasoningModeTests(unittest.TestCase):
    @staticmethod
    def _v4_review_payload(
        fact_id: str,
        assignment: dict,
        *,
        reviewer: str = "legacy-fresh-verifier",
    ) -> dict:
        return {
            "schema_version": 4,
            "policy_revision": POLICY_REVISION_V4,
            "fact_id": fact_id,
            "submission_sha256": assignment["submission_sha256"],
            "bundle_sha256": assignment["bundle_sha256"],
            "verdict": "correct",
            "findings": [],
            "prior_review_dispositions": [],
            "reviewer": reviewer,
            "host_attestation": {
                "host": "legacy-fixture-host",
                "agent_id": reviewer,
                "isolation": "fresh_context",
                "fork_turns": "none",
                "allowed_bundle_sha256": assignment["bundle_sha256"],
            },
        }

    @staticmethod
    def _atomic_facts(project_id: str) -> tuple[Fact, Fact]:
        first = Fact(
            problem_id=project_id,
            author="legacy-bundle-worker",
            predecessors=[],
            statement="[CLAIM:A] The historical atomic lemma holds.",
            proof="Direct.",
        )
        second = Fact(
            problem_id=project_id,
            author="legacy-bundle-worker",
            predecessors=[first.fact_id],
            statement="[CLAIM:B] The historical atomic consequence holds.",
            proof="Use the historical atomic lemma.",
        )
        return first, second

    def test_v3_is_read_only_but_dry_run_upgrade_remains_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            root = base / "legacy-v3"
            writer = MathGraphStore._for_legacy_workflow_fixture(root)
            writer.initialize(project_id="legacy-v3", title="Legacy V3")
            before = project_tree_snapshot(root)

            strict = MathGraphStore(root)
            with self.assertRaisesRegex(ValueError, "V1-V3 is read-only"):
                strict.memory_add(
                    {"kind": "direction", "claim": "Forbidden V3 mutation."},
                    actor="main",
                )
            self.assertEqual(before, project_tree_snapshot(root))

            blocked_child_writers = {
                "atomic submit": lambda: strict.fact_bundles().submit(
                    {},
                    worker="forbidden-worker",
                    external_fact_exists=lambda _fact_id: False,
                ),
                "atomic verifier": lambda: strict.fact_bundles().verifier_task(
                    "factbundle-" + "0" * 64
                ),
                "atomic review": lambda: strict.fact_bundles().record_review(
                    "factbundle-" + "0" * 64,
                    {},
                ),
                "atomic admit": lambda: strict.fact_bundles().admit(
                    "factbundle-" + "0" * 64,
                    review_id="0" * 64,
                ),
                "ordinary verification bundle": (
                    lambda: strict.verification_bundles().create()
                ),
                "blackboard": lambda: strict.blackboard().create_space(
                    name="forbidden",
                    scope="legacy projects remain immutable",
                    actor="operator",
                ),
            }
            for label, writer_call in blocked_child_writers.items():
                with self.subTest(writer=label):
                    with self.assertRaisesRegex(ValueError, "V1-V3 is read-only"):
                        writer_call()
                    self.assertEqual(before, project_tree_snapshot(root))

            self.assertTrue(strict.audit().current_ok)
            self.assertEqual(
                strict.reasoning_modes().status()["compatibility"],
                "legacy_v1_v3_read_only_requires_upgrade_project_copy",
            )
            self.assertEqual(before, project_tree_snapshot(root))

            payload_path = base / "forbidden-memory.json"
            payload_path.write_text(
                json.dumps({"kind": "direction", "claim": "Still forbidden."}),
                encoding="utf-8",
            )
            stderr = StringIO()
            with redirect_stderr(stderr):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "operator",
                        "memory-add",
                        "--input",
                        str(payload_path),
                        "--actor",
                        "main",
                    ]
                )
            self.assertEqual(code, 2)
            self.assertIn("V1-V3 is read-only", stderr.getvalue())
            self.assertEqual(before, project_tree_snapshot(root))

            stdout = StringIO()
            with redirect_stdout(stdout):
                code = cli_main(
                    [
                        "--root",
                        str(root),
                        "--role",
                        "operator",
                        "upgrade-workflow",
                        "--to",
                        "4",
                        "--dry-run",
                        "--actor",
                        "operator",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(before, project_tree_snapshot(root))

            empty = base / "strict-new-v3"
            with self.assertRaisesRegex(ValueError, "creates V4 projects only"):
                MathGraphStore(empty).initialize(
                    project_id="strict-new-v3", title="Strict V3"
                )
            self.assertFalse(empty.exists())

    def test_v3_interface_materialization_is_guarded_and_reads_are_pure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            fixture = MathGraphStore._for_legacy_workflow_fixture(root)
            fixture.initialize(project_id="legacy-v3-interface", title="V3")
            fact = Fact(
                problem_id="legacy-v3-interface",
                author="legacy-worker",
                predecessors=[],
                statement="A historical V3 interface fact.",
                proof="Direct.",
            )
            fixture.submit(fact, worker="legacy-worker")
            packet = fixture.freeze_verification_packet(fact.fact_id)
            review_path = fixture.record_review(
                {
                    "fact_id": fact.fact_id,
                    "submission_sha256": packet["submission_sha256"],
                    "packet_sha256": packet["packet_sha256"],
                    "verdict": "correct",
                    "critical_errors": [],
                    "gaps": [],
                    "repair_hints": [],
                    "reviewer": "legacy-fresh-verifier",
                }
            )
            fixture.admit(fact.fact_id, review_id=review_path.stem)
            fixture.statement_interface(fact.fact_id)
            interface_path = fixture.interfaces_dir / f"{fact.fact_id}.json"
            interface_path.unlink()

            strict = MathGraphStore(root)
            before = project_tree_snapshot(root)
            with self.assertRaisesRegex(ValueError, "V1-V3 is read-only"):
                strict.statement_interface(fact.fact_id)
            self.assertEqual(before, project_tree_snapshot(root))

            interface = strict.statement_interface(
                fact.fact_id,
                materialize=False,
            )
            self.assertEqual(interface["fact_id"], fact.fact_id)
            self.assertEqual(interface["schema_version"], 3)
            self.assertTrue(strict.audit().current_ok)
            strict.reasoning_modes().status()
            strict.blackboard().reindex(apply=False)
            strict.search("historical")
            self.assertEqual(before, project_tree_snapshot(root))

    def test_optional_source_ambiguity_preserves_legacy_profile_hashes(self) -> None:
        legacy = workload_profile(
            activity="literature",
            source=True,
        )
        validated = validate_workload_profile(legacy)
        plan = build_adoption_plan(legacy)
        binding = compact_adoption_binding(plan)
        self.assertEqual(validated, legacy)
        self.assertEqual(
            sha256_json(validated),
            "052e004c8ed4fc938ecc425c436b0f3bead0ef171330dea4f23567e339a33dbf",
        )
        self.assertEqual(
            plan["plan_sha256"],
            "19d0b663d1450b92d7bc0a7e0fe3e0b58c9cf0fe76e5f7f04dc556d2be671854",
        )
        self.assertEqual(
            binding["binding_sha256"],
            "0667b5f0365760f2c3765639f77535184d4427d4da8e8422d596cdd5a23d77a1",
        )
        explicit_false = workload_profile(
            activity="literature",
            source=True,
            ambiguity=False,
        )
        self.assertNotEqual(sha256_json(explicit_false), sha256_json(legacy))

    def test_source_ambiguity_requires_source_claim(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires source_claim=true"):
            validate_workload_profile(
                workload_profile(
                    activity="literature",
                    source=False,
                    ambiguity=True,
                )
            )

    def test_auto_source_ambiguity_has_deterministic_routing_effect(self) -> None:
        event_id = "modeevt-" + "8" * 64
        baseline_binding = adoption_binding(
            workload_profile(activity="literature", source=True)
        )
        ambiguous_binding = adoption_binding(
            workload_profile(
                activity="literature",
                source=True,
                ambiguity=True,
            )
        )
        baseline = build_execution_profile(
            reasoning_mode="auto",
            reasoning_mode_event_id=event_id,
            adoption_binding=baseline_binding,
        )
        ambiguous = build_execution_profile(
            reasoning_mode="auto",
            reasoning_mode_event_id=event_id,
            adoption_binding=ambiguous_binding,
        )
        self.assertEqual(
            baseline["adoption_feature_statuses"]["source_claim_gate"],
            "required",
        )
        self.assertEqual(
            ambiguous["adoption_feature_statuses"]["source_claim_gate"],
            "required",
        )
        self.assertEqual(
            baseline["exploration_features"]["paper_logic_graph"]["status"],
            "required",
        )
        for feature in (
            "paper_audit_graph",
            "full_fidelity_paper_mirror",
            "parallel_clean_context_panel",
            "barriered_blackboard_pulse",
            "orthogonal_specialist_escalation",
        ):
            with self.subTest(feature=feature):
                self.assertEqual(
                    baseline["exploration_features"][feature]["status"],
                    "available",
                )
                self.assertEqual(
                    ambiguous["exploration_features"][feature]["status"],
                    "required",
                )

    def test_fact_admission_contract_is_identical_across_modes(self) -> None:
        self.assertEqual(
            FACT_ADMISSION_CONTRACT_SHA256,
            "68c4785a8c36558ee7effb79be755405d2be785ee00f81795328c6cc5a211289",
        )
        observed: set[str] = set()
        for mode in ("fast", "auto", "deep"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                store = MathGraphStore(Path(tmp))
                store.initialize(
                    project_id=f"mode-{mode}",
                    title=f"Mode {mode}",
                    workflow_evidence_version=4,
                    reasoning_mode=mode,
                )
                status = store.reasoning_modes().status()
                observed.add(status["fact_admission_contract_sha256"])
                envelope = store._read_json(
                    store.reasoning_modes().contract_path
                )
                self.assertEqual(
                    status["fact_admission_contract_sha256"],
                    envelope["contract_sha256"],
                )
        self.assertEqual(observed, {FACT_ADMISSION_CONTRACT_SHA256})

    def test_mode_switch_applies_only_to_future_frozen_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = MathGraphStore(root)
            store.initialize(
                project_id="future-only",
                title="Future-only mode switch",
                workflow_evidence_version=4,
                reasoning_mode="fast",
            )
            first_memory = store.memory_add(
                {
                    "kind": "direction",
                    "claim": "Inspect the first frozen route.",
                },
                actor="main",
            )
            first = create_round(
                store,
                workers=1,
                memory_ids=[first_memory],
                host_task_scope_id="unified-future-only-test",
            )
            first_manifest_path = (
                store.rounds_dir / first["round_id"] / "round.json"
            )
            frozen_before = first_manifest_path.read_bytes()
            first_event = first["reasoning_mode_event_id"]
            self.assertEqual(first["reasoning_mode"], "fast")

            switched = store.reasoning_modes().switch(
                to_mode="deep",
                actor="main",
                reason="Exercise the future-only boundary.",
            )
            self.assertNotEqual(first_event, switched["reasoning_mode_event_id"])
            self.assertEqual(first_manifest_path.read_bytes(), frozen_before)

            second_memory = store.memory_add(
                {
                    "kind": "direction",
                    "claim": "Inspect the second frozen route.",
                },
                actor="main",
            )
            second = create_round(
                store,
                workers=1,
                memory_ids=[second_memory],
                host_task_scope_id="unified-future-only-test",
            )
            self.assertEqual(second["reasoning_mode"], "deep")
            self.assertEqual(
                first["fact_admission_contract_sha256"],
                second["fact_admission_contract_sha256"],
            )
            self.assertNotEqual(
                first["reasoning_mode_event_id"],
                second["reasoning_mode_event_id"],
            )
            self.assertTrue(store.audit().ok)

    def test_legacy_chalk_v4_requires_explicit_mode_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = MathGraphStore(root)
            store.initialize(
                project_id="legacy-chalk-v4",
                title="Legacy Chalk V4",
                workflow_evidence_version=4,
            )
            mode_root = store.reasoning_modes().root
            shutil.rmtree(mode_root)

            status = store.reasoning_modes().status()
            self.assertFalse(status["initialized"])
            self.assertEqual(
                status["compatibility"],
                "legacy_chalk_v4_read_only_until_mode_init",
            )
            audit = store.audit()
            self.assertTrue(audit.ok)
            self.assertTrue(
                any("legacy" in warning for warning in audit.warnings)
            )
            with self.assertRaisesRegex(ValueError, "read-only"):
                store.reasoning_modes().binding_for_new_work_unit(
                    adoption_binding=adoption_binding(workload_profile())
                )

            initialized = store.reasoning_modes().initialize(
                reasoning_mode="auto",
                actor="operator",
                reason="Explicitly activate future unified writes.",
                source_kind="legacy_chalk_v4_upgrade",
            )
            self.assertTrue(initialized["initialized"])
            receipt = store._read_json(
                store.reasoning_modes().activation_receipt_path
            )
            self.assertEqual(
                receipt["source_kind"],
                "legacy_chalk_v4_upgrade",
            )
            self.assertTrue(store.audit().ok)

    def test_public_mode_none_is_not_a_writable_v4_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "forbidden-mode-none"
            store = MathGraphStore(root)
            with self.assertRaisesRegex(
                ValueError,
                "reserved for the internal inherited-Chalk fixture seam",
            ):
                store.initialize(
                    project_id="forbidden-mode-none",
                    title="Forbidden mode-less V4",
                    workflow_evidence_version=4,
                    reasoning_mode=None,
                )
            self.assertFalse(root.exists())

    def test_public_constructors_expose_no_legacy_writer_switch(self) -> None:
        self.assertNotIn(
            "allow_legacy_writes",
            inspect.signature(MathGraphStore).parameters,
        )
        self.assertNotIn(
            "allow_legacy_admission",
            inspect.signature(FactBundleStore).parameters,
        )
        self.assertNotIn(
            "allow_legacy_creation",
            inspect.signature(VerificationBundleStore).parameters,
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "no-public-legacy-switch"
            with self.assertRaises(TypeError):
                MathGraphStore(root, allow_legacy_writes=True)
            self.assertFalse(root.exists())

    def test_mode_init_requires_clean_preactivation_audit_before_writing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            fixture = MathGraphStore._for_inherited_chalk_fixture(root)
            fixture.initialize(
                project_id="legacy-v4-dirty-preactivation",
                title="Legacy V4 dirty preactivation",
                workflow_evidence_version=4,
                reasoning_mode=None,
            )
            certificate_path = (
                fixture.reports_dir / "target-closure-certificate.json"
            )
            certificate = json.loads(
                certificate_path.read_text(encoding="utf-8")
            )
            certificate["certificate_sha256"] = "0" * 64
            certificate_path.write_text(
                json.dumps(certificate, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            fixture.lock_path.unlink()
            self.assertFalse(fixture.lock_path.exists())

            strict = MathGraphStore(root)
            self.assertFalse(strict.audit().current_ok)
            before = project_tree_snapshot(root)
            with self.assertRaisesRegex(
                ValueError,
                "mode-init requires a clean pre-activation audit",
            ):
                strict.reasoning_modes().initialize(
                    reasoning_mode="auto",
                    actor="operator",
                    reason="Must not activate a dirty inherited project.",
                    source_kind="legacy_chalk_v4_upgrade",
                )
            self.assertEqual(before, project_tree_snapshot(root))
            self.assertFalse(strict.reasoning_modes().has_any_state())

    def test_modeless_v4_all_public_writers_fail_before_bytes_change(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            fixture = MathGraphStore._for_inherited_chalk_fixture(root)
            fixture.initialize(
                project_id="legacy-v4-api-guard",
                title="Legacy V4 API guard",
                workflow_evidence_version=4,
                reasoning_mode=None,
            )
            pending = Fact(
                problem_id="legacy-v4-api-guard",
                author="legacy-worker",
                predecessors=[],
                statement="[CLAIM:P] A pending historical candidate.",
                proof="Candidate proof.",
            )
            pending_id = fixture.submit(pending, worker="legacy-worker")
            verifier = create_verifier_assignment(fixture, pending_id)
            review_payload = self._v4_review_payload(
                pending_id,
                verifier,
            )

            first, second = self._atomic_facts("legacy-v4-api-guard")
            bundle_payload = {
                "schema_version": 4,
                "policy_revision": POLICY_REVISION_V4,
                "project_id": "legacy-v4-api-guard",
                "facts": [
                    first.as_submission_dict(),
                    second.as_submission_dict(),
                ],
                "bundle_claim": "A pending historical atomic candidate.",
            }
            bundle_id = fixture.fact_bundles().submit(
                bundle_payload,
                worker="legacy-bundle-worker",
                external_fact_exists=lambda _fact_id: False,
            )
            bundle_manifest = fixture.fact_bundles().manifest(bundle_id)
            bundle_task = fixture.fact_bundle_verifier_task(bundle_id)
            bundle_review = {
                "fact_bundle_id": bundle_id,
                "manifest_sha256": bundle_manifest["manifest_sha256"],
                "verification_manifest_sha256": bundle_task[
                    "verification_manifest_sha256"
                ],
                "packet_sha256": bundle_task["packet_sha256"],
                "verdict": "correct",
                "findings": [],
                "reviewer": "legacy-bundle-verifier",
            }

            strict = MathGraphStore(root)
            before = project_tree_snapshot(root)
            new_fact = Fact(
                problem_id="legacy-v4-api-guard",
                author="new-worker",
                predecessors=[],
                statement="[CLAIM:N] A forbidden pre-activation candidate.",
                proof="Not writable yet.",
            )
            writers = {
                "ordinary submit": lambda: strict.submit(
                    new_fact,
                    worker="new-worker",
                ),
                "ordinary verifier": lambda: create_verifier_assignment(
                    strict,
                    pending_id,
                ),
                "ordinary review": lambda: strict.record_review(
                    review_payload
                ),
                "ordinary admit": lambda: strict.admit(
                    pending_id,
                    review_id="0" * 64,
                ),
                "atomic submit": lambda: strict.fact_bundles().submit(
                    bundle_payload,
                    worker="legacy-bundle-worker",
                    external_fact_exists=lambda _fact_id: False,
                ),
                "atomic verifier": lambda: strict.fact_bundles().verifier_task(
                    bundle_id
                ),
                "atomic review": lambda: strict.fact_bundles().record_review(
                    bundle_id,
                    bundle_review,
                ),
                "atomic admit": lambda: strict.fact_bundles().admit(
                    bundle_id,
                    review_id="0" * 64,
                ),
                "blackboard": lambda: strict.blackboard().create_space(
                    name="forbidden",
                    scope="must remain absent",
                    actor="operator",
                ),
                "claims": lambda: strict.claims().add_claim(
                    {}, actor="operator"
                ),
                "campaigns": lambda: strict.campaigns().create(
                    {}, actor="operator"
                ),
                "verification bundles": lambda: strict.verification_bundles().create(),
                "paper logic": lambda: strict.paper_logic().initialize(
                    actor="operator"
                ),
                "experiments": lambda: strict.experiments().start(
                    task_card={}, manifest={}
                ),
                "collaboration": lambda: strict.collaboration().create_plan(),
                "profile closure": lambda: strict.profile_closures().record(
                    "round-20260726T000000000000Z-00000000",
                    {"evidence": []},
                    actor="operator",
                ),
            }
            for label, writer in writers.items():
                with self.subTest(writer=label):
                    with self.assertRaisesRegex(ValueError, "read-only"):
                        writer()
                    self.assertEqual(before, project_tree_snapshot(root))

            activated = strict.reasoning_modes().initialize(
                reasoning_mode="deep",
                actor="operator",
                reason="Explicitly activate guarded future work.",
                source_kind="legacy_chalk_v4_upgrade",
            )
            self.assertTrue(activated["initialized"])
            strict.memory_add(
                {
                    "kind": "direction",
                    "claim": "A post-activation write is permitted.",
                },
                actor="main",
            )
            with self.assertRaisesRegex(ValueError, "profile-bound round"):
                create_verifier_assignment(strict, pending_id)
            with self.assertRaisesRegex(
                ValueError,
                "requires profile-bound round provenance",
            ):
                strict.fact_bundle_verifier_task(bundle_id)

            bundle_directory = strict.fact_bundles().root / bundle_id
            bundle_before = {
                path.relative_to(bundle_directory).as_posix(): path.read_bytes()
                for path in bundle_directory.rglob("*")
                if path.is_file()
            }
            low_level_calls = (
                lambda: strict.fact_bundles().verifier_task(bundle_id),
                lambda: strict.fact_bundles().record_review(
                    bundle_id,
                    bundle_review,
                ),
                lambda: strict.fact_bundles().admit(
                    bundle_id,
                    review_id="0" * 64,
                ),
            )
            for call in low_level_calls:
                with self.assertRaisesRegex(
                    ValueError,
                    "requires MathGraphStore authority",
                ):
                    call()
                self.assertEqual(
                    bundle_before,
                    {
                        path.relative_to(bundle_directory).as_posix(): path.read_bytes()
                        for path in bundle_directory.rglob("*")
                        if path.is_file()
                    },
                )
            self.assertFalse(
                (strict.fact_bundles().root / bundle_id / "ACCEPTED.json").exists()
            )
            self.assertTrue(
                set(bundle_manifest["fact_ids"]).isdisjoint(strict.fact_ids())
            )

    def test_modeless_v4_read_apis_do_not_materialize_or_rebuild(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            fixture = MathGraphStore._for_inherited_chalk_fixture(root)
            fixture.initialize(
                project_id="legacy-v4-read-matrix",
                title="Legacy V4 read matrix",
                workflow_evidence_version=4,
                reasoning_mode=None,
            )
            fact = Fact(
                problem_id="legacy-v4-read-matrix",
                author="legacy-worker",
                predecessors=[],
                statement="[CLAIM:R] The historical read fixture holds.",
                proof="Direct.",
            )
            fact_id = fixture.submit(fact, worker="legacy-worker")
            verifier = create_verifier_assignment(fixture, fact_id)
            review_path = fixture.record_review(
                self._v4_review_payload(fact_id, verifier)
            )
            fixture.admit(fact_id, review_id=review_path.stem)
            interface_path = fixture.interfaces_dir / f"{fact_id}.json"
            self.assertTrue(interface_path.is_file())
            interface_path.unlink()

            strict = MathGraphStore(root)
            before = project_tree_snapshot(root)
            with self.assertRaisesRegex(ValueError, "read-only"):
                strict.statement_interface(fact_id)
            self.assertEqual(before, project_tree_snapshot(root))

            pure_interface = strict.statement_interface(
                fact_id,
                materialize=False,
            )
            self.assertEqual(pure_interface["fact_id"], fact_id)
            self.assertEqual(pure_interface["schema_version"], 4)
            read_matrix = {
                "audit": strict.audit,
                "mode status": strict.reasoning_modes().status,
                "blackboard reindex dry-run": (
                    lambda: strict.blackboard().reindex(apply=False)
                ),
                "claim card": lambda: strict.claim_card(
                    fact_id,
                    audience="expert",
                ),
                "verification bundle verify": (
                    lambda: strict.verification_bundles().verify(
                        verifier["bundle_sha256"]
                    )
                ),
                "fact search": lambda: strict.search("historical"),
                "frontier": strict.frontier,
                "fact-bundle audit": lambda: strict.fact_bundles().audit(),
                "paper status": lambda: strict.paper_logic().status(),
            }
            for label, read_call in read_matrix.items():
                with self.subTest(read_api=label):
                    read_call()
                    self.assertEqual(before, project_tree_snapshot(root))

    def test_mode_activation_baselines_only_exact_historical_admissions(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            fixture = MathGraphStore._for_inherited_chalk_fixture(root)
            fixture.initialize(
                project_id="legacy-v4-activation-baseline",
                title="Legacy V4 activation baseline",
                workflow_evidence_version=4,
                reasoning_mode=None,
            )
            ordinary = Fact(
                problem_id="legacy-v4-activation-baseline",
                author="legacy-worker",
                predecessors=[],
                statement="[CLAIM:O] The historical ordinary fact holds.",
                proof="Direct.",
            )
            ordinary_id = fixture.submit(
                ordinary,
                worker="legacy-worker",
            )
            ordinary_task = create_verifier_assignment(
                fixture,
                ordinary_id,
            )
            ordinary_review = fixture.record_review(
                self._v4_review_payload(ordinary_id, ordinary_task)
            ).stem
            fixture.admit(ordinary_id, review_id=ordinary_review)

            first, second = self._atomic_facts(
                "legacy-v4-activation-baseline"
            )
            bundle_id = fixture.fact_bundles().submit(
                {
                    "schema_version": 4,
                    "policy_revision": POLICY_REVISION_V4,
                    "project_id": "legacy-v4-activation-baseline",
                    "facts": [
                        first.as_submission_dict(),
                        second.as_submission_dict(),
                    ],
                    "bundle_claim": "Historical accepted atomic evidence.",
                },
                worker="legacy-bundle-worker",
                external_fact_exists=lambda _fact_id: False,
            )
            manifest = fixture.fact_bundles().manifest(bundle_id)
            bundle_task = fixture.fact_bundle_verifier_task(bundle_id)
            bundle_review_id = fixture.fact_bundles().record_review(
                bundle_id,
                {
                    "fact_bundle_id": bundle_id,
                    "manifest_sha256": manifest["manifest_sha256"],
                    "verification_manifest_sha256": bundle_task[
                        "verification_manifest_sha256"
                    ],
                    "packet_sha256": bundle_task["packet_sha256"],
                    "verdict": "correct",
                    "findings": [],
                    "reviewer": "legacy-bundle-verifier",
                },
            )
            fixture.admit_fact_bundle(
                bundle_id,
                review_id=bundle_review_id,
            )

            strict = MathGraphStore(root)
            self.assertTrue(strict.audit().current_ok)
            strict.reasoning_modes().initialize(
                reasoning_mode="auto",
                actor="operator",
                reason="Freeze exact historical admissions.",
                source_kind="legacy_chalk_v4_upgrade",
            )
            receipt = strict._read_json(
                strict.reasoning_modes().activation_receipt_path
            )
            inventory = receipt["legacy_admission_inventory"]
            self.assertEqual(set(inventory["ordinary"]), {ordinary_id})
            self.assertEqual(set(inventory["atomic_bundles"]), {bundle_id})
            self.assertTrue(strict.audit().current_ok)
            self.assertEqual(
                set(strict.fact_ids()),
                {ordinary_id, *manifest["fact_ids"]},
            )

            ordinary_path = strict.fact_path(ordinary_id)
            ordinary_bytes = ordinary_path.read_bytes()
            ordinary_path.write_bytes(ordinary_bytes + b"\n")
            drifted = strict.audit()
            self.assertFalse(drifted.current_ok)
            self.assertTrue(
                any(
                    "bytes drifted after mode activation" in error
                    for error in drifted.errors
                ),
                drifted.errors,
            )
            ordinary_path.write_bytes(ordinary_bytes)
            self.assertTrue(strict.audit().current_ok)

            verification_bytes = strict.verification_log.read_bytes()
            verification_lines = verification_bytes.splitlines(
                keepends=True
            )
            accepted_line_index = next(
                index
                for index, line in enumerate(verification_lines)
                if ordinary_id.encode("utf-8") in line
                and b'"event": "accepted"' in line
            )
            verification_lines[accepted_line_index] = (
                verification_lines[accepted_line_index].rstrip(b"\r\n")
                + b" \n"
            )
            strict.verification_log.write_bytes(b"".join(verification_lines))
            event_byte_drift = strict.audit()
            self.assertFalse(event_byte_drift.current_ok)
            self.assertTrue(
                any(
                    "acceptance event bytes drifted" in error
                    for error in event_byte_drift.errors
                ),
                event_byte_drift.errors,
            )
            strict.verification_log.write_bytes(verification_bytes)
            self.assertTrue(strict.audit().current_ok)

            marker_path = (
                strict.fact_bundles().root / bundle_id / "ACCEPTED.json"
            )
            marker_bytes = marker_path.read_bytes()
            marker_path.write_bytes(marker_bytes.rstrip() + b" \n")
            marker_drift = strict.audit()
            self.assertFalse(marker_drift.current_ok)
            self.assertTrue(
                any(
                    "bytes drifted after mode activation" in error
                    for error in marker_drift.errors
                ),
                marker_drift.errors,
            )
            marker_path.write_bytes(marker_bytes)
            self.assertTrue(strict.audit().current_ok)

            same_bytes_path = root / "same-historical-fact-bytes.md"
            same_bytes_path.write_bytes(ordinary_bytes)
            ordinary_path.unlink()
            ordinary_path.symlink_to(same_bytes_path)
            symlink_drift = strict.audit()
            self.assertFalse(symlink_drift.current_ok)
            self.assertTrue(
                any(
                    "path is missing or unsafe" in error
                    for error in symlink_drift.errors
                ),
                symlink_drift.errors,
            )

    def test_deep_requires_every_applicable_expensive_feature(self) -> None:
        binding = adoption_binding(
            workload_profile(
                activity="literature",
                audience="expert",
                computation_role="load_bearing",
                stages=2,
                candidates=2,
                internal_edges=1,
                atomic=True,
                source=True,
                convention=True,
                quantifier=True,
                terminology=True,
            )
        )
        profile = build_execution_profile(
            reasoning_mode="deep",
            reasoning_mode_event_id="modeevt-" + "a" * 64,
            adoption_binding=binding,
        )
        self.assertEqual(
            set(profile["exploration_features"]),
            set(EXPLORATION_FEATURES),
        )
        self.assertTrue(
            all(
                decision["status"] == "required"
                for decision in profile["exploration_features"].values()
            )
        )

    def test_fast_never_relaxes_truth_relevant_gates(self) -> None:
        binding = adoption_binding(
            workload_profile(
                activity="literature",
                audience="expert",
                computation_role="load_bearing",
                stages=2,
                candidates=2,
                internal_edges=1,
                atomic=True,
                source=True,
                convention=True,
                quantifier=True,
                terminology=True,
            )
        )
        event_id = "modeevt-" + "b" * 64
        profile = build_execution_profile(
            reasoning_mode="fast",
            reasoning_mode_event_id=event_id,
            adoption_binding=binding,
        )
        self.assertFalse(profile["mode_may_override_adoption_or_truth_gates"])
        self.assertEqual(
            profile["blocking_state"],
            "candidate_only_until_gate_satisfied",
        )
        self.assertEqual(
            {item["feature"] for item in profile["nonnegotiable_admission_obligations"]},
            {
                "experiment_checkpoint",
                "artifact_replay",
                "atomic_fact_bundle",
                "source_claim_gate",
                "convention_gate",
                "quantifier_gate",
            },
        )
        bound = {
            "reasoning_mode": "fast",
            "reasoning_mode_event_id": event_id,
            "reasoning_mode_policy_sha256": MODE_POLICY_SHA256,
            "fact_admission_contract_sha256": FACT_ADMISSION_CONTRACT_SHA256,
            "execution_profile": profile,
        }
        validate_mode_binding_fields(bound, adoption_binding=binding)
        tampered = deepcopy(bound)
        tampered["fact_admission_contract_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "admission contract"):
            validate_mode_binding_fields(tampered, adoption_binding=binding)

        for mode in ("auto", "deep"):
            with self.subTest(mode=mode):
                other = build_execution_profile(
                    reasoning_mode=mode,
                    reasoning_mode_event_id="modeevt-" + mode[0] * 64,
                    adoption_binding=binding,
                )
                self.assertEqual(
                    other["blocking_state"],
                    "candidate_only_until_gate_satisfied",
                )
                self.assertEqual(
                    other["nonnegotiable_admission_obligations"],
                    profile["nonnegotiable_admission_obligations"],
                )

    def test_work_unit_abort_blocks_research_mutations_not_read_only_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = MathGraphStore(root)
            store.initialize(
                project_id="abort-boundary",
                title="Abort boundary",
                workflow_evidence_version=4,
                reasoning_mode="auto",
            )
            memory_id = store.memory_add(
                {"kind": "direction", "claim": "A frozen unit to abort."},
                actor="main",
            )
            planned = create_round(
                store,
                workers=1,
                memory_ids=[memory_id],
                host_task_scope_id="unified-abort-test",
            )
            assignment = planned["assignments"][0]
            card = json.loads(
                Path(assignment["task_card_path"]).read_text(encoding="utf-8")
            )
            optional_commitment = (
                store.collaboration().make_wave1_commitment(
                    round_id=planned["round_id"],
                    assignment_id=assignment["assignment_id"],
                    criticality="optional",
                )
            )
            pulse = store.collaboration().create_plan(
                wave1_commitments=[optional_commitment],
                minimum_wave1_contributors=1,
            )
            store.reasoning_modes().abort_work_unit(
                round_id=planned["round_id"],
                actor="main",
                reason="Exercise managed continuation blocking.",
            )
            self.assertTrue(store.reasoning_modes().status()["initialized"])
            with self.assertRaisesRegex(ValueError, "explicitly aborted"):
                validate_return(
                    store,
                    planned["round_id"],
                    assignment["assignment_id"],
                )
            with self.assertRaisesRegex(ValueError, "explicitly aborted"):
                store.experiments().start(task_card=card, manifest={})
            experiment_calls = (
                lambda: store.experiments().observe(
                    task_card=card,
                    payload={},
                    actor_role="main",
                ),
                lambda: store.experiments().decision(
                    task_card=card,
                    payload={},
                    actor_role="main",
                ),
                lambda: store.experiments().event(
                    task_card=card,
                    experiment_id="experiment-" + "a" * 16,
                    payload={},
                ),
                lambda: store.experiments().resume(
                    task_card=card,
                    experiment_id="experiment-" + "a" * 16,
                    checkpoint_event_id="checkpoint",
                    current_compatibility={},
                ),
                lambda: store.experiments().finalize(
                    task_card=card,
                    experiment_id="experiment-" + "a" * 16,
                    selected_paths=["result.txt"],
                ),
            )
            for call in experiment_calls:
                with self.assertRaisesRegex(ValueError, "explicitly aborted"):
                    call()

            commitment = store.collaboration().make_wave1_commitment(
                round_id=planned["round_id"],
                assignment_id=assignment["assignment_id"],
            )
            with self.assertRaisesRegex(ValueError, "explicitly aborted"):
                store.collaboration().create_plan(
                    wave1_commitments=[commitment],
                    minimum_wave1_contributors=1,
                )
            pulse_calls = (
                lambda: store.collaboration().record_core_ingest_failure(
                    round_id=planned["round_id"],
                    assignment_id=assignment["assignment_id"],
                    return_sha256="1" * 64,
                    worker_final_sha256="2" * 64,
                    error_class="fixture",
                    error_message="fixture",
                ),
                lambda: store.collaboration().void_optional(
                    pulse["pulse_id"],
                    optional_commitment["commitment_id"],
                    reason="fixture",
                ),
                lambda: store.collaboration().record_host_dispatch(
                    pulse["pulse_id"],
                    optional_commitment["commitment_id"],
                    issuer="fixture",
                    host_context_id="fixture",
                ),
                lambda: store.collaboration().derive_barrier(
                    pulse["pulse_id"],
                    after_snapshot_id="bbs-" + "1" * 64,
                    review_commitments=[],
                ),
                lambda: store.collaboration().derive_closure(
                    pulse["pulse_id"],
                ),
            )
            for call in pulse_calls:
                with self.assertRaisesRegex(ValueError, "explicitly aborted"):
                    call()
            cleanup = store.collaboration().abort(
                pulse["pulse_id"],
                failure_phase="work_unit_abort_cleanup",
                reason="Close the now-aborted pulse without continuing work.",
            )
            self.assertTrue(cleanup["abort_id"].startswith("bbabort-"))


class UnifiedLearningPlaneTests(unittest.TestCase):
    def test_learning_graph_writes_do_not_pollute_research_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = MathGraphStore(root)
            store.initialize(
                project_id="learning-isolation",
                title="Learning isolation",
                workflow_evidence_version=4,
            )
            before_ids = store.fact_ids()
            before_audit = store.audit()

            graph = learning_graph.empty_learning_graph()
            content = {
                "pedagogy_kind": "proof-discussion",
                "title": "A teaching-only objection",
                "summary": "Ask whether the inference reverses an implication.",
                "source_locator": None,
                "anchor_node_hashes": [],
            }
            node_hash = learning_graph.canonical_sha256(content)
            graph["nodes"][node_hash] = {
                "node_hash": node_hash,
                "identity_kind": "pedagogical_content_sha256",
                "anchor_kind": "pedagogical",
                "pedagogical_content": content,
                "source_fact_ids": [],
                "source_object_ids": [],
                "source_refs": [],
                "statement_preview": content["title"],
                "truth_status": "pedagogical-not-a-fact",
                "created_at": learning_graph.utc_now(),
                "learning": learning_graph.learning_state(),
            }
            learning_graph.rebuild_indexes(graph)
            sealed = learning_graph.seal_graph(graph)
            self.assertEqual([], learning_graph.verify_graph(sealed))
            learning_path = root / "learning" / "graph.json"
            learning_graph.atomic_write_json(
                learning_path,
                sealed,
                refuse_exists=True,
            )

            after_audit = store.audit()
            self.assertEqual(store.fact_ids(), before_ids)
            self.assertEqual(after_audit.facts, before_audit.facts)
            self.assertEqual(after_audit.errors, before_audit.errors)
            self.assertEqual(
                learning_graph.load_learning_graph(learning_path)["nodes"][node_hash][
                    "truth_status"
                ],
                "pedagogical-not-a-fact",
            )

    def test_legacy_grill_overlay_is_renamed_without_runtime_inheritance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy-learning.json"
            graph = learning_graph.empty_learning_graph()
            graph["graph_family"] = "danus-compatible-learning-overlay"
            graph["interop_policy"] = {
                "protocol": "danus-chalk-readonly-snapshot-mount-v1",
                "runtime_owner": "grill-me",
                "native_graph_family": "danus",
                "allowed_foreign_sources": [
                    "chalk-paper-snapshot",
                    "chalk-blackboard-snapshot",
                ],
                "source_requirements": "immutable manifest-bound local snapshot",
                "truth_inheritance": "forbidden",
                "writeback": "forbidden",
                "research_runtime_invocation": "forbidden",
                "pedagogy_review_level": "lightweight-learning-overlay-only",
            }
            learning_graph.atomic_write_json(
                path,
                learning_graph.seal_graph(graph),
                refuse_exists=True,
            )
            migrated = learning_graph.load_learning_graph(path)
            self.assertEqual(
                migrated["graph_family"],
                "mathgraph-unified-nontruth-learning-plane",
            )
            self.assertEqual(
                migrated["interop_policy"]["runtime_owner"],
                "none-static-consumer",
            )
            self.assertEqual([], learning_graph.verify_graph(migrated))


if __name__ == "__main__":
    unittest.main()
