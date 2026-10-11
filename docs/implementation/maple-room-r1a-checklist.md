# Maple Room R1a Checklist

**Live status of the R1a workstreams.** Plan: `maple-room-r1a-plan.md`. History: `maple-room-r1a-worklog.md`.

- **Starting baseline:** `v0.2-development` @ `5c6db41c0139e1da6a2178b36d838e4da57074b1` (original planning baseline: `dfd5972`).
- **R1a authorization:** AUTHORIZED by owner; Pre-R1 Gate APPROVED / CLEAR. R1A-01–10 and R1A-14 DONE / OWNER ACCEPTED / MERGED. PR #12 merge `7b45af4d94cd736390a1477e925e137698bc4aac` is the verified integration HEAD and includes PR #11 merge `f7e313cbe16992593d7f387450c9101d1b31f358`. R1A-11 REVIEW / OWNER ACCEPTED / CLOSURE VERIFIED / MERGE PENDING (STEP 132); atlas dependency RESOLVED on the merged tree. Historical PR #12 CI run `38144587116` passed all five jobs, including native Windows PNG/metadata/generated-index reproduction and frontend build. R1A-12/13 and R1A-15–20 TODO. Production remains schema v10, legacy Room default, explicit development fixture preview only. STEP 132 owner acceptance authorizes the eight-file documentation commit, normal push, closure PR and CI inspection. No remaining R1A-11 blockers; closure record integration is pending. No merge, deployment, production access, schema-v11 activation or later-workstream implementation authorized. [Closure evidence](maple-room-r1a-11-pixi-renderer-shell.md#step-131--formal-closure-verification). Current counters: **11 DONE / 1 REVIEW / 8 TODO**. After closure PR merge: **R1A-11 DONE / OWNER ACCEPTED / CLOSURE VERIFIED; 12 DONE / 8 TODO / 60% complete**.
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
| 20 | 8 | 0 | 0 | 1 | 11 | 0 |

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
| R1A-11 | Pixi renderer shell | REVIEW / OWNER ACCEPTED / CLOSURE VERIFIED / MERGE PENDING | 02 + 10 + 14 merged; atlas dependency resolved | 2026-10-11 |
| R1A-12 | Camera, zoom and DPR behavior | TODO | 11 | 2026-10-09 |
| R1A-13 | Lighting zones and emitter hooks | TODO | 11, 02 | 2026-10-09 |
| R1A-14 | Asset pipeline and atlas integration | DONE / OWNER ACCEPTED / MERGED | 01, 03, 11 shell merged; native Windows PASS | 2026-10-11 |
| R1A-15 | Feature flag and old/new Room coexistence | TODO | 10, 11 (completion: 12, 13, 14) | 2026-10-09 |
| R1A-16 | Validators and property tests | TODO | 01 (continuous; completion: 02-14) | 2026-10-09 |
| R1A-17 | Fixtures and simulation coverage | TODO | 01 (continuous; completion: 02-15 as needed) | 2026-10-09 |
| R1A-18 | CI and Linux reproducibility | TODO | 01 (continuous; completion: 14) | 2026-10-09 |
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
- **Dependencies:** 04 merged; bounded R1A-17 tuning support recorded (17 remains TODO)
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

- **Status:** REVIEW / OWNER ACCEPTED / CLOSURE VERIFIED / MERGE PENDING
- **Dependencies:** 02/10/14 merged; atlas completion dependency RESOLVED on integration `7b45af4`
- **Branch:** closure verification `codex/r1a-11-closure`
- **Start commit:** original shell `e3a031699b41f941d62bc754e4cb9c1819bdd67f`; closure baseline `7b45af4d94cd736390a1477e925e137698bc4aac`
- **End commit:** closure record in this documentation change, integration pending; shell merged via PR #11, atlases via PR #12
- **Evidence / tests:** STEP 131 fresh 423 frontend + 65 asset/bundle + 237 backend/API/security/Oracle cases PASS; 144 depth-ring cases / zero mismatches plus two supporting cases (subset, not additive). TypeScript/ESLint/build, exact API exports and ten import contracts PASS. Actual DPR-2 WebGL idle/walking/playback/arrival, clean console; screenshot outside Git. PR #12 native Windows evidence independently verified as historical CI.
- **Notes:** All original shell completion criteria PASS; owner accepted / closure verified, not DONE until merge of closure record. Presentation-only, fixture-only, legacy default and simulation pin unchanged. Camera/lighting/live coexistence/final art/real devices remain separate gates.
- **Last updated:** 2026-10-11 (STEP 132)
- **Detailed task plan:** [Formal closure matrix](maple-room-r1a-11-pixi-renderer-shell.md#step-131--formal-closure-verification)

### R1A-12 — Camera, zoom and DPR behavior

- **Status:** TODO
- **Dependencies:** 11
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** —
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

### R1A-13 — Lighting zones and emitter hooks

- **Status:** TODO
- **Dependencies:** 11, 02
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** —
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

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

- **Status:** TODO
- **Dependencies:** 10, 11 (completion: 12, 13, 14)
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** —
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

### R1A-16 — Validators and property tests

- **Status:** TODO
- **Dependencies:** 01 (continuous; completion: 02-14)
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** Continuous: starts with R1A-01 and grows with every item; DONE only when every S-rule S1–S17 has positive and negative tests.
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

### R1A-17 — Fixtures and simulation coverage

- **Status:** TODO
- **Dependencies:** 01 (continuous; completion: 02-15 as needed)
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** Continuous. The existing pinned 30-day simulation digest must stay unchanged in R1a.
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

### R1A-18 — CI and Linux reproducibility

- **Status:** TODO
- **Dependencies:** 01 (continuous; completion: 14)
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** Continuous. Includes the Linux atlas reproducibility deferred from the spike.
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

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
