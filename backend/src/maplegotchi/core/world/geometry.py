"""Derived L8 structure before door carving; no walkability or lighting zones."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from maplegotchi.core.world.coordinates import GRID_HEIGHT, GRID_WIDTH, Tile
from maplegotchi.core.world.model import Region
from maplegotchi.core.world.validation import validate_regions

NORTH_BAND_ROWS: Final = 3


class TileKind(StrEnum):
    FLOOR = "floor"
    NORTH_BAND = "north_band"
    SIDE_WALL = "side_wall"
    SOUTH_CUTAWAY = "south_cutaway"


@dataclass(frozen=True, slots=True)
class StructuralCell:
    """One physical cell and its owning region, not an access permission."""

    tile: Tile
    kind: TileKind
    region_id: str


@dataclass(frozen=True, slots=True)
class Structure:
    """Validated row-major partition, before any door openings are carved."""

    cells: tuple[StructuralCell, ...]

    def cell_at(self, tile: Tile) -> StructuralCell:
        return self.cells[tile.ty * GRID_WIDTH + tile.tx]


def derive_structure(
    regions: tuple[Region, ...],
    *,
    grid_width: int = GRID_WIDTH,
    grid_height: int = GRID_HEIGHT,
) -> Structure:
    """Enforce S1/S2 and derive structure solely from immutable region floors.

    Shared band corners and side columns are one physical cell. Band ownership
    follows the southern floor; shared horizontal corner ownership is westward.
    The cutaway occurs only beneath the lowest tier, across the whole house.
    """
    ordered = validate_regions(regions, grid_width=grid_width, grid_height=grid_height)
    lowest_edge = max(region.floor.y + region.floor.h for region in ordered)
    candidates: dict[Tile, list[tuple[TileKind, Region]]] = {}

    def add(x: int, y: int, kind: TileKind, region: Region) -> None:
        if not (0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT):
            raise ValueError(f"S2: {region.id} {kind.value} outside grid at ({x}, {y})")
        candidates.setdefault(Tile(x, y), []).append((kind, region))

    for region in ordered:
        rect = region.floor
        for y in range(rect.y, rect.y + rect.h):
            for x in range(rect.x, rect.x + rect.w):
                add(x, y, TileKind.FLOOR, region)
            for x in (rect.x - 1, rect.x + rect.w):
                add(x, y, TileKind.SIDE_WALL, region)
        for y in range(rect.y - NORTH_BAND_ROWS, rect.y):
            for x in range(rect.x - 1, rect.x + rect.w + 1):
                add(x, y, TileKind.NORTH_BAND, region)
        if rect.y + rect.h == lowest_edge:
            for x in range(rect.x - 1, rect.x + rect.w + 1):
                add(x, lowest_edge, TileKind.SOUTH_CUTAWAY, region)

    cells: list[StructuralCell] = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            tile = Tile(x, y)
            claims = candidates.get(tile, [])
            if not claims:
                raise ValueError(f"S2: uncovered tile {tile}")
            kinds = {kind for kind, _ in claims}
            if len(kinds) != 1:
                raise ValueError(f"S2: conflicting floor/structure or wall kinds at {tile}")
            kind = claims[0][0]
            if kind is TileKind.NORTH_BAND and len({r.floor.y for _, r in claims}) != 1:
                raise ValueError(f"S2: misaligned shared north bands at {tile}")
            if kind is TileKind.SOUTH_CUTAWAY and y != GRID_HEIGHT - 1:
                raise ValueError(f"S2: south cutaway must be exterior at {tile}")
            # West room owns shared side/corner cells; at the exterior west edge
            # only the room east of the cell claims it. IDs never decide geometry.
            owner = min((r for _, r in claims), key=lambda r: (r.floor.x, r.id))
            cells.append(StructuralCell(tile, kind, owner.id))
    return Structure(tuple(cells))
