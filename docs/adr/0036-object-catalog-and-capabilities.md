# ADR-0036: Object catalog, capability-based interaction, and the backend's geometry ownership

- **Status:** Accepted — FIXED design (CLAUDE.md D35). **NOT IMPLEMENTED.** Implementation is not yet authorized. Footprints, point coordinates and other art-dependent numbers are PROVISIONAL until the technical spike (ADR-0041).
- **Date:** 2026-10-08
- **Decided by:** owner, Maple Room review decision **B13** (baseline A2, A3, A4, A5, A9, A14), as amended by **B9** (facing vocabulary) and **B10** (legacy projection).
- **Extends:** ADR-0027 §1 (interaction points). **Preserves:** D26, the rule that the Writing Desk and the Computer Desk are, and stay, different furniture. **Related:** ADR-0035, ADR-0037, ADR-0039, ADR-0041.

## Context

Today an activity maps to exactly one location (`SPECS[activity].locations[0]`). Furniture geometry exists only in the frontend (`frontend/src/room/layout/anchors.ts`), and the frontend ignores the backend's `pose` and `facing`. The roadmap (R2) forbids hard-coding such as "READ = bookshelf only". It also asks for capability tags, and for new activities to be addable without an architecture rewrite.

## Decision

### 1. The backend owns all geometry (A2)
- Footprints, blocking masks, interaction points, pose and facing come from the backend.
- The new renderer path keeps no duplicated geometry or rule constants. The legacy 1000×600 view keeps its constants only as part of the transitional projection (ADR-0037, ADR-0040).

### 2. Furniture registry: catalog plus instances (A3)
**Object types** live in a release-shipped, root-owned, immutable **catalog** (`maplegotchi/world_catalog/`, loaded by `runtime` and passed to core as frozen data). Each type defines:
- `type` id (never reused);
- `category`: `functional | decorative | creation_display | structural`;
- `geometry_version`;
- `footprint` (tiles at orientation `south`) and a `blocks` mask;
- supported `orientations` (ADR-0035 vocabulary);
- `capabilities`;
- interaction-point templates (§4);
- slot templates (ADR-0039);
- `states`;
- `movable_by` and `deletable_by`;
- placement rules.

**Object instances** live in the layout (ADR-0037). Each instance has: `id` (stable across layout revisions), `type`, `tx`/`ty`, `orientation`, `state`, `owner` (`paolo | maple`) and an optional soft `link`.

**Owner amendment, 2026-10-11 (STEP 97, Option A):** catalog types own default slot templates. A layout instance may explicitly override only `approach` and/or character `facing` per named slot; never infer an override from position or mutate the type. Retain slot identity, accepts, capacity, placement permissions and ownership unless independently authorized by ADR-0039 §2. Validate strict local coordinates/direction, orientation transform, grid/host-room bounds and declared same-host point reuse. Full walkability/collision/reachability/keep-clear remain with R1A-04/05/07. Preserve T5: bedside `top` local `(1,0)`, left; living/library `top` local `(0,1)`, up. No new type or named variant. This is instance layout metadata; type geometry/version is unchanged by an instance override (type template changes still require geometry-version review).

### 3. Capability-based interaction (A4)
- Each activity has **capability requirements** (any-of groups), held in a core table versioned with the activity set.
- Interaction points on placed instances **provide** capabilities.
- **Resolution** is pure core:
  1. Candidates are points whose provided capabilities satisfy a requirement group, whose instance state allows use, and whose capacity is free.
  2. The point must be reachable from Maple (ADR-0035).
  3. Candidates get an integer score from path cost, room-kind affinity, task preference, accepted preferences (ADR-0030) and current-point stickiness.
  4. Ties are broken by the seeded `decision` RNG stream, never by set order.
- **No candidate means the activity is not allowed now.** The Director's `allowed.actions` lists only activities with a reachable candidate.
- **The Writing Desk and the Computer Desk** remain distinct types with disjoint capabilities (D26).
  - **Owner amendment, 2026-10-11 (STEP 95, Option A):** `furniture.writing_desk` capabilities and `desk.writing/chair` provides are exactly `{writing_surface}`; `furniture.computer_desk` capabilities and `desk.computer/operator` provides are exactly `{computer}`. Neither desk nor its interaction point provides `seat`. The `write` requirement is `writing_surface` alone; seating is expressed by the preserved `sit_write` / `sit_monitor` occupy poses, not a shared capability. Approaches, occupy offsets, orientations, directions, footprints, IDs and room layout are unchanged. This reconciles Final Design Spec S15 and T3/T4/T6 without weakening disjointness. Decision and pending Oracle reconciliation: [R1a worklog](../implementation/maple-room-r1a-worklog.md).
- **Adding an activity** needs only: an enum/lookup row (ADR-0037), a requirement row, capabilities on the relevant types, and art keys with fallbacks (ADR-0041). It needs no movement code. Each new activity still needs owner approval: the activity set is FIXED by policy.

### 4. Approach and occupy interaction points (A9, B9)
- `approach` is the walkable tile Maple stands on, plus her **character direction** (`down/left/right/up`).
- `occupy` is optional: a px offset from the object anchor, a pose and a direction for drawing Maple while she uses the object (sitting, lying). `null` means she stays on the approach tile.
- Each point also lists `provides` (capabilities) and `capacity`.
- Point coordinates are object-local and rotate with the orientation.

### 5. Activity vs Task (A5)
- **Activity** is the broad behaviour. **Task** is the real target (`core/tasks.py`). **Furniture** is resolved by capability.
- **A task never names an object instance.** The chosen point is recorded on the decision (`decision.executed_point`, existing).
- Task target namespaces may grow (`library:`, `document:`, `file:`, `project:`, `artifact:`, `inv:`). That growth belongs to the Workspace and System Investigator ADRs, not this one.

### 6. The renderer draws only (A14)
- PixiJS renders tiles, objects, Maple, lighting and the camera.
- It **never** pathfinds, validates, resolves capabilities or chooses destinations.
- Text and controls stay in the DOM (D2 / ADR-0002).
- Collision, slot and validation overlays in Edit Mode are drawn from backend data.

## PROVISIONAL
- All catalog footprints, `blocks` masks, approach/occupy coordinates, slot coordinates and canvas sizes. They depend on T and on the art (ADR-0041).
- The initial capability vocabulary, which may be extended by review: `sleep_spot`, `seat`, `seat_soft`, `writing_surface`, `computer`, `system_console`, `reading_spot`, `book_source`, `book_storage`, `window_view`, `quiet_spot`, `plant`, `display_wall`, `display_shelf`, `project_board`, `open_floor`, `light_source`.
- The scoring weights.

## Deferred
- Stored object state that Maple changes, such as lamps she toggles. For now visual state is derived from day phase, occupancy and domain data.
- Capabilities and targets for Workspace and System Investigator. Only the hooks above exist.

## Consequences
- The roadmap rule "no READ = bookshelf" is enforced structurally. A test asserts that no code path maps an activity directly to an object type.
- New furniture providing an existing capability is used without code changes.
- **Future compatibility:** a future `system_console` in the System Room or a `project_board` in the Work Studio is just another type. Workspace and Investigator tasks express needs as capabilities.
