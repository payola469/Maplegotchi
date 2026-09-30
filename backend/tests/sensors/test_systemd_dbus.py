"""The read-only systemd D-Bus client can send exactly two kinds of read message."""

from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime

import pytest
from dbus_fast import Message, MessageFlag, MessageType, Variant

from maplegotchi.core.observations import ObservationStatus, ServiceState
from maplegotchi.sensors.service_health.dbus_transport import DbusFastSystemTransport
from maplegotchi.sensors.service_health.interface import ServiceTarget
from maplegotchi.sensors.service_health.systemd_dbus import (
    ACCESS_DENIED,
    ALLOWED_CALLS,
    BUS_PERMISSION_DENIED,
    BUS_TIMEOUT,
    BUS_UNAVAILABLE,
    MANAGER_INTERFACE,
    NO_SUCH_UNIT,
    PROPERTIES_INTERFACE,
    SYSTEMD_BUS_NAME,
    UNEXPECTED_REPLY,
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


T = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
A, U = ObservationStatus.AVAILABLE, ObservationStatus.UNKNOWN


def readings(provider: SystemdDbusServiceHealth, unit: str | None = UNIT) -> tuple[object, ...]:
    reading = provider.read([ServiceTarget("grafana", unit)], now=T)["grafana"]
    return reading.status, reading.state, reading.reason


@pytest.mark.parametrize("state", ["active", "inactive", "failed", "activating"])
def test_provider_reports_systemd_states(state: str) -> None:
    provider = SystemdDbusServiceHealth(client(RecordingBus(state)))
    assert readings(provider) == (A, ServiceState(state), None)


@pytest.mark.parametrize(
    ("bus", "reason"),
    [
        (RecordingBus("exploded"), "unrecognized_state"),
        (RecordingBus(get_unit_error=NO_SUCH_UNIT), "unit_not_loaded"),
        (RecordingBus(get_unit_error=ACCESS_DENIED), "permission_denied"),
        (RecordingBus(get_unit_error=BUS_PERMISSION_DENIED), "permission_denied"),
        (RecordingBus(get_unit_error=BUS_UNAVAILABLE), "bus_unavailable"),
        (RecordingBus(get_unit_error=BUS_TIMEOUT), "dbus_timeout"),
        (RecordingBus(get_unit_error="org.freedesktop.DBus.Error.Failed"), "dbus_error"),
        (RecordingBus(state=42), "unexpected_reply"),
        (RecordingBus(state=None), "unexpected_reply"),
    ],
)
def test_every_failure_is_unknown_with_a_reason(bus: RecordingBus, reason: str) -> None:
    assert readings(SystemdDbusServiceHealth(client(bus))) == (U, None, reason)


def test_provider_without_bus_or_units() -> None:
    assert readings(SystemdDbusServiceHealth(None)) == (U, None, "bus_unavailable")
    assert readings(SystemdDbusServiceHealth(None), unit=None) == (U, None, "unit_not_configured")


def test_unit_off_the_allowlist_is_unknown_not_a_crash() -> None:
    bus = RecordingBus()
    provider = SystemdDbusServiceHealth(client(bus, units=frozenset()))
    assert readings(provider) == (U, None, "call_refused")
    assert bus.calls == []


# ---------------------------------------------------------------- timer-driven jobs

JOB = "personal-ai-monitor.service"
TIMER = "personal-ai-monitor.timer"


class UnitBus:
    """Answers per unit: a state string, or a D-Bus error name to raise."""

    def __init__(self, answers: dict[str, str]) -> None:
        self.answers = answers
        self.asked: list[str] = []

    def call(
        self, destination: str, path: str, interface: str, member: str, args: tuple[str, ...]
    ) -> object:
        if member == "GetUnit":
            self.asked.append(args[0])
            answer = self.answers[args[0]]
            if answer.startswith(("org.", "maplegotchi.")):
                raise DbusCallError(answer)
            escaped = args[0].replace("-", "_2d").replace(".", "_2e")
            return "/org/freedesktop/systemd1/unit/" + escaped
        return self.answers[self.asked[-1]]


def job_reading(answers: dict[str, str]) -> tuple[object, ...]:
    bus = UnitBus(answers)
    provider = SystemdDbusServiceHealth(ReadOnlySystemdClient(bus, frozenset({JOB, TIMER})))
    target = ServiceTarget("metrics_collector", JOB, timer_name=TIMER)
    reading = provider.read([target], now=T)["metrics_collector"]
    return reading.status, reading.state, reading.reason


@pytest.mark.parametrize(
    ("service", "timer", "expected"),
    [
        ("inactive", "active", (A, ServiceState.ACTIVE, None)),  # ran cleanly, scheduled
        ("inactive", "inactive", (A, ServiceState.INACTIVE, None)),  # timer stopped
        ("inactive", "failed", (A, ServiceState.FAILED, None)),
        ("failed", "active", (A, ServiceState.FAILED, None)),  # last run failed
        ("activating", "active", (A, ServiceState.ACTIVATING, None)),  # running now
        ("inactive", NO_SUCH_UNIT, (U, None, "unit_not_loaded")),
        (ACCESS_DENIED, "active", (U, None, "permission_denied")),
    ],
)
def test_timer_driven_job_composition(
    service: str, timer: str, expected: tuple[object, ...]
) -> None:
    assert job_reading({JOB: service, TIMER: timer}) == expected


def test_timer_is_read_only_when_the_job_is_idle() -> None:
    bus = UnitBus({JOB: "failed", TIMER: "active"})
    provider = SystemdDbusServiceHealth(ReadOnlySystemdClient(bus, frozenset({JOB, TIMER})))
    provider.read([ServiceTarget("metrics_collector", JOB, timer_name=TIMER)], now=T)
    assert bus.asked == [JOB]


# ---------------------------------------------------------------- dbus-fast transport

GET_UNIT = (SYSTEMD_BUS_NAME, "/org/freedesktop/systemd1", MANAGER_INTERFACE, "GetUnit", (UNIT,))
GET_STATE = (
    SYSTEMD_BUS_NAME,
    UNIT_PATH,
    PROPERTIES_INTERFACE,
    "Get",
    (UNIT_INTERFACE, "ActiveState"),
)


def reply(signature: str, body: list[object]) -> Message:
    return Message(
        message_type=MessageType.METHOD_RETURN, reply_serial=1, signature=signature, body=body
    )


def error_reply(name: str) -> Message:
    return Message(message_type=MessageType.ERROR, reply_serial=1, error_name=name)


class ScriptedRoundtrip:
    def __init__(self, *answers: Message | BaseException) -> None:
        self.answers = list(answers)
        self.sent: list[Message] = []

    async def __call__(self, message: Message) -> Message:
        self.sent.append(message)
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer


def test_transport_sends_only_the_two_reads_without_autostart() -> None:
    roundtrip = ScriptedRoundtrip(reply("o", [UNIT_PATH]), reply("v", [Variant("s", "failed")]))
    transport = DbusFastSystemTransport(roundtrip=roundtrip)
    assert ReadOnlySystemdClient(transport, frozenset({UNIT})).active_state(UNIT) == "failed"
    sent = [(m.destination, m.path, m.interface, m.member, tuple(m.body)) for m in roundtrip.sent]
    assert sent == [GET_UNIT, GET_STATE]
    assert all(m.flags == MessageFlag.NO_AUTOSTART for m in roundtrip.sent)
    assert [m.signature for m in roundtrip.sent] == ["s", "ss"]


MANAGER = "/org/freedesktop/systemd1"
LOGIN = "org.freedesktop.login1"


@pytest.mark.parametrize(
    ("destination", "path", "interface", "member", "args"),
    [
        (SYSTEMD_BUS_NAME, MANAGER, MANAGER_INTERFACE, "StartUnit", (UNIT, "replace")),
        (SYSTEMD_BUS_NAME, MANAGER, MANAGER_INTERFACE, "StopUnit", (UNIT, "replace")),
        (SYSTEMD_BUS_NAME, MANAGER, MANAGER_INTERFACE, "RestartUnit", (UNIT, "replace")),
        (SYSTEMD_BUS_NAME, MANAGER, MANAGER_INTERFACE, "EnableUnitFiles", (UNIT,)),
        (SYSTEMD_BUS_NAME, MANAGER, MANAGER_INTERFACE, "DisableUnitFiles", (UNIT,)),
        (SYSTEMD_BUS_NAME, MANAGER, MANAGER_INTERFACE, "Reload", ()),
        (SYSTEMD_BUS_NAME, MANAGER, MANAGER_INTERFACE, "GetUnit", (UNIT, "extra")),
        (SYSTEMD_BUS_NAME, UNIT_PATH, MANAGER_INTERFACE, "GetUnit", (UNIT,)),
        (SYSTEMD_BUS_NAME, UNIT_PATH, PROPERTIES_INTERFACE, "Set", (UNIT_INTERFACE, "ActiveState")),
        (SYSTEMD_BUS_NAME, UNIT_PATH, PROPERTIES_INTERFACE, "GetAll", (UNIT_INTERFACE,)),
        (SYSTEMD_BUS_NAME, UNIT_PATH, PROPERTIES_INTERFACE, "Get", (UNIT_INTERFACE, "ExecStart")),
        (SYSTEMD_BUS_NAME, "/etc/passwd", PROPERTIES_INTERFACE, "Get", GET_STATE[4]),
        (SYSTEMD_BUS_NAME, MANAGER, PROPERTIES_INTERFACE, "Get", (UNIT_INTERFACE, "ActiveState")),
        (LOGIN, "/org/freedesktop/login1", "org.freedesktop.login1.Manager", "PowerOff", ()),
        (LOGIN, MANAGER, MANAGER_INTERFACE, "GetUnit", (UNIT,)),
    ],
)  # fmt: skip
def test_transport_refuses_everything_else_before_sending(
    destination: str, path: str, interface: str, member: str, args: tuple[str, ...]
) -> None:
    roundtrip = ScriptedRoundtrip()
    transport = DbusFastSystemTransport(roundtrip=roundtrip)
    with pytest.raises(PermissionError):
        transport.call(destination, path, interface, member, args)
    assert roundtrip.sent == []


def test_transport_public_api_is_one_call() -> None:
    public = {n for n, _ in inspect.getmembers(DbusFastSystemTransport) if not n.startswith("_")}
    assert public == {"call"}


@pytest.mark.parametrize(
    ("answer", "error_name"),
    [
        (error_reply(NO_SUCH_UNIT), NO_SUCH_UNIT),
        (error_reply(ACCESS_DENIED), ACCESS_DENIED),
        (FileNotFoundError("/run/dbus/system_bus_socket"), BUS_UNAVAILABLE),
        (ConnectionRefusedError(), BUS_UNAVAILABLE),
        (PermissionError("socket"), BUS_PERMISSION_DENIED),
        (RuntimeError("library bug"), BUS_UNAVAILABLE),
        (reply("s", ["not-an-object-path"]), UNEXPECTED_REPLY),
        (reply("u", [7]), UNEXPECTED_REPLY),
    ],
)
def test_transport_failures_become_dbus_call_errors(
    answer: Message | BaseException, error_name: str
) -> None:
    transport = DbusFastSystemTransport(roundtrip=ScriptedRoundtrip(answer))
    with pytest.raises(DbusCallError) as caught:
        transport.call(*GET_UNIT)
    assert caught.value.name == error_name


async def _too_slow(message: Message) -> Message:
    await asyncio.sleep(5)
    raise AssertionError("unreachable")


def test_transport_timeout() -> None:
    transport = DbusFastSystemTransport(timeout_seconds=0.01, roundtrip=_too_slow)
    with pytest.raises(DbusCallError) as caught:
        transport.call(*GET_UNIT)
    assert caught.value.name == BUS_TIMEOUT


@pytest.mark.parametrize(
    ("signature", "value"),
    [("v", Variant("u", 3)), ("v", Variant("as", ["active"])), ("s", "active")],
)
def test_transport_rejects_odd_property_replies(signature: str, value: object) -> None:
    transport = DbusFastSystemTransport(roundtrip=ScriptedRoundtrip(reply(signature, [value])))
    with pytest.raises(DbusCallError) as caught:
        transport.call(*GET_STATE)
    assert caught.value.name == UNEXPECTED_REPLY


def test_real_transport_degrades_on_any_machine() -> None:
    """No such unit exists anywhere: NoSuchUnit, or no usable bus — never a crash."""
    absent = "maplegotchi-test-absent.service"
    systemd = ReadOnlySystemdClient(DbusFastSystemTransport(), frozenset({absent}))
    with pytest.raises(DbusCallError) as caught:
        systemd.active_state(absent)
    assert caught.value.name in {NO_SUCH_UNIT, BUS_UNAVAILABLE, BUS_PERMISSION_DENIED}
