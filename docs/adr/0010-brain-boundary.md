# ADR-0010: Replaceable Brain, RuleBrain default

- **Status:** Accepted — FIXED (CLAUDE.md D10)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
An LLM may later help Maple choose activities or write journal entries. Maple's identity must not belong to any provider.

## Decision
- A `Brain` interface (`kind: local | external`) receives an explicit serialisable context and returns advisory output that core validates.
- RuleBrain (local) is the v0.1 default. No external LLM integration yet.
- Adding one later must not change Maple's identity or core state model.

## Consequences
- Identity lives in Maple's data and is passed to the Brain.
- A Brain cannot write state, touch files, or call tools.
