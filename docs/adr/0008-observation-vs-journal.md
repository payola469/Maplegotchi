# ADR-0008: Observation and Journal are separate

- **Status:** Accepted — FIXED (CLAUDE.md D8)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
Maple both notices facts and reflects on its life. Mixing them would let interpretation masquerade as fact.

## Decision
- Observation = factual machine/world event data.
- Journal = Maple's interpretation / life record.
- Separate in model, storage, API, and UI. v0.1 journal text is produced by RuleBrain/templates.

## Consequences
- Journal entries may reference observations by id; observations never depend on journal text.
- The UI shows facts only from observations and styles the two differently.
