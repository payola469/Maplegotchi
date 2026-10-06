# ADR-0034: Brain Health / Observability v1

- **Status:** Accepted — FIXED (CLAUDE.md D33)
- **Date:** 2026-10-06
- **Decided by:** owner (Brain Health / Observability v1 request: a read-only view in the
  Maple Inspector showing whether Maple's AI brain is healthy, degraded, or offline, with
  recent latency and fallback statistics; quota/credits out of scope).
- **Related:** ADR-0025 (runtime boundary), ADR-0026 (decision audit), ADR-0031 (Maple
  day), ADR-0032 (conversations), ADR-0033 (`maple-brain` companion).

## Context

Journal Brain, Director and Replier all run through the loopback `maple-brain`
companion. The decision audit already records `director_kind`, `director_name`,
`verdict`, `reason_code` and `latency_ms`; conversation replies record `replier_kind`,
`replier_name` and `fallback_code` but not how long the reply took. The owner has no
single place to see whether the AI path works.

## Decision

1. **Companion `/health`** returns exactly `{"status": "ok", "provider": <provider kind>,
   "model": <MAPLE_BRAIN_MODEL or null>}`. Never credentials, OAuth state, the provider
   command argv, prompts, responses, or reasoning.
2. **Reply latency.** Maplegotchi times every external replier attempt (wall time of the
   call, measured outside the writer lock, including failed attempts that fall back to a
   rule reply) and stores it with Maple's outgoing message: schema **v10** adds nullable
   `conversation_message.latency_ms` (`0..600000`). Rule replies and all pre-v10 rows are
   `NULL`. Forward-only; preceded by the automatic verified `pre-migration/` copy
   (ADR-0028 R2). Returning to a pre-v10 release means restoring that copy (loses life
   since), as for every earlier migration.
3. **`GET /api/brain-health`** is read-only and aggregates stored audit rows only (no
   second logging system, no new table, no write endpoint, no background polling):
   - *Director calls* = `decision` rows with `director_kind = 'external'`. Success =
     verdict `accepted`/`clamped`; fallback = verdict `fallback`/`rejected`; timeouts and
     transport errors = `reason_code IN ('timeout', 'transport_error')`. `stale` rows (an
     answer that arrived after the decision stopped being due) are neither success nor
     failure and are ignored. Rule-kind rows (including the heartbeat's overdue
     fallback) are not AI calls.
   - *Replier calls* = outgoing `conversation_message` rows with `replier_kind =
     'external'` (success) or a non-null `fallback_code` (fallback; `timeout` and
     `transport_error` also count as timeouts/transport errors).
   - The journal Brain's failures are not recorded anywhere (a failing Brain costs only
     the words), so v1 reports its mode but does not use it for status.
   - **"Today"** is the current **Maple day** (local 06:00 → 06:00 at the core
     `utc_offset`, +07:00 in production; `core.daily.reflection_day`/`day_window`). The
     response names the day and its UTC window.
4. **Status** (closed set):
   - `offline` — an external mode is configured and the companion's `/health` cannot be
     reached (connect/read failure, timeout, non-200, or not `{"status": "ok"}`).
   - `degraded` — the companion is reachable but the latest relevant AI call (the newer
     of the latest Director call and the latest Replier call; on an exact time tie the
     failure counts as the latest) fell back, timed out or errored. Only callers whose
     mode is currently external are considered.
   - `healthy` — the companion is reachable and that latest call succeeded.
   - `unknown` — with `status_reason` `no_calls_yet` (reachable, no AI call recorded)
     or `not_configured` (every mode is `rule`; the companion is not probed). Nothing is
     invented.
5. **Failure isolation.** The probe is one `GET /health` per request with a hard 2 s
   timeout, no redirects, a 4 KB response cap, made outside Maple's writer lock; any
   failure is reported, never raised. Provider and model are passed through only if they
   are short, printable identifiers (else `null`). Brain Health never touches the life
   loop, Director, fallback, goal, memory, reflection, movement, provider selection or
   the Discord companion.
6. **UI.** A *Brain Health* card in the owner Inspector only (never the living room).
   Unavailable values show `Unknown`, never a guess.

## Consequences

- One additive nullable column; no behavior change for Maple.
- The owner can see AI health from real stored data; the companion is probed only when
  someone opens the Inspector.
- Quota/credits, journal-Brain failure accounting, and alerts are later work.
