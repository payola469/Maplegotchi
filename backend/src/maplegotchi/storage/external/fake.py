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

    def describe_schema(self, *, row_counts: bool = False) -> SchemaReport:
        return self._report

    def sample_rows(self, table: str, limit: int = 3) -> tuple[tuple[object, ...], ...]:
        if self._report.table(table) is None:
            raise ExternalSourceError("unknown_table", table)
        return self._rows.get(table, ())[:limit]

    def close(self) -> None:
        self.closed = True
