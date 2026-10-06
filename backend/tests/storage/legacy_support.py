"""Pre-v4 databases written with raw SQL, exactly as older releases stored them.

Current code can no longer produce v1-v3 rows (the repository writes v4
columns), so upgrade tests build their old lives here, row by row.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from maplegotchi.storage.migrations import MIGRATIONS, migrate

LEGACY_SEED = "7a" * 32
LEGACY_BORN = "2026-01-01T00:00:00+00:00"


def _ts(base: datetime, minutes: float) -> str:
    return (base + timedelta(minutes=minutes)).isoformat()


def write_legacy_life(
    conn: sqlite3.Connection,
    *,
    version: int,
    activity: str = "rest",
    location: str = "bed",
    ticks: int = 12,
) -> None:
    """A Maple lived under schema `version` (1-3): identity, state, ledger, history.

    The state's (activity, location) may be a pair that v1-v3 allowed but v4 does
    not (rest@bed, idle@window, walk@desk...), which the v4 migration must convert.
    """
    assert 1 <= version <= 3
    assert migrate(conn, MIGRATIONS[:version]) == version
    born = datetime.fromisoformat(LEGACY_BORN)
    last = _ts(born, 5 * ticks)
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO maple (id, name, born_at, life_seed) VALUES (1, 'Maple', ?, ?)",
        (LEGACY_BORN, LEGACY_SEED),
    )
    conn.execute(
        "INSERT INTO life_state (maple_id, revision, mood, energy, curiosity, social, activity,"
        " location, activity_started_at, activity_until, last_tick_at, last_updated_at,"
        " tick_counter, interaction_counter, reaction_kind, reaction_variant,"
        " reaction_started_at, reaction_until)"
        " VALUES (1, ?, 61.5, 72.25, 40.0, 55.0, ?, ?, ?, ?, ?, ?, ?, 2, 'pet_happy', 1, ?, ?)",
        (
            ticks + 3,
            activity,
            location,
            _ts(born, 5 * ticks - 10),
            _ts(born, 5 * ticks + 20),
            last,
            last,
            ticks,
            last,
            (born + timedelta(minutes=5 * ticks, seconds=8)).isoformat(),
        ),
    )
    conn.execute(
        "INSERT INTO interaction_ledger (maple_id, position, kind, at) VALUES (1, 0, 'greet', ?)",
        (_ts(born, 5 * ticks - 1),),
    )
    conn.execute(
        "INSERT INTO interaction_ledger (maple_id, position, kind, at) VALUES (1, 1, 'pet', ?)",
        (last,),
    )
    conn.execute(
        "INSERT INTO timeline_event (maple_id, revision, tick_id, kind, at, payload)"
        " VALUES (1, 1, NULL, 'born', ?, '{\"name\":\"Maple\"}')",
        (LEGACY_BORN,),
    )
    for tick in range(1, ticks + 1):
        conn.execute(
            "INSERT INTO timeline_event (maple_id, revision, tick_id, kind, at, payload)"
            " VALUES (1, ?, ?, 'activity_changed', ?,"
            ' \'{"current":"read","previous":"idle"}\')',
            (tick + 1, tick, _ts(born, 5 * tick)),
        )
    if version >= 2:
        for tick in range(1, ticks + 1):
            conn.execute(
                "INSERT INTO observation (maple_id, revision, tick_id, observed_at, metric,"
                " subject, status, value, state, unit, source, reason)"
                " VALUES (1, ?, ?, ?, 'cpu_usage', 'host', 'available', 12.5, NULL,"
                " 'percent', 'psutil', NULL)",
                (tick + 1, tick, _ts(born, 5 * tick)),
            )
    if version >= 3:
        cursor = conn.execute(
            "INSERT INTO journal_entry (maple_id, revision, tick_id, created_at, category,"
            " trigger_kind, topic, text, importance, brain_kind, brain_name, brain_version,"
            " template_id, activity, expression) VALUES (1, 2, 1, ?, 'daily_life', 'activity',"
            " 'daily:read', 'I read for a while.', 'low', 'rule', 'rule_brain', '1',"
            " 'daily.read.0', 'rest', 'calm')",
            (_ts(born, 5),),
        )
        conn.execute(
            "INSERT INTO journal_entry_observation (entry_id, observation_id, position)"
            " VALUES (?, 1, 0)",
            (cursor.lastrowid,),
        )
        conn.execute(
            "INSERT INTO journal_state (maple_id, journal_day, daily_seen, interactions_today,"
            " notices_today, last_interaction_entry_at, active_alerts, last_reflection_day,"
            " milestones) VALUES (1, '2026-01-01', '[\"read\"]', 1, 0, NULL, '[]', NULL, '[]')"
        )
    conn.execute("COMMIT")
