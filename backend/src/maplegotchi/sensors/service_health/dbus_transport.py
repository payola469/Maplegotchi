"""The concrete system-bus transport for `ReadOnlySystemdClient` (dbus-fast).

Deliberately narrow:
- connects to the system bus, sends one method call, reads one reply, disconnects;
- re-checks every message against the same two-call allowlist as the client
  (GetUnit on the manager, Properties.Get of Unit.ActiveState), so it cannot be
  used as a generic D-Bus pass-through even when called directly;
- sets NO_AUTO_START and never ALLOW_INTERACTIVE_AUTHORIZATION;
- every failure (no bus, permission, timeout, error reply, odd reply) becomes a
  `DbusCallError`, which the provider reports as `unknown` with a reason.

The life loop reads senses in a worker thread (`asyncio.to_thread`), so each
call runs its own short-lived event loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from dbus_fast import BusType, Message, MessageFlag, MessageType, Variant

from maplegotchi.sensors.service_health.systemd_dbus import (
    BUS_PERMISSION_DENIED,
    BUS_TIMEOUT,
    BUS_UNAVAILABLE,
    UNEXPECTED_REPLY,
    DbusCallError,
    check_allowed_call,
)

DEFAULT_TIMEOUT_SECONDS = 2.0
_REQUEST_SIGNATURE = {"GetUnit": "s", "Get": "ss"}
_REPLY_SIGNATURE = {"GetUnit": "o", "Get": "v"}

Roundtrip = Callable[[Message], Awaitable[Message]]


def build_message(
    destination: str, path: str, interface: str, member: str, args: tuple[str, ...]
) -> Message:
    check_allowed_call(destination, path, interface, member, args)
    return Message(
        destination=destination,
        path=path,
        interface=interface,
        member=member,
        signature=_REQUEST_SIGNATURE[member],
        body=list(args),
        flags=MessageFlag.NO_AUTOSTART,
    )


def decode_reply(member: str, reply: Message) -> str:
    """The single string value of an allowlisted reply, or DbusCallError."""
    if reply.message_type is MessageType.ERROR:
        raise DbusCallError(str(reply.error_name or "org.freedesktop.DBus.Error.Failed"))
    if reply.message_type is not MessageType.METHOD_RETURN:
        raise DbusCallError(UNEXPECTED_REPLY)
    if reply.signature != _REPLY_SIGNATURE[member] or len(reply.body) != 1:
        raise DbusCallError(UNEXPECTED_REPLY)
    value = reply.body[0]
    if member == "Get":
        if not isinstance(value, Variant) or value.signature != "s":
            raise DbusCallError(UNEXPECTED_REPLY)
        value = value.value
    if not isinstance(value, str):
        raise DbusCallError(UNEXPECTED_REPLY)
    return value


async def _system_bus_roundtrip(message: Message) -> Message:
    # Imported here: dbus_fast.aio needs Unix socket support, so on Windows
    # (development) it fails at import and the provider reports bus_unavailable.
    from dbus_fast.aio import MessageBus

    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    try:
        return await bus.call(message)
    finally:
        bus.disconnect()


class DbusFastSystemTransport:
    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        roundtrip: Roundtrip = _system_bus_roundtrip,  # replaceable in tests only
    ) -> None:
        if not 0 < timeout_seconds <= 30:
            raise ValueError("timeout_seconds must be in (0, 30]")
        self._timeout = timeout_seconds
        self._roundtrip = roundtrip

    def call(
        self, destination: str, path: str, interface: str, member: str, args: tuple[str, ...]
    ) -> object:
        message = build_message(destination, path, interface, member, args)
        try:
            reply = asyncio.run(self._bounded(message))
        except TimeoutError as exc:
            raise DbusCallError(BUS_TIMEOUT) from exc
        except PermissionError as exc:  # socket permission, not an allowlist refusal
            raise DbusCallError(BUS_PERMISSION_DENIED) from exc
        except Exception as exc:  # no bus, auth failure, running loop, library error
            raise DbusCallError(BUS_UNAVAILABLE) from exc
        return decode_reply(member, reply)

    async def _bounded(self, message: Message) -> Message:
        async with asyncio.timeout(self._timeout):
            return await self._roundtrip(message)
