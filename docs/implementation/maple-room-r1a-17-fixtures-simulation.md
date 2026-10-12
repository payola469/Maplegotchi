# R1A-17 — Fixtures and simulation coverage

## Design recorded before major implementation — STEP 146, 2026-10-12

Verified integration baseline: `50ec74865cee9c65ed566251476df7bbeed2dbd2`, R1A-16 PR #17 merge. Clean Windows main fetched and fast-forwarded only. Worktree `C:/GitHub/Maplegotchi-worktrees/r1a-17-fixtures-simulation`, branch `codex/r1a-17-fixtures-simulation`. R1A-15/16 and unrelated worktrees/branches preserved; no Mac-only commit imported/reconstructed or baseline branch repaired. Authorization is local implementation/tests/docs only; no commit, push, PR, merge, deployment or production access.

### Inventory, source boundaries and gaps

The original pure `core/simulation.py` drives fake-time legacy heartbeats; its 30-day pin remains `458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917`. R1A-05 `tests/world/pathfinding_tuning.py` supplies the independent T6 routes and eight speed/penalty combinations. R1A-16 `canonical_candidate()` reads the accepted release house/catalog and art metadata without duplicating geometry. Oracle T1–T7 is independently approved and remains unchanged. R1A-10 supplies four typed synthetic world states and five exact JSON/type/OpenAPI exports. R1A-08 supplies disposable, registered v10 lives and test-only rehearsal; no path input is accepted. R1A-11–15 already cover renderer/camera/lighting/atlas/coexistence. Missing: one complete grid-world schedule/trace, explicit A–N scenario mapping, long-run digest, richer offline renderer states and consolidated timing analysis.

### Deterministic simulation design

All new Python implementation lives under `backend/tests`, outside the wheel and production imports. Reuse accepted loaders, validator, resolver, A*, Travel, recovery, placement and Legacy projection. A supplied repeating activity schedule (all eight activities, including distant sleep/observe/rest/write transitions) is coverage input, not an AI policy. Minimum activity durations come from existing SPECS. Integer logical milliseconds advance at every route tile and activity completion. Check before-arrival interpolation, exact activity start, legal capability/target, four-neighbor steps, open-room access and bounded transitions. No path cache, generic framework, threads, network or uncontrolled randomness. Seed/version are explicit; resolver decision counters advance deliberately.

Long-run target: at least 30 logical days using complete schedule cycles, consistent with the existing legacy simulation convention; report exact actual duration and event count. Never truncate an active walk. Every valid run must complete with zero failures, unresolvable loops, stuck transitions or unexpected recovery. Exceptional starting-position recovery is explicit and separately counted; invalid layouts must reject before any simulated movement.

### Synthetic scenario matrix (planned)

A canonical valid house; B a permitted noncritical tile blocked by a test-only object move; C protected Hall corridor obstruction; D closed-door target unavailable; E test-only Future Space region AND its door opened together (door-only opening into a closed region still rejects); F last required provider removed; G required approach blocked/unreachable with explicit rejection/no_candidate; H invalid Maple starting tile; I deterministic recorded emergency recovery, then validation and walking; J proposed protected-path obstruction rejected by placement safety; K authorized display placement preserving connectivity; L repeated distant activity transitions; M typed renderer/API snapshots; N generated disposable v10 rehearsal and corrupt-source rejection. Canonical release data/closed-room policy is never modified. Per-case actual codes/results and reproduction commands will be recorded after implementation.

### Digest and trace review

New scenario version `r1a17-grid-v1`, seed 146, integer logical time, ordered events and canonical UTF-8 JSON (sorted keys, compact separators, LF). No wall-clock timestamps, OS paths, environment data, floats or nondeterministic identifiers enter the digest. Review the initial trace, route continuity and counters before pinning SHA256; repeat at least three times and compare full bytes. A short smoke trace and long run use the same engine. Performance/memory observations are outside digest and explicitly not R1A-19 acceptance. Existing legacy and R1A-05 digest pins remain untouched.

### Timing and renderer evidence

Reuse all 49 T6 directed trips at 250/300 ms per step and penalties 0/1/2/4; penalty is path cost, not extra elapsed turn time. Report steps, turns, travel duration, destination duration and walking share of the complete cycle, plus short/medium/long/max and repeated-turn examples. Retain configured provisional 250/1; no new canonical parameter or production timing change. Any proposal to change locked semantics requires owner decision.

Renderer snapshots reuse WorldOut and accepted release geometry: initial state, distant travel/interior edge, arrival/activity, all four lighting phases, camera target through actor position, closed doors and recovered state. Envelopes explicitly label development_fixture/simulation and cannot be served as live data. Offline JSON uses existing DTO validation; no endpoint, activation or frontend import changes. Existing R1A-10 fixture exports stay byte-identical. Scripted snapshots support later R1A-19 measurements without implementing performance acceptance.

### Reproduction, cross-platform and safety gates

Use Python3.12 and existing uv-locked dependencies. Tests are pytest-discovered by existing Ubuntu/Windows CI; no workflow redesign. Explicit UTF-8/LF, sorted iteration, integer serialization and supplied UTC base time prevent locale/path/clock differences. Native Ubuntu execution is deferred to separately authorized GitHub Integration; Linux-target mypy does not prove Linux execution.

Run full backend pytest, Ruff lint/format, strict mypy, ten import contracts, original/new digest assertions, R1A-16/Oracle/rehearsal/security regressions and exact contract exports. Frontend lint/typecheck/test/assets/build and accepted atlas golden hashes must pass. Audit doc links, counters, exact append-only worklog prefix, manifest and diff whitespace; main/unrelated worktrees remain clean. Final evidence must give actual new totals and categorized Windows skips. Browser QA is historical unless actually rerun; no production/hardware/soak claim.

Status starts **IN PROGRESS**. R1A-01–16 verified merged; R1A-18–20 TODO. After local validation: R1A-17 REVIEW / pending owner acceptance, 16 DONE / 1 REVIEW / 3 TODO = 80%; after eventual accepted merge 17/20 = 85%. No schema-v11 production activation, production database access, Director policy change, API/SSE/security/default-room change, art/geometry edits, B14/R1b approval or later-workstream implementation.

## Implementation and reviewed results — STEP 146

Status: **REVIEW / pending owner acceptance**, local work only. Current counters are **16 DONE / 1 REVIEW / 3 TODO = 80%**. R1A-01–16 are merged at the verified baseline; R1A-18–20 remain TODO. R1A-17 is not DONE; eventual owner acceptance and confirmed merge would make 17/20 = 85%. STEP 144 status blocks in historical evidence/worklog are historical, not current publication permission.

### Actual A–N matrix

All candidates derive from `tests.world.validation_corpus.canonical_candidate()`. `test_scenarios.py` asserts repeated construction and validation equality without mutation for every A–N case. Run from `backend`: `uv run pytest tests/grid_world/test_scenarios.py -q` (32 tests). For L run `test_simulation.py`; for M run `test_renderer.py`. Full pytest discovers all automatically.

| Case | Actual input | Validator result | Engine/error/recovery assertion |
|---|---|---|---|
| A | Accepted initial house, Maple Hall (21,15) | Valid | 44×26; 8 regions/7 doors; 5 open/3 closed; 431 walkable cells in one component; 15 types/28 instances/17 points/12 slots/8 lighting zones. Independent Oracle region/point/slot equality and all existing T1–T7 tests retained. |
| B | Move existing lamp from (14,5) to noncritical bedroom (5,6) | Valid | Old tile becomes free; count stays 431. (5,7)→(5,5) detours beyond two steps; eight activities complete. |
| C | Lamp obstructs protected Hall corridor (3,14) | S10 | Simulation rejects `invalid_layout` before movement. |
| D | Canonical Future Space/door closed | Valid | Hall→(6,20) gives `no_destination`; recovery from closed door (6,18) returns Hall. |
| E | Test-only Future Space region AND its door opened | Valid | 502 walkable cells; route passes (6,18). System Room stays inaccessible; subsequent canonical load remains 431. Door-only opening into closed region remains rejected by existing S5 regressions. |
| F | Remove last bed provider | S9 | Sleep resolution gives `no_candidate`; simulation rejects layout. |
| G | Move lamp onto bed approach (3,4) | S8, S10 | Sleep resolution gives `no_candidate`; simulation rejects layout. |
| H | Maple starts inside closed region (1,20) | S13 | Explicit bounded layout rejection, no attempt to force success. |
| I | Valid candidate plus exceptional supplied positions (1,20), (1,3), (-1,0) | Valid after explicit recovery | Repeated recovery results equal and destinations walkable; `maple_relocated` recorded first, exactly one recovery, eight activities complete. Does not bypass H's validator. |
| J | Proposed layout obstructs protected path | S10 | Existing placement validator returns `INVALID_LAYOUT`; no placement action or simulation occurs. |
| K | Maple-owned synthetic creation into permitted bedside top slot | Valid | Existing placement permission, route and active-placement checks pass; walkability/component unchanged. |
| L | Repeating all-eight-activity schedule, 270 complete cycles | Valid | Full per-step trace, bounded completion, three full-byte repeats, independent trace audit and new pin. |
| M | Ten synthetic world/Legacy presentation snapshots | Valid | Typed DTO envelope validation; exact generated JSON; source label, pose/follow target, arrival/time phases, closed-door failure and recorded recovery tested. |
| N | Six generated v10 lives, twice each; corrupt application ID | Valid world | Source capture/conversion digest/tile repeat exactly. Rehearsal reaches v11 only in owned temporary lives; integrity OK. Corrupt input raises MigrationError before conversion; runtime registry stays v10. |

Initial new-test setup issues were corrected without changing engine/oracle: B initially expected an extra blocked cell despite the vacated lamp tile; walking rehearsal input initially paired observe_server with an incompatible location. Renderer test construction now uses the accepted pose enum. No accepted expected hash was changed to manufacture PASS.

### Simulation architecture and invariants

Nine test-only Python files under `backend/tests/grid_world/` contain candidate adapters, simulation, offline renderer export, report CLI and tests. The wheel still contains only `src/maplegotchi`. There are no production callers/imports. Activity coverage order is sleep → observe_server → rest → write → read → think → walk → idle; existing SPECS minimum durations total 160 minutes per cycle. The schedule is supplied coverage input, not a new autonomous policy, physiology model or production Director.

Each decision reuses accepted seeded resolution and advances its draw counter. Reused A*/Travel advances every unit step at 250 logical ms, checks four-neighbor continuity, walkability, closed-region exclusion, route length bound and pre-boundary interpolation. Arrival precedes exact activity start and minimum-duration completion. Provider capability and target approach are checked; Legacy projection reuses existing facts and rejects unsupported mappings explicitly. Valid long-run mappings have zero rejection. Placement checks are in K/J and the existing suite; the simulator itself does not invent placement actions.

An independent complete-trace audit checks event order, monotonic exact times, unit steps, declared step counts, no within-route tile loops, target positions, minimum activity durations and final counters. Explicit abnormal-start recovery is outside invalid-layout acceptance. Bounded cycle/route loops and completion assertions fail immediately if stuck; negative cases are excluded from valid-run totals. No real-state writes, network, threads, wall-clock or uncontrolled random input occur in `simulate`.

### New digest and long-run evidence

Version **r1a17-grid-v1**, seed **146**, supplied UTC epoch **2026-10-12T00:00:00Z**, 270 cycles. Events use integers and immutable ordered tuples; canonical serialization is sorted-key compact UTF-8 JSON, ASCII escapes, `allow_nan=False`, one LF. OS paths/platform/memory/timing are report metadata only.

The first full trace was independently inspected before pinning: legal state machine, every step/timestamp, all activities/providers, counts and final state. The reviewed trace is 9,838,654 bytes; only its digest and deterministic generator are tracked, avoiding a large redundant trace artifact.

- **New SHA256:** `b3287b3d13ed406fc98ecc5be58494e9f3ac9df7fc4b0a70cedb6e85ad5500d3`.
- Three complete runs compared **bit for bit**, including the complete event bytes, not just equal hashes; pinned tests repeat the long run three times again.
- Logical duration **2,608,335,000 ms = 30 days 4 h 32 min 15 s**. This matches the historical ≥30-day convention and ends after a full cycle, without truncating travel.
- **2,160 transitions / 2,160 successful activities**, 270 of each activity; **65,340 movement steps**, maximum route **53 steps**.
- **71,821 events** = initial 1 + selected 2,160 + arrived 2,160 + completed 2,160 + step 65,340.
- Valid-run failures, invalid-action rejections, unresolvable loops, stuck transitions, unexpected recoveries and Legacy projection rejections: **zero**. Recovery count **0**. Final state **idle, Hall (21,15)**.
- Unprofiled CLI runs including serialization: **16.4952601 / 17.1419213 / 17.1422372 seconds**, median **17.1419213 seconds**. A separate final-fixture run took **16.5994785 seconds**.
- A separate identical run measured with `tracemalloc` peaked at **57,741,883 bytes** of Python allocations. This includes trace serialization, is not process RSS/GPU memory, and is not an R1A-19 performance budget or soak claim.
- Original R1A-01 30-day digest preserved: `458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917`.
- Original R1A-05 timing digest preserved: `722a4e5359852fa4c049a985210e6a8f07a663df86bdf6c4a0a8218e8c51c936`.

Reports and raw audit trace are ignored local evidence under `var/`; the tests and this document retain reproducible evidence. Reproduce from `backend` with `uv run python -m tests.grid_world.report --repeat 3`; append `--memory` for an additional instrumented run. Measurements vary with machine/load and do not enter the pin.

### Timing and recommendation

All 49 independent T6 directed trips are checked for each candidate; **zero T6 step differences in all eight combinations**. Separate enumeration of all 17 canonical provider approaches (289 ordered pairs) found maximum route length 53 steps as well. Existing path cost applies penalty per turn; it does not add elapsed turn time.

| ms/step | Penalty | Sum of turns, 49 trips | Max walk ms | Max walking share, complete cycle |
|---|---|---|---|---|
| 250 | 0 | 166 | 13,250 | 4.2298% |
| 250 | 1 | 130 | 13,250 | 4.2298% |
| 250 | 2 | 130 | 13,250 | 4.2298% |
| 250 | 4 | 130 | 13,250 | 4.2298% |
| 300 | 0 | 166 | 15,900 | 5.0332% |
| 300 | 1 | 130 | 15,900 | 5.0332% |
| 300 | 2 | 130 | 15,900 | 5.0332% |
| 300 | 4 | 130 | 15,900 | 5.0332% |

At provisional 250/1:

| Trip | Steps | Turns | Movement ms | Destination minimum ms | Walking share |
|---|---|---|---|---|---|
| write → observe | 5 | 0 | 1,250 | 300,000 | 0.4149% |
| idle → rest | 18 | 2 | 4,500 | 900,000 | 0.4975% |
| sleep → write | 52 | 4 | 13,000 | 900,000 | 1.4239% |
| sleep → observe | 53 | 4 | 13,250 | 300,000 | 4.2298% |

Shares use `movement / (movement + destination minimum activity)`, not the historical R1A-05 travel/activity ratio. CLI emits integer basis points rounded down (422/503 maximum). Largest turn count is four; sleep→rest is a representative 31-step/four-turn trip. The schedule also exercises read/think and idle arrivals repeatedly.

**Recommendation: retain provisional 250 ms/step and penalty 1.** Penalty 1 reduces unnecessary turns without extra steps; 2/4 add no benefit in this corpus, and 300 increases travel share. No default changed and no new parameter is locked. No owner architectural decision is required for these local fixtures; later locking/cutover remains separately authorized.

### Offline renderer/API contract

[Scripted Room states](../fixtures/maple-room/r1a-17/scripted-room-states.json) contains ten deterministic frames: initial, distant departure, interior edge at 125 ms, arrival at 13,250 ms, active observation, night/morning/afternoon/evening, recovered. Every frame is validated through the existing full WorldOut envelope/WorldSnapshotOut contract, with accepted catalog/geometry, position/facing/pose, exact camera-follow coordinates and truthful Legacy projection/timing. Closed-door attempt and `maple_relocated` event are explicit supplemental records.

Labels: source `development_fixture`, visible label `SIMULATION - synthetic R1A-17 fixture; not live Maple`. Cases are independent; only the explicit `travel_sequence` should be interpolated as one sequence. No independent phase/recovery case should be interpreted as a teleport from its neighbor. JSON SHA256 **1a5c843a2260c82a58a6345c287e2ccdd030192afad548e28dea08a8c7884f42**. Recreate deliberately with `uv run python -m tests.grid_world.report --repeat 1 --write-fixtures`, then review the diff; exact-byte export tests fail on drift.

This is offline test/evidence data, not a frontend import, live endpoint or production enablement. The five existing R1A-10 JSON/type/OpenAPI exports remain unchanged and regression-tested. Existing Legacy Pixi lifecycle and feature gates are unchanged. No new browser session was run for STEP 146; earlier DPR/renderer browser QA is historical. Current frontend camera/lighting/atlas/coexistence automated regressions were freshly run.

### Cross-platform preparation and limits

Windows 11 build 26200, Python **3.12.10**, uv **0.13.0**, Node **24.20.0**, pnpm **12.3.4**. Existing locked dependencies only. Tests are in existing pytest-discovered paths; workflow architecture is unchanged. Explicit UTF-8/LF, sorted events, integer times, fixed UTC input and seeded accepted RNG avoid path/locale/clock/float instability. Temporary persistence paths do not enter captures/digests.

Native **Ubuntu execution and GitHub Integration remain pending separate owner authorization**. Linux-target static typing, if reported, is not execution proof. No R1A-18 workflow/atlas work, R1A-19 budgets/real-device/GPU/soak acceptance, production-copy migration, schema-v11 activation, R1b or B14 approval is claimed. Synthetic coverage cannot establish production soak. Legacy projection retains accepted unmappable/collapsed-route limitations. No new owner decision is needed before reviewing this local result.

### Fresh final local validation

All results here were executed in STEP 146 after implementation, not copied from R1A-16:

| Gate | Actual result |
|---|---|
| Full Windows backend pytest | **3,896 PASS / 21 SKIPPED**, 219.10 s; baseline 3,842 + 54 new tests |
| New tests (included above) | 32 scenario + 9 simulation + 12 renderer + 1 timing = **54 PASS**, no new skips |
| R1A-16 / S1–S17 / T1–T7 / security regressions | PASS in full pytest; existing accepted tests/pins unchanged |
| Backend Ruff lint / format | PASS; 244 formatted files; deploy tools 7 formatted files PASS |
| Strict mypy | PASS, 242 files; Windows and Linux-target checks (Linux not executed) |
| Import contracts | **10 kept, 0 broken** |
| Exact existing contract exporter | OpenAPI, TypeScript and five fixture exports match |
| Frontend ESLint / TypeScript | PASS |
| Frontend tests | **586 PASS / 25 files** |
| Asset/bundle tests | **69 PASS**, no skips |
| Production frontend build | PASS; productionPreview=false, raw sources=0, two hashed atlas pages |
| Companion discord / brain | **22 / 28 PASS**; locked install, lint, format, strict typing PASS |
| ShellCheck | PASS, version 0.11.0; all existing check.sh script groups |

The 21 Windows skips are exactly **18 Bash-unavailable deployment integration cases**, **one POSIX permissions/non-root case**, and **two file-symlink privilege cases**. None is new R1A-17 simulation coverage. The commands from `scripts/check.sh` were executed using PowerShell and explicit uv paths; the Bash wrapper itself was not executed. Native Ubuntu CI is pending; ShellCheck is freshly executed locally.

Accepted atlas references remain exact (193 frames, two pages):

| Artifact | SHA256 |
|---|---|
| character PNG | `630070036d3fdc838d782d6f7be8ced0f309ce864b6705110fc5cbba5154e669` |
| character metadata | `8776fdc50db20fd91246c05cef63c306c32af1a75129b44d0d043860e66ee6ee` |
| shared PNG | `ec634d545d1af7dc4a1c53fe6c92462f4da820b0ff4cefc5b2c30077c36f77a3` |
| shared metadata | `1b50a5a357501708bf5fc90cec4da8c994ae47aaa24d61c1ce2ca9bb4c708192` |
| atlas index | `5ee8f05364b6a9f42c1a75d4ee2b2b219dbc5648d636413241115491a060e833` |

Static/runtime/resident texture bytes: 1,572,864 / 4,194,304 / 5,767,168. No art assets, metadata or geometry changed. Fresh production bundle inspection and automated guard tests exclude preview logic/raw sources; new offline fixture/version/state markers are absent from production JS, source maps, HTML and JSON. Query/direct activation rules remain unchanged, with existing production-isolation tests passing; no new browser run is claimed.

### Exact local changed-file manifest — 17 paths

All paths below are relative to the isolated worktree. Six existing documentation files modified; eleven new files. No shipped backend/frontend source, dependency/lock file, canonical geometry, Oracle, accepted digest pin, API export, art or workflow changed.

| Path | Purpose |
|---|---|
| `CLAUDE.md` | Current STEP 146 authorization/status pointer |
| `docs/architecture.md` | Current status and test-only simulation architecture |
| `docs/autonomy.md` | Timing findings, unchanged provisional recommendation |
| `docs/implementation/maple-room-r1a-plan.md` | Current merged/local-review status and evidence pointer |
| `docs/implementation/maple-room-r1a-checklist.md` | R1A-16 merged, R1A-17 REVIEW and counters |
| `docs/implementation/maple-room-r1a-worklog.md` | Append-only kickoff/results/integrity evidence |
| `docs/implementation/maple-room-r1a-17-fixtures-simulation.md` | Preimplementation design and final evidence |
| `docs/fixtures/maple-room/r1a-17/scripted-room-states.json` | Labelled, typed offline scripted renderer cases |
| `backend/tests/grid_world/__init__.py` | Test-only package |
| `backend/tests/grid_world/fixtures.py` | Accepted-data A–N candidate adapters |
| `backend/tests/grid_world/simulation.py` | Pure deterministic grid trace orchestration |
| `backend/tests/grid_world/renderer.py` | Existing DTO/Legacy fixture construction |
| `backend/tests/grid_world/report.py` | Reproduction, timing/memory report and explicit exporter |
| `backend/tests/grid_world/test_scenarios.py` | A–N validator/engine/rehearsal assertions |
| `backend/tests/grid_world/test_simulation.py` | Independent trace audit, reviewed pin, repeats |
| `backend/tests/grid_world/test_renderer.py` | Exact offline export and typed state assertions |
| `backend/tests/grid_world/test_timing.py` | All eight tuning candidates and cycle arithmetic |

No corrective production change was necessary. Only new test/fixture construction issues noted above were corrected. Main was fast-forwarded only to the owner-specified merge; all unrelated branches/worktrees, the accidentally advanced baseline branch and Mac-only history remain preserved. No commit, push, PR, merge, deployment, production access or paolo-core access occurred. **Ready for owner acceptance of local R1A-17; no GitHub Integration until separately authorized.**

### Final integrity audit

PASS: exact **17 changed paths**, **104 local Markdown links** resolve, all 17 changed files use LF, checklist summary/detailed state and counters agree. The complete **143,356-byte** pre-STEP146 worklog prefix remains byte-identical; its Git blob equals the baseline worklog blob (`8ddb050d404f95ecb5cf51ed831468e38a98f1e6`). Final whitespace audit PASS. One new package-marker file was normalized from CRLF to LF during this audit; it contains no executable behavior, and fresh lint/format checks passed afterward.

Main is clean at `50ec74865cee9c65ed566251476df7bbeed2dbd2`; R1A-15 is clean at `25efc8de46e14682ab869f016b1639c0860a2e2f`; R1A-16 is clean at `4d51ecb36c084b416e2148bdf94b4caa9080b8f0`. All pre-existing local branch heads match the initial inventory, including `codex/r1a-01-baseline` at `a85f226fb664056482baf8f27389870fce14fd45`. R1A-17 HEAD still equals its baseline and staging is empty. No unrelated or generated files are in the 17-path manifest. Local validation is complete; stop here for owner review.

## STEP 147 — owner acceptance and GitHub Integration

Owner accepts STEP 146 implementation/evidence and authorizes final review, fresh local checks, commit, normal feature-branch push, PR to `v0.2-development` and CI inspection. Current status **REVIEW / OWNER ACCEPTED / MERGE PENDING**, 16 DONE / 1 REVIEW / 3 TODO = 80%. This supersedes STEP 146's local-only publication restriction; earlier sections retain historical provenance. Merge/deployment/production access remain unauthorized.

Initial STEP 147 verification: retained existing worktree/branch at `50ec74865cee9c65ed566251476df7bbeed2dbd2`; fetched origin and confirmed integration branch unchanged at that exact SHA. Origin matches `https://github.com/payola469/Maplegotchi.git`. Main, R1A-15 and R1A-16 clean; unrelated heads preserved. Final review inspected all nine Python files, offline JSON construction/exact export and seven documentation paths. No production source, dependency, geometry, art, accepted pin, API/SSE/CSP or migration registry edits; no new autonomous policy or real database input. No implementation correction needed. Fresh local and native CI evidence follow; STEP 146 measurements above remain historical.

### STEP 147 fresh validation and precommit audit

Full Windows backend **3,896 PASS / 21 SKIPPED in 225.94s**, including all 54 R1A-17 tests, three complete long traces/full-byte equality, independent trace audit and both unchanged digest assertions. Oracle/S1–S17, R1A-08 rehearsal and all earlier backend/security regressions PASS. Skips remain 18 Bash-unavailable, one POSIX/non-root permission case, two Windows file-symlink privilege cases.

Fresh frontend **586 PASS / 25 files**, assets **69 PASS / no skips**; ESLint/TypeScript/build PASS. Atlas golden PNG/metadata/index hashes match STEP 146's accepted values; 193 frames/two pages. Production bundle guard: productionPreview=false, raw sources=0, hashed pages=2; offline fixture/version labels absent from JS/maps/HTML/JSON. No browser or physical-device revalidation performed.

Ruff lint/format PASS (244 backend files, seven deploy files); strict mypy PASS (242 files), ten import contracts kept, exact existing OpenAPI/TypeScript/five fixture exports match. Fresh ShellCheck PASS. Companion discord/brain 22/28 tests PASS with locked installs/lint/format/strict typing. PowerShell executed actual project commands; Bash wrapper was not run.

Separate fresh long-run measurement including serialization: **15.6649703s**, same 30d4h32m15s,2160 activities,65340 steps,71821 events,max53,zero recovery/projection rejection,final idle Hall(21,15),new pin unchanged. Three-repeat equality was executed inside full pytest; the extra measurement is one run. Memory was not remeasured in STEP 147; STEP 146's allocation figure remains historical.

Precommit integrity PASS: exact 17 Git-derived reviewed paths,105 resolving local Markdown links,LF throughout,16 DONE/1 REVIEW/3 TODO counters,git diff --check. Complete **147,573-byte pre-STEP147** and **143,356-byte baseline** worklog prefixes preserved byte for byte. No secrets/real DB/temp/generated files or machine paths in portable fixture. Main/R1A15/R1A16 remain clean; pre-existing branch heads unchanged; origin integration SHA still matches expected baseline. Only this reviewed manifest will be staged.

Native CI is pending PR creation. Existing workflow runs unfiltered `uv run pytest` on Ubuntu and Windows; the new `tests/grid_world/test_simulation.py` has nine cases, including `test_thirty_day_grid_digest_repeats_full_trace_three_times`. Actual per-job logs must confirm collection/execution and pin success before claiming cross-platform verification. Commit/remote SHA, PR identity and actual CI inspection will be reported in the PR/final integration report; no merge is authorized.
