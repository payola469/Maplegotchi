"""Canonical tile access and prevention checks; no placement execution or pathfinding."""

from __future__ import annotations

from dataclasses import dataclass

from maplegotchi.core.world.catalog import CatalogLayout
from maplegotchi.core.world.coordinates import GRID_HEIGHT, GRID_WIDTH, Tile
from maplegotchi.core.world.layout import WorldLayout
from maplegotchi.core.world.model import DoorState, Rect, RegionKind, RegionStatus


def ordered(cells: set[Tile]) -> tuple[Tile, ...]:
    return tuple(sorted(cells, key=lambda tile: (tile.ty, tile.tx)))


def cells(rect: Rect) -> tuple[Tile, ...]:
    return tuple(
        Tile(x, y) for y in range(rect.y, rect.y + rect.h) for x in range(rect.x, rect.x + rect.w)
    )


def neighbors(tile: Tile) -> tuple[Tile, ...]:
    """Four neighbors in canonical order, without constructing out-of-grid Tiles."""
    return ordered(
        {
            Tile(x, y)
            for x, y in (
                (tile.tx, tile.ty - 1),
                (tile.tx - 1, tile.ty),
                (tile.tx + 1, tile.ty),
                (tile.tx, tile.ty + 1),
            )
            if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT
        }
    )


def components(tiles: tuple[Tile, ...]) -> tuple[tuple[Tile, ...], ...]:
    remaining = set(tiles)
    result: list[tuple[Tile, ...]] = []
    while remaining:
        start = min(remaining, key=lambda tile: (tile.ty, tile.tx))
        pending = [start]
        reached = {start}
        remaining.remove(start)
        while pending:
            for neighbor in neighbors(pending.pop()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    reached.add(neighbor)
                    pending.append(neighbor)
        result.append(ordered(reached))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class Walkability:
    permitted: tuple[Tile, ...]
    blocked: tuple[Tile, ...]
    walkable: tuple[Tile, ...]
    keep_clear: tuple[Tile, ...]
    required: tuple[Tile, ...]
    door_access: tuple[Tile, ...]
    components: tuple[tuple[Tile, ...], ...]
    safe_tile: Tile | None


def derive_walkability(world: WorldLayout, catalog: CatalogLayout) -> Walkability:
    """S5 access mask, K1-K3 cells and dynamic K4 targets from frozen domain data.

    CatalogLayout must come from build_catalog_layout, which owns transforms and S6-S8.
    Open doors with a closed endpoint are rejected rather than exposing closed areas.
    This derivation permits unsafe candidates so prevention can diagnose them and
    emergency recovery can inspect exceptional state. Call validate_safe_layout
    before accepting a proposed change.
    """
    rooms = {room.id: room for room in world.regions}
    permitted = {
        tile
        for room in world.regions
        if room.status is RegionStatus.OPEN
        for tile in cells(room.floor)
    }
    protected: set[Tile] = set()
    access: set[Tile] = set()
    for door in sorted(world.doors, key=lambda item: item.id):
        rect = door.passage
        approaches = {
            Tile(x, y)
            for x in range(rect.x, rect.x + rect.w)
            for y in (rect.y - 2, rect.y - 1, rect.y + rect.h, rect.y + rect.h + 1)
        }
        if any(
            not (
                rooms[door.north_room].floor.contains(tile)
                or rooms[door.south_room].floor.contains(tile)
            )
            for tile in approaches
        ):
            raise ValueError(f"S10/K1: insufficient floor clearance for {door.id}")
        protected.update(approaches)
        if door.state is DoorState.OPEN:
            if any(
                rooms[id].status is not RegionStatus.OPEN
                for id in (door.north_room, door.south_room)
            ):
                raise ValueError(f"S5: open door {door.id} connects a closed region")
            permitted.update(cells(rect))
            access.update(approaches)
    required = {
        Tile(point.template.approach.x, point.template.approach.y) for point in catalog.points
    }
    required.update(
        Tile(slot.template.approach.x, slot.template.approach.y) for slot in catalog.slots
    )
    protected.update(required)
    for room in world.regions:
        if room.kind is RegionKind.HALL:
            protected.update(tile for tile in cells(room.floor) if tile.ty in (14, 15))
    safe = Tile(21, 15)
    safe_declared = any(
        point.instance_id == "idle.hall_center"
        and (point.template.approach.x, point.template.approach.y) == (safe.tx, safe.ty)
        for point in catalog.points
    )
    blocked = set(catalog.blocking_tiles)
    walkable = ordered(permitted - blocked)
    return Walkability(
        ordered(permitted),
        ordered(blocked),
        walkable,
        ordered(protected),
        ordered(required),
        ordered(access),
        components(walkable),
        safe if safe_declared else None,
    )


def validate_safe_layout(
    world: WorldLayout, catalog: CatalogLayout, maple: Tile | None = None
) -> Walkability:
    """Reject unsafe proposals. Never invoke recovery to accept a failed layout.

    K4 reserves connectivity, not a fixed straight corridor. The single component
    contains all open-door accesses, all required approaches and Maple (if supplied).
    Closed-door K1 approaches remain protected but are not required walkable.
    """
    mask = derive_walkability(world, catalog)
    collision = ordered(set(mask.blocked) & set(mask.keep_clear))
    if collision:
        raise ValueError(f"S10/K1-K3: blocked protected tile {collision[0]}")
    if mask.safe_tile is None or mask.safe_tile not in mask.walkable:
        raise ValueError("S13: canonical fallback missing or not walkable")
    if len(mask.components) != 1:
        raise ValueError("S10/K4: open walkable area must form one component")
    reachable = set(mask.components[0])
    missing = ordered((set(mask.required) | set(mask.door_access)) - reachable)
    if missing:
        raise ValueError(f"S10/K4: unreachable required tile {missing[0]}")
    if maple is not None and maple not in reachable:
        raise ValueError("S13: Maple is not in the safe walkable component")
    return mask
