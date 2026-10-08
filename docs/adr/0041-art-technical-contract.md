# ADR-0041: Art technical contract

- **Status:** Accepted — FIXED design for the **rule set** (CLAUDE.md D40). **NOT IMPLEMENTED** (no asset pipeline or art exists yet). All numeric art values are **PROVISIONAL** until the art/PixiJS technical spike validates them. A follow-up owner decision then records the locked values.
- **Date:** 2026-10-08
- **Decided by:** owner, Maple Room review decisions **B6** (face overlays), **B7** (art file locations), **B9** (direction vocabulary, art side), **B12** (feet in tile, provisional), **B13** (baseline A16), **B15** (master palette location), and **B2** (production art scope).
- **Contract text:** `docs/architecture/maple-art-production-contract.md` (DRAFT / PROPOSED / FOR HUMAN REVIEW; this ADR records which parts are accepted). **Related:** ADR-0035, ADR-0036, ADR-0040.

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
- **Final face pixel dimensions and readability are not locked** until the spike verifies the expressions remain readable at the proposed Maple sprite scale.

### 4. Art file locations (B7)
- **Production exports** stay in the main repository as **plain Git (not LFS)**: `art/export/**`, containing only production-ready PNGs and their `meta.json`.
- The build pipeline reads **only** from `art/export/**`.
- Generated atlases are build artifacts and are **never edited by hand**.
- **Working sources and concept material live outside the main repository**, in a separate private art repository or a deliberate Drive folder. That includes `.aseprite` files, mood boards, concept art, visual exploration and style references.
- Raw `art/export` is marked `export-ignore` if the release pipeline packs it into `frontend/dist`.
- **LFS pointer files must never enter production asset inputs.** The validator rejects them.
- Art source history stays separate from runtime and release history.
- **Master palette (B15):**
  - It lives in `art/palette/**` in the main repository, as **plain Git (no LFS)**.
  - It holds only the production palette definitions used by the art validator and build pipeline.
  - It is not runtime content and not concept or mood-board material.
  - It is excluded from the release bundle unless the build needs it at runtime.
  - `art/export/**` stays reserved for production PNGs and `meta.json`.

### 5. Production scope (B2)
- Concept art may cover all 8 rooms now.
- Production art follows the phased rollout: the 5 open rooms and Maple's core set first (ADR-0040 §4). Placeholder rooms need no production art.

## PROVISIONAL (pending the technical spike)
| Value | Provisional |
|---|---|
| Tile size T | 16 px |
| Maple frame | 32 × 48 px |
| Maple sprite feet anchor | (16, 47) |
| `FEET_IN_TILE` | (8, 13) for T = 16; proportional if T changes (ADR-0035 §6) |
| Face overlay dimensions | not set; validated for readability |
| Frame counts and timings per animation | contract table |
| North-wall height, door opening, window size | 3T, 2T, 2T × 2T |
| Floor autotile layout | not set |
| Integer zoom steps, texture-memory budget | 1×–6× engine range; budget set by the spike |

**The spike validates together:**
- T, the Maple frame, the feet anchor and `FEET_IN_TILE`;
- face readability;
- visual grounding near walls, doors and furniture;
- depth sorting and occupant overlays at 1×–3×;
- integer zoom with fractional device pixel ratios;
- multiply/additive/emissive lighting;
- the camera modes and phone fallback;
- the asset pipeline (trimming with anchors preserved, the validator, same-origin loading under the current CSP, `export-ignore`, rejection of LFS pointers).

**Safe to produce now:** style bible, Maple concept and turnaround, room mood and concept art for all 8 rooms, furniture concepts with interaction spots marked, lighting and environment references, creation archetype concepts, and placeholder sprites that follow the rule set.

**Wait for the lock:** final sheet and canvas sizes, exact T, final footprints and collision, final interaction and slot coordinates, frame counts, door, wall and window dimensions, export sizes, and face pixel dimensions.

## Deferred
- Production art for the closed placeholder rooms (Creation Room, System Room, Future Space) waits until each room opens (ADR-0040 §2).
- Audio assets (`sfx.*`, `amb.*`, `mus.*`) come with roadmap R6.
- Representation art beyond the archetype concepts (project, library, creation and report objects in use) comes with W2/W3/S5.

## Consequences
- The Art chat can work now without rework risk on any accepted rule.
- Numeric values become binding only through a recorded owner decision after the spike.
