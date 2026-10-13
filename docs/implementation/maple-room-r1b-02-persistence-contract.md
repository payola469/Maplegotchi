# R1B-02 — v11 Persistence Contract: Stage A / D02 Proposal

**STEP168 — 2026-10-13 / DOCUMENTATION ONLY.** Owner explicitly approves the exact STEP167 ADR0035 §3/§6 and ADR0037 §1 clarification; locally recorded and validated in STEP168. **D02-F RESOLVED IN LOCAL DOCUMENTATION / NOT YET MERGED**; no claim that integration contains these amendments. All D02-A–J design directions remain accepted; D02 overall remains conditional for integration, with D02-I individual enabled-payload reviews outstanding. R1B-02 **IN PROGRESS / Stage A documentation reconciliation**; Stage B **NOT STARTED / NOT AUTHORIZED**. D01 and D03–D06 remain OPEN.01 DONE;03–12 TODO; **1/12 DONE = 8.3%**. No implementation or publication authority. Earlier dated status/evidence is historical. [Local clarification record](#step168-local-clarification).

**STEP166 — 2026-10-13 Asia/Bangkok / DOCUMENTATION ONLY.** Owner-approved design directions D02-A–J are recorded below from the owner-supplied STEP166 instruction, following the ChatGPT review. **D02 overall OPEN / CONDITIONAL:** design review complete, subject to the **D02-F ADR-0035 classification B interpretation gate**. D02-I accepts minimal hooks only; every future enabled event payload still needs explicit contract review. R1B-02 remains **IN PROGRESS / Stage A owner-reviewed**; Stage B is **NOT STARTED / NOT AUTHORIZED**. Binding ADR text is unchanged. No implementation or publication authority. D01 and D03–D06 remain OPEN. Earlier STEP164 status/evidence is historical. See [owner register and ADR gate](#d02-f-adr-gate).

**STEP164 · 2026-10-13 Asia/Bangkok · LOCAL DESIGN ONLY.** Stage A audit/design packet complete for owner review; **R1B-02 IN PROGRESS**, not full REVIEW or DONE. **D02 OPEN / owner decision pending**. The Stage A proposal below was unapproved at STEP164; STEP166 records owner design acceptance, with the D02-F condition and no implementation authority. These decisions do not amend binding ADRs or create new ADR-level locks.

## STEP185 — owner-approved SQLite compatibility clarification

**Approved policy; bounded test-only Slice 1 implementation authorized.** Shipped
schema v10 retains SQLite **>=3.38.0**. Schema v11 structural creation or activation
requires SQLite **>=3.41.0**, because the physical Unicode code-point bound CHECK
correction uses `unhex()`. Unsupported runtimes must fail closed before v11 DDL,
writes or activation side effects. This does not alter the shipped v10 runtime
guard. Test-only declarations are not an activated migration; this correction
adds preflight only to their fresh in-memory factory.

Future CI, migration/converter, runtime and deployment entry points must enforce
this requirement when separately authorized; that enforcement is not implemented
by this step. Exact linked SQLite versions in both Windows and Linux CI remain
unverified pending explicit environment evidence. The 17 inherited bounded fields
in rebuilt tables are preserved without hardening in this Slice 1 correction.
Earlier Stage A authorization/status blocks retain their historical context; no
production activation, publication or Slice 2 is authorized.

## 1. Baseline and authorization

Repository `payola469/Maplegotchi`; integration `v0.2-development`; verified PR23 merge baseline **`c26edba311f8ac01de88f4d5e3bf759e9d9a4fe7`**. PR23 merged at2026-10-12T16:53:28Z; parents `edb6b128e41590d2822bdbe41c16e68d3f634206` and `64fe82401ee1f26d6fdc6608c173372c8ee8a021`. Fetch/PR metadata and ancestry were checked before creating dedicated worktree `C:/GitHub/Maplegotchi-worktrees/r1b-02-persistence`, branch `codex/r1b-02-persistence`, at that exact merge. Nine preexisting worktrees were clean and preserved. Main stays at `3e89996216336f453b03939467e6a06cb33da3fb`; no fast-forward/reset.

STEP164 grants bounded G2 for Stage A source inspection, schema design, compatibility/conservation audit, D02 alternatives and local documentation validation only. R1B-01 is DONE / OWNER ACCEPTED / MERGED after confirmed PR23; R1B-03–12 remain TODO. Progress **1/12 DONE = 8.3%**. G2 does not grant schema-dependent implementation, publication P, real-data G3 or production G4/G5/G6. Earlier dated authorization blocks are historical.

## 2. Accepted persistence architecture

Binding sources: [Final Design Spec](../architecture/maple-room-final-design-spec.md) §§K/N/R/S/T, [ADR0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md), [ADR0035](../adr/0035-world-model.md), [ADR0036](../adr/0036-object-catalog-and-capabilities.md), [ADR0039](../adr/0039-storage-and-maple-slot-placement.md), [ADR0040](../adr/0040-room-view-transition-and-acceptance-gate.md), [ADR0023](../adr/0023-release-and-runtime.md), [ADR0024](../adr/0024-maple-database-backup.md), [ADR0028](../adr/0028-activity-set-v2-events-and-schema-v4.md) R1–R8. [Master Plan](maple-room-r1b-plan.md), [safety plan](maple-room-r1b-migration-safety.md), [cutover plan](maple-room-r1b-cutover-plan.md), [risk/gates](maple-room-r1b-risk-gates.md), [R1B-01 inventory](maple-room-r1b-01-contract-inventory.md), [R08 evidence](maple-room-r1a-08-persistence-v11.md), [R09 evidence](maple-room-r1a-09-legacy-projection.md) define scope and evidence provenance.

Accepted: one canonical layout truth; immutable append-only layout revisions, catalog identity and active pointer; stable instance/local-point/room identities; lookup structures and display hooks; grid state and derived room; no independent room graph or duplicated geometry. Direct final44×26 house,8regions/5open/3closed/7doors/431walkable, safe Hall and capability coverage remain unchanged. Exact SQL/JSON/cap are deliberately provisional in ADR0037. R1a synthetic candidate is evidence, not D02 approval.

One forward-only transaction with verified pre-migration copies, all-row conservation, verification before final version bump and commit; no fabricated birth/history or reverse migration. Existing code must refuse too-new databases. Restore is a separately authorized known-loss decision, not code-pointer rollback. Legacy remains default; B14/R4 are separate.

Historical provenance discrepancy: ADR0028 §3 historical explanatory FK-on paragraph differs from the frozen rebuild mechanism. Actual `migrations.migrate` disables FKs outside rebuild transactions; `journal_entry_observation` references rebuilt `journal_entry`. Accepted R08 and current safety plan explicitly document OFF-before-BEGIN plus in-transaction `foreign_key_check` and restored mode. Preserve R1–R8 safety requirements; do not rewrite the ADR here. Owner should review this stale mechanism commentary; any proposed normative departure would require an explicit ADR amendment before implementation.

## 3. Implemented v10 contract inventory

Method: read checked-in migration literals through AST and statically fold ordered CREATE/DROP/RENAME/ADD operations for registry1–10. No module import, SQLite connection, database file, SQL execution or migration. Independently compare life columns to repository `_STATE_COLUMNS` (34 fields plus maple_id/revision), verify every source line against the column name and account for every DDL statement. Counts describe the final checked-in schema, not production rows.

**17 application tables;213 columns;9 explicit indexes;32 triggers;11 AUTOINCREMENT tables.** `sqlite_sequence(name,seq)` is an internal table, in addition to17. SQLite-generated indexes for PK/UNIQUE constraints are represented by their exact constraints, not guessed internal names. Every table is STRICT. Inline and table constraints below include actual PK/FK/CHECK/uniqueness/nullability/defaults. TEXT UTC checks are lexical checks; core UTC/time invariants still require semantic validation.

Source schema: [migrations.py](../../backend/src/maplegotchi/storage/migrations.py); usage: [repositories.py](../../backend/src/maplegotchi/storage/repositories.py) `_STATE_COLUMNS`:269, `encode_route_path`:281, `decode_route`:286, `_state_values`:302, `LifeRepository`:356, `_load`:403, `_goal`:486; [state.py](../../backend/src/maplegotchi/core/state.py) `MapleState`:125, `birth`:336. History codecs are linked per table below. Definition line numbers refer to this baseline.

Inventory cell convention: **P0** = preserve exact stored value/type/null/text/row identity without normalization or fabricated records; **V0** = future synthetic converter must compare complete keyed source/target rows and counts, MAX(id) and sequence separately; loader must round-trip decoded values and reject invalid references. **R0** = any coercion, missing row or rewritten historical fact is data loss. Every field row specifies usage, preservation/mapping and risk/verification; table-level rules add invariants, not replacements for field coverage. Conservation coverage is a design audit, not executed conversion proof.

### v10 `maple` — 4 columns

Definition `_V1_INITIAL` at migrations.py:43; current usage [repositories.py](../../backend/src/maplegotchi/storage/repositories.py): LifeRepository._load / immutable identity.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `maple.id` — `id INTEGER PRIMARY KEY CHECK (id = 1)` | migrations.py:44 | LifeRepository._load / immutable identity; id | P0; `maple.id` unchanged | R0 | V0; existing SQL/core constraints |
| `maple.name` — `name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 32)` | migrations.py:45 | LifeRepository._load / immutable identity; name | P0; `maple.name` unchanged | R0; rebirth or changed deterministic identity | V0; existing SQL/core constraints; complete identity equality / immutable trigger refusal |
| `maple.born_at` — `born_at TEXT NOT NULL CHECK (born_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:46 | LifeRepository._load / immutable identity; born_at | P0; `maple.born_at` unchanged | R0; rebirth or changed deterministic identity | V0; existing SQL/core constraints; complete identity equality / immutable trigger refusal; UTC semantic parse and original temporal relationships |
| `maple.life_seed` — `life_seed TEXT NOT NULL CHECK (length(life_seed) = 64 AND life_seed NOT GLOB '*[^0-9a-f]*')` | migrations.py:47 | LifeRepository._load / immutable identity; life_seed | P0; `maple.life_seed` unchanged | R0; changed deterministic life identity | V0; existing SQL/core constraints; exact seed equality / immutable trigger refusal |

Table constraints (verbatim SQL content, whitespace folded):

None beyond the inline column contracts above.

### v10 `interaction_ledger` — 4 columns

Definition `_V1_INITIAL` at migrations.py:77; current usage [repositories.py](../../backend/src/maplegotchi/storage/repositories.py): LifeRepository interaction/rate-limit state.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `interaction_ledger.maple_id` — `maple_id INTEGER NOT NULL REFERENCES maple (id)` | migrations.py:78 | LifeRepository interaction/rate-limit state; maple_id | P0; `interaction_ledger.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `interaction_ledger.position` — `position INTEGER NOT NULL CHECK (position BETWEEN 0 AND 9)` | migrations.py:79 | LifeRepository interaction/rate-limit state; position | P0; `interaction_ledger.position` unchanged | R0 | V0; existing SQL/core constraints |
| `interaction_ledger.kind` — `kind TEXT NOT NULL CHECK (kind IN ('greet', 'pet'))` | migrations.py:80 | LifeRepository interaction/rate-limit state; kind | P0; `interaction_ledger.kind` unchanged | R0 | V0; existing SQL/core constraints |
| `interaction_ledger.at` — `at TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:81 | LifeRepository interaction/rate-limit state; at | P0; `interaction_ledger.at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |

Table constraints (verbatim SQL content, whitespace folded):

- `PRIMARY KEY (maple_id, position)`

### v10 `observation` — 13 columns

Definition `_V2_OBSERVATIONS` at migrations.py:124; current usage [repositories.py](../../backend/src/maplegotchi/storage/repositories.py): observations / last-seen cursors.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `observation.id` — `id INTEGER PRIMARY KEY AUTOINCREMENT` | migrations.py:125 | observations / last-seen cursors; id | P0; `observation.id` unchanged | R0 | V0; existing SQL/core constraints |
| `observation.maple_id` — `maple_id INTEGER NOT NULL REFERENCES maple (id)` | migrations.py:126 | observations / last-seen cursors; maple_id | P0; `observation.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `observation.revision` — `revision INTEGER NOT NULL CHECK (revision >= 1)` | migrations.py:127 | observations / last-seen cursors; revision | P0; `observation.revision` unchanged | R0 | V0; existing SQL/core constraints |
| `observation.tick_id` — `tick_id INTEGER NOT NULL CHECK (tick_id >= 1)` | migrations.py:128 | observations / last-seen cursors; tick_id | P0; `observation.tick_id` unchanged | R0 | V0; existing SQL/core constraints |
| `observation.observed_at` — `observed_at TEXT NOT NULL CHECK (observed_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:129 | observations / last-seen cursors; observed_at | P0; `observation.observed_at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `observation.metric` — `metric TEXT NOT NULL CHECK (metric IN ('cpu_usage', 'memory_usage', 'disk_usage', 'load_1m', 'load_5m', 'load_15m', 'cpu_count', 'temperature', 'service_state'))` | migrations.py:130 | observations / last-seen cursors; metric | P0; `observation.metric` unchanged | R0 | V0; existing SQL/core constraints |
| `observation.subject` — `subject TEXT NOT NULL CHECK (length(subject) BETWEEN 1 AND 64)` | migrations.py:133 | observations / last-seen cursors; subject | P0; `observation.subject` unchanged | R0 | V0; existing SQL/core constraints |
| `observation.status` — `status TEXT NOT NULL CHECK (status IN ('available', 'unavailable', 'unknown', 'error'))` | migrations.py:134 | observations / last-seen cursors; status | P0; `observation.status` unchanged | R0 | V0; existing SQL/core constraints |
| `observation.value` — `value REAL` | migrations.py:135 | observations / last-seen cursors; value | P0; `observation.value` unchanged | R0 | V0; existing SQL/core constraints |
| `observation.state` — `state TEXT CHECK (state IN ('active', 'reloading', 'inactive', 'failed', 'activating', 'deactivating', 'maintenance', 'refreshing'))` | migrations.py:136 | observations / last-seen cursors; state | P0; `observation.state` unchanged | R0 | V0; existing SQL/core constraints |
| `observation.unit` — `unit TEXT NOT NULL CHECK (unit IN ('percent', 'celsius', 'load', 'count', 'state'))` | migrations.py:139 | observations / last-seen cursors; unit | P0; `observation.unit` unchanged | R0 | V0; existing SQL/core constraints |
| `observation.source` — `source TEXT NOT NULL CHECK (length(source) BETWEEN 1 AND 32)` | migrations.py:140 | observations / last-seen cursors; source | P0; `observation.source` unchanged | R0 | V0; existing SQL/core constraints |
| `observation.reason` — `reason TEXT CHECK (length(reason) BETWEEN 1 AND 200)` | migrations.py:141 | observations / last-seen cursors; reason | P0; `observation.reason` unchanged | R0 | V0; existing SQL/core constraints |

Table constraints (verbatim SQL content, whitespace folded):

- `CHECK ((status = 'available') = (reason IS NULL))`
- `CHECK (status = 'available' OR (value IS NULL AND state IS NULL))`
- `CHECK (status <> 'available' OR ((value IS NULL) <> (state IS NULL)))`
- `UNIQUE (tick_id, metric, subject)`

### v10 `journal_entry_observation` — 3 columns

Definition `_V3_JOURNAL` at migrations.py:186; current usage [repositories.py](../../backend/src/maplegotchi/storage/repositories.py): journal-to-observation associations.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `journal_entry_observation.entry_id` — `entry_id INTEGER NOT NULL REFERENCES journal_entry (id)` | migrations.py:187 | journal-to-observation associations; entry_id | P0; `journal_entry_observation.entry_id` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry_observation.observation_id` — `observation_id INTEGER NOT NULL REFERENCES observation (id)` | migrations.py:188 | journal-to-observation associations; observation_id | P0; `journal_entry_observation.observation_id` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry_observation.position` — `position INTEGER NOT NULL CHECK (position >= 0)` | migrations.py:189 | journal-to-observation associations; position | P0; `journal_entry_observation.position` unchanged | R0 | V0; existing SQL/core constraints |

Table constraints (verbatim SQL content, whitespace folded):

- `PRIMARY KEY (entry_id, position)`
- `UNIQUE (entry_id, observation_id)`

### v10 `journal_state` — 9 columns

Definition `_V3_JOURNAL` at migrations.py:194; current usage [repositories.py](../../backend/src/maplegotchi/storage/repositories.py): reflection_state / journal cursor and activity.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `journal_state.maple_id` — `maple_id INTEGER PRIMARY KEY REFERENCES maple (id)` | migrations.py:195 | reflection_state / journal cursor and activity; maple_id | P0; `journal_state.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_state.journal_day` — `journal_day TEXT CHECK (journal_day GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')` | migrations.py:196 | reflection_state / journal cursor and activity; journal_day | P0; `journal_state.journal_day` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_state.daily_seen` — `daily_seen TEXT NOT NULL CHECK (json_valid(daily_seen))` | migrations.py:197 | reflection_state / journal cursor and activity; daily_seen | P0; `journal_state.daily_seen` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_state.interactions_today` — `interactions_today INTEGER NOT NULL CHECK (interactions_today >= 0)` | migrations.py:198 | reflection_state / journal cursor and activity; interactions_today | P0; `journal_state.interactions_today` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_state.notices_today` — `notices_today INTEGER NOT NULL CHECK (notices_today >= 0)` | migrations.py:199 | reflection_state / journal cursor and activity; notices_today | P0; `journal_state.notices_today` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_state.last_interaction_entry_at` — `last_interaction_entry_at TEXT CHECK (last_interaction_entry_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:200 | reflection_state / journal cursor and activity; last_interaction_entry_at | P0; `journal_state.last_interaction_entry_at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `journal_state.active_alerts` — `active_alerts TEXT NOT NULL CHECK (json_valid(active_alerts))` | migrations.py:201 | reflection_state / journal cursor and activity; active_alerts | P0; `journal_state.active_alerts` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_state.last_reflection_day` — `last_reflection_day TEXT CHECK (last_reflection_day GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')` | migrations.py:202 | reflection_state / journal cursor and activity; last_reflection_day | P0; `journal_state.last_reflection_day` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_state.milestones` — `milestones TEXT NOT NULL CHECK (json_valid(milestones))` | migrations.py:203 | reflection_state / journal cursor and activity; milestones | P0; `journal_state.milestones` unchanged | R0 | V0; existing SQL/core constraints |

Table constraints (verbatim SQL content, whitespace folded):

None beyond the inline column contracts above.

### v10 `goal` — 9 columns

Definition `_V4_AUTONOMY` at migrations.py:239; current usage [repositories.py](../../backend/src/maplegotchi/storage/repositories.py): _goal / active and suspended goals / explicit goal IDs.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `goal.id` — `id INTEGER PRIMARY KEY CHECK (id >= 1)` | migrations.py:240 | _goal / active and suspended goals / explicit goal IDs; id | P0; `goal.id` unchanged | R0 | V0; existing SQL/core constraints |
| `goal.maple_id` — `maple_id INTEGER NOT NULL REFERENCES maple (id)` | migrations.py:241 | _goal / active and suspended goals / explicit goal IDs; maple_id | P0; `goal.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `goal.revision` — `revision INTEGER NOT NULL CHECK (revision >= 1)` | migrations.py:242 | _goal / active and suspended goals / explicit goal IDs; revision | P0; `goal.revision` unchanged | R0 | V0; existing SQL/core constraints |
| `goal.goal_type` — `goal_type TEXT NOT NULL CHECK (goal_type IN ('learn', 'create', 'recover', 'reflect', 'monitor', 'socialize', 'explore', 'organize', 'maintain', 'practice', 'plan', 'wait', 'play', 'help', 'investigate', 'remember'))` | migrations.py:243 | _goal / active and suspended goals / explicit goal IDs; goal_type | P0; `goal.goal_type` unchanged | R0 | V0; existing SQL/core constraints |
| `goal.summary` — `summary TEXT NOT NULL CHECK (length(summary) BETWEEN 1 AND 120 AND instr(summary, char(10)) = 0 AND instr(summary, char(13)) = 0)` | migrations.py:244 | _goal / active and suspended goals / explicit goal IDs; summary | P0; `goal.summary` unchanged | R0 | V0; existing SQL/core constraints |
| `goal.source` — `source TEXT NOT NULL CHECK (source IN ('rule', 'external'))` | migrations.py:246 | _goal / active and suspended goals / explicit goal IDs; source | P0; `goal.source` unchanged | R0 | V0; existing SQL/core constraints |
| `goal.decision_id` — `decision_id INTEGER REFERENCES decision (id)` | migrations.py:247 | _goal / active and suspended goals / explicit goal IDs; decision_id | P0; `goal.decision_id` unchanged | R0 | V0; existing SQL/core constraints |
| `goal.started_at` — `started_at TEXT NOT NULL CHECK (started_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:248 | _goal / active and suspended goals / explicit goal IDs; started_at | P0; `goal.started_at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `goal.horizon_until` — `horizon_until TEXT NOT NULL CHECK (horizon_until GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:249 | _goal / active and suspended goals / explicit goal IDs; horizon_until | P0; `goal.horizon_until` unchanged | R0 | V0; existing SQL/core constraints |

Table constraints (verbatim SQL content, whitespace folded):

None beyond the inline column contracts above.

### v10 `decision` — 29 columns

Definition `_V4_AUTONOMY` at migrations.py:252; current usage [audit_rows.py](../../backend/src/maplegotchi/storage/audit_rows.py): insert_decision / _decode_decision.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `decision.id` — `id INTEGER PRIMARY KEY AUTOINCREMENT` | migrations.py:253 | insert_decision / _decode_decision; id | P0; `decision.id` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.maple_id` — `maple_id INTEGER NOT NULL REFERENCES maple (id)` | migrations.py:254 | insert_decision / _decode_decision; maple_id | P0; `decision.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.revision` — `revision INTEGER NOT NULL CHECK (revision >= 1)` | migrations.py:255 | insert_decision / _decode_decision; revision | P0; `decision.revision` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.at` — `at TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:256 | insert_decision / _decode_decision; at | P0; `decision.at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `decision.trigger` — `trigger TEXT NOT NULL CHECK (trigger IN ('action_completed', 're_evaluate', 'no_plan', 'overdue', 'critical'))` | migrations.py:257 | insert_decision / _decode_decision; trigger | P0; `decision.trigger` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.priority` — `priority TEXT CHECK (priority IN ('critical', 'high', 'normal', 'low'))` | migrations.py:260 | insert_decision / _decode_decision; priority | P0; `decision.priority` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.director_kind` — `director_kind TEXT NOT NULL CHECK (director_kind IN ('rule', 'external'))` | migrations.py:261 | insert_decision / _decode_decision; director_kind | P0; `decision.director_kind` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.director_name` — `director_name TEXT NOT NULL CHECK (length(director_name) BETWEEN 1 AND 32)` | migrations.py:262 | insert_decision / _decode_decision; director_name | P0; `decision.director_name` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.director_version` — `director_version TEXT NOT NULL CHECK (length(director_version) BETWEEN 1 AND 16)` | migrations.py:263 | insert_decision / _decode_decision; director_version | P0; `decision.director_version` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.context_summary` — `context_summary TEXT NOT NULL CHECK (length(context_summary) BETWEEN 1 AND 400 AND instr(context_summary, char(10)) = 0 AND instr(context_summary, char(13)) = 0)` | migrations.py:264 | insert_decision / _decode_decision; context_summary | P0; `decision.context_summary` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.proposed_goal_op` — `proposed_goal_op TEXT CHECK (proposed_goal_op IN ('keep', 'new', 'complete', 'resume', 'abandon'))` | migrations.py:266 | insert_decision / _decode_decision; proposed_goal_op | P0; `decision.proposed_goal_op` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.proposed_goal_type` — `proposed_goal_type TEXT CHECK (proposed_goal_type IN ('learn', 'create', 'recover', 'reflect', 'monitor', 'socialize', 'explore', 'organize', 'maintain', 'practice', 'plan', 'wait', 'play', 'help', 'investigate', 'remember'))` | migrations.py:268 | insert_decision / _decode_decision; proposed_goal_type | P0; `decision.proposed_goal_type` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.proposed_goal_summary` — `proposed_goal_summary TEXT CHECK (length(proposed_goal_summary) BETWEEN 1 AND 120 AND instr(proposed_goal_summary, char(10)) = 0 AND instr(proposed_goal_summary, char(13)) = 0)` | migrations.py:269 | insert_decision / _decode_decision; proposed_goal_summary | P0; `decision.proposed_goal_summary` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.proposed_horizon_minutes` — `proposed_horizon_minutes REAL` | migrations.py:271 | insert_decision / _decode_decision; proposed_horizon_minutes | P0; `decision.proposed_horizon_minutes` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.proposed_abandon_reason` — `proposed_abandon_reason TEXT CHECK (length(proposed_abandon_reason) BETWEEN 1 AND 40)` | migrations.py:272 | insert_decision / _decode_decision; proposed_abandon_reason | P0; `decision.proposed_abandon_reason` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.proposed_action` — `proposed_action TEXT CHECK (proposed_action IN ('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest', 'think'))` | migrations.py:273 | insert_decision / _decode_decision; proposed_action | P0; `decision.proposed_action` unchanged; frozen enum CHECK becomes activity_kind FK, values unchanged | R0; dropped vocabulary or changed NULL semantics | V0; existing SQL/core constraints; exact accepted activity vocabulary / FK targets |
| `decision.proposed_duration_minutes` — `proposed_duration_minutes REAL` | migrations.py:274 | insert_decision / _decode_decision; proposed_duration_minutes | P0; `decision.proposed_duration_minutes` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.proposed_reason` — `proposed_reason TEXT CHECK (length(proposed_reason) BETWEEN 1 AND 240 AND instr(proposed_reason, char(10)) = 0 AND instr(proposed_reason, char(13)) = 0)` | migrations.py:275 | insert_decision / _decode_decision; proposed_reason | P0; `decision.proposed_reason` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.verdict` — `verdict TEXT NOT NULL CHECK (verdict IN ('accepted', 'clamped', 'rejected', 'fallback', 'stale'))` | migrations.py:277 | insert_decision / _decode_decision; verdict | P0; `decision.verdict` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.reason_code` — `reason_code TEXT CHECK (length(reason_code) BETWEEN 1 AND 40)` | migrations.py:279 | insert_decision / _decode_decision; reason_code | P0; `decision.reason_code` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.clamped` — `clamped TEXT CHECK (clamped IS NULL OR json_valid(clamped))` | migrations.py:280 | insert_decision / _decode_decision; clamped | P0; `decision.clamped` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.executed_by` — `executed_by TEXT CHECK (executed_by IN ('rule', 'external'))` | migrations.py:281 | insert_decision / _decode_decision; executed_by | P0; `decision.executed_by` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.executed_reason` — `executed_reason TEXT CHECK (length(executed_reason) BETWEEN 1 AND 240 AND instr(executed_reason, char(10)) = 0 AND instr(executed_reason, char(13)) = 0)` | migrations.py:282 | insert_decision / _decode_decision; executed_reason | P0; `decision.executed_reason` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.goal_id` — `goal_id INTEGER CHECK (goal_id >= 1)` | migrations.py:284 | insert_decision / _decode_decision; goal_id | P0; `decision.goal_id` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.action_id` — `action_id INTEGER CHECK (action_id >= 0)` | migrations.py:285 | insert_decision / _decode_decision; action_id | P0; `decision.action_id` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.executed_action` — `executed_action TEXT CHECK (executed_action IN ('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest', 'think'))` | migrations.py:286 | insert_decision / _decode_decision; executed_action | P0; `decision.executed_action` unchanged; frozen enum CHECK becomes activity_kind FK, values unchanged | R0; dropped vocabulary or changed NULL semantics | V0; existing SQL/core constraints; exact accepted activity vocabulary / FK targets |
| `decision.executed_point` — `executed_point TEXT CHECK (length(executed_point) BETWEEN 1 AND 40)` | migrations.py:287 | insert_decision / _decode_decision; executed_point | P0; `decision.executed_point` unchanged; retain historical legacy text; add nullable canonical reference triple only for future new records | R0; historical fact relabeled/backfilled | V0; existing SQL/core constraints; old field byte equality and old canonical triple all NULL |
| `decision.executed_duration_minutes` — `executed_duration_minutes INTEGER CHECK (executed_duration_minutes >= 1)` | migrations.py:288 | insert_decision / _decode_decision; executed_duration_minutes | P0; `decision.executed_duration_minutes` unchanged | R0 | V0; existing SQL/core constraints |
| `decision.latency_ms` — `latency_ms INTEGER CHECK (latency_ms >= 0)` | migrations.py:289 | insert_decision / _decode_decision; latency_ms | P0; `decision.latency_ms` unchanged | R0 | V0; existing SQL/core constraints |

Table constraints (verbatim SQL content, whitespace folded):

None beyond the inline column contracts above.

### v10 `action_event` — 9 columns

Definition `_V4_AUTONOMY` at migrations.py:294; current usage [audit_rows.py](../../backend/src/maplegotchi/storage/audit_rows.py): insert_actions / action_events.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `action_event.id` — `id INTEGER PRIMARY KEY AUTOINCREMENT` | migrations.py:295 | insert_actions / action_events; id | P0; `action_event.id` unchanged | R0 | V0; existing SQL/core constraints |
| `action_event.maple_id` — `maple_id INTEGER NOT NULL REFERENCES maple (id)` | migrations.py:296 | insert_actions / action_events; maple_id | P0; `action_event.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `action_event.revision` — `revision INTEGER NOT NULL CHECK (revision >= 1)` | migrations.py:297 | insert_actions / action_events; revision | P0; `action_event.revision` unchanged | R0 | V0; existing SQL/core constraints |
| `action_event.action_id` — `action_id INTEGER NOT NULL CHECK (action_id >= 0)` | migrations.py:298 | insert_actions / action_events; action_id | P0; `action_event.action_id` unchanged | R0 | V0; existing SQL/core constraints |
| `action_event.goal_id` — `goal_id INTEGER CHECK (goal_id >= 1)` | migrations.py:299 | insert_actions / action_events; goal_id | P0; `action_event.goal_id` unchanged | R0 | V0; existing SQL/core constraints |
| `action_event.kind` — `kind TEXT NOT NULL CHECK (kind IN ('destination_selected', 'walking_started', 'walking_cancelled', 'arrived', 'activity_started', 'activity_completed', 'activity_interrupted', 'activity_resumed', 'needs_attention'))` | migrations.py:300 | insert_actions / action_events; kind | P0; `action_event.kind` unchanged | R0 | V0; existing SQL/core constraints |
| `action_event.at` — `at TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:304 | insert_actions / action_events; at | P0; `action_event.at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `action_event.priority` — `priority TEXT CHECK (priority IN ('critical', 'high', 'normal', 'low'))` | migrations.py:305 | insert_actions / action_events; priority | P0; `action_event.priority` unchanged | R0 | V0; existing SQL/core constraints |
| `action_event.payload` — `payload TEXT NOT NULL CHECK (json_valid(payload))` | migrations.py:306 | insert_actions / action_events; payload | P0; `action_event.payload` unchanged | R0 | V0; existing SQL/core constraints |

Table constraints (verbatim SQL content, whitespace folded):

None beyond the inline column contracts above.

### v10 `life_state` — 36 columns

Definition `_V4_AUTONOMY` at migrations.py:311; current usage [repositories.py](../../backend/src/maplegotchi/storage/repositories.py): _STATE_COLUMNS / _state_values / _load, MapleState.

Retain all non-world state including nullable `needs_at` fallback to last_tick, decision_due_since → reevaluate_since and action_counter → action_id aliases. Map world fields only as stated. All-or-none reaction/task/suspension/route bundles and MapleState temporal invariants remain required; no loader-generated counter increments.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `life_state.maple_id` — `maple_id INTEGER PRIMARY KEY REFERENCES maple (id)` | migrations.py:312 | _STATE_COLUMNS / _state_values / _load, MapleState; maple_id | P0; `life_state.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.revision` — `revision INTEGER NOT NULL CHECK (revision >= 1)` | migrations.py:313 | _STATE_COLUMNS / _state_values / _load, MapleState; revision | P0; `life_state.revision` unchanged | R0; rewind/extra increment | V0; existing SQL/core constraints; exact equality and next-ID/RNG replay |
| `life_state.mood` — `mood REAL NOT NULL CHECK (mood BETWEEN 0 AND 100)` | migrations.py:314 | _STATE_COLUMNS / _state_values / _load, MapleState; mood | P0; `life_state.mood` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.energy` — `energy REAL NOT NULL CHECK (energy BETWEEN 0 AND 100)` | migrations.py:315 | _STATE_COLUMNS / _state_values / _load, MapleState; energy | P0; `life_state.energy` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.curiosity` — `curiosity REAL NOT NULL CHECK (curiosity BETWEEN 0 AND 100)` | migrations.py:316 | _STATE_COLUMNS / _state_values / _load, MapleState; curiosity | P0; `life_state.curiosity` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.social` — `social REAL NOT NULL CHECK (social BETWEEN 0 AND 100)` | migrations.py:317 | _STATE_COLUMNS / _state_values / _load, MapleState; social | P0; `life_state.social` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.activity` — `activity TEXT NOT NULL CHECK (activity IN ('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest', 'think'))` | migrations.py:318 | _STATE_COLUMNS / _state_values / _load, MapleState; activity | P0; `life_state.activity` unchanged; frozen enum CHECK becomes activity_kind FK, values unchanged | R0; dropped vocabulary or changed NULL semantics | V0; existing SQL/core constraints; exact accepted activity vocabulary / FK targets |
| `life_state.location` — `location TEXT NOT NULL CHECK (location IN ('bed', 'desk', 'bookshelf', 'window', 'terminal', 'rug', 'sofa'))` | migrations.py:319 | _STATE_COLUMNS / _state_values / _load, MapleState; location | Validate old location/activity/point first; remove authoritative room string; derive room from canonical tile/region | Wrong Hall fallback or two room truths | SpecR mapping plus old source invariant; future derived-room assertions |
| `life_state.activity_started_at` — `activity_started_at TEXT NOT NULL CHECK (activity_started_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:321 | _STATE_COLUMNS / _state_values / _load, MapleState; activity_started_at | P0; `life_state.activity_started_at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `life_state.activity_until` — `activity_until TEXT NOT NULL CHECK (activity_until GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:322 | _STATE_COLUMNS / _state_values / _load, MapleState; activity_until | P0; `life_state.activity_until` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.last_tick_at` — `last_tick_at TEXT NOT NULL CHECK (last_tick_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:323 | _STATE_COLUMNS / _state_values / _load, MapleState; last_tick_at | P0; `life_state.last_tick_at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `life_state.last_updated_at` — `last_updated_at TEXT NOT NULL CHECK (last_updated_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:324 | _STATE_COLUMNS / _state_values / _load, MapleState; last_updated_at | P0; `life_state.last_updated_at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `life_state.tick_counter` — `tick_counter INTEGER NOT NULL CHECK (tick_counter >= 0)` | migrations.py:325 | _STATE_COLUMNS / _state_values / _load, MapleState; tick_counter | P0; `life_state.tick_counter` unchanged | R0; rewind/extra increment | V0; existing SQL/core constraints; exact equality and next-ID/RNG replay |
| `life_state.interaction_counter` — `interaction_counter INTEGER NOT NULL CHECK (interaction_counter >= 0)` | migrations.py:326 | _STATE_COLUMNS / _state_values / _load, MapleState; interaction_counter | P0; `life_state.interaction_counter` unchanged | R0; rewind/extra increment | V0; existing SQL/core constraints; exact equality and next-ID/RNG replay |
| `life_state.reaction_kind` — `reaction_kind TEXT CHECK (reaction_kind IN ('greet_happy', 'greet_sleepy', 'pet_happy', 'pet_sleepy'))` | migrations.py:327 | _STATE_COLUMNS / _state_values / _load, MapleState; reaction_kind | P0; `life_state.reaction_kind` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.reaction_variant` — `reaction_variant INTEGER CHECK (reaction_variant >= 0)` | migrations.py:329 | _STATE_COLUMNS / _state_values / _load, MapleState; reaction_variant | P0; `life_state.reaction_variant` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.reaction_started_at` — `reaction_started_at TEXT CHECK (reaction_started_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:330 | _STATE_COLUMNS / _state_values / _load, MapleState; reaction_started_at | P0; `life_state.reaction_started_at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `life_state.reaction_until` — `reaction_until TEXT CHECK (reaction_until GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:331 | _STATE_COLUMNS / _state_values / _load, MapleState; reaction_until | P0; `life_state.reaction_until` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.point_id` — `point_id TEXT CHECK (length(point_id) BETWEEN 1 AND 40)` | migrations.py:332 | _STATE_COLUMNS / _state_values / _load, MapleState; point_id | SpecR old point → (layout_revision,point_host,point_id); NULL uses validated canonical legacy point | Unknown point silently substituted | All9 SpecR mappings; NULL source canonical case; invalid source rejection |
| `life_state.route_departed_at` — `route_departed_at TEXT CHECK (route_departed_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:333 | _STATE_COLUMNS / _state_values / _load, MapleState; route_departed_at | P0 when no legacy route; in-flight conversion uses original scheduled arrival for zero-step depart/arrive per SpecR | Changed scheduled activity start or invented migration walk | Exact original arrival/activity timestamps; explicit allowed-difference ledger; UTC semantic parse and original temporal relationships |
| `life_state.route_from_activity` — `route_from_activity TEXT CHECK (route_from_activity IN ('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest', 'think'))` | migrations.py:334 | _STATE_COLUMNS / _state_values / _load, MapleState; route_from_activity | P0; `life_state.route_from_activity` unchanged; frozen enum CHECK becomes activity_kind FK, values unchanged | R0; dropped vocabulary or changed NULL semantics | V0; existing SQL/core constraints; exact accepted activity vocabulary / FK targets |
| `life_state.route_path` — `route_path TEXT CHECK (route_path IS NULL OR json_valid(route_path))` | migrations.py:335 | _STATE_COLUMNS / _state_values / _load, MapleState; route_path | Legacy float corner array → PROPOSED versioned grid Travel JSON; migration-only zero-step at destination, original scheduled arrival | Route/edge/timing erased or D01 accidentally selected | SpecR transition and route bundle; pending/mid-edge/arrival/restart tests; no fabricated event |
| `life_state.needs_at` — `needs_at TEXT CHECK (needs_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:336 | _STATE_COLUMNS / _state_values / _load, MapleState; needs_at | P0; `life_state.needs_at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `life_state.decision_counter` — `decision_counter INTEGER NOT NULL DEFAULT 0 CHECK (decision_counter >= 0)` | migrations.py:337 | _STATE_COLUMNS / _state_values / _load, MapleState; decision_counter | P0; `life_state.decision_counter` unchanged | R0; rewind/extra increment | V0; existing SQL/core constraints; exact equality and next-ID/RNG replay |
| `life_state.action_counter` — `action_counter INTEGER NOT NULL DEFAULT 0 CHECK (action_counter >= 0)` | migrations.py:338 | _STATE_COLUMNS / _state_values / _load, MapleState; action_counter | P0; `life_state.action_counter` unchanged | R0; rewind/extra increment | V0; existing SQL/core constraints; exact equality and next-ID/RNG replay |
| `life_state.goal_counter` — `goal_counter INTEGER NOT NULL DEFAULT 0 CHECK (goal_counter >= 0)` | migrations.py:339 | _STATE_COLUMNS / _state_values / _load, MapleState; goal_counter | P0; `life_state.goal_counter` unchanged | R0; rewind/extra increment | V0; existing SQL/core constraints; exact equality and next-ID/RNG replay |
| `life_state.action_priority` — `action_priority TEXT NOT NULL DEFAULT 'normal' CHECK (action_priority IN ('critical', 'high', 'normal', 'low'))` | migrations.py:340 | _STATE_COLUMNS / _state_values / _load, MapleState; action_priority | P0; `life_state.action_priority` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.active_goal_id` — `active_goal_id INTEGER REFERENCES goal (id)` | migrations.py:342 | _STATE_COLUMNS / _state_values / _load, MapleState; active_goal_id | P0; `life_state.active_goal_id` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.suspended_goal_id` — `suspended_goal_id INTEGER REFERENCES goal (id)` | migrations.py:343 | _STATE_COLUMNS / _state_values / _load, MapleState; suspended_goal_id | P0; `life_state.suspended_goal_id` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.suspended_action` — `suspended_action TEXT CHECK (suspended_action IN ('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest', 'think'))` | migrations.py:344 | _STATE_COLUMNS / _state_values / _load, MapleState; suspended_action | P0; `life_state.suspended_action` unchanged; frozen enum CHECK becomes activity_kind FK, values unchanged | R0; dropped vocabulary or changed NULL semantics | V0; existing SQL/core constraints; exact accepted activity vocabulary / FK targets |
| `life_state.decision_due_since` — `decision_due_since TEXT CHECK (decision_due_since GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:345 | _STATE_COLUMNS / _state_values / _load, MapleState; decision_due_since | P0; `life_state.decision_due_since` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `life_state.critical_since` — `critical_since TEXT CHECK (critical_since GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:521 | _STATE_COLUMNS / _state_values / _load, MapleState; critical_since | P0; `life_state.critical_since` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `life_state.task_tool` — `task_tool TEXT CHECK (task_tool IN ('reader', 'writer'))` | migrations.py:527 | _STATE_COLUMNS / _state_values / _load, MapleState; task_tool | P0; `life_state.task_tool` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.task_target` — `task_target TEXT CHECK (length(task_target) BETWEEN 1 AND 60)` | migrations.py:529 | _STATE_COLUMNS / _state_values / _load, MapleState; task_target | P0; `life_state.task_target` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.task_title` — `task_title TEXT CHECK (length(task_title) BETWEEN 1 AND 80)` | migrations.py:531 | _STATE_COLUMNS / _state_values / _load, MapleState; task_title | P0; `life_state.task_title` unchanged | R0 | V0; existing SQL/core constraints |
| `life_state.task_category` — `task_category TEXT CHECK (length(task_category) BETWEEN 1 AND 40)` | migrations.py:533 | _STATE_COLUMNS / _state_values / _load, MapleState; task_category | P0; `life_state.task_category` unchanged | R0 | V0; existing SQL/core constraints |

Table constraints (verbatim SQL content, whitespace folded):

- `CHECK ((reaction_kind IS NULL) = (reaction_variant IS NULL) AND (reaction_kind IS NULL) = (reaction_started_at IS NULL) AND (reaction_kind IS NULL) = (reaction_until IS NULL))`
- `CHECK ((route_path IS NULL) = (route_departed_at IS NULL) AND (route_path IS NULL) = (route_from_activity IS NULL))`
- `CHECK (active_goal_id IS NULL OR suspended_goal_id IS NULL OR active_goal_id <> suspended_goal_id)`
- `CHECK ((suspended_goal_id IS NULL) = (suspended_action IS NULL))`

### v10 `timeline_event` — 7 columns

Definition `_V4_AUTONOMY` at migrations.py:391; current usage [repositories.py](../../backend/src/maplegotchi/storage/repositories.py): events / unique birth record.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `timeline_event.id` — `id INTEGER PRIMARY KEY AUTOINCREMENT` | migrations.py:392 | events / unique birth record; id | P0; `timeline_event.id` unchanged | R0 | V0; existing SQL/core constraints |
| `timeline_event.maple_id` — `maple_id INTEGER NOT NULL REFERENCES maple (id)` | migrations.py:393 | events / unique birth record; maple_id | P0; `timeline_event.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `timeline_event.revision` — `revision INTEGER NOT NULL CHECK (revision >= 1)` | migrations.py:394 | events / unique birth record; revision | P0; `timeline_event.revision` unchanged | R0 | V0; existing SQL/core constraints |
| `timeline_event.tick_id` — `tick_id INTEGER CHECK (tick_id >= 1)` | migrations.py:395 | events / unique birth record; tick_id | P0; `timeline_event.tick_id` unchanged | R0 | V0; existing SQL/core constraints |
| `timeline_event.kind` — `kind TEXT NOT NULL CHECK (kind IN ('born', 'activity_changed', 'interaction_accepted', 'downtime_gap', 'goal_started', 'goal_suspended', 'goal_resumed', 'goal_completed', 'goal_abandoned'))` | migrations.py:396 | events / unique birth record; kind | P0; `timeline_event.kind` unchanged | R0 | V0; existing SQL/core constraints |
| `timeline_event.at` — `at TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:400 | events / unique birth record; at | P0; `timeline_event.at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `timeline_event.payload` — `payload TEXT NOT NULL CHECK (json_valid(payload))` | migrations.py:401 | events / unique birth record; payload | P0; `timeline_event.payload` unchanged | R0 | V0; existing SQL/core constraints |

Table constraints (verbatim SQL content, whitespace folded):

None beyond the inline column contracts above.

### v10 `journal_entry` — 16 columns

Definition `_V4_AUTONOMY` at migrations.py:421; current usage [repositories.py](../../backend/src/maplegotchi/storage/repositories.py): journal history.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `journal_entry.id` — `id INTEGER PRIMARY KEY AUTOINCREMENT` | migrations.py:422 | journal history; id | P0; `journal_entry.id` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry.maple_id` — `maple_id INTEGER NOT NULL REFERENCES maple (id)` | migrations.py:423 | journal history; maple_id | P0; `journal_entry.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry.revision` — `revision INTEGER NOT NULL CHECK (revision >= 1)` | migrations.py:424 | journal history; revision | P0; `journal_entry.revision` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry.tick_id` — `tick_id INTEGER CHECK (tick_id >= 1)` | migrations.py:425 | journal history; tick_id | P0; `journal_entry.tick_id` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry.created_at` — `created_at TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:426 | journal history; created_at | P0; `journal_entry.created_at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `journal_entry.category` — `category TEXT NOT NULL CHECK (category IN ('daily_life', 'server_notice', 'interaction', 'reflection', 'milestone'))` | migrations.py:427 | journal history; category | P0; `journal_entry.category` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry.trigger_kind` — `trigger_kind TEXT NOT NULL CHECK (trigger_kind IN ('activity', 'interaction', 'server_problem', 'server_recovery', 'daily_reflection', 'milestone'))` | migrations.py:429 | journal history; trigger_kind | P0; `journal_entry.trigger_kind` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry.topic` — `topic TEXT NOT NULL CHECK (length(topic) BETWEEN 1 AND 80)` | migrations.py:432 | journal history; topic | P0; `journal_entry.topic` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry.text` — `text TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 240 AND instr(text, char(10)) = 0 AND instr(text, char(13)) = 0)` | migrations.py:433 | journal history; text | P0; `journal_entry.text` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry.importance` — `importance TEXT NOT NULL CHECK (importance IN ('low', 'normal', 'high'))` | migrations.py:436 | journal history; importance | P0; `journal_entry.importance` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry.brain_kind` — `brain_kind TEXT NOT NULL CHECK (brain_kind IN ('rule', 'external'))` | migrations.py:437 | journal history; brain_kind | P0; `journal_entry.brain_kind` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry.brain_name` — `brain_name TEXT NOT NULL CHECK (length(brain_name) BETWEEN 1 AND 32)` | migrations.py:438 | journal history; brain_name | P0; `journal_entry.brain_name` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry.brain_version` — `brain_version TEXT NOT NULL CHECK (length(brain_version) BETWEEN 1 AND 16)` | migrations.py:439 | journal history; brain_version | P0; `journal_entry.brain_version` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry.template_id` — `template_id TEXT NOT NULL CHECK (length(template_id) BETWEEN 1 AND 80)` | migrations.py:440 | journal history; template_id | P0; `journal_entry.template_id` unchanged | R0 | V0; existing SQL/core constraints |
| `journal_entry.activity` — `activity TEXT NOT NULL CHECK (activity IN ('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest', 'think'))` | migrations.py:441 | journal history; activity | P0; `journal_entry.activity` unchanged; frozen enum CHECK becomes activity_kind FK, values unchanged | R0; dropped vocabulary or changed NULL semantics | V0; existing SQL/core constraints; exact accepted activity vocabulary / FK targets |
| `journal_entry.expression` — `expression TEXT NOT NULL CHECK (expression IN ('calm', 'happy', 'curious', 'sleepy', 'focused'))` | migrations.py:442 | journal history; expression | P0; `journal_entry.expression` unchanged | R0 | V0; existing SQL/core constraints |

Table constraints (verbatim SQL content, whitespace folded):

None beyond the inline column contracts above.

### v10 `document` — 10 columns

Definition `_V6_TOOLS` at migrations.py:536; current usage [tool_rows.py](../../backend/src/maplegotchi/storage/tool_rows.py): _document / documents / document.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `document.id` — `id INTEGER PRIMARY KEY AUTOINCREMENT` | migrations.py:537 | _document / documents / document; id | P0; `document.id` unchanged | R0 | V0; existing SQL/core constraints |
| `document.maple_id` — `maple_id INTEGER NOT NULL REFERENCES maple (id)` | migrations.py:538 | _document / documents / document; maple_id | P0; `document.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `document.revision` — `revision INTEGER NOT NULL CHECK (revision >= 1)` | migrations.py:539 | _document / documents / document; revision | P0; `document.revision` unchanged | R0 | V0; existing SQL/core constraints |
| `document.kind` — `kind TEXT NOT NULL CHECK (kind IN ('note', 'summary', 'reflection', 'research'))` | migrations.py:540 | _document / documents / document; kind | P0; `document.kind` unchanged | R0 | V0; existing SQL/core constraints |
| `document.title` — `title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 80 AND instr(title, char(10)) = 0)` | migrations.py:541 | _document / documents / document; title | P0; `document.title` unchanged | R0 | V0; existing SQL/core constraints |
| `document.body` — `body TEXT NOT NULL CHECK (length(body) BETWEEN 1 AND 4000)` | migrations.py:543 | _document / documents / document; body | P0; `document.body` unchanged | R0 | V0; existing SQL/core constraints |
| `document.created_at` — `created_at TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:544 | _document / documents / document; created_at | P0; `document.created_at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `document.action_id` — `action_id INTEGER NOT NULL CHECK (action_id >= 0)` | migrations.py:545 | _document / documents / document; action_id | P0; `document.action_id` unchanged | R0 | V0; existing SQL/core constraints |
| `document.goal_id` — `goal_id INTEGER CHECK (goal_id >= 1)` | migrations.py:546 | _document / documents / document; goal_id | P0; `document.goal_id` unchanged | R0 | V0; existing SQL/core constraints |
| `document.sources` — `sources TEXT NOT NULL CHECK (json_valid(sources))` | migrations.py:547 | _document / documents / document; sources | P0; `document.sources` unchanged | R0 | V0; existing SQL/core constraints |

Table constraints (verbatim SQL content, whitespace folded):

None beyond the inline column contracts above.

### v10 `tool_use` — 15 columns

Definition `_V6_TOOLS` at migrations.py:550; current usage [tool_rows.py](../../backend/src/maplegotchi/storage/tool_rows.py): insert_tools / tool_uses.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `tool_use.id` — `id INTEGER PRIMARY KEY AUTOINCREMENT` | migrations.py:551 | insert_tools / tool_uses; id | P0; `tool_use.id` unchanged | R0 | V0; existing SQL/core constraints |
| `tool_use.maple_id` — `maple_id INTEGER NOT NULL REFERENCES maple (id)` | migrations.py:552 | insert_tools / tool_uses; maple_id | P0; `tool_use.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `tool_use.revision` — `revision INTEGER NOT NULL CHECK (revision >= 1)` | migrations.py:553 | insert_tools / tool_uses; revision | P0; `tool_use.revision` unchanged | R0 | V0; existing SQL/core constraints |
| `tool_use.at` — `at TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:554 | insert_tools / tool_uses; at | P0; `tool_use.at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `tool_use.action_id` — `action_id INTEGER NOT NULL CHECK (action_id >= 0)` | migrations.py:555 | insert_tools / tool_uses; action_id | P0; `tool_use.action_id` unchanged | R0 | V0; existing SQL/core constraints |
| `tool_use.goal_id` — `goal_id INTEGER CHECK (goal_id >= 1)` | migrations.py:556 | insert_tools / tool_uses; goal_id | P0; `tool_use.goal_id` unchanged | R0 | V0; existing SQL/core constraints |
| `tool_use.tool` — `tool TEXT NOT NULL CHECK (tool IN ('reader', 'writer'))` | migrations.py:557 | insert_tools / tool_uses; tool | P0; `tool_use.tool` unchanged | R0 | V0; existing SQL/core constraints |
| `tool_use.operation` — `operation TEXT NOT NULL CHECK (operation IN ('read_started', 'read_completed', 'read_failed', 'write_started', 'write_completed', 'write_failed'))` | migrations.py:558 | insert_tools / tool_uses; operation | P0; `tool_use.operation` unchanged | R0 | V0; existing SQL/core constraints |
| `tool_use.target` — `target TEXT NOT NULL CHECK (length(target) BETWEEN 1 AND 60)` | migrations.py:561 | insert_tools / tool_uses; target | P0; `tool_use.target` unchanged | R0 | V0; existing SQL/core constraints |
| `tool_use.title` — `title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 80)` | migrations.py:562 | insert_tools / tool_uses; title | P0; `tool_use.title` unchanged | R0 | V0; existing SQL/core constraints |
| `tool_use.category` — `category TEXT NOT NULL CHECK (length(category) BETWEEN 1 AND 40)` | migrations.py:563 | insert_tools / tool_uses; category | P0; `tool_use.category` unchanged | R0 | V0; existing SQL/core constraints |
| `tool_use.status` — `status TEXT NOT NULL CHECK (status IN ('success', 'failure'))` | migrations.py:564 | insert_tools / tool_uses; status | P0; `tool_use.status` unchanged | R0 | V0; existing SQL/core constraints |
| `tool_use.detail` — `detail TEXT CHECK (length(detail) BETWEEN 1 AND 200 AND instr(detail, char(10)) = 0)` | migrations.py:565 | insert_tools / tool_uses; detail | P0; `tool_use.detail` unchanged | R0 | V0; existing SQL/core constraints |
| `tool_use.chars` — `chars INTEGER CHECK (chars >= 0)` | migrations.py:567 | insert_tools / tool_uses; chars | P0; `tool_use.chars` unchanged | R0 | V0; existing SQL/core constraints |
| `tool_use.document_id` — `document_id INTEGER REFERENCES document (id)` | migrations.py:568 | insert_tools / tool_uses; document_id | P0; `tool_use.document_id` unchanged | R0 | V0; existing SQL/core constraints |

Table constraints (verbatim SQL content, whitespace folded):

None beyond the inline column contracts above.

### v10 `memory` — 13 columns

Definition `_V7_MEMORY` at migrations.py:588; current usage [memory_rows.py](../../backend/src/maplegotchi/storage/memory_rows.py): apply_changes / _memory / memories.

Rows are not wholly append-only: preserve mutable tier/status and other mutable facts too; identity fields kind/text/created_at/key are protected. No historical rewrite or delete is introduced.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `memory.id` — `id INTEGER PRIMARY KEY AUTOINCREMENT` | migrations.py:589 | apply_changes / _memory / memories; id | P0; `memory.id` unchanged | R0 | V0; existing SQL/core constraints |
| `memory.maple_id` — `maple_id INTEGER NOT NULL REFERENCES maple (id)` | migrations.py:590 | apply_changes / _memory / memories; maple_id | P0; `memory.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `memory.revision` — `revision INTEGER NOT NULL CHECK (revision >= 1)` | migrations.py:591 | apply_changes / _memory / memories; revision | P0; `memory.revision` unchanged | R0 | V0; existing SQL/core constraints |
| `memory.kind` — `kind TEXT NOT NULL CHECK (kind IN ('event', 'goal_outcome', 'reading', 'writing', 'interaction', 'conversation', 'knowledge', 'moment', 'preference'))` | migrations.py:592 | apply_changes / _memory / memories; kind | P0; `memory.kind` unchanged | R0 | V0; existing SQL/core constraints |
| `memory.tier` — `tier TEXT NOT NULL CHECK (tier IN ('short_term', 'long_term', 'archive'))` | migrations.py:595 | apply_changes / _memory / memories; tier | P0; `memory.tier` unchanged | R0 | V0; existing SQL/core constraints |
| `memory.status` — `status TEXT NOT NULL CHECK (status IN ('active', 'candidate', 'accepted', 'rejected'))` | migrations.py:596 | apply_changes / _memory / memories; status | P0; `memory.status` unchanged | R0 | V0; existing SQL/core constraints |
| `memory.key` — `key TEXT CHECK (length(key) BETWEEN 1 AND 120)` | migrations.py:598 | apply_changes / _memory / memories; key | P0; `memory.key` unchanged | R0 | V0; existing SQL/core constraints |
| `memory.text` — `text TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 240 AND instr(text, char(10)) = 0)` | migrations.py:599 | apply_changes / _memory / memories; text | P0; `memory.text` unchanged | R0 | V0; existing SQL/core constraints |
| `memory.source` — `source TEXT CHECK (length(source) BETWEEN 1 AND 60)` | migrations.py:601 | apply_changes / _memory / memories; source | P0; `memory.source` unchanged | R0 | V0; existing SQL/core constraints |
| `memory.importance` — `importance REAL NOT NULL CHECK (importance BETWEEN 0 AND 1)` | migrations.py:602 | apply_changes / _memory / memories; importance | P0; `memory.importance` unchanged | R0 | V0; existing SQL/core constraints |
| `memory.evidence_days` — `evidence_days TEXT NOT NULL CHECK (json_valid(evidence_days))` | migrations.py:603 | apply_changes / _memory / memories; evidence_days | P0; `memory.evidence_days` unchanged | R0 | V0; existing SQL/core constraints |
| `memory.created_at` — `created_at TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:604 | apply_changes / _memory / memories; created_at | P0; `memory.created_at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `memory.last_seen_at` — `last_seen_at TEXT NOT NULL CHECK (last_seen_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:605 | apply_changes / _memory / memories; last_seen_at | P0; `memory.last_seen_at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |

Table constraints (verbatim SQL content, whitespace folded):

- `CHECK ((kind = 'preference') = (status <> 'active'))`

### v10 `memory_event` — 7 columns

Definition `_V7_MEMORY` at migrations.py:621; current usage [memory_rows.py](../../backend/src/maplegotchi/storage/memory_rows.py): memory_events / immutable audit.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `memory_event.id` — `id INTEGER PRIMARY KEY AUTOINCREMENT` | migrations.py:622 | memory_events / immutable audit; id | P0; `memory_event.id` unchanged | R0 | V0; existing SQL/core constraints |
| `memory_event.maple_id` — `maple_id INTEGER NOT NULL REFERENCES maple (id)` | migrations.py:623 | memory_events / immutable audit; maple_id | P0; `memory_event.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `memory_event.revision` — `revision INTEGER NOT NULL CHECK (revision >= 1)` | migrations.py:624 | memory_events / immutable audit; revision | P0; `memory_event.revision` unchanged | R0 | V0; existing SQL/core constraints |
| `memory_event.memory_id` — `memory_id INTEGER NOT NULL REFERENCES memory (id)` | migrations.py:625 | memory_events / immutable audit; memory_id | P0; `memory_event.memory_id` unchanged | R0 | V0; existing SQL/core constraints |
| `memory_event.kind` — `kind TEXT NOT NULL CHECK (kind IN ('created', 'reinforced', 'promoted', 'archived', 'confirmed', 'rejected'))` | migrations.py:626 | memory_events / immutable audit; kind | P0; `memory_event.kind` unchanged | R0 | V0; existing SQL/core constraints |
| `memory_event.at` — `at TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:628 | memory_events / immutable audit; at | P0; `memory_event.at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `memory_event.detail` — `detail TEXT CHECK (length(detail) BETWEEN 1 AND 200)` | migrations.py:629 | memory_events / immutable audit; detail | P0; `memory_event.detail` unchanged | R0 | V0; existing SQL/core constraints |

Table constraints (verbatim SQL content, whitespace folded):

None beyond the inline column contracts above.

### v10 `daily_reflection` — 15 columns

Definition `_V8_DAILY` at migrations.py:641; current usage [daily_rows.py](../../backend/src/maplegotchi/storage/daily_rows.py): insert_reflection / _decode / reflection_for.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `daily_reflection.id` — `id INTEGER PRIMARY KEY AUTOINCREMENT` | migrations.py:642 | insert_reflection / _decode / reflection_for; id | P0; `daily_reflection.id` unchanged | R0 | V0; existing SQL/core constraints |
| `daily_reflection.maple_id` — `maple_id INTEGER NOT NULL REFERENCES maple (id)` | migrations.py:643 | insert_reflection / _decode / reflection_for; maple_id | P0; `daily_reflection.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `daily_reflection.revision` — `revision INTEGER NOT NULL CHECK (revision >= 1)` | migrations.py:644 | insert_reflection / _decode / reflection_for; revision | P0; `daily_reflection.revision` unchanged | R0 | V0; existing SQL/core constraints |
| `daily_reflection.day` — `day TEXT NOT NULL UNIQUE CHECK (day GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')` | migrations.py:645 | insert_reflection / _decode / reflection_for; day | P0; `daily_reflection.day` unchanged | R0 | V0; existing SQL/core constraints |
| `daily_reflection.created_at` — `created_at TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:646 | insert_reflection / _decode / reflection_for; created_at | P0; `daily_reflection.created_at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `daily_reflection.recovered` — `recovered INTEGER NOT NULL CHECK (recovered IN (0, 1))` | migrations.py:647 | insert_reflection / _decode / reflection_for; recovered | P0; `daily_reflection.recovered` unchanged | R0 | V0; existing SQL/core constraints |
| `daily_reflection.summary` — `summary TEXT NOT NULL CHECK (length(summary) BETWEEN 1 AND 1000)` | migrations.py:648 | insert_reflection / _decode / reflection_for; summary | P0; `daily_reflection.summary` unchanged | R0 | V0; existing SQL/core constraints |
| `daily_reflection.learned` — `learned TEXT NOT NULL CHECK (json_valid(learned))` | migrations.py:649 | insert_reflection / _decode / reflection_for; learned | P0; `daily_reflection.learned` unchanged | R0 | V0; existing SQL/core constraints |
| `daily_reflection.moments` — `moments TEXT NOT NULL CHECK (json_valid(moments))` | migrations.py:650 | insert_reflection / _decode / reflection_for; moments | P0; `daily_reflection.moments` unchanged | R0 | V0; existing SQL/core constraints |
| `daily_reflection.memory_candidates` — `memory_candidates TEXT NOT NULL CHECK (json_valid(memory_candidates))` | migrations.py:651 | insert_reflection / _decode / reflection_for; memory_candidates | P0; `daily_reflection.memory_candidates` unchanged | R0 | V0; existing SQL/core constraints |
| `daily_reflection.promoted` — `promoted TEXT NOT NULL CHECK (json_valid(promoted))` | migrations.py:652 | insert_reflection / _decode / reflection_for; promoted | P0; `daily_reflection.promoted` unchanged | R0 | V0; existing SQL/core constraints |
| `daily_reflection.preference_candidates` — `preference_candidates TEXT NOT NULL CHECK (json_valid(preference_candidates))` | migrations.py:653 | insert_reflection / _decode / reflection_for; preference_candidates | P0; `daily_reflection.preference_candidates` unchanged | R0 | V0; existing SQL/core constraints |
| `daily_reflection.intent_type` — `intent_type TEXT NOT NULL CHECK (intent_type IN ('learn', 'create', 'recover', 'reflect', 'monitor', 'socialize', 'explore', 'organize', 'maintain', 'practice', 'plan', 'wait', 'play', 'help', 'investigate', 'remember'))` | migrations.py:654 | insert_reflection / _decode / reflection_for; intent_type | P0; `daily_reflection.intent_type` unchanged | R0 | V0; existing SQL/core constraints |
| `daily_reflection.intent_summary` — `intent_summary TEXT NOT NULL CHECK (length(intent_summary) BETWEEN 1 AND 120)` | migrations.py:658 | insert_reflection / _decode / reflection_for; intent_summary | P0; `daily_reflection.intent_summary` unchanged | R0 | V0; existing SQL/core constraints |
| `daily_reflection.needs` — `needs TEXT NOT NULL CHECK (json_valid(needs))` | migrations.py:659 | insert_reflection / _decode / reflection_for; needs | P0; `daily_reflection.needs` unchanged | R0 | V0; existing SQL/core constraints |

Table constraints (verbatim SQL content, whitespace folded):

None beyond the inline column contracts above.

### v10 `conversation_message` — 14 columns

Definition `_V9_CONVERSATION` at migrations.py:671; current usage [conversation_rows.py](../../backend/src/maplegotchi/storage/conversation_rows.py): insert_message / _decode / by_external_id / reply_to.

| Field / SQL contract | Source definition | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|---|
| `conversation_message.id` — `id INTEGER PRIMARY KEY AUTOINCREMENT` | migrations.py:672 | insert_message / _decode / by_external_id / reply_to; id | P0; `conversation_message.id` unchanged | R0 | V0; existing SQL/core constraints |
| `conversation_message.maple_id` — `maple_id INTEGER NOT NULL REFERENCES maple (id)` | migrations.py:673 | insert_message / _decode / by_external_id / reply_to; maple_id | P0; `conversation_message.maple_id` unchanged | R0 | V0; existing SQL/core constraints |
| `conversation_message.revision` — `revision INTEGER NOT NULL CHECK (revision >= 1)` | migrations.py:674 | insert_message / _decode / by_external_id / reply_to; revision | P0; `conversation_message.revision` unchanged | R0 | V0; existing SQL/core constraints |
| `conversation_message.at` — `at TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')` | migrations.py:675 | insert_message / _decode / by_external_id / reply_to; at | P0; `conversation_message.at` unchanged | R0 | V0; existing SQL/core constraints; UTC semantic parse and original temporal relationships |
| `conversation_message.channel` — `channel TEXT NOT NULL CHECK (channel IN ('discord'))` | migrations.py:676 | insert_message / _decode / by_external_id / reply_to; channel | P0; `conversation_message.channel` unchanged | R0 | V0; existing SQL/core constraints |
| `conversation_message.direction` — `direction TEXT NOT NULL CHECK (direction IN ('in', 'out'))` | migrations.py:677 | insert_message / _decode / by_external_id / reply_to; direction | P0; `conversation_message.direction` unchanged | R0 | V0; existing SQL/core constraints |
| `conversation_message.speaker` — `speaker TEXT NOT NULL CHECK (speaker IN ('paolo', 'maple'))` | migrations.py:678 | insert_message / _decode / by_external_id / reply_to; speaker | P0; `conversation_message.speaker` unchanged | R0 | V0; existing SQL/core constraints |
| `conversation_message.external_id` — `external_id TEXT CHECK (length(external_id) BETWEEN 1 AND 64)` | migrations.py:679 | insert_message / _decode / by_external_id / reply_to; external_id | P0; `conversation_message.external_id` unchanged | R0 | V0; existing SQL/core constraints |
| `conversation_message.reply_to` — `reply_to INTEGER REFERENCES conversation_message (id)` | migrations.py:680 | insert_message / _decode / by_external_id / reply_to; reply_to | P0; `conversation_message.reply_to` unchanged | R0 | V0; existing SQL/core constraints |
| `conversation_message.text` — `text TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 2000)` | migrations.py:681 | insert_message / _decode / by_external_id / reply_to; text | P0; `conversation_message.text` unchanged | R0 | V0; existing SQL/core constraints |
| `conversation_message.replier_kind` — `replier_kind TEXT CHECK (replier_kind IN ('rule', 'external'))` | migrations.py:682 | insert_message / _decode / by_external_id / reply_to; replier_kind | P0; `conversation_message.replier_kind` unchanged | R0 | V0; existing SQL/core constraints |
| `conversation_message.replier_name` — `replier_name TEXT CHECK (length(replier_name) BETWEEN 1 AND 32)` | migrations.py:683 | insert_message / _decode / by_external_id / reply_to; replier_name | P0; `conversation_message.replier_name` unchanged | R0 | V0; existing SQL/core constraints |
| `conversation_message.fallback_code` — `fallback_code TEXT CHECK (length(fallback_code) BETWEEN 1 AND 40)` | migrations.py:684 | insert_message / _decode / by_external_id / reply_to; fallback_code | P0; `conversation_message.fallback_code` unchanged | R0 | V0; existing SQL/core constraints |
| `conversation_message.latency_ms` — `latency_ms INTEGER CHECK (latency_ms BETWEEN 0 AND 600000)` | migrations.py:703 | insert_message / _decode / by_external_id / reply_to; latency_ms | P0; `conversation_message.latency_ms` unchanged | R0 | V0; existing SQL/core constraints |

Table constraints (verbatim SQL content, whitespace folded):

- `CHECK ((direction = 'in') = (speaker = 'paolo'))`
- `CHECK ((direction = 'in') = (external_id IS NOT NULL))`
- `CHECK ((direction = 'out') = (replier_kind IS NOT NULL))`

### Explicit indexes and triggers

Every surviving object: source definition, usage, conservation/mapping, risk and verification. Existing indexes/triggers on rebuilt tables must be recreated unchanged except the reviewed enum-to-FK substitution and new world invariants.

| Object | Source / exact definition | Current usage | Preservation / v11 mapping | Risk | Verification |
|---|---|---|---|---|---|
| `maple_immutable_update` (trigger, `maple`) | migrations.py:99; `CREATE TRIGGER maple_immutable_update BEFORE UPDATE ON maple BEGIN SELECT RAISE(ABORT, 'maple identity is immutable'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `maple_immutable_delete` (trigger, `maple`) | migrations.py:102; `CREATE TRIGGER maple_immutable_delete BEFORE DELETE ON maple BEGIN SELECT RAISE(ABORT, 'maple identity is immutable'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `observation_append_only_update` (trigger, `observation`) | migrations.py:148; `CREATE TRIGGER observation_append_only_update BEFORE UPDATE ON observation BEGIN SELECT RAISE(ABORT, 'observations are append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `observation_append_only_delete` (trigger, `observation`) | migrations.py:151; `CREATE TRIGGER observation_append_only_delete BEFORE DELETE ON observation BEGIN SELECT RAISE(ABORT, 'observations are append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `journal_entry_observation_append_only_update` (trigger, `journal_entry_observation`) | migrations.py:212; `CREATE TRIGGER journal_entry_observation_append_only_update BEFORE UPDATE ON journal_entry_observation BEGIN SELECT RAISE(ABORT, 'journal references are immutable'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `journal_entry_observation_append_only_delete` (trigger, `journal_entry_observation`) | migrations.py:216; `CREATE TRIGGER journal_entry_observation_append_only_delete BEFORE DELETE ON journal_entry_observation BEGIN SELECT RAISE(ABORT, 'journal references are immutable'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `journal_state_no_delete` (trigger, `journal_state`) | migrations.py:220; `CREATE TRIGGER journal_state_no_delete BEFORE DELETE ON journal_state BEGIN SELECT RAISE(ABORT, 'journal state cannot be deleted'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `decision_by_time` (index, `decision`) | migrations.py:292; `CREATE INDEX decision_by_time ON decision (at);` | query ordering/uniqueness | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `action_event_by_action` (index, `action_event`) | migrations.py:309; `CREATE INDEX action_event_by_action ON action_event (action_id);` | query ordering/uniqueness | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `life_state_no_delete` (trigger, `life_state`) | migrations.py:378; `CREATE TRIGGER life_state_no_delete BEFORE DELETE ON life_state BEGIN SELECT RAISE(ABORT, 'life state cannot be deleted'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `life_state_revision_advances` (trigger, `life_state`) | migrations.py:381; `CREATE TRIGGER life_state_revision_advances BEFORE UPDATE ON life_state WHEN NEW.revision <> OLD.revision + 1 BEGIN SELECT RAISE(ABORT, 'life state revision must advance by exactly one'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `life_state_counters_never_decrease` (trigger, `life_state`) | migrations.py:385; `CREATE TRIGGER life_state_counters_never_decrease BEFORE UPDATE ON life_state WHEN NEW.tick_counter < OLD.tick_counter OR NEW.interaction_counter < OLD.interaction_counter OR NEW.decision_counter < OLD.decision_counter OR NEW.action_counter < OLD.action_counter OR NEW.goal_counter < OLD.goal_counter BEGIN SELECT RAISE(ABORT, 'RNG counters never decrease'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `timeline_event_by_time` (index, `timeline_event`) | migrations.py:411; `CREATE INDEX timeline_event_by_time ON timeline_event (at);` | query ordering/uniqueness | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `timeline_event_one_birth` (unique index, `timeline_event`) | migrations.py:413; `CREATE UNIQUE INDEX timeline_event_one_birth ON timeline_event (maple_id) WHERE kind = 'born';` | query ordering/uniqueness | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `timeline_event_append_only_update` (trigger, `timeline_event`) | migrations.py:415; `CREATE TRIGGER timeline_event_append_only_update BEFORE UPDATE ON timeline_event BEGIN SELECT RAISE(ABORT, 'timeline is append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `timeline_event_append_only_delete` (trigger, `timeline_event`) | migrations.py:418; `CREATE TRIGGER timeline_event_append_only_delete BEFORE DELETE ON timeline_event BEGIN SELECT RAISE(ABORT, 'timeline is append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `journal_entry_by_time` (index, `journal_entry`) | migrations.py:457; `CREATE INDEX journal_entry_by_time ON journal_entry (created_at);` | query ordering/uniqueness | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `journal_entry_append_only_update` (trigger, `journal_entry`) | migrations.py:459; `CREATE TRIGGER journal_entry_append_only_update BEFORE UPDATE ON journal_entry BEGIN SELECT RAISE(ABORT, 'journal entries are immutable'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `journal_entry_append_only_delete` (trigger, `journal_entry`) | migrations.py:462; `CREATE TRIGGER journal_entry_append_only_delete BEFORE DELETE ON journal_entry BEGIN SELECT RAISE(ABORT, 'journal entries are immutable'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `goal_append_only_update` (trigger, `goal`) | migrations.py:465; `CREATE TRIGGER goal_append_only_update BEFORE UPDATE ON goal BEGIN SELECT RAISE(ABORT, 'goals are immutable'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `goal_append_only_delete` (trigger, `goal`) | migrations.py:468; `CREATE TRIGGER goal_append_only_delete BEFORE DELETE ON goal BEGIN SELECT RAISE(ABORT, 'goals are immutable'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `decision_append_only_update` (trigger, `decision`) | migrations.py:471; `CREATE TRIGGER decision_append_only_update BEFORE UPDATE ON decision BEGIN SELECT RAISE(ABORT, 'decisions are append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `decision_append_only_delete` (trigger, `decision`) | migrations.py:474; `CREATE TRIGGER decision_append_only_delete BEFORE DELETE ON decision BEGIN SELECT RAISE(ABORT, 'decisions are append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `action_event_append_only_update` (trigger, `action_event`) | migrations.py:477; `CREATE TRIGGER action_event_append_only_update BEFORE UPDATE ON action_event BEGIN SELECT RAISE(ABORT, 'action events are append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `action_event_append_only_delete` (trigger, `action_event`) | migrations.py:480; `CREATE TRIGGER action_event_append_only_delete BEFORE DELETE ON action_event BEGIN SELECT RAISE(ABORT, 'action events are append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `tool_use_by_action` (index, `tool_use`) | migrations.py:571; `CREATE INDEX tool_use_by_action ON tool_use (action_id);` | query ordering/uniqueness | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `document_append_only_update` (trigger, `document`) | migrations.py:573; `CREATE TRIGGER document_append_only_update BEFORE UPDATE ON document BEGIN SELECT RAISE(ABORT, 'documents are append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `document_append_only_delete` (trigger, `document`) | migrations.py:576; `CREATE TRIGGER document_append_only_delete BEFORE DELETE ON document BEGIN SELECT RAISE(ABORT, 'documents are append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `tool_use_append_only_update` (trigger, `tool_use`) | migrations.py:579; `CREATE TRIGGER tool_use_append_only_update BEFORE UPDATE ON tool_use BEGIN SELECT RAISE(ABORT, 'tool provenance is append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `tool_use_append_only_delete` (trigger, `tool_use`) | migrations.py:582; `CREATE TRIGGER tool_use_append_only_delete BEFORE DELETE ON tool_use BEGIN SELECT RAISE(ABORT, 'tool provenance is append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `memory_by_key` (unique index, `memory`) | migrations.py:609; `CREATE UNIQUE INDEX memory_by_key ON memory (key) WHERE key IS NOT NULL;` | query ordering/uniqueness | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `memory_by_tier` (index, `memory`) | migrations.py:611; `CREATE INDEX memory_by_tier ON memory (tier, last_seen_at);` | query ordering/uniqueness | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `memory_no_delete` (trigger, `memory`) | migrations.py:613; `CREATE TRIGGER memory_no_delete BEFORE DELETE ON memory BEGIN SELECT RAISE(ABORT, 'memories are never deleted'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `memory_identity_is_fixed` (trigger, `memory`) | migrations.py:616; `CREATE TRIGGER memory_identity_is_fixed BEFORE UPDATE ON memory WHEN NEW.kind <> OLD.kind OR NEW.text <> OLD.text OR NEW.created_at <> OLD.created_at OR NEW.key IS NOT OLD.key BEGIN SELECT RAISE(ABORT, 'a memory keeps its kind, text, key and birth'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `memory_event_append_only_update` (trigger, `memory_event`) | migrations.py:632; `CREATE TRIGGER memory_event_append_only_update BEFORE UPDATE ON memory_event BEGIN SELECT RAISE(ABORT, 'memory events are append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `memory_event_append_only_delete` (trigger, `memory_event`) | migrations.py:635; `CREATE TRIGGER memory_event_append_only_delete BEFORE DELETE ON memory_event BEGIN SELECT RAISE(ABORT, 'memory events are append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `daily_reflection_append_only_update` (trigger, `daily_reflection`) | migrations.py:662; `CREATE TRIGGER daily_reflection_append_only_update BEFORE UPDATE ON daily_reflection BEGIN SELECT RAISE(ABORT, 'daily reflections are append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `daily_reflection_append_only_delete` (trigger, `daily_reflection`) | migrations.py:665; `CREATE TRIGGER daily_reflection_append_only_delete BEFORE DELETE ON daily_reflection BEGIN SELECT RAISE(ABORT, 'daily reflections are append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `conversation_message_external` (unique index, `conversation_message`) | migrations.py:690; `CREATE UNIQUE INDEX conversation_message_external ON conversation_message (channel, external_id) WHERE external_id IS NOT NULL;` | query ordering/uniqueness | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `conversation_message_append_only_update` (trigger, `conversation_message`) | migrations.py:693; `CREATE TRIGGER conversation_message_append_only_update BEFORE UPDATE ON conversation_message BEGIN SELECT RAISE(ABORT, 'conversations are append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |
| `conversation_message_append_only_delete` (trigger, `conversation_message`) | migrations.py:696; `CREATE TRIGGER conversation_message_append_only_delete BEFORE DELETE ON conversation_message BEGIN SELECT RAISE(ABORT, 'conversations are append-only'); END;` | SQL mutation/identity/append-only enforcement | Preserve definition/behavior on final target table | Missing enforcement or changed ordering/uniqueness | Future compare sqlite_schema definition and exercise permitted/refused mutations; query-plan/index presence |

### Sequences, max IDs and physical/runtime metadata

| Item / source | Current usage | Preservation / proposed v11 mapping | Data-loss risk | Required verification |
|---|---|---|---|---|
| `sqlite_sequence.name` (SQLite-created by AUTOINCREMENT definitions above) | allocator table identity | P0 every existing name; new world_event sequence only if a real event is inserted | renamed/dropped allocator | compare exact rows; no migration event means no invented world_event sequence |
| `sqlite_sequence.seq` | high-water, possibly greater than MAX(id) | P0 exactly; explicitly restore after table rebuild | reused IDs despite equal row counts/MAX | synthetic seq > MAX plus next insert assertions |
| MAX(id), complete row keys and counts for all17 tables | continuity / identity linkage | compute privately in future authorized rehearsal, compare whole rows; no resetting gaps | aggregates hide omissions/changed values | V0 plus sequence and association checks |
| Explicit goal.id, action_counter/action_id; no action table | counter-issued identities | preserve counters and historical IDs; do not retrofit action FK or decision.goal_id FK where none exists | historic records rejected / fabricated parents | old valid historical rows and next-ID replay |
| PRAGMA application_id / user_version — migrations.py; db.py `_verify`:110 / open:199 | identify Maple / version guards | same application marker; future11 only after verified atomic conversion; shipped registry stays10 | foreign DB, blind upgrade or false success | wrong marker,0/10/11/too-new, partial shapes and unchanged file on refusal |
| Schema SQL / STRICT / PK / FK / CHECK / defaults / implicit PK+UNIQUE indexes | persisted validity | exact inventory above; only enumerated proposed changes permitted | partial schema accepted on version alone | future schema fingerprint + FK/integrity check; all allowed differences enumerated |
| Journaling / FK mode / transaction scope — db.py:66–91; repositories.py:87,100 | connections / consistent reads and writes | preserve existing v10 behavior; future isolated read cannot migrate or create | mixed snapshots or disabled FK leaked | connection mode before/after failure; snapshot-consistent read; no fallback writes |

AUTOINCREMENT tables: `observation`, `decision`, `action_event`, `timeline_event`, `journal_entry`, `document`, `tool_use`, `memory`, `memory_event`, `daily_reflection`, `conversation_message`. Actual row counts, MAX IDs, sequence values, identity values, database size and production schema are **UNKNOWN / NOT ACCESSED**. This is definition coverage, not a claim about real data.

Existing startup source: [db.py](../../backend/src/maplegotchi/storage/db.py) `_give_birth`:126, `_verify`:110, `take_pre_migration_snapshot`:154, `open_life_database`:199; [migrations.py](../../backend/src/maplegotchi/storage/migrations.py) `MIGRATIONS`:707, `schema_version`:754, `migrate`:759. Missing file triggers birth only through the existing explicit data-directory path; empty/foreign/corrupt/no-life files refuse. Older recognized schemas snapshot as configured and migrate to latest shipped10; too-new refuses. Do not use this auto-birth/migrate path for future isolated v11 inspection. Production preflight must reject wrong/missing target paths rather than creating another life.

## 4. Existing v11 synthetic candidate assessment

Exact candidate: [rehearsal/v11.py](../../backend/tests/rehearsal/v11.py) `canonical`:75; `digest`:79; `capture`:89; `initial_document`:108; `SCHEMA`:119; `freeze_table`:171; `CandidateLife`:181; `load_candidate`:205; `rebuild`:347; `rehearse`:425. [fixtures.py](../../backend/tests/rehearsal/fixtures.py) guards owned disposable synthetic handles; [test_v11.py](../../backend/tests/rehearsal/test_v11.py) is historical test implementation, not freshly executed STEP164 evidence.

| Aspect | Actual candidate | Assessment / required D02 choice |
|---|---|---|
| Physical shape |10 new tables: activity_kind,room_kind,layout_revision,world_state,layout_host,layout_room,layout_point,layout_slot,world_event,display_placement; life/journal_entry/decision rebuilt | Good accepted-architecture starting point; STEP166 design acceptance is recorded in§14, implementation remains absent |
| Canonical serializer | Python json.dumps(sort_keys=True,separators=(',',':'),allow_nan=False), default ensure_ascii=True; SHA256 UTF8 | Deterministic; NaN is already refused. Freeze algorithm/strict shape/version and predecode cap explicitly |
| Revision document | house + instances + empty themes/lighting_presets; no document format_version/cap | Version envelope and exact byte cap missing |
| Catalog | hash canonical types; loader requires current shipped initial types/version1 | Historical revisions can become unreadable after a catalog release; versioned immutable resolution needed |
| Indexes | immutable derived revision/host/room/point/slot keys, checked against active document | Keep keys derived; no geometry second truth. STRICT TEXT PK already implies NOT NULL |
| Life | removes location; adds layout_revision/point_host/tx/ty/route_arrives_at; maps point and route | Exact added-field constraints and full reconstruction need review |
| Routes | array of grid waypoints; global MS_PER_STEP; no persisted Entry or per-route speed | Cannot fully restart accepted reroute entry model; proposed versioned Travel object required |
| CandidateLife output | identity/revision/activity/needs/RNG/tile/host/point/Travel/world/catalog | Partial view: not the full existing reaction/task/goals/suspension/ledger/counters model. Conservation checks do not prove complete loader reconstruction |
| Version admission | synthetic-only guard; allows10/11 inside conversion before final bump | Not a normal loader that treats10 as a grid life; separate stage-specific version policy needed |
| Conservation/atomicity | all rows captured, backup verified, source rechecked, FK OFF outside BEGIN, one transaction, sequence restored, full checks, version last | Retain accepted approach; real-copy adapter/registration remain future scopes |
| Birth/history | existing identity preserved; no fabricated events; in-flight → zero-step at original arrival | Retain SpecR exception; old MapleState constructor rejects some pending canonical route timing, so cannot be reused blindly |
| Display | nullable soft link/origin_event, active item uniqueness, external eligible metadata | Hooks only; no inventory, placement execution or invented domain objects |

Static serialization measurements at this baseline: candidate document **7328 UTF8 bytes**; proposed envelope **7347 bytes**. Proposed262144-byte cap provides **35.7×** current-document headroom; This STEP164 measurement is not production workload evidence; STEP166 subsequently accepts the256KiB cap as a design direction.


## 5. Proposed v11 physical schema

**Option A — owner-approved design direction, STEP166; D02 overall OPEN / CONDITIONAL.** Exact contract text below is retained from the reviewed Stage A proposal. Descriptive contract only, not executable SQL; no Stage B authority. All new tables STRICT; no ON DELETE/UPDATE CASCADE. New world identifiers: nonempty TEXT, binary identity comparison, PROPOSED length1–128 Unicode code points. This bound does not retrofit old history. Composite keys include revision; host/local IDs must not alias across revisions. No second geometry, graph, inventory or item-catalog table.

PROPOSED column conventions: `I+` INTEGER NOT NULL≥1; `I0` INTEGER NOT NULL≥0; `K` TEXT NOT NULL length1–128; `UTC` TEXT NOT NULL, existing lexical UTC CHECK plus semantic parsing; `H` TEXT NOT NULL exactly64 lowercase hex characters; `J` TEXT NOT NULL json_valid plus strict typed canonical shape; `?` explicitly nullable. Retain unchanged existing contracts exactly as §3; no implicit defaults on new authoritative world fields.

| Proposed table | Exact proposed columns / keys / constraints | Existing relationship / serialization |
|---|---|---|
| activity_kind | id K PK | All old and accepted activity tokens;6 enum occurrences become FKs |
| room_kind | id K PK | Accepted canonical region kinds; no Maple RoomLocation enum |
| layout_revision | id I+ PK; created_at UTC; author TEXT NOT NULL IN(paolo,migration); base_revision INTEGER? FK layout_revision(id), positive and < id if present; catalog_version I+; catalog_hash H; document J, UTF8 bytes≤262144; validation_digest H | Initial1/baseNULL; append-only; digest SHA256 canonical document UTF8 |
| world_state | id INTEGER PK CHECK(id=1); active_revision I+ FK layout_revision(id) | Exactly one row, atomic pointer/life consistency; FK alone cannot ensure existence |
| layout_host | revision I+ FK layout_revision(id); id K; PK(revision,id) | Derived instance identities including accepted idle host; no coordinate copy |
| layout_room | revision I+ FK layout_revision(id); id K; kind K FK room_kind(id); PK(revision,id) | Derived region keys/kinds, no geometry copy |
| layout_point | revision I+; host_id K; id K; PK(revision,host_id,id); FK(revision,host_id)→layout_host(revision,id) | Catalog-resolved point identities; capability/override validation derives geometry |
| layout_slot | revision I+; host_id K; id K; PK(revision,host_id,id); FK(revision,host_id)→layout_host(revision,id) | Named slot keys only, no independent permission model |
| world_event | id INTEGER PK AUTOINCREMENT CHECK≥1; maple_id I+ FK maple(id); type TEXT NOT NULL length1–80; at UTC; revision I+ (life revision); layout_revision INTEGER? FK layout_revision(id); goal_id INTEGER? FK goal(id); action_id INTEGER? CHECK≥0; decision_id INTEGER? FK decision(id); priority TEXT? existing critical/high/normal/low vocabulary; payload J | Append-only; actual accepted events only, strict typed/versioned payload; no fabricated migration event |
| display_placement | id K PK; item_id K; layout_revision I+; host_id K; slot_id K; active INTEGER NOT NULL IN(0,1); link TEXT?; origin_event INTEGER? FK world_event(id); composite FK(layout_revision,host_id,slot_id)→layout_slot(revision,host_id,id) | Mutable current hooks; UNIQUE(item_id) WHERE active=1; active-layout/eligibility/capacity core validation; link opaque, never fetched/executed |

New enforcement objects PROPOSED: UPDATE/DELETE refusal triggers on layout_revision/layout_host/layout_room/layout_point/layout_slot/world_event; partial unique index one_active_display_per_item. Lookup vocabulary extends only by reviewed inserts; no referenced-ID removal/rename. Retain existing9 indexes/32 triggers on final existing tables. Names, constraints and the cap are owner-approved design contracts, not executable DDL; Stage B and publication remain unauthorized.

### Existing table changes — exhaustive proposed delta

- life_state: retain35 of36 existing columns, removing only location. Change point_id to K NOT NULL canonical local ID; add layout_revision I+ FK layout_revision(id), point_host K, tx INTEGER NOT NULL0..43, ty INTEGER NOT NULL0..25, route_arrives_at TEXT? with UTC CHECK. Composite FK(layout_revision,point_host,point_id)→layout_point(revision,host_id,id). Four fields route_path/departed/from/arrives all NULL or all non-NULL; retain reaction/task/suspension/goal checks. activity,route_from_activity,suspended_action gain activity_kind FKs with original nullability. route_path nullable TEXT JSON gains versioned shape below. Result40 columns; no authoritative room string.
- journal_entry.activity: literal CHECK→activity_kind FK; all16 columns/values/triggers retained. This plus3 life and2 decision fields accounts for6 enum occurrences.
- decision.proposed_action/executed_action: CHECK→activity_kind FK with original nullability. Keep old immutable executed_point legacy strings. PROPOSED nullable added columns executed_layout_revision INTEGER FK layout_revision(id), executed_point_host TEXT and executed_point_id TEXT (text length1–128 if present); all3 NULL or all3 non-NULL; composite FK to layout_point. Old rows get only NULL in new fields, no invented provenance. Future grid writes belong04, still D01 blocked.
- Other14 existing tables: no physical/row changes. Recreate existing objects on rebuilt tables, except reviewed enum-FK replacements. Preserve sqlite_sequence high-water values beyond MAX. Do not retrofit historical FKs that do not exist today.

### Per-structure decision records

All exact types/constraints inherit §5. STEP166 accepts the reviewed design directions, subject to the D02-F gate and D02-I payload reviews. Validation is planned future proof, not implementation or execution; original PROPOSED labels identify the reviewed proposal text rather than a new ADR lock.

| Proposed name | Purpose | Type / constraints | Existing relationship | Serialization | Invariant | Validation | Known risks | Alternatives | Recommendation / rationale | Decision status |
|---|---|---|---|---|---|---|---|---|---|---|
| activity_kind / room_kind | extensible vocabulary | K PK/FK above | v10 enums / derived regions | keyed rows | stable referenced vocabulary | enums/null/FK tests | lost token | CHECK rebuilds; generic vocabulary | dedicated keys, ADR0037 direction | ACCEPTED DESIGN A/B |
| layout_revision | canonical immutable world | I+/UTC/author/base/H/J/cap | new world | versioned document | one truth, append-only | digest/base/cap/validator/trigger | old catalog unreadable | relational geometry; unindexed JSON | canonical document + keys | ACCEPTED DESIGN A/C/D/E |
| world_state | active pointer | singleton PK/FK | one life | scalar | active=life.layout_revision | missing/mismatch/snapshot | mixed revisions | pointer in life only | explicit accepted pointer model | ACCEPTED DESIGN G |
| layout_host / layout_room | stable identities | revision PK/FK | instances / derived region | key-only rows | exact derived sets | missing/extra rows | second truth | JSON-only refs | SQL FKs without duplicated geometry | ACCEPTED DESIGN A/B |
| layout_point / layout_slot | capability/display refs | host composite keys | old point mappings / hooks | key-only rows | exact resolved keys | S8/S9/override/capability | local-ID alias | normalized geometry; JSON refs | key indexes + catalog geometry | ACCEPTED DESIGN A/B/E |
| life_state grid reference | canonical location/state | exhaustive delta above | all36 fields accounted | integer tiles / local point | room derived, references agree | full state reconstruction | partial loader hides loss | partial CandidateLife; second state store | complete isolated codec | ACCEPTED DESIGN B/H |
| route_path envelope | exact restart timing | typed JSON/UTC §6 | SpecR float-path conversion | integer waypoints / temporal entry | Travel time, no rounded edge | entry/pending/arrival/restart | transient Entry interpretation | waypoint-only; SQL child tables | versioned JSON, owner-confirmed ADR alignment | ACCEPTED DESIGN F / LOCALLY RESOLVED, NOT MERGED |
| decision reference triple | old facts / future refs | nullable all-or-none FK | executed_point stays exact | scalar refs | no backfill | old equality/new FK | relabeled history | typed provenance JSON | additive namespace, visible distinction | ACCEPTED DESIGN B |
| world_event | true append-only history | contract above | identity/goal/decision refs | typed versioned JSON | no invented event | immutable/FK/type | arbitrary JSON accepted | overload timeline | dedicated accepted hooks | ACCEPTED DESIGN I / payload review OPEN |
| display_placement | presentation hooks | contract above | eligible existing domain metadata | row / opaque link | unique item, valid active slot | capacity/eligibility/ref | invented inventory | item subsystem; no hooks | separate minimal hooks / derived Storage | ACCEPTED DESIGN I / payload review OPEN |
| persisted-life reconstruction | ongoing continuity | all fields/core invariants | current repository/model | immutable decoded record | deterministic pure read | equality/supplied-time replay | incompatible old constructor | forge Legacy location; partial view | complete canonical codec,04 integration later | ACCEPTED DESIGN H |
| lifecycle / mapping | prevent rebirth | explicit version/path §8/9 | born/seed/Born/history | provided actual identity/time | no restart/conversion events | birth-once/refusal/no-write | wrong path new life | fallback birth; bootstrap author | explicit dev birth, migration initialization convention | ACCEPTED DESIGN J |

## 6. Data model and canonical truth

PROPOSED layout format1 has exactly5 root keys: format_version(integer1),house,instances,themes,lighting_presets. house and instances use exact checked-in [initial_house.json](../../backend/src/maplegotchi/world_catalog/initial_house.json) and [initial_catalog.json](../../backend/src/maplegotchi/world_catalog/initial_catalog.json) model shapes, including slot overrides/policies and nullable links. Immutable catalog types remain release resources identified by exact version/hash. Parse into immutable World/Catalog models; validate S1–S17/capabilities/placements. No unknown/missing fields/version, duplicate keys, bool-as-int, nonfinite values, implicit Hall/default geometry or coercion.

Canonical bytes: sorted string keys, comma/colon separators, ensure_ascii=True, allow_nan=False, UTF8, no BOM/newline. Arrays retain semantic order. Reject noncanonical stored text, never normalize during load. Proposed SQL cap length(CAST(document AS BLOB))≤262144; loader bounds bytes before decode/hash. validation_digest hashes exact canonical document bytes; catalog_hash separately hashes canonical types identically. Refuse invalid hex, hash mismatch, unknown version/hash or incompatible catalog geometry. Resolve immutable versioned release resources retained for every referenced revision, not just current catalog. No remote fetch or duplicate DB-owned type catalog.

Initial themes/lighting_presets must be empty objects; nonempty content requires separately reviewed typed format. Do not invent final colors/tints. World-event payload uses explicit format_version and typed accepted event codecs; new event kinds/placement actions are not authorized by a generic JSON column.

PROPOSED route_path format1 has exactly: format_version=1; ms_per_step=positive integer; waypoints=array of [tx,ty,cumulative_steps]; entry=NULL or object {a:[tx,ty],b:[tx,ty],progress_us:integer,endpoint:[tx,ty]}. Reconstruct via [movement.py](../../backend/src/maplegotchi/core/world/movement.py) EdgeStart:22,Entry:48,Travel:72 and [pathfinding.py](../../backend/src/maplegotchi/core/world/pathfinding.py). step_us=ms_per_step×1000 derived, not duplicated. Entry endpoints adjacent/walkable;0<progress_us<step_us; endpoint=a or b and route.origin. Validate strict integer Tiles, cumulative steps and every traversed orthogonal cell; no fractional tile/pixel field.

Times remain in UTC columns: departed_at+Travel.duration=route_arrives_at=activity_started_at; retain activity_until and needs/reaction/goal/task timing. No duplicate JSON arrival. tx/ty denotes stationary tile when route=NULL; otherwise route.origin (Entry endpoint if present). Exact current position/edge derives from Travel at supplied time. Validate pending/departure/entry/path/arrival/postarrival; no rounded-edge restart.

**D02-F clarification locally recorded in STEP168:** owner approved the exact STEP167 wording now present in ADR0035 §3/§6 and ADR0037 §1. Temporal Entry is fixed route reconstruction metadata; current between-tile position derives from Travel and evaluation time. Original arrival and completed-travel reconstruction survive restart without load-time writes, fabricated events or silent repair. Narrow interpretation gate **RESOLVED IN LOCAL DOCUMENTATION / NOT YET MERGED**, fresh STEP168 validation PASS. No Stage B or D01 strategy is authorized; pure movement.py remains unchanged.

## 7. Revision and active-pointer rules

PROPOSED initial revision1/baseNULL/catalog1 exact hash/document/digest, author migration. Future actual owner revisions use paolo; parent is previous active revision, positive and lower ID. Allocate max revision+1 under writer transaction. Revert appends a new row with copied validated content/current parent, never UPDATE. R4 editor/revert execution remains deferred.

Derived keys materialize from immutable validated document/catalog once, freeze, and must match exact sets on load. Pointer, canonical life reference and any accepted placement transition commit together. Active placements match active revision; inactive historical placements may retain old refs. Conversion alone does not increment life revision/counters or invent world events. One read transaction captures pointer/revision/life/goals/ledger. Missing pointer/revision, extra singleton, life-layout mismatch or inconsistent keys refuses; never choose latest as repair.

## 8. New-birth and migrated-life mapping

| Case | PROPOSED identity/time/history behavior |
|---|---|
| Completely new future v11 development life | Explicit dev-only create, no repair-on-load. Start idle.hall_center(21,15). Actual caller born_at/name/seed, existing initial needs/counters/FIRST_ACTIVITY_DURATION. One genuine Born. Layout created_at=actual birth, author migration as initialization convention accepted in STEP166 D02-J; never falsely paolo edit |
| Existing v10 | Verify old core invariants first; preserve identity/needs/counters/goals/tasks/suspension/reaction/ledger/journal/memory/history. All9 SpecR mappings, NULL canonical. Layout1 created_at=explicit migration time≥last_updated_at, author migration; born_at exact. In-flight route zero-step destination with depart=arrive=original scheduled activity_started_at; activity times unchanged; no new Born/event |
| Restart valid v11 | Full immutable snapshot reconstruction; no new seed/name/birth/time/revision/counter/event. Supplied runtime time determines phase; no load-time mutation or automatic relocation. Later downtime policy04 |
| Unsupported future | Refuse before parsing/writes; no downgrade/create/partial best-effort life |
| Verified old v10 copy with old compatible code | May load under separately authorized restore; cannot open11. Pointer rollback does not restore DB; owner must accept known lost life |

Old MapleState requires route.departed_at≤last_updated_at; SpecR pending zero-step may depart at future original arrival. Canonical codec must preserve that exception explicitly, not rewrite time or forge Legacy location. Live admission/projection remains04/05 under unresolved D01.

## 9. Loader and version policy

PROPOSED isolated v11 codec initially accepts explicit synthetic-owned handles only, never normal startup. Future real-copy adapter requires03/08/G3; do not weaken fixture guard. Inspection opens read-only/create=False; verifies marker/schema/version/integrity/FKs; reads one snapshot; validates bounded document/catalog/indexes; reconstructs every life field and referenced fact. No shipped test imports, network/catalog fetch, privileged paths, auto-migration/birth or repair.

| Condition | PROPOSED policy |
|---|---|
| Recognized10 normal startup | Unchanged shipped latest10; isolated11 codec refuses10 legacy shape |
| Recognized11 | Future authorized isolated codec only; shipped support waits09 and later gates |
| Foreign/0/negative/future>11/missing schema | Refuse unexpected state; existing explicit normal new-life path unchanged |
| Missing/extra singleton/revision or life-layout mismatch | Typed refusal; no choose-latest fallback |
| Invalid point/slot/host or derived index extra/missing rows | Refuse even when FK passes; compare resolved canonical keys |
| Invalid JSON/cap/hash/version/catalog/geometry | Refuse before partial state escapes; category only, no private payload/seed/history in errors |
| Invalid full life/reaction/task/goals/RNG/ledger/time | Refuse, no partial CandidateLife success |
| Integrity/FK failure | Refuse; no relocation or repair event |
| Partial/uncertain migration, version/schema mismatch | Stop writer/startup; preserve copies; authorized durable-state inspection before retry/restore |

Candidate allows10/11 only under synthetic conversion before final bump. Future controlled internal precommit validator may validate target shape while user_version is still10, explicitly separate from public reopen requiring11. No broader normal version admission. Registry remains10 throughout02/03;11 registration belongs09.

## 10. Conservation/invariant matrix

All213 fields in §3 identify definition/source, current use, preservation/mapping, risk and verification. Allowed data changes only: enumerated location/point/route transition; new target-only refs; all existing historical values exact. Enum CHECK→FK is a reviewed constraint change, not a value rewrite. Coverage PASS means documentation coverage, **not migrated-data PASS**.

| Invariant family | Source | Proposed conservation / planned proof | Status |
|---|---|---|---|
| Identity4 | maple / immutable triggers | exact id/name/born_at/life_seed, one genuine Born, no rebirth | Covered; execution pending |
| Complete life36 | life_state / _STATE_COLUMNS34 + keys | every field, only enumerated world changes; full reconstruction | Covered; execution pending |
| Needs/RNG/counters/revision | needs floats, seed, tick/interaction/decision/action/goal counters | exact values, no RNG draw/tick/decision; next-ID/replay equality | Covered; execution pending |
| Times/nullable needs_at | identity/life/history/core | exact UTC text/nulls, alias/fallback; explicit pending SpecR exception | Covered; execution pending |
| Activity/goals/suspension/task/reaction/ledger | current state/repositories | decode all facts/null bundles, no dropped rate limit or unfinished task | Covered; execution pending |
| All history/associations | all17 tables / §3 codecs | complete keyed rows/counts/MAX/order/IDs/text/NULL/FKs, no backfill | Covered; execution pending |
| Mutable memory/journal cursors | memory/journal_state | preserve mutable tier/status/cursor as well as immutable identity | Covered; execution pending |
|11 sequences | AUTOINCREMENT | exact name/high-water even >MAX; next insert proof | Covered; execution pending |
| PK/FK/CHECK/index/trigger/STRICT | §3 definitions | retain9 indexes/32 triggers; enumerated replacements, mutation-refusal tests | Covered; execution pending |
| Point/room/Travel | FinalSpecR/movement/catalog |9 mappings/walkability/original arrival, no fabricated walk; Entry if accepted | Covered; F locally resolved, implementation pending |
| Layout/catalog/pointer/display | ADR0037/39/candidate | one truth/immutable revisions/exact derived keys/active-life match | Covered; design accepted, D02 conditional |
| Version/transaction/failure | db.py/migrate/ADR0028 | registry10; future verify then version-last COMMIT; no mutation on refusal | Covered; execution pending |

No actual database identity/count/MAX/sequence values accessed. Future03 synthetic and08 authorized owner-copy conservation must both pass; synthetic evidence cannot close G3/G4.

## 11. Restart and failure handling

Future conversion: explicit approved source, consistent verified owner-held and automatic copies, source lineage recheck; FK OFF before rebuild transaction as actual mechanism requires; one BEGIN IMMEDIATE; target DDL/copy/index/sequence construction; complete core/all-row/FK/integrity verification; final user_version11 then single COMMIT; restore connection FK mode on success/failure. No executescript split transactions. This does not relax snapshot permissions, durability or owner gate.

Snapshot/preflight failure: no conversion. Controlled precommit failure: rollback all DDL/data/version, retain verified copies. Process loss/unknown COMMIT acknowledgement: do not assert rollback; authorized operator inspects durable version/schema/invariants before retry. Valid durable11 with later app fault: no rerun/downgrade. Partial/corrupt/unknown: stop, no automatic repair/restore/retry/merge. Prefer forward-fix; v10 return only by owner-approved verified restore accepting lost-life cutoff and retaining failed DB/sidecars privately. D04/D06 remain OPEN, no invented outage/loss budgets.

## 12. Synthetic test plan

**Planned only; none implemented or executed STEP164.** Owned disposable factories only. Inspected existing definitions: [test_database.py](../../backend/tests/storage/test_database.py) birth-once:96, empty/foreign/corrupt:191–250; [test_migrations.py](../../backend/tests/storage/test_migrations.py) ordered:108,fresh:120,rollback:186,too-new:205,enums:226; [test_v11.py](../../backend/tests/rehearsal/test_v11.py) conservation:78,atomic:151,append-only:236,FK:268,invalid-load:290,registry:374,isolation:390,revision/revert/lookup:416–446,source-change/FK-mode/one-transaction:468–498. Those DB/migration tests were not run in this design-only stage.

| Planned ID | Cases / acceptance | Future authorized scope |
|---|---|---|
| T01 | schema/type/NULL/key/check/trigger/index fingerprint;213-field allowed-difference ledger |02 codecs /03 converter |
| T02 | full identity/life/ledger/goals/task/reaction/suspension/memory/journal decode, immutable output, no side effects |02 |
| T03 | canonical bytes/ASCII/key order/duplicate/unknown/missing/version/bool/nonfinite; hash/catalog mismatch |02 |
| T04 | UTF8 cap−1/cap/cap+1 with valid padded layouts, bound before parse; nonempty themes/presets refusal |02 |
| T05 | initial/parent/revert append-only, singleton/life match, missing/extra indexes, snapshot reader during writer |02; editor R4 deferred |
| T06 | all9 mappings/NULL canonical; wrong source point/location/destination; pending zero-step/original arrival |03 |
| T07 | zero/multiple corners, Entry toward either endpoint; before departure/mid-edge/arrival/postarrival/downtime/restart; subsecond times; stored speed independent of later global constant |02 encoding;04 live behavior D01 blocked |
| T08 | explicit dev birth once, conversion no birth, restart no new rows/times; all history exact; seq>MAX/next ID |02/03 |
| T09 | one transaction/version last/FK mode; failures each DDL/copy/check/bump/commit and process/reopen classification |03/07 |
| T10 | absent/foreign/too-new/corrupt/partial/wrong-path refusal; registry10/refusal11; no import/call/package/fixture bypass |02/03/07 |
| T11 | typed actual events/provenance, active item uniqueness/slot capacity/eligibility/inactive old revision; soft links never fetched; no inventory/actions |02 hooks |
| T12 | historical catalog version/hash compatibility and unknown resource refusal; later owner-copy conservation/restore |02/07;08 requiresG3 |

## 13. Schema alternatives and trade-offs

| Option | Accepted architecture fit | Trade-off / recommendation |
|---|---|---|
| A strengthened candidate-shaped document + derived identity indexes + complete codecs | Fits one truth, subject to D02-F interpretation | Recommended: retains FK protection and accepted model; adds explicit versions/cap/catalog/full state/route contract |
| B document with fewer SQL reference indexes | Only if remaining accepted lookup/FK obligations explicitly satisfied | Fewer rows but weaker DB integrity and more loader checks; not recommended |
| C fully normalized relational geometry as canonical replacement | Requires explicit ADR0037 amendment | Cannot silently replace accepted document architecture with a documentation proposal |
| D unchanged synthetic candidate | Useful historical evidence, insufficient final restart contract | Missing full state/Entry/version/cap/catalog evolution; not recommended |

## 14. D02 decision package

**All ten design directions accepted by the owner on2026-10-13 in STEP166**, after the ChatGPT review; provenance is the owner-supplied STEP166 instruction (attachment e954311b-f5cb-423e-a934-c78ef39153a4). The owner explicitly selects Option A for A,C–J and the exact Stage A §5 contract for B. D02 overall remains conditional for integration, not all gates cleared; STEP168 locally resolves the narrow F interpretation, with publication/merge and payload review still separate. The existing matrix retains accepted constraints, original candidate/alternatives, workstream impact and required tests. No implementation is authorized for any row.

| Choice | Accepted constraint | Current candidate | Alternatives / trade-offs | Owner-approved direction / rationale | Affected workstreams | Required tests | ADR/spec amendment? | Status |
|---|---|---|---|---|---|---|---|---|
| D02-A physical shape | canonical revision/lookup/FK/one truth |10 new tables,3 rebuilds | derived indexes vs fewer indexes; normalized replacement needs ADR | OptionA, keys only, no second geometry |02,03,04,07–12 |T01,T05,T10 |No replacement architecture; owner design acceptance recordedSTEP166 | OWNER-APPROVED DESIGN / NOT IMPLEMENTED |
| D02-B exact columns/keys | identity/history/stable refs | no canonical decision triple; weaker hash/time checks | nullable triple vs typed provenance JSON; bounded vs unbounded IDs | §5 exact delta, new IDs1–128, lowerhex hashes, UTC arrival, nullable triple preserving history |02–05,07–12 |T01,T02,T06,T08 |Old-fact rewrite would require amendment; none proposed | OWNER-APPROVED DESIGN / NOT IMPLEMENTED |
| D02-C JSON/canonical version | deterministic truth | unversioned4-key layout | explicit format_version vs external version; serializer changes digests | five-key format1 / exact §6 serializer / strict fields |02,03,07–12 |T03,T10 |Exact JSON provisional inADR0037 | OWNER-APPROVED DESIGN / NOT IMPLEMENTED |
| D02-D byte cap | provisional bounded layout | uncapped |256KiB vs1MiB vs unbounded; smaller cap needs later growth review |262144 UTF8 bytes preparse+SQL, ~35.7× initial7347 bytes |02,03,07–12 |T04 |Owner cap acceptance recordedSTEP166, not ADR lock | OWNER-APPROVED DESIGN / NOT IMPLEMENTED |
| D02-E catalog compatibility | immutable release-owned types, old revisions readable | current initial types/version1 only | retained versioned resources vs embedded catalog snapshot | exact version/hash immutable resources retained for referenced revisions; fail unknown, no duplication |02–04,07–12 |T03,T12 |DB-owned catalog would need separate ownership review | OWNER-APPROVED DESIGN / NOT IMPLEMENTED |
| D02-F Travel serialization | tile/route/time, exact accepted movement, no fractional position truth | waypoint array/global speed/no Entry | versioned JSON vs route/entry SQL children; waypoint-only loses Entry origin | JSON format1 with per-route speed and temporal Entry; exact restart, no D01 strategy |02–07,09–12 |T06,T07 |Owner must confirm ADR0035 transient-entry alignment; narrow ADR/spec clarification if needed before code | OWNER-APPROVED DESIGN / LOCALLY RESOLVED, NOT YET MERGED |
| D02-G revision/pointer | append-only active truth | immutable keys/pointer | explicit pointer vs life-only; both need atomic consistency | singleton/consistent snapshot/life match/parent<id/revert new row |02–04,07–12 |T05,T09 |No new R4 authority | OWNER-APPROVED DESIGN / NOT IMPLEMENTED |
| D02-H complete loader/version | fail closed/full restart/old-code guard | partial CandidateLife, internal10/11 | full isolated codec vs partial view/forged old state | complete immutable persisted life, public11 only, separate internal precommit validator, normal10 untouched |02–05,07–12 |T02,T07,T08,T10 |Live integration04 remains D01 blocked | OWNER-APPROVED DESIGN / NOT IMPLEMENTED |
| D02-I event/display hooks | separate placements/true append-only history/derived Storage | generic JSON + external metadata | typed codecs vs arbitrary JSON; no need item table | minimal hooks, typed accepted payloads, active-slot/item/capacity validation, no inventory |02,03,07–12 |T01,T11 |No new event kinds/domain/actions approved; review each enabled codec | OWNER-APPROVED DESIGN / payload reviews OPEN |
| D02-J lifecycle/mapping | identity/history conservation, true birth, SpecR | conversion author migration only | migration initialization vs new bootstrap author; never false paolo | explicit dev birth with actual inputs, migration-author convention, existing maps exactlySpecR, pure restart |02–04,07–12 |T06,T08,T09 |New author requiresADR0037 amendment; migration convention acceptedSTEP166 | OWNER-APPROVED DESIGN / NOT IMPLEMENTED |

**Remaining gates before schema-dependent loader implementation:** owner-selected A–J directions are recorded; STEP168 records the approved F clarification locally, not yet merged. Stage B still requires new bounded owner authorization and review of each payload proposed for enablement. Future display/event behaviors may remain deferred only if absent from enabled codecs and explicitly rejected; persisted hooks and enabled typed payloads must be frozen. Retention, final art/tints/device defaults, operating budgets, R4 auth/mutations and D01 strategy stay outside D02. Do not introduce an unresolved persisted shape while claiming D02 frozen.



<a id="step168-local-clarification"></a>

### STEP168 approved clarification — local record

Owner approval date **2026-10-13**; provenance **STEP167 exact-wording approval, explicitly authorized for recording by STEP168**, attachment `b53fa939-19cb-433f-95e7-0478a0a6caf5`. Approved passages were extracted directly from that instruction, not reworded. [ADR0035 §3](../adr/0035-world-model.md#3-movement-and-pathfinding-b8-a6-a7) replaces only the route bullet; [ADR0035 §6](../adr/0035-world-model.md#6-feet-point-inside-a-tile-b12--locked-2026-10-09) keeps the tile-coordinate-only rule and adds the approved explanation; [ADR0037 §1](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md#1-persistence-model-a10) replaces only its position bullet. Amendment metadata records date/provenance/nature without changing original acceptance dates.

Before: F classification B / architecture interpretation OPEN (STEP166); STEP167 proposed exact resolution. After successful STEP168 exact-text validation: **D02-F RESOLVED IN LOCAL DOCUMENTATION / NOT YET MERGED**. This resolves only the persistence interpretation; no integration-branch/implemented/operational closure is claimed. The earlier STEP166 owner register, review and draft below are retained as historical records of that stage, not current pending wording. The exact approved STEP167 wording supersedes its earlier draft.

One position model remains: persisted world-position fields integer tiles; optional Entry is fixed temporal-origin metadata; current position/phase derives from validated Travel plus supplied evaluation time. Whole-step duration plus remaining Entry time retains exact arrival/activity-start equality. After original arrival, reconstructed travel is complete at destination; destination activity completion and downtime processing retain existing semantics. Loader writes no events/state, never rounds/teleports/repairs and refuses unsupported/inconsistent data. Movement implementation is unchanged.

All other approved directions and exact persistence/schema/canonical/catalog/lifecycle/version contracts remain intact. D02-I minimal hooks are design-approved; **every event payload proposed for enablement still requires explicit individual review**, and unspecified payloads remain unapproved. D01/D03–D06 OPEN,40collapsed-anchor/mid-edge evidence retained. No runtime admission/Legacy strategy follows from Entry clarification.

Publication and merge are **NOT AUTHORIZED / NOT DONE**. New bounded Stage B authorization and applicable payload reviews are outstanding; no Stage B starts here. R1B-02 stays IN PROGRESS, not REVIEW/DONE;1/12DONE=8.3%. STEP168 checks/evidence are recorded separately in the append-only worklog; STEP166119/119 is historical, not a freshly rerun result.

### Historical STEP166 owner-selected contracts and limits

For **each row**: accepted date **2026-10-13 Asia/Bangkok**; provenance **owner STEP166 instruction following ChatGPT D02 review**, attachment `e954311b-f5cb-423e-a934-c78ef39153a4`. Acceptance is design-level only, subordinate to binding ADRs and the F condition. Workstream impacts/tests are the corresponding rows in the matrix above; all tests remain required, not freshly run. **Implementation NOT AUTHORIZED for every decision.**

| Decision | Exact owner selection | Approved contract and limits | Remaining condition |
|---|---|---|---|
| D02-A | Option A | Ten candidate-shaped new tables; rebuild life_state,journal_entry,decision; canonical document sole geometry truth, indexes references only | Preserve binding architecture; no code/migration |
| D02-B | Exact proposed Stage A §5 contract | Columns/IDs/composite keys/nullability/constraints/hashes/time checks/activity FKs/additive nullable decision refs; preserve historical values/indexes/triggers/sequence high-water marks | Exact reviewed contract preserved; no historical rewrite or implementation |
| D02-C | Option A | Five-key format_version=1 envelope and exact canonical serialization/parsing/digest/strict refusal rules | No unknown or implicit shape extensions |
| D02-D | Option A |262144 UTF8 bytes/256KiB maximum; preparse and SQLite byte enforcement, boundary tests retained | No cap relaxation or character-count substitution |
| D02-E | Option A | Immutable versioned release catalogs retained while referenced; exact catalog_version/hash; refuse missing/incompatible; no DB-owned type truth | Historical-resource compatibility tests still required |
| D02-F | Option A | Complete route/ms_per_step/timestamps/temporal Entry for exact restart under reviewed versioned shape/invariants | **ADR-0035 classification B / interpretation OPEN**; no automatic ADR amendment or D01 approval |
| D02-G | Option A | Immutable append-only revisions; explicit singleton pointer/parent ordering/atomic life consistency/read snapshots/append-only revert | No R4 editor/revert execution authority |
| D02-H | Option A | Complete isolated fail-closed reconstruction; no partial/invented state,birth,repair,relocation,migration; public/internal validator separation; shipped10 unchanged | Stage B not authorized; registry/startup unchanged |
| D02-I | Option A | Minimal world_event/display_placement hooks; typed reviewed true-event payloads only; no fabrication/arbitrary accepted JSON/inventory/unauthorized placement | **Each enabled payload contract needs separate explicit review; unspecified payloads NOT APPROVED** |
| D02-J | Option A | Existing author migration for automatic initial layout including explicit future dev birth; actual identity/time/seed/Born, exactSpecR timing/history, pure restart | No bootstrap author or false owner edit; no birth/migration implementation |

### D02-I outstanding event-payload reviews

STEP166 approves the minimal persistence direction, **not any unspecified event type or payload contract**. No new payload is enabled by this documentation step. Before any future payload is enabled, its individual type/version, exact fields and nullability, references, serialization/refusal rules and true-event provenance must be reviewed explicitly and associated with T11. Generic json_valid or direction acceptance is insufficient. Review status for every not-yet-specified enabled-payload proposal is **OPEN / not approved**; do not infer an approved list or invent event kinds here. Deferred payloads remain absent from enabled codecs and explicitly rejected. This gate is distinct from the D02-F architecture gate and from Stage B authorization.

<a id="d02-f-adr-gate"></a>

### Historical STEP166 D02-F ADR review — classification B, OPEN at that stage

**Finding: B — ambiguous extension requiring a narrow interpretation decision.** A is not established merely by selecting Option A. C is not established either: the proposal can preserve integer position storage and existing pure movement semantics, but persistence of temporal Entry is not expressly specified in accepted normative text. This is documentation analysis, not a silent owner interpretation or ADR amendment.

| Exact source | Accepted/implemented rule | Relevance to the unresolved interpretation |
|---|---|---|
| [ADR0035](../adr/0035-world-model.md) §3,lines36–43 | ADR0027 semantics retained; phase derives from now; reroute starts at current position; compressed integer waypoints; duration steps×ms_per_step; no normal teleport | Supports exact supplied-time reconstruction, but the waypoint-only duration description does not expressly cover a serialized partial-edge Entry duration |
| [ADR0035](../adr/0035-world-model.md) §6,line81 | Stored world positions are tile coordinates only | Temporal progress can imply an edge position; owner must distinguish fixed route-origin time metadata from independent current-position truth |
| [ADR0037](../adr/0037-world-persistence-v11-migration-and-legacy-projection.md) §1,line27 and provisional section,line58 | life_state stores tile coordinates plus waypoints; exact SQL/JSON shapes provisional | Allows detailed schema design, but provisional JSON alone does not waive ADR0035's position rule |
| [movement.py](../../backend/src/maplegotchi/core/world/movement.py) lines1,22–35 | Pure module says never persisted here; EdgeStart describes transient temporal progress, adjacent integer endpoints and interior integer progress | Existing pure contracts are not already a persistence approval |
| [movement.py](../../backend/src/maplegotchi/core/world/movement.py) Entry:48–68; Travel:72–105 | Entry joins route origin at the same speed; duration is entry duration plus whole-step duration; arrival=departure+duration; activity start=arrival | Exact existing Travel with Entry cannot be reconstructed from integer waypoints/global speed alone |
| [movement.py](../../backend/src/maplegotchi/core/world/movement.py) current_at:114–128; position_at:130–136; reroute:146–193 | Current edge/position derives from supplied time; reroute compares both adjacent endpoints using entry plus step duration | Supports preserving temporal-origin information without rounding/teleport, but does not decide its storage interpretation |

The tension is precise: serialized progress_us describes the Travel's temporal origin and allows an implied fractional location; ADR0035 explicitly stores positions as tiles and describes whole-step timing, without an explicit Entry persistence exception/interpretation. The pure module implements that temporal state but intentionally performs no storage. Therefore the owner-selected representation remains subject to an explicit interpretation gate rather than automatic A/C classification.

### Historical STEP166 narrow clarification draft — superseded by exact STEP167 wording approved in STEP168

Proposed clarification for ADR0035 §3/§6 and its ADR0037 §1 reference:

> Stored world-position fields remain integer tile coordinates. A versioned route representation may retain the fixed temporal origin of an already accepted Travel as adjacent integer edge endpoints, integer progress_us at the route's departure, its selected endpoint, per-route ms_per_step and UTC timing. This is route reconstruction metadata, not a separately updated fractional current-position field. Current edge/position remains derived from the complete Travel and supplied time. When Entry exists, total duration is its remaining entry duration plus whole-route steps×ms_per_step; without Entry, the existing whole-step formula applies. Preserve exact arrival/activity-start equality, validated adjacency/walkability and route-origin continuity; never round or teleport to reconstruct a route. This clarification grants no Legacy projection strategy, runtime admission, migration, production or implementation authorization.

**Exact next owner decision:** accept/reject/amend this narrow interpretation, and explicitly authorize any necessary ADR0035/ADR0037 wording update in a later documentation step. Accepted normative ADR files are not edited in STEP166. If the owner considers this a material change rather than clarification, obtain an explicit amendment before affected Stage B. D02-F interpretation stays **OPEN** until that decision is recorded; do not relabel it CLOSED from design selection alone.

**Stage B gates:** recorded architecture interpretation/clarification (or approved amendment if required), explicit reviews for every payload to be enabled, then separate bounded Stage B authorization. No schema-dependent implementation starts under STEP166. D01 remains OPEN independently;40collapsed-anchor pairs and ambiguous mid-edge projection are unchanged.

## 15. Compatibility boundaries

D01 **OPEN by owner direction**:40 positive-duration collapsed-anchor walking pairs and ambiguous mid-edge projections reject deliberately.334 timed/26 zero-step pairs are historical R09 evidence, not rerun164. No backend prevention or Legacy compatibility strategy selected/approved/implemented. Direct blocks04/05; transitive06–12.02/03 independent only within isolated persistence/synthetic scope and own prerequisites/authorization.

D03 **OPEN** liveDTO/SSE before05; D04 **OPEN** current snapshot/retry readiness before08/10/G3/G4; D05 **OPEN** integrated simulation approval before repins; D06 **OPEN** operating window/acceptable restore loss beforeG4/G5/G6. No live API/SSE/security/projection changes, registry remains10. Legacy renderer/default/anchors/walker and production query gating unchanged. B14/R4/later representations remain separate.

Unchanged graph:01→02;02→03;{01,02,D01}→04;{01,04,D01,D03}→05;{04,05}→06;{03,04,05,06}→07;{03,07,G3}→08;{07,08,P}→09;{08,09,D04,D06,G4}→10;{10,G5}→11;{11,G6}→12. Critical path01→02→D01→04→05→06→07→08→09→10/G4→11/G5→12/G6;03 joins07/08. G1 accepted; G2 current02 StageA only; P ungranted for02; G3–G6 ungranted; G7 deferred.01 DONE does not bypass D01.

## 16. Deferred work and risks

Owner-review risks: incomplete loader mistaken for conserved restart; Entry persistence interpretation; historical catalog unreadability; D01 descendants starting prematurely; counts mistaken for full-row/sequence proof; old constructor rejecting pending zero-step; unknown COMMIT treated as rollback; stale ADR0028 FK explanatory commentary mistaken for implemented mechanism. Future shape changes need explicit review, never infer compatibility from user_version alone.

02 StageB remains unimplemented/unauthorized: design directions accepted in STEP166; F clarification locally resolved inSTEP168/not merged, applicable payload reviews remain OPEN; new bounded G2 authorization is required.03 converter,04–12, owner-copy/restore, registration, production cutover, P/publication, pins, B14/R4 deferred. Historical CI/R1a evidence proves no current production schema/backups/restore/readiness.

## 17. Owner acceptance criteria

All ten owner design directions remain accepted. STEP168 records the exact STEP167 clarification in ADR0035 §3/§6 and ADR0037 §1; successful fresh validation resolves the narrow F interpretation **IN LOCAL DOCUMENTATION / NOT YET MERGED**. D02 is not implementation/publication/operational acceptance; integration remains pending, and enabled-payload review requirements underI remain. R1B-02 IN PROGRESS / Stage A reconciliation; Stage B NOT STARTED / NOT AUTHORIZED.01DONE/03–12TODO;1/12DONE=8.3%.

Local documentation may be submitted for a separate publication review only under future explicit permission. No stage/commit/push/PR/merge follows from this approval. Stage B requires new bounded owner authorization and each payload proposed for enablement must be reviewed. D01 andD03–D06 remain OPEN; no projection strategy requested or selected.

STEP164/166 validation results remain historical. STEP168 fresh checks compare approved text directly to the owner attachment, preserve all unrelated ADR text and prior contracts, and validate counters/links/UTF8/LF/diff/manifest/append-only worklog. No application/runtime/browser/pytest/CI/migration tests run. Full preSTEP168 worklog bytes retained.

## 18. Explicit non-goals

No schema implementation, loader/converter code, migration/registry11 or DB opening; no runtime/model/test/dependency changes. No D01 strategy/D02 self-approval/D03–D06 closure; no stage/commit/push/PR/merge/deploy, production/copy access, service action, paolo-core change, Legacy default switch, digest repin, B14/R4. Ignored local helpers only parse source/JSON and validate docs. Stop after StageA report pending owner review.
