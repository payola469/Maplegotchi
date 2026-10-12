# Maple Room R1a Checklist

**Live status of the R1a workstreams.** Plan: `maple-room-r1a-plan.md`. History: `maple-room-r1a-worklog.md`.

- **Starting baseline:** `v0.2-development` @ `5c6db41c0139e1da6a2178b36d838e4da57074b1` (original planning baseline: `dfd5972`).
- **R1a authorization:** R1A-01–17 DONE / OWNER ACCEPTED / MERGED; verified integration baseline `4dc0e095470bcb572aeaebccb7bfa8e624f9b2fe`. R1A-18 REVIEW / OWNER ACCEPTED / MERGE PENDING (STEP 150, 2026-10-12). Owner authorizes final review, fresh local checks, commit, normal feature-branch push, PR into `v0.2-development` and CI/artifact inspection. 17 DONE / 1 REVIEW / 2 TODO = 85%; R1A-19/20 TODO. No merge, deployment, production/paolo-core access, schema-v11 activation, Legacy default switch, R1b or B14 approval. Actual cross-platform CI evidence will be recorded in the PR and final integration report; earlier dated evidence remains historical. [R1A-18 evidence](maple-room-r1a-18-ci-linux-reproducibility.md).
- **This checklist was created by the planning framework.** The framework itself is **not** an R1A work item; creating these documents does not complete or start R1A-01.

## Pre-R1 Gate

Not an R1A work item. Source: plan §9; future-architecture §22 item 1. Last updated 2026-10-10.

| Gate item | Status | Notes |
|---|---|---|
| Stage C authorization | **RESOLVED** | 2026-10-09: install of `160ed4f…` retroactively authorized; Stage C stays open; M3 not claimed |
| Phase 8 status | **RESOLVED** | 2026-10-09: not authorized, not started, deferred until Stage C is closed; blocks neither R1a nor R1b |
| Boundary probe (OD-01) | **RESOLVED** | **PASS / CLOSED**, recorded 2026-10-10 from owner-supplied production evidence; worklog contains results and limitations |
| Restore test (OD-01) | **RESOLVED** | **PASS / CLOSED**, recorded 2026-10-10: owner-executed isolated restic restore; restored `maple.db` opens and passes `integrity_check`; evidence and limitations in worklog |
| R-01 | **RESOLVED** | **PASS / CLOSED**; repository acceptance recorded; owner confirms production deployment completed and HTTP Health PASS (2026-10-10). Exact deployed SHA / detailed acceptance transcript not supplied |
| Pre-R1 Gate clearance | **RESOLVED** | **APPROVED / CLEAR** by explicit owner decision, 2026-10-10; does not imply release-gate/CI PASS |
| R1a authorization | **RESOLVED** | **AUTHORIZED** by owner, 2026-10-10; R1A-01 baseline/test infrastructure only |

Gate statuses: OPEN · RESOLVED · BLOCKED. They are separate from the item statuses below.

## Counters

| Total | TODO | IN PROGRESS | BLOCKED | REVIEW | DONE | DEFERRED |
|---|---|---|---|---|---|---|
| 20 | 2 | 0 | 0 | 1 | 17 | 0 |

## Status vocabulary (only these values)

| Status | Meaning |
|---|---|
| **TODO** | Not started. |
| **IN PROGRESS** | Detailed task plan written; implementation under way on the recorded branch. |
| **BLOCKED** | Cannot proceed. Must state the blocking dependency or decision. |
| **REVIEW** | Implementation complete; acceptance/review or repository integration pending. OWNER ACCEPTED / MERGE PENDING is a REVIEW substate until merge. |
| **DONE** | Completion criteria met, evidence recorded, reviewed and merged. |
| **DEFERRED** | Moved out of R1a. Must state the explicit destination phase or gate. |

## Mandatory rules

1. Status changes are committed **with** the implementation or change that caused them.
2. No item may be marked **DONE** without evidence (tests, measurements or review records named in "Evidence / tests").
3. **REVIEW** means implementation is complete but acceptance evidence, review or repository integration is still pending. Owner acceptance alone does not mean merged or DONE.
4. **BLOCKED** must state the blocking dependency.
5. **DEFERRED** requires an explicit destination phase or gate.
6. The checklist must match **repository truth, not intention**.
7. Every change follows the documentation policy (plan §8): plan → implement → test → evidence → checklist → worklog → docs → review → commit. An architecture conflict triggers the stop rule (plan §8): the item becomes BLOCKED until the owner accepts the new decision.
8. Update the counters in the same commit as any status change.

## Summary

| ID | Title | Status | Dependencies (start) | Last updated |
|---|---|---|---|---|
| R1A-01 | Baseline and test harness | DONE / OWNER ACCEPTED / MERGED | Pre-R1 Gate closed + owner authorization of R1a | 2026-10-10 |
| R1A-02 | Canonical world model and final house geometry | DONE / OWNER ACCEPTED / MERGED | 01 (DONE) | 2026-10-11 |
| R1A-03 | Object catalog and capability metadata | DONE / OWNER ACCEPTED / MERGED | 02 | 2026-10-11 |
| R1A-04 | Walkability, collision and recovery | DONE / OWNER ACCEPTED / MERGED | 02, 03 (merged) | 2026-10-11 |
| R1A-05 | Deterministic A* pathfinding | DONE / OWNER ACCEPTED / MERGED | 04 (merged); bounded 17 tuning evidence recorded | 2026-10-11 |
| R1A-06 | Interaction and capability resolution | DONE / OWNER ACCEPTED / MERGED | 03, 05 (merged) | 2026-10-11 |
| R1A-07 | Placement slots and Storage hooks | DONE / OWNER ACCEPTED / MERGED | 03, 04, 05 (merged) | 2026-10-11 |
| R1A-08 | Persistence model / schema-v11 preparation | DONE / OWNER ACCEPTED / MERGED | 02, 03, 05, 07 (merged) | 2026-10-11 |
| R1A-09 | Legacy projection compatibility | DONE / OWNER ACCEPTED / MERGED | 05, 06 (merged) | 2026-10-11 |
| R1A-10 | New Room backend/API contracts | DONE / OWNER ACCEPTED / MERGED | 02, 06, 07, 08, 09 (merged) | 2026-10-11 |
| R1A-11 | Pixi renderer shell | DONE / OWNER ACCEPTED / MERGED | 02 + 10 + 14 merged; atlas dependency resolved | 2026-10-11 |
| R1A-12 | Camera, zoom and DPR behavior | DONE / OWNER ACCEPTED / MERGED | 11 (merged) | 2026-10-11 |
| R1A-13 | Lighting zones and emitter hooks | DONE / OWNER ACCEPTED / MERGED | 02/11/12/14 merged | 2026-10-12 |
| R1A-14 | Asset pipeline and atlas integration | DONE / OWNER ACCEPTED / MERGED | 01, 03, 11 shell merged; native Windows PASS | 2026-10-11 |
| R1A-15 | Feature flag and old/new Room coexistence | DONE / OWNER ACCEPTED / MERGED | 10–14 merged | 2026-10-12 |
| R1A-16 | Validators and property tests | DONE / OWNER ACCEPTED / MERGED | 01–15 merged | 2026-10-12 |
| R1A-17 | Fixtures and simulation coverage | DONE / OWNER ACCEPTED / MERGED | 01–16 merged | 2026-10-12 |
| R1A-18 | CI and Linux reproducibility | REVIEW / OWNER ACCEPTED / MERGE PENDING | 01–17 merged | 2026-10-12 |
| R1A-19 | Performance and soak validation | TODO | 14, 15, 17 | 2026-10-09 |
| R1A-20 | R1a Acceptance Gate | TODO | 01-19 | 2026-10-09 |

## Items

### R1A-01 — Baseline and test harness

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** Pre-R1 Gate closed + owner authorization of R1a
- **Branch:** `codex/r1a-01-baseline`
- **Start commit:** `5c6db41c0139e1da6a2178b36d838e4da57074b1`
- **End commit:** `a754efc9cd35f66e15efb8707dc9b4066d5ab54d` (PR #1 merge into `v0.2-development`)
- **Evidence / tests:** Approved base `5c6db41c0139e1da6a2178b36d838e4da57074b1`; previously verified isolated Docker release gate PASS and baseline counts retained. Owner-verified 30-day simulation: 8,640 ticks; computed digest `458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917`. PR HEAD `26aed831b82eebf2db8e73ff9b04f60a436b9a38`: [GitHub Actions run 38062574000](https://github.com/payola469/Maplegotchi/actions/runs/38062574000), Backend Ubuntu / Backend Windows / Frontend / ShellCheck PASS. PR-head CI is not separate original-base CI evidence.
- **Notes:** Oracle/Harness: 48 new focused tests passed; 635 cells and 49 walk values; 10 import contracts kept / 0 broken. Owner explicitly APPROVES R1A-01 acceptance on 2026-10-10, acknowledging that run `38062574000` validates PR HEAD `26aed831b82eebf2db8e73ff9b04f60a436b9a38`, not a separate CI run on base `5c6db41c0139e1da6a2178b36d838e4da57074b1`, and complete raw baseline Docker gate details are unavailable. PR #1 merged into `v0.2-development` at `a754efc9cd35f66e15efb8707dc9b4066d5ab54d`; R1A-01 repository integration is complete. R1A-01 introduced no World Model or Engine behavior. Current R1A-02 status is recorded below.
- **Last updated:** 2026-10-10 (STEP 78; completion reconciled)
- **Detailed task plan:** [R1A-01 baseline and focused task plan](maple-room-r1a-01-baseline.md)

### R1A-02 — Canonical world model and final house geometry

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 01
- **Branch:** `feat/r1a-02-world-model`
- **Start commit:** `a754efc9cd35f66e15efb8707dc9b4066d5ab54d` (workstream baseline; Checkpoints 4–6 start at `06295b65a2f8c79825b154249cf6e7869f66e9cb`)
- **End commit:** `37794564d921e69e29b90f47ea8d437d24bd704e` (PR #2 merge; verified STEP 107)
- **Evidence / tests:** STEP 90 consolidated **380 passed / 0 failed**; Ruff lint/format PASS (12 files); strict mypy PASS (23 files); **10 import contracts kept / 0 broken**. Exact T1/T2 Oracle equality; 44×26, 8 regions, 7 doors, 4 open edges, 1,144 singly covered lighting cells. Wheel resource inclusion/byte equality and isolated wheel loading PASS. Earlier checkpoint evidence retained in worklog.
- **Notes:** PR #2 merged; original evidence retained below/in the append-only worklog. No production activation. R1A-04 dynamic K4/emergency recovery and accepted desk/slot decisions remain unchanged.
- **Last updated:** 2026-10-11 (STEP 107 merge reconciliation)
- **Detailed task plan:** [R1A-02 world model breakdown](maple-room-r1a-02-world-model.md)


### R1A-03 — Object catalog and capability metadata

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 02 (PR #2 merged; baseline `37794564d921e69e29b90f47ea8d437d24bd704e`)
- **Branch:** `codex/r1a-03-desk-capability-decision`
- **Start commit:** `37794564d921e69e29b90f47ea8d437d24bd704e`
- **End commit:** `cd382d430c2da41954ffcc072b3525404def3761` (PR #3 merge; verified STEP 107)
- **Evidence / tests:** STEP 97 **510 passed / 0 failed**, including 130 new catalog cases. Ruff lint/format PASS (3 Python files), strict mypy PASS (25 files), 10 import contracts kept / 0 broken; wheel resource byte equality and isolated loading PASS. Exact T3/T4/T5 equality; T1/T2 unaffected; five-cell Oracle correction only.
- **Notes:** PR #3 merged; original evidence retained below/in the append-only worklog. No production activation. R1A-04 dynamic K4/emergency recovery and accepted desk/slot decisions remain unchanged.
- **Last updated:** 2026-10-11 (STEP 107 merge reconciliation)
- **Detailed task plan:** [Object catalog breakdown](maple-room-r1a-03-object-catalog.md)


### R1A-04 — Walkability, collision and recovery

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 02, 03 merged; STEP 103/104 decisions approved
- **Branch:** `codex/r1a-04-walkability-recovery`
- **Start commit:** `cd382d430c2da41954ffcc072b3525404def3761`
- **End commit:** `02efa73964a4f4d611b755970e26d38e0b0b7d31` (PR #4 merge; verified STEP 107)
- **Evidence / tests:** STEP 104: 605 passed / 0 failed (95 new); Ruff lint/format PASS (3); strict mypy PASS (29); 10 import contracts kept / 0 broken. Initial 431 cells / one component, 200 closed floors excluded, 26 distinct approaches reachable; recovery/prevention negatives PASS.
- **Notes:** PR #4 merged; original evidence retained below/in the append-only worklog. No production activation. R1A-04 dynamic K4/emergency recovery and accepted desk/slot decisions remain unchanged.
- **Last updated:** 2026-10-11 (STEP 107 merge reconciliation)
- **Detailed task plan:** [Walkability and recovery breakdown](maple-room-r1a-04-walkability-recovery.md)


### R1A-05 — Deterministic A* pathfinding

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 04 merged; bounded R1A-17 tuning support recorded; current R1A-17 evidence linked below
- **Branch:** `codex/r1a-05-deterministic-pathfinding`
- **Start commit:** `02efa73964a4f4d611b755970e26d38e0b0b7d31`
- **End commit:** `68fab979df2198342df7c8d0f5f45b4335f67cfb` (PR #5 merge; verified STEP 110)
- **Evidence / tests:** STEP 107: 1,184 passed / 0 failed (559 new), no warnings reported; T6 49/49 exact at four penalties; strict mypy Linux/Windows targets PASS (33 files each); Ruff lint/format PASS (4); 10 import contracts kept; original simulation pin test unchanged/PASS.
- **Notes:** provisional 250 ms/step, turn penalty 1. Compressed immutable routes, exact supplied-time integer interpolation, transient mid-edge rerouting and explicit no_destination. No production/persistence/resolution/placement integration. PR #5 merged; prior local evidence retained; dedicated grid-tuning digest in detailed plan.
- **Last updated:** 2026-10-11 (STEP 110 merge reconciliation)
- **Detailed task plan:** [Pathfinding breakdown](maple-room-r1a-05-pathfinding.md)

### R1A-06 — Interaction and capability resolution

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 03, 05 merged
- **Branch:** `codex/r1a-06-capability-resolution`
- **Start commit:** `68fab979df2198342df7c8d0f5f45b4335f67cfb`
- **End commit:** `f4b1f8ad14adc294a6b43778024f7bd2a6a03182`; PR #6 merge `bd6afa40c7ed2efb86e8733a9b4098b3f7d27774`
- **Evidence / tests:** STEP 110: **1,443 passed / 0 failed**, 141 new resolver cases; T6 exact candidates, S9 provider-loss rejection, S15 preserved; Ruff lint/format PASS (2); strict Linux/Windows-target mypy PASS (35 files each); 10 import contracts kept; three 384-resolution hash-seed replays agree; original simulation pin PASS unchanged.
- **Notes:** Isolated pure resolver, integer scoring/private decision ties and transient availability/preference hooks; no live Director/allowed.actions or production activation. Owner acceptance and merge confirmed by STEP 112.
- **Last updated:** 2026-10-11 (STEP 112 merge reconciliation)
- **Detailed task plan:** [Capability resolution breakdown](maple-room-r1a-06-capability-resolution.md)

### R1A-07 — Placement slots and Storage hooks

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 03, 04, 05 merged; 06 resolver isolation preserved
- **Branch:** `codex/r1a-07-placement-storage`
- **Start commit:** `bd6afa40c7ed2efb86e8733a9b4098b3f7d27774`
- **End commit:** `e2a7123a1936a2da9cfe1baacf5a9b5f3786528f`; PR #7 merge `82b37ea3ddcc6571062d8d8bffc9fd231bf27b60`
- **Evidence / tests:** STEP 112: **1,592 passed / 0 failed**, 149 new placement/Storage cases. T5 exact; 12 slots / 17 points / 29 references / 26 tiles / 3 reuses; S8/S11/S16, permissions/capacity, cooldown/rate boundaries and Storage/invariance PASS. Ruff lint/format PASS (2); strict Linux/Windows-target mypy PASS (37 each); 10 import contracts kept; original simulation pin unchanged/PASS.
- **Notes:** Pure candidate results and existing-item Storage derivation; no mutation, execution, audit creation, schema or production wiring. Provisional supplied-time limits documented. Owner accepted and PR #7 merged; historical STEP 112 evidence retained.
- **Last updated:** 2026-10-11 (STEP 115 integration reconciliation)
- **Detailed task plan:** [Placement and Storage breakdown](maple-room-r1a-07-placement-storage.md)

### R1A-08 — Persistence model / schema-v11 preparation

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 02, 03, 05, 07 merged
- **Branch:** `codex/r1a-08-persistence-v11-preparation`
- **Start commit:** `82b37ea3ddcc6571062d8d8bffc9fd231bf27b60`
- **End commit:** `aefa9c2ac9ca78afab57b251e768a9970e1ebe13` (PR #8 merge; verified STEP 119)
- **Evidence / tests:** 2,165 distinct passing cases / 0 unresolved failures: 115 new rehearsal cases plus 2,050 existing storage/migration/backup/world/Oracle/security/legacy regressions. Ruff lint/format PASS (4 files), strict Linux/Windows-target mypy PASS (38 each), 10 import contracts kept, offline wheel exclusion/loading PASS; original simulation pin unchanged/PASS.
- **Notes:** Owner accepted R1A-08 and PR #8 merged; STEP 115/117 records remain historical. Only registered, owned temporary synthetic lives can enter the converter. Candidate tables/loaders live under tests, absent from the wheel; shipped registry ends at v10 and normal startup rejects v11. All source history/identity/counters/sequence values preserved; verified snapshot plus one atomic transaction. Not a production migration PASS. Owner snapshot/copy rehearsal/cutover remain R1b.
- **Last updated:** 2026-10-11 (STEP 119 integration reconciliation)
- **Detailed task plan:** [Persistence rehearsal breakdown](maple-room-r1a-08-persistence-v11.md)

### R1A-09 — Legacy projection compatibility

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 05, 06 (merged)
- **Branch:** `codex/r1a-09-legacy-projection`
- **Start commit:** `aefa9c2ac9ca78afab57b251e768a9970e1ebe13`
- **End commit:** `efba67e7602c7cc70964a36f61b1734d58e22c28` (PR #9 merge; verified STEP 122)
- **Evidence / tests:** STEP 119: 3,121 passed / 0 failed, including 610 new projection cases. All T7 providers/S14, exact-time graph routes, deterministic interpolation, passthrough and negative inputs; Ruff lint/format PASS (2 files), strict Linux/Windows-target mypy PASS (24 each), 10 import contracts kept, unchanged original simulation pin PASS.
- **Notes:** STEP 120 owner ACCEPTED with limitations; no old-renderer/anchor/walker expansion. Before R1b uses this projection, an explicitly validated integration strategy must prevent collapsed-anchor and ambiguous mid-edge rejection from causing unsafe or misleading behavior; see the detailed plan pre-cutover gate. Fixture-only pure projection; no production caller, API/SSE/Director/frontend/schema change. 400 provider pairs: 334 timed paths, 26 zero-step cases, 40 collapsed-anchor routes explicitly reject under STEP 119's unmappable-input rule; mid-edge inputs without a projected origin reject. No invented loops or fallback positions. Native platform CI not claimed.
- **Last updated:** 2026-10-11 (STEP 122 merge reconciliation)
- **Detailed task plan:** [Legacy projection breakdown and evidence](maple-room-r1a-09-legacy-projection.md)

### R1A-10 — New Room backend/API contracts

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 02, 06, 07, 08, 09 merged
- **Branch:** `codex/r1a-10-world-api-contracts`
- **Start commit:** `efba67e7602c7cc70964a36f61b1734d58e22c28`
- **End commit:** `e3a031699b41f941d62bc754e4cb9c1819bdd67f` (PR #10 merge, verified STEP 125)
- **Evidence / tests:** 3,695 distinct backend cases / 0 unresolved failures: full suite 3,692 PASS, followed by 108 focused API/security passes including three added default-deny cases (82 new R1A-10 cases total). Frontend 208 PASS (four new), TypeScript/ESLint/build PASS. Ruff lint/format PASS (seven Python files); configured strict Linux/Windows-target mypy PASS (228 each); ten import contracts kept. Five fixture JSON exports, OpenAPI and generated TypeScript reproduce exactly. Original simulation pin unchanged/PASS. Native platform CI not claimed.
- **Notes:** Normal live GETs always 503; isolated validated development/fake factory only. Fixture snapshot nested in world, legacy snapshot byte-compatible. No world SSE; deferred R1b. No production loader or v11 activation. STEP 122/123 publication restrictions were historical; PR #10 is now merged. R1A-11 is separately authorized in STEP 125.
- **Last updated:** 2026-10-11 (STEP 125 merge reconciliation)
- **Detailed task plan:** [API contracts and evidence](maple-room-r1a-10-world-api-contracts.md)

### R1A-11 — Pixi renderer shell

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 02/10/14 merged; atlas completion dependency RESOLVED on integration `7b45af4`
- **Branch:** closure verification `codex/r1a-11-closure`
- **Start commit:** original shell `e3a031699b41f941d62bc754e4cb9c1819bdd67f`; closure baseline `7b45af4d94cd736390a1477e925e137698bc4aac`
- **End commit:** closure PR #13 merge `cd328010a71f2cbcb1d0aee9f59ce925132447ae`; shell merged via PR #11, atlases via PR #12
- **Evidence / tests:** STEP 131 fresh 423 frontend + 65 asset/bundle + 237 backend/API/security/Oracle cases PASS; 144 depth-ring cases / zero mismatches plus two supporting cases (subset, not additive). TypeScript/ESLint/build, exact API exports and ten import contracts PASS. Actual DPR-2 WebGL idle/walking/playback/arrival, clean console; screenshot outside Git. PR #12 native Windows evidence independently verified as historical CI.
- **Notes:** All original shell completion criteria PASS; owner accepted / closure verified and merged. Presentation-only, fixture-only, legacy default and simulation pin unchanged. Camera/lighting/live coexistence/final art/real devices remain separate gates.
- **Last updated:** 2026-10-11 (STEP 134 baseline reconciliation)
- **Detailed task plan:** [Formal closure matrix](maple-room-r1a-11-pixi-renderer-shell.md#step-131--formal-closure-verification)

### R1A-12 — Camera, zoom and DPR behavior

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 11/14 merged
- **Branch:** `codex/r1a-12-camera-zoom-dpr`
- **Start commit:** `cd328010a71f2cbcb1d0aee9f59ce925132447ae`
- **End commit:** PR14 merge `48897c8e6b81a674441f089336930ba20ae53913`
- **Evidence / tests:** STEP135 fresh focused461 Vitest /13 files, ESLint/TypeScript/production build PASS; earlier accepted511 Vitest /21 files PASS (88 new cases), 65 asset/bundle tests, 237 backend/API/security/Oracle/Harness regressions, ten import contracts, TypeScript/ESLint/build and exact API exports PASS. Existing 144 depth ring + two supporting cases preserved.
- **Notes:** Owner-approved §O clarification; L13/L14 unchanged. Overview/Follow/Focus, 25% dead-zone, oversize Focus, integer device output, reduced-motion snap and accessible fallback implemented in fixture-only preview. STEP134B Playwright DPR1/1.25/1.5/2/3 × L1–L4 PASS; reduced-motion snap and first-frame live CDP DPR updates verified. Physical-device QA remains deferred. Product default remains UNDECIDED; no lighting/coexistence/production implementation.
- **Last updated:** 2026-10-11 (STEP 135)
- **Detailed task plan:** [Camera architecture and browser closure evidence](maple-room-r1a-12-camera-zoom-dpr.md)

### R1A-13 — Lighting zones and emitter hooks

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 02/11/12/14 merged
- **Branch:** `codex/r1a-13-lighting-zones`
- **Start commit:** `48897c8e6b81a674441f089336930ba20ae53913`
- **End commit:** PR #15 merge `a85f226fb664056482baf8f27389870fce14fd45`
- **Evidence / tests:**549 frontend,66 asset/bundle,237 backend PASS;10 import contracts kept;lint/type/build/export PASS. Night reference hair7.572,skin2.007,shirt/pants2.094;doorway minimum1.802. Five DPRs × four phases validate exact single-tint coverage and edges. Native Windows atlas reproduction required on the PR. STEP138 fresh checks reproduce the stated test counts;browser evidence remains historical.
- **Notes:** Eight supplied zones/1144 cells,four provisional phases,4 window+2 lamp+1 screen hooks. Owner-approved original placeholder colors only;palette,geometry,metadata,spec and Oracle unchanged. Owner acceptance recorded in STEP138; PR #15 merge verified in STEP140. STEP138 restrictions are historical; current STEP141 authorization permits R1A-15 commit,push,PR and CI inspection only.
- **Last updated:**2026-10-12 (STEP140 merge reconciliation)
- **Detailed task plan:** [Lighting architecture and closure evidence](maple-room-r1a-13-lighting-zones.md)

### R1A-14 — Asset pipeline and atlas integration

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 01/03 and 11 shell merged
- **Branch:** `codex/r1a-14-asset-pipeline`
- **Start commit:** `f7e313cbe16992593d7f387450c9101d1b31f358`
- **End commit:** PR #12 merge `7b45af4d94cd736390a1477e925e137698bc4aac`; feature `5a5c4b6378060b0d925582e61cd857778cf8259f`
- **Evidence / tests:** Historical run `38144587116`: Ubuntu/Windows backend, frontend, ShellCheck, native Windows golden PNG/metadata/generated-index reproduction and build PASS. STEP 129 committed-revision release script/payload gate PASS. STEP 131 independently verifies merged atlas integration: 65 asset/bundle tests and six atlas loading cases within 423 frontend cases PASS; hashes/budget unchanged.
- **Notes:** 193 frames, two pages, 1.5 MiB static RGBA8 / 5.5 MiB resident upper bound. Placeholder art only; faces provisional. No production activation. R1A-18 independent Linux reproduction remains TODO. Earlier pending-platform/publication statements are historical.
- **Last updated:** 2026-10-11 (STEP 131 reconciliation)
- **Detailed task plan:** [Asset pipeline and merged evidence](maple-room-r1a-14-asset-pipeline.md)

### R1A-15 — Feature flag and old/new Room coexistence

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 10–14 merged
- **Branch:** `codex/r1a-15-room-coexistence`
- **Start commit:** `a85f226fb664056482baf8f27389870fce14fd45`
- **End commit:** `78953ce60d929a4e0a595b8c957ad5dd6b9fa49e` (PR #16 merge verified STEP 143)
- **Evidence / tests:** 586 frontend,69 asset/bundle,3674 backend PASS;21 expected Windows skips. TypeScript/ESLint/build, strict Windows/Linux-target mypy,10 import contracts,exact exports and deterministic atlas hashes PASS. Browser hardware WebGL/DPR1,1440/820/390 emulation,toggle/focus/fallback/production query/direct-route checks PASS. STEP140B fresh Playwright1.62.1/Chrome154.0.8037.98 actual DPR1/1.25/1.5/2/3 × desktop/tablet/phone15/15 PASS on measured NVIDIA RTX3060 D3D11 WebGL2; switching/focus/camera/backing/lighting/atlas/cleanup/console/overflow PASS. Fresh586+69 tests,lint/typecheck/build and3 production bypass checks PASS; backend evidence above is STEP140,not rerun. Fractional-DPR gap closed;STEP140B browser evidence accepted and not rerun in STEP141. Fresh STEP141586+69 tests,lint/typecheck/build,exports,import contracts and native atlas reproduction PASS;fresh full backend3674 PASS/21 expected Windows skips (142.37s).
- **Notes:** Owner clarified Legacy Pixi must stay functional when flag is OFF. Exact development-only fixture query and persistent DOM selector, abort-safe scene teardown,canonical room summary and truthful source labels. Legacy panels reused intact; fixture contracts cannot supply live journal/vitals/interactions. No B14,production default change or later workstream.
- **Last updated:** 2026-10-12 (STEP 143 merge reconciliation)
- **Detailed task plan:** [Coexistence architecture and evidence](maple-room-r1a-15-coexistence.md)

### R1A-16 — Validators and property tests

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 01–15 merged
- **Branch:** `codex/r1a-16-validators-property-tests`
- **Start commit:** `78953ce60d929a4e0a595b8c957ad5dd6b9fa49e`
- **End commit:** `50ec74865cee9c65ed566251476df7bbeed2dbd2` (PR #17 merge verified STEP 146)
- **Evidence / tests:** [Detailed API, S1–S17 matrix, properties and validation evidence](maple-room-r1a-16-validators-property-tests.md).
- **Notes:** Fresh STEP 144 local validation PASS:3842 backend/21 expected Windows skips,586 frontend,69 asset tests; all static/build/export gates PASS. PR #17 merge verified STEP 146; historical CI run38197593984 all five jobs PASS; this is not a fresh CI run. STEP 146 begins separately authorized R1A-17 local work.
- **Last updated:** 2026-10-12 (STEP 146 merge reconciliation)
- **Detailed task plan:** [R1A-16 plan/evidence](maple-room-r1a-16-validators-property-tests.md)

### R1A-17 — Fixtures and simulation coverage

- **Status:** DONE / OWNER ACCEPTED / MERGED
- **Dependencies:** 01–16 merged
- **Branch:** `codex/r1a-17-fixtures-simulation`
- **Start commit:** `50ec74865cee9c65ed566251476df7bbeed2dbd2`
- **End commit:** `4dc0e095470bcb572aeaebccb7bfa8e624f9b2fe` (PR #18 merge verified STEP 149)
- **Evidence / tests:** [A–N matrix, full local gates, reviewed long-run digest and timing](maple-room-r1a-17-fixtures-simulation.md).
- **Notes:** Test-only simulation and offline JSON; original 30-day digest preserved. PR #18 merged; historical STEP 147 CI-pending entries remain historical. STEP 149 starts separately authorized R1A-18.
- **Last updated:** 2026-10-12 (STEP 149 merge reconciliation)
- **Detailed task plan:** [Design and implementation evidence](maple-room-r1a-17-fixtures-simulation.md)

### R1A-18 — CI and Linux reproducibility

- **Status:** REVIEW / OWNER ACCEPTED / MERGE PENDING
- **Dependencies:** 01–17 merged
- **Branch:** `codex/r1a-18-ci-linux-reproducibility`
- **Start commit:** `4dc0e095470bcb572aeaebccb7bfa8e624f9b2fe`
- **End commit:** — (merge pending; feature commit/PR reported by STEP 150)
- **Evidence / tests:** [Coverage, actual-byte artifact comparison and local validation](maple-room-r1a-18-ci-linux-reproducibility.md).
- **Notes:** STEP 150 authorizes integration and CI/artifact inspection. Actual results belong in the PR/final report. DONE requires full cross-platform evidence and confirmed merge.
- **Last updated:** 2026-10-12 (STEP 150)
- **Detailed task plan:** [Design and evidence](maple-room-r1a-18-ci-linux-reproducibility.md)

### R1A-19 — Performance and soak validation

- **Status:** TODO
- **Dependencies:** 14, 15, 17
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** —
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

### R1A-20 — R1a Acceptance Gate

- **Status:** TODO
- **Dependencies:** 01-19
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** Gate criteria: plan §3 R1A-20. Passing the gate does not authorize R1b.
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)
