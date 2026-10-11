# R1A-09 — Legacy projection compatibility

**Status:** REVIEW / OWNER ACCEPTED / MERGE PENDING (STEP 120). Commit, normal push, PR and CI inspection authorized; merge, deployment and production activation are not authorized.

## Baseline and binding inputs

Fresh `codex/r1a-09-legacy-projection` worktree from fetched `origin/v0.2-development` at `aefa9c2ac9ca78afab57b251e768a9970e1ebe13` (PR #8 merge). R1A-08 is DONE / OWNER ACCEPTED / MERGED; earlier rehearsal/Windows-fix records retain their original context. Local-only `40f0eb7` and earlier worktrees are preserved.

Precedence: locked ADR values, accepted ADR rules, Final Design Spec, proposals. Binding sources: [Master Plan](maple-room-r1a-plan.md#r1a-09--legacy-projection-compatibility), [Final Spec §N / S14 / T7](../architecture/maple-room-final-design-spec.md), [ADR-0037 §4](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md), [ADR-0040](../adr/0040-room-view-transition-and-acceptance-gate.md), ADR-0035/0036 and existing immutable catalog, grid travel and legacy point/route contracts. Existing frontend anchors/walker are inspected only.

## Implementation sequence and gates

1. Verify baseline and contracts; record this plan before implementation. Explicit fixture/development context rebuilds existing world/catalog derivations, rather than trusting forged derived fields.
2. Pure T7 point projection: resolve actual point metadata/capabilities; reject unknown, unsupported, unavailable or closed-room sources; validate S14 against existing immutable legacy points. Cover five reading providers, five think providers, desks, bed/sofa and three Hall points with idle/walk.
3. Pure travel projection: require explicit origin point/activity semantics and validated canonical route endpoints/access; reuse legacy graph and Route with exact canonical departure/arrival. Supplied time alone determines interpolation; retain activity start/end and all presentation fields verbatim.
4. Focused positive/negative tests, then affected world/core/legacy/API/rehearsal/security regressions, simulation-pin test, Ruff, strict Linux/Windows-target mypy and ten import contracts. Review source isolation and documentation links/history/counters/whitespace.
5. Consolidated evidence and REVIEW only after passing gates. R1A-10–20 remain TODO. No source caller, serializer, Director, renderer, schema or feature-flag wiring.

## Contracts and exceptional inputs

Projection context contains existing canonical world/catalog values. Frozen point references identify instance/local point. A frozen presentation payload carries explicitly supplied activity/times, needs, reaction, expression, pose class, day phase, status and existing goal/task values. Output retains that exact payload; only legacy point, facing, position and route are derived. No state transition, mood inference, event creation or hidden state.

T7 expands `reading_spot` and `window_view | quiet_spot` by validated point capabilities, not one example object. Exact named bed/sofa/desk/Hall mappings remain distinct. Closed rooms require no mapping and are rejected explicitly if requested.

**Unmappable travel:** a positive-length grid walk can collapse to one legacy anchor (e.g. bookshelf.library_1/front_l `(21,4)` → front_r `(22,4)`, both `bookshelf.front`). Legacy `plan_route` returns None for the identical anchor; a stationary legacy Route fails its strictly increasing distance invariant. STEP 119 explicitly authorizes deterministic errors for unmappable routes: reject this case, never invent a graph loop, erase timing, or substitute Hall center. A truly zero-step source with equal departure/arrival projects to no route. Mid-edge entry without an unambiguous projected origin also rejects explicitly. These are compatibility limitations, not canonical movement changes. No legacy contract or accepted design amendment is made.

Pose is passed through as the supplied existing legacy Pose or canonical PointPose, including `sit_read`; it is not replaced with the target anchor's default pose. This fixture-only output does not change the existing frontend's activity-derived poses or claim renderer parity.

## Acceptance evidence

Final local combined run: **3,121 passed / zero failed**, including **610 new projection cases** and 2,511 existing world/Oracle/Harness/pathfinding/resolver/placement/rehearsal/security/core/runtime/API/legacy regressions. All 20 activity/provider combinations cover T7 and existing InteractionPoint/MapleState location/action invariants (S14). Five reading and five think providers are exhaustively enumerated; synthetic new providers prove capability-based expansion.

All 400 provider pairs: **334 projectable positive-duration paths**, **26 zero-step cases** (Hall idle/walk combinations included), **40 positive-duration collapsed-anchor errors**. Projectable pairs test exact departure/arrival, pending/departure/midpoint/arrival/post-arrival positions, legacy graph edges, repeated equality, unchanged source objects and identical presentation payload. Zero-step plans retain activity start/end. Invalid origins, destinations, routes through forbidden cells, missing metadata, transient entries, timing, activity pairs, capabilities, unavailable/blocked points and forged/mutable contexts reject. All supplied legacy/canonical pose classes and actual immutable goal/task facts pass through unchanged; no events are output.

Ruff lint/format **PASS (2 files)**; strict mypy **PASS (24 files each, Linux and Windows targets)**; import-linter **10 kept / zero broken**. Security AST/import allowlists pass unchanged. Initial regression run found the new module's disallowed `itertools` import; replaced it with existing allowlisted primitives, without changing tests/contracts. Narrow type findings fixed before the final successful run. Counts are final distinct coverage, not summed reruns.

Combined command (from backend; shared existing Python 3.12 environment, bytecode disabled and caches under temporary storage): `pytest -q tests/world tests/rehearsal tests/security tests/runtime tests/api <all tests/core/test_*.py except test_simulation.py> tests/core/test_simulation.py::test_thirty_day_digest_is_pinned`. Targeted mypy inputs: `src/maplegotchi/core/world`, the two existing runtime resource readers, new projection test and `tests/rehearsal`; `--strict --platform linux` and `--platform win32`. No Full Release Gate.

Only new Python files are `core/world/legacy_projection.py` and `tests/world/test_legacy_projection.py`. Executable source-caller scan, existing API/runtime/legacy/rehearsal tests and final diff establish unchanged live Director, Room API/SSE, anchors/walker, schema-v10 registry, v11 test-only boundaries and production default. No resource or build configuration changed, so wheel packaging was not repeated. The existing rehearsal isolation assertions remain green. Original simulation pin is unchanged/PASS at `458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917`. Native-platform GitHub CI is not part of this unpublished local batch.


## Historical STEP 119 consolidated review and limits

PASS for the authorized isolated projection scope. No accepted ADR/Spec/Oracle amendment, production wiring, migration, publication or later-workstream implementation. R1A-09 remains REVIEW until owner acceptance; R1A-10–20 TODO. Documentation current pointers reconcile R1A-08 integration while worklog entries stay append-only.

Unmappable collapsed-anchor and mid-edge-origin cases deliberately fail rather than change accepted legacy contracts. Supporting them visually would require a separately approved representation; this batch makes no such amendment. Canonical/legacy pose metadata is preserved, while rendering new pose classes stays outside this workstream. Caller-supplied presentation facts are not inferred or persisted. Isolation guards prevent accidental coupling, not malicious Python running in-process. Native Linux/Windows CI and production readiness are not claimed.


## STEP 120 — Owner acceptance and R1b pre-cutover integration gate

Owner explicitly ACCEPTS R1A-09 with its documented limitations. Of the 400 tested activity/provider pairs, 334 project as timed walks, 26 are zero-step cases, and 40 positive-duration pairs collapse to one legacy anchor and reject deterministically. Ambiguous mid-edge projections also reject. The owner prioritizes the new Maple Room and explicitly defers old-view compatibility expansion; no old renderer, anchor or waypoint-walker changes are authorized.

Before any R1b production cutover uses this projection, the integration must have an explicitly validated strategy preventing collapsed-anchor and ambiguous mid-edge rejections from causing unsafe or misleading behavior. This is a pre-cutover integration gate, not a requirement or authorization to enhance the old Room renderer, anchors or waypoint walker. Deterministic rejection stays intact; fabricated routes and fallback anchors are forbidden. No new compatibility implementation is authorized by STEP 120.

R1A-09 remains REVIEW / OWNER ACCEPTED / MERGE PENDING until its PR is merged. R1A-10–20 remain TODO. STEP 119's 3,121 passing cases (610 new) and static/import evidence remain the accepted implementation evidence; STEP 120 verification is recorded in the append-only worklog.
