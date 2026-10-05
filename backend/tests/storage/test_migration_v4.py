"""Schema v4 (ADR-0028): conversion, preservation, snapshot, failure and refusal rules (R2-R7)."""

from __future__ import annotations

import importlib.util
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.state import MapleState
from maplegotchi.core.timeline import Born
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.storage.datadir import DataDir
from maplegotchi.storage.db import (
    PRE_MIGRATION_DIR,
    PreMigrationSnapshotError,
    open_life_database,
)
from maplegotchi.storage.errors import MigrationError, SchemaTooNewError
from maplegotchi.storage.migrations import MIGRATIONS, latest_version, migrate, schema_version
from maplegotchi.storage.repositories import LifeRepository
from tests.persistence_support import make_data_dir, open_runtime, raw_db
from tests.storage.legacy_support import LEGACY_BORN, LEGACY_SEED, write_legacy_life

REPO = Path(__file__).resolve().parents[3]
BORN = datetime.fromisoformat(LEGACY_BORN)
TICKS = 12
LAST = BORN + timedelta(minutes=5 * TICKS)


def _snapshot_tool() -> Any:
    script = REPO / "deploy" / "backup" / "maple_db_snapshot.py"
    spec = importlib.util.spec_from_file_location("maple_db_snapshot", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def legacy_dir(tmp_path: Path, *, version: int = 3, **kwargs: Any) -> DataDir:
    data_dir = make_data_dir(tmp_path)
    conn = sqlite3.connect(data_dir.path("maple.db"), isolation_level=None)
    write_legacy_life(conn, version=version, ticks=TICKS, **kwargs)
    conn.close()
    return data_dir


def preserved(data_dir: DataDir) -> dict[str, object]:
    with raw_db(data_dir) as conn:
        return {
            "maple": conn.execute("SELECT * FROM maple").fetchall(),
            "counters": conn.execute(
                "SELECT revision, tick_counter, interaction_counter, mood, energy, curiosity,"
                " social, activity_started_at, activity_until, last_tick_at, last_updated_at"
                " FROM life_state"
            ).fetchall(),
            "ledger": conn.execute("SELECT * FROM interaction_ledger").fetchall(),
            "timeline": conn.execute("SELECT * FROM timeline_event ORDER BY id").fetchall(),
            "observations": conn.execute("SELECT * FROM observation ORDER BY id").fetchall(),
            "journal": conn.execute("SELECT * FROM journal_entry ORDER BY id").fetchall(),
            "refs": conn.execute("SELECT * FROM journal_entry_observation").fetchall(),
            "journal_state": conn.execute("SELECT * FROM journal_state").fetchall(),
        }


def snapshots(data_dir: DataDir) -> list[Path]:
    folder = data_dir.root / PRE_MIGRATION_DIR
    return sorted(folder.glob("*.db")) if folder.exists() else []


def test_v3_life_migrates_with_identity_seed_counters_and_history_intact(tmp_path: Path) -> None:
    data_dir = legacy_dir(tmp_path)
    before = preserved(data_dir)
    with open_runtime(data_dir, FakeClock(LAST)) as runtime:
        state = runtime.state
        assert state.identity.name == "Maple"
        assert state.identity.born_at == BORN
        assert state.rng.seed_hex == LEGACY_SEED
        assert state.rng.tick_counter == TICKS
        assert state.rng.interaction_counter == 2
        assert runtime.revision == TICKS + 3
        assert [r.kind.value for r in state.recent_interactions] == ["greet", "pet"]
    after = preserved(data_dir)
    assert after == before  # every preserved row, byte for byte (incl. ids)
    with raw_db(data_dir) as conn:
        assert schema_version(conn) == latest_version()
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


@pytest.mark.parametrize(
    ("activity", "old_location", "new_location"),
    [
        ("rest", "bed", RoomLocation.SOFA),
        ("rest", "rug", RoomLocation.SOFA),
        ("idle", "window", RoomLocation.RUG),
        ("idle", "rug", RoomLocation.RUG),
        ("walk", "desk", RoomLocation.RUG),
        ("walk", "bookshelf", RoomLocation.RUG),
        ("sleep", "bed", RoomLocation.BED),
        ("write", "desk", RoomLocation.DESK),
        ("observe_server", "terminal", RoomLocation.TERMINAL),
        ("read", "bookshelf", RoomLocation.BOOKSHELF),
    ],
)
def test_v3_locations_are_converted_to_their_v4_furniture(
    tmp_path: Path, activity: str, old_location: str, new_location: RoomLocation
) -> None:
    data_dir = legacy_dir(tmp_path, activity=activity, location=old_location)
    with open_runtime(data_dir, FakeClock(LAST)) as runtime:
        state = runtime.state
        assert state.activity is Activity(activity)
        assert state.location is new_location
        assert state.route is None and state.point_id is None  # canonical point, no walk
        assert state.point.location is new_location
        # No event is fabricated for the conversion.
        assert len(runtime.timeline()) == TICKS + 1


def test_new_rows_continue_the_preserved_id_sequences(tmp_path: Path) -> None:
    data_dir = legacy_dir(tmp_path)
    clock = FakeClock(LAST)
    with open_runtime(data_dir, clock) as runtime:
        clock.advance(timedelta(minutes=30))
        assert runtime.heartbeat_if_due() is not None
        ids = [e.id for e in runtime.timeline()]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    assert ids[: TICKS + 1] == list(range(1, TICKS + 2))


def test_migrating_an_existing_database_first_writes_a_verified_snapshot(tmp_path: Path) -> None:
    data_dir = legacy_dir(tmp_path)
    before = preserved(data_dir)
    with open_runtime(data_dir, FakeClock(LAST)):
        pass
    [copy] = snapshots(data_dir)
    assert copy.name.startswith("maple.v3.20260101T010000Z.")
    assert not list((data_dir.root / PRE_MIGRATION_DIR).glob("*.partial*"))
    tool = _snapshot_tool()
    report = tool.verify(copy)
    assert report["user_version"] == 3
    # The copy is a complete, working v3 life: the previous release's schema and data.
    conn = sqlite3.connect(copy, isolation_level=None)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert migrate(conn, MIGRATIONS[:3]) == 3  # nothing to do for v3 code
        assert conn.execute("SELECT * FROM maple").fetchall() == before["maple"]
        assert (
            conn.execute("SELECT * FROM timeline_event ORDER BY id").fetchall()
            == (before["timeline"])
        )
        assert conn.execute("SELECT location FROM life_state").fetchone()[0] == "bed"
    finally:
        conn.close()


def test_birth_and_already_migrated_opens_take_no_snapshot(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    clock = FakeClock(BORN)
    with open_runtime(data_dir, clock):
        pass
    with open_runtime(data_dir, clock):
        pass
    assert snapshots(data_dir) == []


def test_failed_snapshot_refuses_migration_and_leaves_the_database_untouched(
    tmp_path: Path,
) -> None:
    data_dir = legacy_dir(tmp_path)
    original = (data_dir.root / "maple.db").read_bytes()
    (data_dir.root / PRE_MIGRATION_DIR).write_text("not a directory")
    with pytest.raises(PreMigrationSnapshotError):
        open_runtime(data_dir, FakeClock(LAST))
    assert (data_dir.root / "maple.db").read_bytes() == original
    with raw_db(data_dir) as conn:
        assert schema_version(conn) == 3


def test_snapshot_that_fails_verification_refuses_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = legacy_dir(tmp_path)
    calls = {"n": 0}

    def flaky(conn: sqlite3.Connection) -> int:
        # Calls: open_life_database, snapshot source, snapshot copy -> the copy "lies".
        calls["n"] += 1
        version = schema_version(conn)
        return version + 1 if calls["n"] == 3 else version

    def no_birth() -> tuple[MapleState, Born]:
        raise AssertionError("an existing database is never reborn")

    monkeypatch.setattr("maplegotchi.storage.db.schema_version", flaky)
    with pytest.raises(PreMigrationSnapshotError):
        open_life_database(data_dir, no_birth)
    monkeypatch.undo()
    assert snapshots(data_dir) == []
    assert not list((data_dir.root / PRE_MIGRATION_DIR).iterdir())
    with raw_db(data_dir) as conn:
        assert schema_version(conn) == 3


def test_failure_inside_the_v4_migration_rolls_back_to_v3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = legacy_dir(tmp_path)
    before = preserved(data_dir)

    def corrupt_verify(conn: sqlite3.Connection, captured: object) -> None:
        raise MigrationError("injected")

    broken = (*MIGRATIONS[:3], MIGRATIONS[3].__class__(
        4, MIGRATIONS[3].name, MIGRATIONS[3].sql, rebuilds_tables=True,
        capture=MIGRATIONS[3].capture, verify=corrupt_verify,
    ))  # fmt: skip
    monkeypatch.setattr("maplegotchi.storage.migrations.MIGRATIONS", broken)
    monkeypatch.setattr("maplegotchi.storage.db.migrate", lambda conn: migrate(conn, broken))
    with pytest.raises(MigrationError, match="left at v3"):
        open_runtime(data_dir, FakeClock(LAST))
    monkeypatch.undo()
    assert len(snapshots(data_dir)) == 1  # R2 copy was taken first and is kept
    with raw_db(data_dir) as conn:
        assert schema_version(conn) == 3
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 0  # raw connection default
        assert "goal" not in {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert preserved(data_dir) == before
    with open_runtime(data_dir, FakeClock(LAST)) as runtime:  # the fixed code migrates fine
        assert runtime.state.rng.seed_hex == LEGACY_SEED


def test_verify_detects_a_changed_preserved_row(tmp_path: Path) -> None:
    data_dir = legacy_dir(tmp_path)
    v4 = MIGRATIONS[3]
    assert v4.capture is not None and v4.verify is not None
    with raw_db(data_dir) as conn:
        before = v4.capture(conn)
        conn.execute("DROP TRIGGER timeline_event_append_only_delete")
        conn.execute("DELETE FROM timeline_event WHERE id = 3")
        with pytest.raises(MigrationError, match="timeline"):
            v4.verify(conn, before)


def test_v3_code_refuses_a_v4_database(tmp_path: Path) -> None:
    data_dir = legacy_dir(tmp_path)
    with open_runtime(data_dir, FakeClock(LAST)):
        pass
    with raw_db(data_dir) as conn, pytest.raises(SchemaTooNewError):
        migrate(conn, MIGRATIONS[:3])


def test_foreign_keys_are_restored_after_the_rebuild(tmp_path: Path) -> None:
    data_dir = legacy_dir(tmp_path)
    conn = sqlite3.connect(data_dir.path("maple.db"), isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        assert migrate(conn) == latest_version()
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        repo = LifeRepository(conn)
        assert repo.load().state.rng.seed_hex == LEGACY_SEED
    finally:
        conn.close()
