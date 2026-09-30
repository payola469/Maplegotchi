# ADR-0009: 72-hour trial gates only the stable release

- **Status:** Accepted — FIXED (CLAUDE.md D9)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
A long trial run on paolo-core is needed for confidence, but should not stall development.

## Decision
A 72-hour trial run on paolo-core is required before declaring v0.1 stable. It does not block earlier milestones or local visual testing.

## Consequences
- Milestones: M1 headless local, M2 local playable, M3 `v0.1.0-rc` on paolo-core, then `v0.1.0` after the trial.
