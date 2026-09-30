"""Opening Maple's database: first birth, migration, and integrity checks.

Database: `<MAPLE_DATA_DIR>/maple.db` (production: /data/maple/maple.db).

Opening policy (see docs/persistence.md):
- `maple.db` absent  -> first birth. The new life is written to a temporary
  file in rollback-journal (DELETE) mode, fully migrated and committed, and
  closed. Only after verifying that the file is self-contained (no -journal,
  -wal or -shm sidecar; header says rollback journal) is it published as
  `maple.db` with a link that never overwrites. Birth is therefore
  all-or-nothing, never depends on an unpublished sidecar, and happens at most
  once even if two starters race. WAL is enabled only afterwards, on the
  published canonical file.
- `maple.db` present -> it must be a non-empty Maplegotchi database that
  passes integrity checks, migrates cleanly, and holds exactly one life.
  Otherwise opening fails loudly. Existing files are never recreated.
"""

from __future__ import annotations

import secrets
import sqlite3
from collections.abc import Callable
from pathlib import Path

from maplegotchi.core.state import MapleState
from maplegotchi.core.timeline import Born
from maplegotchi.storage.datadir import DataDir
from maplegotchi.storage.errors import (
    CorruptDatabaseError,
    NotAMapleDatabaseError,
    StorageError,
)
from maplegotchi.storage.migrations import APPLICATION_ID, migrate
from maplegotchi.storage.repositories import LifeRepository

DB_FILENAME = "maple.db"
BIRTH_PREFIX = "maple.db.birth-"
_SIDE_FILE_SUFFIXES = ("-journal", "-wal", "-shm")
_SQLITE_MAGIC = b"SQLite format 3\x00"
# Header bytes 18-19 are the file-format write/read versions: 1 = rollback journal, 2 = WAL.
_ROLLBACK_JOURNAL_VERSIONS = b"\x01\x01"
MIN_SQLITE_VERSION = (3, 38, 0)  # STRICT tables, json_valid

FirstLife = Callable[[], tuple[MapleState, Born]]


def _connect(path: Path, *, create: bool) -> sqlite3.Connection:
    if sqlite3.sqlite_version_info < MIN_SQLITE_VERSION:
        raise StorageError(f"SQLite {sqlite3.sqlite_version} is too old; need 3.38+")
    mode = "rwc" if create else "rw"
    conn = sqlite3.connect(
        f"{path.as_uri()}?mode={mode}",
        uri=True,
        isolation_level=None,  # explicit BEGIN/COMMIT only
        check_same_thread=False,  # the runtime serializes all access with a lock
    )
    conn.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)
    conn.execute("PRAGMA trusted_schema = OFF")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _enable_wal(conn: sqlite3.Connection) -> None:
    mode = conn.execute("PRAGMA journal_mode = WAL").fetchone()[0]
    if str(mode).lower() != "wal":
        raise StorageError(f"could not enable WAL journal mode (got {mode!r})")
    # FULL: a committed life transition survives power loss, not just a crash.
    conn.execute("PRAGMA synchronous = FULL")


def _use_rollback_journal(conn: sqlite3.Connection) -> None:
    mode = conn.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
    if str(mode).lower() != "delete":
        raise StorageError(f"birth database must use DELETE journal mode (got {mode!r})")


def _require_self_contained(data_dir: DataDir, name: str) -> None:
    """Refuse to publish unless every committed byte is in the main file itself."""
    for suffix in _SIDE_FILE_SUFFIXES:
        if data_dir.exists(name + suffix):
            raise StorageError(f"{name}{suffix} exists; birth database is not self-contained")
    with data_dir.path(name).open("rb") as file:
        header = file.read(100)
    if len(header) < 100 or not header.startswith(_SQLITE_MAGIC):
        raise StorageError("birth database is not a complete SQLite file")
    if header[18:20] != _ROLLBACK_JOURNAL_VERSIONS:
        raise StorageError("birth database is in WAL mode; refusing to publish")


def _verify(conn: sqlite3.Connection) -> None:
    app_id = conn.execute("PRAGMA application_id").fetchone()[0]
    if app_id != APPLICATION_ID:
        raise NotAMapleDatabaseError(f"application_id is {app_id:#x}, not a Maplegotchi database")
    problems = [row[0] for row in conn.execute("PRAGMA integrity_check").fetchall()]
    if problems != ["ok"]:
        raise CorruptDatabaseError(f"integrity check failed: {problems[:5]}")
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise CorruptDatabaseError("foreign key check failed")


def _remove_with_side_files(data_dir: DataDir, name: str) -> None:
    for suffix in ("", *_SIDE_FILE_SUFFIXES):
        data_dir.remove(name + suffix)


def _give_birth(data_dir: DataDir, first_life: FirstLife) -> None:
    for stale in data_dir.names_with_prefix(BIRTH_PREFIX):
        data_dir.remove(stale)  # leftovers from an interrupted earlier birth

    temp = f"{BIRTH_PREFIX}{secrets.token_hex(8)}"
    try:
        conn = _connect(data_dir.path(temp), create=True)
        try:
            _use_rollback_journal(conn)
            migrate(conn)
            state, born = first_life()
            LifeRepository(conn).create(state, born)
        finally:
            conn.close()  # DELETE journal: after commit + close only the main file remains
        _require_self_contained(data_dir, temp)
        try:
            data_dir.publish(temp, DB_FILENAME)
        except FileExistsError:
            pass  # another starter published first; that life wins, ours is discarded
    finally:
        _remove_with_side_files(data_dir, temp)


def open_life_database(data_dir: DataDir, first_life: FirstLife) -> sqlite3.Connection:
    """Open Maple's database, giving birth first if and only if none exists yet."""
    if not data_dir.exists(DB_FILENAME):
        _give_birth(data_dir, first_life)

    path = data_dir.path(DB_FILENAME)
    if path.stat().st_size == 0:
        raise NotAMapleDatabaseError(f"{DB_FILENAME} is empty; refusing to treat it as new")
    conn = _connect(path, create=False)
    try:
        _verify(conn)
        _enable_wal(conn)
        migrate(conn)
        if not LifeRepository(conn).has_life():
            raise NotAMapleDatabaseError(f"{DB_FILENAME} holds no Maple life")
    except sqlite3.DatabaseError as exc:
        conn.close()
        raise CorruptDatabaseError(f"cannot read {DB_FILENAME}: {exc}") from exc
    except BaseException:
        conn.close()
        raise
    return conn
