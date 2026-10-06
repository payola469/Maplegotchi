"""Rows for Daily Reflection (schema v8, ADR-0031): one append-only row per Maple day,
plus the time-window queries that gather a day's facts."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from maplegotchi.core.daily import DailyReflection, MemoryCandidate
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.goals import GoalType
from maplegotchi.core.state import Needs
from maplegotchi.storage.errors import CorruptStateError

MAPLE_ID = 1


@dataclass(frozen=True, slots=True)
class StoredReflection:
    id: int
    revision: int
    reflection: DailyReflection


def _ts(value: datetime) -> str:
    require_utc(value)
    return value.isoformat()


def insert_reflection(conn: sqlite3.Connection, revision: int, r: DailyReflection) -> None:
    conn.execute(
        "INSERT INTO daily_reflection (maple_id, revision, day, created_at, recovered, summary,"
        " learned, moments, memory_candidates, promoted, preference_candidates, intent_type,"
        " intent_summary, needs) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            MAPLE_ID,
            revision,
            r.day.isoformat(),
            _ts(r.created_at),
            int(r.recovered),
            r.summary,
            json.dumps(list(r.learned)),
            json.dumps(list(r.moments)),
            json.dumps([[c.memory_id, c.text, c.reason] for c in r.memory_candidates]),
            json.dumps(list(r.promoted)),
            json.dumps([list(p) for p in r.preference_candidates]),
            r.intent_type.value,
            r.intent_summary,
            json.dumps(
                {
                    "mood": r.needs.mood,
                    "energy": r.needs.energy,
                    "curiosity": r.needs.curiosity,
                    "social": r.needs.social,
                }
            ),
        ),
    )


_SQL = (
    "SELECT id, revision, day, created_at, recovered, summary, learned, moments,"
    " memory_candidates, promoted, preference_candidates, intent_type, intent_summary, needs"
    " FROM daily_reflection"
)


def _decode(row: Any) -> StoredReflection:
    (row_id, rev, day, created, recovered, summary, learned, moments, candidates, promoted,
     prefs, intent_type, intent_summary, needs) = row  # fmt: skip
    created_at = datetime.fromisoformat(created)
    n = json.loads(needs)
    return StoredReflection(
        row_id,
        rev,
        DailyReflection(
            day=date.fromisoformat(day),
            created_at=created_at,
            recovered=bool(recovered),
            summary=summary,
            learned=tuple(json.loads(learned)),
            moments=tuple(json.loads(moments)),
            memory_candidates=tuple(
                MemoryCandidate(int(i), str(t), str(why)) for i, t, why in json.loads(candidates)
            ),
            promoted=tuple(int(i) for i in json.loads(promoted)),
            preference_candidates=tuple((str(k), str(t)) for k, t in json.loads(prefs)),
            intent_type=GoalType(intent_type),
            intent_summary=intent_summary,
            needs=Needs(
                mood=n["mood"], energy=n["energy"], curiosity=n["curiosity"], social=n["social"]
            ),
        ),
    )


def reflections(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
    revision: int | None = None,
    since_revision: int | None = None,
) -> list[StoredReflection]:
    sql = _SQL
    params: list[object] = []
    if revision is not None:
        sql += " WHERE revision = ?"
        params.append(revision)
    elif since_revision is not None:
        sql += " WHERE revision > ?"
        params.append(since_revision)
    if limit is None or revision is not None or since_revision is not None:
        rows = conn.execute(sql + " ORDER BY day" + (" LIMIT ?" if limit else ""),
                            (*params, limit) if limit else params).fetchall()  # fmt: skip
    else:
        rows = conn.execute(sql + " ORDER BY day DESC LIMIT ?", (*params, limit)).fetchall()
        rows.reverse()
    try:
        return [_decode(r) for r in rows]
    except (ValueError, TypeError, KeyError) as exc:
        raise CorruptStateError(f"daily reflection row is invalid: {exc}") from exc


def reflection_for(conn: sqlite3.Connection, day: date) -> StoredReflection | None:
    row = conn.execute(_SQL + " WHERE day = ?", (day.isoformat(),)).fetchone()
    if row is None:
        return None
    try:
        return _decode(row)
    except (ValueError, TypeError, KeyError) as exc:
        raise CorruptStateError(f"daily reflection row is invalid: {exc}") from exc


_DAY_QUERIES = {
    "timeline_event": "SELECT kind, payload FROM timeline_event",
    "action_event": "SELECT kind, payload FROM action_event",
    "decision": "SELECT verdict FROM decision",
    "tool_use": "SELECT operation, status, title, detail FROM tool_use",
}


def rows_between(conn: sqlite3.Connection, table: str, start: datetime, end: datetime) -> list[Any]:
    """Rows of an allowlisted table whose `at` lies in [start, end), oldest first.

    Every `at` is ISO-8601 UTC with the same "+00:00" suffix, so text order is time
    order ("+" sorts before "." for fractional seconds); the bounds are whole seconds.
    """
    query = _DAY_QUERIES.get(table)
    if query is None:
        raise ValueError(f"not an allowed day query: {table}")
    return conn.execute(
        query + " WHERE at >= ? AND at < ? ORDER BY id", (_ts(start), _ts(end))
    ).fetchall()
