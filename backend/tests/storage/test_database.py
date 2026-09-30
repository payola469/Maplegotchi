"""Database opening: pragmas, WAL behavior, schema guards, birth-once, corruption policy."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from maplegotchi.core.state import InteractionKind
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.life import LifeRuntime
from maplegotchi.storage import db as storage_db
from maplegotchi.storage.db import BIRTH_PREFIX, DB_FILENAME, open_life_database
from maplegotchi.storage.errors import (
    CorruptDatabaseError,
    NotAMapleDatabaseError,
    SchemaTooNewError,
    StorageError,
)
from maplegotchi.storage.migrations import migrate
from maplegotchi.storage.repositories import LifeRepository
from tests.persistence_support import (
    BIRTH,
    PARAMS,
    SEED,
    TICK,
    make_data_dir,
    new_life,
    open_runtime,
    raw_db,
    run_ticks,
)

# ---------------------------------------------------------------- connection settings


def test_database_lives_in_data_dir_with_expected_settings(tmp_path: Path) -> None:
    data_dir, _, runtime = new_life(tmp_path)
    with runtime:
        assert (data_dir.root / DB_FILENAME).is_file()
        conn = runtime._repository()._conn  # inspecting settings of the real connection
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2  # FULL
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA trusted_schema").fetchone()[0] == 0
    leftovers = {p.name for p in data_dir.root.iterdir()}
    assert leftovers <= {DB_FILENAME, f"{DB_FILENAME}-wal", f"{DB_FILENAME}-shm"}


def test_wal_readers_see_last_commit_while_a_write_is_in_progress(tmp_path: Path) -> None:
    data_dir, _, runtime = new_life(tmp_path)
    runtime.close()
    with raw_db(data_dir) as writer, raw_db(data_dir) as reader:
        writer.execute("PRAGMA journal_mode = WAL")
        before = reader.execute("SELECT mood FROM life_state").fetchone()[0]
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("UPDATE life_state SET revision = revision + 1, mood = 1.5")
        # Not blocked, and sees the last committed snapshot, not the pending write.
        assert reader.execute("SELECT mood FROM life_state").fetchone()[0] == before
        writer.execute("COMMIT")
        assert reader.execute("SELECT mood FROM life_state").fetchone()[0] == 1.5


def test_foreign_keys_and_protective_triggers(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 3)
    runtime.close()
    with raw_db(data_dir) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        attacks = [
            "INSERT INTO interaction_ledger VALUES (2, 0, 'greet', '2026-01-01T00:00:00+00:00')",
            "UPDATE maple SET name = 'Impostor'",
            "UPDATE maple SET life_seed = '" + "0" * 64 + "'",
            "DELETE FROM maple",
            "DELETE FROM life_state",
            "UPDATE life_state SET revision = revision + 2",
            "UPDATE life_state SET revision = revision - 1",
            "UPDATE life_state SET revision = revision + 1, tick_counter = 0",
            "UPDATE timeline_event SET kind = 'born'",
            "DELETE FROM timeline_event",
            "INSERT INTO timeline_event (maple_id, revision, kind, at, payload)"
            " VALUES (1, 1, 'born', '2026-01-01T00:00:00+00:00', '{}')",
            "UPDATE life_state SET revision = revision + 1, mood = 101",
            "UPDATE life_state SET revision = revision + 1, activity = 'dance'",
            "UPDATE life_state SET revision = revision + 1, last_tick_at = '2026-01-01 00:00'",
        ]
        for sql in attacks:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(sql)


# ---------------------------------------------------------------- birth exactly once


def test_birth_happens_exactly_once_across_restarts(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    clock = FakeClock(BIRTH)
    seeds_issued: list[str] = []

    def counting_seed() -> str:
        seeds_issued.append(f"{len(seeds_issued):064x}")
        return seeds_issued[-1]

    identities = set()
    for restart in range(5):
        clock.advance(TICK * 7)
        runtime = LifeRuntime.open(
            data_dir, clock, PARAMS, name=f"Other{restart}", new_seed=counting_seed
        )
        with runtime:
            identities.add((runtime.state.identity, runtime.state.rng.seed_hex))
            births = [e for e in runtime.timeline() if e.event == runtime.birth_record()]
            assert len(births) == 1
    assert len(seeds_issued) == 1  # the seed factory ran only at birth
    assert len(identities) == 1
    ((identity, seed),) = identities
    assert identity.name == "Other0"  # names passed on later restarts are ignored
    assert seed == seeds_issued[0]


def test_birth_record_says_when_maple_was_born(tmp_path: Path) -> None:
    _, _, runtime = new_life(tmp_path)
    with runtime:
        born = runtime.birth_record()
        assert f"{born.name} was born on {born.at:%Y-%m-%d}" == "Maple was born on 2026-01-01"
        first = runtime.timeline()[0]
        assert first.event == born and first.revision == 1 and first.tick_id is None


def test_repository_refuses_a_second_birth(tmp_path: Path) -> None:
    data_dir, _, runtime = new_life(tmp_path)
    state, born = runtime.state, runtime.birth_record()
    runtime.close()
    with raw_db(data_dir) as conn:
        with pytest.raises(StorageError, match="birth happens once"):
            LifeRepository(conn).create(state, born)


def test_losing_a_birth_race_keeps_the_existing_life(tmp_path: Path) -> None:
    data_dir, _, runtime = new_life(tmp_path)
    winner = runtime.state
    runtime.close()
    loser_clock = FakeClock(BIRTH + TICK)

    def loser_first_life():  # type: ignore[no-untyped-def]
        from maplegotchi.core.state import birth
        from maplegotchi.core.timeline import Born

        state = birth(name="Loser", born_at=loser_clock.now(), seed_hex="ff" * 32)
        return state, Born(state.identity.born_at, "Loser")

    storage_db._give_birth(data_dir, loser_first_life)  # publish finds maple.db taken
    assert not data_dir.names_with_prefix(BIRTH_PREFIX)
    with open_runtime(data_dir, loser_clock) as again:
        assert again.state == winner


def test_interrupted_birth_leaves_nothing_and_retries_cleanly(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)

    def failing_first_life():  # type: ignore[no-untyped-def]
        raise RuntimeError("power cut during birth")

    with pytest.raises(RuntimeError):
        open_life_database(data_dir, failing_first_life)
    assert list(data_dir.root.iterdir()) == []
    (data_dir.root / f"{BIRTH_PREFIX}stale").write_bytes(b"half-written")
    with open_runtime(data_dir, FakeClock(BIRTH)) as runtime:
        assert runtime.state.rng.seed_hex == SEED
    assert not data_dir.names_with_prefix(BIRTH_PREFIX)


# ---------------------------------------------------------------- corruption policy


def _maple_with_history(tmp_path: Path) -> tuple[Path, FakeClock]:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 50)
    runtime.interact(InteractionKind.GREET)
    runtime.close()
    return data_dir.root, clock


def _open_again(root: Path, clock: FakeClock) -> LifeRuntime:
    from maplegotchi.storage.datadir import DataDir

    return open_runtime(DataDir(root), clock)


def test_empty_database_file_is_refused_not_reborn(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    (data_dir.root / DB_FILENAME).write_bytes(b"")
    with pytest.raises(NotAMapleDatabaseError):
        open_runtime(data_dir, FakeClock(BIRTH))
    assert (data_dir.root / DB_FILENAME).stat().st_size == 0


def test_garbage_file_is_refused(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    (data_dir.root / DB_FILENAME).write_bytes(b"this is not sqlite" * 300)
    with pytest.raises(CorruptDatabaseError):
        open_runtime(data_dir, FakeClock(BIRTH))


def test_foreign_sqlite_database_is_refused(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    conn = sqlite3.connect(data_dir.root / DB_FILENAME)
    conn.execute("CREATE TABLE other_app (x)")
    conn.commit()
    conn.close()
    with pytest.raises(NotAMapleDatabaseError):
        open_runtime(data_dir, FakeClock(BIRTH))


def test_migrated_database_without_a_life_is_refused(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    conn = sqlite3.connect(data_dir.root / DB_FILENAME, isolation_level=None)
    migrate(conn)
    conn.close()
    with pytest.raises(NotAMapleDatabaseError, match="no Maple life"):
        open_runtime(data_dir, FakeClock(BIRTH))


@pytest.mark.parametrize("keep", [0.5, 0.9])
def test_truncated_database_is_refused_and_left_untouched(tmp_path: Path, keep: float) -> None:
    root, clock = _maple_with_history(tmp_path)
    db = root / DB_FILENAME
    data = db.read_bytes()
    assert len(data) >= 4 * 4096
    db.write_bytes(data[: int(len(data) * keep) // 4096 * 4096 - 100])
    damaged = db.read_bytes()
    with pytest.raises(StorageError):
        _open_again(root, clock)
    assert db.read_bytes() == damaged  # never repaired or replaced


def test_corrupted_page_headers_are_refused(tmp_path: Path) -> None:
    # Bytes in a page's unused space are not corruption; a damaged b-tree header is.
    root, clock = _maple_with_history(tmp_path)
    db = root / DB_FILENAME
    data = bytearray(db.read_bytes())
    for page in range(1, len(data) // 4096):
        data[page * 4096] = 0x00  # invalid b-tree page type
    db.write_bytes(bytes(data))
    with pytest.raises(StorageError):
        _open_again(root, clock)


def test_newer_schema_is_refused_on_open(tmp_path: Path) -> None:
    root, clock = _maple_with_history(tmp_path)
    conn = sqlite3.connect(root / DB_FILENAME)
    conn.execute("PRAGMA user_version = 99")
    conn.close()
    with pytest.raises(SchemaTooNewError):
        _open_again(root, clock)
