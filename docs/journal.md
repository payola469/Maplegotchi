# Journal, reflection, and the Brain boundary (Phase 4)

Status: implemented and approved (2026-09-30). Choices here are **[PROPOSED]**
unless they follow directly from a FIXED decision (noted inline).

## Three separate records (D8)

| Record | What it is | Written by | Stored in |
|---|---|---|---|
| **Timeline** | factual lifecycle events: birth, activity changes, accepted interactions, downtime gaps | core transitions | `timeline_event` |
| **Observations** | factual world data: metrics and service states, with status and reason | sensors | `observation` |
| **Journal** | Maple's subjective interpretation and reflection | Brain wording of core-detected triggers | `journal_entry` (+ `journal_entry_observation`) |

They never share a table or a model. Journal entries may *cite* observations
(by row id); observations and timeline events never depend on the journal.

## Pipeline

```
transition (heartbeat / accepted Greet-Pet)
  └─ core/reflection.py: triggers + new ReflectionState   ← decides WHETHER and ABOUT WHAT
       └─ Brain.compose_journal(BrainContext) → JournalDraft[]  ← decides only HOW to say it
            └─ core/journal.py: accept_drafts()             ← validates / grounds / labels
                 └─ one transaction: state + events + observations + journal + ReflectionState
```

A Brain cannot decide whether Maple writes, which facts an entry cites, the
category, or anything about behavior or state.

## Brain interface (`brain/interface.py`)

```python
class Brain(Protocol):
    kind: BrainKind            # "rule" | "external"
    name: str                  # e.g. "rule_brain"
    version: str               # e.g. "1"
    def compose_journal(self, context: BrainContext) -> Sequence[JournalDraft]: ...
```

`BrainContext` is immutable plain data: `now`, `local_hour`, `owner_name`,
Maple's `state` and `expression`, the observation `snapshot` (or none), and the
`triggers`. No handles, clock, storage, filesystem, or network. The `brain`
package is held to core's purity rules by the AST scanner and the import
allowlist test.

`JournalDraft(trigger_index, text, importance, template_id)` is untrusted.

CLAUDE.md §3.6 sketched `suggest_activity` and `compose_reaction` too; Phase 4
defines only `compose_journal`, because behavior and reactions stay in core
rules (narrower is safer).

## JournalEntry schema (`core/journal.py`)

| Field | Meaning |
|---|---|
| `created_at` | UTC time of the transition |
| `category` | `daily_life`, `server_notice`, `interaction`, `reflection`, `milestone` (fixed by trigger kind) |
| `trigger` | `activity`, `interaction`, `server_problem`, `server_recovery`, `daily_reflection`, `milestone` |
| `topic` | stable key, e.g. `service:jellyfin`, `daily:read`, `reflection` |
| `text` | 1–240 chars, trimmed, one printable line (no line breaks or control characters) |
| `importance` | `low`, `normal`, `high` |
| `brain_kind`, `brain_name`, `brain_version`, `template_id` | who wrote it and with which template (`rule`, `rule_brain`, `1`, …) |
| `activity`, `expression` | Maple's context when writing |
| `observation_keys` → stored as `observation_ids` | the facts it interprets (row ids, ordered) |
| `tick_id` | heartbeat that produced it; `None` for interaction entries |

Entries are frozen in memory and append-only in the database (UPDATE/DELETE
triggers on both tables; the text CHECK enforces length and a single line).
Numbers are **not** banned by the journal or the schema: a future grounded
entry may legitimately say "96%" or "21:00".

## Grounding rules

1. An entry's observation references come from its **trigger**, which core
   built from real observations in the snapshot; the Brain cannot add any.
2. A trigger citing something not in the snapshot is rejected.
3. **RuleBrain template policy (v0.1):** the built-in RuleBrain never writes
   digits, so it cannot invent or misquote a value. This is a policy of that
   Brain (enforced in `rule_brain.py` and proven by tests over every template
   and trigger shape), not a journal invariant. Numerical grounding for other
   Brains is future work and out of v0.1 scope.
4. Text may not name a service (from the D12 name list) that the trigger does
   not reference.
5. Unknown / unavailable / error observations never start or clear a
   condition, and the daily reflection's server sentence is chosen from a
   core-computed `ServerSummary` (`calm` only when everything essential was
   observed and fine; `unclear` when something was not seen; `no_data`).
6. Causal explanations are never generated: templates only state that
   something is or is no longer wrong.

Drafts failing any rule are dropped, never repaired.

## RuleBrain (`brain/rule_brain.py`)

Offline, deterministic, template-driven. Each trigger kind has a small fixed
set of sentences; the variant is chosen by hashing the trigger topic and time,
so identical input gives identical output. Interaction wording depends on
Maple's state (e.g. "Paolo stopped by and gave me a little pat." awake vs "I
felt a gentle pat while I was sleeping." asleep). The owner name is a
`JournalParameters.owner_name` setting (default "Paolo").

## Triggers, deduplication, and frequency (`core/reflection.py`)

| Trigger | Rule |
|---|---|
| Daily life | Maple's **journal day** runs 06:00–06:00 Asia/Bangkok. At most one entry per kind per journal day for waking, sleeping, reading, writing, checking the server; at most one per heartbeat. |
| Interaction | Accepted Greet/Pet only; no second interaction entry within 30 minutes (all are still counted for the reflection). Rejections never journal. |
| Server problem / recovery | Conditions: service `failed`; disk ≥ 95 % (clears < 90); memory ≥ 90 % (< 85); temperature ≥ 85 °C (< 80); CPU ≥ 90 % (< 75). Journaled once when a condition starts and once when it clears. Active conditions are persisted, so a restart mid-problem does not re-announce it. Unknown data neither starts nor clears a condition; a service clears only when observed `active`. |
| Daily reflection | See below. |
| Milestone | First heartbeat; ages of one day, week, month, year. After long downtime only the largest newly reached milestone is written. |

Routine calm heartbeats produce no entry. Measured: a full simulated day
(263 heartbeats) yields 12 entries.

## When the Brain fails or declines

Detection and marking are separate. `heartbeat_triggers` /
`interaction_triggers` only detect triggers (and roll the journal day and
count interactions, which are facts). `mark_journaled` then advances each
trigger's marker **only if an entry for it was actually accepted**:

| Trigger | Marker advanced only when written |
|---|---|
| Server problem | becomes an active alert; counted as a notice today |
| Server recovery | the active alert is cleared |
| Daily life | the kind is marked seen for the journal day |
| Daily reflection | the journal day is marked reflected |
| Milestone | the milestone (and smaller ones) are recorded |
| Interaction | the 30-minute spacing timer starts |

If `compose_journal` raises, returns nothing, or every draft is rejected,
the heartbeat or interaction still commits its state, events, and
observations, but no marker moves, so the same trigger fires again at the
next opportunity under the normal rules (e.g. a still-failed service is
noticed at the next heartbeat; a missed reflection is retried within the
same window; the first-heartbeat milestone stays open for the first day).

## Daily reflection semantics

- One opportunity per journal day, between 21:00 and 06:00 local
  (Asia/Bangkok, D16).
- At most one per journal day, recorded in the persisted `ReflectionState`
  (`last_reflection_day`), so restarts never duplicate it.
- If Maple is offline through the whole window, that day gets no reflection;
  there is never catch-up for past days (after days offline, at most the
  current day's reflection is written).
- No reflection for a journal day Maple did not live from its start (e.g.
  born at 02:00 during the previous day's window).
- Content: the server sentence from `ServerSummary`, one sentence about what
  Maple did (reading / writing / checking the server), and whether the owner
  stopped by. No numbers.

## Persistence (migration v3)

`journal_entry`, `journal_entry_observation (entry_id, observation_id,
position)` with foreign keys to `observation`, and a single-row
`journal_state` holding `ReflectionState` (journal day, daily kinds seen,
interaction and notice counts, last interaction entry time, active alerts,
last reflection day, milestones). All are written in the same transaction as
the transition that caused them; a failure rolls back everything. A life
from before v3 starts with an empty `ReflectionState`.

## External Brain boundary (D6, D10, ADR-0025)

ADR-0025 extended the Phase 4 RuleBrain-only boundary: runtime may select an
ExternalHttpBrain through the separately hardened loopback companion. Output
remains advisory; only the built-in RuleBrain may claim rule kind. Brain labels
come from the accepted implementation, never external output.

**R-01 PASS / CLOSED; owner confirms production deployment and HTTP Health PASS (2026-10-10).** Exact deployed SHA / detailed post-deployment evidence not supplied; no new agent production verification. Implementation and limitations:

- Rule/Director decisions, arrival, heartbeat and accepted interactions prepare
  context and a candidate transition under the writer lock. External composition
  runs unlocked with no open transaction and no storage access in the worker.
- Lifecycle and base revision are checked before commit. An unchanged candidate
  retains its logical timestamp. An overtaken operation is recomputed from current
  state/time without stale drafts or another request; eligibility/cooldowns may
  yield no-op/rejection. Existing Director stale-audit behavior is preserved.
- State, observations, accepted entries and reflection markers commit together;
  memory adoption and publication follow persistence. RuleBrain keeps the original
  deterministic locked path. Trigger ordering/validation are unchanged.
- Busy, timeout, stale, invalid or failed wording advances no wording markers.
  Factual interaction counts/day rollover still commit. Existing retry opportunities
  remain; event-only triggers are not guaranteed eventual wording. No durable queue.
- One nonblocking external request slot per runtime. A daemon receives context and
  storage-free coordination. The 30 s monotonic caller deadline covers startup,
  request preparation, I/O, decoding and parsing. Timed-out workers retain the slot
  until cleanup, so no replacement worker can overlap.
- Connect at most 2 s; streamed response cap 64 KiB before JSON parsing. Redirects
  and environment proxies refused, no automatic retries. Compressed content is
  refused to prevent decompression expansion before the cap; plain JSON is supported.
- Shutdown rejects new operations, invalidates preparations, wakes waiters and
  drains admitted callers through final reads before storage closure. Every write
  obtains an irrevocable commit permit under the same gate lock as shutdown.
  Shutdown first aborts persistence; permit first allows one atomic transaction
  to finish, including when shutdown arrives before SQLite starts. The gate lock
  is released before persistence and never held while acquiring the writer lock.
  Late workers cannot commit. App teardown now closes storage;
  post-teardown reads raise `RuntimeClosedError`; close is idempotent.
- Bounded composition waiting does not guarantee worker termination or bounded
  whole-process shutdown. A stuck daemon can keep wording busy until restart.

Schema/stored formats stay v10. Same-schema code rollback (`docs/deployment.md`)
preserves the database, discards memory-only attempts and restores the older
release's R-01 limitation. Deployment/rollback execution need separate owner
authorization. Owner has approved Pre-R1 clearance and authorized R1a (2026-10-10);
R1A-01 is OWNER ACCEPTED / MERGE PENDING, other items TODO. Baseline Docker release-gate PASS and computed simulation are recorded; PR-head CI
PASS (run `38062574000`, HEAD `26aed831…`) is not a separate CI execution of the
original base. R1A-01 remains OWNER ACCEPTED / MERGE PENDING. Owner explicitly approved acceptance on 2026-10-10, acknowledging PR-head-only CI provenance and unavailable complete raw baseline Docker gate details. PR #1 is not merged; repository integration is pending. Evidence: R1a worklog and R1A-01 baseline record.

## Demo

`uv run maplegotchi demo-day --data-dir <empty dir>` runs a deterministic day
(fake clock and senses, real runtime/storage/RuleBrain) with two restarts, a
Jellyfin failure and recovery, Greet/Pet, and the daily reflection, and prints
timeline, observations, and journal separately.
