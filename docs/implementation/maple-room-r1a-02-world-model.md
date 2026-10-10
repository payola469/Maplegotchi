# R1A-02 — Canonical World Model and Final House Geometry

**Status:** REVIEW / PENDING FINAL OWNER ACCEPTANCE — Checkpoints 1–6 implemented and focused validation complete (STEP 90). Checkpoints 4–6 are uncommitted; no commit, push, merge or deployment authorized. Checkpoint 3 owner accepted and committed/pushed as `06295b65a2f8c79825b154249cf6e7869f66e9cb` (STEP 89). R1A-02 is not DONE before acceptance and repository integration.
**Date:** 2026-10-10 (+07), STEP 78.
**Workspace:** `/Users/paolo_cu/GitHub Desktop/Maplegotchi-r1a-02-world-model`
**Branch / starting HEAD:** `feat/r1a-02-world-model` / `a754efc9cd35f66e15efb8707dc9b4066d5ab54d`.

## Goal, dependencies and authority

Produce an isolated, pure-domain representation of the approved initial house,
with derived structure, topology and lighting ownership, validated before use.
This document defines the implementation breakdown. STEP 90 authorizes Checkpoints 4–6 sequentially: lighting/mount predicates, initial-house release data/isolated reader and consolidated evidence. The implementation remains isolated; production activation, commit/push/merge and later workstreams are not authorized.
R1A-01 is DONE / OWNER ACCEPTED / MERGED through [PR #1](https://github.com/payola469/Maplegotchi/pull/1)
into `v0.2-development` at the starting HEAD above. Its two acknowledged evidence
limitations remain: run `38062574000` validates `26aed831…`, not a separate original-base
CI execution; complete raw baseline Docker gate details are unavailable.

Binding source order: locked ADR values → accepted ADR rules → Final Design Spec
→ proposed documents. Read together:

- [CLAUDE.md](../../CLAUDE.md), architecture boundaries and pure-core coding rules.
- [Master Plan](maple-room-r1a-plan.md), R1A-02 and §§4, 7, 8.
- [Final Design Spec](../architecture/maple-room-final-design-spec.md), conventions,
  §§A–D, I, P, S, T1/T2 and O1.
- [ADR-0035](../adr/0035-world-model.md), §§1–6; geometry as data, global grid,
  topology, direction vocabulary and feet definition.
- [ADR-0036](../adr/0036-object-catalog-and-capabilities.md), backend ownership and
  runtime-loaded frozen catalog data boundary.
- [ADR-0041](../adr/0041-art-technical-contract.md), L1/L4/L7–L10/L16 and C5.
- [R1A-01 harness](../../backend/tests/world/README.md), immutable Oracle,
  test-only approved snapshot, deterministic mutation conventions and contracts.

Historical “not authorized”/“undecided” text in older sources does not override
later owner authorization or ADR-0035 §7's explicit delegation of house sizes and
door positions to the Final Design Spec. No locked geometry conflict was found
within R1A-02. Do not edit accepted sources or the Oracle to fit implementation.

## Scope and non-goals

In scope: integer tiles and rectangles; eight region identities/kinds/statuses;
L8 structural cells and ownership; seven north–south archways with door states;
derived open-door graph; direction vocabulary alongside legacy values; one shared
feet formula; backend lighting partition; T1/T2 initial data; S1–S4, S7 band-side
predicates and S12 validation.

Out of scope: furniture/types/instances/capabilities/slots (R1A-03/06/07), object
collision and recovery (04), A* and timing (05/17), persistence/migrations (08),
legacy position projection (09), API/DTO/renderer integration (10–15), art, lighting
colours/intensities, side doors, non-rectangular rooms, opening placeholders in
production, and production state/default-view changes. No new dependency is planned.
The 431 walkable-tile and T6 routing assertions require objects/pathing and are
not R1A-02 completion claims. No later workstream starts under this plan.

## Pure-domain model and proposed modules

Mandatory architecture: `core/world/` owns pure values, derivation and validation;
it never imports runtime, storage, API, sensors, catalog or tests, and never reads
files, time, environment or random state. Backend owns canonical geometry.
Runtime alone may read release-shipped declarative data and pass frozen values to
core. The test Oracle is an independent expectation, never production input.

The following filenames and type names are **proposals**, not accepted architecture
requirements:

| Proposed location | Responsibility / boundary |
|---|---|
| `backend/src/maplegotchi/core/world/model.py` | Frozen Tile, Rect, Region, Door, House values; closed vocabularies and immutable ordered collections; no loader or mutable defaults. |
| `core/world/geometry.py` under the same package | Floor/band/side/cutaway cells, passage ownership, tile classification and room derivation. |
| `core/world/topology.py` | Deterministic graph derived from validated open doors; no authored edge list or pathfinder. |
| `core/world/validation.py` | Pure geometry diagnostics with S-rule/entity/tile context; reject invalid values before use. |
| `core/world/directions.py` and `coordinates.py` | Character/object vocabulary mapping, legacy-facing adapter and single T/FEET formula. |
| `backend/src/maplegotchi/world_catalog/initial_house.json` | Proposed release-shipped declarative T1/T2/lighting data, separate from object catalog work; no Python behavior. |
| `backend/src/maplegotchi/runtime/world_layout.py` | Proposed narrow read/parse/freeze/validate boundary, callable only in isolated tests/development until later integration; no app startup/life-loop wiring. |
| New `backend/tests/world/test_geometry.py`, `test_topology.py`, `test_layout_data.py` | Proposed positive/negative model, data and Oracle comparison tests. Existing Oracle/Harness/snapshot remain unchanged. |
| `docs/architecture.md`, checklist and worklog | Record actual implementation/evidence at checkpoints. |

Confirm these names at implementation review. An isolated layout reader is not an
object catalog loader or production activation. Verify resource packaging when
choosing JSON; do not add release/dependency changes implicitly. If another data
placement is required, preserve runtime-only loading and do not put initial-house
literals in geometry algorithms. Validation should separate generic geometric
invariants from exact initial-house T1/T2 equality in tests.

## Coordinates, rectangles and regions

Tiles `(tx, ty)` have north-west origin; x increases east, y south. Grid dimensions
are exactly 44×26 (704×416 world px at locked T=16). Valid cells have `0 ≤ tx < 44`,
`0 ≤ ty < 26`. Reject non-integer coordinates and non-positive rectangle extents;
no rounding, clipping or wraparound. Proposed internal rectangle iteration is
half-open `[x,x+w) × [y,y+h)`; source endpoint ranges remain inclusive. Conversion
must be explicit and tested at all boundaries.

T1 defines floor rectangles, not wall-inclusive room boxes:

| id / kind | (x,y,w,h) | Floor count | Status |
|---|---|---|---|
| bedroom / bedroom | (1,3,8,7) | 56 | open |
| living_room / living | (10,3,10,7) | 70 | open |
| library / library | (21,3,10,7) | 70 | open |
| work_studio / studio | (32,3,11,7) | 77 | open |
| central_hall / hall | (1,13,42,4) | 168 | open |
| future_space / future | (1,20,13,5) | 65 | closed |
| creation_room / creation | (15,20,14,5) | 70 | closed |
| system_room / system | (30,20,13,5) | 65 | closed |

Derive room from the tile; do not add stored room state. Distinguish floor/passage
room membership from structural lighting ownership: a wall is not a floor tile.
Door passages belong to the southern room. A wall-only tile lookup must report
its structural classification, not silently return a walkable floor. Closed floor
geometry still exists; geometry membership does not imply permission to enter.

## L8 wall derivation and ownership

For a floor `(x,y,w,h)`, the north band occupies inclusive x `x−1 … x+w` and
rows `y−3 … y−1`; side columns are `x−1` and `x+w` alongside the floor rows.
A shared vertical boundary is one physical side column, not duplicate wall cells.
Overlapping north-band corner cells are one structural cell. Track ownership
separately from physical-cell union so valid shared walls are not rejected as
floor overlap. Floors must not intersect derived structural cells.

Initial rows: north exterior band 0–2; north floors 3–9; Hall band 10–12;
Hall floor 13–16; southern bands 17–19; southern floors 20–24; exterior south
cutaway 25. Side columns: north tier 0/9/20/31/43, Hall 0/43, south tier
0/14/29/43. Derive these from the regions rather than author a second wall map.
Only the lowest tier has the exterior one-row south cutaway, across the house;
never add cutaway rows at interior south boundaries. No outside margin.

Bands shared vertically belong to the southern room. Structural side-wall
lighting ownership is westward, except exterior west wall ownership is eastward;
south cutaway ownership is northward (§P). L8's 3T wall faces, ≤13 px cap and
no-lintel archways are retained as contract constraints; drawing is deferred.

## Doors, passage cells and topology

T2 endpoints below are inclusive. Each door covers exactly 2 columns × 3 rows,
inside one southern-room north band, with floor immediately above and below
across both columns. Adjacency is through that band, not direct contact between
floor rectangles. Reject self-links, missing IDs, wrong north/south assignment,
non-adjacent rooms, out-of-band ranges, wrong width/height, and overlapping
passage definitions. No side-door support is introduced.

| Door suffix (`door.` prefix) | north → south | x range | y range | State |
|---|---|---|---|---|
| hall_bedroom | bedroom → central_hall | 5–6 | 10–12 | open |
| hall_living | living_room → central_hall | 15–16 | 10–12 | open |
| hall_library | library → central_hall | 25–26 | 10–12 | open |
| hall_studio | work_studio → central_hall | 36–37 | 10–12 | open |
| hall_future | central_hall → future_space | 6–7 | 17–19 | closed |
| hall_creation | central_hall → creation_room | 21–22 | 17–19 | closed |
| hall_system | central_hall → system_room | 36–37 | 17–19 | closed |

Keep underlying band geometry distinct from door carving/state. Passage ownership
is southern for both states; closed passages are not thereby traversable. R1A-04
will combine open floors/passages with object masks. This item does not implement
object walkability, keep-clear collision checks, movement or recovery.

Derive an undirected graph from open doors, with deterministic room/neighbor order.
Initial result: 8 room nodes, 4 open edges connecting Hall to the four north rooms;
three closed placeholders have no open edges. Validate all five open rooms belong
to one connected component (S4); closed rooms are exempt from connectivity. Never
persist or independently author graph edges. Synthetic geometry tests may change
a valid door/room state to check derivation; they do not open production rooms.

## Directions and shared feet definition

Character order is `down, left, right, up`; object orientation order is
`south, east, west, north`. Fixed mapping: down↔south, up↔north, left↔west,
right↔east. Preserve legacy `Facing` values `front/back/left/right`; front→down,
back→up, left/right unchanged. Prefer a pure adapter and separate new vocabulary
to widening an existing API enum in this item. API serialization, legacy anchors,
existing poses and movement remain unchanged. Retirement of front/back is later.

Define T=16 once in the new world domain and derive the shared
`FEET_IN_TILE = (T/2, floor(13*T/16)) = (8,13)` with exact arithmetic. Proposed
pure tile-to-feet conversion: `(tx*T + 8, ty*T + 13)`, consuming that definition,
not copied literals. Store tile coordinates only. Sprite anchor `(16,47)` and
south-edge depth sorting are distinct concepts. No renderer/frontend constant is
added here: the later API/renderer consumes backend-owned values without a second
rule definition. Route interpolation and renderer wiring remain deferred.

## Backend-owned lighting and band predicates

Spec §P provides eight zone rectangles (inclusive endpoints):

| Zone | x | y |
|---|---|---|
| bedroom | 0–9 | 0–9 |
| living_room | 10–20 | 0–9 |
| library | 21–31 | 0–9 |
| work_studio | 32–43 | 0–9 |
| central_hall | 0–43 | 10–16 |
| future_space | 0–14 | 17–25 |
| creation_room | 15–29 | 17–25 |
| system_room | 30–43 | 17–25 |

They cover all 1,144 cells exactly once, including walls, doors and closed rooms.
Compare the input rectangles with T1's `lighting_zone`, and independently test
ownership against §P. S12 must count memberships per cell, not just sum areas;
one overlap plus one gap could preserve total area. Geometry stays backend-owned;
no renderer recomputation, tint choices, emitters or appearance implementation.

S7 band-side support is a pure predicate over derived structure: proposed wall
mount cells must be plain north-band cells, excluding door columns; proposed
window mounts must be on exterior north bands only (rows 0–2). Reject Hall and
placeholder window bands; O1 remains interior/windowless. Predicates accept
geometry values for tests, not object instances or catalog behavior. Full object
mount validation is R1A-03. No window instances are introduced here.

## Initial-house data and validation gates

Transcribe runtime T1/T2 data independently from the binding spec, preserving IDs,
kinds, coordinates, statuses and zone ranges. Never read Markdown or
`approved_tables.json` from application code, and never generate production data
by importing the Oracle. Test-side serialization of loaded frozen values must
compare every T1/T2 header/cell/row in approved order, including derived floor
counts. A geometry validator passing does not waive exact initial-house equality.

| Rule | Required positive evidence | Required negative evidence |
|---|---|---|
| S1 | Exact grid; 8 floors with T1 areas and IDs; deterministic boundary inclusion. | Wrong grid, outside/overlapping rectangles, zero/negative extent, duplicate IDs, malformed numeric/state/kind input. |
| S2 | Exact row bands/side columns/cutaway, shared-cell union and structural ownership; every cell is floor, structure or passage. | Two-/four-row band, extra interior cutaway, missing side column, floor/structure collision; where walls are derived, use independent expected-cell assertions to detect bad derivation rather than accept invalid wall input. |
| S3 | All 7 T2 doors; 6 cells each; north/south floor adjacency; southern ownership. | Width 1/3, wrong height, off-band placement, swapped/non-adjacent endpoints, self/missing references, overlapping passages. |
| S4 | Four-edge star and five connected open rooms; isolated closed nodes allowed. | Close/remove a north connection leaving an open room disconnected; disconnected open-room fixture. |
| S7 band side | Plain exterior band window accepted; plain interior band non-window mount accepted. | Window on interior band, mount on floor/side/cutaway, any mount on door column. |
| S12 | Exactly one membership for each of 1,144 cells; §P ownership and T1 zone equality. | Gap, overlap, out-of-grid zone, duplicate/missing zone; overlap-plus-gap with unchanged total area. |

Add direct tests for all direction mappings/order, invalid vocabulary, legacy
round-trip mappings, feet formula and boundary-tile pixel conversion. Verify frozen
inputs remain unchanged after derivation/validation. Use deterministic ordered
mutations from the existing harness conventions; no production RNG or database.
Proposed diagnostics identify S-rule plus entity/cell, without private state.

## Implementation sequence and checkpoints (after authorization)

1. **Model and contract checkpoint:** agree proposed module/data boundaries; add
   frozen types, coordinate/rectangle primitives, new vocabularies and feet mapping.
   Focused tests cover valid/invalid values and immutability. Existing legacy/API
   outputs unchanged; no runtime wiring.
2. **Structural checkpoint:** derive floor cells, bands, shared side columns and
   exterior cutaway from region values. Add independent edge/corner/ownership tests
   and S1/S2 validation. No object geometry or pathfinder.
3. **Topology checkpoint:** validate doors against the single band and adjacent
   floors; derive southern passages and open-door graph. Positive/negative S3/S4
   tests and deterministic adjacency order.
4. **Lighting / mount checkpoint:** derive/expose zone ownership and geometry-only
   band predicates; positive/negative S7/S12 cases, exhaustive per-cell partition.
5. **Initial data / Oracle checkpoint:** add declarative T1/T2 data and narrow
   isolated runtime read/freeze/validate path; verify packaging, exact approved
   Oracle equality and all explicit acceptance targets. Keep existing Oracle,
   snapshot and Harness unchanged; extend through new tests only.
6. **Review/evidence checkpoint:** run focused world tests and affected Ruff/mypy,
   existing import/AST boundaries, and relevant legacy regression checks as justified
   by actual edits. Record commands/results/platform, diff scope and zero Oracle
   differences. Preserve the existing simulation pin; do not rerun a full gate
   automatically. Owner review precedes commit/merge under existing policy.

Checkpoint failures stop progression; a needed SPEC/accepted/locked change invokes
Master Plan §8: document conflict, mark blocked, propose amendment, obtain owner
approval, update accepted sources, then resume. Do not fix tests by changing the
Oracle, spec or accepted ADR. No stage is executed in STEP 78.

## Checkpoint 1 evidence (STEP 81, 2026-10-10)

Implemented in `core/world/coordinates.py`, `model.py` and `directions.py`:
frozen, slotted Tile/Rect/Region values; RegionKind/RegionStatus; CharacterDirection
and ObjectOrientation; strict legacy Facing adapters; T=16, grid 44×26 and one
`FEET_IN_TILE = (T // 2, (13 * T) // 16)` definition. Rectangles use half-open
ranges and reject invalid extents; coordinates reject non-integers (including
booleans) and out-of-grid values. No initial-house data or structural geometry
is introduced. The proposed module boundaries are adopted for these values only;
Door/House types remain deferred until their dependent checkpoints.

Validation: **65 new tests**, **24 existing world contract tests** and **3 existing
core/security boundary tests**, **92 passed** total. Ruff lint/format and strict
targeted mypy (5 files) pass; all **10 import contracts kept, 0 broken**.
Checkpoint 1 completion criteria are met pending review. Legacy Facing and live
outputs are unchanged; production has no imports of these new modules. Existing
Oracle, Harness, snapshot and simulation pin are unchanged; no full gate rerun.
Checkpoints 2–6 have not begun and require separate owner authorization.

## Checkpoint 2 evidence (STEP 84, 2026-10-10)

`geometry.py` derives an immutable row-major Structure of StructuralCell values
from region floors. TileKind distinguishes floor, north band, side wall and south
cutaway, without access/walkability semantics. Bands have exactly three rows and
span inclusive x−1 through x+w; side columns span the half-open floor y range.
The one-row cutaway is derived only beneath the lowest tier and must occupy the
exterior last row. Shared walls/corners are deduplicated; bands follow the southern
floor, side/corner ownership is westward (eastward at the west exterior), and
cutaway ownership is northward. No lighting-zone data or logic is introduced.

`validation.py` enforces applicable S1: fixed 44×26 grid, nonempty valid region
values, unique IDs and disjoint floors; Checkpoint 1 Rect bounds remain unchanged.
S2 derivation rejects out-of-grid walls, floor/wall or incompatible wall-kind
collisions, misaligned shared bands, an interior cutaway and uncovered grid cells.
Walls are derived, never accepted as separately authored input. Exact eight-region
T1 identities/areas and approved house/Oracle comparisons remain Checkpoint 5;
doors, passages and graph remain Checkpoint 3.

**130 tests passed:** 38 new structural cases + 65 Checkpoint 1 cases + 24 existing
world contract cases + 3 existing security boundary cases. Synthetic layouts
exercise independent exact cell sets, all 1,144 cells of a mixed-width three-tier
layout, bounds/corners, deduplication/ownership, immutable/order-independent
results and deterministic rejection diagnostics. No T1/T2 runtime data is added.
Ruff lint/format PASS; strict targeted mypy PASS (7 files); import contracts
**10 kept / 0 broken**. One initial negative test expected a later collision
diagnostic; it was corrected to the first uncovered-cell diagnostic, retaining
the invalid fixture and rejection requirement. No production wiring, Oracle,
Harness, snapshot, simulation pin, API, schema or renderer changes. Checkpoint 2
is ready for review; Checkpoints 3–6 have not begun.

## Checkpoint 3 evidence (STEP 87, 2026-10-10)

`model.py` adds frozen Door/DoorState values: named north/south regions, a
grid-contained Rect of exactly 2×3 cells, open/closed state and explicit rejection
of malformed values or self-links. Existing Checkpoint 1 types are unchanged.
`topology.py` derives frozen Passage, RoomNode and Topology values, independently
revalidating S1/S2 structure before checking S3. Door IDs must be unique; named
rooms must exist with floor immediately north/south across both columns. Every
passage cell must be in the southern room's north band; overlaps are rejected
in either state. Passage cells remain southern-owned in both states and are
separate from the uncarved structure. No tile walkability permission is inferred.

Graph nodes, neighbor lists and passages have canonical ID order; only open
doors add undirected edges, and repeated neighbors are deduplicated. S4 requires
connectivity among open rooms; closed rooms remain represented but cannot bridge
that component (consistent with their inaccessibility, spec S5 / ADR-0035 §2).
Closed rooms are exempt from connectivity; a single open room needs no edge.
No topology edges are authored independently or persisted.

**182 distinct focused cases passed, 0 failed:** 52 new topology + 65 Checkpoint 1
+ 38 Checkpoint 2 + 24 contract + 3 security cases. The initial combined run
passed 179 cases; after three extra topology cases and test-only regex lint fixes,
the final topology-only run passed 52 cases, reusing the unaffected 130 passes.
Tests cover valid edge openings, six-cell passages, ownership/state, invalid
dimensions/locations/endpoints, missing/duplicate IDs, overlaps, nonadjacent and
straddled rooms, closed-edge disconnection, transitive connectivity, closed-room
exemption, deterministic failures and deeply immutable/order-independent results.
Ruff lint/format PASS; strict targeted mypy PASS (8 files); import contracts
**10 kept / 0 broken**. Full commands and final scope are in the worklog.

No complete initial-house data or final-house Oracle equality is introduced.
No lighting/mount predicates, tile pathfinder/walkability engine, API, persistence,
renderer or production wiring is added. Checkpoint 3 is ready for acceptance
review; Checkpoints 4–6 have not begun.

## Consolidated Checkpoints 4–6 evidence (STEP 90)

- **Checkpoint 4 PASS:** `lighting.py` provides frozen LightingZone and
  LightingPartition values, deterministic per-tile ownership and S12 rejection of
  missing/duplicate/unknown zones, gaps, overlaps and wrong ownership. Rect
  enforces bounds. Every cell must have exactly one zone matching floor,
  structural or southern passage ownership, including closed areas. `can_mount`
  is S7 geometry only: plain north band, no passage cells in either state;
  windows additionally require exterior rows 0–2. No appearance or catalog logic.
  Gate: **39 new lighting tests**, Ruff, strict mypy and import contracts PASS.
- **Checkpoint 5 PASS:** independent spec transcription in release-shipped
  `world_catalog/initial_house.json`; no snapshot generation or runtime spec
  parsing. Pure `layout.py` assembles frozen WorldLayout values.
  `runtime/world_layout.py` alone reads the named package resource, strictly
  parses JSON (including duplicate/unknown fields and numeric types), freezes
  values and invokes S1–S4/S12 validation. No startup/life-loop caller exists.
  Gate: **52 data/acceptance tests** PASS; exact T1/T2 columns, rows/order and all
  cells equal the unchanged Oracle. Grid 44×26, 8 regions, 7 doors, 4 open edges,
  3 closed placeholders, approved floor counts and 1,144 singly owned cells.
  Ruff, strict mypy and import contracts PASS.
- **Resource packaging PASS:** existing hatchling wheel build succeeded offline
  into temporary storage; no packaging/dependency configuration change. Wheel
  resource bytes equal the JSON source, tests/snapshot are excluded, and an
  isolated Python import directly from the wheel validates 8/7/1,144 values.
- **Checkpoint 6 PASS:** **380 tests passed / 0 failed** across `tests/world`,
  forbidden-API/security boundaries and legacy `tests/core/test_room.py`.
  Ruff lint/format PASS (12 files); strict targeted mypy PASS (23 files);
  import contracts **10 kept / 0 broken**. Scope/history/whitespace checks PASS.
  These consolidated totals include the checkpoint tests; do not sum reruns.
- **Safety / pending:** no changes to earlier primitive/structure/topology code,
  legacy runtime paths, Oracle/Harness/snapshot, approved sources, database/schema,
  API, renderer or production default. The existing 30-day digest test and its
  dependency sources are unchanged; the full simulation and Release Gate were
  not rerun. Only isolated runtime resource loading is added. Original design
  conversation was not consulted; accepted repository sources are the evidence.
  Final owner acceptance and subsequent commit/integration remain pending.
  R1A-03–R1A-20 stay TODO; the deferred desk-capability decision is outside R1A-02.

## Acceptance checklist for the complete implementation

- [x] Grid 44×26; 8 regions with exact T1 identities, floor counts and statuses.
- [x] L8 bands, side columns and exterior south cutaway reproduce the spec.
- [x] 7 T2 archways, correct 2×3 passages, adjacency and southern ownership.
- [x] Derived graph has 4 open edges and connects all 5 open rooms; closed
  placeholders unconnected initially.
- [x] Backend lighting has 1,144 cells covered exactly once, including structure.
- [x] Zero differences against approved T1/T2 Oracle; snapshot/Harness unchanged.
- [x] S1–S4, S7 band-side and S12 positive and negative tests pass.
- [x] Direction/legacy mapping and one shared feet formula verified (Checkpoint 1).
- [x] Pure-core/catalog/test boundaries preserved; no runtime activation, API,
  renderer, DB/schema, production/default-view or pinned-digest changes.
- [ ] Focused validation evidence and docs reviewed; owner acceptance recorded.

## Risks, ambiguities and approvals

**No unresolved geometry conflict blocks R1A-02 planning.** Separate owner
implementation authorization remains required. Module names, JSON data placement,
reader boundary, diagnostics and half-open internal ranges above are implementation
proposals for review; they do not change accepted geometry. The plan does not
choose movement tuning, face size, phase tints or default zoom.

**Reported cross-source conflict, outside this item:** ADR-0036 §3 says the Writing
Desk and Computer Desk have disjoint capabilities (also spec S15), while spec T3
and T4 list `seat` for both; T6 requires `writing_surface&seat`. Literal disjoint
sets and those rows cannot both hold. Do not silently remove `seat`, rewrite the
Oracle or reinterpret disjointness. Record for owner/ADR/spec clarification before
R1A-03/06 capability validation; no catalog/capability behavior is implemented by
R1A-02, and no later detailed plan is started here.

Geometry risks to guard explicitly: inclusive source ranges vs half-open internal
ranges; deduplicating shared walls without losing ownership; confusing floor room
membership with lighting ownership; treating a closed passage as traversable;
mutating frozen inputs; allowing area totals to hide partition overlaps/gaps;
and coupling runtime data to the test Oracle. Structural geometry validation is
not a substitute for later collision/pathing/keep-clear validation.
