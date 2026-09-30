"""The read-only external metrics datasource contract. No sqlite3 here.

The Stage A survey documented paolo-core's monitoring schema (deploy/survey/
findings.md). The contract offers read-only schema discovery, bounded sampling,
and one aggregate read (`max_value`) over a table and column that must exist in
the discovered schema. There is no generic SQL entry point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ExternalSourceError(Exception):
    """The external source could not be read. `code` is a short reason code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ColumnInfo:
    name: str
    declared_type: str
    not_null: bool
    primary_key: bool


@dataclass(frozen=True, slots=True)
class TableInfo:
    name: str
    columns: tuple[ColumnInfo, ...]
    row_count: int | None  # None when not requested

    def column_names(self) -> frozenset[str]:
        return frozenset(c.name for c in self.columns)


@dataclass(frozen=True, slots=True)
class SchemaReport:
    tables: tuple[TableInfo, ...]
    user_version: int
    journal_mode: str

    def table(self, name: str) -> TableInfo | None:
        return next((t for t in self.tables if t.name == name), None)


@dataclass(frozen=True, slots=True)
class SchemaExpectation:
    """Tables and columns a reader relies on. Written from the survey, not guessed."""

    required: tuple[tuple[str, tuple[str, ...]], ...]


def check_schema(report: SchemaReport, expectation: SchemaExpectation) -> tuple[str, ...]:
    """Problems as reason codes (empty tuple = schema fits)."""
    problems: list[str] = []
    for table_name, columns in expectation.required:
        table = report.table(table_name)
        if table is None:
            problems.append(f"missing_table:{table_name}")
            continue
        present = table.column_names()
        problems.extend(f"missing_column:{table_name}.{c}" for c in columns if c not in present)
    return tuple(problems)


class MetricsSource(Protocol):
    """Read-only view of an external metrics database. There is no write method."""

    def describe_schema(self, *, row_counts: bool = False) -> SchemaReport: ...

    def sample_rows(self, table: str, limit: int = 3) -> tuple[tuple[object, ...], ...]: ...

    def max_value(self, table: str, column: str) -> object:
        """MAX(column) of a discovered table and column; None for an empty table."""
        ...

    def close(self) -> None: ...
