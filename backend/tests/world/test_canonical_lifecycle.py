"""Pure canonical life-loop evidence; no databases, wall clock or default service."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.rng import RngState
from maplegotchi.core.state import Needs
from maplegotchi.core.world.canonical_lifecycle import LifeFrame, LifeLoopBlocked, step
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.resolution import PointKey, ResolutionSnapshot
from maplegotchi.runtime.world_catalog import load_initial_catalog
from maplegotchi.runtime.world_layout import load_initial_house

AT = datetime(2026, 10, 14, 12, tzinfo=UTC)
PARAMS = CoreParameters(heartbeat_interval=timedelta(seconds=1))


@pytest.fixture(scope="module")
def world() -> ResolutionSnapshot:
    layout = load_initial_house()
    return ResolutionSnapshot(layout, load_initial_catalog(layout))


def initial() -> LifeFrame:
    return LifeFrame(
        Needs(60, 20, 60, 50),
        Activity.IDLE,
        AT,
        AT + timedelta(minutes=15),
        AT,
        AT,
        AT,
        RngState("ab" * 32),
        0,
        PointKey("idle.hall_center", "idle"),
        Tile(21, 15),
        None,
        None,
    )


def test_deterministic_actual_action_and_exact_arrival(world: ResolutionSnapshot) -> None:
    old = initial()
    now = AT + timedelta(minutes=15)
    a = step(old, world, now, BehaviorInputs(), PARAMS)
    b = step(old, world, now, BehaviorInputs(), PARAMS)
    assert a == b and a is not None
    assert old == initial()
    travel = a.frame.travel
    assert travel is not None
    walking = step(a.frame, world, now + timedelta(seconds=1), BehaviorInputs(), PARAMS)
    assert walking is not None and walking.frame.travel == travel
    assert walking.frame.rng.decision_counter == 1
    assert walking.frame.action_id == 1 and walking.actions == ()
    arrived = step(walking.frame, world, travel.arrives_at, BehaviorInputs(), PARAMS)
    assert arrived is not None and arrived.frame.travel is None
    assert arrived.frame.tile == travel.route.destination
    assert [e.kind.value for e in arrived.actions] == ["arrived", "activity_started"]
    assert all(e.at == travel.arrives_at for e in arrived.actions)
    assert step(arrived.frame, world, travel.arrives_at, BehaviorInputs(), PARAMS) is None


@pytest.mark.parametrize("critical", [False, True])
def test_mid_edge_priority_cannot_be_delayed(world: ResolutionSnapshot, critical: bool) -> None:
    started = step(initial(), world, AT + timedelta(minutes=15), BehaviorInputs(), PARAMS)
    assert started is not None and started.frame.travel is not None
    frame = started.frame if critical else replace(started.frame, needs=Needs(60, 5, 60, 50))
    # Before another tick is due, the supplied urgent signal must still fail closed.
    now = frame.travel.departed_at + timedelta(microseconds=100000) if frame.travel else AT
    with pytest.raises(
        LifeLoopBlocked, match="critical_interrupt" if critical else "high_interrupt"
    ):
        step(frame, world, now, BehaviorInputs(server_attention=1 if critical else 0), PARAMS)
    assert frame.travel == started.frame.travel


def test_clock_reversal_and_overdue_arrival_are_explicit(world: ResolutionSnapshot) -> None:
    with pytest.raises(LifeLoopBlocked, match="time"):
        step(initial(), world, AT - timedelta(seconds=1), BehaviorInputs(), PARAMS)
    started = step(initial(), world, AT + timedelta(minutes=15), BehaviorInputs(), PARAMS)
    assert started is not None
    continued = step(started.frame, world, started.frame.until, BehaviorInputs(), PARAMS)
    assert continued is not None and continued.frame.action_id == 2
    arrival = [e for e in continued.actions if e.kind.value == "arrived"]
    assert len(arrival) == 1 and started.frame.travel is not None
    assert arrival[0].at == started.frame.travel.arrives_at
    assert (
        step(continued.frame, world, continued.frame.updated_at, BehaviorInputs(), PARAMS) is None
    )


def test_continuing_same_activity_in_place_preserves_original_start(
    world: ResolutionSnapshot,
) -> None:
    before = replace(initial(), needs=Needs(60, 80, 60, 50), rng=RngState(f"{12:064x}"))
    now = before.until
    outcome = step(before, world, now, BehaviorInputs(), PARAMS)
    assert outcome is not None
    assert outcome.frame.activity is before.activity
    assert outcome.frame.travel is None
    assert outcome.frame.started_at == before.started_at
    assert outcome.frame.until > now
    assert outcome.actions[0].at == before.until
