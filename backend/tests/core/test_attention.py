"""server_attention: a bounded, deterministic reduction of factual observations."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from maplegotchi.core.attention import (
    assess_server_attention,
    behavior_inputs,
)
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.observations import (
    Metric,
    Observation,
    ObservationSnapshot,
    ObservationStatus,
    ServiceState,
    measured,
    not_measured,
)

T = datetime(2026, 1, 1, 5, 0, tzinfo=UTC)


def m(metric: Metric, value: float, subject: str = "x") -> Observation:
    return measured(metric, subject, value, observed_at=T, source="fake")


def service(name: str, state: ServiceState) -> Observation:
    return Observation(
        metric=Metric.SERVICE_STATE,
        subject=name,
        status=ObservationStatus.AVAILABLE,
        observed_at=T,
        source="fake",
        state=state,
    )


def gap(metric: Metric, subject: str, status: ObservationStatus) -> Observation:
    return not_measured(metric, subject, status, "no_data", observed_at=T, source="fake")


def snap(*observations: Observation) -> ObservationSnapshot:
    return ObservationSnapshot(observed_at=T, observations=observations)


CALM = snap(
    m(Metric.CPU_USAGE, 18.0, "cpu"),
    m(Metric.MEMORY_USAGE, 51.0, "memory"),
    m(Metric.DISK_USAGE, 62.0, "/"),
    m(Metric.LOAD_1M, 0.4, "system"),
    m(Metric.CPU_COUNT, 4, "cpu"),
    m(Metric.TEMPERATURE, 54.0, "cpu"),
    service("jellyfin", ServiceState.ACTIVE),
)


def test_no_snapshot_and_calm_server_mean_no_attention() -> None:
    assert assess_server_attention(None).level == 0.0
    calm = assess_server_attention(CALM)
    assert calm.level == 0.0 and calm.reasons == ()
    assert behavior_inputs(CALM) == BehaviorInputs(server_attention=0.0)


@pytest.mark.parametrize(
    ("observation", "level", "reason"),
    [
        (m(Metric.CPU_USAGE, 74.99, "cpu"), 0.0, None),
        (m(Metric.CPU_USAGE, 75.0, "cpu"), 0.3, "cpu_usage:cpu>=75"),
        (m(Metric.CPU_USAGE, 90.0, "cpu"), 0.6, "cpu_usage:cpu>=90"),
        (m(Metric.MEMORY_USAGE, 80.0, "memory"), 0.3, "memory_usage:memory>=80"),
        (m(Metric.MEMORY_USAGE, 95.0, "memory"), 0.6, "memory_usage:memory>=90"),
        (m(Metric.DISK_USAGE, 85.0, "/"), 0.4, "disk_usage:/>=85"),
        (m(Metric.DISK_USAGE, 96.0, "/"), 0.8, "disk_usage:/>=95"),
        (m(Metric.TEMPERATURE, 75.0, "cpu"), 0.4, "temperature:cpu>=75"),
        (m(Metric.TEMPERATURE, 90.0, "cpu"), 0.8, "temperature:cpu>=85"),
        (service("grafana", ServiceState.FAILED), 0.8, "service_state:grafana=failed"),
        (service("backup", ServiceState.INACTIVE), 0.0, None),  # inactive can be normal
        (service("grafana", ServiceState.ACTIVATING), 0.0, None),
    ],
)
def test_single_fact_thresholds(observation: Observation, level: float, reason: str | None) -> None:
    result = assess_server_attention(snap(observation))
    assert result.level == level
    assert result.reasons == ((reason,) if reason else ())


def test_load_is_judged_per_cpu() -> None:
    four_cpus = m(Metric.CPU_COUNT, 4, "cpu")
    assert assess_server_attention(snap(m(Metric.LOAD_1M, 3.9, "system"), four_cpus)).level == 0
    busy = assess_server_attention(snap(m(Metric.LOAD_1M, 4.0, "system"), four_cpus))
    assert busy.level == 0.25 and busy.reasons == ("load_per_cpu:1m>=1",)
    overloaded = assess_server_attention(snap(m(Metric.LOAD_1M, 8.0, "system"), four_cpus))
    assert overloaded.level == 0.5
    # Without a CPU count, load alone says nothing.
    assert assess_server_attention(snap(m(Metric.LOAD_1M, 50.0, "system"))).level == 0


def test_combination_is_max_not_sum_and_bounded() -> None:
    everything = snap(
        m(Metric.CPU_USAGE, 100.0, "cpu"),
        m(Metric.MEMORY_USAGE, 100.0, "memory"),
        m(Metric.DISK_USAGE, 100.0, "/"),
        m(Metric.DISK_USAGE, 99.0, "/data"),
        m(Metric.TEMPERATURE, 150.0, "cpu"),
        m(Metric.LOAD_1M, 100.0, "system"),
        m(Metric.CPU_COUNT, 1, "cpu"),
        service("grafana", ServiceState.FAILED),
        service("jellyfin", ServiceState.FAILED),
    )
    result = assess_server_attention(everything)
    assert result.level == 0.8
    assert 0.0 <= result.level <= 1.0
    assert len(result.reasons) == 8  # every crossed threshold is named
    BehaviorInputs(server_attention=result.level)  # always a valid input


@pytest.mark.parametrize(
    "status", [ObservationStatus.UNAVAILABLE, ObservationStatus.UNKNOWN, ObservationStatus.ERROR]
)
def test_missing_data_never_manufactures_attention(status: ObservationStatus) -> None:
    gaps = snap(
        gap(Metric.CPU_USAGE, "cpu", status),
        gap(Metric.TEMPERATURE, "cpu", status),
        gap(Metric.SERVICE_STATE, "jellyfin", status),
    )
    assert assess_server_attention(gaps).level == 0.0


def test_derivation_is_deterministic_and_order_independent() -> None:
    a = snap(m(Metric.DISK_USAGE, 96.0, "/b"), m(Metric.DISK_USAGE, 90.0, "/a"))
    b = snap(m(Metric.DISK_USAGE, 90.0, "/a"), m(Metric.DISK_USAGE, 96.0, "/b"))
    assert assess_server_attention(a) == assess_server_attention(b)
    assert assess_server_attention(a).reasons == ("disk_usage:/a>=85", "disk_usage:/b>=95")
