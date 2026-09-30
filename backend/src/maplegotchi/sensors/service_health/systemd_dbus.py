"""Read-only systemd service state over D-Bus (provider #2, D4) — only for gaps.

`ReadOnlySystemdClient` is the only thing that talks to the bus, and it can
send exactly two messages, both reads:
  org.freedesktop.systemd1.Manager.GetUnit(unit)
  org.freedesktop.DBus.Properties.Get("org.freedesktop.systemd1.Unit", "ActiveState")
to the systemd bus name, for units on the configured allowlist only. Anything
else is refused before it reaches the transport. There is no systemctl or
subprocess fallback.

The concrete bus transport (a small D-Bus library) is added only if the Phase 3
paolo-core survey shows existing monitoring cannot supply service state; until
then the provider runs without a bus and reports `bus_unavailable`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Protocol

from maplegotchi.core.observations import ObservationStatus, ServiceState
from maplegotchi.sensors.service_health.interface import ServiceReading, ServiceTarget

SYSTEMD_BUS_NAME = "org.freedesktop.systemd1"
MANAGER_PATH = "/org/freedesktop/systemd1"
MANAGER_INTERFACE = "org.freedesktop.systemd1.Manager"
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
UNIT_INTERFACE = "org.freedesktop.systemd1.Unit"

ALLOWED_CALLS = frozenset({(MANAGER_INTERFACE, "GetUnit"), (PROPERTIES_INTERFACE, "Get")})
ALLOWED_PROPERTIES = frozenset({"ActiveState"})
NO_SUCH_UNIT = "org.freedesktop.systemd1.NoSuchUnit"
_UNIT_OBJECT_PATH = re.compile(r"/org/freedesktop/systemd1/unit/[A-Za-z0-9_]{1,255}")


class DbusCallError(Exception):
    """A D-Bus error reply. `name` is the D-Bus error name."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class DbusTransport(Protocol):
    def call(
        self, destination: str, path: str, interface: str, member: str, args: tuple[str, ...]
    ) -> object: ...


class ReadOnlySystemdClient:
    def __init__(self, transport: DbusTransport, allowed_units: frozenset[str]) -> None:
        self._transport = transport
        self._allowed_units = frozenset(allowed_units)

    def _call(self, path: str, interface: str, member: str, *args: str) -> object:
        if (interface, member) not in ALLOWED_CALLS:
            raise PermissionError(f"D-Bus call {interface}.{member} is not allowed")
        if interface == PROPERTIES_INTERFACE and (
            len(args) != 2 or args[0] != UNIT_INTERFACE or args[1] not in ALLOWED_PROPERTIES
        ):
            raise PermissionError("only Unit.ActiveState may be read")
        return self._transport.call(SYSTEMD_BUS_NAME, path, interface, member, args)

    def active_state(self, unit_name: str) -> str:
        if unit_name not in self._allowed_units:
            raise PermissionError(f"unit {unit_name!r} is not on the allowlist")
        path = self._call(MANAGER_PATH, MANAGER_INTERFACE, "GetUnit", unit_name)
        if not isinstance(path, str) or not _UNIT_OBJECT_PATH.fullmatch(path):
            raise DbusCallError("maplegotchi.UnexpectedReply")
        value = self._call(path, PROPERTIES_INTERFACE, "Get", UNIT_INTERFACE, "ActiveState")
        if not isinstance(value, str):
            raise DbusCallError("maplegotchi.UnexpectedReply")
        return value


class SystemdDbusServiceHealth:
    source = "systemd_dbus"

    def __init__(self, client: ReadOnlySystemdClient | None) -> None:
        self._client = client

    def read(self, targets: Sequence[ServiceTarget]) -> Mapping[str, ServiceReading]:
        return {t.service_id: self._read_one(t) for t in targets}

    def _read_one(self, target: ServiceTarget) -> ServiceReading:
        unknown = ObservationStatus.UNKNOWN
        if target.unit_name is None:
            return ServiceReading(unknown, reason="unit_not_configured")
        if self._client is None:
            return ServiceReading(unknown, reason="bus_unavailable")
        try:
            value = self._client.active_state(target.unit_name)
        except DbusCallError as exc:
            reason = "unit_not_loaded" if exc.name == NO_SUCH_UNIT else "dbus_error"
            return ServiceReading(unknown, reason=reason)
        try:
            return ServiceReading(ObservationStatus.AVAILABLE, state=ServiceState(value))
        except ValueError:
            return ServiceReading(unknown, reason="unrecognized_state")
