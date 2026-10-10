"""Checkpoint 1 values only: no walls, doors, layout loading or live state."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Any

import pytest

from maplegotchi.core.room import Facing
from maplegotchi.core.world.coordinates import (
    FEET_IN_TILE,
    GRID_HEIGHT,
    GRID_WIDTH,
    T,
    Tile,
    tile_to_feet,
)
from maplegotchi.core.world.directions import (
    CharacterDirection,
    ObjectOrientation,
    character_to_orientation,
    from_legacy_facing,
    orientation_to_character,
    to_legacy_facing,
)
from maplegotchi.core.world.model import Rect, Region, RegionKind, RegionStatus


@pytest.mark.parametrize("tx,ty", [(0, 0), (43, 25), (0, 25), (43, 0)])
def test_tile_bounds_and_feet(tx: int, ty: int) -> None:
    tile = Tile(tx, ty)
    assert tile_to_feet(tile) == (tx * T + FEET_IN_TILE[0], ty * T + FEET_IN_TILE[1])
    assert Tile(tx, ty) == tile


@pytest.mark.parametrize(
    "tx,ty",
    [
        (-1, 0),
        (0, -1),
        (44, 0),
        (0, 26),
        (1.0, 0),
        (0, 1.0),
        (True, 0),
        (0, False),
        ("1", 0),
        (0, None),
    ],
)
def test_invalid_tile_is_rejected(tx: Any, ty: Any) -> None:
    with pytest.raises(ValueError):
        Tile(tx, ty)


@pytest.mark.parametrize("rect", [Rect(0, 0, 44, 26), Rect(43, 25, 1, 1), Rect(2, 3, 4, 5)])
def test_rect_half_open_bounds(rect: Rect) -> None:
    assert rect.area == rect.w * rect.h
    assert rect.contains(Tile(rect.x, rect.y))
    assert rect.contains(Tile(rect.x + rect.w - 1, rect.y + rect.h - 1))
    if rect.x + rect.w < GRID_WIDTH:
        assert not rect.contains(Tile(rect.x + rect.w, rect.y))
    if rect.y + rect.h < GRID_HEIGHT:
        assert not rect.contains(Tile(rect.x, rect.y + rect.h))
    if rect.x:
        assert not rect.contains(Tile(rect.x - 1, rect.y))
    if rect.y:
        assert not rect.contains(Tile(rect.x, rect.y - 1))


@pytest.mark.parametrize(
    "values",
    [
        (-1, 0, 1, 1),
        (0, -1, 1, 1),
        (0, 0, 0, 1),
        (0, 0, 1, 0),
        (0, 0, -1, 1),
        (0, 0, 1, -1),
        (43, 0, 2, 1),
        (0, 25, 1, 2),
        (44, 0, 1, 1),
        (0, 26, 1, 1),
        (0.0, 0, 1, 1),
        (0, 0.0, 1, 1),
        (0, 0, 1.0, 1),
        (0, 0, 1, 1.0),
        (True, 0, 1, 1),
        (0, False, 1, 1),
        (0, 0, True, 1),
        (0, 0, 1, False),
    ],
)
def test_invalid_rect_is_rejected(values: tuple[Any, Any, Any, Any]) -> None:
    with pytest.raises(ValueError):
        Rect(*values)


@pytest.mark.parametrize("status", list(RegionStatus))
def test_region_is_a_floor_value(status: RegionStatus) -> None:
    floor = Rect(2, 3, 4, 5)
    region = Region("synthetic", RegionKind.HALL, floor, status)
    assert region.floor is floor and region.status is status
    assert region.floor.area == 20


@pytest.mark.parametrize(
    "changes",
    [
        {"id": ""},
        {"id": " "},
        {"id": None},
        {"kind": "hall"},
        {"kind": "unknown"},
        {"floor": [0, 0, 1, 1]},
        {"status": "open"},
        {"status": "unknown"},
    ],
)
def test_invalid_region_is_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        replace(
            Region("synthetic", RegionKind.HALL, Rect(0, 0, 1, 1), RegionStatus.OPEN), **changes
        )


@pytest.mark.parametrize(
    "value,field,new",
    [
        (Tile(2, 3), "tx", 4),
        (Rect(2, 3, 4, 5), "w", 6),
        (
            Region("synthetic", RegionKind.HALL, Rect(2, 3, 4, 5), RegionStatus.OPEN),
            "status",
            RegionStatus.CLOSED,
        ),
    ],
)
def test_values_are_frozen_and_hashable(value: Any, field: str, new: Any) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(value, field, new)
    assert not hasattr(value, "__dict__")
    assert value in {value}


@pytest.mark.parametrize(
    "character,orientation,legacy",
    [
        (CharacterDirection.DOWN, ObjectOrientation.SOUTH, Facing.FRONT),
        (CharacterDirection.LEFT, ObjectOrientation.WEST, Facing.LEFT),
        (CharacterDirection.RIGHT, ObjectOrientation.EAST, Facing.RIGHT),
        (CharacterDirection.UP, ObjectOrientation.NORTH, Facing.BACK),
    ],
)
def test_direction_conversions(
    character: CharacterDirection, orientation: ObjectOrientation, legacy: Facing
) -> None:
    assert character_to_orientation(character) is orientation
    assert orientation_to_character(orientation) is character
    assert from_legacy_facing(legacy) is character
    assert to_legacy_facing(character) is legacy


def test_direction_order_and_legacy_vocabulary_are_unchanged() -> None:
    assert tuple(d.value for d in CharacterDirection) == ("down", "left", "right", "up")
    assert tuple(d.value for d in ObjectOrientation) == ("south", "east", "west", "north")
    assert tuple(d.value for d in Facing) == ("left", "right", "front", "back")


@pytest.mark.parametrize("invalid", [None, "unknown", "down", "south", "front", 1])
def test_adapters_do_not_coerce_cross_vocabularies(invalid: Any) -> None:
    for adapter in (
        character_to_orientation,
        orientation_to_character,
        from_legacy_facing,
        to_legacy_facing,
    ):
        with pytest.raises(ValueError):
            adapter(invalid)


@pytest.mark.parametrize("enum", [CharacterDirection, ObjectOrientation, RegionKind, RegionStatus])
def test_unknown_enum_value_is_rejected(enum: Any) -> None:
    with pytest.raises(ValueError):
        enum("unknown")


def test_feet_formula_and_determinism_over_entire_coordinate_domain() -> None:
    assert T == 16 and FEET_IN_TILE == (8, 13)
    assert FEET_IN_TILE == (T // 2, 13 * T // 16)
    first = tuple(tile_to_feet(Tile(x, y)) for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH))
    second = tuple(tile_to_feet(Tile(x, y)) for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH))
    assert first == second and len(first) == 1144
    assert first[0] == (8, 13) and first[-1] == (696, 413)
    assert len(set(first)) == len(first)


def test_nested_values_preserve_inputs_and_value_equality() -> None:
    floor = Rect(2, 3, 4, 5)
    region = Region("synthetic", RegionKind.HALL, floor, RegionStatus.OPEN)
    other = Region("synthetic", RegionKind.HALL, Rect(2, 3, 4, 5), RegionStatus.OPEN)
    assert other == region and hash(other) == hash(region)
    changed = replace(region, status=RegionStatus.CLOSED)
    assert changed.floor is floor and region.status is RegionStatus.OPEN
    with pytest.raises(FrozenInstanceError):
        region.floor.x = 0  # type: ignore[misc]
    assert floor == Rect(2, 3, 4, 5)
