"""CLAUDE.md §4.1 / §4.6: forbidden-API checks over backend/src, plus scanner self-tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.security.forbidden_apis import is_core_path, scan_source, scan_tree

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
        "import sqlite3",
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
    assert not is_core_path(Path("src/maplegotchi/brain/core.py"))
