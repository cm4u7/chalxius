from __future__ import annotations

import ast
import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import architecture_reconnaissance as reconnaissance
import chx_ledger
from mathgraph.release_contracts import (
    ARCHITECTURE_RECONNAISSANCE_REVISION,
    CAPABILITY_TOPOLOGY_REGISTRY_REVISION,
    RELEASE_VALIDATION_MATRIX_REVISION,
    REPOSITORY_RELEASE_METADATA_REVISION,
    validate_release_audit_revision_bindings,
)


class ArchitectureReconnaissanceTests(unittest.TestCase):
    def test_quiet_strict_failure_emits_bounded_diagnostic(self):
        root = Path(reconnaissance.__file__).resolve().parents[1]
        report = {
            "errors": ["missing_modules:candidate_identity"],
            "warnings": ["unclassified_orphan_modules"],
            "inventory_sha256": "a" * 64,
        }
        stderr = io.StringIO()
        with mock.patch.object(
            reconnaissance, "inventory", return_value=report
        ), contextlib.redirect_stderr(stderr):
            returncode = reconnaissance.main(
                ["--root", str(root), "--quiet", "--strict"]
            )
        self.assertEqual(returncode, 1)
        self.assertEqual(
            json.loads(stderr.getvalue()),
            {
                "errors": ["missing_modules:candidate_identity"],
                "warnings": ["unclassified_orphan_modules"],
                "inventory_sha256": "a" * 64,
                "truth_effect": "none",
            },
        )

    def test_release_revision_bindings_have_one_source_of_truth(self):
        root = Path(reconnaissance.__file__).resolve().parents[1]
        expected = validate_release_audit_revision_bindings(root)
        self.assertEqual(
            reconnaissance.RECONNAISSANCE_REVISION,
            ARCHITECTURE_RECONNAISSANCE_REVISION,
        )
        self.assertEqual(
            chx_ledger.ARCHITECTURE_RECONNAISSANCE_CONTRACT_REVISION,
            ARCHITECTURE_RECONNAISSANCE_REVISION,
        )
        self.assertEqual(
            reconnaissance.CAPABILITY_REGISTRY_REVISION,
            CAPABILITY_TOPOLOGY_REGISTRY_REVISION,
        )
        self.assertEqual(
            expected["registry_contract_revision"],
            CAPABILITY_TOPOLOGY_REGISTRY_REVISION,
        )

    def test_release_revision_binding_rejects_each_drifted_owner(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            references = root / "references"
            references.mkdir()
            lock_path = root / "INHERITANCE.lock.json"
            registry_path = references / "capability_topology_registry.json"
            lock = {
                "release_audit": {
                    "architecture_reconnaissance_revision": (
                        ARCHITECTURE_RECONNAISSANCE_REVISION
                    ),
                    "capability_registry_revision": (
                        CAPABILITY_TOPOLOGY_REGISTRY_REVISION
                    ),
                    "coordinator_contract_revision": (
                        RELEASE_VALIDATION_MATRIX_REVISION
                    ),
                    "repository_release_metadata_revision": (
                        REPOSITORY_RELEASE_METADATA_REVISION
                    ),
                }
            }
            registry = {
                "contract_revision": CAPABILITY_TOPOLOGY_REGISTRY_REVISION
            }
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            validate_release_audit_revision_bindings(root)
            mutations = (
                ("architecture_reconnaissance_revision", "stale-recon"),
                ("capability_registry_revision", "stale-registry-lock"),
                ("coordinator_contract_revision", "stale-coordinator"),
                (
                    "repository_release_metadata_revision",
                    "stale-repository-metadata",
                ),
            )
            for key, value in mutations:
                with self.subTest(key=key):
                    mutated = deepcopy(lock)
                    mutated["release_audit"][key] = value
                    lock_path.write_text(json.dumps(mutated), encoding="utf-8")
                    with self.assertRaisesRegex(
                        ValueError, "release audit revision binding mismatch"
                    ):
                        validate_release_audit_revision_bindings(root)
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            registry_path.write_text(
                json.dumps({"contract_revision": "stale-registry-file"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError, "release audit revision binding mismatch"
            ):
                validate_release_audit_revision_bindings(root)

    def _fixture(self, root: Path):
        scripts = root / "scripts"
        references = root / "references"
        tests = root / "tests"
        scripts.mkdir(parents=True)
        references.mkdir()
        tests.mkdir()
        (scripts / "owner.py").write_text(
            "VALUE = 1\n\n"
            "def main():\n"
            "    return VALUE\n\n"
            "if __name__ == '__main__':\n"
            "    raise SystemExit(main())\n",
            encoding="utf-8",
        )
        launcher = scripts / "tool"
        launcher.write_text(
            "#!/bin/sh\nexec python3 owner.py \"$@\"\n", encoding="utf-8"
        )
        launcher.chmod(0o755)
        (references / "contract.md").write_text("contract\n", encoding="utf-8")
        (tests / "test_anchor.py").write_text("pass\n", encoding="utf-8")
        registry = {
            "schema_version": 3,
            "contract_revision": reconnaissance.CAPABILITY_REGISTRY_REVISION,
            "truth_effect": "none",
            "capabilities": {
                "cap.test": {
                    "summary": "One isolated test capability.",
                    "status": "active",
                    "authority_effects": ["none"],
                    "stateful": True,
                    "state_roots": [{
                        "path": "state",
                        "owner_module": "owner",
                        "relationship": "canonical",
                    }],
                    "documents": ["references/contract.md"],
                    "tests": ["tests/test_anchor.py"],
                    "activation_paths": [
                        {"kind": "cli", "command": "mgraph:do"}
                    ],
                }
            },
            "modules": {
                "owner": {
                    "capability_id": "cap.test",
                    "path": "scripts/owner.py",
                    "roles": ["entrypoint", "state_owner"],
                    "standalone_entry_symbols": ["owner.main"],
                    "standalone_reason": "Isolated fixture entrypoint.",
                }
            },
            "commands": {
                "mgraph:do": {
                    "capability_id": "cap.test",
                    "status": "canonical",
                    "authority_effects": ["none"],
                }
            },
            "compatibility_aliases": {},
            "launchers": {
                "scripts/tool": {
                    "capability_id": "cap.test",
                    "target_module": "owner",
                    "target_path": "scripts/owner.py",
                }
            },
        }
        modules = {
            "owner": {
                "path": "scripts/owner.py",
                "incoming_modules": [],
                "production_incoming_modules": [],
                "literal_state_roots": [{
                    "attribute": "state_dir",
                    "path": "state",
                    "expression": "self.root / 'state'",
                    "line": 1,
                }],
                "functions": [{"qualname": "main"}],
            }
        }
        return registry, modules

    @staticmethod
    def _write_registry(root: Path, registry) -> None:
        (root / "references" / "capability_topology_registry.json").write_text(
            json.dumps(registry, indent=2) + "\n", encoding="utf-8"
        )

    @staticmethod
    def _write_behavioral_registry(root: Path, registry) -> None:
        (root / "references" / "behavioral_feature_registry.json").write_text(
            json.dumps(registry, indent=2) + "\n", encoding="utf-8"
        )

    def _behavioral_fixture(self, root: Path):
        scripts = root / "scripts"
        references = root / "references"
        tests = root / "tests"
        scripts.mkdir(parents=True)
        references.mkdir()
        tests.mkdir()
        (scripts / "helper.py").write_text(
            "VALUE = 'imported but not called'\n",
            encoding="utf-8",
        )
        (scripts / "flow.py").write_text(
            "def produce():\n"
            "    return {'type_id': 'flow-handoff-1'}\n\n"
            "def validate_handoff(value):\n"
            "    return value.get('type_id') == 'flow-handoff-1'\n\n"
            "def entry():\n"
            "    return produce()\n\n"
            "def consume(value):\n"
            "    return validate_handoff(value)\n",
            encoding="utf-8",
        )
        (tests / "test_flow.py").write_text(
            "import unittest\n"
            "from flow import produce\n\n"
            "class FlowTests(unittest.TestCase):\n"
            "    def test_positive(self):\n"
            "        self.assertEqual(produce()['type_id'], 'flow-handoff-1')\n\n"
            "    def test_predicate_false(self):\n"
            "        self.assertFalse(False)\n\n"
            "    def test_tamper(self):\n"
            "        self.assertNotEqual({}, {'type_id': 'flow-handoff-1'})\n",
            encoding="utf-8",
        )
        registry = {
            "schema_version": 1,
            "contract_revision": reconnaissance.BEHAVIORAL_REGISTRY_REVISION,
            "truth_effect": "none",
            "features": {
                "feature.flow": {
                    "classification": "normal_flow",
                    "lifecycle_decision": "retain_and_integrate",
                    "required": True,
                    "summary": "Fixture normal flow.",
                    "production_entry_symbol": "flow.entry",
                    "producer_symbol": "flow.produce",
                    "activation_predicate": {
                        "predicate_id": "flow_enabled",
                        "domain": ["enabled", "disabled"],
                        "conditional": True,
                    },
                    "typed_handoff": {
                        "type_id": "flow-handoff-1",
                        "validator_symbol": "flow.validate_handoff",
                    },
                    "consumer_symbol": "flow.consume",
                    "observable_effect": {
                        "effect_id": "flow_result_visible",
                        "kind": "bounded_output",
                        "description": "The fixture result is visible.",
                    },
                    "probes": {
                        "positive": "tests.test_flow.FlowTests.test_positive",
                        "predicate_false": (
                            "tests.test_flow.FlowTests.test_predicate_false"
                        ),
                        "tamper": "tests.test_flow.FlowTests.test_tamper",
                    },
                },
                "feature.manual": {
                    "classification": "explicit_manual",
                    "lifecycle_decision": "retain_bounded",
                    "replacement_feature_id": "",
                    "required": False,
                    "summary": "Fixture manual boundary.",
                    "boundary_reason": "Only a caller can opt into it.",
                    "guard_symbol": "flow.entry",
                    "boundary_probe": "tests.test_flow.FlowTests.test_predicate_false",
                },
            },
        }
        self._write_behavioral_registry(root, registry)
        return registry

    def _run_behavioral(
        self,
        root: Path,
        *,
        excluded_modules=None,
        capability_activation_symbols=(),
    ):
        modules, parse_errors = reconnaissance._parse_modules(root)
        self.assertEqual(parse_errors, [])
        ast_index = reconnaissance._behavioral_ast_index(
            root,
            module_records=modules,
            excluded_modules=set(excluded_modules or ()),
        )
        probe_index = reconnaissance._behavioral_probe_symbols(root)
        return reconnaissance._behavioral_feature_registry(
            root,
            ast_index=ast_index,
            probe_index=probe_index,
            capability_activation_symbols=capability_activation_symbols,
        )

    def _run(self, root, registry, modules, commands=None, launchers=None):
        self._write_registry(root, registry)
        return reconnaissance._capability_registry(
            root,
            module_records=modules,
            command_names={"mgraph:do"} if commands is None else commands,
            production_unreferenced_modules=set(modules),
            launcher_paths={"scripts/tool"} if launchers is None else launchers,
        )

    def test_valid_registry_and_duplicate_key_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry, modules = self._fixture(root)
            report = self._run(root, registry, modules)
            self.assertTrue(report["ok"], report["errors"])
            path = root / "references" / "capability_topology_registry.json"
            path.write_text(
                '{"schema_version":2,"schema_version":2}\n', encoding="utf-8"
            )
            report = reconnaissance._capability_registry(
                root,
                module_records=modules,
                command_names={"mgraph:do"},
                production_unreferenced_modules={"owner"},
                launcher_paths={"scripts/tool"},
            )
            self.assertIn("registry_json:ValueError", report["errors"])

    def test_duplicate_body_adjudication_is_exact_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            references = root / "references"
            references.mkdir()
            digest = "a" * 64
            duplicates = [
                {
                    "body_sha256": digest,
                    "definitions": [
                        {
                            "module": "first",
                            "path": "scripts/first.py",
                            "name": "helper",
                            "qualname": "Owner.helper",
                            "line": 10,
                        },
                        {
                            "module": "second",
                            "path": "scripts/second.py",
                            "name": "helper",
                            "qualname": "helper",
                            "line": 20,
                        },
                    ],
                }
            ]
            registry = {
                "schema_version": 1,
                "contract_revision": reconnaissance.DUPLICATE_ADJUDICATION_REVISION,
                "truth_effect": "none",
                "groups": {
                    digest: {
                        "decision": "retain_local",
                        "category": "package_local_stateless",
                        "authoritative_owner": "",
                        "definitions": [
                            "first:Owner.helper",
                            "second:helper",
                        ],
                        "reason": "One reviewed local helper boundary.",
                    }
                },
            }
            path = references / "duplicate_body_adjudication.json"
            path.write_text(json.dumps(registry), encoding="utf-8")
            report = reconnaissance._duplicate_body_adjudication(
                root, duplicates
            )
            self.assertTrue(report["ok"], report["errors"])

            registry["groups"][digest]["decision"] = (
                "replace_with_authoritative_mechanism"
            )
            path.write_text(json.dumps(registry), encoding="utf-8")
            report = reconnaissance._duplicate_body_adjudication(
                root, duplicates
            )
            self.assertIn(
                f"unresolved_decision:{digest}", report["errors"]
            )

            registry["groups"].pop(digest)
            path.write_text(json.dumps(registry), encoding="utf-8")
            report = reconnaissance._duplicate_body_adjudication(
                root, duplicates
            )
            self.assertIn(f"unadjudicated:{digest}", report["errors"])

    def test_malformed_and_missing_registry_surfaces_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry, modules = self._fixture(root)
            malformed_cases = (
                ("capabilities", [], "capabilities_not_object"),
                ("modules", [], "modules_not_object"),
                ("commands", [], "commands_not_object"),
                ("compatibility_aliases", [], "compatibility_aliases_not_object"),
                ("launchers", [], "launchers_not_object"),
            )
            for field, value, expected in malformed_cases:
                with self.subTest(field=field):
                    candidate = deepcopy(registry)
                    candidate[field] = value
                    report = self._run(root, candidate, modules)
                    self.assertIn(expected, report["errors"])

            missing_cases = (
                ("module", "modules", "owner", "missing_modules:owner"),
                ("command", "commands", "mgraph:do", "missing_commands:mgraph:do"),
                ("launcher", "launchers", "scripts/tool", "missing_launchers:scripts/tool"),
            )
            for label, field, key, expected in missing_cases:
                with self.subTest(label=label):
                    candidate = deepcopy(registry)
                    candidate[field].pop(key)
                    report = self._run(root, candidate, modules)
                    self.assertIn(expected, report["errors"])

            for field, expected in (
                ("activation_paths", "capability_activation_paths:cap.test"),
                ("state_roots", "capability_state_roots_empty:cap.test"),
            ):
                candidate = deepcopy(registry)
                candidate["capabilities"]["cap.test"][field] = []
                report = self._run(root, candidate, modules)
                self.assertIn(expected, report["errors"])

            missing_alias = deepcopy(registry)
            missing_alias["commands"]["mgraph:legacy"] = {
                "capability_id": "cap.test",
                "status": "compatibility_surface",
                "authority_effects": ["none"],
            }
            report = self._run(
                root,
                missing_alias,
                modules,
                commands={"mgraph:do", "mgraph:legacy"},
            )
            self.assertIn("compatibility_alias_set", report["errors"])

    def test_candidate_and_verifier_cannot_be_declared_as_fact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry, modules = self._fixture(root)
            for command in ("mgraph:candidate-release", "mgraph:verifier-capsule"):
                with self.subTest(command=command):
                    candidate = deepcopy(registry)
                    candidate["commands"] = {
                        command: {
                            "capability_id": "cap.test",
                            "status": "canonical",
                            "authority_effects": ["fact"],
                        }
                    }
                    candidate["capabilities"]["cap.test"]["authority_effects"] = [
                        "fact", "none"
                    ]
                    candidate["capabilities"]["cap.test"]["activation_paths"] = [
                        {"kind": "cli", "command": command}
                    ]
                    report = self._run(root, candidate, modules, commands={command})
                    self.assertIn(
                        f"critical_command_authority:{command}", report["errors"]
                    )

            alias = deepcopy(registry)
            alias["capabilities"]["cap.test"]["authority_effects"] = [
                "none", "source"
            ]
            alias["commands"]["mgraph:legacy"] = {
                "capability_id": "cap.test",
                "status": "exact_alias",
                "authority_effects": ["source"],
            }
            alias["compatibility_aliases"]["mgraph:legacy"] = {
                "canonical_command": "mgraph:do",
                "relation": "exact_alias",
                "reason": "Fixture alias.",
            }
            report = self._run(
                root, alias, modules, commands={"mgraph:do", "mgraph:legacy"}
            )
            self.assertIn(
                "compatibility_alias_authority:mgraph:legacy", report["errors"]
            )

    def test_relative_import_and_production_edge_semantics(self) -> None:
        node = ast.parse("from .model import Item\n").body[0]
        self.assertEqual(
            reconnaissance._resolve_import("mathgraph", node, is_package=True),
            ["mathgraph.model"],
        )
        self.assertEqual(
            reconnaissance._resolve_import("mathgraph.cli", node, is_package=False),
            ["mathgraph.model"],
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            scripts.mkdir()
            sources = {
                "feature.py": "VALUE = 1\n",
                "audit_only.py": "VALUE = 2\n",
                "architecture_reconnaissance.py": "import feature\n",
                "runtime.py": "import feature\n",
                "self_test.py": "import audit_only\n",
            }
            for name, body in sources.items():
                (scripts / name).write_text(body, encoding="utf-8")
            records, errors = reconnaissance._parse_modules(root)
            self.assertEqual(errors, [])
            self.assertEqual(
                records["feature"]["incoming_modules"],
                ["architecture_reconnaissance", "runtime"],
            )
            self.assertEqual(
                records["feature"]["production_incoming_modules"], ["runtime"]
            )
            self.assertEqual(
                records["audit_only"]["production_incoming_modules"], []
            )

    def test_literal_state_root_and_current_authority_contract(self) -> None:
        tree = ast.parse(
            "class Owner:\n"
            "    def __init__(self, store):\n"
            "        self.root = store.root / 'governance' / 'v5'\n"
            "        self.admissions_dir = store.fact_graph_dir / 'v5_admissions' / 'by-release'\n"
        )
        visitor = reconnaissance.ModuleVisitor("mathgraph.v5_lifecycle")
        visitor.visit(tree)
        self.assertEqual(
            sorted(item["path"] for item in visitor.literal_state_roots),
            ["fact_graph/v5_admissions/by-release", "governance/v5"],
        )
        registry_path = (
            Path(__file__).resolve().parents[1]
            / "references"
            / "capability_topology_registry.json"
        )
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        required = {
            "mgraph:candidate-release": ["candidate"],
            "mgraph:verifier-capsule": ["none"],
            "mgraph:certification-record": ["certification"],
            "mgraph:fact-admit": ["fact"],
        }
        self.assertEqual(registry["schema_version"], 3)
        for command, effects in required.items():
            self.assertEqual(registry["commands"][command]["authority_effects"], effects)

    def test_behavioral_registry_requires_real_direct_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = self._behavioral_fixture(root)
            report = self._run_behavioral(root)
            self.assertTrue(report["ok"], report["errors"])
            self.assertEqual(report["behavioral_orphan_features"], [])
            self.assertEqual(report["counts"]["normal_flow"], 1)
            self.assertEqual(report["counts"]["explicit_manual"], 1)
            self.assertEqual(
                report["lifecycle_dispositions"]["retain_and_integrate"],
                ["feature.flow"],
            )
            self.assertEqual(
                report["lifecycle_dispositions"]["retain_bounded"],
                ["feature.manual"],
            )

            (root / "scripts" / "flow.py").write_text(
                "from helper import VALUE as imported_marker\n\n"
                "def produce():\n"
                "    return {'type_id': 'flow-handoff-1'}\n\n"
                "def validate_handoff(value):\n"
                "    return value.get('type_id') == 'flow-handoff-1'\n\n"
                "def entry():\n"
                "    marker = 'produce'\n"
                "    return marker\n\n"
                "def consume(value):\n"
                "    return validate_handoff(value)\n",
                encoding="utf-8",
            )
            report = self._run_behavioral(root)
            errors = report["errors"]
            self.assertIn(
                "entry_producer_call_missing",
                {error["code"] for error in errors},
            )
            self.assertIn("feature.flow", report["behavioral_orphan_features"])
            missing_edge = next(
                error
                for error in errors
                if error["code"] == "entry_producer_call_missing"
            )
            self.assertEqual(missing_edge["caller"], "flow.entry")
            self.assertEqual(missing_edge["callee"], "flow.produce")

            (root / "scripts" / "flow.py").write_text(
                "def produce():\n"
                "    return {'type_id': 'flow-handoff-1'}\n\n"
                "def validate_handoff(value):\n"
                "    return value.get('type_id') == 'flow-handoff-1'\n\n"
                "def entry(external):\n"
                "    return external.produce()\n\n"
                "def consume(value):\n"
                "    return validate_handoff(value)\n",
                encoding="utf-8",
            )
            report = self._run_behavioral(root)
            self.assertIn(
                "entry_producer_call_missing",
                {error["code"] for error in report["errors"]},
            )

            (root / "scripts" / "flow.py").write_text(
                "def produce():\n"
                "    return {'type_id': 'flow-handoff-1'}\n\n"
                "def validate_handoff(value):\n"
                "    return value.get('type_id') == 'flow-handoff-1'\n\n"
                "def entry():\n"
                "    return produce()\n\n"
                "def consume(value):\n"
                "    return value\n",
                encoding="utf-8",
            )
            report = self._run_behavioral(root)
            self.assertIn(
                "consumer_validator_call_missing",
                {error["code"] for error in report["errors"]},
            )

            registry["features"]["feature.flow"]["activation_predicate"][
                "domain"
            ] = ["enabled"]
            self._write_behavioral_registry(root, registry)
            report = self._run_behavioral(root)
            self.assertIn(
                "conditional_predicate_needs_true_false_domain",
                {error["code"] for error in report["errors"]},
            )

    def test_behavioral_registry_requires_real_probes_and_production_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = self._behavioral_fixture(root)
            registry["features"]["feature.flow"]["probes"]["tamper"] = (
                "tests.test_flow.FlowTests.test_missing_tamper"
            )
            self._write_behavioral_registry(root, registry)
            report = self._run_behavioral(root)
            missing = [
                error
                for error in report["errors"]
                if error["code"] == "probe_missing"
            ]
            self.assertEqual(len(missing), 1)
            self.assertEqual(missing[0]["probe_kind"], "tamper")
            self.assertEqual(missing[0]["feature_id"], "feature.flow")

            registry["features"]["feature.flow"]["probes"]["tamper"] = (
                "tests.test_flow.FlowTests.test_tamper"
            )
            self._write_behavioral_registry(root, registry)
            report = self._run_behavioral(root, excluded_modules={"flow"})
            codes = {error["code"] for error in report["errors"]}
            self.assertIn("production_entry_symbol_missing", codes)
            self.assertIn("producer_symbol_missing", codes)
            self.assertIn("consumer_symbol_missing", codes)
            self.assertIn("validator_symbol_missing", codes)

    def test_unregistered_public_state_method_is_not_invisible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._behavioral_fixture(root)
            flow_path = root / "scripts" / "flow.py"
            flow_path.write_text(
                flow_path.read_text(encoding="utf-8")
                + "\n\nclass HiddenWriter:\n"
                + "    def _commit(self, path):\n"
                + "        path.write_text('state', encoding='utf-8')\n\n"
                + "    def orphan_write(self, path):\n"
                + "        return self._commit(path)\n\n"
                + "class UnrelatedReceiver:\n"
                + "    def invoke_same_basename(self, external):\n"
                + "        return external.orphan_write()\n",
                encoding="utf-8",
            )
            report = self._run_behavioral(root)
            self.assertIn(
                "flow.HiddenWriter.orphan_write",
                report["unregistered_public_state_symbols"],
            )
            errors = [
                error
                for error in report["errors"]
                if error["code"] == "unregistered_public_state_symbol"
            ]
            self.assertEqual(
                [error["symbol"] for error in errors],
                ["flow.HiddenWriter.orphan_write"],
            )

    def test_writer_detection_is_owner_and_flag_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._behavioral_fixture(root)
            flow_path = root / "scripts" / "flow.py"
            flow_path.write_text(
                flow_path.read_text(encoding="utf-8")
                + "\n\nimport os\n"
                + "from pathlib import Path\n\n"
                + "def string_replace(value):\n"
                + "    return value.replace('old', 'new')\n\n"
                + "def path_replace(source: Path, target: Path):\n"
                + "    return source.replace(target)\n\n"
                + "def readonly_open(path):\n"
                + "    descriptor = os.open(path, os.O_RDONLY)\n"
                + "    os.close(descriptor)\n\n"
                + "def writable_open(path):\n"
                + "    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT)\n"
                + "    os.close(descriptor)\n",
                encoding="utf-8",
            )
            modules, parse_errors = reconnaissance._parse_modules(root)
            self.assertEqual(parse_errors, [])
            index = reconnaissance._behavioral_ast_index(
                root,
                module_records=modules,
                excluded_modules=set(),
            )
            stateful = set(index["public_stateful_symbols"])
            self.assertNotIn("flow.string_replace", stateful)
            self.assertNotIn("flow.readonly_open", stateful)
            self.assertIn("flow.path_replace", stateful)
            self.assertIn("flow.writable_open", stateful)
            self.assertEqual(index["uncertain_state_write_receivers"], {})

    def test_argparse_callback_and_typed_factory_edges_activate_exact_writers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._behavioral_fixture(root)
            flow_path = root / "scripts" / "flow.py"
            flow_path.write_text(
                flow_path.read_text(encoding="utf-8")
                + "\n\nimport argparse\n\n"
                + "class FirstWriter:\n"
                + "    def persist(self, path):\n"
                + "        path.write_text('first', encoding='utf-8')\n\n"
                + "class SecondWriter:\n"
                + "    def persist(self, path):\n"
                + "        path.write_text('second', encoding='utf-8')\n\n"
                + "class WriterFactory:\n"
                + "    def writer(self) -> FirstWriter | SecondWriter:\n"
                + "        return FirstWriter()\n\n"
                + "def cli_handler(path):\n"
                + "    return WriterFactory().writer().persist(path)\n\n"
                + "def parser():\n"
                + "    value = argparse.ArgumentParser()\n"
                + "    value.set_defaults(func=cli_handler)\n"
                + "    return value\n\n"
                + "def cli_main():\n"
                + "    args = parser().parse_args([])\n"
                + "    return args.func(args.path)\n\n"
                + "def callback_writer(path):\n"
                + "    path.write_text('callback', encoding='utf-8')\n\n"
                + "def callback_entry(path, callback=callback_writer):\n"
                + "    return callback(path)\n",
                encoding="utf-8",
            )
            report = self._run_behavioral(
                root,
                capability_activation_symbols={
                    "flow.cli_main",
                    "flow.callback_entry",
                },
            )
            self.assertEqual(
                report["unregistered_public_state_symbols"],
                [],
                report["errors"],
            )

    def test_standalone_entry_symbol_must_be_executed_by_module(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry, modules = self._fixture(root)
            registry["modules"]["owner"]["standalone_entry_symbols"] = [
                "owner.missing"
            ]
            report = self._run(root, registry, modules)
            self.assertIn(
                "module_standalone_entry_symbol_missing:owner:owner.missing",
                report["errors"],
            )

    def test_behavioral_orphans_require_an_explicit_lifecycle_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = self._behavioral_fixture(root)
            clean_registry = deepcopy(registry)
            registry["features"]["feature.flow"]["lifecycle_decision"] = "retire"
            registry["features"]["feature.manual"]["lifecycle_decision"] = (
                "replace_with_authoritative_mechanism"
            )
            registry["features"]["feature.manual"]["replacement_feature_id"] = (
                "feature.missing"
            )
            self._write_behavioral_registry(root, registry)
            report = self._run_behavioral(root)
            codes = {error["code"] for error in report["errors"]}
            self.assertIn("normal_flow_lifecycle_decision", codes)
            self.assertIn("replacement_feature_target", codes)
            self.assertIn("bounded_feature_disposition", codes)

            registry = clean_registry
            registry["features"]["feature.manual"].pop("boundary_probe")
            self._write_behavioral_registry(root, registry)
            report = self._run_behavioral(root)
            self.assertIn(
                "boundary_fields",
                {error["code"] for error in report["errors"]},
            )

    def test_behavioral_replacement_cycles_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = self._behavioral_fixture(root)
            dormant = {
                "classification": "dormant",
                "lifecycle_decision": "replace_with_authoritative_mechanism",
                "required": False,
                "summary": "Fixture dormant predecessor.",
                "boundary_reason": "A current owner replaces this predecessor.",
                "guard_symbol": "",
                "boundary_probe": "tests.test_flow.FlowTests.test_predicate_false",
            }
            registry["features"]["feature.old_a"] = {
                **dormant,
                "replacement_feature_id": "feature.old_b",
            }
            registry["features"]["feature.old_b"] = {
                **dormant,
                "replacement_feature_id": "feature.old_a",
            }
            self._write_behavioral_registry(root, registry)
            report = self._run_behavioral(root)
            cycles = [
                error
                for error in report["errors"]
                if error["code"] == "replacement_feature_cycle"
            ]
            self.assertEqual(
                {error["feature_id"] for error in cycles},
                {"feature.old_a", "feature.old_b"},
            )

    def test_behavioral_registry_duplicate_keys_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._behavioral_fixture(root)
            path = root / "references" / "behavioral_feature_registry.json"
            path.write_text(
                '{"schema_version":1,"schema_version":1}\n',
                encoding="utf-8",
            )
            report = self._run_behavioral(root)
            self.assertEqual(report["errors"][0]["code"], "registry_json")
            self.assertEqual(report["errors"][0]["error_type"], "ValueError")


if __name__ == "__main__":
    unittest.main()
