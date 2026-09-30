"""Read-only systemd service state over D-Bus (provider #2, D4).

`ReadOnlySystemdClient` is the only thing that talks to the bus, and it can
send exactly two messages, both reads:
  org.freedesktop.systemd1.Manager.GetUnit(unit)
  org.freedesktop.DBus.Properties.Get("org.freedesktop.systemd1.Unit", "ActiveState")
to the systemd bus name, for units on the configured allowlist only. Anything
else is refused before it reaches the transport (and the concrete transport in
`dbus_transport` refuses it again). There is no systemctl or subprocess fallback.

A target scheduled by a timer (a oneshot job such as the metrics collector or
the nightly backup) is read from both units:
  service failed                                  -> failed (last run failed)
  service activating/active/deactivating/...      -> that state (running now)
  service inactive (last run finished cleanly)    -> the timer's state
                                                     (active = scheduled)
Every failure to read degrades to `unknown` with a reason; nothing is inferred.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
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
UNIT_OBJECT_PATH = re.compile(r"/org/freedesktop/systemd1/unit/[A-Za-z0-9_]{1,255}")

# D-Bus error names, and the transport's own names for local failures.
NO_SUCH_UNIT = "org.freedesktop.systemd1.NoSuchUnit"
ACCESS_DENIED = "org.freedesktop.DBus.Error.AccessDenied"
AUTH_REQUIRED = "org.freedesktop.DBus.Error.InteractiveAuthorizationRequired"
BUS_UNAVAILABLE = "maplegotchi.BusUnavailable"
BUS_PERMISSION_DENIED = "maplegotchi.BusPermissionDenied"
BUS_TIMEOUT = "maplegotchi.Timeout"
UNEXPECTED_REPLY = "maplegotchi.UnexpectedReply"

_REASONS: Mapping[str, str] = {
    NO_SUCH_UNIT: "unit_not_loaded",
    ACCESS_DENIED: "permission_denied",
    AUTH_REQUIRED: "permission_denied",
    BUS_PERMISSION_DENIED: "permission_denied",
    BUS_UNAVAILABLE: "bus_unavailable",
    BUS_TIMEOUT: "dbus_timeout",
    UNEXPECTED_REPLY: "unexpected_reply",
}


class DbusCallError(Exception):
    """A D-Bus error reply or transport failure. `name` is the D-Bus error name."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class DbusTransport(Protocol):
    def call(
        self, destination: str, path: str, interface: str, member: str, args: tuple[str, ...]
    ) -> object: ...


def check_allowed_call(
    destination: str, path: str, interface: str, member: str, args: tuple[str, ...]
) -> None:
    """Raise PermissionError unless this is one of the two allowlisted read messages."""
    if destination != SYSTEMD_BUS_NAME:
        raise PermissionError(f"destination {destination!r} is not allowed")
    if (interface, member) not in ALLOWED_CALLS:
        raise PermissionError(f"D-Bus call {interface}.{member} is not allowed")
    if member == "GetUnit":
        if path != MANAGER_PATH or len(args) != 1:
            raise PermissionError("GetUnit takes one unit name on the manager object")
    elif (
        not UNIT_OBJECT_PATH.fullmatch(path)
        or len(args) != 2
        or args[0] != UNIT_INTERFACE
        or args[1] not in ALLOWED_PROPERTIES
    ):
        raise PermissionError("only Unit.ActiveState of a unit object may be read")


class ReadOnlySystemdClient:
    def __init__(self, transport: DbusTransport, allowed_units: frozenset[str]) -> None:
        self._transport = transport
        self._allowed_units = frozenset(allowed_units)

    def _call(self, path: str, interface: str, member: str, *args: str) -> object:
        check_allowed_call(SYSTEMD_BUS_NAME, path, interface, member, args)
        return self._transport.call(SYSTEMD_BUS_NAME, path, interface, member, args)

    def active_state(self, unit_name: str) -> str:
        if unit_name not in self._allowed_units:
            raise PermissionError(f"unit {unit_name!r} is not on the allowlist")
        path = self._call(MANAGER_PATH, MANAGER_INTERFACE, "GetUnit", unit_name)
        if not isinstance(path, str) or not UNIT_OBJECT_PATH.fullmatch(path):
            raise DbusCallError(UNEXPECTED_REPLY)
        value = self._call(path, PROPERTIES_INTERFACE, "Get", UNIT_INTERFACE, "ActiveState")
        if not isinstance(value, str):
            raise DbusCallError(UNEXPECTED_REPLY)
        return value


class _Unreadable(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SystemdDbusServiceHealth:
    source = "systemd_dbus"

    def __init__(self, client: ReadOnlySystemdClient | None) -> None:
        self._client = client

    def read(
        self, targets: Sequence[ServiceTarget], *, now: datetime
    ) -> Mapping[str, ServiceReading]:
        return {t.service_id: self._read_one(t) for t in targets}

    def _state(self, client: ReadOnlySystemdClient, unit_name: str) -> ServiceState:
        try:
            value = client.active_state(unit_name)
        except DbusCallError as exc:
            raise _Unreadable(_REASONS.get(exc.name, "dbus_error")) from exc
        except PermissionError as exc:  # not on the allowlist: a wiring mistake
            raise _Unreadable("call_refused") from exc
        try:
            return ServiceState(value)
        except ValueError as exc:
            raise _Unreadable("unrecognized_state") from exc

    def _read_one(self, target: ServiceTarget) -> ServiceReading:
        unknown = ObservationStatus.UNKNOWN
        if target.unit_name is None:
            return ServiceReading(unknown, reason="unit_not_configured")
        if self._client is None:
            return ServiceReading(unknown, reason="bus_unavailable")
        try:
            state = self._state(self._client, target.unit_name)
            if target.timer_name is not None and state is ServiceState.INACTIVE:
                state = self._state(self._client, target.timer_name)
        except _Unreadable as gap:
            return ServiceReading(unknown, reason=gap.reason)
        return ServiceReading(ObservationStatus.AVAILABLE, state=state)
