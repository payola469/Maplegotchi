"""How Maple's needs evolve over time, as pure arithmetic (CLAUDE.md §5).

Only + - * / on floats, which IEEE 754 rounds identically everywhere, so
replays are bit-identical on Windows and Linux.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from maplegotchi.core.activities import SPECS, Activity
from maplegotchi.core.state import NEED_MAX, MapleState, Needs

# Social fulfilment relaxes toward this floor when nobody interacts with Maple.
SOCIAL_FLOOR = 20.0
SOCIAL_RELAX_PER_HOUR = 0.03
# Mood relaxes toward a target set by energy and social fulfilment.
MOOD_RELAX_PER_HOUR = 0.15


def mood_target(energy: float, social: float) -> float:
    """Mood Maple drifts toward: 20 when exhausted and lonely, 100 when rested and fulfilled."""
    return 20.0 + 0.35 * energy + 0.45 * social


def _relax(value: float, target: float, rate_per_hour: float, hours: float) -> float:
    # Rational stand-in for exponential decay: monotonic, never overshoots, exact rounding.
    return target + (value - target) / (1.0 + rate_per_hour * hours)


def evolve_needs(needs: Needs, activity: Activity, elapsed: timedelta) -> Needs:
    """Needs after spending `elapsed` doing `activity`."""
    if elapsed < timedelta(0):
        raise ValueError("elapsed must be >= 0")
    hours = elapsed.total_seconds() / 3600.0
    spec = SPECS[activity]
    energy = needs.energy + spec.energy_per_hour * hours
    curiosity = needs.curiosity + spec.curiosity_per_hour * hours
    social = _relax(needs.social, SOCIAL_FLOOR, SOCIAL_RELAX_PER_HOUR, hours)
    clamped_energy = min(NEED_MAX, max(0.0, energy))
    target = mood_target(clamped_energy, social)
    mood = _relax(needs.mood, target, MOOD_RELAX_PER_HOUR, hours) + spec.mood_per_hour * hours
    return Needs.clamped(mood=mood, energy=energy, curiosity=curiosity, social=social)


def evolve_through(state: MapleState, now: datetime, elapsed: timedelta) -> Needs:
    """Needs over the window [now - elapsed, now], honouring a walk in progress.

    Before departure Maple was still doing the previous activity; while walking the
    `walk` spec applies; the new activity's spec applies only from arrival
    (ADR-0027). Without a route this is exactly `evolve_needs` over the window.
    """
    route = state.route
    if route is None:
        return evolve_needs(state.needs, state.activity, elapsed)
    start = now - elapsed
    walk_start = min(max(route.departed_at, start), now)
    walk_end = min(max(route.arrives_at, walk_start), now)
    segments = (
        (route.from_activity, walk_start - start),
        (Activity.WALK, walk_end - walk_start),
        (state.activity, now - walk_end),
    )
    needs = state.needs
    for activity, span in segments:
        if span > timedelta(0):  # zero spans are skipped: relaxing by 0 h is not exact
            needs = evolve_needs(needs, activity, span)
    return needs


def needs_since(state: MapleState) -> datetime:
    """When the stored needs were last evolved."""
    return state.needs_at if state.needs_at is not None else state.last_tick_at
