"""Rows for the decision audit and the action lifecycle (schema v4, ADR-0028 §2).

Both tables are append-only (DB triggers). Rows are written inside the commit
of the transition that produced them and read back through core's own types,
so an invalid row raises CorruptStateError instead of being shown.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from maplegotchi.core.activities import Activity
from maplegotchi.core.audit import (
    ActionEvent,
    ActionEventKind,
    DecisionRecord,
    Executed,
    Proposal,
    Verdict,
)
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.goals import GoalEndReason, GoalType
from maplegotchi.core.priority import Priority
from maplegotchi.storage.errors import CorruptStateError

MAPLE_ID = 1


@dataclass(frozen=True, slots=True)
class StoredDecision:
    id: int
    revision: int
    record: DecisionRecord


@dataclass(frozen=True, slots=True)
class StoredActionEvent:
    id: int
    revision: int
    event: ActionEvent


def _ts(value: datetime) -> str:
    require_utc(value)
    return value.isoformat()


def _parse_ts(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    require_utc(value)
    return value


_DECISION_COLUMNS = (
    "maple_id, revision, at, trigger, priority, director_kind, director_name,"
    " director_version, context_summary, proposed_goal_op, proposed_goal_type,"
    " proposed_goal_summary, proposed_horizon_minutes, proposed_abandon_reason,"
    " proposed_action, proposed_duration_minutes, proposed_reason, verdict, reason_code,"
    " clamped, executed_by, executed_reason, goal_id, action_id, executed_action,"
    " executed_point, executed_duration_minutes, latency_ms"
)


def insert_decision(conn: sqlite3.Connection, revision: int, record: DecisionRecord) -> int:
    p = record.proposal
    x = record.executed
    cursor = conn.execute(
        f"INSERT INTO decision ({_DECISION_COLUMNS})"  # noqa: S608 - fixed column list
        " VALUES (" + ", ".join("?" * 28) + ")",
        (
            MAPLE_ID,
            revision,
            _ts(record.at),
            record.trigger,
            record.priority.value if record.priority else None,
            record.director_kind,
            record.director_name,
            record.director_version,
            record.context_summary,
            p.goal_op if p else None,
            p.goal_type.value if p and p.goal_type else None,
            p.goal_summary if p else None,
            p.horizon_minutes if p else None,
            p.abandon_reason.value if p and p.abandon_reason else None,
            p.action.value if p and p.action else None,
            p.duration_minutes if p else None,
            p.reason if p else None,
            record.verdict.value,
            record.reason_code,
            json.dumps(dict(record.clamped), sort_keys=True) if record.clamped else None,
            x.by if x else None,
            x.reason if x else None,
            x.goal_id if x else None,
            x.action_id if x else None,
            x.action.value if x else None,
            x.point if x else None,
            x.duration_minutes if x else None,
            record.latency_ms,
        ),
    )
    row_id = cursor.lastrowid
    if row_id is None:  # pragma: no cover - sqlite always reports the rowid
        raise CorruptStateError("decision insert returned no id")
    return row_id


def insert_actions(conn: sqlite3.Connection, revision: int, actions: Sequence[ActionEvent]) -> None:
    conn.executemany(
        "INSERT INTO action_event (maple_id, revision, action_id, goal_id, kind, at, priority,"
        " payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                MAPLE_ID,
                revision,
                a.action_id,
                a.goal_id,
                a.kind.value,
                _ts(a.at),
                a.priority.value if a.priority else None,
                json.dumps(dict(a.payload), sort_keys=True, separators=(",", ":")),
            )
            for a in actions
        ],
    )


def _where(revision: int | None, since_revision: int | None) -> tuple[str, tuple[object, ...]]:
    if revision is not None:
        return " WHERE revision = ?", (revision,)
    if since_revision is not None:
        return " WHERE revision > ?", (since_revision,)
    return "", ()


def _select(
    conn: sqlite3.Connection,
    table_sql: str,
    *,
    limit: int | None,
    revision: int | None,
    since_revision: int | None,
) -> list[Any]:
    where, params = _where(revision, since_revision)
    if limit is None or revision is not None:
        rows = conn.execute(table_sql + where + " ORDER BY id", params).fetchall()
    elif since_revision is not None:
        rows = conn.execute(table_sql + where + " ORDER BY id LIMIT ?", (*params, limit)).fetchall()
    else:
        rows = conn.execute(table_sql + where + " ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        rows.reverse()
    return rows


def decisions(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
    revision: int | None = None,
    since_revision: int | None = None,
) -> list[StoredDecision]:
    rows = _select(
        conn,
        f"SELECT id, {_DECISION_COLUMNS} FROM decision",  # noqa: S608 - fixed column list
        limit=limit,
        revision=revision,
        since_revision=since_revision,
    )
    try:
        return [_decode_decision(row) for row in rows]
    except (ValueError, TypeError, KeyError) as exc:
        raise CorruptStateError(f"decision row is invalid: {exc}") from exc


def _decode_decision(row: tuple[Any, ...]) -> StoredDecision:
    (row_id, _maple, revision, at, trigger, priority, kind, name, version, summary,
     goal_op, goal_type, goal_summary, horizon, abandon, action, duration, reason,
     verdict, code, clamped, by, executed_reason, goal_id, action_id, executed_action,
     point, executed_duration, latency) = row  # fmt: skip
    proposal = None
    if any(v is not None for v in (goal_op, goal_type, goal_summary, horizon, abandon, action,
                                   duration, reason)):  # fmt: skip
        proposal = Proposal(
            goal_op=str(goal_op) if goal_op is not None else None,
            goal_type=GoalType(goal_type) if goal_type is not None else None,
            goal_summary=str(goal_summary) if goal_summary is not None else None,
            horizon_minutes=float(horizon) if horizon is not None else None,
            abandon_reason=GoalEndReason(abandon) if abandon is not None else None,
            action=Activity(action) if action is not None else None,
            duration_minutes=float(duration) if duration is not None else None,
            reason=str(reason) if reason is not None else None,
        )
    executed = None
    if by is not None:
        executed = Executed(
            by=str(by),
            reason=str(executed_reason),
            goal_id=int(goal_id) if goal_id is not None else None,
            action_id=int(action_id),
            action=Activity(executed_action),
            point=str(point),
            duration_minutes=int(executed_duration),
        )
    record = DecisionRecord(
        at=_parse_ts(str(at)),
        trigger=str(trigger),
        director_kind=str(kind),
        director_name=str(name),
        director_version=str(version),
        context_summary=str(summary),
        verdict=Verdict(verdict),
        proposal=proposal,
        reason_code=str(code) if code is not None else None,
        clamped=MappingProxyType(json.loads(str(clamped))) if clamped is not None else {},
        executed=executed,
        priority=Priority(priority) if priority is not None else None,
        latency_ms=int(latency) if latency is not None else None,
    )
    return StoredDecision(int(row_id), int(revision), record)


def action_events(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
    revision: int | None = None,
    since_revision: int | None = None,
) -> list[StoredActionEvent]:
    rows = _select(
        conn,
        "SELECT id, revision, action_id, goal_id, kind, at, priority, payload FROM action_event",
        limit=limit,
        revision=revision,
        since_revision=since_revision,
    )
    try:
        out = []
        for row_id, rev, action_id, goal_id, kind, at, priority, payload in rows:
            data = json.loads(str(payload))
            if not isinstance(data, dict):
                raise ValueError("payload must be an object")
            event = ActionEvent(
                kind=ActionEventKind(kind),
                at=_parse_ts(str(at)),
                action_id=int(action_id),
                goal_id=int(goal_id) if goal_id is not None else None,
                priority=Priority(priority) if priority is not None else None,
                payload=MappingProxyType(data),
            )
            out.append(StoredActionEvent(int(row_id), int(rev), event))
        return out
    except (ValueError, TypeError) as exc:
        raise CorruptStateError(f"action event row is invalid: {exc}") from exc
