"""Frozen validated layout assembly; resource parsing belongs to runtime."""

from __future__ import annotations

from dataclasses import dataclass

from maplegotchi.core.world.geometry import Structure, derive_structure
from maplegotchi.core.world.lighting import LightingPartition, LightingZone, derive_lighting
from maplegotchi.core.world.model import Door, Region
from maplegotchi.core.world.topology import Topology, derive_topology


@dataclass(frozen=True, slots=True)
class WorldLayout:
    regions: tuple[Region, ...]
    doors: tuple[Door, ...]
    structure: Structure
    topology: Topology
    lighting: LightingPartition


def build_layout(
    regions: tuple[Region, ...], doors: tuple[Door, ...], zones: tuple[LightingZone, ...]
) -> WorldLayout:
    """Validate before returning frozen values; preserve declared table order."""
    return WorldLayout(
        regions,
        doors,
        derive_structure(regions),
        derive_topology(regions, doors),
        derive_lighting(regions, doors, zones),
    )
