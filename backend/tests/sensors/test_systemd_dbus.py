"""The read-only systemd D-Bus client can send exactly two kinds of read message."""

from __future__ import annotations

import inspect

import pytest

from maplegotchi.core.observations import ObservationStatus, ServiceState
from maplegotchi.sensors.service_health.interface import ServiceTarget
from maplegotchi.sensors.service_health.systemd_dbus import (
    ALLOWED_CALLS,
    MANAGER_INTERFACE,
    NO_SUCH_UNIT,
    PROPERTIES_INTERFACE,
    SYSTEMD_BUS_NAME,
    UNIT_INTERFACE,
    DbusCallError,
    ReadOnlySystemdClient,
    SystemdDbusServiceHealth,
)

UNIT = "grafana-server.service"
UNIT_PATH = "/org/freedesktop/systemd1/unit/grafana_2dserver_2eservice"


class RecordingBus:
    """Fake transport that answers like systemd and records every message."""

    def __init__(self, state: object = "active", get_unit_error: str | None = None) -> None:
        self.calls: list[tuple[str, str, str, str, tuple[str, ...]]] = []
        self.state = state
        self.get_unit_error = get_unit_error

    def call(
        self, destination: str, path: str, interface: str, member: str, args: tuple[str, ...]
    ) -> object:
        self.calls.append((destination, path, interface, member, args))
        if member == "GetUnit":
            if self.get_unit_error:
                raise DbusCallError(self.get_unit_error)
            return UNIT_PATH
        return self.state


def client(bus: RecordingBus, units: frozenset[str] = frozenset({UNIT})) -> ReadOnlySystemdClient:
    return ReadOnlySystemdClient(bus, units)


def test_reads_active_state_with_exactly_two_allowlisted_messages() -> None:
    bus = RecordingBus()
    assert client(bus).active_state(UNIT) == "active"
    assert bus.calls == [
        (SYSTEMD_BUS_NAME, "/org/freedesktop/systemd1", MANAGER_INTERFACE, "GetUnit", (UNIT,)),
        (SYSTEMD_BUS_NAME, UNIT_PATH, PROPERTIES_INTERFACE, "Get", (UNIT_INTERFACE, "ActiveState")),
    ]
    assert {(c[2], c[3]) for c in bus.calls} <= ALLOWED_CALLS


@pytest.mark.parametrize(
    ("interface", "member", "args"),
    [
        (MANAGER_INTERFACE, "StartUnit", (UNIT, "replace")),
        (MANAGER_INTERFACE, "StopUnit", (UNIT, "replace")),
        (MANAGER_INTERFACE, "RestartUnit", (UNIT, "replace")),
        (MANAGER_INTERFACE, "KillUnit", (UNIT, "all", "9")),
        (MANAGER_INTERFACE, "LoadUnit", (UNIT,)),
        (MANAGER_INTERFACE, "Reboot", ()),
        (PROPERTIES_INTERFACE, "Set", (UNIT_INTERFACE, "ActiveState")),
        (PROPERTIES_INTERFACE, "GetAll", (UNIT_INTERFACE,)),
        (PROPERTIES_INTERFACE, "Get", ("org.freedesktop.systemd1.Service", "ExecStart")),
        (PROPERTIES_INTERFACE, "Get", (UNIT_INTERFACE, "FragmentPath")),
        ("org.freedesktop.login1.Manager", "PowerOff", ()),
    ],
)
def test_any_other_message_is_refused_before_reaching_the_bus(
    interface: str, member: str, args: tuple[str, ...]
) -> None:
    bus = RecordingBus()
    with pytest.raises(PermissionError):
        client(bus)._call("/org/freedesktop/systemd1", interface, member, *args)
    assert bus.calls == []


def test_units_off_the_allowlist_are_refused() -> None:
    bus = RecordingBus()
    with pytest.raises(PermissionError):
        client(bus).active_state("ssh.service")
    assert bus.calls == []


def test_client_public_api_is_read_only() -> None:
    public = {n for n, _ in inspect.getmembers(ReadOnlySystemdClient) if not n.startswith("_")}
    assert public == {"active_state"}


def test_unexpected_replies_are_rejected() -> None:
    with pytest.raises(DbusCallError):
        client(RecordingBus(state=42)).active_state(UNIT)

    class OddPath(RecordingBus):
        def call(self, *args: object) -> object:
            return "/etc/passwd"

    with pytest.raises(DbusCallError):
        client(OddPath()).active_state(UNIT)


def readings(provider: SystemdDbusServiceHealth, unit: str | None = UNIT) -> tuple[object, ...]:
    reading = provider.read([ServiceTarget("grafana", unit)])["grafana"]
    return reading.status, reading.state, reading.reason


def test_provider_states() -> None:
    A, U = ObservationStatus.AVAILABLE, ObservationStatus.UNKNOWN
    assert readings(SystemdDbusServiceHealth(client(RecordingBus("failed")))) == (
        A,
        ServiceState.FAILED,
        None,
    )
    assert readings(SystemdDbusServiceHealth(client(RecordingBus("exploded")))) == (
        U,
        None,
        "unrecognized_state",
    )
    missing = RecordingBus(get_unit_error=NO_SUCH_UNIT)
    assert readings(SystemdDbusServiceHealth(client(missing))) == (U, None, "unit_not_loaded")
    denied = RecordingBus(get_unit_error="org.freedesktop.DBus.Error.AccessDenied")
    assert readings(SystemdDbusServiceHealth(client(denied))) == (U, None, "dbus_error")
    assert readings(SystemdDbusServiceHealth(None)) == (U, None, "bus_unavailable")
    assert readings(SystemdDbusServiceHealth(None), unit=None) == (U, None, "unit_not_configured")
