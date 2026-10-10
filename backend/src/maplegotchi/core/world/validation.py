"""S1 region validation, independent of layout loading and door topology."""

from __future__ import annotations

from maplegotchi.core.world.coordinates import GRID_HEIGHT, GRID_WIDTH, Tile
from maplegotchi.core.world.model import Region


def validate_regions(
    regions: tuple[Region, ...],
    *,
    grid_width: int = GRID_WIDTH,
    grid_height: int = GRID_HEIGHT,
) -> tuple[Region, ...]:
    """Validate S1 and return a canonical order without changing the input."""
    if (
        type(grid_width) is not int
        or type(grid_height) is not int
        or (grid_width, grid_height) != (GRID_WIDTH, GRID_HEIGHT)
    ):
        raise ValueError("S1: grid must be 44 x 26")
    if not regions:
        raise ValueError("S1: regions must not be empty")
    if any(not isinstance(region, Region) for region in regions):
        raise ValueError("S1: expected Region values")
    ordered = tuple(sorted(regions, key=lambda region: region.id))
    seen_ids: set[str] = set()
    floors: dict[Tile, str] = {}
    for region in ordered:
        if region.id in seen_ids:
            raise ValueError(f"S1: duplicate region id {region.id}")
        seen_ids.add(region.id)
        rect = region.floor
        # Rect already enforces integer, positive and grid-contained bounds.
        for y in range(rect.y, rect.y + rect.h):
            for x in range(rect.x, rect.x + rect.w):
                tile = Tile(x, y)
                if tile in floors:
                    raise ValueError(f"S1: floor overlap at {tile}: {floors[tile]}, {region.id}")
                floors[tile] = region.id
    return ordered
