"""The external metrics datasource is read-only, by API and by SQLite enforcement."""

from __future__ import annotations

import hashlib
import inspect
import sqlite3
from pathlib import Path

import pytest

from maplegotchi.storage.external.fake import FakeMetricsSource
from maplegotchi.storage.external.interface import (
    ExternalSourceError,
    SchemaExpectation,
    check_schema,
)
from maplegotchi.storage.external.sqlite_metrics import MAX_SAMPLE_ROWS, SqliteMetricsSource


def make_metrics_db(path: Path, *, wal: bool = False) -> Path:
    conn = sqlite3.connect(path)
    if wal:
        conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("CREATE TABLE cpu (ts TEXT NOT NULL, value REAL, PRIMARY KEY (ts))")
    conn.execute("CREATE TABLE services (unit TEXT, state TEXT)")
    conn.execute('CREATE TABLE "odd ""name""" (x INTEGER)')
    conn.execute("CREATE TABLE kv (k TEXT PRIMARY KEY, v TEXT) WITHOUT ROWID")
    conn.executemany(
        "INSERT INTO cpu VALUES (?, ?)", [(f"2026-01-01T00:0{i}", i * 1.5) for i in range(8)]
    )
    conn.execute("INSERT INTO services VALUES ('grafana-server.service', 'active')")
    conn.execute("INSERT INTO kv VALUES ('a', '1')")
    conn.commit()
    conn.close()
    return path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return make_metrics_db(tmp_path / "metrics.db")


def test_schema_discovery(db: Path) -> None:
    with SqliteMetricsSource(db) as source:
        report = source.describe_schema(row_counts=True)
    names = [t.name for t in report.tables]
    assert names == sorted(["cpu", "kv", 'odd "name"', "services"])
    cpu = report.table("cpu")
    assert cpu is not None and cpu.row_count == 8
    assert [(c.name, c.declared_type, c.not_null, c.primary_key) for c in cpu.columns] == [
        ("ts", "TEXT", True, True),
        ("value", "REAL", False, False),
    ]
    assert report.journal_mode == "delete"


def test_bounded_sampling_of_discovered_tables_only(db: Path) -> None:
    with SqliteMetricsSource(db) as source:
        rows = source.sample_rows("cpu", 3)
        assert rows == (
            ("2026-01-01T00:07", 10.5),
            ("2026-01-01T00:06", 9.0),
            ("2026-01-01T00:05", 7.5),
        )
        assert source.sample_rows('odd "name"', 1) == ()
        assert source.sample_rows("kv", 5) == (("a", "1"),)  # WITHOUT ROWID fallback
        for table in ["nope", "cpu; DROP TABLE cpu", 'cpu" --', "sqlite_master"]:
            with pytest.raises(ExternalSourceError) as err:
                source.sample_rows(table, 1)
            assert err.value.code == "unknown_table"
        for limit in [0, -1, MAX_SAMPLE_ROWS + 1, True, 2.5]:
            with pytest.raises(ExternalSourceError):
                source.sample_rows("cpu", limit)  # type: ignore[arg-type]


def test_connection_is_read_only_and_query_only(db: Path) -> None:
    before = digest(db)
    source = SqliteMetricsSource(db)
    conn = source._conn  # the private connection, to prove SQLite itself refuses writes
    assert conn is not None
    assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
    attacks = [
        "INSERT INTO cpu VALUES ('x', 1)",
        "UPDATE cpu SET value = 0",
        "DELETE FROM cpu",
        "CREATE TABLE evil (x)",
        "DROP TABLE cpu",
        "ALTER TABLE cpu ADD COLUMN y",
        "CREATE INDEX i ON cpu (value)",
        "REPLACE INTO cpu VALUES ('x', 1)",
        "VACUUM",
        "PRAGMA user_version = 5",
    ]
    for sql in attacks:
        with pytest.raises(sqlite3.Error):
            conn.execute(sql)
    # Even switching query_only off cannot write: the file was opened with mode=ro.
    conn.execute("PRAGMA query_only = OFF")
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("INSERT INTO cpu VALUES ('y', 2)")
    source.describe_schema(row_counts=True)
    source.sample_rows("cpu", 5)
    source.close()
    assert digest(db) == before


def test_public_api_has_no_write_capability() -> None:
    public = {n for n, _ in inspect.getmembers(SqliteMetricsSource) if not n.startswith("_")}
    assert public == {"describe_schema", "sample_rows", "close"}
    fake_public = {n for n in dir(FakeMetricsSource) if not n.startswith("_")}
    for name in public | fake_public:
        assert not any(
            word in name.lower()
            for word in ("insert", "update", "delete", "write", "execute", "create", "drop",
                         "migrate", "commit", "save", "set")
        ), name  # fmt: skip


def test_missing_file_is_reported_and_never_created(tmp_path: Path) -> None:
    missing = tmp_path / "metrics.db"
    with pytest.raises(ExternalSourceError) as err:
        SqliteMetricsSource(missing)
    assert err.value.code == "missing"
    assert not missing.exists()


def test_relative_path_refused() -> None:
    with pytest.raises(ExternalSourceError) as err:
        SqliteMetricsSource(Path("metrics.db"))
    assert err.value.code == "invalid_path"


@pytest.mark.parametrize("content", [b"", b"garbage" * 500])
def test_non_database_is_unreadable(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "metrics.db"
    path.write_bytes(content)
    if not content:
        # An empty file is a valid empty SQLite database; it simply has no tables.
        with SqliteMetricsSource(path) as source:
            assert source.describe_schema().tables == ()
        assert path.read_bytes() == b""
        return
    with pytest.raises(ExternalSourceError) as err:
        SqliteMetricsSource(path)
    assert err.value.code == "unreadable"


def test_wal_mode_database_can_be_read(tmp_path: Path) -> None:
    db = make_metrics_db(tmp_path / "metrics.db", wal=True)
    with SqliteMetricsSource(db) as source:
        assert source.describe_schema().journal_mode == "wal"
        assert len(source.sample_rows("cpu", 2)) == 2


def test_closed_source_refuses_reads(db: Path) -> None:
    source = SqliteMetricsSource(db)
    source.close()
    source.close()
    with pytest.raises(ExternalSourceError):
        source.describe_schema()


def test_check_schema_reports_problems(db: Path) -> None:
    with SqliteMetricsSource(db) as source:
        report = source.describe_schema()
    fits = SchemaExpectation(required=(("cpu", ("ts", "value")),))
    wrong = SchemaExpectation(required=(("cpu", ("ts", "host")), ("memory", ("ts",))))
    assert check_schema(report, fits) == ()
    assert check_schema(report, wrong) == ("missing_column:cpu.host", "missing_table:memory")
