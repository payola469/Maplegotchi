"""Integer grid coordinates and the shared feet offset (ADR-0035 / ADR-0041)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

T: Final = 16
GRID_WIDTH: Final = 44
GRID_HEIGHT: Final = 26
FEET_IN_TILE: Final[tuple[int, int]] = (T // 2, (13 * T) // 16)


def require_integer(value: int, label: str) -> None:
    """Reject coercion, including bool (an int subclass)."""
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer")


@dataclass(frozen=True, slots=True)
class Tile:
    """One cell in the canonical grid; north-west origin, east/south positive."""

    tx: int
    ty: int

    def __post_init__(self) -> None:
        require_integer(self.tx, "tx")
        require_integer(self.ty, "ty")
        if not (0 <= self.tx < GRID_WIDTH and 0 <= self.ty < GRID_HEIGHT):
            raise ValueError("tile outside grid")


def tile_to_feet(tile: Tile) -> tuple[int, int]:
    """Derive world pixels without storing pixel position or rounding a tile."""
    return tile.tx * T + FEET_IN_TILE[0], tile.ty * T + FEET_IN_TILE[1]
