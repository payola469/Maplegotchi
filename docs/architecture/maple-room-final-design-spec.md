# Maple Room Final Design Spec: the initial house

> **OWNER-APPROVED IN PRINCIPLE (2026-10-09). NOT IMPLEMENTED.**
> - This document defines the initial Maple house that R1b migrates production into (ADR-0037 §3).
> - Implementation is **not authorized**: R1a has not started, and no code, schema, service, configuration or deployment exists for it.
> - It applies the accepted Room baseline (ADR-0035..0041, CLAUDE.md D34–D40) and the values locked by the technical spike (ADR-0041 "Locked values", `docs/spikes/2026-10-room-art-spike.md`). It changes **no** locked decision.
> - Owner decision **O1** (2026-10-09) is recorded in §U: the placeholder rooms are interior rooms without windows.
> - Final art appearance is out of scope. Art follows `maple-art-production-contract.md`.

- **Status:** owner-approved in principle. It becomes binding geometry for R1b when R1a/R1b are authorized and the implementation reproduces it under the validation rules of §S. Changes before then need an owner decision.
- **Date:** 2026-10-09
- **Baseline:** `v0.2-development` @ `081a037`, schema v10.
- **Inputs:**
  - ADR-0035 (world model), ADR-0036 (catalog and capabilities), ADR-0037 (persistence, v11, legacy projection), ADR-0038 (Edit Mode), ADR-0039 (Storage and slots), ADR-0040 (view transition and gate), ADR-0041 (art contract and locked values);
  - `maple-future-architecture.md` §6 and §9;
  - `maple-art-production-contract.md`;
  - the spike report;
  - the current room implementation (`backend/src/maplegotchi/core/room.py`, `core/activities.py`, `frontend/src/room/layout/anchors.ts`) for legacy compatibility.
- **Roadmap:** `docs/roadmap/maple-roadmap.md` is unchanged. This spec is roadmap STEP 1 (Room Final Design Spec) for R1.
- **Verification:**
  - All geometry was checked by a scratch script (not repository code) for overlaps, room-floor containment, reachability, door corridors, approach-tile conflicts (§K, S8), the lighting partition and the camera fit. It found **0 violations** (§T6).
  - The R1a implementation must re-establish every rule in §S with real tests.

### Status vocabulary used here

| Label | Meaning |
|---|---|
| **LOCKED** | Fixed by an accepted ADR or the 2026-10-09 technical lock. Cited, never changed here. |
| **SPEC** | Decided by this spec (owner-approved in principle). |
| **PROVISIONAL** | Tuning or reference values that R1a may adjust under the §S rules, e.g. scoring weights and occupy px offsets. |
| **UNDECIDED** | A product or art choice that stays open. |
| **DEFERRED** | Belongs to a later phase. |

### Conventions
- **Tiles** are `(tx, ty)`: origin at the north-west, x grows east, y grows south. T = 16 px (LOCKED).
- **Regions:**
  - A room **region** is its **floor rectangle** `(x, y, w, h)`.
  - Walls follow ADR-0041 L8 (LOCKED):
    - each room has a 3-row north band directly above its region, spanning x−1 … x+w;
    - 1-column side walls at x−1 and x+w;
    - an exterior south cutaway row below the lowest tier.
  - A band shared by two vertically stacked rooms is the **southern** room's north wall.
- **Objects:**
  - An object's **tile origin** is the north-west tile of its footprint.
  - All initial instances use orientation `south`, which keeps the first art deliveries to the `south` orientation (contract A.5).
  - Occupy offsets are px from the object anchor (contract B.4). They are the spike's reference values, **PROVISIONAL** per object (`geometry_version` review, ADR-0036).
- **Wall-mounted objects** occupy band columns. Their approach tile is the floor tile directly below.

---

## A. Global house dimensions (SPEC)

- **Grid:** **44 × 26 tiles = 704 × 416 world px.**
- **No outer margin:** every cell is a room floor, a wall, or a door passage. The camera letterboxes.
- **Vertical stack:**

  | Rows | Content |
  |---|---|
  | 0–2 | exterior north band (north tier) |
  | 3–9 | north-tier floors (7 rows) |
  | 10–12 | Central Hall north band (interior) |
  | 13–16 | Central Hall floor (4 rows) |
  | 17–19 | south-tier north bands (interior) |
  | 20–24 | south-tier floors (5 rows) |
  | 25 | exterior south cutaway |

- **Side-wall columns:**
  - north tier: 0, 9, 20, 31, 43;
  - Hall: 0, 43;
  - south tier: 0, 14, 29, 43.
- **Why 44 × 26:** it is the largest grid that fits **desktop Overview at L1 at every DPR from 1 to 3** under the locked zoom rule `Zd = max(1, ⌊L·DPR + 0.25⌋)`.
  - The binding case is DPR 1.75: Zd = 2 gives 44.1 × 26.5 visible tiles in the measured 806×484 room box (spike M01).
  - Tablet and phone use the locked DOM room-list fallback.
  - Growth happens inside the reserved regions and rooms (§Q), never by resizing the grid.

### House map (generated from the verified geometry)

```
    0         1         2         3         4
    01234567890123456789012345678901234567890123
 0  ============================================
 1  =====WW=F===F====WW======WW=====PP==WW======
 2  ============================================
 3  |###o.o.o|..o.....o#|####.o....|o###.o#####|
 4  |##o.....|.........o|oooo......|.###..###o.|
 5  |##......|#####.....|..........|..o....o...|
 6  |........|oror......|..........|...........|
 7  |........|.rrr......|###.......|...........|
 8  |........|..........|.oo.......|...........|
 9  |........|..........|..........|...........|
10  =====DD========DD========DD=========DD======
11  =====DD===F====DD========DD====F====DD======
12  =====DD========DD========DD=========DD======
13  |.........o....................o...........|
14  |...................rrr....................|
15  |.........i.........rir.........i..........|
16  |..........................................|
17  ======XX=============XX=============XX======
18  ======XX=============XX=============XX======
19  ======XX=============XX=============XX======
20  |:::::::::::::|::::::::::::::|:::::::::::::|
21  |:::::::::::::|::::::::::::::|:::::::::::::|
22  |:::::::::::::|::::::::::::::|:::::::::::::|
23  |:::::::::::::|::::::::::::::|:::::::::::::|
24  |:::::::::::::|::::::::::::::|:::::::::::::|
25  ____________________________________________
```

**Legend:**

| Symbol | Meaning |
|---|---|
| `=` | 3-row wall band |
| `\|` | side wall |
| `_` | south cutaway |
| `.` | walkable floor |
| `:` | closed-room floor (inaccessible) |
| `#` | blocking object |
| `r` | rug (non-blocking) |
| `i` | idle spot |
| `o` | interaction or slot approach tile |
| `D` / `X` | open / closed archway passage |
| `W` / `F` / `P` | window / wall frame / project board (on the band) |

**Rooms in the map:**
- North tier, west to east: Bedroom, Living Room, Library, Work Studio.
- Middle: Central Hall.
- South tier, west to east: Future Space, Creation Room, System Room.

## B. Room regions (SPEC)

| Room | x | y | w × h | Floor tiles | Walls | Status | Role |
|---|---|---|---|---|---|---|---|
| `bedroom` | 1 | 3 | 8 × 7 | 56 | exterior N band rows 0–2; side x0, x9; south edge = Hall band | **open** | production-active |
| `living_room` | 10 | 3 | 10 × 7 | 70 | exterior N band; side x9, x20 | **open** | production-active |
| `library` | 21 | 3 | 10 × 7 | 70 | exterior N band; side x20, x31 | **open** | production-active |
| `work_studio` | 32 | 3 | 11 × 7 | 77 | exterior N band; side x31, x43 | **open** | production-active |
| `central_hall` | 1 | 13 | 42 × 4 | 168 | interior N band rows 10–12; side x0, x43; south edge = placeholder bands | **open** | production-active hub |
| `future_space` | 1 | 20 | 13 × 5 | 65 | interior N band rows 17–19; side x0, x14; S cutaway row 25 | **closed** | placeholder |
| `creation_room` | 15 | 20 | 14 × 5 | 70 | interior N band; side x14, x29; S cutaway | **closed** | placeholder |
| `system_room` | 30 | 20 | 13 × 5 | 65 | interior N band; side x29, x43; S cutaway | **closed** | placeholder |

**Intended capabilities** (ADR-0036 vocabulary):

| Room | Capabilities |
|---|---|
| `bedroom` | `sleep_spot`, `window_view`, display (`display_shelf`, `display_wall`) |
| `living_room` | `seat`, `seat_soft`, `window_view`, `plant`, `quiet_spot`, `light_source`, display |
| `library` | `reading_spot`, `book_source`, `book_storage`, `seat`, `window_view`, `light_source`, display |
| `work_studio` | `writing_surface`, `computer`, `seat`, `window_view`, `display_shelf`, `project_board` (hook) |
| `central_hall` | `open_floor`, `display_wall` |
| `future_space` | none now; later capability **UNDECIDED** |
| `creation_room` | none now; later creation/project display types (`project_board`, creation-display furniture) |
| `system_room` | none now; later `system_console` |

**Why the open rooms form the north tier:**
- Windows are allowed only on exterior north walls (ADR-0041 L10). The Living Room's window/plant corner needs one, and every open room gets a daylight hook.
- The west-to-east order Bedroom → Living Room → Library → Work Studio **mirrors the legacy x-order** (bed/sofa 150, bookshelf 330, window 500, desk 640, terminal 840), so the legacy projection stays monotonic (§N).

## C. House topology (SPEC)

- **Doors:**
  - All doors are **2T open archways** through a 3-row east–west band (ADR-0041 L9, C5), with the passage running north–south.
  - The initial house has **no side doors**.
  - A passage's tiles belong to the room **south** of the band.
- **Door list:** see table T2 (§T).
  - The 4 north-tier doors pass through the Hall's north band and are **open**.
  - The 3 placeholder doors pass through the placeholders' bands and start **closed**.
- **Derived room graph (open doors only):** a **star centred on the Central Hall**.
  - Edges: `bedroom—central_hall`, `living_room—central_hall`, `library—central_hall`, `work_studio—central_hall`.
  - Each placeholder becomes a leaf when its door opens.
- **Reachability:** every open room is reachable from every other through the Hall, without teleport (verified).
- **Why a star:**
  - it is the simplest topology that is always connected;
  - a closed or future room can never sit on a path between open rooms;
  - opening a placeholder is a door-state change only (ADR-0035 §2).

## D. Central Hall (SPEC)

- **Size:** 42 × 4 floor (x1–42, y13–16), the full house width, plus its band rows 10–12.
- **Doors:**
  - north to Bedroom (x5–6), Living Room (x15–16), Library (x25–26) and Work Studio (x36–37);
  - south to Future Space (x6–7), Creation Room (x21–22) and System Room (x36–37).
- **Walking lanes:**

  | Row | Role |
  |---|---|
  | 14–15 | main east–west lanes, 2 tiles wide, x1–42 |
  | 13 | north-door approach row |
  | 16 | south-door approach row |

- **Idle areas:** three `open_floor` spots: west (10,15), **centre (21,15)**, east (32,15). They correspond 1:1 to the legacy `open_area.west/center/east`.
- **Contents:** light decoration only, with **0 blocking tiles**.
  - a non-blocking rug at x20–22, y14–15;
  - two wall frames on the Hall band at x10 and x31.
- **Why it is the circulation hub:**
  - every room is one door away;
  - it can never be obstructed;
  - its long east–west lanes give the camera a predictable Follow path between rooms.

## E. Bedroom (SPEC; x1–8, y3–9)

| Instance | Placement | Interaction / slot |
|---|---|---|
| `bed.bedroom` (`furniture.bed_single`, 2 × 3, north wall) | origin (1,3) | `sleep`: approach **(3,4), facing left**; occupy px (16, −10), `lie_sleep`, facing up. The blanket is an `above_occupant` part (spike M11). |
| `bedside.bedroom` (`furniture.side_table`, 1 × 1) | (3,3) | slot `top`: approach (4,3), facing left |
| `window.bedroom` (`window.north_2w`) | north band x5–6, `mount_y_px` 8 | `view`: approach (6,3), facing up |
| `frame.bedroom` (`decor.wall_frame_small`) | north band x8, `mount_y_px` 28 | slot `artwork`: approach (8,3), facing up |

- **Sleep capability:** `sleep_spot`, provided only by the bed.
- **Clearance:**
  - 49 walkable tiles;
  - the door corridor (x5–6, y8–9) is clear;
  - the bed's approach is 5 steps from the door.
- **Free display space:** x5–8, y5–8, available to the owner (§Q).

## F. Living Room (SPEC; x10–19, y3–9)

| Instance | Placement | Interaction / slot |
|---|---|---|
| `sofa.living` (`furniture.sofa`, 3 × 1) | (11,5) | `seat`: approach **(12,6), facing up**; occupy px (24, −4), `sit_rest`, facing down |
| `side_table.living` (`furniture.side_table`) | (10,5) | slot `top`: approach (10,6), facing up |
| `lamp.living` (`furniture.lamp_floor`) | (14,5) | `light_source` (geometry hook) |
| `rug.living` (`furniture.rug`, 3 × 2, non-blocking) | (11,6) | — |
| `window.living` (`window.north_2w`) | north band x17–18, `mount_y_px` 8 | `view`: approach **(18,3), facing up**. This is the canonical think spot (legacy "Window / Plant Corner"). |
| `plant.living` (`furniture.plant_tall`) | (19,3) | `think`: approach (19,4), facing up |
| `frame.living` (`decor.wall_frame_small`) | north band x12 | slot `artwork`: approach (12,3), facing up |

- **Capabilities:** rest (`seat_soft`, sofa) and think (`window_view` / `quiet_spot`).
- **Clearance:** 64 walkable tiles. Columns 15–19, rows 4–9 stay open between the door and the window corner.

## G. Library (SPEC; x21–30, y3–9)

| Instance | Placement | Interaction / slot |
|---|---|---|
| `bookshelf.library_1` (`furniture.bookshelf_tall`, 2 × 1, north wall) | (21,3) | `front_l` (21,4) and `front_r` (22,4), facing up, `stand_read`, no occupy; slot `books` (hook) |
| `bookshelf.library_2` | (23,3) | `front_l` (23,4) and `front_r` (24,4); slot `books` (hook) |
| `window.library` (`window.north_2w`) | north band x25–26 | `view`: approach (26,3), facing up |
| `armchair.library` (`furniture.armchair`, 1 × 1) | (22,7) | `seat`: approach (22,8), facing up; occupy px (8, −4), `sit_read`, facing down |
| `side_table.library` (`furniture.side_table`) | (23,7) | slot `top`: approach (23,8), facing up |
| `lamp.library` (`furniture.lamp_floor`) | (21,7) | `light_source` |

- **Reading capability:** `reading_spot`, with 5 points (4 shelf fronts and the armchair).
- **Document hooks:**
  - the bookshelves' `books` slots (library items, fullness derived);
  - the side table accepts `document.stack` as well as small creations.
- **Growth reserve:** x27–30, y3 along the north wall, room for **two more bookshelves** (+4 reading points, +8 book capacity) without moving anything.
- **Clearance:** 63 walkable tiles. The door corridor x25–26 leads straight to the window.

## H. Work Studio (SPEC; x32–42, y3–9)

| Instance | Placement | Interaction / slot |
|---|---|---|
| `desk.writing` (`furniture.writing_desk`, 3 × 2) | (33,3) | `chair`: approach **(34,5), facing up**; occupy px (24, −6), `sit_write`, facing up; slot `desktop` |
| `desk.computer` (`furniture.computer_desk`, 3 × 2) | (38,3) | `operator`: approach **(39,5), facing up**; occupy px (24, −6), `sit_monitor`, facing up |
| `window.studio` (`window.north_2w`) | north band x36–37 | `view`: approach (37,3), facing up |
| `shelf.studio` (`furniture.shelf_low`, 2 × 1) | (41,3) | slot `display`: approach (41,4), facing up |
| `board.studio` (`decor.project_board`, wall, 2 wide) | north band x32–33, `mount_y_px` 28 | slot `cards` (hook): approach (32,3), facing up |

- **Write and observe_server:**
  - `write` resolves only to the Writing Desk.
  - `observe_server` resolves to the Computer Desk until the System Room opens with a `system_console` (§M).
  - The Writing Desk and the Computer Desk remain **distinct types with disjoint capabilities** (D26, LOCKED).
- **Chairs** are part of each desk's footprint (the desk's south row), so there are no separate chair instances.
- **Growth reserve:** x40–42, y6–8 for a future project table (W-phases).
- **Clearance:** 63 walkable tiles. The two desk approaches are 5 steps apart.

## I. Closed placeholder rooms (SPEC; O1 applied)

| Room | Region | Door | Why this location | Later capability |
|---|---|---|---|---|
| `future_space` | (1,20) 13 × 5 | x6–7, y17–19 | West end. The most neutral position for an undecided purpose. | **UNDECIDED** |
| `creation_room` | (15,20) 14 × 5 | x21–22, y17–19 | Central, just across the Hall from the Living Room / Library boundary and near the Studio. | Creation/project display types (roadmap R5, W-phases) |
| `system_room` | (30,20) 13 × 5 | x36–37, y17–19 | **Directly in line with the Work Studio door**: a straight 11-step walk across the Hall. | `system_console` (System Investigator). `observe_server` then prefers it. |

**Rules:**
- **Closed now:**
  - no furniture, no production art (ADR-0040 §2, ADR-0041 §5);
  - their floors are **inaccessible** (§K).
- **Opening later** is a door-state change to `open`, plus a layout revision that adds furniture.
  - Regions, walls, bands and the room graph's shape are unchanged.
  - Both sides of every closed door are already kept clear (K1).
- **Interior rooms (O1, owner decision 2026-10-09):**
  - The placeholders have no exterior north wall, so they have no windows and no natural daylight.
  - The System Room suits an interior location.
  - The Creation Room may use designed artificial and task lighting.
  - Future Space stays undecided.
  - The topology is **not** to be redesigned to add windows to them.
  - O1 does **not** alter the locked window rule (ADR-0041 L10): windows remain exterior-north-wall-only. These rooms simply have no exterior north wall.

## J. Object instances (SPEC)

The full list is table T3 (§T).
- **Totals:** 28 instances (19 floor objects and markers, 9 wall-mounted) and **34 blocking tiles**: Bedroom 7, Living Room 6, Library 7, Work Studio 14, Hall 0.
- **Ownership:** every initial instance is `owner: paolo`, `movable_by: [owner]`, `deletable_by: [owner]`. **Maple moves no furniture** (ADR-0039).

**Catalog types beyond the spike fixtures.** Their reference geometry is defined in R1a and is **PROVISIONAL** under `geometry_version` review:

| Type | Footprint | Blocks | Points | Slots / capabilities |
|---|---|---|---|---|
| `furniture.side_table` | 1 × 1 | yes | none (slot only) | slot `top` |
| `furniture.armchair` | 1 × 1 | yes | `seat`, approach south | `reading_spot`, `seat` |
| `furniture.shelf_low` | 2 × 1 | yes | none (slot only) | slot `display` |
| `decor.project_board` | wall, 2 wide | n/a | none (slot only) | `project_board`, `display_wall`; slot `cards` |
| `marker.idle_spot` | 1 × 1 | no | `idle` on its own tile | `open_floor`; **no art**; structural kind |

## K. Walkability (SPEC)

- **Rule:** walkable = floor of **open** rooms + passages of **open** doors − blocking masks.
  - Floors of **closed** rooms and closed passages are **not** walkable.
  - This makes ADR-0035's recovery safe: Maple can never be relocated into a closed room.
- **Result:**
  - **431 walkable tiles** (Bedroom 49, Living Room 64, Library 63, Work Studio 63, Hall 168, open passages 24), all in **one connected component**;
  - 200 closed-room floor tiles are excluded.
- **Clearances:**
  - Maple occupies 1 tile, so the minimum corridor is 1 tile.
  - The Hall main lanes are 2 tiles wide.
  - Every door has **2 clear tiles on both sides** across both of its columns, including closed doors.
  - **Approach-tile sharing rule (S8):**
    - Two **unrelated** references (points or slots on different objects, or two points) must **never** share an approach tile.
    - A slot **may** reuse an interaction point **of its own host object**, but only when that reuse is **declared** (T5 `shares_point`) and validated: the declared point must exist on the same instance and have the same tile and facing.
    - The initial house has **29 approach references** (17 points + 12 slots) on **26 distinct tiles**. Exactly **three declared reuses** account for the difference:
      - `bookshelf.library_1/books` → `front_l`;
      - `bookshelf.library_2/books` → `front_l`;
      - `desk.writing/desktop` → `chair`.
- **Keep-clear tiles** (never accept a blocking footprint; non-blocking rugs and markers are allowed):

  | Code | Tiles |
  |---|---|
  | **K1** | each door's 2 columns × 2 rows on each side |
  | **K2** | every interaction and slot approach tile |
  | **K3** | Hall rows 14–15 |
  | **K4** | in each north room, the columns of its door from row 9 up to the room's approach row (the door-to-furniture path) |

- **No-trap condition:** all walkable tiles of open rooms form one component (verified). Dead-end corners are allowed. Isolated pockets are not.
- **Recovery-safe tile:** `idle.hall_center` (21,15). It is never blocked (K2/K3) and is the canonical fallback. The ADR-0035 BFS searches only the open connected component.

## L. Placement slots (SPEC)

The full list is table T5 (§T).
- **Active slots** exist now and accept an eligible item as soon as one exists.
  - `maple_may_place = true` (ADR-0039 B5): only `movable_by: maple` objects, walk first, core-validated, audited, rate-limited, with a cooldown after owner removal.
  - No eligible items exist before creations and representations ship (W-phases), so the active slots start empty.
- **Hook slots** have `maple_may_place = false`. Derived representations fill them in later phases:
  - bookshelf `books` (library items, fullness derived);
  - board `cards` (planned projects).
- **Accepts classes** (`creation.small`, `creation.flat`, `document.stack`, `library.book`, `project.active`, `project.card`) are **PROVISIONAL** names (ADR-0039).
- **Slots never affect walkability** (ADR-0039 §2).

## M. Interaction model (SPEC; scoring PROVISIONAL)

**Activity requirements for R1b** (core table, versioned with the activity set):

| Activity | Requires | Candidates in the initial house | Approach → occupy (facing) | If no candidate |
|---|---|---|---|---|
| `sleep` | `sleep_spot` | `bed.bedroom/sleep` | (3,4) facing left → `lie_sleep` facing up, under the blanket overlay | activity not allowed |
| `rest` | `seat_soft` | `sofa.living/seat` | (12,6) facing up → `sit_rest` facing down | not allowed |
| `think` | `window_view` ∨ `quiet_spot` | `window.living/view`, `plant.living/think`, `window.{bedroom,library,studio}/view` | approach, facing up → `stand_think` on the tile | not allowed |
| `read` | `reading_spot` | 4 shelf fronts; `armchair.library/seat` | facing up → `stand_read` on the tile; armchair: `sit_read` facing down | not allowed |
| `write` | `writing_surface` ∧ `seat` | `desk.writing/chair` | (34,5) facing up → `sit_write` facing up | not allowed |
| `observe_server` | `system_console` ∨ `computer` | `desk.computer/operator` | (39,5) facing up → `sit_monitor` facing up | not allowed |
| `idle`, `walk` | `open_floor` | `idle.hall_{west,center,east}` | on the tile, facing down → `idle` | not allowed |

- **"Not allowed"** means the activity drops out of the Director's `allowed.actions`, and rule direction picks another (ADR-0036 §3).
  - Rule S9 guarantees ≥ 1 reachable candidate for every activity in every saved layout, so in practice it never happens.
- **Two deliberate narrowings** of the *PROPOSED* table in `maple-future-architecture.md` §6.6:
  1. `rest` drops "∨ `sleep_spot`";
  2. the bed provides only `sleep_spot`, and the armchair provides `seat` (not `seat_soft`).

  **Why:**
  - each activity keeps one legacy-faithful object class in R1b, so the legacy view never has to show something it cannot (e.g. daytime rest in bed);
  - daytime rest stays on the sofa, as today.

  Both are additive changes later.
- **Resolution score** (PROVISIONAL weights; ADR-0036 §3): `score = 1000·room_tier + path_steps − 50·sticky − 200·preference`.
  - The lowest score wins. Ties use the seeded `decision` RNG stream, never set order.
  - Room tiers (0 is preferred):

    | Activity | Tier 0 | Tier 1 | Tier 2 |
    |---|---|---|---|
    | think | `living_room` | `library` | others |
    | read | `library` | `living_room` | — |
    | observe_server | `system_room` (once open) | `work_studio` | — |
    | others | their only room | — | — |

  - **Effect:** R1b behaviour matches today's 1:1 legacy behaviour, while new furniture providing the same capability is used without code changes.

## N. Legacy projection (SPEC; ADR-0037 §4)

- **Rule:** **legacy point = f(activity, idle spot)**. The legacy world maps each activity to exactly one point, except idle/walk, which have three. The projected point therefore always passes the legacy `InteractionPoint` validation (`allowed_actions` contains the activity). Full mapping: table T7.
- **Walking in the legacy view:**
  - The legacy route runs from the projected origin point to the projected destination point over the existing legacy waypoint graph.
  - It uses the grid route's **same `departed_at` and `arrives_at`**, so the arrival and the activity start match the backend exactly.
  - Only the path shape and apparent speed differ (cosmetic).
- **Closed placeholder rooms** are unreachable, so they need no legacy mapping. The projection **raises** on an unmapped point instead of guessing.
- **No invented state:**
  - activity, timing, reaction, expression, pose class and day phase pass through unchanged;
  - only position is simplified;
  - the true room, tile and point stay in the new API fields.
- **Lifetime:** the projection is pure, unit-tested, and removed only with the old view (ADR-0040 §4).

## O. Camera fit (SPEC check against LOCKED L13–L15)

All values are computed with `Zd = max(1, ⌊L·DPR + 0.25⌋)` in the spike's measured room boxes: desktop 806 × 484, tablet 654 × 392, phone 348 × 209 CSS px.

**Overview (house 44 × 26 at L1):**

| Form factor | Result |
|---|---|
| desktop | **fits at every DPR 1–3** |
| tablet | fits at DPR 1.25, 1.5, 2.25 and 2.5; DOM room-list fallback at 1, 1.75, 2, 2.75 and 3 |
| phone | always the DOM room-list fallback |

**Follow (visible tiles, the same at every DPR):**

| Form factor | L2 | L3 |
|---|---|---|
| desktop | 25.2 × 15.1 | 16.8 × 10.1 |
| tablet | 20.4 × 12.3 | 13.6 × 8.2 |
| phone | 10.9 × 6.5 | 7.3 × 4.4 |

A north room including its band is at most 13 × 10 tiles, so it is almost entirely visible at desktop L3.

**Focus (largest L that fits the room including its walls, at the worst DPR):**

| Room | Desktop | Tablet | Phone |
|---|---|---|---|
| north rooms | L2 | L2 | L1 |
| placeholders | L2–L3 | L2 | L1 |
| `central_hall` | L1 | **none** | **none** |

**Oversize Focus target.** The Hall (44 tiles wide with walls) exceeds the tablet and phone boxes even at L1. The locked L15 rule ("largest L ≤ 4 that fits") does not define this case. This spec specifies, as a camera clarification for R1a (not a change to a locked value): **Focus on a region that does not fit at L1 uses L1, centred on Maple if she is in that region, otherwise on the region centre, clamped to the house.**

**Not chosen here:** the default zoom per form factor (including the default Follow level) stays **UNDECIDED** (Q4, ADR-0041).

**Verdict:** the geometry is technically viable under every locked camera rule.

## P. Lighting-zone geometry (SPEC; LOCKED L16 applied)

**Partition rule:**
- a band belongs to the room whose floor lies south of it, including that band's door passages;
- a side wall belongs to the room west of it, and the exterior west wall to the room east of it;
- the exterior south cutaway belongs to the room north of it.

| Zone | Cells |
|---|---|
| `bedroom` | x0–9, y0–9 |
| `living_room` | x10–20, y0–9 |
| `library` | x21–31, y0–9 |
| `work_studio` | x32–43, y0–9 |
| `central_hall` | x0–43, y10–16 |
| `future_space` | x0–14, y17–25 |
| `creation_room` | x15–29, y17–25 |
| `system_room` | x30–43, y17–25 |

- **Coverage:** the 8 rectangles tile all **1,144 cells exactly once**, so a double-tint seam is impossible.
- **Light hooks** (geometry only; colours and strengths UNDECIDED, Q4):

  | Hook | Positions |
  |---|---|
  | daylight spill | the 4 north-band windows (x5–6, x17–18, x25–26, x36–37) |
  | floor lamps | (14,5) and (21,7) |
  | emissive | the Computer Desk screen |

- **Hall and placeholders:** the Hall is lit by its room preset. The placeholders are interior and windowless (O1). When opened, they use artificial room presets, task lights and emissive hooks, with no natural window daylight.

## Q. Growth capacity (SPEC)

None of these changes the grid, regions, walls, bands or door positions:
- **Creation Room opening:** set `door.hall_creation` to open, then a layout revision adds creation and project display furniture in its 14 × 5 region.
- **System Room opening:** set `door.hall_system` to open, then add a `system_console`. `observe_server` then prefers the System Room (tier 0), with the Computer Desk as fallback.
- **Future Space:** a 13 × 5 region, purpose UNDECIDED. Opening it is the same door flip.
- **More display furniture:**

  | Room | Space |
  |---|---|
  | Library | 2 bookshelves at x27–30, y3 |
  | Work Studio | project-table reserve x40–42, y6–8 |
  | Bedroom | free x5–8, y5–8 |
  | Hall | 34 plain band columns for more wall frames |

  Every addition must pass §S, notably K1–K4 and S9.
- **Project and library representations:** through the hook slots (`books`, `cards`, `document.stack` on the Library side table) and the soft `link` field (ADR-0037 §1, ADR-0039 §4).

## R. Migration implications (SPEC; no migration code)

**Current legacy points map to the new points:**

| Current point (legacy location) | New point | Tile |
|---|---|---|
| `bed.side` (`bed`) | `bed.bedroom/sleep` | (3,4) |
| `sofa.seat` (`sofa`) | `sofa.living/seat` | (12,6) |
| `bookshelf.front` (`bookshelf`) | `bookshelf.library_1/front_l` | (21,4) |
| `window.view` (`window`) | `window.living/view` | (18,3) |
| `writing_desk.chair` (`desk`) | `desk.writing/chair` | (34,5) |
| `computer_desk.chair` (`terminal`) | `desk.computer/operator` | (39,5) |
| `open_area.west` / `.center` / `.east` (`rug`) | `idle.hall_west` / `idle.hall_center` / `idle.hall_east` | (10,15) / (21,15) / (32,15) |
| `point_id` null | the canonical new point of the location (`rug` → `idle.hall_center`) | — |

- **Initial Maple position:**
  - her current point is mapped through this table;
  - a route in flight at migration becomes a zero-length plan at its destination's new point (ADR-0037 §3);
  - no timeline events are fabricated.
- **Room derivation:** Maple's room is derived from the region; there is no stored room field.
- **New births** (development data only) start at `idle.hall_center`.
- **Legacy anchors** stay exactly as today (`core/room.py` POINTS, `anchors.ts`). §N feeds them.
- **Migration discipline:** the v11 migration discipline, the rehearsal on a production copy and the owner snapshot gate are unchanged (ADR-0037, ADR-0028).

## S. Validation rules (SPEC; the layout must always satisfy these)

1. **S1** The grid is 44 × 26. Every region lies inside it, and regions do not overlap.
2. **S2** Bands, side walls and the cutaway follow L8. North-tier bands (rows 0–2) are the only exterior north walls.
3. **S3** Each door is 2 columns through exactly one 3-row band. It joins the region directly above and the region directly below, which are physically adjacent.
4. **S4** The room graph over **open** doors is connected across all open rooms. Closed rooms are exempt.
5. **S5** Closed-room floors and closed door passages are not walkable. No path, recovery or placement targets them.
6. **S6** Every floor footprint lies inside one room's floor. Blocking masks do not overlap.
7. **S7** Wall-mounted objects sit only on plain band cells, never on door columns. Windows sit only on exterior north bands.
8. **S8** Every interaction-point and slot approach tile is walkable and reachable from `idle.hall_center`.
   - **No two unrelated references share a tile.** Unrelated means points of different instances, two points of one instance, or a slot and a point of different instances.
   - The **only** allowed reuse is a slot that **declares** `shares_point` naming an interaction point of the **same instance**. The validator checks that the point exists on that instance and has the same approach tile and facing.
   - An undeclared coincidence is an error.
   - Initial house: 29 references on 26 distinct tiles, with exactly 3 declared reuses (T5).
9. **S9** Every activity in the activity set has ≥ 1 reachable candidate. This carries today's `core/room.py` `_validate_room` invariant forward. A layout removing the last provider is rejected.
10. **S10** No blocking footprint lies on a keep-clear tile (K1–K4), including the corridors of closed doors.
11. **S11** Slots never affect walkability. Hook slots have `maple_may_place = false`.
12. **S12** The lighting zones partition all cells exactly once.
13. **S13** Maple's tile is walkable. Recovery uses a BFS inside the open component only. `idle.hall_center` exists and is never blocked.
14. **S14** Every legacy projection target exists, and its legacy `allowed_actions` contain the projected activity.
15. **S15** The Writing Desk and Computer Desk capability sets are disjoint (D26).
16. **S16** No initial instance is `movable_by: maple`. Only display placements are Maple-controlled (ADR-0039).
17. **S17** Every type and orientation used exists in the catalog. Its `geometry_version` matches the art manifest (ADR-0041, contract C.8).

## T. Final design tables (SPEC; machine-friendly)

### T1. House regions
```
id,kind,x,y,w,h,floor_tiles,status,lighting_zone
bedroom,bedroom,1,3,8,7,56,open,x0-9:y0-9
living_room,living,10,3,10,7,70,open,x10-20:y0-9
library,library,21,3,10,7,70,open,x21-31:y0-9
work_studio,studio,32,3,11,7,77,open,x32-43:y0-9
central_hall,hall,1,13,42,4,168,open,x0-43:y10-16
future_space,future,1,20,13,5,65,closed,x0-14:y17-25
creation_room,creation,15,20,14,5,70,closed,x15-29:y17-25
system_room,system,30,20,13,5,65,closed,x30-43:y17-25
```

### T2. Doors (all: archway, width 2, north–south passage)
```
id,north_room,south_room,x0,x1,y0,y1,state
door.hall_bedroom,bedroom,central_hall,5,6,10,12,open
door.hall_living,living_room,central_hall,15,16,10,12,open
door.hall_library,library,central_hall,25,26,10,12,open
door.hall_studio,work_studio,central_hall,36,37,10,12,open
door.hall_future,central_hall,future_space,6,7,17,19,closed
door.hall_creation,central_hall,creation_room,21,22,17,19,closed
door.hall_system,central_hall,system_room,36,37,17,19,closed
```

### T3. Object instances (orientation `south`; `band` = wall-mounted on that room's north band)
```
instance_id,type,room,origin,footprint,blocks,capabilities,mount_y_px
bed.bedroom,furniture.bed_single,bedroom,1;3,2x3,all,sleep_spot,-
bedside.bedroom,furniture.side_table,bedroom,3;3,1x1,all,display_shelf,-
window.bedroom,window.north_2w,bedroom,band x5-6,wall 2,-,window_view;light_source,8
frame.bedroom,decor.wall_frame_small,bedroom,band x8,wall 1,-,display_wall,28
sofa.living,furniture.sofa,living_room,11;5,3x1,all,seat;seat_soft,-
side_table.living,furniture.side_table,living_room,10;5,1x1,all,display_shelf,-
lamp.living,furniture.lamp_floor,living_room,14;5,1x1,all,light_source,-
rug.living,furniture.rug,living_room,11;6,3x2,none,-,-
window.living,window.north_2w,living_room,band x17-18,wall 2,-,window_view;light_source,8
plant.living,furniture.plant_tall,living_room,19;3,1x1,all,plant;quiet_spot,-
frame.living,decor.wall_frame_small,living_room,band x12,wall 1,-,display_wall,28
bookshelf.library_1,furniture.bookshelf_tall,library,21;3,2x1,all,reading_spot;book_source;book_storage,-
bookshelf.library_2,furniture.bookshelf_tall,library,23;3,2x1,all,reading_spot;book_source;book_storage,-
window.library,window.north_2w,library,band x25-26,wall 2,-,window_view;light_source,8
armchair.library,furniture.armchair,library,22;7,1x1,all,reading_spot;seat,-
side_table.library,furniture.side_table,library,23;7,1x1,all,display_shelf,-
lamp.library,furniture.lamp_floor,library,21;7,1x1,all,light_source,-
desk.writing,furniture.writing_desk,work_studio,33;3,3x2,all,writing_surface;seat,-
desk.computer,furniture.computer_desk,work_studio,38;3,3x2,all,computer;seat,-
window.studio,window.north_2w,work_studio,band x36-37,wall 2,-,window_view;light_source,8
shelf.studio,furniture.shelf_low,work_studio,41;3,2x1,all,display_shelf,-
board.studio,decor.project_board,work_studio,band x32-33,wall 2,-,project_board;display_wall,28
rug.hall,furniture.rug,central_hall,20;14,3x2,none,-,-
idle.hall_west,marker.idle_spot,central_hall,10;15,1x1,none,open_floor,-
idle.hall_center,marker.idle_spot,central_hall,21;15,1x1,none,open_floor,-
idle.hall_east,marker.idle_spot,central_hall,32;15,1x1,none,open_floor,-
frame.hall_west,decor.wall_frame_small,central_hall,band x10,wall 1,-,display_wall,28
frame.hall_east,decor.wall_frame_small,central_hall,band x31,wall 1,-,display_wall,28
```

### T4. Interaction points (approach = absolute tile; occupy px PROVISIONAL)
```
point,approach,facing,occupy_px,pose,occupy_dir,provides
bed.bedroom/sleep,3;4,left,16;-10,lie_sleep,up,sleep_spot
sofa.living/seat,12;6,up,24;-4,sit_rest,down,seat;seat_soft
window.living/view,18;3,up,null,stand_think,up,window_view
plant.living/think,19;4,up,null,stand_think,up,plant;quiet_spot
window.bedroom/view,6;3,up,null,stand_think,up,window_view
window.library/view,26;3,up,null,stand_think,up,window_view
window.studio/view,37;3,up,null,stand_think,up,window_view
bookshelf.library_1/front_l,21;4,up,null,stand_read,up,reading_spot;book_source
bookshelf.library_1/front_r,22;4,up,null,stand_read,up,reading_spot;book_source
bookshelf.library_2/front_l,23;4,up,null,stand_read,up,reading_spot;book_source
bookshelf.library_2/front_r,24;4,up,null,stand_read,up,reading_spot;book_source
armchair.library/seat,22;8,up,8;-4,sit_read,down,reading_spot;seat
desk.writing/chair,34;5,up,24;-6,sit_write,up,writing_surface;seat
desk.computer/operator,39;5,up,24;-6,sit_monitor,up,computer;seat
idle.hall_west/idle,10;15,down,null,idle,down,open_floor
idle.hall_center/idle,21;15,down,null,idle,down,open_floor
idle.hall_east/idle,32;15,down,null,idle,down,open_floor
```

### T5. Placement slots (accepts class names PROVISIONAL; `shares_point` = declared reuse of the same instance's interaction point, S8)
```
slot,approach,approach_facing,shares_point,accepts,capacity,maple_may_place,status
bedside.bedroom/top,4;3,left,-,creation.small,1,true,active
frame.bedroom/artwork,8;3,up,-,creation.flat,1,true,active
side_table.living/top,10;6,up,-,creation.small,1,true,active
frame.living/artwork,12;3,up,-,creation.flat,1,true,active
side_table.library/top,23;8,up,-,creation.small;document.stack,2,true,active
bookshelf.library_1/books,21;4,up,front_l,library.book,4,false,hook (derived fullness)
bookshelf.library_2/books,23;4,up,front_l,library.book,4,false,hook (derived fullness)
desk.writing/desktop,34;5,up,chair,project.active;creation.small,2,true,active
shelf.studio/display,41;4,up,-,creation.small,3,true,active
board.studio/cards,32;3,up,-,project.card,4,false,hook (planned projects)
frame.hall_west/artwork,10;13,up,-,creation.flat,1,true,active
frame.hall_east/artwork,31;13,up,-,creation.flat,1,true,active
```

### T6. Capability resolution (R1b)
```
activity,requires,candidates,room_tiers
sleep,sleep_spot,bed.bedroom/sleep,bedroom
rest,seat_soft,sofa.living/seat,living_room
think,window_view|quiet_spot,window.living/view;plant.living/think;window.bedroom/view;window.library/view;window.studio/view,living_room>library>others
read,reading_spot,bookshelf.library_1/front_l;bookshelf.library_1/front_r;bookshelf.library_2/front_l;bookshelf.library_2/front_r;armchair.library/seat,library>living_room
write,writing_surface&seat,desk.writing/chair,work_studio
observe_server,system_console|computer,desk.computer/operator,system_room>work_studio
idle|walk,open_floor,idle.hall_west/idle;idle.hall_center/idle;idle.hall_east/idle,central_hall
```

**Walk lengths between the canonical activity points** (grid steps, computed):

|  | sleep | rest | read | think | write | observe | idle |
|---|---|---|---|---|---|---|---|
| **sleep** | 0 | 31 | 44 | 34 | 52 | 53 | 29 |
| **rest** | 31 | 0 | 33 | 9 | 41 | 42 | 18 |
| **read** | 44 | 33 | 0 | 34 | 34 | 35 | 19 |
| **think** | 34 | 9 | 34 | 0 | 42 | 43 | 19 |
| **write** | 52 | 41 | 34 | 42 | 0 | 5 | 27 |
| **observe** | 53 | 42 | 35 | 43 | 5 | 0 | 28 |
| **idle** | 29 | 18 | 19 | 19 | 27 | 28 | 0 |

The longest walk is 53 steps: about 16 s at 300 ms/step, or 13 s at 250 ms/step. `ms_per_step` stays PROVISIONAL tuning (ADR-0035 §7).

### T7. Legacy projection (legacy coordinates in the 1000 × 600 room)
```
activity,new_points,legacy_point,legacy_xy
sleep,bed.bedroom/sleep,bed.side,150;455
rest,sofa.living/seat,sofa.seat,150;560
read,any reading_spot point,bookshelf.front,330;500
think,any window_view|quiet_spot point,window.view,500;470
write,desk.writing/chair,writing_desk.chair,640;470
observe_server,desk.computer/operator,computer_desk.chair,840;470
idle|walk,idle.hall_west/idle,open_area.west,400;550
idle|walk,idle.hall_center/idle,open_area.center,480;545
idle|walk,idle.hall_east/idle,open_area.east,580;550
walking,route in flight,legacy graph path origin->destination,same departed_at/arrives_at
```

**Verification record (scratch check, 2026-10-09; 0 violations):**
- **Reachability:** 431 walkable tiles, all reachable in one component; 0 closed-room tiles reachable.
- **Objects:** 34 blocking tiles, none overlapping, all inside their room floor.
- **Wall objects:** all on plain band cells.
- **Doors:** all 7 join adjacent regions, and their corridors are clear on both sides.
- **Approach tiles:** all 29 approach references (17 points, 12 slots) are walkable and reachable. They occupy 26 distinct tiles. The only coincidences are the 3 declared host-slot reuses (`bookshelf.library_1/books`, `bookshelf.library_2/books`, `desk.writing/desktop`), and there are 0 unrelated conflicts.
- **Lighting:** the partition covers 1,144 of 1,144 cells.
- **Camera:** desktop Overview fits at DPR 1–3.

## U. Owner decisions

| # | Decision | Status |
|---|---|---|
| **O1** | **Placeholder rooms are interior and windowless.** Creation Room, System Room and Future Space have no natural daylight. The topology is not redesigned to add windows. Reasons: preserve the validated 44 × 26 geometry and the desktop Overview fit; do not expand the house for inactive capabilities; the System Room suits an interior location; the Creation Room may use designed artificial and task lighting; Future Space stays undecided. | **DECIDED** (owner, 2026-10-09) |
| — | Future Space purpose | UNDECIDED (as accepted in ADR-0035/0040) |
| — | Default zoom per form factor; phase tint colours and light strengths | UNDECIDED (Q4, ADR-0041) |
| — | Face overlay size (12 × 6 vs 14 × 8) | PROVISIONAL (owner blind test, ADR-0041 P1) |
| — | Production art appearance of every object | UNDECIDED (Art chat; the contract governs delivery) |

Engineering choices made by this spec need no owner question: room order, door columns, furniture placement, the activity narrowings in §M, the scoring tiers, and the oversize-Focus rule.

## Risks and R1a notes (none blocks R1a)

1. **Oversize Focus:** the Central Hall cannot be focused at L1 on tablet or phone. §O specifies the behaviour, and R1a must implement and test it.
2. **Desktop Overview fit** assumes today's 806 × 484 room box (spike M01). If R1a's page layout shrinks the room panel, desktop Overview falls back to the DOM room list. That is allowed, but it should be covered by a layout test.
3. **New catalog types** (`side_table`, `armchair`, `shelf_low`, `decor.project_board`, `marker.idle_spot`) need reference geometry and validator support. The validator must accept a structural marker kind with no art frames.
4. **Closed-room inaccessibility** (§K, S5) is implied by ADR-0035 but stated explicitly here. Core walkability and recovery must implement it.
5. **Longer walks** (up to 53 steps) than today's few seconds. Choose `ms_per_step` with the simulation digest (ADR-0035 §7).
6. **Legacy walking speed** varies per walk, because the legacy path reuses the grid route's times. This is cosmetic, and the projection tests cover it.

## Deferred
- Side doors and room-to-room doors (none in the initial house; adding one is a validated layout change in R4).
- Free-standing placement zones (after R5, ADR-0039).
- Opening the placeholder rooms (ADR-0035, ADR-0040).
- Real representations in the hook slots (W2/W3/R5).
- Outdoor backdrops, sound and ambience (R6).
