# ADR-0035: World model — one house grid, derived room graph, 4-direction movement

- **Status:** Accepted — FIXED design (CLAUDE.md D34). **NOT IMPLEMENTED.** Implementation is not yet authorized. **Amended 2026-10-09:** the art/PixiJS technical spike passed (`docs/spikes/2026-10-room-art-spike.md`). `FEET_IN_TILE` (§6) and the wall grid convention (§4) are **LOCKED** (ADR-0041 L4, L8). Room sizes, door positions and movement tuning (§7) stay undecided.
- **Clarification (2026-10-13):** Owner approval of the exact STEP167 wording, recorded locally in STEP168: temporal Entry persistence and restart semantics in §3/§6. Documentation only; no implementation authorization. Not yet published or merged.
- **Date:** 2026-10-08 (amended 2026-10-09)
- **Decided by:** owner, Maple Room review decisions **B8** (geometry), **B9** (direction vocabulary), **B12** (feet in tile, provisional), and **B13** (baseline A1, A6, A7, A8).
- **Supersedes (on implementation at R1b, ADR-0037):** the *geometry* of ADR-0027. That covers the single 1000×600 front-view room, the hard-coded points in `core/room.py`, and the waypoint graph with declared edge lengths. ADR-0027's movement *semantics* are kept unchanged. Until R1b, ADR-0027 describes the running system.
- **Related:** ADR-0036 (objects), ADR-0037 (persistence and migration), ADR-0040 (view transition), ADR-0041 (art contract), `docs/architecture/maple-future-architecture.md` §6, `docs/roadmap/maple-roadmap.md` R1.

## Context

Today Maple's room is a single hard-coded 1000×600 front-view space (`core/room.py`). It has 9 interaction points, a waypoint graph with declared integer edge lengths, and a 1:1 mapping from activity to location. The roadmap (R1) asks for a 3/4 top-down, multi-room world. That world needs a room graph, doors, walkable areas, collision, pathfinding and 4-direction movement, it must have no hard-coded routes, and Maple must not teleport by default.

## Decision

### 1. Room as data (A1)
Rooms, doors and object placements are versioned **data** that core validates, not code. Adding or rearranging rooms requires no code change. Persistence is covered in ADR-0037.

### 2. One global house grid (B8)
- The world is **one house tile grid** with integer tile coordinates `(tx, ty)`. The origin is at the north-west, x grows east and y grows south.
- **Rooms are labelled regions** on that grid. They are rectangular for now; non-rectangular rooms are deferred.
- Walls lie on room edges.
- A **door is a wall opening between two physically adjacent rooms.** It has a width in tiles and a state of `open` or `closed`.
- **The room graph is derived** from door topology and is never authored separately. It serves AI context ("Maple is in the Library"), the overview, and room-level rules.
- **Room set (B2, ADR-0040):**
  - Regions for all 8 roadmap rooms are reserved from the start.
  - 5 rooms open in R1b: Central Hall, Bedroom, Living Room, Library and Work Studio.
  - 3 are closed placeholders: Creation Room, System Room and Future Space. They are structurally present but inaccessible, behind closed doors and with no furniture. Opening one later is a door-state and layout change, not a topology redesign.
- **Core rejects overlapping or invalid room geometry** before any save (ADR-0038).

### 3. Movement and pathfinding (B8, A6, A7)
- Pathfinding is **one flat, deterministic 4-direction A\*** over the whole house grid.
  - It uses integer costs plus a small turn penalty.
  - The heuristic is Manhattan distance.
  - Ties break deterministically on `(f, h, ty, tx)`.
  - No `sqrt` and no floating-point geometry are used (CLAUDE.md §5).
- **There is no hierarchical pathfinding and no path cache** unless future profiling shows they are needed.
- **The movement semantics of ADR-0027 are unchanged:**
  - action selected → destination resolved → walk → arrive → activity begins;
  - `activity_started_at = arrives_at`;
  - phase is derived from `now`;
  - rerouting cancels the old destination and plans from Maple's current position.
- **The route lives in state** as compressed integer waypoints `(tx, ty, cumulative_steps)`, together with the movement rate and UTC timing required to reconstruct the same Travel. A route beginning between tiles may additionally retain temporal Entry metadata: adjacent integer edge endpoints, integer `progress_us` at that plan’s departure, and the selected endpoint joining the waypoint route’s origin. This metadata describes the plan’s temporal origin; it is not a continuously updated current-position snapshot.

  `step_us = ms_per_step × 1000`. Total travel duration is `entry_duration_us + steps × step_us`, where `entry_duration_us` is zero without Entry. For Entry, the duration is `progress_us` when returning to the edge’s first endpoint, or `step_us − progress_us` when continuing to its second endpoint. Require `0 < progress_us < step_us`, adjacent walkable endpoints, and an Entry endpoint equal to the waypoint route’s origin.

  Preserve `arrives_at = departed_at + total travel duration` and `activity_started_at = arrives_at`. Current position and travel phase are derived from the complete validated Travel and supplied evaluation time using the existing deterministic movement rules. Rerouting starts from that exact derived position without rounding or normal teleport.

  Restart reconstructs the same Travel without restarting its clock or changing its original arrival time. At an evaluation time on or after `arrives_at`, travel is complete and its derived position is the destination. This does not by itself mean the destination activity is complete; activity completion and any subsequent downtime processing retain their existing semantics.

  Loading performs no movement-history fabrication, event insertion, relocation or silent repair. Unsupported or inconsistent persisted data is refused. Deriving completed travel after downtime does not create a new movement or relocation event.
- **No teleport (A7).** A destination with no path makes the action invalid (`no_destination`) and rule fallback applies. Normal movement never teleports. The only allowed non-walking position change is emergency **recorded recovery**, under the owner-approved policy below.

#### Prevention first, recovery last resort — owner amendment, STEP 103

Validate a proposed layout before acceptance. Reject blocked protected door corridors or K1–K3 tiles, broken K4 connectivity, disconnected permitted walkable areas, Maple trapped away from the canonical safe location, unreachable required interaction/slot approaches, and access into closed rooms or through closed doors. Geometric cells need not all be walkable; the permitted walkable area and required targets must remain connected. R1A-04 supplies pure-core validation; R1A-07 integrates placement acceptance. Recovery cannot bypass failed placement validation.

Recovery is emergency-only for exceptional invalid state or an escaped layout inconsistency:

- A valid walkable current tile produces no relocation.
- A blocked tile within an open-room floor or approved open passage may be used only as the BFS starting point. After initialization, traverse only valid walkable cells using orthogonal adjacency. Never traverse walls, other blocked tiles, closed rooms or closed passages. Select the nearest reachable valid tile by BFS distance, breaking ties by `(ty, tx)`.
- If no valid candidate is reachable, use the canonical fallback `idle.hall_center` at `(21,15)`. A source inside a closed region, closed passage, wall or outside the grid skips traversal and uses that fallback directly.
- Validate the fallback as safe and walkable. If unsafe, return an explicit failure; do not relocate to an unsafe position.
- Every actual relocation produces an immutable `maple_relocated` record containing the original and destination tile and a deterministic reason. Event persistence belongs to R1A-08.

House geometry, K1–K3, S5/S13, fallback coordinates and approved Oracle values remain unchanged. **Subsequent STEP 104 owner decision (including revised S10):** K1–K3 stay protected; K4 is explicitly revised to dynamic four-neighbor connectivity in [Final Spec §K](../architecture/maple-room-final-design-spec.md#k-walkability-spec), replacing the fixed straight corridor. Alternative routes are permitted only after fresh safe-layout validation. It does not authorize live movement, placement execution or persistence.

### 4. Collision (A8)
- Walkability = floor tiles − wall tiles − the blocking masks of placed objects + door tiles in `open` state.
- **Wall grid convention (LOCKED 2026-10-09, ADR-0041 L8; spike M09):**
  - A north (east–west) wall occupies **H_w / T = 3 non-walkable grid rows** (H_w = 3T). Its face is drawn exactly over those rows.
  - A side (north–south) wall occupies **1 non-walkable grid column**.
  - The exterior south wall is 1 cutaway row.
  - A door is an opening **2 tiles** wide in the wall. North doors are open archways (no lintel). A side door is a gap whose neighbouring wall tiles carry end caps.
  - Room sizes and door positions remain undecided (§7).
- Maple occupies exactly **one tile**, her feet tile.
- There are no other agents, and dynamic occupancy is deferred.

### 5. Direction vocabulary (B9)
- **Character direction** is where a sprite looks: `down`, `left`, `right`, `up`. It is used for Maple's facing, interaction-point facing and animation sheet row order.
- **Object orientation** is how furniture is rotated: `south`, `east`, `west`, `north`. It is used for furniture rotation and catalog orientation metadata.
- **Fixed mapping:** `down = south`, `up = north`, `left = west`, `right = east`.
- **Transition:**
  - Today's backend `Facing` values `front` and `back` are API-only (not stored in the database).
  - During R1a, the new character directions are added alongside them, with `front → down` and `back → up`.
  - `front`/`back` are retired only after the flagged transition is complete (ADR-0040).

### 6. Feet point inside a tile (B12) — LOCKED 2026-10-09
- **Accepted:**
  - Stored world positions are **tile coordinates only**.
  - The tile-coordinate-only rule applies to persisted world-position fields. Temporal Entry metadata permitted by §3 belongs to the route’s reconstruction state and does not introduce a separately authoritative fractional or pixel position. During travel, the stored integer tile reference is interpreted together with that route; it must not be treated as a rounded replacement for the derived current position.
  - One shared constant `FEET_IN_TILE` maps a tile to the pixel where Maple's feet stand. Backend and renderer use the same constant, and so do route positions and walking interpolation.
  - Feet are horizontally centred in the tile and sit slightly toward its south (lower) side.
- **LOCKED (2026-10-09, ADR-0041 L4):** `FEET_IN_TILE = (T/2, ⌊13T/16⌋) = (8, 13)` at the locked `T = 16`.
  - It was validated together with T, the Maple frame (32×48), the sprite feet anchor (16, 47), grounding near walls, doors and furniture, and depth sorting (spike M02, M06, M09, M10).
  - FEET y 12, 13 and 14 all passed, so the tie keeps 13.
  - The formula is the definition: if T were ever changed by a new owner decision, the constant follows the formula, not the literal `(8, 13)`.
- **Depth (renderer, ADR-0041 L11):** Maple sorts by the **south edge of her feet tile**, not by her feet pixel. The feet tile is the one tile she occupies (§4).
- *Previously PROVISIONAL (2026-10-08): `(8, 13)` for `T = 16`, proportional if T changes.*

### 7. PROVISIONAL tuning (not architecture)
These are set during implementation and changed only together with the pinned simulation digest:
- `ms_per_step`;
- the turn penalty;
- the room sizes and door positions of the initial house. These were intentionally left open for the Room Final Design Spec (confirmed with B15). The technical art spike (2026-10-09) did **not** decide them; it only locked the wall, door and window conventions they must use (ADR-0041 L7–L10).
  - **Update 2026-10-09:** they are now defined by the **Room Final Design Spec** (`docs/architecture/maple-room-final-design-spec.md`): a 44×26 grid, 8 regions and 7 doors in a star around the Central Hall.
  - Their status is **SPEC, owner-approved in principle, not implemented**, and **not** an ADR-level lock. They bind R1b once R1a/R1b are authorized. Changes before then need an owner decision.
  - The spec also records owner decision O1: the placeholder rooms are interior and windowless.
- **R1A-05 provisional tuning (STEP 107):** isolated grid engine selects 250 ms/step and integer turn penalty 1 with step-cost units 4576; all 49 T6 lengths unchanged. Bounded speed/penalty evidence and separate test-only grid digest: [R1A-05 plan](../implementation/maple-room-r1a-05-pathfinding.md#selected-provisional-tuning-and-deterministic-evidence). Legacy runtime, existing 30-day simulation pin and production speed remain unchanged; no R1b activation or full R1A-17 completion is claimed.
- Spike evidence for `ms_per_step` (M05): 300 ms gives 1 px per 60 Hz frame with 11 % zero-advance frames; 250 ms gives mostly 1 px, occasionally 2. Either is acceptable; the choice is made in R1a with the simulation digest.

## Deferred
- Hierarchical pathfinding and path caches (only if profiling shows a need).
- Non-rectangular rooms.
- Other agents and dynamic occupancy.
- Opening the placeholder rooms. The Creation Room opens with project/creation capabilities and the System Room with System Investigator integration; Future Space is undecided.

## Consequences
- Maple's walks are always physically plausible: doors only exist where rooms touch.
- Adding a room or a door is a validated data change.
- Determinism is preserved: Manhattan integer costs need no declared edge lengths.
- **Future compatibility:**
  - Workspace, Projects, Library and System Investigator need no movement changes. They act only through capabilities, task targets and slots (ADR-0036, ADR-0039).
  - The System Room and Creation Room already exist as reserved regions.
