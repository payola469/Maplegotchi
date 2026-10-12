# R1B-01 — Contract Inventory and Compatibility Decisions

## 1. Scope and current status

**STEP162 — R1B-01 REVIEW / ACCEPTED FOR INTEGRATION REVIEW / MERGE PENDING.** Owner accepts STEP161 local work for final publication review, subject to fresh validation, and authorizes documentation corrections, reviewed commit, normal push, PR and CI inspection for01 only. Separate owner merge approval is required. R1B-02–12 remain11TODO;0/12DONE=0%. D01–D06 OPEN; no projection strategy or future implementation approved. No runtime/test changes, schema11 registration/activation, DB migration/data access, production/paolo-core, deployment, default switch, repin, B14 orR4. Earlier dated authorization/evidence below is historical. [R1B-01 inventory](maple-room-r1b-01-contract-inventory.md).

**STEP161, 2026-10-12 — LOCAL PASS / REVIEW pending separate owner acceptance.** Bounded G2 authorizes R1B-01 documentation, source inspection, existing-contract verification and test-case planning only. No runtime/test implementation or contract change. R1B-02–12 remain 11 TODO; R1b completion 0/12 DONE = 0%. D01–D06 remain OPEN. No projection strategy selected. Publication P is NOT granted for this batch; no stage, commit, push, PR or merge.

## 2. Verified baseline and repository boundary

Repository origin is https://github.com/payola469/Maplegotchi.git. Fetched origin/v0.2-development exactly `edb6b128e41590d2822bdbe41c16e68d3f634206`; PR22 merge confirmed2026-10-12T15:33:36Z, parents 3e89996216336f453b03939467e6a06cb33da3fb and da322dc6aa7b90fe6174f190069dc97f372a4729. Existing 8 worktrees were clean. Created isolated `C:/GitHub/Maplegotchi-worktrees/r1b-01-contract-inventory`, branch `codex/r1b-01-contract-inventory`, at that exact integration commit. No end commit exists for this uncommitted work.

Main remains clean at 3e89996216336f453b03939467e6a06cb33da3fb; planning worktree remains clean at da322dc6aa7b90fe6174f190069dc97f372a4729. Automatic approval review rejected the combined main-fast-forward/setup command as a prohibited merge; nothing in that command executed. The permitted worktree-only alternative succeeded. No reset, rebase, force operation or other branch update. Main need not move to inspect the verified baseline in this isolated worktree.

## 3. Authority and reference map

Accepted design is not automatically implemented behavior. Precedence: locked owner/ADR rules, accepted ADRs, Final Spec and reviewed proposals. Historical evidence remains attributed to its original run; future proof is explicitly missing until authorized.

| Authority | Relevant contract / boundary |
|---|---|
|[CLAUDE](../../CLAUDE.md)|Fixed decisions, current bounded STEP161 scope; older dated authorization/deployment statements historical|
|[Final Design Spec](../architecture/maple-room-final-design-spec.md)|K/L/M/N/R/S and T1–T7: geometry, capabilities, slots, projection and fixed migration mapping|
|[ADR0035](../adr/0035-world-model.md)|Grid geometry, movement/recovery, directions, feet/timing|
|[ADR0036](../adr/0036-object-catalog-and-capabilities.md)|Backend catalog ownership, capability resolution, task separation, narrow STEP97 overrides|
|[ADR0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md)|Persistence, lookup tables, single final-house cutover, Legacy projection; exact schema proposed|
|[ADR0038](../adr/0038-owner-edit-mode-and-owner-authentication.md)|R4 auth/editor deferred; no new owner endpoint authority|
|[ADR0039](../adr/0039-storage-and-maple-slot-placement.md)|Slot-only validation/derived Storage; no game inventory or R1b placement execution|
|[ADR0040](../adr/0040-room-view-transition-and-acceptance-gate.md)|Legacy default, all 10 B14 criteria, later removal after one full release|
|[ADR0041](../adr/0041-art-technical-contract.md)|Locked device-pixel/atlas/geometry/render-only contracts; final art/device decisions separate|
|[ADR0027](../adr/0027-room-interaction-points-and-movement.md)|Legacy movement semantics retained on geometry transition|
|[ADR0028](../adr/0028-activity-set-v2-events-and-schema-v4.md),[0023](../adr/0023-release-and-runtime.md),[0024](../adr/0024-maple-database-backup.md)|Forward-only atomic migration, snapshots, owner restoration, release boundary|
|[R1b Master Plan](maple-room-r1b-plan.md),[Checklist](maple-room-r1b-checklist.md),[Safety](maple-room-r1b-migration-safety.md),[Cutover](maple-room-r1b-cutover-plan.md),[Risks](maple-room-r1b-risk-gates.md)|Accepted 12 workstreams, acyclic dependencies, 22 risks, G1–G7/separateP, D01–D06 OPEN|
|[R1A-08](maple-room-r1a-08-persistence-v11.md),[R1A-09](maple-room-r1a-09-legacy-projection.md),[R1A-10](maple-room-r1a-10-world-api-contracts.md),[R1A-15](maple-room-r1a-15-coexistence.md)|Historical synthetic rehearsal, rejection acceptance, fixture contracts and Legacy Pixi preservation|

## 4. Implemented contract inventory

**24 contracts, C01–C24.** Each record identifies accepted design, current code/current behavior, future target, invariant, existing evidence, missing evidence, downstream impact and owner gate. Code line links identify the actual symbols at the verified baseline. Evidence links identify existing test definitions, not a claim that those suites ran STEP161.

<a id="c01"></a>

### C01 — Coordinates and direction vocabulary

**Status / classification:** isolated implemented library; live integration unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C01
- **Owning component:** Pure world values
- **Accepted design reference:** [ADR-0035](../adr/0035-world-model.md) §2/5/6; ADR-0041 L1/L4
- **Implemented code reference:** [Tile](../../backend/src/maplegotchi/core/world/coordinates.py#L21); [tile_to_feet](../../backend/src/maplegotchi/core/world/coordinates.py#L34)
- **Current behavior:** Integer tx/ty, 44×26, T=16, feet=(8, 13); bool/coercion/out-of-range rejected. Character and object direction vocabularies remain distinct.
- **Required future behavior:** Persist tile/route truth and derive pixels; retain legacy facing until separate removal.
- **Compatibility invariant:** No pixel-to-tile rounding as authoritative state; front/back is compatibility vocabulary.
- **Existing evidence:** [test_tile_bounds_and_feet](../../backend/tests/world/test_primitives.py#L31); [test_direction_order_and_legacy_vocabulary_are_unchanged](../../backend/tests/world/test_primitives.py#L165)
- **Missing evidence:** Live v11 state/API roundtrip not implemented.
- **Impacted R1b workstreams:** 02, 04, 05, 07
- **Applicable owner gate:** Future bounded G2; D02/D03

<a id="c02"></a>

### C02 — House topology, walkability and recovery

**Status / classification:** isolated implemented library; live integration unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C02
- **Owning component:** Pure layout/walkability
- **Accepted design reference:** [ADR-0035](../adr/0035-world-model.md) §2–4; Final Spec K/S/T1–T2
- **Implemented code reference:** [validate_safe_layout](../../backend/src/maplegotchi/core/world/walkability.py#L141)
- **Current behavior:** Canonical layout and prevention/recovery exist in isolated libraries; 431-cell open component, closed floors/passages forbidden.
- **Required future behavior:** Use validated canonical final house directly at single cutover; recorded relocation only on approved emergency recovery.
- **Compatibility invariant:** 8 regions, 5 open, 3 closed, 7 door corridors; K1–K3 protection, K4 dynamic connectivity; never unsafe fallback.
- **Existing evidence:** [Walkability tests](../../backend/tests/world/test_walkability.py); [layout validator/property tests](../../backend/tests/world/test_layout_validation.py)
- **Missing evidence:** No live recovery-event persistence or production house activation.
- **Impacted R1b workstreams:** 02, 04, 06–12
- **Applicable owner gate:** Future G2; G4/G5/G6

<a id="c03"></a>

### C03 — Catalog and backend geometry ownership

**Status / classification:** isolated implemented library; live integration unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C03
- **Owning component:** Runtime resource readers / pure catalog
- **Accepted design reference:** [ADR-0036](../adr/0036-object-catalog-and-capabilities.md) §1–2/4; STEP97 slot overrides
- **Implemented code reference:** [build_catalog_layout](../../backend/src/maplegotchi/core/world/catalog.py#L466); [load_initial_catalog](../../backend/src/maplegotchi/runtime/world_catalog.py#L233)
- **Current behavior:** Frozen catalog/instances; strict release-resource parsing; local approaches resolve to absolute tiles; occupy remains anchor-relative px.
- **Required future behavior:** Reuse canonical geometry/versioned resources in persistence/runtime; frontend consumes resolved metadata.
- **Compatibility invariant:** No second geometry truth. Geometry overrides are confined to explicit named-slot approach/facing metadata; existing accepts/capacity/permission policy follows ADR-0039. Never infer an override.
- **Existing evidence:** [Catalog tests](../../backend/tests/world/test_catalog.py); [Oracle tables](../../backend/tests/world/approved_tables.json)
- **Missing evidence:** Final production furniture/art versions require later review; live integration absent.
- **Impacted R1b workstreams:** 01–05, 07, 09
- **Applicable owner gate:** G2 for each future scope; D02; separate art/B14 review

<a id="c04"></a>

### C04 — Compressed grid routes and deterministic pathfinding

**Status / classification:** isolated implemented library; live integration unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C04
- **Owning component:** Pure pathfinding
- **Accepted design reference:** [ADR-0035](../adr/0035-world-model.md) §3; Final Spec T6
- **Implemented code reference:** [Route](../../backend/src/maplegotchi/core/world/pathfinding.py#L42); [find_route](../../backend/src/maplegotchi/core/world/pathfinding.py#L112)
- **Current behavior:** Immutable orthogonal compressed waypoints; cumulative steps match Manhattan lengths; integer deterministic A*, turn penalty1; zero-step route valid.
- **Required future behavior:** Use grid route in future authoritative life, without editing accepted tuning/pins for convenience.
- **Compatibility invariant:** No teleport on unreachable destination; no hierarchy/cache absent profiling; invalid segments rejected.
- **Existing evidence:** [test_canonical_t6](../../backend/tests/world/test_pathfinding.py#L36); [test_invalid_route_contract](../../backend/tests/world/test_pathfinding.py#L171)
- **Missing evidence:** No integrated live route persistence/restart proof.
- **Impacted R1b workstreams:** 02, 04, 06, 07
- **Applicable owner gate:** Future G2; D01 before04; D05 before pin changes

<a id="c05"></a>

### C05 — Travel timing and phases

**Status / classification:** isolated implemented library; live integration unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C05
- **Owning component:** Pure movement
- **Accepted design reference:** [ADR-0035](../adr/0035-world-model.md) §3; ADR-0027 movement semantics
- **Implemented code reference:** [Travel](../../backend/src/maplegotchi/core/world/movement.py#L72)
- **Current behavior:** Supplied UTC time; 250 ms default/step; arrival = steps×step_us plus optional entry duration; pending/walking/performing derived; activity starts at arrival.
- **Required future behavior:** Preserve exact timing across committed runtime/API/restart.
- **Compatibility invariant:** No inferred clock or animation-owned arrival; 317 ms in projection fixture is a deliberate test override, not production tuning.
- **Existing evidence:** [test_zero_length_and_phase](../../backend/tests/world/test_pathfinding.py#L184); [test_integer_interpolation_four_directions](../../backend/tests/world/test_pathfinding.py#L199)
- **Missing evidence:** Live scheduling, catch-up and all activity-boundary integration missing.
- **Impacted R1b workstreams:** 04–07, 11, 12
- **Applicable owner gate:** Future G2; D01; G5/G6

<a id="c06"></a>

### C06 — Exact mid-edge rerouting

**Status / classification:** isolated implemented library; live integration unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C06
- **Owning component:** Pure movement / projection boundary
- **Accepted design reference:** [ADR-0035](../adr/0035-world-model.md) §3; ADR-0037 §4
- **Implemented code reference:** [reroute](../../backend/src/maplegotchi/core/world/movement.py#L146); [EdgeStart](../../backend/src/maplegotchi/core/world/movement.py#L22)
- **Current behavior:** Reroute preserves transient exact microsecond edge progress, compares both endpoints; Travel entry is valid pure grid input but Legacy projection rejects every non-null entry.
- **Required future behavior:** Prove reachable reroute/restart compatibility after an explicitly approved D01 decision.
- **Compatibility invariant:** Do not round current position, invent an anchor or silently discard remaining travel.
- **Existing evidence:** [test_mid_route_replanning](../../backend/tests/world/test_pathfinding.py#L238); [test_repeated_mid_entry_rerouting](../../backend/tests/world/test_pathfinding.py#L268)
- **Missing evidence:** No approved Legacy representation of ambiguous mid-edge origin; one existing rejection fixture is not exhaustive live proof.
- **Impacted R1b workstreams:** 04, 05; transitive06–12
- **Applicable owner gate:** D01 OPEN; future G2; G4/G5

<a id="c07"></a>

### C07 — Current life and runtime authority

**Status / classification:** current shipped behavior; future world integration or later-stage changes unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C07
- **Owning component:** MapleState / LifeRuntime / repositories
- **Accepted design reference:** [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) §1/3–4
- **Implemented code reference:** [MapleState](../../backend/src/maplegotchi/core/state.py#L125); [LifeRuntime](../../backend/src/maplegotchi/runtime/life.py#L243)
- **Current behavior:** Live life still uses RoomLocation, legacy point and legacy Route; arrival ties to activity_started_at. Grid libraries are isolated.
- **Required future behavior:** Grid becomes sole backend authority at approved cutover; Legacy is derived; preserve needs/RNG/actions/goals/tasks/reactions.
- **Compatibility invariant:** No parallel simulation, second writer or contradictory stored location.
- **Existing evidence:** [Legacy restart tests](../../backend/tests/runtime/test_movement_runtime.py); [repository tests](../../backend/tests/storage/test_repository.py)
- **Missing evidence:** Authoritative v11 runtime/restart/catch-up and committed-grid compatibility absent.
- **Impacted R1b workstreams:** 02, 04–12
- **Applicable owner gate:** D01 before04; future G2; G4/G5/G6

<a id="c08"></a>

### C08 — Existing Legacy anchors and waypoint walker

**Status / classification:** current shipped behavior; future world integration or later-stage changes unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C08
- **Owning component:** Legacy core room / frontend
- **Accepted design reference:** [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) §4; Final Spec N/R/T7
- **Implemented code reference:** [Route](../../backend/src/maplegotchi/core/room.py#L263); [anchors](../../frontend/src/room/layout/anchors.ts)
- **Current behavior:** Nine legacy points and existing graph/1000×600 presentation remain authoritative for current runtime.
- **Required future behavior:** Keep renderer/anchors/walker intact while projecting same committed future truth.
- **Compatibility invariant:** No fabricated graph loop, Hall substitution or compatibility rewrite from this inventory.
- **Existing evidence:** [Legacy room tests](../../backend/tests/core/test_room.py); [movement tests](../../backend/tests/core/test_movement.py)
- **Missing evidence:** Live grid projection integration still gated; old renderer expansion explicitly deferred.
- **Impacted R1b workstreams:** 04, 05, 07, 11, 12
- **Applicable owner gate:** D01; future G2; later G7 for default switch

<a id="c09"></a>

### C09 — Pure projection mapping and presentation

**Status / classification:** isolated implemented library; live integration unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C09
- **Owning component:** Pure legacy_projection
- **Accepted design reference:** [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) §4; Final Spec N/T7/S14
- **Implemented code reference:** [project_point](../../backend/src/maplegotchi/core/world/legacy_projection.py#L157); [project](../../backend/src/maplegotchi/core/world/legacy_projection.py#L255)
- **Current behavior:** Explicit DevelopmentWorld and presentation; capability-based read/think; named sleep/rest/write/observe andHall idle/walk mappings; caller facts pass through unchanged.
- **Required future behavior:** Emit truthful Legacy compatibility fields from one committed grid snapshot after D01/D03 review.
- **Compatibility invariant:** Exact departure/arrival and activity start; existing allowed_actions; no events, mutation or independent presentation rules.
- **Existing evidence:** [test_t7_and_s14](../../backend/tests/world/test_legacy_projection.py#L124); [test_passthrough_and_immutable](../../backend/tests/world/test_legacy_projection.py#L290)
- **Missing evidence:** No live caller; validator composition remains isolated; new pose rendering and full live truth unproven.
- **Impacted R1b workstreams:** 04, 05, 07, 11, 12
- **Applicable owner gate:** D01/D03; future G2; G4/G6

<a id="c10"></a>

### C10 — Projection rejection surface and 400-pair corpus

**Status / classification:** isolated implemented library; live integration unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C10
- **Owning component:** Pure projection / independent fixtures
- **Accepted design reference:** [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) §4; accepted R1A-09 STEP120
- **Implemented code reference:** [_project_route](../../backend/src/maplegotchi/core/world/legacy_projection.py#L217)
- **Current behavior:** 334 timed, 26zero, 40positive-step same-anchor refusals across20×20 fixture cases; non-null entry refused before route projection. Unknown/unusable/forbidden/inconsistent inputs also refuse.
- **Required future behavior:** Owner-approved safe compatibility must cover all reachable live states, including transient origins, without silently relaxing accepted rejection.
- **Compatibility invariant:** D01 remainsOPEN; 400provider cases do not exhaust all runtime states.
- **Existing evidence:** [test_all_provider_pairs_timing_boundaries_and_determinism](../../backend/tests/world/test_legacy_projection.py#L232); [test_invalid_travel_or_inputs](../../backend/tests/world/test_legacy_projection.py#L351)
- **Missing evidence:** No selected strategy; no exhaustive future runtime-reachable transient/catch-up proof.
- **Impacted R1b workstreams:** Direct04/05; transitive06–12
- **Applicable owner gate:** D01 OPEN; future G2; G4/G5

<a id="c11"></a>

### C11 — Shipped v10 registry and startup

**Status / classification:** current shipped behavior; future world integration or later-stage changes unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C11
- **Owning component:** Storage migrations / database open
- **Accepted design reference:** [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) §2–3; ADR-0028 R1–R8
- **Implemented code reference:** [MIGRATIONS](../../backend/src/maplegotchi/storage/migrations.py#L707); [open_life_database](../../backend/src/maplegotchi/storage/db.py#L199)
- **Current behavior:** Registry1–10; too-new schema refuses; older supported source gets automatic copy before migration; missing file may create a first life.
- **Required future behavior:** Freeze1–10; review11/new loaders/startup as separate09release change; production preflight must refuse wrong/missing source.
- **Compatibility invariant:** Registering11 makes startup eligible; renderer flag cannot guard DB migration.
- **Existing evidence:** [test_shipped_registry_startup_and_too_new_guard](../../backend/tests/rehearsal/test_v11.py#L374); [v10 tests](../../backend/tests/storage/test_migration_v10.py)
- **Missing evidence:** No shipped11/production-safe new loader or current source preflight proof.
- **Impacted R1b workstreams:** 02, 03, 07, 09–12
- **Applicable owner gate:** D02; future G2; separate P; G4/G5

<a id="c12"></a>

### C12 — Synthetic rehearsal capability guard

**Status / classification:** test-only unshipped candidate; normal v11 runtime integration unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C12
- **Owning component:** Test-only rehearsal factory
- **Accepted design reference:** [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) §3; accepted R1A-08 isolation
- **Implemented code reference:** [guarded](../../backend/tests/rehearsal/fixtures.py#L83); [synthetic_life](../../backend/tests/rehearsal/fixtures.py#L111)
- **Current behavior:** Only live registered owned synthetic handles; reject arbitrary paths/connections, forged/expired handles and changed inode/symlink/lifetime.
- **Required future behavior:** Retain guard; separately reviewed trusted-copy adapter and G3 before any real-data input.
- **Compatibility invariant:** Ignored var is not a real-data permission; no weakened factory to accept owner copies.
- **Existing evidence:** [test_external_inputs_cannot_enter_rehearsal](../../backend/tests/rehearsal/test_v11.py#L344); [test_fixture_factory_rejects_external_path](../../backend/tests/rehearsal/test_v11.py#L514)
- **Missing evidence:** No approved real-copy adapter or actual data rehearsal.
- **Impacted R1b workstreams:** 03, 07, 08, 09
- **Applicable owner gate:** Future G2 synthetic scope; G3 for real copies

<a id="c13"></a>

### C13 — Fixed legacy-to-grid migration mapping

**Status / classification:** test-only unshipped candidate; normal v11 runtime integration unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C13
- **Owning component:** Test-only converter
- **Accepted design reference:** [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) §3; Final Spec R
- **Implemented code reference:** [POINT_MAP](../../backend/tests/rehearsal/v11.py#L53); [rehearse](../../backend/tests/rehearsal/v11.py#L425)
- **Current behavior:** Nine identities map via catalog approaches; null point uses canonical old point; in-flight route becomes destination zero-length plan with departure=arrival=old scheduled arrival.
- **Required future behavior:** Preserve approved mapping and continuity in separately reviewed unshipped03 and later real-copy/shipped paths.
- **Compatibility invariant:** Migration exception is not a normal runtime teleport/projection strategy; emit no fabricated events.
- **Existing evidence:** [test_round_trip_preserves_every_row_and_continuity](../../backend/tests/rehearsal/test_v11.py#L78); [R1A-08 mapping evidence](maple-room-r1a-08-persistence-v11.md)
- **Missing evidence:** No migration run in STEP161; real-source coverage and durable-host behavior missing.
- **Impacted R1b workstreams:** 02, 03, 08, 09, 11
- **Applicable owner gate:** D02; future G2; G3; G4/G5

<a id="c14"></a>

### C14 — Candidate transaction, conservation and retry

**Status / classification:** test-only unshipped candidate; normal v11 runtime integration unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C14
- **Owning component:** Test-only converter / storage discipline
- **Accepted design reference:** [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) §3; ADR-0028 R1–R8
- **Implemented code reference:** [rehearse](../../backend/tests/rehearsal/v11.py#L425)
- **Current behavior:** Capture, verified automatic copy, BEGIN IMMEDIATE, DDL/rebuild, FK/core/full-row/sequence verification, version bump thenCOMMIT; rollback on controlled failure.
- **Required future behavior:** Add reviewed process-kill/unknown-commit/disk-full/source-drift proof before real cutover; version-aware once-only startup.
- **Compatibility invariant:** No automatic restore, downgrade, blind retry or invented history; code rollback differs from DB restoration.
- **Existing evidence:** [test_one_immediate_transaction_and_version_bump_last](../../backend/tests/rehearsal/test_v11.py#L498); [test_atomic_rollback_and_usable_v10](../../backend/tests/rehearsal/test_v11.py#L151)
- **Missing evidence:** Injected pre-commit failure is not acknowledgment-loss/power-fault proof; no current real-copy restore evidence.
- **Impacted R1b workstreams:** 03, 07–12
- **Applicable owner gate:** D02/D04/D06; future G2; G3–G6

<a id="c15"></a>

### C15 — Layout revisions, active pointer and identity indexes

**Status / classification:** test-only unshipped candidate; normal v11 runtime integration unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C15
- **Owning component:** Candidate persistence / pure layout
- **Accepted design reference:** [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) §1; ADR-0038 §4 future revert
- **Implemented code reference:** [load_candidate](../../backend/tests/rehearsal/v11.py#L205)
- **Current behavior:** Append-only revision and derived key indexes; singleton world_state active_revision; life_state revision must match; canonical document/hash/catalog/index consistency enforced.
- **Required future behavior:** Reviewed D02 v11 loader reconstructs one authoritative validated revision; edits/revert remain separate R4.
- **Compatibility invariant:** Layout ID, catalog version/hash, life revision and fixture hash are distinct namespaces; no duplicated geometry tables.
- **Existing evidence:** [test_revision_revert_is_new_record_and_indices_are_authoritative](../../backend/tests/rehearsal/test_v11.py#L428); [test_candidate_loader_rejects_invalid_state](../../backend/tests/rehearsal/test_v11.py#L290)
- **Missing evidence:** Only candidate loader exists; exact schema, JSON bounds/versioning and live snapshot correlation undecided.
- **Impacted R1b workstreams:** 02–05, 07–12
- **Applicable owner gate:** D02/D03; future G2; separate R4 authorization

<a id="c16"></a>

### C16 — World DTO identity and snapshot revisions

**Status / classification:** implemented fixture DTO/router boundary; successful live world contract unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C16
- **Owning component:** World fixture DTO/serializer
- **Accepted design reference:** [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) PROPOSED DTOs; accepted R1A-10
- **Implemented code reference:** [WorldIdentityOut](../../backend/src/maplegotchi/api/world_models.py#L46); [WorldSnapshotOut](../../backend/src/maplegotchi/api/world_models.py#L140)
- **Current behavior:** r1a-10.v1; development_fixture/synthetic literals; layout_revision fixture content hash, catalog_version content hash; world snapshot has string world_revision.
- **Required future behavior:** Define truthful distinct live source/status/revision/version policy under D03; one committed consistent snapshot.
- **Compatibility invariant:** Never relabel fixture content or reuse fixture hash as DB active revision; do not invent missing live fields.
- **Existing evidence:** [test_shared_identity_idle_route_and_immutability](../../backend/tests/api/test_world_api.py#L253); [test_dtos_reject_wrong_source_and_unknown_fields](../../backend/tests/api/test_world_api.py#L350)
- **Missing evidence:** No accepted live DTO or revision correlation; current WorldOut lacks live needs/journal/interaction availability.
- **Impacted R1b workstreams:** 01, 05, 07, 11, 12
- **Applicable owner gate:** D03 before05; future G2; G4/G6

<a id="c17"></a>

### C17 — Read-only world API and production unavailability

**Status / classification:** implemented fixture DTO/router boundary; successful live world contract unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C17
- **Owning component:** API routers / explicit fixture app
- **Accepted design reference:** [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) PROPOSED additive GETs; R1A-10
- **Implemented code reference:** [unavailable_world_router](../../backend/src/maplegotchi/api/world_routes.py#L14); [create_fixture_app](../../backend/src/maplegotchi/api/world_fixtures.py#L258)
- **Current behavior:** Normal /api/world,/catalog,/placements GETs503; explicit fixture app serves synthetic truth under profile checks; no normal fixture injection.
- **Required future behavior:** Future separately reviewed live GETs use authoritative world; preserve /api/room,/snapshot and security.
- **Compatibility invariant:** Fixture and live app boundaries remain distinct; reads do not mutate or synthesize life/events.
- **Existing evidence:** [test_live_v10_never_exposes_fixtures](../../backend/tests/api/test_world_api.py#L92); [test_fixture_app_has_no_live_state_or_event_surface](../../backend/tests/api/test_world_api.py#L193)
- **Missing evidence:** Live world GET implementation and exact compatibility export changes unapproved.
- **Impacted R1b workstreams:** 05, 07, 09, 11, 12
- **Applicable owner gate:** D03; future G2; P/G4/G5

<a id="c18"></a>

### C18 — Existing SSE replay and revision semantics

**Status / classification:** current shipped behavior; future world integration or later-stage changes unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C18
- **Owning component:** Legacy stream / EventHub
- **Accepted design reference:** [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) §4 compatibility; accepted R1A-10 SSE deferral
- **Implemented code reference:** [event_stream](../../backend/src/maplegotchi/api/stream.py#L47); [EventHub](../../backend/src/maplegotchi/runtime/events.py#L42)
- **Current behavior:** boot-seq event IDs, bounded replay, foreign/malformed/old IDs resync snapshot; keepalive comments; legacy payloads; no world SSE.
- **Required future behavior:** Preserve existing meanings; only demonstrated need and D03 review may add world events/revision ordering/resync.
- **Compatibility invariant:** SSE sequence is not persisted layout ID or life revision; read-only waiting never holds writer lock.
- **Existing evidence:** [test_reconnect_with_last_event_id_replays_only_what_was_missed](../../backend/tests/api/test_sse.py#L157); [test_waiting_client_does_not_hold_the_writer_lock](../../backend/tests/api/test_sse.py#L235)
- **Missing evidence:** No accepted world SSE contract or live cross-revision/reconnect proof.
- **Impacted R1b workstreams:** 05, 07, 11, 12
- **Applicable owner gate:** D03; future G2; security compatibility review

<a id="c19"></a>

### C19 — Capabilities, scoring and task boundaries

**Status / classification:** isolated implemented library; live integration unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C19
- **Owning component:** Pure world resolution / current Director boundary
- **Accepted design reference:** [ADR-0036](../adr/0036-object-catalog-and-capabilities.md) §3/5; Final Spec M/S9/S15/T6
- **Implemented code reference:** [REQUIREMENTS](../../backend/src/maplegotchi/core/world/resolution.py#L69); [Score](../../backend/src/maplegotchi/core/world/resolution.py#L279)
- **Current behavior:** Any-of capability groups, state/capacity/reachability/room tiers; integer1000tier+steps−50sticky−200preference; seeded decision ties; isolated from live Director.
- **Required future behavior:** Integrate approved candidate admission/decision/task metadata without object-type dispatch or duplicated rules.
- **Compatibility invariant:** Writing/computer desks remain disjoint. If no reachable candidate exists, exclude the activity from allowed actions. Tasks name domain targets, not furniture.
- **Existing evidence:** [Resolution coverage/tie tests](../../backend/tests/world/test_resolution.py)
- **Missing evidence:** No live decision/restart integration; provisional weights do not become new fixed architecture.
- **Impacted R1b workstreams:** 04, 06, 07, 11, 12
- **Applicable owner gate:** D01 before04; future G2; D05 before pin changes

<a id="c20"></a>

### C20 — Slot validation and derived Storage

**Status / classification:** isolated implemented library; live integration unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C20
- **Owning component:** Pure placement / candidate hooks
- **Accepted design reference:** [ADR-0039](../adr/0039-storage-and-maple-slot-placement.md) §1–4; ADR-0036 STEP97; Final Spec L/S8/S11/S16
- **Implemented code reference:** [validate_placement](../../backend/src/maplegotchi/core/world/placement.py#L296); [derive_storage](../../backend/src/maplegotchi/core/world/placement.py#L372)
- **Current behavior:** Explicit slots, accepts/capacity/ownership/state, rate/cooldown and reachable approach; Storage derived from supplied existing eligible items; no placement execution.
- **Required future behavior:** Retain persistence hooks only in R1b; walk/commit/audit autonomy and representations need separate future scope.
- **Compatibility invariant:** Slots do not alter walkability; functional furniture never Maple-movable; no fabricated inventory/items.
- **Existing evidence:** [test_placement_has_no_geometry_or_resolver_effect](../../backend/tests/world/test_placement.py#L525); [test_hooks_rejected](../../backend/tests/world/test_placement.py#L162)
- **Missing evidence:** Eligible production domains, live placement event writer and owner editor absent/deferred; policy tuning not frozen.
- **Impacted R1b workstreams:** 02, 03, 07, 08, 09; later R3–R5/W2/W3/S5
- **Applicable owner gate:** Future G2/D02; separate later-stage authorization

<a id="c21"></a>

### C21 — RNG continuity and simulation digests

**Status / classification:** existing separate simulation harnesses; integrated R1b digest unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C21
- **Owning component:** Core RNG / separate simulation harnesses
- **Accepted design reference:** [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) §3 determinism; ADR-0035 §7
- **Implemented code reference:** [test_thirty_day_digest_is_pinned](../../backend/tests/core/test_simulation.py#L48); [test_thirty_day_grid_digest_repeats_full_trace_three_times](../../backend/tests/grid_world/test_simulation.py#L79)
- **Current behavior:** Original legacy and isolated grid digests both pinned; separate worlds/harnesses do not prove integrated live equivalence.
- **Required future behavior:** Explain full repeated integrated traces and intentional differences; explicit D05 before any new pin.
- **Compatibility invariant:** Preserve seed/streams/counters and old pin history; never repin to hide mismatch.
- **Existing evidence:** [Original simulation](../../backend/tests/core/test_simulation.py); [grid simulation](../../backend/tests/grid_world/test_simulation.py)
- **Missing evidence:** No integrated runtime digest or approved pin update; neither suite freshly rerun STEP161.
- **Impacted R1b workstreams:** 03, 04, 06, 07, 08, 11, 12
- **Applicable owner gate:** D05; future G2; separate P/G4

<a id="c22"></a>

### C22 — Legacy/New renderer gating and lifecycle

**Status / classification:** current shipped behavior; future world integration or later-stage changes unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C22
- **Owning component:** Frontend bootstrap / development switcher
- **Accepted design reference:** [ADR-0040](../adr/0040-room-view-transition-and-acceptance-gate.md) §1/4; R1A-15 owner Legacy Pixi clarification
- **Implemented code reference:** [main.tsx](../../frontend/src/main.tsx); [RoomSwitcher](../../frontend/src/dev/RoomSwitcher.tsx); [gate](../../frontend/src/world-room/gate.ts)
- **Current behavior:** Production mounts Legacy; DEV-only lazy fixture path; exact single room=fixture; new-world renderer disabled off; cancelled mounts/teardown preserve ownership.
- **Required future behavior:** Retain Legacy default/lifecycle and fixture disclosure; any live New enablement/default change separately scoped.
- **Compatibility invariant:** FlagOFF forbids NEW-WORLD Pixi, not existing Legacy Pixi; query/direct route cannot bypass production.
- **Existing evidence:** [Switcher tests](../../frontend/src/dev/RoomSwitcher.test.tsx); [guards](../../frontend/src/world-room/guards.test.ts); [R1A-15 historical browser evidence](maple-room-r1a-15-coexistence.md)
- **Missing evidence:** No fresh browser run STEP161; physical-device/final-art/B14 proof remains later; no live New consumer.
- **Impacted R1b workstreams:** 05, 07, 09, 11, 12; later B14
- **Applicable owner gate:** Future G2; separate live preview scope; G7/B14 default

<a id="c23"></a>

### C23 — Security and deferred owner editing

**Status / classification:** current shipped behavior; future world integration or later-stage changes unimplemented. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C23
- **Owning component:** API security / separate R4 design
- **Accepted design reference:** [ADR-0038](../adr/0038-owner-edit-mode-and-owner-authentication.md) §1–4; ADR-0040 §4
- **Implemented code reference:** [origin_guard](../../backend/src/maplegotchi/api/security.py#L107); [app routes](../../backend/src/maplegotchi/api/app.py)
- **Current behavior:** Exact Origin/CSP/current browser Greet/Pet boundary; no R4 owner layout authentication/editor in current implementation.
- **Required future behavior:** Preserve boundaries in R1b; R4 requires dedicated secret/session, header spike and core validation under separate authorization.
- **Compatibility invariant:** No owner endpoints, credential discovery or CSP/Origin relaxation from local inventory.
- **Existing evidence:** [Security route tests](../../backend/tests/api/test_api_security.py)
- **Missing evidence:** R4 auth/header/editor deliberately deferred; not a prerequisite for R1b or B14.
- **Impacted R1b workstreams:** 05, 07, 09; later R4
- **Applicable owner gate:** Future G2/security review; separate R4; G7 for default

<a id="c24"></a>

### C24 — Snapshot, activation and restore readiness

**Status / classification:** repository tooling exists; operational backup/restore readiness UNVERIFIED. Accepted design, current behavior, historical test definitions and future requirements are distinguished in the11fields below. Fresh narrow audit is recorded in sections8/18; D01–D06 remain OPEN.

- **Contract ID:** C24
- **Owning component:** Repository backup/release tools / future owner operations
- **Accepted design reference:** [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) §3; ADR-0023/0024/0028
- **Implemented code reference:** [stage](../../deploy/backup/maple_db_snapshot.py#L92); [check_database](../../deploy/backup/maple_db_snapshot.py#L56); [activation script](../../deploy/install/activate_release.sh)
- **Current behavior:** Tooling has read-only SQLite backup/private publication; check_database accepts migrated version>=1; activation flag acknowledges manual gate, does not verify snapshot receipt or start/migrate.
- **Required future behavior:** Current expected-version/source/conservation/restore proof and approved operator window before activation; one migration per approved lineage.
- **Compatibility invariant:** Feature flags do not guard schema; code pointer rollback cannot restore DB; no automatic restore or lost-life acceptance.
- **Existing evidence:** [Snapshot tests](../../backend/tests/deploy); [migration safety plan](maple-room-r1b-migration-safety.md)
- **Missing evidence:** Current backup/restore/source readiness UNVERIFIED; no production/copy data inspected.
- **Impacted R1b workstreams:** 08–12
- **Applicable owner gate:** D04/D06; G3 real-copy scope; G4/G5/G6

## 5. Database v10 and proposed v11 boundary

C11–C15 distinguish shipped code from candidate tests. Shipped migrations are 1–10; 10 adds nullable conversation_message.latency_ms. No new migration is registered. The candidate under backend/tests/rehearsal proposes 10 new tables:activity_kind, room_kind, layout_revision, world_state, layout_host, layout_room, layout_point, layout_slot, world_event, display_placement; rebuilds life_state, journal_entry, decision. Exact names/shapes/JSON cap are D02 OPEN, not a new frozen schema.

Conservation inventory covers maple, life_state, interaction_ledger, timeline_event, observation, journal_entry, journal_entry_observation, journal_state, goal, decision, action_event, document, tool_use, memory, memory_event, daily_reflection, conversation_message plus sqlite_sequence/indexes/triggers/FKs. Preserve complete rows/IDs/high-water marks and all unaffected needs/RNG/time/action/goal/task/reaction fields. No source database was opened, created, copied or converted STEP161; source SQL and existing tests were inspected only. Registry and source invariants are unchanged.

## 6. Fixed migration mapping rules

Final Spec R and candidate POINT_MAP agree on the nine identities below. Tiles are independently specified in Final Spec and resolved from accepted catalog data in the converter, not newly chosen coordinates.

| Legacy point | Canonical grid point | Tile |
|---|---|---|
|bed.side|bed.bedroom/sleep|(3, 4)|
|sofa.seat|sofa.living/seat|(12, 6)|
|bookshelf.front|bookshelf.library_1/front_l|(21, 4)|
|window.view|window.living/view|(18, 3)|
|writing_desk.chair|desk.writing/chair|(34, 5)|
|computer_desk.chair|desk.computer/operator|(39, 5)|
|open_area.west|idle.hall_west/idle|(10, 15)|
|open_area.center|idle.hall_center/idle|(21, 15)|
|open_area.east|idle.hall_east/idle|(32, 15)|

Null point uses canonical_point(activity, location), rug center. Invalid source activity/location/point or route destination mismatch refuses. Existing route maps to a destination zero-length route with departure=arrival=original scheduled arrival/activity_started_at; activity end, history/counters remain unchanged. Before scheduled arrival this may be pending zero-length travel. No fabricated walk, arrival, activity or world event. This one-time migration exception does not resolve D01 or authorize normal-runtime teleportation.

## 7. Runtime grid movement boundary

C04–C07: isolated grid pathfinding/Travel/reroute exist, but live MapleState/LifeRuntime/service/repositories still use legacy location/route contracts. Grid cutover is future 04/11, not implemented by catalog readers or synthetic rehearsal. Pending, departure, mid-edge, arrival, post-arrival, suspension, interaction and restart/downtime cases require integrated proof. Recovery must remain exceptional/recorded; unreachable actions fail no_destination rather than teleport.

## 8. Legacy projection boundary and complete provider corpus

C08–C10 retain the accepted [STEP120 gate](maple-room-r1a-09-legacy-projection.md#step-120--owner-acceptance-and-r1b-pre-cutover-integration-gate). Source CASES in test_legacy_projection.py independently transcribes T4/T7. **20 activity/provider cases on 17 distinct physical provider points**, including separate idle/walk labels for each of 3 Hall points. Cartesian ordered origin×destination gives 400; not 400 arbitrary tiles or every live transient state.

STEP161 read-only audit at this baseline read CASES through AST and used existing pure find_route/Travel/project with checked-in resource readers. No test/runtime source changed; no pytest, storage module, database, LifeRuntime or service loaded. Canonical fixture geometry produced 334 T / 26 Z / 40 C. Five supplied time boundaries for each of 360 successful pairs gave 1,800 checks; repeat projection and presentation identity were verified. This is fresh narrow contract verification, not a fresh full R1A-09 suite/browser/CI run. Test speed 317 ms is the existing projection fixture override; default engine 250 ms is unchanged.

| ID | Activity | Provider | Legacy anchor | Tile |
|---|---|---|---|---|
|P01|sleep|bed.bedroom/sleep|bed.side|(3, 4)|
|P02|rest|sofa.living/seat|sofa.seat|(12, 6)|
|P03|read|bookshelf.library_1/front_l|bookshelf.front|(21, 4)|
|P04|read|bookshelf.library_1/front_r|bookshelf.front|(22, 4)|
|P05|read|bookshelf.library_2/front_l|bookshelf.front|(23, 4)|
|P06|read|bookshelf.library_2/front_r|bookshelf.front|(24, 4)|
|P07|read|armchair.library/seat|bookshelf.front|(22, 8)|
|P08|think|window.bedroom/view|window.view|(6, 3)|
|P09|think|window.living/view|window.view|(18, 3)|
|P10|think|window.library/view|window.view|(26, 3)|
|P11|think|window.studio/view|window.view|(37, 3)|
|P12|think|plant.living/think|window.view|(19, 4)|
|P13|write|desk.writing/chair|writing_desk.chair|(34, 5)|
|P14|observe_server|desk.computer/operator|computer_desk.chair|(39, 5)|
|P15|idle|idle.hall_west/idle|open_area.west|(10, 15)|
|P16|idle|idle.hall_center/idle|open_area.center|(21, 15)|
|P17|idle|idle.hall_east/idle|open_area.east|(32, 15)|
|P18|walk|idle.hall_west/idle|open_area.west|(10, 15)|
|P19|walk|idle.hall_center/idle|open_area.center|(21, 15)|
|P20|walk|idle.hall_east/idle|open_area.east|(32, 15)|

Complete directed matrix:row=origin, column=destination. **T**=positive-step timed projection;**Z**=zero-step/no legacy route;**C**=positive-step same-anchor deterministic rejection. Count all 400cells, including20 diagonal Z plus6 cross-activity Hall Z. No missing classification.

|From / To|P01|P02|P03|P04|P05|P06|P07|P08|P09|P10|P11|P12|P13|P14|P15|P16|P17|P18|P19|P20|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|P01|Z|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|
|P02|T|Z|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|
|P03|T|T|Z|C|C|C|C|T|T|T|T|T|T|T|T|T|T|T|T|T|
|P04|T|T|C|Z|C|C|C|T|T|T|T|T|T|T|T|T|T|T|T|T|
|P05|T|T|C|C|Z|C|C|T|T|T|T|T|T|T|T|T|T|T|T|T|
|P06|T|T|C|C|C|Z|C|T|T|T|T|T|T|T|T|T|T|T|T|T|
|P07|T|T|C|C|C|C|Z|T|T|T|T|T|T|T|T|T|T|T|T|T|
|P08|T|T|T|T|T|T|T|Z|C|C|C|C|T|T|T|T|T|T|T|T|
|P09|T|T|T|T|T|T|T|C|Z|C|C|C|T|T|T|T|T|T|T|T|
|P10|T|T|T|T|T|T|T|C|C|Z|C|C|T|T|T|T|T|T|T|T|
|P11|T|T|T|T|T|T|T|C|C|C|Z|C|T|T|T|T|T|T|T|T|
|P12|T|T|T|T|T|T|T|C|C|C|C|Z|T|T|T|T|T|T|T|T|
|P13|T|T|T|T|T|T|T|T|T|T|T|T|Z|T|T|T|T|T|T|T|
|P14|T|T|T|T|T|T|T|T|T|T|T|T|T|Z|T|T|T|T|T|T|
|P15|T|T|T|T|T|T|T|T|T|T|T|T|T|T|Z|T|T|Z|T|T|
|P16|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|Z|T|T|Z|T|
|P17|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|Z|T|T|Z|
|P18|T|T|T|T|T|T|T|T|T|T|T|T|T|T|Z|T|T|Z|T|T|
|P19|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|Z|T|T|Z|T|
|P20|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|T|Z|T|T|Z|

All 40 collapsed-anchor **ordered** rejected pairs are explicitly enumerated below. Each destination ID resolves to the exact provider/activity in the lookup above. Every listed pair has nonzero canonical steps; all map to the row's single legacy anchor.

| Origin | Exact rejected destinations | Legacy anchor |
|---|---|---|
|P03 bookshelf.library_1/front_l|P04, P05, P06, P07|bookshelf.front|
|P04 bookshelf.library_1/front_r|P03, P05, P06, P07|bookshelf.front|
|P05 bookshelf.library_2/front_l|P03, P04, P06, P07|bookshelf.front|
|P06 bookshelf.library_2/front_r|P03, P04, P05, P07|bookshelf.front|
|P07 armchair.library/seat|P03, P04, P05, P06|bookshelf.front|
|P08 window.bedroom/view|P09, P10, P11, P12|window.view|
|P09 window.living/view|P08, P10, P11, P12|window.view|
|P10 window.library/view|P08, P09, P11, P12|window.view|
|P11 window.studio/view|P08, P09, P10, P12|window.view|
|P12 plant.living/think|P08, P09, P10, P11|window.view|

READ P03–P07 accounts for 20 directed rejections; THINK P08–P12 accounts for 20. Hall west/center/east have distinct anchors and do not contribute collapse errors. The40-pair set is not a backend-prevention policy.

**Mid-edge evidence:**existing test_invalid_travel_or_inputs[mid_edge] constructs EdgeStart((20, 15),(21, 15), 1000, step_us), Entry ending(21, 15) and Travel to desk.writing/chair. Fresh audit used step_us 317000 and confirmed exact `projection: mid-edge origin has no unambiguous legacy anchor`. _project_route rejects any non-null entry, not just this one sample; the guard precedes endpoint/path mapping and does not disappear merely because supplied time later passes arrival. Existing grid reroute tests admit exact transient entries. No source-backed finite count of all possible ambiguous temporal states exists here; do not equate one negative fixture with exhaustive live coverage.

Other exact refusal boundaries:zero-step route with different mapped anchors; wrong origin/destination approach; forbidden route cells; unknown/unavailable/closed/unwalkable source; unmapped activity/capability; missing origin metadata; activity start differing from arrival; future stationary activity; naive time; forged/mutable inconsistent context. Successful projection preserves caller presentation facts and exact route times, uses the existing legacy graph, emits no event and changes no state. R1A-16 pure layout validator may compose projection; there is no live production caller. Existing source-isolation test expressly allows only that isolated composition.

**D01 decision assessment:**normal valid grid transitions can lose distinguishable Legacy anchors; valid transient reroute origins can have no unambiguous Legacy source anchor. Such reachable states need owner-reviewed compatibility evidence before04/05implementation. No prevention strategy, Legacy modification, fallback, approximate coordinate, fabricated loop or silent error-handling change is selected, approved or implemented. R1B-01 can be accepted with D01 OPEN.

## 9. API, DTO and SSE compatibility boundary

C16–C18/C23: normal world GETs503; explicit fixture app is separate. WorldIdentityOut source/status are literal development_fixture/synthetic. Normal SnapshotOut integer revision, WorldSnapshotOut string world_revision, fixture layout/catalog content hashes, candidate layout ID and EventHub boot-seq IDs are different meanings. Preserve /api/room,/api/snapshot and existing SSE payloads, replay/resync/read-only waiting andexactOrigin/CSP/Greet-Pet protection. Current fixture WorldOut lacks needs, journal andinteraction availability; do not fabricate a legacy business-panel adapter. D03 live source/revision/SSE/versioning remains OPEN; world SSE is deferred absent demonstrated need.

## 10. Revision and active-pointer contracts

C15/C16/C18: layout document is authoritative; key indexes are derived FK targets. Candidate active pointer must resolve exactly one immutable revision; life_state.layout_revision must match; canonical document/digest/catalog/hash/index agreement required. Revert means a new base-linked revision, not mutating old history; no R4 endpoint is authorized. Exact SQL/version/size bounds remain D02. Live read/SSE correlation remains D03. Fixture hash equality proves shared synthetic content only.

## 11. Route and coordinate invariants

C01/C04–C06/C13: integer bounded tile values, half-open rectangle geometry, orthogonal compressed waypoints, exact cumulative steps; derivedfeet=(16tx+8, 16ty+13); no persisted fractional pixel authority. Temporary EdgeStart stores adjacent tile endpoints andinteger temporal progress, not a fractional Tile. Travel duration includes partial entry; reroute keeps exact current position. Legacy Route has pixel-distance/graph nodes and must not be confused with grid Route despite the shared class name. Neither migration zero-length mapping nor emergency recovery permits normal movement teleport.

## 12. Capability and slot contracts

C03/C19/C20: 8 activities use accepted any-of groups; READ 5 providers, THINK 5 providers; WRITE writing_surface andOBSERVE computer/system_console remain disjoint desk capabilities; REST seat_soft only. Reachability, state/capacity, room tiers andseeded tie breaking determine candidates. Current resolver is pure/isolated, not live Director integration. Slots have explicit identity, accepts/capacity/permissions, narrow declared instance approach/facing overrides andsame-host shares_point reuse.29 approach references / 26 tiles / 3 declared reuses; slots never affect walkability. Storage derives existing eligible objects, not a new inventory. Walk/commit/audit placement execution, real representations andowner editing are deferred.

## 13. Existing evidence and fresh verification limits

Historical accepted R1A-08 reports23 synthetic fixture outcomes and24 controlled failure cases; R1A-09 records334/26/40 plusmid-edge refusal; R1A-10 records deterministic synthetic exports andproduction503/compatibility; R1A-15 records renderer isolation/lifecycle/browser evidence. These suites and historical GitHub/hardware results were NOT freshly rerun STEP161. Existing test definitions were mapped in C01–C24 and section16.

STEP161 fresh audit only:400pair classifications, 1800time-boundary checks andoneexplicit mid-edge refusal, using immutable in-memory values andchecked-in catalog/house resources. Local helper/output under ignored var/r1b161 is not published or staged; full400matrix and40-pair set are retained above. No database conversion, DB-backed test, new pytest test, live/browser/server or production operation. Original pin `458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917` andgridpin `b3287b3d13ed406fc98ecc5be58494e9f3ac9df7fc4b0a70cedb6e85ad5500d3` unchanged; neither simulation was rerun.

## 14. Contract gaps and open decisions

| Decision | Status / affected contracts | Required evidence and earliest block | Approval / still unapproved |
|---|---|---|---|
|D01 Projection|OPEN; C06–C10|400corpus plusruntime-reachable transient/restart coverage; blocks04/05directly, 06–12transitively|Owner explicit decision before affected implementation; no strategy or Legacy expansion approved|
|D02 Schema|OPEN; C03/C11–C15/C20|Exact v11 tables/columns/JSON/cap/hash/lookup/reconstruction contract in02; before dependent03/09|Owner contract review under separately boundedG2; no schema lock/registration now|
|D03 Live DTO/SSE|OPEN; C09/C15–C18/C22/C23|Truthful live source/version/revision/read consistency; demonstrated SSE need if any; before05|Owner accepted design/compatibility review; no live DTO/SSE change now|
|D04 Snapshot/retry|OPEN; C11–C15/C24|Actual copy/restore/process-fault/current source lineage proof; 08feeds10/G4|Owner G3 scope andG4 readiness; no present backup/restore assertion|
|D05 Digest|OPEN; C04/C19/C21|Repeated integrated traces/explained intentional differences in06, before repinning|Owner explicit digest approval; both existing pins preserved|
|D06 Window/loss|OPEN; C14/C24|Exact operator/window/recovery cutoff andacceptable lost life in10/G4/G5/G6|Owner operational approval; no invented downtime/RPO/RTO orrestore permission|

No binding ADR/spec conflict requiring amendment was found. Deliberate implementation gaps are not design approvals. ADR historical NOT IMPLEMENTED/old provisional rows describe their recorded dates; accepted R1a libraries andlateramendments provide implementation evidence without claiming live cutover. Any actual need to amend accepted geometry, movement, projectiontruth, conservation orsecurity stops this bounded scope.

## 15. Downstream dependencies

The Master Plan graph is unchanged and acyclic. The independent lane is01 inventory →02/D02 isolated persistence →03 synthetic unshipped conversion.01 can finish with D01 OPEN;02 requires accepted01 and new bounded G2;03 requires accepted02/D02 and new G2. D01 directly blocks04/05 and transitively blocks06–12. Partial preparation cannot close integrated07 or real-copy08.

Critical path:01 →02 →D01 gate →04 →05 →06 →07 →08 →09 →10/G4 →11/G5 →12/G6;03 joins07/08. Future09 local registration does not permit production startup before G4/G5. G1 and the merged planning PR22 grant neither publication of this inventory nor G2 for02–12. G3–G7 remain separate approvals.

## 16. Planned compatibility test cases

Every row is an inventory/planned acceptance case, not a newly implemented test or proof of future behavior. Existing evidence names refer to source definitions mapped in C01–C24; fresh narrow checks are explicitly labeled. Future execution requires separate workstream authorization.

| Case | Contracts | Existing evidence / future acceptance case | Downstream / gate |
|---|---|---|---|
|TC01 Coordinates|C01|test_primitives.py: bounds, bool rejection, feet conversions and directions; future persistence/DTO roundtrip|02/05/07; D02/D03/G2|
|TC02 Geometry|C02/C03|test_layout_data.py, test_oracle.py, test_walkability.py: exact T1–T5, 431-cell component, closed regions and K1–K4|02/04/07; G2/G4|
|TC03 All 400 pairs|C09/C10|Existing provider-pair test; fresh 400 classifications and 1,800 time-boundary checks recorded above|05/07; D01/G2|
|TC04 All 40 collapses|C10|Explicit 40-pair set above; retain exact refusal; future approved policy must cover reachable transitions|04/05; D01/G2|
|TC05 Mid-edge|C06/C10|Existing mid_edge negative and repeated-entry reroute tests; future transient/reroute/restart corpus|04/05; D01/G2|
|TC06 Other refusals|C09/C10|Wrong point, metadata, route, capability, time or forged context; closed/blocked inputs; no fallback fabrication|05/07; D01/G2|
|TC07 v10 compatibility|C07/C08/C11|Storage/database/repository tests; keep registry10, frozen migrations1–10 and too-new refusal|02/03/07/09; D02/G2|
|TC08 Fixed mapping|C13|Existing full-row roundtrip test: nine points, nulls and in-flight route; future before/at/after arrival and restart|03/08/09; D02/G2/G3|
|TC09 Revision|C15|Existing new-revision/revert/index test; future active-pointer and consistent-read correlation|02/05/07; D02/D03/G2|
|TC10 DTO/API|C16/C17|test_world_api.py: source literals, shared hashes, 503, GET-only, isolation and exports; future live/Legacy contract|05/07; D03/G2|
|TC11 SSE|C18|test_sse.py: boot/sequence, replay/gaps/resync, unsubscribe and read-only waiting; world additions only if approved|05/07; D03/G2|
|TC12 Authority|C07/C19|Current runtime movement tests cover Legacy; future committed/reopened grid truth, Director admission and counters|04/06/07; D01/G2|
|TC13 Projection truth|C08–C10|Existing presentation/pose/goal/task identity and time/graph checks; future live panel/reaction/arrival equivalence|05/07/12; D01/G2/G6|
|TC14 Failure/restart|C14|Existing rollback/source-drift/FK-mode tests; future process kill, disk-full and unknown-COMMIT classification|03/07/08; G2/G3/G4|
|TC15 Conservation|C11/C13/C14/C21|Existing unaffected rows/fields/IDs and sequence high-water checks; future exact-candidate owner-copy manifest|03/08/09; D02/G2/G3|
|TC16 Capabilities|C19|test_resolution.py: all eight activities, capacity/state/room filters, seeded ties, preferences and last-provider rejection|04/06/07; D01/G2|
|TC17 Slots|C03/C20|Catalog/placement tests: overrides/reuse, hooks, permissions, capacity, derived Storage and unchanged geometry|02/03/07; G2; later placement scope|
|TC18 Production isolation|C17/C22/C23|World API, switcher and guard tests: production query/direct-route refusal, Legacy Pixi functional and New off|05/07/09; G2/P; B14 later|
|TC19 Lifecycle|C22|Switcher/scene tests: cancelled imports, round trips, idempotent disposal and focus/CSP; future scoped live consumer|05/07; G2; separate live preview|
|TC20 Determinism|C04/C19/C21|Two existing simulation pins; future three full integrated traces, explained restart differences and Windows/Linux equality|06/07; D05/G2/P|
|TC21 Real-copy/restore|C12/C14/C24|Repository tools and historical synthetic evidence only; future private owner-copy lineage and independent old-code restore|08/10; G3/G4|
|TC22 Production verification|C07/C09/C16/C24|No current production evidence; future health, identity/history, grid, Legacy and restart checks beyond HTTP200|11/12; G5/G6|

## 17. Risks and stop conditions

All22 existing risk rows and classifications remain unchanged. Relevant risks cover projection truth, schema, competing state authority, fixture/live confusion, snapshots/conservation/retry, privacy, repinning, B14 and scope expansion. Their accepted gates remain binding; no operational tolerances or new architecture are invented.

Stop for an unapproved ADR/spec amendment, unexpected user changes, external/live data input, an unknown mapping, source/revision mismatch, unsafe projection, failed current restore proof or a request to publish/expand beyond bounded01 without approval. Current real-data readiness remains UNVERIFIED.

## 18. Owner acceptance criteria and local validation

**STEP162 publication review:** All24 records reviewed,11required fields retained,explicit classifications added. Clarified C03 geometry versus policy overrides and C19 no-candidate admission wording without changing accepted contracts. Fresh pure source/resource verification again reproduced400pairs=334timed+26zero+40collapsed,1800time boundaries and exactmid-edge refusal;no storage/database/live runtime loaded. Existing67symbol/line references match unchanged baseline source. All22cases remain planned coverage,not newly implemented or passing tests. Source/runtime/fixture/revision/production boundaries andD01–D06OPEN are retained. Current production backup/restore readiness remains UNVERIFIED. Fresh final documentation result: PASS:332relative links,23heading/explicit anchors,67code-line references,zero broken links;24complete11-field records with24explicit classifications;18sections;exact400matrix/40rejected set;22plannedcases;all6decisionsOPEN;22riskrows andactual dependency graph unchanged/acyclic;UTF-8/LF andgit diff --check PASS. Full pre-STEP162 worklog181756-byte prefix/SHA256 `c66093f0a05320cfed382ff3b8d948edb342c67a4ecea9ed847310c89706fd0d` retained exactly. Exact8-doc manifest;main/planning/history worktrees andunrelatedrefs unchanged. Fresh hosted PRCI is PENDING at document commit;actual results will be recorded in the PR evidence,not inferred from PR22..

Accept inventory completeness and source traceability with D01–D06 OPEN; do not approve a strategy by implication. Required evidence:24 complete contract records; all400 matrix cells and40 rejected ordered pairs; exact mid-edge rejection and limits; fixed migration versus normal movement; DTO/revision/capability/slot boundaries;22 planned cases and downstream gates; correct counters; append-only history; documentation-only scope. No source, contract, pin, data, production or publication change.

STEP162 accepts01 for final integration review and authorizes reviewed publication only. Separate owner merge approval and confirmed integration remain pending. R1B-01 is REVIEW, not DONE.

Exact local changed-file manifest (8 documentation paths):

- [New inventory](maple-room-r1b-01-contract-inventory.md)
- [Checklist](maple-room-r1b-checklist.md)
- [Master Plan](maple-room-r1b-plan.md)
- [Migration Safety Plan](maple-room-r1b-migration-safety.md)
- [Cutover Plan](maple-room-r1b-cutover-plan.md)
- [Risk/Gate Matrix](maple-room-r1b-risk-gates.md)
- [CLAUDE](../../CLAUDE.md)
- [Append-only worklog](maple-room-r1a-worklog.md)

Fresh final local validation PASS: 324 relative links, 23 heading/explicit anchors and 67 code-line references resolve; zero broken links. All 24 contract records contain 11 required fields; 18 sections; 22 planned compatibility cases; 400 directed classifications and40 ordered collapse refusals agree with fresh source audit. Actual dependency graph unchanged/acyclic with D01 descendants 04–12; 22 risk rows/classifications unchanged. Counters:01 REVIEW, 11 TODO, 0 DONE. UTF-8/LF and git diff --check PASS. Full pre-STEP161 worklog prefix 178366 bytes/SHA256 `e70cacff34dfb8f478062818e09142eca8ef7329fdf1a222c3a3874181da13e2` preserved. HEAD/refs/registered worktrees unchanged after authorized isolated creation; main/planning/history worktrees clean; index empty; no remote01 branch. Exactly 8 documentation paths changed; no source/test/configuration/schema/pin/runtime changes.

STEP162 next action: reviewed documentation commit,normal push,PR andactual CI inspection;feature SHA/PR/tested revision/job evidence will be recorded in the PR review comment after execution,avoiding a self-referential commit SHA or an extra commit solely for run IDs. Stop for separate owner merge approval. Do not begin R1B-02;no runtime/test/migration/schema/default/pin/production change.
