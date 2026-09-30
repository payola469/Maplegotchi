"""Monitoring-DB provider: reads through the read-only interface; never guesses."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from maplegotchi.core.observations import ObservationStatus
from maplegotchi.sensors.service_health.interface import ServiceTarget
from maplegotchi.sensors.service_health.monitor_db import MonitoringDbServiceHealth
from maplegotchi.storage.external.fake import FakeMetricsSource
from maplegotchi.storage.external.interface import (
    ColumnInfo,
    MetricsSource,
    SchemaExpectation,
    SchemaReport,
    TableInfo,
)
from maplegotchi.storage.external.sqlite_metrics import SqliteMetricsSource

TARGETS = [ServiceTarget("grafana"), ServiceTarget("jellyfin")]
EXPECT = SchemaExpectation(required=(("service_status", ("unit", "state", "ts")),))


def reasons(provider: MonitoringDbServiceHealth) -> set[str | None]:
    result = provider.read(TARGETS)
    assert all(r.status is ObservationStatus.UNKNOWN for r in result.values())
    return {r.reason for r in result.values()}


def report(*tables: tuple[str, tuple[str, ...]]) -> SchemaReport:
    return SchemaReport(
        tables=tuple(
            TableInfo(name, tuple(ColumnInfo(c, "TEXT", False, False) for c in cols), None)
            for name, cols in tables
        ),
        user_version=0,
        journal_mode="wal",
    )


def sqlite_opener(path: Path):  # type: ignore[no-untyped-def]
    def open_source() -> MetricsSource:
        return SqliteMetricsSource(path)

    return open_source


def test_not_surveyed_until_an_expectation_is_configured(tmp_path: Path) -> None:
    provider = MonitoringDbServiceHealth(sqlite_opener(tmp_path / "missing.db"), expectation=None)
    assert reasons(provider) == {"not_surveyed"}


def test_missing_database(tmp_path: Path) -> None:
    missing = tmp_path / "metrics.db"
    assert reasons(MonitoringDbServiceHealth(sqlite_opener(missing), EXPECT)) == {"source_missing"}
    assert not missing.exists()  # read-only open never creates it


def test_unreadable_database(tmp_path: Path) -> None:
    garbage = tmp_path / "metrics.db"
    garbage.write_bytes(b"not a database" * 100)
    provider = MonitoringDbServiceHealth(sqlite_opener(garbage), EXPECT)
    assert reasons(provider) == {"source_unreadable"}


def test_wrong_schema(tmp_path: Path) -> None:
    db = tmp_path / "metrics.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE cpu (ts TEXT, value REAL)")
    conn.commit()
    conn.close()
    assert reasons(MonitoringDbServiceHealth(sqlite_opener(db), EXPECT)) == {"wrong_schema"}


def test_fitting_schema_still_waits_for_surveyed_queries() -> None:
    fake = FakeMetricsSource(report(("service_status", ("unit", "state", "ts", "extra"))))
    provider = MonitoringDbServiceHealth(lambda: fake, EXPECT)
    assert reasons(provider) == {"query_not_configured"}
    assert fake.closed  # the source is always closed after a look
