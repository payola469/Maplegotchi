"""Read-only SQLite access to an external metrics database (D18).

Guarantees:
- opened with `mode=ro` (SQLite never writes or creates the file) and
  `PRAGMA query_only = ON` (every write statement is refused), verified;
- defensive mode and `trusted_schema = OFF`;
- the public API is schema discovery, bounded sampling of discovered tables,
  and MAX() of a discovered column: no arbitrary SQL, no write, schema, or
  migration method;
- a hot rollback journal left by the writer cannot be replayed through a
  read-only connection: that surfaces as `unreadable`, never as a repair.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType

from maplegotchi.storage.external.interface import (
    ColumnInfo,
    ExternalSourceError,
    SchemaReport,
    TableInfo,
)

MAX_SAMPLE_ROWS = 5
_BUSY_TIMEOUT_MS = 2000


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class SqliteMetricsSource:
    __slots__ = ("_conn",)

    def __init__(self, path: Path) -> None:
        if not path.is_absolute():
            raise ExternalSourceError("invalid_path", "external database path must be absolute")
        if not path.is_file():
            raise ExternalSourceError("missing", str(path))
        try:
            conn = sqlite3.connect(
                f"{path.as_uri()}?mode=ro",
                uri=True,
                isolation_level=None,
                check_same_thread=False,
            )
        except sqlite3.Error as exc:
            raise ExternalSourceError("unreadable", str(exc)) from exc
        try:
            conn.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)
            conn.execute("PRAGMA query_only = ON")
            conn.execute("PRAGMA trusted_schema = OFF")
            conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS:d}")
            if conn.execute("PRAGMA query_only").fetchone()[0] != 1:
                raise ExternalSourceError("unreadable", "query_only could not be enabled")
            conn.execute("SELECT count(*) FROM sqlite_master").fetchone()  # is it a database?
        except ExternalSourceError:
            conn.close()
            raise
        except sqlite3.Error as exc:
            conn.close()
            raise ExternalSourceError("unreadable", str(exc)) from exc
        self._conn: sqlite3.Connection | None = conn

    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise ExternalSourceError("closed")
        return self._conn

    def _table_names(self) -> tuple[str, ...]:
        rows = self._connection().execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' ORDER BY name"
        )
        return tuple(r[0] for r in rows)

    def describe_schema(self, *, row_counts: bool = False) -> SchemaReport:
        conn = self._connection()
        try:
            tables = []
            for name in self._table_names():
                columns = tuple(
                    ColumnInfo(
                        name=col_name,
                        declared_type=col_type or "",
                        not_null=bool(not_null),
                        primary_key=bool(pk),
                    )
                    for col_name, col_type, not_null, pk in conn.execute(
                        'SELECT name, type, "notnull", pk FROM pragma_table_info(?) ORDER BY cid',
                        (name,),
                    )
                )
                count = None
                if row_counts:
                    query = f"SELECT count(*) FROM {_quote_identifier(name)}"  # noqa: S608
                    count = int(conn.execute(query).fetchone()[0])
                tables.append(TableInfo(name=name, columns=columns, row_count=count))
            return SchemaReport(
                tables=tuple(tables),
                user_version=int(conn.execute("PRAGMA user_version").fetchone()[0]),
                journal_mode=str(conn.execute("PRAGMA journal_mode").fetchone()[0]),
            )
        except sqlite3.Error as exc:
            raise ExternalSourceError("unreadable", str(exc)) from exc

    def sample_rows(self, table: str, limit: int = 3) -> tuple[tuple[object, ...], ...]:
        """The most recent `limit` rows of a table discovered in the schema."""
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_SAMPLE_ROWS
        ):
            raise ExternalSourceError("invalid_limit", f"limit must be 1..{MAX_SAMPLE_ROWS}")
        if table not in self._table_names():
            raise ExternalSourceError("unknown_table", table)
        quoted = _quote_identifier(table)
        conn = self._connection()
        try:
            try:
                rows = conn.execute(
                    f"SELECT * FROM {quoted} ORDER BY rowid DESC LIMIT ?",  # noqa: S608
                    (limit,),
                ).fetchall()
            except sqlite3.OperationalError:  # WITHOUT ROWID table
                rows = conn.execute(f"SELECT * FROM {quoted} LIMIT ?", (limit,)).fetchall()  # noqa: S608
        except sqlite3.Error as exc:
            raise ExternalSourceError("unreadable", str(exc)) from exc
        return tuple(tuple(row) for row in rows)

    def max_value(self, table: str, column: str) -> object:
        """MAX(column) of a table and column discovered in the schema (None if empty)."""
        if table not in self._table_names():
            raise ExternalSourceError("unknown_table", table)
        conn = self._connection()
        try:
            columns = {
                r[0] for r in conn.execute("SELECT name FROM pragma_table_info(?)", (table,))
            }
            if column not in columns:
                raise ExternalSourceError("unknown_column", f"{table}.{column}")
            query = f"SELECT max({_quote_identifier(column)}) FROM {_quote_identifier(table)}"  # noqa: S608
            row = conn.execute(query).fetchone()
        except sqlite3.Error as exc:
            raise ExternalSourceError("unreadable", str(exc)) from exc
        return None if row is None else row[0]

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> SqliteMetricsSource:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
