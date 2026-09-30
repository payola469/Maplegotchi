"""Provider-independent service health (D4, D12).

`get_service_health()` asks providers in priority order for each allowlisted
service. The first `available` answer wins. If none can answer, the service is
reported `unknown` with every provider's reason, never inferred.

Unit names are deployment facts from the paolo-core survey (D12, D15). A target
without them reads as unknown; a target the survey found no read-only way to
observe (e.g. a Docker container) carries an explicit `unobservable` reason and
is reported unknown without asking any provider.
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
_TIMER_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@:-]{0,190}\.timer")
_REASON_CODE = re.compile(r"[a-z0-9_]{1,48}")


@dataclass(frozen=True, slots=True)
class ServiceTarget:
    service_id: str  # stable logical name, e.g. "grafana"
    unit_name: str | None = None  # verified systemd unit, from the deployment service map
    timer_name: str | None = None  # verified timer that schedules unit_name (a oneshot job)
    unobservable: str | None = None  # reason code: the survey found no read-only source

    def __post_init__(self) -> None:
        if not _SERVICE_ID.fullmatch(self.service_id):
            raise ValueError(f"invalid service id {self.service_id!r}")
        if self.unit_name is not None and not _UNIT_NAME.fullmatch(self.unit_name):
            raise ValueError(f"invalid unit name {self.unit_name!r}")
        if self.timer_name is not None:
            if not _TIMER_NAME.fullmatch(self.timer_name):
                raise ValueError(f"invalid timer name {self.timer_name!r}")
            if self.unit_name is None or not self.unit_name.endswith(".service"):
                raise ValueError("a timer schedules a .service unit_name")
        if self.unobservable is not None:
            if not _REASON_CODE.fullmatch(self.unobservable):
                raise ValueError(f"invalid reason code {self.unobservable!r}")
            if self.unit_name is not None:
                raise ValueError("an unobservable target has no unit names")

    @property
    def units(self) -> tuple[str, ...]:
        return tuple(u for u in (self.unit_name, self.timer_name) if u is not None)


# D12 intent. Unit names are deliberately absent here; the verified production
# map (after the Stage A survey) lives with the runtime wiring.
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

    def read(
        self, targets: Sequence[ServiceTarget], *, now: datetime
    ) -> Mapping[str, ServiceReading]: ...


def get_service_health(
    targets: Sequence[ServiceTarget],
    providers: Sequence[ServiceHealthProvider],
    *,
    now: datetime,
) -> tuple[Observation, ...]:
    observable = [t for t in targets if t.unobservable is None]
    answers: list[Mapping[str, ServiceReading] | str] = []
    for provider in providers:
        try:
            answers.append(provider.read(observable, now=now) if observable else {})
        except Exception as exc:  # one broken provider must not hide the others
            answers.append(f"provider_error_{type(exc).__name__.lower()}")

    observations: list[Observation] = []
    for target in targets:
        if target.unobservable is not None:
            observations.append(
                not_measured(
                    Metric.SERVICE_STATE,
                    target.service_id,
                    ObservationStatus.UNKNOWN,
                    f"not_observable:{target.unobservable}",
                    observed_at=now,
                    source="service_health",
                )
            )
            continue
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
