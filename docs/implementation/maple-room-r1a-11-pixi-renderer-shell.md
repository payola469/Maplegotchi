# R1A-11 — Pixi renderer shell

**Current STEP 134 baseline reconciliation:** DONE / OWNER ACCEPTED / MERGED. Closure PR #13 merged at `cd328010a71f2cbcb1d0aee9f59ce925132447ae`. All STEP 131/132 evidence and publication status below remains historical. Camera work is separately tracked in [R1A-12](maple-room-r1a-12-camera-zoom-dpr.md).

**Current STEP 132 status (2026-10-11): REVIEW / OWNER ACCEPTED / CLOSURE VERIFIED / MERGE PENDING.** Owner accepts the STEP 131 completion matrix PASS and merged-tree renderer/atlas evidence. PR #11 and PR #12 are merged; atlas dependency RESOLVED. No remaining R1A-11 blockers. Commit, normal push, closure PR and CI inspection authorized for eight documentation files only; no merge, deployment, Production access, schema-v11 activation or later workstream. On closure PR merge, record **DONE / OWNER ACCEPTED / CLOSURE VERIFIED**, with **12 DONE / 8 TODO / 60% complete**; until then, current counters remain **11 DONE / 1 REVIEW / 8 TODO**. Earlier STEP records below retain their historical context.

**Current STEP 131 status (2026-10-11): REVIEW / CLOSURE REVIEW PASS / OWNER ACCEPTANCE PENDING.** All original renderer-shell completion criteria PASS on merged integration `7b45af4d94cd736390a1477e925e137698bc4aac`. R1A-14 atlas dependency RESOLVED; R1A-14 is DONE / OWNER ACCEPTED / MERGED. Recommend **R1A-11 — READY FOR OWNER ACCEPTANCE / CLOSURE**. Do not mark R1A-11 DONE until owner acceptance and integration of this closure record. Current authorization is local verification/documentation only; all STEP 125/126/128 scope, evidence, blockers and publication permissions below are historical and superseded for current status by the STEP 131 matrix.

**Current STEP 128 CONTINUE status (2026-10-11): REVIEW / PARTIAL.** Shell PR #11 merged at `f7e313cbe16992593d7f387450c9101d1b31f358`. Generated atlas loading, required keys, L19 lifecycle and renderer regressions now PASS locally; [R1A-14 evidence](maple-room-r1a-14-asset-pipeline.md) records 423 frontend cases, 65 asset cases, budget/release/browser checks and Windows-native pending gate. Atlas dependency is locally resolved. Formal acceptance, publication and CI/integration of atlas changes remain pending; neither workstream is DONE. The STEP 125/126 scope, authorization and evidence below are historical. R1A-12/13/15 are not implemented here.

**Status:** OWNER ACCEPTED FOR PARTIAL INTEGRATION / STEP 126. **PARTIAL — RENDERER SHELL INTEGRATED / ATLAS COMPLETION PENDING.** Repository merge pending; checklist BLOCKED denotes the R1A-14 completion dependency, not rejection of this shell. Commit, normal push, PR and initial CI inspection authorized; no merge or production activation. R1A-11 remains PARTIAL even if this PR passes CI or is merged.
**Baseline:** `e3a031699b41f941d62bc754e4cb9c1819bdd67f` — fetched integration HEAD, PR #10 merged.
**Worktree/branch:** `r1a-11-pixi-renderer-shell/Maplegotchi`, `codex/r1a-11-pixi-renderer-shell`.

## Inputs, scope and boundaries

Precedence: locked [ADR-0041](../adr/0041-art-technical-contract.md) values → accepted ADR-0035–0040 rules → [Final Spec](../architecture/maple-room-final-design-spec.md) → proposed [Future Architecture §9](../architecture/maple-future-architecture.md#9-art--visual-technical-architecture). [Master Plan](maple-room-r1a-plan.md#r1a-11--pixi-renderer-shell) and [R1A-10 handoff](maple-room-r1a-10-world-api-contracts.md) define workstream boundaries. The [spike](../spikes/2026-10-room-art-spike.md) supplies locked technical evidence, not production code or art.

Dedicated `frontend/src/world-room/` modules consume generated R1A-10 DTOs. Development-only `?room=fixture` dynamically imports the preview before constructing any legacy API/store/SSE connection. Production builds eliminate this branch. Legacy Room remains the default. Checked-in labeled fixtures supply data; no network world loader or production switch. All text, controls, errors, fallback descriptions and disclosure remain DOM.

No pathfinding, collision/placement validation, capability resolution, state mutation, live integration, Edit Mode, artwork pipeline or final art. R1A-12 camera interactions, R1A-13 lighting presets/emitters and R1A-15 live coexistence remain separate authorizations.

## Sequential implementation gates

1. Typed presentation helpers: tile/pixel projection from DTO grid, L11 depth keys and stable ties, compressed-route interpolation with supplied UTC times and partial entry, L12 distance frames. Test boundaries, corners, long/zero routes and fixed-time repeatability.
2. Placeholder resource interface: per-frame integer face anchors (null up), separate body/face textures, configurable PROVISIONAL face size; object visual offsets belong to art metadata. No production manifests or geometry-version invention. Assets initialization uses L19 `preferWorkers: false` and existing unsafe-eval import. Own only locally generated test textures; release once.
3. Scene shell: §9.2 ordered layers, floor variants/edges, backend structural cells with explicit passage overrides, north caps/side caps, lintel-free archways/windows, catalog-driven object presentation, Maple and above-occupant parts. Lighting layers reserved, neutral only until R1A-13. No inferred walkability.
4. Lifecycle and preview: once per mount, async cancellation, error cleanup, idempotent disposal, one owned ticker and ResizeObserver. L13 device content box validated against CSS×DPR, fallback rounded; DPR checked each render. Integer device zoom from L14; minimum Overview fitting and DOM room fallback, no R1A-12 Follow/Focus implementation. Reduced motion shows a fixed selected-time frame without autonomous playback.
5. Validation/review: presentation and lifecycle/component/architecture tests; broad frontend suite, strict TypeScript, ESLint/build, relevant backend API regression and export check, links/whitespace/scope review. Browser evidence only if actually rendered. Record limitations and exact results below.

## Required gates and handoff

Fixture coverage: 44×26, eight regions, seven doors, 28 instances, 17 points, 12 slots and 431 backend walkable cells. Renderer draws closed regions but never changes their access. Floors/edge masks are visual boundary decoration from region rectangles, never navigation rules. L11: sortY×8+priority; south tile edge for Maple, footprint south edge plus art offset for objects, occupant inherits object depth; priorities 1/2/3/4 and insertion-order ties. L12: floor(distance-in-tiles×2) modulo 4; no invented speed/path/timestamps. FEET_IN_TILE is consumed from DTO, not redefined.

L6 body canvas 32×48/anchor (16,47) is locked art geometry; faces are separate per-frame overlays, selected only from backend expression. Face size, colors and default form-factor zoom remain provisional. Placeholder source carries its own anchors/visual offsets; no claim of delivered furniture/sprite/slot geometry. R1A-14 must provide reviewed Vite-hashed atlas imports, trim/extrusion/anchor preservation, catalog cross-check, production manifests, texture budgets and loading/unloading strategy. R1A-11 cannot be DONE before this dependency. R1A-12 receives device-pixel sizing/transform primitives; R1A-13 receives named neutral lighting layers and backend zones; R1A-15 receives an isolated scene handle and DTO consumption.

## Evidence and consolidated review

**Overall: CONCERN / workstream PARTIAL. Renderer-shell readiness PASS; atlas completion BLOCKED.**

| Requirement | Result | Evidence / remaining boundary |
|---|---|---|
| Baseline / R1A-10 completion | PASS | Integration HEAD/PR #10 merge verified; original local-only `40f0eb7` preserved |
| Fixture entry / legacy default | PASS | `import.meta.env.DEV` and explicit query required before constructing live clients; production JS has no preview or fixture payload |
| Full house / structured presentation | PASS | 641 region-floor cells, seven passage footprints, all structural cells, 28 catalog instances (three no-art markers), four windows; eight regions, 17 points/12 slots/431 walkable cells retained as backend data |
| §9.2 layers | PASS shell / PARTIAL art | All twelve containers ordered; floor/decals/walls/entities/caps/backdrop drawn. Optional above-occupant parts supported at the art boundary; shadows/lighting/fx/editor containers reserved, no editor behavior |
| L11 sort | PASS | 144 same-row/around-object ring cases, zero mismatches; north/south/corners, footprint vs tall visual extent, art offsets, priorities and actual Pixi stable insertion ties tested. Occupant inherits host depth; above-occupant priority tested with recording art |
| L12 walk | PASS | Supplied compressed route/timing only; start/mid/end, corners, long/zero routes, partial entries both directions, repeatability and four-frame distance lock. No fabricated route or state transition |
| L6 / L2 / L3 | PASS method / PARTIAL final art | 32×48 canvas, (16,47) anchor; body and expression overlays separate, integer per-frame anchors, null back-facing overlay. Configurable 12×6 test face (14×8 tested), explicitly PROVISIONAL. Full activity sheets/occupant art and owner readability test pending |
| L8 / L9 / L10 | PASS placeholder | Passage DTO overrides wall map, caps omit archways, side caps sort per tile, south cutaway drawn. 2T×2T window pane at backend mount offset, transparent pane/visual wall cutout reveals backdrop; no interior window synthesis |
| L13 / L14 | PASS shell | Device box checked against CSS×DPR; rounded fallback; per-render DPR read, integer device zoom/camera translation; WebGL/resolution1/autoDensity false/antialias false/roundPixels true; nearest/no mipmaps. Real multi-DPR/device and camera QA remain R1A-12/19 |
| L17 | PASS placeholder | Four integer-hash variants; N1/E2/S4/W8 edge masks in an actual sixteen-cell 4×4 row-major test texture; geometry untouched |
| L19 | PASS initialization / BLOCKED atlases | `preferWorkers: false`, unsafe-eval module retained, CSP unchanged. No accepted production atlas loader exists on baseline; interface uses locally owned generated test textures only. R1A-14 remains required |
| DOM / accessibility / reduced motion | PASS local | All text/controls outside canvas; aria-hidden canvas, summary/current-room list, keyboard-native controls, init/import errors; reduced-motion playback disabled with fixed-time inspection. No real-device accessibility certification |
| Lifecycle / security / guards | PASS | 1 application/ticker/observer per mount; cleanup/cancellation/failure/idempotence/source ownership tests. No new fetch/SSE/mutations, geometry authority, pathfinding or capability/placement validation. No HTML sinks/CSP change |

Final local validation: **417 frontend cases, 0 failed, 19 files (209 new cases)**; `pnpm typecheck`, `pnpm lint`, `pnpm test`, `pnpm build` PASS. Backend: `pytest tests/api/test_world_api.py tests/api/test_api_security.py -q -p no:cacheprovider` **108 PASS**; `python -m tests.api.world_contract_export` exact five-fixture/OpenAPI/TypeScript regeneration PASS. No backend changes; original simulation pin, Oracle/Harness, API/SSE, Director, storage/schema/deployment and legacy `room/` modules untouched. Full Release Gate and simulation not rerun.

Actual in-app-browser WebGL QA: full 44×26 house, idle feet (344,253), walking at fixed +375 ms feet (368,253), phase 3/right; Play progresses and stops at +2750 ms feet (520,253), idle frame 0. Desktop viewport 1440×1100; 820 and 390 px emulation checked, no horizontal overflow; narrow Overview fallback/current-room list confirmed. Captured `r1a11-idle.jpg`, `r1a11-walking.jpg`, `r1a11-mobile-fallback.jpg` as local artifacts outside Git. Browser review corrected text contrast and opaque window-pane occlusion; regression checks pass. One benign Assets-already-initialized warning occurred during hot module replacement, not a fresh page boot; no browser errors. These are placeholder/local browser observations, not production-art, real-mobile, performance/soak or all-DPR acceptance.

Remaining: R1A-14 reviewed atlas/manifest/trim/geometry versions/loading and resource budgets; final face size/art/pose sheets; R1A-12 camera modes, R1A-13 lighting; R1A-19 device/performance evidence. Smallest safe sequence: review shell now; authorize R1A-12 separately, and R1A-14 when planned; close R1A-11 only after atlas loading integration is validated. No new binding conflict or owner decision is required for this shell. No later workstream started.

## STEP 125 final scope and documentation checks (historical)

22 files changed, none staged. New renderer sources: `frontend/src/world-room/{presentation,assets,scene,fixtures,gate}.ts`, `Preview.tsx`, `preview.css`; new tests: `presentation.test.ts`, `assets.test.ts`, `scene.test.ts`, `guards.test.ts`, `Preview.test.tsx`. Existing entry/config changes: `frontend/src/main.tsx`, `frontend/vite.config.ts`. Documentation: this plan, R1A-10 completion pointer, Master Plan, checklist, append-only worklog, `docs/frontend.md`, `docs/architecture.md`, `CLAUDE.md`.

Final checks: 68 relative documentation links valid; checklist counters 20 total / 10 DONE / 1 BLOCKED / 9 TODO; original worklog byte prefix preserved; tracked/untracked `git diff --check` PASS; production `.js` output contains no preview or fixture payload; scoped credential-pattern scan PASS. No backend, legacy renderer/API/client/store, dependencies/lockfile, accepted ADR/Final Spec, Oracle/Harness/simulation pin, schema or deployment file differences. All other worktrees clean; local `v0.2-development` still `40f0eb76166560de9475ca4f834919ca04f2a8ef`. No commit/push/PR/merge performed.

## STEP 126 — Owner acceptance for partial integration (2026-10-11)

Owner accepts the reviewed renderer shell for commit, normal push and PR against `v0.2-development`, with initial CI inspection. R1A-11 remains **PARTIAL — RENDERER SHELL INTEGRATED / ATLAS COMPLETION PENDING**, repository merge pending; R1A-14 must complete asset validation, deterministic packing, extrusion/trim metadata, hashed output, budgets, catalog/manifest checks, release integration and renderer atlas loading before R1A-11 can be DONE. R1A-12/13/14 remain TODO.

Verified unchanged remote baseline `e3a031699b41f941d62bc754e4cb9c1819bdd67f` and 22-file scope. Focused rerun: **209 renderer cases passed / 0 failed**, **108 backend API/security cases passed / 0 failed**; TypeScript, ESLint, production build and exact OpenAPI/TypeScript/five-fixture export PASS. Accepted full frontend evidence remains **417 passed**, including **144/144 depth ring cases**; unrelated suites were not repeated. STEP 125 browser/WebGL evidence is reused (idle, walking, completion, doors/windows, DOM disclosure/controls, 390/820 px emulation); no new browser testing claimed. Fresh-boot checks were clean; HMR-only Assets warning retains its historical context.

Production safety PASS: legacy default and production build preserved; fixture preview/payload excluded from shipped JavaScript; no backend/API/SSE, database/schema, Director, deployment, accepted spec/ADR, Oracle/Harness or simulation-pin changes. Worklog append-only; checklist counters remain 20 total / 10 DONE / 1 BLOCKED / 9 TODO; documentation links and patch whitespace checked. All unrelated worktrees and local-only `40f0eb7` preserved. PR/CI outcome is reported after publication; no merge, deployment, production access or later-workstream implementation authorized.

## STEP 131 — Formal closure verification

### Baseline and source precedence

Fresh isolated worktree `/Users/paolo_cu/.codex/worktrees/r1a-11-closure/Maplegotchi`, branch `codex/r1a-11-closure`, starts clean at latest fetched `origin/v0.2-development` **`7b45af4d94cd736390a1477e925e137698bc4aac`**. Both PR #11 merge `f7e313cbe16992593d7f387450c9101d1b31f358` and PR #12 merge `7b45af4d94cd736390a1477e925e137698bc4aac` are verified ancestors. All existing worktrees, original shell/atlas trees and local-only `40f0eb76166560de9475ca4f834919ca04f2a8ef` preserved.

Reviewed CLAUDE, Master Plan/checklist/append-only history, R1A-10/11/14 records, Final Spec, art contract/spike, ADR-0035–0041 and renderer/tests/build loading. Precedence remains locked ADR values → accepted ADR rules → Final Spec → proposed documents; approved E8 light/shadow clarification retained. No new design decision or corrective runtime change was necessary.

### Requirement-by-requirement closure matrix

| Requirement | Verdict | Merged code/tests and completion boundary |
|---|---|---|
| A — Pixi 8.21.0 and full typed house | PASS | `scene.ts`, generated DTOs and fixture assertions: 44×26, eight regions, seven doors, 28 instances. Three structural markers intentionally have no art; all required visual keys resolve. Actual WebGL house observed. |
| A — Presentation-only boundary | PASS | `guards.test.ts`: no pathfinding, world/placement validation, capability resolution, hardcoded geometry authority or live/mutation clients. Backend DTOs supply grid, rooms, structure, passages, objects and routes. |
| B — Floors/edges L17 | PASS | Integer visual hash, four variants, sixteen N1/E2/S4/W8 edge cells; packed frame/pixel and scene tests. These are visual transforms, not walkability logic. |
| B — Walls/caps/doors/windows L8–L10 | PASS | Atlas sprites use supplied structural cells; north faces clipped around exterior windows, caps omit passages, side caps sort per tile, south cutaway retained; seven 2×3 archways have no lintels. Four transparent 2T windows at supplied mount expose backdrops. |
| B — Objects/Maple/occupant layers | PASS | Twelve named ordered layers; objects use catalog footprints and art offsets, separate Maple body/face, approved cover parts at above-occupant priority. Neutral lighting/editor containers only. |
| C — L11 depth ring | PASS | **144/144 ring cases, zero ordering mismatches**, plus two supporting offset/priority/stable-tie cases. Maple tile-south-edge, footprint-south-edge + art offset, occupant host depth, priorities 1/2/3/4 and actual Pixi stable insertion ordering covered. |
| D — L12 deterministic supplied routes | PASS | Start, pre-departure, segment/corner, arrival, after-arrival, zero/long routes, partial entry forward/backward and repeatability. `floor(distance×2)%4`; four frames per two steps. No frontend route generation. |
| D — FEET_IN_TILE/facing | PASS | DTO offset consumed, including nondefault injected grid test. Idle `(344,253)`, right-facing +375 ms `(368,253)`/frame3, arrival +2750 ms `(520,253)`/stationary frame0. |
| E — L6 face method | PASS | Separate body/face textures; expression and direction select manifest keys, integer per-frame face anchors, null up-facing overlay. Metadata-driven overlay dimensions remain adjustable; 12×6 is provisional, 14×8 shell-resource alternative tested. No final-size/appearance acceptance. |
| F — L13 renderer shell | PASS | WebGL/resolution1/autoDensity false/antialias false/roundPixels true; validated device-pixel box/CSS×DPR fallback, DPR read every render, integer device zoom/translation, nearest/no automatic mipmaps. Fresh DPR2 backing 2136×1000 for CSS1068×500. Broader camera/device acceptance remains separate. |
| F — Initialization/cleanup | PASS | L19 preferWorkers false and unsafe-eval import retained; tests cover abort/init failure, one app/ticker/observer per mount, idempotent disposal and texture ownership. Preview closed and server stopped after QA. |
| Atlas — loading/URLs/required keys | PASS / RESOLVED | `atlas.ts` parses generated Pixi sheets from Vite PNG imports, metadata bundled. Two pages and required keys resolve; source PNGs/sidecars/palette are absent from runtime bundle. Missing keys/version mismatch throw instead of unrelated fallback. |
| Atlas — trim/anchors/extrusion | PASS / RESOLVED | All 193 source frames round-trip pixels/2 px extrusion; sourceSize/spriteSourceSize restore canvases. Base/ordinary/occupant/emissive share canonical anchor; only explicitly declared light/shadow centres differ, stable within each part. Negative E8 tests and actual Sprite trim/centre-position assertions pass. Original `(24,8)` contract example remains valid. |
| Atlas — failure/refcount/sampling | PASS / RESOLVED | Six real Pixi sheet tests cover shared leases, last-owner unload, partial-page and parse failures, retry, missing keys/version, disposed-resource guard, sampling and centres. Scene failure/abort cleanup tests also pass. |
| Atlas — deterministic output/budget | PASS / RESOLVED | 193 frames; character512×512/shared512×256; 1.5 MiB RGBA8 static + 4 MiB reserve = 5.5 MiB upper bound, budget rule8 MiB. Clean PNG/metadata/index hashes equal committed reference; native Windows proof below. |
| Legacy/production isolation | PASS | DEV + explicit `?room=fixture` selection precedes live-client construction; disclosure/DOM controls visible. Production JS excludes preview/fixture payload; normal legacy path/default and `/api/room`/snapshots unchanged. Backend/API/security regressions and import/AST contracts pass; no live DB/SSE world connection, Director/schema-v11/config/CSP change. |
| Camera modes/full zoom-DPR behavior | DEFERRED BY SPEC | R1A-12; shell backing/integer Overview primitives above are complete, not a claim of full camera or multi-device acceptance. |
| Lighting/emitter behavior | DEFERRED BY SPEC | R1A-13; neutral layers and anchor-position primitives do not implement lighting. |
| Live coexistence/Edit Mode/cutover | DEFERRED BY SPEC | R1A-15, later owner-edit and R1b gates; no production activation or owner interaction execution. |
| Final art/face blind test/devices/performance | DEFERRED BY SPEC | Final artwork and face-size/readability approval, real tablet/phone QA, performance/soak remain their accepted gates. No production-ready claim. R1A-18 independent Linux reproduction remains explicit. |

### Fresh local validation

macOS, Node24.16.0/pnpm12.9.1 with unchanged frozen lockfile; Pixi8.21.0. Commands from `frontend`:

```sh
pnpm install --offline --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm exec vitest run src/world-room/presentation.test.ts --testNamePattern 'L11 independent expected-depth ring' --reporter=json --outputFile=/private/tmp/r1a11-closure-depth.json
```

**423 Vitest cases / 20 files PASS, 0 failures** (includes 215 renderer cases and six atlas cases); **65 Node asset/bundle cases PASS, 0 failures**. Explicit depth rerun: 144 ring + two supporting cases PASS; these are subsets, not added to the full count. ESLint, TypeScript and production build PASS; bundle report two hashed pages, zero raw source files, no production fixture preview. No test edits or weakened assertions.

From `backend`:

```sh
uv sync --locked --offline
uv run pytest tests/api/test_world_api.py tests/api/test_api_security.py tests/security tests/world/test_oracle.py tests/world/test_harness.py tests/world/test_contracts.py -q -p no:cacheprovider
uv run python -m tests.api.world_contract_export
uv run lint-imports --no-cache
```

**237 backend/API/security/Oracle/Harness cases PASS, 0 failures**; exact OpenAPI/derived TypeScript/five fixture exports PASS; **10 import contracts kept / 0 broken**. No Python changes, so no new Ruff/mypy run required; historical CI covers them. Documentation links/counters/append-only history and `git diff --check` PASS.

Legacy/protected paths show no implementation differences between pre-shell R1A-10 integration `e3a0316` and current HEAD: backend, deployment, old Room/API/state and dependency lockfile unchanged by shell/atlas integration. Original `tests/core/test_simulation.py` digest remains **`458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917`**, source/dependencies unchanged; full simulation and Full Release Gate were not rerun. This batch changes documentation only.

### Historical native Windows / integration evidence

PR #12 feature `5a5c4b6378060b0d925582e61cd857778cf8259f` merged at `7b45af4`. [Run38144587116](https://github.com/payola469/Maplegotchi/actions/runs/38144587116) completed all five jobs successfully: Ubuntu/Windows backend, frontend, ShellCheck and **art reproducibility (windows-latest)**. Inspected native job114485169135 logs: 65 tests PASS, including clean macOS-reference PNG/metadata/index equality; following frontend build/bundle check PASS with two hashed pages/no raw source/preview. Index SHA-256 `5ee8f05364b6a9f42c1a75d4ee2b2b219dbc5648d636413241115491a060e833`; page/metadata hashes in [R1A-14 evidence](maple-room-r1a-14-asset-pipeline.md) and machine reference unchanged. This is historical PR-head native CI, not a new Windows run on the merge SHA in this local macOS batch. Ubuntu CI success does not close R1A-18's separately required independent Linux handoff.

### Fresh browser verification

Codex in-app browser, local `http://127.0.0.1:5177/?room=fixture`, **default viewport1280×720, DPR2**. Actual WebGL preview ready; canvas2136×1000 device pixels for CSS1068×500. Full eight-region house, seven doors, atlas floors/walls/windows/furniture and Maple body/face visible. No missing textures, visible extrusion seams or implausible depth ordering at tested scale. Idle feet `(344,253)`; fixed +375 ms right/walk frame3 at `(368,253)`. Clicked Play; observed progression +591 ms `(381.82,253)`/frame0, then automatic stop +2750 ms `(520,253)`/stationary frame0. Clear synthetic disclosure, native DOM labels/buttons/slider and accessible room summary retained; no horizontal page overflow (scrollWidth1280).

Console warnings/errors **zero**. Saved `r1a11-closure-walking.jpg` and `r1a11-closure-arrival.jpg` outside Git in the task visualization directory. No viewport override, no real-device/mobile/performance/soak or untested-DPR claim. Temporary tab closed and preview server stopped. Cleanup behavior additionally exercised by unit tests.

### Completion recommendation and documentation scope

**Overall PASS for original R1A-11 closure criteria. R1A-14 dependency RESOLVED on the merged tree. R1A-11 — READY FOR OWNER ACCEPTANCE / CLOSURE.** Proposed status is **REVIEW / CLOSURE REVIEW PASS / OWNER ACCEPTANCE PENDING** until owner accepts and closure documentation is integrated. No blocker requires a new design decision. Deferred features above do not redefine renderer-shell completion.

Eight documentation files changed: CLAUDE, architecture current pointer, frontend notes, Master Plan, checklist, append-only worklog, R1A-11 evidence and R1A-14 merge pointer. Checklist20 total / 11 DONE / 1 REVIEW / 8 TODO. R1A-14 accurately DONE / OWNER ACCEPTED / MERGED; R1A-12/13/15–20 TODO. Prior evidence/worklog entries preserved. No runtime/source/test/art/contract/spec/schema/pin correction, commit, push, PR, merge, deployment or production access performed. Await owner review.
