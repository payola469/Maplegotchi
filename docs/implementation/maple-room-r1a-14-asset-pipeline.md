# R1A-14 — Asset pipeline and atlas integration

**Current STEP 129 status (2026-10-11): REVIEW / INTEGRATION PENDING.** Owner accepts the local evidence for reviewed commit, normal push, PR and native CI inspection. R1A-11 remains REVIEW / PARTIAL pending formal atlas integration acceptance. No merge, deployment, production access or other workstream. STEP 128 local-only authorization and evidence below remain historical.

**Status:** REVIEW / PARTIAL / STEP 128 CONTINUE. Local implementation and consolidated review PASS; full acceptance has a CONCERN: native Windows reproduction pending. R1A-11 atlas dependency locally resolved; formal acceptance/integration pending. No publication or deployment.
**Baseline:** `f7e313cbe16992593d7f387450c9101d1b31f358`, verified PR #11 merge and origin integration HEAD.
**Workspace:** `r1a-14-asset-pipeline/Maplegotchi`; branch `codex/r1a-14-asset-pipeline`. Existing branches/worktrees and local-only `40f0eb7` preserved.

## Binding inputs and decision

Locked [ADR-0041](../adr/0041-art-technical-contract.md) → accepted ADR-0035–0040 → [Final Spec](../architecture/maple-room-final-design-spec.md) → proposed Future Architecture. [Art contract](../architecture/maple-art-production-contract.md) B.14/B.18/C/E, [spike](../spikes/2026-10-room-art-spike.md), [Master Plan](maple-room-r1a-plan.md#r1a-14--asset-pipeline-and-atlas-integration), [R1A-11](maple-room-r1a-11-pixi-renderer-shell.md) and [R1A-10](maple-room-r1a-10-world-api-contracts.md) supply scope and contracts.

Owner STEP 128 CONTINUE resolves B.4/E8 versus C.2: canonical base/occupant/emissive/ordinary parts share an anchor; explicitly declared light/shadow centres alone may differ. Each part is stable across frames/states per orientation. Independent kinds retain kind-specific anchors. Contract and ADR clarification preserve the original C.2 `(24,8)` light example; no broader exception.

## Sequential implementation and validation gates

1. Reconcile anchors and implement offline E1–E8, E10–E13, E18/E20/E23–E25 validator; positive complete placeholders and isolated rule-negative tests. Check effective Git attributes, source integrity and S17 against backend catalog, including the no-art structural marker exception.
2. Deterministic MaxRects BSSF: sort longest side, area, lexical frame key; placement ties short-side, long-side, y, x, page; split all intersecting free rectangles and prune contained ones. No rotation. Trim alpha bounds, preserve original sourceSize/spriteSourceSize/anchor, 2 px extrusion. Per-pack power-of-two pages within 512 (character/fx) or 1024 (others). Pixel and metadata hashes compared independently.
3. Source inputs `art/export/**` PNG/sidecars and `art/palette/**`, original neutral test art only. Authoring is explicit; builds never repair/regenerate invalid source art. Generated pages/metadata/module live in ignored `frontend/src/world-room/generated/`, never public or committed. Complete required keys fail closed. Placeholder face 12×6 remains provisional; no final art or palette freeze.
4. Vite imports generated PNG URLs and bundles metadata; release archive carries source art, palette, attributes and frontend tooling. Production fixture preview remains eliminated; no new route or live-world wiring. Bundle-content check rejects source art/sidecars/palette leaks. Clean isolated archive-style builds must regenerate without developer output.
5. Pixi 8.21 spritesheets preserve original canvases/trim offsets. Reference-counted serialized loading/unloading leases own shared textures, nearest/no mipmaps, once-only Assets.init/preferWorkers false/unsafe-eval; no CSP change. Scene retains L6/L11/L12/L13/L17 and DOM ownership. Light/shadow anchor-position primitives only; no R1A-13 lighting behavior.
6. Full frontend, targeted API/security/export and import checks; deterministic clean rebuilds, release package checks, browser QA if actually run. Windows reproduction prepared in CI but native Windows pending; Linux independent reproduction belongs to R1A-18. Separate implementation readiness, full acceptance and R1A-11 dependency verdicts.

## Formats and boundaries

Source sidecars follow contract C fields. Initial tooling extensions: `tiles` declares sheet rows/columns; `role: face_overlay|structural` distinguishes C3 border classes; `catalog_points`/`catalog_slots` retain build-time canonical data for S17 comparison; `anchor_role` identifies the two approved centre exceptions. `frame_anchors`/`state_anchors` may explicitly assert stability and must match the part anchor. Optional `display_anchors` name existing host slots and stay within their asset canvas. R1A-10 explicitly deferred slot pixel anchors to art delivery: the backend has no approved numeric display-anchor values, and the current shell draws no slot-item sprites. No approach tile is converted into an invented display anchor; final slot art must supply these coordinates before its visual integration. No independent runtime geometry table is authored in the frontend.

Generated page JSON uses Pixi frames (`frame`, `rotated:false`, `trimmed`, `spriteSourceSize`, `sourceSize`), page meta, plus original integer `anchor_px` and per-frame `face_anchor`. The generated module imports page URLs and embeds metadata/manifest. No absolute paths or timestamps. PNG encoding uses RGBA8/filter-0/stored DEFLATE blocks, fixed chunk sequence and checksums: independent of compressor version and platform. Decoder accepts RGBA8 filters 0–4 with CRC and bounded decompression, rejecting forbidden ancillary chunks.

GPU budgets use actual page width×height×4, no mipmaps; static ≤28 MiB, reserved runtime ≤4 MiB, resident ≤32 MiB. Report includes `max(ceil8(upper bound), ceil8(1.5 × realistic projection))`. Compressed file sizes are not GPU budgets.

No legacy Room, backend runtime, schema, Oracle/Harness, simulation pin, camera/lighting, Edit Mode or production changes. E9/E14–E17/E19/E21/E22 manual/diff/visual responsibilities retain their original status; automated checks do not certify final production art.

## Evidence

### Commands and actual results — 2026-10-11

macOS Node **24.16.0**, pnpm **12.9.1**, lockfile unchanged; Pixi **8.21.0**, Vite **8.3.1**, TypeScript **6.0.3**, Vitest **5.0.2**, ESLint **10.11.0**. Tooling uses Node stdlib only; no dependency/lockfile changes. CI retains Node 24/pnpm 12.3.4.

From `frontend`:

```sh
pnpm assets:build
pnpm lint
pnpm typecheck
pnpm test
pnpm assets:test
pnpm build
```

- Full Vitest: **423 cases / 20 files / 0 failures** (417 existing + six new atlas cases). Unchanged L11 depth ring **144/144**, L12 supplied-time/distance phases, L13 sizing, L17 variants/edges and production/fixture isolation remain covered.
- Final Node asset/bundle tests: **65 passed / 0 failed**. The final three optional display-anchor cases were run after the full frontend suite; unrelated Vitest tests were not repeated.
- ESLint/TypeScript/production build PASS; there is no separate configured frontend formatter. Generated files are ignored by lint; security rules still apply to handwritten tools/source.
- 193 frames independently round-trip pixel-for-pixel with sourceSize/trim/anchors and every extrusion pixel checked. Anchor regression cases cover base/occupant/emissive matching, declared light/shadow exceptions, unauthorized mismatches, bounds and frame/state changes. Actual Pixi trim/orig and light/shadow Sprite position checks PASS.
- E-rule negative fixtures cover invalid metadata, IDs, dimensions, PNG integrity/profile/alpha/palette, border/safe area, frames/states/orientations/timing/face anchors, catalog/version/mount/mask/point/slot mismatch, missing keys, LFS pointers/effective attributes, and export-ignore. Synthetic oversized page/budget inputs fail. Source art is never silently repaired.
- Atlas lifecycle cases exercise two simultaneous leases, last-user unload, missing/version errors, partial-load and parse failure, retry, cancellation/GPU failure cleanup. No production network loader was added.

From `backend`, focused `uv run pytest` over `tests/world/test_catalog.py`, `test_oracle.py`, `test_harness.py`, `test_contracts.py`, `tests/api/test_world_api.py`, `test_api_security.py` and `tests/security`: **367 passed / 0 failed**. `uv run python -m tests.api.world_contract_export`: OpenAPI, derived TypeScript and all five fixture exports reproduce exactly. `uv run lint-imports --no-cache`: **10 kept / 0 broken**. No Python changes; existing Ruff/mypy evidence is unaffected, no new Python static-check claim. Full Release Gate and 30-day simulation were not rerun; original simulation pin and its dependencies remain unchanged.

`bash -n scripts/build_release.sh`, `shellcheck scripts/build_release.sh`, documentation link/counter checks and `git diff --check`: PASS.

### Outputs, hashes and budgets

65 source PNGs / 25 sidecars plus one palette; **193 packed frames / two pages**:

| Page | RGBA8 dimensions | GPU bytes | PNG SHA-256 | Metadata SHA-256 |
|---|---|---:|---|---|
| character-0 | 512×512 | 1,048,576 | `257d52e812ee058ffbb544efc479caa7856af7b0a47c48fe28572f9d1480696f` | `8776fdc50db20fd91246c05cef63c306c32af1a75129b44d0d043860e66ee6ee` |
| shared-0 | 512×256 | 524,288 | `ec634d545d1af7dc4a1c53fe6c92462f4da820b0ff4cefc5b2c30077c36f77a3` | `1b50a5a357501708bf5fc90cec4da8c994ae47aaa24d61c1ce2ca9bb4c708192` |

Static **1.5 MiB**, runtime reserve **4 MiB**, resident upper bound **5.5 MiB**; L20 budget formula **8 MiB**. All below locked limits. Machine evidence: ignored generated `budget.json` and checked-in source test reference [`reproducibility.json`](../../frontend/tools/art/reproducibility.json). Two clean rebuilds are byte-identical for PNG, page JSON and generated index. Changed valid shared source pixels invalidate only the relevant image hash.

Vite emits `character-0-vVpon7yL.png` / `shared-0-LxlzOm8s.png`. Build verifies their bytes match generated pages, with **zero raw source/sidecar/palette files and no fixture-preview JavaScript**. Four bundle boundary tests include deliberately leaked sidecar/raw PNG/preview failures. Production legacy chunk names remain unchanged. Required metadata is embedded in the development atlas module; no metadata HTTP fetch.

### Release-style clean build

A temporary-index tree (no commit/ref or real-index mutation) was archived with exactly the script's source path list. Fresh extraction had no node_modules/dist/generated atlases; `pnpm install --offline --frozen-lockfile && pnpm build` PASS with identical page hashes. Runtime payload assembled with the existing copy rules contains processed frontend assets and backend catalog; source art/palette/tools are absent. Release script change is limited to adding art source/palette/attributes to build inputs. No installation/deployment changes.

The committed-revision tarball command was not run: it requires a committed revision/clean HEAD, whereas this batch explicitly forbids committing. Clean archive/build/payload verification is the local evidence, not a claim of an emitted release tarball or deployment.

### Browser review

Actual in-app WebGL fixture preview at local port 5176, no GPU fallback. All eight regions, wall/cap/door/window sprites, furniture, Maple and face overlays rendered from atlases. Desktop 1440×1100: idle feet `(344,253)`; at route time 375 ms feet `(368,253)`, right/walk frame 3; arrival 2750 ms feet `(520,253)`, stationary frame 0. No missing-texture checkerboards or visible extrusion seams at tested scale. 390×844 DOM fallback and 820×1100 Overview emulation have no horizontal overflow. Fresh reload console warnings/errors: **zero**. Unit tests cover cleanup; this was not a soak or real-device performance certification. Viewport restored; screenshots kept outside Git in the task visualization directory (`r1a14-atlas-walking.jpg`, `r1a14-atlas-mobile.jpg`). STEP 125 screenshots retain before-atlas history.

### Consolidated review and handoff

- **A — anchor conflict: PASS.** B.4/C.2/E8 and append-only ADR clarification agree with the owner decision, including the original `(24,8)` light example. No arbitrary-part exemption.
- **B — R1A-14 local implementation: PASS; full acceptance: CONCERN / REVIEW / PARTIAL.** Native Windows hash reproduction has not run. Windows CI job is prepared to compare image AND metadata bytes to the macOS golden reference. Cross-platform separator tests alone are not native evidence. No GitHub run/publication authorized in this batch.
- **C — R1A-11 atlas dependency: locally resolved.** Required current visual keys, full house, L19, trim/anchors, lifecycle and regressions pass. Shell completion criteria can now be reviewed with atlas evidence; formal owner acceptance and normal integration/CI remain required. R1A-11 remains REVIEW / PARTIAL, not DONE.
- **D — reproduction readiness: prepared.** R1A-18 must independently build clean committed inputs on Linux and compare both hashes, including release/archive attributes and bundle boundaries. Windows CI must pass before cross-platform acceptance.

No backend runtime, schema v10, accepted house/DTO geometry, Final Spec, Oracle/Harness, simulation pin, API/SSE/security/CSP, legacy Room, dependencies, production configuration or unrelated worktree changes. Source and runtime manifests preserve backend S17 versions/geometry; the structural-marker no-art exception is unchanged. No camera/lighting/Edit Mode, R1A-12/13 or later implementation. Final art, provisional face dimensions, slot-art display coordinates, real-device acceptance, performance and soak remain their documented future gates. The light/shadow APIs preserve positions without implementing lighting. No further accepted-design conflict found in consolidated scope review.

Owner can review the local implementation now; full acceptance is pending native Windows evidence and normal owner/integration gates. No commit/push/PR/merge/deployment performed.


## Changed-file manifest

124 files; source PNGs/sidecars included, ignored generated output/build/browser artifacts excluded.

```text
.github/workflows/ci.yml
.gitignore
CLAUDE.md
art/README.md
art/export/backdrop/backdrop.window/backdrop.window--default--south.png
art/export/backdrop/backdrop.window/backdrop.window.meta.json
art/export/char/char.faces/char.faces--face_calm.png
art/export/char/char.faces/char.faces--face_curious.png
art/export/char/char.faces/char.faces--face_focused.png
art/export/char/char.faces/char.faces--face_happy.png
art/export/char/char.faces/char.faces--face_sleepy.png
art/export/char/char.faces/char.faces.meta.json
art/export/char/char.maple/char.maple--idle.png
art/export/char/char.maple/char.maple--lie_sleep.png
art/export/char/char.maple/char.maple--react_greet.png
art/export/char/char.maple/char.maple--react_pet.png
art/export/char/char.maple/char.maple--sit_idle.png
art/export/char/char.maple/char.maple--sit_monitor.png
art/export/char/char.maple/char.maple--sit_read.png
art/export/char/char.maple/char.maple--sit_rest.png
art/export/char/char.maple/char.maple--sit_write.png
art/export/char/char.maple/char.maple--stand_read.png
art/export/char/char.maple/char.maple--stand_think.png
art/export/char/char.maple/char.maple--walk.png
art/export/char/char.maple/char.maple.meta.json
art/export/decor/decor.project_board/decor.project_board--default--south--shadow.png
art/export/decor/decor.project_board/decor.project_board--default--south.png
art/export/decor/decor.project_board/decor.project_board.meta.json
art/export/decor/decor.wall_frame_small/decor.wall_frame_small--default--south--shadow.png
art/export/decor/decor.wall_frame_small/decor.wall_frame_small--default--south.png
art/export/decor/decor.wall_frame_small/decor.wall_frame_small.meta.json
art/export/door/door.closed/door.closed--default--south.png
art/export/door/door.closed/door.closed.meta.json
art/export/door/door.north_2w/door.north_2w--default--south.png
art/export/door/door.north_2w/door.north_2w.meta.json
art/export/furniture/furniture.armchair/furniture.armchair--default--south--cover.png
art/export/furniture/furniture.armchair/furniture.armchair--default--south--shadow.png
art/export/furniture/furniture.armchair/furniture.armchair--default--south.png
art/export/furniture/furniture.armchair/furniture.armchair.meta.json
art/export/furniture/furniture.bed_single/furniture.bed_single--default--south--cover.png
art/export/furniture/furniture.bed_single/furniture.bed_single--default--south--shadow.png
art/export/furniture/furniture.bed_single/furniture.bed_single--default--south.png
art/export/furniture/furniture.bed_single/furniture.bed_single.meta.json
art/export/furniture/furniture.bookshelf_tall/furniture.bookshelf_tall--default--south--shadow.png
art/export/furniture/furniture.bookshelf_tall/furniture.bookshelf_tall--default--south.png
art/export/furniture/furniture.bookshelf_tall/furniture.bookshelf_tall.meta.json
art/export/furniture/furniture.computer_desk/furniture.computer_desk--default--south--cover.png
art/export/furniture/furniture.computer_desk/furniture.computer_desk--default--south--emissive.png
art/export/furniture/furniture.computer_desk/furniture.computer_desk--default--south--light.png
art/export/furniture/furniture.computer_desk/furniture.computer_desk--default--south--shadow.png
art/export/furniture/furniture.computer_desk/furniture.computer_desk--default--south.png
art/export/furniture/furniture.computer_desk/furniture.computer_desk.meta.json
art/export/furniture/furniture.lamp_floor/furniture.lamp_floor--default--south--emissive.png
art/export/furniture/furniture.lamp_floor/furniture.lamp_floor--default--south--light.png
art/export/furniture/furniture.lamp_floor/furniture.lamp_floor--default--south--shadow.png
art/export/furniture/furniture.lamp_floor/furniture.lamp_floor--default--south.png
art/export/furniture/furniture.lamp_floor/furniture.lamp_floor.meta.json
art/export/furniture/furniture.plant_tall/furniture.plant_tall--default--south--shadow.png
art/export/furniture/furniture.plant_tall/furniture.plant_tall--default--south.png
art/export/furniture/furniture.plant_tall/furniture.plant_tall.meta.json
art/export/furniture/furniture.rug/furniture.rug--default--south--shadow.png
art/export/furniture/furniture.rug/furniture.rug--default--south.png
art/export/furniture/furniture.rug/furniture.rug.meta.json
art/export/furniture/furniture.shelf_low/furniture.shelf_low--default--south--shadow.png
art/export/furniture/furniture.shelf_low/furniture.shelf_low--default--south.png
art/export/furniture/furniture.shelf_low/furniture.shelf_low.meta.json
art/export/furniture/furniture.side_table/furniture.side_table--default--south--shadow.png
art/export/furniture/furniture.side_table/furniture.side_table--default--south.png
art/export/furniture/furniture.side_table/furniture.side_table.meta.json
art/export/furniture/furniture.sofa/furniture.sofa--default--south--cover.png
art/export/furniture/furniture.sofa/furniture.sofa--default--south--shadow.png
art/export/furniture/furniture.sofa/furniture.sofa--default--south.png
art/export/furniture/furniture.sofa/furniture.sofa.meta.json
art/export/furniture/furniture.writing_desk/furniture.writing_desk--default--south--cover.png
art/export/furniture/furniture.writing_desk/furniture.writing_desk--default--south--shadow.png
art/export/furniture/furniture.writing_desk/furniture.writing_desk--default--south.png
art/export/furniture/furniture.writing_desk/furniture.writing_desk.meta.json
art/export/tile/tile.floor_edge/tile.floor_edge--sheet.png
art/export/tile/tile.floor_edge/tile.floor_edge.meta.json
art/export/tile/tile.floor_wood/tile.floor_wood--sheet.png
art/export/tile/tile.floor_wood/tile.floor_wood.meta.json
art/export/wall/wall.cap/wall.cap--default--south.png
art/export/wall/wall.cap/wall.cap.meta.json
art/export/wall/wall.north/wall.north--default--south.png
art/export/wall/wall.north/wall.north.meta.json
art/export/wall/wall.side/wall.side--default--south.png
art/export/wall/wall.side/wall.side.meta.json
art/export/wall/wall.south/wall.south--default--south.png
art/export/wall/wall.south/wall.south.meta.json
art/export/window/window.north_2w/window.north_2w--default--south--emissive.png
art/export/window/window.north_2w/window.north_2w--default--south--light.png
art/export/window/window.north_2w/window.north_2w--default--south--shadow.png
art/export/window/window.north_2w/window.north_2w--default--south.png
art/export/window/window.north_2w/window.north_2w.meta.json
art/palette/maple-master.hex
docs/adr/0041-art-technical-contract.md
docs/architecture.md
docs/architecture/maple-art-production-contract.md
docs/deployment.md
docs/frontend.md
docs/implementation/maple-room-r1a-11-pixi-renderer-shell.md
docs/implementation/maple-room-r1a-14-asset-pipeline.md
docs/implementation/maple-room-r1a-checklist.md
docs/implementation/maple-room-r1a-plan.md
docs/implementation/maple-room-r1a-worklog.md
frontend/eslint.config.js
frontend/package.json
frontend/src/world-room/Preview.tsx
frontend/src/world-room/assets.ts
frontend/src/world-room/atlas.test.ts
frontend/src/world-room/atlas.ts
frontend/src/world-room/scene.test.ts
frontend/src/world-room/scene.ts
frontend/tools/art/bundle.mjs
frontend/tools/art/bundle.test.mjs
frontend/tools/art/cli.mjs
frontend/tools/art/make-placeholders.mjs
frontend/tools/art/pack.mjs
frontend/tools/art/pipeline.test.mjs
frontend/tools/art/png.mjs
frontend/tools/art/reproducibility.json
frontend/tools/art/validate.mjs
frontend/vite.config.ts
scripts/build_release.sh
```

## STEP 129 — final integration review

Final scope remains **124 files**; every path in the manifest above classified below. No additional assets or runtime wiring. Security review found no credentials/private data, generated outputs, browser artifacts, raw public art, LFS pointers or forbidden attributes. Backend/legacy/API/SSE/schema/Oracle/Harness/simulation/CSP/dependencies remain unchanged. All required source inputs will be staged explicitly from this manifest; real index was empty before staging.

Closed the two STEP 129 gate additions before publication: generated-index SHA-256 is now part of the machine report/reference; Windows CI runs the clean golden PNG/metadata/index comparison and then a frontend production build/bundle check. Index SHA-256: `5ee8f05364b6a9f42c1a75d4ee2b2b219dbc5648d636413241115491a060e833`. Existing PNG/metadata hashes and 193-frame/page/budget figures are unchanged. These are stricter gate additions, no weakened expectations.

Final focused commands: `pnpm lint`, `pnpm typecheck`, `pnpm assets:test`, `pnpm exec vitest run src/world-room`, `pnpm build`: **65 asset/bundle + 215 renderer cases PASS**, zero failures; ESLint/TypeScript/build PASS. Reuse accepted full 423 frontend / 367 backend / ten import-contract / exact export evidence. Browser evidence reused; no new visual or backend testing claim. Patch whitespace and documentation consistency checked. Windows result remains pending actual execution.

After committing, STEP 129 requires an isolated build using `scripts/build_release.sh` on the exact committed revision, with GNU tar available on macOS and an offline frozen install. Verify archived tracked sources, no inherited generated files, regenerated PNG/metadata/index hashes and processed-only tarball contents. The gate outcome, exact commit/PR and CI statuses will be reported in the PR/final report; no pre-commit PASS claim for that future gate. R1A-18 independent Linux reproduction remains separate.

| Scope classification | Files |
|---|---:|
| Vite/build/release configuration (including CI and generated-output ignore) | 6 |
| Documentation | 12 |
| Art source | 66 |
| Art metadata | 25 |
| Renderer atlas integration | 4 |
| Tests | 4 |
| Validator/packer (including golden reference and explicit placeholder authoring) | 7 |

No Other paths. The full 124-path manifest remains authoritative.
