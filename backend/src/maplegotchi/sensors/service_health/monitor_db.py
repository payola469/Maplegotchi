"""Collector freshness from paolo-core's existing monitoring data (provider #1, D4/D11).

Stage A facts (deploy/survey/findings.md): `/data/monitor/metrics.db` has a wide
`metrics` table with one row about every 300 s, `ts` in Unix epoch seconds,
written by `personal-ai-monitor.service`. Its only service columns
(`ollama_ok`, `n8n_ok`, `discord_bot_ok`, `docker_ok`) are legacy flags for
services outside Maple's allowlist and are deliberately NOT read.

So this provider answers for exactly one target, the metrics collector:
- the newest `ts` is within `max_age` of now          -> active (it recently wrote)
- older, empty, in the future, unreadable, wrong schema -> unknown with a reason,
  and the next provider (systemd D-Bus) answers from the units instead.
Every other target is `not_recorded` here. Reads go through the read-only
MetricsSource interface (D18); this module never imports sqlite3.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta

from maplegotchi.core.observations import ObservationStatus, ServiceState
from maplegotchi.sensors.service_health.interface import ServiceReading, ServiceTarget
from maplegotchi.storage.external.interface import (
    ExternalSourceError,
    MetricsSource,
    SchemaExpectation,
    check_schema,
)

METRICS_TABLE = "metrics"
TIMESTAMP_COLUMN = "ts"
# Surveyed in Stage A; only what this provider reads is required.
PAOLO_CORE_METRICS_SCHEMA = SchemaExpectation(required=((METRICS_TABLE, (TIMESTAMP_COLUMN,)),))
COLLECTOR_CADENCE = timedelta(seconds=300)
# Two missed rows plus a minute of slack before the data counts as stale.
DEFAULT_MAX_AGE = 2 * COLLECTOR_CADENCE + timedelta(seconds=60)
CLOCK_SKEW_ALLOWANCE = timedelta(seconds=60)


class MonitoringDbServiceHealth:
    source = "monitor_db"

    def __init__(
        self,
        open_source: Callable[[], MetricsSource],
        expectation: SchemaExpectation | None = None,
        *,
        collector_id: str = "metrics_collector",
        max_age: timedelta = DEFAULT_MAX_AGE,
    ) -> None:
        self._open_source = open_source
        self._expectation = expectation
        self._collector_id = collector_id
        self._max_age = max_age

    def read(
        self, targets: Sequence[ServiceTarget], *, now: datetime
    ) -> Mapping[str, ServiceReading]:
        unknown = ObservationStatus.UNKNOWN
        result = {t.service_id: ServiceReading(unknown, reason="not_recorded") for t in targets}
        if self._collector_id in result:
            result[self._collector_id] = self._collector(now)
        return result

    def _collector(self, now: datetime) -> ServiceReading:
        unknown = ObservationStatus.UNKNOWN
        if self._expectation is None:
            return ServiceReading(unknown, reason="not_surveyed")
        try:
            newest = self._newest_timestamp(self._expectation)
        except ExternalSourceError as exc:
            return ServiceReading(unknown, reason=f"source_{exc.code}")
        except _SchemaMismatch:
            return ServiceReading(unknown, reason="wrong_schema")
        if newest is None:
            return ServiceReading(unknown, reason="no_rows")
        if (
            isinstance(newest, bool)
            or not isinstance(newest, int | float)
            or not math.isfinite(newest)
        ):
            return ServiceReading(unknown, reason="invalid_timestamp")
        age = now.timestamp() - float(newest)
        if age < -CLOCK_SKEW_ALLOWANCE.total_seconds():
            return ServiceReading(unknown, reason="timestamp_in_future")
        if age > self._max_age.total_seconds():
            return ServiceReading(unknown, reason="stale_data")
        return ServiceReading(ObservationStatus.AVAILABLE, state=ServiceState.ACTIVE)

    def _newest_timestamp(self, expectation: SchemaExpectation) -> object:
        source = self._open_source()  # one look at the source per pass
        try:
            if check_schema(source.describe_schema(), expectation):
                raise _SchemaMismatch
            return source.max_value(METRICS_TABLE, TIMESTAMP_COLUMN)
        finally:
            source.close()


class _SchemaMismatch(Exception):
    pass
