"""Wiring for Maple's senses. Runtime is the only place concrete probes are chosen."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from maplegotchi.core.observations import ObservationSnapshot
from maplegotchi.sensors.interface import HostProbe
from maplegotchi.sensors.observe import DEFAULT_MOUNTS, observe_paolo_core
from maplegotchi.sensors.service_health.interface import (
    INTENDED_SERVICES,
    ServiceHealthProvider,
    ServiceTarget,
)
from maplegotchi.sensors.service_health.monitor_db import MonitoringDbServiceHealth
from maplegotchi.sensors.service_health.systemd_dbus import SystemdDbusServiceHealth
from maplegotchi.sensors.system import PsutilHostProbe
from maplegotchi.storage.external.interface import MetricsSource
from maplegotchi.storage.external.sqlite_metrics import SqliteMetricsSource

# D11: the existing collector's database. Read-only; never written by Maple.
DEFAULT_MONITOR_DB = Path("/data/monitor/metrics.db")


@dataclass(frozen=True)
class Senses:
    host: HostProbe | None
    service_providers: tuple[ServiceHealthProvider, ...]
    targets: tuple[ServiceTarget, ...] = INTENDED_SERVICES
    mounts: tuple[str, ...] = field(default=DEFAULT_MOUNTS)

    def observe(self, now: datetime) -> ObservationSnapshot:
        return observe_paolo_core(
            self.host, self.service_providers, self.targets, now=now, mounts=self.mounts
        )


def paolo_core_senses(monitor_db: Path = DEFAULT_MONITOR_DB) -> Senses:
    """Real, read-only senses. Until the survey is recorded, services read as unknown."""

    def open_monitor_db() -> MetricsSource:
        return SqliteMetricsSource(monitor_db)

    return Senses(
        host=PsutilHostProbe(),
        service_providers=(
            MonitoringDbServiceHealth(open_monitor_db, expectation=None),  # not surveyed yet
            SystemdDbusServiceHealth(client=None),  # no bus transport until the survey says so
        ),
    )
