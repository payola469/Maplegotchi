"""Independent §K counts, dynamic K4 prevention and emergency recovery acceptance."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from maplegotchi.core.world.catalog import CatalogLayout, build_catalog_layout
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.layout import WorldLayout
from maplegotchi.core.world.model import DoorState, RegionStatus
from maplegotchi.core.world.recovery import Position, RelocationReason, recover
from maplegotchi.core.world.walkability import (
    Walkability,
    cells,
    components,
    derive_walkability,
    neighbors,
    validate_safe_layout,
)
from maplegotchi.runtime.world_catalog import load_initial_catalog
from maplegotchi.runtime.world_layout import load_initial_house


@pytest.fixture(scope="module")
def world() -> WorldLayout:
    return load_initial_house()


@pytest.fixture(scope="module")
def catalog(world: WorldLayout) -> CatalogLayout:
    return load_initial_catalog(world)


def add_blocks(catalog: CatalogLayout, *tiles: Tile) -> CatalogLayout:
    """Inject candidate masks at the derived collision boundary, not into resources."""
    return replace(catalog, blocking_tiles=catalog.blocking_tiles + tiles)


def test_initial_counts_and_connectivity(world: WorldLayout, catalog: CatalogLayout) -> None:
    mask = validate_safe_layout(world, catalog, Tile(21, 15))
    assert len(mask.walkable) == 431
    expected = {
        "bedroom": 49,
        "living_room": 64,
        "library": 63,
        "work_studio": 63,
        "central_hall": 168,
    }
    for room in world.regions:
        if room.id in expected:
            assert sum(room.floor.contains(tile) for tile in mask.walkable) == expected[room.id]
    assert (
        sum(
            tile in mask.walkable
            for passage in world.topology.passages
            if passage.state is DoorState.OPEN
            for tile in passage.cells
        )
        == 24
    )
    closed = {
        tile
        for room in world.regions
        if room.status is RegionStatus.CLOSED
        for tile in cells(room.floor)
    }
    assert len(closed) == 200
    assert not closed.intersection(mask.walkable)
    assert len(mask.blocked) == 34
    assert tuple(map(len, mask.components)) == (431,)
    assert mask.safe_tile == Tile(21, 15)
    assert set(mask.required) <= set(mask.components[0])
    assert len(mask.required) == 26
    assert set(mask.blocked).isdisjoint(mask.keep_clear)
    assert set(mask.blocked).isdisjoint(mask.walkable)
    for passage in world.topology.passages:
        if passage.state is DoorState.CLOSED:
            assert set(passage.cells).isdisjoint(mask.walkable)


def test_dynamic_k4_allows_detour(world: WorldLayout, catalog: CatalogLayout) -> None:
    candidate = add_blocks(catalog, Tile(5, 6), Tile(6, 6))
    mask = validate_safe_layout(world, candidate, Tile(5, 7))
    assert len(mask.walkable) == 429
    assert len(mask.components) == 1
    assert Tile(5, 6) not in mask.keep_clear
    assert set(mask.required) <= set(mask.components[0])


def test_last_route_rejected(world: WorldLayout, catalog: CatalogLayout) -> None:
    candidate = add_blocks(catalog, *(Tile(x, 6) for x in range(1, 9)))
    with pytest.raises(ValueError, match="K4"):
        validate_safe_layout(world, candidate, Tile(5, 7))


@pytest.mark.parametrize(
    "tile",
    [
        Tile(5, 8),
        Tile(6, 9),
        Tile(5, 13),
        Tile(6, 14),
        Tile(6, 16),
        Tile(7, 20),
        Tile(21, 15),
        Tile(3, 4),
        Tile(4, 3),
    ],
)
def test_k1_k2_k3_collisions(world: WorldLayout, catalog: CatalogLayout, tile: Tile) -> None:
    with pytest.raises(ValueError, match="S10"):
        validate_safe_layout(world, add_blocks(catalog, tile))


@pytest.mark.parametrize("position", [Tile(1, 3), Tile(0, 0), Tile(1, 20), Tile(6, 18)])
def test_invalid_maple_rejected_not_recovered(
    world: WorldLayout, catalog: CatalogLayout, position: Tile
) -> None:
    with pytest.raises(ValueError, match="S13"):
        validate_safe_layout(world, catalog, position)


def test_unreachable_approach(world: WorldLayout, catalog: CatalogLayout) -> None:
    point = catalog.points[0]
    template = replace(point.template, approach=replace(point.template.approach, x=1, y=20))
    candidate = replace(catalog, points=(replace(point, template=template), *catalog.points[1:]))
    with pytest.raises(ValueError, match="unreachable"):
        validate_safe_layout(world, candidate)


def test_open_door_to_closed_room_rejected(world: WorldLayout, catalog: CatalogLayout) -> None:
    doors = tuple(
        replace(door, state=DoorState.OPEN) if door.south_room == "future_space" else door
        for door in world.doors
    )
    with pytest.raises(ValueError, match="S5"):
        derive_walkability(replace(world, doors=doors), catalog)


def test_missing_safe_marker(world: WorldLayout, catalog: CatalogLayout) -> None:
    candidate = replace(
        catalog,
        points=tuple(point for point in catalog.points if point.instance_id != "idle.hall_center"),
    )
    with pytest.raises(ValueError, match="fallback"):
        validate_safe_layout(world, candidate)
    assert recover(derive_walkability(world, candidate), Position(-1, 0)).error == "unsafe_fallback"


def test_disconnected_pocket(world: WorldLayout, catalog: CatalogLayout) -> None:
    candidate = add_blocks(catalog, Tile(7, 5), Tile(8, 4), Tile(8, 6))
    with pytest.raises(ValueError, match="component"):
        validate_safe_layout(world, candidate)


def test_permutation_and_immutability(world: WorldLayout, catalog: CatalogLayout) -> None:
    expected = derive_walkability(world, catalog)
    changed = replace(
        world, regions=tuple(reversed(world.regions)), doors=tuple(reversed(world.doors))
    )
    shuffled = replace(
        catalog,
        instances=tuple(reversed(catalog.instances)),
        points=tuple(reversed(catalog.points)),
        slots=tuple(reversed(catalog.slots)),
        blocking_tiles=tuple(reversed(catalog.blocking_tiles)),
    )
    assert derive_walkability(changed, shuffled) == expected
    assert derive_walkability(world, catalog) == expected
    assert expected.walkable == tuple(
        sorted(expected.walkable, key=lambda tile: (tile.ty, tile.tx))
    )
    with pytest.raises(FrozenInstanceError):
        expected.walkable = ()  # type: ignore[misc]


def test_no_diagonal_connectivity() -> None:
    assert len(components((Tile(1, 1), Tile(2, 2)))) == 2
    assert neighbors(Tile(0, 0)) == (Tile(1, 0), Tile(0, 1))


@pytest.fixture(scope="module")
def mask(world: WorldLayout, catalog: CatalogLayout) -> Walkability:
    return validate_safe_layout(world, catalog)


def test_valid_position_no_event(mask: Walkability) -> None:
    result = recover(mask, Position(21, 15))
    assert result.destination == Tile(21, 15)
    assert result.event is None and result.error is None


def test_recovery_distance_and_row_then_column_tie(
    world: WorldLayout, catalog: CatalogLayout
) -> None:
    # All four adjacent cells are free: north wins, then west when north is blocked.
    candidate = add_blocks(catalog, Tile(16, 6))
    first = recover(derive_walkability(world, candidate), Position(16, 6))
    assert first.destination == Tile(16, 5)
    second = recover(derive_walkability(world, add_blocks(candidate, Tile(16, 5))), Position(16, 6))
    assert second.destination == Tile(15, 6)
    assert second.event is not None
    assert second.event.original == Position(16, 6)
    assert second.event.reason is RelocationReason.BLOCKED_SOURCE
    assert second.event.kind == "maple_relocated"
    assert second == recover(
        derive_walkability(world, add_blocks(candidate, Tile(16, 5))), Position(16, 6)
    )
    with pytest.raises(FrozenInstanceError):
        second.event.kind = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "source",
    [
        Position(-1, 0),
        Position(44, 0),
        Position(0, 26),
        Position(0, 0),
        Position(1, 20),
        Position(6, 18),
    ],
)
def test_invalid_closed_wall_outside_sources_fallback(mask: Walkability, source: Position) -> None:
    result = recover(mask, source)
    assert result.destination == Tile(21, 15)
    assert result.event is not None and result.event.reason is RelocationReason.INVALID_SOURCE
    assert result.event.original == source


def test_isolated_source_no_tunneling(mask: Walkability) -> None:
    # Interior of bed: no adjacent walkable cell. Other blocked cells cannot be crossed.
    result = recover(mask, Position(1, 3))
    assert result.destination == Tile(21, 15)
    assert result.event is not None
    assert result.event.reason is RelocationReason.NO_REACHABLE_CANDIDATE


def test_blocked_open_passage_source(world: WorldLayout, catalog: CatalogLayout) -> None:
    mask = derive_walkability(world, add_blocks(catalog, Tile(5, 11)))
    result = recover(mask, Position(5, 11))
    assert result.destination == Tile(5, 10)


def test_unsafe_fallback_explicit_failure(world: WorldLayout, catalog: CatalogLayout) -> None:
    mask = derive_walkability(world, add_blocks(catalog, Tile(21, 15)))
    result = recover(mask, Position(-1, -1))
    assert result.destination is None and result.event is None
    assert result.error == "unsafe_fallback"


@pytest.mark.parametrize("value", [True, 1.5, "1", None])
def test_source_integer_validation(value: object) -> None:
    with pytest.raises(ValueError, match="integer"):
        Position(value, 0)  # type: ignore[arg-type]


def test_real_furniture_move_allows_dynamic_detour(
    world: WorldLayout, catalog: CatalogLayout
) -> None:
    instances = tuple(
        replace(item, origin=Tile(15, 5)) if item.id == "sofa.living" else item
        for item in catalog.instances
    )
    candidate = build_catalog_layout(catalog.catalog, instances, world)
    mask = validate_safe_layout(world, candidate, Tile(16, 6))
    assert len(mask.walkable) == 431
    assert len(mask.components) == 1
    assert Tile(15, 5) in mask.blocked
    assert Tile(16, 5) in mask.blocked
    assert set(mask.required) <= set(mask.components[0])


@pytest.mark.parametrize("door_index", range(7))
@pytest.mark.parametrize("dx", [0, 1])
@pytest.mark.parametrize("dy", [-2, -1, 3, 4])
def test_every_door_clearance_including_closed(
    world: WorldLayout, catalog: CatalogLayout, door_index: int, dx: int, dy: int
) -> None:
    door = world.doors[door_index]
    protected = Tile(door.passage.x + dx, door.passage.y + dy)
    assert protected in derive_walkability(world, catalog).keep_clear
    with pytest.raises(ValueError, match="S10"):
        validate_safe_layout(world, add_blocks(catalog, protected))


def test_source_immutability() -> None:
    source = Position(-1, 0)
    with pytest.raises(FrozenInstanceError):
        source.tx = 2  # type: ignore[misc]
