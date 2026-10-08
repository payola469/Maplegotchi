# Maple Art Production Contract

> **DRAFT · PROPOSED · FOR HUMAN REVIEW. NOT IMPLEMENTED.**
> - The current renderer is procedural and uses a 1000×600 front-view room (`docs/frontend.md`). This contract describes a *future* asset system.
> - **Accepted rule set (2026-10-08):** the RULE items of this contract, face overlays (B6), art file locations (B7) and the direction vocabulary (B9) are accepted as **ADR-0041** (CLAUDE.md D40). The asset pipeline and art are still **not implemented**.
> - **PROVISIONAL until technical validation** (the art/PixiJS spike; locked values recorded later by an owner decision under ADR-0041):
>   - tile size **16 px**;
>   - Maple frame **32×48**;
>   - sprite feet anchor **(16, 47)**;
>   - `FEET_IN_TILE` **(8, 13)** at T=16 (ADR-0035);
>   - face overlay sizes.

- **Status:** DRAFT for owner review. Values marked **PROVISIONAL** become binding only after the technical spike, through a recorded owner decision under ADR-0041. Values marked **RULE** are accepted (ADR-0041) and binding for production assets now.
- **Date:** 2026-10-08
- **Audience:** the separate Maple Art chat or artist, and the engineers who integrate the assets. The document is self-contained, so you do not need the codebase to use it.
- **Related:** `docs/architecture/maple-future-architecture.md` §6 (Room), §9 (visual architecture), §11 (representations).
- **Out of scope:** art style. The agreed direction is not redesigned here: 3/4 top-down pixel art, *Cozy Digital Home + Personal AI Lab*, a multi-room world, and Maple as a female character in a simple shirt and simple skirt. This contract only fixes **how** assets are made and delivered so they plug into the engine without reinterpretation.

---

## 0. How to use this contract

1. **Concept work (Part A)** can start today. It has no engine constraints beyond perspective and lighting discipline.
2. **Production assets (Part B)** must follow the RULE items now. PROVISIONAL numbers (tile size, frame sizes, frame counts, footprints) may still change, so do not mass-produce final sprites until §D says they are locked.
3. **Every production asset ships with a metadata sidecar (Part C).** The art side fills in the art fields and *proposes* the engine fields. Engineering reviews the engine fields and copies them into the object catalog, which then becomes authoritative.
4. **Run the validation checklist (Part E)** before handing anything over.

### Glossary

| Term | Meaning |
|---|---|
| **px** | One art pixel at 1× scale. This is also the world unit. |
| **T** | Tile size in px. PROVISIONAL: 16. |
| **Footprint** | The floor rectangle an object occupies, in tiles. |
| **Anchor** | The point in a frame that the engine places at a world position. It is a pixel *corner*, not a pixel centre (§B.4). |
| **Part** | A separately drawn piece of one object, such as a bed base and its blanket overlay, so the engine can layer it independently. |
| **Approach point** | The walkable tile where Maple stands to use an object. |
| **Occupy point** | Where Maple's sprite is drawn while she uses the object: sitting, lying. |
| **Slot** | A place on an object where a small item can be displayed, such as a shelf position or desk top. |
| **Orientation** | Which way an object faces: `south`, the default, faces the camera; then `east`, `west`, `north`. |
| **Direction** | Which way a character faces: `down`, `left`, `right`, `up`. |

---

## Part A: Concept art rules

Concept art is free in style within the agreed direction. These rules only prevent choices that production cannot reproduce.

| # | Rule |
|---|---|
| A.1 | **Perspective:** 3/4 top-down oblique with no vanishing points. Floor tiles read as squares. Object fronts (south faces) and tops are both visible. Side faces are seen only as thin edges or not at all. All furniture and rooms use the same viewing angle. |
| A.2 | **Scale reference (PROVISIONAL):** one floor tile ≈ one step for Maple. Maple stands about 3 tiles tall including her head. A door opening is 2 tiles wide. A bed is 2 tiles wide by 3 tiles long. Use these proportions in concepts so production does not need to rescale. |
| A.3 | **Key light** comes from the top-left at about 45°. Self-shading on objects follows it consistently. Do **not** paint night, sunset or lamp glow into object concepts. Show time of day and lighting as separate mood pieces (A.7). |
| A.4 | **Silhouettes must read at 1×.** Check every concept at actual pixel size (for example a 32×48 character) as well as zoomed in. |
| A.5 | **Draw furniture concepts in the `south` orientation first.** Note whether an object needs `east`, `west` or `north` versions, or whether it only ever sits against one wall. |
| A.6 | **Mark interaction spots** on functional furniture concepts: where Maple stands or sits or lies, and which way she faces. Mark display spots too: shelf rows, desk top, wall hooks. |
| A.7 | **Lighting and mood concepts** (day, evening, night, lamp-lit, monitor glow, System Room alert) are references only. In-engine lighting is layered (§B.9), so these show intent, not baked pixels. |
| A.8 | **Maple turnaround:** front (down), back (up), left and right at production scale, plus pose sketches for idle, walk, sit, sleep, read, type/write, observe monitor, think and rest. |
| A.9 | **Palette:** concept art establishes the **master palette** (see B.3). Its exact colours are frozen for production. Prefer 32–64 colours total, with ramps for wood, fabric, skin, hair, metal, screens and plants. |
| A.10 | **No text baked into objects.** Book titles, labels and screen text are not drawn as readable words. The engine shows labels separately in the DOM. Abstract glyph marks are fine. |
| A.11 | **Rooms are modular** (B.19). Concept a room as floor + walls + doors + windows + furniture, not as one painting. A single painting is fine as a mood target, but production rebuilds it from parts. |
| A.12 | **Outside the windows:** "Digital Nature / Quiet City Edge" backdrops are separate wide strips that sit behind window openings. They are not painted inside window frames. |

---

## Part B: Production asset rules

### B.1 Canvas and frame conventions (RULE, sizes PROVISIONAL)

- **One canvas size per asset type.** All frames of one asset share it. Canvas sizes are whole multiples of 8 px. They do not have to be multiples of T.
- **Objects:** canvas width = `footprint_w × T` plus any declared horizontal overhang. Canvas height = `footprint_h × T` + the object's visible height above its footprint.
- **Maple:** every animation uses one canvas size. PROVISIONAL: **32 × 48 px**, for standing, sitting and lying alike.

### B.2 Tile and grid alignment (RULE; T is PROVISIONAL = 16)

- Floor tiles are exactly `T × T`.
- Every object footprint is a whole number of tiles.
- An object's footprint edges coincide with tile edges at its anchor (§B.4).
- No floor-standing object may straddle half tiles. Use the anchor and footprint, not pixel nudging.
- Wall-mounted objects align to wall tile columns horizontally and declare their mount height in px (§C.5).

### B.3 Transparency, colour, palette (RULE)

| Item | Rule |
|---|---|
| Background | fully transparent |
| Transparent pixels | Alpha 0 *and* RGB = 0,0,0. This avoids halos when textures are filtered or packed. |
| Base and part layers | Binary alpha only: 0 or 255. No anti-aliased edges, no soft brushes. |
| Partial alpha | Allowed **only** in `shadow`, `light`, `glass` and `fx` layers, quantised to at most 8 alpha levels. |
| Palette | Base and part layers use **only** master-palette colours. Light and glow layers use palette colours with alpha. |
| Colour space | sRGB with no embedded profile. |
| Pixel size | No mixels. Every pixel is the same size, with no scaled-up or scaled-down sub-art. No rotation by non-90° angles. |

### B.4 Anchor / origin rules (RULE)

An anchor `(ax, ay)` is given in frame pixel coordinates from the frame's top-left. It names a **pixel corner**, so `(16, 47)` is the corner between pixel columns 15|16 and above pixel row 47.

| Asset kind | Anchor means | PROVISIONAL value |
|---|---|---|
| Maple (all frames) | The point between her feet where they meet the floor. Feet contact row = `ay − 1`. | (16, 47) on 32×48 |
| Floor object | South-west corner of the footprint, at floor level | (0, canvas_h), unless the object overhangs to the left |
| Wall-mounted object | Bottom-left of the canvas. The engine places it at the wall column with `mount_y_px` above the floor line. | (0, canvas_h) |
| Slot item (things on shelves and desks) | Bottom-centre contact point | (canvas_w/2, canvas_h) |
| Floor tile | Top-left | (0, 0) |
| Shadow sprite | Its centre on the floor | per sprite |
| Light sprite | Its source centre | per sprite |

Rules that apply to every anchor:
- The anchor is identical across all frames, states and parts of one orientation.
- Animation never moves the anchor. Motion happens inside the frame.

### B.5 Object footprint rules (RULE)

- The footprint is drawn as the object's floor contact area. The object's lowest visible front edge lies on the footprint's south edge.
- **Collision mask:** one character per tile. `#` blocks walking, `.` does not. Most objects block their whole footprint. Rugs and floor decals block nothing.
- Leave **walkable approach tiles outside the footprint.** Maple never walks onto a blocking tile. She walks to an approach tile, then the engine draws her at the occupy point.
- **Rotation:** for `east` and `west` orientations the footprint swaps to `h × w`. Each orientation is its own drawing unless it is declared mirrorable (§B.6).

### B.6 Facing and direction conventions (RULE)

- **Character directions are ordered `down, left, right, up`.** This order is used everywhere: sheet rows, metadata arrays, file lists.
- **Object orientations are ordered `south, east, west, north`.** `south` faces the camera.
- **Two vocabularies by role (B9, ADR-0035):**
  - *character direction* `down/left/right/up` covers Maple's facing, interaction-point facing and sheet rows;
  - *object orientation* `south/east/west/north` covers furniture rotation and catalog metadata.
  - **Fixed mapping:** `down = south`, `up = north`, `left = west`, `right = east`.
  - Never mix them. An interaction point's facing is always a character direction.
- **Mirroring:** `right` may be produced by mirroring `left` only if the metadata declares `"mirror": {"right": "left"}`. For Maple, asymmetric details such as a hair part or a skirt fold are expected, so drawn `right` frames are preferred. Objects may declare mirrored orientations such as `east` from `west`.
- Interaction points state the direction Maple faces while using them (§C.4).

### B.7 Z-order and layer conventions (RULE)

The engine draws these layers, back to front:

| # | Layer | Contents |
|---|---|---|
| 0 | backdrop | outside-window scenery |
| 1 | floor | floor tiles |
| 2 | floor_decals | rugs, mats |
| 3 | walls_back | north walls and anything mounted on them |
| 4 | shadows | shadow sprites |
| 5 | entities | furniture parts, Maple, props; **y-sorted** |
| 6 | occluders | wall tops, door lintels, parts marked `always_front` |
| 7 | darkness | multiply layer, generated by the engine |
| 8 | light | additive light sprites |
| 9 | emissive | screen and LED pixels that stay bright at night |
| 10 | fx | sparkles, reaction icons |
| 11 | editor overlay | grid and editing aids |

How the y-sort in layer 5 works:
- Each part's sort line is the footprint's south edge plus the part's `sort_offset_px`.
- Maple's sort line is her feet.
- Lower on screen means drawn later, so it appears in front.

### B.8 Occlusion rules (RULE)

- When Maple uses an object and part of it must appear **in front of her**, deliver that part separately as `--<part>.png` with `"sort": "above_occupant"`. Examples: a bed blanket, a chair back when she sits facing up, a desk front panel.
- Tall objects such as bookshelves and plants naturally hide Maple when she walks behind them, because of the y-sort. Nothing extra is needed. Optionally set `"fade_when_occluding": true` so the engine fades them.
- Wall tops and door lintels are always in front (`occluders` layer). Deliver them as their own parts.
- Do not draw Maple into furniture art. Occupied states are composited by the engine.

### B.9 Shadows and lighting (RULE)

| Item | Rule |
|---|---|
| Base art lighting | Neutral daylight, key light from the top-left (A.3). Only self-shading inside the object's own pixels. |
| Cast shadows on the floor | Never baked. Use separate `shadow.*` sprites: black with banded alpha. A generic set per footprint is fine, for example `shadow.rect_2x1`, `shadow.rect_3x2`, `shadow.char_small`. |
| Night, evening, room tint | Never baked. The engine's multiply layer handles them. |
| Lamps, windows, monitors | Deliver the glow as a separate `--light` sprite: additive, banded alpha, palette colour. |
| Screens, LEDs, lit windows at night | Deliver as a separate `--emissive` sprite: the exact pixels that must stay bright, binary alpha. |
| Glass | A window pane that shows the backdrop is either alpha 0, or a separate `--glass` part with partial alpha. |
| Ambient occlusion | A 1 px contact darkening at the object base, inside the footprint, is allowed in base art. |

### B.10 State variants (RULE)

- A state is a named visual variant: `default`, `on`/`off`, `open`/`closed`, `calm`/`alert`/`investigating`/`reporting`, `fill_0`…`fill_4`, `draft`/`final`.
- **Every state has the same canvas, anchor and parts as `default`.** If a state needs a different geometry, it is a different asset.
- **Prefer additive overlay parts to whole repaints** when a state only adds something. For example, deliver an empty bookshelf base plus `--books_1` to `--books_4` overlays.
- State names: `[a-z][a-z0-9_]*`. `default` is required.

### B.11 Animation sheet layout (RULE; frame counts PROVISIONAL)

- **One animation per file.**
- **Rows = directions** in the order `down, left, right, up`. If an animation is delivered for only some directions, include only those rows, in that order, and list them in the metadata `rows`.
- **Columns = frames** in playback order, left to right.
- **Cells abut:** no gutters, no outer margin. Sheet size = `frames × cell_w` by `rows × cell_h`.
- Object animations such as monitor flicker or a door opening follow the same layout. Their rows are orientations, in the order `south, east, west, north`.
- **Timing lives in the metadata:** per-frame `ms`, `loop` (`loop | once | pingpong`), and optional `events`, such as a footstep on frames 1 and 3 for future sound.

**Maple animation set.** Frame counts are PROVISIONAL; timing is in the metadata.

| Key | Directions | Frames (prov.) | Notes |
|---|---|---|---|
| `idle` | down, left, right, up | 4 | breathing/blink, ~400–600 ms per frame |
| `walk` | down, left, right, up | 4 | contact–pass–contact–pass, ~150 ms per frame |
| `sit_idle` | down, left, right, up | 2 | seated base pose |
| `sit_write` | up (required), down | 4 | writing at a desk |
| `sit_type` | up (required) | 4 | typing (coding, W4) |
| `sit_monitor` | up (required) | 2 | watching a screen |
| `sit_read` | down (required), left, right | 2 | reading a book on the sofa or an armchair |
| `stand_read` | up (required), down | 2 | at the bookshelf |
| `stand_think` | up (required), down | 2 | at the window or plant |
| `sit_rest` | down (required) | 2 | resting on the sofa |
| `lie_sleep` | up (head toward north; required) | 2 | lying; composited under the bed blanket |
| `react_greet` | down (required), left, right, up | 4, `once` | wave |
| `react_pet` | down (required) | 4, `once` | happy |

- **Fallback chain:** a missing key falls back in a fixed order, for example `sit_type_up → sit_write_up → sit_idle_up → idle_up`. New activities can therefore ship before their art exists.
- **Expressions: face overlays (RULE, B6, ADR-0041).**
  - Maple's **five fixed expressions** (`calm`, `happy`, `curious`, `sleepy`, `focused`) are drawn as **separate face overlay sprites**.
  - **Body animation sheets are not duplicated per expression.** Body frames have a neutral face area.
  - The engine composites the face at a **per-frame face anchor** given in the metadata, so faces stay aligned during head movement, sitting and animation.
  - The `up` (back) direction needs no face. Sleep may use a fixed closed-eye face. Blink may be an optional small overlay animation.
  - The backend decides the expression; the renderer never invents one.
  - **Face pixel dimensions are PROVISIONAL** until the spike verifies readability at the proposed Maple scale.
  - File pattern: `char.maple--face_<expression>.png`, with rows `down, left, right` and an optional blink column.

### B.12 Export format (RULE)

- PNG, 8-bit per channel RGBA, non-interlaced.
- Strip ancillary chunks: no iCCP, gAMA, cHRM or sRGB intent chunks, no text metadata.
- No premultiplied alpha.
- Deliver at **1× only.** Never upscale. The engine scales by integers. *(This replaces an older note in the repository that asked for 2× PNGs.)*
- Maximum single file: 2048 px in either dimension. Maximum single frame: 512 × 512.
- Source `.aseprite` files are **not** delivered into the main repository (B7). They live in the separate private art repository or the deliberate Drive folder (§B.14).

### B.13 Naming convention (RULE)

**Asset ID:** `category.name[.variant]`, matching `^[a-z][a-z0-9_]*\.[a-z0-9_]+(\.[a-z0-9_]+)?$`.

- **Categories:** `char`, `furniture`, `decor`, `creation`, `project`, `library`, `system`, `tile`, `wall`, `door`, `window`, `prop`, `shadow`, `light`, `fx`, `backdrop`, `ui_world`, `sfx`, `amb`, `mus`.
- **Examples:**
  - `char.maple`
  - `furniture.bed_single.oak`
  - `furniture.writing_desk`
  - `furniture.bookshelf_tall`
  - `system.console`
  - `decor.wall_frame_small`
  - `creation.device.a`
  - `tile.floor_wood`
  - `door.north_2w`

**Files:**

| Kind | Pattern |
|---|---|
| Static object or state | `<id>--<state>--<orientation>.png`, e.g. `furniture.bed_single.oak--default--south.png` |
| Part | `<id>--<state>--<orientation>--<part>.png`, e.g. `…--default--south--blanket.png` |
| Light / emissive / glass | as a part, with part name `light`, `emissive` or `glass` |
| Character animation | `<id>--<anim>.png`, e.g. `char.maple--walk.png` |
| Object animation | `<id>--<state>--anim.png`, rows = orientations |
| Tiles | `<id>--sheet.png`, a grid of `T×T` tiles indexed row-major |
| Metadata sidecar | `<id>.meta.json` (one per asset ID) |

Further rules:
- Lowercase only, ASCII only, no spaces.
- `--` separates fields. A single `_` is used inside names.
- **IDs are never reused.** A retired asset keeps its ID, marked `"deprecated": true, "replaced_by": "<id>"`.

### B.14 Directory structure (RULE, B7 / ADR-0041)

**Main Maplegotchi repository**, plain Git with **no LFS**:

```
art/
├── README.md                 (points to this contract)
├── palette/                  production palette definitions only, e.g. maple-master.{png,gpl,hex} — validator/build input (B15)
└── export/                   production-ready PNGs + their meta.json ONLY — the only input to the asset pipeline
    ├── char/maple/           char.maple--idle.png … char.maple.meta.json
    ├── furniture/<id>/       PNGs + <id>.meta.json
    ├── decor/<id>/
    ├── creation/<id>/   project/<id>/   library/<id>/   system/<id>/
    ├── tile/<id>/   wall/<id>/   door/<id>/   window/<id>/
    ├── prop/<id>/   shadow/   light/   fx/   backdrop/<id>/
    └── audio/ (future: sfx/, amb/, mus/)
```

**`art/palette/**` (B15, ADR-0041):**
- plain Git, no LFS;
- production palette definitions used by the art validator and build pipeline, and nothing else;
- not runtime content and not concept or mood-board material;
- excluded from the release bundle unless the build needs it at runtime.

**Outside the main repository**, in a separate private art repository or a deliberate Drive folder:
- `.aseprite` working sources;
- mood boards and concept art;
- visual exploration;
- the style bible and style reference material.

Their history stays separate from runtime and release history.

**Pipeline rules:**
- The build pipeline reads **only** `art/export/**` and packs it into `frontend/public/assets/atlas/<pack>.{png,json}`.
- Generated atlases are build artifacts, **never edited by hand**.
- Raw `art/export` is marked `export-ignore` if the release pipeline packs it into `frontend/dist`.
- **LFS pointer files must never enter production asset inputs.** The validator rejects any non-PNG or pointer file under `art/export/**`.

### B.15 Versioning and compatibility (RULE)

Each `meta.json` carries two numbers:

| Field | Bump it when | What it requires |
|---|---|---|
| `art_revision` | You repaint without changing geometry | Nothing |
| `geometry_version` | **Any** change to canvas size, anchor, footprint, collision, parts list, `sort_offset`, interaction or occupy points, slots, or orientations | Engineering review and a matching update in the engine catalog. CI refuses mismatches. |

- Adding a new **state** or a new **animation key** is additive. Bump `art_revision`.
- Removing a state or key is breaking. Bump `geometry_version`.

### B.16 Padding and safe area (RULE)

- Keep a 1 px fully transparent border inside every frame, except floor tiles and wall tiles, which are edge-to-edge.
- **Maple safe area (PROVISIONAL):** x 2–29, y 1–46 on the 32×48 canvas. Nothing outside it except the reserved transparent rows.
- Bubbles and emote icons are separate `fx` sprites. Do not draw them inside character frames.

### B.17 Pixel-perfect scaling (RULE)

- The engine renders at integer zoom (1×–6×) with nearest-neighbour sampling.
- Art must look right at 1×, 2× and 3×.
- No detail may depend on sub-pixel placement.
- Anything that moves smoothly, such as Maple walking, is rounded to whole pixels at render time. Do not rely on half-pixel offsets between parts.

### B.18 Atlas compatibility (RULE)

- Artists **do not pack atlases.** Deliver individual sheets.
- The pipeline trims transparent space, records offsets so anchors stay exact, adds 2 px edge extrusion, and packs into pages of 2048×2048 or smaller.
- So that trimming and extrusion work, deliveries must follow B.3 (transparent pixels are RGB 0) and B.16 (1 px border).
- Group assets by the room theme they belong to via `pack` in the metadata, for example `bedroom`, `living`, `library`, `studio`, `creation`, `system`, `hall` or `shared`. This keeps per-room loading small.

### B.19 Room and environment assets (RULE; dimensions PROVISIONAL)

| Asset | Delivery |
|---|---|
| Floors | Tileable `T×T` tile sheets, with ≥ 4 variants per material to break repetition. Seams must tile in all four directions. Optional transition or edge tiles in a declared blob/autotile layout, which is locked at the spike. |
| North walls (full face) | Column segments `T` wide × **3T** tall (48 px PROVISIONAL), tileable horizontally. Include left and right ends, inner and outer corners, and a top cap row delivered as an `occluders` part. |
| Side walls (east/west) | Shown as a thin top cap strip (`T` wide segments). No face drawn. |
| South walls | Cutaway: a low top cap or edge only, so the room interior is never hidden. |
| Doors | North-wall door: opening **2T** wide, frame `2T × 3T`, states `closed`/`open` plus an optional 4-frame `anim`. Side and south doors are gap thresholds with frame cap pieces. Lintels are `occluders` parts. |
| Windows | North-wall window `2T × 2T` (PROVISIONAL) at a declared `mount_y_px`, with transparent or `--glass` panes, a `--light` daylight spill sprite and an `--emissive` night-lit variant. |
| Backdrops | Wide horizontal strips, tileable or long, with optional parallax layers (`--far`, `--mid`, `--near`). Day-neutral; the engine tints them. |
| Composite set pieces | Allowed only as **objects** with a footprint (a large fireplace, a server rack wall). Never as a baked full-room image. |

---

## Part C: Engine metadata requirements

Every asset ID ships one `<id>.meta.json`. Fields marked **E** are engine fields: proposed by art, reviewed by engineering, then held authoritatively in the backend object catalog. Fields marked **A** are art fields, authoritative in the art manifest.

### C.1 Common fields

```jsonc
{
  "id": "furniture.writing_desk",          // A+E  (§B.13)
  "art_revision": 1,                        // A
  "geometry_version": 1,                    // A+E  (§B.15)
  "pack": "studio",                         // A    atlas group (§B.18)
  "kind": "floor_object",                   // A+E  floor_object | wall_object | slot_item | tile | character | fx | light | shadow | backdrop
  "canvas": [48, 48],                       // A    frame size in px
  "orientations": ["south"],                // A+E  delivered orientations, order south,east,west,north
  "mirror": {},                             // A    e.g. {"east": "west"}
  "states": ["default"],                    // A+E
  "parts": [ /* §C.2 */ ],                  // A
  "shadow": "shadow.rect_3x2",              // A
  "hit": [[0,16],[48,16],[48,48],[0,48]],   // A    polygon in frame px (fallback: footprint rect)
  "fallback": "placeholder.floor_3x2"       // A
}
```

### C.2 Parts

```jsonc
{"part": "base", "anchor": [0, 48], "sort_offset_px": 0, "layer": "entities"}
{"part": "chair_back", "anchor": [0, 48], "sort": "above_occupant"}
{"part": "light", "anchor": [24, 8], "layer": "light", "blend": "add"}
{"part": "emissive", "anchor": [0, 48], "layer": "emissive"}
```

### C.3 Footprint and collision (E)

```jsonc
"footprint": {"w": 3, "h": 2},               // tiles, for orientation "south"
"blocks": ["###", "###"],                    // one row per tile row, '#' blocks, '.' free
"placement": {"surface": "floor", "against_wall": "north_required|north_optional|none"}
```

### C.4 Interaction points (E)

All coordinates are object-local. `approach` is in tiles relative to the footprint's north-west tile, and may lie outside the footprint. `occupy` is in px relative to the object anchor.

```jsonc
"points": [{
  "id": "chair",
  "approach": {"tx": 1, "ty": 2, "facing": "up"},            // tile Maple walks to
  "occupy":   {"px": [24, -6], "pose": "sit", "direction": "up"}, // where Maple's anchor is drawn while using
  "provides": ["writing_surface", "seat"],
  "capacity": 1
}]
```

### C.5 Slots (E)

```jsonc
"slots": [{"id": "shelf_1", "px": [8, -40], "accepts": ["creation.small", "library.book"], "capacity": 3,
           "spacing_px": 8, "maple_may_place": true}]
// wall objects: "mount_y_px": 28   (height of the anchor above the floor line)
```

### C.6 Animations (A)

```jsonc
"animations": {
  "walk": {"file": "char.maple--walk.png", "rows": ["down","left","right","up"], "frames": 4,
           "ms": [150,150,150,150], "loop": "loop", "events": {"footstep": [0, 2]}}
}
```

### C.7 Capabilities and category (E)

```jsonc
"category": "functional",                   // functional | decorative | creation_display | structural
"capabilities": ["writing_surface", "seat"],
"movable_by": ["owner"], "deletable_by": ["owner"]
```

**Capability vocabulary (initial; additions need review):**
- Rest and sleep: `sleep_spot`, `seat`, `seat_soft`
- Work: `writing_surface`, `computer`, `system_console`
- Reading and books: `reading_spot`, `book_source`, `book_storage`
- Contemplation and nature: `window_view`, `quiet_spot`, `plant`
- Display: `display_wall`, `display_shelf`, `project_board`
- Movement and ambience: `open_floor`, `light_source`, `music_source` (future)

### C.8 Versioning in metadata (A+E)

`geometry_version` must match the catalog entry. Engineering's CI fails if they differ, if any delivered state or orientation lacks frames, or if an animation's sheet size does not equal `frames × canvas_w` by `rows × canvas_h`.

### C.9 Representation link (E, for project, creation and library objects)

```jsonc
"represents": {"entity": "artifact", "kinds": ["program"], "states": ["final"]}
```

This states which domain entities can appear as this object. The engine chooses; art never encodes specific projects.

### C.10 Placeholders (A)

Every asset declares a `fallback`. The pipeline ships generic placeholders: `placeholder.floor_<w>x<h>`, `placeholder.wall_<w>`, `placeholder.slot_item`, `placeholder.char`. A missing frame never breaks rendering.

---

## Part C-bis: Worked examples (PROVISIONAL numbers, T = 16)

### Ex.1 Maple character: `char.maple`

- **Canvas:** 32×48 for every animation. Anchor (16, 47). Feet contact row 46. Safe area x 2–29, y 1–46.
- **Files:**
  - `char.maple--idle.png`: 4 frames × 4 rows, so 128×192.
  - `char.maple--walk.png`: 128×192.
  - `char.maple--sit_write.png`: rows `up, down`, 4 frames, so 128×96.
  - `char.maple--lie_sleep.png`: row `up`, 2 frames, so 64×48.
  - …and the rest of the B.11 set.
- **Meta excerpt:**

```jsonc
{"id": "char.maple", "art_revision": 1, "geometry_version": 1, "pack": "character_maple",
 "kind": "character", "canvas": [32, 48], "anchor": [16, 47], "mirror": {},
 "shadow": "shadow.char_small",
 "animations": {
   "idle": {"file": "char.maple--idle.png", "rows": ["down","left","right","up"], "frames": 4,
            "ms": [500,120,500,400], "loop": "loop"},
   "walk": {"file": "char.maple--walk.png", "rows": ["down","left","right","up"], "frames": 4,
            "ms": [150,150,150,150], "loop": "loop", "events": {"footstep": [0,2]}},
   "lie_sleep": {"file": "char.maple--lie_sleep.png", "rows": ["up"], "frames": 2,
            "ms": [900,900], "loop": "loop"}},
 "fallbacks": {"sit_type": "sit_write", "sit_write": "sit_idle", "sit_idle": "idle",
               "stand_read": "idle", "stand_think": "idle", "sit_read": "sit_idle", "sit_rest": "sit_idle"},
 "faces": {"file_pattern": "char.maple--face_<expression>.png", "rows": ["down","left","right"],
           "expressions": ["calm","happy","curious","sleepy","focused"], "sleep_face": "closed",
           "anchors": "per animation frame, e.g. animations.walk.face_anchor[row][frame] = [x, y]"},  // B6; sizes PROVISIONAL
 "collision": {"tiles": 1}}
```

### Ex.2 Bed: `furniture.bed_single.oak`

- **Footprint:** 2×3 tiles (32×48 floor), placed against the north wall.
- **Canvas:** 32×64. The headboard rises 16 px above the footprint.
- **Parts:**
  - `base`: frame, mattress, pillow.
  - `blanket`: `above_occupant`, covering Maple's body from the chest down.
- **Interaction:** approach on the tile east of the middle row, facing left. Occupy places Maple's anchor at the bed's centre line, `lie_sleep` with her head toward the north.

```jsonc
{"id": "furniture.bed_single.oak", "art_revision": 1, "geometry_version": 1, "pack": "bedroom",
 "kind": "floor_object", "canvas": [32, 64], "orientations": ["south"], "states": ["default"],
 "parts": [{"part": "base", "anchor": [0, 64], "sort_offset_px": 0},
           {"part": "blanket", "anchor": [0, 64], "sort": "above_occupant"}],
 "shadow": "shadow.rect_2x3", "hit": [[0,8],[32,8],[32,64],[0,64]],
 "footprint": {"w": 2, "h": 3}, "blocks": ["##", "##", "##"],
 "placement": {"surface": "floor", "against_wall": "north_required"},
 "points": [{"id": "sleep", "approach": {"tx": 2, "ty": 1, "facing": "left"},
             "occupy": {"px": [16, -10], "pose": "lie", "direction": "up"},
             "provides": ["sleep_spot", "seat_soft"], "capacity": 1}],
 "category": "functional", "capabilities": ["sleep_spot", "seat_soft"],
 "movable_by": ["owner"], "deletable_by": ["owner"], "fallback": "placeholder.floor_2x3"}
```

### Ex.3 Writing desk: `furniture.writing_desk`

- **Footprint:** 3×2 tiles. The desk occupies the north row and the chair sits in the south row.
- **Canvas:** 48×48. Desk items rise 16 px above the footprint.
- **Parts:** `base`; `chair_back` (`above_occupant`, because Maple sits facing up).
- **Slot:** `desktop` holds active-project items.
- **Approach:** tile (1, 2), just south of the footprint, facing up.

```jsonc
{"id": "furniture.writing_desk", "art_revision": 1, "geometry_version": 1, "pack": "studio",
 "kind": "floor_object", "canvas": [48, 48], "orientations": ["south"], "states": ["default"],
 "parts": [{"part": "base", "anchor": [0, 48]}, {"part": "chair_back", "anchor": [0, 48], "sort": "above_occupant"}],
 "footprint": {"w": 3, "h": 2}, "blocks": ["###", "###"],
 "placement": {"surface": "floor", "against_wall": "north_optional"},
 "points": [{"id": "chair", "approach": {"tx": 1, "ty": 2, "facing": "up"},
             "occupy": {"px": [24, -6], "pose": "sit", "direction": "up"},
             "provides": ["writing_surface", "seat"], "capacity": 1}],
 "slots": [{"id": "desktop", "px": [12, -30], "accepts": ["project.active", "creation.small"],
            "capacity": 2, "spacing_px": 14, "maple_may_place": true}],
 "category": "functional", "capabilities": ["writing_surface", "seat"],
 "shadow": "shadow.rect_3x2", "fallback": "placeholder.floor_3x2"}
```

*The Writing Desk and the Computer Desk stay separate assets with different capabilities: a fixed owner decision.*

### Ex.4 Bookshelf: `furniture.bookshelf_tall`

- **Footprint:** 2×1 tiles, against the north wall.
- **Canvas:** 32×64. The shelf rises 48 px above its footprint.
- **States:** `default` is the empty shelf. Fill is shown with **overlay parts** `books_1` to `books_4`; the engine shows N of them, derived from library item count.
- **Approach:** the tile south of each column, facing up (`stand_read`).

```jsonc
{"id": "furniture.bookshelf_tall", "art_revision": 1, "geometry_version": 1, "pack": "library",
 "kind": "floor_object", "canvas": [32, 64], "orientations": ["south"], "states": ["default"],
 "parts": [{"part": "base", "anchor": [0, 64]},
           {"part": "books_1", "anchor": [0, 64]}, {"part": "books_2", "anchor": [0, 64]},
           {"part": "books_3", "anchor": [0, 64]}, {"part": "books_4", "anchor": [0, 64]}],
 "footprint": {"w": 2, "h": 1}, "blocks": ["##"],
 "placement": {"surface": "floor", "against_wall": "north_required"},
 "points": [{"id": "front_l", "approach": {"tx": 0, "ty": 1, "facing": "up"},
             "occupy": null, "provides": ["reading_spot", "book_source"], "capacity": 1},
            {"id": "front_r", "approach": {"tx": 1, "ty": 1, "facing": "up"},
             "occupy": null, "provides": ["reading_spot", "book_source"], "capacity": 1}],
 "category": "functional", "capabilities": ["reading_spot", "book_source", "book_storage"],
 "fade_when_occluding": true, "shadow": "shadow.rect_2x1", "fallback": "placeholder.floor_2x1"}
```

`occupy: null` means Maple stays on the approach tile in the given direction.

### Ex.5 Server console: `system.console` (System Room)

- **Footprint:** 3×2 tiles. Canvas 48×56.
- **States:** `calm`, `alert`, `investigating`, `reporting`. Each has a 4-frame `--emissive` screen animation at 200 ms per frame, plus a `--light` glow.
- **Parts:** `base`; `chair_back` (`above_occupant`).

```jsonc
{"id": "system.console", "art_revision": 1, "geometry_version": 1, "pack": "system",
 "kind": "floor_object", "canvas": [48, 56], "orientations": ["south"],
 "states": ["calm", "alert", "investigating", "reporting"],
 "parts": [{"part": "base", "anchor": [0, 56]},
           {"part": "chair_back", "anchor": [0, 56], "sort": "above_occupant"},
           {"part": "emissive", "anchor": [0, 56], "layer": "emissive",
            "anim": {"frames": 4, "ms": [200,200,200,200], "loop": "loop"}},
           {"part": "light", "anchor": [24, 20], "layer": "light", "blend": "add"}],
 "footprint": {"w": 3, "h": 2}, "blocks": ["###", "###"],
 "points": [{"id": "operator", "approach": {"tx": 1, "ty": 2, "facing": "up"},
             "occupy": {"px": [24, -6], "pose": "sit", "direction": "up"},
             "provides": ["system_console", "computer", "seat"], "capacity": 1}],
 "category": "functional", "capabilities": ["system_console", "computer"],
 "shadow": "shadow.rect_3x2", "fallback": "placeholder.floor_3x2"}
```

File pattern: `system.console--alert--south--emissive.png` is a 4-frame strip in 1 row (rows = orientations).

### Ex.6 Wall decoration: `decor.wall_frame_small`

- **Kind:** `wall_object`, mounted on a north wall.
- **Canvas:** 16×16, anchor (0, 16), `mount_y_px: 28`. No footprint and no collision.
- **States:** `default`, plus an optional `artwork` slot when it displays a creation.

```jsonc
{"id": "decor.wall_frame_small", "art_revision": 1, "geometry_version": 1, "pack": "shared",
 "kind": "wall_object", "canvas": [16, 16], "orientations": ["south"], "states": ["default"],
 "parts": [{"part": "base", "anchor": [0, 16], "layer": "walls_back"}],
 "placement": {"surface": "wall_north", "width_tiles": 1}, "mount_y_px": 28,
 "slots": [{"id": "artwork", "px": [8, -3], "accepts": ["creation.flat"], "capacity": 1, "maple_may_place": true}],
 "category": "creation_display", "capabilities": ["display_wall"],
 "movable_by": ["owner", "maple"], "deletable_by": ["owner"], "fallback": "placeholder.wall_1"}
```

### Ex.7 Project / creation object: `creation.device.a`

- **Kind:** `slot_item`, small enough to sit on shelves or desks.
- **Canvas:** 16×16, anchor (8, 16).
- **Variants** `a`–`d` give palette and shape variety. The engine picks one deterministically per artifact.
- **States:** `final` (displayed) and `archived` (dimmed or dust-covered variant).
- No text is baked into the art. The title comes from the DOM tooltip.

```jsonc
{"id": "creation.device.a", "art_revision": 1, "geometry_version": 1, "pack": "creation",
 "kind": "slot_item", "canvas": [16, 16], "anchor": [8, 16], "states": ["final", "archived"],
 "parts": [{"part": "base", "anchor": [8, 16]}],
 "size_class": "creation.small",
 "represents": {"entity": "artifact", "kinds": ["program"], "states": ["final", "archived"]},
 "fallback": "placeholder.slot_item"}
```

Related archetypes, all following the same rules:

| Archetype | Kind | Size / variants | Represents |
|---|---|---|---|
| `creation.book` | slot_item | | |
| `creation.frame` | wall or slot | `creation.flat` | |
| `creation.plant` | slot_item | | |
| `creation.trophy` | slot_item | | |
| `project.card` | board slot item | 16×16 | planned |
| `project.active_stack` | desk slot item | 16×16 | active |
| `project.box` | shelf slot item | 16×16 | paused |
| `library.book` | | spine variants by kind and status | |
| `system.report_binder` | | | |

---

## Part D: Production readiness

### D.1 SAFE TO PRODUCE NOW

- Visual style bible: palette candidates, ramps, outline and shading rules, key light.
- Maple character concept and turnaround (down/left/right/up), with pose concepts for every B.11 key.
- Room mood and concept art for **all 8 rooms**: Bedroom, Living Room, Library, Work Studio, Creation Room, System Room, Central Hall and Future Space. Concept work may cover all 8 now (B2).
- **Production art follows the phased rollout (B2, ADR-0040).** The 5 open rooms (Central Hall, Bedroom, Living Room, Library, Work Studio), Maple's core set and the face overlays come first. They are required by the default-switch gate. Closed placeholders (Creation Room, System Room, Future Space) need no production art yet.
- Furniture concept art in the `south` orientation, with interaction spots and slots marked (A.6).
- Lighting references: day, evening, night, lamp, monitor glow, System Room alert.
- Environment references: Digital Nature / Quiet City Edge backdrops, materials (wood, fabric, metal, screens, plants).
- Creation and project archetype concepts (B, C-bis Ex.7).
- Placeholder or programmer-art sprites that follow Part B, used for engine development and expected to be replaced.

### D.2 WAIT FOR TECHNICAL LOCK (spike → owner decision under ADR-0041)

- Final sprite-sheet dimensions and canvas sizes (Maple 32×48 is provisional).
- Exact tile size T (16 is provisional).
- Final object footprints and collision masks.
- Final interaction approach and occupy coordinates, and slot coordinates.
- Atlas packing configuration (pipeline-owned in any case).
- Exact frame counts and timings per animation.
- Final door, window and wall dimensions (2T openings and 3T walls are provisional).
- Production export sizes and the final palette freeze.
- Face overlay pixel dimensions and per-frame face anchor values. The *method* is decided: face overlays (B6). Only sizes and readability wait.
- `FEET_IN_TILE` (provisional (8, 13) at T=16; proportional if T changes).
- The floor autotile/blob layout.

**Lock procedure.** The engineering spike renders placeholder assets made per this contract in a PixiJS prototype: integer zoom 2×/3×/4×, y-sort, occupant overlays, multiply and additive lighting, camera modes. The spike validates together T, the Maple frame, the feet anchor, `FEET_IN_TILE`, face readability, grounding near walls, doors and furniture, and depth sorting at 1×–3×. The owner then records the locked values (an owner decision under ADR-0041), which changes the PROVISIONAL items in §F to LOCKED.

---

## Part E: Validation checklist

Run this per delivery. Items marked ⚙ are checked automatically by the asset pipeline once it exists. The others are manual review.

| # | Check | ⚙ |
|---|---|---|
| E1 | File names match §B.13. Each ID has exactly one `meta.json`. | ⚙ |
| E2 | PNG RGBA 8-bit, non-interlaced, no iCCP/gAMA/cHRM/sRGB/text chunks | ⚙ |
| E3 | Every transparent pixel has RGB = 0 | ⚙ |
| E4 | Base and part layers use binary alpha only. Partial alpha appears only in shadow/light/glass/fx, with ≤ 8 levels. | ⚙ |
| E5 | Base and part layers use only master-palette colours | ⚙ |
| E6 | Sheet size = frames × canvas_w by rows × canvas_h. No gutters or margins. | ⚙ |
| E7 | 1 px transparent border in every frame (except tiles). Maple pixels lie inside the safe area. | ⚙ |
| E8 | Anchor is identical across frames, states and parts. It lies inside the canvas. It is the feet point for Maple and the footprint SW corner for floor objects. | ⚙ (consistency) / manual (placement) |
| E9 | Footprint × T is consistent with the visible floor contact. The front edge sits on the footprint's south edge. | manual + ⚙ overlay render |
| E10 | `blocks` has `footprint.h` rows of `footprint.w` characters | ⚙ |
| E11 | Approach tiles lie outside blocking tiles. Occupy pose and direction exist in Maple's animation keys or fallbacks. | ⚙ |
| E12 | Directions and orientations are in canonical order. Mirrors are declared, not implied. | ⚙ |
| E13 | All declared states and orientations have frames. `default` (or the declared base state) exists. | ⚙ |
| E14 | Occupant-covering pieces are separate `above_occupant` parts. Maple is not drawn into furniture. | manual |
| E15 | No baked cast shadows, night tint or glow in base art. Lights and emissives are separate. | manual |
| E16 | Delivered at 1×. No mixels, no non-90° rotation, no anti-aliased edges. | ⚙ (alpha) / manual |
| E17 | No readable text baked in | manual |
| E18 | Frame ≤ 512², file ≤ 2048 px per side | ⚙ |
| E19 | `geometry_version` was bumped if any geometry changed (§B.15) | ⚙ (diff vs previous) |
| E20 | `pack` is set. `fallback` is set. A `hit` polygon is present for interactive objects. | ⚙ |
| E21 | Looks correct at 1×, 2× and 3× in the preview (the spike's viewer) | manual |
| E22 | The tile sheet tiles seamlessly in 4 directions | ⚙ (seam diff) / manual |
| E23 | Animation timing is present (`ms` per frame, `loop`) | ⚙ |
| E24 | Only PNG and `meta.json` files under `art/export/**`; no LFS pointer files; no `.aseprite` or concept files (B7) | ⚙ |
| E25 | Face overlays exist for all five expressions in `down/left/right`; per-frame face anchors present for every body frame that shows a face (B6) | ⚙ |

---

## Part F: Value status table

| Value | Status | Default |
|---|---|---|
| Perspective 3/4 top-down oblique, key light top-left | RULE | — |
| Tile size T | PROVISIONAL | 16 px |
| Maple canvas / anchor | PROVISIONAL | 32×48 / (16, 47) |
| `FEET_IN_TILE` (tile → feet pixel, shared backend/renderer constant) | PROVISIONAL | (8, 13) at T=16; proportional if T changes |
| Direction vocabulary (character `down/left/right/up`, object `south/east/west/north`, fixed mapping) | RULE (B9) | — |
| Art file locations (`art/export/**` plain Git, no LFS; sources/concept outside the repo) | RULE (B7) | — |
| Master palette location (`art/palette/**`, plain Git, no LFS; validator/build input only; not shipped unless needed at runtime) | RULE (B15) | — |
| Direction order `down, left, right, up` | RULE | — |
| Orientation order `south, east, west, north` | RULE | — |
| Sheet layout (rows = directions, columns = frames, no gutters) | RULE | — |
| PNG RGBA, binary alpha on base, RGB 0 on transparent pixels, 1× only | RULE | — |
| Separate shadow / light / emissive / glass / occupant-overlay parts | RULE | — |
| Naming and ID grammar | RULE | — |
| `art_revision` / `geometry_version` semantics | RULE | — |
| North wall height | PROVISIONAL | 3T |
| Door opening | PROVISIONAL | 2T |
| Window size | PROVISIONAL | 2T × 2T |
| Frame counts per animation | PROVISIONAL | §B.11 table |
| Expression method | RULE (B6) | face overlays, per-frame face anchors |
| Face overlay dimensions | PROVISIONAL | set by the spike (readability) |
| Floor autotile layout | PROVISIONAL | not yet set; locked at the spike |
| Atlas page size | RULE (pipeline) | ≤ 2048² |
| Integer-only zoom (no fractional world scaling) | RULE (engine) | — |
| Exact zoom steps | PROVISIONAL | engine range 1×–6×; set by the spike |
| Texture-memory budget | PROVISIONAL | set by the spike |
| Room dimensions, door positions | UNDECIDED | Room Final Design Spec / technical art spike (B15) |
