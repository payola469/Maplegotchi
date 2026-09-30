"""observe_paolo_core(): one snapshot, tolerant of partial failure."""

from __future__ import annotations

from datetime import UTC, datetime

from maplegotchi.core.observations import (
    Metric,
    ObservationSnapshot,
    ObservationStatus,
    ServiceState,
)
from maplegotchi.runtime.senses import PAOLO_CORE_SERVICES, Senses, paolo_core_senses
from maplegotchi.sensors.fake import FakeHostProbe
from maplegotchi.sensors.interface import MetricUnavailable
from maplegotchi.sensors.observe import observe_paolo_core
from maplegotchi.sensors.service_health.fake import FakeServiceHealth
from maplegotchi.sensors.service_health.interface import (
    INTENDED_SERVICES,
    ServiceReading,
    ServiceTarget,
)
from maplegotchi.sensors.service_health.systemd_dbus import SystemdDbusServiceHealth

T = datetime(2026, 1, 1, 5, 0, tzinfo=UTC)
A = ObservationStatus.AVAILABLE


def all_active() -> FakeServiceHealth:
    return FakeServiceHealth(
        {t.service_id: ServiceReading(A, state=ServiceState.ACTIVE) for t in INTENDED_SERVICES}
    )


def test_complete_snapshot() -> None:
    snap = observe_paolo_core(FakeHostProbe(), [all_active()], INTENDED_SERVICES, now=T)
    assert snap.observed_at == T
    assert len(snap.observations) == 8 + len(INTENDED_SERVICES)
    assert all(o.status is A for o in snap.observations)
    assert all(o.observed_at == T for o in snap.observations)


def test_partial_failure_snapshot_keeps_healthy_readings() -> None:
    host = FakeHostProbe(
        temperature=MetricUnavailable("no_temperature_sensors"), memory=OSError("boom")
    )
    services = FakeServiceHealth(
        {"grafana": ServiceReading(A, state=ServiceState.ACTIVE)}, source="monitor_db"
    )
    snap = observe_paolo_core(
        host,
        [services, SystemdDbusServiceHealth(None)],
        [ServiceTarget("grafana"), ServiceTarget("jellyfin")],
        now=T,
    )
    status = {(o.metric, o.subject): o.status for o in snap.observations}
    assert status[(Metric.CPU_USAGE, "cpu")] is A
    assert status[(Metric.DISK_USAGE, "/")] is A
    assert status[(Metric.TEMPERATURE, "cpu")] is ObservationStatus.UNAVAILABLE
    assert status[(Metric.MEMORY_USAGE, "memory")] is ObservationStatus.ERROR
    assert status[(Metric.SERVICE_STATE, "grafana")] is A
    assert status[(Metric.SERVICE_STATE, "jellyfin")] is ObservationStatus.UNKNOWN


def test_every_provider_broken_still_yields_a_valid_snapshot() -> None:
    host = FakeHostProbe(
        cpu=RuntimeError(), memory=RuntimeError(), disks={"/": RuntimeError()},
        load=RuntimeError(), cpus=RuntimeError(), temperature=RuntimeError(),
    )  # fmt: skip
    broken = FakeServiceHealth({}, failure=ConnectionError())
    snap = observe_paolo_core(host, [broken], INTENDED_SERVICES, now=T)
    assert len(snap.observations) == 8 + len(INTENDED_SERVICES)
    assert all(o.status is not A for o in snap.observations)


def test_no_host_probe() -> None:
    snap = observe_paolo_core(None, [], [ServiceTarget("grafana")], now=T)
    host = [o for o in snap.observations if o.metric is not Metric.SERVICE_STATE]
    assert host and all(o.reason == "no_host_probe" for o in host)


def test_fake_snapshots_are_deterministic() -> None:
    def take() -> ObservationSnapshot:
        return Senses(FakeHostProbe(), (all_active(),)).observe(T)

    assert take() == take()


def test_real_senses_on_this_machine_are_honest(tmp_path) -> None:  # type: ignore[no-untyped-def]
    senses = paolo_core_senses(monitor_db=tmp_path / "metrics.db")
    snap = senses.observe(datetime.now(UTC))
    services = {o.subject: o for o in snap.observations if o.metric is Metric.SERVICE_STATE}
    assert list(services) == [t.service_id for t in PAOLO_CORE_SERVICES]
    # No metrics.db here, and none of paolo-core's units exist on a dev/CI machine
    # (or there is no system bus at all): honestly unknown, never invented.
    assert all(o.status is ObservationStatus.UNKNOWN for o in services.values())
    assert services["grafana"].reason == "not_observable:docker_container"
    assert services["lycan_watch"].reason == "not_observable:no_systemd_unit"
    assert services["metrics_collector"].reason is not None
    assert services["metrics_collector"].reason.startswith("monitor_db:source_missing;")
    for service_id in ("maplegotchi", "backup"):
        reason = services[service_id].reason
        assert reason is not None and reason.startswith("monitor_db:not_recorded;systemd_dbus:")
    assert snap.get(Metric.MEMORY_USAGE, "memory") is not None
