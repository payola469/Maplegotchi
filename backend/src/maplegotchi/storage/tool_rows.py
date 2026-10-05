"""Rows for Maple's document workspace and reader/writer provenance (schema v6, ADR-0029).

Both tables are append-only (DB triggers). A successful `write_completed`
record carries its document, which is inserted first so the provenance row can
point at it, all in the transition's own transaction.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from maplegotchi.core.daytime import require_utc
from maplegotchi.core.tasks import Task, Tool, ToolOp, ToolRecord, WriteKind
from maplegotchi.storage.errors import CorruptStateError

MAPLE_ID = 1


@dataclass(frozen=True, slots=True)
class StoredDocument:
    id: int
    revision: int
    kind: WriteKind
    title: str
    body: str
    created_at: datetime
    action_id: int
    goal_id: int | None
    sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StoredToolUse:
    id: int
    revision: int
    record: ToolRecord
    document_id: int | None


def _ts(value: datetime) -> str:
    require_utc(value)
    return value.isoformat()


def _parse_ts(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    require_utc(value)
    return value


def insert_tools(conn: sqlite3.Connection, revision: int, tools: Sequence[ToolRecord]) -> None:
    for record in tools:
        document_id = None
        doc = record.document
        if doc is not None:
            cursor = conn.execute(
                "INSERT INTO document (maple_id, revision, kind, title, body, created_at,"
                " action_id, goal_id, sources) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    MAPLE_ID,
                    revision,
                    doc.kind.value,
                    doc.title,
                    doc.body,
                    _ts(record.at),
                    record.action_id,
                    record.goal_id,
                    json.dumps(list(doc.sources)),
                ),
            )
            document_id = cursor.lastrowid
        task = record.task
        conn.execute(
            "INSERT INTO tool_use (maple_id, revision, at, action_id, goal_id, tool, operation,"
            " target, title, category, status, detail, chars, document_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                MAPLE_ID,
                revision,
                _ts(record.at),
                record.action_id,
                record.goal_id,
                task.tool.value,
                record.op.value,
                task.target,
                task.title,
                task.category,
                "success" if record.success else "failure",
                record.detail,
                record.chars,
                document_id,
            ),
        )


def tool_uses(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
    revision: int | None = None,
    since_revision: int | None = None,
    operation: ToolOp | None = None,
) -> list[StoredToolUse]:
    sql = (
        "SELECT id, revision, at, action_id, goal_id, tool, operation, target, title, category,"
        " status, detail, chars, document_id FROM tool_use"
    )
    where: list[str] = []
    params: list[object] = []
    if revision is not None:
        where.append("revision = ?")
        params.append(revision)
    if since_revision is not None:
        where.append("revision > ?")
        params.append(since_revision)
    if operation is not None:
        where.append("operation = ?")
        params.append(operation.value)
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows: list[Any]
    if limit is None or revision is not None:
        rows = conn.execute(sql + " ORDER BY id", params).fetchall()
    elif since_revision is not None:
        rows = conn.execute(sql + " ORDER BY id LIMIT ?", (*params, limit)).fetchall()
    else:
        rows = conn.execute(sql + " ORDER BY id DESC LIMIT ?", (*params, limit)).fetchall()
        rows.reverse()
    try:
        out = []
        for (row_id, rev, at, action_id, goal_id, tool, op, target, title, category, status,
             detail, chars, document_id) in rows:  # fmt: skip
            record = ToolRecord(
                op=ToolOp(op),
                at=_parse_ts(at),
                action_id=action_id,
                goal_id=goal_id,
                task=Task(Tool(tool), target, title, category),
                success=status == "success",
                detail=detail,
                chars=chars,
            )
            out.append(StoredToolUse(row_id, rev, record, document_id))
        return out
    except (ValueError, TypeError) as exc:
        raise CorruptStateError(f"tool provenance row is invalid: {exc}") from exc


def _document(row: Any) -> StoredDocument:
    row_id, rev, kind, title, body, created, action_id, goal_id, sources = row
    return StoredDocument(
        id=row_id,
        revision=rev,
        kind=WriteKind(kind),
        title=title,
        body=body,
        created_at=_parse_ts(created),
        action_id=action_id,
        goal_id=goal_id,
        sources=tuple(str(s) for s in json.loads(sources)),
    )


_DOCUMENT_SQL = (
    "SELECT id, revision, kind, title, body, created_at, action_id, goal_id, sources FROM document"
)


def documents(conn: sqlite3.Connection, *, limit: int | None = None) -> list[StoredDocument]:
    if limit is None:
        rows = conn.execute(_DOCUMENT_SQL + " ORDER BY id").fetchall()
    else:
        rows = conn.execute(_DOCUMENT_SQL + " ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        rows.reverse()
    try:
        return [_document(r) for r in rows]
    except (ValueError, TypeError) as exc:
        raise CorruptStateError(f"document row is invalid: {exc}") from exc


def document(conn: sqlite3.Connection, document_id: int) -> StoredDocument | None:
    row = conn.execute(_DOCUMENT_SQL + " WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        return None
    try:
        return _document(row)
    except (ValueError, TypeError) as exc:
        raise CorruptStateError(f"document row is invalid: {exc}") from exc
