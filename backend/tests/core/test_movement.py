"""Walk, arrive, then act (ADR-0027): the activity never begins before arrival."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from maplegotchi.core.activities import SPECS, Activity
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.heartbeat import evolve_needs, evolve_through, heartbeat
from maplegotchi.core.movement import (
    MovementResult,
    begin_activity,
    choose_point,
    performed_activity,
    settle_movement,
)
from maplegotchi.core.rng import RngStream
from maplegotchi.core.room import POINT_BY_ID
from maplegotchi.core.state import Expression
from maplegotchi.core.timeline import ActivityChanged
from tests.core.support import PARAMS, SEED, at_local, make_state, needs

NOON = at_local(12)
HOUR = timedelta(hours=1)
DESK = POINT_BY_ID["writing_desk.chair"]
TERMINAL = POINT_BY_ID["computer_desk.chair"]
BED = POINT_BY_ID["bed.side"]


def walking_to_desk() -> MovementResult:
    reading = make_state(at=NOON, activity=Activity.READ)
    return begin_activity(reading, NOON, Activity.WRITE, DESK, NOON + 30 * timedelta(minutes=1))


def test_selecting_an_action_resolves_a_destination_and_starts_walking() -> None:
    moved = walking_to_desk()
    state = moved.state
    assert state.activity is Activity.WRITE
    assert state.point == DESK
    assert moved.route is not None and state.route == moved.route
    assert moved.events == ()  # nothing has begun yet
    assert moved.cancelled is None
    assert state.route.departed_at == NOON
    assert state.activity_started_at == state.route.arrives_at > NOON
    # The planned duration is kept and shifted to begin at arrival.
    assert state.activity_until - state.activity_started_at == timedelta(minutes=30)


def test_activity_is_not_active_until_arrival() -> None:
    state = walking_to_desk().state
    route = state.route
    assert route is not None
    just_before = route.arrives_at - timedelta(milliseconds=1)
    assert state.walking_at(NOON) and state.walking_at(just_before)
    assert not state.walking_at(route.arrives_at)
    assert performed_activity(state, just_before) is Activity.READ
    assert performed_activity(state, route.arrives_at) is Activity.WRITE
    # Expression follows walking, not writing, until Maple sits down.
    assert state.expression_at(just_before) is not Expression.FOCUSED
    assert state.expression_at(route.arrives_at) is Expression.FOCUSED
    assert state.position_at(route.arrives_at) == (DESK.x, DESK.y)


def test_settling_before_arrival_changes_nothing() -> None:
    state = walking_to_desk().state
    route = state.route
    assert route is not None
    same, events = settle_movement(state, route.arrives_at - timedelta(milliseconds=1))
    assert same is state and events == ()


def test_arrival_begins_the_activity_at_the_exact_arrival_time() -> None:
    state = walking_to_desk().state
    route = state.route
    assert route is not None
    later = route.arrives_at + timedelta(minutes=3)
    settled, events = settle_movement(state, later)
    assert settled.route is None
    assert settled.point == DESK
    assert events == (ActivityChanged(route.arrives_at, Activity.READ, Activity.WRITE),)
    assert settled.activity_started_at == route.arrives_at
    assert settled.last_updated_at == route.arrives_at


def test_changing_the_action_while_walking_reroutes_from_the_current_position() -> None:
    state = walking_to_desk().state
    first = state.route
    assert first is not None
    midway = first.departed_at + (first.arrives_at - first.departed_at) / 2
    here = state.position_at(midway)
    moved = begin_activity(state, midway, Activity.OBSERVE_SERVER, TERMINAL, midway + HOUR / 6)
    second = moved.route
    assert moved.cancelled == first  # the old destination is cancelled
    assert second is not None and second.departed_at == midway
    assert (second.path[0].x, second.path[0].y) == pytest.approx(here)
    assert second.destination == TERMINAL
    assert second.from_activity is Activity.READ  # writing never began
    assert moved.state.activity is Activity.OBSERVE_SERVER
    _, events = settle_movement(moved.state, second.arrives_at)
    assert events == (ActivityChanged(second.arrives_at, Activity.READ, Activity.OBSERVE_SERVER),)


def test_rerouting_back_toward_where_maple_came_from_turns_around() -> None:
    reading = make_state(at=NOON, activity=Activity.READ)
    moved = begin_activity(reading, NOON, Activity.SLEEP, BED, NOON + 2 * HOUR)
    route = moved.route
    assert route is not None
    soon = NOON + timedelta(milliseconds=100)  # 12 units into the first 20-unit edge
    walked = route.progress_at(soon)
    back = begin_activity(
        moved.state, soon, Activity.READ, POINT_BY_ID["bookshelf.front"], soon + HOUR
    )
    assert back.route is not None
    assert back.route.length == pytest.approx(walked)  # just the steps back, not via the bed
    assert back.route.path[1].node == "bookshelf.front"


def test_beginning_the_same_activity_where_maple_already_is_continues_it() -> None:
    writing = make_state(at=NOON, activity=Activity.WRITE)
    moved = begin_activity(writing, NOON + HOUR, Activity.WRITE, writing.point, NOON + 2 * HOUR)
    assert moved.route is None and moved.events == ()
    assert moved.state.activity_started_at == NOON
    assert moved.state.activity_until == NOON + 2 * HOUR


def test_a_new_activity_at_the_same_point_begins_immediately() -> None:
    idle = make_state(at=NOON, activity=Activity.IDLE)
    moved = begin_activity(idle, NOON, Activity.WALK, idle.point, NOON + HOUR / 4)
    assert moved.route is None
    assert moved.events == (ActivityChanged(NOON, Activity.IDLE, Activity.WALK),)
    assert moved.state.activity_started_at == NOON


def test_begin_refuses_unsettled_arrivals_and_wrong_points() -> None:
    state = walking_to_desk().state
    route = state.route
    assert route is not None
    with pytest.raises(ValueError, match="settle"):
        begin_activity(state, route.arrives_at, Activity.READ, POINT_BY_ID["bookshelf.front"],
                       route.arrives_at + HOUR)  # fmt: skip
    with pytest.raises(ValueError):
        begin_activity(make_state(at=NOON), NOON, Activity.SLEEP, DESK, NOON + HOUR)
    with pytest.raises(ValueError):
        begin_activity(make_state(at=NOON), NOON, Activity.WRITE, DESK, NOON)


def test_state_rejects_inconsistent_routes_and_points() -> None:
    state = walking_to_desk().state
    with pytest.raises(ValueError):
        replace(state, activity_started_at=state.activity_started_at + HOUR)
    with pytest.raises(ValueError):
        replace(state, point_id="bed.side")
    with pytest.raises(ValueError):
        replace(state, point_id="no.such.point")


def test_point_draw_happens_only_when_there_is_a_choice() -> None:
    rng = RngStream(SEED, "tick", 1)
    assert choose_point(Activity.WRITE, DESK.location, rng) == DESK
    assert rng.random() == RngStream(SEED, "tick", 1).random()  # no draw consumed
    open_area = {
        choose_point(Activity.IDLE, POINT_BY_ID["open_area.center"].location,
                     RngStream(SEED, "tick", i)).id
        for i in range(40)
    }  # fmt: skip
    assert open_area == {"open_area.center", "open_area.west", "open_area.east"}


def test_needs_while_walking_use_the_walk_spec_until_arrival() -> None:
    state = replace(walking_to_desk().state, last_tick_at=NOON)
    route = state.route
    assert route is not None
    now = NOON + timedelta(minutes=5)
    expected = evolve_needs(state.needs, Activity.WALK, route.arrives_at - NOON)
    expected = evolve_needs(expected, Activity.WRITE, now - route.arrives_at)
    assert evolve_through(state, now, now - NOON) == expected
    plain = make_state(at=NOON, activity=Activity.WRITE)
    assert evolve_through(plain, now, now - NOON) == evolve_needs(
        plain.needs, Activity.WRITE, now - NOON
    )


def test_heartbeat_settles_arrival_before_choosing() -> None:
    state = walking_to_desk().state
    tick = heartbeat(state, NOON + PARAMS.heartbeat_interval, _calm(), PARAMS)
    assert tick.state.route is None
    route = state.route
    assert route is not None
    assert ActivityChanged(route.arrives_at, Activity.READ, Activity.WRITE) in tick.events


def test_heartbeat_reroutes_an_exhausted_maple_to_bed_mid_walk() -> None:
    reading = make_state(at=NOON, activity=Activity.READ, state_needs=needs(energy=10.4))
    moved = begin_activity(reading, NOON, Activity.WRITE, DESK, NOON + HOUR)
    assert moved.route is not None
    # A route long enough that the next heartbeat still finds Maple walking.
    slow = replace(
        moved.state,
        route=replace(moved.route, arrives_at=NOON + 2 * PARAMS.heartbeat_interval),
        activity_started_at=NOON + 2 * PARAMS.heartbeat_interval,
        activity_until=NOON + 3 * HOUR,
    )
    tick = heartbeat(slow, NOON + PARAMS.heartbeat_interval, _calm(), PARAMS)
    assert tick.state.activity is Activity.SLEEP
    assert tick.state.route is not None and tick.state.route.destination == BED
    assert tick.state.route.from_activity is Activity.READ


def test_agreed_duration_ranges() -> None:
    agreed = {
        Activity.READ: (20, 60),
        Activity.WRITE: (15, 45),
        Activity.OBSERVE_SERVER: (5, 15),
        Activity.THINK: (5, 15),
        Activity.REST: (15, 45),
        Activity.WALK: (5, 20),
        Activity.IDLE: (5, 30),
        Activity.SLEEP: (90, 240),  # per segment, renewed at night (ADR-0028)
    }
    assert {a: (s.min_minutes, s.max_minutes) for a, s in SPECS.items()} == agreed


def _calm() -> BehaviorInputs:
    return BehaviorInputs()
