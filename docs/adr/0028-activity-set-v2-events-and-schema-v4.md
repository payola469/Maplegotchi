# ADR-0028: Activity set v2, life event model, and schema v4 with rollback/recovery

- **Status:** Accepted — FIXED (CLAUDE.md D27)
- **Date:** 2026-10-05
- **Decided by:** owner (2026-10-05: add `think` and the new room locations;
  separate `decision` and `action_event` tables; only goal-level significant
  events on the timeline; the rollback/recovery strategy must be fixed before any
  migration code is written). Tuning numbers are [PROPOSED].
- **Amends:** the FIXED activity set (CLAUDE.md §5), ADR-0023 (states this
  migration's rollback story, as ADR-0023 requires of every migration).
  **Preserves:** ADR-0024 (nightly backup), identity/seed immutability, append-only
  history. **Related:** ADR-0026, ADR-0027.

## Context

ADR-0026 and ADR-0027 add goals, an action plan, decisions, and movement. They
require a new activity (`think`), a new location (`sofa`), new persisted state,
and new append-only records. SQLite cannot alter a CHECK constraint in place, so
`life_state` and `timeline_event` must be rebuilt. Maple's database is
irreplaceable (identity, `born_at`, seed, history), and D22 forbids downgrading a
database, so the way back must be decided first.

## Decision

### 1. Activity set v2
`Activity` = `idle`, `walk`, `sleep`, `read`, `write`, `observe_server`, `rest`,
**`think`**. `RoomLocation` adds **`sofa`**. Expressions are unchanged (`think`
uses the general expression rules; no new expression).

| Activity | Duration (min) | Location (ADR-0027) | Change from v1 |
|---|---|---|---|
| read | 20–60 | bookshelf | — |
| write | 15–45 | desk (Writing Desk) | was 20–50 |
| observe_server | 5–15 | terminal (Computer Desk) | was 10–30 |
| think | 5–15 | window (Window / Plant Corner) | new |
| rest | 15–45 | sofa | was bed or rug |
| walk | 5–20 | rug (Open Area) | was 5–15, four locations |
| idle | 5–30 | rug (Open Area) | was 10–30, rug or window |
| sleep | 90–240 per segment, renewed at night | bed | — (existing wake rules kept) |

- `think` need rates [PROPOSED]: energy −1.5/h, curiosity −4/h, mood +1/h, and a
  modest daytime score in rule direction. All other need rates and scores are
  unchanged.
- Activities may end early when core records a completion condition (accepted
  Director `complete`, or an interrupt); no new early-completion rules are added
  here.
- Because durations and locations change, the pinned 30-day simulation digest and
  location-specific tests are updated deliberately in the same change; every
  other existing test must pass unchanged.

### 2. Life event model (one model, three stores, one bus)
All events share one envelope, used by REST, SSE, and future Discord/iOS
consumers:
`{id, type, at, revision, goal_id | null, action_id | null, priority | null, payload}`.

| Store | Event types | Why |
|---|---|---|
| `timeline_event` (existing; significant life events) | existing kinds + `goal_started`, `goal_suspended`, `goal_resumed`, `goal_completed`, `goal_abandoned` | goal-level milestones only |
| `action_event` (new, append-only) | `destination_selected`, `walking_started`, `walking_cancelled`, `arrived`, `activity_started`, `activity_completed`, `activity_interrupted`, `activity_resumed`, `needs_attention` | fine-grained action lifecycle; would flood the timeline |
| `decision` (new, append-only) | presented as `goal_proposed`, `decision_rejected` (and accepted/clamped/fallback/stale verdicts) | audit of each decision transition |

- `activity_changed` stays on the timeline with its v1 meaning, now recorded when
  an activity actually begins (at arrival).
- `activity_resumed` is used when, after an interruption, the resumed goal
  continues the same action kind that was interrupted.
- The existing `EventHub` is the only live bus: new SSE kinds `action` and
  `decision` carry lists of envelopes; `timeline` carries the new goal kinds.
  REST (additive): `GET /api/room`, `GET /api/decisions`, `GET /api/actions`
  (paged by id), and additive `goal` / `action` fields in the snapshot. No
  existing field changes meaning or disappears.

### 3. Schema v4 (one migration, one transaction)
1. **Rebuild `life_state`** (single row) with: `think` and `sofa` in its CHECKs;
   new columns `decision_counter`, `active_goal_id`, `suspended_goal_id`,
   `decision_due_since`, and the plan columns (`plan_point`, `plan_path` JSON,
   `plan_departed_at`, `plan_arrives_at`, `plan_started_from` JSON); all existing
   values copied; existing triggers recreated. v3 rows are converted as ADR-0027
   specifies (zero-length plan at the canonical point; no fabricated events).
2. **Rebuild `timeline_event`** with the five goal kinds added to its CHECK:
   rows copied with their ids, `sqlite_sequence` preserved, indexes (incl. the
   one-birth unique index) and append-only triggers recreated.
3. **Create** `goal` (immutable definition rows: id, type, summary, source,
   decision_id, started_at, horizon_until), `decision`, and `action_event`, each
   with STRICT CHECKs and append-only triggers. `decision` columns: id, revision,
   at, trigger, director kind/name/version, context_summary, proposed goal
   op/type/summary/horizon, proposed action/duration, reason, verdict,
   reason_code, clamped originals, executed goal_id/action/point. No column may
   hold a prompt or a raw model response.
4. `user_version = 4`.

Neither rebuilt table is referenced by a foreign key, and the rebuilt tables'
own references (to `maple`) are unchanged, so the rebuild runs with foreign keys
on. SQLite's implicit delete on `DROP TABLE` does not fire triggers, so the
append-only triggers do not block the rebuild; they are recreated before commit.

**In-transaction verification** (any failure raises → whole migration rolls
back, database stays v3):
- `maple` row unchanged (name, `born_at`, `life_seed`);
- `life_state` revision, needs, counters, and interaction ledger unchanged;
- `timeline_event` row count and max id unchanged;
- `PRAGMA foreign_key_check` empty;
- the converted state loads through core invariants (checked again at startup).

### 4. Rollback and recovery strategy (normative)

**R1 — Forward-only.** No down-migration code ships. A downgrade would have to
discard goals, decisions, and action history and remap `think`/`sofa` states; an
untested reverse path on irreplaceable data is a worse risk than a documented
restore.

**R2 — Two verified pre-migration copies before v4 touches the database.**
- *Automatic (all environments, incl. local dev):* before applying any migration
  ≥ 4 to an existing database, `maplegotchi.storage` writes
  `MAPLE_DATA_DIR/pre-migration/maple.v3.<UTC timestamp>.db` with the SQLite
  online backup API through the `DataDir` write jail: journal mode DELETE (one
  self-contained file), `integrity_check` = `ok`, Maplegotchi `application_id`,
  `user_version` = 3, mode 0600, fsync, atomic rename. If any step fails,
  **migration is refused**, Maple does not start, and `maple.db` is untouched.
  The copy is never deleted, pruned, or restored automatically.
- *Owner-held (paolo-core):* unchanged ADR-0023 gate — `activate_release.sh`
  refuses the v4 release without `--allow-migration`, which the owner passes only
  after `maple-db-snapshot stage --source /data/maple/maple.db --dest
  /root/maple-pre-<sha>.db` succeeded. This copy is outside the service's writable
  area.

**R3 — Atomic migration.** Steps §3.1–4 and the verification run in one
`BEGIN IMMEDIATE` transaction (existing `migrate()` model). Failure ⇒
`MigrationError`, database still v3 and still usable by the previous release.

**R4 — Startup check after migrating.** The migrated state must load through
core invariants and the repository; otherwise Maple refuses to start (no repair,
no automatic restore). The pre-migration copies are intact.

**R5 — Recovery decision table.**
| Situation | Remedy | Data loss |
|---|---|---|
| AI misbehaves | `MAPLE_DIRECTOR=rule`, restart | none |
| v4 code bug, database fine | **forward-fix** on schema v4 (preferred), `activate_release.sh <fixed-sha>` | none |
| Migration failed | nothing to undo (still v3); fix and redeploy | none |
| Must return to a pre-v4 release | owner-run restore (R6) | life lived since migration |
| Corruption after migration | restore the latest nightly restic `maple.db` (v4, ADR-0024) with the v4 release; or R6 | since that backup |

**R6 — Owner-run restore to v3** (documented in `deploy/install.md` with the
migration PR; never automatic, never run by Maple):
1. `systemctl stop maplegotchi`.
2. Move `maple.db`, `maple.db-wal`, `maple.db-shm` to a dated quarantine directory
   (not deleted).
3. `maple-db-snapshot verify` the chosen v3 copy (`integrity_check` ok,
   `user_version` 3).
4. Install it as `/data/maple/maple.db`, `maple-svc:maple-svc` 0600.
5. `activate_release.sh <pre-v4 sha>` (its schema check now passes), start, run
   `check_boundaries.py`.
Identity, `born_at`, seed, and all v3 history return exactly; everything lived
after the migration is lost (it remains only in the quarantined v4 file). A later
re-upgrade migrates the restored v3 file again with fresh copies (R2).

**R7 — Required tests before the migration merges.** A realistic v3 fixture
(including `rest`@`bed`, `idle`@`window`, `walk`@`desk`, journal, observations,
interaction ledger) migrates with identity, seed, counters, and timeline intact;
an injected failure mid-migration leaves v3 intact and the snapshot present; a
snapshot failure refuses migration without touching `maple.db`; a v3 release
refuses the v4 file (`SchemaTooNewError`); the automatic snapshot passes
`maple-db-snapshot verify` and opens as a working v3 life in the previous code.

**R8 — Backup.** ADR-0024's nightly job stages `maple.db` as before (the helper
accepts any migrated `user_version`). Files in `pre-migration/` are not added to
the restic paths automatically; the owner copies them off-host if wanted.

## Consequences
- The activity/location set is no longer the v1 FIXED set; CLAUDE.md §5 and the
  frozen-enum migration tests move to v2.
- A one-time, bounded write of a database-sized file in `/data/maple` at
  migration; no new path outside the write jail; no sandbox change.
- Rolling back past v4 is possible but always an explicit owner decision with
  known loss; forward-fix is the default.
- `docs/persistence.md`, `docs/deployment.md`, `docs/api.md`, and
  `deploy/install.md` must be updated in the same change as the migration.
