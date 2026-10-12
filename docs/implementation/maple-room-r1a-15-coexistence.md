# R1A-15 — Feature flag and Legacy/new Room coexistence

**Current integration reconciliation — STEP 155, 2026-10-12: DONE / OWNER ACCEPTED / MERGED.** PR #16 merge `78953ce60d929a4e0a595b8c957ad5dd6b9fa49e` independently verified in the acceptance baseline ancestry. Earlier dated implementation/review/publication statements below are historical. Accepted decisions and measurement provenance remain unchanged. [Current R1A-20 audit](maple-room-r1a-20-acceptance-gate.md).

Status: REVIEW / OWNER ACCEPTED / MERGE PENDING — STEP141,2026-10-12. Owner accepts implementation and STEP140B browser results;authorizes reviewed commit,normal push,PR and CI inspection only. Baseline `a85f226fb664056482baf8f27389870fce14fd45`;branch `codex/r1a-15-room-coexistence`;existing Windows worktree retained.

## Owner clarification and binding boundary

Owner explicitly approved: “No NEW-WORLD Pixi renderer is initialized when the flag is OFF. The Legacy Room's existing Pixi renderer remains unchanged.” Preserve Legacy Pixi initialization, rendering, lifecycle, data flow and behavior. No production default change, schema-v11 activation, B14 approval, production access, merge or deployment. STEP141 now authorizes reviewed commit,normal push,PR and CI inspection.

R1A-10 through R1A-14 are merged in the verified baseline (PR #15 includes R1A-13); older STEP138 status lines are historical. Current integrated progress is 14/20 DONE = 70%. R1A-15 cannot become DONE until owner acceptance and merge; eventual progress would be 15/20 = 75%.

## Selected design (before implementation)

Legacy currently enters through `src/main.tsx`, constructs Store/read API/LiveConnection and mounts unchanged `ui/App.tsx`; its scene is `room/scene/RoomScene.ts`. Existing explicit development `?room=fixture` lazy-loads `world-room/Preview.tsx`, with canonical checked-in R1A-10 fixtures, scene/camera/lighting/atlas modules and no live connection.

Keep the smallest flag: a single exact `room=fixture` query parameter, accepted only by Vite's compile-time DEV branch. Missing, off, unknown, ambiguous duplicate or malformed values fall back to Legacy. A development-only DOM selector changes view without a page reload. The selector persists while the selected view unmounts, preserving focus. The existing fixture URL remains supported. No storage, new dependencies or production configuration.

Extract existing Legacy bootstrap into an owned mount function with idempotent teardown of its live connection, bootstrap subscription and pagehide listener. Its App, RoomView, overlay, panels and scene remain untouched. Development switching invokes that teardown and unmounts before loading the other view. Async preview imports must check cancellation, so an old import cannot mount after a rollback. The new scene retains existing AbortSignal cleanup, ticker, observer, camera and shared atlas lease ownership.

## Shared DOM and accessible summary

Reuse existing DOM controls and fixture description from WorldPreview; reuse Legacy App and all its DOM panels intact. The two typed sources cannot truthfully share StatusPanel/InteractionBar/JournalPanel: WorldOut has no legacy needs, journal or interaction availability. No synthetic SnapshotOut adapter or duplicated business rules will be introduced. Sharing the outer development selector and existing component implementations is the smallest safe integration; fixture controls remain visibly distinct from live controls. Any future shared business panels require explicit canonical data contracts in R1b.

Add a keyboard-focusable current-room summary, with canonical human-readable name and open/closed status from the actor's world region (existing currentRegion), never the focused camera region. A separate polite announcement changes only with region/status, not playback frames. Preserve canvas-independent details and error fallback. Names are display labels only, not geometry authority.

## Production/security/bundle boundaries

Compile-time `import.meta.env.DEV` must remove the switcher, Preview, fixtures and new scene from production JavaScript and source maps. No direct path/query may turn DEV on in a production build. Preserve existing source/import guards and ten backend import contracts, CSP/Origin, generated DTOs, API/SSE and Director. Inspect the actual built payload; only pre-existing hashed processed atlas pages may ship. No raw art, palette or fixture JSON. No renderer mutation calls.

## Validation matrix and handoff

Automated: strict gate matrix including duplicate/query bypass attempts; default Legacy rendering/factory calls and DOM equivalence; lazy loading and canceled imports; both switching round trips and repeated toggles; AbortSignal/destroy exactly once, late scene completion, fixture playback cleanup; source truthfulness and room summary independent of camera; existing scene/camera/lighting/atlas regressions. Run frontend typecheck/lint/test/build, asset/bundle/reproduction tests, backend pytest/import/type/security checks, regeneration comparisons, documentation links/counters and diff check.

Browser: record browser version, actual DPR and WebGL renderer; default Legacy; explicit fixture and source label; keyboard focus and repeated transitions; canonical summary; Overview/Follow/Focus and L1–L4; four day phases; DPR 1/1.25/1.5/2/3 when supported; 1440/820/390 emulation, overflow, canvas fallback, errors/network/cleanup. Report incomplete checks explicitly; emulation does not prove physical devices.

Rollback: select Legacy (flag off), or remove `room=fixture` and reload. Production requires no configuration change. R1A-19 owns full L21 performance/soak; R1A-20 owns acceptance consolidation. Final art/face size, device default zoom, physical mobile QA, production world integration and B14 gate remain deferred. Do not begin these workstreams here.

## Changed-file manifest and fresh evidence

The preceding design was recorded before implementation. Fresh results below supersede its planning-only evidence state.

## STEP 140 Windows validation and owner acceptance report (historical)

STEP140B below supersedes the non-1 browser DPR limitation and CONCERN result in this dated report.

1. **Result: CONCERN / ready for owner review.** Supported local gates PASS. Fresh browser DPR 1.25/1.5/2/3 are incomplete because available browser controls expose viewport dimensions only. No functional, truthfulness, security or cleanup blocker found. R1A-15 stays REVIEW pending acceptance and merge.
2. **Worktree/branch:** existing `C:\GitHub\Maplegotchi-worktrees\r1a-15-room-coexistence`, `codex/r1a-15-room-coexistence`, reused without discarding progress. Main checkout and pre-existing branches untouched.
3. **Baseline:** `a85f226fb664056482baf8f27389870fce14fd45`; clean main HEAD, integration branch and local remote-tracking ref matched before worktree creation. Includes merged R1A-10–14, including lighting PR #15 and camera PR #14. No remote fetch or production connection needed.
4. **Manifest:** exact 20-file list below. No backend, lockfile, generated DTO, canonical fixture, atlas/art input, policy or deployment-script changes.
5. **Flag:** single exact `room=fixture`, accepted only inside compile-time DEV. Persistent development DOM selector sets/removes it with replaceState. Default, off, unknown, malformed, case mismatch and duplicate values fall back to Legacy. No environment variable or persistent storage.
6. **Legacy evidence:** App/RoomView/RoomOverlay/panels/scene unchanged. Regression compares full default Legacy DOM with direct rendering and verifies Legacy scene factory/update/disposal and zero new-world loader/factory calls. Actual bootstrap tests prove original snapshot/room/life-event reads, Pixi loading, SSE close, pagehide removal, idempotent disposal and removal of the pending-snapshot bootstrap subscription. Browser artwork/panels/keyboard remain functional.
7. **Production isolation:** actual build audit PASS: two matching hashed processed pages, zero raw sources, no fixture preview. Adversarial bundle tests reject development controls and development/fixture source-map modules. Actual production browser `/?room=fixture&dev=true` and `/world-room/Preview?room=fixture` both render Legacy, with zero development controls/disclosure. No schema-v11/API/SSE/Director/CSP/Origin activation or modification.
8. **Integrated candidate:** reuses R1A-10 fixtures/DTOs, R1A-11 renderer/depth, R1A-12 camera/DPR/reduced motion, R1A-13 partition/emitters and R1A-14 atlases. Canonical 44×26, eight regions, seven doors, 28 objects, 17 points, 12 slots and 431 walkable cells. Visible FIXTURE / DEMO disclosure. No mutation client or backend-rule additions.
9. **DOM/accessibility:** existing Legacy panels and fixture controls reused intact. WorldOut lacks live needs/journal/interactions, so no fabricated SnapshotOut panel adapter. Persistent selector is shared DOM. Keyboard-focusable summary names the actor's canonical region and supplied status independently of camera focus. Polite atomic text excludes per-frame coordinates/time. Eight canonical names and unavailable-region fallback tested. Renderer status has a distinct accessible name. Spoken screen-reader output not tested.
10. **Toggle/cleanup:** both initial states and four automated round trips per state PASS; actual browser keyboard cycles and Enter return-button rollback PASS. Unresolved module imports cannot mount after rollback; late scenes dispose; scene signals abort; owned scenes destroy once; fixture playback RAF cancels. Legacy SSE/bootstrap/pagehide, switcher history and reduced-motion listeners clean up. Settled fixture resources remain one canvas, two pending RAF callbacks and two ResizeObservers including Pixi internals across four final keyboard cycles. Transition gap observed at zero; forced canvas failure also leaves zero. No heap/long-soak acceptance claimed.
11. **Browser:** Chrome/155.0.0.0, Windows NT10.0 Win64, Codex in-app browser. Hardware ANGLE NVIDIA GeForce RTX3060 (0x00002504), Direct3D11 vs_5_0 ps_5_0/D3D11. Actual DPR1. Legacy QA uses accepted `maplegotchi run --senses fake` and isolated ignored `var/r1a15-browser-data`. Ignored local HTML instrumentation reports resources/errors/fetches and simulates canvas failure; it is outside the build/manifest. Matrix below.
12. **Camera/lighting/atlas regressions:** existing suites preserved/PASS. Settled browser Follow L1–L4 reports zoom1/2/3/4 at DPR1; Overview fits desktop/tablet and uses DOM room-list fallback on phone; Focus works with Enter and leaves the current-room summary truthful. Four phases explicitly observed; eight supplied zones cover1144 cells with seven window/lamp/emissive hooks. Existing automated five-DPR coverage/night-contrast/depth/camera tests PASS. Final art/default zoom/lighting acceptance remains separate.
13. **Frontend:** 586 Vitest tests/25 files PASS, zero failures/skips; 37 added over549. Asset/bundle suite69 PASS, zero failures/skips; three added over66. Separate counts, no double counting. Logs in ignored `var/`.
14. **Backend:** fresh `uv run pytest -q`:3674 PASS,21 SKIPPED,131.08s.18 Bash-unavailable deployment cases, one POSIX/non-root permissions case and two Windows file-symlink privilege cases. These skips are not Linux passes. Tests unchanged; suite includes security/Oracle/projection/pinned simulation regression.
15. **Static/build:** frontend typecheck/lint/build PASS. Locked Node24.20.0,pnpm12.3.4,Vite8.3.1 retained; uv0.13.0 and CPython3.12.10 locked sync. Strict Windows/Linux-target mypy228 files, Ruff check/format230 files,10 import contracts PASS. World OpenAPI/TypeScript/five-fixture exact regeneration comparison PASS. No Linux execution, remote CI or Full Release Gate claim.
16. **Atlas:** native Windows reproducibility/golden tests PASS;193 frames,two pages,1.5MiB static RGBA8,5.5MiB resident upper bound within32MiB. Index SHA256 `5ee8f05364b6a9f42c1a75d4ee2b2b219dbc5648d636413241115491a060e833`. Character PNG `630070036d3fdc838d782d6f7be8ced0f309ce864b6705110fc5cbba5154e669`, metadata `8776fdc50db20fd91246c05cef63c306c32af1a75129b44d0d043860e66ee6ee`. Shared PNG `ec634d545d1af7dc4a1c53fe6c92462f4da820b0ff4cefc5b2c30077c36f77a3`, metadata `1b50a5a357501708bf5fc90cec4da8c994ae47aaa24d61c1ce2ca9bb4c708192`. No atlas/art changes; independent Linux reproduction remains R1A-18.
17. **Git/security:** local unstaged changes only; HEAD unchanged, main clean, pre-existing baseline branch untouched. No commit/push/PR/merge/deployment/production access. Existing source/import guards pass. Instrumentation: zero mutation fetches, zero API requests on direct fixture entry;16 normal Legacy GETs across four final fresh Legacy mounts, API count stayed16 while fixture remained active. Atlas image loads expected. No new-world live client/storage/raw HTML sinks.
18. **Documentation:** evidence, Master Plan, checklist, append-only worklog, frontend and CLAUDE current status updated.14 DONE/1 REVIEW/5 TODO=20,70% integrated;75% only after acceptance+merge. Earlier dated blocks historical. Final audit checks local links, worklog prefix, unchanged Legacy source, counters and diff whitespace.
19. **Deferred:** fresh non-1 browser DPR matrix with capable controls; physical tablet/phone and spoken screen-reader QA; final art/face size/product default zoom/final lighting; full L21 performance/soak (R1A-19), acceptance consolidation (R1A-20), R1b production integration/soak and B14 switch. R1A-16–20 implementation not started.
20. **Readiness:** ready for local owner review with stated browser limitations. No owner acceptance/publication authorization implied. Rollback selects Legacy/removes query; production requires no configuration change.

### Browser matrix — fresh local Windows checks

| Check | Actual context | Result |
|---|---|---|
| Default Legacy/Pixi/panels | Development root, isolated fake-sensor backend | PASS |
| New fixture and source disclosure | Selector/direct fixture URL | PASS |
| Round trips, repeated toggles and focus | Native ArrowUp/ArrowDown, Enter return button | PASS; focus SELECT, one canvas after mount |
| Current room independent of camera | Focus closed Creation Room, actor remains Central Hall/open | PASS |
| Overview/Follow/Focus and L1–L4 | Actual DPR1, hardware WebGL | PASS |
| Four day phases/eight zones | Settled scene DOM diagnostics | PASS;1144 cells,seven hooks |
| Desktop1440×1000 | DPR1,806×484 device canvas | PASS; no horizontal overflow |
| Tablet820×1180 | Emulation,DPR1,773×464 device canvas | PASS; no horizontal overflow |
| Phone390×844 | Emulation,DPR1,343×206 device canvas | PASS; Overview DOM fallback,Follow/Focus |
| Canvas-independent fallback | Test-only forced HTML/offscreen canvas failure | PASS; summary retained,resources0,uncaught errors0 |
| Production query/direct-route bypass | Actual build,loopback4173 | PASS; Legacy,development controls0,console warnings/errors0 |
| Errors/mutations/cleanup | Instrumented fixture and final four keyboard cycles | PASS; errors0,mutation fetches0,stable resources |
| Browser DPR1 | Actual native ratio | PASS |
| Browser DPR1.25/1.5/2/3 | Browser capability has no DPR override | INCOMPLETE; automated five-DPR suite PASS |
| Physical devices/spoken screen reader | Not available in local browser | NOT CLAIMED |

Screenshots inspected in browser tool: Legacy artwork, desktop/tablet fixture and phone layout. No physical-device claim. Disposable ignored browser instrumentation does not alter production code or policy. Viewport overrides reset after QA.

### Exact changed-file manifest

```text
CLAUDE.md
docs/frontend.md
docs/implementation/maple-room-r1a-15-coexistence.md
docs/implementation/maple-room-r1a-checklist.md
docs/implementation/maple-room-r1a-plan.md
docs/implementation/maple-room-r1a-worklog.md
frontend/src/dev/RoomSwitcher.test.tsx
frontend/src/dev/RoomSwitcher.tsx
frontend/src/dev/coexistence.css
frontend/src/main.tsx
frontend/src/ui/legacy.test.tsx
frontend/src/ui/legacy.tsx
frontend/src/world-room/Preview.test.tsx
frontend/src/world-room/Preview.tsx
frontend/src/world-room/RoomSummary.test.tsx
frontend/src/world-room/RoomSummary.tsx
frontend/src/world-room/gate.ts
frontend/src/world-room/guards.test.ts
frontend/tools/art/bundle.mjs
frontend/tools/art/bundle.test.mjs
```

### Final local audit

87 local documentation link targets PASS; append-only worklog historical prefix exactly preserved; checklist14 DONE/1 REVIEW/5 TODO PASS; changed Legacy components,backend/art/deploy/API/state/renderer/camera/lighting/atlas and lockfiles comparison confirms unchanged sources. Production CSS contains no development selector styles. `git diff --check` PASS, staged diff empty, feature HEAD and pre-existing baseline branch remain `a85f226fb664056482baf8f27389870fce14fd45`, main checkout clean on `v0.2-development`. Exact manifest20 files (12 modified,8 new). Final full frontend gate586+69 tests/typecheck/lint PASS; actual build/audit PASS. QA browser closed and the three verified loopback-only QA service processes stopped. Ignored local logs/data/harness retained for review. No publication or production action.


## STEP 140B — fractional DPR browser closure (2026-10-12)

**Result: PASS / ready for owner acceptance.** This fresh closure supersedes the STEP 140 browser-capability concern and non-1 DPR deferral above. R1A-15 remains REVIEW / PENDING OWNER ACCEPTANCE; no acceptance, merge or production activation is implied. Existing branch and baseline are unchanged. No application, test, dependency, backend, API/SSE or security-boundary changes were necessary in this batch; only evidence/status documentation changed.

### Runtime and method

Bundled Playwright **1.62.1**, installed Google Chrome **154.0.8037.98**, Windows headless browser. Explicit newContext deviceScaleFactor **1, 1.25, 1.5, 2, 3**; every page reported the exact requested window.devicePixelRatio. Desktop 1440×1000; tablet 820×1180 and phone 390×844 use Chromium mobile/touch emulation. These differ from the prior viewport-only emulation, including scrollbar layout. Actual context inspection for Legacy and New reports **WebGL2 / ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 (0x00002504) Direct3D11 vs_5_0 ps_5_0, D3D11)**, vendor Google Inc. (NVIDIA), throughout. WebGL probes are also recorded; no assumption of hardware rendering was used. Cached Chromium1223 failed launch with Windows spawn UNKNOWN; the installed Chrome fallback succeeded. No installation or package/lockfile changes.

Local-only Vite5173, synthetic backend8470 using retained ignored var/r1a15-browser-data, and audited production preview4173. Disposable Playwright instrumentation wraps RAF, ResizeObserver, canvas contexts and fetch-based SSE before app entry; it observes aborts and actual WebGL context information. Initial harness attempts were corrected for fetch-based SSE, full accessible labels and the allowed pure gate helper; they do not represent product defects. Final complete report and supplemental direct-entry run both PASS. Scripts/logs/screenshots stay ignored under var/ and are excluded from production.

### DPR × Room-switching matrix

Each PASS covers default Legacy → keyboard New → Return Legacy → keyboard New, direct development fixture entry, visible fixture disclosure, Overview/Follow/Focus, all four logical zoom levels and phases, backing dimensions, cleanup, retained selector focus, assets, console and overflow.

| Actual DPR | Desktop | Tablet | Phone | Follow L1/L2/L3/L4 device zoom | Initial New backing: desktop / tablet / phone |
|---|---|---|---|---|---|
| 1 | PASS | PASS | PASS | 1/2/3/4 | 806×484 / 788×473 / 358×215 |
| 1.25 | PASS | PASS | PASS | 1/2/4/5 | 1008×605 / 985×591 / 448×269 |
| 1.5 | PASS | PASS | PASS | 1/3/4/6 | 1209×726 / 1182×710 / 537×322 |
| 2 | PASS | PASS | PASS | 2/4/6/8 | 1612×968 / 1576×946 / 716×430 |
| 3 | PASS | PASS | PASS | 3/6/9/12 | 2418×1452 / 2364×1420 / 1074×645 |

Backing follows measured CSS size × actual DPR, rounded to device pixels (validated within the accepted one-pixel ResizeObserver box tolerance); actual canvas width/height equals camera diagnostic width/height at every L1–L4. Integer zoom follows the locked floor(L×DPR+0.25) rule, capped at12. Legacy retains its existing **1000×600 logical renderer size with backing 1000×min(DPR,2) by 600×min(DPR,2)** at all five DPRs and all three form factors, including return mounts; Legacy renderer sources remain unchanged.

### Functional, cleanup and visual evidence

- **OFF:** Legacy canvas, live DOM panels and normal synthetic-backend connection render; zero new-world scene/Preview/atlas module loads before activation. The pure gate helper is permitted and initializes no renderer. Owner clarification remains binding: no NEW-WORLD Pixi when OFF; Legacy Pixi stays functional.
- **ON:** authorized development query and selector mount exactly one new-world canvas. Source disclosure stays visible. Supplemental15 direct fixture entries make **zero /api/ endpoint requests**, including SSE. No fixture-to-live adapter or mutation fetches.
- **Camera:** Overview and Focus compute fitting locked levels; phone Overview uses the existing truthful DOM room-list fallback when the house cannot fit. Follow L1–L4 and canonical-room Focus work across the entire matrix; camera focus leaves the actor summary Central Hall/open. This batch does not change device defaults.
- **Lighting/atlas:** morning/afternoon/evening/night each settle with8 zones,1144 cells and7 hooks. Both packed character/shared PNGs load successfully in every context.60 phase screenshots have distinct phase hashes within each context.15 full-page Overview screenshots capture source labels, controls, room list and responsive fallback. Representative full layouts and phase/atlas images were visually inspected across all five DPRs, including fractional and phone/tablet contexts; placeholder art and lighting presets remain provisional.
- **Switching/focus:**15 complete Legacy → New → Legacy → New cycles PASS. ArrowDown/Enter selects New; Return button restores focus to the persistent selector; keyboard remount retains focus. Old New canvas is detached. Legacy has one canvas and one active fetch-based SSE; New has one canvas and zero active SSE. Both settled views have2 pending RAF callbacks and2 ResizeObservers including Pixi internals; return/remount matches initial resource counts, with no accumulation. Fresh regression suites additionally verify AbortSignal, late completion, canceled imports, exact scene destruction and atlas lease ownership. These observations are finite lifecycle evidence, not a heap/soak proof.
- **Console/network/layout:** zero console errors, page exceptions, console warnings, HTTP4xx/5xx or unexpected failed requests across15 contexts. Intentional aborted SSE on rollback/navigation is excluded from broken-resource counts. Zero mutation fetches and zero unexpected horizontal overflow in Legacy/New. Mobile emulation uses the desktop Chrome engine with touch/mobile flags; it does not prove Safari or physical devices.

### Fresh production isolation

Fresh pnpm build and built-payload audit PASS: hashedPages2, rawSourceFiles0, productionPreview false; development/fixture/new-scene modules are absent from production JavaScript/source-map runtime. Existing hashed processed atlas PNGs remain shipped by the accepted build policy; raw art and fixture JSON do not. On the actual local production build, /?room=fixture&dev=true, /world-room/Preview?room=fixture and /?room=fixture&room=fixture all render Legacy with zero development selector/fixture UI and zero console errors. Queries and direct navigation cannot activate New. Backend/API/SSE/security source boundaries remain unchanged, and no production endpoint was accessed.

### Fresh automated results and provenance

STEP140B freshly ran pnpm test: **586 frontend tests /25 files PASS;69 asset/bundle tests PASS**, zero failures/skips; pnpm lint, pnpm typecheck and pnpm build PASS. The asset suite includes deterministic atlas/golden and production-leak regressions. Browser matrix15/15, supplemental direct-entry15/15 and production routes3/3 PASS. Previous STEP140 backend3674 PASS/21 Windows skips, Ruff/mypy/import-contract/export comparisons are retained historical evidence and **were not rerun in STEP140B**; no backend changes justify repeating them. Full release/Linux/remote CI is not claimed.

Raw ignored evidence: var/r1a15-dpr/report.json, var/r1a15-dpr/supplement.json, var/r1a15-dpr/*.png (75 screenshots), var/r1a15-dpr.cjs, var/r1a15-dpr-supplement.cjs and var/r1a15-step140b-tests.log. Browser contexts closed after each case. No corrective production code changes or new dependencies. Documentation updates only in this batch; original20-file implementation manifest remains intact.

**Remaining limits:** physical mobile/tablet, other browser engines, software-renderer coverage, spoken screen-reader output, final art/lighting/device defaults and long performance/heap/soak acceptance remain separate. The fractional-DPR evidence gap is closed. Ready for owner acceptance review; R1A-16 or later work was not started. No commit, push, PR, merge, deployment, paolo-core modification or production access.

STEP140B final local audit:78 current-document local links PASS;exact pre-STEP140B worklog prefix preserved;20 checklist rows14DONE/1REVIEW/5TODO PASS;git diff --check PASS. Baseline HEAD/branch unchanged,staged diff empty,main clean. Legacy renderer/UI,backend/API/state and lockfile comparisons unchanged. Original20-file manifest retained. All QA browser contexts closed and loopback5173/4173/8470 listeners verified stopped. No publication action.


## STEP141 — owner acceptance and GitHub integration preparation (2026-10-12)

Owner accepts the implementation and STEP140B browser QA. **REVIEW / OWNER ACCEPTED / MERGE PENDING**,not DONE. Verified expected worktree/branch/HEAD and origin https://github.com/payola469/Maplegotchi.git. Remote v0.2-development remains a85f226fb664056482baf8f27389870fce14fd45;no feature remote ref existed before publication. Derived manifest20 files directly from Git (12 modified,8 new);each path reviewed. No raw art,fixtures,generated output,QA screenshots/logs,secrets,packages/lockfiles,backend/security/production config or deployment-script changes. Existing full manifest above remains exact.

Final source/TSX/security review PASS:development-only exact fixture gate with duplicate/invalid fallback;Legacy scene/panels/backend flow preserved;lazy loading/cancelled imports and idempotent disposal;actor-based room summary and stable polite text;accessible persistent selector and rollback;safe typed-source panel-reuse boundary retained. Pure gate import never initializes New Pixi. Existing architecture/CSP/Origin/import guards preserved and strengthened for actual production JS/source maps. No binding conflict found;dated pre-authorization text is historical and current owner authorization governs this batch.

Fresh frozen pnpm install and locked/offline uv sync PASS. Fresh586 Vitest/25 files and69 asset/bundle tests PASS,zero failures/skips;includes feature-gate,Legacy-equivalence,lifecycle,camera/lighting/atlas regressions. ESLint,TypeScript,production build and bundle audit PASS:2 hashed processed atlas pages,0 raw sources,productionPreview false. Native Windows complete-output reproducibility and reference PNG/metadata/generated-index comparisons PASS;193 frames,unchanged accepted hashes. Ruff check/format230 files,strict Windows and Linux-target mypy228 files each,10 kept import contracts and exact OpenAPI/TypeScript/five-fixture comparisons PASS. Full Windows backend result recorded below after completion.

Accepted STEP140B browser evidence is reused,**not rerun here**:Playwright1.62.1/Chrome154.0.8037.98,actual DPR1/1.25/1.5/2/3 × desktop/tablet/phone15/15,15 switching cycles,hardware WebGL2 ANGLE NVIDIA RTX3060 D3D11,camera/backing/four phases/atlas/focus/cleanup/console/assets/layout PASS;3 actual production query/direct-route bypass attempts stay Legacy. Fresh actual production bundle inspection corroborates compile-time isolation;no policy relaxation. Physical devices,other engines/software-renderer coverage,spoken screen reader,final art/defaults and fullL21/heap/soak remain deferred. No B14,live world/schema-v11 activation,merge,deployment,production access or later-workstream work. Current14DONE/1REVIEW/5TODO=70%;15/20=75% only after confirmed merge. Commit,PR and actual per-job CI facts are reported after execution,not predeclared here.


Fresh STEP141 full Windows backend: **3674 PASS,21 SKIPPED in142.37s**;18 Bash-unavailable deployment cases,1 POSIX/non-root permissions case,2 file-symlink privilege cases. No failures;no Linux execution or full release-gate claim. Includes API/security,Oracle/Harness,projection and pinned simulation regressions. Logs remain ignored under var/r1a15-step141-frontend.log and var/r1a15-step141-backend.log.


Final precommit audit: **20 reviewed paths**,93 local-document links PASS;exact pre-STEP141 worklog byte prefix and original baseline history preserved;14DONE/1REVIEW/5TODO counters PASS;source/secret/temp/generated-file review PASS;git diff --check PASS. Main checkout clean at baseline,staging empty before explicit staging,unrelated branches/worktrees unchanged. No critical gate failure. Commit and normal push authorized;PR/CI pending execution.
