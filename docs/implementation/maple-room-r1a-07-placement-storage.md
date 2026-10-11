# R1A-07 — Placement slots and Storage hooks

Status: REVIEW / PENDING OWNER ACCEPTANCE (STEP 112). Baseline: `bd6afa40c7ed2efb86e8733a9b4098b3f7d27774`, PR #6 merged. R1A-01–06 DONE / OWNER ACCEPTED / MERGED. No publication or production authorization.

## Binding inputs and boundaries

[Master Plan](maple-room-r1a-plan.md#r1a-07--placement-slots-and-storage-hooks), [Final Spec §§K/L, S8/S11/S16 and T5](../architecture/maple-room-final-design-spec.md), [ADR-0039](../adr/0039-storage-and-maple-slot-placement.md), [ADR-0036](../adr/0036-object-catalog-and-capabilities.md), [ADR-0035](../adr/0035-world-model.md), [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) and [ADR-0038](../adr/0038-owner-edit-mode-and-owner-authentication.md) bind this work. Locked ADR values precede accepted ADR rules, Final Spec and proposals. Reuse merged R1A-03–06; preserve STEP 97 named slot overrides and independent Oracle.

No catalog defaults, geometry, representation contents, live Director, API, renderer, persistence/schema, placement execution, owner editor or audit creation. Eligible items are caller-supplied existing representation metadata; canonical initial slots remain empty. Caller authority is a domain input, not authentication.

## Implementation sequence and completion gates

1. Immutable candidate contracts in proposed `core/world/placement.py`: stable host/slot key, existing display item metadata, active/inactive relationship, supplied history and validated provisional limits. No collision geometry on display items. Strict typed tuples, enum/bool/integer/UTC validation and canonical identity ordering.
2. Pure proposed-placement validation: resolve host/item/slot, reject hook targets for either actor, validate catalog-derived geometry/S8 and safe-layout K1–K4/S5/S13, then genuine approach reachability. Reuse existing catalog permissions. Class, eligibility, uniqueness and capacity apply to both actors; Maple additionally requires its own creation or an allowed decoration, `movable_by: maple`, slot permission, cooldown and rate budget. Owner bypasses only Maple-specific restrictions.
3. Derived Storage: eligible existing creations with Room representation and explicitly movable/displayable decorations, minus active relationships. Functional/structural/system-critical/non-displayable objects excluded. Inactive records retain metadata but reserve neither item nor capacity. Reject inconsistent active references, eligibility, capacity or duplicate active item; never silently drop invalid state.
4. Focused positive/negative tests: canonical T5, 12/17/29/26/3 counts, S8 reuses, permissions/class/capacity/duplicates/hooks, bad references/closed/blocked approaches, exact time boundaries and owner distinction; storage entry/exit, immutability, ordering, walkability/path/resolver invariance.
5. Run world/Oracle/Harness and affected legacy/security regressions, Ruff, strict Linux/Windows-target mypy and ten import contracts. Preserve original pin; run pin assertion only, not full release gate.
6. Consolidated review, documentation links/counters/history/scope/whitespace checks; REVIEW only when gates pass. R1A-08–20 remain TODO.

## Candidate-only contracts and tuning

`DisplayItem` is existing identity, class, catalog Category/Owner/Permission metadata, Room-representation and displayable flags, system-critical exclusion and optional opaque soft link. It creates nothing and contains no footprint. `DisplayPlacement` is relationship identity, item ID, stable `SlotKey`, active flag and optional soft link; sorted by relationship ID. It is not a DB schema or audit event. Candidate results carry explicit deterministic rejection codes, approach and immutable route, not committed changes. Supplied history/removals are evidence inputs only; no events are fabricated.

Provisional `PlacementPolicy`: 3 successful Maple placements per Maple local calendar day, using existing `core.memory.local_day` and caller-supplied UTC offset (no new calendar); owner actions do not consume this autonomous budget. Cooldown = 7 elapsed 24-hour days since any owner removal matching the item OR slot; exactly at expiry allowed. Future-dated history is invalid, not ignored. Owner bypasses autonomous cooldown/rate limits. Parameters are validated and caller replaceable; tuning is not an accepted architectural constant. History must be authoritative and complete, including removed placements, in the future adapter. No adapter is implemented.

All proposed placements first validate the supplied structural snapshot and Maple's supplied walkable position. Recovery cannot rescue a rejected proposal. Display relationships never enter blocking masks: compare mask, keep-clear cells, components, graph, routes and resolver outputs before/after. S16 initial furniture ownership remains unchanged; display IDs cannot impersonate structural host IDs.

## Evidence and review

Final focused command from `backend/` (existing external venv, no new dependencies):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m pytest tests/world tests/security/test_forbidden_apis.py tests/core/test_room.py tests/core/test_movement.py tests/runtime/test_movement_runtime.py tests/core/test_rng.py tests/core/test_memory.py tests/core/test_proposal.py tests/core/test_behavior.py tests/runtime/test_director_runtime.py tests/core/test_simulation.py::test_thirty_day_digest_is_pinned -q -o cache_dir=/private/tmp/r1a07-final-cache
```

**1,592 passed / 0 failed**, including **149 new R1A-07 cases** and 1,443 affected world/catalog/walkability/pathfinding/resolver/Oracle/Harness/security/legacy regressions. T5 zero differences; 12 slots, 17 points, 29 references, 26 distinct tiles and three same-host reuses. All nine active targets permit appropriate synthetic items; all three hooks reject both actors. Positive/negative permissions, classes, capacities, duplicate/corrupt records, owner distinction, exact cooldown/local-day limits, closed/invalid approaches and all declared-reuse failures pass. Existing dynamic-detour/last-route prevention tests pass unchanged.

Ruff lint/format PASS (two new files); strict mypy PASS on **37 files each** for Linux and Windows targets (world core, two isolated runtime readers, world tests); import-linter **10 kept / 0 broken**. Platform-specific typing is not native Windows/Linux execution or GitHub CI. Security AST/harness scans pass with no allowlist changes. No resources/build configuration changed, so wheel packaging was not repeated.

Display before/after: identical 431 walkable tiles, one component, keep-clear cells, 26 required destinations, room graph, genuine A* routes and all eight resolver outputs. Original 8,640-tick digest regression PASS unchanged at `458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917`; no Full Release Gate or unrelated simulation scenarios.

Development evidence: first 136 new cases passed; strict tuple typing and test lint corrected. A combined run found the existing resolver no-source-callers isolation contract (1 failed / 1,592 passed). Corrected implementation by introducing independent `PlacementSnapshot` with existing builders, leaving the R1A-06 test intact; strengthened exact shared-point tests. Final total supersedes intermediate runs, never sums them. No accepted-source amendment or Oracle change.

Consolidated self-review PASS: immutable inputs/results, canonical ordering, existing permission vocabulary, conservative rejection of corrupt active relationships, independent structural reconstruction, supplied-time history, owner gates and no hidden clock/RNG/I/O or production callers. Local links, counters, append-only worklog prefix, changed-file scope and whitespace checked. Counters: 20 total / 13 TODO / 0 IN PROGRESS / 0 BLOCKED / 1 REVIEW / 6 DONE / 0 DEFERRED. No unresolved owner blocker; ready for owner acceptance, not integrated or publication-authorized.

 No inaccessible design conversation is claimed as verified. No material accepted-source conflict identified during planning. Real representation adapters, audit/execution/walk-before-commit, history persistence, concurrency and owner authentication remain later responsibilities.
