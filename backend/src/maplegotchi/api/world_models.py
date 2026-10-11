"""Read-only candidate world contracts; not the proposed v11 persistence schema."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from maplegotchi.core.daytime import DayPhase
from maplegotchi.core.room import Facing
from maplegotchi.core.state import Expression
from maplegotchi.core.world.catalog import (
    Capability,
    Category,
    Footprint,
    PointPose,
    PointTemplate,
    SlotTemplate,
    Surface,
)
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.directions import CharacterDirection, ObjectOrientation
from maplegotchi.core.world.geometry import StructuralCell
from maplegotchi.core.world.model import Door, Region
from maplegotchi.core.world.movement import EdgeStart, Entry
from maplegotchi.core.world.pathfinding import Waypoint
from maplegotchi.core.world.topology import Passage, RoomNode


class WorldDTO(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
        json_schema_serialization_defaults_required=True,
    )


class WorldUnavailableOut(WorldDTO):
    detail: Literal["Canonical world is unavailable; live Maple remains on schema v10"] = (
        "Canonical world is unavailable; live Maple remains on schema v10"
    )


class WorldIdentityOut(WorldDTO):
    contract_version: Literal["r1a-10.v1"] = "r1a-10.v1"
    source: Literal["development_fixture"] = "development_fixture"
    status: Literal["synthetic"] = "synthetic"
    layout_revision: str  # fixture content hash, never a persisted DB revision
    catalog_version: str  # content hash, never a release or art version claim


class GridOut(WorldDTO):
    width_tiles: int
    height_tiles: int
    tile_size_px: int
    feet_in_tile_px: tuple[int, int]


class WorldObjectOut(WorldDTO):
    id: str
    type_id: str
    room_id: str
    origin: Tile
    orientation: ObjectOrientation
    state: str
    # Links/owner and permission policy are not needed for this renderer handoff.


class WorldPointOut(WorldDTO):
    instance_id: str
    template: PointTemplate  # resolved absolute approach; occupy remains anchor-relative px


class WorldSlotOut(WorldDTO):
    instance_id: str
    template: SlotTemplate  # resolved absolute approach, not a sprite anchor


class WorldTypeOut(WorldDTO):
    id: str
    category: Category
    geometry_version: int
    footprint: Footprint  # south orientation
    blocks: tuple[str, ...]
    orientations: tuple[ObjectOrientation, ...]
    capabilities: tuple[Capability, ...]
    points: tuple[PointTemplate, ...]  # local tile approach; occupy in px
    slots: tuple[SlotTemplate, ...]  # local defaults; resolved overrides in world
    states: tuple[str, ...]
    surface: Surface
    mount_y_px: int | None
    art_id: str | None  # soft key; no URL or claim of available production art


class WorldCatalogOut(WorldIdentityOut):
    types: tuple[WorldTypeOut, ...]


class TilePositionOut(WorldDTO):
    kind: Literal["tile"] = "tile"
    tile: Tile


class EdgePositionOut(WorldDTO):
    kind: Literal["edge"] = "edge"
    edge: EdgeStart  # exact integer progress in microseconds; no rounded authoritative tile


class PixelPositionOut(WorldDTO):
    x_px: int
    y_px: int


class WorldRouteOut(WorldDTO):
    departed_at: datetime
    arrives_at: datetime
    ms_per_step: int  # provisional engine tuning, not legacy route speed
    waypoints: tuple[Waypoint, ...]
    entry: Entry | None


class WorldPointRefOut(WorldDTO):
    instance_id: str
    point_id: str


class WorldMapleOut(WorldDTO):
    destination_point: WorldPointRefOut
    position: TilePositionOut | EdgePositionOut
    derived_pixels: PixelPositionOut
    facing: CharacterDirection
    legacy_facing: Facing
    pose: PointPose | Literal["walk"]
    expression: Expression
    route: WorldRouteOut | None


class WorldSnapshotOut(WorldDTO):
    """Explicit synthetic snapshot; production SnapshotOut is not extended."""

    generated_at: datetime
    world_revision: str
    day_phase: DayPhase
    maple: WorldMapleOut


class WorldOut(WorldIdentityOut):
    grid: GridOut
    regions: tuple[Region, ...]
    doors: tuple[Door, ...]
    structure: tuple[StructuralCell, ...]  # uncarved bands; passages override these cells
    passages: tuple[Passage, ...]
    room_graph: tuple[RoomNode, ...]
    lighting_zones: tuple[LightingZoneOut, ...]
    objects: tuple[WorldObjectOut, ...]
    points: tuple[WorldPointOut, ...]
    slots: tuple[WorldSlotOut, ...]
    walkable: tuple[Tile, ...]
    snapshot: WorldSnapshotOut


class LightingZoneOut(WorldDTO):
    region_id: str
    bounds: RectOut


class RectOut(WorldDTO):
    x: int
    y: int
    w: int
    h: int


class DisplayItemOut(WorldDTO):
    id: str
    item_class: str
    category: Category
    # Representation content and art/slot sprite anchors remain later-workstream inputs.


class DisplayPlacementOut(WorldDTO):
    id: str
    item_id: str
    host_id: str
    slot_id: str
    active: Literal[True] = True


class WorldPlacementsOut(WorldIdentityOut):
    items: tuple[DisplayItemOut, ...]
    placements: tuple[DisplayPlacementOut, ...]
    storage_item_ids: tuple[str, ...]  # derived existing eligible items, never invented storage


WorldOut.model_rebuild()
