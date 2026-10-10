"""Explicitly isolated fixtures: no environment config, production paths or real clock."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.world.oracle import Oracle, load_spec


@pytest.fixture
def spec_oracle() -> Oracle:
    return load_spec()


@pytest.fixture
def scratch_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Set a decoy before opening any database, proving the fixture ignores config.
    monkeypatch.setenv("MAPLE_DATA_DIR", str(tmp_path / "must-not-be-used"))
    root = tmp_path / "world-harness"
    root.mkdir(mode=0o700)
    return root


@pytest.fixture
def scratch_database(scratch_root: Path) -> Iterator[sqlite3.Connection]:
    path = scratch_root / "scratch.db"
    with path.open("xb"):
        pass
    conn = sqlite3.connect(f"{path.as_uri()}?mode=rw", uri=True, isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    finally:
        conn.close()
