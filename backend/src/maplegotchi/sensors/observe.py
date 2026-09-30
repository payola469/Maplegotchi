"""One read-only pass over paolo-core: host metrics and service health.

Partial failure is normal: each metric and each provider is isolated, so one
broken source leaves every healthy reading in the snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from maplegotchi.core.observations import ObservationSnapshot
from maplegotchi.sensors.host import host_unavailable, read_host
from maplegotchi.sensors.interface import HostProbe
from maplegotchi.sensors.service_health.interface import (
    ServiceHealthProvider,
    ServiceTarget,
    get_service_health,
)

DEFAULT_MOUNTS: tuple[str, ...] = ("/",)


def observe_paolo_core(
    host: HostProbe | None,
    service_providers: Sequence[ServiceHealthProvider],
    targets: Sequence[ServiceTarget],
    *,
    now: datetime,
    mounts: Sequence[str] = DEFAULT_MOUNTS,
) -> ObservationSnapshot:
    if host is None:
        host_part = host_unavailable("no_host_probe", mounts=mounts, now=now)
    else:
        host_part = read_host(host, mounts=mounts, now=now)
    services = get_service_health(targets, service_providers, now=now)
    return ObservationSnapshot(observed_at=now, observations=(*host_part, *services))
