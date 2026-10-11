# R1A-05 — Deterministic Pathfinding and Route Timing

**Status:** REVIEW / PENDING OWNER ACCEPTANCE (STEP 107, 2026-10-11). Implementation, focused tuning support and consolidated local review complete. No commit/push/PR/merge or production authorization.

## Baseline and binding inputs

Fresh worktree `/Users/paolo_cu/.codex/worktrees/r1a-05-deterministic-pathfinding/Maplegotchi`, branch `codex/r1a-05-deterministic-pathfinding`, fetched baseline `02efa73964a4f4d611b755970e26d38e0b0b7d31` (PR #4 merge). PR #2/#3/#4 are integrated. All other worktrees and original local-only `40f0eb7` are preserved.

Precedence: locked ADR values → accepted rules → Final Spec → proposals. Sources: [Master Plan](maple-room-r1a-plan.md), [Final Spec T6](../architecture/maple-room-final-design-spec.md#t6-capability-resolution-r1b), ADR-0035 §§3/6/7, ADR-0027 §§3/4, ADR-0036 point metadata, ADR-0037 tile-only persistence/isolation and ADR-0041 T/feet/timing locks. Consume existing R1A-04 Walkability; never reconstruct house geometry or change Oracle expectations.

## Implementation checkpoints

1. **Routes and A\*:** frozen integer waypoint/route/result models; validate origin, cumulative steps, axis-aligned segments and compression. Direction-aware states preserve turn costs. Manhattan heuristic, integer costs and `(f,h,ty,tx)` ties; secondary heading/g ordering resolves remaining ties. No cache/hierarchy/randomness. Invalid or inaccessible endpoints return `no_destination`, without recovery.
2. **Timing:** supplied UTC datetime only, integer microsecond elapsed arithmetic, `steps * ms_per_step` duration, `activity_started_at = arrives_at`, derived walking/performing phase, integer pixel interpolation through canonical `tile_to_feet`. Clamp before departure/after arrival; zero route immediate arrival. No legacy state-machine change.
3. **Rerouting:** ADR-0027 temporary start joined to both endpoints of the current unit edge. Derive exact fractional edge progress from old route and timestamps, never from rounded display pixels. Represent a transient partial-edge entry with integer numerator/denominator and duration, followed by an integer-tile route. Repeated rerouting derives the current edge again. No fractional-tile persistence or schema decision; R1A-08 owns serialization. Failed replanning returns explicit `no_destination` without moving Maple.
4. **Focused R1A-17 support:** evaluate 250/300 ms per step and small integer penalties against all 49 T6 entries; record turns, durations, repeated-run digest and representative activity-duration ratios. Keep the original 30-day pin untouched. Choose provisional values only after evidence; do not claim R1A-17 complete.
5. **Consolidated validation/review:** world/catalog/Oracle/Harness, legacy movement, security/import checks; Ruff/format/strict mypy; deterministic tuning fixture. Review scope and update evidence/status only after actual passes.

## Shortest-walk cost contract

Use a fixed integer step cost of `4 * GRID_WIDTH * GRID_HEIGHT = 4576`, with candidate turn penalties 0/1/2/4 (maximum 4). A shortest simple path has at most 1143 steps and no more than 1143 penalized turns including an initial heading. Its entire turn surcharge is below one grid step. Thus turn preference cannot buy an extra step; it only selects among shortest walks. These are search-cost units, independent of travel milliseconds. This makes shortest-walk behavior explicit rather than changing T6 to accommodate a penalty.

The frontier uses a deterministic ordered minimum over integer tuples, avoiding a new `heapq` import outside the current pure-core allowlist. Optimize only if measurements justify it; no boundary weakening.

## Acceptance and tests

All 49 T6 lengths must equal the approved Oracle, with canonical points obtained from accepted T4/T6: bed sleep; sofa seat; first library shelf front_l; living window view; writing chair; computer operator; Hall center idle. The Hall center follows explicit Spec §K rather than the first idle candidate. These fixture choices are not an activity resolver (R1A-06).

Cover trivial/adjacent/straight/detour/tie routes, every tile/segment walkable and orthogonal, closed/blocked/disconnected targets, malformed route/cost/speed inputs, immutable outputs, exact compression and cumulative steps, timestamp and FEET boundaries, sub-millisecond interpolation, mid-edge reversal/continuation/repeated replanning, mutations and no-teleport/no-recovery behavior. Independently compare synthetic paths to BFS minimum steps and minimum turns among shortest paths. Verify permutations and repeated outputs. Cross-platform native execution remains GitHub CI after separately authorized publication; do not claim it locally.

No R1A-06 resolver, placement, persistence/migration, API/renderer/production wiring, geometry/resource/Oracle changes or unrelated cleanup. No Full Release Gate or production access. Actual evidence follows.


## Selected provisional tuning and deterministic evidence

| ms/step | Turn penalty | T6 differences (49 cells) | Total directed-matrix turns | Longest walk |
|---|---|---|---|---|
| 250 | 0 | 0 | 166 | 13,250 ms |
| 250 | 1 / 2 / 4 | 0 each | 130 each | 13,250 ms |
| 300 | 0 | 0 | 166 | 15,900 ms |
| 300 | 1 / 2 / 4 | 0 each | 130 each | 15,900 ms |

Selected **250 ms/step** and **turn penalty 1** (integer step cost 4576). The smallest positive penalty gives all observed smoothing benefit without additional steps. The 250-ms art-spike candidate reduces the longest walk by 2.65 seconds versus 300 ms. Across all directed canonical trips, travel is below 4.42% of the destination's existing minimum activity duration at 250 ms, versus at most 5.30% at 300 ms. For example sleep→observe is 53 steps / 13.25 s before a minimum 5-minute observation; observe→sleep takes the same travel time before minimum 90-minute sleep. This is a bounded route/timing fixture, not a live activity resolver or full autonomy soak.

`python -m tests.world.pathfinding_tuning` evaluates 8 combinations / 392 directed trips, including zero-length diagonal entries. Report includes exact compressed routes, turns, durations and integer activity-duration ratios. Dedicated grid-tuning SHA-256:

`722a4e5359852fa4c049a985210e6a8f07a663df86bdf6c4a0a8218e8c51c936`

Repeated reports and separate processes with `PYTHONHASHSEED=1` / `97` agree exactly. This separate test-only pin does not replace the existing 30-day simulation digest. R1A-17 remains TODO: end-to-end grid life simulation, resolver/placement/migration/renderer fixtures and full soak remain later responsibilities.

## Final contracts and acceptance evidence

- `pathfinding.py`: immutable `Waypoint(tx,ty,cumulative_steps)`, canonical compressed `Route`, `PathResult`, `compress`, `find_route`. Origin is cumulative zero; final waypoint is exact destination/total steps. Zero route has one waypoint. Nonzero segments are orthogonal, nonempty and match cumulative Manhattan distance; redundant straight waypoints are rejected. Route expansion is lossless. Heading-aware A* uses `(f,h,ty,tx,heading,g)` integer ordering; equal-cost parents retain the first canonical discovery. Search order uses no hash iteration or randomness. Default penalty 1, allowed tuning candidates 0–4 preserve the shortest-step bound.
- `movement.py`: immutable `Travel`, transient `EdgeStart`/`Entry`, `TravelResult`, `reroute`. Ordinary duration is `total_steps * ms_per_step`, represented exactly in microseconds for supplied UTC timestamps. Before departure pixels clamp to start; phase is pending before departure, walking until arrival, performing from arrival. Activity starts exactly at arrival. Pixel coordinates are temporary integers derived via canonical tile feet and floor division; they are not stored world positions.
- Mid-edge replanning derives unrounded integer temporal progress and considers both current unit-edge endpoints. Candidate order: exact remaining travel duration, turns, endpoint `(ty,tx)`; endpoint searches use A* with incoming direction. The chosen entry reverses or continues physically on that edge before following integer-tile waypoints. Its duration is partial-edge microseconds plus whole-step travel time; cumulative grid steps remain integers on the suffix. Repeated rerouting, entry arrival and direction changes remain position-continuous. Before-prior-departure replanning is an explicit invalid operation. If the active edge is invalidated or no target path exists, return `no_destination` without moving, recovery or fabricated route. The caller owns fallback/cancellation audit; no state/event execution or fractional-tile persistence is implemented.
- **Focused final suite:** `python -m pytest tests/world tests/security/test_forbidden_apis.py tests/core/test_room.py tests/core/test_movement.py tests/runtime/test_movement_runtime.py tests/core/test_simulation.py::test_thirty_day_digest_is_pinned -q -o cache_dir=/private/tmp/r1a05-final-cache` with `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.` — **1,184 passed / 0 failed; no warnings reported**. Includes **559 new R1A-05 cases**, 256 exhaustive 3×3-maze/penalty cases against independent BFS plus shortest-path turn DP, all 49 T6 entries at four penalties, exact waypoint timing at two speeds, 40 four-direction sub-millisecond interpolation cases, repeated/mid-corner rerouting and failure/boundary checks. All R1A-02/03/04, Oracle/Harness and selected legacy/runtime movement regressions pass.
- Ruff lint and formatting PASS on four new Python files; strict mypy PASS on **33 files** for both `--platform linux` and `--platform win32`; import contracts **10 kept / 0 broken**, without allowlist/config relaxation. Security/pure-core checks included in the final suite. Native Windows/Linux execution is not claimed locally; it remains separately authorized GitHub CI after publication.
- The existing 30-day pinned digest test passed unchanged (`458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917`, 8,640 ticks). Only that directly relevant simulation regression ran; no Full Release Gate or unrelated simulation scenarios. No resource/package changes, so packaging was not repeated.
- Development findings: corrected the new T4 fixture delimiter (semicolon); initial 546 focused tests passed. Review tightened redundant-waypoint and explicit-domain-input rejection; lint findings were fixed with no import/security weakening. Combined regression before final refinements: 1,181 passed. Final 1,184 above supersedes that count, not a sum of repeated runs.
- Consolidated review: one canonical mask consumer, no geometry duplication, no new activity resolver, placement, persistence, API/renderer/runtime wiring, schema, accepted-spec/Oracle or simulation-pin changes. Existing worktrees and `40f0eb7` remain intact. Documentation links/counters, worklog append-only history, whitespace and exact scope checked.

No unresolved design blocker. Timing is provisional and isolated; R1A-06 resolution, R1A-08 serialization/auditing, R1A-09 projection, R1A-10 integration and full R1A-17/19 coverage remain deferred. Owner acceptance/integration still required; R1A-05 is not DONE.
