"""Independent shortest-path, T6, compression, timing and no-teleport acceptance."""

from __future__ import annotations

from collections import deque
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from maplegotchi.core.world.coordinates import Tile, tile_to_feet
from maplegotchi.core.world.movement import EdgeStart, Entry, Travel, reroute
from maplegotchi.core.world.pathfinding import Route, Waypoint, compress, find_route
from maplegotchi.core.world.walkability import Walkability
from tests.world.oracle import Oracle
from tests.world.pathfinding_tuning import canonical_fixture, report

AT = datetime(2026, 10, 11, tzinfo=UTC)


@pytest.fixture(scope="module")
def house() -> tuple[Walkability, tuple[Tile, ...], Oracle]:
    return canonical_fixture()


def synthetic(
    house: tuple[Walkability, tuple[Tile, ...], Oracle], tiles: tuple[Tile, ...]
) -> Walkability:
    # Deliberately bypass safe-layout acceptance to test unavailable paths. No validator weakening.
    return replace(house[0], walkable=tiles)


@pytest.mark.parametrize("i", range(7))
@pytest.mark.parametrize("j", range(7))
@pytest.mark.parametrize("penalty", [0, 1, 2, 4])
def test_canonical_t6(
    house: tuple[Walkability, tuple[Tile, ...], Oracle], i: int, j: int, penalty: int
) -> None:
    mask, points, spec = house
    result = find_route(mask, points[i], points[j], penalty)
    assert result.error is None and result.route is not None
    route = result.route
    assert route.total_steps == int(spec.walks.rows[i][j + 1])
    tiles = route.tiles()
    assert len(tiles) == route.total_steps + 1
    assert tiles[0] == points[i] and tiles[-1] == points[j]
    assert set(tiles) <= set(mask.walkable)
    assert all(
        abs(tiles[i].tx - tiles[i + 1].tx) + abs(tiles[i].ty - tiles[i + 1].ty) == 1
        for i in range(len(tiles) - 1)
    )
    assert compress(tiles) == route
    for speed in (250, 300):
        travel = Travel(route, AT, speed)
        assert travel.arrives_at == AT + timedelta(milliseconds=route.total_steps * speed)
        assert travel.activity_started_at == travel.arrives_at
        for point in route.waypoints:
            now = AT + timedelta(milliseconds=point.cumulative_steps * speed)
            assert travel.position_at(now) == tile_to_feet(point.tile)
        assert travel.position_at(travel.arrives_at) == tile_to_feet(points[j])


def reference(allowed: set[Tile], start: Tile, target: Tile) -> tuple[int, int] | None:
    """Independent BFS levels, then turn DP on the shortest-path DAG (not A*)."""
    distances = {start: 0}
    queue = deque([start])
    while queue:
        tile = queue.popleft()
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            x, y = tile.tx + dx, tile.ty + dy
            if not 0 <= x < 44 or not 0 <= y < 26:
                continue
            neighbor = Tile(x, y)
            if neighbor in allowed and neighbor not in distances:
                distances[neighbor] = distances[tile] + 1
                queue.append(neighbor)
    if target not in distances:
        return None
    costs = {(start, (0, 0)): 0}
    for depth in range(distances[target]):
        for (tile, incoming), turns in tuple(costs.items()):
            if distances[tile] != depth:
                continue
            for neighbor, level in distances.items():
                if (
                    level != depth + 1
                    or abs(neighbor.tx - tile.tx) + abs(neighbor.ty - tile.ty) != 1
                ):
                    continue
                direction = (neighbor.tx - tile.tx, neighbor.ty - tile.ty)
                cost = turns + int(incoming != (0, 0) and incoming != direction)
                state = (neighbor, direction)
                costs[state] = min(costs.get(state, cost), cost)
    return distances[target], min(turns for (tile, _), turns in costs.items() if tile == target)


@pytest.mark.parametrize("bits", range(128))
@pytest.mark.parametrize("penalty", [1, 4])
def test_exhaustive_small_maze(
    house: tuple[Walkability, tuple[Tile, ...], Oracle], bits: int, penalty: int
) -> None:
    start, target = Tile(1, 1), Tile(3, 3)
    options = tuple(
        Tile(x, y) for y in range(1, 4) for x in range(1, 4) if (x, y) not in ((1, 1), (3, 3))
    )
    allowed = {start, target} | {tile for i, tile in enumerate(options) if bits & (1 << i)}
    expected = reference(allowed, start, target)
    mask = synthetic(house, tuple(sorted(allowed, key=lambda t: (t.ty, t.tx))))
    result = find_route(mask, start, target, penalty)
    if expected is None:
        assert result.error == "no_destination" and result.route is None
    else:
        assert result.route is not None
        assert (result.route.total_steps, result.route.turns) == expected
        assert set(result.route.tiles()) <= allowed
    assert (
        find_route(replace(mask, walkable=tuple(reversed(mask.walkable))), start, target, penalty)
        == result
    )


def test_trivial_adjacent_straight_and_ties(
    house: tuple[Walkability, tuple[Tile, ...], Oracle],
) -> None:
    mask = synthetic(house, tuple(Tile(x, y) for y in range(1, 4) for x in range(1, 4)))
    for target, length in ((Tile(1, 1), 0), (Tile(2, 1), 1), (Tile(3, 1), 2)):
        result = find_route(mask, Tile(1, 1), target)
        assert result.route is not None and result.route.total_steps == length
        assert len(result.route.waypoints) == (1 if length == 0 else 2)
    tie = find_route(mask, Tile(1, 1), Tile(3, 3))
    assert tie.route == Route((Waypoint(1, 1, 0), Waypoint(3, 1, 2), Waypoint(3, 3, 4)))
    headed = find_route(mask, Tile(1, 1), Tile(2, 2), initial_heading=3)
    assert headed.route == compress((Tile(1, 1), Tile(1, 2), Tile(2, 2)))
    for _ in range(10):
        assert find_route(mask, Tile(1, 1), Tile(3, 3)) == tie


@pytest.mark.parametrize(
    "start,target",
    [
        (Tile(1, 3), Tile(21, 15)),
        (Tile(21, 15), Tile(1, 3)),
        (Tile(1, 20), Tile(21, 15)),
        (Tile(21, 15), Tile(6, 18)),
        (Tile(0, 0), Tile(21, 15)),
    ],
)
def test_invalid_closed_blocked_no_destination(
    house: tuple[Walkability, tuple[Tile, ...], Oracle], start: Tile, target: Tile
) -> None:
    result = find_route(house[0], start, target)
    assert result.error == "no_destination" and result.route is None


@pytest.mark.parametrize("penalty", [-1, 5, True, 1.5])
def test_invalid_penalty(house: tuple[Walkability, tuple[Tile, ...], Oracle], penalty: int) -> None:
    with pytest.raises(ValueError):
        find_route(house[0], Tile(21, 15), Tile(21, 15), penalty)


@pytest.mark.parametrize(
    "points",
    [
        (),
        (Waypoint(1, 1, 1),),
        (Waypoint(1, 1, 0), Waypoint(2, 2, 2)),
        (Waypoint(1, 1, 0), Waypoint(1, 1, 0)),
        (Waypoint(1, 1, 0), Waypoint(2, 1, 2)),
    ],
)
def test_invalid_route_contract(points: tuple[Waypoint, ...]) -> None:
    with pytest.raises(ValueError):
        Route(points)


@pytest.mark.parametrize(
    "tiles", [(), (Tile(1, 1), Tile(2, 2)), (Tile(1, 1), Tile(3, 1)), (Tile(1, 1), Tile(1, 1))]
)
def test_invalid_compression(tiles: tuple[Tile, ...]) -> None:
    with pytest.raises(ValueError):
        compress(tiles)


def test_zero_length_and_phase() -> None:
    route = compress((Tile(1, 1),))
    travel = Travel(route, AT)
    assert travel.arrives_at == AT
    assert travel.phase_at(AT - timedelta(microseconds=1)) == "pending"
    assert travel.phase_at(AT) == "performing"
    for offset in (-100, 0, 100):
        assert travel.position_at(AT + timedelta(seconds=offset)) == (24, 29)
    with pytest.raises(FrozenInstanceError):
        travel.ms_per_step = 300  # type: ignore[misc]


@pytest.mark.parametrize("target", [Tile(3, 2), Tile(1, 2), Tile(2, 3), Tile(2, 1)])
@pytest.mark.parametrize("speed", [250, 300])
@pytest.mark.parametrize("elapsed", [0, 1, 62500, 125000, 249999])
def test_integer_interpolation_four_directions(target: Tile, speed: int, elapsed: int) -> None:
    travel = Travel(compress((Tile(2, 2), target)), AT, speed)
    before = travel.position_at(AT - timedelta(seconds=1))
    assert before == tile_to_feet(Tile(2, 2))
    now = AT + timedelta(microseconds=elapsed)
    pixels = travel.position_at(now)
    ax, ay = before
    bx, by = tile_to_feet(target)
    assert pixels == (
        (ax * speed * 1000 + (bx - ax) * elapsed) // (speed * 1000),
        (ay * speed * 1000 + (by - ay) * elapsed) // (speed * 1000),
    )
    assert all(type(value) is int for value in pixels)
    assert travel.phase_at(now) == "walking"
    assert travel.phase_at(travel.arrives_at) == "performing"
    assert travel.position_at(travel.arrives_at + timedelta(days=1)) == (bx, by)


@pytest.mark.parametrize("speed", [0, -1, True, 1.5])
def test_bad_speed(speed: int) -> None:
    with pytest.raises(ValueError):
        Travel(compress((Tile(1, 1),)), AT, speed)


def test_naive_time_rejected() -> None:
    with pytest.raises(ValueError):
        Travel(compress((Tile(1, 1),)), AT.replace(tzinfo=None))
    travel = Travel(compress((Tile(1, 1),)), AT)
    with pytest.raises(ValueError):
        travel.position_at(AT.replace(tzinfo=None))


@pytest.fixture
def lane(house: tuple[Walkability, tuple[Tile, ...], Oracle]) -> Walkability:
    return synthetic(house, tuple(Tile(x, 3) for x in range(1, 11)))


@pytest.mark.parametrize("target", [Tile(1, 3), Tile(10, 3), Tile(4, 3)])
@pytest.mark.parametrize("elapsed", [500000, 500001, 625000, 687500, 1749999, 1750000, 2000000])
def test_mid_route_replanning(lane: Walkability, target: Tile, elapsed: int) -> None:
    old_route = find_route(lane, Tile(1, 3), Tile(8, 3)).route
    assert old_route is not None
    old = Travel(old_route, AT)
    now = AT + timedelta(microseconds=elapsed)
    replacement = reroute(lane, old, target, now)
    assert replacement.error is None and replacement.travel is not None
    new = replacement.travel
    assert new.departed_at == now
    assert new.position_at(now) == old.position_at(now)
    assert new.position_at(new.arrives_at) == tile_to_feet(target)
    assert new.activity_started_at == new.arrives_at
    assert set(new.route.tiles()) <= set(lane.walkable)
    assert reroute(lane, old, target, now) == replacement
    # Straight lane: duration is exact physical distance, even when reversing mid-tile.
    current = old.current_at(now)
    if isinstance(current, Tile):
        expected_us = abs(current.tx - target.tx) * old.step_us
    else:
        current_numerator = (
            current.a.tx * old.step_us + (current.b.tx - current.a.tx) * current.progress_us
        )
        expected_us = abs(current_numerator - target.tx * old.step_us)
    assert new.duration_us == expected_us
    if new.entry is not None:
        assert new.position_at(now + timedelta(microseconds=new.entry.duration_us)) == tile_to_feet(
            new.route.origin
        )


def test_repeated_mid_entry_rerouting(lane: Walkability) -> None:
    path = find_route(lane, Tile(1, 3), Tile(8, 3)).route
    assert path is not None
    old = Travel(path, AT)
    now = AT + timedelta(microseconds=687500)
    first = reroute(lane, old, Tile(1, 3), now).travel
    assert first is not None and first.entry is not None
    later = now + timedelta(microseconds=12345)
    second = reroute(lane, first, Tile(10, 3), later).travel
    assert second is not None
    assert second.position_at(later) == first.position_at(later)
    assert second.position_at(second.arrives_at) == tile_to_feet(Tile(10, 3))


def test_failed_replan_no_teleport_or_recovery(lane: Walkability) -> None:
    path = find_route(lane, Tile(1, 3), Tile(8, 3)).route
    assert path is not None
    old = Travel(path, AT)
    now = AT + timedelta(microseconds=625000)
    before = old.position_at(now)
    failed = reroute(lane, old, Tile(1, 20), now)
    assert failed.travel is None and failed.error == "no_destination"
    mutated = replace(lane, walkable=tuple(tile for tile in lane.walkable if tile != Tile(4, 3)))
    assert reroute(mutated, old, Tile(1, 3), now).reason == "invalid_current_edge"
    assert old.position_at(now) == before
    with pytest.raises(ValueError, match="departure"):
        reroute(lane, old, Tile(1, 3), AT - timedelta(microseconds=1))


@pytest.mark.parametrize("progress,step", [(0, 250000), (250000, 250000), (-1, 250000), (1, 0)])
def test_bad_partial_start(progress: int, step: int) -> None:
    with pytest.raises(ValueError):
        EdgeStart(Tile(1, 3), Tile(2, 3), progress, step)


def test_bad_entry_join() -> None:
    start = EdgeStart(Tile(1, 3), Tile(2, 3), 100, 250000)
    with pytest.raises(ValueError):
        Entry(start, Tile(3, 3))
    with pytest.raises(ValueError):
        Travel(compress((Tile(3, 3),)), AT, entry=Entry(start, Tile(2, 3)))


def test_tuning_repeatability() -> None:
    first, digest = report()
    second, repeated = report()
    assert first == second and digest == repeated
    assert digest == "722a4e5359852fa4c049a985210e6a8f07a663df86bdf6c4a0a8218e8c51c936"
    assert all(run.differences == 0 for run in first)
    assert {run.total_turns for run in first if run.turn_penalty == 0} == {166}
    assert {run.total_turns for run in first if run.turn_penalty > 0} == {130}


def test_redundant_waypoints_rejected() -> None:
    with pytest.raises(ValueError, match="compressed"):
        Route((Waypoint(1, 1, 0), Waypoint(2, 1, 1), Waypoint(3, 1, 2)))


@pytest.mark.parametrize(
    "tx,ty,steps", [(-1, 0, 0), (44, 0, 0), (0, 26, 0), (0, 0, -1), (True, 0, 0), (0, 0, True)]
)
def test_invalid_waypoint(tx: int, ty: int, steps: int) -> None:
    with pytest.raises(ValueError):
        Waypoint(tx, ty, steps)


@pytest.mark.parametrize("heading", [-1, 5, True])
def test_bad_initial_heading(
    house: tuple[Walkability, tuple[Tile, ...], Oracle], heading: int
) -> None:
    with pytest.raises(ValueError):
        find_route(house[0], Tile(21, 15), Tile(21, 15), initial_heading=heading)


def test_replan_unreachable_existing_target(lane: Walkability) -> None:
    path = find_route(lane, Tile(1, 3), Tile(8, 3)).route
    assert path is not None
    disconnected = replace(lane, walkable=(*lane.walkable, Tile(20, 20)))
    result = reroute(disconnected, Travel(path, AT), Tile(20, 20), AT + timedelta(microseconds=100))
    assert result.travel is None and result.error == "no_destination"
    assert result.reason == "unreachable_or_invalid_target"


def test_mid_corner_replan(house: tuple[Walkability, tuple[Tile, ...], Oracle]) -> None:
    mask = synthetic(house, tuple(Tile(x, y) for y in range(1, 7) for x in range(1, 7)))
    path = find_route(mask, Tile(2, 2), Tile(5, 5)).route
    assert path is not None
    old = Travel(path, AT)
    now = AT + timedelta(microseconds=875000)
    new = reroute(mask, old, Tile(2, 5), now).travel
    assert new is not None and new.entry is not None
    assert new.position_at(now) == old.position_at(now)
    assert set(new.route.tiles()) <= set(mask.walkable)
    assert new.position_at(new.arrives_at) == tile_to_feet(Tile(2, 5))


def test_wrong_domain_inputs_explicit() -> None:
    with pytest.raises(ValueError, match="Route"):
        Travel(None, AT)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Tiles"):
        EdgeStart(None, Tile(1, 1), 1, 2)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="EdgeStart"):
        Entry(None, Tile(1, 1))  # type: ignore[arg-type]
