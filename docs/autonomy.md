# Maple's autonomy (v0.2): room, movement, goals, decisions

Implementation notes for ADR-0026 (AI Director), ADR-0027 (room and movement)
and ADR-0028 (activity set v2, events, schema). These are [PROPOSED]
implementation details unless the ADRs fix them.

## Room and movement (A1, ADR-0027)

- `core/room.py` is the single source of the room: interaction points
  (`id`, `location`, `x`/`y`, `facing`, `pose`, `allowed_actions`), the
  furniture identity of each location, and a waypoint graph whose edge lengths
  are declared integers. `GET /api/room` serves it.
- `core/movement.py`: `begin_activity` resolves the walk from Maple's position
  at `now` (part-way along a route if still walking) to the destination point.
  The activity's `activity_started_at` is the arrival time. `settle_movement`
  records an arrival and emits `activity_changed` at the exact arrival time.
- Walking time is attributed to the `walk` need rates; the new activity's rates
  apply from arrival (`core/needs.py:evolve_through`).
- The runtime records arrivals between heartbeats (`LifeRuntime.settle_committed`,
  run by the life loop every few seconds) and before any interaction.

| Furniture | Location id | Actions |
|---|---|---|
| Writing Desk | `desk` | write |
| Computer Desk | `terminal` | observe_server |
| Bookshelf | `bookshelf` | read |
| Sofa | `sofa` | rest |
| Bed | `bed` | sleep |
| Window / Plant Corner | `window` | think |
| Open Area | `rug` | walk, idle |

## Goals (A2, ADR-0026 §6)

- `core/goals.py`: 16 goal types (semantic intent only), `Goal` (id, type,
  one-line summary ≤ 120 chars, source `rule|external`, start, horizon 30–120 min).
- At most one active and one suspended goal. A goal ends when its horizon
  passes (`goal_completed`, `horizon_reached`), when a Director completes it,
  or is abandoned with a closed reason code (`expired`, `superseded`,
  `no_longer_relevant`, `director_abandoned`).
- Rule direction (`core/direction.py:rule_plan`) chooses a goal type from a small
  rule table and leans toward fitting actions with a soft score bias
  (`goals.AFFINITY`, ×1.6). No goal type fixes an action sequence; the tests
  check that one goal type leads to different actions.

## Decisions (A2, ADR-0026 §3)

A decision is its own transition: `prepare` (needs to `now`, arrival settled,
an expired goal completed) → plan → `check_plan` (core's legality rules) →
`execute` (goal events, destination, walk, counters). It uses the RNG stream
`decision` with the persisted `decision_counter`.

- Due when the current action has ended (never while walking), or when a
  high-priority input set `reevaluate_since`.
- The runtime runs due decisions from the life loop (`MapleService.step`:
  settle → decide → heartbeat). The heartbeat applies rule direction only if a
  decision is overdue by `CoreParameters.decision_grace` (production 120 s,
  pure lives and tests 0).
- Hard rules: energy ≤ 10 → only `sleep`; energy < 25 → `sleep`/`rest`.

## Priority and interruption (A2, ADR-0026 §7)

`core/signals.py` classifies what is going on; `core/priority.py` holds the levels.

| Signal | Priority | Interrupts? |
|---|---|---|
| server attention ≥ 0.8 (failed service, disk ≥ 95 %, temp ≥ 85 °C) | critical | yes, once per problem (`critical_since`); not another critical response |
| energy ≤ 10 | high | yes (the existing forced-sleep rule; even a critical response) |
| owner message (reserved for real chat) | high | interrupts normal/low |
| server attention 0.3–0.8, curiosity ≥ 75, social < 30 | normal | never; offered to the next decision |
| mood < 35 | low | never |

Greet and Pet are not signals: they never interrupt (D3).

On interruption the active goal becomes suspended (an older suspended goal is
abandoned as `superseded`), the interrupted activity is remembered, and core
starts the response (`observe_server` or `sleep`) with the signal's priority.
The first decision after the response must resume the suspended goal (rule
direction: if its horizon has not passed and the cause cleared) or abandon it
with `expired` / `no_longer_relevant`.

## Persistence

- Schema v4: goals, the plan columns and counters (`docs/persistence.md`).
- Schema v5: `life_state.critical_since` (ALTER TABLE ADD COLUMN; a verified
  pre-migration copy is taken first, as for every migration from v4 on).

## Audit and events (A3, ADR-0026 §8, ADR-0028 §2)

- `core/audit.py`: `DecisionRecord` (core's context summary, proposal, verdict
  `accepted|clamped|rejected|fallback|stale`, closed reason code, clamped
  originals, execution) and `ActionEvent` (the nine lifecycle kinds). Built by
  pure core in the transition that causes them and committed in the same
  transaction (`storage/audit_rows.py`).
- Every executed decision has exactly one record; a stale proposal has a record
  and no execution. Goals name the decision that started them (`goal.decision_id`).
- The heartbeat's overdue rule decision is recorded as `fallback` / `timeout`.
- The API serves the stores as one envelope stream (`docs/api.md` → Life events).

## The AI Director (A4, ADR-0026 §2-§5)

- `brain/director.py`: the `Director` protocol (`propose_decision(context)`),
  separate from the journal `Brain`. Rule direction is not a Director; it is
  core's own and always the fallback.
- `MAPLE_DIRECTOR=rule|antigravity` (default `rule`); `antigravity` uses
  `runtime/external_director.py` → companion `POST /decide`
  (`docs/brain-contract.md`), loopback only, no redirects, 16 KB cap.
- Flow (`MapleService.decide`): the runtime builds a frozen `maple.decision.v1`
  context under the lock; the service asks the Director **outside** the lock with
  a hard deadline (`MAPLE_DIRECTOR_TIMEOUT_SECONDS`, default 15 s; a stuck call is
  never stacked); the runtime then re-validates the answer against the state as it
  is now (`decide_proposal_committed`). If the decision stopped being due, the
  proposal is recorded `stale` and nothing changes.
- Validation (`core/proposal.py`): strict parsing, clamping within ×0.5–×2 of a
  range, `check_plan` against current state, hard rules first. Everything else
  falls back to rule direction in the same transition, with the reason recorded.
- The heartbeat applies rule direction if a decision stays undecided past
  `decision_grace` (120 s in production) — a hung companion cannot stall Maple.
- `GET /api/snapshot` and `/api/status` carry `director` (`kind`, `name`, `version`).

## Real reading and writing (A5, ADR-0029)

- A `read`/`write` action carries a **task** (`core/tasks.py`): tool, target, title,
  category. Rule direction chooses by goal (e.g. `monitor` → `server:status`,
  `reflect` → `journal:recent`, `create` → a note); a Director may name a target.
- **Catalog** (`runtime/tasks.py:TaskWorker.catalog`): the release library
  (`maplegotchi/library`, read via `importlib.resources`), Maple's 5 most recent
  documents, `journal:recent`, `server:status`. Ids only — no paths, listing, or network.
- **When**: a task's text is fetched when its action is chosen (`read_started`, with
  an extract and size, or `read_failed`/`unavailable`); at completion the reading is
  confirmed (`read_completed`) or, if interrupted, `read_failed`/`interrupted`.
  A write produces its document at completion (`write_completed` → `document` row)
  from recent readings, journal lines, the goal and a server line; an interrupted
  write produces nothing (`write_failed`/`interrupted`).
- The workspace is the `document` table in maple.db: backed up nightly, no new files.

## Memory (A6, ADR-0030)

- `core/memory.py` creates short-term memories from what a transition produced:
  goal outcomes, a serious server problem, the first Greet/Pet of a local day,
  completed readings and writings. Committed in the same transaction.
- Each heartbeat consolidates: short-term memories older than 36 h move to the
  archive. Nothing is promoted automatically; `promote` is explicit (Daily
  Reflection, A7), and preferences need evidence on 3 distinct days or explicit
  confirmation (`reinforce_preference`, `confirm_preference`, `reject_preference`).
- Retrieval (`retrieve`): keyword overlap with the goal/activity/task, tier,
  importance, evidence, recency; archive and rejected preferences excluded; ≤ 5 items.
  Used by the Director context (`memories`) and the writer; `memory:long_term` is a
  readable source once long-term memories exist.
- Memory is Maple's data in maple.db; a test switches the Director and checks that
  nothing in memory changes.

## Daily Reflection (A7, ADR-0031)

- A Maple day runs 06:00 → 06:00 local. When a `sleep` action begins between 20:00
  and 06:00, the runtime gathers that day's facts from Maple's own records
  (`runtime/daily.py`: goals, completed activities, readings, writings,
  Greet/Pet, serious server events, interruptions, failures) and core writes the
  reflection (`core/daily.py`). If the previous day was missed (restart, failure,
  sleeping through), the first awake transition afterwards writes it `recovered`.
- Outputs: summary, learned (reading extracts), important moments, up to 3 memory
  candidates (only the strongest, importance ≥ 0.6, is promoted), preference
  candidates (one day of evidence each), and tomorrow's intent.
- It never changes needs. The next day's rule direction leans toward the intent's
  goal type (×4 among everyday goals) when nothing more urgent applies, and the
  Director sees `intent` in its context.

## Room UX (A8)

The backend derives Maple's speech bubble from real state (`core/presence.py`,
`maple.bubble`); the frontend adds furniture hotspots from `/api/room`, a live feed
of the shared life events, and a separate owner Inspector (`docs/frontend.md`).

## Conversations via Discord (A9, ADR-0032)

- `companion/discord` (`maple-discord`, its own account and unit) holds the bot
  token, accepts only Paolo's messages in `#maple-chat`, and relays them to
  `POST /api/conversation/messages` with the shared gateway token. Slash commands
  (`/status`, `/needs`, `/goal`, `/journal`, `/server`, `/memory`, `/brain`, `/help`) call GET endpoints only
  and answer only Paolo.
- `core/conversation.py`: a message raises social (+6) and mood (+2), halved per other
  message in 10 minutes; it is a high-priority `owner_message` signal: Maple stops to
  listen in the open area (bubble "Listening to Paolo"), suspending its goal for the
  usual resume/abandon; it never wakes a sleeping Maple or overrides urgent work.
- Replies: a frozen `maple.reply.v1` context (activity, task, goal, needs, server,
  relevant memories, recent conversation, the message). The rule replier answers from
  those facts only, in Thai for Thai messages; `MAPLE_REPLIER=antigravity` asks the
  companion's `/reply` outside the lock with a timeout, validated, else rule fallback.
- Both directions are stored (`conversation_message`), each incoming message becomes a
  short-term `conversation` memory, and both join the life-event stream. A retried
  Discord message id returns the stored reply.

## Brain companion packaging (A10, ADR-0033)

- `companion/brain` (`maple-brain`) is the version-controlled companion behind
  `MAPLE_BRAIN_URL`: `/generate`, `/decide`, `/reply`, `/health`, loopback only.
- The provider is configured, never hard-coded: `MAPLE_BRAIN_PROVIDER=none` (the
  default; Maple uses its rule fallbacks) or `command` with `MAPLE_BRAIN_COMMAND` (JSON
  argv, absolute path, no shell) and `MAPLE_BRAIN_MODEL`. Auto-approve flags are refused.
- `deploy/brain/` holds the hardened unit (`maple-brain-svc`, no access to Maple's data
  or configuration), the env template and the install/update/rollback procedure.
