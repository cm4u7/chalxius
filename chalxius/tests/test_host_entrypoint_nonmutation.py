from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import mathgraph.runtime_cutover as runtime_cutover_module


SOURCE_SCRIPTS = Path(runtime_cutover_module.__file__).resolve().parents[1]


class HostEntrypointNonMutationTests(unittest.TestCase):
    def test_default_python_entrypoints_do_not_create_bytecode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            shutil.copytree(
                SOURCE_SCRIPTS,
                scripts,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            environment = dict(os.environ)
            environment.pop("PYTHONDONTWRITEBYTECODE", None)
            environment.pop("PYTHONPYCACHEPREFIX", None)
            for name in (
                "archive_runtime.py",
                "chx_ledger.py",
                "runtime_cutover.py",
            ):
                outcome = subprocess.run(
                    [sys.executable, str(scripts / name), "--help"],
                    cwd=root,
                    env=environment,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertEqual(outcome.returncode, 0, outcome.stdout)
            self.assertEqual(list(root.rglob("__pycache__")), [])
            self.assertEqual(list(root.rglob("*.pyc")), [])


if __name__ == "__main__":
    unittest.main()
