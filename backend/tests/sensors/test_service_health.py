"""Service health: provider chain, honest unknowns, no guessed unit names."""

from __future__ import annotations

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
