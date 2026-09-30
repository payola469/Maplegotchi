# ADR-0015: Phase 3 read-only paolo-core survey

- **Status:** Accepted — FIXED (CLAUDE.md D15)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
Provider choice and configuration depend on facts only paolo-core can answer.

## Decision
Phase 3 includes an explicit, read-only survey of the real paolo-core runtime before the final service-health provider is selected or configured. Fake sensors/providers are built first so development never depends on access to paolo-core.

## Consequences
- The survey covers at least: `metrics.db` schema, cadence, ownership/permissions, journal mode; actual unit names for the ADR-0012 services; which of those the monitoring data can and cannot supply.
- Findings are recorded under `deploy/survey/` and drive deployment config.
