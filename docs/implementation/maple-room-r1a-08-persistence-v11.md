# R1A-08 — Persistence model / schema-v11 preparation

Status: REVIEW / PENDING OWNER ACCEPTANCE, STEP 115 (2026-10-11). Verified base `82b37ea3ddcc6571062d8d8bffc9fd231bf27b60` (PR #7 merge); R1A-01–07 DONE / OWNER ACCEPTED / MERGED. Isolated branch `codex/r1a-08-persistence-v11-preparation`.

## Authority and safety gates

[Master Plan](maple-room-r1a-plan.md#r1a-08--persistence-model--schema-v11-preparation), [Final Spec §R/S and T1–T7](../architecture/maple-room-final-design-spec.md), [ADR-0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md), [ADR-0028 R1–R8](../adr/0028-activity-set-v2-events-and-schema-v4.md), ADR-0023/24/35/36/39/40 bind this rehearsal. Locked decisions precede accepted ADR rules, Final Spec and proposals. Exact tables/columns are candidate choices, not newly locked architecture.

All converter, candidate loading and synthetic fixture code belongs under proposed `backend/tests/rehearsal/`, never `backend/src`. The shipped wheel includes only `src/maplegotchi`; no src, startup, migration-registry, service, CLI, deployment or default development caller is added. Normal migrations still end at v10. The entry point accepts only a live, registered synthetic handle allocated by a factory that creates a fresh private TemporaryDirectory and births a synthetic v10 life. No path, DataDir, external connection, existing database or production copy can be supplied. Guard the handle's identity, database inode/path, link count and lifetime before any access; reject forged/expired handles. This is structural isolation and accidental-path prevention, not a sandbox against malicious Python executing in tests.

## Candidate model and implementation sequence

1. Inspect shipped v10 SQL, repository codecs, route/core invariants and backup helper; write this plan before code. Reuse synthetic runtime helpers and approved release-data parsers, not Oracle-derived geometry.
2. Synthetic harness: fresh life, demo day, aged history/counters, every location/point/null-point, in-flight route and active/suspended goals. Authoritative factory owns the connection and directory; cleanup only its own temporary files.
3. Candidate schema: append-only `layout_revision` with timestamp, author, base, catalog version/hash, canonical document and validation digest; singleton active `world_state`; immutable derived identity indexes for room-kind, host, point and slot FKs. Layout document owns geometry; indexes contain keys/kinds only. Unset themes/lighting preset values remain empty hooks, never invented colours.
4. Separate current `display_placement` relationships, item identity/slot/link/active plus optional world-event origin hook. No inventory table or fabricated items. Existing display-item metadata is supplied from its future authoritative domain and validated by R1A-07. Append-only `world_event` follows existing envelope fields; migration emits zero events. Lookup tables replace all activity CHECK lists in life_state, decision and journal_entry; legacy current location is removed, room kind references use lookups. Historical legacy point strings/payloads remain unchanged.
5. Forward-only conversion: verify v10 application ID/schema/integrity/FKs and load source through existing LifeRepository/core. Verified online backup via existing DataDir helper, no overwrite, 0600, file fsync and atomic publication; add directory fsync on POSIX. Snapshot failure prevents conversion. One BEGIN IMMEDIATE covers all DDL/data, verification and final version bump. Foreign keys are disabled before rebuild, as shipped v4 does, with explicit in-transaction foreign_key_check and restoration afterwards; no partial commit or executescript transaction splitting.
6. Rebuild only affected tables, copy all history rows/IDs and recreate existing indexes/triggers. Preserve sqlite_sequence explicitly, including high-water values above current maxima. Compare every unaffected table row and all unaffected life-state columns, not just aggregate counts, before COMMIT. Validate canonical house, S9 coverage, prevention, placement invariants and candidate state/Travel. Any failure rolls back, leaves verified backup available, never restores or repairs automatically.
7. Failure injection: snapshot, partial DDL, conversion, FK violation, candidate-state violation and pre-commit failure; invalid app/version/state/point/location/route; repeat refusal; shipped-v10 startup refuses candidate-v11. Negative isolation tests, resource/wheel exclusion and unchanged deployment/startup/source tree.
8. Focused rehearsal plus storage/migrations/snapshots/world/Oracle/security/legacy-runtime/pin regressions; Ruff, strict platform-target mypy, ten import contracts, documentation links/counters/history/whitespace; consolidated review. REVIEW only with actual successful evidence, R1A-09–20 TODO.

## Mapping and continuity

Transcribe only §R point identities, resolve coordinates from the approved catalog at rehearsal time and check all mappings against independent Spec tests. Null points use the existing canonical legacy point of the validated location/activity, rug center. Unknown/inconsistent state fails through source invariants or explicit mapping errors.

For a legacy route, require its declared endpoint to match the legacy destination and valid timing through source core. Store a zero-length grid Route at the mapped destination. Its departure equals the original arrival / activity_started_at, preserving scheduled activity start, activity end and every continuity counter. This may be a pending zero-length plan until the originally scheduled start; it introduces no invented walking/arrival/activity event. No normal movement teleport or live cutover is implemented. Stationary sources retain no travel and map directly to their point. New synthetic births map to Hall center. The current region is always derived from tile, never stored as competing state.

## Deferred activation

 Owner-held snapshot gate, rehearsal on an owner-provided production copy, registered v11 migration, real adapters/cutover/restart, legacy projection (R1A-09), live APIs/Director/renderer/default flag and post-cutover soak remain R1b/later work. No production path or data is accessed. No commit/push/PR/merge/deployment authorization.


## Implemented evidence and review (2026-10-11)

**PASS for synthetic rehearsal only.** New files: `backend/tests/rehearsal/{__init__,fixtures,v11,test_v11}.py`. No shipped source/configuration/resource/deployment/test-Oracle file changed. Candidate initial layout digest (separate from simulation pin): `8f2257f5b75f13dcb2528403cf77969e7d4e59cda443f049e5d38b9030b5eb53`. Catalog hash covers canonical type definitions; instance placements belong to the revision document. Initial candidate catalog version 1 is proposed, not a new accepted design constant.

### Synthetic fixture outcomes

All **23 fixture cases** start at v10 and end at candidate v11, with identical identity, born_at, seed, needs, counters, existing revisions, history rows/IDs and sqlite_sequence. Verification compares entire unaffected tables and every unaffected life-state column. Each backup independently loads as the original v10 life. FK/integrity and world/capability/placement invariants pass for each case. Initial world remains 44×26 / eight regions (five open) / seven doors / 28 instances / 431 walkable cells in one component. Coordinates resolve from shipped approved data; independent expectations are Final Spec §R in `test_v11.py`, not a new geometry source.

| Fixture | Destination | Revision retained | Timeline / decision / action count=max-ID | Tick / interaction / decision / action / goal counters retained |
|---|---|---|---|---|
| Fresh | Hall center (21,15) | 1 | 1 / 0 / 0 | 0 / 0 / 0 / 0 / 0 |
| Demo day (288 ticks) | Writing Desk (34,5) | 289 | 54 / 40 / 178 | 288 / 0 / 39 / 39 / 12 |
| Aged (96 ticks + 30-day gap, synthetic greet) | Library (21,4) | 99 | 28 / 17 / 77 | 97 / 1 / 16 / 16 / 6 |
| Active goal | Hall center | 2 | 2 / 1 / 1 | 0 / 0 / 0 / 0 / 1 |
| Suspended goal/action | Hall center | 2 | 2 / 1 / 1 | 0 / 0 / 0 / 0 / 1 |
| Nine explicit legacy points | Each exact §R destination | 2 each | 1 / 1 / 1 each | All zero |
| Eight null-point cases: seven locations, rug idle + walk | Canonical per location, rug center | 2 each | 1 / 1 / 1 each | All zero |
| In-flight bed route (1 ms after departure) | Bed (3,4) | 2 | 1 / 1 / 1 | All zero |

Empty histories have max-ID NULL. Every explicit point and null-location is individually parametrized, covering all eight activities. Demo/aged fixtures also raise existing sqlite_sequence high-water values above row maxima; conversion retains them exactly. Five fixture families repeated independently produce identical complete converted table contents; snapshot filenames use the existing random collision-avoidance suffix and are intentionally outside that equality.

In-flight conversion produces exactly `[[3,4,0]]`, with departure=arrival=original scheduled arrival; original activity timing/counters remain intact. No invented arrival, walking, activity or world event. Candidate state validates real Tile/Route/Travel, active-point capability/room compatibility, identity/needs/RNG, safe position and time relationships; source loads through the unchanged full LifeRepository/core before conversion and all remaining continuity fields are verified unchanged. This rehearsal loader is not a live v11 runtime or R1A-09 projection.

### Atomicity, backup and isolation

Six failure stages across fresh/aged/suspended/walking lives (24 cases): snapshot, partial DDL, conversion, FK violation, candidate-state failure, pre-commit failure. All retain original v10 table definitions/data/sequence values and restore FK mode; normal v10 runtime reopens. Every post-snapshot failure retains its verified original copy. A separate snapshot-helper exception prevents any DDL. A source modification after backup is refused before candidate DDL. Trace asserts one BEGIN IMMEDIATE, in-transaction FK checks and the version bump immediately before COMMIT. No restoration or downgrade is automatic.

Invalid app/version/missing/unknown/inconsistent state and route inputs fail explicitly. Repeat conversion refuses v11. Candidate negatives cover FK references, unsafe positions, activity/point mismatch, route/timing, hashes, canonical documents and identity-index mismatch. Immutable revision/index/event triggers reject UPDATE/DELETE. Revert contract is demonstrated by a new base-linked row leaving the original intact. Display relationships load through R1A-07 using supplied authoritative item metadata; invalid active relationships/duplicate active items reject, inactive records reserve nothing. No inventory or execution implementation.

Executable isolation: shipped registry ends at 10; normal initialization/open stays v10; normal database and runtime startup reject candidate v11 without changing its contents. Source import/entrypoint and deployment scans forbid rehearsal references; factory/converter reject external paths, connections, forged/expired handles and replaced database paths. Offline wheel built from a temporary source copy excludes tests/rehearsal and loads eight regions/28 instances with shipped schema v10 under isolated Python. No source/build/deploy edits. This is accidental-path protection with an owned synthetic factory, not a malicious-code sandbox.

### Validation commands and actual results

Run from the isolated `backend/`, existing Python 3.12 virtualenv, `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.`; caches under `/private/tmp`:

```sh
python -m pytest tests/rehearsal -q
python -m pytest tests/rehearsal tests/storage tests/deploy tests/world tests/security tests/runtime tests/core/test_room.py tests/core/test_movement.py tests/core/test_rng.py tests/core/test_memory.py tests/core/test_proposal.py tests/core/test_behavior.py tests/core/test_simulation.py::test_thirty_day_digest_is_pinned -q
ruff check --no-cache tests/rehearsal
ruff format --check --no-cache tests/rehearsal
mypy --strict --platform linux tests/rehearsal src/maplegotchi/core/world src/maplegotchi/storage src/maplegotchi/runtime/world_catalog.py src/maplegotchi/runtime/world_layout.py
mypy --strict --platform win32 tests/rehearsal src/maplegotchi/core/world src/maplegotchi/storage src/maplegotchi/runtime/world_catalog.py src/maplegotchi/runtime/world_layout.py
lint-imports --no-cache
```

**2,165 distinct passing cases / zero unresolved failures**: final **115 new cases**, plus **2,050 existing regressions** from the combined gate. Existing snapshot/restore/deploy-safety, shipped v4/v10 migrations, world/Oracle/Harness, security and legacy runtime passed. Original 8,640-tick digest assertion PASS unchanged at `458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917`. No Full Release Gate. Development: fixture enum/API/revision-trigger mistakes corrected; a combined run had 2,163 passes and one new-test missing-helper-import failure, corrected before the final new-suite rerun; subsequently strengthened full-day/aged-interaction/all-activity fixtures. Counts are distinct final coverage, never summed across repeated runs. No existing regression was changed to pass.

Ruff lint/format **PASS (4 files)**; strict mypy Linux/Windows-target **PASS (38 files each)**; **10 import contracts kept / 0 broken**. Offline packaging/isolated load PASS using cached hatchling from a temporary source copy (initial direct import/uv-cache permission attempts failed; no dependency/config/cache workaround in repository). Native Linux/Windows execution and GitHub CI are not claimed from Mac typing. POSIX file/directory durability tested locally; Windows directory-fsync limitation remains for a separately reviewed R1b native migration implementation.

Consolidated self-review: PASS. Binding source precedence preserved, proposed shapes labelled, full-row/history/sequence continuity and atomic rollback checked, zero production reachability in imports/wheel/startup, no Oracle/layout/legacy/pin changes. Documentation links/counters/history-prefix/scope and whitespace checked. R1A-08 remains REVIEW until owner acceptance/integration; 20 total / 12 TODO / 1 REVIEW / 7 DONE; R1A-09–20 TODO. No new binding conflict or owner decision is required for this rehearsal. All live adapters, placement/event writing, schema registration and owner-authorized R1b production-copy/snapshot/cutover/restore/soak work remain deferred.


## STEP 117 — Windows SQLite handle-lifecycle correction (2026-10-11)

PR #8 / [run 38113198224](https://github.com/payola469/Maplegotchi/actions/runs/38113198224), `backend (windows-latest)` / `Run uv run pytest`: 2,953 passed, 44 failed, one skipped. Traceback confirms 43 temporary-directory cleanup failures on open pre-migration snapshots and one source-database rename failure (`WinError 32`). The two snapshot-reader blocks in `test_v11.py` used `with sqlite3.connect(...)`, which controls transactions but does not close a connection: 23 conversion cases plus 20 post-snapshot rollback cases. The path-replacement test renamed the source while its fixture-owned connection remained open. The shared snapshot writer already closes its target in finally; the candidate loader opens no connection and borrows the source. No converter or production lifecycle change was needed.

Narrow correction: `fixtures.py` gives its existing source owner an explicit once-only close operation, protects setup with finally before PRAGMA/load work, and rejects closed-handle access. `test_v11.py` uses `contextlib.closing` for both snapshot readers and requests owner release before renaming the source. The test first proves closed-handle rejection, then requires the specific ownership/path-changed error after substitution, preserving the inode/path guard. Factory cleanup does not close the source again after early release. Borrowed connections remain open during converter/candidate loading. No sleeps, retries, garbage collection, skips or global connection cache added.

Five new tracked-connection cases hold strong references and assert one actual SQLite close per owned handle and no use-after-close, across success, verification exception, rollback, early release and fixture setup failure. Local focused command: `pytest tests/rehearsal tests/storage tests/security tests/deploy/test_maple_db_snapshot.py tests/deploy/test_backup_integration.py -q`: **406 passed / zero failed**, including **120 rehearsal cases**. Ruff lint/format PASS; strict Linux/Windows-target mypy PASS (38 files each); ten import contracts kept; whitespace/history-prefix/scope review PASS. Existing 2,165-case STEP 115 evidence remains historical and is not summed with these reruns.

Changed files: `backend/tests/rehearsal/fixtures.py`, `backend/tests/rehearsal/test_v11.py`, this evidence record and the append-only worklog. `v11.py`, shipped source/registry/schema constants, deployment/snapshot gate, wheel configuration, Oracle and original simulation pin remain unchanged. New native Windows CI remains PENDING until the corrective push's run is inspected and reported; local Mac and platform-target typing are insufficient to claim Windows PASS. R1A-08 remains REVIEW; no merge/deployment/production access or R1A-09 work.
