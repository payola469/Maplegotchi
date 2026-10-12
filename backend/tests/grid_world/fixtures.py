"""Named synthetic candidates derived only from accepted release inputs."""

from __future__ import annotations

from dataclasses import replace

from maplegotchi.core.world.catalog import Catalog, build_catalog_layout
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.layout import build_layout
from maplegotchi.core.world.layout_validation import LayoutCandidate
from maplegotchi.core.world.model import DoorState, RegionStatus
from maplegotchi.core.world.resolution import ResolutionSnapshot
from tests.world.validation_corpus import canonical_candidate, mutate


def snapshot(candidate: LayoutCandidate) -> ResolutionSnapshot:
    world = build_layout(candidate.regions, candidate.doors, candidate.zones)
    catalog = build_catalog_layout(Catalog(candidate.types), candidate.instances, world)
    return ResolutionSnapshot(world, catalog)


def scenario(name: str) -> LayoutCandidate:
    base = canonical_candidate()
    if name in ("A", "D", "I", "K", "L", "M", "N"):
        return base
    if name in ("B", "G"):
        tile = Tile(5, 6) if name == "B" else Tile(3, 4)
        return replace(
            base,
            instances=tuple(
                replace(item, origin=tile, room_id="bedroom") if item.id == "lamp.living" else item
                for item in base.instances
            ),
        )
    if name in ("C", "J"):
        return mutate(base, "S10")
    if name == "E":
        return replace(
            base,
            regions=tuple(
                replace(r, status=RegionStatus.OPEN) if r.id == "future_space" else r
                for r in base.regions
            ),
            doors=tuple(
                replace(d, state=DoorState.OPEN) if d.id == "door.hall_future" else d
                for d in base.doors
            ),
        )
    if name == "F":
        return mutate(base, "S9")
    if name == "H":
        return replace(base, maple=Tile(1, 20))
    raise ValueError("unknown R1A-17 scenario")
