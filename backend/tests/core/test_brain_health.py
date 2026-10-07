"""Brain Health rules (ADR-0034): status semantics and what "today" means."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from maplegotchi.core.brain_health import (
    NO_CALLS,
    TIMEOUT_CODES,
    AiCall,
    CallStats,
    HealthStatus,
    StatusReason,
    assess,
    latest_call,
    maple_today,
)

BANGKOK = timedelta(hours=7)
T = datetime(2026, 10, 6, 10, 0, tzinfo=UTC)


def stats(*, ok: bool, at: datetime = T, code: str | None = None) -> CallStats:
    return CallStats(AiCall(at, ok, code, 1200), at if ok else None, 0, 0)


def test_not_configured_is_unknown_and_never_offline() -> None:
    assert assess(configured=False, reachable=False, director=None, replier=None) == (
        HealthStatus.UNKNOWN,
        StatusReason.NOT_CONFIGURED,
    )


def test_unreachable_companion_is_offline_whatever_the_history() -> None:
    result = assess(configured=True, reachable=False, director=stats(ok=True), replier=None)
    assert result == (HealthStatus.OFFLINE, StatusReason.COMPANION_UNREACHABLE)


def test_no_calls_yet_is_unknown_not_a_failure() -> None:
    result = assess(configured=True, reachable=True, director=NO_CALLS, replier=NO_CALLS)
    assert result == (HealthStatus.UNKNOWN, StatusReason.NO_CALLS_YET)


def test_latest_call_decides_healthy_or_degraded() -> None:
    later = T + timedelta(minutes=1)
    ok_then_failed = assess(
        configured=True,
        reachable=True,
        director=stats(ok=True),
        replier=stats(ok=False, at=later, code="timeout"),
    )
    assert ok_then_failed == (HealthStatus.DEGRADED, StatusReason.LATEST_CALL_FAILED)
    failed_then_ok = assess(
        configured=True,
        reachable=True,
        director=stats(ok=False, code="transport_error"),
        replier=stats(ok=True, at=later),
    )
    assert failed_then_ok == (HealthStatus.HEALTHY, StatusReason.LATEST_CALL_OK)


def test_a_disabled_caller_does_not_decide_the_status() -> None:
    old_failure = stats(ok=False, at=T + timedelta(hours=1), code="timeout")
    assert latest_call(stats(ok=True), None) == stats(ok=True).last
    result = assess(configured=True, reachable=True, director=stats(ok=True), replier=None)
    assert result[0] is HealthStatus.HEALTHY
    assert latest_call(None, old_failure) == old_failure.last


@pytest.mark.parametrize(
    ("now", "day"),
    [
        (datetime(2026, 10, 5, 22, 59, 59, tzinfo=UTC), date(2026, 10, 5)),  # 05:59:59 local
        (datetime(2026, 10, 5, 23, 0, 0, tzinfo=UTC), date(2026, 10, 6)),  # 06:00 local
        (datetime(2026, 10, 6, 16, 59, 0, tzinfo=UTC), date(2026, 10, 6)),  # 23:59 local
        (datetime(2026, 10, 6, 17, 0, 0, tzinfo=UTC), date(2026, 10, 6)),  # local midnight
    ],
)
def test_today_is_the_maple_day_at_the_core_offset(now: datetime, day: date) -> None:
    today = maple_today(now, BANGKOK)
    assert today.day == day
    assert today.start == datetime.combine(day, datetime.min.time(), UTC) - timedelta(hours=1)
    assert today.end - today.start == timedelta(days=1)
    assert today.start <= now < today.end


def test_today_follows_the_supplied_offset_not_the_server() -> None:
    now = datetime(2026, 10, 6, 3, 0, tzinfo=UTC)  # 10:00 in Bangkok, 05:00 at UTC+2
    assert maple_today(now, BANGKOK).day == date(2026, 10, 6)
    assert maple_today(now, timedelta(hours=2)).day == date(2026, 10, 5)


def test_naive_times_are_refused() -> None:
    with pytest.raises(ValueError):
        maple_today(datetime(2026, 10, 6, 3, 0), BANGKOK)  # noqa: DTZ001


def test_on_an_exact_tie_the_failure_is_the_latest_call() -> None:
    ok, failed = stats(ok=True), stats(ok=False, code="timeout")
    assert latest_call(ok, failed) == failed.last
    assert latest_call(failed, ok) == failed.last


def test_busy_is_a_fallback_but_not_a_timeout() -> None:
    assert "busy" not in TIMEOUT_CODES
    later = T + timedelta(minutes=1)
    result = assess(
        configured=True,
        reachable=True,
        director=stats(ok=True),
        replier=stats(ok=False, at=later, code="busy"),
    )
    assert result == (HealthStatus.DEGRADED, StatusReason.LATEST_CALL_FAILED)
