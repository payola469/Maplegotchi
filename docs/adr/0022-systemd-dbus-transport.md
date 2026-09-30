# ADR-0022: systemd D-Bus transport with dbus-fast

- **Status:** Accepted — FIXED (CLAUDE.md D21)
- **Date:** 2026-09-30
- **Decided by:** owner (Stage B locked decision 8)

## Context
ADR-0004 allowed a read-only D-Bus provider for what monitoring cannot supply.
Stage A: monitoring supplies none of the allowlisted units, and the system bus is
readable by ordinary users.

## Decision
- `DbusFastSystemTransport` (dbus-fast ≥ 5, installed only in Maple's venv) sits
  behind the existing `ReadOnlySystemdClient`. One short-lived connection per call,
  `NO_AUTO_START`, a 2 s timeout, never interactive authorization.
- Exactly two messages exist: `Manager.GetUnit(unit)` on `/org/freedesktop/systemd1`
  and `Properties.Get("org.freedesktop.systemd1.Unit", "ActiveState")` on a unit
  object path. The client and the transport each refuse anything else before
  sending; units must be on the allowlist derived from the service map.
- Every failure (no bus, socket permission, AccessDenied, NoSuchUnit, timeout,
  malformed reply) degrades to `unknown` with a reason; nothing crashes the tick.
- `dbus_fast.aio` is imported lazily (it needs Unix sockets), so Windows development
  reports `bus_unavailable`.

## Consequences
- Only `sensors/service_health/dbus_transport.py` may import dbus_fast (tested).
- polkit additionally denies every action to `maple-svc`.
