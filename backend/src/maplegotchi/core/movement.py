"""Moving Maple between interaction points (ADR-0027), as pure state transitions.

action selected -> destination resolved -> walk -> arrive -> activity begins.

- `begin_activity` resolves the destination point and plans the walk from where
  Maple is at `now` (part-way along a previous route if still walking: the old
  destination is simply cancelled and never begins).
- `settle_movement` records an arrival whose time has passed. Arrival is
  already true in every derived view at `arrives_at`; settling only makes it
  part of the stored state and emits `ActivityChanged` at the exact arrival time.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.rng import RngStream
from maplegotchi.core.room import InteractionPoint, Route, plan_route, points_for, whereabouts
from maplegotchi.core.state import MapleState
from maplegotchi.core.timeline import ActivityChanged, LifeEvent


@dataclass(frozen=True, slots=True)
class MovementResult:
    state: MapleState
    events: tuple[LifeEvent, ...]
    route: Route | None  # the new walk, if one started
    cancelled: Route | None  # a walk abandoned before arrival, if any


def performed_activity(state: MapleState, now: datetime) -> Activity:
    """The activity Maple is actually doing at `now` (the previous one while walking)."""
    if state.route is not None and state.walking_at(now):
        return state.route.from_activity
    return state.activity


def settle_movement(state: MapleState, now: datetime) -> tuple[MapleState, tuple[LifeEvent, ...]]:
    """Record an arrival that has happened by `now`. No-op if not walking or not there yet."""
    require_utc(now, "now")
    route = state.route
    if route is None or now < route.arrives_at:
        return state, ()
    events: tuple[LifeEvent, ...] = ()
    if route.from_activity is not state.activity:
        events = (
            ActivityChanged(
                at=route.arrives_at, previous=route.from_activity, current=state.activity
            ),
        )
    settled = replace(
        state, route=None, last_updated_at=max(state.last_updated_at, route.arrives_at)
    )
    return settled, events


def choose_point(
    activity: Activity, location: RoomLocation, rng: RngStream | None
) -> InteractionPoint:
    """A point for `activity` at `location`; a seeded draw only if there are several."""
    candidates = points_for(activity, location)
    if not candidates:
        raise ValueError(f"{activity} has no interaction point at {location}")
    if len(candidates) == 1 or rng is None:
        return candidates[0]
    return candidates[rng.randint(0, len(candidates) - 1)]


def begin_activity(
    state: MapleState,
    now: datetime,
    activity: Activity,
    point: InteractionPoint,
    until_after_arrival: datetime,
) -> MovementResult:
    """Start `activity` at `point`, walking there first if Maple is elsewhere.

    `until_after_arrival` is the activity's end as if it began at `now`; the
    planned duration is kept and shifted to start at arrival.
    """
    require_utc(now, "now")
    if now < state.last_updated_at:
        raise ValueError("cannot begin an activity before the latest state update")
    if activity not in point.allowed_actions:
        raise ValueError(f"{point.id} does not allow {activity}")
    duration = until_after_arrival - now
    if duration.total_seconds() <= 0:
        raise ValueError("an activity needs a positive duration")

    walking = state.walking_at(now)
    if state.route is not None and not walking:
        raise ValueError("settle a completed walk before beginning another activity")
    cancelled = state.route if walking else None
    performed = performed_activity(state, now)

    here = whereabouts(state.route, state.point, now)
    route = plan_route(here, point, now, performed)
    if route is None:
        # Already standing at the point (possibly passing through it mid-walk). A new
        # activity begins now; the same, already-begun activity simply continues.
        events: tuple[LifeEvent, ...] = ()
        started = state.activity_started_at
        if walking or activity is not state.activity:
            started = now
            if performed is not activity:
                events = (ActivityChanged(at=now, previous=performed, current=activity),)
        new_state = replace(
            state,
            activity=activity,
            location=point.location,
            point_id=point.id,
            route=None,
            activity_started_at=started,
            activity_until=now + duration,
            last_updated_at=now,
        )
        return MovementResult(new_state, events, None, cancelled)

    arrives = route.arrives_at
    new_state = replace(
        state,
        activity=activity,
        location=point.location,
        point_id=point.id,
        route=route,
        activity_started_at=arrives,
        activity_until=arrives + duration,
        last_updated_at=now,
    )
    return MovementResult(new_state, (), route, cancelled)
