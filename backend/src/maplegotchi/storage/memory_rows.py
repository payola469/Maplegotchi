"""Rows for Maple's memory (schema v7, ADR-0030).

`memory` rows change tier/status/evidence over their life (never deleted, DB
trigger); every change is logged append-only in `memory_event`. New memories
with a key that already exists are skipped (dedup), without an event.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any

from maplegotchi.core.daytime import require_utc
from maplegotchi.core.memory import (
    Memory,
    MemoryChange,
    MemoryEvent,
    MemoryEventKind,
    MemoryKind,
    MemoryStatus,
    Tier,
)
from maplegotchi.storage.errors import CorruptStateError

MAPLE_ID = 1
_COLUMNS = (
    "id, kind, tier, status, key, text, source, importance, evidence_days, created_at, last_seen_at"
)


@dataclass(frozen=True, slots=True)
class StoredMemoryEvent:
    id: int
    revision: int
    memory_id: int
    event: MemoryEvent
    memory_text: str
    memory_kind: MemoryKind
    tier: Tier


def _ts(value: datetime) -> str:
    require_utc(value)
    return value.isoformat()


def _parse_ts(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    require_utc(value)
    return value


def apply_changes(
    conn: sqlite3.Connection, revision: int, changes: Sequence[MemoryChange]
) -> tuple[Memory, ...]:
    """Insert new memories / update existing ones and log each change. Returns stored."""
    stored: list[Memory] = []
    for change in changes:
        m = change.memory
        days = json.dumps([d.isoformat() for d in m.evidence_days])
        if m.id is None:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO memory (maple_id, revision, kind, tier, status, key, text,"
                " source, importance, evidence_days, created_at, last_seen_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (MAPLE_ID, revision, m.kind.value, m.tier.value, m.status.value, m.key, m.text,
                 m.source, m.importance, days, _ts(m.created_at), _ts(m.last_seen_at)),
            )  # fmt: skip
            if cursor.rowcount != 1 or cursor.lastrowid is None:
                continue  # an equal memory (same key) is already there
            m = replace(m, id=cursor.lastrowid)
        else:
            updated = conn.execute(
                "UPDATE memory SET revision = ?, tier = ?, status = ?, importance = ?,"
                " evidence_days = ?, last_seen_at = ? WHERE id = ?",
                (revision, m.tier.value, m.status.value, m.importance, days,
                 _ts(m.last_seen_at), m.id),
            ).rowcount  # fmt: skip
            if updated != 1:
                raise CorruptStateError(f"memory {m.id} is missing")
        conn.execute(
            "INSERT INTO memory_event (maple_id, revision, memory_id, kind, at, detail)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (MAPLE_ID, revision, m.id, change.event.kind.value, _ts(change.event.at),
             change.event.detail),
        )  # fmt: skip
        stored.append(m)
    return tuple(stored)


def _memory(row: Any) -> Memory:
    (row_id, kind, tier, status, key, text, source, importance, days, created,
     last_seen) = row  # fmt: skip
    return Memory(
        id=row_id,
        kind=MemoryKind(kind),
        tier=Tier(tier),
        status=MemoryStatus(status),
        key=key,
        text=text,
        source=source,
        importance=importance,
        evidence_days=tuple(date.fromisoformat(d) for d in json.loads(days)),
        created_at=_parse_ts(created),
        last_seen_at=_parse_ts(last_seen),
    )


def memories(
    conn: sqlite3.Connection,
    *,
    tiers: Sequence[Tier] | None = None,
    limit: int | None = None,
) -> list[Memory]:
    """Memories, most recently seen last (all tiers, or only `tiers`)."""
    sql = f"SELECT {_COLUMNS} FROM memory"  # noqa: S608 - fixed column list
    params: list[object] = []
    if tiers:
        sql += " WHERE tier IN (" + ", ".join("?" * len(tiers)) + ")"
        params += [t.value for t in tiers]
    sql += " ORDER BY last_seen_at DESC, id DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    rows.reverse()
    try:
        return [_memory(r) for r in rows]
    except (ValueError, TypeError) as exc:
        raise CorruptStateError(f"memory row is invalid: {exc}") from exc


def memory_by_key(conn: sqlite3.Connection, key: str) -> Memory | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM memory WHERE key = ?",  # noqa: S608 - fixed column list
        (key,),
    ).fetchone()
    if row is None:
        return None
    try:
        return _memory(row)
    except (ValueError, TypeError) as exc:
        raise CorruptStateError(f"memory row is invalid: {exc}") from exc


def memory_events(
    conn: sqlite3.Connection,
    *,
    revision: int | None = None,
    since_revision: int | None = None,
    limit: int | None = None,
) -> list[StoredMemoryEvent]:
    sql = (
        "SELECT e.id, e.revision, e.memory_id, e.kind, e.at, e.detail, m.text, m.kind, m.tier"
        " FROM memory_event e JOIN memory m ON m.id = e.memory_id"
    )
    params: list[object] = []
    if revision is not None:
        sql += " WHERE e.revision = ?"
        params.append(revision)
    elif since_revision is not None:
        sql += " WHERE e.revision > ?"
        params.append(since_revision)
    sql += " ORDER BY e.id"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    try:
        return [
            StoredMemoryEvent(
                id=row_id,
                revision=rev,
                memory_id=memory_id,
                event=MemoryEvent(MemoryEventKind(kind), _parse_ts(at), detail),
                memory_text=text,
                memory_kind=MemoryKind(memory_kind),
                tier=Tier(tier),
            )
            for row_id, rev, memory_id, kind, at, detail, text, memory_kind, tier in conn.execute(
                sql, params
            ).fetchall()
        ]
    except (ValueError, TypeError) as exc:
        raise CorruptStateError(f"memory event row is invalid: {exc}") from exc
