# ADR-0035: World model — one house grid, derived room graph, 4-direction movement

- **Status:** Accepted — FIXED design (CLAUDE.md D34). **NOT IMPLEMENTED.** Implementation is not yet authorized. **Amended 2026-10-09:** the art/PixiJS technical spike passed (`docs/spikes/2026-10-room-art-spike.md`). `FEET_IN_TILE` (§6) and the wall grid convention (§4) are **LOCKED** (ADR-0041 L4, L8). Room sizes, door positions and movement tuning (§7) stay undecided.
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
- **The route lives in state** as compressed waypoints `(tx, ty, cumulative_steps)`. Travel time is `steps × ms_per_step`. The position at `now` is interpolated with `+ - * /` only.
- **No teleport (A7).** A destination with no path makes the action invalid (`no_destination`) and rule fallback applies. The only allowed non-walking position change is a **recorded recovery**: if a layout change blocks Maple's current tile, she moves to the nearest walkable tile by BFS with tie-break `(ty, tx)`, and a `maple_relocated` event records it.

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
- the room sizes and door positions of the initial house. These are **intentionally undecided** until the Room Final Design Spec (confirmed with B15). The technical art spike (2026-10-09) did **not** decide them; it only locked the wall, door and window conventions they must use (ADR-0041 L7–L10).
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
