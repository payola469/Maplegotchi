"""Movement through the single-writer runtime (ADR-0027): persisted, settled, restart-safe."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from maplegotchi.core.state import InteractionKind
from maplegotchi.core.timeline import ActivityChanged
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.life import LifeRuntime
from tests.persistence_support import new_life, open_runtime

TICK = timedelta(seconds=300)


def walk_starts(runtime: LifeRuntime, clock: FakeClock, limit: int = 400) -> None:
    """Advance heartbeats until a heartbeat sends Maple walking somewhere."""
    for _ in range(limit):
        clock.advance(TICK)
        runtime.heartbeat_if_due()
        route = runtime.state.route
        if route is not None and clock.now() < route.arrives_at:
            return
    raise AssertionError("no walk started")


def test_walk_is_persisted_and_survives_a_restart_mid_walk(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    walk_starts(runtime, clock)
    walking = runtime.state
    runtime.close()
    with open_runtime(data_dir, clock) as reopened:
        assert reopened.state == walking  # route, point, and timing round-trip exactly
        assert reopened.state.route == walking.route


def test_arrival_is_recorded_between_heartbeats_at_the_exact_time(tmp_path: Path) -> None:
    _, clock, runtime = new_life(tmp_path)
    walk_starts(runtime, clock)
    route = runtime.state.route
    assert route is not None
    assert not runtime.arrival_due()
    assert runtime.settle_committed() is None  # not there yet: nothing is written
    clock.set(route.arrives_at + timedelta(seconds=2))
    assert runtime.arrival_due()
    revision = runtime.revision
    committed = runtime.settle_committed()
    assert committed is not None
    assert committed.revision == revision + 1
    assert runtime.state.route is None
    assert runtime.state.activity_started_at == route.arrives_at
    changed = [e for e in committed.events if isinstance(e, ActivityChanged)]
    assert [e.at for e in changed] == [route.arrives_at] or route.from_activity is (
        runtime.state.activity
    )
    timeline = runtime.timeline()
    assert [e.event for e in timeline[-len(committed.events) :]] == list(committed.events)
    assert runtime.settle_committed() is None  # idempotent


def test_interaction_settles_a_finished_walk_first(tmp_path: Path) -> None:
    _, clock, runtime = new_life(tmp_path)
    walk_starts(runtime, clock)
    route = runtime.state.route
    assert route is not None
    clock.set(route.arrives_at + timedelta(seconds=1))
    runtime.interact(InteractionKind.GREET)
    assert runtime.state.route is None
    kinds = [type(e.event).__name__ for e in runtime.timeline()[-2:]]
    if route.from_activity is not runtime.state.activity:
        assert kinds == ["ActivityChanged", "InteractionAccepted"]


def test_heartbeat_after_arrival_records_the_activity_change(tmp_path: Path) -> None:
    _, clock, runtime = new_life(tmp_path)
    walk_starts(runtime, clock)
    route = runtime.state.route
    assert route is not None
    clock.advance(TICK)
    tick = runtime.heartbeat_if_due()
    assert tick is not None
    if route.from_activity is not route.destination.allowed_actions[0]:
        assert any(isinstance(e, ActivityChanged) and e.at == route.arrives_at for e in tick.events)
