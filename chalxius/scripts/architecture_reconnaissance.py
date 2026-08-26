#!/usr/bin/env python3
"""Inventory Chalxius capability topology without mutating the candidate.

This is a release-architecture gate, not a truth or reliability validator.  It
connects files, Python modules, imports, CLI commands, roles, handlers, tests,
documentation, state-owner expressions, exact duplicates, and manifest state.
It complements (and never replaces) the isolated release matrix and the
mutation-based aggressive bug audit.
"""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from typing import Any, Iterable

sys.dont_write_bytecode = True

from mathgraph.release_contracts import (
    ARCHITECTURE_RECONNAISSANCE_REVISION as RECONNAISSANCE_REVISION,
    CAPABILITY_TOPOLOGY_REGISTRY_REVISION as CAPABILITY_REGISTRY_REVISION,
    validate_release_audit_revision_bindings,
)

CAPABILITY_REGISTRY_PATH = PurePosixPath(
    "references/capability_topology_registry.json"
)
BEHAVIORAL_REGISTRY_REVISION = "chalxius-behavioral-feature-registry-3"
BEHAVIORAL_REGISTRY_PATH = PurePosixPath(
    "references/behavioral_feature_registry.json"
)
DUPLICATE_ADJUDICATION_REVISION = "chalxius-duplicate-body-adjudication-1"
DUPLICATE_ADJUDICATION_PATH = PurePosixPath(
    "references/duplicate_body_adjudication.json"
)
GENERATED_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
ENTRYPOINT_MODULES = {
    "mathgraph.__main__",
    "mathgraph.cli",
}
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".py",
    "",
}
SHA256_RE = re.compile(r"[0-9a-f]{64}")
CAPABILITY_STATUSES = {
    "active",
    "advisory",
    "compatibility",
    "learner",
    "presentation",
    "release_validation",
}
AUTHORITY_EFFECTS = {
    "none",
    "source",
    "research",
    "candidate",
    "certification",
    "fact",
    "presentation",
    "runtime",
}
OBSERVATION_ONLY_MODULES = {
    "aggressive_bug_audit",
    "architecture_reconnaissance",
    "release_validation",
    "self_test",
}
# These load-bearing command boundaries are code-owned.  The registry may
# describe them, but it may not grant a verifier, preflight, Candidate Release,
# or Certification operation Fact authority by editing metadata.
CRITICAL_COMMAND_AUTHORITY_EFFECTS = {
    "mgraph:submit": {"candidate"},
    "mgraph:packet": {"none"},
    "mgraph:record-review": {"certification"},
    "mgraph:admit": {"fact"},
    "mgraph:revoke": {"fact"},
    "mgraph:candidate-release": {"candidate"},
    "mgraph:candidate-release-check": {"none"},
    "mgraph:verifier-capsule": {"none"},
    "mgraph:certification-record": {"certification"},
    "mgraph:certification-decision-check": {"none"},
    "mgraph:fact-admit": {"fact"},
    "mgraph:make-verifier-task": {"none"},
    "mgraph:fact-bundle-submit": {"candidate"},
    "mgraph:make-bundle-verifier-task": {"none"},
    "mgraph:fact-bundle-verifier-task": {"none"},
    "mgraph:fact-bundle-record-review": {"certification"},
    "mgraph:fact-bundle-admit": {"fact"},
}
MODULE_ROLES = {
    "adapter",
    "authority_gate",
    "domain_service",
    "entrypoint",
    "learner",
    "presentation",
    "release_tool",
    "state_owner",
    "validation_tool",
}
BEHAVIORAL_CLASSIFICATIONS = {
    "normal_flow",
    "explicit_manual",
    "external_api",
    "compatibility",
    "dormant",
    "deprecated",
}
BEHAVIORAL_EFFECT_KINDS = {
    "bounded_output",
    "external_side_effect",
    "routing",
    "state_transition",
    "validation_gate",
}
BEHAVIORAL_LIFECYCLE_DECISIONS = {
    "retain_and_integrate",
    "retain_bounded",
    "replace_with_authoritative_mechanism",
    "retire",
}
# State-write discovery is deliberately owner-sensitive.  A raw method suffix
# such as ``replace`` cannot distinguish ``Path.replace`` from ``str.replace``
# or ``datetime.replace`` and therefore must never grant or deny activation.
QUALIFIED_STATE_WRITE_CALLS = {
    "os.fdatasync",
    "os.fsync",
    "os.link",
    "os.makedirs",
    "os.mkdir",
    "os.rename",
    "os.replace",
    "os.rmdir",
    "os.symlink",
    "os.unlink",
    "shutil.copy2",
    "shutil.copytree",
    "shutil.move",
    "shutil.rmtree",
    "tempfile.mkdtemp",
    "tempfile.mkstemp",
}
UNAMBIGUOUS_PATH_WRITE_METHODS = {
    "chmod",
    "hardlink_to",
    "mkdir",
    "rmdir",
    "symlink_to",
    "touch",
    "unlink",
    "write_bytes",
    "write_text",
}
PATH_ONLY_AMBIGUOUS_WRITE_METHODS = {"rename", "replace"}
WRITE_OPEN_FLAG_NAMES = {
    "O_APPEND",
    "O_CREAT",
    "O_RDWR",
    "O_TRUNC",
    "O_WRONLY",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _files(root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and not path.is_symlink()
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _module_name(root: Path, path: Path) -> str | None:
    scripts = root / "scripts"
    try:
        relative = path.relative_to(scripts)
    except ValueError:
        return None
    if path.suffix != ".py":
        return None
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_import(
    current: str, node: ast.ImportFrom, *, is_package: bool
) -> list[str]:
    if node.level:
        package = current.split(".") if is_package else current.split(".")[:-1]
        if node.level > 1:
            package = package[: -(node.level - 1)]
        if node.module:
            return [".".join([*package, node.module])]
        return [".".join([*package, alias.name]) for alias in node.names]
    if node.module:
        return [node.module]
    return []


def _is_args_command(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "command"
        and isinstance(node.value, ast.Name)
        and node.value.id == "args"
    )


def _string_values(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        return {
            item.value
            for item in node.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        }
    return set()


class ModuleVisitor(ast.NodeVisitor):
    def __init__(self, module: str, *, is_package: bool = False) -> None:
        self.module = module
        self.is_package = is_package
        self.imports: set[str] = set()
        self.dynamic_imports: set[str] = set()
        self.handlers: set[str] = set()
        self.public_definitions: list[str] = []
        self.functions: list[tuple[str, str, str, int]] = []
        self.class_scope: list[str] = []
        self.state_expressions: list[dict[str, Any]] = []
        self.literal_state_roots: list[dict[str, Any]] = []

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.update(alias.name for alias in node.names)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.update(
            _resolve_import(self.module, node, is_package=self.is_package)
        )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = ""
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name in {"import_module", "__import__"} and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                raw = first.value
                if raw.startswith("."):
                    package = (
                        self.module
                        if self.is_package
                        else self.module.rsplit(".", 1)[0]
                    )
                    raw = package + raw
                self.dynamic_imports.add(raw)
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        test = node.test
        if isinstance(test, ast.Compare) and _is_args_command(test.left):
            for comparator in test.comparators:
                self.handlers.update(_string_values(comparator))
        self.generic_visit(node)

    def _definition(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if not node.name.startswith("_"):
            self.public_definitions.append(node.name)
        original_name = node.name
        node.name = "_"
        fingerprint = _sha256(
            ast.dump(node, annotate_fields=True, include_attributes=False).encode()
        )
        node.name = original_name
        qualname = ".".join([*self.class_scope, node.name])
        self.functions.append((node.name, qualname, fingerprint, node.lineno))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_scope.append(node.name)
        self.generic_visit(node)
        self.class_scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._definition(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._definition(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and target.attr.endswith(("root", "dir", "dirs", "path"))
            ):
                literals = sorted(
                    {
                        child.value
                        for child in ast.walk(node.value)
                        if isinstance(child, ast.Constant)
                        and isinstance(child.value, str)
                        and child.value
                    }
                )
                self.state_expressions.append(
                    {
                        "attribute": target.attr,
                        "expression": ast.unparse(node.value),
                        "literal_segments": literals,
                        "line": node.lineno,
                    }
                )
                if "lock" not in target.attr:
                    literal_state_path = _literal_state_path(
                        self.module, node.value
                    )
                    if literal_state_path is not None:
                        self.literal_state_roots.append(
                            {
                                "attribute": target.attr,
                                "path": literal_state_path,
                                "expression": ast.unparse(node.value),
                                "line": node.lineno,
                            }
                        )
        self.generic_visit(node)


def _division_chain(node: ast.AST) -> tuple[str, list[str]] | None:
    """Return one static ``base / 'literal' / ...`` chain, preserving order."""

    segments: list[str] = []
    current = node
    while isinstance(current, ast.BinOp) and isinstance(current.op, ast.Div):
        if not (
            isinstance(current.right, ast.Constant)
            and isinstance(current.right.value, str)
            and current.right.value
        ):
            return None
        segments.append(current.right.value)
        current = current.left
    if not segments:
        return None
    return ast.unparse(current), list(reversed(segments))


def _literal_state_path(module: str, node: ast.AST) -> str | None:
    """Resolve project-relative state roots whose base is statically known.

    Nested ``self.root`` children are covered by their owning root declaration;
    treating every ``self.root`` as the project root would fabricate paths for
    Paper, Evidence, and V5 child stores.  MathGraphStore is the sole exception:
    its ``self.root`` is the project root by contract.
    """

    chain = _division_chain(node)
    if chain is None:
        return None
    base, segments = chain
    project_bases = {
        "project_root",
        "self.project_root",
        "store.root",
        "self.store.root",
    }
    prefixes = {
        "lifecycle.root": ["governance", "v5"],
        "self.lifecycle.root": ["governance", "v5"],
        "store.fact_graph_dir": ["fact_graph"],
        "self.store.fact_graph_dir": ["fact_graph"],
        "self.fact_graph_dir": ["fact_graph"],
    }
    if module == "mathgraph.store" and base == "self.root":
        prefix: list[str] = []
    elif base in project_bases:
        prefix = []
    elif base in prefixes:
        prefix = prefixes[base]
    else:
        return None
    path = PurePosixPath(*prefix, *segments)
    if path.is_absolute() or ".." in path.parts:
        return None
    return path.as_posix()


def _parse_modules(root: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    modules: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for path in _files(root):
        module = _module_name(root, path)
        if module is None:
            continue
        relative = _relative(root, path)
        raw = path.read_bytes()
        try:
            tree = ast.parse(raw, filename=relative)
        except SyntaxError as error:
            errors.append(f"python_parse:{relative}:{error.lineno}:{error.msg}")
            continue
        visitor = ModuleVisitor(module, is_package=path.name == "__init__.py")
        visitor.visit(tree)
        modules[module] = {
            "path": relative,
            "bytes": len(raw),
            "lines": raw.count(b"\n") + (not raw.endswith(b"\n")),
            "sha256": _sha256(raw),
            "imports": sorted(visitor.imports),
            "dynamic_imports": sorted(visitor.dynamic_imports),
            "handlers": sorted(visitor.handlers),
            "public_definitions": sorted(set(visitor.public_definitions)),
            "functions": [
                {
                    "name": name,
                    "qualname": qualname,
                    "body_sha256": digest,
                    "line": line,
                }
                for name, qualname, digest, line in visitor.functions
            ],
            "state_expressions": visitor.state_expressions,
            "literal_state_roots": sorted(
                visitor.literal_state_roots,
                key=lambda item: (item["path"], item["line"], item["attribute"]),
            ),
        }
    known = set(modules)
    incoming: dict[str, set[str]] = {module: set() for module in modules}
    production_incoming: dict[str, set[str]] = {
        module: set() for module in modules
    }
    for source, record in modules.items():
        targets = [*record["imports"], *record["dynamic_imports"]]
        for target in targets:
            candidates = [target]
            parts = target.split(".")
            candidates.extend(".".join(parts[:index]) for index in range(len(parts), 0, -1))
            resolved = next((item for item in candidates if item in known), None)
            if resolved is not None and resolved != source:
                incoming[resolved].add(source)
                if source not in OBSERVATION_ONLY_MODULES:
                    production_incoming[resolved].add(source)
    for module in modules:
        modules[module]["incoming_modules"] = sorted(incoming[module])
        modules[module]["production_incoming_modules"] = sorted(
            production_incoming[module]
        )
    return modules, errors


def _direct_definition_nodes(
    module: str, tree: ast.Module
) -> dict[str, tuple[str | None, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Return production-callable module functions and class methods.

    Nested functions are intentionally excluded: a feature registry must name
    a stable production surface, not an implementation-local closure.
    """

    result: dict[
        str, tuple[str | None, ast.FunctionDef | ast.AsyncFunctionDef]
    ] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[f"{module}.{node.name}"] = (None, node)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result[f"{module}.{node.name}.{child.name}"] = (
                        node.name,
                        child,
                    )
    return result


def _import_aliases(
    module: str, tree: ast.Module, *, is_package: bool
) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                local = item.asname or item.name.split(".", 1)[0]
                aliases[local] = item.name if item.asname else local
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_import(module, node, is_package=is_package)
            if node.module:
                if not resolved:
                    continue
                base = resolved[0]
                for item in node.names:
                    if item.name != "*":
                        aliases[item.asname or item.name] = f"{base}.{item.name}"
            else:
                for item, target in zip(node.names, resolved):
                    if item.name != "*":
                        aliases[item.asname or item.name] = target
    return aliases


def _attribute_parts(node: ast.AST) -> list[str] | None:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        prefix = _attribute_parts(node.value)
        return [*prefix, node.attr] if prefix is not None else None
    return None


def _reference_candidates(
    node: ast.AST,
    *,
    module: str,
    class_name: str | None,
    aliases: dict[str, str],
) -> list[str]:
    """Return only namespace-qualified candidates proved by the syntax."""

    parts = _attribute_parts(node)
    if parts is None:
        return []
    candidates: list[str] = []
    if len(parts) == 1:
        name = parts[0]
        imported = aliases.get(name)
        if imported is not None:
            candidates.append(imported)
        if class_name is not None:
            candidates.append(f"{module}.{class_name}.{name}")
        candidates.append(f"{module}.{name}")
    else:
        first, remainder = parts[0], parts[1:]
        if first in {"self", "cls"} and class_name is not None:
            candidates.append(".".join([module, class_name, *remainder]))
        imported = aliases.get(first)
        if imported is not None:
            candidates.append(".".join([imported, *remainder]))
        candidates.append(".".join([module, *parts]))
    return list(dict.fromkeys(candidates))


class _NoNestedScopeVisitor(ast.NodeVisitor):
    """Shared scope barrier for collectors that index one callable body."""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return


class _LocalImportCollector(_NoNestedScopeVisitor):
    """Collect function-local import bindings without entering nested scopes."""

    def __init__(self, module: str, *, is_package: bool) -> None:
        self.module = module
        self.is_package = is_package
        self.aliases: dict[str, str] = {}

    def visit_Import(self, node: ast.Import) -> None:
        for item in node.names:
            local = item.asname or item.name.split(".", 1)[0]
            self.aliases[local] = item.name if item.asname else local

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        resolved = _resolve_import(
            self.module,
            node,
            is_package=self.is_package,
        )
        if node.module:
            if not resolved:
                return
            base = resolved[0]
            for item in node.names:
                if item.name != "*":
                    self.aliases[item.asname or item.name] = (
                        f"{base}.{item.name}"
                    )
        else:
            for item, target in zip(node.names, resolved):
                if item.name != "*":
                    self.aliases[item.asname or item.name] = target

def _function_aliases(
    module: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    is_package: bool,
    module_aliases: dict[str, str],
) -> dict[str, str]:
    collector = _LocalImportCollector(module, is_package=is_package)
    for statement in node.body:
        collector.visit(statement)
    return {**module_aliases, **collector.aliases}


def _annotation_class_types(
    annotation: ast.AST | None,
    *,
    module: str,
    class_name: str | None,
    aliases: dict[str, str],
    class_symbols: set[str],
) -> set[str]:
    if annotation is None:
        return set()
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            annotation = ast.parse(annotation.value, mode="eval").body
        except SyntaxError:
            return set()
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return _annotation_class_types(
            annotation.left,
            module=module,
            class_name=class_name,
            aliases=aliases,
            class_symbols=class_symbols,
        ).union(
            _annotation_class_types(
                annotation.right,
                module=module,
                class_name=class_name,
                aliases=aliases,
                class_symbols=class_symbols,
            )
        )
    if isinstance(annotation, ast.Subscript):
        return _annotation_class_types(
            annotation.slice,
            module=module,
            class_name=class_name,
            aliases=aliases,
            class_symbols=class_symbols,
        )
    return {
        candidate
        for candidate in _reference_candidates(
            annotation,
            module=module,
            class_name=class_name,
            aliases=aliases,
        )
        if candidate in class_symbols
    }


def _callable_argument_class_types(
    annotation: ast.AST | None,
    *,
    module: str,
    class_name: str | None,
    aliases: dict[str, str],
    class_symbols: set[str],
) -> list[set[str]]:
    """Resolve ``Callable[[A, B], R]`` argument classes when explicit."""

    if annotation is None:
        return []
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            annotation = ast.parse(annotation.value, mode="eval").body
        except SyntaxError:
            return []
    if not isinstance(annotation, ast.Subscript):
        return []
    callable_name = _attribute_parts(annotation.value)
    if not callable_name or callable_name[-1] != "Callable":
        return []
    slice_node = annotation.slice
    if not isinstance(slice_node, ast.Tuple) or not slice_node.elts:
        return []
    arguments = slice_node.elts[0]
    if not isinstance(arguments, (ast.List, ast.Tuple)):
        return []
    return [
        _annotation_class_types(
            item,
            module=module,
            class_name=class_name,
            aliases=aliases,
            class_symbols=class_symbols,
        )
        for item in arguments.elts
    ]


class _DirectCallCollector(_NoNestedScopeVisitor):
    """Collect exact Call edges, typed receivers and dynamic CLI handlers."""

    def __init__(
        self,
        *,
        module: str,
        class_name: str | None,
        aliases: dict[str, str],
        symbols: set[str],
        class_symbols: set[str],
        return_types: dict[str, set[str]],
        parameter_types: dict[str, set[str]],
        attribute_types: dict[tuple[str, str], set[str]],
        callback_bindings: dict[str, set[str]],
        constructor_parameters: dict[str, list[str]],
        callable_parameters: dict[str, list[str]],
        callback_argument_types: dict[tuple[str, str], list[set[str]]],
        nested_functions: dict[
            str, ast.FunctionDef | ast.AsyncFunctionDef
        ],
    ) -> None:
        self.module = module
        self.class_name = class_name
        self.class_symbol = (
            f"{module}.{class_name}" if class_name is not None else None
        )
        self.aliases = aliases
        self.symbols = symbols
        self.class_symbols = class_symbols
        self.return_types = return_types
        self.attribute_types = attribute_types
        self.callback_bindings = callback_bindings
        self.constructor_parameters = constructor_parameters
        self.callable_parameters = callable_parameters
        self.callback_argument_types = callback_argument_types
        self.nested_functions = nested_functions
        self.local_types = {
            name: set(types) for name, types in parameter_types.items()
        }
        if self.class_symbol is not None:
            self.local_types["self"] = {self.class_symbol}
            self.local_types["cls"] = {self.class_symbol}
        self.targets: set[str] = set()
        self.inferred_return_types: set[str] = set()
        self.inferred_attribute_types: dict[tuple[str, str], set[str]] = (
            defaultdict(set)
        )
        self.constructor_argument_types: dict[
            tuple[str, str], set[str]
        ] = defaultdict(set)
        self.call_argument_types: dict[tuple[str, str], set[str]] = (
            defaultdict(set)
        )

    def _infer_types(self, expression: ast.AST | None) -> set[str]:
        if expression is None:
            return set()
        if isinstance(expression, ast.Name):
            return set(self.local_types.get(expression.id, set()))
        if isinstance(expression, ast.Attribute):
            result: set[str] = set()
            for owner in self._infer_types(expression.value):
                result.update(
                    self.attribute_types.get((owner, expression.attr), set())
                )
            return result
        if isinstance(expression, ast.Call):
            targets = self._resolve_targets(expression.func)
            result = {
                target for target in targets if target in self.class_symbols
            }
            for target in targets:
                result.update(self.return_types.get(target, set()))
            # MathGraphStore._guard_child returns its first argument.  This is
            # an exact local wrapper contract, not a terminal-name guess.
            if (
                isinstance(expression.func, ast.Attribute)
                and expression.func.attr == "_guard_child"
                and expression.args
            ):
                result.update(self._infer_types(expression.args[0]))
            return result
        if isinstance(expression, ast.IfExp):
            return self._infer_types(expression.body).union(
                self._infer_types(expression.orelse)
            )
        return set()

    def _resolve_targets(self, function: ast.AST) -> set[str]:
        if isinstance(function, ast.Name):
            bound = self.callback_bindings.get(function.id)
            if bound:
                return set(bound)
        candidates = _reference_candidates(
            function,
            module=self.module,
            class_name=self.class_name,
            aliases=self.aliases,
        )
        resolved = {
            candidate
            for candidate in candidates
            if candidate in self.symbols or candidate in self.class_symbols
        }
        if isinstance(function, ast.Attribute):
            for owner in self._infer_types(function.value):
                candidate = f"{owner}.{function.attr}"
                if candidate in self.symbols:
                    resolved.add(candidate)
        return resolved

    def _record_constructor_arguments(self, node: ast.Call) -> None:
        for target in self._resolve_targets(node.func):
            parameters = self.constructor_parameters.get(target)
            if parameters is None:
                continue
            for name, value in zip(parameters, node.args):
                self.constructor_argument_types[(target, name)].update(
                    self._infer_types(value)
                )
            for keyword in node.keywords:
                if keyword.arg in parameters:
                    self.constructor_argument_types[
                        (target, keyword.arg)
                    ].update(self._infer_types(keyword.value))

    def _record_call_arguments(
        self,
        node: ast.Call,
        targets: set[str],
    ) -> None:
        for target in targets:
            parameters = self.callable_parameters.get(target)
            if parameters is None:
                continue
            bound_values: list[tuple[str, ast.AST]] = list(
                zip(parameters, node.args)
            )
            bound_values.extend(
                (keyword.arg, keyword.value)
                for keyword in node.keywords
                if keyword.arg in parameters
            )
            for parameter, value in bound_values:
                self.call_argument_types[(target, parameter)].update(
                    self._infer_types(value)
                )
                if not (
                    isinstance(value, ast.Lambda)
                    or (
                        isinstance(value, ast.Name)
                        and value.id in self.nested_functions
                    )
                ):
                    continue
                expected = self.callback_argument_types.get(
                    (target, parameter), []
                )
                callback_node: ast.Lambda | ast.FunctionDef | ast.AsyncFunctionDef
                if isinstance(value, ast.Lambda):
                    callback_node = value
                elif isinstance(value, ast.Name) and value.id in self.nested_functions:
                    callback_node = self.nested_functions[value.id]
                else:
                    continue
                callback_args = callback_node.args.args
                saved = {
                    argument.arg: set(self.local_types.get(argument.arg, set()))
                    for argument in callback_args
                }
                for argument, types in zip(callback_args, expected):
                    self.local_types[argument.arg] = set(types)
                if isinstance(callback_node, ast.Lambda):
                    self.visit(callback_node.body)
                else:
                    for statement in callback_node.body:
                        self.visit(statement)
                for argument in callback_args:
                    prior = saved[argument.arg]
                    if prior:
                        self.local_types[argument.arg] = prior
                    else:
                        self.local_types.pop(argument.arg, None)

    def visit_Call(self, node: ast.Call) -> None:
        targets = self._resolve_targets(node.func)
        self.targets.update(target for target in targets if target in self.symbols)
        self._record_constructor_arguments(node)
        self._record_call_arguments(node, targets)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "set_defaults":
            for keyword in node.keywords:
                # argparse stores exact callable objects in the Namespace.
                # The later ``args.func(...)``/``args.function(...)`` is a
                # dynamic call, so bind the parser builder directly to every
                # statically named handler here.
                self.targets.update(
                    target
                    for target in self._resolve_targets(keyword.value)
                    if target in self.symbols
                )
        self.generic_visit(node)

    def _bind_assignment(self, target: ast.AST, types: set[str]) -> None:
        if not types:
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            return
        if isinstance(target, ast.Name):
            self.local_types.setdefault(target.id, set()).update(types)
        elif (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
            and self.class_symbol is not None
        ):
            self.inferred_attribute_types[
                (self.class_symbol, target.attr)
            ].update(types)

    def visit_Assign(self, node: ast.Assign) -> None:
        types = self._infer_types(node.value)
        for target in node.targets:
            self._bind_assignment(target, types)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        types = self._infer_types(node.value)
        types.update(
            _annotation_class_types(
                node.annotation,
                module=self.module,
                class_name=self.class_name,
                aliases=self.aliases,
                class_symbols=self.class_symbols,
            )
        )
        self._bind_assignment(node.target, types)
        if node.value is not None:
            self.visit(node.value)

    def visit_Return(self, node: ast.Return) -> None:
        self.inferred_return_types.update(self._infer_types(node.value))
        if node.value is not None:
            self.visit(node.value)

class _DirectStateWriteCollector(_NoNestedScopeVisitor):
    """Detect persistent writes without conflating unrelated method owners."""

    def __init__(
        self,
        *,
        aliases: dict[str, str],
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        self.aliases = aliases
        self.evidence: set[str] = set()
        self.uncertain: set[str] = set()
        self.path_names: set[str] = set()
        self.write_handle_names: set[str] = set()
        self.flag_names: dict[str, set[str]] = {}
        positional = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        for argument in positional:
            if self._annotation_is_path(argument.annotation):
                self.path_names.add(argument.arg)

    @staticmethod
    def _open_mode(node: ast.Call) -> str:
        mode: ast.AST | None = node.args[1] if len(node.args) > 1 else None
        for keyword in node.keywords:
            if keyword.arg == "mode":
                mode = keyword.value
        return (
            mode.value
            if isinstance(mode, ast.Constant) and isinstance(mode.value, str)
            else ""
        )

    @staticmethod
    def _annotation_is_path(annotation: ast.AST | None) -> bool:
        if annotation is None:
            return False
        names = {
            child.id
            for child in ast.walk(annotation)
            if isinstance(child, ast.Name)
        }
        attributes = {
            child.attr
            for child in ast.walk(annotation)
            if isinstance(child, ast.Attribute)
        }
        return "Path" in names.union(attributes) and "str" not in names

    def _qualified_name(self, node: ast.AST) -> str | None:
        parts = _attribute_parts(node)
        if not parts:
            return None
        imported = self.aliases.get(parts[0])
        if imported is not None:
            parts = [imported, *parts[1:]]
        return ".".join(parts)

    def _path_like(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id in self.path_names
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            return True
        if isinstance(node, ast.Attribute):
            return node.attr == "parent" or self._path_like(node.value)
        if isinstance(node, ast.Call):
            qualified = self._qualified_name(node.func)
            if qualified in {"pathlib.Path", "Path"}:
                return True
            if isinstance(node.func, ast.Attribute) and node.func.attr in {
                "absolute",
                "resolve",
                "with_name",
                "with_stem",
                "with_suffix",
            }:
                return self._path_like(node.func.value)
        return False

    def _os_open_flag_names(self, node: ast.AST) -> set[str]:
        if isinstance(node, ast.Name):
            if node.id in self.flag_names:
                return set(self.flag_names[node.id])
            return {node.id} if node.id.startswith("O_") else set()
        if isinstance(node, ast.Attribute):
            return {node.attr} if node.attr.startswith("O_") else set()
        if isinstance(node, ast.Constant):
            return (
                {node.value}
                if isinstance(node.value, str) and node.value.startswith("O_")
                else set()
            )
        result: set[str] = set()
        for child in ast.iter_child_nodes(node):
            result.update(self._os_open_flag_names(child))
        return result

    def _os_open_is_write(self, node: ast.Call) -> bool | None:
        flags: ast.AST | None = node.args[1] if len(node.args) > 1 else None
        for keyword in node.keywords:
            if keyword.arg == "flags":
                flags = keyword.value
        if flags is None:
            return None
        names = self._os_open_flag_names(flags)
        if names.intersection(WRITE_OPEN_FLAG_NAMES):
            return True
        if names and all(name.startswith("O_") for name in names):
            return False
        if isinstance(flags, ast.Constant) and flags.value == 0:
            return False
        return None

    def _open_call_is_write(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        qualified = self._qualified_name(node.func)
        is_open = qualified in {"open", "builtins.open", "os.fdopen"}
        is_open = is_open or (
            isinstance(node.func, ast.Attribute) and node.func.attr == "open"
        )
        return is_open and any(flag in self._open_mode(node) for flag in "wax+")

    def _bind_path(self, target: ast.AST, value: ast.AST) -> None:
        if isinstance(target, ast.Name) and self._path_like(value):
            self.path_names.add(target.id)

    def _bind_write_handle(self, target: ast.AST | None, value: ast.AST) -> None:
        if (
            isinstance(target, ast.Name)
            and self._open_call_is_write(value)
        ):
            self.write_handle_names.add(target.id)

    def visit_Call(self, node: ast.Call) -> None:
        qualified = self._qualified_name(node.func)
        if qualified in QUALIFIED_STATE_WRITE_CALLS:
            self.evidence.add(qualified)
        elif qualified == "os.open":
            disposition = self._os_open_is_write(node)
            if disposition is True:
                self.evidence.add(qualified)
            elif disposition is None:
                self.uncertain.add("os.open:unresolved_flags")
        elif self._open_call_is_write(node):
            self.evidence.add(qualified or "open")
        elif isinstance(node.func, ast.Attribute):
            method = node.func.attr
            receiver = node.func.value
            if method in UNAMBIGUOUS_PATH_WRITE_METHODS:
                self.evidence.add(f"Path.{method}")
            elif (
                method in PATH_ONLY_AMBIGUOUS_WRITE_METHODS
                and self._path_like(receiver)
            ):
                self.evidence.add(f"Path.{method}")
            elif (
                method in {"truncate", "write", "writelines"}
                and isinstance(receiver, ast.Name)
                and receiver.id in self.write_handle_names
            ):
                self.evidence.add(f"write_handle.{method}")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        flag_names = self._os_open_flag_names(node.value)
        for target in node.targets:
            self._bind_path(target, node.value)
            self._bind_write_handle(target, node.value)
            if isinstance(target, ast.Name) and flag_names:
                self.flag_names[target.id] = set(flag_names)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name) and self._annotation_is_path(
            node.annotation
        ):
            self.path_names.add(node.target.id)
        if node.value is not None:
            flag_names = self._os_open_flag_names(node.value)
            if isinstance(node.target, ast.Name) and flag_names:
                self.flag_names[node.target.id] = set(flag_names)
            self._bind_path(node.target, node.value)
            self._bind_write_handle(node.target, node.value)
            self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if isinstance(node.target, ast.Name):
            names = self._os_open_flag_names(node.value)
            if names:
                self.flag_names.setdefault(node.target.id, set()).update(names)
        self.visit(node.value)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            self._bind_write_handle(item.optional_vars, item.context_expr)
            self.visit(item.context_expr)
        for statement in node.body:
            self.visit(statement)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self.visit_With(node)

def _behavioral_ast_index(
    root: Path,
    *,
    module_records: dict[str, dict[str, Any]],
    excluded_modules: set[str],
) -> dict[str, Any]:
    """Index production symbols and direct Call edges for feature closure."""

    parsed: dict[str, tuple[ast.Module, bool]] = {}
    errors: list[dict[str, Any]] = []
    symbol_nodes: dict[
        str,
        tuple[str, str | None, ast.FunctionDef | ast.AsyncFunctionDef],
    ] = {}
    for module, record in module_records.items():
        if module in excluded_modules:
            continue
        relative = record.get("path")
        path = _safe_registry_path(root, relative) if isinstance(relative, str) else None
        if path is None:
            errors.append(
                {"code": "production_module_path_missing", "module": module}
            )
            continue
        try:
            tree = ast.parse(path.read_bytes(), filename=relative)
        except SyntaxError as error:
            errors.append(
                {
                    "code": "production_ast_parse",
                    "module": module,
                    "line": error.lineno,
                }
            )
            continue
        is_package = path.name == "__init__.py"
        parsed[module] = (tree, is_package)
        for symbol, (class_name, node) in _direct_definition_nodes(
            module, tree
        ).items():
            symbol_nodes[symbol] = (module, class_name, node)

    symbols = set(symbol_nodes)
    class_symbols = {
        f"{module}.{node.name}"
        for module, (tree, _is_package) in parsed.items()
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }
    aliases_by_module = {
        module: _import_aliases(module, tree, is_package=is_package)
        for module, (tree, is_package) in parsed.items()
    }
    aliases_by_symbol: dict[str, dict[str, str]] = {}
    parameter_types_by_symbol: dict[str, dict[str, set[str]]] = {}
    callback_bindings_by_symbol: dict[str, dict[str, set[str]]] = {}
    return_types: dict[str, set[str]] = defaultdict(set)
    attribute_types: dict[tuple[str, str], set[str]] = defaultdict(set)
    constructor_parameters: dict[str, list[str]] = {}
    callable_parameters: dict[str, list[str]] = {}
    callback_argument_types: dict[tuple[str, str], list[set[str]]] = {}

    for symbol, (module, class_name, node) in symbol_nodes.items():
        is_package = parsed[module][1]
        aliases = _function_aliases(
            module,
            node,
            is_package=is_package,
            module_aliases=aliases_by_module.get(module, {}),
        )
        aliases_by_symbol[symbol] = aliases
        parameters: dict[str, set[str]] = {}
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        callable_parameters[symbol] = [
            argument.arg
            for argument in arguments
            if argument.arg not in {"self", "cls"}
        ]
        for argument in arguments:
            parameters[argument.arg] = _annotation_class_types(
                argument.annotation,
                module=module,
                class_name=class_name,
                aliases=aliases,
                class_symbols=class_symbols,
            )
            callable_types = _callable_argument_class_types(
                argument.annotation,
                module=module,
                class_name=class_name,
                aliases=aliases,
                class_symbols=class_symbols,
            )
            if callable_types:
                callback_argument_types[(symbol, argument.arg)] = callable_types
        parameter_types_by_symbol[symbol] = parameters
        return_types[symbol].update(
            _annotation_class_types(
                node.returns,
                module=module,
                class_name=class_name,
                aliases=aliases,
                class_symbols=class_symbols,
            )
        )
        callback_bindings: dict[str, set[str]] = defaultdict(set)
        positional = [*node.args.posonlyargs, *node.args.args]
        for argument, default in zip(
            positional[-len(node.args.defaults) :] if node.args.defaults else [],
            node.args.defaults,
        ):
            callback_bindings[argument.arg].update(
                candidate
                for candidate in _reference_candidates(
                    default,
                    module=module,
                    class_name=class_name,
                    aliases=aliases,
                )
                if candidate in symbols
            )
        for argument, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            if default is None:
                continue
            callback_bindings[argument.arg].update(
                candidate
                for candidate in _reference_candidates(
                    default,
                    module=module,
                    class_name=class_name,
                    aliases=aliases,
                )
                if candidate in symbols
            )
        callback_bindings_by_symbol[symbol] = callback_bindings
        if class_name is not None and node.name == "__init__":
            constructor_parameters[f"{module}.{class_name}"] = [
                argument.arg
                for argument in arguments
                if argument.arg not in {"self", "cls"}
            ]

    # Resolve factory returns, constructor-injected owner fields and typed
    # local receivers to a fixed point before constructing the exact call
    # graph.  This supports ``store.factory().method()`` and Union returns
    # without falling back to terminal method names.
    for _iteration in range(12):
        changed = False
        inferred_constructor_types: dict[tuple[str, str], set[str]] = (
            defaultdict(set)
        )
        for symbol, (module, class_name, node) in symbol_nodes.items():
            collector = _DirectCallCollector(
                module=module,
                class_name=class_name,
                aliases=aliases_by_symbol[symbol],
                symbols=symbols,
                class_symbols=class_symbols,
                return_types=return_types,
                parameter_types=parameter_types_by_symbol[symbol],
                attribute_types=attribute_types,
                callback_bindings=callback_bindings_by_symbol[symbol],
                constructor_parameters=constructor_parameters,
                callable_parameters=callable_parameters,
                callback_argument_types=callback_argument_types,
                nested_functions={
                    statement.name: statement
                    for statement in node.body
                    if isinstance(
                        statement, (ast.FunctionDef, ast.AsyncFunctionDef)
                    )
                },
            )
            for statement in node.body:
                collector.visit(statement)
            before_return = len(return_types[symbol])
            return_types[symbol].update(collector.inferred_return_types)
            changed = changed or len(return_types[symbol]) != before_return
            for key, types in collector.inferred_attribute_types.items():
                before = len(attribute_types[key])
                attribute_types[key].update(types)
                changed = changed or len(attribute_types[key]) != before
            for key, types in collector.constructor_argument_types.items():
                inferred_constructor_types[key].update(types)
            for (target, parameter), types in collector.call_argument_types.items():
                if target not in parameter_types_by_symbol:
                    continue
                before = len(
                    parameter_types_by_symbol[target].setdefault(parameter, set())
                )
                parameter_types_by_symbol[target][parameter].update(types)
                changed = changed or (
                    len(parameter_types_by_symbol[target][parameter]) != before
                )
        for (class_symbol, parameter), types in inferred_constructor_types.items():
            init_symbol = f"{class_symbol}.__init__"
            if init_symbol not in parameter_types_by_symbol:
                continue
            before = len(parameter_types_by_symbol[init_symbol].setdefault(
                parameter, set()
            ))
            parameter_types_by_symbol[init_symbol][parameter].update(types)
            changed = changed or (
                len(parameter_types_by_symbol[init_symbol][parameter]) != before
            )
        if not changed:
            break

    call_edges: set[tuple[str, str]] = set()
    direct_state_writers: dict[str, list[str]] = {}
    uncertain_state_write_receivers: dict[str, list[str]] = {}
    public_symbols = {
        symbol
        for symbol, (_module, _class_name, node) in symbol_nodes.items()
        if not node.name.startswith("_")
    }
    for caller, (module, class_name, node) in symbol_nodes.items():
        collector = _DirectCallCollector(
            module=module,
            class_name=class_name,
            aliases=aliases_by_symbol[caller],
            symbols=symbols,
            class_symbols=class_symbols,
            return_types=return_types,
            parameter_types=parameter_types_by_symbol[caller],
            attribute_types=attribute_types,
            callback_bindings=callback_bindings_by_symbol[caller],
            constructor_parameters=constructor_parameters,
            callable_parameters=callable_parameters,
            callback_argument_types=callback_argument_types,
            nested_functions={
                statement.name: statement
                for statement in node.body
                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            },
        )
        for statement in node.body:
            collector.visit(statement)
        call_edges.update((caller, target) for target in collector.targets)
        write_collector = _DirectStateWriteCollector(
            aliases=aliases_by_symbol[caller],
            node=node,
        )
        for statement in node.body:
            write_collector.visit(statement)
        if write_collector.evidence:
            direct_state_writers[caller] = sorted(write_collector.evidence)
        if write_collector.uncertain:
            uncertain_state_write_receivers[caller] = sorted(
                write_collector.uncertain
            )
    stateful_symbols = set(direct_state_writers)
    changed = True
    while changed:
        changed = False
        for caller, callee in call_edges:
            if callee in stateful_symbols and caller not in stateful_symbols:
                stateful_symbols.add(caller)
                changed = True
    return {
        "symbols": sorted(symbols),
        "public_symbols": sorted(public_symbols),
        "call_edges": [
            {"caller": caller, "callee": callee}
            for caller, callee in sorted(call_edges)
        ],
        "call_edge_set": call_edges,
        "direct_state_writers": direct_state_writers,
        "uncertain_state_write_receivers": uncertain_state_write_receivers,
        "resolved_return_types": {
            symbol: sorted(types)
            for symbol, types in sorted(return_types.items())
            if types
        },
        "resolved_attribute_types": {
            f"{owner}.{attribute}": sorted(types)
            for (owner, attribute), types in sorted(attribute_types.items())
            if types
        },
        "stateful_symbols": sorted(stateful_symbols),
        "public_stateful_symbols": sorted(public_symbols.intersection(stateful_symbols)),
        "errors": errors,
    }


def _behavioral_probe_symbols(root: Path) -> dict[str, Any]:
    symbols: set[str] = set()
    errors: list[dict[str, Any]] = []
    tests = root / "tests"
    if tests.is_symlink() or not tests.is_dir():
        return {
            "symbols": [],
            "errors": [{"code": "behavioral_tests_root_missing"}],
        }
    for path in sorted(tests.glob("test_*.py")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root).with_suffix("")
        module = ".".join(relative.parts)
        try:
            tree = ast.parse(path.read_bytes(), filename=path.as_posix())
        except SyntaxError as error:
            errors.append(
                {
                    "code": "probe_ast_parse",
                    "path": path.relative_to(root).as_posix(),
                    "line": error.lineno,
                }
            )
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    symbols.add(f"{module}.{node.name}")
            elif isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(
                        child, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ) and child.name.startswith("test_"):
                        symbols.add(f"{module}.{node.name}.{child.name}")
    return {"symbols": sorted(symbols), "errors": errors}


def _manifest(root: Path, actual_files: list[str]) -> dict[str, Any]:
    path = root / "MANIFEST.sha256"
    result: dict[str, Any] = {
        "present": path.is_file() and not path.is_symlink(),
        "valid_rows": False,
        "hashes_match": False,
        "path_set_matches": False,
        "manifest_sha256": None,
        "missing_paths": [],
        "unlisted_paths": [],
        "digest_mismatches": [],
        "errors": [],
    }
    if not result["present"]:
        result["errors"].append("MANIFEST.sha256 is missing or unsafe")
        return result
    raw = path.read_bytes()
    result["manifest_sha256"] = _sha256(raw)
    entries: dict[str, str] = {}
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        digest, separator, relative = line.partition("  ")
        candidate = PurePosixPath(relative)
        if (
            not separator
            or SHA256_RE.fullmatch(digest) is None
            or candidate.is_absolute()
            or ".." in candidate.parts
            or relative == "MANIFEST.sha256"
            or relative in entries
        ):
            result["errors"].append(f"invalid manifest row {number}")
            continue
        entries[relative] = digest
    result["valid_rows"] = not result["errors"] and list(entries) == sorted(entries)
    actual = sorted(path for path in actual_files if path != "MANIFEST.sha256")
    result["missing_paths"] = sorted(set(entries).difference(actual))
    result["unlisted_paths"] = sorted(set(actual).difference(entries))
    result["path_set_matches"] = not result["missing_paths"] and not result["unlisted_paths"]
    for relative, digest in entries.items():
        member = root / relative
        if member.is_file() and not member.is_symlink() and _sha256(member.read_bytes()) != digest:
            result["digest_mismatches"].append(relative)
    result["hashes_match"] = not result["digest_mismatches"] and not result["missing_paths"]
    return result


def _exact_duplicates(root: Path, paths: Iterable[Path]) -> list[dict[str, Any]]:
    by_hash: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        if any(part in GENERATED_PARTS for part in path.parts):
            continue
        by_hash[_sha256(path.read_bytes())].append(_relative(root, path))
    return [
        {"sha256": digest, "paths": sorted(items)}
        for digest, items in sorted(by_hash.items())
        if len(items) > 1
    ]


def _function_duplicates(modules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for module, record in modules.items():
        for function in record["functions"]:
            by_hash[function["body_sha256"]].append(
                {
                    "module": module,
                    "path": record["path"],
                    "name": function["name"],
                    "qualname": function["qualname"],
                    "line": function["line"],
                }
            )
    return [
        {"body_sha256": digest, "definitions": items}
        for digest, items in sorted(by_hash.items())
        if len(items) > 1
    ]


def _duplicate_body_adjudication(
    root: Path, duplicates: list[dict[str, Any]]
) -> dict[str, Any]:
    """Require one exact reviewed disposition for every repeated body."""

    path = root.joinpath(*DUPLICATE_ADJUDICATION_PATH.parts)
    result: dict[str, Any] = {
        "path": DUPLICATE_ADJUDICATION_PATH.as_posix(),
        "present": path.is_file() and not path.is_symlink(),
        "registry_sha256": None,
        "counts": {"observed": len(duplicates), "adjudicated": 0},
        "decisions": {},
        "errors": [],
        "ok": False,
    }
    if not result["present"]:
        result["errors"].append("registry_missing_or_unsafe")
        return result
    raw_bytes = path.read_bytes()
    result["registry_sha256"] = _sha256(raw_bytes)
    try:
        raw = json.loads(raw_bytes, object_pairs_hook=_unique_json_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        result["errors"].append(f"registry_json:{type(error).__name__}")
        return result
    if not isinstance(raw, dict):
        result["errors"].append("registry_not_object")
        return result
    if set(raw) != {"schema_version", "contract_revision", "truth_effect", "groups"}:
        result["errors"].append("registry_fields")
    if raw.get("schema_version") != 1:
        result["errors"].append("schema_version")
    if raw.get("contract_revision") != DUPLICATE_ADJUDICATION_REVISION:
        result["errors"].append("contract_revision")
    if raw.get("truth_effect") != "none":
        result["errors"].append("truth_effect")
    groups = raw.get("groups")
    if not isinstance(groups, dict):
        result["errors"].append("groups_not_object")
        groups = {}

    observed = {item["body_sha256"]: item for item in duplicates}
    missing = sorted(set(observed).difference(groups))
    stale = sorted(set(groups).difference(observed))
    if missing:
        result["errors"].append("unadjudicated:" + ",".join(missing))
    if stale:
        result["errors"].append("stale_adjudication:" + ",".join(stale))
    categories = {
        "standalone_portability",
        "state_boundary_local",
        "structural_method_parity",
        "package_local_stateless",
    }
    for digest in sorted(set(observed).intersection(groups)):
        record = groups[digest]
        if not isinstance(record, dict) or set(record) != {
            "decision",
            "category",
            "authoritative_owner",
            "definitions",
            "reason",
        }:
            result["errors"].append(f"record_fields:{digest}")
            continue
        if record.get("decision") != "retain_local":
            result["errors"].append(f"unresolved_decision:{digest}")
        category = record.get("category")
        if category not in categories:
            result["errors"].append(f"category:{digest}")
        owner = record.get("authoritative_owner")
        if not isinstance(owner, str):
            result["errors"].append(f"authoritative_owner:{digest}")
        definitions = record.get("definitions")
        expected = sorted(
            f'{item["module"]}:{item["qualname"]}'
            for item in observed[digest]["definitions"]
        )
        if (
            not isinstance(definitions, list)
            or definitions != sorted(definitions)
            or definitions != expected
        ):
            result["errors"].append(f"definitions:{digest}")
        if not isinstance(record.get("reason"), str) or not record["reason"].strip():
            result["errors"].append(f"reason:{digest}")
        result["decisions"].setdefault(str(category), []).append(digest)
    for digests in result["decisions"].values():
        digests.sort()
    result["counts"]["adjudicated"] = len(set(observed).intersection(groups))
    result["errors"] = sorted(set(result["errors"]))
    result["ok"] = not result["errors"]
    return result


def _text_corpus(root: Path, roots: tuple[str, ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in roots:
        base = root / name
        candidates = [base] if base.is_file() else list(base.rglob("*")) if base.exists() else []
        for path in candidates:
            if (
                path.is_file()
                and not path.is_symlink()
                and path.suffix in TEXT_SUFFIXES
                and not any(part in GENERATED_PARTS for part in path.parts)
            ):
                try:
                    result[_relative(root, path)] = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
    return result


def _subparser_choices(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    choices: dict[str, argparse.ArgumentParser] = {}
    for action in parser._actions:  # argparse exposes no public choice iterator
        if action.__class__.__name__ == "_SubParsersAction":
            choices.update(action.choices)
    return choices


def _command_inventory(root: Path, modules: dict[str, dict[str, Any]]) -> dict[str, Any]:
    scripts = root / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        cli = importlib.import_module("mathgraph.cli")
        roles = importlib.import_module("mathgraph.roles")
        learning = importlib.import_module("learning_graph")
        chx = importlib.import_module("chx_ledger")
        phx = importlib.import_module("phx_ledger")
        paper_library = importlib.import_module("paper_library")
        paper_research = importlib.import_module("paper_research_pipeline")
        surface_parsers = {
            "mgraph": ("mathgraph.cli", cli.build_parser()),
            "learn": ("learning_graph", learning.build_parser()),
            "chx": ("chx_ledger", chx._parser()),
            "phx": ("phx_ledger", phx._parser()),
            "paperlib": ("paper_library", paper_library.parser()),
            "paper-research": ("paper_research_pipeline", paper_research._parser()),
        }
        role_commands = set(roles.ALL_COMMANDS)
        role_coverage = {
            command: sorted(
                role for role, commands in roles.ROLE_COMMANDS.items() if command in commands
            )
            for command in sorted(role_commands)
        }
    finally:
        try:
            sys.path.remove(str(scripts))
        except ValueError:
            pass
    docs = _text_corpus(
        root,
        ("SKILL.md", "KNOWN_LIMITATIONS.md", "references", "assets", "agents"),
    )
    tests = _text_corpus(root, ("tests",))
    entries: list[dict[str, Any]] = []
    parser_ids: set[str] = set()
    handler_ids: set[str] = set()
    static_handler_ids: set[str] = set()
    surface_counts: dict[str, dict[str, int]] = {}
    for surface, (module, parser) in surface_parsers.items():
        choices = _subparser_choices(parser)
        static_handlers = set(modules.get(module, {}).get("handlers", []))
        static_handler_ids.update(f"{surface}:{token}" for token in static_handlers)
        surface_handler_count = 0
        for token, subparser in sorted(choices.items()):
            command_id = f"{surface}:{token}"
            parser_ids.add(command_id)
            default_dispatch = any(
                key in subparser._defaults for key in ("func", "function")
            )
            handler = token in static_handlers or default_dispatch
            if handler:
                handler_ids.add(command_id)
                surface_handler_count += 1
            documented = sorted(path for path, text in docs.items() if token in text)
            tested = sorted(path for path, text in tests.items() if token in text)
            entries.append(
                {
                    "command_id": command_id,
                    "surface": surface,
                    "token": token,
                    "parser": True,
                    "handler": handler,
                    "role_registry": surface == "mgraph" and token in role_commands,
                    "roles": role_coverage.get(token, []) if surface == "mgraph" else [],
                    "authorization_model": (
                        "mgraph_role_registry"
                        if surface == "mgraph"
                        else "standalone_parser_contract"
                    ),
                    "documentation": documented,
                    "tests": tested,
                }
            )
        surface_counts[surface] = {
            "parser": len(choices),
            "handlers": surface_handler_count,
            "role_registry": len(role_commands) if surface == "mgraph" else 0,
        }
    role_ids = {f"mgraph:{token}" for token in role_commands}
    return {
        "counts": {
            "parser": len(parser_ids),
            "handlers": len(handler_ids),
            "mgraph_role_registry": len(role_commands),
        },
        "surface_counts": surface_counts,
        "parser_without_handler": sorted(parser_ids.difference(handler_ids)),
        "handler_without_parser": sorted(static_handler_ids.difference(parser_ids)),
        "parser_without_role": sorted(
            command_id
            for command_id in parser_ids
            if command_id.startswith("mgraph:") and command_id not in role_ids
        ),
        "role_without_parser": sorted(role_ids.difference(parser_ids)),
        "undocumented": sorted(
            item["command_id"]
            for item in entries
            if item["parser"] and not item["documentation"]
        ),
        "untested": sorted(
            item["command_id"]
            for item in entries
            if item["parser"] and not item["tests"]
        ),
        "entries": sorted(entries, key=lambda item: item["command_id"]),
    }


def _comparison(root: Path, other: Path | None) -> dict[str, Any] | None:
    if other is None:
        return None
    if other.is_symlink() or not other.is_dir():
        raise ValueError(f"comparison root is unsafe or missing: {other}")
    current = {
        _relative(root, path): _sha256(path.read_bytes())
        for path in _files(root)
        if not any(part in GENERATED_PARTS for part in path.parts)
    }
    compared = {
        _relative(other, path): _sha256(path.read_bytes())
        for path in _files(other)
        if not any(part in GENERATED_PARTS for part in path.parts)
    }
    return {
        "root": str(other),
        "added": sorted(set(current).difference(compared)),
        "removed": sorted(set(compared).difference(current)),
        "changed": sorted(
            path for path in set(current).intersection(compared) if current[path] != compared[path]
        ),
        "unchanged_count": sum(
            current[path] == compared[path] for path in set(current).intersection(compared)
        ),
    }


def _safe_registry_path(root: Path, relative: str) -> Path | None:
    candidate = PurePosixPath(relative)
    if not relative or candidate.is_absolute() or ".." in candidate.parts:
        return None
    path = root.joinpath(*candidate.parts)
    return path if path.is_file() and not path.is_symlink() else None


def _managed_launchers(root: Path) -> set[str]:
    scripts = root / "scripts"
    if scripts.is_symlink() or not scripts.is_dir():
        return set()
    return {
        path.relative_to(root).as_posix()
        for path in scripts.iterdir()
        if path.is_file()
        and not path.is_symlink()
        and path.suffix == ""
        and os.access(path, os.X_OK)
    }


def _registry_record(mapping: dict[str, Any], key: Any) -> dict[str, Any] | None:
    if not isinstance(key, str):
        return None
    value = mapping.get(key)
    return value if isinstance(value, dict) else None


class _TopLevelCallCollector(_NoNestedScopeVisitor):
    """Resolve calls executed by a module entry block, excluding definitions."""

    def __init__(
        self,
        *,
        module: str,
        aliases: dict[str, str],
        known_symbols: set[str],
    ) -> None:
        self.module = module
        self.aliases = aliases
        self.known_symbols = known_symbols
        self.targets: set[str] = set()

    def visit_Call(self, node: ast.Call) -> None:
        self.targets.update(
            candidate
            for candidate in _reference_candidates(
                node.func,
                module=self.module,
                class_name=None,
                aliases=self.aliases,
            )
            if candidate in self.known_symbols
        )
        self.generic_visit(node)

def _standalone_entry_candidates(
    root: Path,
    *,
    module: str,
    module_record: dict[str, Any],
    known_symbols: set[str],
) -> set[str]:
    relative = module_record.get("path")
    path = _safe_registry_path(root, relative) if isinstance(relative, str) else None
    if path is None:
        return set()
    try:
        tree = ast.parse(path.read_bytes(), filename=relative)
    except SyntaxError:
        return set()
    collector = _TopLevelCallCollector(
        module=module,
        aliases=_import_aliases(
            module,
            tree,
            is_package=path.name == "__init__.py",
        ),
        known_symbols=known_symbols,
    )
    for statement in tree.body:
        collector.visit(statement)
    return collector.targets


def _authority_effect_set(value: Any) -> set[str] | None:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item in AUTHORITY_EFFECTS for item in value)
        or len(value) != len(set(value))
        or value != sorted(value)
    ):
        return None
    return set(value)


def _state_path_covers(declared: str, observed: str) -> bool:
    if declared.startswith("@"):
        return False
    declared_path = PurePosixPath(declared)
    observed_path = PurePosixPath(observed)
    if declared_path.is_absolute() or observed_path.is_absolute():
        return False
    declared_parts = declared_path.parts
    observed_parts = observed_path.parts
    if len(declared_parts) > len(observed_parts):
        return False
    return all(
        declared_part == observed_part
        or (declared_part.startswith("{") and declared_part.endswith("}"))
        for declared_part, observed_part in zip(declared_parts, observed_parts)
    )


def _capability_registry(
    root: Path,
    *,
    module_records: dict[str, dict[str, Any]],
    command_names: set[str],
    production_unreferenced_modules: set[str],
    launcher_paths: set[str],
) -> dict[str, Any]:
    path = root.joinpath(*CAPABILITY_REGISTRY_PATH.parts)
    result: dict[str, Any] = {
        "path": CAPABILITY_REGISTRY_PATH.as_posix(),
        "present": path.is_file() and not path.is_symlink(),
        "registry_sha256": None,
        "counts": {
            "capabilities": 0,
            "modules": 0,
            "commands": 0,
            "compatibility_aliases": 0,
            "state_roots": 0,
            "launchers": 0,
        },
        "errors": [],
        "warnings": [],
        "classified_standalone_modules": [],
        "validation_tool_modules": [],
        "activation_symbols": [],
        "ok": False,
    }
    if not result["present"]:
        result["errors"].append("registry_missing_or_unsafe")
        return result
    raw_bytes = path.read_bytes()
    result["registry_sha256"] = _sha256(raw_bytes)
    try:
        raw = json.loads(raw_bytes, object_pairs_hook=_unique_json_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        result["errors"].append(f"registry_json:{type(error).__name__}")
        return result
    if not isinstance(raw, dict):
        result["errors"].append("registry_not_object")
        return result
    if raw.get("schema_version") != 3:
        result["errors"].append("schema_version")
    if raw.get("contract_revision") != CAPABILITY_REGISTRY_REVISION:
        result["errors"].append("contract_revision")
    if raw.get("truth_effect") != "none":
        result["errors"].append("truth_effect")
    module_names = set(module_records)
    capabilities = raw.get("capabilities")
    modules = raw.get("modules")
    commands = raw.get("commands")
    aliases = raw.get("compatibility_aliases")
    launchers = raw.get("launchers")
    if not isinstance(capabilities, dict):
        result["errors"].append("capabilities_not_object")
        capabilities = {}
    if not isinstance(modules, dict):
        result["errors"].append("modules_not_object")
        modules = {}
    if not isinstance(commands, dict):
        result["errors"].append("commands_not_object")
        commands = {}
    if not isinstance(aliases, dict):
        result["errors"].append("compatibility_aliases_not_object")
        aliases = {}
    if not isinstance(launchers, dict):
        result["errors"].append("launchers_not_object")
        launchers = {}
    registered_launchers = set(launchers)
    missing_launchers = sorted(launcher_paths.difference(registered_launchers))
    unknown_launchers = sorted(registered_launchers.difference(launcher_paths))
    if missing_launchers:
        result["errors"].append(
            "missing_launchers:" + ",".join(missing_launchers)
        )
    if unknown_launchers:
        result["errors"].append(
            "unknown_launchers:" + ",".join(unknown_launchers)
        )
    capability_ids = set(capabilities)
    registered_modules = set(modules)
    registered_commands = set(commands)
    missing_modules = sorted(module_names.difference(registered_modules))
    unknown_modules = sorted(registered_modules.difference(module_names))
    missing_commands = sorted(command_names.difference(registered_commands))
    unknown_commands = sorted(registered_commands.difference(command_names))
    if missing_modules:
        result["errors"].append("missing_modules:" + ",".join(missing_modules))
    if unknown_modules:
        result["errors"].append("unknown_modules:" + ",".join(unknown_modules))
    if missing_commands:
        result["errors"].append("missing_commands:" + ",".join(missing_commands))
    if unknown_commands:
        result["errors"].append("unknown_commands:" + ",".join(unknown_commands))

    production_symbols = {
        f"{module}.{definition['qualname']}"
        for module, module_record in module_records.items()
        for definition in module_record.get("functions", [])
        if isinstance(definition, dict)
        and isinstance(definition.get("qualname"), str)
    }
    required_entry_modules = {
        record.get("target_module")
        for record in launchers.values()
        if isinstance(record, dict)
        and isinstance(record.get("target_module"), str)
    }
    required_entry_modules.update(
        activation.get("module")
        for capability in capabilities.values()
        if isinstance(capability, dict)
        for activation in capability.get("activation_paths", [])
        if isinstance(activation, dict)
        and activation.get("kind") in {"standalone", "subprocess"}
        and isinstance(activation.get("module"), str)
    )

    capability_usage: dict[str, int] = {item: 0 for item in capability_ids}
    classified_standalone: list[str] = []
    validation_tool_modules: list[str] = []
    activation_symbols: set[str] = set()
    for module, record in modules.items():
        if not isinstance(record, dict):
            result["errors"].append(f"module_record:{module}")
            continue
        capability_id = record.get("capability_id")
        if not isinstance(capability_id, str) or capability_id not in capability_ids:
            result["errors"].append(f"module_capability:{module}")
        else:
            capability_usage[capability_id] += 1
        if record.get("path") != module_records.get(module, {}).get("path"):
            result["errors"].append(f"module_path:{module}")
        roles = record.get("roles")
        roles_valid = (
            isinstance(roles, list)
            and bool(roles)
            and all(isinstance(role, str) and role in MODULE_ROLES for role in roles)
        )
        if roles_valid:
            roles_valid = len(roles) == len(set(roles))
        if not roles_valid:
            result["errors"].append(f"module_roles:{module}")
            roles = []
        elif "validation_tool" in roles:
            validation_tool_modules.append(module)
        entry_symbols = record.get("standalone_entry_symbols")
        if module in required_entry_modules and entry_symbols is None:
            result["errors"].append(f"module_standalone_entry_symbols:{module}")
            entry_symbols = []
        if entry_symbols is not None:
            if (
                not isinstance(entry_symbols, list)
                or not entry_symbols
                or not all(isinstance(item, str) and item for item in entry_symbols)
                or len(entry_symbols) != len(set(entry_symbols))
            ):
                result["errors"].append(
                    f"module_standalone_entry_symbols:{module}"
                )
                entry_symbols = []
            candidates = _standalone_entry_candidates(
                root,
                module=module,
                module_record=module_records.get(module, {}),
                known_symbols=production_symbols,
            )
            for symbol in entry_symbols:
                if symbol not in production_symbols:
                    result["errors"].append(
                        f"module_standalone_entry_symbol_missing:{module}:{symbol}"
                    )
                elif symbol not in candidates:
                    result["errors"].append(
                        f"module_standalone_entry_not_called:{module}:{symbol}"
                    )
                else:
                    activation_symbols.add(symbol)
        if module in production_unreferenced_modules:
            if set(roles).intersection({
                "entrypoint",
                "learner",
                "release_tool",
                "validation_tool",
            }) and isinstance(record.get("standalone_reason"), str) and record[
                "standalone_reason"
            ].strip():
                classified_standalone.append(module)
            else:
                result["errors"].append(f"unclassified_standalone_module:{module}")
    for launcher, record in launchers.items():
        if not isinstance(record, dict):
            result["errors"].append(f"launcher_record:{launcher}")
            continue
        capability_id = record.get("capability_id")
        target_module = record.get("target_module")
        target_path = record.get("target_path")
        launcher_path = _safe_registry_path(root, launcher)
        target_record = _registry_record(modules, target_module)
        if not isinstance(capability_id, str) or capability_id not in capability_ids:
            result["errors"].append(f"launcher_capability:{launcher}")
        else:
            capability_usage[capability_id] += 1
        if (
            not isinstance(target_record, dict)
            or target_record.get("capability_id") != capability_id
            or not isinstance(target_path, str)
            or target_record.get("path") != target_path
            or _safe_registry_path(root, target_path) is None
        ):
            result["errors"].append(f"launcher_target:{launcher}")
        if launcher_path is None or not os.access(launcher_path, os.X_OK):
            result["errors"].append(f"launcher_not_executable:{launcher}")
        elif (
            not isinstance(target_path, str)
            or PurePosixPath(target_path).name
            not in launcher_path.read_text(encoding="utf-8", errors="replace")
        ):
            result["errors"].append(f"launcher_target_not_executed:{launcher}")
    alias_commands: set[str] = set()
    command_authority_effects: dict[str, set[str]] = {}
    for command, record in commands.items():
        if not isinstance(record, dict):
            result["errors"].append(f"command_record:{command}")
            continue
        capability_id = record.get("capability_id")
        if not isinstance(capability_id, str) or capability_id not in capability_ids:
            result["errors"].append(f"command_capability:{command}")
        else:
            capability_usage[capability_id] += 1
        status = record.get("status")
        if status not in {"canonical", "compatibility_surface", "exact_alias"}:
            result["errors"].append(f"command_status:{command}")
        if status != "canonical":
            alias_commands.add(command)
        effects = _authority_effect_set(record.get("authority_effects"))
        if effects is None:
            result["errors"].append(f"command_authority_effects:{command}")
            effects = set()
        command_authority_effects[command] = effects
        required_effects = CRITICAL_COMMAND_AUTHORITY_EFFECTS.get(command)
        if required_effects is not None and effects != required_effects:
            result["errors"].append(f"critical_command_authority:{command}")
    if set(aliases) != alias_commands:
        result["errors"].append("compatibility_alias_set")
    for alias, record in aliases.items():
        if not isinstance(record, dict):
            result["errors"].append(f"compatibility_alias_record:{alias}")
            continue
        canonical = record.get("canonical_command")
        canonical_record = _registry_record(commands, canonical)
        alias_record = _registry_record(commands, alias)
        relation = record.get("relation")
        target_statuses = (
            {"canonical", "compatibility_surface"}
            if relation == "exact_alias"
            else {"canonical"}
        )
        if not isinstance(relation, str) or relation not in {
            "exact_alias",
            "v5_compatibility_surface",
        }:
            result["errors"].append(f"compatibility_alias_relation:{alias}")
        if canonical == alias or not isinstance(canonical_record, dict) or (
            canonical_record.get("status") not in target_statuses
        ):
            result["errors"].append(f"compatibility_alias_target:{alias}")
        if (
            relation == "exact_alias"
            and isinstance(canonical_record, dict)
            and canonical_record.get("capability_id")
            != (alias_record.get("capability_id") if isinstance(alias_record, dict) else None)
        ):
            result["errors"].append(f"exact_alias_capability:{alias}")
        if (
            isinstance(canonical, str)
            and command_authority_effects.get(alias, set())
            != command_authority_effects.get(canonical, set())
        ):
            result["errors"].append(f"compatibility_alias_authority:{alias}")
        if not isinstance(record.get("reason"), str) or not record["reason"].strip():
            result["errors"].append(f"compatibility_alias_reason:{alias}")

    state_owners: dict[str, dict[str, str]] = {}
    capability_authority_effects: dict[str, set[str]] = {}
    document_count = 0
    test_count = 0
    activation_count = 0
    for capability_id, record in capabilities.items():
        if not isinstance(record, dict):
            result["errors"].append(f"capability_record:{capability_id}")
            continue
        if not isinstance(record.get("summary"), str) or not record["summary"].strip():
            result["errors"].append(f"capability_summary:{capability_id}")
        status = record.get("status")
        if not isinstance(status, str) or status not in CAPABILITY_STATUSES:
            result["errors"].append(f"capability_status:{capability_id}")
        effects = _authority_effect_set(record.get("authority_effects"))
        if effects is None:
            result["errors"].append(
                f"capability_authority_effects:{capability_id}"
            )
            effects = set()
        capability_authority_effects[capability_id] = effects
        activation_paths = record.get("activation_paths")
        if not isinstance(activation_paths, list) or not activation_paths:
            result["errors"].append(f"capability_activation_paths:{capability_id}")
            activation_paths = []
        for index, activation in enumerate(activation_paths):
            if not isinstance(activation, dict):
                result["errors"].append(
                    f"capability_activation_record:{capability_id}:{index}"
                )
                continue
            kind = activation.get("kind")
            if kind == "cli":
                command = activation.get("command")
                command_record = _registry_record(commands, command)
                if (
                    not isinstance(command_record, dict)
                    or command_record.get("capability_id") != capability_id
                ):
                    result["errors"].append(
                        f"capability_activation_cli:{capability_id}:{index}"
                    )
                else:
                    activation_count += 1
            elif kind == "standalone":
                module = activation.get("module")
                module_record = _registry_record(modules, module)
                module_roles = (
                    module_record.get("roles", [])
                    if isinstance(module_record, dict)
                    else []
                )
                if (
                    not isinstance(module_record, dict)
                    or not isinstance(module, str)
                    or module not in production_unreferenced_modules
                    or not isinstance(module_roles, list)
                    or not all(isinstance(role, str) for role in module_roles)
                    or not set(module_roles).intersection(
                        {"entrypoint", "learner", "release_tool", "validation_tool"}
                    )
                ):
                    result["errors"].append(
                        f"capability_activation_standalone:{capability_id}:{index}"
                    )
                else:
                    activation_count += 1
            elif kind == "automatic":
                module = activation.get("module")
                consumer = activation.get("consumer_module")
                if (
                    not isinstance(module, str)
                    or module not in modules
                    or not isinstance(consumer, str)
                    or consumer not in module_names
                    or consumer not in module_records.get(module, {}).get(
                        "production_incoming_modules", []
                    )
                ):
                    result["errors"].append(
                        f"capability_activation_automatic:{capability_id}:{index}"
                    )
                else:
                    activation_count += 1
            elif kind == "launcher":
                launcher = activation.get("path")
                launcher_record = _registry_record(launchers, launcher)
                if (
                    not isinstance(launcher_record, dict)
                    or launcher_record.get("capability_id") != capability_id
                ):
                    result["errors"].append(
                        f"capability_activation_launcher:{capability_id}:{index}"
                    )
                else:
                    activation_count += 1
            elif kind == "subprocess":
                module = activation.get("module")
                consumer = activation.get("consumer_module")
                command_path = activation.get("command_path")
                consumer_path = (
                    _safe_registry_path(root, module_records[consumer]["path"])
                    if isinstance(consumer, str) and consumer in module_records
                    else None
                )
                if (
                    not isinstance(module, str)
                    or module not in modules
                    or consumer_path is None
                    or not isinstance(command_path, str)
                    or _safe_registry_path(root, command_path) is None
                    or command_path
                    not in consumer_path.read_text(encoding="utf-8", errors="replace")
                ):
                    result["errors"].append(
                        f"capability_activation_subprocess:{capability_id}:{index}"
                    )
                else:
                    activation_count += 1
            else:
                result["errors"].append(
                    f"capability_activation_kind:{capability_id}:{index}"
                )
        if not isinstance(record.get("stateful"), bool):
            result["errors"].append(f"capability_stateful:{capability_id}")
        state_roots = record.get("state_roots")
        if not isinstance(state_roots, list):
            result["errors"].append(f"capability_state_roots:{capability_id}")
            state_roots = []
        if record.get("stateful") is True and not state_roots:
            result["errors"].append(f"capability_state_roots_empty:{capability_id}")
        if record.get("stateful") is False and state_roots:
            result["errors"].append(f"capability_stateless_has_roots:{capability_id}")
        for index, state_root in enumerate(state_roots):
            if not isinstance(state_root, dict):
                result["errors"].append(
                    f"capability_state_root_record:{capability_id}:{index}"
                )
                continue
            state_path = state_root.get("path")
            owner = state_root.get("owner_module")
            relationship = state_root.get("relationship")
            if not isinstance(state_path, str) or not state_path.strip():
                result["errors"].append(
                    f"capability_state_root_path:{capability_id}:{index}"
                )
                continue
            normalized = PurePosixPath(state_path)
            if normalized.is_absolute() or ".." in normalized.parts:
                result["errors"].append(f"capability_unsafe_state_root:{capability_id}")
            owner_record = _registry_record(modules, owner)
            owner_roles = (
                owner_record.get("roles", [])
                if isinstance(owner_record, dict)
                else []
            )
            if (
                not isinstance(owner_roles, list)
                or "state_owner" not in owner_roles
            ):
                result["errors"].append(
                    f"capability_state_owner:{capability_id}:{index}"
                )
            if not isinstance(relationship, str) or relationship not in {
                "canonical",
                "delegated_child",
                "derived_index",
                "external_host",
                "projection",
            }:
                result["errors"].append(
                    f"capability_state_relationship:{capability_id}:{index}"
                )
            previous = state_owners.get(state_path)
            if previous is not None:
                result["errors"].append(
                    f"duplicate_state_root:{state_path}:{previous['capability_id']}:{capability_id}"
                )
            state_owners[state_path] = {
                "capability_id": capability_id,
                "owner_module": str(owner),
                "relationship": str(relationship),
                "parent_path": str(state_root.get("parent_path", "")),
            }
        for field, expected_prefix in (("documents", "references/"), ("tests", "tests/")):
            values = record.get(field)
            if not isinstance(values, list) or not values:
                result["errors"].append(f"capability_{field}:{capability_id}")
                continue
            for relative in values:
                if not isinstance(relative, str) or not relative.startswith(expected_prefix):
                    result["errors"].append(f"capability_{field}_path:{capability_id}")
                elif _safe_registry_path(root, relative) is None:
                    result["errors"].append(
                        f"capability_{field}_missing:{capability_id}:{relative}"
                    )
                elif field == "documents":
                    document_count += 1
                else:
                    test_count += 1
        if capability_usage.get(capability_id, 0) == 0:
            result["errors"].append(f"unused_capability:{capability_id}")

    state_paths = sorted(
        state_owners, key=lambda item: (len(PurePosixPath(item).parts), item)
    )
    for child_path in state_paths:
        child = state_owners[child_path]
        ancestors = [
            parent_path
            for parent_path in state_paths
            if parent_path != child_path
            and PurePosixPath(parent_path) in PurePosixPath(child_path).parents
        ]
        if not ancestors:
            continue
        nearest = max(ancestors, key=lambda item: len(PurePosixPath(item).parts))
        if (
            child["relationship"]
            not in {"delegated_child", "derived_index", "projection"}
            or child["parent_path"] != nearest
        ):
            result["errors"].append(
                f"undeclared_state_root_overlap:{nearest}:{child_path}"
            )

    for command, record in commands.items():
        if not isinstance(record, dict):
            continue
        capability_id = record.get("capability_id")
        if not isinstance(capability_id, str):
            continue
        if not command_authority_effects.get(command, set()).issubset(
            capability_authority_effects.get(capability_id, set())
        ):
            result["errors"].append(
                f"command_authority_outside_capability:{command}"
            )

    declared_by_owner: dict[str, list[str]] = defaultdict(list)
    for state_path, state_record in state_owners.items():
        owner = state_record.get("owner_module")
        if isinstance(owner, str):
            declared_by_owner[owner].append(state_path)
    literal_state_root_count = 0
    for module, module_record in module_records.items():
        literal_roots = module_record.get("literal_state_roots", [])
        if not isinstance(literal_roots, list):
            result["errors"].append(f"literal_state_roots_record:{module}")
            continue
        for literal in literal_roots:
            if not isinstance(literal, dict) or not isinstance(
                literal.get("path"), str
            ):
                result["errors"].append(f"literal_state_root_record:{module}")
                continue
            literal_state_root_count += 1
            observed_path = literal["path"]
            if not any(
                _state_path_covers(declared_path, observed_path)
                for declared_path in declared_by_owner.get(module, [])
            ):
                result["errors"].append(
                    f"unregistered_literal_state_root:{module}:{observed_path}"
                )

    result["counts"] = {
        "capabilities": len(capabilities),
        "modules": len(modules),
        "commands": len(commands),
        "compatibility_aliases": len(aliases),
        "state_roots": len(state_owners),
        "document_anchors": document_count,
        "test_anchors": test_count,
        "activation_paths": activation_count,
        "launchers": len(launchers),
        "literal_state_roots": literal_state_root_count,
        "standalone_entry_symbols": len(activation_symbols),
    }
    result["errors"] = sorted(set(result["errors"]))
    result["warnings"] = sorted(set(result["warnings"]))
    result["classified_standalone_modules"] = sorted(classified_standalone)
    result["validation_tool_modules"] = sorted(validation_tool_modules)
    result["activation_symbols"] = sorted(activation_symbols)
    result["ok"] = not result["errors"]
    return result


def _behavioral_feature_registry(
    root: Path,
    *,
    ast_index: dict[str, Any],
    probe_index: dict[str, Any],
    capability_activation_symbols: Iterable[str] = (),
) -> dict[str, Any]:
    """Validate feature-level normal-flow closure without executing code.

    This gate deliberately proves less than a behavioral test run: it proves
    that named production symbols and direct Call edges exist, and that the
    three named probe methods are real AST definitions.  It nevertheless
    proves more than module reachability, because imports, strings, tests, and
    release validation tools cannot make a normal-flow feature non-orphaned.
    """

    path = root.joinpath(*BEHAVIORAL_REGISTRY_PATH.parts)
    result: dict[str, Any] = {
        "path": BEHAVIORAL_REGISTRY_PATH.as_posix(),
        "present": path.is_file() and not path.is_symlink(),
        "registry_sha256": None,
        "counts": {
            "features": 0,
            "required_normal_flow": 0,
            "production_symbols": len(ast_index.get("symbols", [])),
            "production_call_edges": len(ast_index.get("call_edges", [])),
            "public_stateful_symbols": len(
                ast_index.get("public_stateful_symbols", [])
            ),
            "probe_symbols": len(probe_index.get("symbols", [])),
            "capability_activation_symbols": 0,
            **{classification: 0 for classification in BEHAVIORAL_CLASSIFICATIONS},
        },
        "errors": [],
        "warnings": [],
        "behavioral_orphan_features": [],
        "unregistered_public_state_symbols": [],
        "lifecycle_dispositions": {
            decision: [] for decision in sorted(BEHAVIORAL_LIFECYCLE_DECISIONS)
        },
        "ok": False,
    }

    feature_error_ids: set[str] = set()

    def add_error(
        code: str, *, feature_id: str = "", **details: Any
    ) -> None:
        error = {"code": code}
        if feature_id:
            error["feature_id"] = feature_id
            feature_error_ids.add(feature_id)
        error.update(details)
        result["errors"].append(error)

    for error in ast_index.get("errors", []):
        if isinstance(error, dict):
            add_error("production_ast_index_error", detail=error)
    for error in probe_index.get("errors", []):
        if isinstance(error, dict):
            add_error("probe_ast_index_error", detail=error)
    if not result["present"]:
        add_error("registry_missing_or_unsafe")
        return result
    raw_bytes = path.read_bytes()
    result["registry_sha256"] = _sha256(raw_bytes)
    try:
        raw = json.loads(raw_bytes, object_pairs_hook=_unique_json_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        add_error("registry_json", error_type=type(error).__name__)
        return result
    if not isinstance(raw, dict):
        add_error("registry_not_object")
        return result
    if raw.get("schema_version") != 1:
        add_error("schema_version")
    if raw.get("contract_revision") != BEHAVIORAL_REGISTRY_REVISION:
        add_error("contract_revision")
    if raw.get("truth_effect") != "none":
        add_error("truth_effect")
    features = raw.get("features")
    if not isinstance(features, dict):
        add_error("features_not_object")
        features = {}
    result["counts"]["features"] = len(features)

    production_symbols = set(ast_index.get("symbols", []))
    call_edges = set(ast_index.get("call_edge_set", set()))
    probe_symbols = set(probe_index.get("symbols", []))
    predicate_owners: dict[str, str] = {}
    normal_flow_ids: set[str] = set()
    registered_activation_roots: set[str] = production_symbols.intersection(
        capability_activation_symbols
    )
    result["counts"]["capability_activation_symbols"] = len(
        registered_activation_roots
    )
    for caller, uncertainties in sorted(
        ast_index.get("uncertain_state_write_receivers", {}).items()
    ):
        result["warnings"].append(
            {
                "code": "uncertain_state_write_receiver",
                "symbol": caller,
                "evidence": uncertainties,
            }
        )
    normal_fields = {
        "classification",
        "required",
        "summary",
        "lifecycle_decision",
        "production_entry_symbol",
        "producer_symbol",
        "activation_predicate",
        "typed_handoff",
        "consumer_symbol",
        "observable_effect",
        "probes",
    }
    boundary_fields = {
        "classification",
        "required",
        "summary",
        "lifecycle_decision",
        "replacement_feature_id",
        "boundary_reason",
        "guard_symbol",
        "boundary_probe",
    }
    for feature_id, record in features.items():
        if not isinstance(feature_id, str) or re.fullmatch(
            r"feature\.[a-z][a-z0-9_]*", feature_id
        ) is None:
            add_error("feature_id", feature_id=str(feature_id))
        if not isinstance(record, dict):
            add_error("feature_record", feature_id=str(feature_id))
            continue
        classification = record.get("classification")
        if classification not in BEHAVIORAL_CLASSIFICATIONS:
            add_error("classification", feature_id=feature_id)
            continue
        result["counts"][classification] += 1
        if not isinstance(record.get("summary"), str) or not record[
            "summary"
        ].strip():
            add_error("summary", feature_id=feature_id)
        if not isinstance(record.get("required"), bool):
            add_error("required", feature_id=feature_id)
        lifecycle_decision = record.get("lifecycle_decision")
        if lifecycle_decision not in BEHAVIORAL_LIFECYCLE_DECISIONS:
            add_error("lifecycle_decision", feature_id=feature_id)
        else:
            result["lifecycle_dispositions"][lifecycle_decision].append(feature_id)

        if classification != "normal_flow":
            missing = sorted(boundary_fields.difference(record))
            extra = sorted(set(record).difference(boundary_fields))
            if missing or extra:
                add_error(
                    "boundary_fields",
                    feature_id=feature_id,
                    missing=missing,
                    extra=extra,
                )
            if record.get("required") is not False:
                add_error("boundary_required_false", feature_id=feature_id)
            replacement_feature_id = record.get("replacement_feature_id")
            if not isinstance(replacement_feature_id, str):
                add_error("replacement_feature_id", feature_id=feature_id)
            elif lifecycle_decision == "replace_with_authoritative_mechanism":
                if (
                    replacement_feature_id == feature_id
                    or replacement_feature_id not in features
                ):
                    add_error(
                        "replacement_feature_target",
                        feature_id=feature_id,
                        replacement_feature_id=replacement_feature_id,
                    )
            elif replacement_feature_id:
                add_error(
                    "unexpected_replacement_feature_id",
                    feature_id=feature_id,
                )
            if classification in {"explicit_manual", "external_api", "compatibility"}:
                if lifecycle_decision != "retain_bounded":
                    add_error("bounded_feature_disposition", feature_id=feature_id)
            elif classification == "dormant" and lifecycle_decision not in {
                "replace_with_authoritative_mechanism",
                "retire",
            }:
                add_error("dormant_feature_disposition", feature_id=feature_id)
            elif classification == "deprecated" and lifecycle_decision != "retire":
                add_error("deprecated_feature_disposition", feature_id=feature_id)
            if not isinstance(record.get("boundary_reason"), str) or not record[
                "boundary_reason"
            ].strip():
                add_error("boundary_reason", feature_id=feature_id)
            guard_symbol = record.get("guard_symbol")
            if not isinstance(guard_symbol, str):
                add_error("guard_symbol", feature_id=feature_id)
            elif guard_symbol and guard_symbol not in production_symbols:
                add_error(
                    "guard_symbol_missing",
                    feature_id=feature_id,
                    symbol=guard_symbol,
                )
            elif guard_symbol:
                registered_activation_roots.add(guard_symbol)
            boundary_probe = record.get("boundary_probe")
            if not isinstance(boundary_probe, str) or not boundary_probe:
                add_error("boundary_probe", feature_id=feature_id)
            elif boundary_probe not in probe_symbols:
                add_error(
                    "boundary_probe_missing",
                    feature_id=feature_id,
                    qualname=boundary_probe,
                )
            continue

        normal_flow_ids.add(feature_id)
        missing = sorted(normal_fields.difference(record))
        extra = sorted(set(record).difference(normal_fields))
        if missing or extra:
            add_error(
                "normal_flow_fields",
                feature_id=feature_id,
                missing=missing,
                extra=extra,
            )
        if record.get("required") is not True:
            add_error("normal_flow_required_true", feature_id=feature_id)
        else:
            result["counts"]["required_normal_flow"] += 1
        if lifecycle_decision != "retain_and_integrate":
            add_error("normal_flow_lifecycle_decision", feature_id=feature_id)

        predicate = record.get("activation_predicate")
        if not isinstance(predicate, dict) or set(predicate) != {
            "predicate_id",
            "domain",
            "conditional",
        }:
            add_error("activation_predicate", feature_id=feature_id)
        else:
            predicate_id = predicate.get("predicate_id")
            domain = predicate.get("domain")
            conditional = predicate.get("conditional")
            if not isinstance(predicate_id, str) or re.fullmatch(
                r"[a-z][a-z0-9_]*", predicate_id
            ) is None:
                add_error("activation_predicate_id", feature_id=feature_id)
            else:
                previous = predicate_owners.get(predicate_id)
                if previous is not None and previous != feature_id:
                    add_error(
                        "activation_predicate_duplicate",
                        feature_id=feature_id,
                        predicate_id=predicate_id,
                        previous_feature_id=previous,
                    )
                predicate_owners[predicate_id] = feature_id
            domain_valid = (
                isinstance(domain, list)
                and bool(domain)
                and all(isinstance(item, str) and item for item in domain)
                and len(domain) == len(set(domain))
            )
            if not domain_valid or not isinstance(conditional, bool):
                add_error("activation_predicate_domain", feature_id=feature_id)
            elif conditional and len(domain) < 2:
                add_error(
                    "conditional_predicate_needs_true_false_domain",
                    feature_id=feature_id,
                )
            elif not conditional and domain != ["always"]:
                add_error(
                    "unconditional_predicate_domain",
                    feature_id=feature_id,
                )

        handoff = record.get("typed_handoff")
        validator_symbol = ""
        if not isinstance(handoff, dict) or set(handoff) != {
            "type_id",
            "validator_symbol",
        }:
            add_error("typed_handoff", feature_id=feature_id)
        else:
            type_id = handoff.get("type_id")
            validator_symbol = handoff.get("validator_symbol")
            if not isinstance(type_id, str) or not type_id.strip():
                add_error("handoff_type_id", feature_id=feature_id)
            if not isinstance(validator_symbol, str) or not validator_symbol:
                add_error("validator_symbol", feature_id=feature_id)
                validator_symbol = ""

        effect = record.get("observable_effect")
        if not isinstance(effect, dict) or set(effect) != {
            "effect_id",
            "kind",
            "description",
        }:
            add_error("observable_effect", feature_id=feature_id)
        else:
            if not isinstance(effect.get("effect_id"), str) or re.fullmatch(
                r"[a-z][a-z0-9_]*", effect.get("effect_id", "")
            ) is None:
                add_error("observable_effect_id", feature_id=feature_id)
            if effect.get("kind") not in BEHAVIORAL_EFFECT_KINDS:
                add_error("observable_effect_kind", feature_id=feature_id)
            if not isinstance(effect.get("description"), str) or not effect[
                "description"
            ].strip():
                add_error("observable_effect_description", feature_id=feature_id)

        symbol_fields = {
            "production_entry_symbol": record.get("production_entry_symbol"),
            "producer_symbol": record.get("producer_symbol"),
            "consumer_symbol": record.get("consumer_symbol"),
            "validator_symbol": validator_symbol,
        }
        for field, symbol in symbol_fields.items():
            if not isinstance(symbol, str) or not symbol:
                add_error(field, feature_id=feature_id)
            elif symbol not in production_symbols:
                add_error(
                    f"{field}_missing",
                    feature_id=feature_id,
                    symbol=symbol,
                )
            else:
                registered_activation_roots.add(symbol)

        entry = symbol_fields["production_entry_symbol"]
        producer = symbol_fields["producer_symbol"]
        consumer = symbol_fields["consumer_symbol"]
        validator = symbol_fields["validator_symbol"]
        if (
            isinstance(entry, str)
            and isinstance(producer, str)
            and entry in production_symbols
            and producer in production_symbols
            and (entry, producer) not in call_edges
        ):
            add_error(
                "entry_producer_call_missing",
                feature_id=feature_id,
                caller=entry,
                callee=producer,
            )
        if (
            isinstance(consumer, str)
            and isinstance(validator, str)
            and consumer in production_symbols
            and validator in production_symbols
            and (consumer, validator) not in call_edges
        ):
            add_error(
                "consumer_validator_call_missing",
                feature_id=feature_id,
                caller=consumer,
                callee=validator,
            )

        probes = record.get("probes")
        if not isinstance(probes, dict) or set(probes) != {
            "positive",
            "predicate_false",
            "tamper",
        }:
            add_error("probes", feature_id=feature_id)
        else:
            values = list(probes.values())
            if any(not isinstance(item, str) or not item for item in values):
                add_error("probe_qualname", feature_id=feature_id)
            elif len(values) != len(set(values)):
                add_error("probe_qualname_duplicate", feature_id=feature_id)
            for probe_kind, qualname in probes.items():
                if isinstance(qualname, str) and qualname not in probe_symbols:
                    add_error(
                        "probe_missing",
                        feature_id=feature_id,
                        probe_kind=probe_kind,
                        qualname=qualname,
                    )

    outgoing: dict[str, set[str]] = defaultdict(set)
    for caller, callee in call_edges:
        outgoing[caller].add(callee)
    activated_symbols = set(registered_activation_roots)
    pending = list(sorted(registered_activation_roots))
    while pending:
        caller = pending.pop()
        for callee in sorted(outgoing.get(caller, set())):
            if callee not in activated_symbols:
                activated_symbols.add(callee)
                pending.append(callee)
    unregistered_stateful = sorted(
        set(ast_index.get("public_stateful_symbols", []))
        .difference(activated_symbols)
    )
    result["unregistered_public_state_symbols"] = unregistered_stateful
    for symbol in unregistered_stateful:
        add_error("unregistered_public_state_symbol", symbol=symbol)

    replacement_edges = {
        feature_id: record["replacement_feature_id"]
        for feature_id, record in features.items()
        if isinstance(record, dict)
        and record.get("lifecycle_decision")
        == "replace_with_authoritative_mechanism"
        and isinstance(record.get("replacement_feature_id"), str)
        and record["replacement_feature_id"] in features
        and record["replacement_feature_id"] != feature_id
    }
    for origin in sorted(replacement_edges):
        path: list[str] = []
        positions: dict[str, int] = {}
        current = origin
        while current in replacement_edges:
            if current in positions:
                cycle = path[positions[current] :] + [current]
                add_error(
                    "replacement_feature_cycle",
                    feature_id=origin,
                    cycle=cycle,
                )
                break
            positions[current] = len(path)
            path.append(current)
            current = replacement_edges[current]

    for feature_ids in result["lifecycle_dispositions"].values():
        feature_ids.sort()
    deduplicated = {
        json.dumps(error, ensure_ascii=False, sort_keys=True): error
        for error in result["errors"]
    }
    result["errors"] = [deduplicated[key] for key in sorted(deduplicated)]
    result["behavioral_orphan_features"] = sorted(
        normal_flow_ids.intersection(feature_error_ids)
    )
    result["ok"] = not result["errors"]
    return result


def inventory(root: Path, *, baseline: Path | None, installed: Path | None) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("candidate root must be one safe directory")
    paths = _files(root)
    relative_paths = [_relative(root, path) for path in paths]
    generated = sorted(
        relative
        for relative in relative_paths
        if any(part in GENERATED_PARTS or part.endswith(".pyc") for part in PurePosixPath(relative).parts)
    )
    modules, parse_errors = _parse_modules(root)
    unreferenced_modules = {
        module for module, record in modules.items() if not record["incoming_modules"]
    }
    production_unreferenced_modules = {
        module
        for module, record in modules.items()
        if not record["production_incoming_modules"]
    }
    commands = _command_inventory(root, modules)
    capability_registry = _capability_registry(
        root,
        module_records=modules,
        command_names={item["command_id"] for item in commands["entries"]},
        production_unreferenced_modules=production_unreferenced_modules,
        launcher_paths=_managed_launchers(root),
    )
    behavioral_ast = _behavioral_ast_index(
        root,
        module_records=modules,
        excluded_modules=set(OBSERVATION_ONLY_MODULES),
    )
    behavioral_features = _behavioral_feature_registry(
        root,
        ast_index=behavioral_ast,
        probe_index=_behavioral_probe_symbols(root),
        capability_activation_symbols=capability_registry.get(
            "activation_symbols", []
        ),
    )
    orphan_modules = sorted(
        production_unreferenced_modules.difference(
            capability_registry["classified_standalone_modules"]
        )
    )
    manifest = _manifest(root, relative_paths)
    exact_duplicates = _exact_duplicates(root, paths)
    function_duplicates = _function_duplicates(modules)
    duplicate_adjudication = _duplicate_body_adjudication(
        root, function_duplicates
    )
    errors = [*parse_errors]
    try:
        validate_release_audit_revision_bindings(root)
    except ValueError as exc:
        errors.append(f"release_audit_revision_binding:{exc}")
    errors.extend(
        f"capability_registry:{error}" for error in capability_registry["errors"]
    )
    if not behavioral_features["ok"]:
        errors.append("behavioral_feature_closure_incomplete")
    if not duplicate_adjudication["ok"]:
        errors.append("duplicate_body_adjudication_incomplete")
    if generated:
        errors.append("generated_artifacts_present")
    for key in (
        "parser_without_handler",
        "handler_without_parser",
        "parser_without_role",
        "role_without_parser",
    ):
        if commands[key]:
            errors.append(f"command_closure:{key}")
    warnings = []
    if orphan_modules:
        warnings.append("unclassified_orphan_modules")
    if exact_duplicates:
        warnings.append("exact_duplicate_files")
    if function_duplicates and not duplicate_adjudication["ok"]:
        warnings.append("duplicate_function_bodies")
    if not (manifest["valid_rows"] and manifest["hashes_match"] and manifest["path_set_matches"]):
        warnings.append("manifest_drift")
    version_path = root / "VERSION"
    version = (
        version_path.read_text(encoding="utf-8").strip()
        if version_path.is_file() and not version_path.is_symlink()
        else None
    )
    semantic = {
        "schema_version": 1,
        "contract_revision": RECONNAISSANCE_REVISION,
        "root": str(root),
        "version": version,
        "counts": {
            "files": len(paths),
            "bytes": sum(path.stat().st_size for path in paths),
            "python_modules": len(modules),
            "mathgraph_modules": sum(module.startswith("mathgraph") for module in modules),
            "tests": sum(relative.startswith("tests/test_") and relative.endswith(".py") for relative in relative_paths),
            "generated_artifacts": len(generated),
            "exact_duplicate_groups": len(exact_duplicates),
            "duplicate_function_body_groups": len(function_duplicates),
            "adjudicated_duplicate_function_body_groups": (
                duplicate_adjudication["counts"]["adjudicated"]
            ),
            "orphan_modules": len(orphan_modules),
            "behavioral_orphan_features": len(
                behavioral_features["behavioral_orphan_features"]
            ),
        },
        "generated_artifacts": generated,
        "manifest": manifest,
        "modules": modules,
        "unreferenced_modules": sorted(unreferenced_modules),
        "production_unreferenced_modules": sorted(
            production_unreferenced_modules
        ),
        "orphan_modules": orphan_modules,
        "exact_duplicate_files": exact_duplicates,
        "duplicate_function_bodies": function_duplicates,
        "duplicate_body_adjudication": duplicate_adjudication,
        "commands": commands,
        "capability_registry": capability_registry,
        "behavioral_features": behavioral_features,
        "baseline_comparison": _comparison(root, baseline),
        "installed_comparison": _comparison(root, installed),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "truth_effect": "none",
    }
    return {
        **semantic,
        "inventory_sha256": _sha256(
            json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--baseline-root", type=Path)
    parser.add_argument("--installed-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--quiet",
        action="store_true",
        help=(
            "suppress the full success report; strict failures still emit a "
            "bounded diagnostic summary"
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return nonzero for structural errors (manifest drift remains a warning)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.expanduser().resolve()
    report = inventory(
        root,
        baseline=args.baseline_root.expanduser().resolve() if args.baseline_root else None,
        installed=args.installed_root.expanduser().resolve() if args.installed_root else None,
    )
    payload = _json_bytes(report)
    if args.output:
        output = args.output.expanduser().resolve()
        if output == root or root in output.parents:
            raise ValueError("architecture inventory output must be outside the candidate tree")
        _atomic_write(output, payload)
    strict_failed = bool(args.strict and report["errors"])
    if not args.quiet:
        sys.stdout.buffer.write(payload)
    elif strict_failed:
        failure_summary = {
            "errors": report["errors"],
            "warnings": report["warnings"],
            "inventory_sha256": report["inventory_sha256"],
            "truth_effect": "none",
        }
        sys.stderr.write(_json_bytes(failure_summary).decode("utf-8"))
    return 1 if strict_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
