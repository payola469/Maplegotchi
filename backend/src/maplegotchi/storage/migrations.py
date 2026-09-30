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
from collections.abc import Sequence
from dataclasses import dataclass

from maplegotchi.storage.errors import MigrationError, SchemaTooNewError

APPLICATION_ID = 0x4D41504C  # "MAPL"


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str


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

MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "initial life state", _V1_INITIAL),
    Migration(2, "factual observations", _V2_OBSERVATIONS),
    Migration(3, "journal", _V3_JOURNAL),
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
        try:
            conn.execute("BEGIN IMMEDIATE")
            for statement in split_statements(migration.sql):
                conn.execute(statement)
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
    return schema_version(conn)
