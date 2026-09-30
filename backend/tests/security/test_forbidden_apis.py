"""CLAUDE.md §4.1 / §4.6: forbidden-API checks over backend/src, plus scanner self-tests."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.security.forbidden_apis import is_core_path, is_storage_path, scan_source, scan_tree

SRC = Path(__file__).resolve().parents[2] / "src"


def test_source_tree_has_no_forbidden_apis() -> None:
    scanned, violations = scan_tree(SRC)
    assert scanned > 0, f"scanner found no Python files under {SRC}"
    assert violations == [], "\n".join(str(v) for v in violations)


@pytest.mark.parametrize(
    "source",
    [
        "import subprocess",
        "import subprocess as sp",
        "from subprocess import run",
        "import multiprocessing.pool",
        "import pty",
        "import os\nos.system('x')",
        "import os as o\no.popen('x')",
        "from os import system",
        "import os\nos.execv('x', [])",
        "import os\nos.spawnl(0, 'x')",
        "import os\nos.kill(1, 9)",
        "import os\nf = os.system",
        "import asyncio\nasyncio.create_subprocess_shell('x')",
        "import shutil\nshutil.rmtree('x')",
        "import importlib\nimportlib.import_module('x')",
        "eval('1')",
        "exec('x = 1')",
        "compile('1', 'f', 'eval')",
        "__import__('os')",
        "run('x', shell=True)",
    ],
)
def test_scanner_flags_forbidden_everywhere(source: str) -> None:
    assert scan_source(source), f"not flagged: {source!r}"


@pytest.mark.parametrize(
    "source",
    [
        "x = 1",
        "import os\nos.getpid()",
        "import os.path\nos.path.join('a', 'b')",
        "from pathlib import Path\nPath('a')",
        "run('x', shell=False)",
        "from datetime import datetime\ndatetime.now()",
    ],
)
def test_scanner_allows_ordinary_code_outside_core(source: str) -> None:
    assert scan_source(source) == []


@pytest.mark.parametrize(
    "source",
    [
        "import os",
        "import random",
        "from time import monotonic",
        "import sqlite3",
        "import asyncio",
        "import psutil",
        "from pathlib import Path",
        "from datetime import datetime\ndatetime.now()",
        "from datetime import datetime as dt\ndt.utcnow()",
        "import datetime\ndatetime.datetime.today()",
        "from datetime import date\ndate.today()",
        "open('x')",
    ],
)
def test_scanner_flags_impurity_in_core(source: str) -> None:
    assert scan_source(source, core=True), f"not flagged in core: {source!r}"


@pytest.mark.parametrize(
    "source",
    [
        "from datetime import datetime, timedelta\n"
        "def later(now: datetime) -> datetime:\n    return now + timedelta(seconds=300)",
        "from dataclasses import dataclass",
        "import enum",
        "from typing import Protocol",
    ],
)
def test_scanner_allows_pure_code_in_core(source: str) -> None:
    assert scan_source(source, core=True) == []


def test_core_path_detection() -> None:
    assert is_core_path(Path("src/maplegotchi/core/state.py"))
    assert is_core_path(Path("src/maplegotchi/core/__init__.py"))
    assert not is_core_path(Path("src/maplegotchi/storage/db.py"))
    assert is_core_path(Path("src/maplegotchi/brain/rule_brain.py"))  # brains are pure too
    assert not is_core_path(Path("src/maplegotchi/runtime/core.py"))


# Core may import only these (CLAUDE.md §3.3, §5). Anything else needs a review.
CORE_IMPORT_ALLOWLIST = frozenset(
    {
        "__future__",
        "collections",
        "dataclasses",
        "datetime",
        "enum",
        "hashlib",
        "math",
        "re",  # pure, deterministic validation of codes (Phase 3 observations)
        "types",
        "typing",
        "maplegotchi",
    }
)


def test_core_modules_are_scanned_with_core_rules() -> None:
    core_files = sorted((SRC / "maplegotchi" / "core").rglob("*.py"))
    assert len(core_files) >= 10
    assert all(is_core_path(p) for p in core_files)


def test_core_imports_only_allowlisted_modules() -> None:
    offenders: list[str] = []
    pure_files = [
        *sorted((SRC / "maplegotchi" / "core").rglob("*.py")),
        *sorted((SRC / "maplegotchi" / "brain").rglob("*.py")),
    ]
    for path in pure_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module]
            else:
                continue
            for module in modules:
                top = module.split(".", 1)[0]
                if top not in CORE_IMPORT_ALLOWLIST:
                    offenders.append(f"{path.name}:{node.lineno}: {module}")
                elif top == "maplegotchi" and not module.startswith(
                    ("maplegotchi.core", "maplegotchi.brain")
                ):
                    offenders.append(f"{path.name}:{node.lineno}: {module}")
    assert offenders == []


# ---------------------------------------------------------------- storage-only writes


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3",
        "import shutil",
        "import tempfile",
        "open('x', 'w')",
        "open('x')",
        "import os\nos.remove('x')",
        "import os\nos.replace('a', 'b')",
        "import os\nos.link('a', 'b')",
        "from os import makedirs",
        "from pathlib import Path\nPath('x').write_text('y')",
        "p.write_bytes(b'')",
        "p.unlink()",
        "p.mkdir(parents=True)",
        "p.touch()",
        "p.rename('q')",
        "p.symlink_to('q')",
    ],
)
def test_writes_are_flagged_outside_storage(source: str) -> None:
    assert scan_source(source), f"not flagged outside storage: {source!r}"
    assert scan_source(source, writer=True) == [], f"wrongly flagged in storage: {source!r}"


@pytest.mark.parametrize("source", ["'a'.replace('a', 'b')", "p.exists()", "p.read_text()"])
def test_reads_and_str_methods_are_not_writes(source: str) -> None:
    assert scan_source(source) == []


def test_storage_path_detection() -> None:
    assert is_storage_path(Path("src/maplegotchi/storage/db.py"))
    assert not is_storage_path(Path("src/maplegotchi/runtime/life.py"))
    assert not is_storage_path(Path("src/maplegotchi/core/storage.py"))
