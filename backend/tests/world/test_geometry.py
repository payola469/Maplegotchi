"""Independent synthetic S1/S2 cases; no initial-house fixture or door data."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Any

import pytest

from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.geometry import TileKind, derive_structure
from maplegotchi.core.world.model import Rect, Region, RegionKind, RegionStatus
from maplegotchi.core.world.validation import validate_regions


def region(name: str, x: int, y: int, w: int, h: int) -> Region:
    return Region(name, RegionKind.HALL, Rect(x, y, w, h), RegionStatus.OPEN)


def vertical() -> tuple[Region, ...]:
    return (region("north", 1, 3, 42, 7), region("south", 1, 13, 42, 12))


def horizontal() -> tuple[Region, ...]:
    # IDs intentionally oppose geometric ordering.
    return (region("z_west", 1, 3, 20, 22), region("a_east", 22, 3, 21, 22))


def test_single_floor_independent_exact_partition() -> None:
    structure = derive_structure((region("one", 1, 3, 42, 22),))
    expected = {
        TileKind.NORTH_BAND: {(x, y) for y in range(3) for x in range(44)},
        TileKind.SIDE_WALL: {(x, y) for y in range(3, 25) for x in (0, 43)},
        TileKind.SOUTH_CUTAWAY: {(x, 25) for x in range(44)},
        TileKind.FLOOR: {(x, y) for y in range(3, 25) for x in range(1, 43)},
    }
    assert len(structure.cells) == 1144
    for kind, coordinates in expected.items():
        assert {(c.tile.tx, c.tile.ty) for c in structure.cells if c.kind is kind} == coordinates
    assert all(c.region_id == "one" for c in structure.cells)
    assert tuple((c.tile.tx, c.tile.ty) for c in structure.cells) == tuple(
        (x, y) for y in range(26) for x in range(44)
    )


@pytest.mark.parametrize(
    "x,y,kind,owner",
    [
        (0, 0, TileKind.NORTH_BAND, "north"),
        (43, 2, TileKind.NORTH_BAND, "north"),
        (1, 3, TileKind.FLOOR, "north"),
        (42, 9, TileKind.FLOOR, "north"),
        (0, 9, TileKind.SIDE_WALL, "north"),
        (1, 10, TileKind.NORTH_BAND, "south"),
        (43, 12, TileKind.NORTH_BAND, "south"),
        (1, 13, TileKind.FLOOR, "south"),
        (43, 24, TileKind.SIDE_WALL, "south"),
        (0, 25, TileKind.SOUTH_CUTAWAY, "south"),
        (43, 25, TileKind.SOUTH_CUTAWAY, "south"),
    ],
)
def test_band_bounds_and_southern_ownership(x: int, y: int, kind: TileKind, owner: str) -> None:
    cell = derive_structure(vertical()).cell_at(Tile(x, y))
    assert (cell.kind, cell.region_id) == (kind, owner)


def test_shared_column_corners_are_deduplicated_and_owned_westward() -> None:
    structure = derive_structure(horizontal())
    assert len({c.tile for c in structure.cells}) == 1144
    for y in range(26):
        cell = structure.cell_at(Tile(21, y))
        assert cell.region_id == "z_west"
        expected = (
            TileKind.NORTH_BAND
            if y < 3
            else TileKind.SOUTH_CUTAWAY
            if y == 25
            else TileKind.SIDE_WALL
        )
        assert cell.kind is expected
        assert structure.cell_at(Tile(0, y)).region_id == "z_west"
        assert structure.cell_at(Tile(43, y)).region_id == "a_east"
    assert structure.cell_at(Tile(20, 3)).kind is TileKind.FLOOR
    assert structure.cell_at(Tile(22, 3)).kind is TileKind.FLOOR


def test_no_interior_cutaway_and_closed_geometry_remains_present() -> None:
    rooms = vertical()
    rooms = (rooms[0], replace(rooms[1], status=RegionStatus.CLOSED))
    structure = derive_structure(rooms)
    assert {c.tile.ty for c in structure.cells if c.kind is TileKind.SOUTH_CUTAWAY} == {25}
    assert structure.cell_at(Tile(2, 13)).kind is TileKind.FLOOR
    assert {c.tile.ty for c in structure.cells if c.kind is TileKind.NORTH_BAND} == {
        0,
        1,
        2,
        10,
        11,
        12,
    }


def test_derivation_is_immutable_and_input_order_independent() -> None:
    rooms = horizontal()
    original = tuple(rooms)
    first = derive_structure(rooms)
    assert first == derive_structure(tuple(reversed(rooms))) == derive_structure(rooms)
    assert rooms == original
    assert hash(first) == hash(derive_structure(rooms))
    with pytest.raises(FrozenInstanceError):
        first.cells = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        first.cells[0].region_id = "other"  # type: ignore[misc]


@pytest.mark.parametrize("width,height", [(43, 26), (44, 25), (45, 26), (44.0, 26), (True, 26)])
def test_s1_grid_rejected(width: Any, height: Any) -> None:
    with pytest.raises(ValueError, match="S1: grid"):
        derive_structure(vertical(), grid_width=width, grid_height=height)


@pytest.mark.parametrize(
    "rooms,message",
    [
        ((), "S1: regions"),
        ((None,), "S1: expected Region"),
        ((region("same", 1, 3, 20, 22), region("same", 22, 3, 21, 22)), "S1: duplicate"),
        ((region("a", 1, 3, 22, 22), region("b", 22, 3, 21, 22)), "S1: floor overlap"),
    ],
)
def test_s1_invalid_region_collections(rooms: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        derive_structure(rooms)


@pytest.mark.parametrize(
    "rooms,message",
    [
        # North-band extent must be three rows, never clipped to two.
        ((region("two_rows", 1, 2, 42, 23),), "S2: .*outside grid"),
        # Four rows of margin leaves a missing exterior-band row.
        ((region("four_rows", 1, 4, 42, 21),), "S2: uncovered"),
        ((region("no_west", 0, 3, 43, 22),), "S2: .*outside grid"),
        ((region("no_east", 1, 3, 43, 22),), "S2: .*outside grid"),
        ((region("no_south", 1, 3, 42, 23),), "S2: .*outside grid"),
        ((region("interior_cutaway", 1, 3, 42, 21),), "S2: south cutaway"),
        ((region("gap", 2, 3, 41, 22),), "S2: uncovered"),
        # Floors do not overlap, but a side wall would occupy another floor.
        ((region("a", 1, 3, 21, 22), region("b", 22, 3, 21, 22)), "S2: conflicting"),
        # Only two rows between tiers: derived band intersects the upper floor.
        ((region("a", 1, 3, 42, 7), region("b", 1, 12, 42, 13)), "S2: conflicting"),
        # Four rows between tiers: the missing row is not an interior cutaway.
        ((region("a", 1, 3, 42, 7), region("b", 1, 14, 42, 11)), "S2: uncovered"),
        # A shifted exterior tier leaves an uncovered row before its band.
        ((region("a", 1, 3, 20, 22), region("b", 22, 4, 21, 21)), "S2: uncovered"),
    ],
)
def test_s2_invalid_structural_arrangements(rooms: tuple[Region, ...], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        derive_structure(rooms)


def test_s1_validation_canonical_order_preserves_values() -> None:
    rooms = horizontal()
    validated = validate_regions(rooms)
    assert validated == tuple(reversed(rooms))
    assert validated[0] is rooms[1]


def test_three_tiers_with_different_shared_columns() -> None:
    rooms = (
        region("nw", 1, 3, 20, 5),
        region("ne", 22, 3, 21, 5),
        region("middle", 1, 11, 42, 4),
        region("sw", 1, 18, 12, 7),
        region("se", 14, 18, 29, 7),
    )
    structure = derive_structure(rooms)
    # Independently classify every cell in this synthetic, non-T1 layout.
    for y in range(26):
        for x in range(44):
            if y < 8:
                owner = "nw" if x <= 21 else "ne"
                kind = (
                    TileKind.NORTH_BAND
                    if y < 3
                    else (TileKind.SIDE_WALL if x in (0, 21, 43) else TileKind.FLOOR)
                )
            elif y < 15:
                owner = "middle"
                kind = (
                    TileKind.NORTH_BAND
                    if y < 11
                    else (TileKind.SIDE_WALL if x in (0, 43) else TileKind.FLOOR)
                )
            else:
                owner = "sw" if x <= 13 else "se"
                kind = (
                    TileKind.NORTH_BAND
                    if y < 18
                    else (
                        TileKind.SOUTH_CUTAWAY
                        if y == 25
                        else (TileKind.SIDE_WALL if x in (0, 13, 43) else TileKind.FLOOR)
                    )
                )
            cell = structure.cell_at(Tile(x, y))
            assert (cell.kind, cell.region_id) == (kind, owner)
    assert structure == derive_structure(tuple(reversed(rooms)))


def test_failure_diagnostic_is_input_order_independent() -> None:
    rooms = (region("a", 1, 3, 22, 22), region("b", 22, 3, 21, 22))
    messages = []
    for values in (rooms, tuple(reversed(rooms))):
        with pytest.raises(ValueError) as error:
            derive_structure(values)
        messages.append(str(error.value))
    assert messages[0] == messages[1]
    assert "S1" in messages[0] and "Tile(tx=22, ty=3)" in messages[0]
