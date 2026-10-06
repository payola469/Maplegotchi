"""Read-only aggregates over the stored audit for Brain Health (ADR-0034 §3).

No table of its own: Director calls are external `decision` rows, Replier calls are
outgoing `conversation_message` rows that used (or fell back from) the external
replier. Timestamps are UTC ISO strings, which sort in time order.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from maplegotchi.core.brain_health import (
    DIRECTOR_FALLBACK_VERDICTS,
    DIRECTOR_SUCCESS_VERDICTS,
    TIMEOUT_CODES,
    AiCall,
    CallStats,
)
from maplegotchi.core.daytime import require_utc
from maplegotchi.storage.errors import CorruptStateError

_EXTERNAL_DECISION = "FROM decision WHERE director_kind = 'external'"
_EXTERNAL_REPLY = (
    "FROM conversation_message WHERE direction = 'out'"
    " AND (replier_kind = 'external' OR fallback_code IS NOT NULL)"
)


def _ts(value: datetime) -> str:
    require_utc(value)
    return value.isoformat()


def _parse(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    require_utc(value)
    return value


def _in(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def _one(conn: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()) -> Any:
    return conn.execute(sql, params).fetchone()


def director_stats(conn: sqlite3.Connection, start: datetime, end: datetime) -> CallStats:
    """External Director calls; `start`/`end` bound "today" (stale rows are ignored)."""
    ok = _in(DIRECTOR_SUCCESS_VERDICTS)
    try:
        last = _one(
            conn,
            f"SELECT at, verdict IN {ok}, reason_code, latency_ms {_EXTERNAL_DECISION}"
            " AND verdict != 'stale' ORDER BY id DESC LIMIT 1",
        )
        success = _one(
            conn,
            f"SELECT at {_EXTERNAL_DECISION} AND verdict IN {ok} ORDER BY id DESC LIMIT 1",
        )
        counts = _one(
            conn,
            f"SELECT coalesce(sum(verdict IN {_in(DIRECTOR_FALLBACK_VERDICTS)}), 0),"
            f" coalesce(sum(reason_code IN {_in(TIMEOUT_CODES)}), 0) {_EXTERNAL_DECISION}"
            " AND at >= ? AND at < ?",
            (_ts(start), _ts(end)),
        )
        return CallStats(
            last=AiCall(_parse(last[0]), bool(last[1]), last[2], last[3]) if last else None,
            last_success_at=_parse(success[0]) if success else None,
            fallbacks_today=int(counts[0]),
            timeouts_today=int(counts[1]),
        )
    except (ValueError, TypeError) as exc:
        raise CorruptStateError(f"decision row is invalid: {exc}") from exc


def replier_stats(conn: sqlite3.Connection, start: datetime, end: datetime) -> CallStats:
    """External Replier attempts: successes, and fallbacks to a rule reply."""
    try:
        last = _one(
            conn,
            f"SELECT at, fallback_code IS NULL, fallback_code, latency_ms {_EXTERNAL_REPLY}"
            " ORDER BY id DESC LIMIT 1",
        )
        success = _one(
            conn,
            f"SELECT at {_EXTERNAL_REPLY} AND fallback_code IS NULL ORDER BY id DESC LIMIT 1",
        )
        counts = _one(
            conn,
            "SELECT coalesce(sum(fallback_code IS NOT NULL), 0),"
            f" coalesce(sum(fallback_code IN {_in(TIMEOUT_CODES)}), 0) {_EXTERNAL_REPLY}"
            " AND at >= ? AND at < ?",
            (_ts(start), _ts(end)),
        )
        return CallStats(
            last=AiCall(_parse(last[0]), bool(last[1]), last[2], last[3]) if last else None,
            last_success_at=_parse(success[0]) if success else None,
            fallbacks_today=int(counts[0]),
            timeouts_today=int(counts[1]),
        )
    except (ValueError, TypeError) as exc:
        raise CorruptStateError(f"conversation row is invalid: {exc}") from exc
