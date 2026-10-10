# R1A-03 — Object Catalog and Capability Metadata

**Status:** REVIEW / PENDING OWNER ACCEPTANCE (STEP 97, 2026-10-11). Stages B–E complete under explicit owner authorization. No commit/push/merge/deployment authorization. STEP 96 stop evidence below is historical.

## Inputs, dependencies and scope

Use the [Master Plan R1A-03](maple-room-r1a-plan.md#r1a-03--object-catalog-and-capability-metadata), [Final Design Spec](../architecture/maple-room-final-design-spec.md) T3–T5 and §§J/K/S, ADR-0035, [ADR-0036](../adr/0036-object-catalog-and-capabilities.md), ADR-0039 and ADR-0041. Precedence: locked ADR values → accepted ADR rules → Final Design Spec → proposals. The starting development baseline is `37794564d921e69e29b90f47ea8d437d24bd704e`, with R1A-02 merged through PR #2. Original design conversation content was not accessed or claimed verified.

R1A-03 provides immutable catalog/instance metadata and pure validation, loaded from release resources only at an isolated runtime boundary. No production startup wiring, database, API, rendering, pathfinding, movement execution, activity resolution/scoring/Director integration, Storage or placement execution. Slot templates and T5 reference metadata are required by the Master Plan; slot functionality remains R1A-07. No later workstream begins here.

## Metadata contracts

- A release catalog contains unique stable type IDs, ADR-0036 categories, positive integer `geometry_version`, south-orientation footprints, tile-sized blocking masks, supported canonical orientations, capability sets, point/slot templates, states, ownership permissions and placement metadata. Frozen tuples and deterministic ID ordering protect caller input and lookup output; reject duplicates, malformed enum/identifier values, invalid dimensions/masks and unresolved references.
- Keep catalog type definitions separate from layout instances (`id`, `type`, origin, orientation, state, owner and optional link). Initial instances use `south`, `paolo`, and owner-only movement/deletion as specified in §J. The initial resource references **15 types / 28 instances / 17 interaction points / 12 slots**. Transcribe release data from accepted spec sources, independently of test snapshots; do not promote provisional values into ADR locks.
- Reuse R1A-02 coordinate/direction primitives and lighting mount predicates. Floor footprints and blocking masks use integer tiles; east/west swap width/height per art contract B.5. Point coordinates are object-local and rotate with orientation (ADR-0036 §4); tests must cover canonical rotations and legacy compatibility without changing existing Facing or production points.
- Point templates define ID, approach tile and character facing, optional occupy pixel offset/pose/direction, provided capabilities and capacity. Preserve T4 poses and offsets; no arrival/activity execution. `occupy: null` retains the approved on-tile pose/direction metadata. Validate type capabilities and point-provided capabilities without introducing activity candidate selection.
- Use the reviewed capability vocabulary. Option A is exact: Writing Desk/type point `{writing_surface}`, Computer Desk/type point `{computer}`; writing requires only `writing_surface`. Preserve `sit_write` / `sit_monitor`. Other furniture may retain `seat`.
- Slot defaults include the existing accepted classes/capacities/permissions and declared `shares_point` metadata. Per-instance accepts/capacity/permission overrides are accepted by ADR-0039 §2. STEP 97 authorizes explicit per-instance/per-slot approach/facing overrides; no position-derived defaults or named variants. Keep policy overrides separately typed under ADR-0039, reject unknown fields and retain type defaults.
- Geometry-version and art-key checks must distinguish catalog reference/type/orientation validation from real art-manifest validation. R1A-14 owns delivered assets, frame availability and catalog/manifest matching; do not fabricate art manifests or mark provisional geometry production-approved. Structural `marker.idle_spot` needs no art.

## Validation ownership and acceptance evidence

| Rule | R1A-03 responsibility | Deferred responsibility |
|---|---|---|
| S6 | Valid floor footprints within one room; blocking masks non-overlapping; exact initial 34 blocking tiles and 7/6/7/14/0 room counts | R1A-04 walkability/collision engine |
| S7 | Validate wall metadata using R1A-02 plain-band and exterior-window predicates; reject side walls, passages and invalid bands | Renderer and placement operations |
| S8 | Valid point/slot metadata and declared references; T4/T5 equality, after approach-policy resolution | R1A-04/05 walkability/reachability; R1A-07 full slot reuse/placement validation |
| S9 | Provider metadata exists for approved requirements, including Option A; no selection or path search | R1A-06 reachable candidates, scoring and allowed actions |
| S15 | Exact disjoint desk capabilities and point provides, with positive/negative tests | No relaxation of disjointness |
| S16 | Initial instances are owner-controlled; no Maple-movable furniture | R1A-07 placement authorization |
| S17 | Every referenced type/state/orientation exists; valid geometry version and art reference metadata | R1A-14 actual art manifest/version/frame validation |

Positive and negative tests must cover identifier uniqueness, type existence, footprint/mask dimensions, invalid orientations/states/owners, malformed capabilities, point metadata, immutability, deterministic input-order-independent output, S6/S7 geometry failures, desk disjointness and poses, and the structural marker's no-art exception. Compare exact T3/T4/T5 cells without modifying further Oracle values. Preserve T1/T2, initial layout resource, all walk lengths and the simulation pin.

## Sequential implementation checkpoints

1. STEP 97 resolves the schema gate: separate explicit geometry overrides from ADR-0039 policy overrides. Validate local signed coordinates/direction, rotation, world/host-room bounds and same-host reuse; do not claim full reachability.
2. Add frozen pure-domain values, canonical ordering, lookup and generic geometry/rotation validation. Gate: focused positive/negative unit tests plus strict type/lint checks.
3. Independently transcribe accepted initial catalog/instance metadata and implement a strict isolated resource reader. Gate: exact T3/T4/T5 comparisons, S6/S7/S15/S16/catalog-S17, packaging inclusion and isolated wheel loading.
4. Run the focused new/world/regression/import/security checks, Ruff lint/format, targeted strict mypy and diff checks. Reuse unaffected simulation evidence; no automatic full gate or simulation run.
5. Review combined scope and update evidence. Set REVIEW only after all R1A-03-owned conditions pass; DONE requires owner acceptance and repository integration.

Implemented module locations: `core/world/catalog.py` for immutable metadata and validation, `runtime/world_catalog.py` for release loading, `world_catalog/` JSON resources and `tests/world/test_catalog.py`. These follow the approved pure-core/runtime boundary; file names are implementation choices, not new architecture mandates.

## Historical STEP 96 ambiguity and STEP 97 resolution

[ADR-0036 §2](../adr/0036-object-catalog-and-capabilities.md#2-furniture-registry-catalog-plus-instances-a3) puts slot templates on types; instance fields have no explicit template selector or approach override. [ADR-0039 §2](../adr/0039-storage-and-maple-slot-placement.md#2-slot-only-placement-through-r3r5-b11) permits overrides for accepts, capacity and `maple_may_place`; it does not clearly extend that permission to approach/facing geometry. The Master Plan R1A-07 lists approach data on instances but does not define its relationship to per-type templates. These accepted rules leave the following initial data's representation materially underspecified:

| Instance (all `furniture.side_table`, orientation `south`) | T3 origin | T5 `top` approach / facing | Object-local approach |
|---|---|---|---|
| `bedside.bedroom` | (3,3) | (4,3), left | (1,0), left |
| `side_table.living` | (10,5) | (10,6), up | (0,1), up |
| `side_table.library` | (23,7) | (23,8), up | (0,1), up |

One south-oriented `top` geometry template cannot produce all three without an explicit override/variant rule. Library accepts/capacity differences are already covered by ADR-0039 and are not the blocker. All existing T3/T5 cells must stay unchanged under STEP 96's five-cell Oracle limit.

Historical options considered in STEP 96:

- **A — explicit instance approach/facing overrides (recommended):** authorize a narrowly validated override of slot approach/facing, retaining type defaults, all current IDs/orientations/geometry and T5 values. Define validation and any geometry-version implications before implementation.
- **B — named approach variants:** authorize type-declared slot geometry variants and an instance selector, preserving current IDs/orientations/geometry and T5 values. Define selection and geometry-version rules before implementation.

Do not change orientations, type IDs, T5 geometry or Oracle expectations to avoid this decision. No accepted ADR amendment is made in STEP 96. This is a planning/schema gate, not a regression or failure of Option A.

## Historical STEP 96 evidence and stop state

Stage A PASS: exactly five approved Oracle cells changed, all other data/order/headers preserved; directly affected Oracle/Harness/initial-layout tests **76 passed / 0 failed**. See [worklog](maple-room-r1a-worklog.md) for the command and exact cell list. Stage B is DRAFT / BLOCKED by the approach-policy decision; Stages C–E are not performed. No new catalog code, release resources or test implementations exist, and no packaging/static runtime PASS is claimed. R1A-03 remains TODO / PLANNING BLOCKED, not REVIEW or DONE.


## STEP 97 accepted resolution and implementation details

Option A is owner approved; the STEP 96 gate above is closed. A `SlotOverride` names exactly one existing slot and carries optional local approach and/or facing; at least one must be set. Policy overrides are separate values limited to ADR-0039 accepts/capacity/permission fields. Duplicate/unknown overrides and undeclared fields are rejected. Resolution does not mutate type metadata.

Use `core/world/catalog.py` for immutable catalog types/lookup/transform/assembly, `runtime/world_catalog.py` for strict JSON parsing and isolated shipped-resource loading; `world_catalog/initial_catalog.json` declares types and instances. No runtime entry point consumes it. The initial supported catalog orientation is `south` (spec initial delivery); generic quarter-turn transforms and validation are tested for all four declared orientations using synthetic types. `geometry_version = 1` denotes the initial provisional reference revision, not production art approval. Art IDs reference the accepted type IDs; actual manifests/frame coverage remain R1A-14. Categories, masks and `default` states are reference metadata, not new locked art values.

`LocalPoint` supports signed object-local tile/pixel offsets without file/time/randomness access. Clockwise image-grid quarter turns map south→west→north→east, transform footprint/mask/local approach and character directions consistently; occupy pixel vectors rotate about the object anchor. No renderer anchor/canvas behavior is implemented. Wall origins are their north band's top-left columns; mount offsets remain separate pixel metadata.

Completion evidence must show exact T3/T4/T5 equality, 15 types/28 instances/17 points/12 slots, 34 blocking tiles (7/6/7/14/0), explicit bedside override, unchanged T1/T2 and five-cell Oracle limit; catalog-only S6/S7/S8/S9/S15/S16/S17 tests, import/purity checks, strict typing and wheel resource loading. Full reachability/collision engine/keep-clear (04/05), resolver/scoring (06), placement/Storage (07), persistence/API/renderer/art (08–15) stay deferred.


## STEP 97 consolidated acceptance evidence

- Stage B PASS: Option A accepted and amended in ADR-0036/0039 and spec §L. No T5 cell changes or new type/variant. The historical ambiguity above is resolved.
- Stage C PASS: frozen, validated pure catalog/type/instance/point/slot/override metadata, canonical ID ordering, quarter-turn transforms, S6/S7 geometry and static S8 coincidence/reuse validation. Explicit geometry overrides are separate from existing ADR-0039 policy overrides; unknown/duplicate/empty/malformed declarations fail. All 15 types, 28 instances, 17 points, 12 slots and 34 blocking tiles are present. Full T3/T4/T5 equality and 29 approach references / 26 distinct tiles / 3 declared reuses PASS.
- Stage D PASS: **510 passed / 0 failed** in the consolidated focused suite, comprising 130 new catalog cases plus 380 existing world/Oracle/Harness/security/legacy-room cases. `ruff check --no-cache` and `ruff format --check` PASS (3 new Python files); strict mypy PASS (25 files); 10 import contracts kept / 0 broken. Offline wheel build PASS; initial catalog/house resource byte equality, snapshot exclusion and isolated Python `-I` wheel-only loading PASS. Commands and fixture correction details are in the append-only worklog.
- Stage E PASS: only five authorized Oracle data cells differ from baseline. All other Oracle cells/headers/order, T1/T2 and initial-house resource, approved T3/T4/T5 geometry/poses, existing runtime entry points, legacy Facing, schema and simulation pin remain unchanged. No API/renderer/production activation or later workstream implementation. No full release gate or simulation rerun needed: no simulation dependency path changes. `git diff --check` and documentation consistency checks PASS.

R1A-03 is ready for owner acceptance review; DONE and repository integration are not claimed. Actual art manifests/version matches/frame availability and final provisional art geometry remain R1A-14 review dependencies. Full walkability, reachability, keep-clear, resolver and placement behavior remain assigned to later workstreams; metadata provider coverage is not reachable-candidate acceptance. No additional owner decision blocker found.
