# ADR-0017: Maple's home timezone

- **Status:** Accepted — FIXED (CLAUDE.md D16)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
Day/night behavior needs Maple's local time. Core must stay pure and cannot read system timezone data.

## Decision
paolo-core's production local time is Asia/Bangkok: UTC+07:00, no daylight saving. Core's default `utc_offset` is +07:00. The offset remains a parameter so tests and simulations can inject any value.

## Consequences
- A fixed offset is exact for Asia/Bangkok because it has no DST.
- Core never consults a timezone database; runtime may pass a different offset if the deployment ever changes.
