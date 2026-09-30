"""Time helpers for core. Time is always supplied by the caller; core never reads a clock."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum

NIGHT_STARTS_HOUR = 22
NIGHT_ENDS_HOUR = 6


class DayPhase(StrEnum):
    NIGHT = "night"
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


def require_utc(value: datetime, name: str = "time") -> None:
    """Core only accepts timezone-aware UTC datetimes."""
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be timezone-aware UTC")


def local_hour(now: datetime, utc_offset: timedelta) -> float:
    """Hour of day in [0, 24) at Maple's home, as a fraction."""
    local = now + utc_offset
    return local.hour + local.minute / 60 + local.second / 3600


def day_phase(hour: float) -> DayPhase:
    if not 0 <= hour < 24:
        raise ValueError("hour must be in [0, 24)")
    if hour >= NIGHT_STARTS_HOUR or hour < NIGHT_ENDS_HOUR:
        return DayPhase.NIGHT
    if hour < 12:
        return DayPhase.MORNING
    if hour < 18:
        return DayPhase.AFTERNOON
    return DayPhase.EVENING


def is_night(hour: float) -> bool:
    return day_phase(hour) is DayPhase.NIGHT
