"""Birth publication is WAL-safe: the published maple.db is complete on its own.

The published file is copied ALONE (no -journal/-wal/-shm) into an isolated
directory and opened with a fresh connection there. If any committed birth
data lived only in a sidecar, the copy would be missing it — the negative
control below shows that this inspection does catch exactly that case.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from maplegotchi.runtime.clock import FakeClock
from maplegotchi.storage import db as storage_db
from maplegotchi.storage.datadir import DataDir
from maplegotchi.storage.db import BIRTH_PREFIX, DB_FILENAME, open_life_database
from maplegotchi.storage.errors import StorageError
from maplegotchi.storage.migrations import latest_version
from tests.persistence_support import BIRTH, SEED, make_data_dir, open_runtime

SIDECARS = ("-journal", "-wal", "-shm")


def inspect_alone(main_file: Path, scratch: Path) -> dict[str, Any]:
    """Copy only the main database file somewhere isolated and read it there."""
    scratch.mkdir()
    copy = scratch / "isolated.db"
    shutil.copyfile(main_file, copy)
    assert not any(Path(f"{copy}{s}").exists() for s in SIDECARS)
    header = copy.read_bytes()[:100]
    conn = sqlite3.connect(f"{copy.as_uri()}?mode=ro", uri=True)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "maple" not in tables:
            return {"tables": tables, "header_versions": header[18:20]}
        return {
            "tables": tables,
            "header_versions": header[18:20],
            "integrity": conn.execute("PRAGMA integrity_check").fetchall(),
            "user_version": conn.execute("PRAGMA user_version").fetchone()[0],
            "maple": conn.execute("SELECT id, name, born_at, life_seed FROM maple").fetchall(),
            "life_state": conn.execute(
                "SELECT revision, tick_counter, interaction_counter, last_tick_at FROM life_state"
            ).fetchall(),
            "events": conn.execute("SELECT revision, kind, at FROM timeline_event").fetchall(),
            "ledger": conn.execute("SELECT count(*) FROM interaction_ledger").fetchone()[0],
        }
    finally:
        conn.close()


def expected_newborn() -> dict[str, Any]:
    born = BIRTH.isoformat()
    return {
        "integrity": [("ok",)],
        "user_version": latest_version(),
        "maple": [(1, "Maple", born, SEED)],
        "life_state": [(1, 0, 0, born)],  # revision 1, tick 0, interaction 0
        "events": [(1, "born", born)],
        "ledger": 0,
    }


def test_birth_is_published_from_a_self_contained_main_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = make_data_dir(tmp_path)
    seen: dict[str, Any] = {}
    real_publish = DataDir.publish

    def checking_publish(self: DataDir, source: str, destination: str) -> None:
        # At the moment of publication: all connections closed, no sidecars anywhere.
        seen["files"] = sorted(p.name for p in self.root.iterdir())
        seen["alone"] = inspect_alone(self.path(source), tmp_path / "at-publish")
        real_publish(self, source, destination)

    monkeypatch.setattr(DataDir, "publish", checking_publish)
    with open_runtime(data_dir, FakeClock(BIRTH)) as runtime:
        # Canonical operation switches to WAL only after publication.
        header = (data_dir.root / DB_FILENAME).read_bytes()[:100]
        assert header[18:20] == b"\x02\x02"
        assert runtime.revision == 1

    [birth_file] = seen["files"]
    assert birth_file.startswith(BIRTH_PREFIX)  # the main file only: no -journal/-wal/-shm
    alone = seen["alone"]
    assert alone["header_versions"] == b"\x01\x01"  # rollback journal, not WAL
    assert {k: alone[k] for k in expected_newborn()} == expected_newborn()


def test_published_database_reopens_alone_as_a_fresh_connection(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    open_life_database(data_dir, _first_life).close()  # birth only; closes cleanly
    assert sorted(p.name for p in data_dir.root.iterdir()) == [DB_FILENAME]
    alone = inspect_alone(data_dir.root / DB_FILENAME, tmp_path / "fresh")
    assert {k: alone[k] for k in expected_newborn()} == expected_newborn()


def test_negative_control_wal_only_data_is_detected(tmp_path: Path) -> None:
    # A WAL database whose committed rows are still only in its -wal sidecar.
    path = tmp_path / "wal-only.db"
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA wal_autocheckpoint = 0")
    conn.execute("CREATE TABLE maple (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO maple VALUES (1, 'Maple')")  # committed (autocommit)
    try:
        assert Path(f"{path}-wal").stat().st_size > 0
        alone = inspect_alone(path, tmp_path / "control")
        assert "maple" not in alone["tables"]  # the lone main file lacks the committed data
        assert alone["header_versions"] == b"\x02\x02"
    finally:
        conn.close()


def test_publication_refuses_sidecars_and_wal_files(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    name = f"{BIRTH_PREFIX}test"
    conn = sqlite3.connect(data_dir.path(name), isolation_level=None)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.close()
    storage_db._require_self_contained(data_dir, name)  # clean rollback-journal file: fine

    (data_dir.root / f"{name}-wal").write_bytes(b"pending")
    with pytest.raises(StorageError, match="not self-contained"):
        storage_db._require_self_contained(data_dir, name)
    (data_dir.root / f"{name}-wal").unlink()

    conn = sqlite3.connect(data_dir.path(name), isolation_level=None)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.close()
    with pytest.raises(StorageError, match="WAL mode"):
        storage_db._require_self_contained(data_dir, name)


def test_a_wal_mode_birth_is_never_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = make_data_dir(tmp_path)

    def wal_instead(conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA journal_mode = WAL")

    monkeypatch.setattr(storage_db, "_use_rollback_journal", wal_instead)
    with pytest.raises(StorageError):
        open_life_database(data_dir, _first_life)
    assert not (data_dir.root / DB_FILENAME).exists()  # all-or-nothing: nothing published
    assert list(data_dir.root.iterdir()) == []  # temporary files and sidecars cleaned up


def _first_life():  # type: ignore[no-untyped-def]
    from maplegotchi.core.state import birth
    from maplegotchi.core.timeline import Born

    return birth(name="Maple", born_at=BIRTH, seed_hex=SEED), Born(at=BIRTH, name="Maple")
