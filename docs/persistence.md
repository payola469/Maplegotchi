# Persistence and restart recovery (Phase 2)

Status: implemented and approved in the Phase 2 review (2026-09-30). These
are implementation decisions, not FIXED owner decisions, unless noted inline.
The one FIXED decision added in this phase is D18 (see *External databases*).

## Database file and location

| | |
|---|---|
| File | `maple.db` — one SQLite application database for v0.1 |
| Location | `MAPLE_DATA_DIR/maple.db`; production `/data/maple/maple.db` (FIXED, S1 §4.1 #3: `/data/maple` is Maple's only writable area) |
| Side files | `maple.db-wal`, `maple.db-shm` (WAL mode), transient `maple.db.birth-<hex>` during first birth |
| Identity | `PRAGMA application_id = 0x4D41504C` ("MAPL") |
| Schema version | `PRAGMA user_version` (currently **6**) |
| Pre-migration copies | `pre-migration/maple.v<N>.<UTC stamp>.<hex>.db` (ADR-0028 R2; never pruned or restored automatically) |

All writes go through `storage/datadir.py` (see *Path guard*). Code outside
`maplegotchi.storage` may not open files for writing or import `sqlite3`
(enforced by `tests/security`).

## Connection settings

| Setting | Value | Why |
|---|---|---|
| `journal_mode` | `WAL` | Readers (the future API) never block the single writer and see the last committed snapshot. Tested: a reader is not blocked by an open write transaction and does not see uncommitted changes. |
| `synchronous` | `FULL` | A committed life transition survives power loss, not just a process crash. Cost measured at ~2.4 ms per commit; Maple commits once per 5-minute heartbeat plus rare interactions. |
| `foreign_keys` | `ON` | Ledger, state, and timeline rows must belong to the one Maple. |
| `trusted_schema` | `OFF`, plus `SQLITE_DBCONFIG_DEFENSIVE` | Schema content cannot run functions with side effects; no writable-schema tricks. |
| `busy_timeout` | 5000 ms | Brief waits instead of spurious lock errors. |
| isolation | explicit `BEGIN IMMEDIATE` / `COMMIT` | Every logical commit takes the write lock up front. |

WAL is PROPOSED, not FIXED: it is tested here and on CI (Linux/Windows); the
Phase 3 paolo-core survey should confirm `/data/maple` is on a local
filesystem (WAL does not work on network filesystems).

## Schema (migration 1)

```
maple               one row (id = 1): name, born_at, life_seed          immutable (triggers)
life_state          one row: revision, needs, activity, location,
                    activity_started_at/until, last_tick_at,
                    last_updated_at, tick_counter, interaction_counter,
                    reaction_kind/variant/started_at/until              revision +1 per update;
                                                                        counters never decrease;
                                                                        cannot be deleted
interaction_ledger  0-10 rows (position 0..9): kind, at                 replaced each commit
timeline_event      append-only: revision, tick_id, kind, at, payload   no UPDATE/DELETE;
                                                                        exactly one 'born'
```

Every column has a CHECK constraint (ranges, enum lists, UTC timestamp
shape, 64-hex seed). Tables are `STRICT`. Full SQL:
`backend/src/maplegotchi/storage/migrations.py`.

Migration 2 (Phase 3) adds:

```
observation         append-only: revision, tick_id, observed_at, metric, subject,
                    status, value, state, unit, source, reason     no UPDATE/DELETE;
                                                                   UNIQUE (tick_id, metric, subject)
```

Observations are written in the same transaction as the heartbeat that used
them; see `docs/sensors.md` for semantics and measured growth.

Migration 3 (Phase 4) adds:

```
journal_entry              append-only: revision, tick_id, created_at, category, trigger_kind,
                           topic, text (1-240 chars, one line), importance, brain_kind/name/version,
                           template_id, activity, expression
journal_entry_observation  append-only: entry_id -> journal_entry, observation_id -> observation
journal_state              one row: the persisted ReflectionState (dedup + daily reflection)
```

See `docs/journal.md`.

Migration 4 (v0.2 autonomy, ADR-0026/0027/0028) — one transaction, foreign keys
OFF for the table rebuilds (SQLite's documented procedure), verified before COMMIT:

```
life_state      rebuilt: activity adds 'think', location adds 'sofa'; v3 rows converted
                (rest -> sofa, idle/walk -> rug, everything else unchanged); new columns
                point_id, route_departed_at/from_activity/path (JSON), needs_at,
                decision_counter, action_counter, goal_counter, action_priority,
                active_goal_id, suspended_goal_id, suspended_action, decision_due_since
timeline_event  rebuilt with ids and sequence preserved; adds goal_started, goal_suspended,
                goal_resumed, goal_completed, goal_abandoned
journal_entry   rebuilt with ids and sequence preserved; activity adds 'think'
goal            append-only goal definitions (type, summary, source, horizon)
decision        append-only decision audit (ADR-0026 §8): no prompt, no raw model output
action_event    append-only action lifecycle (ADR-0028 §2)
```

`_v4_verify` refuses to commit unless the `maple` row, the life-state values and
counters, the interaction ledger, timeline/journal counts, max ids and sequences,
journal references and observations are unchanged and `foreign_key_check` is
empty. Before any migration to v4+ of an existing database, `storage.db` writes a
verified copy to `pre-migration/` (online backup API, DELETE journal,
`integrity_check`, application_id, source `user_version`, 0600, fsync,
non-overwriting publish); if that fails, the migration is refused and `maple.db`
is untouched (`PreMigrationSnapshotError`). Recovery procedure: ADR-0028 R5/R6 and
`deploy/install.md` → Rollback.

Migration 5 (goals) adds `life_state.critical_since` (ALTER TABLE ADD COLUMN):
a serious problem interrupts once per problem, not at every heartbeat
(`docs/autonomy.md`). Like every migration from v4 on, it is preceded by a
verified `pre-migration/` copy.

Migration 6 (reader/writer, ADR-0029) adds `life_state.task_*` and two append-only
tables: `document` (Maple's workspace: kind, title, body ≤ 4,000 chars, sources) and
`tool_use` (provenance of every read/write step, linked to the document it wrote).

## Canonical vs derived state

Persisted (canonical) — exactly the fields of `core.state.MapleState`:

| Core field | Stored in |
|---|---|
| `identity.name`, `identity.born_at` | `maple.name`, `maple.born_at` |
| `rng.seed_hex` | `maple.life_seed` |
| `rng.tick_counter`, `rng.interaction_counter` | `life_state` |
| `needs` (mood, energy, curiosity, social) | `life_state` (REAL; bit-exact round trip) |
| `activity`, `location`, `activity_started_at`, `activity_until` | `life_state` |
| `last_tick_at`, `last_updated_at` | `life_state` |
| `recent_interactions` (Greet/Pet cooldowns + global rate window, D14) | `interaction_ledger` |
| `reaction` (transient, D17) | `life_state.reaction_*` |

Derived, never stored: `expression_at(now)`, `active_reaction(now)`, age,
`ticks_lived`. Persistence metadata: `life_state.revision`.

## Transaction model

- One logical transition = one transaction: the `life_state` UPDATE, the full
  ledger rewrite, and the new timeline events commit together or not at all.
- Optimistic concurrency: the UPDATE requires `revision = expected`; a
  mismatch raises `ConcurrentWriteError` (e.g. a second process).
- Identity and seed are re-checked inside the transaction and can never change.
- Rejected interactions change nothing and are not persisted.

## Single-writer runtime

`runtime/life.py: LifeRuntime` serializes all transitions (heartbeats and
Greet/Pet) behind one lock. Inside the lock it reads the injected clock,
computes the transition with pure core, commits, and only then adopts the new
state in memory. If anything fails, memory and database both stay at the last
committed revision; the next call starts from there.

If the wall clock steps backwards, heartbeats wait and interactions act at
the latest known time (core never goes back in time).

## Restart model

- `LifeRuntime.open(data_dir, clock, ...)`:
  - `maple.db` exists → validate, migrate if older, load, continue.
  - `maple.db` absent → birth (below), then load.
- The name and seed factory passed to `open` are used only at birth.
- Restart never regenerates the seed, resets counters, changes age, clears the
  ledger or an active reaction, or re-creates identity. Proven by
  `tests/runtime/test_continuity.py` (pure core vs persisted runtime vs
  runtime restarted at 1, 7, 290, mid-burst, last, every 97, every 5 steps:
  identical states, RNG counters, outcomes, and timelines).

## Downtime

After restart, `heartbeat_if_due()` runs **one** heartbeat at the current
time. Core applies bounded catch-up (need changes capped at
`max_catchup` = 6 h) and emits `DowntimeGap(since, until)` when the gap exceeds
two intervals. Ten years of downtime is still one heartbeat. The outcome is
deterministic for the same database and restart time (tested with two copies).

## Birth semantics

- Happens exactly once per life, when `maple.db` does not exist.
- The new life is built in a temporary `maple.db.birth-<hex>` file that is
  explicitly put in **rollback-journal (DELETE) mode**, fully migrated,
  committed, and closed.
- Before publication the file must be self-contained: no `-journal`, `-wal`
  or `-shm` sidecar may exist, and header bytes 18-19 must be `1,1` (rollback
  journal, not WAL). Otherwise birth aborts, nothing is published, and the
  temporary files are removed.
- Only then is it published as `maple.db` with a hard link, which never
  overwrites. A losing concurrent starter discards its temporary file and
  loads the winner.
- WAL is enabled only afterwards, when the canonical `maple.db` is opened for
  normal operation.
- Proof (`tests/storage/test_birth_publication.py`): at the moment of
  publication the directory holds only the temporary main file; that file,
  copied **alone** to an isolated directory and opened by a fresh connection,
  has a clean integrity check, the identity, `life_state` (revision 1,
  counters 0), the seed, and exactly one `born` event. A negative control shows
  the same inspection detects data that exists only in a WAL sidecar, and a
  mutation run (WAL birth, check disabled) makes the proof fail.
- Stored as the `maple` row plus a `born` timeline event (revision 1),
  enough to show "Maple was born on 2026-01-01".
- The database also refuses a second `born` event (unique partial index) and
  any change to the `maple` row (triggers).

## Corruption and failure policy

Never invent replacement state. Every case below fails loudly with a
`StorageError` subclass and leaves the file untouched:

| Situation | Result |
|---|---|
| `maple.db` is empty (0 bytes) | `NotAMapleDatabaseError` — not treated as "new" |
| Not a SQLite file / truncated / damaged pages | `CorruptDatabaseError` |
| SQLite file from another application | `NotAMapleDatabaseError` (application_id) |
| Schema newer than the code | `SchemaTooNewError` |
| Migration fails | `MigrationError`; that migration fully rolled back, previous version intact |
| Values smuggled past CHECK constraints | `CorruptDatabaseError` (SQLite's integrity check re-verifies CHECKs) |
| Rows valid for SQL but not for core (e.g. sleeping at the desk, tick after update) | `CorruptStateError` |
| Missing state row, zero or two births, ledger gaps | `CorruptStateError` |
| Crash before COMMIT | Transaction discarded; last committed state loads |
| Interrupted birth | Temporary file discarded; `maple.db` never partially exists |

Recovery from a real corruption is a manual owner decision (restore a
backup). Backups are out of Phase 2 scope.

## Migration model

- `storage/migrations.py`: ordered `Migration(version, name, sql)` tuples,
  numbered 1..N without gaps (validated).
- Each migration runs in one transaction together with its `user_version`
  bump; failure rolls back that migration entirely.
- Shipped migrations are frozen: enum lists are written literally, and a test
  fails if core enums drift from them — the fix is a new migration.
- Tested: fresh install, idempotence, upgrade from v1 with a living Maple to a
  synthetic v2, failure mid-migration, too-new schema.
- A migration may declare `rebuilds_tables` (foreign keys OFF around its
  transaction, restored afterwards) and `capture`/`verify` hooks that run inside
  the transaction before COMMIT (`tests/storage/test_migration_v4.py`).
- Upgrade tests write pre-v4 lives with raw SQL exactly as old releases stored
  them (`tests/storage/legacy_support.py`).

## External databases (D18, ADR-0019)

`maple.db` is Maple's only writable database. External data, starting in
Phase 3 with paolo-core's `/data/monitor/metrics.db`, is read through a
separate read-only datasource in `maplegotchi.storage.external`. That datasource:

- opens a read-only connection (`mode=ro`, `query_only`);
- exposes only SELECT-backed read methods;
- has no write, schema, or migration API;
- shares nothing with `LifeRepository`, `DataDir`, or this database's migrations.

Sensors depend on its read API and never import `sqlite3`.

## Path guard

`storage/datadir.py: DataDir` accepts only relative names made of
`[A-Za-z0-9._-]` components separated by `/`; rejects `.`/`..`, empty
components, absolute and drive paths, backslashes, colons, NUL, Windows device
names, trailing dots, and over-long names; then resolves symlinks/junctions and
requires the result to lie strictly inside the resolved root. Adversarial
tests: `tests/storage/test_datadir.py`. This is in addition to the Phase 7
systemd sandbox.
