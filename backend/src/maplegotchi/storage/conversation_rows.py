"""Rows for conversations with Paolo (schema v9, ADR-0032); append-only."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from maplegotchi.core.conversation import Channel, Speaker
from maplegotchi.core.daytime import require_utc
from maplegotchi.storage.errors import CorruptStateError

MAPLE_ID = 1


@dataclass(frozen=True, slots=True)
class StoredMessage:
    id: int
    revision: int
    at: datetime
    channel: Channel
    speaker: Speaker
    text: str
    external_id: str | None
    reply_to: int | None
    replier_kind: str | None
    replier_name: str | None
    fallback_code: str | None


@dataclass(frozen=True, slots=True)
class MessageRecord:
    """One message to store with a commit (incoming from Paolo, or Maple's reply)."""

    at: datetime
    channel: Channel
    speaker: Speaker
    text: str
    external_id: str | None = None
    reply_to: int | None = None
    replier_kind: str | None = None
    replier_name: str | None = None
    fallback_code: str | None = None


def _ts(value: datetime) -> str:
    require_utc(value)
    return value.isoformat()


def insert_message(conn: sqlite3.Connection, revision: int, m: MessageRecord) -> int:
    cursor = conn.execute(
        "INSERT INTO conversation_message (maple_id, revision, at, channel, direction, speaker,"
        " external_id, reply_to, text, replier_kind, replier_name, fallback_code)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            MAPLE_ID,
            revision,
            _ts(m.at),
            m.channel.value,
            "in" if m.speaker is Speaker.PAOLO else "out",
            m.speaker.value,
            m.external_id,
            m.reply_to,
            m.text,
            m.replier_kind,
            m.replier_name,
            m.fallback_code,
        ),
    )
    if cursor.lastrowid is None:  # pragma: no cover - sqlite always reports the rowid
        raise CorruptStateError("message insert returned no id")
    return cursor.lastrowid


_SQL = (
    "SELECT id, revision, at, channel, speaker, text, external_id, reply_to, replier_kind,"
    " replier_name, fallback_code FROM conversation_message"
)


def _decode(row: Any) -> StoredMessage:
    (row_id, rev, at, channel, speaker, text, external_id, reply_to, kind, name,
     code) = row  # fmt: skip
    value = datetime.fromisoformat(at)
    require_utc(value)
    return StoredMessage(row_id, rev, value, Channel(channel), Speaker(speaker), text,
                         external_id, reply_to, kind, name, code)  # fmt: skip


def messages(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
    revision: int | None = None,
    since_revision: int | None = None,
) -> list[StoredMessage]:
    sql = _SQL
    params: list[object] = []
    if revision is not None:
        sql += " WHERE revision = ?"
        params.append(revision)
    elif since_revision is not None:
        sql += " WHERE revision > ?"
        params.append(since_revision)
    if limit is None or revision is not None:
        rows = conn.execute(sql + " ORDER BY id", params).fetchall()
    elif since_revision is not None:
        rows = conn.execute(sql + " ORDER BY id LIMIT ?", (*params, limit)).fetchall()
    else:
        rows = conn.execute(sql + " ORDER BY id DESC LIMIT ?", (*params, limit)).fetchall()
        rows.reverse()
    try:
        return [_decode(r) for r in rows]
    except (ValueError, TypeError) as exc:
        raise CorruptStateError(f"conversation row is invalid: {exc}") from exc


def by_external_id(
    conn: sqlite3.Connection, channel: Channel, external_id: str
) -> StoredMessage | None:
    row = conn.execute(
        _SQL + " WHERE channel = ? AND external_id = ?", (channel.value, external_id)
    ).fetchone()
    return _decode(row) if row else None


def reply_to(conn: sqlite3.Connection, message_id: int) -> StoredMessage | None:
    row = conn.execute(_SQL + " WHERE reply_to = ? ORDER BY id LIMIT 1", (message_id,)).fetchone()
    return _decode(row) if row else None


def recent_incoming(conn: sqlite3.Connection, since: datetime) -> int:
    """Incoming messages at or after `since` (UTC ISO strings sort in time order)."""
    row = conn.execute(
        "SELECT count(*) FROM conversation_message WHERE direction = 'in' AND at >= ?",
        (_ts(since),),
    ).fetchone()
    return int(row[0])
