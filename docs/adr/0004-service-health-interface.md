# ADR-0004: Service health: required, provider-independent, no subprocess

- **Status:** Accepted — FIXED (CLAUDE.md D4)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
Maple should know whether paolo-core's important services are healthy, without ever being able to change them.

## Decision
- Service health is required in v0.1.
- Core sees only `get_service_health()`; providers are swappable.
- Provider order: (1) existing paolo-core monitoring data (ADR-0011), (2) narrowly scoped read-only systemd D-Bus, only for what (1) cannot supply.
- No subprocess, no `systemctl`, no shell fallback of any kind.

## Consequences
- The D-Bus provider may call only `Manager.GetUnit` and `Properties.Get/GetAll` on allowlisted units; a test enforces the method set.
- Missing data is reported as `unknown`.
