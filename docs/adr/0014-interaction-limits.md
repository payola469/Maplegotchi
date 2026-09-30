# ADR-0014: Interaction cooldowns and rate limit

- **Status:** Accepted — FIXED (CLAUDE.md D14)
- **Date:** 2026-09-30
- **Decided by:** owner

## Decision
- Greet: 60 s cooldown.
- Pet: 30 s cooldown.
- Global: 10 interactions per 10 minutes.
- Cooldown and rate-limit state is persisted; a restart cannot reset it.

## Consequences
- Limits are enforced by the backend as part of Maple's state; rejections return `429` with `retry_after`, which the UI displays.
