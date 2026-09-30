"""Provider-independent service health (D4, D12).

`get_service_health()` asks providers in priority order for each allowlisted
service. The first `available` answer wins. If none can answer, the service is
reported `unknown` with every provider's reason, never inferred.

Unit names are deployment facts from the paolo-core survey (D12, D15); until
they are configured, targets carry only a logical id and read as unknown.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from maplegotchi.core.observations import (
    Metric,
    Observation,
    ObservationStatus,
    ServiceState,
    not_measured,
)

_SERVICE_ID = re.compile(r"[a-z][a-z0-9_]{0,31}")
_UNIT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@:-]{0,190}\.(?:service|timer)")


@dataclass(frozen=True, slots=True)
class ServiceTarget:
    service_id: str  # stable logical name, e.g. "grafana"
    unit_name: str | None = None  # verified systemd unit, from deployment config

    def __post_init__(self) -> None:
        if not _SERVICE_ID.fullmatch(self.service_id):
            raise ValueError(f"invalid service id {self.service_id!r}")
        if self.unit_name is not None and not _UNIT_NAME.fullmatch(self.unit_name):
            raise ValueError(f"invalid unit name {self.unit_name!r}")


# D12 intent. Unit names are deliberately absent until the survey verifies them.
INTENDED_SERVICES: tuple[ServiceTarget, ...] = (
    ServiceTarget("maplegotchi"),
    ServiceTarget("metrics_collector"),
    ServiceTarget("grafana"),
    ServiceTarget("lycan_watch"),
    ServiceTarget("qbittorrent"),
    ServiceTarget("jellyfin"),
    ServiceTarget("backup"),
)


@dataclass(frozen=True, slots=True)
class ServiceReading:
    status: ObservationStatus
    state: ServiceState | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        available = self.status is ObservationStatus.AVAILABLE
        if available != (self.state is not None) or available == (self.reason is not None):
            raise ValueError("available readings carry a state; others carry a reason")


class ServiceHealthProvider(Protocol):
    source: str

    def read(self, targets: Sequence[ServiceTarget]) -> Mapping[str, ServiceReading]: ...


def get_service_health(
    targets: Sequence[ServiceTarget],
    providers: Sequence[ServiceHealthProvider],
    *,
    now: datetime,
) -> tuple[Observation, ...]:
    answers: list[Mapping[str, ServiceReading] | str] = []
    for provider in providers:
        try:
            answers.append(provider.read(targets))
        except Exception as exc:  # one broken provider must not hide the others
            answers.append(f"provider_error_{type(exc).__name__.lower()}")

    observations: list[Observation] = []
    for target in targets:
        reasons: list[str] = []
        found: Observation | None = None
        for provider, answer in zip(providers, answers, strict=True):
            if isinstance(answer, str):
                reasons.append(f"{provider.source}:{answer}")
                continue
            reading = answer.get(target.service_id)
            if reading is None:
                reasons.append(f"{provider.source}:no_reading")
            elif reading.status is ObservationStatus.AVAILABLE:
                found = Observation(
                    metric=Metric.SERVICE_STATE,
                    subject=target.service_id,
                    status=ObservationStatus.AVAILABLE,
                    observed_at=now,
                    source=provider.source,
                    state=reading.state,
                )
                break
            else:
                reasons.append(f"{provider.source}:{reading.reason}")
        if found is None:
            found = not_measured(
                Metric.SERVICE_STATE,
                target.service_id,
                ObservationStatus.UNKNOWN,
                ";".join(reasons) or "no_provider",
                observed_at=now,
                source="service_health",
            )
        observations.append(found)
    return tuple(observations)
