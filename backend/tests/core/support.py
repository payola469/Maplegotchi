"""Shared builders for core tests. Times are explicit; nothing reads a clock."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from maplegotchi.core.activities import SPECS, Activity, RoomLocation
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.state import MapleState, Needs, birth

SEED = "ab" * 32
OTHER_SEED = "cd" * 32
PARAMS = CoreParameters()  # utc_offset +7h

# Born at local midnight (UTC+7) on 2026-01-01.
BORN = datetime(2025, 12, 31, 17, 0, tzinfo=UTC)


def at_local(hour: float, day: int = 1) -> datetime:
    """UTC time for `hour` o'clock local on day `day` after birth."""
    return BORN + timedelta(days=day, hours=hour)


def needs(
    *, mood: float = 60.0, energy: float = 80.0, curiosity: float = 60.0, social: float = 50.0
) -> Needs:
    return Needs(mood=mood, energy=energy, curiosity=curiosity, social=social)


def make_state(
    *,
    at: datetime | None = None,
    activity: Activity = Activity.IDLE,
    location: RoomLocation | None = None,
    state_needs: Needs | None = None,
    until: timedelta = timedelta(minutes=30),
    seed: str = SEED,
) -> MapleState:
    """A valid state whose latest update, heartbeat, and activity start are all `at`."""
    at = at or at_local(12)
    base = birth(name="Maple", born_at=BORN, seed_hex=seed)
    return replace(
        base,
        needs=state_needs or base.needs,
        activity=activity,
        location=location or SPECS[activity].locations[0],
        activity_started_at=at,
        activity_until=at + until,
        last_tick_at=at,
        last_updated_at=at,
    )
