"""One logical heartbeat of Maple's life, as a pure function.

The caller supplies the time. There is no scheduler, no sleeping, and no Brain
parameter: an ordinary heartbeat cannot invoke an external Brain (D6).

Need dynamics use only +, -, *, / (no exp/log), which IEEE 754 rounds exactly,
so replays are bit-identical on Windows dev machines and on paolo-core.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from maplegotchi.core.activities import SPECS, Activity
from maplegotchi.core.behavior import FORCED_SLEEP_ENERGY, BehaviorInputs, choose_next_activity
from maplegotchi.core.daytime import is_night, local_hour, require_utc
from maplegotchi.core.movement import begin_activity, choose_point, settle_movement
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.rng import RngStream
from maplegotchi.core.state import NEED_MAX, MapleState, Needs, prune_interactions
from maplegotchi.core.timeline import DowntimeGap, LifeEvent

# Social fulfilment relaxes toward this floor when nobody interacts with Maple.
SOCIAL_FLOOR = 20.0
SOCIAL_RELAX_PER_HOUR = 0.03
# Mood relaxes toward a target set by energy and social fulfilment.
MOOD_RELAX_PER_HOUR = 0.15
# A gap longer than this many heartbeat intervals is recorded as downtime.
DOWNTIME_GAP_INTERVALS = 2


@dataclass(frozen=True, slots=True)
class TickResult:
    state: MapleState
    tick_id: int
    events: tuple[LifeEvent, ...]


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


def needs_new_activity(state: MapleState, now: datetime, params: CoreParameters) -> bool:
    if now >= state.activity_until:
        return True
    if state.activity is not Activity.SLEEP and state.needs.energy <= FORCED_SLEEP_ENERGY:
        return True  # exhausted: interrupt whatever Maple is doing
    fully_rested = state.needs.energy >= NEED_MAX
    daytime = not is_night(local_hour(now, params.utc_offset))
    return state.activity is Activity.SLEEP and fully_rested and daytime


def heartbeat(
    state: MapleState,
    now: datetime,
    inputs: BehaviorInputs,
    params: CoreParameters,
) -> TickResult:
    """Advance Maple's life to `now`: evolve needs, expire reactions, maybe change activity."""
    require_utc(now, "now")
    if now <= state.last_tick_at:
        raise ValueError("heartbeat time must be after the previous heartbeat")
    if now < state.last_updated_at:
        raise ValueError("heartbeat time must not precede the latest state update")

    tick_id = state.rng.tick_counter + 1
    rng = RngStream(state.rng.seed_hex, "tick", tick_id)
    gap = now - state.last_tick_at
    elapsed = min(gap, params.max_catchup)

    events: list[LifeEvent] = []
    if gap > params.heartbeat_interval * DOWNTIME_GAP_INTERVALS:
        events.append(DowntimeGap(since=state.last_tick_at, until=now))

    reaction = state.reaction
    if reaction is not None and not reaction.is_active(now):
        reaction = None  # housekeeping only; expression already ignores ended reactions

    advanced = replace(
        state,
        needs=evolve_through(state, now, elapsed),
        reaction=reaction,
        recent_interactions=prune_interactions(state.recent_interactions, now),
        last_tick_at=now,
        last_updated_at=now,
        rng=replace(state.rng, tick_counter=tick_id),
    )

    advanced, arrival = settle_movement(advanced, now)
    events.extend(arrival)

    if needs_new_activity(advanced, now, params):
        choice = choose_next_activity(advanced, now, inputs, params, rng)
        if choice.activity is advanced.activity and choice.location is advanced.location:
            point = advanced.point  # continuing: stay put
        else:
            point = choose_point(choice.activity, choice.location, rng)
        moved = begin_activity(advanced, now, choice.activity, point, choice.until)
        events.extend(moved.events)
        advanced = moved.state

    return TickResult(state=advanced, tick_id=tick_id, events=tuple(events))
