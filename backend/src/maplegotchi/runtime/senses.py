"""Wiring for Maple's senses. Runtime is the only place concrete probes are chosen."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from maplegotchi.core.observations import ObservationSnapshot
from maplegotchi.sensors.interface import HostProbe
from maplegotchi.sensors.observe import DEFAULT_MOUNTS, observe_paolo_core
from maplegotchi.sensors.service_health.dbus_transport import DbusFastSystemTransport
from maplegotchi.sensors.service_health.interface import (
    INTENDED_SERVICES,
    ServiceHealthProvider,
    ServiceTarget,
)
from maplegotchi.sensors.service_health.monitor_db import (
    PAOLO_CORE_METRICS_SCHEMA,
    MonitoringDbServiceHealth,
)
from maplegotchi.sensors.service_health.systemd_dbus import (
    ReadOnlySystemdClient,
    SystemdDbusServiceHealth,
)
from maplegotchi.sensors.system import PsutilHostProbe
from maplegotchi.storage.external.interface import MetricsSource
from maplegotchi.storage.external.sqlite_metrics import SqliteMetricsSource

# D11: the existing collector's database. Read-only; never written by Maple.
DEFAULT_MONITOR_DB = Path("/data/monitor/metrics.db")

# The verified paolo-core service map (Stage A survey, deploy/survey/findings.md).
# This is reviewed, root-owned release code: Maple cannot change it (§4.1 #5).
# No auto-discovery (D12). qBittorrent and Jellyfin were not found on paolo-core
# and are not part of this deployment's map.
PAOLO_CORE_SERVICES: tuple[ServiceTarget, ...] = (
    ServiceTarget("maplegotchi", "maplegotchi.service"),
    ServiceTarget(
        "metrics_collector", "personal-ai-monitor.service", timer_name="personal-ai-monitor.timer"
    ),
    # Grafana runs as a Docker container; Maple gets no Docker socket (v0.1: unknown).
    ServiceTarget("grafana", unobservable="docker_container"),
    # No dedicated systemd unit exists for Lycan Watch / updates; none is invented.
    ServiceTarget("lycan_watch", unobservable="no_systemd_unit"),
    ServiceTarget("backup", "paolo-core-backup.service", timer_name="paolo-core-backup.timer"),
)


def allowed_units(targets: tuple[ServiceTarget, ...]) -> frozenset[str]:
    return frozenset(unit for target in targets for unit in target.units)


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
    """Real, read-only senses: psutil host metrics, collector freshness, systemd D-Bus."""

    def open_monitor_db() -> MetricsSource:
        return SqliteMetricsSource(monitor_db)

    targets = PAOLO_CORE_SERVICES
    client = ReadOnlySystemdClient(DbusFastSystemTransport(), allowed_units(targets))
    return Senses(
        host=PsutilHostProbe(),
        service_providers=(
            MonitoringDbServiceHealth(open_monitor_db, PAOLO_CORE_METRICS_SCHEMA),
            SystemdDbusServiceHealth(client),
        ),
        targets=targets,
    )
