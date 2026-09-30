"""Turn a HostProbe into factual observations, one guarded metric at a time.

A probe failing on one metric never affects the others:
- MetricUnavailable      -> `unavailable` with the probe's reason code
- any other exception    -> `error` with `provider_error:<exception type>`
- an invalid raw value   -> `error` with `invalid_value` (checked by core)
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from maplegotchi.core.observations import (
    Metric,
    Observation,
    ObservationStatus,
    measured,
    not_measured,
)
from maplegotchi.sensors.interface import HostProbe, MetricUnavailable

HOST_METRICS = (
    Metric.CPU_USAGE,
    Metric.MEMORY_USAGE,
    Metric.DISK_USAGE,
    Metric.LOAD_1M,
    Metric.LOAD_5M,
    Metric.LOAD_15M,
    Metric.CPU_COUNT,
    Metric.TEMPERATURE,
)


def _error_code(exc: BaseException) -> str:
    return f"provider_error:{type(exc).__name__.lower()}"


def _read_values(
    read: Callable[[], object], arity: int
) -> tuple[list[object], ObservationStatus | None, str | None]:
    try:
        raw = read()
    except MetricUnavailable as gap:
        return [], ObservationStatus.UNAVAILABLE, gap.reason
    except Exception as exc:
        return [], ObservationStatus.ERROR, _error_code(exc)
    if arity == 1:
        return [raw], None, None
    if not isinstance(raw, tuple) or len(raw) != arity:
        return [], ObservationStatus.ERROR, "invalid_value"
    return list(raw), None, None


def read_host(probe: HostProbe, *, mounts: Sequence[str], now: datetime) -> tuple[Observation, ...]:
    source = probe.source
    observations: list[Observation] = []

    def emit(metrics: Sequence[tuple[Metric, str]], read: Callable[[], object]) -> None:
        values, status, reason = _read_values(read, len(metrics))
        for index, (metric, subject) in enumerate(metrics):
            if status is None:
                observations.append(
                    measured(metric, subject, values[index], observed_at=now, source=source)
                )
            else:
                observations.append(
                    not_measured(
                        metric, subject, status, reason or "unknown", observed_at=now, source=source
                    )
                )

    emit([(Metric.CPU_USAGE, "cpu")], probe.cpu_percent)
    emit([(Metric.MEMORY_USAGE, "memory")], probe.memory_percent)
    for mount in mounts:
        emit([(Metric.DISK_USAGE, mount)], lambda m=mount: probe.disk_percent(m))  # type: ignore[misc]
    emit(
        [(Metric.LOAD_1M, "system"), (Metric.LOAD_5M, "system"), (Metric.LOAD_15M, "system")],
        probe.load_average,
    )
    emit([(Metric.CPU_COUNT, "cpu")], probe.cpu_count)
    emit([(Metric.TEMPERATURE, "cpu")], probe.temperature_celsius)
    return tuple(observations)


def host_unavailable(
    reason: str, *, mounts: Sequence[str], now: datetime, source: str = "host"
) -> tuple[Observation, ...]:
    """Every host metric as `unavailable` — used when there is no probe at all."""
    subjects = [
        (Metric.CPU_USAGE, "cpu"),
        (Metric.MEMORY_USAGE, "memory"),
        *[(Metric.DISK_USAGE, m) for m in mounts],
        (Metric.LOAD_1M, "system"),
        (Metric.LOAD_5M, "system"),
        (Metric.LOAD_15M, "system"),
        (Metric.CPU_COUNT, "cpu"),
        (Metric.TEMPERATURE, "cpu"),
    ]
    return tuple(
        not_measured(m, s, ObservationStatus.UNAVAILABLE, reason, observed_at=now, source=source)
        for m, s in subjects
    )
