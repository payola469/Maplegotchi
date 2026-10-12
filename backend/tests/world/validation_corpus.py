"""Named, reproducible R1A-16 mutations; release inputs are never modified."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from maplegotchi.core.room import POINTS
from maplegotchi.core.world.catalog import (
    Capability,
    LocalPoint,
    Permission,
    SlotOverride,
    SlotPolicyOverride,
)
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.layout_validation import ArtGeometry, LayoutCandidate
from maplegotchi.core.world.model import DoorState, Rect
from maplegotchi.runtime.world_catalog import load_initial_catalog
from maplegotchi.runtime.world_layout import load_initial_house


def canonical_candidate() -> LayoutCandidate:
    world = load_initial_house()
    house = load_initial_catalog(world)
    root = Path(__file__).resolve().parents[3]
    art = []
    for path in sorted((root / "art/export").rglob("*.meta.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if "geometry_version" in data:
            art.append(
                ArtGeometry(data["id"], data["geometry_version"], tuple(data["orientations"]))
            )
    return LayoutCandidate(
        world.regions,
        world.doors,
        world.lighting.zones,
        house.catalog.types,
        house.instances,
        tuple(art),
        POINTS,
        Tile(21, 15),
    )


def mutate(candidate: LayoutCandidate, name: str) -> LayoutCandidate:
    """Each name identifies an intended S-rule failure, not merely any error."""

    def host(identifier: str, **changes: Any) -> LayoutCandidate:
        return replace(
            candidate,
            instances=tuple(
                replace(item, **changes) if item.id == identifier else item
                for item in candidate.instances
            ),
        )

    if name == "S1":
        return replace(candidate, grid_width=43)
    if name == "S2":
        return replace(
            candidate,
            regions=tuple(
                replace(room, floor=Rect(2, 3, 7, 7)) if room.id == "bedroom" else room
                for room in candidate.regions
            ),
        )
    if name in ("S3", "S4", "S5"):
        selected = "door.hall_future" if name == "S5" else "door.hall_bedroom"
        return replace(
            candidate,
            doors=tuple(
                replace(
                    door,
                    **(
                        {"passage": Rect(5, 9, 2, 3)}
                        if name == "S3"
                        else {"state": DoorState.CLOSED if name == "S4" else DoorState.OPEN}
                    ),
                )
                if door.id == selected
                else door
                for door in candidate.doors
            ),
        )
    if name == "S6":
        return host("lamp.living", origin=Tile(11, 5))
    if name == "S7":
        return host("frame.hall_west", origin=Tile(5, 10))
    if name == "S8":
        return host("side_table.library", slot_overrides=(SlotOverride("top", LocalPoint(-1, 1)),))
    if name in ("S9", "S13"):
        removed = "bed.bedroom" if name == "S9" else "idle.hall_center"
        return replace(
            candidate, instances=tuple(item for item in candidate.instances if item.id != removed)
        )
    if name == "S10":
        return host("lamp.living", room_id="central_hall", origin=Tile(3, 14))
    if name == "S11":
        return host(
            "bookshelf.library_1",
            slot_policies=(SlotPolicyOverride("books", maple_may_place=True),),
        )
    if name == "S12":
        return replace(candidate, zones=candidate.zones[1:])
    if name == "S14":
        return replace(
            candidate,
            legacy_targets=tuple(
                point for point in candidate.legacy_targets if point.id != "bed.side"
            ),
        )
    if name == "S15":
        return replace(
            candidate,
            types=tuple(
                replace(
                    item,
                    capabilities=(Capability.COMPUTER,),
                    points=tuple(
                        replace(point, provides=(Capability.COMPUTER,)) for point in item.points
                    ),
                )
                if item.id == "furniture.writing_desk"
                else item
                for item in candidate.types
            ),
        )
    if name == "S16":
        return replace(
            candidate,
            types=tuple(
                replace(item, movable_by=(Permission.MAPLE,))
                if item.id == "furniture.lamp_floor"
                else item
                for item in candidate.types
            ),
        )
    if name == "S17":
        return replace(
            candidate,
            art=tuple(
                replace(record, geometry_version=record.geometry_version + 1)
                for record in candidate.art
            ),
        )
    raise ValueError(f"Unknown mutation: {name}")
