"""The room as data (ADR-0027): furniture mapping, interaction points, the walking graph."""

from __future__ import annotations

import itertools
import math
from datetime import UTC, datetime, timedelta

import pytest

from maplegotchi.core.activities import SPECS, Activity, RoomLocation
from maplegotchi.core.room import (
    ADJACENCY,
    EDGES,
    FURNITURE_AT,
    POINT_BY_ID,
    POINTS,
    WALK_SPEED,
    Furniture,
    PathPoint,
    Route,
    Whereabouts,
    canonical_point,
    node_xy,
    plan_route,
    points_for,
    shortest_path,
    travel_time,
)

T0 = datetime(2026, 3, 1, 5, 0, tzinfo=UTC)

# The owner's room v1 mapping (ADR-0027): activity -> furniture.
ROOM_V1 = {
    Activity.WRITE: Furniture.WRITING_DESK,
    Activity.OBSERVE_SERVER: Furniture.COMPUTER_DESK,
    Activity.READ: Furniture.BOOKSHELF,
    Activity.REST: Furniture.SOFA,
    Activity.SLEEP: Furniture.BED,
    Activity.THINK: Furniture.WINDOW_PLANT_CORNER,
    Activity.WALK: Furniture.OPEN_AREA,
    Activity.IDLE: Furniture.OPEN_AREA,
}


@pytest.mark.parametrize(("activity", "furniture"), ROOM_V1.items())
def test_every_action_resolves_to_its_furniture(activity: Activity, furniture: Furniture) -> None:
    points = points_for(activity)
    assert points, activity
    assert {p.furniture for p in points} == {furniture}
    assert all(FURNITURE_AT[loc] is furniture for loc in SPECS[activity].locations)


def test_writing_desk_and_computer_desk_are_separate_furniture() -> None:
    write = points_for(Activity.WRITE)
    observe = points_for(Activity.OBSERVE_SERVER)
    assert {p.location for p in write} == {RoomLocation.DESK}
    assert {p.location for p in observe} == {RoomLocation.TERMINAL}
    assert {p.id for p in write}.isdisjoint({p.id for p in observe})
    assert all((p.x, p.y) != (q.x, q.y) for p in write for q in observe)


def test_rest_is_on_the_sofa_and_sleep_in_bed() -> None:
    assert {p.location for p in points_for(Activity.REST)} == {RoomLocation.SOFA}
    assert {p.location for p in points_for(Activity.SLEEP)} == {RoomLocation.BED}
    assert {p.location for p in points_for(Activity.THINK)} == {RoomLocation.WINDOW}


def test_interaction_points_carry_position_facing_pose_and_actions() -> None:
    for point in POINTS:
        assert point.id and point.allowed_actions
        assert point.facing.value in {"left", "right", "front", "back"}
        assert point.pose.value
        for action in point.allowed_actions:
            assert point.location in SPECS[action].locations


def test_declared_edge_lengths_match_the_geometry() -> None:
    for a, b, length in EDGES:
        (ax, ay), (bx, by) = node_xy(a), node_xy(b)
        assert abs(math.hypot(bx - ax, by - ay) - length) < 1.0, (a, b)


def test_graph_is_connected() -> None:
    for point in POINTS:
        for other in POINTS:
            nodes, length = shortest_path(point.id, other.id)
            assert nodes[0] == point.id and nodes[-1] == other.id
            assert length >= 0


def test_shortest_path_is_deterministic_and_uses_edges() -> None:
    first = shortest_path("bed.side", "computer_desk.chair")
    assert first == shortest_path("bed.side", "computer_desk.chair")
    nodes, length = first
    assert nodes == (
        "bed.side",
        "lane.bed",
        "lane.bookshelf",
        "lane.window",
        "lane.desk",
        "lane.terminal",
        "computer_desk.chair",
    )
    assert length == 65 + 180 + 170 + 140 + 200 + 50
    for a, b in itertools.pairwise(nodes):
        assert any(n == b for n, _ in ADJACENCY[a])


def test_travel_time_rounds_up_to_milliseconds() -> None:
    assert travel_time(WALK_SPEED) == timedelta(seconds=1)
    assert travel_time(1) == timedelta(milliseconds=math.ceil(1000 / WALK_SPEED))
    with pytest.raises(ValueError):
        travel_time(0)


def test_route_from_a_point_ends_at_the_destination() -> None:
    bed = POINT_BY_ID["bed.side"]
    desk = POINT_BY_ID["writing_desk.chair"]
    route = plan_route(Whereabouts(bed.x, bed.y, node=bed.id), desk, T0, Activity.SLEEP)
    assert route is not None
    assert route.destination == desk
    assert route.path[0].node == bed.id and route.path[0].distance == 0
    assert route.arrives_at == T0 + travel_time(route.length)
    assert route.position_at(T0) == (bed.x, bed.y)
    assert route.position_at(route.arrives_at) == (desk.x, desk.y)
    assert route.position_at(route.arrives_at + timedelta(hours=1)) == (desk.x, desk.y)


def test_no_route_when_already_at_the_destination() -> None:
    desk = POINT_BY_ID["writing_desk.chair"]
    assert plan_route(Whereabouts(desk.x, desk.y, node=desk.id), desk, T0, Activity.WRITE) is None


def test_position_is_interpolated_along_the_path() -> None:
    a = POINT_BY_ID["bookshelf.front"]
    b = POINT_BY_ID["window.view"]
    route = plan_route(Whereabouts(a.x, a.y, node=a.id), b, T0, Activity.READ)
    assert route is not None
    midway = T0 + (route.arrives_at - T0) / 2
    x, _ = route.position_at(midway)
    assert min(a.x, b.x) <= x <= max(a.x, b.x)
    walked = route.progress_at(midway)
    assert abs(walked - route.length / 2) < 1e-6


def test_route_invariants_are_enforced() -> None:
    desk = POINT_BY_ID["writing_desk.chair"]
    lane = node_xy("lane.desk")
    ok = (PathPoint(lane[0], lane[1], 0.0, "lane.desk"), PathPoint(desk.x, desk.y, 50.0, desk.id))
    Route(T0, T0 + timedelta(seconds=1), ok, Activity.IDLE)
    with pytest.raises(ValueError):
        Route(T0, T0, ok, Activity.IDLE)  # arrives must be after departure
    with pytest.raises(ValueError):
        Route(T0, T0 + timedelta(seconds=1), ok[:1], Activity.IDLE)
    with pytest.raises(ValueError):  # must end at an interaction point
        Route(T0, T0 + timedelta(seconds=1), (ok[1], PathPoint(*lane, 60.0, "lane.desk")), _A())
    with pytest.raises(ValueError):  # off-graph corner only at the start
        Route(T0, T0 + timedelta(seconds=1), (ok[0], PathPoint(0, 0, 9.0, None), ok[1]), _A())


def _A() -> Activity:
    return Activity.IDLE


def test_canonical_point_is_the_first_matching_point() -> None:
    for activity in Activity:
        for location in SPECS[activity].locations:
            assert canonical_point(activity, location) == points_for(activity, location)[0]
    with pytest.raises(ValueError):
        canonical_point(Activity.SLEEP, RoomLocation.SOFA)
