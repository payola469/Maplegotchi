"""Monitoring-DB provider: collector freshness only, through the read-only interface."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from maplegotchi.core.observations import ObservationStatus, ServiceState
from maplegotchi.sensors.service_health.interface import ServiceReading, ServiceTarget
from maplegotchi.sensors.service_health.monitor_db import (
    DEFAULT_MAX_AGE,
    PAOLO_CORE_METRICS_SCHEMA,
    MonitoringDbServiceHealth,
)
from maplegotchi.storage.external.fake import FakeMetricsSource
from maplegotchi.storage.external.interface import (
    ColumnInfo,
    ExternalSourceError,
    MetricsSource,
    SchemaReport,
    TableInfo,
)
from maplegotchi.storage.external.sqlite_metrics import SqliteMetricsSource

NOW = datetime(2026, 9, 30, 11, 42, 45, tzinfo=UTC)
COLLECTOR = ServiceTarget(
    "metrics_collector", "personal-ai-monitor.service", timer_name="personal-ai-monitor.timer"
)
TARGETS = [COLLECTOR, ServiceTarget("backup", "paolo-core-backup.service")]
U = ObservationStatus.UNKNOWN

# The Stage A `metrics` table, abridged to a few of its real columns.
METRICS_DDL = (
    "CREATE TABLE metrics (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL,"
    " cpu_usage REAL, cpu_temp REAL, ollama_ok INTEGER, n8n_ok INTEGER, uptime_seconds INTEGER)"
)


def sqlite_opener(path: Path) -> Callable[[], MetricsSource]:
    def open_source() -> MetricsSource:
        return SqliteMetricsSource(path)

    return open_source


def make_metrics_db(path: Path, *timestamps: float) -> Path:
    conn = sqlite3.connect(path)
    conn.execute(METRICS_DDL)
    conn.executemany(
        "INSERT INTO metrics (ts, cpu_usage, ollama_ok, n8n_ok) VALUES (?, 0.1, 0, 1)",
        [(ts,) for ts in timestamps],
    )
    conn.commit()
    conn.close()
    return path


def provider_for(path: Path) -> MonitoringDbServiceHealth:
    return MonitoringDbServiceHealth(sqlite_opener(path), PAOLO_CORE_METRICS_SCHEMA)


def collector(provider: MonitoringDbServiceHealth, now: datetime = NOW) -> ServiceReading:
    return provider.read(TARGETS, now=now)["metrics_collector"]


def test_fresh_row_means_the_collector_is_active(tmp_path: Path) -> None:
    db = make_metrics_db(tmp_path / "metrics.db", NOW.timestamp() - 900, NOW.timestamp() - 224)
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    readings = provider_for(db).read(TARGETS, now=NOW)
    assert readings["metrics_collector"] == ServiceReading(
        ObservationStatus.AVAILABLE, state=ServiceState.ACTIVE
    )
    # metrics.db records nothing about the other allowlisted services.
    assert readings["backup"] == ServiceReading(U, reason="not_recorded")
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["metrics.db"]


@pytest.mark.parametrize(
    ("age", "reason"),
    [
        (DEFAULT_MAX_AGE + timedelta(seconds=1), "stale_data"),
        (timedelta(days=3), "stale_data"),
        (timedelta(seconds=-600), "timestamp_in_future"),
    ],
)
def test_stale_or_future_data_is_unknown(tmp_path: Path, age: timedelta, reason: str) -> None:
    db = make_metrics_db(tmp_path / "metrics.db", (NOW - age).timestamp())
    assert collector(provider_for(db)) == ServiceReading(U, reason=reason)


def test_boundary_of_freshness(tmp_path: Path) -> None:
    db = make_metrics_db(tmp_path / "metrics.db", (NOW - DEFAULT_MAX_AGE).timestamp())
    assert collector(provider_for(db)).state is ServiceState.ACTIVE


def test_empty_table(tmp_path: Path) -> None:
    db = make_metrics_db(tmp_path / "metrics.db")
    assert collector(provider_for(db)) == ServiceReading(U, reason="no_rows")


def test_not_surveyed_without_an_expectation(tmp_path: Path) -> None:
    provider = MonitoringDbServiceHealth(sqlite_opener(tmp_path / "missing.db"), None)
    assert collector(provider) == ServiceReading(U, reason="not_surveyed")


def test_missing_database(tmp_path: Path) -> None:
    missing = tmp_path / "metrics.db"
    assert collector(provider_for(missing)) == ServiceReading(U, reason="source_missing")
    assert not missing.exists()  # read-only open never creates it


def test_unreadable_database(tmp_path: Path) -> None:
    garbage = tmp_path / "metrics.db"
    garbage.write_bytes(b"not a database" * 100)
    assert collector(provider_for(garbage)) == ServiceReading(U, reason="source_unreadable")


def test_wrong_schema(tmp_path: Path) -> None:
    db = tmp_path / "metrics.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE cpu (ts TEXT, value REAL)")
    conn.commit()
    conn.close()
    assert collector(provider_for(db)) == ServiceReading(U, reason="wrong_schema")


def test_hot_journal_is_unknown_and_never_repaired(tmp_path: Path) -> None:
    db = make_metrics_db(tmp_path / "metrics.db", NOW.timestamp() - 60)
    journal = tmp_path / "metrics.db-journal"
    # A rollback-journal header (magic + garbage) left behind by an interrupted writer.
    journal.write_bytes(bytes.fromhex("d9d505f920a163d7") + b"\x00\x00\x00\x01" + b"\x07" * 500)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert collector(provider_for(db)) == ServiceReading(U, reason="source_unreadable")
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def fake_source(
    value: object = None, failure: ExternalSourceError | None = None
) -> FakeMetricsSource:
    report = SchemaReport(
        tables=(TableInfo("metrics", (ColumnInfo("ts", "INTEGER", True, False),), None),),
        user_version=0,
        journal_mode="delete",
    )
    fake = FakeMetricsSource(report)
    fake.max_values[("metrics", "ts")] = value
    fake.max_failure = failure
    return fake


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("yesterday", "invalid_timestamp"),
        (True, "invalid_timestamp"),
        (float("nan"), "invalid_timestamp"),
    ],
)
def test_odd_timestamps_are_unknown(value: object, reason: str) -> None:
    fake = fake_source(value)
    provider = MonitoringDbServiceHealth(lambda: fake, PAOLO_CORE_METRICS_SCHEMA)
    assert collector(provider) == ServiceReading(U, reason=reason)
    assert fake.closed  # the source is always closed after a look


def test_read_failure_mid_query_is_unknown_and_closes() -> None:
    fake = fake_source(failure=ExternalSourceError("unreadable", "database is locked"))
    provider = MonitoringDbServiceHealth(lambda: fake, PAOLO_CORE_METRICS_SCHEMA)
    assert collector(provider) == ServiceReading(U, reason="source_unreadable")
    assert fake.closed


def test_only_the_collector_is_read_from_metrics_db() -> None:
    fake = fake_source(NOW.timestamp())
    provider = MonitoringDbServiceHealth(lambda: fake, PAOLO_CORE_METRICS_SCHEMA)
    readings = provider.read([ServiceTarget("maplegotchi", "maplegotchi.service")], now=NOW)
    assert readings == {"maplegotchi": ServiceReading(U, reason="not_recorded")}
