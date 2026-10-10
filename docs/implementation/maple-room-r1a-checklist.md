# Maple Room R1a Checklist

**Live status of the R1a workstreams.** Plan: `maple-room-r1a-plan.md`. History: `maple-room-r1a-worklog.md`.

- **Starting baseline:** `v0.2-development` @ `5c6db41c0139e1da6a2178b36d838e4da57074b1` (original planning baseline: `dfd5972`).
- **R1a authorization:** **AUTHORIZED** by owner, 2026-10-10; Pre-R1 Gate clearance **APPROVED / CLEAR**. R1A-01 baseline/test infrastructure is DONE / OWNER ACCEPTED / MERGED. R1A-02 is REVIEW / PENDING FINAL OWNER ACCEPTANCE (STEP 90 authorizes Checkpoints 4–6 implementation and validation only; commit/push/merge and production activation are not authorized); R1A-03–R1A-20 remain TODO. Approval does not claim baseline checks or CI PASS.
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
| 20 | 18 | 0 | 0 | 1 | 1 | 0 |

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
| R1A-02 | Canonical world model and final house geometry | REVIEW / PENDING OWNER ACCEPTANCE | 01 (DONE) | 2026-10-10 |
| R1A-03 | Object catalog and capability metadata | TODO | 02 | 2026-10-09 |
| R1A-04 | Walkability, collision and recovery | TODO | 02, 03 | 2026-10-09 |
| R1A-05 | Deterministic A* pathfinding | TODO | 04 (completion: 17 tuning evidence) | 2026-10-09 |
| R1A-06 | Interaction and capability resolution | TODO | 03, 05 | 2026-10-09 |
| R1A-07 | Placement slots and Storage hooks | TODO | 03, 04, 05 | 2026-10-09 |
| R1A-08 | Persistence model / schema-v11 preparation | TODO | 02, 03, 05 (completion: 07) | 2026-10-09 |
| R1A-09 | Legacy projection compatibility | TODO | 05, 06 | 2026-10-09 |
| R1A-10 | New Room backend/API contracts | TODO | 02 for the fixture draft (completion: 06, 07, 08, 09) | 2026-10-09 |
| R1A-11 | Pixi renderer shell | TODO | 02 + 10 draft (completion: 10, 14) | 2026-10-09 |
| R1A-12 | Camera, zoom and DPR behavior | TODO | 11 | 2026-10-09 |
| R1A-13 | Lighting zones and emitter hooks | TODO | 11, 02 | 2026-10-09 |
| R1A-14 | Asset pipeline and atlas integration | TODO | 01 (completion: 03, 11) | 2026-10-09 |
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

- **Status:** REVIEW / PENDING FINAL OWNER ACCEPTANCE (Checkpoints 1–6 implemented; 4–6 uncommitted, integration pending)
- **Dependencies:** 01
- **Branch:** `feat/r1a-02-world-model`
- **Start commit:** `a754efc9cd35f66e15efb8707dc9b4066d5ab54d` (workstream baseline; Checkpoints 4–6 start at `06295b65a2f8c79825b154249cf6e7869f66e9cb`)
- **End commit:** —
- **Evidence / tests:** STEP 90 consolidated **380 passed / 0 failed**; Ruff lint/format PASS (12 files); strict mypy PASS (23 files); **10 import contracts kept / 0 broken**. Exact T1/T2 Oracle equality; 44×26, 8 regions, 7 doors, 4 open edges, 1,144 singly covered lighting cells. Wheel resource inclusion/byte equality and isolated wheel loading PASS. Earlier checkpoint evidence retained in worklog.
- **Notes:** Checkpoints 4–6 add backend lighting/S7 predicates, declarative initial house, strict isolated runtime reader and consolidated validation. No production wiring, object catalog, pathfinder/walkability engine, API, renderer, schema, Oracle or simulation-pin change. Final owner acceptance and integration pending; no commit/push/merge in STEP 90. R1A-03–R1A-20 TODO; desk-capability conflict remains deferred to R1A-03/06.
- **Last updated:** 2026-10-10 (STEP 90; final review preparation)
- **Detailed task plan:** [R1A-02 world model breakdown](maple-room-r1a-02-world-model.md)

### R1A-03 — Object catalog and capability metadata

- **Status:** TODO
- **Dependencies:** 02
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** —
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

### R1A-04 — Walkability, collision and recovery

- **Status:** TODO
- **Dependencies:** 02, 03
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** —
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

### R1A-05 — Deterministic A* pathfinding

- **Status:** TODO
- **Dependencies:** 04 (completion: 17 tuning evidence)
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** —
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

### R1A-06 — Interaction and capability resolution

- **Status:** TODO
- **Dependencies:** 03, 05
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** —
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

### R1A-07 — Placement slots and Storage hooks

- **Status:** TODO
- **Dependencies:** 03, 04, 05
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** —
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

### R1A-08 — Persistence model / schema-v11 preparation

- **Status:** TODO
- **Dependencies:** 02, 03, 05 (completion: 07)
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** Production-safety constraint (plan R1A-08): the v11 conversion must not be reachable from production startup or release activation. Rehearsal on synthetic v10 databases only.
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

### R1A-09 — Legacy projection compatibility

- **Status:** TODO
- **Dependencies:** 05, 06
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** —
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

### R1A-10 — New Room backend/API contracts

- **Status:** TODO
- **Dependencies:** 02 for the fixture draft (completion: 06, 07, 08, 09)
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** —
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

### R1A-11 — Pixi renderer shell

- **Status:** TODO
- **Dependencies:** 02 + 10 draft (completion: 10, 14)
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** —
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

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

- **Status:** TODO
- **Dependencies:** 01 (completion: 03, 11)
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** —
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

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
