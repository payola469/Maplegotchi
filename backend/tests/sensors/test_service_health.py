"""Service health: provider chain, honest unknowns, no guessed unit names."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import pytest

from maplegotchi.core.observations import Metric, ObservationStatus, ServiceState
from maplegotchi.sensors.service_health.fake import FakeServiceHealth
from maplegotchi.sensors.service_health.interface import (
    INTENDED_SERVICES,
    ServiceHealthProvider,
    ServiceReading,
    ServiceTarget,
    get_service_health,
)
from maplegotchi.sensors.service_health.systemd_dbus import SystemdDbusServiceHealth

T = datetime(2026, 1, 1, 5, 0, tzinfo=UTC)
A = ObservationStatus.AVAILABLE
U = ObservationStatus.UNKNOWN


def active(state: ServiceState = ServiceState.ACTIVE) -> ServiceReading:
    return ServiceReading(A, state=state)


def test_intended_services_match_d12_without_guessed_unit_names() -> None:
    assert [t.service_id for t in INTENDED_SERVICES] == [
        "maplegotchi",
        "metrics_collector",
        "grafana",
        "lycan_watch",
        "qbittorrent",
        "jellyfin",
        "backup",
    ]
    assert all(t.unit_name is None for t in INTENDED_SERVICES)


def test_first_available_provider_wins() -> None:
    primary = FakeServiceHealth({"grafana": active()}, source="monitor_db")
    fallback = FakeServiceHealth({"grafana": active(ServiceState.FAILED)}, source="systemd_dbus")
    [o] = get_service_health([ServiceTarget("grafana")], [primary, fallback], now=T)
    assert (o.status, o.state, o.source) == (A, ServiceState.ACTIVE, "monitor_db")


def test_fallback_used_only_for_gaps() -> None:
    primary = FakeServiceHealth({"grafana": active()}, source="monitor_db")
    fallback = FakeServiceHealth({"jellyfin": active(ServiceState.FAILED)}, source="systemd_dbus")
    targets = [ServiceTarget("grafana"), ServiceTarget("jellyfin")]
    result = {o.subject: o for o in get_service_health(targets, [primary, fallback], now=T)}
    assert result["grafana"].source == "monitor_db"
    assert (result["jellyfin"].source, result["jellyfin"].state) == (
        "systemd_dbus",
        ServiceState.FAILED,
    )


def test_unknown_keeps_every_providers_reason() -> None:
    providers: list[ServiceHealthProvider] = [
        FakeServiceHealth(
            {"jellyfin": ServiceReading(U, reason="not_surveyed")}, source="monitor_db"
        ),
        SystemdDbusServiceHealth(client=None),
    ]
    [o] = get_service_health([ServiceTarget("jellyfin")], providers, now=T)
    assert o.metric is Metric.SERVICE_STATE and o.status is U and o.state is None
    assert o.reason == "monitor_db:not_surveyed;systemd_dbus:unit_not_configured"
    assert o.source == "service_health"


def test_broken_provider_does_not_hide_others() -> None:
    broken = FakeServiceHealth({}, source="monitor_db", failure=RuntimeError("db gone"))
    good = FakeServiceHealth({"grafana": active()}, source="systemd_dbus")
    [o] = get_service_health([ServiceTarget("grafana")], [broken, good], now=T)
    assert o.status is A and o.source == "systemd_dbus"
    [lone] = get_service_health([ServiceTarget("grafana")], [broken], now=T)
    assert lone.status is U and lone.reason == "monitor_db:provider_error_runtimeerror"


def test_no_providers_is_unknown() -> None:
    [o] = get_service_health([ServiceTarget("grafana")], [], now=T)
    assert o.status is U and o.reason == "no_provider"


@pytest.mark.parametrize(
    "unit",
    ["grafana", "../grafana.service", "grafana.service;reboot", "grafana service", "x.socket", ""],
)
def test_unit_names_are_validated(unit: str) -> None:
    with pytest.raises(ValueError):
        ServiceTarget("grafana", unit)


def test_valid_unit_names() -> None:
    assert ServiceTarget("backup", "backup-integrity@daily.timer").unit_name
    assert ServiceTarget("grafana", "grafana-server.service").unit_name


@pytest.mark.parametrize("service_id", ["", "Grafana", "1st", "a-b", "x" * 33])
def test_service_ids_are_validated(service_id: str) -> None:
    with pytest.raises(ValueError):
        ServiceTarget(service_id)


def test_service_reading_invariants() -> None:
    with pytest.raises(ValueError):
        ServiceReading(A)
    with pytest.raises(ValueError):
        ServiceReading(U, state=ServiceState.ACTIVE, reason="x")
    with pytest.raises(ValueError):
        ServiceReading(U)


# ---------------------------------------------------------------- Stage A service map


def test_timer_driven_target_lists_both_units() -> None:
    job = ServiceTarget("backup", "paolo-core-backup.service", timer_name="paolo-core-backup.timer")
    assert job.units == ("paolo-core-backup.service", "paolo-core-backup.timer")


@pytest.mark.parametrize(
    ("unit", "timer", "unobservable"),
    [
        (None, "paolo-core-backup.timer", None),  # a timer needs the service it runs
        ("a.timer", "b.timer", None),  # a timer schedules a .service
        ("a.service", "b.service", None),  # timer_name must be a timer
        ("grafana.service", None, "docker_container"),  # unobservable has no units
        (None, None, "Docker Container"),  # reason codes are lowercase words
    ],
)
def test_invalid_targets_are_refused(
    unit: str | None, timer: str | None, unobservable: str | None
) -> None:
    with pytest.raises(ValueError):
        ServiceTarget("backup", unit, timer_name=timer, unobservable=unobservable)


def test_unobservable_targets_are_unknown_without_asking_providers() -> None:
    asked: list[list[str]] = []

    class Spy(FakeServiceHealth):
        def read(
            self, targets: Sequence[ServiceTarget], *, now: datetime
        ) -> Mapping[str, ServiceReading]:
            asked.append([t.service_id for t in targets])
            return super().read(targets, now=now)

    spy = Spy({"backup": active()}, source="systemd_dbus")
    targets = [
        ServiceTarget("grafana", unobservable="docker_container"),
        ServiceTarget("backup", "paolo-core-backup.service"),
    ]
    grafana, backup = get_service_health(targets, [spy], now=T)
    assert (grafana.status, grafana.reason, grafana.source) == (
        U,
        "not_observable:docker_container",
        "service_health",
    )
    assert backup.status is A
    assert asked == [["backup"]]
    get_service_health(targets[:1], [spy], now=T)
    assert asked == [["backup"]]  # nothing observable: providers are not called at all


def test_paolo_core_service_map_matches_the_stage_a_findings() -> None:
    from maplegotchi.runtime.senses import PAOLO_CORE_SERVICES, allowed_units

    by_id = {t.service_id: t for t in PAOLO_CORE_SERVICES}
    assert list(by_id) == ["maplegotchi", "metrics_collector", "grafana", "lycan_watch", "backup"]
    assert "qbittorrent" not in by_id and "jellyfin" not in by_id  # not found on paolo-core
    assert by_id["maplegotchi"] == ServiceTarget("maplegotchi", "maplegotchi.service")
    assert by_id["metrics_collector"] == ServiceTarget(
        "metrics_collector", "personal-ai-monitor.service", timer_name="personal-ai-monitor.timer"
    )
    assert by_id["backup"] == ServiceTarget(
        "backup", "paolo-core-backup.service", timer_name="paolo-core-backup.timer"
    )
    assert by_id["grafana"].unobservable == "docker_container"
    assert by_id["lycan_watch"].unobservable == "no_systemd_unit"
    # The D-Bus allowlist is exactly these five units: no monitor-v2, no Docker, nothing else.
    assert allowed_units(PAOLO_CORE_SERVICES) == {
        "maplegotchi.service",
        "personal-ai-monitor.service",
        "personal-ai-monitor.timer",
        "paolo-core-backup.service",
        "paolo-core-backup.timer",
    }
    assert set(by_id) <= {t.service_id for t in INTENDED_SERVICES}  # within D12 intent
