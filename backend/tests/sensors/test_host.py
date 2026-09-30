"""Host sensors: structured readings, honest gaps, isolated failures."""

from __future__ import annotations

import sys
from datetime import UTC, datetime

import pytest

from maplegotchi.core.observations import Metric, ObservationStatus, Unit
from maplegotchi.sensors.fake import FakeHostProbe
from maplegotchi.sensors.host import HOST_METRICS, host_unavailable, read_host
from maplegotchi.sensors.interface import MetricUnavailable
from maplegotchi.sensors.system import PsutilHostProbe

T = datetime(2026, 1, 1, 5, 0, tzinfo=UTC)
A = ObservationStatus.AVAILABLE


def by_key(observations: tuple) -> dict:  # type: ignore[type-arg]
    return {(o.metric, o.subject): o for o in observations}


def test_complete_fake_reading() -> None:
    result = by_key(read_host(FakeHostProbe(), mounts=["/"], now=T))
    expected = {
        (Metric.CPU_USAGE, "cpu"): (18.0, Unit.PERCENT),
        (Metric.MEMORY_USAGE, "memory"): (51.0, Unit.PERCENT),
        (Metric.DISK_USAGE, "/"): (62.0, Unit.PERCENT),
        (Metric.LOAD_1M, "system"): (0.42, Unit.LOAD),
        (Metric.LOAD_5M, "system"): (0.37, Unit.LOAD),
        (Metric.LOAD_15M, "system"): (0.30, Unit.LOAD),
        (Metric.CPU_COUNT, "cpu"): (4.0, Unit.COUNT),
        (Metric.TEMPERATURE, "cpu"): (54.0, Unit.CELSIUS),
    }
    assert {k: (o.value, o.unit) for k, o in result.items()} == expected
    for o in result.values():
        assert o.status is A and o.observed_at == T and o.source == "fake"
    assert {m for m, _ in result} == set(HOST_METRICS)


def test_fake_probe_is_deterministic() -> None:
    assert read_host(FakeHostProbe(), mounts=["/"], now=T) == read_host(
        FakeHostProbe(), mounts=["/"], now=T
    )


def test_unavailable_temperature_is_reported_not_invented() -> None:
    probe = FakeHostProbe(temperature=MetricUnavailable("no_temperature_sensors"))
    temp = by_key(read_host(probe, mounts=["/"], now=T))[(Metric.TEMPERATURE, "cpu")]
    assert temp.status is ObservationStatus.UNAVAILABLE
    assert temp.value is None and temp.reason == "no_temperature_sensors"


def test_one_broken_metric_leaves_the_others_intact() -> None:
    probe = FakeHostProbe(memory=OSError("proc unreadable"))
    result = by_key(read_host(probe, mounts=["/"], now=T))
    broken = result[(Metric.MEMORY_USAGE, "memory")]
    assert broken.status is ObservationStatus.ERROR
    assert broken.reason == "provider_error:oserror"
    healthy = [o for k, o in result.items() if k != (Metric.MEMORY_USAGE, "memory")]
    assert all(o.status is A for o in healthy)


def test_load_failure_marks_all_three_load_windows() -> None:
    probe = FakeHostProbe(load=MetricUnavailable("not_supported_on_platform"))
    result = by_key(read_host(probe, mounts=["/"], now=T))
    for metric in (Metric.LOAD_1M, Metric.LOAD_5M, Metric.LOAD_15M):
        assert result[(metric, "system")].reason == "not_supported_on_platform"


@pytest.mark.parametrize(
    ("field", "raw"),
    [
        ("cpu", float("nan")),
        ("cpu", 140.0),
        ("memory", -3.0),
        ("cpus", 0),
        ("temperature", 900.0),
        ("cpu", "high"),
        ("cpu", True),
        ("load", (1.0, 2.0)),
        ("load", "0.5 0.4 0.3"),
        ("load", (1.0, float("inf"), 0.5)),
    ],
)
def test_invalid_or_extreme_provider_values_become_errors(field: str, raw: object) -> None:
    probe = FakeHostProbe(**{field: raw})  # type: ignore[arg-type]
    result = read_host(probe, mounts=["/"], now=T)
    errors = [o for o in result if o.status is ObservationStatus.ERROR]
    assert errors, f"{field}={raw!r} was accepted"
    assert all(o.reason == "invalid_value" for o in errors)
    assert all(o.value is None for o in errors)


def test_unknown_mount_is_unavailable_and_mounts_are_independent() -> None:
    probe = FakeHostProbe(disks={"/": 62.0, "/data": RuntimeError("stale nfs")})
    result = by_key(read_host(probe, mounts=["/", "/data", "/missing"], now=T))
    assert result[(Metric.DISK_USAGE, "/")].status is A
    assert result[(Metric.DISK_USAGE, "/data")].reason == "provider_error:runtimeerror"
    assert result[(Metric.DISK_USAGE, "/missing")].reason == "mount_not_found"


def test_no_probe_means_every_host_metric_unavailable() -> None:
    result = host_unavailable("no_host_probe", mounts=["/"], now=T)
    assert {o.metric for o in result} == set(HOST_METRICS)
    assert all(o.status is ObservationStatus.UNAVAILABLE for o in result)


# ---------------------------------------------------------------- the real psutil probe


def test_psutil_probe_reads_this_machine_honestly() -> None:
    probe = PsutilHostProbe()
    first = by_key(read_host(probe, mounts=["/"], now=T))
    cpu = first[(Metric.CPU_USAGE, "cpu")]
    assert cpu.status is ObservationStatus.UNAVAILABLE and cpu.reason == "warming_up"
    mem = first[(Metric.MEMORY_USAGE, "memory")]
    assert mem.status is A and mem.value is not None and 0 < mem.value <= 100
    assert first[(Metric.DISK_USAGE, "/")].status is A
    assert first[(Metric.CPU_COUNT, "cpu")].status is A
    load = first[(Metric.LOAD_1M, "system")]
    if sys.platform.startswith("linux"):
        assert load.status is A
    else:
        assert load.reason == "not_supported_on_platform"
    temp = first[(Metric.TEMPERATURE, "cpu")]
    assert temp.status in (A, ObservationStatus.UNAVAILABLE)  # hardware-dependent, never faked

    second = by_key(read_host(probe, mounts=["/"], now=T))[(Metric.CPU_USAGE, "cpu")]
    assert second.status in (A, ObservationStatus.UNAVAILABLE)
    if second.status is A:
        assert second.value is not None and 0 <= second.value <= 100


class _Temp:
    def __init__(self, label: str, current: float) -> None:
        self.label, self.current = label, current


def _chips(monkeypatch: pytest.MonkeyPatch, chips: dict[str, list[_Temp]]) -> None:
    import psutil

    monkeypatch.setattr(psutil, "sensors_temperatures", lambda: chips, raising=False)


def test_coretemp_package_sensor_is_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    # Shapes from the Stage A survey of paolo-core's hwmon chips.
    _chips(
        monkeypatch,
        {
            "acpitz": [_Temp("", 47.0), _Temp("", 27.8)],
            "nvme": [_Temp("Composite", 34.85)],
            "coretemp": [_Temp("Package id 0", 49.0), _Temp("Core 0", 48.0), _Temp("Core 5", 50.0)],
        },
    )
    assert PsutilHostProbe().temperature_celsius() == 49.0


def test_without_a_package_sensor_the_hottest_core_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    _chips(monkeypatch, {"coretemp": [_Temp("Core 0", 48.0), _Temp("Core 1", 51.0)]})
    assert PsutilHostProbe().temperature_celsius() == 51.0


def test_no_temperature_sensors_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    _chips(monkeypatch, {})
    with pytest.raises(MetricUnavailable):
        PsutilHostProbe().temperature_celsius()
