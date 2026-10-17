"""Approved exact Entry scoring and tie-only RNG; no storage or clock reads."""

from dataclasses import replace
from datetime import timedelta

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.rng import RngState, RngStream
from maplegotchi.core.world.canonical_lifecycle import step
from maplegotchi.core.world.catalog import Capability
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.movement import EdgeStart, Entry, Travel
from maplegotchi.core.world.pathfinding import find_route
from maplegotchi.core.world.resolution import (
    DecisionContext,
    PointKey,
    PointUse,
    ResolutionSnapshot,
    resolve,
    resolve_urgent,
)
from tests.world.test_canonical_lifecycle import AT, PARAMS, initial
from tests.world.test_canonical_lifecycle import world as world
from tests.world.test_resolution import extra


def previous(world: ResolutionSnapshot) -> Travel:
    route = find_route(world.mask, Tile(21, 15), Tile(21, 14)).route
    assert route is not None
    return Travel(route, AT)


@pytest.mark.parametrize("activity", tuple(Activity))
def test_tile_only_order_and_selection_remain_identical(
    world: ResolutionSnapshot, activity: Activity
) -> None:
    context = DecisionContext(RngState("ab" * 32, decision_counter=8))
    travel = previous(world)
    ordinary = resolve(activity, world, travel.route.origin, context)
    urgent = resolve_urgent(activity, world, travel, AT, context)
    assert ordinary.selected is not None and urgent.selected is not None
    assert urgent.selected.key == ordinary.selected.key
    assert [c.key for c in urgent.candidates] == [c.key for c in ordinary.candidates]
    assert [c.score for c in urgent.candidates] == [
        c.score.total * travel.step_us for c in ordinary.candidates
    ]
    assert urgent.decision_draws == ordinary.decision_draws


@pytest.mark.parametrize("backward", [False, True])
def test_entry_continuation_preserves_exact_origin_in_both_directions(
    world: ResolutionSnapshot, backward: bool
) -> None:
    old = previous(world)
    edge = EdgeStart(old.route.origin, old.route.destination, 100000, old.step_us)
    endpoint = edge.a if backward else edge.b
    route = find_route(world.mask, endpoint, Tile(10, 15)).route
    assert route is not None
    old = Travel(route, AT, old.ms_per_step, Entry(edge, endpoint))
    now = AT + timedelta(microseconds=20000)
    result = resolve_urgent(Activity.SLEEP, world, old, now, DecisionContext(RngState("ab" * 32)))
    assert result.selected is not None
    assert result.selected.travel.current_at(now) == old.current_at(now)
    for candidate in result.candidates:
        t = candidate.travel
        assert t.entry is not None
        assert t.entry.start == old.current_at(now)
        # Sleep has room tier zero, no preferences and mid-edge sticky=0.
        assert candidate.score == t.route.total_steps * t.step_us + t.entry.duration_us


@pytest.mark.parametrize("tie", [False, True])
def test_tie_is_exactly_one_seeded_draw_and_no_tie_is_zero(
    world: ResolutionSnapshot, tie: bool
) -> None:
    unavailable = [PointUse(PointKey("idle.hall_center", "idle"), available=False)]
    if not tie:
        unavailable.append(PointUse(PointKey("idle.hall_east", "idle"), available=False))
    snapshot = ResolutionSnapshot(world.world, world.catalog, points=tuple(unavailable))
    context = DecisionContext(
        RngState("ab" * 32, decision_counter=7), PointKey("idle.hall_west", "idle")
    )
    old = previous(snapshot)
    result = resolve_urgent(
        Activity.WALK, snapshot, old, AT + timedelta(microseconds=100000), context
    )
    assert result.selected is not None and result.decision_draws == int(tie)
    if tie:
        assert len(result.candidates) == 2
        assert result.candidates[0].score == result.candidates[1].score
        expected = RngStream(context.rng.seed_hex, "decision", 8)
        assert result.selected == result.candidates[expected.randint(0, 1)]
        assert expected.draw_count == 1
    assert context.rng.decision_counter == 7  # Pure resolver never installs counters.


@pytest.mark.parametrize("tie", [False, True])
def test_urgent_transition_installs_only_tie_counter_once(
    world: ResolutionSnapshot, tie: bool
) -> None:
    snapshot = (
        extra(world, Capability.COMPUTER, room="work_studio", tile=Tile(40, 6)) if tie else world
    )
    old = replace(
        initial(),
        travel=previous(snapshot),
        from_activity=Activity.IDLE,
        rng=RngState("ab" * 32, tick_counter=5, decision_counter=7),
    )
    outcome = step(
        old,
        snapshot,
        AT + timedelta(microseconds=100000),
        BehaviorInputs(server_attention=1),
        PARAMS,
    )
    assert outcome is not None
    assert outcome.frame.rng.tick_counter == 6
    assert outcome.frame.rng.decision_counter == 7 + int(tie)
    assert outcome.frame.action_id == old.action_id + 1
    assert outcome.frame.from_activity == Activity.IDLE
    assert (
        step(
            outcome.frame,
            snapshot,
            outcome.frame.updated_at,
            BehaviorInputs(server_attention=1),
            PARAMS,
        )
        is None
    )
