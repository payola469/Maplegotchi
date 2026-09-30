# ADR-0018: Transient interaction reactions

- **Status:** Accepted — FIXED (CLAUDE.md D17)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
The first Phase 1 implementation cleared a Greet/Pet reaction at the next heartbeat, so its happy expression could linger for up to five minutes.

## Decision
- An interaction may create a transient reaction with an explicit `until`.
- v0.1 reaction duration: 8 seconds.
- A reaction is active only while `started_at <= now < until`.
- The presented expression is derived from a supplied `now`, so the reaction ends at `until` without a heartbeat, scheduler, or timer.

## Consequences
- `MapleState.expression_at(now)` and `MapleState.active_reaction(now)` replace a time-less expression property.
- The stored reaction record may remain until the next heartbeat drops it; presentation ignores it once ended, including after a restart.
- The API (Phase 5) presents state at request time, and the UI hides the reaction at the backend-provided `until`.
