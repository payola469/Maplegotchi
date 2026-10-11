// Generated from docs/api/world-openapi.json; do not edit.
// Backend is authoritative. No renderer logic or legacy DTO replacement.

export type Capability = "sleep_spot" | "seat" | "seat_soft" | "writing_surface" | "computer" | "system_console" | "reading_spot" | "book_source" | "book_storage" | "window_view" | "quiet_spot" | "plant" | "display_wall" | "display_shelf" | "project_board" | "open_floor" | "light_source";

export type Category = "functional" | "decorative" | "creation_display" | "structural";

export type CharacterDirection = "down" | "left" | "right" | "up";

export type DayPhase = "night" | "morning" | "afternoon" | "evening";

export type DisplayItemOut = {
  readonly "category": Category;
  readonly "id": string;
  readonly "item_class": string;
};

export type DisplayPlacementOut = {
  readonly "active": true;
  readonly "host_id": string;
  readonly "id": string;
  readonly "item_id": string;
  readonly "slot_id": string;
};

export type Door = {
  readonly "id": string;
  readonly "north_room": string;
  readonly "passage": Rect;
  readonly "south_room": string;
  readonly "state": DoorState;
};

export type DoorState = "open" | "closed";

export type EdgePositionOut = {
  readonly "edge": EdgeStart;
  readonly "kind": "edge";
};

export type EdgeStart = {
  readonly "a": Tile;
  readonly "b": Tile;
  readonly "progress_us": number;
  readonly "step_us": number;
};

export type Entry = {
  readonly "endpoint": Tile;
  readonly "start": EdgeStart;
};

export type Expression = "calm" | "happy" | "curious" | "sleepy" | "focused";

export type Facing = "left" | "right" | "front" | "back";

export type Footprint = {
  readonly "h": number;
  readonly "w": number;
};

export type GridOut = {
  readonly "feet_in_tile_px": readonly [number, number];
  readonly "height_tiles": number;
  readonly "tile_size_px": number;
  readonly "width_tiles": number;
};

export type LightingZoneOut = {
  readonly "bounds": RectOut;
  readonly "region_id": string;
};

export type LocalPoint = {
  readonly "x": number;
  readonly "y": number;
};

export type ObjectOrientation = "south" | "east" | "west" | "north";

export type Passage = {
  readonly "cells": ReadonlyArray<Tile>;
  readonly "door_id": string;
  readonly "region_id": string;
  readonly "state": DoorState;
};

export type PixelPositionOut = {
  readonly "x_px": number;
  readonly "y_px": number;
};

export type PointPose = "lie_sleep" | "sit_rest" | "stand_think" | "stand_read" | "sit_read" | "sit_write" | "sit_monitor" | "idle";

export type PointTemplate = {
  readonly "approach": LocalPoint;
  readonly "capacity": number;
  readonly "facing": CharacterDirection;
  readonly "id": string;
  readonly "occupy": (LocalPoint | null);
  readonly "occupy_direction": CharacterDirection;
  readonly "pose": PointPose;
  readonly "provides": ReadonlyArray<Capability>;
};

export type Rect = {
  readonly "h": number;
  readonly "w": number;
  readonly "x": number;
  readonly "y": number;
};

export type RectOut = {
  readonly "h": number;
  readonly "w": number;
  readonly "x": number;
  readonly "y": number;
};

export type Region = {
  readonly "floor": Rect;
  readonly "id": string;
  readonly "kind": RegionKind;
  readonly "status": RegionStatus;
};

export type RegionKind = "bedroom" | "living" | "library" | "studio" | "hall" | "future" | "creation" | "system";

export type RegionStatus = "open" | "closed";

export type RoomNode = {
  readonly "neighbors": ReadonlyArray<string>;
  readonly "region_id": string;
};

export type SlotStatus = "active" | "hook (derived fullness)" | "hook (planned projects)";

export type SlotTemplate = {
  readonly "accepts": ReadonlyArray<string>;
  readonly "approach": LocalPoint;
  readonly "capacity": number;
  readonly "facing": CharacterDirection;
  readonly "id": string;
  readonly "maple_may_place": boolean;
  readonly "shares_point": (string | null);
  readonly "status": SlotStatus;
};

export type StructuralCell = {
  readonly "kind": TileKind;
  readonly "region_id": string;
  readonly "tile": Tile;
};

export type Surface = "floor" | "north_band";

export type Tile = {
  readonly "tx": number;
  readonly "ty": number;
};

export type TileKind = "floor" | "north_band" | "side_wall" | "south_cutaway";

export type TilePositionOut = {
  readonly "kind": "tile";
  readonly "tile": Tile;
};

export type Waypoint = {
  readonly "cumulative_steps": number;
  readonly "tx": number;
  readonly "ty": number;
};

export type WorldCatalogOut = {
  readonly "catalog_version": string;
  readonly "contract_version": "r1a-10.v1";
  readonly "layout_revision": string;
  readonly "source": "development_fixture";
  readonly "status": "synthetic";
  readonly "types": ReadonlyArray<WorldTypeOut>;
};

export type WorldMapleOut = {
  readonly "derived_pixels": PixelPositionOut;
  readonly "destination_point": WorldPointRefOut;
  readonly "expression": Expression;
  readonly "facing": CharacterDirection;
  readonly "legacy_facing": Facing;
  readonly "pose": (PointPose | "walk");
  readonly "position": (TilePositionOut | EdgePositionOut);
  readonly "route": (WorldRouteOut | null);
};

export type WorldObjectOut = {
  readonly "id": string;
  readonly "orientation": ObjectOrientation;
  readonly "origin": Tile;
  readonly "room_id": string;
  readonly "state": string;
  readonly "type_id": string;
};

export type WorldOut = {
  readonly "catalog_version": string;
  readonly "contract_version": "r1a-10.v1";
  readonly "doors": ReadonlyArray<Door>;
  readonly "grid": GridOut;
  readonly "layout_revision": string;
  readonly "lighting_zones": ReadonlyArray<LightingZoneOut>;
  readonly "objects": ReadonlyArray<WorldObjectOut>;
  readonly "passages": ReadonlyArray<Passage>;
  readonly "points": ReadonlyArray<WorldPointOut>;
  readonly "regions": ReadonlyArray<Region>;
  readonly "room_graph": ReadonlyArray<RoomNode>;
  readonly "slots": ReadonlyArray<WorldSlotOut>;
  readonly "snapshot": WorldSnapshotOut;
  readonly "source": "development_fixture";
  readonly "status": "synthetic";
  readonly "structure": ReadonlyArray<StructuralCell>;
  readonly "walkable": ReadonlyArray<Tile>;
};

export type WorldPlacementsOut = {
  readonly "catalog_version": string;
  readonly "contract_version": "r1a-10.v1";
  readonly "items": ReadonlyArray<DisplayItemOut>;
  readonly "layout_revision": string;
  readonly "placements": ReadonlyArray<DisplayPlacementOut>;
  readonly "source": "development_fixture";
  readonly "status": "synthetic";
  readonly "storage_item_ids": ReadonlyArray<string>;
};

export type WorldPointOut = {
  readonly "instance_id": string;
  readonly "template": PointTemplate;
};

export type WorldPointRefOut = {
  readonly "instance_id": string;
  readonly "point_id": string;
};

export type WorldRouteOut = {
  readonly "arrives_at": string;
  readonly "departed_at": string;
  readonly "entry": (Entry | null);
  readonly "ms_per_step": number;
  readonly "waypoints": ReadonlyArray<Waypoint>;
};

export type WorldSlotOut = {
  readonly "instance_id": string;
  readonly "template": SlotTemplate;
};

export type WorldSnapshotOut = {
  readonly "day_phase": DayPhase;
  readonly "generated_at": string;
  readonly "maple": WorldMapleOut;
  readonly "world_revision": string;
};

export type WorldTypeOut = {
  readonly "art_id": (string | null);
  readonly "blocks": ReadonlyArray<string>;
  readonly "capabilities": ReadonlyArray<Capability>;
  readonly "category": Category;
  readonly "footprint": Footprint;
  readonly "geometry_version": number;
  readonly "id": string;
  readonly "mount_y_px": (number | null);
  readonly "orientations": ReadonlyArray<ObjectOrientation>;
  readonly "points": ReadonlyArray<PointTemplate>;
  readonly "slots": ReadonlyArray<SlotTemplate>;
  readonly "states": ReadonlyArray<string>;
  readonly "surface": Surface;
};

export type WorldUnavailableOut = {
  readonly "detail": "Canonical world is unavailable; live Maple remains on schema v10";
};
