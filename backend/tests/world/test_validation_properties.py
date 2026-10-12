"""Seed 143 cross-module properties; inputs, time and RNG are explicit."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from random import Random

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.daytime import DayPhase
from maplegotchi.core.rng import RngState
from maplegotchi.core.room import Pose
from maplegotchi.core.state import Expression, Needs
from maplegotchi.core.world.catalog import Category, Owner, Permission
from maplegotchi.core.world.coordinates import Tile, tile_to_feet
from maplegotchi.core.world.legacy_projection import (
    DevelopmentWorld,
    PointRef,
    Presentation,
    project,
    project_point,
)
from maplegotchi.core.world.movement import Travel
from maplegotchi.core.world.pathfinding import find_route
from maplegotchi.core.world.placement import (
    DisplayItem,
    DisplayPlacement,
    PlacementContext,
    PlacementSnapshot,
    SlotKey,
    validate_placement,
)
from maplegotchi.core.world.recovery import Position, recover
from maplegotchi.core.world.resolution import (
    DecisionContext,
    ResolutionSnapshot,
    candidates_for,
    requirement_for,
    resolve,
)
from maplegotchi.core.world.walkability import derive_walkability, validate_safe_layout
from maplegotchi.runtime.world_catalog import load_initial_catalog
from maplegotchi.runtime.world_layout import load_initial_house

AT = datetime(2026, 10, 12, tzinfo=UTC)
CONTEXT = DecisionContext(RngState("8f" * 32))


@pytest.fixture(scope="module")
def snapshot() -> ResolutionSnapshot:
    world = load_initial_house()
    return ResolutionSnapshot(world, load_initial_catalog(world))


@pytest.mark.parametrize("case", range(64))
def test_seeded_path_and_continuity(snapshot: ResolutionSnapshot, case: int) -> None:
    rng = Random(143 + case)  # noqa: S311 - fixed test corpus
    start, end = rng.sample(snapshot.mask.walkable, 2)
    result = find_route(snapshot.mask, start, end)
    assert result == find_route(snapshot.mask, start, end)
    route = result.route
    assert route is not None
    tiles = route.tiles()
    assert (tiles[0], tiles[-1]) == (start, end)
    assert set(tiles) <= set(snapshot.mask.walkable)
    assert all(abs(a.tx - b.tx) + abs(a.ty - b.ty) == 1 for a, b in pairwise(tiles))
    travel = Travel(route, AT, 250)
    for step, (a, b) in enumerate(pairwise(tiles)):
        t = AT + timedelta(milliseconds=step * 250)
        assert travel.position_at(t) == tile_to_feet(a)
        before = travel.position_at(t + timedelta(milliseconds=249))
        after = travel.position_at(t + timedelta(milliseconds=250))
        assert after == tile_to_feet(b)
        assert abs(before[0] - after[0]) + abs(before[1] - after[1]) <= 1
    assert travel.activity_started_at == travel.arrives_at
    assert travel.position_at(travel.arrives_at) == tile_to_feet(end)


@pytest.mark.parametrize("row", range(26))
def test_every_grid_source_recovers_only_to_open_component(
    snapshot: ResolutionSnapshot, row: int
) -> None:
    mask = snapshot.mask
    for x in range(44):
        source = Position(x, row)
        result = recover(mask, source)
        assert result == recover(mask, source)
        assert result.error is None
        assert result.destination in mask.components[0]
        if Tile(x, row) in mask.walkable:
            assert result.destination == Tile(x, row) and result.event is None
        if result.event and result.event.reason.value == "blocked_source":
            assert abs(x - result.destination.tx) + abs(row - result.destination.ty) == 1


def test_recovery_failure_and_closed_path_are_explicit(snapshot: ResolutionSnapshot) -> None:
    empty = replace(snapshot.mask, walkable=(), safe_tile=None, components=())
    assert recover(empty, Position(-1, -1)).error == "unsafe_fallback"
    for room in snapshot.world.regions:
        if room.status.value == "closed":
            target = Tile(room.floor.x, room.floor.y)
            assert find_route(snapshot.mask, Tile(21, 15), target).route is None


@pytest.mark.parametrize("activity", tuple(Activity))
def test_capability_candidate_and_selection_properties(
    snapshot: ResolutionSnapshot, activity: Activity
) -> None:
    requirement = requirement_for(activity)
    for position in Random(143).sample(snapshot.mask.walkable, 8):  # noqa: S311
        candidates = candidates_for(activity, snapshot, position, CONTEXT)
        assert candidates
        assert candidates == candidates_for(activity, snapshot, position, CONTEXT)
        for candidate in candidates:
            assert any(
                set(group) <= set(candidate.point.template.provides)
                for group in requirement.alternatives
            )
            assert candidate.route.origin == position
            assert candidate.route.destination in snapshot.mask.walkable
        selected = resolve(activity, snapshot, position, CONTEXT)
        assert selected == resolve(activity, snapshot, position, CONTEXT)
        assert selected.selected in candidates


@pytest.mark.parametrize("index", range(12))
def test_slots_authorization_and_no_walkability_effect(
    snapshot: ResolutionSnapshot, index: int
) -> None:
    bound = snapshot.catalog.slots[index]
    slot = bound.template
    item = DisplayItem(
        "creation.property",
        slot.accepts[0],
        Category.CREATION_DISPLAY,
        Owner.MAPLE,
        (Permission.MAPLE,),
        True,
        True,
    )
    placement_snapshot = PlacementSnapshot(snapshot.world, snapshot.catalog)
    context = PlacementContext(
        placement_snapshot, (item,), (), AT, timedelta(hours=7), Tile(21, 15)
    )
    key = SlotKey(bound.instance_id, slot.id)
    before = derive_walkability(snapshot.world, snapshot.catalog)
    result = validate_placement(context, item.id, key, Permission.MAPLE)
    assert result == validate_placement(context, item.id, key, Permission.MAPLE)
    assert result.accepted == (slot.status.value == "active" and slot.maple_may_place)
    if result.accepted:
        placed = replace(
            context, placements=(DisplayPlacement("placement.property", item.id, key),)
        )
        assert placed.snapshot.mask == before
        assert validate_safe_layout(snapshot.world, snapshot.catalog, context.maple) == before
    if slot.shares_point:
        point = next(
            p.template
            for p in snapshot.catalog.points
            if p.instance_id == bound.instance_id and p.template.id == slot.shares_point
        )
        assert (point.approach, point.facing) == (slot.approach, slot.facing)


@pytest.mark.parametrize("activity", tuple(Activity))
def test_projection_timing_no_fabricated_movement(
    snapshot: ResolutionSnapshot, activity: Activity
) -> None:
    context = DevelopmentWorld(snapshot.world, snapshot.catalog)
    destinations = candidates_for(activity, snapshot, Tile(21, 15), CONTEXT)
    origins = candidates_for(Activity.IDLE, snapshot, Tile(21, 15), CONTEXT)
    for destination in destinations:
        dest = PointRef(destination.key.instance_id, destination.key.point_id)
        point = project_point(context, dest, activity)
        assert activity in point.allowed_actions
        for origin in origins:
            source = PointRef(origin.key.instance_id, origin.key.point_id)
            start_tile = origin.route.destination
            route = find_route(snapshot.mask, start_tile, destination.route.destination).route
            assert route is not None
            travel = Travel(route, AT, 317)
            presentation = Presentation(
                activity,
                travel.arrives_at,
                travel.arrives_at + timedelta(minutes=1),
                Needs(30, 30, 30, 30),
                None,
                Expression.CALM,
                Pose.STAND,
                DayPhase.AFTERNOON,
                "fixture",
            )
            if route.total_steps and project_point(context, source, Activity.IDLE).id == point.id:
                with pytest.raises(ValueError, match="collapses"):
                    project(
                        context,
                        dest,
                        presentation,
                        AT,
                        travel=travel,
                        origin=source,
                        from_activity=Activity.IDLE,
                    )
            else:
                projected = project(
                    context,
                    dest,
                    presentation,
                    AT,
                    travel=travel,
                    origin=source,
                    from_activity=Activity.IDLE,
                )
                if projected.route:
                    assert (projected.route.departed_at, projected.route.arrives_at) == (
                        travel.departed_at,
                        travel.arrives_at,
                    )
                arrival = project(
                    context,
                    dest,
                    presentation,
                    travel.arrives_at,
                    travel=travel,
                    origin=source,
                    from_activity=Activity.IDLE,
                )
                assert arrival.position == (float(point.x), float(point.y))
                assert arrival.presentation is presentation
