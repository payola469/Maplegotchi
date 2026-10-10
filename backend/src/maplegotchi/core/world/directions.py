"""Canonical direction vocabulary and pure legacy adapters (ADR-0035 §5)."""

from __future__ import annotations

from enum import StrEnum

from maplegotchi.core.room import Facing


class CharacterDirection(StrEnum):
    """Animation row order is down, left, right, up."""

    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"


class ObjectOrientation(StrEnum):
    """Catalog orientation order is south, east, west, north."""

    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NORTH = "north"


# Tuples keep the adapters immutable and independent of enum declaration order.
_CHARACTER_ORIENTATION = (
    (CharacterDirection.DOWN, ObjectOrientation.SOUTH),
    (CharacterDirection.LEFT, ObjectOrientation.WEST),
    (CharacterDirection.RIGHT, ObjectOrientation.EAST),
    (CharacterDirection.UP, ObjectOrientation.NORTH),
)
_CHARACTER_LEGACY = (
    (CharacterDirection.DOWN, Facing.FRONT),
    (CharacterDirection.LEFT, Facing.LEFT),
    (CharacterDirection.RIGHT, Facing.RIGHT),
    (CharacterDirection.UP, Facing.BACK),
)


def character_to_orientation(direction: CharacterDirection) -> ObjectOrientation:
    if isinstance(direction, CharacterDirection):
        for character, orientation in _CHARACTER_ORIENTATION:
            if direction is character:
                return orientation
    raise ValueError("expected CharacterDirection")


def orientation_to_character(orientation: ObjectOrientation) -> CharacterDirection:
    if isinstance(orientation, ObjectOrientation):
        for character, candidate in _CHARACTER_ORIENTATION:
            if orientation is candidate:
                return character
    raise ValueError("expected ObjectOrientation")


def from_legacy_facing(facing: Facing) -> CharacterDirection:
    if isinstance(facing, Facing):
        for character, legacy in _CHARACTER_LEGACY:
            if facing is legacy:
                return character
    raise ValueError("expected legacy Facing")


def to_legacy_facing(direction: CharacterDirection) -> Facing:
    if isinstance(direction, CharacterDirection):
        for character, legacy in _CHARACTER_LEGACY:
            if direction is character:
                return legacy
    raise ValueError("expected CharacterDirection")
