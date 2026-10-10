"""Backend-owned zone partition and geometry-only mount predicates (S7/S12)."""

from __future__ import annotations

from dataclasses import dataclass

from maplegotchi.core.world.coordinates import GRID_HEIGHT, GRID_WIDTH, Tile
from maplegotchi.core.world.geometry import Structure, TileKind, derive_structure
from maplegotchi.core.world.model import Door, Rect, Region
from maplegotchi.core.world.topology import Topology, derive_topology


@dataclass(frozen=True, slots=True)
class LightingZone:
    region_id: str
    bounds: Rect

    def __post_init__(self) -> None:
        if not isinstance(self.region_id, str) or not self.region_id.strip():
            raise ValueError("S12: zone region id must be nonempty text")
        if not isinstance(self.bounds, Rect):
            raise ValueError("S12: zone bounds must be Rect")


@dataclass(frozen=True, slots=True)
class LightingPartition:
    zones: tuple[LightingZone, ...]
    owners: tuple[str, ...]

    def zone_at(self, tile: Tile) -> str:
        return self.owners[tile.ty * GRID_WIDTH + tile.tx]


def derive_lighting(
    regions: tuple[Region, ...], doors: tuple[Door, ...], zones: tuple[LightingZone, ...]
) -> LightingPartition:
    """Reject gaps, overlaps and incorrect ownership, including closed rooms."""
    structure = derive_structure(regions)
    topology = derive_topology(regions, doors)
    if any(not isinstance(zone, LightingZone) for zone in zones):
        raise ValueError("S12: expected LightingZone values")
    ordered = tuple(sorted(zones, key=lambda zone: zone.region_id))
    ids = tuple(zone.region_id for zone in ordered)
    if len(set(ids)) != len(ids) or set(ids) != {region.id for region in regions}:
        raise ValueError("S12: duplicate, missing or unknown zone region")
    owners: list[str] = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            tile = Tile(x, y)
            claims = [zone for zone in ordered if zone.bounds.contains(tile)]
            if len(claims) != 1:
                raise ValueError(f"S12: tile {tile} has {len(claims)} zones, expected one")
            passage = topology.passage_at(tile)
            expected = passage.region_id if passage else structure.cell_at(tile).region_id
            if claims[0].region_id != expected:
                raise ValueError(f"S12: incorrect owner at {tile}: expected {expected}")
            owners.append(expected)
    return LightingPartition(ordered, tuple(owners))


def can_mount(
    structure: Structure, topology: Topology, tile: Tile, *, window: bool = False
) -> bool:
    """S7 band-side predicate only; no object catalog or mount instance."""
    return (
        structure.cell_at(tile).kind is TileKind.NORTH_BAND
        and topology.passage_at(tile) is None
        and (not window or tile.ty < 3)
    )
