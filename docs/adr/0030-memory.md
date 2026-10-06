# ADR-0030: Maple's memory — short-term, long-term, archive; relevant retrieval; preferences by evidence

- **Status:** Accepted — FIXED (CLAUDE.md D29)
- **Date:** 2026-10-05
- **Decided by:** owner (v0.2 autonomy program, Phase A6). Thresholds and scoring
  are [PROPOSED] tuning.
- **Related:** ADR-0010/0026 (identity is Maple's data; providers are replaceable),
  ADR-0028 (events), ADR-0029 (reading/writing).

## Context

Maple needs a memory that outlives a decision: what just happened, what it learned,
what mattered, and what it seems to like — without feeding its whole history into
every AI call, and without letting one AI sentence become a permanent trait.

## Decision

1. **Memory is Maple's data** in `maple.db` (`memory`, `memory_event`). It is never
   stored by, or keyed to, a Brain/Director provider; switching providers changes
   nothing in it. Directors only ever see a few retrieved items as plain data.
2. **Three tiers**:
   - `short_term` — recent events, goal outcomes, readings, writings, interactions
     (and, later, conversations); kept about 36 hours [PROPOSED];
   - `long_term` — learned knowledge, important moments, accepted preferences,
     important interaction facts; only by explicit promotion;
   - `archive` — everything that left short-term without promotion; searchable
     (`GET /api/memory/search`) but never injected into decision context.
3. **Creation** is a pure core rule over what a transition produced (goal ended,
   reading/writing completed, a serious server problem, the first Greet/Pet of a
   day), committed in the same transaction. Texts are core templates, one line.
4. **Consolidation** (each heartbeat): expired short-term items move to `archive`
   unless promoted. **Nothing is promoted automatically**: promotion is an explicit
   step (Daily Reflection selection, ADR-0031; or explicit confirmation).
5. **Preferences evolve by evidence**: a preference is a `candidate` until it has
   evidence on 3 distinct local days [PROPOSED] or an explicit confirmation; then
   `accepted` (long-term). A single statement (from a Director or anywhere else) can
   at most create or reinforce a candidate. An explicit denial rejects it.
6. **Retrieval** is relevance-ranked and small (default 5 items): keyword overlap
   with the current goal/action, tier, importance, evidence and recency; archive is
   excluded. Used for the Director context (`memories`), the writer, and the
   readable source `memory:long_term`.
7. Every lifecycle step is logged append-only in `memory_event` (created,
   reinforced, promoted, archived, confirmed, rejected).

## Schema v7 and rollback

Two new tables; forward-only; preceded by the verified automatic pre-migration copy;
ADR-0028 R1-R8 apply.

## Consequences

- Decisions and writing can draw on what Maple remembers without unbounded context.
- Long-term memory grows only through reviewed promotion paths.
