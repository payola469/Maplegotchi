"""Deterministic in-memory MetricsSource for development and tests."""

from __future__ import annotations

from collections.abc import Mapping

from maplegotchi.storage.external.interface import ExternalSourceError, SchemaReport


class FakeMetricsSource:
    def __init__(
        self,
        report: SchemaReport,
        rows: Mapping[str, tuple[tuple[object, ...], ...]] | None = None,
    ) -> None:
        self._report = report
        self._rows = dict(rows or {})
        self.closed = False
        self.max_values: dict[tuple[str, str], object] = {}
        self.max_failure: ExternalSourceError | None = None

    def describe_schema(self, *, row_counts: bool = False) -> SchemaReport:
        return self._report

    def sample_rows(self, table: str, limit: int = 3) -> tuple[tuple[object, ...], ...]:
        if self._report.table(table) is None:
            raise ExternalSourceError("unknown_table", table)
        return self._rows.get(table, ())[:limit]

    def max_value(self, table: str, column: str) -> object:
        info = self._report.table(table)
        if info is None:
            raise ExternalSourceError("unknown_table", table)
        if column not in info.column_names():
            raise ExternalSourceError("unknown_column", f"{table}.{column}")
        if self.max_failure is not None:
            raise self.max_failure
        return self.max_values.get((table, column))

    def close(self) -> None:
        self.closed = True
