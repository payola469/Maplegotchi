# Maple Room R1a Master Implementation Plan

**Status:** PLANNED — NOT IMPLEMENTED

**Baseline:** `v0.2-development` @ `dfd5972` (schema v10)

**Purpose:** R1a builds and validates the new Maple Room engine in isolation. It must **not** migrate production state and must **not** switch the production default view.

> - **R1a is NOT authorized.** This document plans R1a; it does not authorize it. Implementation starts only after an explicit owner authorization.
> - **Pre-R1 gate (§9): two items remain OPEN and are BLOCKERS before R1A-01:** the OD-01 restore test and R-01 (fixed or explicitly accepted). The boundary probe is **PASS / CLOSED**, recorded 2026-10-10 from owner-supplied evidence (worklog). Stage C authorization and Phase 8 status were resolved on 2026-10-09.
> - This is a planning document. It records **no** implementation result. Live status is in `maple-room-r1a-checklist.md`; history is in `maple-room-r1a-worklog.md`.
> - Planning depth: every workstream is defined by scope, dependencies, outputs, evidence and completion criteria. Detailed task breakdowns are written **only immediately before** an item starts (§7).

## Contents

1. Inputs and authority
2. Known design baseline (input, not new design)
3. Workstreams R1A-01 … R1A-20
4. Dependency graph, critical path, parallel groups
5. Known risks and open values
6. R1a / R1b boundary
7. Detailed work-item policy
8. Documentation policy and the architecture-change stop rule
9. Pre-R1 gate and authorization preconditions

---

## 1. Inputs and authority

The plan applies these accepted documents. It changes none of them.

| Document | Role for R1a |
|---|---|
| `CLAUDE.md` (D34–D40, §3–§5) | Project rules: pure core, determinism, security boundary, coding rules, check commands |
| `docs/architecture/maple-room-final-design-spec.md` | **Binding target geometry** (SPEC, owner-approved in principle): 44×26 house, regions, doors, instances, points, slots, resolution, legacy projection, validation rules **S1–S17**, tables **T1–T7** |
| ADR-0035 | World model: one grid, derived room graph, flat 4-dir A\*, collision, recovery, direction vocabulary, `FEET_IN_TILE` |
| ADR-0036 | Catalog + instances, capability resolution, approach/occupy points, backend owns geometry, renderer draws only |
| ADR-0037 | Persistence model, lookup tables, R1a/R1b staging, v11 discipline, legacy projection |
| ADR-0038 | Owner Edit Mode and authentication — **R4, not R1a**; R1a only keeps validation reusable |
| ADR-0039 | Storage and slot-only placement; R1a builds the slot model and hooks only |
| ADR-0040 | Flagged view transition; B14 default-switch gate (not an R1a gate) |
| ADR-0041 | Art rule set, **locked values L1–L22**, amendments **C1–C8** |
| `maple-future-architecture.md` §6, §9, §22 | Component boundaries, proposed APIs/events, render layers, pre-implementation criteria |
| `maple-art-production-contract.md` | Asset rules, metadata (Part C), validator checklist (Part E) |
| `docs/spikes/2026-10-room-art-spike.md` | Evidence M01–M22 for the locked values; follow-ups (§10) |

**Precedence when documents appear to disagree:** locked ADR values > accepted ADR rules > Final Design Spec (SPEC) > future-architecture / contract text marked PROPOSED. A disagreement is **not** resolved inside an implementation item; it triggers the stop rule (§8).

**Spike branch:** `spike/room-art-tech` stays **unmerged**. R1a does not merge it. Production code is written and reviewed as new code against the locked values; the spike remains evidence only.

## 2. Known design baseline (input, not new design)

R1a implements these. It does not redesign them.

| Area | Baseline | Source |
|---|---|---|
| House | 44 × 26 tiles (704 × 416 px), T = 16 | Spec §A; ADR-0041 L1 |
| Regions | 8 reserved; **5 open** (Bedroom, Living Room, Library, Work Studio, Central Hall); **3 closed placeholders** (Future Space, Creation Room, System Room) | Spec §B, T1; ADR-0035 §2 |
| Doors | 7 two-tile **open archways** through 3-row bands; 4 open, 3 closed | Spec §C, T2; ADR-0041 L9, C5 |
| Topology | **Star** through Central Hall; graph derived from open doors | Spec §C |
| Closed rooms | Floors and passages **inaccessible**; never a path, recovery or placement target | Spec §K, S5 |
| Maple | 32 × 48 canvas, feet anchor (16, 47), occupies 1 tile | ADR-0041 L2, L3 |
| Feet in tile | `FEET_IN_TILE = (T/2, ⌊13T/16⌋) = (8, 13)` | ADR-0035 §6; L4 |
| Walls | 3T north walls = 3 rows; side walls = 1 column; south cutaway row | ADR-0041 L7, L8 |
| Depth | Tile-south-edge sort, `zIndex = sortY·8 + priority` | L11, C4 |
| Movement | Deterministic flat 4-direction A\*, integer costs, turn penalty, `(f, h, ty, tx)` ties; ADR-0027 semantics kept; no teleport except recorded recovery | ADR-0035 §3 |
| Objects | Backend-owned geometry; catalog + instances; 28 instances, 34 blocking tiles, 17 points, 12 slots | ADR-0036; Spec §J, T3–T5 |
| Interaction | Capability-based resolution; seeded tie-break; Writing Desk ≠ Computer Desk | ADR-0036 §3; Spec §M, T6 |
| Placement | Slots only; Maple places only into `maple_may_place` slots, only `movable_by: maple` objects | ADR-0039 |
| Legacy | Legacy 1000×600 view retained and fed by a deterministic projection | ADR-0037 §4; Spec §N, T7 |
| View | Old Room view is the default; new view behind a feature flag | ADR-0040 §1 |
| Renderer | Device-pixel renderer, zoom L1–L4, Overview/Follow/Focus, grid-partition lighting, Vite-hashed atlases, `preferWorkers: false`, budgets | L13–L21 |

**Spec headline numbers R1a must reproduce:** 431 walkable tiles in one component (Bedroom 49, Living Room 64, Library 63, Work Studio 63, Hall 168, open passages 24); 200 closed-room floor tiles excluded; 29 approach references on 26 distinct tiles with exactly 3 declared reuses; lighting partition 1,144 cells covered exactly once; walk-length matrix (T6), longest walk 53 steps.

---

## 3. Workstreams

Each workstream lists: objective, scope, dependencies, outputs, evidence, completion criteria, non-goals, parallelism, documentation, and what it blocks. **Start** dependencies must be met before work begins; **completion** dependencies must be met before the item can be DONE.

Every item also inherits these global rules:
- Pure domain logic stays in `core` (no I/O, clock or randomness; `+ - * /` only; deterministic iteration) — CLAUDE.md §5.
- No production state change, no production default-view change, no deployment.
- The existing pinned 30-day simulation digest is **unchanged** by R1a (production behaviour does not change until R1b). A change to it is a stop-rule event (§8).
- Existing checks (`scripts/check.sh`, CI) stay green at every commit.

### R1A-01 — Baseline and test harness

- **Objective:** establish a verified, reproducible starting point and the shared test scaffolding before any world code exists.
- **Scope:**
  - record the starting baseline: commit, `scripts/check.sh` result, CI result (backend on Ubuntu + Windows, frontend on Ubuntu), existing test counts, the pinned 30-day simulation digest, the approved route table;
  - a **spec oracle**: a test-side, machine-readable reading of spec tables T1–T7 used to prove the implementation reproduces the spec exactly (test input only, never the runtime source of geometry);
  - package placement and import-linter / AST purity contracts for the new world domain code, using the boundaries in future-architecture §6.1 and ADR-0036 §2 (catalog under `maplegotchi/world_catalog/`);
  - the property-testing approach (a new test dependency or seeded generators — a new dependency is a reviewed decision recorded in the worklog);
  - conventions for fixtures, scratch databases and evidence capture.
- **Dependencies:** start — the pre-R1 gate closed and owner authorization of R1a (§9); completion — none.
- **Outputs:** baseline record (worklog), test harness and oracle, purity/import contracts, fixture conventions. No world behaviour.
- **Tests / evidence:** checks green on the start commit; oracle parses the spec and rejects deliberately mutated copies; new import/purity contracts pass and fail on a planted violation.
- **Completion criteria:** baseline recorded; harness usable by R1A-02; contracts enforced in CI; no runtime behaviour changed.
- **Non-goals:** world logic, schema, renderer, catalog content.
- **May run in parallel with:** nothing (precedes all implementation). The frameworks of R1A-16/17/18 are seeded here.
- **Docs to update:** `CLAUDE.md` §3.2 layout and `docs/architecture.md` if new packages appear.
- **Blocks later R1a items:** yes, all. **Blocks R1b:** yes (indirectly).

### R1A-02 — Canonical world model and final house geometry

- **Objective:** a pure-core house model that reproduces the Final Design Spec geometry exactly.
- **Scope:**
  - tile coordinates, rectangular regions, room-of-tile derivation;
  - wall cells derived by the L8 convention (3-row bands, side columns, south cutaway; shared band belongs to the southern room);
  - doors (2-tile archways, `open`/`closed`), passage tiles belonging to the southern room;
  - the derived room graph over open doors;
  - direction vocabulary `down/left/right/up` ↔ `south/east/west/north` (ADR-0035 §5), added alongside legacy `front/back`;
  - `FEET_IN_TILE` from its formula (single shared definition);
  - lighting-zone partition geometry as backend data (spec §P), so the renderer never derives it;
  - the initial-house layout data for regions and doors (T1, T2);
  - geometry validation S1–S4, S7 (band side), S12.
- **Dependencies:** start — R1A-01.
- **Outputs:** world model types, initial house regions/doors data, geometry validation.
- **Tests / evidence:** grid 44×26; 8 regions with the T1 floor counts; band/side/cutaway cells; 7 doors joining the regions directly above/below; star graph (4 open edges; placeholders unconnected while closed); 1,144 cells covered once by lighting zones; oracle equality with T1/T2; negative cases (overlap, door off a band, non-adjacent door, interior window band) rejected.
- **Completion criteria:** spec geometry reproduced with zero oracle differences; S1–S4, S12 enforced with positive and negative tests.
- **Non-goals:** objects, walkability with objects, pathfinding, persistence, rendering, non-rectangular rooms, side doors.
- **May run in parallel with:** R1A-14 (pipeline start), R1A-16/17 (continuous), a draft of R1A-10 contracts.
- **Docs to update:** `docs/architecture.md`; ADR-0035 / spec only through the stop rule.
- **Blocks later R1a items:** yes (03–13). **Blocks R1b:** yes.

### R1A-03 — Object catalog and capability metadata

- **Objective:** the release-shipped object-type catalog and the initial-house instances, with capability, point and slot metadata.
- **Scope:**
  - catalog type fields per ADR-0036 §2 (category, `geometry_version`, footprint, `blocks`, orientations, capabilities, point and slot templates, states, `movable_by`, `deletable_by`, placement rules);
  - catalog loaded by `runtime` and passed to core as frozen data;
  - object-local point/slot coordinates with rotation by orientation;
  - types used by the spec, including the new types **`furniture.side_table`, `furniture.armchair`, `furniture.shelf_low`, `decor.project_board`, `marker.idle_spot`** (structural, no art);
  - reference geometry from the spike conventions (PROVISIONAL per object, `geometry_version` review);
  - the 28 instances (T3), resolved points (T4) and slots (T5, including `shares_point`);
  - capability vocabulary (ADR-0036);
  - validation S6, S7 (object side), S15, S16, and the catalog half of S17.
- **Dependencies:** start — R1A-02.
- **Outputs:** catalog data and loader boundary, instance layout data, catalog validation.
- **Tests / evidence:** instances equal T3; absolute points equal T4; slots equal T5; 34 blocking tiles with per-room counts (7/6/7/14/0); footprints inside one room floor; wall objects on plain band cells, windows only on exterior bands; Writing/Computer Desk capabilities disjoint; no instance `movable_by: maple`; rotation tests for all orientations; marker kind accepted without art.
- **Completion criteria:** oracle equality for T3–T5 geometry; listed S-rules enforced with negative tests.
- **Non-goals:** art, Edit Mode, object state machines beyond `default`, representations, Maple-movable objects.
- **May run in parallel with:** R1A-14, R1A-16/17.
- **Docs to update:** `docs/architecture.md`; contract Part C / ADR-0036 only through the stop rule.
- **Blocks later R1a items:** yes (04, 06, 07, 14 completion). **Blocks R1b:** yes.

### R1A-04 — Walkability, collision and recovery

- **Objective:** the walkable mask, connectivity and the recorded recovery rule.
- **Scope:**
  - walkable = floors of open rooms + passages of open doors − blocking masks (spec §K);
  - closed floors and passages never walkable;
  - connectivity of the open component; keep-clear rules K1–K4 (S10);
  - Maple occupies one tile;
  - recovery: nearest walkable tile by BFS inside the open component, tie-break `(ty, tx)`, producing a `maple_relocated` record (persistence of the event in R1A-08);
  - validation S5, S10, S13.
- **Dependencies:** start — R1A-02, R1A-03.
- **Outputs:** walkability and recovery in core; validation rules.
- **Tests / evidence:** **431** walkable tiles with per-area counts 49/64/63/63/168/24; one component; **0** closed tiles walkable or reachable; 200 closed floor tiles excluded; door corridors clear on both sides including closed doors; recovery property tests (deterministic, always inside the open component, never a closed room); `idle.hall_center` (21,15) walkable and never blocked.
- **Completion criteria:** all counts match the spec; S5, S10, S13 enforced with negative tests.
- **Non-goals:** dynamic occupancy, other agents, pathfinding.
- **May run in parallel with:** R1A-14, R1A-16/17.
- **Docs to update:** `docs/architecture.md`.
- **Blocks later R1a items:** yes (05, 07, 08). **Blocks R1b:** yes.

### R1A-05 — Deterministic A\* pathfinding

- **Objective:** one flat, deterministic, integer 4-direction A\* and route timing.
- **Scope:**
  - integer step cost, PROVISIONAL turn penalty, Manhattan heuristic, ties on `(f, h, ty, tx)`; no `sqrt`, no float geometry, no hierarchy, no cache;
  - compressed route waypoints `(tx, ty, cumulative_steps)`;
  - travel time `steps × ms_per_step`; position at `now` with `+ - * /` only; pixel position via `FEET_IN_TILE`;
  - `no_destination` when no path; reroute from the current position (ADR-0027 semantics);
  - selecting `ms_per_step` (and the turn penalty) with simulation evidence from R1A-17.
- **Dependencies:** start — R1A-04.
- **Outputs:** pathfinding and route/time model in core.
- **Tests / evidence:** walk-length matrix T6 reproduced, or each difference caused by the chosen turn penalty recorded as a decision; property tests: contiguous 4-neighbour paths, every tile walkable, never a closed tile, no teleport, identical results across runs and across Windows/Linux CI; interpolation exactness at waypoints and arrival.
- **Completion criteria:** properties green; `ms_per_step` and turn penalty values chosen with recorded evidence (still tunable).
- **Non-goals:** door animations as state, path caching, multi-agent avoidance.
- **May run in parallel with:** R1A-14, R1A-16/17.
- **Docs to update:** `docs/architecture.md`, `docs/autonomy.md` (movement), ADR-0035 §7 tuning note if values are recorded there.
- **Blocks later R1a items:** yes (06, 07, 09, 11 walking). **Blocks R1b:** yes.

### R1A-06 — Interaction and capability resolution

- **Objective:** pure capability resolution from activity to a reachable interaction point.
- **Scope:**
  - the activity requirement table (spec §M, T6), including the two deliberate narrowings (`rest` = `seat_soft`; bed = `sleep_spot` only; armchair = `reading_spot` + `seat`);
  - candidate filtering: capability groups, instance state, capacity, reachability;
  - integer scoring with PROVISIONAL weights and room tiers; ties via the seeded `decision` stream, never set order;
  - approach + occupy output (pose, direction);
  - the allowed-activities derivation (S9);
  - activities `sleep`, `rest`, `think`, `read`, `write`, `observe_server`, `idle`/`walk`.
- **Dependencies:** start — R1A-03, R1A-05.
- **Outputs:** resolution functions in core, tested in isolation. **Not** wired into the live decision transition (that is R1b).
- **Tests / evidence:** each activity resolves to the T6 candidates; the canonical choice per activity matches the legacy-faithful tier rules; deterministic tie-breaks; removing the last provider disallows the activity and the layout is rejected by S9; structural test that no code maps an activity directly to an object type (ADR-0036 consequence); D26 preserved.
- **Completion criteria:** every activity resolves correctly in the initial house and in synthetic variants; S9 and S15 enforced.
- **Non-goals:** Director/rule-direction wiring in production, new activities, preference-memory tuning beyond the scoring hook.
- **May run in parallel with:** R1A-07, R1A-08 (model), R1A-14, R1A-16/17.
- **Docs to update:** `docs/autonomy.md`, `docs/architecture.md`.
- **Blocks later R1a items:** yes (09, 10). **Blocks R1b:** yes.

### R1A-07 — Placement slots and Storage hooks

- **Objective:** the slot model and the pure placement/Storage rules, with no autonomous placement behaviour.
- **Scope:**
  - slot data on instances (`accepts`, `capacity`, `maple_may_place`, `shares_point`, approach);
  - S8 (approach-sharing rule) and S11 (slots never affect walkability; hook slots `maple_may_place = false`);
  - pure placement validation: class accepted, capacity free, permission set, `movable_by: maple`, cooldown and rate limit as PROVISIONAL parameters;
  - Storage as a derivation (eligible object with no active placement);
  - the display-placement data shape (persisted in R1A-08).
- **Dependencies:** start — R1A-03, R1A-04, R1A-05 (approach reachability).
- **Outputs:** slot model and validation in core.
- **Tests / evidence:** 12 slots; 29 references on 26 tiles with exactly 3 declared reuses; an undeclared coincidence is rejected; a declared reuse with a different tile or facing is rejected; Maple placement rejected for hook slots, non-`maple_may_place` slots, non-Maple-movable objects, full slots, unaccepted classes, during cooldown, over the rate limit; walkable mask identical with and without placements.
- **Completion criteria:** S8, S11, S16 enforced; Maple cannot place into any unauthorized location.
- **Non-goals:** Maple's autonomous placement decisions/actions (R3–R5), Edit Mode (R4), representations (W-phases), storage chest, placement zones.
- **May run in parallel with:** R1A-06, R1A-08, R1A-14, R1A-16/17.
- **Docs to update:** `docs/architecture.md`.
- **Blocks later R1a items:** yes (08, 10). **Blocks R1b:** yes.

### R1A-08 — Persistence model / schema-v11 preparation

- **Objective:** design and rehearse the v11 persistence model and the v10 → v11 conversion, **without** making it reachable by production.
- **Scope:**
  - ADR-0037 model: append-only layout revisions, active-revision pointer, display placements with history, world events, lookup tables replacing CHECK enums (A17), Maple position `(tx, ty)` plus route waypoints;
  - the conversion into the final initial house: spec §R point mapping, an in-flight route becomes a zero-length plan at its destination's new point, no fabricated timeline events;
  - ADR-0028 discipline: forward-only, one `BEGIN IMMEDIATE` transaction, in-transaction verification, converted state loads through core invariants, verified pre-migration copy;
  - **rehearsal only on synthetic v10 databases** in scratch directories (fresh birth, demo-day, aged data covering every legacy location/point and a route in flight).
- **Production-safety constraint (mandatory):**
  - in R1a the v11 conversion must **not** be reachable from production startup or release activation; a release built from R1a work still opens and keeps v10 databases at v10;
  - the shipped-migration immutability rule (CLAUDE.md §5) applies from the moment a migration is shipped, so the v11 migration is registered as a shipped migration **only in R1b**;
  - the mechanism is decided in this item's breakdown and reviewed.
- **Dependencies:** start — R1A-02, R1A-03, R1A-05; completion — R1A-07.
- **Outputs:** v11 candidate model and conversion, rehearsal harness, rehearsal evidence.
- **Tests / evidence:** on every synthetic v10 database: identity, `born_at`, seed, counters, history counts and max ids preserved; `foreign_key_check` clean; converted state loads; every legacy point maps per §R; in-flight route handled; no fabricated events; second run refused (forward-only); failure mid-transaction leaves v10 intact; a test proves the production code path still reports and requires schema v10.
- **Completion criteria:** rehearsal passes on all synthetic databases; production unreachability proven by test.
- **Non-goals:** rehearsal on a production copy (R1b), the production migration, the owner snapshot gate run, any deploy-script or service change, data retention.
- **May run in parallel with:** R1A-06, R1A-07, R1A-09, R1A-11…14.
- **Docs to update:** `docs/persistence.md` (v11 candidate, clearly marked not shipped), ADR-0037 [PROPOSED] shapes recorded as candidate.
- **Blocks later R1a items:** yes (10 revision identity, 20). **Blocks R1b:** **yes, directly.**

### R1A-09 — Legacy projection compatibility

- **Objective:** a pure, deterministic projection of the new world onto the legacy 1000×600 view.
- **Scope:**
  - legacy point = f(activity, idle spot) per T7; raises on an unmapped point (closed rooms need no mapping);
  - legacy walking between projected points over the existing legacy waypoint graph, using the grid route's **same** `departed_at` / `arrives_at`;
  - activity, timing, reaction, expression, pose class and day phase pass through unchanged; only position is simplified;
  - S14.
- **Dependencies:** start — R1A-05, R1A-06.
- **Outputs:** projection functions in core, applied in R1a to development/fixture world state only. Production keeps emitting legacy fields natively until R1b.
- **Tests / evidence:** every T7 row; projected points pass the legacy `InteractionPoint` validation; property: projected arrival equals the grid `arrives_at`; determinism; unmapped point raises; existing legacy room tests unchanged and green.
- **Completion criteria:** S14 enforced; projection truthful and deterministic.
- **Non-goals:** changing the legacy view, the legacy anchors or the legacy walker.
- **May run in parallel with:** R1A-07, R1A-08, R1A-11…14.
- **Docs to update:** `docs/architecture.md`, `docs/frontend.md` (legacy feed note).
- **Blocks later R1a items:** yes (10, 15). **Blocks R1b:** yes.

### R1A-10 — New Room backend/API contracts

- **Objective:** additive, read-only API contracts for the new world, without changing any legacy contract.
- **Scope:**
  - read-only endpoints as proposed in future-architecture §6.11 (`/api/world`, `/api/world/catalog`, `/api/world/placements`; exact names and DTOs fixed in this item);
  - snapshot extensions: world revision, tile position with derived px, tile route, `down/left/right/up` facing alongside `front/back`;
  - the `world` SSE kind only if R1A-15 needs it; otherwise deferred to R1b by a recorded decision;
  - OpenAPI and derived frontend types; the route-table test updated deliberately;
  - **truthfulness:** while production data is v10, the new endpoints must never present fixture or simulated world state as Maple's real state; exposure is limited to development/fixture runtime or an explicit flag (mechanism decided in the breakdown);
  - security headers, `Origin` rules and CSP unchanged; **no mutation endpoints** (owner endpoints are R4).
- **Dependencies:** start — R1A-02 (a fixture contract draft may start here for R1A-11); completion — R1A-06, R1A-07, R1A-08 (revision identity), R1A-09.
- **Outputs:** endpoints, DTOs, OpenAPI, frontend types, fixture JSON for renderer work.
- **Tests / evidence:** API tests; route table equals the deliberately updated set, still GET-only for the new routes; `/api/room` and every legacy snapshot field unchanged (contract tests); security-header tests unchanged; no fixture data reachable as real state in a production-shaped configuration.
- **Completion criteria:** contracts stable and documented; legacy contracts byte-compatible.
- **Non-goals:** owner auth, Edit Mode endpoints, write endpoints, removal of `/api/room`.
- **May run in parallel with:** R1A-11…14 (against the fixture draft).
- **Docs to update:** `docs/api.md`, `docs/security-model.md` (route surface), `CLAUDE.md` if the API surface summary changes.
- **Blocks later R1a items:** yes (11 completion, 15). **Blocks R1b:** yes.

### R1A-11 — Pixi renderer shell

- **Objective:** a new, flagged PixiJS room renderer that only draws backend (or fixture) data.
- **Scope:**
  - locked renderer settings (L13), atlas loading per L19;
  - layers per future-architecture §9.2: floor (variants + edge overlay, L17), walls/bands/caps, archway doors, windows (L10), objects, Maple, occupant overlays;
  - depth sort L11 (tile-south-edge for Maple, footprint south edge + offset for objects, priorities, insertion-order ties);
  - Maple walk animation phase locked to route distance (L12) and positioned via `FEET_IN_TILE`;
  - face overlay **method** (L6) with a face-size parameter (size PROVISIONAL);
  - placeholder/test art only;
  - DOM keeps all text and controls (D2);
  - no pathfinding, validation, capability resolution or geometry constants in the renderer (ADR-0036 §6).
- **Dependencies:** start — R1A-02 and the R1A-10 fixture contract draft; completion — R1A-10, R1A-14 (atlas loading).
- **Outputs:** renderer module behind the flag; frontend guard tests.
- **Tests / evidence:** guard tests (no duplicated geometry or rules, API-driven only); depth-sort cases with 0 mismatches on a fixture ring of same-row and around-object positions; walk-phase determinism; renders the full initial house from fixture data.
- **Completion criteria:** the full house renders from API data with locked settings; guard tests green.
- **Non-goals:** production art, final face size, Edit Mode overlays, sound.
- **May run in parallel with:** R1A-06…10 (after its start dependencies), R1A-14.
- **Docs to update:** `docs/frontend.md`, `CLAUDE.md` §3.2 if the frontend layout changes.
- **Blocks later R1a items:** yes (12, 13, 15, 19). **Blocks R1b:** no (R1b is backend cutover; the old view stays default), but it blocks the later B14 switch.

### R1A-12 — Camera, zoom and DPR behaviour

- **Objective:** implement the locked camera and pixel rules and the spec's oversize-Focus clarification.
- **Scope:**
  - device-pixel backing (`devicePixelContentBoxSize` validated against CSS × DPR, otherwise rounded), DPR re-checked on every render (L13);
  - `Zd = max(1, ⌊L·DPR + 0.25⌋)`, L1–L4, Zd ∈ [1, 12] (L14);
  - Overview / Follow / Focus (L15); DOM room-list fallback with Maple's room highlighted;
  - **oversize Focus** (spec §O): a region that does not fit at L1 uses L1, centred on Maple if she is in it, otherwise on the region centre, clamped;
  - reduced motion snaps;
  - default zoom per form factor configurable and explicitly non-final (UNDECIDED);
  - a layout test that the desktop room box stays near the measured 806 × 484, with the DOM fallback allowed if it shrinks.
- **Dependencies:** start — R1A-11.
- **Outputs:** camera module, fit computations, fallback UI.
- **Tests / evidence:** unit tests reproducing spec §O tables (Overview desktop fit at DPR 1–3; tablet/phone fallback cases; Follow visible tiles; Focus levels; Hall oversize case); browser evidence of pixel conformance at DPR {1, 1.25, 1.5, 2, 3} × L1–L4 (EMULATED for tablet/phone); DPR change applied within one frame.
- **Completion criteria:** all locked camera rules and the oversize rule pass; viewport assumption covered by a test.
- **Non-goals:** choosing default zoom levels; real-device QA (B14).
- **May run in parallel with:** R1A-13, R1A-14.
- **Docs to update:** `docs/frontend.md`.
- **Blocks later R1a items:** yes (15, 19). **Blocks R1b:** no.

### R1A-13 — Lighting zones and emitter hooks

- **Objective:** layered lighting driven by backend day phase and backend zone geometry.
- **Scope:**
  - L16 order: neutral base → per-zone multiply tint over the backend partition → additive light sprites → emissive last;
  - hooks from spec §P: window daylight spill (4 north windows), floor lamps (14,5) and (21,7), Computer Desk emissive;
  - placeholder phase-tint presets (colours UNDECIDED) that keep Maple's night contrast ≥ 1.5;
  - placeholder rooms use artificial presets, no window daylight (O1).
- **Dependencies:** start — R1A-11, R1A-02.
- **Outputs:** lighting layers and preset plumbing.
- **Tests / evidence:** rendered partition 0 overlaps and 0 gaps; emissive exact in all four phases; night contrast ≥ 1.5 with placeholder presets; draw-call contribution recorded.
- **Completion criteria:** L16 satisfied; presets replaceable without code changes.
- **Non-goals:** final tint colours and strengths, weather, sound.
- **May run in parallel with:** R1A-12, R1A-14.
- **Docs to update:** `docs/frontend.md`.
- **Blocks later R1a items:** yes (15, 19). **Blocks R1b:** no.

### R1A-14 — Asset pipeline and atlas integration

- **Objective:** the production asset pipeline from `art/export/**` to hashed atlases, proven with placeholder art.
- **Scope:**
  - inputs `art/export/**` and `art/palette/**`, plain Git, no LFS, never `export-ignore` (C1, B7, B15);
  - validator with the locked rule set E1–E8, E10–E13, E18, E20, E23–E25 (L22), honouring C3;
  - atlas packing per L18 (per pack, page caps, trim with `spriteSourceSize`, 2 px extrusion, deterministic MaxRects, anchors preserved);
  - Vite-imported, content-hashed atlases, never `public/` (C2); `preferWorkers: false`, `pixi.js/unsafe-eval` kept, CSP unchanged (L19);
  - texture budget check: static packs ≤ 28 MiB, 32 MiB resident (L20);
  - bundle-content test: no raw art, `meta.json` or palette in `frontend/dist` (C1);
  - release build input: `scripts/build_release.sh` includes the art inputs in its `git archive` path list (spike §10 follow-up);
  - catalog ↔ manifest cross-check (`geometry_version`, S17), with the structural marker kind allowed without art;
  - a placeholder art set covering every key the renderer needs, with fallbacks.
- **Dependencies:** start — R1A-01; completion — R1A-03 (catalog cross-check), R1A-11 (loading integration).
- **Outputs:** validator, packer, build integration, placeholder art, budget and bundle checks.
- **Tests / evidence:** positive set with 0 false positives; negative set rejected with the expected rule (including LFS pointers and `filter=lfs`); byte-identical rebuild on Windows; release build produces only hashed atlases plus the built frontend; CSP tests unchanged.
- **Completion criteria:** pipeline green end to end; Linux reproduction handed to R1A-18.
- **Non-goals:** production art, face overlay final size, audio.
- **May run in parallel with:** R1A-02…13.
- **Docs to update:** `maple-art-production-contract.md` (only factual pipeline references), `docs/frontend.md`, `docs/deployment.md` (release build input), `CLAUDE.md` §3.2 if `art/` appears in the layout.
- **Blocks later R1a items:** yes (11 completion, 18, 19). **Blocks R1b:** no (art is not part of the cutover), but blocks the B14 switch.

### R1A-15 — Feature flag and old/new Room coexistence

- **Objective:** both views coexist; the legacy view remains the default and is unchanged.
- **Scope:**
  - a flag selecting the legacy or the new view; default **legacy** (ADR-0040 §1);
  - rollback = turning the flag off;
  - shared DOM panels; a DOM room summary naming Maple's room in the new view (accessibility baseline);
  - in R1a the new view shows only development, fixture or simulation worlds and labels them as such; it never presents them as production Maple;
  - no backend business rules duplicated in the renderer;
  - the flag mechanism is decided in the breakdown; production configuration is **not** modified in R1a.
- **Dependencies:** start — R1A-10, R1A-11; completion — R1A-12, R1A-13, R1A-14.
- **Outputs:** flag, view switch, integrated new-view candidate.
- **Tests / evidence:** flag off → legacy view identical (existing frontend tests unchanged and green); flag on → new renderer; toggle round trip; guard tests; security and CSP tests unchanged.
- **Completion criteria:** an integrated, flagged candidate exists; the legacy default is provably unchanged.
- **Non-goals:** switching the default, removing the old view or `front/back`, the B14 gate.
- **May run in parallel with:** R1A-16…18.
- **Docs to update:** `docs/frontend.md`, `CLAUDE.md` status (when the candidate exists).
- **Blocks later R1a items:** yes (19, 20). **Blocks R1b:** no; it preserves the coexistence R1b relies on.

### R1A-16 — Validators and property tests (continuous)

- **Objective:** one complete, pure validation surface and the property-test suite, grown with each item.
- **Scope:**
  - a single layout validation entry covering S1–S17 with structured errors (reusable later by the R4 preview);
  - property tests: no teleport, path validity, recovery determinism, capability resolution, slot rules, projection timing;
  - a negative corpus of mutated spec layouts;
  - the asset validator suites (with R1A-14);
  - the structural "no activity → object type" test.
- **Dependencies:** start — R1A-01; grows with R1A-02…14.
- **Outputs:** validator, property suites, negative corpus.
- **Tests / evidence:** every S-rule has at least one positive and one negative test; all property suites green on both CI operating systems.
- **Completion criteria:** S1–S17 coverage complete; no rule untested.
- **Non-goals:** Edit Mode UI.
- **May run in parallel with:** everything (continuous).
- **Docs to update:** spec §S only through the stop rule.
- **Blocks later R1a items:** R1A-20. **Blocks R1b:** yes (B14 criterion 3 property tests).

### R1A-17 — Fixtures and simulation coverage (continuous)

- **Objective:** deterministic fixtures and a grid-world simulation that exercise the engine end to end.
- **Scope:**
  - the canonical initial-house fixture (from the engine data, checked against the spec oracle);
  - synthetic layouts (blocked tiles, closed and hypothetically opened doors for tests only, provider removal);
  - synthetic v10 databases for R1A-08;
  - a deterministic grid-world simulation with its **own** pinned digest; the existing 30-day digest stays unchanged;
  - `ms_per_step` / turn-penalty tuning evidence (route durations against activity durations);
  - renderer fixtures (API JSON) for R1A-11…13 and scripted scenarios for R1A-19.
- **Dependencies:** start — R1A-01; grows with R1A-02…15.
- **Outputs:** fixtures, simulation, digests, tuning evidence.
- **Tests / evidence:** digests identical on Windows and Linux CI; the existing digest unchanged; a long simulated run with no failures, unresolvable action loops or unexpected recoveries.
- **Completion criteria:** coverage for every workstream that needs data; tuning evidence recorded.
- **Non-goals:** production data.
- **May run in parallel with:** everything (continuous).
- **Docs to update:** `docs/architecture.md` (simulation), `docs/autonomy.md` if timing changes are recorded.
- **Blocks later R1a items:** R1A-05 completion (tuning), R1A-19, R1A-20. **Blocks R1b:** yes (digest updated deliberately in R1b).

### R1A-18 — CI and Linux reproducibility (continuous)

- **Objective:** every new check runs in `scripts/check.sh` and CI, including the deferred Linux atlas reproduction.
- **Scope:**
  - new backend tests on the existing Ubuntu + Windows matrix; frontend tests, validator, budget and bundle checks on CI;
  - **Linux atlas reproducibility:** the deterministic rebuild on Linux is byte-identical to the Windows rebuild (comparison method decided in the breakdown);
  - LFS rejection on art inputs;
  - a release-build check proving the bundle contains hashed atlases only.
- **Dependencies:** start — R1A-01; completion — R1A-14.
- **Outputs:** CI configuration and check-script updates.
- **Tests / evidence:** green CI on both operating systems; recorded matching atlas hashes for Windows and Linux.
- **Completion criteria:** Linux reproduction verified; no check runs only locally.
- **Non-goals:** deployment pipelines.
- **May run in parallel with:** everything after R1A-01.
- **Docs to update:** `CLAUDE.md` Commands, `docs/deployment.md` if the release build changes.
- **Blocks later R1a items:** R1A-20. **Blocks R1b:** no (but required for any release containing R1a art).

### R1A-19 — Performance and soak validation

- **Objective:** prove the integrated candidate meets the locked budgets.
- **Scope:**
  - renderer, on the integrated flagged candidate with placeholder art and the full initial house: draw calls ≤ 40; CPU render p95 ≤ 4 ms desktop and ≤ 8 ms in 4×-throttled phone emulation; 0 frames > 33 ms in 60 s on desktop; 10-minute soak heap growth < 5 MB; texture memory ≤ 32 MiB resident (L20, L21);
  - backend: worst-case pathfinding, resolution and validation cost per transition on the full house, recorded;
  - a long grid-world simulation run (R1A-17).
- **Dependencies:** start — R1A-15, R1A-14, R1A-17.
- **Outputs:** measurement records and scripts.
- **Tests / evidence:** recorded measurements with environment details (EMULATED for mobile); comparison against each budget.
- **Completion criteria:** every budget passes; measurements reproducible.
- **Non-goals:** real-device measurements (B14), production-art measurements (B14), the 7-day production soak (B14, after R1b).
- **May run in parallel with:** R1A-16…18.
- **Docs to update:** `docs/frontend.md` (budgets evidence), worklog.
- **Blocks later R1a items:** R1A-20. **Blocks R1b:** no.

### R1A-20 — R1a Acceptance Gate

- **Objective:** a strict, evidence-based decision that R1a is complete. Code existing is **not** completion.
- **Dependencies:** every required item R1A-01…19 DONE with evidence.
- **Gate criteria (all required):**

**Domain / world**
- [ ] Final Design Spec geometry reproduced exactly (oracle equality T1–T5).
- [ ] 44×26 world validated; 8 room regions valid.
- [ ] 5 open rooms connected; 3 closed rooms inaccessible.
- [ ] All 7 door corridors valid.
- [ ] **431** open walkable tiles (unless an approved spec revision changes this).
- [ ] Recovery stays inside the open connected component.

**Objects / interactions**
- [ ] Blocking masks valid (34 tiles, no overlaps).
- [ ] Approach/slot reuse rules valid (29 references, 26 tiles, 3 declared reuses).
- [ ] Capability candidates resolve correctly.
- [ ] `sleep`, `rest`, `think`, `read`, `write`, `observe_server`, `idle` (and `walk`) supported.
- [ ] Slot rules validated; Maple cannot place into unauthorized locations.

**Pathing**
- [ ] Deterministic 4-direction A\*; stable tie behaviour across runs and OS.
- [ ] No path into closed rooms.
- [ ] All required interaction points reachable.
- [ ] Recovery deterministic.

**Persistence**
- [ ] v11 model rehearsal passes (synthetic v10 databases).
- [ ] No production migration; v11 unreachable from production startup/activation.
- [ ] Legacy projection stays truthful.

**Compatibility**
- [ ] Existing Room view still works and is the default.
- [ ] New view remains feature-flagged.
- [ ] No duplicated backend business rules in the renderer.

**Rendering**
- [ ] DPR rules pass.
- [ ] Camera rules pass, including the Central Hall oversize fallback.
- [ ] Lighting partition has no overlaps or gaps.
- [ ] Atlases load through hashed Vite imports.
- [ ] `preferWorkers: false` valid under the unchanged CSP.

**Quality**
- [ ] Validators green; property tests green.
- [ ] Fixtures and simulations green; existing 30-day digest unchanged.
- [ ] CI green.
- [ ] Linux atlas reproducibility verified.
- [ ] Performance budgets pass; soak test passes.

**Documentation**
- [ ] Checklist current; worklog current.
- [ ] Architecture/spec/ADR changes documented where applicable.
- [ ] No unresolved, undocumented architectural deviation.

**Production safety**
- [ ] No production migration performed.
- [ ] No production default switch performed.
- [ ] Rollback / coexistence path preserved.

- **Outputs:** a gate report (worklog entry + checklist) listing evidence per criterion.
- **Completion criteria:** every box checked with linked evidence; owner review of the gate report. **Passing R1a does not authorize R1b**; R1b needs its own owner authorization.
- **Non-goals:** any R1b action; the B14 default-switch gate.
- **Blocks R1b:** yes.

---

## 4. Dependency graph, critical path, parallel groups

### 4.1 Graph (start dependencies; `⇢` = may start on a draft/fixture, must wait for completion)

```
                 [pre-R1 gate closed + owner authorization]
                                  │
                               R1A-01 ─────────────────────────────┐
                                  │                                │
                               R1A-02 ─────────────┐               ├─► R1A-16  (continuous)
                                  │                │               ├─► R1A-17  (continuous)
                               R1A-03              │               ├─► R1A-18  (continuous; completes after 14)
                                  │                │               └─► R1A-14  (start; completes after 03, 11)
                               R1A-04              │
                                  │                ⇢ R1A-10 draft (fixture contracts)
                               R1A-05                     ⇣
                              ╱   │   ╲              R1A-11 ──► R1A-12
                        R1A-06  R1A-07  R1A-08         │   └──► R1A-13
                           │      │       │            │
                        R1A-09    │       │            │
                           ╲      │      ╱             │
                             R1A-10 (complete) ────────┤
                                                       ▼
                                   R1A-15  (needs 10, 11, 12, 13, 14)
                                                       │
                                   R1A-19  (needs 15, 14, 17)
                                                       │
                                   R1A-20  (needs all; 16, 17, 18 complete)
```

### 4.2 Dependency table

| Item | Start after | Complete after |
|---|---|---|
| R1A-01 | pre-R1 gate closed + owner authorization (§9) | — |
| R1A-02 | 01 | — |
| R1A-03 | 02 | — |
| R1A-04 | 02, 03 | — |
| R1A-05 | 04 | 17 (tuning evidence) |
| R1A-06 | 03, 05 | — |
| R1A-07 | 03, 04, 05 | — |
| R1A-08 | 02, 03, 05 | 07 |
| R1A-09 | 05, 06 | — |
| R1A-10 | 02 (fixture draft) | 06, 07, 08, 09 |
| R1A-11 | 02 + 10 draft | 10, 14 |
| R1A-12 | 11 | — |
| R1A-13 | 11, 02 | — |
| R1A-14 | 01 | 03, 11 |
| R1A-15 | 10, 11 | 12, 13, 14 |
| R1A-16 | 01 | 02–14 (all S-rules covered) |
| R1A-17 | 01 | 02–15 (as needed) |
| R1A-18 | 01 | 14 |
| R1A-19 | 14, 15, 17 | — |
| R1A-20 | 01–19 | — |

### 4.3 Critical path

```
01 → 02 → 03 → 04 → 05 → 06 → 09 → 10 → 15 → 19 → 20
```

- The domain chain 02–06 is strictly sequential; each step consumes the previous model.
- **Near-critical:** the renderer chain `11 → 12/13 → 15` and `14 → 18`. It runs beside the domain chain once the R1A-10 fixture draft exists. If it slips, it becomes critical at R1A-15.
- **R1A-08** sits off the critical path for R1a acceptance but is on the **critical path for R1b**.

### 4.4 Parallelizable groups

| Group | Items | Window |
|---|---|---|
| P1 — foundations | 14 (pipeline start), 16, 17, 18 frameworks | from R1A-01 onward |
| P2 — domain fan-out | 06, 07, 08 | after R1A-05 |
| P3 — compatibility | 09, 08 | after R1A-06 |
| P4 — renderer | 11, then 12 ‖ 13 ‖ 14 integration | after R1A-02 + 10 draft |
| P5 — hardening | 16, 17, 18, 19 | after R1A-15 |

### 4.5 Continuous verification work

R1A-16 (validators/property tests), R1A-17 (fixtures/simulation) and R1A-18 (CI/reproducibility) start at R1A-01 and grow with every item. Each item's evidence must land in these suites, not in one-off scripts. They are completed, not started, at the end.

---

## 5. Known risks and open values

Classification: **BLOCKER** (prevents starting R1a work) · **REQUIRED BEFORE R1A ACCEPTANCE** (must be resolved by R1A-20; does not prevent starting) · **NON-BLOCKING / DEFERRED** (outside the R1a gate, with a destination).

| # | Item | Classification | Handling |
|---|---|---|---|
| 1 | **Central Hall oversized Focus** — the Hall does not fit L1 on tablet/phone | REQUIRED BEFORE R1A ACCEPTANCE | Not a blocker: spec §O specifies the behaviour. Implemented and tested in R1A-12. |
| 2 | **Desktop Overview assumes the ~806 × 484 room box** (spike M01) | REQUIRED BEFORE R1A ACCEPTANCE | A layout test covers it (R1A-12). If the box shrinks, the DOM room-list fallback is allowed and is not a failure. |
| 3 | **New catalog types** `side_table`, `armchair`, `shelf_low`, `project_board`, `marker.idle_spot` | REQUIRED BEFORE R1A ACCEPTANCE | Catalog and validator support in R1A-03 / R1A-14 / R1A-16; the validator accepts a structural marker with no art. |
| 4 | **Closed-room walkability and recovery** | REQUIRED BEFORE R1A ACCEPTANCE (core invariant) | Enforced in R1A-04, R1A-05, R1A-07; property-tested in R1A-16. |
| 5 | **`ms_per_step`** (and turn penalty) PROVISIONAL | REQUIRED BEFORE R1A ACCEPTANCE (a chosen value with evidence) | Does not block early engine work. Tuned with simulation in R1A-17; stays tunable later (ADR-0035 §7). |
| 6 | **Legacy projection route timing** (apparent speed varies per walk) | REQUIRED BEFORE R1A ACCEPTANCE | Cosmetic, but must stay truthful (same `departed_at` / `arrives_at`) and deterministic; R1A-09 tests. |
| 7 | **Linux atlas reproducibility** (deferred from the spike) | REQUIRED BEFORE R1A ACCEPTANCE | R1A-18. |
| 8 | **Real-device mobile QA** | NON-BLOCKING / DEFERRED → **B14 gate** (ADR-0040 §4 item 5) | R1a records EMULATED evidence only. |
| 9 | **Face overlay size (12×6 vs 14×8) / final art** | NON-BLOCKING / DEFERRED → owner blind test (P1) and Art chat; production art at **B14** | Engine parameterises face size; placeholder art only in R1a. |
| 10 | **Default Follow zoom / phase tint colours** | NON-BLOCKING / DEFERRED → owner/art decision (Q4) before **B14** | Engine keeps them configurable; placeholders must keep night contrast ≥ 1.5. |

**Additional risks found while planning** (same classification):

| # | Item | Classification | Handling |
|---|---|---|---|
| 11 | v11 migration accidentally reachable by a production release | REQUIRED BEFORE R1A ACCEPTANCE | R1A-08 production-safety constraint and test. |
| 12 | Fixture/simulated world shown as if it were Maple's real state | REQUIRED BEFORE R1A ACCEPTANCE | R1A-10 / R1A-15 truthfulness constraints (CLAUDE.md §3.9). |
| 13 | Release build missing art inputs (C1) | REQUIRED BEFORE R1A ACCEPTANCE | R1A-14 build input + R1A-18 release-build check. |
| 14 | Turn penalty yields walk lengths different from spec T6 | REQUIRED BEFORE R1A ACCEPTANCE | Recorded as a decision in R1A-05; spec unchanged unless the stop rule applies. |
| 15 | Tailscale Serve identity-header spike | NON-BLOCKING / DEFERRED → before **R4** (ADR-0038 §3) | Not needed for R1a (no owner endpoints). |

**BLOCKER:** none among the design and technical items above. The blockers are the two OPEN pre-R1 gate items (OD-01 restore test, R-01) and R1a authorization, all in §9.

---

## 6. R1a / R1b boundary

### R1a MAY
- implement isolated domain and engine behaviour (world, catalog, walkability, A\*, resolution, slots, projection);
- create fixtures and development data;
- prepare the v11 schema as a **non-shipped candidate** for development and tests;
- create validators and property tests;
- create new read-only APIs and contracts;
- create the feature-flagged renderer;
- preserve the old Room view unchanged as the default;
- test the v11 conversion in rehearsal/scratch contexts on **synthetic** v10 databases;
- run simulation, performance and CI checks;
- update the release build input for art (C1) and CI.

### R1a MUST NOT
- migrate the production Maple world to v11, or make v11 reachable by a production release;
- change the production default Room view;
- remove the legacy view, the legacy projection or `front/back` facing;
- open placeholder rooms in production;
- deploy, or deploy an irreversible production migration;
- change services, production configuration or deployment;
- require final production art;
- bypass any owner approval gate.

### R1b is responsible for
- the rehearsed production migration: v11 on an owner-taken **copy of the production database**, with in-transaction verification and the restore path (ADR-0037 §3);
- registering the v11 migration as shipped and executing the **single** production migration under the owner snapshot gate;
- production state cutover: Maple's backend movement switches to the grid; the legacy fields come from the projection;
- the final production house instantiation (8 regions, 5 open, 3 closed);
- updating the pinned 30-day simulation digest deliberately;
- production verification;
- later, the default-switch process — only when every B14 condition (ADR-0040 §4) is satisfied, in a separate change.

---

## 7. Detailed work-item policy

Before starting **any** individual R1A work item:

1. Review its Master Plan section (§3) and its dependencies (§4).
2. Create a focused implementation breakdown **for that item only** (recorded in the checklist item's "Detailed task plan" field, as a section in the checklist or a linked file under `docs/implementation/`).
3. Record the starting status in the checklist (IN PROGRESS, branch, start commit).
4. Implement.
5. Test.
6. Collect evidence.
7. Update the checklist.
8. Append to the worklog.
9. Update affected docs / ADR / spec if needed (§8).
10. Review before commit.

**Do not create detailed micro-task plans for future work items that are not about to start.** This plan intentionally does not prescribe function names, internal classes or file-by-file edits, except where an accepted architecture document already requires them (e.g. the catalog location in ADR-0036 §2).

**Branches (PROPOSED convention):** one branch per item or tightly coupled pair, `feat/r1a-NN-<slug>`, from `v0.2-development`. Merges follow the existing review practice.

## 8. Documentation policy and the architecture-change stop rule

For **every** R1a implementation or update:

```
Plan current work item
→ Implement
→ Test
→ Collect evidence
→ Update Checklist
→ Append Worklog
→ Update ADR/spec/docs if affected
→ Review
→ Commit
```

**Stop rule.** If implementation discovers that an accepted architecture decision (ADR, locked value, or Final Design Spec geometry) must change:

**STOP implementation.** Then:
1. document the conflict (worklog entry; checklist item set to BLOCKED with the reason);
2. propose an ADR or spec amendment;
3. obtain the required owner approval;
4. update the architecture documents;
5. resume implementation only after the new decision is accepted.

**Never silently drift from the accepted architecture.** PROVISIONAL tuning values (e.g. scoring weights, occupy px offsets, `ms_per_step`, turn penalty) may be set inside an item, with evidence recorded in the worklog; they do not trigger the stop rule unless they change a SPEC or LOCKED value.

## 9. Pre-R1 gate and authorization preconditions

Status updated 2026-10-10 (boundary probe PASS; prior owner decisions recorded in `CLAUDE.md` and `docs/architecture.md`). Preference recorded by the owner: known pre-R1 architectural gates are resolved **before** R1a.

| Precondition | Status | Classification |
|---|---|---|
| **Pre-R1 gate** (future-architecture §22 item 1) | | |
| OD-01: Stage C authorization record | **RESOLVED** 2026-10-09: install of `160ed4f…` retroactively authorized; Stage C stays open; M3 not claimed | — |
| OD-01: Phase 8 status | **RESOLVED** 2026-10-09: not authorized, not started, deferred until Stage C is closed; blocks neither R1a nor R1b (ADR-0009) | — |
| OD-01: inside-service boundary probe (`check_boundaries.py` / `sandbox_probe.sh` for the deployed release) | **RESOLVED** — PASS / CLOSED, recorded 2026-10-10; evidence and limitations in worklog | Met |
| OD-01: restore test (restic restore; restored `maple.db` opens and passes `integrity_check`) | **OPEN** | **BLOCKER** before R1A-01 |
| R-01: journal Brain call inside the writer lock — fixed (separate small PR, §17 M-0) or explicitly accepted by the owner | **OPEN** | **BLOCKER** before R1A-01 |
| **R1a authorization** | | |
| Owner authorization of R1a | **Not given.** BLOCKED until the two OPEN pre-R1 items are resolved | **BLOCKER** for starting R1A-01 |
| **Design baseline** | | |
| Room Final Design Spec approved | Approved in principle (2026-10-09) | Met |
| Technical lock (ADR-0041 L1–L22, C1–C8) | Locked 2026-10-09 | Met |
| ADR-0035..0041 accepted | Accepted 2026-10-08 (amended 2026-10-09) | Met |
| Face size blind test (P1) | Pending | Not required for R1a |
| Tailscale Serve identity spike | Not run | Not required before R4 |
