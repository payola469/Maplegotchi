# Maple Room R1b — Migration Safety Plan

**STEP162 — R1B-01 REVIEW / ACCEPTED FOR INTEGRATION REVIEW / MERGE PENDING.** Owner accepts STEP161 local work for final publication review, subject to fresh validation, and authorizes documentation corrections, reviewed commit, normal push, PR and CI inspection for01 only. Separate owner merge approval is required. R1B-02–12 remain11TODO;0/12DONE=0%. D01–D06 OPEN; no projection strategy or future implementation approved. No runtime/test changes, schema11 registration/activation, DB migration/data access, production/paolo-core, deployment, default switch, repin, B14 orR4. Earlier dated authorization/evidence below is historical. [R1B-01 inventory](maple-room-r1b-01-contract-inventory.md).

**STEP161 — R1B-01 REVIEW / pending owner acceptance.** Verified PR22 merge baseline `edb6b128e41590d2822bdbe41c16e68d3f634206`. Bounded G2 authorizes only R1B-01 inventory, source inspection, existing-contract verification and test-case planning. No runtime or test implementation. R1B-02–12 remain 11 TODO; completion is 0/12 DONE = 0%. D01–D06 remain OPEN; no projection strategy selected. No current publication P, stage, commit, push, PR, merge, real-data access/copy/migration, production/paolo-core, deployment, default switch, repin, B14 or R4. Planning PR22 is merged; earlier dated status blocks below are historical. [R1B-01 inventory](maple-room-r1b-01-contract-inventory.md).

**STEP159,2026-10-12 — PLANNING REVIEW / OWNER ACCEPTED / MERGE PENDING.** G1 is accepted for planning-document integration only: final review, documentation corrections, commit, normal push, PR and CI inspection are authorized. Merge requires separate owner authorization. G2 implementation and G3–G7 operational/default-switch authority are NOT granted; future implementation publication P is also NOT granted. All12implementation workstreams remain TODO (0/12 DONE, including after a future planning-only merge). D01–D06 remain OPEN; no projection strategy is approved. Historical STEP158 records below describe the planning stage.

**STEP158,2026-10-12 — planning proposal only.** No database opened/copied/migrated; no host access, implementation or production readiness claimed. Baseline `3e89996216336f453b03939467e6a06cb33da3fb`. All operational steps below are **FUTURE / REQUIRES OWNER AUTHORIZATION**. [Master Plan/gates](maple-room-r1b-plan.md), [cutover](maple-room-r1b-cutover-plan.md), [risks](maple-room-r1b-risk-gates.md).

## 1. Binding discipline and implementation inventory

[ADR0037 section3](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) extends [ADR0028 R1–R8](../adr/0028-activity-set-v2-events-and-schema-v4.md): forward-only; verified automatic pre-migration copy plus owner-held snapshot; one BEGIN IMMEDIATE with capture/verification/version bump; core load; one direct final-house cutover; no fabricated timeline events; forward-fix preferred, owner restore for older schema. [ADR0023](../adr/0023-release-and-runtime.md) and [ADR0024](../adr/0024-maple-database-backup.md) remain authoritative. Exact v11 schema is proposed until its reviewed migration PR; this document does not freeze SQL or authorize activation.

Source inventory, not a query of an actual database: [storage/migrations.py](../../backend/src/maplegotchi/storage/migrations.py) ships contiguous versions1–10; PRAGMA application_id is0x4D41504C, user_version identifies schema. Version10 only adds nullable conversation_message.latency_ms. Frozen migrations1–10 must never be edited. Relevant current tables below are derived from source SQL, including v4 rebuilt names, not from production records:

| v10 tables / state | Required treatment in future v11 |
|---|---|
| maple | Preserve exact sole identity/name/born_at/life_seed; no rebirth |
| life_state | Current activity/location CHECK enums, legacy point/1000×600 route and all needs/time/RNG/action/goal/task/reaction fields; deliberately map current position/route only, preserve remaining continuity |
| interaction_ledger | Preserve complete ledger/cooldowns/order |
| timeline_event | Preserve every row/ID/timestamp/payload, append-only triggers, count/maxID/sequence; migration emits none |
| observation | Preserve entire history/IDs and indexes |
| journal_entry, journal_entry_observation, journal_state | Preserve content/provenance/history/relationships; reviewed activity lookup conversion, no historical point/payload reinterpretation |
| goal, decision, action_event | Preserve goal/suspension/action IDs, counters/priorities, complete decision/action history; reviewed activity-reference constraints, not fabricated decisions |
| document, tool_use | Preserve stored documents/reader-writer provenance; no new representations |
| memory, memory_event | Preserve state/history/IDs/immutable rules |
| daily_reflection | Preserve full history and references |
| conversation_message | Preserve full records and nullable latency_ms; never expose content in evidence |
| sqlite_sequence, indexes, triggers, FK definitions | Preserve high-water marks even above maxima; retain all unrelated definitions and validate affected replacements explicitly |

[Candidate test converter](../../backend/tests/rehearsal/v11.py) currently proposes:

| Candidate v11 structure | Status / intended contract |
|---|---|
| activity_kind, room_kind | Lookup keys plus FKs replace literal current enum constraints; adding a row alone does not authorize a new core behavior |
| layout_revision | Append-only id/created_at/author/base_revision/catalog_version/catalog_hash/document/validation_digest; immutable validated house/catalog/themes/lighting document |
| world_state | Single active_revision pointer |
| layout_host, layout_room, layout_point, layout_slot | Revision-scoped identity indexes and FK targets derived from authoritative document; no second geometry truth |
| world_event | Append-only envelope with time/revision/layout/goal/action/decision references and payload; candidate migration creates zero events |
| display_placement | Active item/host/slot/layout/link relationship and optional origin event; no inventory rows or invented items |
| rebuilt life_state | Proposed layout_revision/point_host/point_id/tx/ty/route_arrives_at and grid route; remove current location as competing authority; derive region |
| rebuilt journal_entry and decision | Activity lookup references; historical facts untouched |

This is **candidate inventory**, not production schema. D02 must review exact columns/constraints, table/JSON names, document bounds, canonicalization and hash/index consistency. Current R08 candidate defaults/catalog version1/empty theme hooks are not new locked architecture. [Synthetic tests](../../backend/tests/rehearsal/test_v11.py) prove23 fixture outcomes, owned-factory isolation and failure stages historically; they do not certify a real snapshot, durable host storage or live runtime.

## 2. Existing registration, startup and activation controls

[open_life_database](../../backend/src/maplegotchi/storage/db.py) validates database and takes an automatic pre-migration copy for an older supported file, then runs the shipped registry and loads LifeRepository. Missing data can create a first life: future production preflight must refuse a missing/wrong source path instead of permitting unintended rebirth. Adding Migration11 changes latest_version and makes an old database eligible for migration on startup. Feature flags do not prevent that once11 is shipped. Registration09 must therefore be reviewed with loader/release/startup behavior and never used as implicit production authority.

[activate_release.sh](../../deploy/install/activate_release.sh) inspects schema compatibility, refuses older-code/newer-data and requires --allow-migration for forward activation; it swaps code pointers and may install a unit, but does not start the service or itself migrate the database. It does **not independently verify a snapshot receipt**. The accepted owner protocol, current proof and permission must precede the flag; any future mechanical hardening is a reviewed implementation proposal, not an existing guarantee. Normal startup remains v10 in STEP158.

[Snapshot helper](../../deploy/backup/maple_db_snapshot.py) opens source read-only/query-only, uses SQLite online backup, private partial file, DELETE journal, integrity/application marker/identity checks, fsync and atomic publication. Its schema check accepts any migrated version>=1; it is not by itself proof of exact expected10 or correct current-life identity/history. Future readiness adds expected-version/FK/core/conservation evidence. [Automatic helper](../../backend/src/maplegotchi/storage/db.py) verifies original version and private non-overwriting pre-migration copy through DataDir. [Backup procedure](../../deploy/backup/README.md) describes restic staging; historical install/restore descriptions are not proof that today's backup exists or restores.

## 3. Snapshot/copy safety and sensitive handling

Every item is **FUTURE / REQUIRES OWNER AUTHORIZATION**:

1. G3 identifies the owner-taken consistent snapshot, approved isolated host/path, operator, exact candidate SHA, data scope and handling/retention. Do not reach paolo-core, download data or discover credentials through this plan.
2. Keep owner source copy immutable; run each conversion/fault experiment on distinct disposable descendants. Never use the production live path or the retained original as test target. Validate canonical resolved paths, ownership/ACLs and non-overlap with live/service paths; no arbitrary CLI path accepted by the existing synthetic factory. A separate reviewed adapter is needed; do not disable its existing guards.
3. Use approved isolated offline environment, no production credentials/config, live probes/providers/Discord/Brain/gateway, timers or mutation/network access. Do not use production MapleService settings to load a copied life. Copy contains potentially private conversations/journal/identity/seed; even ignored var/ is not a data-handling approval or security boundary.
4. Store raw evidence privately under approved restricted/encrypted storage; do not add DBs, SQL dumps, record bodies, tokens, seed, private paths, screenshots or full production-derived fixtures to Git/CI/chat/cloud tools. Public evidence uses redacted summaries/fingerprints; private verification may compare exact rows without printing them. Privacy/retention and later cleanup require owner approval; no silent deletion of recovery artifacts.
5. Capture source schema/application marker, integrity/FKs, identity fingerprint and conservation manifest privately; record backup file fingerprint/size/time and release/tool version. A file hash identifies bytes, not recoverability. A WAL-mode live file must not be copied alone with a generic file copy; use approved consistent SQLite backup/stopped procedure.
6. Independently verify chosen snapshot, reopen in known-compatible v10 code in the isolated environment and exercise state/core invariants. Windows tests do not prove POSIX directory fsync, permissions or production systemd boundary; require authorized target-host-compatible evidence before G4.
7. At G4 establish **current** owner-held snapshot and automatic copy readiness for exact source/release. Prior historical restore and R08 synthetic PASS are supporting design evidence only. Do not assume off-host recovery includes pre-migration/ files; ADR0028 R8 requires an explicit owner decision to copy them off-host.

## 4. Transaction, conversion and verification

**FUTURE / G2 synthetic development; G3 real-copy rehearsal; G5 production execution.** Review source prerequisites before DDL: exact expected v10, marker/identity/integrity/FKs, old loader consistency, mapping for every current point/activity/route, current source matching approved snapshot, exclusive writer/quiescence and enough filesystem capacity for database plus verified copies/WAL. No invented capacity margin; measure candidate needs and obtain owner operational approval.

Use one BEGIN IMMEDIATE for new tables/lookups/immutable initial revision, identity indexes, affected rebuilds, state mapping, FK/core verification and final user_version11 before COMMIT. FK-off if required for rebuild occurs outside the transaction, with explicit in-transaction foreign_key_check and restored connection setting on every exit; do not assume toggling inside a transaction works. No executescript splitting, nested autocommit or intermediate version bump. Snapshot publication occurs before migration and remains intact on failure. Source drift between snapshot/capture and transaction aborts rather than migrating a stale lineage.

The mapping is Final Spec sectionR; coordinates resolve through canonical data, not new hard-coded geometry. Existing point maps to new point; null uses validated canonical mapping. In-flight route becomes a zero-length plan at mapped destination, departure=arrival=original scheduled arrival; preserve activity start/end/counters and pending schedule, no fabricated arrival/walk/activity/world event. Validate behavior before and after scheduled arrival and after restart. This authorized migration exception does not allow normal teleportation. Unknown/inconsistent source or future time relationships fail closed; no arbitrary safe-tile repair of an invalid migration input.

Required in-transaction acceptance: exact identity/birth/seed; all unaffected life-state needs/times/counters/ledger/goal/task/reaction fields; every unaffected history row and reference; counts/maxIDs/sqlite_sequence high water; all unrelated indexes/triggers; FK check empty; canonical layout/catalog/hash/index agreement;8regions/5open/3closed/7corridors/431walkable;34blocked/29approach references/26distinct/3reuses; S1–S17, activity/provider/slot/recovery rules; candidate loads through future production core/repository invariants. Check identity/history again after reopen; aggregate counts alone cannot detect row mutation.

## 5. Retry, restart and failure classification

| Outcome | Evidence / allowed response — all FUTURE, owner-controlled |
|---|---|
| Snapshot/preflight failure, no transaction | Refuse conversion/start; source untouched; diagnose only under authorized scope |
| Known failure before COMMIT, verified rollback to10 | Preserve snapshots and failure evidence; previous compatible code may reopen verified10; fix candidate and repeat approved disposable rehearsal, not blind live retry |
| Connection loss/power failure/COMMIT acknowledgment unknown | Stop writers/startup; determine durable version/integrity/FKs/core load and approved lineage first; do not claim rollback or rerun11 blindly |
| Durable11, valid state, later startup/application fault | Do not rerun migration or downgrade automatically; keep safe stop, owner reviews forward-fix versus restore |
| Partial/corrupt/unrecognized schema or preserved-data mismatch | Quarantine evidence; do not repair in place or resume; owner selects verified restore/forensic action |
| Repeated startup on valid11 | Version-aware no conversion/no duplicate history/new revisions; ordinary state load only; test idempotent startup distinct from repeating converter |
| Request to migrate11 again or unsupported version | Explicit refusal/no double mapping; migration is once per approved source lineage, with owner-authorized restore/re-upgrade a separate operation |

R08 tests inject snapshot/partialDDL/conversion/FK/state/precommit failures; they do not cover every OS crash, fsync/device fault or acknowledgment-loss outcome. Future03/07/08 must add controlled kill/restart/uncertain-commit/disk-full cases on disposable data and target-compatible filesystem, never on live data to manufacture evidence. Unknown outcome is a stop condition, not a retry policy.

## 6. Recovery: code rollback versus state restore

Source [deployment rollback](../deployment.md#rollback-and-schema-compatibility), [owner restore runbook](../../deploy/install.md), ADR0028 R4–R6. These are **FUTURE / REQUIRES G6 OWNER AUTHORIZATION**:

- Intact v11/code bug: reviewed forward-fix on compatible v11 preferred. Changing current code pointer alone never restores data and old v10 code must refuse v11.
- Need v10: stop/quiesce approved service operations; retain/quarantine current maple.db and -wal/-shm together without deleting; verify owner-selected pre-v11 copy/schema/identity/integrity/FKs and old-code load; restore correct owner/private permissions to approved data path; activate compatible known v10 release only after data matches; start and run reviewed health/boundary/functional checks. Exact production commands/paths are finalized in the future migration PR/runbook; STEP158 runs none.
- Restoration loses all life since chosen snapshot. Record cutoff and explicit owner acceptance; keep quarantined newer life for analysis, do not merge its rows or counters back by ad-hoc SQL. A v11 latest-backup restore needs compatible v11 code. No automatic down-migration, restore or birth if restored file missing/invalid.

## 7. Readiness and stop conditions

Before G4/G5:01–09 evidence accepted;D01/D02/D03/D05 resolved for exact candidate; current verified dual-copy/restore evidence; source/schema/path/release identity bound; operators/window/recovery authority/data-loss decision known; no source drift; all mandatory regression/CI green; no fixture/live confusion; default Legacy proven. Any mismatch, corruption, missing/failed backup/restore, unknown commit, unsupported source mapping, unapproved runtime activation, mandatory failure or unexpected production signal stops readiness/cutover. Health HTTP200 alone cannot establish migration success. None of these current real-data/host controls is verified by STEP158.

## STEP158 continuation — Safe D01-independent preparation

D01 remains OPEN; no projection strategy is approved. Its40collapsed-anchor walking pairs and ambiguousmid-edge projections concern normal live compatibility, not the already accepted FinalSpec sectionR migration-point mapping/zero-length scheduled destination rule. Do not use this distinction to implement a live policy.

After future G1/G2 authorization,01 can complete an inventory while retaining OPEN decisions;02 can define/review D02 and isolated persistence loaders;03 can prove synthetic conversion, atomicity/failure/reopen behavior with registry10 and external-path guards intact. These tasks do not require D01 resolution and do not access production.02/03 still require their predecessors and contract approvals. This is the safe preparation lane,not an approved execution instruction.

04/05 implementation must wait for D01. Integrated06/07,real-copy08,shipped09,readiness10,cutover11 andverification12 depend on that lane and remain blocked at full scope until their prerequisites and independent approvals are satisfied. Do not treat03-only synthetic proof as sufficient for08/G3 or09/G4/G5. All12status entries remainTODO; all production controls remain unverified until authorized actual evidence.
