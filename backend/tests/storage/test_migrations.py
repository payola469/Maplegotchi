"""Migration framework: ordering, fresh install, upgrade, failure, too-new schemas."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.observations import Metric, ServiceState, Unit
from maplegotchi.core.state import InteractionKind, ReactionKind
from maplegotchi.core.timeline import LifeEvent
from maplegotchi.runtime.clock import FakeClock
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
from tests.persistence_support import (
    TICK,
    make_data_dir,
    new_life,
    open_runtime,
    raw_db,
    run_ticks,
)
from tests.storage.legacy_support import LEGACY_BORN, LEGACY_SEED, write_legacy_life

V1_SQL = MIGRATIONS[0].sql
V2_SQL = MIGRATIONS[1].sql
V3_SQL = MIGRATIONS[2].sql
V4_SQL = MIGRATIONS[3].sql
LATEST = latest_version()
EXPECTED_TABLES = {
    "maple",
    "life_state",
    "interaction_ledger",
    "timeline_event",
    "observation",
    "journal_entry",
    "journal_entry_observation",
    "journal_state",
    "goal",  # v4 (ADR-0028)
    "decision",
    "action_event",
}
EXPECTED_TRIGGERS = {
    "maple_immutable_update",
    "maple_immutable_delete",
    "life_state_no_delete",
    "life_state_revision_advances",
    "life_state_counters_never_decrease",
    "timeline_event_append_only_update",
    "timeline_event_append_only_delete",
    "observation_append_only_update",
    "observation_append_only_delete",
    "journal_entry_append_only_update",
    "journal_entry_append_only_delete",
    "journal_entry_observation_append_only_update",
    "journal_entry_observation_append_only_delete",
    "journal_state_no_delete",
    "goal_append_only_update",  # v4 (ADR-0028)
    "goal_append_only_delete",
    "decision_append_only_update",
    "decision_append_only_delete",
    "action_event_append_only_update",
    "action_event_append_only_delete",
}


def fresh(tmp_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(tmp_path / "fresh.db", isolation_level=None)


def names(conn: sqlite3.Connection, kind: str) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = ?", (kind,)).fetchall()
    return {r[0] for r in rows if not r[0].startswith("sqlite_")}


def test_real_migrations_are_well_ordered() -> None:
    validate_migrations(MIGRATIONS)
    assert [m.version for m in MIGRATIONS] == [1, 2, 3, 4, 5]
    assert LATEST == 5


@pytest.mark.parametrize("versions", [[2], [0, 1], [1, 1], [1, 3], [2, 1], [1, 2, 4]])
def test_validation_rejects_gaps_duplicates_and_disorder(versions: list[int]) -> None:
    with pytest.raises(MigrationError):
        validate_migrations([Migration(v, f"m{v}", "SELECT 1;") for v in versions])


def test_fresh_database_migrates_to_latest(tmp_path: Path) -> None:
    conn = fresh(tmp_path)
    assert schema_version(conn) == 0
    assert migrate(conn) == LATEST
    assert schema_version(conn) == LATEST
    assert conn.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
    assert names(conn, "table") == EXPECTED_TABLES
    assert names(conn, "trigger") == EXPECTED_TRIGGERS
    assert migrate(conn) == LATEST  # idempotent
    conn.close()


@pytest.mark.parametrize("sql", [V1_SQL, V2_SQL, V3_SQL])
def test_splitter_keeps_trigger_bodies_intact(sql: str) -> None:
    statements = split_statements(sql)
    creates = re.findall(r"^CREATE ", sql, flags=re.MULTILINE)
    assert len(statements) == len(creates)
    assert all(s.startswith("CREATE") and s.endswith(";") for s in statements)
    with pytest.raises(MigrationError):
        split_statements("CREATE TABLE t (x INTEGER")


def with_next(sql: str) -> tuple[Migration, ...]:
    return (*MIGRATIONS, Migration(LATEST + 1, "test upgrade", sql))


def test_real_upgrade_from_v1_preserves_a_living_maple(tmp_path: Path) -> None:
    # A Maple born and lived under schema v1, before observations existed. Its rows
    # are written as v1 stored them (current code writes v4 rows).
    data_dir = make_data_dir(tmp_path)
    conn = sqlite3.connect(data_dir.path("maple.db"), isolation_level=None)
    write_legacy_life(conn, version=1, activity="read", location="bookshelf", ticks=29)
    conn.close()

    clock = FakeClock(datetime.fromisoformat(LEGACY_BORN) + TICK * 29)
    with open_runtime(data_dir, clock) as runtime:  # opening migrates v1 -> latest
        state = runtime.state
        assert (state.identity.name, state.rng.seed_hex) == ("Maple", LEGACY_SEED)
        assert state.identity.born_at == datetime.fromisoformat(LEGACY_BORN)
        assert state.rng.tick_counter == 29
        assert runtime.revision == 32
        assert len(runtime.timeline()) == 30
        clock.advance(TICK)
        assert runtime.heartbeat_if_due() is not None  # life continues on the latest
    with raw_db(data_dir) as check:
        assert schema_version(check) == LATEST
        assert "observation" in names(check, "table")


def test_framework_upgrade_to_a_future_version_preserves_life(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 20)
    before = runtime.state
    runtime.close()

    with raw_db(data_dir) as conn:
        assert schema_version(conn) == LATEST
        future = with_next(
            "CREATE TABLE note (id INTEGER PRIMARY KEY, text TEXT NOT NULL) STRICT;\n"
            "ALTER TABLE life_state ADD COLUMN extra INTEGER NOT NULL DEFAULT 0;\n"
        )
        assert migrate(conn, future) == LATEST + 1
        assert "note" in names(conn, "table")
        assert LifeRepository(conn).load().state == before


def test_failed_migration_rolls_back_completely(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 5)
    before = runtime.state
    runtime.close()

    with raw_db(data_dir) as conn:
        broken = with_next(
            "CREATE TABLE half_done (id INTEGER PRIMARY KEY) STRICT;\n"
            "ALTER TABLE no_such_table ADD COLUMN x INTEGER;\n"
        )
        with pytest.raises(MigrationError, match=f"left at v{LATEST}"):
            migrate(conn, broken)
        assert schema_version(conn) == LATEST
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


V1_ACTIVITIES = {"idle", "walk", "sleep", "read", "write", "observe_server", "rest"}
V1_LOCATIONS = {"bed", "desk", "bookshelf", "window", "terminal", "rug"}


def test_frozen_enum_lists_match_core() -> None:
    # v1 is frozen at the v1 sets; activity set v2 (ADR-0028) arrived in migration 4.
    assert _check_values("activity") == V1_ACTIVITIES
    assert _check_values("location") == V1_LOCATIONS
    assert _v4_values("life_state_v4", "activity") == {a.value for a in Activity}
    assert _v4_values("life_state_v4", "location") == {loc.value for loc in RoomLocation}
    assert _check_values("reaction_kind") == {r.value for r in ReactionKind}
    assert _check_values("kind") >= {k.value for k in InteractionKind}
    event_kinds = {"born", "activity_changed", "interaction_accepted", "downtime_gap"}
    assert event_kinds <= set(re.findall(r"'([a-z_]+)'", V1_SQL))
    # Goal-level events arrived with the v4 timeline rebuild (ADR-0028 §2).
    goal_kinds = {"goal_started", "goal_suspended", "goal_resumed", "goal_completed"}
    goal_kinds |= {"goal_abandoned"}
    assert len(LifeEvent.__args__) == len(event_kinds | goal_kinds)
    timeline_v4 = V4_SQL[V4_SQL.index("CREATE TABLE timeline_event_v4") :]
    timeline_v4 = timeline_v4[: timeline_v4.index(") STRICT;")]
    assert set(re.findall(r"'([a-z_]+)'", timeline_v4)) == event_kinds | goal_kinds


def _v2_values(column: str) -> set[str]:
    pattern = rf"\b{column}\s+TEXT\s+(?:NOT NULL\s+)?CHECK \({column} IN\s*\(([^)]*)\)"
    match = re.search(pattern, V2_SQL)
    assert match is not None, column
    return set(re.findall(r"'([a-z_0-9]+)'", match.group(1)))


def test_frozen_observation_lists_match_core() -> None:
    # If an observation enum changes, add a migration rather than editing v2.
    assert _v2_values("metric") == {m.value for m in Metric}
    assert _v2_values("state") == {s.value for s in ServiceState}
    assert _v2_values("unit") == {u.value for u in Unit}


def _v3_values(column: str) -> set[str]:
    pattern = rf"\b{column}\s+TEXT\s+NOT NULL CHECK \({column} IN\s*\(([^)]*)\)"
    match = re.search(pattern, V3_SQL)
    assert match is not None, column
    return set(re.findall(r"'([a-z_0-9]+)'", match.group(1)))


def test_frozen_journal_lists_match_core() -> None:
    from maplegotchi.core.journal import BrainKind, Importance, JournalCategory, TriggerKind
    from maplegotchi.core.state import Expression

    assert _v3_values("category") == {c.value for c in JournalCategory}
    assert _v3_values("trigger_kind") == {t.value for t in TriggerKind}
    assert _v3_values("importance") == {i.value for i in Importance}
    assert _v3_values("brain_kind") == {b.value for b in BrainKind}
    assert _v3_values("activity") == V1_ACTIVITIES  # frozen; v4 rebuilt the table
    assert _v4_values("journal_entry_v4", "activity") == {a.value for a in Activity}
    assert _v3_values("expression") == {e.value for e in Expression}


def _v4_values(table: str, column: str) -> set[str]:
    """A CHECK list in the v4 rebuild of `table` (constants expanded as in the SQL)."""
    body = V4_SQL[V4_SQL.index(f"CREATE TABLE {table} (") :]
    body = body[: body.index(") STRICT;")]
    pattern = rf"\b{column}\s+TEXT\s+NOT NULL CHECK \({column} IN\s*\(([^)]*)\)"
    match = re.search(pattern, body)
    assert match is not None, (table, column)
    return set(re.findall(r"'([a-z_0-9]+)'", match.group(1)))
