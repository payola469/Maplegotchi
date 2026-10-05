"""Minimal, ordered SQLite migrations.

- The schema version is SQLite's `PRAGMA user_version`; the file is marked as a
  Maplegotchi database with `PRAGMA application_id`.
- Migrations are numbered 1..N with no gaps and applied in order.
- Each migration runs in its own transaction together with its version bump,
  so a failure rolls back completely and leaves the previous version intact.
- Shipped migrations are frozen text. Never edit one; add a new migration.
  Enum value lists are written out literally (not generated from code) for
  that reason; tests check they still match core's enums.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from maplegotchi.storage.errors import MigrationError, SchemaTooNewError

APPLICATION_ID = 0x4D41504C  # "MAPL"


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str
    # Table rebuilds run with foreign keys OFF (SQLite's documented procedure;
    # the pragma only works outside a transaction) and must pass `verify`.
    rebuilds_tables: bool = False
    # Optional in-transaction check: `capture` before the SQL, `verify` after it,
    # both before COMMIT. `verify` raises to roll the migration back.
    capture: Callable[[sqlite3.Connection], object] | None = None
    verify: Callable[[sqlite3.Connection, object], None] | None = None


_UTC_TS = (
    "GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'"
)

_V1_INITIAL = f"""
CREATE TABLE maple (
    id        INTEGER PRIMARY KEY CHECK (id = 1),
    name      TEXT    NOT NULL CHECK (length(name) BETWEEN 1 AND 32),
    born_at   TEXT    NOT NULL CHECK (born_at {_UTC_TS}),
    life_seed TEXT    NOT NULL CHECK (length(life_seed) = 64 AND life_seed NOT GLOB '*[^0-9a-f]*')
) STRICT;

CREATE TABLE life_state (
    maple_id            INTEGER PRIMARY KEY REFERENCES maple (id),
    revision            INTEGER NOT NULL CHECK (revision >= 1),
    mood                REAL    NOT NULL CHECK (mood BETWEEN 0 AND 100),
    energy              REAL    NOT NULL CHECK (energy BETWEEN 0 AND 100),
    curiosity           REAL    NOT NULL CHECK (curiosity BETWEEN 0 AND 100),
    social              REAL    NOT NULL CHECK (social BETWEEN 0 AND 100),
    activity            TEXT    NOT NULL CHECK (activity IN
                            ('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest')),
    location            TEXT    NOT NULL CHECK (location IN
                            ('bed', 'desk', 'bookshelf', 'window', 'terminal', 'rug')),
    activity_started_at TEXT    NOT NULL CHECK (activity_started_at {_UTC_TS}),
    activity_until      TEXT    NOT NULL CHECK (activity_until {_UTC_TS}),
    last_tick_at        TEXT    NOT NULL CHECK (last_tick_at {_UTC_TS}),
    last_updated_at     TEXT    NOT NULL CHECK (last_updated_at {_UTC_TS}),
    tick_counter        INTEGER NOT NULL CHECK (tick_counter >= 0),
    interaction_counter INTEGER NOT NULL CHECK (interaction_counter >= 0),
    reaction_kind       TEXT    CHECK (reaction_kind IN
                            ('greet_happy', 'greet_sleepy', 'pet_happy', 'pet_sleepy')),
    reaction_variant    INTEGER CHECK (reaction_variant >= 0),
    reaction_started_at TEXT    CHECK (reaction_started_at {_UTC_TS}),
    reaction_until      TEXT    CHECK (reaction_until {_UTC_TS}),
    CHECK ((reaction_kind IS NULL) = (reaction_variant IS NULL)
       AND (reaction_kind IS NULL) = (reaction_started_at IS NULL)
       AND (reaction_kind IS NULL) = (reaction_until IS NULL))
) STRICT;

CREATE TABLE interaction_ledger (
    maple_id INTEGER NOT NULL REFERENCES maple (id),
    position INTEGER NOT NULL CHECK (position BETWEEN 0 AND 9),
    kind     TEXT    NOT NULL CHECK (kind IN ('greet', 'pet')),
    at       TEXT    NOT NULL CHECK (at {_UTC_TS}),
    PRIMARY KEY (maple_id, position)
) STRICT;

CREATE TABLE timeline_event (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    maple_id INTEGER NOT NULL REFERENCES maple (id),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    tick_id  INTEGER CHECK (tick_id >= 1),
    kind     TEXT    NOT NULL CHECK (kind IN
                 ('born', 'activity_changed', 'interaction_accepted', 'downtime_gap')),
    at       TEXT    NOT NULL CHECK (at {_UTC_TS}),
    payload  TEXT    NOT NULL CHECK (json_valid(payload))
) STRICT;

CREATE INDEX timeline_event_by_time ON timeline_event (at);
CREATE UNIQUE INDEX timeline_event_one_birth ON timeline_event (maple_id) WHERE kind = 'born';

CREATE TRIGGER maple_immutable_update BEFORE UPDATE ON maple
BEGIN SELECT RAISE(ABORT, 'maple identity is immutable'); END;

CREATE TRIGGER maple_immutable_delete BEFORE DELETE ON maple
BEGIN SELECT RAISE(ABORT, 'maple identity is immutable'); END;

CREATE TRIGGER life_state_no_delete BEFORE DELETE ON life_state
BEGIN SELECT RAISE(ABORT, 'life state cannot be deleted'); END;

CREATE TRIGGER life_state_revision_advances BEFORE UPDATE ON life_state
WHEN NEW.revision <> OLD.revision + 1
BEGIN SELECT RAISE(ABORT, 'life state revision must advance by exactly one'); END;

CREATE TRIGGER life_state_counters_never_decrease BEFORE UPDATE ON life_state
WHEN NEW.tick_counter < OLD.tick_counter OR NEW.interaction_counter < OLD.interaction_counter
BEGIN SELECT RAISE(ABORT, 'RNG counters never decrease'); END;

CREATE TRIGGER timeline_event_append_only_update BEFORE UPDATE ON timeline_event
BEGIN SELECT RAISE(ABORT, 'timeline is append-only'); END;

CREATE TRIGGER timeline_event_append_only_delete BEFORE DELETE ON timeline_event
BEGIN SELECT RAISE(ABORT, 'timeline is append-only'); END;
"""

_V2_OBSERVATIONS = f"""
CREATE TABLE observation (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    maple_id    INTEGER NOT NULL REFERENCES maple (id),
    revision    INTEGER NOT NULL CHECK (revision >= 1),
    tick_id     INTEGER NOT NULL CHECK (tick_id >= 1),
    observed_at TEXT    NOT NULL CHECK (observed_at {_UTC_TS}),
    metric      TEXT    NOT NULL CHECK (metric IN
                    ('cpu_usage', 'memory_usage', 'disk_usage', 'load_1m', 'load_5m', 'load_15m',
                     'cpu_count', 'temperature', 'service_state')),
    subject     TEXT    NOT NULL CHECK (length(subject) BETWEEN 1 AND 64),
    status      TEXT    NOT NULL CHECK (status IN ('available', 'unavailable', 'unknown', 'error')),
    value       REAL,
    state       TEXT    CHECK (state IN
                    ('active', 'reloading', 'inactive', 'failed', 'activating', 'deactivating',
                     'maintenance', 'refreshing')),
    unit        TEXT    NOT NULL CHECK (unit IN ('percent', 'celsius', 'load', 'count', 'state')),
    source      TEXT    NOT NULL CHECK (length(source) BETWEEN 1 AND 32),
    reason      TEXT    CHECK (length(reason) BETWEEN 1 AND 200),
    CHECK ((status = 'available') = (reason IS NULL)),
    CHECK (status = 'available' OR (value IS NULL AND state IS NULL)),
    CHECK (status <> 'available' OR ((value IS NULL) <> (state IS NULL))),
    UNIQUE (tick_id, metric, subject)
) STRICT;

CREATE TRIGGER observation_append_only_update BEFORE UPDATE ON observation
BEGIN SELECT RAISE(ABORT, 'observations are append-only'); END;

CREATE TRIGGER observation_append_only_delete BEFORE DELETE ON observation
BEGIN SELECT RAISE(ABORT, 'observations are append-only'); END;
"""

_DATE = "GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"

_V3_JOURNAL = f"""
CREATE TABLE journal_entry (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    maple_id       INTEGER NOT NULL REFERENCES maple (id),
    revision       INTEGER NOT NULL CHECK (revision >= 1),
    tick_id        INTEGER CHECK (tick_id >= 1),
    created_at     TEXT    NOT NULL CHECK (created_at {_UTC_TS}),
    category       TEXT    NOT NULL CHECK (category IN
                       ('daily_life', 'server_notice', 'interaction', 'reflection', 'milestone')),
    trigger_kind   TEXT    NOT NULL CHECK (trigger_kind IN
                       ('activity', 'interaction', 'server_problem', 'server_recovery',
                        'daily_reflection', 'milestone')),
    topic          TEXT    NOT NULL CHECK (length(topic) BETWEEN 1 AND 80),
    text           TEXT    NOT NULL CHECK (length(text) BETWEEN 1 AND 240
                                         AND instr(text, char(10)) = 0
                                         AND instr(text, char(13)) = 0),
    importance     TEXT    NOT NULL CHECK (importance IN ('low', 'normal', 'high')),
    brain_kind     TEXT    NOT NULL CHECK (brain_kind IN ('rule', 'external')),
    brain_name     TEXT    NOT NULL CHECK (length(brain_name) BETWEEN 1 AND 32),
    brain_version  TEXT    NOT NULL CHECK (length(brain_version) BETWEEN 1 AND 16),
    template_id    TEXT    NOT NULL CHECK (length(template_id) BETWEEN 1 AND 80),
    activity       TEXT    NOT NULL CHECK (activity IN
                       ('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest')),
    expression     TEXT    NOT NULL CHECK (expression IN
                       ('calm', 'happy', 'curious', 'sleepy', 'focused'))
) STRICT;

CREATE INDEX journal_entry_by_time ON journal_entry (created_at);

CREATE TABLE journal_entry_observation (
    entry_id       INTEGER NOT NULL REFERENCES journal_entry (id),
    observation_id INTEGER NOT NULL REFERENCES observation (id),
    position       INTEGER NOT NULL CHECK (position >= 0),
    PRIMARY KEY (entry_id, position),
    UNIQUE (entry_id, observation_id)
) STRICT;

CREATE TABLE journal_state (
    maple_id                  INTEGER PRIMARY KEY REFERENCES maple (id),
    journal_day               TEXT    CHECK (journal_day {_DATE}),
    daily_seen                TEXT    NOT NULL CHECK (json_valid(daily_seen)),
    interactions_today        INTEGER NOT NULL CHECK (interactions_today >= 0),
    notices_today             INTEGER NOT NULL CHECK (notices_today >= 0),
    last_interaction_entry_at TEXT    CHECK (last_interaction_entry_at {_UTC_TS}),
    active_alerts             TEXT    NOT NULL CHECK (json_valid(active_alerts)),
    last_reflection_day       TEXT    CHECK (last_reflection_day {_DATE}),
    milestones                TEXT    NOT NULL CHECK (json_valid(milestones))
) STRICT;

CREATE TRIGGER journal_entry_append_only_update BEFORE UPDATE ON journal_entry
BEGIN SELECT RAISE(ABORT, 'journal entries are immutable'); END;

CREATE TRIGGER journal_entry_append_only_delete BEFORE DELETE ON journal_entry
BEGIN SELECT RAISE(ABORT, 'journal entries are immutable'); END;

CREATE TRIGGER journal_entry_observation_append_only_update
BEFORE UPDATE ON journal_entry_observation
BEGIN SELECT RAISE(ABORT, 'journal references are immutable'); END;

CREATE TRIGGER journal_entry_observation_append_only_delete
BEFORE DELETE ON journal_entry_observation
BEGIN SELECT RAISE(ABORT, 'journal references are immutable'); END;

CREATE TRIGGER journal_state_no_delete BEFORE DELETE ON journal_state
BEGIN SELECT RAISE(ABORT, 'journal state cannot be deleted'); END;
"""

_ACTIVITIES_V4 = "('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest', 'think')"
_GOAL_TYPES_V4 = (
    "('learn', 'create', 'recover', 'reflect', 'monitor', 'socialize', 'explore', 'organize',"
    " 'maintain', 'practice', 'plan', 'wait', 'play', 'help', 'investigate', 'remember')"
)
_PRIORITIES_V4 = "('critical', 'high', 'normal', 'low')"
_ONE_LINE = "instr({col}, char(10)) = 0 AND instr({col}, char(13)) = 0"

# Schema v4 (ADR-0026/0027/0028): activity set v2, movement, goals, decisions,
# action lifecycle. Tables whose CHECK lists change are rebuilt (SQLite cannot
# alter a CHECK): life_state, timeline_event, journal_entry. Runs with foreign
# keys OFF (set outside the transaction by `migrate`, per SQLite's documented
# table-rebuild procedure); `_v4_verify` runs foreign_key_check and checks that
# identity, state, counters and history survived, before COMMIT.
_V4_AUTONOMY = f"""
CREATE TABLE goal (
    id            INTEGER PRIMARY KEY CHECK (id >= 1),
    maple_id      INTEGER NOT NULL REFERENCES maple (id),
    revision      INTEGER NOT NULL CHECK (revision >= 1),
    goal_type     TEXT    NOT NULL CHECK (goal_type IN {_GOAL_TYPES_V4}),
    summary       TEXT    NOT NULL CHECK (length(summary) BETWEEN 1 AND 120
                                        AND {_ONE_LINE.format(col="summary")}),
    source        TEXT    NOT NULL CHECK (source IN ('rule', 'external')),
    decision_id   INTEGER REFERENCES decision (id),
    started_at    TEXT    NOT NULL CHECK (started_at {_UTC_TS}),
    horizon_until TEXT    NOT NULL CHECK (horizon_until {_UTC_TS})
) STRICT;

CREATE TABLE decision (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    maple_id                  INTEGER NOT NULL REFERENCES maple (id),
    revision                  INTEGER NOT NULL CHECK (revision >= 1),
    at                        TEXT    NOT NULL CHECK (at {_UTC_TS}),
    trigger                   TEXT    NOT NULL CHECK (trigger IN
                                  ('action_completed', 're_evaluate', 'no_plan', 'overdue',
                                   'critical')),
    priority                  TEXT    CHECK (priority IN {_PRIORITIES_V4}),
    director_kind             TEXT    NOT NULL CHECK (director_kind IN ('rule', 'external')),
    director_name             TEXT    NOT NULL CHECK (length(director_name) BETWEEN 1 AND 32),
    director_version          TEXT    NOT NULL CHECK (length(director_version) BETWEEN 1 AND 16),
    context_summary           TEXT    NOT NULL CHECK (length(context_summary) BETWEEN 1 AND 400
                                          AND {_ONE_LINE.format(col="context_summary")}),
    proposed_goal_op          TEXT    CHECK (proposed_goal_op IN
                                  ('keep', 'new', 'complete', 'resume', 'abandon')),
    proposed_goal_type        TEXT    CHECK (proposed_goal_type IN {_GOAL_TYPES_V4}),
    proposed_goal_summary     TEXT    CHECK (length(proposed_goal_summary) BETWEEN 1 AND 120
                                          AND {_ONE_LINE.format(col="proposed_goal_summary")}),
    proposed_horizon_minutes  REAL,
    proposed_abandon_reason   TEXT    CHECK (length(proposed_abandon_reason) BETWEEN 1 AND 40),
    proposed_action           TEXT    CHECK (proposed_action IN {_ACTIVITIES_V4}),
    proposed_duration_minutes REAL,
    proposed_reason           TEXT    CHECK (length(proposed_reason) BETWEEN 1 AND 240
                                          AND {_ONE_LINE.format(col="proposed_reason")}),
    verdict                   TEXT    NOT NULL CHECK (verdict IN
                                  ('accepted', 'clamped', 'rejected', 'fallback', 'stale')),
    reason_code               TEXT    CHECK (length(reason_code) BETWEEN 1 AND 40),
    clamped                   TEXT    CHECK (clamped IS NULL OR json_valid(clamped)),
    executed_by               TEXT    CHECK (executed_by IN ('rule', 'external')),
    executed_reason           TEXT    CHECK (length(executed_reason) BETWEEN 1 AND 240
                                          AND {_ONE_LINE.format(col="executed_reason")}),
    goal_id                   INTEGER CHECK (goal_id >= 1),
    action_id                 INTEGER CHECK (action_id >= 0),
    executed_action           TEXT    CHECK (executed_action IN {_ACTIVITIES_V4}),
    executed_point            TEXT    CHECK (length(executed_point) BETWEEN 1 AND 40),
    executed_duration_minutes INTEGER CHECK (executed_duration_minutes >= 1),
    latency_ms                INTEGER CHECK (latency_ms >= 0)
) STRICT;

CREATE INDEX decision_by_time ON decision (at);

CREATE TABLE action_event (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    maple_id  INTEGER NOT NULL REFERENCES maple (id),
    revision  INTEGER NOT NULL CHECK (revision >= 1),
    action_id INTEGER NOT NULL CHECK (action_id >= 0),
    goal_id   INTEGER CHECK (goal_id >= 1),
    kind      TEXT    NOT NULL CHECK (kind IN
                  ('destination_selected', 'walking_started', 'walking_cancelled', 'arrived',
                   'activity_started', 'activity_completed', 'activity_interrupted',
                   'activity_resumed', 'needs_attention')),
    at        TEXT    NOT NULL CHECK (at {_UTC_TS}),
    priority  TEXT    CHECK (priority IN {_PRIORITIES_V4}),
    payload   TEXT    NOT NULL CHECK (json_valid(payload))
) STRICT;

CREATE INDEX action_event_by_action ON action_event (action_id);

CREATE TABLE life_state_v4 (
    maple_id            INTEGER PRIMARY KEY REFERENCES maple (id),
    revision            INTEGER NOT NULL CHECK (revision >= 1),
    mood                REAL    NOT NULL CHECK (mood BETWEEN 0 AND 100),
    energy              REAL    NOT NULL CHECK (energy BETWEEN 0 AND 100),
    curiosity           REAL    NOT NULL CHECK (curiosity BETWEEN 0 AND 100),
    social              REAL    NOT NULL CHECK (social BETWEEN 0 AND 100),
    activity            TEXT    NOT NULL CHECK (activity IN {_ACTIVITIES_V4}),
    location            TEXT    NOT NULL CHECK (location IN
                            ('bed', 'desk', 'bookshelf', 'window', 'terminal', 'rug', 'sofa')),
    activity_started_at TEXT    NOT NULL CHECK (activity_started_at {_UTC_TS}),
    activity_until      TEXT    NOT NULL CHECK (activity_until {_UTC_TS}),
    last_tick_at        TEXT    NOT NULL CHECK (last_tick_at {_UTC_TS}),
    last_updated_at     TEXT    NOT NULL CHECK (last_updated_at {_UTC_TS}),
    tick_counter        INTEGER NOT NULL CHECK (tick_counter >= 0),
    interaction_counter INTEGER NOT NULL CHECK (interaction_counter >= 0),
    reaction_kind       TEXT    CHECK (reaction_kind IN
                            ('greet_happy', 'greet_sleepy', 'pet_happy', 'pet_sleepy')),
    reaction_variant    INTEGER CHECK (reaction_variant >= 0),
    reaction_started_at TEXT    CHECK (reaction_started_at {_UTC_TS}),
    reaction_until      TEXT    CHECK (reaction_until {_UTC_TS}),
    point_id            TEXT    CHECK (length(point_id) BETWEEN 1 AND 40),
    route_departed_at   TEXT    CHECK (route_departed_at {_UTC_TS}),
    route_from_activity TEXT    CHECK (route_from_activity IN {_ACTIVITIES_V4}),
    route_path          TEXT    CHECK (route_path IS NULL OR json_valid(route_path)),
    needs_at            TEXT    CHECK (needs_at {_UTC_TS}),
    decision_counter    INTEGER NOT NULL DEFAULT 0 CHECK (decision_counter >= 0),
    action_counter      INTEGER NOT NULL DEFAULT 0 CHECK (action_counter >= 0),
    goal_counter        INTEGER NOT NULL DEFAULT 0 CHECK (goal_counter >= 0),
    action_priority     TEXT    NOT NULL DEFAULT 'normal' CHECK (action_priority IN
                            {_PRIORITIES_V4}),
    active_goal_id      INTEGER REFERENCES goal (id),
    suspended_goal_id   INTEGER REFERENCES goal (id),
    suspended_action    TEXT    CHECK (suspended_action IN {_ACTIVITIES_V4}),
    decision_due_since  TEXT    CHECK (decision_due_since {_UTC_TS}),
    CHECK ((reaction_kind IS NULL) = (reaction_variant IS NULL)
       AND (reaction_kind IS NULL) = (reaction_started_at IS NULL)
       AND (reaction_kind IS NULL) = (reaction_until IS NULL)),
    CHECK ((route_path IS NULL) = (route_departed_at IS NULL)
       AND (route_path IS NULL) = (route_from_activity IS NULL)),
    CHECK (active_goal_id IS NULL OR suspended_goal_id IS NULL
           OR active_goal_id <> suspended_goal_id),
    CHECK ((suspended_goal_id IS NULL) = (suspended_action IS NULL))
) STRICT;

INSERT INTO life_state_v4 (
    maple_id, revision, mood, energy, curiosity, social, activity, location,
    activity_started_at, activity_until, last_tick_at, last_updated_at,
    tick_counter, interaction_counter,
    reaction_kind, reaction_variant, reaction_started_at, reaction_until)
SELECT
    maple_id, revision, mood, energy, curiosity, social, activity,
    CASE activity
        WHEN 'rest' THEN 'sofa'
        WHEN 'idle' THEN 'rug'
        WHEN 'walk' THEN 'rug'
        ELSE location
    END,
    activity_started_at, activity_until, last_tick_at, last_updated_at,
    tick_counter, interaction_counter,
    reaction_kind, reaction_variant, reaction_started_at, reaction_until
FROM life_state;

DROP TABLE life_state;

ALTER TABLE life_state_v4 RENAME TO life_state;

CREATE TRIGGER life_state_no_delete BEFORE DELETE ON life_state
BEGIN SELECT RAISE(ABORT, 'life state cannot be deleted'); END;

CREATE TRIGGER life_state_revision_advances BEFORE UPDATE ON life_state
WHEN NEW.revision <> OLD.revision + 1
BEGIN SELECT RAISE(ABORT, 'life state revision must advance by exactly one'); END;

CREATE TRIGGER life_state_counters_never_decrease BEFORE UPDATE ON life_state
WHEN NEW.tick_counter < OLD.tick_counter OR NEW.interaction_counter < OLD.interaction_counter
  OR NEW.decision_counter < OLD.decision_counter OR NEW.action_counter < OLD.action_counter
  OR NEW.goal_counter < OLD.goal_counter
BEGIN SELECT RAISE(ABORT, 'RNG counters never decrease'); END;

CREATE TABLE timeline_event_v4 (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    maple_id INTEGER NOT NULL REFERENCES maple (id),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    tick_id  INTEGER CHECK (tick_id >= 1),
    kind     TEXT    NOT NULL CHECK (kind IN
                 ('born', 'activity_changed', 'interaction_accepted', 'downtime_gap',
                  'goal_started', 'goal_suspended', 'goal_resumed', 'goal_completed',
                  'goal_abandoned')),
    at       TEXT    NOT NULL CHECK (at {_UTC_TS}),
    payload  TEXT    NOT NULL CHECK (json_valid(payload))
) STRICT;

INSERT INTO timeline_event_v4 (id, maple_id, revision, tick_id, kind, at, payload)
SELECT id, maple_id, revision, tick_id, kind, at, payload FROM timeline_event ORDER BY id;

DROP TABLE timeline_event;

ALTER TABLE timeline_event_v4 RENAME TO timeline_event;

CREATE INDEX timeline_event_by_time ON timeline_event (at);

CREATE UNIQUE INDEX timeline_event_one_birth ON timeline_event (maple_id) WHERE kind = 'born';

CREATE TRIGGER timeline_event_append_only_update BEFORE UPDATE ON timeline_event
BEGIN SELECT RAISE(ABORT, 'timeline is append-only'); END;

CREATE TRIGGER timeline_event_append_only_delete BEFORE DELETE ON timeline_event
BEGIN SELECT RAISE(ABORT, 'timeline is append-only'); END;

CREATE TABLE journal_entry_v4 (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    maple_id       INTEGER NOT NULL REFERENCES maple (id),
    revision       INTEGER NOT NULL CHECK (revision >= 1),
    tick_id        INTEGER CHECK (tick_id >= 1),
    created_at     TEXT    NOT NULL CHECK (created_at {_UTC_TS}),
    category       TEXT    NOT NULL CHECK (category IN
                       ('daily_life', 'server_notice', 'interaction', 'reflection', 'milestone')),
    trigger_kind   TEXT    NOT NULL CHECK (trigger_kind IN
                       ('activity', 'interaction', 'server_problem', 'server_recovery',
                        'daily_reflection', 'milestone')),
    topic          TEXT    NOT NULL CHECK (length(topic) BETWEEN 1 AND 80),
    text           TEXT    NOT NULL CHECK (length(text) BETWEEN 1 AND 240
                                         AND instr(text, char(10)) = 0
                                         AND instr(text, char(13)) = 0),
    importance     TEXT    NOT NULL CHECK (importance IN ('low', 'normal', 'high')),
    brain_kind     TEXT    NOT NULL CHECK (brain_kind IN ('rule', 'external')),
    brain_name     TEXT    NOT NULL CHECK (length(brain_name) BETWEEN 1 AND 32),
    brain_version  TEXT    NOT NULL CHECK (length(brain_version) BETWEEN 1 AND 16),
    template_id    TEXT    NOT NULL CHECK (length(template_id) BETWEEN 1 AND 80),
    activity       TEXT    NOT NULL CHECK (activity IN {_ACTIVITIES_V4}),
    expression     TEXT    NOT NULL CHECK (expression IN
                       ('calm', 'happy', 'curious', 'sleepy', 'focused'))
) STRICT;

INSERT INTO journal_entry_v4 (id, maple_id, revision, tick_id, created_at, category, trigger_kind,
    topic, text, importance, brain_kind, brain_name, brain_version, template_id, activity,
    expression)
SELECT id, maple_id, revision, tick_id, created_at, category, trigger_kind, topic, text,
    importance, brain_kind, brain_name, brain_version, template_id, activity, expression
FROM journal_entry ORDER BY id;

DROP TABLE journal_entry;

ALTER TABLE journal_entry_v4 RENAME TO journal_entry;

CREATE INDEX journal_entry_by_time ON journal_entry (created_at);

CREATE TRIGGER journal_entry_append_only_update BEFORE UPDATE ON journal_entry
BEGIN SELECT RAISE(ABORT, 'journal entries are immutable'); END;

CREATE TRIGGER journal_entry_append_only_delete BEFORE DELETE ON journal_entry
BEGIN SELECT RAISE(ABORT, 'journal entries are immutable'); END;

CREATE TRIGGER goal_append_only_update BEFORE UPDATE ON goal
BEGIN SELECT RAISE(ABORT, 'goals are immutable'); END;

CREATE TRIGGER goal_append_only_delete BEFORE DELETE ON goal
BEGIN SELECT RAISE(ABORT, 'goals are immutable'); END;

CREATE TRIGGER decision_append_only_update BEFORE UPDATE ON decision
BEGIN SELECT RAISE(ABORT, 'decisions are append-only'); END;

CREATE TRIGGER decision_append_only_delete BEFORE DELETE ON decision
BEGIN SELECT RAISE(ABORT, 'decisions are append-only'); END;

CREATE TRIGGER action_event_append_only_update BEFORE UPDATE ON action_event
BEGIN SELECT RAISE(ABORT, 'action events are append-only'); END;

CREATE TRIGGER action_event_append_only_delete BEFORE DELETE ON action_event
BEGIN SELECT RAISE(ABORT, 'action events are append-only'); END;
"""  # noqa: S608 - fixed schema text built only from the constants above


def _v4_capture(conn: sqlite3.Connection) -> dict[str, object]:
    """What schema v4 must preserve exactly (ADR-0028 §3, in-transaction verification)."""
    return {
        "maple": conn.execute("SELECT id, name, born_at, life_seed FROM maple").fetchall(),
        "state": conn.execute(
            "SELECT maple_id, revision, mood, energy, curiosity, social, activity,"
            " activity_started_at, activity_until, last_tick_at, last_updated_at,"
            " tick_counter, interaction_counter, reaction_kind, reaction_variant,"
            " reaction_started_at, reaction_until FROM life_state"
        ).fetchall(),
        "ledger": conn.execute("SELECT * FROM interaction_ledger ORDER BY position").fetchall(),
        "timeline": conn.execute(
            "SELECT count(*), max(id), coalesce((SELECT seq FROM sqlite_sequence"
            " WHERE name = 'timeline_event'), 0) FROM timeline_event"
        ).fetchone(),
        "journal": conn.execute(
            "SELECT count(*), max(id), coalesce((SELECT seq FROM sqlite_sequence"
            " WHERE name = 'journal_entry'), 0) FROM journal_entry"
        ).fetchone(),
        "journal_refs": conn.execute("SELECT count(*) FROM journal_entry_observation").fetchone(),
        "observations": conn.execute("SELECT count(*), max(id) FROM observation").fetchone(),
    }


def _v4_verify(conn: sqlite3.Connection, before: object) -> None:
    after = _v4_capture(conn)
    if after != before:
        changed = sorted(k for k in after if after[k] != before[k])  # type: ignore[index]
        raise MigrationError(f"schema v4 would change preserved data: {changed}")
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise MigrationError("schema v4 foreign key check failed")


# Schema v5 (ADR-0026 §7): remember that a serious problem is being handled, so a
# critical interruption happens once per problem, not at every heartbeat.
_V5_CRITICAL = f"""
ALTER TABLE life_state ADD COLUMN critical_since TEXT CHECK (critical_since {_UTC_TS});
"""

# Schema v6 (ADR-0029): what a read/write action is about, Maple's document
# workspace, and reader/writer provenance. Both new tables are append-only.
_V6_TOOLS = f"""
ALTER TABLE life_state ADD COLUMN task_tool TEXT CHECK (task_tool IN ('reader', 'writer'));

ALTER TABLE life_state ADD COLUMN task_target TEXT CHECK (length(task_target) BETWEEN 1 AND 60);

ALTER TABLE life_state ADD COLUMN task_title TEXT CHECK (length(task_title) BETWEEN 1 AND 80);

ALTER TABLE life_state ADD COLUMN task_category TEXT
    CHECK (length(task_category) BETWEEN 1 AND 40);

CREATE TABLE document (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    maple_id   INTEGER NOT NULL REFERENCES maple (id),
    revision   INTEGER NOT NULL CHECK (revision >= 1),
    kind       TEXT    NOT NULL CHECK (kind IN ('note', 'summary', 'reflection', 'research')),
    title      TEXT    NOT NULL CHECK (length(title) BETWEEN 1 AND 80
                                   AND instr(title, char(10)) = 0),
    body       TEXT    NOT NULL CHECK (length(body) BETWEEN 1 AND 4000),
    created_at TEXT    NOT NULL CHECK (created_at {_UTC_TS}),
    action_id  INTEGER NOT NULL CHECK (action_id >= 0),
    goal_id    INTEGER CHECK (goal_id >= 1),
    sources    TEXT    NOT NULL CHECK (json_valid(sources))
) STRICT;

CREATE TABLE tool_use (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    maple_id    INTEGER NOT NULL REFERENCES maple (id),
    revision    INTEGER NOT NULL CHECK (revision >= 1),
    at          TEXT    NOT NULL CHECK (at {_UTC_TS}),
    action_id   INTEGER NOT NULL CHECK (action_id >= 0),
    goal_id     INTEGER CHECK (goal_id >= 1),
    tool        TEXT    NOT NULL CHECK (tool IN ('reader', 'writer')),
    operation   TEXT    NOT NULL CHECK (operation IN
                    ('read_started', 'read_completed', 'read_failed',
                     'write_started', 'write_completed', 'write_failed')),
    target      TEXT    NOT NULL CHECK (length(target) BETWEEN 1 AND 60),
    title       TEXT    NOT NULL CHECK (length(title) BETWEEN 1 AND 80),
    category    TEXT    NOT NULL CHECK (length(category) BETWEEN 1 AND 40),
    status      TEXT    NOT NULL CHECK (status IN ('success', 'failure')),
    detail      TEXT    CHECK (length(detail) BETWEEN 1 AND 200
                               AND instr(detail, char(10)) = 0),
    chars       INTEGER CHECK (chars >= 0),
    document_id INTEGER REFERENCES document (id)
) STRICT;

CREATE INDEX tool_use_by_action ON tool_use (action_id);

CREATE TRIGGER document_append_only_update BEFORE UPDATE ON document
BEGIN SELECT RAISE(ABORT, 'documents are append-only'); END;

CREATE TRIGGER document_append_only_delete BEFORE DELETE ON document
BEGIN SELECT RAISE(ABORT, 'documents are append-only'); END;

CREATE TRIGGER tool_use_append_only_update BEFORE UPDATE ON tool_use
BEGIN SELECT RAISE(ABORT, 'tool provenance is append-only'); END;

CREATE TRIGGER tool_use_append_only_delete BEFORE DELETE ON tool_use
BEGIN SELECT RAISE(ABORT, 'tool provenance is append-only'); END;
"""

MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "initial life state", _V1_INITIAL),
    Migration(2, "factual observations", _V2_OBSERVATIONS),
    Migration(3, "journal", _V3_JOURNAL),
    Migration(
        4,
        "autonomy: activity set v2, movement, goals, decisions, action events",
        _V4_AUTONOMY,
        rebuilds_tables=True,
        capture=_v4_capture,
        verify=_v4_verify,
    ),
    Migration(5, "goals: critical interruption tracking", _V5_CRITICAL),
    Migration(6, "reader/writer: task, workspace documents, provenance", _V6_TOOLS),
)


def validate_migrations(migrations: Sequence[Migration]) -> None:
    versions = [m.version for m in migrations]
    if versions != list(range(1, len(migrations) + 1)):
        raise MigrationError(f"migrations must be numbered 1..N in order, got {versions}")


def latest_version(migrations: Sequence[Migration] = MIGRATIONS) -> int:
    return migrations[-1].version if migrations else 0


def split_statements(sql: str) -> list[str]:
    """Split a script into complete statements (trigger bodies stay intact)."""
    statements: list[str] = []
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            if statement:
                statements.append(statement)
            buffer = ""
    if buffer.strip():
        raise MigrationError("migration ends with an incomplete statement")
    return statements


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def migrate(conn: sqlite3.Connection, migrations: Sequence[Migration] = MIGRATIONS) -> int:
    """Bring the database to the latest version. Returns the resulting version."""
    validate_migrations(migrations)
    current = schema_version(conn)
    target = latest_version(migrations)
    if current > target:
        raise SchemaTooNewError(f"database schema v{current} is newer than supported v{target}")
    for migration in migrations[current:]:
        foreign_keys = bool(conn.execute("PRAGMA foreign_keys").fetchone()[0])
        try:
            if migration.rebuilds_tables:
                conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("BEGIN IMMEDIATE")
            before = migration.capture(conn) if migration.capture else None
            for statement in split_statements(migration.sql):
                conn.execute(statement)
            if migration.verify is not None:
                migration.verify(conn, before)
            if migration.version == 1:
                conn.execute(f"PRAGMA application_id = {APPLICATION_ID:d}")
            conn.execute(f"PRAGMA user_version = {migration.version:d}")
            conn.execute("COMMIT")
        except Exception as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise MigrationError(
                f"migration {migration.version} ({migration.name}) failed; "
                f"database left at v{schema_version(conn)}"
            ) from exc
        finally:
            if migration.rebuilds_tables and foreign_keys:
                conn.execute("PRAGMA foreign_keys = ON")
    return schema_version(conn)
