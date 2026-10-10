# Maple Room R1a Checklist

**Live status of the R1a workstreams.** Plan: `maple-room-r1a-plan.md`. History: `maple-room-r1a-worklog.md`.

- **Starting baseline:** `v0.2-development` @ `5c6db41c0139e1da6a2178b36d838e4da57074b1` (original planning baseline: `dfd5972`).
- **R1a authorization:** **AUTHORIZED** by owner, 2026-10-10; Pre-R1 Gate clearance **APPROVED / CLEAR**. R1A-01 starts with baseline preparation only; R1A-02–R1A-20 remain TODO. Approval does not claim baseline checks or CI PASS.
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
| R1a authorization | **RESOLVED** | **AUTHORIZED** by owner, 2026-10-10; R1A-01 kickoff only in this step |

Gate statuses: OPEN · RESOLVED · BLOCKED. They are separate from the item statuses below.

## Counters

| Total | TODO | IN PROGRESS | BLOCKED | REVIEW | DONE | DEFERRED |
|---|---|---|---|---|---|---|
| 20 | 19 | 1 | 0 | 0 | 0 | 0 |

## Status vocabulary (only these values)

| Status | Meaning |
|---|---|
| **TODO** | Not started. |
| **IN PROGRESS** | Detailed task plan written; implementation under way on the recorded branch. |
| **BLOCKED** | Cannot proceed. Must state the blocking dependency or decision. |
| **REVIEW** | Implementation complete; acceptance evidence or review still pending. |
| **DONE** | Completion criteria met, evidence recorded, reviewed and merged. |
| **DEFERRED** | Moved out of R1a. Must state the explicit destination phase or gate. |

## Mandatory rules

1. Status changes are committed **with** the implementation or change that caused them.
2. No item may be marked **DONE** without evidence (tests, measurements or review records named in "Evidence / tests").
3. **REVIEW** means implementation is complete but acceptance evidence or review is still pending.
4. **BLOCKED** must state the blocking dependency.
5. **DEFERRED** requires an explicit destination phase or gate.
6. The checklist must match **repository truth, not intention**.
7. Every change follows the documentation policy (plan §8): plan → implement → test → evidence → checklist → worklog → docs → review → commit. An architecture conflict triggers the stop rule (plan §8): the item becomes BLOCKED until the owner accepts the new decision.
8. Update the counters in the same commit as any status change.

## Summary

| ID | Title | Status | Dependencies (start) | Last updated |
|---|---|---|---|---|
| R1A-01 | Baseline and test harness | IN PROGRESS | Pre-R1 Gate closed + owner authorization of R1a | 2026-10-10 |
| R1A-02 | Canonical world model and final house geometry | TODO | 01 | 2026-10-09 |
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

- **Status:** IN PROGRESS
- **Dependencies:** Pre-R1 Gate closed + owner authorization of R1a
- **Branch:** `codex/r1a-01-baseline`
- **Start commit:** `5c6db41c0139e1da6a2178b36d838e4da57074b1`
- **End commit:** —
- **Evidence / tests:** Owner approval; local Git/remote/clean-start verification; documentation/static checks. Historical R-01 validation is not full baseline/CI evidence; see baseline record.
- **Notes:** Kickoff/documentation preparation only. Baseline verification and harness remain outstanding; no World Model, Test Oracle or Engine created. R1A-02–R1A-20 not started.
- **Last updated:** 2026-10-10 (owner-authorized kickoff)
- **Detailed task plan:** [R1A-01 baseline and focused task plan](maple-room-r1a-01-baseline.md)

### R1A-02 — Canonical world model and final house geometry

- **Status:** TODO
- **Dependencies:** 01
- **Branch:** —
- **Start commit:** —
- **End commit:** —
- **Evidence / tests:** —
- **Notes:** —
- **Last updated:** 2026-10-09 (planning framework created)
- **Detailed task plan:** — (created only when this item starts)

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
