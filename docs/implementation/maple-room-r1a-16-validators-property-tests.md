# R1A-16 — Validators and property tests

**Current integration reconciliation — STEP 155, 2026-10-12: DONE / OWNER ACCEPTED / MERGED.** PR #17 merge `50ec74865cee9c65ed566251476df7bbeed2dbd2` independently verified in the acceptance baseline ancestry. Earlier dated implementation/review/publication statements below are historical. Accepted decisions and measurement provenance remain unchanged. [Current R1A-20 audit](maple-room-r1a-20-acceptance-gate.md).

## Plan recorded before implementation — STEP 143, 2026-10-12

Verified integration baseline: `78953ce60d929a4e0a595b8c957ad5dd6b9fa49e` (PR #16, R1A-15 merged). Clean main was fetched and fast-forwarded only. Worktree: `C:\GitHub\Maplegotchi-worktrees\r1a-16-validators-property-tests`; branch: `codex/r1a-16-validators-property-tests`. Other checkouts/branches are preserved.

### Inventory and gaps

Existing pure validators: `validation.validate_regions` (S1), `geometry.derive_structure` (S1/S2), `topology.derive_topology` (S3/S4), `lighting.derive_lighting/can_mount` (S7/S12), catalog constructors and `build_catalog_layout` (S6/S7/S8/S15/S16/S17), `walkability.derive_walkability/validate_safe_layout` (S5/S8/S10/S13), `resolution.validate_activity_coverage/candidates_for` (S9), placement candidate validation (S11/authorized display placement), recovery and legacy projection (S13/S14). Existing Oracle independently pins T1–T7; Harness, synthetic v11 rehearsal and simulation tests remain authoritative. Missing: one aggregate entry point with structured failures, explicit art-version cross-check, complete named mutation matrix and cross-module deterministic properties.

### API and error proposal

Add a separate pure module, avoiding the existing geometry→validation dependency cycle. `validate_layout(candidate)` returns a frozen result containing a tuple of frozen errors and success status. Candidate uses immutable domain inputs (regions, doors, zones, object types, instances, Maple tile) and explicitly supplied immutable art geometry records and legacy targets. It performs no resource loading. Constructors remain the strict deserialization boundary; this API accepts typed domain values, not arbitrary JSON.

Errors have stable rule/code (`S1`–`S17`), tuple location, and safe fixed actionable rule message; sorted by numeric rule then location. Existing fail-fast validators are composed in dependency stages; independent stages continue after failures, dependent stages are skipped, with no promise of exhaustive errors after a prerequisite failure. No exception-string parsing is used to determine public codes where a check can be isolated; an explicit adapter is needed for existing multi-rule builders. Original caller behavior stays intact.

### Test matrix and corpus

Canonical house passes all S1–S17. Named deterministic mutations fail each corresponding rule: grid/region overlap; band gap; door adjacency; disconnected graph; open door into closed room; overlapping furniture; doorway mount; undeclared slot reuse; missing last provider; blocked K corridor; unauthorized hook policy; lighting gap; invalid Maple/fallback; missing legacy target/action; desk capability overlap; Maple-movable initial furniture; art version/type/orientation mismatch. Corpus fixtures are reconstructed from release inputs; canonical data and Oracle pins are never edited. Constructor rejection and aggregate validation are distinguished.

### Properties and integration

Use standard-library deterministic parameterization, fixed seed 143, with explicit case IDs. Check routes and supplied-time movement, all-grid recovery, capability eligibility/repeatability/provider removal, slot permission/sharing/geometry invariance, and truthful legacy timing with the accepted collapsed-anchor/mid-edge rejection policy. Compose existing Oracle/Harness expectations; do not duplicate their tables or loosen pins. Art records are read in tests from accepted `art/export/**/*.meta.json`; source/frame/anchor/LFS/atlas/bundle rules stay in the existing JavaScript pipeline. No new dependency.

### Cost, isolation and reproducibility

Measure canonical 44×26 valid, invalid and multi-error candidates with repeated ordering checks; report input counts, environment and min/median/max timing. This is bounded validation evidence, not R1A-19 performance acceptance. Core has no I/O, network, clock, environment, rendering or global mutable state dependence. No route/API/SSE/schema/production/default-room changes. Full Windows backend and frontend/asset regression gates, static checks, exports, links, counters, append-only worklog and diff checks are required. Windows-only skips remain explicit; Ubuntu CI is deferred to separately authorized integration. Owner acceptance and merge remain pending; R1A-16 becomes REVIEW only after local validation.

## Implementation and acceptance evidence — STEP 143

### Delivered API and scope

`backend/src/maplegotchi/core/world/layout_validation.py` exports `ArtGeometry`, `LayoutCandidate`, `ValidationError`, `ValidationResult` and `validate_layout`. The typed candidate checks immutable tuple inputs. Art records check immutable unique orientations and positive integer geometry versions. Domain constructors remain the parsing boundary. Example use: `result = validate_layout(candidate); result.valid; result.errors`. Invalid layouts return structured errors; malformed typed envelopes raise `ValueError` before validation. No loader, renderer, endpoint or runtime activation is added.

Error shape: `ValidationError(code="S10", location=("walkability",), message="Keep K1-K3 clear and preserve dynamic K4 connectivity.")`. Error records/result are frozen. Codes are S1–S17, sorted numerically and then by location; duplicate records collapse. Coarse section locations are retained for reused fail-fast builders; newly checked art, hook and projection errors carry stable IDs. Fixed messages never copy input strings or exception details. The adapter recognizes documented S-prefixes only, falling back to the stage's rule; corpus tests protect those mappings. Independent stages continue; dependent checks are suppressed after invalid prerequisites. This is intentionally not exhaustive diagnosis of every downstream symptom.

### S1–S17 coverage matrix

Every positive row executes `test_each_rule_positive[S#]` on the release house; every negative row executes `test_named_negative_corpus[S#]` and asserts that exact code. Canonical inputs are unchanged after every mutation. The full corpus and canonical candidate also produce identical results when all input tuples are reversed; seed143 shuffles multi-error metadata20 times without changing the result.

| Rule/code | Positive | Deliberate negative / checked location |
|---|---|---|
| S1 | PASS | Width43; additional overlapping regions / regions |
| S2 | PASS | Shift Bedroom floor to leave structural gap / regions |
| S3 | PASS | Door passage moved out of adjacent band / doors |
| S4 | PASS | Close sole Bedroom door / doors |
| S5 | PASS | Open door into closed Future Space / doors |
| S6 | PASS | Lamp blocking mask overlaps sofa / instances |
| S7 | PASS | Hall frame mounted over door columns / instances |
| S8 | PASS | Undeclared slot/armchair point coincidence / instances; additional blocked approach / points |
| S9 | PASS | Remove sole sleep provider / activities; additional last-provider removal for all8 activities |
| S10 | PASS | Move lamp onto Hall K3 corridor / walkability |
| S11 | PASS | Hook slot policy permits Maple placement / instances, host, slot |
| S12 | PASS | Remove lighting zone / zones |
| S13 | PASS | Remove central idle marker / walkability; additional Maple in closed room |
| S14 | PASS | Remove `bed.side` target / legacy_targets, target, activity; additional incompatible action |
| S15 | PASS | Writing Desk gains Computer Desk capabilities / types |
| S16 | PASS | Initial lamp becomes Maple-movable / instances |
| S17 | PASS | Manifest geometry versions disagree / art, type; additional missing manifest and unknown type |

The corpus is `backend/tests/world/validation_corpus.py`, built afresh from release readers and accepted art metadata. There is no persisted invalid production document, new random dependency, modified canonical JSON or changed Oracle table.

### Property and regression integration

New suites contain **168 cases**:49 aggregate/corpus cases and119 cross-module properties. Seed143+case selects64 route pairs; each verifies start/end, every four-direction step, walkability, repeatability and pixel continuity immediately before/at every step boundary. Existing independent shortest-path reference and exact tie-break tests remain unchanged.26 row cases cover all1144 recovery sources, retaining valid positions and returning only the open component; explicit empty-mask fallback failure is bounded. Closed targets have no route. Eight activity cases inspect candidates from8 supplied positions each, required capabilities, repeated selection and valid destinations. Twelve slot cases check actual placement permission/results, deterministic validation, declared sharing and unchanged K1–K4 mask. Eight projection cases cover all candidate destinations from three Hall origins, exact317ms/step departure/arrival relationships and presentation identity. Existing400 provider-pair timing cases,40 collapsed-anchor rejection pairs, ambiguous mid-edge rejection and independent T7 expectations remain authoritative and run in regression.

The initial full run exposed the old resolver guard's blanket prohibition on imports from any other module (3841 PASS,1 FAIL,21 SKIPPED). It is narrowly updated to permit the aggregate pure library, as is the projection guard. The no-object-type-dispatch assertions are unchanged. The projection guard additionally rejects imports of the aggregate validator from every other shipped Python module, preserving the no-production-caller boundary. Both guards pass; the final full rerun is recorded below. Oracle/Harness pins and expectations are unchanged.

### Art integration and production isolation

The Python corpus extracts25 geometry records directly from accepted `art/export/**/*.meta.json`; core receives only frozen records. S17 compares catalog art IDs, versions and all declared orientations. Structural marker types without art remain accepted. The existing JavaScript pipeline retains the sole source of truth for full frame/anchor/source/palette/LFS/atlas/bundle rules. Fresh69 asset/bundle tests and the production build pass; two deterministic atlas builds and the golden Windows PNG/metadata/index comparisons pass.193 frames, two pages; static1,572,864 bytes, runtime allowance4,194,304, resident upper bound5,767,168. Raw source files0 and productionPreview=false.

| Accepted output | Fresh matching SHA256 |
|---|---|
| character PNG | `630070036d3fdc838d782d6f7be8ced0f309ce864b6705110fc5cbba5154e669` |
| character metadata | `8776fdc50db20fd91246c05cef63c306c32af1a75129b44d0d043860e66ee6ee` |
| shared PNG | `ec634d545d1af7dc4a1c53fe6c92462f4da820b0ff4cefc5b2c30077c36f77a3` |
| shared metadata | `1b50a5a357501708bf5fc90cec4da8c994ae47aaa24d61c1ce2ca9bb4c708192` |
| generated index | `5ee8f05364b6a9f42c1a75d4ee2b2b219dbc5648d636413241115491a060e833` |

No frontend source/assets, backend API/SSE, Origin/CSP, storage/migrations, Director, legacy business behavior or Room default changes. No production or paolo-core access. R1A-15 browser evidence is historical; no new browser run is claimed in this backend validation workstream. Fresh frontend tests/build cover coexistence and production bundle exclusion.

### Reproducible cost measurements

Windows11 build26200, Intel Core i5-12400F, CPython3.12.10, Node24.20.0, pnpm12.3.4, uv0.13.0.44×26 house:1144 cells,8 regions,7 doors,28 instances,15 types,17 points,12 slots,25 art records; canonical walkable431 cells/one component and34 blocking cells are retained by existing exact regressions. Benchmark excludes resource loading and performs20 measured repetitions per candidate after an untimed validation. Every result equals its initial ordered result.

| Candidate | Errors | Min / median / max ms | Ordered repeats |
|---|---:|---|---|
| Canonical valid | 0 | 83.255 / 86.083 / 87.879 | 20/20 PASS |
| Invalid S10 | 1 | 23.877 / 24.284 / 26.589 | 20/20 PASS |
| Combined S1/S15/S17 | 16 | 0.050 / 0.051 / 0.056 | 20/20 PASS |

The faster multi-error case skips dependent work after the failed grid prerequisite; it is not an optimization claim. Searches are iterative and grid-bounded; no recursion, network, clock or randomness in core. This is representative local cost evidence, **not R1A-19 acceptance**.

Reproduce from `backend`:

```text
uv run pytest tests/world/test_layout_validation.py tests/world/test_validation_properties.py
uv run python -m tests.world.validation_benchmark
uv run python -m tests.api.world_contract_export
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run mypy --platform linux
uv run lint-imports
```

From `frontend`: `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`. Locked dependency installation changed no manifest/lockfile. Full tests use synthetic scratch data only.

### Local validation results

Fresh final affected batch: **802 PASS in9.83s**, covering both new suites, world purity/import contract tests and legacy projection; contract OpenAPI/TypeScript/five fixture exports reproduce exactly. Backend Ruff lint/format, strict Windows-target mypy233 files and all10 import contracts pass. Frontend **586 PASS in25 files**, **69 asset/bundle PASS**, ESLint, TypeScript and production build PASS. Final full Windows backend: **3842 PASS,21 SKIPPED in130.77s**. Skips:18 Bash-unavailable deployment cases,1 POSIX/non-root permission case,2 Windows file-symlink privilege cases. No tests were altered to remove skips. Final uv-driven Ruff lint/format (235 files), strict Linux-target mypy (233 files) and10 import contracts PASS; strict Windows-target mypy (233 files) also PASS. Deploy Python Ruff lint/format7 files PASS. Existing simulation, exact Oracle/Harness, catalog/geometry, synthetic v11 rehearsal, API/security, pathfinding/recovery/capability/placement/projection regressions all pass without pin changes. Ignored logs: `var/r1a16-backend.log`, `var/r1a16-backend-initial.log`, `var/r1a16-frontend.log`. Native Ubuntu/CI and full release/ShellCheck gate are not claimed.

### Exact final manifest (13 files)

```text
CLAUDE.md
backend/src/maplegotchi/core/world/layout_validation.py
backend/tests/world/test_layout_validation.py
backend/tests/world/test_validation_properties.py
backend/tests/world/validation_corpus.py
backend/tests/world/validation_benchmark.py
backend/tests/world/test_legacy_projection.py
backend/tests/world/test_resolution.py
docs/architecture.md
docs/implementation/maple-room-r1a-16-validators-property-tests.md
docs/implementation/maple-room-r1a-plan.md
docs/implementation/maple-room-r1a-checklist.md
docs/implementation/maple-room-r1a-worklog.md
```

### Limitations and acceptance boundary

Native Ubuntu execution and Windows/Ubuntu GitHub CI are deferred to separately authorized integration; Linux-target mypy is not Linux execution. Expected Windows Bash/POSIX/symlink skips remain explicit. The new API accepts immutable domain inputs, not arbitrary JSON; future R4 parsing/auth/UI remains deferred. Existing fail-fast dependencies mean aggregate errors are not exhaustive after prerequisite failure, and builder locations can identify a whole section. Full art validation is composed through the existing suite rather than recreated in Python. Legacy collapsed-anchor/mid-edge limitations remain accepted rejection policy. R1A-17/18/19/20, real-device/performance/soak, final art/defaults and B14 are unclaimed. Owner acceptance and confirmed merge are required before R1A-16 becomes DONE. No commit, push, PR, merge, deployment or production access in this batch.


Final status: **PASS / READY FOR OWNER ACCEPTANCE**. R1A-15 DONE / MERGED; R1A-16 REVIEW, not DONE. Counters15 DONE/1 REVIEW/4 TODO=75%;16 DONE/4 TODO=80% only after future owner acceptance and confirmed merge. No publication or production activity occurred. Final audit PASS: exact13-file manifest,91 local documentation link targets,15 DONE/1 REVIEW/4 TODO counters,LF endings for changed source/docs,empty staging and unchanged branch HEAD. The worklog preserves the exact136,873-byte baseline prefix. Main and R1A-15 checkouts remain clean;art/frontend/deploy/dependency inputs and all baseline pins are unchanged. `git diff --check` PASS. No generated/log files are tracked.


## STEP 144 — Owner acceptance and GitHub integration — 2026-10-12 (+07)

Owner accepts STEP 143 implementation/evidence. Status: **REVIEW / OWNER ACCEPTED / MERGE PENDING**. Existing feature worktree/branch and baseline retained. Final changed-file, architecture and security review found only the intended 13 paths listed above. The only implementation-review correction was replacing a garbled dash in the validator module docstring with ASCII `S1-S17`; no runtime behavior or test expectation changed.

Fresh precommit Windows checks: **3842 backend PASS, 21 SKIPPED in 135.76s**; skips remain 18 Bash unavailable, 1 POSIX/non-root permissions and 2 Windows file-symlink privilege cases. Ruff check and format (235 files), strict mypy (233 files), all ten import contracts and exact OpenAPI/TypeScript/five-fixture exports PASS. Frontend ESLint, TypeScript, **586 tests in 25 files**, **69 asset/bundle tests**, production build and production-preview/raw-art exclusion guards PASS. Native Windows 193-frame/two-page atlas PNG, metadata and generated-index SHA256 values match every accepted reference in the table above. Ignored fresh logs: `var/r1a16-step144-backend.log`, `var/r1a16-step144-frontend.log`.

Full backend regressions freshly include the 49 aggregate/corpus and 119 property cases: all S1–S17 positives and named negatives, numeric/deduplicated error ordering, seed-143 permutations/reversed inputs, 64 routes, all 1144 recovery sources, activities/slots and truthful projection. Existing Oracle/Harness and simulation pins remain unchanged. No production caller imports the aggregate; no geometry/art metadata, dependencies, frontend logic, API/SSE, Director, security, schema or Legacy-default changes. The existing R1A-14 pipeline stays authoritative. `validate_layout(LayoutCandidate) -> ValidationResult` remains pure, immutable and deterministic for future R4 reuse.

The 20-repeat medians **86.083 / 24.284 / 0.051 ms** remain historical STEP 143 measurements with the environment/methodology above; not rerun or represented as R1A-19 acceptance. Prior STEP 140B browser QA also remains historical. Typed-domain input and prerequisite-dependent aggregation limits remain unchanged.

This entry records the reviewed precommit state. Commit, normal push, PR into `v0.2-development` and CI inspection are authorized next. Native Ubuntu, Windows CI, ShellCheck and additional PR checks must complete before merge readiness can be claimed; their actual results will be recorded in the PR and final integration report. Full deployment/release acceptance is unclaimed. No merge, deployment, production access, paolo-core changes, schema-v11 activation, B14 approval or later workstream is authorized. Counters remain **15 DONE / 1 REVIEW / 4 TODO = 75%**; intended after confirmed merge **16 DONE / 4 TODO = 80%**.


STEP 144 final precommit integrity audit PASS: exact13 reviewed paths,93 local documentation links,15 DONE/1 REVIEW/4 TODO counters,LF source/docs and git diff --check. Complete140,854-byte pre-STEP144 worklog prefix and136,873-byte baseline prefix preserved. Main and R1A-15 checkouts remain clean at their original SHAs;staging empty before explicit staging. No generated/log/temp files or unrelated changes included.
