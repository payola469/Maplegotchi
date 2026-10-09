# Maple Room R1a Work Log

**Append-only implementation history of R1a.** Plan: `maple-room-r1a-plan.md`. Live status: `maple-room-r1a-checklist.md`.

## Rules

- **Append-only**, except factual corrections. A correction is marked `Correction (date):` and keeps the original text visible.
- **Never rewrite history** to make a failed attempt disappear.
- **Record failed experiments** when they materially affect design or implementation.
- **Do not record raw chain-of-thought.** Record decisions, evidence and technical reasoning at a concise engineering level.
- **Record only what happened.** No planned or expected results are written as if they occurred.
- Every entry follows the documentation policy (plan §8): plan → implement → test → evidence → checklist → worklog → docs → review → commit.
- An architecture conflict triggers the stop rule (plan §8). The entry records the conflict, the proposed amendment and the owner decision when it arrives.

### BEFORE → CHANGE → EVIDENCE

Every entry states:
- **Before:** the verifiable state before the change;
- **Change:** what was actually changed;
- **Evidence:** the tests, measurements or review results that prove the new state.

Example format (illustrative only; this did **not** happen):

> **Before:**
> - Canonical room walkability mask does not exist.
>
> **Change:**
> - Added walkable mask generation from room regions, doors and blocking masks.
> - Excluded closed rooms.
>
> **Evidence:**
> - expected open walkable tiles reachable
> - zero closed-room tiles reachable
> - validation/tests PASS

## Entry template

```
### <YYYY-MM-DD HH:MM +07> — <R1A-NN[, R1A-NN]> — <short title>

- **Work item(s):**
- **Branch:**
- **Starting commit:**
- **Ending commit:**
- **Goal:**
- **Before:**
- **Changes made:**
- **Files changed:**
- **Tests run:**
- **Evidence / results:**
- **Problems found:**
- **Decisions made:**
- **ADR / spec impact:**
- **Checklist status changes:**
- **Remaining risks:**
- **Next step:**
- **Deployment status:**
```

---

## Entries

### 2026-10-09 — Bootstrap (no R1A item) — R1a planning framework created

- **Work item(s):** none. The planning framework is not an R1A work item.
- **Branch:** `docs/maple-room-r1a-plan`
- **Starting commit:** `dfd5972` (`v0.2-development`)
- **Ending commit:** not yet committed (recorded when the framework is committed after review)
- **Goal:** make the whole R1a path, its dependencies and its acceptance gate visible before any coding starts.
- **Before:**
  - The Room Final Design Spec (`docs/architecture/maple-room-final-design-spec.md`) is merged into `v0.2-development` (`dfd5972`) and owner-approved in principle.
  - ADR-0035..0041 are accepted; the technical spike values are locked (ADR-0041 L1–L22, C1–C8).
  - No R1a plan, checklist or worklog exists.
  - R1a implementation has **not** started and is **not** authorized.
- **Changes made:**
  - Created the master plan with workstreams R1A-01 … R1A-20, the dependency graph and critical path, the risk classification, the R1a/R1b boundary, the work-item policy and the documentation policy.
  - Created the live checklist with all 20 items at TODO.
  - Created this work log.
- **Files changed:**
  - `docs/implementation/maple-room-r1a-plan.md` (new)
  - `docs/implementation/maple-room-r1a-checklist.md` (new)
  - `docs/implementation/maple-room-r1a-worklog.md` (new)
- **Tests run:** none applicable (documentation only); `git diff --check` for whitespace.
- **Evidence / results:** documentation only. No R1a implementation result exists.
- **Problems found:** none.
- **Decisions made:** none beyond the plan's structure. No accepted decision was changed.
- **ADR / spec impact:** none. The Room Final Design Spec, ADR-0035..0041, the art contract, the future architecture and `docs/roadmap/maple-roadmap.md` are unchanged.
- **Checklist status changes:** created; R1A-01 … R1A-20 = TODO.
- **Remaining risks:** see plan §5. The only blocker is R1a authorization (plan §9).
- **Next step:** after this planning framework is approved, write a focused implementation breakdown for **R1A-01** only, once the owner authorizes R1a.
- **Deployment status:** no runtime, schema, service, configuration, script or deployment change. Nothing deployed. Production remains schema v10 with the legacy Room view.

> **Correction (2026-10-09)** — a factual correction to the historical record above, **not** an implementation entry. The bootstrap text is kept unchanged.
> - The bootstrap statement "The only blocker is R1a authorization." is superseded by the reconciled Pre-R1 Gate (plan §9; checklist "Pre-R1 Gate").
> - R1a authorization is currently blocked by three open items:
>   1. OD-01 inside-service boundary probe;
>   2. OD-01 restore test;
>   3. R-01 fixed or explicitly accepted.
> - Stage C authorization and Phase 8 status are already resolved (see the next entry).

### 2026-10-09 — Pre-R1 gate (no R1A item) — Stage C and Phase 8 status clarified; pre-R1 gate made explicit

- **Work item(s):** none (documentation/planning; pre-R1 gate).
- **Branch:** `docs/maple-room-r1a-plan`
- **Starting commit:** `dfd5972` (uncommitted framework on top)
- **Ending commit:** not yet committed
- **Goal:** record the owner's decisions on the OD-01 items and make the pre-R1 gate explicit before R1a.
- **Before:**
  - The repository's last record of Stage C was "NOT authorized" (2026-09-30), although the release `160ed4f…` is installed and active.
  - Phase 8 had no recorded status.
  - The plan left OD-01/R-01 as an "owner decision at authorization time".
- **Changes made:**
  - Recorded the owner decision (2026-10-09): the Stage C install of release `160ed4fb9f2534a4609d826d9c4535cc7863ae3d` is **retroactively authorized**; Stage C stays **open** until the inside-service boundary probe and the restore test pass; M3 is not claimed.
  - Recorded the owner decision (2026-10-09): Phase 8 is **not authorized, not started, deferred** until Stage C is closed; it blocks neither R1a nor R1b (ADR-0009).
  - Added a dated pointer in future-architecture §2.7 and a status note under §22 item 1; the 2026-10-08 statements are kept as history.
  - Plan §9 and §5 and the checklist now classify the three remaining pre-R1 items as **BLOCKER before R1A-01**; the checklist has a Pre-R1 Gate section.
- **Files changed:** `CLAUDE.md`, `docs/architecture.md`, `docs/architecture/maple-future-architecture.md`, `docs/implementation/maple-room-r1a-plan.md`, `docs/implementation/maple-room-r1a-checklist.md`, this work log.
- **Tests run:** none applicable (documentation only); `git diff --check`.
- **Evidence / results:** owner decisions given in conversation on 2026-10-09; no production evidence was collected and no production command was run.
- **Problems found:** none.
- **Decisions made:** owner: Stage C option (a); Phase 8 option (a); known pre-R1 gates are resolved before R1a.
- **ADR / spec impact:** none. No ADR, spec or roadmap change.
- **Checklist status changes:** Pre-R1 Gate added (Stage C authorization RESOLVED, Phase 8 status RESOLVED, boundary probe OPEN, restore test OPEN, R-01 OPEN, R1a authorization BLOCKED). R1A-01 … R1A-20 remain TODO.
- **Remaining risks:** OD-01 now has only two open evidence items (boundary probe, restore test). R-01 remains separately open. The bootstrap entry's "only blocker is R1a authorization" is superseded by this entry.
- **Next step:** resolve the three OPEN pre-R1 items (owner-run probe and restore on paolo-core; R-01 fix or explicit acceptance), then request R1a authorization and write the R1A-01 breakdown.
- **Deployment status:** no production behaviour changed; nothing deployed; no production command run. R1a has not started.
