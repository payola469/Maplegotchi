# ADR-0027: Room interaction points and backend-modeled movement

- **Status:** Accepted — FIXED (CLAUDE.md D26)
- **Date:** 2026-10-05
- **Decided by:** owner (2026-10-05: distinct physical destinations; an activity
  begins only after Maple arrives; movement is backend-modeled; rerouting cancels
  the previous destination). Geometry, speed, and point lists are [PROPOSED].
- **Extends:** ADR-0018 (presentation derived from a supplied `now`), ADR-0002
  (PixiJS renders the room only). **Related:** ADR-0026, ADR-0028.

## Context

Today the backend stores only an activity and a logical `RoomLocation`; walking is
an animation invented by the frontend (`room/animation/motion.ts`). The owner's
rule — *action selected → destination resolved → walk → arrive → align → activity
begins* — makes walking part of Maple's real life, so by CLAUDE.md §3.9 it must be
backend state, not a frontend effect.

## Decision

### 1. Interaction points (pure data in `core/room.py`)
- Room geometry uses the existing logical space: 1000 × 600 units, the same units
  as `frontend/src/room/layout/anchors.ts`. `core/room.py` becomes the single
  source of truth; the frontend reads it from `GET /api/room`.
- `InteractionPoint`: `id` (e.g. `writing_desk.chair`), `location`
  (`RoomLocation`), `x`, `y` (floor/feet position), `facing`
  (`left`|`right`|`front`|`back`), `pose`, `allowed_actions` (ordered tuple).
- A location may have several points (the open area has several for walk/idle).
  The choice among valid points is a seeded draw (decision stream), never a set
  iteration.
- Location ids stay as persisted today, so existing rows remain valid; display
  names are presentation:

| Location id | Furniture (display) | Actions |
|---|---|---|
| `desk` | Writing Desk | `write` |
| `terminal` | Computer Desk | `observe_server` (future computer-related work) |
| `bookshelf` | Bookshelf | `read` |
| `sofa` (new) | Sofa | `rest` |
| `bed` | Bed | `sleep` |
| `window` | Window / Plant Corner | `think` (new) |
| `rug` | Open Area | `walk`, `idle` |

  Writing Desk and Computer Desk are, and stay, different furniture and points.
- No furniture-specific movement code: destination resolution is
  `points_for(action) -> tuple[InteractionPoint, ...]` over the table.

### 2. Navigation
- A fixed waypoint graph over the floor (every interaction point plus a few lane
  nodes), with explicitly declared edges whose lengths are **declared integer
  constants** (a test checks each against the geometry). Shortest path by
  Dijkstra with deterministic tie-break on node id. No runtime `sqrt`; position
  interpolation along an edge uses only `+ - * /` (CLAUDE.md §5).
- `WALK_SPEED` [PROPOSED: 120 units/s] is a core tuning constant. Travel time =
  path length / speed, rounded up to whole milliseconds. Typical walks take a few
  seconds; the frontend no longer has its own speed.

### 3. The action plan in state
`MapleState` gains an `ActionPlan`:
`action`, `point_id`, `path` (node ids), `departed_at`, `arrives_at`, `until`,
`started_from` (the start position when departing mid-edge).
- `activity_started_at` **equals** `arrives_at`; `until = arrives_at + duration`.
  The invariant `activity_started_at <= last_updated_at` is replaced by
  `departed_at <= last_updated_at` and `departed_at <= arrives_at <= until`.
- **Phase is derived from a supplied `now`** (like D17 reactions): `walking` while
  `departed_at <= now < arrives_at`, then `performing` until `until`. Arrival
  needs no tick, timer, or scheduler to be true in snapshots and in core.
- While walking, the presented pose is `walk` and the activity label is "going to
  <furniture>"; the activity's pose, facing, and expression rules apply only from
  `arrives_at`. Needs for the walking interval evolve with the `walk` spec; the
  activity's spec applies from arrival.
- Already at the destination point → `arrives_at = departed_at` (zero walk).

### 4. Rerouting
If a new action is committed while `now < arrives_at`:
1. the current destination is cancelled (`walking_cancelled`, ADR-0028);
2. Maple's position is `position_at(now)` on the current path (pure, exact);
3. that position becomes a temporary start node joined to both ends of the edge it
   lies on; the new destination is resolved and a new path computed from there;
4. a new plan starts at `now` (`destination_selected`, `walking_started`).
The previous action never begins, and no `activity_started` is recorded for it.

### 5. Materialising arrival and completion
Because arrival and completion are derived from time, their audit events
(`arrived`, `activity_started`, `activity_completed`) are written by a lightweight
**progress step** in `runtime/life` that the existing life-loop poll
(`loop_poll_seconds`, 5 s) runs when such a time has passed. The events carry the
exact derived time (`at = arrives_at` / `until`), not the poll time. The progress
step uses no randomness and no Director; when it finds the action completed it
makes a decision due (ADR-0026). Snapshots are correct even before the progress
step runs, because they derive phase from `now`.

### 6. Frontend
- The frontend renders the backend plan: it animates along `path` from
  `departed_at` to `arrives_at` using the server-time offset it already tracks,
  and switches to the backend pose/facing at `arrives_at`. Reduced motion snaps to
  `position_at(now)`. `Motion` stops choosing speed or target on its own.
- New furniture art: sofa and plant corner. PixiJS stays limited to the room
  (D2); goal/action panels are DOM.

## Schema v4 and rollback

The plan columns, the `sofa` location, and the relaxed invariants are part of the
single schema-v4 migration in **ADR-0028**, whose rollback/recovery strategy is
normative. Specific to this ADR: existing v3 rows are converted without inventing
movement — the current activity gets a zero-length plan at its canonical point
(`departed_at = arrives_at = activity_started_at`, `until = activity_until`); a v3
state whose (activity, location) pair is no longer valid (`rest` at `bed`/`rug`,
`idle` at `window`, `walk` at a non-`rug` location) keeps its activity and times
and is placed at that activity's canonical point. No timeline event is fabricated
for this conversion. Restoring the v3 snapshot (ADR-0028) restores the old
locations exactly.

## Consequences
- What the room shows during a walk is backend truth; the activity never appears
  to begin before arrival.
- Rerouting is a pure function of state and time, testable without a browser.
- The frontend loses its independent walking logic; anchors move to the API.
- Interaction points are data, so future real reading/writing tools can attach to
  `desk`/`bookshelf` points without new movement code.
