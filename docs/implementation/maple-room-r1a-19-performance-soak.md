# R1A-19 — Performance and soak validation

**STEP 153, 2026-10-12: REVIEW / OWNER ACCEPTED / MERGE PENDING.** Owner accepted STEP 152 local measurements and authorized review, fresh checks, commit, normal push, PR and CI inspection. No merge is authorized. Historical STEP 152: PASS / REVIEW / pending owner acceptance. All six locked renderer budgets pass. R1A-01–18 are DONE / OWNER ACCEPTED / MERGED; R1A-19 is REVIEW / OWNER ACCEPTED / MERGE PENDING; R1A-20 is TODO. Counters: 18 DONE / 1 REVIEW / 1 TODO = 90%. Separate owner authorization is required for merge.

## Baseline, scope and plan recorded before instrumentation

Verified PR #19 merge `26c4a959322aaab1d38779739cea583be75455ea`, merged 2026-10-12T07:50:21Z. Main `v0.2-development` was clean, fetched and fast-forwarded only. Worktree `C:/GitHub/Maplegotchi-worktrees/r1a-19-performance-soak`, branch `codex/r1a-19-performance-soak`, begins at that exact baseline. R1A-15–18 and unrelated worktrees/branches were preserved, including the existing `codex/r1a-01-baseline` head and the Mac-only commit without reconstruction.

Binding inputs reviewed: CLAUDE.md, Master Plan R1A-19, checklist/worklog, Final Design Spec, ADR-0040/0041 and L20/L21, frontend/architecture/autonomy, accepted R1A-05 and R1A-10–18 evidence, art contract and existing browser/test infrastructure. No material architectural conflict was found.

The initial plan identified missing actual render timing/draw submissions, frame intervals, retained heap and GPU allocation tracking. It specified test-only Playwright response instrumentation, warmup separate from measurement, repeated desktop/4× phone scenarios, two contiguous desktop frame windows, at least 600 seconds of soak, comparable post-GC endpoints, offline backend stress timings, fresh regression/static/build/security checks and append-only history. No blind optimization or runtime redesign was planned or performed.

[Machine-readable reviewed results](../fixtures/maple-room/r1a-19/windows-performance.json) retain per-trial distributions, environment, resources, backend raw nanosecond samples and local raw-evidence hashes. Complete unchanged browser timing arrays and corrected allocation records are now archived in [compressed raw JSON](../fixtures/maple-room/r1a-19/windows-browser-raw.json.gz). Console/command logs remain in ignored `var/r1a19/`. Results below are historical STEP 152 measurements/checks; fresh STEP 153 checks are identified separately.

## Environment and candidate

Windows 11 Home 10.0.26200; Intel i5-12400F, 6 cores/12 threads; NVIDIA RTX 3060, driver 32.0.15.9186; physical display 1920×1080 at 60 Hz. Python 3.12.10, uv 0.13.0, Node 24.20.0, pnpm 12.3.4, Playwright 1.62.1, installed Chrome 154.0.8037.98. Headless Chrome; development Vite 8.3.1 at loopback; visible document and `document.hasFocus() === true` at environment capture. New Room uses WebGL2, actual renderer:

`ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 (0x00002504) Direct3D11 vs_5_0 ps_5_0, D3D11)`

This run used hardware ANGLE/D3D11, not software WebGL. Desktop viewport/screen emulation: 1440×1000, actual DPR 1. Phone: 390×844, actual DPR 3, mobile/touch emulation, actual CDP `Emulation.setCPUThrottlingRate` rate 4. Independent fixed-work calibration retained every result: normal median 1.1 ms; throttled median 4.1 ms (3.73× observed, with JIT/scheduling variation). This corroborates the applied 4× CDP setting; it is not a physical-phone performance claim.

The authorized `?room=fixture` coexistence path renders the canonical 44×26 house: 8 regions, 7 doors, 28 objects and 1,971 scene-tree nodes. Accepted 193-frame placeholder atlases remain byte-identical. The harness substitutes only the development fixture module response with accepted R1A-17 `base_world`/catalog and `initial`, `distant_departure` and `activity_observe` snapshots. Geometry and fixtures on disk remain unchanged. The accepted long route has 53 steps / 13,250 ms. The visible UI retains FIXTURE / DEMO disclosure; the R1A-17 extension is explicitly synthetic here. No client pathfinding or live AI is used. New mode made no API/SSE connection; Legacy QA uses offline read-only synthetic responses.

## Measurement boundary and aggregation

The browser intercepts only the actual Vite scene response, verifies each source anchor occurs exactly once, attaches after `app.init`, times `app.renderer.render` with `performance.now`, and delegates the original invocation unchanged. CPU timing includes synchronous Pixi CPU work and GL submission; it excludes simulation, the separately timed draw/update callback, browser compositing and GPU completion. No `gl.finish` is used. Draw counts wrap actual WebGL drawArrays/drawElements and native instanced variants, not sprites. The active renderer is WebGL2; no WebGL1 instanced-extension submissions occur in this measured path.

Nearest-rank p95 is sorted sample `ceil(0.95*n)-1`; zero-valued timings remain as reported at Chrome timer precision. All measured outliers are retained. Each short scenario has at least 2.1 seconds warmup and two 5-second measured trials. Gate CPU by the worst individual scenario/window/soak-segment p95 in each environment; gate draw calls by the maximum individual measured render. No fallback-only hidden phone Overview samples enter the CPU gate. The complete scene still mounts, and visible phone Follow/Focus/lighting scenarios draw it without scene culling.

Static canvas SHA256 is identical with and without the renderer timing wrapper: `288581c12d50ec89ad1c0948e03eb9a7ab6f0fd1ce942adc6f4a50a7d8a26cd0`. Instrumentation adds a small conservative measurement overhead; it is outside the shipped application. Window/document listener tracking is scoped to those targets; CDP DOM counters provide the broader endpoint check.

Expensive backend/regression jobs ran after the authoritative browser timings ended. During those timings only light evidence preparation and observation took place. Windows scheduling, timer precision, headless operation, development DOM diagnostics and GPU driver behavior remain environmental factors. RAF intervals measure browser scheduling, not physical display capture.

## Locked budgets

| Metric | Locked budget | Observed | Result |
|---|---|---|---|
| Actual draw submissions | ≤40 per measured render | 4 maximum; min/median/p95/max all 4 in visible scenarios | PASS |
| Desktop synchronous render p95 | ≤4 ms | 2.0 ms worst including soak; short-trial maximum 1.4 ms | PASS |
| Phone EMULATED 4× render p95 | ≤8 ms | 3.4 ms worst | PASS |
| Desktop intervals >33 ms in 60 s | 0 | 0 in each of two contiguous windows | PASS |
| ≥10-minute retained JS heap growth | <5,000,000 bytes | 621,924 bytes over 631.946 seconds | PASS |
| Resident texture/render-target bound | ≤33,554,432 bytes (32 MiB) | 12,656,568 bytes (12.070 MiB), no unknown allocation formats | PASS |

## Repeated scenario matrix

Numbers are render p95 in milliseconds for trials 1 / 2; counts are actual render samples per trial. Every visible trial has four actual draw submissions per render. L1–L4 and camera visibility were confirmed from the accepted DOM diagnostics, not inferred from control labels.

| Scenario | Desktop p95 (n1/n2) | Phone EMULATED 4× p95 (n1/n2) |
|---|---|---|
| overview-idle | 0.3 / 0.3 (301/301) | accepted Overview fallback; hidden, not timed |
| follow-long-L1 | 0.4 / 0.3 (301/301) | 3.1 / 3.1 (301/301) |
| follow-long-L2 | 1.2 / 1.3 (301/302) | 3.3 / 3.2 (301/301) |
| follow-long-L3 | 1.3 / 1.3 (301/301) | 3.1 / 3.4 (301/302) |
| follow-long-L4 | 1.4 / 1.2 (301/301) | 3.2 / 2.9 (301/301) |
| focus-long | 0.8 / 0.3 (301/301) | 0.9 / 0.9 (301/301) |
| activity-observe | 0.3 / 0.2 (301/301) | 1.4 / 1.1 (301/301) |
| lighting-transitions | 0.3 / 0.3 (301/301) | 3.2 / 3.3 (301/301) |

Short trials contain 4,817 desktop and 4,215 phone render samples. Two frame windows contain 7,202 desktop renders, and ten soak segments contain 36,010. All 52,244 measured visible renders are retained locally. Trial differences remain below their budgets; no failing authoritative trial was discarded or replaced. The earlier quick smoke runs are not acceptance measurements.

Desktop Overview shows the complete house at locked L1. Phone Overview cannot fit at locked integer zoom and correctly exposes the accepted accessible fallback; its hidden cheap render is explicitly excluded. Phone Follow L1–L4, Focus and lighting transitions are visible. Focus uses living_room; moving scenarios loop the accepted long travel via the DOM time control. Activity uses the accepted observe_server snapshot. Morning/afternoon/evening/night are exercised; eight lighting zones and seven atlas-backed hooks remain present. Rendering, camera and art source code are unchanged.

## Desktop frame windows

Both windows start after warmup with visible full-house Overview and long-route movement. GC and Room remounts are outside these two windows. Every RAF interval, including outliers, is retained.

| Trial | Intervals | Covered interval sum (ms) | p95 / p99 / max (ms) | >33 ms |
|---|---:|---:|---|---:|
| 1 | 3600 | 60000.800 | 16.800 / 16.900 / 17.200 | 0 |
| 2 | 3600 | 60001.200 | 16.800 / 16.900 / 17.200 | 0 |

## Ten-minute soak and cleanup

631.946 seconds wall duration contains ten measured 60-second segments (600.01+ seconds of rendering), plus control warmup/remount overhead. Segments cycle Overview/Follow/Focus, L1–L4 where applicable, the 53-step route and all lighting phases. Four controlled Legacy/New remounts occur during the soak; an earlier desktop cycle and a phone cycle make six tested round trips overall.

| Segment | Camera / level / phase | Renders | Render p95 (ms) |
|---|---|---:|---:|
| 1 | overview / L1 / morning | 3601 | 0.4 |
| 2 | follow / L2 / afternoon | 3601 | 1.8 |
| 3 | focus / L3 / evening | 3601 | 0.4 |
| 4 | overview / L1 / night | 3601 | 0.5 |
| 5 | follow / L1 / morning | 3601 | 0.5 |
| 6 | focus / L3 / afternoon | 3601 | 0.5 |
| 7 | overview / L1 / evening | 3601 | 0.5 |
| 8 | follow / L4 / night | 3601 | 2.0 |
| 9 | focus / L3 / morning | 3601 | 0.4 |
| 10 | overview / L1 / afternoon | 3601 | 0.5 |

CDP forced GC is performed at both endpoints after matching idle/Overview/morning state, stopped harness driver and stable warmup. Retained used JS heap: 16,819,804 → 17,441,728 bytes, +621,924 bytes. Periodic uncollected heap peaked at 34,443,572 bytes, showing normal GC churn rather than using a transient peak as retained growth. Backing storage: 8,923,315 → 8,923,274 bytes. CDP documents/nodes/listeners: 1/663/70 → 1/663/70.

Comparable resource endpoints: one New Application, one canvas, two pending RAF callbacks, two active ResizeObservers, zero SSE streams; tracked window/document listeners 18/1 unchanged. The harness drains frame arrays between segments; raw data is retained in Node rather than accumulated in page heap. Small retained probe metadata and JIT caches remain included in the conservative heap delta.

On every Legacy switch, New Application count reaches zero and its GL context is lost with tracked allocations cleared; Legacy owns the one replacement canvas and synthetic SSE stream. Returning to New stops Legacy SSE, loses the Legacy context, and returns to one New canvas/application with zero SSE. All earlier actual renderer contexts are lost, with one active renderer allocation set. Pixi's shared capability-test context is retained intentionally. Return-to-Legacy keyboard focus is the persistent selector in all six round trips. No console/page errors or broken assets were recorded.

## Resident allocation accounting and narrow harness correction

GL allocation hooks track texImage2D/texStorage2D dimensions, formats, mip levels, renderbuffers, multisample counts and deletion. Unsupported allocation paths would be recorded as unknown and fail the texture gate. None occurred. Active New GL attributes have antialias=false, so no unaccounted MSAA attachments. Two actual RGBA8 atlas allocations are 128×1024×4 and 512×512×4 = 1,572,864 bytes; two 1×1 utility textures add 8 bytes. There are no extra resident mip levels or offscreen render targets in the observed path.

Default framebuffers are conservatively reserved at 16 bytes per backing pixel (two color buffers plus depth/stencil allowance). The largest observed New backing is 1074×645 in DPR-3 phone emulation. Thus 1,572,872 + 1074×645×16 + 16 for the retained 1×1 capability framebuffer = **12,656,568 bytes**. Desktop backing is 806×484. This estimates resident texture/render-target storage, not compressed PNG size or total GPU process/driver memory; driver metadata is outside the texture-budget definition.

Post-run review found the first probe initialized non-rendering capability-context dimensions to zero. The authoritative timing output's original bound was 12,656,552 bytes, undercounting that retained framebuffer by 16 bytes. The test-only probe now captures actual initial drawingBuffer dimensions. A fresh allocation matrix with the corrected probe confirms the capability context is 1×1 and the corrected bound is 12,656,568, with no unknown formats. Its short timings are explicitly non-authoritative and ran alongside regression validation; original CPU/frame/heap samples are preserved. The correction occurs at context creation outside render timing/warmup, so no full soak retry or application change was required. No threshold was relaxed.

Other pre-measurement harness corrections fixed control sequencing and a selector that matched the surrounding nav. Isolation QA corrected an immediate synthetic-fetch response race by delaying read-only delivery 250 ms, and permits the accepted development switcher/pure gate while forbidding actual New renderer/fixtures. Initial failed harness logs remain local. No accepted Room implementation defect or optimization was found.

## Backend stress timings

Independent exhaustive unweighted BFS over all 431 canonical walkable cells establishes the 57-step shortest-path diameter, (1,6) → (42,4); actual A* agrees. The accepted 53-step activity route is tested separately. Closed/blocked targets, synthetic disconnected search exhaustion, blocked/invalid-source recovery, all eight activities and no eligible candidate, valid/invalid placement, valid/S10/multi-S1-S15-S17 layout validation are measured. The synthetic disconnected mask is an emergency/search stress input, not an accepted layout change.

Each pure synchronous call has one correctness reference, three untimed warmups and 30 raw perf_counter_ns trials. Fixture construction/mutation, diameter discovery, equality assertions and serialization are outside timings. Equal outputs are asserted each trial. These are explicitly tested stress cases, not an invented backend latency gate or a claim to exhaust all possible invalid inputs/CPU scheduling states.

| Case | min / median / p95 / max (ms) |
|---|---|
| path.initial-house-BFS-diameter | 3.1454 / 3.3011 / 3.9351 / 4.6916 |
| path.accepted-53-step-travel | 1.9245 / 2.0302 / 2.3216 / 2.3681 |
| path.closed-region | 0.0385 / 0.0389 / 0.0407 / 0.0443 |
| path.blocked-target | 0.0384 / 0.0388 / 0.0394 / 0.0431 |
| path.synthetic-disconnected-exhaustion | 4.8423 / 5.2157 / 7.7470 / 8.1312 |
| recovery.blocked-source | 0.1190 / 0.1210 / 0.1248 / 0.1250 |
| recovery.invalid-source-fallback | 0.0413 / 0.0423 / 0.0431 / 0.0459 |
| resolution.allowed-all-eight | 41.8737 / 45.1967 / 51.1158 / 51.5557 |
| resolution.no-eligible-candidate | 0.0485 / 0.0514 / 0.0525 / 0.0586 |
| placement.valid | 24.8232 / 28.5551 / 33.3252 / 34.5589 |
| placement.invalid-item | 0.0035 / 0.0037 / 0.0040 / 0.0043 |
| layout.valid | 84.6320 / 97.6698 / 109.4537 / 120.6213 |
| layout.invalid-S10 | 24.1356 / 25.6752 / 36.8987 / 38.0756 |
| layout.multi-S1-S15-S17 | 0.0495 / 0.0505 / 0.0633 / 0.0931 |
| resolution.idle | 2.1381 / 2.1770 / 4.2479 / 6.1299 |
| resolution.walk | 2.1291 / 2.1602 / 4.2582 / 4.7739 |
| resolution.sleep | 0.1356 / 0.1373 / 0.1427 / 0.1458 |
| resolution.read | 19.9352 / 21.8804 / 27.3400 / 28.7059 |
| resolution.write | 6.4744 / 6.6902 / 9.9241 / 12.2299 |
| resolution.observe_server | 2.0376 / 2.0827 / 4.0440 / 4.1018 |
| resolution.rest | 2.2235 / 2.2637 / 5.6306 / 6.7704 |
| resolution.think | 6.3260 / 6.8422 / 11.2809 / 11.3215 |

## Fresh deterministic simulation and regression validation

Full Windows backend pytest: **3,896 passed / 21 skipped in 223.99 seconds**. Skips: 18 Bash unavailable on the executable PATH; one POSIX/non-root permissions check; two Windows symlink-privilege cases. These are environment skips, not performance failures or Linux evidence. The Bash wrapper was not executed; its individual native checks were executed.

The full suite freshly executes the long R1A-17 grid test: three byte-identical 270-cycle traces, 2,608,335,000 logical ms (>30 days), 2,160 successful transitions, 65,340 movement steps, 71,821 events, maximum activity route 53 steps, zero recoveries/projection rejections, final tile (21,15), final idle. Reviewed grid digest remains `b3287b3d13ed406fc98ecc5be58494e9f3ac9df7fc4b0a70cedb6e85ad5500d3`. The original 30-day pin also freshly passes: `458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917`. Neither pin, Oracle/Harness or fixture was changed.

Fresh frontend: **586 Vitest tests / 25 files**, **119 Windows asset tests**, **6 measurement-statistics tests** (nearest-rank/outliers/empty-invalid/missing-environment/locked-threshold checks); 711 tests combined, no skips. Standalone assets:test also reran 119 passes. Discord 22 passed (0.17 s); Brain 28 passed (1.73 s).

Ruff check/format: backend 245 files, deploy 7; strict mypy 243 files; ten import contracts; exact world OpenAPI/TypeScript/five-fixture exporter; companion locked installs/Ruff/format/mypy; ESLint; TypeScript; actual production build and bundle guard; actual Windows atlas manifest; actionlint 1.7.12; all three ShellCheck 0.11.0 groups: PASS. Final ESLint reran after the isolation harness corrections. Backend security, forbidden-API/purity, Origin/CSP and read-only contract regressions are included in full pytest; production bundle negatives are included in the asset suite. No new production dependencies or lockfile changes.

## Production isolation

Fresh loopback browser QA: development `/` and production `/`, `/?room=fixture`, `/room/new?room=fixture` all render Legacy Pixi, one canvas, no actual New renderer/fixture module requests, no browser errors or horizontal overflow. Production has no development selector; development default retains its accepted switcher/pure gate. The actual build guard reports two hashed approved atlas pages, zero raw source files, productionPreview=false. Processed atlas PNGs remain in production for existing rendering; fixture data, preview renderer and simulation logic are excluded. Query/direct navigation cannot bypass compile-time gating.

No backend/API/SSE, schema, Director, CSP/Origin or production runtime source changed. All API responses in QA were synthetic and read-only. No production credentials, database or paolo-core access occurred.

## Reproduction, limitations and readiness

After locked frontend/backend installs, run from this worktree:

```powershell
pnpm --dir frontend exec vite --host 127.0.0.1 --port 5179 --strictPort
# Separate terminal, repository root; Playwright must be available.
# If external, set R1A19_PLAYWRIGHT to its module path and R1A19_CHROME as needed:
node frontend/tools/performance/browser.mjs --output var/r1a19/browser.json
# Optional CLI: --playwright <absolute-module-path> --chrome <absolute-executable>
# --quick is smoke/allocation validation only, never acceptance.
# Backend directory, with uv available:
uv run python -m tests.world.performance_benchmark
# Full native check equivalents are in scripts/check.sh and the CI workflow.
pnpm --dir frontend test
pnpm --dir frontend build
pnpm --dir frontend exec vite preview --host 127.0.0.1 --port 5180 --strictPort
# Separate terminal, repository root, after the production build:
node frontend/tools/performance/isolation.mjs --output var/r1a19/isolation.json
```

Use fresh evidence filenames for reruns to preserve previous raw measurements. Both browser helpers resolve an installed `playwright` module and Chrome channel by default. When tooling is external, pass `--playwright <module-path> --chrome <executable-path>` or set R1A19_PLAYWRIGHT / R1A19_CHROME. No application dependencies are installed by the helpers. Commands are local fixture-only; no database/backend server is needed.

PASS proves these R1a placeholder-art budgets on this Windows hardware/browser/configuration. It does not prove physical phone/tablet behavior, arbitrary browsers/GPUs, final production-art budgets, GPU completion latency, native Linux performance, seven-day production soak or B14/default-switch readiness. Existing accepted fractional-DPR QA is historical, not rerun here. Timing naturally varies; immutable fixture/digest checks do not.

**Historical STEP 152 conclusion:** No owner architecture/budget decision is needed. R1A-19 is ready for owner acceptance of the local evidence, with those explicit deferred limits. R1A-20 remains TODO and was not started. No commit, staging, push, PR, merge, deployment or production access. Local servers are stopped at final validation. Main remains clean and unrelated heads/worktrees unchanged. Worklog prefix is verified byte-for-byte; current counters/status and relative documentation links are audited.

## Historical STEP 152 changed-file manifest (15 paths)

- `CLAUDE.md`
- `backend/tests/world/performance_benchmark.py`
- `docs/fixtures/maple-room/r1a-19/windows-performance.json`
- `docs/frontend.md`
- `docs/implementation/maple-room-r1a-18-ci-linux-reproducibility.md`
- `docs/implementation/maple-room-r1a-19-performance-soak.md`
- `docs/implementation/maple-room-r1a-checklist.md`
- `docs/implementation/maple-room-r1a-plan.md`
- `docs/implementation/maple-room-r1a-worklog.md`
- `frontend/package.json`
- `frontend/tools/performance/browser.mjs`
- `frontend/tools/performance/isolation.mjs`
- `frontend/tools/performance/probe.mjs`
- `frontend/tools/performance/statistics.mjs`
- `frontend/tools/performance/statistics.test.mjs`

## STEP 153 integration review

Owner accepted STEP 152 evidence; R1A-19 REVIEW / OWNER ACCEPTED / MERGE PENDING. Progress remains 18 DONE / 1 REVIEW / 1 TODO = 90%; a separately authorized confirmed merge would yield 19/20 = 95%. R1A-20 remains TODO.

Narrow harness corrections remove machine-specific tool defaults, require two complete RAF interval sums (rather than overall elapsed setup time), fail full benchmark commands when budgets/errors/pixel calibration fail, and explicitly reject overflow in isolation QA. The retained 1x1 framebuffer contributes 16 bytes in the shared residency calculation, with deterministic coverage for disposal. No accepted hardware run is replaced or freshly claimed; the complete authoritative raw arrays and separate non-authoritative corrected allocation matrix are archived without selection or timing changes. Deterministic CI tests recalculate all 52,244 renders, per-row nearest-rank distributions, frame coverage, retained heap and corrected residency. Three backend measurement tests use a synthetic clock to check raw outliers, nearest-rank p95, untimed setup/warmup, stable results and independent BFS components. These execute through existing backend pytest and frontend `pnpm test`; no GPU timing gate or workflow change is introduced.

Fresh STEP 153 validation and exact final manifest follow. CI execution, PR URL and commit SHA are recorded in the PR and final integration report to avoid a self-referential evidence commit. No merge/deployment/production access is authorized.

### Fresh STEP 153 local validation (2026-10-12)

Full Windows backend: **3,899 PASS / 21 expected skips in 205.35 seconds**. Skips: 18 Bash unavailable, one POSIX/non-root permissions, two Windows symlink privileges. All three new measurement tests execute; R1A-16 properties and R1A-17 long/digest tests execute in full pytest. Original and grid pins are unchanged. Frontend **586 Vitest / 25 files**, **119 asset tests**, **11 measurement/archive tests**, total **716**; no skips. Standalone asset suite freshly reruns 119. Discord **22**, Brain **28** pass.

Backend/deploy Ruff/format, configured strict mypy, ten import contracts, exact world OpenAPI/TypeScript/five-fixture export, both companion locked installs/static gates, ESLint, TypeScript, production build/guard, actual Windows atlas manifest, actionlint 1.7.12 and all three ShellCheck 0.11.0 groups PASS. Initial Ruff rejected iterable concatenation in the new deterministic test; corrected to unpacking and final full Ruff plus focused measurement tests pass. No test assertion or budget was weakened. Native Bash wrapper was not run; equivalent Windows checks above were executed.

Fresh browser helpers run with explicit external Playwright/Chrome paths: desktop/phone quick smoke passes source anchors, screenshot equality, controls, two Room round trips, zero errors and corrected residency 12,656,568. Quick frame/heap gates correctly remain false because smoke durations are insufficient; this is not a new acceptance benchmark. Fresh isolation **4/4 PASS**: development default plus production default/query/direct-route remain Legacy Pixi, one canvas, no New renderer modules, no errors or overflow; production switcher absent. Actual production bundle reports hashedPages=2, rawSourceFiles=0, productionPreview=false. Raw fresh logs/JSON stay ignored in `var/r1a153/`; accepted full measurements stay unchanged in `var/r1a19/` and the reviewed archive.

Fresh repository/document audit verifies full changed-path scope, UTF-8/LF, local links, 18 DONE / 1 REVIEW / 1 TODO counters, unchanged main/unrelated heads, append-only STEP 152 worklog prefix and `git diff --check`. Remote base remains the expected baseline after fresh fetch. No source art, production code, locks, workflow, geometry or simulation pins changed. There are no credentials, profiles or screenshots in the manifest; the 120,222-byte gzip contains complete raw JSON measurements, not a browser trace/profile. Hosted CI will verify deterministic correctness and cross-OS atlas output; local RTX 3060 timing acceptance remains historical STEP 152 evidence.

### Final reviewed STEP 153 manifest (20 paths)

- `CLAUDE.md`
- `backend/tests/world/performance_benchmark.py`
- `backend/tests/world/test_performance_benchmark.py`
- `docs/architecture.md`
- `docs/fixtures/maple-room/r1a-19/windows-browser-raw.json.gz`
- `docs/fixtures/maple-room/r1a-19/windows-performance.json`
- `docs/frontend.md`
- `docs/implementation/maple-room-r1a-18-ci-linux-reproducibility.md`
- `docs/implementation/maple-room-r1a-19-performance-soak.md`
- `docs/implementation/maple-room-r1a-checklist.md`
- `docs/implementation/maple-room-r1a-plan.md`
- `docs/implementation/maple-room-r1a-worklog.md`
- `frontend/package.json`
- `frontend/tools/performance/browser.mjs`
- `frontend/tools/performance/evidence.test.mjs`
- `frontend/tools/performance/isolation.mjs`
- `frontend/tools/performance/probe.mjs`
- `frontend/tools/performance/runtime.mjs`
- `frontend/tools/performance/statistics.mjs`
- `frontend/tools/performance/statistics.test.mjs`
