# R1A-13 — Lighting zones and emitter hooks

**Current integration reconciliation — STEP 155, 2026-10-12: DONE / OWNER ACCEPTED / MERGED.** PR #15 merge `a85f226fb664056482baf8f27389870fce14fd45` independently verified in the acceptance baseline ancestry. Earlier dated implementation/review/publication statements below are historical. Accepted decisions and measurement provenance remain unchanged. [Current R1A-20 audit](maple-room-r1a-20-acceptance-gate.md).

Status: REVIEW / OWNER ACCEPTED / MERGE PENDING — STEP138 (2026-10-12). Owner accepts local implementation,QA and temporary placeholder colors;authorizes reviewed commit,normal push,PR and CI inspection. Integration baseline `48897c8e6b81a674441f089336930ba20ae53913`,branch `codex/r1a-13-lighting-zones`. No merge,deployment or new workstream authorization. Earlier STEP137 records below retain their original context.

## Binding inputs and checkpoints

Locked ADR-0041 L16 and L11–L19 → accepted ADR-0035–0040 → Final Spec §P/O → proposed Art Production Contract. Existing R1A-10 DTO supplies `lighting_zones[{region_id,bounds}]` and `snapshot.day_phase` (`night`, `morning`, `afternoon`, `evening`). Existing atlas has window/lamp `light` and Computer Desk `emissive` parts. No new backend field or second geometry map needed. Original conversation not accessed or claimed.

1. Pure presentation module: stable DTO zone order, partition sanity checks against supplied grid, typed replaceable provisional four-phase presets, source-referenced hook discovery from catalog art/objects. Checkpoint: partition/phase/negative/determinism tests. Sanity checks do not replace backend layout acceptance.
2. Existing scene layers: neutral geometry/Maple/depth first; eight multiply rectangles; additive atlas parts; Computer Desk emissive last. Use manifest partPosition/anchors; preserve canonical object anchor and camera transform. Phase updates reuse resources, disposal follows existing ownership. No shadows or weather. Original STEP137 excluded art regeneration;STEP137 CONTINUE narrowly authorizes placeholder correction and deterministic atlas regeneration. Checkpoint: layer/order/source/phase/lifecycle tests and atlas regressions.
3. Fixture-only DOM phase selector with explicitly synthetic derived snapshots; injectable typed preset configuration. No live day simulation. Camera unchanged; all parts share viewport transform. Checkpoint: full frontend/assets/API/security/import/export gates and production build exclusion.
4. Actual software-WebGL preview: phases, boundary walking, camera/DPR/reduced motion, exact emissive pixels, rendered night contrast and draw-call/timing samples. Contrast uses sRGB relative luminance `(lighter+.05)/(darker+.05)` from framebuffer captures, body/face dark/light representative pixels and local background; report limits. L21 full performance acceptance is not claimed without its required soak/device measurements.

## Acceptance and handoff

Eight supplied zones cover1144 cells exactly once, zero gaps/overlaps/double multiply; floor/wall/shared-band ownership comes from DTO. Four north-window hooks, two lamp hooks, one Computer Desk emissive, no placeholder natural daylight. Provisional day-phase colors/strengths remain adjustable; Hall/closed rooms use artificial zone presets without access changes. Night contrast≥1.5; STEP137 CONTINUE permits only necessary original-placeholder palette corrections; no anchor/spec/Oracle change. R1A-15 must later supply authoritative day phase/layout/configuration and safe source/lifecycle integration; this work only draws fixture facts. Defaults/final colors/strengths, real devices and full L21 acceptance remain deferred.

## Evidence — STEP137 initial blocked record (historical)

**BLOCKED at night-contrast acceptance; implementation stopped under STEP137 §§11/18.** Partial work remains uncommitted. Do not mark REVIEW or begin R1A-15.

Implemented `lighting.ts`: supplied-zone partition sanity, deterministic sorting, four typed injectable provisional phase presets and seven source-linked hooks. Existing scene multiplies eight disjoint rectangles, then renders six additive atlas parts and one normal-blend Computer Desk emissive part. Manifest light-centre/partPosition anchors preserve base positions. Fixture-only phase selector derives explicitly synthetic snapshots, leaving canonical fixtures unchanged. Missing-catalog error contract preserved after a regression caught changed wording. No accepted tests weakened.

### Contrast blocker and smallest decision

Method: software-WebGL Chrome154.0.8037.98/Playwright1.62.1,806×484 backing,DPR1,Overview L1. Capture Maple at supplied Hall centre (21,15), then move only the synthetic actor to another Hall location and capture the unchanged background at the same image pixels. sRGB relative luminance ratio `(lighter+.05)/(darker+.05)`. Night Hall artificial tint `0xe4e0ee`, lamp alpha.3,daylight0. Atlas colors are unchanged.

| Down-facing sample | Rendered RGB | Background RGB | Contrast | ≥1.5 |
| --- | --- | --- | --- | --- |
| Hair | 65,54,52 | 165,154,135 | 4.20194 | PASS |
| Skin | 210,172,145 | 165,154,135 | 1.32729 | FAIL |
| Shirt | 102,130,121 | 124,99,85 | 1.33427 | FAIL |
| Pants | 65,54,52 | 124,99,85 | 2.09373 | PASS |

The skin and shirt failures recur in measured left/up views (right's skin sample is occluded by hair). These are sampled rendered regions, not certification of all face pixels/animation frames. The under-shirt background is existing placeholder furniture, not floor; this is disclosed rather than excluded to improve the metric. Source skin RGB235,196,155 was verified from the idle source PNG. For the skin/floor pair235,196,155 versus185,175,145, exhaustive enumeration of all16777216 shared RGB multiply tints with8-bit rounded channels gives maximum1.481446 at254,2,0. This model rules out a shared preset-only fix for that sample under the chosen per-pixel criterion; it is not an exhaustive GPU blend-precision proof or a claim that art-direction changes are forbidden.

**Owner decision needed:** clarify whether ≥1.5 is a per-sampled-pixel requirement (including skin and background furniture) or the spike's silhouette/body-versus-floor metric, with an explicit reproducible sampling rule. If the per-pixel minimum is required, authorize a narrow provisional art/palette contrast adjustment or another specifically approved treatment while preserving L16 and all anchors/geometry. Final colors remain UNDECIDED. No art edits, outline, actor lighting exemption or threshold relaxation was invented. ADR-0040 §3, ADR-0041 L16, spike §5.5/M12 and STEP137 §11 require contrast but do not define a complete pixel/background sampling protocol; spike reports hair/shirt rather than skin/furniture cases. No locked rule was amended.

### Completed checks and limits

- Full frontend: **545 Vitest/22 files PASS,0 failures (34 new cases)**; **65 Node asset/bundle cases PASS**. Existing camera,144 depth-ring,walking,atlas,architecture/fixture/legacy tests pass. New34 comprise28 pure lighting,5 scene composition/phase and1 DOM phase test. These structural tests do not supersede the failed rendered contrast gate.
- **237 backend/API/security/Oracle/Harness tests PASS**,10 import contracts kept/0 broken; exact OpenAPI/TypeScript/five fixture exports match. Production backend, schema, Oracle/Harness and simulation pin unchanged; no full simulation/Full Release Gate.
- ESLint,TypeScript and production build PASS before the final error-message-only correction; full frontend tests reran after that correction. Bundle:2 hashed atlas pages,0 raw sources,productionPreview false. No Python source changed; Ruff/mypy not newly applicable.193 frames,two pages,original atlas hashes retained.
- Browser matrix: all4 phases at actualDPR1/1.25/1.5/2/3; eight zones/seven hooks,night daylight0,screen alpha1,integer camera L1–L4. Focus and fixed walking times inspected; reduced-motion contexts used. Zero captured application errors. No claim of completed frame-by-frame zone-boundary walking, all-DPR seam inspection or physical-device acceptance.
- Recording tests establish L16 neutral→multiply→additive→emissive order,8 rectangles/1144 cells,6 additive+1 emissive sources and unchanged resource ownership. Actual framebuffer screen-color equality is **NOT VERIFIED**: an initial QA sample hit base desk pixels, so those raw values are not an emissive failure/pass claim. Further emissive/face/animation acceptance measurement deferred when contrast stop condition triggered.
- Software-WebGL diagnostic: baseline lighting layers hidden1 draw call versus enabled4 (contribution+3);91/90 frames over1.5seconds each,CPU submit p95≈0.1ms both. Instrumentation/software GPU context is not a hardware performance benchmark; no L21 acceptance/4×phone/60second/10minute soak claim.

Evidence outside Git: [browser and pixel records](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a13-browser.json), [tint enumeration](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a13-contrast-bound.json), [measured night scene](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a13-measured-night.png). Raw records include incomplete/nonasserted measurements; interpretations above are authoritative. Temporary browser contexts closed and preview stopped. Selected evidence retained, transient screenshots held in memory only.

R1A-13 is **not ready for owner acceptance or R1A-15 handoff**. Handoff interfaces exist but acceptance is blocked. Preserve current partial code for review/resumption. No commit,push,PR,merge,deploy,Production access,schema-v11 activation or unrelated-worktree edit.


## STEP137 initial partial manifest and integrity checks (historical)

- `CLAUDE.md`
- `docs/architecture.md`
- `docs/frontend.md`
- `docs/implementation/maple-room-r1a-12-camera-zoom-dpr.md`
- `docs/implementation/maple-room-r1a-13-lighting-zones.md`
- `docs/implementation/maple-room-r1a-checklist.md`
- `docs/implementation/maple-room-r1a-plan.md`
- `docs/implementation/maple-room-r1a-worklog.md`
- `frontend/src/world-room/Preview.test.tsx`
- `frontend/src/world-room/Preview.tsx`
- `frontend/src/world-room/lighting.test.ts`
- `frontend/src/world-room/lighting.ts`
- `frontend/src/world-room/scene.test.ts`
- `frontend/src/world-room/scene.ts`

14 scoped files; `git diff --check` PASS,86 relative links resolve,append-only worklog prefix preserved. Checklist13 DONE/1 BLOCKED/6 TODO,zero REVIEW. Original13 worktrees and separate R1A-12 HEAD/clean status unchanged; local-only40f0eb7 preserved. New worktree HEAD remains the merge baseline,index empty. Local preview port5179 has no listener.


## STEP137 CONTINUE — owner decision and local closure (2026-10-12)

**Local verdict: PASS / READY FOR OWNER ACCEPTANCE.** R1A-13 remains REVIEW, not DONE. The owner authorizes necessary original-placeholder color/pixel corrections, preserving≥1.5,master palette,validation,geometry and L16. No production-art approval or GitHub Integration is implied. The historical measurements and stop above remain preserved in their original context.

### Exact provisional-art correction

Existing ten-color `art/palette/maple-master.hex` is byte-unchanged. All112 body frames across12 pose sheets receive only these substitutions:

| Region | Original palette index / RGB | Replacement index / RGB | Changed pixels |
| --- | --- | --- | --- |
| Skin | 4 / `#ebc49b` | 1 / `#8b715b` | 16,128 |
| Shirt | 3 / `#729482` | 0 / `#493e38` | 29,680 |
| Head hair | 0 / `#493e38` | 8 / `#000000` | 21,840 |

Skin/shirt replacements resolve the original Hall samples. Expanded doorway testing exposed hair matching a wall band at1.0;only head hair changes to existing black,raising its worst sampled boundary contrast to1.80202. Pants remain index0;face overlays are unchanged. Silhouette,alpha mask,32×48 frames,feet anchor(16,47),all face anchors,frame counts/timing,art_revision and geometry_version are unchanged. The authoring generator reproduces these choices. A pixel-by-pixel comparison against HEAD permits only the three substitutions above and verifies unchanged dimensions/alpha;no unrelated art changed. Source colors remain provisional and do not define final Maple character design.

### Reproducible rendered contrast

Same software-WebGL sRGB luminance ratio and Hall fixture/background coordinates as the original record. Original Hall method moves only synthetic Maple to reveal the same background pixels. Boundary extension hides only the actor to reveal background;it does not alter scene geometry or lighting. Animation-aware opaque leg coordinates avoid sampling empty between-leg pixels. Original right-facing skin coordinate is hair-occluded and is not mislabeled as visible skin certification. Additional face-ink/visible-skin measurements cover down,left,right;up intentionally has no face overlay.

| Reference down-facing sample | Before night | After night | Morning | Afternoon | Evening |
| --- | --- | --- | --- | --- | --- |
| Hair/floor | 4.20194 | 7.57196 | 8.37180 | 8.59572 | 7.67518 |
| Skin/floor | 1.32729 | 2.00692 | 2.03664 | 2.05298 | 1.99965 |
| Shirt/furniture | 1.33427 | 2.09373 | 2.15658 | 2.18613 | 2.11532 |
| Pants/furniture | 2.09373 | 2.09373 | 2.15658 | 2.18613 | 2.11532 |

Four phases × four open doorway routes ×13 fixed times ×four body samples = **832 rendered boundary samples**,all≥1.5;night/global minimum1.80201685. Routes use supplied door x coordinates and existing open passage/floor tiles from row8 to14 at250ms/step;they are explicitly synthetic QA inputs,not live history. Twelve face-ink/skin cases pass;night minimum2.09372554. Reference captures cover all directions and all phases;source validation covers all112 body frames. This is representative pixel/animation sampling,not an assertion that every possible body/background pixel pair or final artwork is certified. The1.5 threshold and original failing-sample method are unchanged.

### Lighting/browser closure

Playwright1.62.1,Chrome154.0.8037.98,headless ANGLE/SwiftShader software WebGL. Actual DPR1/1.25/1.5/2/3 ×four phases =20 fixture scenarios. Follow L1–L4 uses exact integer device zoom and translations;Overview and Hall Focus/reduced-motion contexts preserve merged camera behavior. All four open door crossings animate through the zone boundary with stable world coordinates and source hooks. No missing atlas textures or captured application console/page errors in the final isolated runs.

Single-multiply pixel harness hides neutral/emitter layers and inserts a uniform white diagnostic base without changing production code. All20 DPR/phase combinations verify1144 cell centers and32 inside-zone corner/edge pixels: **22,880 cell samples +640 edge samples**,exactly the expected single tint,zero gaps/overlap/double tint. Harness uses production canvas CSS and explicit DPR contexts. Initial harness viewport/CSS/CDP capture mismatches and development HMR reload interference were corrected;they were not treated as app failures or passing evidence. Final runs use a stable preview,fixture URL and blocked main entry for isolated scenes.

Six additive sources ×four phases =24 pixel comparisons against the same frame with only the additive layer hidden. Nonzero hooks change pixels;zero hooks leave pixels unchanged. At night,both lamp samples change from185,160,133 to217,187,153;four window samples remain63,55,56 atalpha0. Windowless placeholders have no daylight hooks;Hall/closed rooms use artificial presets. Eight zones cover1144 cells once;source-linked4 windows+2 lamps+1 screen and L16 multiply→add→emissive are preserved. Actual Computer Desk emissive pixel is **196,203,184 in every phase**,matching palette index9 after additive lighting,withalpha1. The earlier incorrectly located screen sample is superseded. Dispose removes canvas and closes atlas leases;existing lifecycle/abort tests pass.

Short software diagnostic remains1 draw call with lighting hidden versus4 enabled (**+3**),CPU submit p95≈0.1ms over~1.5s. This is not hardware GPU timing,phone throttling,60s frame-budget proof or10minute heap acceptance. L21 full performance acceptance and physical devices remain deferred;no unrelated optimization.

### Art pipeline, budgets and quality gates

Complete art validation,MaxRects trim/round-trip/anchor and2px extrusion tests pass. Two independently built complete outputs are byte-identical,includingPNG,metadata,index andbudget JSON.193 frames/two pages;RGBA8,no mipmaps;static1,572,864bytes,plus4,194,304 runtime allowance =5,767,168bytes upper bound,below8,388,608budget. No texture-budget growth.

- Character PNG SHA-256: `257d52e812ee058ffbb544efc479caa7856af7b0a47c48fe28572f9d1480696f` → `630070036d3fdc838d782d6f7be8ced0f309ce864b6705110fc5cbba5154e669`.
- Shared PNG unchanged: `ec634d545d1af7dc4a1c53fe6c92462f4da820b0ff4cefc5b2c30077c36f77a3`.
- Character metadata unchanged: `8776fdc50db20fd91246c05cef63c306c32af1a75129b44d0d043860e66ee6ee`.
- Shared metadata unchanged: `1b50a5a357501708bf5fc90cec4da8c994ae47aaa24d61c1ce2ca9bb4c708192`.
- Generated index unchanged: `5ee8f05364b6a9f42c1a75d4ee2b2b219dbc5648d636413241115491a060e833`.

Only necessary reproduction reference character hash changes;native Windows comparison test/workflow unchanged. **New source content still requires native Windows GitHub CI after separately authorized integration.** Mac deterministic reproduction is not native Windows evidence. Vite emits updated content-hashed character page;shared page unchanged;bundle verification finds2 hashed pages,0 raw sources,productionPreview false.

**549 Vitest cases/22files +66 Node asset/bundle cases PASS,0 failures.** Compared with the initial STEP137 batch,this adds4 phase/palette contrast cases and1 all-pose source-art regression. Initial34 lighting/scene/DOM cases and existing renderer/camera/depth/walking/atlas/architecture tests remain passing. **237 backend/API/security/Oracle/Harness cases PASS;10 import contracts kept,0 broken.** ESLint,TypeScript,production build PASS on final artwork/code. OpenAPI/types/five fixture regeneration matches exactly. No Python source edits;Ruff/mypy not newly applicable. No full simulation or release gate rerun;original simulation pin and Oracle/Harness remain unchanged.

### Safety and handoff

Production Director/API/SSE/schema-v10/legacy default unchanged;fixture preview remains an explicit development entry. No raw-art exposure,dependencies,canonical geometry,camera math,accepted ADR/spec or Oracle changes. Final lighting colors/strengths,device default zoom and final character artwork remain UNDECIDED. R1A-15 may use the typed phase/configuration and source-linked/lifecycle interfaces only after its own authorization;no coexistence implementation here. Local R1A-13 is ready for owner acceptance;native Windows reproduction and integration remain future gates. No commit,push,PR,merge,deployment,Production access or R1A-15.

### Retained evidence

- [Five-DPR phase/camera/reference contrast and emissive](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a13-continue-browser.json)
- [Four-phase boundary contrasts](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a13-boundary-contrast.json)
- [DPR single-tint coverage](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a13-seams.json)
- [Additive pixels and face contrasts](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a13-emitter-face.json)
- [Source pixel/alpha/dimension comparison](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a13-source-integrity.json)
- [Complete atlas reproduction report](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a13-final-determinism.json)

Browser reproduction scripts are retained beside those JSON records (`r1a13-*.cjs`);they require the existing bundled Playwright/PNG runtime and local preview,not new project dependencies. [Night scene](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a13-continue-measured-night.png),[doorway crossing](/Users/paolo_cu/.codex/visualizations/2026/10/10/01a12655-3005-7c71-807a-96cb2a5e61ef/r1a13-cross-door.hall_living-750.png). Temporary debug captures removed;preview stopped after QA.

### Actual combined changed-file manifest

- `CLAUDE.md`
- `art/export/char/char.maple/char.maple--idle.png`
- `art/export/char/char.maple/char.maple--lie_sleep.png`
- `art/export/char/char.maple/char.maple--react_greet.png`
- `art/export/char/char.maple/char.maple--react_pet.png`
- `art/export/char/char.maple/char.maple--sit_idle.png`
- `art/export/char/char.maple/char.maple--sit_monitor.png`
- `art/export/char/char.maple/char.maple--sit_read.png`
- `art/export/char/char.maple/char.maple--sit_rest.png`
- `art/export/char/char.maple/char.maple--sit_write.png`
- `art/export/char/char.maple/char.maple--stand_read.png`
- `art/export/char/char.maple/char.maple--stand_think.png`
- `art/export/char/char.maple/char.maple--walk.png`
- `docs/architecture.md`
- `docs/frontend.md`
- `docs/implementation/maple-room-r1a-12-camera-zoom-dpr.md`
- `docs/implementation/maple-room-r1a-checklist.md`
- `docs/implementation/maple-room-r1a-plan.md`
- `docs/implementation/maple-room-r1a-worklog.md`
- `frontend/src/world-room/Preview.test.tsx`
- `frontend/src/world-room/Preview.tsx`
- `frontend/src/world-room/scene.test.ts`
- `frontend/src/world-room/scene.ts`
- `frontend/tools/art/make-placeholders.mjs`
- `frontend/tools/art/pipeline.test.mjs`
- `frontend/tools/art/reproducibility.json`
- `docs/implementation/maple-room-r1a-13-lighting-zones.md`
- `frontend/src/world-room/lighting.test.ts`
- `frontend/src/world-room/lighting.ts`

29 scoped files;all uncommitted. Generated atlases/dist and browser artifacts are excluded from Git.

### Final integrity review

`git diff --check` PASS;88 relative Markdown links resolve;20 checklist rows =13 DONE/1 REVIEW/6 TODO. Worklog HEAD content remains an exact byte prefix;prior STEP137 blocked entry also retained. All14 unrelated worktree HEAD/status snapshots and local-only40f0eb7 remain unchanged. Worktree HEAD stays48897c8,index empty;29 scoped changed files. Final ESLint,TypeScript,build and549/66 frontend/asset suite PASS after correcting strict tuple inference in the new test;no renderer/art change for that correction. Vite outputs `character-0-BaduxT1u.png` and unchanged `shared-0-LxlzOm8s.png`,verified by content hash. Preview stopped,port5179 has no listener;browser contexts/processes closed. No accepted ADR/spec,master palette,body/face metadata,backend,Oracle/Harness,simulation pin,dependencies or workflow edits.


## STEP138 — owner acceptance and GitHub integration preparation (2026-10-12)

Owner ACCEPTS R1A-13 and the narrow original-placeholder skin/shirt/head-hair corrections;colors and lighting settings remain provisional. Status is **REVIEW / OWNER ACCEPTED / MERGE PENDING** until confirmed PR merge. R1A-11/12/14 DONE / MERGED. Current13 DONE/1 REVIEW/6 TODO=65%;intended after merge14 DONE/6 TODO=70%. No next workstream,merge,deployment,Production access or schema-v11 activation.

Verified existing worktree/branch/HEAD,live remote development unchanged at48897c8,feature remote absent before publication. Reviewed all29 paths:8 documentation,6 renderer/test,12 placeholder body PNGs,3 art-pipeline files. Pixel comparison freshly confirms only16,128 skin,29,680 shirt and21,840 head-hair substitutions;dimensions/alpha unchanged. Master palette,all metadata/anchors/timing/frame counts,faces/pants,accepted ADR/spec,world data,backend/schema/API/SSE/Director,Oracle/Harness,simulation pin,security policy,dependencies and CI workflows unchanged. No secrets,generated atlases,dist,local config or browser/debug artifacts included.

**Fresh STEP138 integration checks:**549 Vitest/22files and66 Node asset/bundle tests PASS;237 backend/API/security/Oracle/Harness PASS;10 import contracts kept,0 broken;ESLint,TypeScript,production frontend build and exact OpenAPI/TypeScript/five fixture export comparisons PASS. Complete art validation/MaxRects trim-anchor-extrusion tests pass. Two new independent complete atlas outputs are byte-identical and match the Windows reproduction reference. Only the character PNG hash differs from the original baseline;sharedPNG,metadata,index andtexture budget are unchanged. Bundle verifies2 hashed pages,0 raw sources,productionPreview false. No Full Release Gate or simulation rerun.

**Reused accepted STEP137 CONTINUE browser evidence,not newly rerun:**Playwright1.62.1/Chrome154/softwareWebGL;fiveDPRs×fourphases;22,880cell+640edge samples,832doorway contrasts(min1.802),12face/skin samples and exact196,203,184 emissive in every phase. Night hair4.202→7.572,skin1.327→2.007,shirt1.334→2.094,pants2.094→2.094. Original measurement methodology and1.5minimum unchanged. Final artwork/colors/strengths,hardware-device QA and fullL21 acceptance remain deferred.

Native Windows atlas reproduction **PENDING PR CI** at this precommit record;unchanged Windows gate must validate the new source content. Local Mac determinism does not substitute for that result. Commit,push,PR and actual per-job CI outcomes are reported after execution;this record does not predeclare CI success or merge readiness. Worklog remains append-only;29-file manifest above remains the reviewed scope.
