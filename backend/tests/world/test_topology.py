"""Generic synthetic doorway tests, independent of approved initial-house data."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from itertools import permutations
from typing import Any

import pytest

from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.geometry import TileKind, derive_structure
from maplegotchi.core.world.model import Door, DoorState, Rect, Region, RegionKind, RegionStatus
from maplegotchi.core.world.topology import RoomNode, derive_topology


def region(name: str, x: int, y: int, w: int, h: int) -> Region:
    return Region(name, RegionKind.HALL, Rect(x, y, w, h), RegionStatus.OPEN)


def rooms() -> tuple[Region, ...]:
    return (region("north", 1, 3, 42, 7), region("south", 1, 13, 42, 12))


def door(**changes: Any) -> Door:
    value = Door("link", "north", "south", Rect(5, 10, 2, 3), DoorState.OPEN)
    return replace(value, **changes)


@pytest.mark.parametrize("state", list(DoorState))
def test_passage_cells_state_and_southern_ownership(state: DoorState) -> None:
    values = rooms()
    if state is DoorState.CLOSED:
        values = (values[0], replace(values[1], status=RegionStatus.CLOSED))
    structure = derive_structure(values)
    result = derive_topology(values, (door(state=state),))
    passage = result.passages[0]
    assert passage.region_id == "south" and passage.state is state
    assert passage.cells == tuple(Tile(x, y) for y in (10, 11, 12) for x in (5, 6))
    for tile in passage.cells:
        assert result.passage_at(tile) is passage
        assert structure.cell_at(tile).kind is TileKind.NORTH_BAND
    assert result.passage_at(Tile(5, 9)) is None
    assert result.passage_at(Tile(5, 13)) is None
    assert result.passage_at(Tile(4, 10)) is None
    assert result.passage_at(Tile(7, 10)) is None
    expected = ("south",) if state is DoorState.OPEN else ()
    assert result.graph[0] == RoomNode("north", expected)


@pytest.mark.parametrize("x", [1, 41])
def test_two_column_opening_at_floor_edges_is_valid(x: int) -> None:
    result = derive_topology(rooms(), (door(passage=Rect(x, 10, 2, 3)),))
    assert len(result.passages[0].cells) == 6
    assert result.graph == (RoomNode("north", ("south",)), RoomNode("south", ("north",)))


@pytest.mark.parametrize(
    "changes",
    [
        {"id": ""},
        {"id": " "},
        {"id": None},
        {"north_room": ""},
        {"south_room": None},
        {"south_room": "north"},
        {"state": "open"},
        {"state": "unknown"},
        {"state": RegionStatus.OPEN},
        {"passage": (5, 10, 2, 3)},
        {"passage": Rect(5, 10, 1, 3)},
        {"passage": Rect(5, 10, 3, 3)},
        {"passage": Rect(5, 10, 2, 2)},
        {"passage": Rect(5, 10, 2, 4)},
        {"passage": Rect(5, 10, 3, 2)},
    ],
)
def test_invalid_door_value(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="S3"):
        door(**changes)


@pytest.mark.parametrize(
    "values", [(-1, 10, 2, 3), (43, 10, 2, 3), (5, 24, 2, 3), (5.0, 10, 2, 3), (True, 10, 2, 3)]
)
def test_invalid_passage_coordinates(values: tuple[Any, Any, Any, Any]) -> None:
    with pytest.raises(ValueError):
        door(passage=Rect(*values))


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"north_room": "missing"}, "missing room"),
        ({"south_room": "missing"}, "missing room"),
        ({"north_room": "south", "south_room": "north"}, "not north/south adjacent"),
        ({"passage": Rect(5, 0, 2, 3)}, "not north/south adjacent"),
        ({"passage": Rect(5, 9, 2, 3)}, "not north/south adjacent"),
        ({"passage": Rect(5, 11, 2, 3)}, "not north/south adjacent"),
        ({"passage": Rect(5, 22, 2, 3)}, "not north/south adjacent"),
        ({"passage": Rect(0, 10, 2, 3)}, "lacks floor"),
        ({"passage": Rect(42, 10, 2, 3)}, "lacks floor"),
        ({"passage": Rect(0, 5, 2, 3)}, "not north/south adjacent"),
    ],
)
def test_invalid_door_placement(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=f"S3: .*{message}"):
        derive_topology(rooms(), (door(**changes),))


@pytest.mark.parametrize("offset", [0, 1])
@pytest.mark.parametrize("state", list(DoorState))
def test_overlapping_passages_rejected_in_both_states(offset: int, state: DoorState) -> None:
    other = door(id="other", passage=Rect(5 + offset, 10, 2, 3), state=state)
    with pytest.raises(ValueError, match=r"S3: .*overlap"):
        derive_topology(rooms(), (door(), other))


def test_duplicate_ids_rejected_even_with_disjoint_passages() -> None:
    with pytest.raises(ValueError, match="S3: duplicate door id"):
        derive_topology(rooms(), (door(), door(passage=Rect(10, 10, 2, 3))))


def test_non_door_is_rejected() -> None:
    invalid: Any = None
    with pytest.raises(ValueError, match="S3: expected Door"):
        derive_topology(rooms(), (invalid,))


def test_nonadjacent_vertical_rooms_cannot_be_linked() -> None:
    values = (
        region("north", 1, 3, 42, 5),
        region("middle", 1, 11, 42, 4),
        region("south", 1, 18, 42, 7),
    )
    with pytest.raises(ValueError, match=r"S3: .*not north/south adjacent"):
        derive_topology(values, (door(passage=Rect(5, 8, 2, 3)),))


def test_door_cannot_straddle_two_northern_rooms() -> None:
    values = (
        region("west", 1, 3, 20, 7),
        region("east", 22, 3, 21, 7),
        region("south", 1, 13, 42, 12),
    )
    with pytest.raises(ValueError, match=r"S3: .*lacks floor"):
        derive_topology(values, (door(north_room="west", passage=Rect(20, 10, 2, 3)),))


@pytest.mark.parametrize("doors", [(), (door(state=DoorState.CLOSED),)])
def test_s4_open_rooms_disconnected_without_open_door(doors: tuple[Door, ...]) -> None:
    with pytest.raises(ValueError, match="S4: disconnected open rooms: south"):
        derive_topology(rooms(), doors)


@pytest.mark.parametrize("closed_count", [1, 2])
def test_s4_closed_rooms_are_exempt(closed_count: int) -> None:
    values = tuple(
        replace(value, status=RegionStatus.CLOSED) if i >= 2 - closed_count else value
        for i, value in enumerate(rooms())
    )
    result = derive_topology(values, ())
    assert result.graph == (RoomNode("north", ()), RoomNode("south", ()))


def test_closed_room_cannot_bridge_open_rooms() -> None:
    values = (
        region("north", 1, 3, 42, 5),
        replace(region("middle", 1, 11, 42, 4), status=RegionStatus.CLOSED),
        region("south", 1, 18, 42, 7),
    )
    doors = (
        door(south_room="middle", passage=Rect(5, 8, 2, 3)),
        door(id="lower", north_room="middle", passage=Rect(5, 15, 2, 3)),
    )
    with pytest.raises(ValueError, match="S4: disconnected"):
        derive_topology(values, doors)


def test_graph_order_undirected_edges_and_deep_immutability() -> None:
    values = (
        region("z_west", 1, 3, 20, 7),
        region("a_east", 22, 3, 21, 7),
        region("middle", 1, 13, 42, 12),
    )
    doors = (
        door(id="west", north_room="z_west", south_room="middle"),
        door(id="east", north_room="a_east", south_room="middle", passage=Rect(30, 10, 2, 3)),
    )
    first = derive_topology(values, doors)
    assert first.graph == (
        RoomNode("a_east", ("middle",)),
        RoomNode("middle", ("a_east", "z_west")),
        RoomNode("z_west", ("middle",)),
    )
    assert tuple(p.door_id for p in first.passages) == ("east", "west")
    for room_order in permutations(values):
        for door_order in permutations(doors):
            assert derive_topology(room_order, door_order) == first
    assert hash(first) == hash(derive_topology(values, doors))
    for value, field, replacement in (
        (doors[0], "state", DoorState.CLOSED),
        (doors[0].passage, "x", 0),
        (first, "graph", ()),
        (first.graph[0], "neighbors", ()),
        (first.passages[0], "cells", ()),
        (first.passages[0].cells[0], "tx", 0),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(value, field, replacement)


def test_parallel_valid_openings_do_not_duplicate_graph_edges() -> None:
    result = derive_topology(rooms(), (door(), door(id="other", passage=Rect(10, 10, 2, 3))))
    assert len(result.passages) == 2
    assert result.graph == (RoomNode("north", ("south",)), RoomNode("south", ("north",)))


@pytest.mark.parametrize("state", list(DoorState))
def test_s4_transitive_connection_and_closed_edge_rejection(state: DoorState) -> None:
    values = (
        region("north", 1, 3, 42, 5),
        region("middle", 1, 11, 42, 4),
        region("south", 1, 18, 42, 7),
    )
    doors = (
        door(south_room="middle", passage=Rect(5, 8, 2, 3)),
        door(id="lower", north_room="middle", passage=Rect(5, 15, 2, 3), state=state),
    )
    if state is DoorState.CLOSED:
        with pytest.raises(ValueError, match="S4: disconnected"):
            derive_topology(values, doors)
    else:
        result = derive_topology(values, doors)
        assert result.graph == (
            RoomNode("middle", ("north", "south")),
            RoomNode("north", ("middle",)),
            RoomNode("south", ("middle",)),
        )


def test_s3_diagnostic_is_input_order_independent() -> None:
    doors = (door(), door(id="other", passage=Rect(6, 10, 2, 3)))
    messages = []
    for values in (doors, tuple(reversed(doors))):
        with pytest.raises(ValueError, match="S3") as error:
            derive_topology(rooms(), values)
        messages.append(str(error.value))
    assert messages[0] == messages[1]
    assert "overlap at Tile(tx=6, ty=10)" in messages[0]
