# Maple Room Technical Art / PixiJS Spike: Official Report (2026-10)

- **Status:** **COMPLETE: all three gates PASS.** The technically proven values are **LOCKED** by owner decision (2026-10-09) and recorded in **ADR-0041 → "Locked values (2026-10-09)"**. The world, renderer and asset pipeline remain **NOT IMPLEMENTED**. **R1a is not authorized.**
- **Date of this report:** 2026-10-09. The spike ran 2026-10-08/09.
- **Spike branch:** `spike/room-art-tech` (from `f4a6d75`), head `9e51663`.
  - All work stayed isolated under `spikes/room-art/**`.
  - The branch is **not merged** and no spike code is copied into production code.
  - `git diff f4a6d75..9e51663 -- . ':!spikes'` is empty.
- **Source evidence** (on the spike branch, paths relative to `spikes/room-art/report/`):
  - `final-report.md`, `gate1.md`, `gate2.md`, `gate3.md`, `proposed-locked-values.md`;
  - `evidence/gate{1,2,3}/*.json`;
  - `boards/gate{1,2}/*.png`.

  This document is the official summary derived from that evidence. The spike branch remains the raw record.
- **Decisions this report feeds:** ADR-0041 (locked values and rule amendments C1–C8), ADR-0035 §6 (`FEET_IN_TILE` and wall grid), ADR-0040 §3–§4 (camera and budgets). The changes are mirrored in `docs/architecture/maple-art-production-contract.md` and `docs/architecture/maple-future-architecture.md` §9.
- **Unchanged:** `docs/roadmap/maple-roadmap.md`, all runtime code, schema and migrations, services, configuration and deployment.

---

## 1. What the spike had to prove

ADR-0041 accepted the art *rule set* but left every numeric art value PROVISIONAL. The spike had to validate these values together:
- T, the Maple frame, the feet anchor and `FEET_IN_TILE`;
- face readability;
- grounding near walls, doors and furniture;
- depth sorting and occupant overlays;
- integer zoom at fractional DPR;
- layered lighting;
- camera modes and the phone fallback;
- the asset pipeline: trim with anchors preserved, the validator, same-origin loading under the current CSP, `export-ignore`, and LFS rejection.

It ran as three gates:

| Gate | Purpose | Verdict |
|---|---|---|
| 1 | Fundamental visual proof: DPR strategy, shimmer, walk cadence, Maple frame, faces, walls and doors, depth, occupy | **PASS (technical)**. Owner readability sign-off is pending (S3 blind test). |
| 2 | Rendering system proof: viewport, lighting, camera, CSP and cache, atlases, floors | **PASS**. Tablet and phone are EMULATED. |
| 3 | Production-readiness evidence: performance, memory, validator, determinism, soak, bundle content | **PASS**. Linux reproduction was not run. |

## 2. Environment and limits of the evidence

- **Machine and browser:** Windows 11; Chrome stable driven by Playwright 1.64; pixi.js **8.21.0**, the same version as `frontend/`.
- **GPU:** Intel UHD Graphics (integrated), ANGLE/D3D11.
- **Real device-pixel ratios:** set with `--force-device-scale-factor` plus a matching context scale. Context emulation alone reports a CSS-sized `devicePixelContentBoxSize`; the viewer guards against that artifact.
- **Art:** placeholder (programmer) art only. Production assets must re-enter the same validator, boards and budgets.
- **EMULATED mobile:** every tablet and phone result is desktop Chrome at a forced DPR inside the product's measured room boxes. **Real-device QA remains required** before the ADR-0040 default switch.
- **Linux:** atlas reproduction on Linux was **not run** (no environment available). R1a CI must repeat it.
- **Backend use:** the unmodified product backend ran **only locally**, on scratch data directories, for M01 (room box) and M18 (production CSP and cache headers). No production data, schema, service or deployment was touched.

## 3. Measurements M01–M22

| ID | Measurement | Result |
|---|---|---|
| M01 | Current room viewport (`.room__canvas`, 5:3) | 806×484 CSS px (1440 wide), 654×392 (820), 348×209 (390); no horizontal scroll |
| M02 | Grid conformance at DPR {1, 1.25, 1.5, 2, 3} × L1–L4 | **Device-pixel strategy 20/20**: 0 foreign pixels, every art pixel an exact Zd×Zd block, feet row exact. **CSS-zoom strategy FAILS** wherever L·DPR is fractional (uneven 2/3 and 3/4/5 px runs at 1.25 and 1.5). |
| M03 | Backing store vs `devicePixelContentBoxSize` | Exact at real DPR (e.g. 1500×1000 at 1.25). The viewer validates the box against CSS × DPR and otherwise falls back to rounding. |
| M04 | Shimmer: walk + Follow, pan, DPR 1–2 | **8/8**: 0 non-integer transforms, 0 body/face offset errors, 0 static drift |
| M05 | Walk cadence | Distance-locked phase, **0 drift**. At 60 Hz: 300 ms/step → 0 px on 11 % of frames, 1 px otherwise; 250 ms/step → 1 px, sometimes 2. The design criterion "foot-slide ≤ 1 px per contact phase" cannot be met by any 4-frame cycle with continuous motion, so it was replaced by "phase locked to distance, 0 drift". |
| M06 | Maple frame | 32×48 canvas: max visible **22×44**, 0 safe-area violations, 56/56 standing frames with feet contact row exactly 46 |
| M07 | Face distinctness (12×6 overlay) | Minimum pairwise difference 5 px after one allowed redraw (was 3); asleep vs sleepy 11 px |
| M08 | Owner blind test of the faces | **PENDING: owner session** (`?scene=s3&L=2`, `&L=3`; `&faces=14` for the 14×8 challenger) |
| M09 | Walls, doors, grounding | 0 hidden Maple pixels on every wall-adjacent tile for FEET y 12, 13 and 14; cap clearance 6/7/8 px. North-door lintel sweep: 10 px → 8 face-hidden frames, 3 px → 5, **open archway → 0**. Side door as a gap with end caps → 0 hidden. Door width: 22 px ≤ 2T − 2 = 30 passes; 1T fails. |
| M10 | Depth ring (same-row and around-object cases) | **Tile-south-edge rule: 0 mismatches.** Contract feet rule: 28 mismatches, including 8 same-row cases where hair or an arm is cut by a neighbouring shelf or desk. |
| M11 | Occupy: bed, writing desk, computer desk, sofa | All PASS. Overlays cover the intended rows and never the face. Bed occupy y −10 (contract value) PASS; −4 put the blanket over her face. |
| M12 | Lighting | Grid-partition tint: 0 overlaps, 0 gaps. Emissive exact (`#9ff0e0`) in all 4 phases. Maple-vs-floor contrast ≥ 1.97 at night (≥ 1.5 required). 4 draw calls. |
| M13 | Camera and responsive | Modes per form factor (§5.3); DOM marker error 0 CSS px; no horizontal scroll; reduced motion snaps; DPR change applied within 1 frame and pixel-perfect after it |
| M14 | Atlases | 196 frames round-trip with **0 mismatches**; 2 px extrusion exact; 6 pages, 0.88 MiB. Two independent generate + pack runs gave byte-identical output (84 art files, 13 atlas files) on Windows. |
| M15 | Texture memory | 0.88 MiB in 8 textures (6 pages + 2 runtime); mipmaps off |
| M16 | Draw calls | 4 per frame in every scenario |
| M17 | Frame time (CPU render p95) | 2.8 ms desktop; 4.1 ms desktop at 4× throttle; 2.1 ms tablet (EMULATED); 4.4 ms phone (EMULATED, 4×); **0 frames > 33 ms** in 43,101 frames. The scene was 1,219 display objects with no culling and no floor baking. |
| M18 | CSP / same-origin / cache under the production headers | Pixi's default (worker) loader: blob worker refused by `script-src 'self'`, **page never ready**. With `preferWorkers: false`: ready in about 0.5 s, 0 CSP violations, hashed `/assets/<pack>-<n>-<hash>.png` served `public, max-age=31536000, immutable`, 0 JSON fetches (atlas JSON bundled by Vite), 0 cross-origin requests. **CSP unchanged.** |
| M19 | 10-minute soak | Heap +0.14 MB after GC; texture and display-object counts stable |
| M20 | Validator | 0 false positives on 29 assets / 83 files; **30/30 negative cases** rejected with the expected rule |
| M21 | Export / bundle content | With `art/export export-ignore`, **the release build fails** (its input is missing from `git archive`). Without it, the runtime bundle holds only hashed atlas PNGs + `index.html`, with 0 raw art, `meta.json` or palette files. `filter=lfs` on art inputs is rejected. |
| M22 | Memory projection (full declared production inventory) | Expected 6.75 MiB; realistic 14.8 MiB; conservative upper bound 28.3 MiB → **budget 32 MiB** |

## 4. Challengers and alternatives

| Challenger | Result | Consequence |
|---|---|---|
| CSS-integer zoom with `resolution = 1` (future-architecture §9.1 as written) | **FAIL** at fractional DPR | Device-pixel backing adopted (C6) |
| Sort Maple by her feet (contract B.7) | **FAIL** (28 mismatches) | Tile-south-edge rule adopted (C4) |
| North-door lintel at 3T walls (10 px and 3 px) | **FAIL** (face hidden in the doorway) | Open archway at 3T (C5). Owner decision V1: keep 3T walls, archways, Maple stays 32×48 |
| FEET y = 12 or 14 | Both pass | The tie keeps 13 |
| 14×8 face overlay | Built; technically not needed | Kept available for the owner blind test |
| Pixi worker-based loader | **FAIL** under the CSP | `preferWorkers: false` (L19) |
| Overlapping per-room tint rectangles | **FAIL** (seams, double multiply) | Grid-partition tint (L16) |
| Single y-sorted side-door sprite | **FAIL** (jamb covers Maple, 7 frames) | Side door = wall gap with end caps on the neighbouring wall tiles |
| Atlases in `frontend/public/assets/atlas/` | Rejected by analysis | Served `immutable` without a content hash → stale across releases; Vite-hashed imports adopted (C2) |
| `art/export export-ignore` | **FAIL** (build input missing) | C1 |
| T = 24, Maple 40×56 | Not needed | No criterion failed at the primary values |

## 5. Results by area

### 5.1 Pixel-perfect rendering (M02–M04)
- **Device-pixel backing store:**
  - the canvas backing equals the host's device-pixel content box (`devicePixelContentBoxSize`), validated against CSS size × DPR and otherwise rounded;
  - the world scale is an **integer device zoom Zd**;
  - camera translation is in whole device pixels;
  - `devicePixelRatio` is re-checked on every render, because emulated DPR changes fire neither ResizeObserver nor `matchMedia`.
- **Renderer settings:** `preference: "webgl"`, `resolution: 1`, `autoDensity: false`, `antialias: false`, `roundPixels: true`. Textures use `scaleMode = "nearest"` and `autoGenerateMipmaps = false`.

### 5.2 Maple, faces, walking (M05–M08, M11)
- Maple canvas 32×48, anchor (16, 47), feet contact row 46, safe area x 2–29 / y 1–46, max visible width 22 px.
- **Face overlays:**
  - each body frame has a top-left integer anchor `face_anchor[row][frame]`; `null` means no face;
  - glasses sit inside the overlay;
  - the fixed sleep face is one cell.
- **12×6 face overlays pass the automated distinctness proxy.** Final face size and appearance wait for the owner blind test (M08).
- **Walk:** 4 frames per 2 steps; the frame index is locked to route distance, not time.

### 5.3 Walls, doors, windows, depth (M09–M10)
- **Walls:**
  - wall height H_w = 3T = 48 px;
  - an east–west (north) wall occupies **3 non-walkable grid rows**, with its face drawn exactly over them;
  - the top cap is an always-front occluder of at most 13 px (8 px used).
  - A north–south (side) wall occupies **1 grid column**, with its top cap y-sorted per tile.
  - The exterior south wall is one cutaway row.
- **Doors:**
  - the opening is 2T;
  - at H_w = 3T, a north door is an **open archway** with no lintel part;
  - a side door is a wall gap whose neighbouring wall tiles carry end caps.
- **Windows:** 2T × 2T, mounted 8 px above the floor line, on exterior north walls only; the backdrop shows through the pane.
- **Depth:**
  - `zIndex = sortY·8 + priority`;
  - Maple's `sortY` is the south edge of her feet tile;
  - an object's `sortY` is its footprint south edge + `sort_offset_px`;
  - an occupant uses the object's `sortY`;
  - priorities: structural 1 < furniture 2 < character 3 < above_occupant 4;
  - ties are broken by instance insertion order.

### 5.4 Camera and zoom (M13)
- **Zoom:** apparent levels **L1–L4**, device zoom `Zd = max(1, ⌊L·DPR + 0.25⌋)`, Zd ∈ [1, 12].
- **Overview** uses the largest L that fits the house. If L1 does not fit, a DOM room list replaces it, with Maple's room highlighted.
- **Follow** uses a 25 % dead-zone, is clamped to the house, and outputs whole device pixels.
- **Focus** uses the largest L ≤ 4 that fits the room.
- **Reduced motion** snaps the camera.
- **Observed defaults on the fixture house** (evidence only; **not locked**):
  - Overview: L1 on desktop; DOM fallback on tablet and phone.
  - Follow: L3 on desktop and tablet; L2 on phone.
  - Focus: L2 on desktop; L1 on tablet and phone.

### 5.5 Lighting (M12)
- **Layer order:** neutral base, then a per-room multiply tint over a **partition of the grid** (no overlapping rectangles), then additive light sprites, then emissive drawn after both.
- **Night contrast** passes. Hair (1.78) and shirt (1.65) sit close to the 1.5 limit, so production phase-tint presets must account for them.

### 5.6 Floors (S10)
- **Variants:** at least 4 per material, chosen by an integer hash of (room, x, y). Frames are identical across reloads, and wood-plank seams are continuous.
- **Edges:** a 16-cell 4-bit edge overlay, bits `N1 E2 S4 W8`, laid out 4×4 row-major.
- **Sampling:** at Zd 1–6, 0 blended pixels.

### 5.7 Pipeline (M14, M18, M20–M22)
- **Atlas layout:** one atlas per pack; pages ≤ 512 px (character, fx) or ≤ 1024 px (others).
- **Packing:** frames are trimmed with `spriteSourceSize` inside `sourceSize`, extruded by 2 px, and packed with a deterministic MaxRects.
- **Loading:** atlases are imported through Vite (content-hashed), never served from `public/`.
- **Pixi configuration:** `Assets.init({ preferences: { preferWorkers: false } })`; the `pixi.js/unsafe-eval` import stays; CSP unchanged.
- **Budgets:** texture budget 32 MiB resident. The validator rules are listed in §6.
- **Raw art** reaches the release *build* through `git archive`, never the runtime bundle.
- **Budget rule** (an engineering refinement): `max(ceil8(upper bound), ceil8(1.5 × realistic projection))`.

### 5.8 Performance (M15–M17, M19)

| Run | DPR | CPU throttle | Zd (L) | CPU render p50 / p95 / max (ms) | Frames > 33 ms |
|---|---|---|---|---|---|
| desktop Follow | 1.25 | 1× | 4 (L3) | 0.7 / 2.8 / 7.1 | 0 |
| desktop Overview | 1.25 | 1× | 1 (L1) | 0.2 / 0.4 / 5.7 | 0 |
| desktop Follow | 1.25 | 4× | 4 (L3) | 2.3 / 4.1 / 9.2 | 0 |
| tablet Follow (EMULATED) | 2 | 2× | 6 (L3) | 1.2 / 2.1 / 6.4 | 0 |
| phone Follow (EMULATED) | 3 | 4× | 6 (L2) | 2.4 / 4.4 / 15.1 | 0 |

Floor baking is not needed: 1,219 unculled sprites render under 3 ms p95. Baking stays a possible R1a optimisation only if real art changes this.

## 6. Locked values (owner decision 2026-10-09)

Recorded authoritatively in **ADR-0041 → "Locked values (2026-10-09)"**. In summary:

| # | Value | Locked |
|---|---|---|
| L1 | Tile size T | 16 px |
| L2 | Maple canvas (every animation) | 32 × 48 |
| L3 | Maple sprite feet anchor | (16, 47) = (W/2, H−1); feet contact row 46 |
| L4 | `FEET_IN_TILE` | (T/2, ⌊13T/16⌋) = (8, 13) at T = 16 |
| L5 | Maple safe area / max visible width | x 2–29, y 1–46 / ≤ 22 px |
| L6 | Face overlay **method** (not size) | per-frame top-left integer `face_anchor[row][frame]`, `null` = no face; glasses inside the overlay; one-cell sleep face |
| L7 | Wall height / cap | H_w = 3T = 48 px; cap ≤ 13 px |
| L8 | Wall grid convention | north (E–W) walls = 3 non-walkable rows; side (N–S) walls = 1 column with per-tile y-sorted caps; exterior south wall = 1 cutaway row; side door = gap with end caps |
| L9 | North door | 2T opening; frame 2T × 3T; **open archway** (no lintel part) at 3T |
| L10 | Window | 2T × 2T, `mount_y_px` = 8, exterior north walls only |
| L11 | Depth sort | tile-south-edge rule (§5.3) |
| L12 | Walk cycle | 4 frames per 2 steps, distance-locked |
| L13 | Pixel-perfect renderer | device-pixel strategy and Pixi settings (§5.1) |
| L14 | Zoom levels | L1–L4, `Zd = max(1, ⌊L·DPR + 0.25⌋)`, Zd ∈ [1, 12] |
| L15 | Camera technical rules | Overview / Follow / Focus rules (§5.4), without the default level per form factor |
| L16 | Lighting | multiply tint over a non-overlapping grid partition; additive; emissive last |
| L17 | Floor layout | ≥ 4 variants per material (integer hash) + 16-cell 4-bit edge overlay |
| L18 | Atlases | per pack, page caps, trim + `spriteSourceSize`, 2 px extrusion, deterministic MaxRects, Vite-imported hashed output |
| L19 | Loading | `preferWorkers: false`, `pixi.js/unsafe-eval` kept, CSP unchanged |
| L20 | Texture budget | 32 MiB resident (static packs ≤ 28 MiB, runtime ≤ 4 MiB) |
| L21 | Performance budgets | ≤ 40 draw calls; CPU render p95 ≤ 4 ms desktop and ≤ 8 ms 4×-throttled phone emulation; 0 frames > 33 ms in 60 s desktop; 10-minute soak heap growth < 5 MB |
| L22 | Validator rule set | E1–E8, E10–E13, E18, E20, E23–E25 automated |

The **placeholder catalog geometry** is reference convention only. It covers the footprints, approach and occupy offsets, and slot positions of the spike fixtures (bed, writing desk, computer desk, bookshelf, sofa, lamp, plant, rug). It is **not** frozen production furniture geometry; production geometry goes through `geometry_version` review (ADR-0036).

## 7. Contract corrections C1–C8 (accepted RULE amendments)

These amend accepted RULE text of ADR-0041 / the art contract. Each one is recorded as an explicit **ADR-0041 amendment (2026-10-09)** with the old rule, the evidence and the replacement.

| # | Old rule | Evidence | Replacement |
|---|---|---|---|
| C1 | ADR-0041 §4 / contract B.14: "Raw `art/export` is marked `export-ignore` if the release pipeline packs it into `frontend/dist`." | M21: with `export-ignore`, `git archive` drops the build input and the release build fails. | Do **not** mark `art/export/**` (or `art/palette/**`) `export-ignore`. They stay in `git archive` as release-*build* input. Raw art never reaches the runtime bundle; a bundle-content test proves it. |
| C2 | Contract B.14: the pipeline "packs it into `frontend/public/assets/atlas/<pack>.{png,json}`". | M18 and analysis: `static.py` serves `/assets/*` `immutable`, so unhashed `public/` atlases go stale across releases. Vite-hashed imports load with 0 JSON fetches. | Generated atlases are build artifacts **imported through Vite** (content-hashed `/assets/<pack>-<n>-<hash>.png`, JSON bundled). Never `public/`. |
| C3 | Contract B.16: "Keep a 1 px fully transparent border inside every frame, except floor tiles and wall tiles." | Validator conflict: B.5 puts a floor object's lowest front edge on the footprint's south edge, which is the canvas edge. M14: trimming and extrusion round-trip exactly with edge-touching frames, so they do not need the border. | The full 1 px border applies to character body frames, slot items and fx. Floor objects and wall-mounted objects keep only the **top** row clear. Floor tiles and structural wall/door/window/backdrop pieces are edge-to-edge. |
| C4 | Contract B.7: "Maple's sort line is her feet." | M10: feet rule 28 mismatches; tile rule 0. | Maple's sort line is the **south edge of her feet tile** (L11). |
| C5 | Contract B.8 / B.19: "Wall tops and door lintels are always in front"; lintels are `occluders` parts of every north door. | M09: any lintel at H_w = 3T crosses a 44 px Maple's face in the doorway (10 px → 8 frames, 3 px → 5). | Lintels remain `occluders` parts *where they exist*; at H_w = 3T north doors have **none** (open archway). Owner decision: keep 3T walls, use archways, do not raise walls to 4T for lintels, do not shorten Maple. |
| C6 | Future-architecture §9.1: "If DPR is fractional (e.g. 1.25), use `resolution = 1` and integer CSS-pixel zoom." | M02: the CSS strategy fails at DPR 1.25 and 1.5; the device strategy passes 20/20. | Device-pixel backing with integer device zoom Zd (L13, L14). |
| C7 | Future-architecture §9.6: memory "target ≤ 48 MiB". | M22 projection, M15. | **32 MiB** resident (L20). |
| C8 | Contract B.11: walk "~150 ms per frame", time-driven. | M05: a time-driven 4-frame cycle cannot meet the foot-slide criterion; a distance lock gives 0 drift. | `ms` per walk frame = `ms_per_step / 2`; the walk phase is locked to route distance. |

**Other spike-proven clarifications.** None of these contradicts an accepted rule:
- Side and south doors are gaps whose neighbouring wall tiles carry the end caps (B.19 "gap thresholds with frame cap pieces", made exact).
- Atlas pages are capped at ≤ 512 (character, fx) and ≤ 1024 (others), inside the B.18 ≤ 2048 limit.
- Textures use nearest sampling with no mipmaps.
- E24 also rejects a `filter=lfs` attribute on art inputs.
- The bed occupy offset stays at the contract's −10.

## 8. Still open (not locked by this report)

| Item | Status | Next step |
|---|---|---|
| V1: walls and doors | **RESOLVED** (owner, 2026-10-09) | 3T walls; open archway north doors; no 4T walls for lintels; Maple not shortened and stays 32×48 |
| Face overlay size (12×6 vs 14×8) | **PROVISIONAL** (12×6 proposed) | Owner blind test M08 |
| Final face appearance | **UNDECIDED** (art direction) | Art chat + blind test |
| Default Follow zoom per form factor | **UNDECIDED** (Q4) | Visual review |
| Phase tint colours and light strengths | **UNDECIDED** (Q4; night contrast margin noted) | Art direction |
| Production art appearance | **UNDECIDED** (art direction) | Art chat; validator + boards + budgets |
| Room dimensions | **UNDECIDED** | Room Final Design Spec |
| Door positions in the final house layout | **UNDECIDED** | Room Final Design Spec |
| Real-device mobile acceptance | **DEFERRED** to the B14 gate (ADR-0040 §4 item 5), before the default switch | Real tablet and phone QA |
| Linux atlas reproducibility | **DEFERRED** to R1a CI | Repeat M14 reproduction on Linux |
| `ms_per_step` (250 vs 300 ms), turn penalty | **PROVISIONAL tuning** (ADR-0035 §7) | Set in R1a with the simulation digest |
| Optional taller phone room box | **UNDECIDED** (R1a layout) | — |

## 9. Regression proof (spike branch)

The unchanged `scripts/check.sh` on `spike/room-art-tech` exits 0:
- backend: 1432 passed, 3 skipped;
- companion/discord: 22 passed;
- companion/brain: 28 passed;
- frontend: 204 tests passed, plus lint, typecheck and build.

One earlier run hit a known Windows socket abort in `companion/brain` (WinError 10053). That test passed 5/5 in isolation and in the full re-run.

## 10. Follow-up when R1a is authorized (not authorized by this report)

- `scripts/build_release.sh` adds `art/export` and `art/palette` to its `git archive` path list (C1), and a bundle-content test asserts no raw art in `frontend/dist`.
- R1a CI repeats the deterministic atlas reproduction on Linux.
- Production art re-enters the validator, boards and budgets.
