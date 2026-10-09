# ADR-0041: Art technical contract

- **Status:** Accepted — FIXED design for the **rule set** (CLAUDE.md D40). **NOT IMPLEMENTED** (no production asset pipeline or art exists yet).
  - **Amended 2026-10-09:** the art/PixiJS technical spike passed all three gates (`docs/spikes/2026-10-room-art-spike.md`). The technically proven values are now **LOCKED** by owner decision (§"Locked values (2026-10-09)"), and accepted RULE text is corrected by amendments **C1–C8**.
  - The face overlay size, art appearance, default zoom per form factor, phase tints, room dimensions and door positions stay **PROVISIONAL / UNDECIDED**.
  - **R1a is not authorized.**
- **Date:** 2026-10-08 (amended 2026-10-09)
- **Decided by:** owner, Maple Room review decisions **B6** (face overlays), **B7** (art file locations), **B9** (direction vocabulary, art side), **B12** (feet in tile, provisional), **B13** (baseline A16), **B15** (master palette location), and **B2** (production art scope).
- **Contract text:** `docs/architecture/maple-art-production-contract.md` (DRAFT / PROPOSED / FOR HUMAN REVIEW; this ADR records which parts are accepted). **Related:** ADR-0035, ADR-0036, ADR-0040. **Spike report:** `docs/spikes/2026-10-room-art-spike.md`.

## Context

Art is being prepared now in a separate Maple Art chat. Assets must plug into the engine without reinterpretation. The art style itself (3/4 top-down pixel art, Cozy Digital Home + Personal AI Lab) is already agreed and is not part of this ADR.

## Decision

### 1. Accepted rule set (A16)
The RULE items of the contract are accepted:
- **Perspective and lighting:** 3/4 top-down oblique perspective with a top-left key light, and neutral base lighting.
- **Direction orders:** character directions are ordered `down, left, right, up` (rows); object orientations are ordered `south, east, west, north`.
- **Sheet layout:** rows are directions, columns are frames in playback order, cells abut with no gutters, and there is one animation per file.
- **Separate parts:** `shadow`, `light` (additive), `emissive`, `glass`, and occupant-overlay parts (`above_occupant`). No baked cast shadows, night tint or glow.
- **Export:** PNG RGBA at **1× only**, binary alpha on base and part layers, RGB 0 under transparent pixels, ancillary chunks stripped, and no mixels or non-90° rotation.
- **Identity:** the naming grammar (`category.name[.variant]--state--orientation[--part].png`), `meta.json` per asset ID, and IDs never reused.
- **Versioning:** `art_revision` covers repaints; `geometry_version` covers any geometry change, which requires engine catalog review (ADR-0036).
- **Atlases:** artists deliver sheets; the build pipeline trims, extrudes and packs.

### 2. Direction vocabulary (B9)
Character direction is `down/left/right/up` and object orientation is `south/east/west/north`, with the fixed mapping `down = south`, `up = north`, `left = west`, `right = east` (ADR-0035 §5). Every contract example uses this vocabulary.

### 3. Expressions: face overlays (B6)
- Maple's **five fixed expressions** are drawn as separate face overlay sprites: `calm`, `happy`, `curious`, `sleepy` and `focused`.
- **The backend remains the source of truth** for expression, and the renderer never invents one.
- Body animation sheets are **not** duplicated per expression.
- **Per-frame face anchors** keep the overlays aligned during head movement, sitting and animation.
- The `up` (back) direction needs no visible face.
- Sleep may use a fixed closed-eye face.
- Blink may be added as a small optional overlay animation.
- **Final face pixel dimensions and readability are not locked.** The spike proved the overlay *method* (now LOCKED, L6). 12×6 passes the automated distinctness proxy, but the size locks only after the owner's blind test (P1).

### 4. Art file locations (B7)
- **Production exports** stay in the main repository as **plain Git (not LFS)**: `art/export/**`, containing only production-ready PNGs and their `meta.json`.
- The build pipeline reads **only** from `art/export/**`.
- Generated atlases are build artifacts and are **never edited by hand**.
- **Working sources and concept material live outside the main repository**, in a separate private art repository or a deliberate Drive folder. That includes `.aseprite` files, mood boards, concept art, visual exploration and style references.
- ~~Raw `art/export` is marked `export-ignore` if the release pipeline packs it into `frontend/dist`.~~ **Superseded by amendment C1 (2026-10-09):**
  - `art/export/**` and `art/palette/**` are **not** `export-ignore`; they stay in `git archive` as release-build input;
  - raw art never appears in the runtime bundle (`frontend/dist`), and a bundle-content test enforces it.
- **LFS pointer files must never enter production asset inputs.** The validator rejects them.
- Art source history stays separate from runtime and release history.
- **Master palette (B15):**
  - It lives in `art/palette/**` in the main repository, as **plain Git (no LFS)**.
  - It holds only the production palette definitions used by the art validator and build pipeline.
  - It is not runtime content and not concept or mood-board material.
  - It is excluded from the runtime bundle unless the build needs it at runtime. It remains in `git archive` as build input (C1).
  - `art/export/**` stays reserved for production PNGs and `meta.json`.

### 5. Production scope (B2)
- Concept art may cover all 8 rooms now.
- Production art follows the phased rollout: the 5 open rooms and Maple's core set first (ADR-0040 §4). Placeholder rooms need no production art.

## Locked values (2026-10-09)

**Owner decision, 2026-10-09.** These values passed the art/PixiJS technical spike (`docs/spikes/2026-10-room-art-spike.md`; raw evidence on the unmerged branch `spike/room-art-tech`, `spikes/room-art/report/`). They are now **LOCKED** and binding for production assets and for R1a when it is authorized. Changing one needs a new owner decision. All evidence uses placeholder art. Tablet and phone evidence is EMULATED.

**Owner decision V1, walls and doors (same date; resolves spike choice V1):**
- Keep **3T walls**.
- North doors are **open archways**.
- Walls are **not** raised to 4T just to keep lintels.
- Maple is **not** shortened. Her canvas stays **32 × 48** (L2).

### A. Geometry and character

| # | Value | Locked | Evidence |
|---|---|---|---|
| L1 | Tile size T | **16 px** | M02, M06, M09, M10 |
| L2 | Maple canvas (every animation: standing, sitting, lying) | **32 × 48 px** | M06: max visible 22×44; 0 safe-area violations |
| L3 | Maple sprite feet anchor | **(16, 47) = (W/2, H−1)**; feet contact row 46 | M06: 56/56 standing frames exact; M02: feet row exact at every DPR × L |
| L4 | `FEET_IN_TILE` (ADR-0035 §6) | **(T/2, ⌊13T/16⌋) = (8, 13)** at T = 16 | M09: y 12, 13 and 14 all pass, so the tie keeps 13; cap clearance 7 px |
| L5 | Maple safe area / max visible width | x 2–29, y 1–46 / **≤ 22 px** | M06; door clearance 22 ≤ 2T − 2 |
| L6 | Face overlay **method** (not size) | top-left integer anchor per body frame, `face_anchor[row][frame]` (`null` = no face); glasses inside the overlay; the fixed sleep face is one cell | M04: 0 body/face offset errors in motion; M11 |
| L12 | Walk cycle | **4 frames per 2 steps**; the frame index is locked to route distance, not time (`ms` per walk frame = `ms_per_step / 2`, C8) | M05: 0 drift |

### B. Walls, doors, windows, depth

| # | Value | Locked | Evidence |
|---|---|---|---|
| L7 | North-wall height H_w / cap | **3T = 48 px**; wall cap **≤ 13 px** (8 px used by the placeholder) | M09 |
| L8 | Wall grid convention | **North (E–W) walls = 3 non-walkable grid rows** (H_w/T), with the face drawn exactly over them and the cap an always-front occluder. **Side (N–S) walls = 1 grid column**, with the top cap y-sorted per tile. Exterior south wall = 1 cutaway row. A side door is a wall gap whose neighbouring wall tiles carry end caps. | M09: 0 hidden Maple pixels on every wall-adjacent tile |
| L9 | North door | opening **2T**; frame 2T × 3T over the wall band; **at H_w = 3T it is an open archway with no lintel part** (C5) | M09 lintel sweep: 10 px → 8 face-hidden frames, 3 px → 5, archway → 0 |
| L10 | Window | **2T × 2T**, `mount_y_px` = **8** (bottom of the window 8 px above the floor line); exterior north walls only; backdrop through the pane | S4/S6 boards |
| L11 | Depth sort | `zIndex = sortY·8 + priority`. Maple's `sortY` = the **south edge of her feet tile** (not her feet, C4). Objects use footprint south edge + `sort_offset_px`. An occupant uses the object's `sortY`. Priorities: structural 1 < furniture 2 < character 3 < above_occupant 4. Ties go by instance insertion order. | M10: tile rule 0 mismatches vs feet rule 28 |

### C. Renderer, camera, lighting, floors

| # | Value | Locked | Evidence |
|---|---|---|---|
| L13 | Pixel-perfect renderer (device-pixel strategy, C6) | The canvas backing store is the host's device-pixel content box (`devicePixelContentBoxSize`, validated against CSS × DPR, otherwise rounded). The world uses an **integer device zoom Zd**, the camera snaps to whole device pixels, and `devicePixelRatio` is checked on every render. Pixi: `preference: "webgl"`, `resolution: 1`, `autoDensity: false`, `antialias: false`, `roundPixels: true`. Textures: `scaleMode: "nearest"`, `autoGenerateMipmaps: false`. | M02 20/20, M04 8/8, M13 DPR change |
| L14 | Zoom levels | apparent **L1–L4**; `Zd = max(1, ⌊L·DPR + 0.25⌋)`, Zd ∈ [1, 12] | M02, M13 |
| L15 | Camera technical rules | **Overview** = largest L that fits the house, else a DOM room list with Maple's room highlighted. **Follow** = 25 % dead-zone, clamped to the house, output on whole device pixels. **Focus** = largest L ≤ 4 that fits the room. Reduced motion snaps. *The default level per form factor is not locked.* | M13 |
| L16 | Lighting | neutral base → per-room multiply tint over a **non-overlapping partition of the grid** → additive light sprites → emissive drawn after both | M12: 0 overlaps or gaps; emissive exact; 4 draw calls |
| L17 | Floor layout | **≥ 4 variants per material**, chosen by an integer hash of (room, x, y), plus a **16-cell 4-bit edge overlay** (`N1 E2 S4 W8`, 4×4 row-major) | S10 |

### D. Pipeline and budgets

| # | Value | Locked | Evidence |
|---|---|---|---|
| L18 | Atlases | one per `pack`; pages ≤ 512 px (character, fx) or ≤ 1024 px (others); trim with `spriteSourceSize` inside `sourceSize`; **2 px extrusion**; deterministic MaxRects; anchors preserved exactly; output **imported through Vite (content-hashed)**, never `public/` (C2) | M14: 196 frames, 0 mismatches; byte-identical rebuild (Windows) |
| L19 | Loading under the existing CSP | `Assets.init({ preferences: { preferWorkers: false } })`; keep the `pixi.js/unsafe-eval` import; **CSP unchanged** | M18: Pixi default hangs on a refused blob worker |
| L20 | Texture budget | **32 MiB resident**: static packs ≤ 28 MiB (CI check over page sizes), runtime textures ≤ 4 MiB. Budget rule: `max(ceil8(upper bound), ceil8(1.5 × realistic projection))`. | M15, M22 |
| L21 | Performance budgets (rendering-quality acceptance, ADR-0040 §4 item 5) | draw calls per frame **≤ 40**; CPU render p95 **≤ 4 ms** desktop and **≤ 8 ms** in 4×-throttled phone emulation; **0 frames > 33 ms** in 60 s on desktop; 10-minute soak heap growth **< 5 MB** | M16, M17, M19 (measured 4 calls; 2.8 / 4.4 ms; 0; 0.14 MB) |
| L22 | Validator rule set | contract Part E items **E1–E8, E10–E13, E18, E20, E23–E25** are automated. Positive set: 0 false positives. Negatives: 30/30 rejected, including LFS pointers and `filter=lfs` attributes. | M20 |

**Reference conventions only, NOT frozen.** The placeholder catalog geometry of the spike fixtures is a **reference convention** for engine and art work. It covers the footprints, approach and occupy offsets, `sort_offset_px` and slot positions of the bed, writing desk, computer desk, bookshelf, sofa, lamp, plant and rug. It is **not frozen production furniture geometry**. Each production object locks its geometry through `geometry_version` review against the engine catalog (ADR-0036).

## Amendments to accepted RULE items (2026-10-09)

Each amendment replaces accepted RULE text. The contract (`maple-art-production-contract.md`) and `maple-future-architecture.md` are updated to match.

**ADR-0041 AMENDMENT C1: `export-ignore` (§4; contract B.14)**
- **Old rule:** "Raw `art/export` is marked `export-ignore` if the release pipeline packs it into `frontend/dist`."
- **Evidence:** M21. `scripts/build_release.sh` builds from `git archive`. With `export-ignore`, the archive lacks `art/export`, so the atlas build input is missing and the release build fails.
- **Replacement:** `art/export/**` and `art/palette/**` are **never** `export-ignore`. They remain available to `git archive` as release-build input. Raw art (PNG sheets, `meta.json`, palette files) must **not** appear in the final runtime bundle. A bundle-content test proves this: only hashed atlases and the built frontend are in `frontend/dist`.

**ADR-0041 AMENDMENT C2: atlas location (contract B.14)**
- **Old rule:** the pipeline packs into `frontend/public/assets/atlas/<pack>.{png,json}`.
- **Evidence:** M18 and analysis. `static.py` serves `/assets/*` as `immutable`, so unhashed atlases in `public/` would go stale across releases. Vite-imported atlases load as `/assets/<pack>-<n>-<hash>.png`, with the JSON bundled and 0 JSON fetches.
- **Replacement:** generated atlases are build artifacts **imported through Vite** (content-hashed). They are never placed in `public/` and never edited by hand.

**ADR-0041 AMENDMENT C3: frame border vs footprint alignment (contract B.16, E7, B.18)**
- **Old rule:** "Keep a 1 px fully transparent border inside every frame, except floor tiles and wall tiles."
- **Evidence:** the validator found a conflict with B.5. A floor object's lowest front edge lies on the footprint's south edge, which is the canvas edge, so B.16 can only hold on the top edge. M14: trimming and 2 px extrusion round-trip exactly with edge-touching frames, so the pipeline does not need the border.
- **Replacement:**
  - The full 1 px border applies to **character body frames, slot items and fx**.
  - **Floor objects and wall-mounted objects** keep only the **top** row clear; their footprint or mount edges may touch the canvas edge.
  - Floor tiles and structural wall, door, window and backdrop pieces are edge-to-edge.
  - Shadow and light sprites and face overlays carry no border requirement, as applied by the spike validator.

**ADR-0041 AMENDMENT C4: Maple's sort line (contract B.7)**
- **Old rule:** "Maple's sort line is her feet."
- **Evidence:** M10. The feet rule gave 28 mismatches, 8 of them same-row clipping cases. The tile rule gave 0.
- **Replacement:** Maple's sort line is the **south edge of her feet tile** (L11).

**ADR-0041 AMENDMENT C5: lintels (contract B.8, B.19)**
- **Old rule:** wall tops and door lintels are always-front `occluders`; north doors include lintel parts.
- **Evidence:** M09. At H_w = 3T, any lintel crosses a 44 px Maple's face in the doorway (10 px lintel → 8 frames; 3 px → 5).
- **Replacement:**
  - Lintels remain `occluders` parts **where they exist**.
  - **At H_w = 3T, north doors have no lintel part: they are open archways** (owner decision, 2026-10-09).
  - Wall caps remain always-front occluders.

**ADR-0041 AMENDMENT C6: fractional DPR (future-architecture §9.1)**
- **Old rule:** "If DPR is fractional (e.g. 1.25), use `resolution = 1` and integer CSS-pixel zoom."
- **Evidence:** M02. The CSS strategy fails at DPR 1.25 and 1.5 (uneven runs); the device-pixel strategy passes 20/20.
- **Replacement:** the device-pixel strategy (L13, L14).

**ADR-0041 AMENDMENT C7: texture-memory target (future-architecture §9.6)**
- **Old rule:** "target ≤ 48 MiB of GPU textures."
- **Evidence:** M15 and the M22 projection (upper bound 28.3 MiB).
- **Replacement:** **32 MiB** resident (L20).

**ADR-0041 AMENDMENT C8: walk timing (contract B.11)**
- **Old rule:** walk "~150 ms per frame", time-driven.
- **Evidence:** M05. No time-driven 4-frame cycle with continuous motion can meet the foot-slide criterion; a distance lock gives 0 drift.
- **Replacement:** `ms` per walk frame = `ms_per_step / 2`, and the walk phase is locked to route distance (L12).

**Spike-proven clarifications (no accepted rule contradicted):**
- A side or south door is a wall gap whose neighbouring wall tiles carry end caps. This makes B.19's "gap thresholds with frame cap pieces" exact; a single y-sorted side-door sprite failed.
- Atlas page caps of ≤ 512 / ≤ 1024 px sit inside B.18's ≤ 2048 limit.
- The bed occupy offset stays at the contract's −10.

## Still PROVISIONAL, UNDECIDED or DEFERRED

| Value | Status | Resolved by |
|---|---|---|
| P1: face overlay **size** (12×6 vs the 14×8 challenger) | **PROVISIONAL**: 12×6 proposed, technical PASS | Owner S3 blind test (M08) |
| Final face appearance; expression designs; blink | **UNDECIDED** (art direction) | Art chat + blind test |
| Default zoom per form factor (e.g. the default Follow level) | **UNDECIDED** (Q4) | Visual review; must be a passing level L1–L4 |
| Phase tint colours and light strengths | **UNDECIDED** (Q4) | Art direction; must keep Maple's night contrast ≥ 1.5 |
| Production art appearance: Maple's proportions within the canvas, palette, furniture looks, floor materials, cap visual height (≤ 13), door/window styling, backdrops | **UNDECIDED** (art direction) | Art chat; re-enters the validator, boards and budgets |
| Frame counts and timings above the engine minimums | **PROVISIONAL** (contract B.11) | Art delivery |
| Production furniture footprints, collision, approach/occupy and slot coordinates | **PROVISIONAL** (per object) | `geometry_version` review (ADR-0036) |
| Room dimensions; door positions in the final house layout | **UNDECIDED** | Room Final Design Spec (ADR-0035 §7) |
| Real-device mobile acceptance | **DEFERRED** | Real tablet/phone QA at the B14 gate (ADR-0040 §4 item 5), before the default switch |
| Linux atlas reproducibility | **DEFERRED** | R1a CI repeats the deterministic rebuild on Linux |
| `ms_per_step`, turn penalty | **PROVISIONAL tuning** (ADR-0035 §7) | R1a, with the simulation digest |

**Safe to produce now (unchanged, plus the locked values):**
- the style bible;
- Maple concept and turnaround;
- room mood and concept art for all 8 rooms;
- furniture concepts with interaction spots marked;
- lighting and environment references;
- creation archetype concepts;
- placeholder sprites that follow the rule set.

Production sheets at the locked canvas sizes may now be drawn, except the face overlays, which wait for P1.

**Still waits:**
- face pixel dimensions;
- final per-object footprints, collision and interaction/slot coordinates;
- room dimensions and door positions.

### Historical: PROVISIONAL table before the spike (2026-10-08)
For the record, the values that were pending the spike:
- T 16 px;
- Maple frame 32 × 48 px;
- feet anchor (16, 47);
- `FEET_IN_TILE` (8, 13);
- face overlay dimensions;
- frame counts and timings;
- north-wall height, door opening and window size (3T, 2T, 2T × 2T);
- floor autotile layout;
- integer zoom steps (engine range 1×–6×);
- the texture-memory budget.

All except the face overlay size and the frame counts and timings above the engine minimums are now locked (above).

## Deferred
- Production art for the closed placeholder rooms (Creation Room, System Room, Future Space) waits until each room opens (ADR-0040 §2).
- Audio assets (`sfx.*`, `amb.*`, `mus.*`) come with roadmap R6.
- Representation art beyond the archetype concepts (project, library, creation and report objects in use) comes with W2/W3/S5.

## Consequences
- The Art chat can work now without rework risk on any accepted rule.
- Numeric values became binding through the recorded owner decision of 2026-10-09 (Locked values). The values still open bind only through a further owner decision.
- The rule amendments C1–C8 are part of the accepted rule set from 2026-10-09.
- Nothing is implemented. R1a still needs its own authorization.
