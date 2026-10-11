# R1A-12 — Camera, Zoom and DPR Behaviour

**Status: DONE / OWNER ACCEPTED / MERGED — STEP137 reconciliation, 2026-10-11.** Baseline `cd328010a71f2cbcb1d0aee9f59ce925132447ae` (PR #13 merged); branch `codex/r1a-12-camera-zoom-dpr`, existing isolated worktree. R1A-11 and R1A-14 DONE / OWNER ACCEPTED / MERGED. STEP135 owner-authorized commit, normal push, PR and CI inspection; no merge, deployment or production access.

PR14 merged into `v0.2-development` at `48897c8e6b81a674441f089336930ba20ae53913`; verified on STEP137 fetch. STEP135/134B evidence and prior publication status below remain historical. Camera code unchanged by lighting work.

## Binding inputs and owner clarification

Locked [ADR-0041 L13–L15](../adr/0041-art-technical-contract.md) → accepted ADR-0035–0040 → [Final Spec §O](../architecture/maple-room-final-design-spec.md#o-camera-fit-spec-check-against-locked-l13l15) → proposed Future Architecture §9.3. Read Master Plan/checklist/history, R1A-10 DTO boundary, R1A-11 closure, R1A-14 atlas evidence, spike §§5.1/5.4 and existing frontend. No inaccessible original conversation evidence claimed.

Owner-approved STEP 134 CONTINUE clarifies only §O Follow counts: reference baseline DPR 1 values, also reproduced at integer DPR 2/3; fractional DPR varies with integer-quantized Zd. Preserve original table and L13/L14 unchanged. Desktop regression examples are recorded there and tested independently.

## Architecture and implementation checkpoints

1. Pure `camera.ts`: typed request/result, backing selection, L1–L4 formula, coordinate transforms, supplied house/region bounds, visible spans, Overview fitting, Follow dead-zone/clamping and Focus. Completion: independent table/boundary/negative/determinism tests.
2. Scene integration: one existing Pixi ticker, per-render DPR and host measurement, validated ResizeObserver device box, integer device transforms; reset tracking on size/DPR/mode/zoom/region changes. Completion: recording-renderer resize/DPR/lifecycle/route tests; preserve atlas/depth/animation.
3. Fixture-only DOM integration: mode/zoom/region controls, useful focusable room list/current-room highlight, open/closed truth, responsive layout and reduced motion. Completion: DOM tests and actual browser QA. No live API/SSE, world mutation or legacy default change.
4. Full frontend/asset and relevant backend/security/export/import regressions; browser matrix; documentation integrity and consolidated self-review. Completion: actual results below, REVIEW pending owner acceptance.

## Coordinate spaces and modes

Tiles and immutable rectangles are DTO geometry. World pixels = tile coordinates × supplied tile size, with backend feet offsets. Backing dimensions are device pixels, from a valid `devicePixelContentBoxSize` within one pixel of rounded CSS×DPR, else rounded fallback; nonfinite/nonpositive dimensions reject. Hidden/zero-size hosts pause drawing and resume on the existing ticker. Recheck DPR every draw, including no resize event. Pixi resolution1/autoDensity false/WebGL/nearest/no-mipmap/security flags unchanged. `device = world × Zd + integer translation`; CSS only determines canvas display size.

Overview chooses largest L1–L4 fitting complete house; letterboxes, else hides cropped canvas and uses DOM room list. Follow uses selected L, a centered 25%-width/height dead-zone, clamped to house with letterboxing on smaller axes. Presentation easing is provisional 18% per nominal 60-Hz frame using supplied ticker elapsed time, capped at100ms after tab suspension; continuous accumulator avoids integer-rounding stall, output always whole device pixels. Initial view and viewport/DPR/zoom/target changes snap to a safe view. Reduced motion snaps rather than easing; no second camera animation loop.

Focus chooses largest fitting L including supplied north band, both bordering side columns (including shared ownership) and exterior south cutaway. Read structural cells, never duplicate backend wall derivation. Missing target hides the scene and leaves accessible DOM controls/error. Oversize Focus uses L1, centers Maple when her supplied feet tile belongs to selected floor/passage, otherwise region center; clamp to house. Closed placeholders may be viewed without implying access. Camera never mutates Maple or routes.

## Preview, defaults and handoff

Explicit development fixture gate retained. Follow level is a configurable **provisional preview test setting**, not a device product default. Default per form factor stays **UNDECIDED**. DOM owns all text/buttons/selects/status. Canonical IDs/kinds/status come from DTOs; current room derived for presentation from supplied floor/passage ownership. Keyboard room buttons select Focus without moving Maple, retaining DOM focus when Overview fallback activates. Responsive host caps at measured806×484 on wide layout; tablet/narrow layout can fallback honestly, no forced CSS shrinking of the world.

R1A-15 receives the camera request/result and existing scene update boundary; still needs separately authorized live source/coexistence/stale-state integration. R1A-13 lighting, owner Edit Mode, final art/face size, real-device performance/soak and R1b activation remain outside this scope.

## Validation matrix and evidence

Planned: DPR1/1.25/1.5/2/3 × L1–L4; exact formula thresholds/cap; invalid viewport/DPR/targets; spec Overview tablet matrix and phone fallback; actual north/placeholder/Hall bounds and maximum fitting levels; oversize Hall inside/outside; four edges/corners and route progress; deterministic easing/no drift, reduced motion; one-render DPR switch; lifecycle cleanup; accessible DOM; no production fixture payload. Browser evidence will distinguish emulation from native observations. No real-device or performance-budget acceptance claim.


## STEP 135 — Owner acceptance and repository integration preparation (2026-10-11)

Owner accepts the implementation and STEP134B browser QA. **REVIEW / OWNER ACCEPTED / MERGE PENDING** until the accepted PR merges. Fetched `origin/v0.2-development` still equals baseline `cd328010a71f2cbcb1d0aee9f59ce925132447ae`; feature branch had no remote ref before publication. Final reviewed manifest is18 files (the seven STEP134B documentation updates overlap it), with no unrelated files, secrets, generated artifacts or QA screenshots/logs included.

Fresh local results: **461 Vitest cases /13 files PASS,0 failures**, comprising428 camera/world-room/legacy-room cases and33 frontend architecture guards/API fixture contracts/legacy App cases. Commands: `pnpm exec vitest run src/world-room src/room src/main.test.tsx` (no main.test.tsx exists; actual10 matched files/428 cases), then `pnpm exec vitest run src/guards.test.ts src/api/world-contracts.test.ts src/ui/App.test.tsx` (3 files/33 cases). ESLint, TypeScript and production frontend build PASS; bundle check reports2 hashed atlas pages,0 raw sources,`productionPreview:false`. Logs under `/private/tmp/r1a12-step135-*`.

Earlier accepted results retained, **not fresh reruns**:511 frontend tests,65 asset/bundle tests,237 backend/API/security/Oracle/Harness tests,144 depth-ring cases (also covered by the fresh world-room tests),10 import contracts and exact OpenAPI/types/five-fixture exports. STEP134B browser results below remain historical accepted evidence:20/20 DPR/zoom,20/20 stationary images,749 integer walking frames,5/5 reduced motion and5/5 live CDP changes. Both software-WebGL readback warnings remain disclosed.

Final binding/safety review PASS: L13 backing/render/sampling, exact L14 formula/bounds and L15 modes preserved; §O reference clarification is the only approved specification amendment. Legacy default/Room, backend/Director/API/SSE, CSP/Origin policy, schema, atlas inputs, Oracle/Harness and simulation pin unchanged. Fixture initialization still precedes all live initialization under an explicit DEV-only gate; production bundle excludes preview payload. No production world activation. Default zoom UNDECIDED; physical-device/monitor-transition and performance gates deferred. Existing worklog entries remain append-only. Current integrated counters12 DONE/1 REVIEW/7 TODO (60%); intended after merge13 DONE/7 TODO (65%). Commit/PR/CI results are reported after execution, not assumed here. No merge or deployment authorized.

## STEP 134B — Fractional DPR browser QA closure (2026-10-11)

**PASS — the outstanding local browser QA gap is closed. R1A-12 remains REVIEW / PENDING OWNER ACCEPTANCE.** Same worktree/branch and HEAD `cd328010a71f2cbcb1d0aee9f59ce925132447ae`; existing implementation preserved. No camera correction, dependency addition, locked-rule change or test-suite rerun was necessary.

Tool: bundled Playwright **1.62.1**, local Google Chrome **154.0.8037.98**, headless WebGL with ANGLE SwiftShader (`--use-angle=swiftshader --enable-unsafe-swiftshader`). Fresh contexts explicitly set `deviceScaleFactor`; browser `window.devicePixelRatio` matched every requested value. This is actual local browser rendering under emulation, not physical multi-display/device QA or a GPU performance measurement.

Desktop measured host and canvas CSS dimensions **806 × 484** at every DPR. Canvas attributes and camera backing dimensions matched; backing selection stayed within the accepted one-device-pixel tolerance. All 20 Follow combinations had the exact locked L14 zoom and integer x/y translation. Overview fit the whole house at every desktop DPR (L1). Bedroom Focus selected the largest fitting level shown below.

| Actual DPR | Desktop backing pixels | Follow Zd at L1 / L2 / L3 / L4 | Bedroom Focus | Result |
| --- | --- | --- | --- | --- |
| 1 | 806 × 484 | 1 / 2 / 3 / 4 | L3 / Zd3 | PASS |
| 1.25 | 1008 × 605 | 1 / 2 / 4 / 5 | L2 / Zd2 | PASS |
| 1.5 | 1209 × 726 | 1 / 3 / 4 / 6 | L3 / Zd4 | PASS |
| 2 | 1612 × 968 | 2 / 4 / 6 / 8 | L3 / Zd6 | PASS |
| 3 | 2418 × 1452 | 3 / 6 / 9 / 12 | L3 / Zd9 | PASS |

Fractional reference spans reproduced from actual backing: DPR1 L2 25.1875×15.125 / L3 16.791667×10.083333; DPR1.25 L2 31.5×18.90625 / L3 15.75×9.453125; DPR1.5 L2 25.1875×15.125 / L3 18.890625×11.34375. No production literals added.

Responsive contexts used viewport widths686 and380 (actual hosts654×392.72 and348×208.97 CSS pixels). Tablet Overview and Central Hall Focus fit at DPR1.25/1.5; tablet Overview falls back and Hall is oversize L1 at DPR1/2/3. Phone Overview falls back at all five DPRs, and Central Hall Focus remains visible at L1/fitsfalse with house clamping. These are measured browser boxes, not the exact654×392/348×209 unit-test reference boxes. The fractional tablet fits follow quantized zoom; Hall is not necessarily oversize at every DPR.

Follow playback reached2750ms in each context; **749 sampled animation frames** had integer translations, with changing camera position during walking and stable arrival. Atlas sampling was inspected separately at draw time: actual128×1024 and512×512 textures both use `NEAREST` (9728) for min/mag filters in all20 DPR/zoom combinations; CSS `image-rendering: pixelated`. Each combination's two stationary canvas screenshots were byte-identical after settling (**20/20**). Fractional-DPR Focus screenshots visually show crisp pixel boundaries without obvious blur/seams. Integer motion and stationary equality support the no-shimmer check; no real-device perceptual/soak certification is claimed.

**Reduced motion PASS (5/5 contexts):** explicit `reducedMotion: "reduce"`, browser media query true, automatic playback disabled. Route-time jump0→2750 produced only old/final camera translations, no intermediate easing values. Final positions independently match the25% dead-zone/clamp calculation. Overview/Focus transitions also use direct selection; existing implementation tests remain authoritative for all mode boundaries.

**Live DPR PASS (5/5 changes):** on one existing page at Follow L3, CDP `Emulation.setDeviceMetricsOverride` changed1→1.25→1.5→2→3→1 without reload/navigation. An animation-frame sampler registered after the existing renderer ticker captured the first frame reporting each new browser DPR. In every such first frame, camera DPR, exact zoom, canvas backing and integer translation already matched;32 sampled new-DPR frames had zero stale-DPR mismatches. This verifies update by the first observed animation frame in this browser, corroborating the one-ticker renderer tests. It is not a physical monitor transition latency measurement.

Main five-DPR matrix: zero browser console errors/page exceptions. Two Chrome software-WebGL `GPU stall due to ReadPixels` performance warnings occurred during screenshot readback; no missing-texture, context-loss or application error was observed. These warnings are recorded rather than suppressed. Test-harness-only assumptions were corrected: native select names include option text, fallback hosts are intentionally hidden, and fractional tablet Hall can fit. Application code was unchanged.

Preserved evidence: **511 Vitest/21 files (88 new),65 asset/bundle,237 backend/API/security/Oracle/Harness tests PASS**, TypeScript/ESLint/build/API exports PASS and10 import contracts kept. No suite rerun or baseline/simulation change. Only seven current documentation/evidence files were updated in STEP134B; prior STEP134 historical observations below remain intact.

Evidence outside Git:

- [Browser matrix and live-frame records](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a12-step134b-browser.json)
- [20 nearest-filter/stationary-image records](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a12-step134b-sampling.json)
- [DPR1.25 Focus screenshot](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a12-dpr-1.25-focus.png)
- [DPR1.5 Focus screenshot](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a12-dpr-1.5-focus.png)
- [DPR3 Focus screenshot](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a12-dpr-3-focus.png)

Selected evidence screenshots retained; transient screenshot buffers discarded. QA browser contexts/processes closed and local preview server stopped after validation. Owner acceptance is recommended for R1A-12; real-device QA, final per-device default zoom and performance budgets remain their existing deferred responsibilities. No GitHub integration or other workstream started.

Final STEP134B documentation checks: `git diff --check` and new-file whitespace PASS;104 relative links resolve; checklist remains20 total/12 DONE/1 REVIEW/7 TODO. Worklog HEAD bytes preserved as prefix, index empty and HEAD unchanged. All13 unrelated worktree HEAD/status snapshots match; local `v0.2-development` still `40f0eb76166560de9475ca4f834919ca04f2a8ef`. Preview exited with SIGINT and port5178 has no listener.

## STEP 134 CONTINUE — historical validation and consolidated self-review

**Automated implementation gates PASS; overall CONCERN limited to unavailable native fractional-DPR visual QA.** Final 511 Vitest cases /21 files PASS, 0 failed: 88 new cases (79 pure camera, seven additional recording-scene cases, two DOM cases). Full world-room group303 cases includes existing renderer/atlas guards, 144 depth-ring cases/zero mismatches plus two supporting cases (subsets, not additive), route/walking and six real atlas-loader tests. 65 Node asset/bundle cases PASS; 193 frames, two pages, original PNG/metadata/index hashes and5.5MiB resident upper bound unchanged. ESLint, TypeScript and frontend production build PASS. Build report: two hashed atlas pages, zero raw source files, productionPreview false.

237 backend/API/security/Oracle/Harness cases PASS; exact OpenAPI/TypeScript/five fixture exports PASS; ten import contracts kept /zero broken. No Python changes; no new Ruff/mypy required. Simulation pin/source unchanged; full simulation and Full Release Gate not rerun. The first full frontend run identified a presentation variable name matching the broad availability guard; renamed that variable and reran all guards unchanged. Final tests have no failures or weakened assertions.

Commands: `pnpm install --offline --frozen-lockfile`, `pnpm lint`, `pnpm typecheck`, `pnpm test`, final `pnpm exec vitest run --reporter=json --outputFile=/private/tmp/r1a12-vitest.json`, `pnpm build`; backend `uv sync --locked --offline`, `uv run pytest tests/api/test_world_api.py tests/api/test_api_security.py tests/security tests/world/test_oracle.py tests/world/test_harness.py tests/world/test_contracts.py -q -p no:cacheprovider`, `uv run python -m tests.api.world_contract_export`, `uv run lint-imports --no-cache`. Local logs are outside Git under `/private/tmp/r1a12-*`.

### L13/L14/L15 and Spec O evidence

- Backing: valid device box within one pixel of rounded CSS×DPR accepted; invalid/nonfinite/zero/negative/stale CSS-sized boxes fall back. Invalid viewport/DPR rejects in pure math; zero-size scene pauses and resumes. Five DPR values × four levels, formula boundaries and max12, deterministic coordinate round trips, clamping and integer translations pass.
- DPR changes: recording-renderer tests change DPR1/1.25/1.5/2/3 without ResizeObserver and invoke exactly one existing ticker callback; backing, zoom and integer transform update in that callback. Browser viewport emulation also switched observed DPR2→1 and reset1→2 with correctly resized backing; native display-change frame latency was not instrumented.
- Overview: exact desktop/tablet/phone §O matrix at nine DPR samples PASS; additional desktop DPR1–3 hundredth increments fit. Shrunken desktop fallback cannot claim cropped house fits. Browser native806×484/DPR2 gives1612×968 backing, L1/Zd2/x102/y68. Emulated654×392.72 rounds to654×393 atDPR1 and falls back;348×208.97 rounds to348×209 and falls back. Pure tests use exact requested654×392 and348×209 boxes.
- Follow: owner-approved decimal regression table reproduced without production literals. Four world edges/corners, supplied walking routes, centered25% dead-zone, deterministic easing, reduced-motion snapping and stationary convergence/integer output PASS. Baseline §O visible spans derive from dimensions; fractional spans intentionally vary. No route generation/actor mutation.
- Focus: exact DTO floor/band/shared-side/cutaway bounds; all eight targets and five DPR values tested. At worst sampled DPR: north rooms desktop/tabletL2, phoneL1; placeholders desktopL2–L3/tabletL2/phoneL1. Hall tablet/phone usesL1/fitsfalse, Maple center inside and region center outside, clamped. Missing target explicitly unavailable. Browser native bedroom Focus atDPR2 selectsL3/Zd6, x0/y0 due world-edge clamping; entire target fits and Maple remains in Hall. Closed-region viewing does not open doors.

### Actual browser observations and limits

Codex in-app WebGL browser on localhost, fresh boot at1280×720/nativeDPR2. L1–L4 Follow observed Zd2/4/6/8, integer translations; full house Overview, north-room Focus, atlas artwork, face/feet and clamping visually checked. Fresh-boot console warnings/errors **zero**; during earlier HMR editing, one inherited Pixi Assets-already-initialized warning occurred. Closing that tab and testing a fresh boot confirmed clean startup; no claim that the HMR warning never occurred.

Explicit viewport overrides1440/820/390×900 use emulatedDPR1 in this tool: all L1–L4 tested, integer translations and no horizontal overflow. Actual room boxes806×484,788×473,358×215 (rounded backing); do not confuse actual page sizes with Spec's measured reference boxes. Additional686/380 widths reproduce near654×392 and348×209 room boxes. Native DOM buttons activated with Enter/Space, current Hall highlighted, closed labels truthful, focus retained across fallback→Focus. Overview fallback now replaces blank viewport with the same room-list nodes; focus is not removed. Controls wrap without clipping at tested widths.

Phone Follow playback observed +215ms feet(357.82,253), right/frame1, then automatic arrival+2750ms feet(520,253), stationary/frame0; camera x changed from-509 to-861 atL2/Zd2 and remained clamped. No missing textures or visible seams observed in inspected native/emulated views. These are local browser observations, not real-device, performance-soak or all-DPR shimmer certification.

**QA limitation:** the available browser viewport API supports width/height only, not DPR or reduced-motion overrides. Actual fractional-DPR WebGL QA at1.25/1.5/3 and live reduced-motion emulation could not be performed. Those values and snapping are covered by pure/recording-renderer/DOM tests, not claimed as native browser evidence. Full native fractional-DPR visual acceptance remains outstanding; owner review may assess this explicit limitation. No product default selected. No performance-budget measurement/acceptance claimed.

Screenshots outside Git: `r1a12-phone-fallback.png` and `r1a12-bedroom-focus.png` in the task visualization directory. Temporary browser overrides reset, tabs closed and server stopped after QA.

### Scope and handoff conclusion

Implementation review found no remaining code defect or binding conflict. Scene retains one ticker/observer, abort/failure/disposal ownership and original atlas loading; camera easing advances only on ticker deltas, not update/resize callbacks. No backend, dependencies, assets, accepted ADR, Oracle/Harness, schema, production config, legacy Room, API/SSE or simulation-pin changes. Only approved §O reference clarification changes the Final Spec. All original worktrees and local-only40f0eb7 preserved. Worklog append-only; relative links, counters and `git diff --check` checked.

At STEP134 CONTINUE, R1A-12 remained REVIEW / PENDING OWNER ACCEPTANCE with the fractional-DPR browser QA gap outstanding; STEP134B above closes that local browser gap. R1A-15 may reuse the camera request/result/update boundaries after separate authorization; live coexistence/source integration is not implemented. R1A-13 and all other later-workstream responsibilities remain unchanged.


## Changed-file manifest

- `CLAUDE.md`
- `docs/architecture.md`
- `docs/architecture/maple-room-final-design-spec.md`
- `docs/frontend.md`
- `docs/implementation/maple-room-r1a-11-pixi-renderer-shell.md`
- `docs/implementation/maple-room-r1a-12-camera-zoom-dpr.md`
- `docs/implementation/maple-room-r1a-14-asset-pipeline.md`
- `docs/implementation/maple-room-r1a-checklist.md`
- `docs/implementation/maple-room-r1a-plan.md`
- `docs/implementation/maple-room-r1a-worklog.md`
- `frontend/src/world-room/Preview.test.tsx`
- `frontend/src/world-room/Preview.tsx`
- `frontend/src/world-room/camera.test.ts`
- `frontend/src/world-room/camera.ts`
- `frontend/src/world-room/presentation.ts`
- `frontend/src/world-room/preview.css`
- `frontend/src/world-room/scene.test.ts`
- `frontend/src/world-room/scene.ts`

Final documentation checks: 18 scoped files, 103 relative links valid before this code-path-only manifest addition, checklist counters consistent, worklog original bytes preserved as prefix, tracked/untracked whitespace PASS. Index empty; HEAD unchanged. Temporary server exited and port5178 has no listener.
