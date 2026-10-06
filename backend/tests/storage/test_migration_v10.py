"""Schema v10 (ADR-0034): nullable reply latency, forward-only, with a pre-migration copy."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from maplegotchi.runtime.clock import FakeClock
from maplegotchi.storage.db import PRE_MIGRATION_DIR
from maplegotchi.storage.errors import SchemaTooNewError
from maplegotchi.storage.migrations import MIGRATIONS, migrate, schema_version
from tests.persistence_support import BIRTH, make_data_dir, open_runtime, raw_db
from tests.storage.legacy_support import LEGACY_BORN, write_legacy_life

AT = "2026-01-01T03:00:00+00:00"


def _v9_life_with_a_conversation(conn: sqlite3.Connection) -> None:
    """A Maple stored by a v9 release, with one exchange (no latency column yet)."""
    write_legacy_life(conn, version=3)
    assert migrate(conn, MIGRATIONS[:9]) == 9
    conn.execute(
        "INSERT INTO conversation_message (maple_id, revision, at, channel, direction, speaker,"
        " external_id, text) VALUES (1, 1, ?, 'discord', 'in', 'paolo', '42', 'Hi Maple')",
        (AT,),
    )
    conn.execute(
        "INSERT INTO conversation_message (maple_id, revision, at, channel, direction, speaker,"
        " reply_to, text, replier_kind, replier_name, fallback_code)"
        " VALUES (1, 1, ?, 'discord', 'out', 'maple', 1, 'Hello!', 'rule', 'rule_replier',"
        " 'timeout')",
        (AT,),
    )


def _columns(conn: sqlite3.Connection) -> list[str]:
    return [r[1] for r in conn.execute("PRAGMA table_info(conversation_message)")]


def test_v10_is_the_latest_and_only_adds_a_column() -> None:
    assert [m.version for m in MIGRATIONS][-1] == 10
    v10 = MIGRATIONS[9]
    assert not v10.rebuilds_tables
    assert "ADD COLUMN latency_ms" in v10.sql and "DROP" not in v10.sql


def test_v9_database_upgrades_automatically_and_keeps_old_rows(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    conn = sqlite3.connect(data_dir.path("maple.db"), isolation_level=None)
    _v9_life_with_a_conversation(conn)
    before = conn.execute("SELECT * FROM conversation_message ORDER BY id").fetchall()
    conn.close()

    clock = FakeClock(datetime.fromisoformat(LEGACY_BORN) + timedelta(hours=4))
    with open_runtime(data_dir, clock) as runtime:
        stored = runtime.messages(limit=10)
        assert [m.latency_ms for m in stored] == [None, None]  # old rows stay valid
        assert stored[1].fallback_code == "timeout"
    with raw_db(data_dir) as conn:
        assert schema_version(conn) == 10
        assert "latency_ms" in _columns(conn)
        after = conn.execute("SELECT * FROM conversation_message ORDER BY id").fetchall()
        assert [row[:-1] for row in after] == before  # every v9 value unchanged
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    copies = list((data_dir.root / PRE_MIGRATION_DIR).glob("maple.v9.*.db"))
    assert len(copies) == 1
    copy = sqlite3.connect(copies[0], isolation_level=None)
    try:
        assert schema_version(copy) == 9 and "latency_ms" not in _columns(copy)
    finally:
        copy.close()


def test_an_existing_v10_database_opens_without_another_migration(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    open_runtime(data_dir, FakeClock(BIRTH)).close()
    with open_runtime(data_dir, FakeClock(BIRTH + timedelta(hours=1))):
        pass
    with raw_db(data_dir) as conn:
        assert schema_version(conn) == 10
    assert not (data_dir.root / PRE_MIGRATION_DIR).exists() or not list(
        (data_dir.root / PRE_MIGRATION_DIR).iterdir()
    )


def test_a_v9_release_refuses_a_v10_database(tmp_path: Path) -> None:
    """Rollback across v10 is a restore of the pre-migration copy, never a downgrade."""
    conn = sqlite3.connect(tmp_path / "v10.db", isolation_level=None)
    try:
        assert migrate(conn) == 10
        with pytest.raises(SchemaTooNewError):
            migrate(conn, MIGRATIONS[:9])
    finally:
        conn.close()


@pytest.mark.parametrize("latency", [-1, 600001])
def test_latency_must_be_in_range(tmp_path: Path, latency: int) -> None:
    conn = sqlite3.connect(tmp_path / "v10.db", isolation_level=None)
    try:
        _v9_life_with_a_conversation(conn)
        assert migrate(conn) == 10
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO conversation_message (maple_id, revision, at, channel, direction,"
                " speaker, reply_to, text, replier_kind, replier_name, latency_ms)"
                " VALUES (1, 1, ?, 'discord', 'out', 'maple', 1, 'Hi', 'external', 'x', ?)",
                (AT, latency),
            )
    finally:
        conn.close()
