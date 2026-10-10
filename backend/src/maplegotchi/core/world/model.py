"""Immutable rectangular floor-region values; no initial-house layout or walls."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from maplegotchi.core.world.coordinates import GRID_HEIGHT, GRID_WIDTH, Tile, require_integer


@dataclass(frozen=True, slots=True)
class Rect:
    """Grid-contained rectangle with half-open x/y ranges."""

    x: int
    y: int
    w: int
    h: int

    def __post_init__(self) -> None:
        for label, value in (("x", self.x), ("y", self.y), ("w", self.w), ("h", self.h)):
            require_integer(value, label)
        if self.w <= 0 or self.h <= 0:
            raise ValueError("rectangle extents must be positive")
        if not (0 <= self.x < self.x + self.w <= GRID_WIDTH):
            raise ValueError("rectangle x range outside grid")
        if not (0 <= self.y < self.y + self.h <= GRID_HEIGHT):
            raise ValueError("rectangle y range outside grid")

    @property
    def area(self) -> int:
        return self.w * self.h

    def contains(self, tile: Tile) -> bool:
        return self.x <= tile.tx < self.x + self.w and self.y <= tile.ty < self.y + self.h


class RegionKind(StrEnum):
    """Initial-house semantic kinds from the approved T1 vocabulary."""

    BEDROOM = "bedroom"
    LIVING = "living"
    LIBRARY = "library"
    STUDIO = "studio"
    HALL = "hall"
    FUTURE = "future"
    CREATION = "creation"
    SYSTEM = "system"


class RegionStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class Region:
    """A labelled floor rectangle; membership alone does not imply walkability."""

    id: str
    kind: RegionKind
    floor: Rect
    status: RegionStatus

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("region id must be nonempty text")
        if not isinstance(self.kind, RegionKind):
            raise ValueError("region kind must be RegionKind")
        if not isinstance(self.floor, Rect):
            raise ValueError("region floor must be Rect")
        if not isinstance(self.status, RegionStatus):
            raise ValueError("region status must be RegionStatus")


class DoorState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class Door:
    """A north-south archway rectangle; adjacency is validated against regions."""

    id: str
    north_room: str
    south_room: str
    passage: Rect
    state: DoorState

    def __post_init__(self) -> None:
        for label, value in (
            ("id", self.id),
            ("north_room", self.north_room),
            ("south_room", self.south_room),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"S3: door {label} must be nonempty text")
        if self.north_room == self.south_room:
            raise ValueError(f"S3: door {self.id} cannot link a room to itself")
        if not isinstance(self.passage, Rect):
            raise ValueError(f"S3: door {self.id} passage must be Rect")
        if (self.passage.w, self.passage.h) != (2, 3):
            raise ValueError(f"S3: door {self.id} must be 2 columns by 3 rows")
        if not isinstance(self.state, DoorState):
            raise ValueError(f"S3: door {self.id} state must be DoorState")
