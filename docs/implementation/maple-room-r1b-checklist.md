# Maple Room R1b — Checklist

**STEP159,2026-10-12 — PLANNING REVIEW / OWNER ACCEPTED / MERGE PENDING.** G1 is accepted for planning-document integration only: final review, documentation corrections, commit, normal push, PR and CI inspection are authorized. Merge requires separate owner authorization. G2 implementation and G3–G7 operational/default-switch authority are NOT granted; future implementation publication P is also NOT granted. All12implementation workstreams remain TODO (0/12 DONE, including after a future planning-only merge). D01–D06 remain OPEN; no projection strategy is approved. Historical STEP158 records below describe the planning stage.

**STEP158,2026-10-12 — PLANNING REVIEW / pending G1 acceptance.** Baseline `3e89996216336f453b03939467e6a06cb33da3fb`. Branch `codex/r1b-master-plan`; planning worktree `C:/GitHub/Maplegotchi-worktrees/r1b-planning`. This planning task is outside implementation counters. No implementation/data/production authority; STEP159 planning publication is separately authorized above. [Master Plan](maple-room-r1b-plan.md), [migration safety](maple-room-r1b-migration-safety.md), [cutover](maple-room-r1b-cutover-plan.md), [risks/gates](maple-room-r1b-risk-gates.md).

## Counters

| Total | TODO | IN PROGRESS | BLOCKED | REVIEW | DONE | DEFERRED |
|---|---|---|---|---|---|---|
|12|12|0|0|0|0|0|

Implementation completion0/12. Status vocabulary follows R1a: TODO not started; IN PROGRESS authorized plan/implementation underway; BLOCKED names unresolved dependency; REVIEW implemented/evidence ready but owner/integration pending; DONE required review/merge and, for operations, actual authorized evidence/acceptance; DEFERRED requires accepted destination. OPEN decisions live in the plan; future tasks remain TODO rather than being falsely started. Existing R1a synthetic evidence cannot mark real-copy or production work DONE.

## Workstreams

| ID | Title | Status | Dependencies | Branch | Start / end commit | Evidence | Owner approval | Blocking decisions | Updated |
|---|---|---|---|---|---|---|---|---|---|
|R1B-01|Contract inventory and compatibility decisions|TODO|G1,G2 (inventory only)|— (future)|— / —|Not executed; [requirements](maple-room-r1b-plan.md#r1b-01)|NOT GRANTED; G1 then explicit G2 for this local inventory only; D01 resolution is not required and is not implied.|No D01 prerequisite for this inventory. G1/G2 still required; D01/D03 remain OPEN and no strategy is selected.|2026-10-12|
|R1B-02|v11 persistence contract and isolated loaders|TODO|R1B-01|— (future)|— / —|Not executed; [requirements](maple-room-r1b-plan.md#r1b-02)|NOT GRANTED; G2; accepted R1B-01 inventory with D01 still OPEN is sufficient. D02 reviewed before dependent03/09 and rechecked at G4.|Not blocked by D01. Requires accepted01 inventory and G2; resolve/freeze D02 within02 before dependent conversion/loader behavior is implemented. No live projection or startup registration.|2026-10-12|
|R1B-03|Unshipped migration and failure-safe adapter|TODO|R1B-02|— (future)|— / —|Not executed; [requirements](maple-room-r1b-plan.md#r1b-03)|NOT GRANTED; G2; G3 required before any real-copy input.|Not blocked by D01 within the isolated synthetic-only scope. Requires02/D02 acceptance and G2; registry stays10, arbitrary real-copy input remains refused, no live runtime/projection adapter.|2026-10-12|
|R1B-04|Authoritative grid runtime and restart integration|TODO|R1B-01, R1B-02|— (future)|— / —|Not executed; [requirements](maple-room-r1b-plan.md#r1b-04)|NOT GRANTED; G2; D01 resolved before dependent behavior changes.|DIRECT D01 BLOCK: do not begin this workstream implementation while D01 is OPEN. Also requires02/D02 and G2; isolated persistence03 does not remove this gate.|2026-10-12|
|R1B-05|Live contracts and Legacy compatibility|TODO|R1B-01, R1B-04|— (future)|— / —|Not executed; [requirements](maple-room-r1b-plan.md#r1b-05)|NOT GRANTED; G2; D01 and D03 accepted before changing contracts.|DIRECT D01 BLOCK: no strategy/compatibility implementation while D01 is OPEN. Also requires04, accepted D03 live DTO/SSE contract and G2.|2026-10-12|
|R1B-06|Simulation comparison and digest review|TODO|R1B-04, R1B-05|— (future)|— / —|Not executed; [requirements](maple-room-r1b-plan.md#r1b-06)|NOT GRANTED; G2 plus specific digest approval D05 before updating pinned assertions.|INDIRECT D01 BLOCK through04/05. Requires their acceptance; D05 explicit approval before digest updates, with all old pins/history preserved.|2026-10-12|
|R1B-07|Cross-platform regression and release isolation|TODO|R1B-03, R1B-04, R1B-05, R1B-06|— (future)|— / —|Not executed; [requirements](maple-room-r1b-plan.md#r1b-07)|NOT GRANTED; G2 and separately authorized commit/push/PR/CI (not granted by STEP158).|INDIRECT D01 BLOCK through04/05/06. Full integrated closure cannot start or finish from03-only proof. P approval required for any future publication/CI.|2026-10-12|
|R1B-08|Owner-copy rehearsal and restore proof|TODO|R1B-03, R1B-07|— (future)|— / —|Not executed; [requirements](maple-room-r1b-plan.md#r1b-08)|NOT GRANTED; G3 specific host/data/path/privacy/retention approval; not implied by G2.|INDIRECT D01 BLOCK through07. Also requires G3 real-copy/privacy scope and accepted exact candidate; no real-data access from local authorization.|2026-10-12|
|R1B-09|Shipped v11 registration and release contract|TODO|R1B-07, R1B-08|— (future)|— / —|Not executed; [requirements](maple-room-r1b-plan.md#r1b-09)|NOT GRANTED; G2 for local code; separate P publication/review/merge approval after G3 copy acceptance. G4/G5 still required for production.|INDIRECT D01 BLOCK through07/08. Also requires D02 contract, actual-copy acceptance and separate P approval; no startup registration from03-only success.|2026-10-12|
|R1B-10|Production readiness and snapshot gate|TODO|R1B-08, R1B-09|— (future)|— / —|Not executed; [requirements](maple-room-r1b-plan.md#r1b-10)|NOT GRANTED; G4; any actual host/snapshot inspection requires separate explicit scope.|INDIRECT D01 BLOCK through08/09; D04 current snapshot/retry proof and D06 window/loss decisions required for G4 readiness.|2026-10-12|
|R1B-11|Single production migration and grid cutover|TODO|R1B-10|— (future)|— / —|Not executed; [requirements](maple-room-r1b-plan.md#r1b-11)|NOT GRANTED; G5 explicit production migration AND state-cutover authorization; recovery actions under G6.|INDIRECT D01 BLOCK through10. Requires resolved candidate decisions, signed G4 and exact G5 operation; no production cutover with OPEN projection behavior.|2026-10-12|
|R1B-12|Post-cutover verification and acceptance|TODO|R1B-11|— (future)|— / —|Not executed; [requirements](maple-room-r1b-plan.md#r1b-12)|NOT GRANTED; G6; any further production verification/restart/restore scope explicit.|INDIRECT D01 BLOCK through11. Requires authorized cutover and scoped G6 verification/acceptance/recovery authority.|2026-10-12|

## Change discipline

Before a future task begins: record exact authorization, branch/start SHA, focused task plan, dependencies and open decisions. Before REVIEW: actual commands/counts and source/commit fingerprints; separate historical from fresh. Before DONE: owner review and authorized integration, plus actual operational evidence where applicable. Update counters with verified state, never intention. G2 does not imply P/G3/G4/G5/G6/G7. No future branch name/start/end commit is invented in this checklist.

R1a completion is verified20/20 after PR21 merge; that is an accepted prerequisite, not R1b completion or current backup/production-readiness proof. Planning documents are ready for owner review subject to OPEN decisions; no workstream implemented in STEP158.

## Owner clarification after STEP158

Owner explicitly directs D01 to remain OPEN and to be resolved before affected implementation. No projection strategy, local implementation or production action is approved. All12workstreams remainTODO; planning was REVIEW/pendingG1 in STEP158; G1 is accepted for planning integration in STEP159.

## STEP158 continuation — D01 boundary

D01 remains OPEN by owner direction;40collapsed-anchor pairs and ambiguousmid-edge projections remain accepted planning evidence,not authorization to alter projection.01inventory can complete withD01OPEN;02and03are D01-independent successors under future boundedG2 and their own prerequisites.04/05directly blocked;06–12transitively blocked. All12remainTODO. No further projection-strategy choice requested.
