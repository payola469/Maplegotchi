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
