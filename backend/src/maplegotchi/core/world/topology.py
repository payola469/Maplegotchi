"""S3/S4 door passages and derived room graph, without tile pathfinding."""

from __future__ import annotations

from dataclasses import dataclass

from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.geometry import TileKind, derive_structure
from maplegotchi.core.world.model import Door, DoorState, Region, RegionStatus


@dataclass(frozen=True, slots=True)
class Passage:
    """Validated cells belong to the southern room in either door state."""

    door_id: str
    region_id: str
    state: DoorState
    cells: tuple[Tile, ...]


@dataclass(frozen=True, slots=True)
class RoomNode:
    region_id: str
    neighbors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Topology:
    """Canonical passages and graph nodes; no independently authored edges."""

    passages: tuple[Passage, ...]
    graph: tuple[RoomNode, ...]

    def passage_at(self, tile: Tile) -> Passage | None:
        for passage in self.passages:
            if tile in passage.cells:
                return passage
        return None


def derive_topology(regions: tuple[Region, ...], doors: tuple[Door, ...]) -> Topology:
    """Validate geometry then require connectivity across open regions (S4).

    Closed rooms remain graph nodes, but cannot bridge the open-room component.
    Passage state is retained separately from the uncarved structural map.
    """
    structure = derive_structure(regions)
    rooms = {region.id: region for region in regions}
    if any(not isinstance(door, Door) for door in doors):
        raise ValueError("S3: expected Door values")
    ordered = tuple(sorted(doors, key=lambda door: door.id))
    seen_ids: set[str] = set()
    occupied: dict[Tile, str] = {}
    passages: list[Passage] = []
    neighbors: dict[str, set[str]] = {room: set() for room in sorted(rooms)}
    for door in ordered:
        if door.id in seen_ids:
            raise ValueError(f"S3: duplicate door id {door.id}")
        seen_ids.add(door.id)
        if door.north_room not in rooms or door.south_room not in rooms:
            raise ValueError(f"S3: door {door.id} references missing room")
        north = rooms[door.north_room].floor
        south = rooms[door.south_room].floor
        rect = door.passage
        if north.y + north.h != rect.y or rect.y + rect.h != south.y:
            raise ValueError(f"S3: door {door.id} rooms not north/south adjacent to band")
        for x in range(rect.x, rect.x + rect.w):
            if not north.contains(Tile(x, rect.y - 1)) or not south.contains(
                Tile(x, rect.y + rect.h)
            ):
                raise ValueError(f"S3: door {door.id} lacks floor on both sides at x={x}")
        cells = tuple(
            Tile(x, y)
            for y in range(rect.y, rect.y + rect.h)
            for x in range(rect.x, rect.x + rect.w)
        )
        for tile in cells:
            cell = structure.cell_at(tile)
            if cell.kind is not TileKind.NORTH_BAND or cell.region_id != door.south_room:
                raise ValueError(f"S3: door {door.id} outside southern north band at {tile}")
            if tile in occupied:
                raise ValueError(f"S3: doors {occupied[tile]} and {door.id} overlap at {tile}")
            occupied[tile] = door.id
        passages.append(Passage(door.id, door.south_room, door.state, cells))
        if door.state is DoorState.OPEN:
            neighbors[door.north_room].add(door.south_room)
            neighbors[door.south_room].add(door.north_room)

    open_rooms = {region.id for region in regions if region.status is RegionStatus.OPEN}
    if open_rooms:
        pending = [min(open_rooms)]
        reached: set[str] = set()
        while pending:
            room = pending.pop()
            if room in reached:
                continue
            reached.add(room)
            pending.extend(sorted((neighbors[room] & open_rooms) - reached, reverse=True))
        missing = sorted(open_rooms - reached)
        if missing:
            raise ValueError(f"S4: disconnected open rooms: {', '.join(missing)}")
    return Topology(
        tuple(passages),
        tuple(RoomNode(room, tuple(sorted(adjacent))) for room, adjacent in neighbors.items()),
    )
