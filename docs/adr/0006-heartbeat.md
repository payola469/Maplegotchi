# ADR-0006: Heartbeat: 300 s, fake time in tests, no external Brain

- **Status:** Accepted — FIXED (CLAUDE.md D6)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
Maple's life advances on a periodic tick. Tests must not wait in real time, and routine ticks must not depend on an LLM.

## Decision
- Production heartbeat is 300 s, configurable.
- Tests and simulations inject a fake clock and advance it instantly.
- An ordinary heartbeat never invokes an external Brain / LLM.

## Consequences
- `Clock` is injected; `core` never reads the wall clock (enforced by the forbidden-API scanner).
- Runtime refuses to start if the heartbeat brain is not `local`.
