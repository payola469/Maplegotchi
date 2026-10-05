# ADR-0031: Daily Reflection — summarize the day, choose memories, set tomorrow's intent

- **Status:** Accepted — FIXED (CLAUDE.md D30)
- **Date:** 2026-10-06
- **Decided by:** owner (v0.2 autonomy program, Phase A7: summarize → candidate memories →
  tomorrow intent; before main nighttime sleep; recover after restart/wake; never rewrite
  mood/energy). Selection thresholds are [PROPOSED].
- **Related:** ADR-0026 (Director), ADR-0029 (reading/writing), ADR-0030 (memory).

## Decision

1. **What**: once per Maple day (local 06:00 → 06:00), core produces a Daily Reflection:
   a day summary, what was learned, important moments, memory candidates, preference
   candidates, and a tomorrow intent (a goal type and one-line summary).
2. **Inputs** (facts from the day only): goals started/completed/abandoned, completed
   actions, things read and written, Greet/Pet (and, later, conversations with Paolo),
   serious server events, interruptions and failures (rejected/fallback decisions, failed
   reads/writes), and the needs now vs. at the previous reflection.
3. **When**: when Maple begins its main night sleep (a `sleep` action starting at night).
   **Fallback**: if the previous Maple day was not reflected (restart, failure, sleeping
   through), the first awake decision afterwards reflects it, marked `recovered`. Only the
   previous day is recovered; older gaps stay unreflected (and are visible as such).
4. **Memory**: candidates are recorded with reasons, but only the strongest one per day
   (importance ≥ 0.6) is promoted to long-term memory. Preference candidates create or
   reinforce candidate preferences (one day of evidence each); acceptance still needs
   ADR-0030's distinct-day evidence or confirmation. Nothing else is promoted.
5. **Influence**: the reflection never changes needs, mood or energy. Its influence flows
   through memory, preferences, and the intent: the next day's rule direction leans toward
   the intent's goal type when nothing more urgent applies, and the Director sees it in
   `maple.decision.v1` (`intent`).
6. **Records**: one append-only `daily_reflection` row per day (unique), written in the
   same transaction as the transition that triggered it; served by
   `GET /api/reflections` and as a `daily_reflection` life event.

## Schema v8 and rollback

One new append-only table; forward-only; verified pre-migration copy first; ADR-0028
R1-R8 apply.
