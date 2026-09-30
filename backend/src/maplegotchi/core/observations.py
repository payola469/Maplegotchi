"""Factual observations of Maple's world (D8).

An Observation is a fact about the machine: a metric, what it was measured on,
its value or why there is none, when, and by which source. It never contains
interpretation or feelings; that is the Journal's job (Phase 4).

Status semantics:
- available    a valid, in-range value was measured
- unavailable  the metric does not exist here (platform or hardware lacks it)
- unknown      the metric exists but its value cannot be determined right now
               (not configured, not surveyed, source missing or stale)
- error        a source failed or returned an invalid value
Only `available` carries a value; every other status carries a reason code.

A reason starting with `not_observable:` marks a gap that exists by design: the
deployment has no read-only way to observe that subject (e.g. a service running
in a Docker container Maple gets no socket for). It is shown as unknown, but it
is a known limit of Maple's senses, not a sign that something is wrong now.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from maplegotchi.core.daytime import require_utc


class ObservationStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    ERROR = "error"


class Metric(StrEnum):
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_USAGE = "disk_usage"
    LOAD_1M = "load_1m"
    LOAD_5M = "load_5m"
    LOAD_15M = "load_15m"
    CPU_COUNT = "cpu_count"
    TEMPERATURE = "temperature"
    SERVICE_STATE = "service_state"


class Unit(StrEnum):
    PERCENT = "percent"
    CELSIUS = "celsius"
    LOAD = "load"
    COUNT = "count"
    STATE = "state"


class ServiceState(StrEnum):
    """systemd ActiveState values."""

    ACTIVE = "active"
    RELOADING = "reloading"
    INACTIVE = "inactive"
    FAILED = "failed"
    ACTIVATING = "activating"
    DEACTIVATING = "deactivating"
    MAINTENANCE = "maintenance"
    REFRESHING = "refreshing"


@dataclass(frozen=True, slots=True)
class MetricSpec:
    unit: Unit
    minimum: float | None
    maximum: float | None


METRICS: Mapping[Metric, MetricSpec] = MappingProxyType(
    {
        Metric.CPU_USAGE: MetricSpec(Unit.PERCENT, 0.0, 100.0),
        Metric.MEMORY_USAGE: MetricSpec(Unit.PERCENT, 0.0, 100.0),
        Metric.DISK_USAGE: MetricSpec(Unit.PERCENT, 0.0, 100.0),
        Metric.LOAD_1M: MetricSpec(Unit.LOAD, 0.0, 10_000.0),
        Metric.LOAD_5M: MetricSpec(Unit.LOAD, 0.0, 10_000.0),
        Metric.LOAD_15M: MetricSpec(Unit.LOAD, 0.0, 10_000.0),
        Metric.CPU_COUNT: MetricSpec(Unit.COUNT, 1.0, 4096.0),
        Metric.TEMPERATURE: MetricSpec(Unit.CELSIUS, -40.0, 150.0),
        Metric.SERVICE_STATE: MetricSpec(Unit.STATE, None, None),
    }
)

if set(METRICS) != set(Metric):
    raise RuntimeError("every Metric needs a MetricSpec")

_SUBJECT = re.compile(r"[A-Za-z0-9_./:-]{1,64}")
_SOURCE = re.compile(r"[a-z][a-z0-9_]{0,31}")
_REASON_PART = r"[a-z0-9_]+(?::[a-z0-9_.]+)?"
_REASON = re.compile(rf"{_REASON_PART}(?:;{_REASON_PART})*")
MAX_REASON_LENGTH = 200
NOT_OBSERVABLE_PREFIX = "not_observable:"


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


@dataclass(frozen=True, slots=True)
class Observation:
    metric: Metric
    subject: str  # what was measured: "cpu", a mount point, a service id, ...
    status: ObservationStatus
    observed_at: datetime
    source: str  # which provider produced it: "psutil", "fake", "systemd_dbus", ...
    value: float | None = None  # numeric metrics, only when available
    state: ServiceState | None = None  # service_state, only when available
    reason: str | None = None  # reason code, required unless available

    def __post_init__(self) -> None:
        if not isinstance(self.metric, Metric):
            raise TypeError("metric must be a Metric")
        if not isinstance(self.status, ObservationStatus):
            raise TypeError("status must be an ObservationStatus")
        require_utc(self.observed_at, "observed_at")
        if not isinstance(self.subject, str) or not _SUBJECT.fullmatch(self.subject):
            raise ValueError(f"invalid subject {self.subject!r}")
        if not isinstance(self.source, str) or not _SOURCE.fullmatch(self.source):
            raise ValueError(f"invalid source {self.source!r}")

        if self.status is ObservationStatus.AVAILABLE:
            if self.reason is not None:
                raise ValueError("an available observation has no reason")
            if self.metric is Metric.SERVICE_STATE:
                if not isinstance(self.state, ServiceState) or self.value is not None:
                    raise ValueError("an available service_state carries a ServiceState only")
            else:
                if self.state is not None or not _is_number(self.value):
                    raise ValueError("an available measurement carries a numeric value only")
                if not _in_range(self.metric, float(self.value)):  # type: ignore[arg-type]
                    raise ValueError(f"{self.metric} value {self.value!r} is out of range")
        else:
            if self.value is not None or self.state is not None:
                raise ValueError("only available observations carry a value")
            if (
                not isinstance(self.reason, str)
                or len(self.reason) > MAX_REASON_LENGTH
                or not _REASON.fullmatch(self.reason)
            ):
                raise ValueError(f"invalid reason code {self.reason!r}")

    @property
    def unit(self) -> Unit:
        return METRICS[self.metric].unit

    @property
    def unobservable_by_design(self) -> bool:
        return self.reason is not None and self.reason.startswith(NOT_OBSERVABLE_PREFIX)


def _in_range(metric: Metric, value: float) -> bool:
    spec = METRICS[metric]
    if not math.isfinite(value):
        return False
    if spec.minimum is not None and value < spec.minimum:
        return False
    return spec.maximum is None or value <= spec.maximum


def measured(
    metric: Metric, subject: str, value: object, *, observed_at: datetime, source: str
) -> Observation:
    """An available observation, or an `error` one if the value is not a valid reading."""
    if metric is Metric.SERVICE_STATE:
        raise ValueError("use a ServiceState observation for service_state")
    if not _is_number(value) or not _in_range(metric, float(value)):  # type: ignore[arg-type]
        return not_measured(
            metric,
            subject,
            ObservationStatus.ERROR,
            "invalid_value",
            observed_at=observed_at,
            source=source,
        )
    return Observation(
        metric=metric,
        subject=subject,
        status=ObservationStatus.AVAILABLE,
        observed_at=observed_at,
        source=source,
        value=float(value),  # type: ignore[arg-type]
    )


def not_measured(
    metric: Metric,
    subject: str,
    status: ObservationStatus,
    reason: str,
    *,
    observed_at: datetime,
    source: str,
) -> Observation:
    if status is ObservationStatus.AVAILABLE:
        raise ValueError("not_measured needs a non-available status")
    return Observation(
        metric=metric,
        subject=subject,
        status=status,
        observed_at=observed_at,
        source=source,
        reason=reason,
    )


@dataclass(frozen=True, slots=True)
class ObservationSnapshot:
    """Everything observed in one pass. Partial: any entry may be non-available."""

    observed_at: datetime
    observations: tuple[Observation, ...]

    def __post_init__(self) -> None:
        require_utc(self.observed_at, "observed_at")
        keys = [(o.metric, o.subject) for o in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("a snapshot holds at most one observation per metric and subject")
        if any(o.observed_at > self.observed_at for o in self.observations):
            raise ValueError("an observation cannot be later than its snapshot")

    def get(self, metric: Metric, subject: str) -> Observation | None:
        for observation in self.observations:
            if observation.metric is metric and observation.subject == subject:
                return observation
        return None

    def available(self, metric: Metric) -> tuple[Observation, ...]:
        return tuple(
            o
            for o in self.observations
            if o.metric is metric and o.status is ObservationStatus.AVAILABLE
        )
