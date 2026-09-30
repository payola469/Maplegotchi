"""Migration framework: ordering, fresh install, upgrade, failure, too-new schemas."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.state import InteractionKind, ReactionKind
from maplegotchi.core.timeline import LifeEvent
from maplegotchi.storage.errors import MigrationError, SchemaTooNewError
from maplegotchi.storage.migrations import (
    APPLICATION_ID,
    MIGRATIONS,
    Migration,
    latest_version,
    migrate,
    schema_version,
    split_statements,
    validate_migrations,
)
from maplegotchi.storage.repositories import LifeRepository
from tests.persistence_support import new_life, raw_db, run_ticks

V1_SQL = MIGRATIONS[0].sql
EXPECTED_TABLES = {"maple", "life_state", "interaction_ledger", "timeline_event"}
EXPECTED_TRIGGERS = {
    "maple_immutable_update",
    "maple_immutable_delete",
    "life_state_no_delete",
    "life_state_revision_advances",
    "life_state_counters_never_decrease",
    "timeline_event_append_only_update",
    "timeline_event_append_only_delete",
}


def fresh(tmp_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(tmp_path / "fresh.db", isolation_level=None)


def names(conn: sqlite3.Connection, kind: str) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = ?", (kind,)).fetchall()
    return {r[0] for r in rows if not r[0].startswith("sqlite_")}


def test_real_migrations_are_well_ordered() -> None:
    validate_migrations(MIGRATIONS)
    assert [m.version for m in MIGRATIONS] == [1]
    assert latest_version() == 1


@pytest.mark.parametrize("versions", [[2], [0, 1], [1, 1], [1, 3], [2, 1], [1, 2, 4]])
def test_validation_rejects_gaps_duplicates_and_disorder(versions: list[int]) -> None:
    with pytest.raises(MigrationError):
        validate_migrations([Migration(v, f"m{v}", "SELECT 1;") for v in versions])


def test_fresh_database_migrates_to_latest(tmp_path: Path) -> None:
    conn = fresh(tmp_path)
    assert schema_version(conn) == 0
    assert migrate(conn) == 1
    assert schema_version(conn) == 1
    assert conn.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
    assert names(conn, "table") == EXPECTED_TABLES
    assert names(conn, "trigger") == EXPECTED_TRIGGERS
    assert migrate(conn) == 1  # idempotent
    conn.close()


def test_splitter_keeps_trigger_bodies_intact() -> None:
    statements = split_statements(V1_SQL)
    creates = re.findall(r"^CREATE ", V1_SQL, flags=re.MULTILINE)
    assert len(statements) == len(creates)
    assert all(s.startswith("CREATE") and s.endswith(";") for s in statements)
    with pytest.raises(MigrationError):
        split_statements("CREATE TABLE t (x INTEGER")


def with_v2(sql: str) -> tuple[Migration, ...]:
    return (*MIGRATIONS, Migration(2, "test upgrade", sql))


def test_upgrade_from_earliest_schema_preserves_life(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 20)
    before = runtime.state
    runtime.close()

    with raw_db(data_dir) as conn:
        assert schema_version(conn) == 1
        v2 = with_v2(
            "CREATE TABLE note (id INTEGER PRIMARY KEY, text TEXT NOT NULL) STRICT;\n"
            "ALTER TABLE life_state ADD COLUMN extra INTEGER NOT NULL DEFAULT 0;\n"
        )
        assert migrate(conn, v2) == 2
        assert "note" in names(conn, "table")
        assert LifeRepository(conn).load().state == before


def test_failed_migration_rolls_back_completely(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 5)
    before = runtime.state
    runtime.close()

    with raw_db(data_dir) as conn:
        broken = with_v2(
            "CREATE TABLE half_done (id INTEGER PRIMARY KEY) STRICT;\n"
            "ALTER TABLE no_such_table ADD COLUMN x INTEGER;\n"
        )
        with pytest.raises(MigrationError, match="left at v1"):
            migrate(conn, broken)
        assert schema_version(conn) == 1
        assert "half_done" not in names(conn, "table")
        assert not conn.in_transaction
        assert LifeRepository(conn).load().state == before


def test_newer_schema_is_refused(tmp_path: Path) -> None:
    conn = fresh(tmp_path)
    migrate(conn)
    conn.execute("PRAGMA user_version = 7")
    with pytest.raises(SchemaTooNewError):
        migrate(conn)
    conn.close()


def _check_values(column: str) -> set[str]:
    match = re.search(rf"{column}\s+TEXT\s+NOT NULL CHECK \({column} IN\s*\(([^)]*)\)", V1_SQL)
    if match is None:
        match = re.search(rf"{column}\s+TEXT\s+CHECK \({column} IN\s*\(([^)]*)\)", V1_SQL)
    assert match is not None, column
    return set(re.findall(r"'([a-z_]+)'", match.group(1)))


def test_frozen_enum_lists_match_core() -> None:
    # If an enum changes, this fails: add a new migration rather than editing v1.
    assert _check_values("activity") == {a.value for a in Activity}
    assert _check_values("location") == {loc.value for loc in RoomLocation}
    assert _check_values("reaction_kind") == {r.value for r in ReactionKind}
    assert _check_values("kind") >= {k.value for k in InteractionKind}
    event_kinds = {"born", "activity_changed", "interaction_accepted", "downtime_gap"}
    assert len(LifeEvent.__args__) == len(event_kinds)
    assert event_kinds <= set(re.findall(r"'([a-z_]+)'", V1_SQL))
