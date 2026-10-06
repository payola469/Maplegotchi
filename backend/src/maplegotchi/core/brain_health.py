"""Brain Health rules (ADR-0034): what the stored audit says about Maple's AI calls.

Pure: storage supplies the facts (latest calls, counts in a window), runtime supplies
whether the companion answered its health probe; this module only classifies them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from maplegotchi.core.daily import day_window, reflection_day

# Decision verdicts and codes as stored in the audit (core.audit.Verdict, RejectionCode).
DIRECTOR_SUCCESS_VERDICTS = ("accepted", "clamped")
DIRECTOR_FALLBACK_VERDICTS = ("fallback", "rejected")
TIMEOUT_CODES = ("timeout", "transport_error")


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class StatusReason(StrEnum):
    LATEST_CALL_OK = "latest_call_ok"
    LATEST_CALL_FAILED = "latest_call_failed"
    COMPANION_UNREACHABLE = "companion_unreachable"
    NO_CALLS_YET = "no_calls_yet"
    NOT_CONFIGURED = "not_configured"  # every mode is rule: no companion to ask


@dataclass(frozen=True, slots=True)
class AiCall:
    """One stored AI call: when, whether it gave a usable answer, why not, how long."""

    at: datetime
    ok: bool
    code: str | None  # the decision reason_code or reply fallback_code
    latency_ms: int | None


@dataclass(frozen=True, slots=True)
class CallStats:
    """One caller's (Director or Replier) history from the stored audit."""

    last: AiCall | None  # the latest relevant call (stale decisions excluded)
    last_success_at: datetime | None
    fallbacks_today: int
    timeouts_today: int  # timeouts or transport errors


NO_CALLS = CallStats(last=None, last_success_at=None, fallbacks_today=0, timeouts_today=0)


@dataclass(frozen=True, slots=True)
class MapleDay:
    day: date
    start: datetime  # UTC, inclusive
    end: datetime  # UTC, exclusive


def maple_today(now: datetime, utc_offset: timedelta) -> MapleDay:
    """The current Maple day (local 06:00 to 06:00, ADR-0031): what "today" means here."""
    day = reflection_day(now, utc_offset)
    start, end = day_window(day, utc_offset)
    return MapleDay(day, start, end)


def latest_call(*stats: CallStats | None) -> AiCall | None:
    """The newest call among the given callers (None entries are not configured).

    On an exact tie the failure wins: health is never claimed on a coin toss.
    """
    calls = [s.last for s in stats if s is not None and s.last is not None]
    if not calls:
        return None
    return max(calls, key=lambda call: (call.at, not call.ok))


def assess(
    *,
    configured: bool,
    reachable: bool,
    director: CallStats | None,
    replier: CallStats | None,
) -> tuple[HealthStatus, StatusReason]:
    """Overall status: offline > degraded/healthy by the latest call > unknown.

    `director`/`replier` are None when that caller is not external right now, so an
    old call from a since-disabled caller never decides today's status.
    """
    if not configured:
        return HealthStatus.UNKNOWN, StatusReason.NOT_CONFIGURED
    if not reachable:
        return HealthStatus.OFFLINE, StatusReason.COMPANION_UNREACHABLE
    latest = latest_call(director, replier)
    if latest is None:
        return HealthStatus.UNKNOWN, StatusReason.NO_CALLS_YET
    if latest.ok:
        return HealthStatus.HEALTHY, StatusReason.LATEST_CALL_OK
    return HealthStatus.DEGRADED, StatusReason.LATEST_CALL_FAILED
