"""Scratch-only storage and sanitized evidence; no production configuration is read."""

from __future__ import annotations

import json
import random
import sqlite3
from pathlib import Path

import pytest

from maplegotchi.storage.migrations import migrate, schema_version
from tests.world.harness import Evidence, capture_evidence, cell_cases
from tests.world.oracle import Oracle


def test_scratch_database_is_isolated_v10(
    scratch_database: sqlite3.Connection, scratch_root: Path
) -> None:
    actual = Path(scratch_database.execute("PRAGMA database_list").fetchone()[2])
    assert actual == scratch_root / "scratch.db"
    assert migrate(scratch_database) == 10
    assert schema_version(scratch_database) == 10
    assert scratch_database.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert scratch_database.execute("SELECT count(*) FROM maple").fetchone()[0] == 0
    assert not (scratch_root.parent / "must-not-be-used").exists()


def test_scratch_roots_are_distinct(
    scratch_root: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    other = tmp_path_factory.mktemp("other-world-harness")
    assert other != scratch_root and not (other / "scratch.db").exists()


def test_seeded_cases_are_complete_and_do_not_touch_global_rng(spec_oracle: Oracle) -> None:
    before = random.getstate()
    cases = cell_cases(spec_oracle)
    assert cases == cell_cases(spec_oracle)
    assert cases != cell_cases(spec_oracle, seed=102)
    assert (
        len(cases)
        == len(set(cases))
        == sum(len(row) for table in spec_oracle.tables for row in table.rows)
    )
    assert random.getstate() == before


def test_evidence_is_allowlisted_and_never_overwritten(scratch_root: Path) -> None:
    evidence = Evidence("oracle", passed=7, failed=0)
    path = capture_evidence(scratch_root, evidence)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "check": "oracle",
        "passed": 7,
        "failed": 0,
    }
    with pytest.raises(FileExistsError):
        capture_evidence(scratch_root, evidence)
    assert json.loads(path.read_text(encoding="utf-8"))["passed"] == 7


def test_invalid_evidence_does_not_create_file(scratch_root: Path) -> None:
    with pytest.raises(ValueError, match="negative"):
        capture_evidence(scratch_root, Evidence("fixtures", -1, 0))
    assert not (scratch_root / "evidence.json").exists()
