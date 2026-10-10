"""Immutable catalog metadata and geometry validation; no activity/placement execution."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from maplegotchi.core.world.coordinates import GRID_HEIGHT, GRID_WIDTH, Tile, require_integer
from maplegotchi.core.world.directions import CharacterDirection, ObjectOrientation
from maplegotchi.core.world.layout import WorldLayout
from maplegotchi.core.world.lighting import can_mount
from maplegotchi.core.world.model import Rect, RegionStatus


def identifier(value: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789._" for c in value)
        or not value[0].isalpha()
        or any(not part for part in value.split("."))
    ):
        raise ValueError("invalid catalog identifier")


def immutable_tuple(value: tuple[object, ...], item_type: type[object]) -> None:
    if type(value) is not tuple or any(not isinstance(item, item_type) for item in value):
        raise ValueError("expected immutable typed tuple")


def unique(values: tuple[str, ...]) -> None:
    if len(set(values)) != len(values):
        raise ValueError("duplicate identifier/value")


class Capability(StrEnum):
    SLEEP_SPOT = "sleep_spot"
    SEAT = "seat"
    SEAT_SOFT = "seat_soft"
    WRITING_SURFACE = "writing_surface"
    COMPUTER = "computer"
    SYSTEM_CONSOLE = "system_console"
    READING_SPOT = "reading_spot"
    BOOK_SOURCE = "book_source"
    BOOK_STORAGE = "book_storage"
    WINDOW_VIEW = "window_view"
    QUIET_SPOT = "quiet_spot"
    PLANT = "plant"
    DISPLAY_WALL = "display_wall"
    DISPLAY_SHELF = "display_shelf"
    PROJECT_BOARD = "project_board"
    OPEN_FLOOR = "open_floor"
    LIGHT_SOURCE = "light_source"


class Category(StrEnum):
    FUNCTIONAL = "functional"
    DECORATIVE = "decorative"
    CREATION_DISPLAY = "creation_display"
    STRUCTURAL = "structural"


class Surface(StrEnum):
    FLOOR = "floor"
    NORTH_BAND = "north_band"


class Permission(StrEnum):
    OWNER = "owner"
    MAPLE = "maple"


class Owner(StrEnum):
    PAOLO = "paolo"
    MAPLE = "maple"


class PointPose(StrEnum):
    LIE_SLEEP = "lie_sleep"
    SIT_REST = "sit_rest"
    STAND_THINK = "stand_think"
    STAND_READ = "stand_read"
    SIT_READ = "sit_read"
    SIT_WRITE = "sit_write"
    SIT_MONITOR = "sit_monitor"
    IDLE = "idle"


class SlotStatus(StrEnum):
    ACTIVE = "active"
    BOOK_HOOK = "hook (derived fullness)"
    PROJECT_HOOK = "hook (planned projects)"


@dataclass(frozen=True, slots=True)
class LocalPoint:
    """Signed local integer offset, used for tiles or anchor-relative pixels."""

    x: int
    y: int

    def __post_init__(self) -> None:
        require_integer(self.x, "local x")
        require_integer(self.y, "local y")


@dataclass(frozen=True, slots=True)
class Footprint:
    w: int
    h: int

    def __post_init__(self) -> None:
        require_integer(self.w, "width")
        require_integer(self.h, "height")
        if not (0 < self.w <= GRID_WIDTH and 0 < self.h <= GRID_HEIGHT):
            raise ValueError("invalid footprint")


@dataclass(frozen=True, slots=True)
class PointTemplate:
    id: str
    approach: LocalPoint
    facing: CharacterDirection
    occupy: LocalPoint | None
    pose: PointPose
    occupy_direction: CharacterDirection
    provides: tuple[Capability, ...]
    capacity: int

    def __post_init__(self) -> None:
        identifier(self.id)
        if not isinstance(self.approach, LocalPoint) or (
            self.occupy is not None and not isinstance(self.occupy, LocalPoint)
        ):
            raise ValueError("invalid point coordinates")
        if not isinstance(self.facing, CharacterDirection) or not isinstance(
            self.occupy_direction, CharacterDirection
        ):
            raise ValueError("invalid point direction")
        if not isinstance(self.pose, PointPose):
            raise ValueError("invalid point pose")
        immutable_tuple(self.provides, Capability)
        unique(self.provides)
        if not self.provides:
            raise ValueError("point must provide capabilities")
        require_integer(self.capacity, "point capacity")
        if self.capacity <= 0:
            raise ValueError("invalid point capacity")


@dataclass(frozen=True, slots=True)
class SlotTemplate:
    id: str
    approach: LocalPoint
    facing: CharacterDirection
    shares_point: str | None
    accepts: tuple[str, ...]
    capacity: int
    maple_may_place: bool
    status: SlotStatus

    def __post_init__(self) -> None:
        identifier(self.id)
        if not isinstance(self.approach, LocalPoint) or not isinstance(
            self.facing, CharacterDirection
        ):
            raise ValueError("invalid slot geometry")
        if self.shares_point is not None:
            identifier(self.shares_point)
        immutable_tuple(self.accepts, str)
        unique(self.accepts)
        if not self.accepts:
            raise ValueError("slot must accept classes")
        for item in self.accepts:
            identifier(item)
        require_integer(self.capacity, "slot capacity")
        if self.capacity <= 0 or type(self.maple_may_place) is not bool:
            raise ValueError("invalid slot policy")
        if not isinstance(self.status, SlotStatus):
            raise ValueError("invalid slot status")
        if self.status is not SlotStatus.ACTIVE and self.maple_may_place:
            raise ValueError("hook slots cannot allow Maple placement")


@dataclass(frozen=True, slots=True)
class SlotOverride:
    """STEP 97: explicit geometry only, scoped to one existing named slot."""

    slot: str
    approach: LocalPoint | None = None
    facing: CharacterDirection | None = None

    def __post_init__(self) -> None:
        identifier(self.slot)
        if self.approach is None and self.facing is None:
            raise ValueError("empty slot geometry override")
        if self.approach is not None and not isinstance(self.approach, LocalPoint):
            raise ValueError("invalid override approach")
        if self.facing is not None and not isinstance(self.facing, CharacterDirection):
            raise ValueError("invalid override facing")


@dataclass(frozen=True, slots=True)
class SlotPolicyOverride:
    """Separate existing ADR-0039 accepts/capacity/permission override boundary."""

    slot: str
    accepts: tuple[str, ...] | None = None
    capacity: int | None = None
    maple_may_place: bool | None = None

    def __post_init__(self) -> None:
        identifier(self.slot)
        if self.accepts is None and self.capacity is None and self.maple_may_place is None:
            raise ValueError("empty slot policy override")
        if self.accepts is not None:
            immutable_tuple(self.accepts, str)
            unique(self.accepts)
            if not self.accepts:
                raise ValueError("empty accepts override")
            for item in self.accepts:
                identifier(item)
        if self.capacity is not None:
            require_integer(self.capacity, "slot override capacity")
            if self.capacity <= 0:
                raise ValueError("invalid override capacity")
        if self.maple_may_place is not None and type(self.maple_may_place) is not bool:
            raise ValueError("invalid permission override")


@dataclass(frozen=True, slots=True)
class ObjectType:
    id: str
    category: Category
    geometry_version: int
    footprint: Footprint
    blocks: tuple[str, ...]
    orientations: tuple[ObjectOrientation, ...]
    capabilities: tuple[Capability, ...]
    points: tuple[PointTemplate, ...]
    slots: tuple[SlotTemplate, ...]
    states: tuple[str, ...]
    movable_by: tuple[Permission, ...]
    deletable_by: tuple[Permission, ...]
    surface: Surface
    mount_y_px: int | None
    art_id: str | None

    def __post_init__(self) -> None:
        identifier(self.id)
        if not isinstance(self.category, Category) or not isinstance(self.surface, Surface):
            raise ValueError("invalid category/surface")
        require_integer(self.geometry_version, "geometry version")
        if self.geometry_version <= 0 or not isinstance(self.footprint, Footprint):
            raise ValueError("invalid geometry metadata")
        immutable_tuple(self.blocks, str)
        if len(self.blocks) != self.footprint.h or any(
            len(row) != self.footprint.w or any(c not in "#." for c in row) for row in self.blocks
        ):
            raise ValueError("invalid blocking mask")
        for values, kind in (
            (self.orientations, ObjectOrientation),
            (self.capabilities, Capability),
            (self.points, PointTemplate),
            (self.slots, SlotTemplate),
            (self.states, str),
            (self.movable_by, Permission),
            (self.deletable_by, Permission),
        ):
            immutable_tuple(values, kind)
        unique(self.orientations)
        unique(self.capabilities)
        unique(self.states)
        unique(tuple(point.id for point in self.points))
        unique(tuple(slot.id for slot in self.slots))
        if not self.orientations or not self.states or "default" not in self.states:
            raise ValueError("missing orientations/default state")
        for state in self.states:
            identifier(state)
        unique(self.movable_by)
        unique(self.deletable_by)
        object.__setattr__(self, "points", tuple(sorted(self.points, key=lambda p: p.id)))
        object.__setattr__(self, "slots", tuple(sorted(self.slots, key=lambda s: s.id)))
        for point in self.points:
            if not set(point.provides) <= set(self.capabilities):
                raise ValueError("point capabilities outside type capabilities")
        for slot in self.slots:
            if slot.shares_point is not None:
                points = [point for point in self.points if point.id == slot.shares_point]
                if not points or (slot.approach, slot.facing) != (
                    points[0].approach,
                    points[0].facing,
                ):
                    raise ValueError("invalid declared point reuse")
        if self.surface is Surface.NORTH_BAND:
            if self.footprint.h != 1 or any("#" in row for row in self.blocks):
                raise ValueError("invalid wall footprint/mask")
            if self.mount_y_px is None:
                raise ValueError("missing mount height")
            require_integer(self.mount_y_px, "mount height")
            if self.mount_y_px <= 0:
                raise ValueError("invalid mount height")
        elif self.mount_y_px is not None:
            raise ValueError("floor object cannot have mount height")
        if self.art_id is not None:
            identifier(self.art_id)
        elif self.category is not Category.STRUCTURAL:
            raise ValueError("nonstructural type requires art reference")


@dataclass(frozen=True, slots=True)
class Catalog:
    types: tuple[ObjectType, ...]

    def __post_init__(self) -> None:
        immutable_tuple(self.types, ObjectType)
        unique(tuple(item.id for item in self.types))
        if not self.types:
            raise ValueError("empty catalog")
        object.__setattr__(self, "types", tuple(sorted(self.types, key=lambda item: item.id)))
        for item in self.types:
            expected = {
                "furniture.writing_desk": Capability.WRITING_SURFACE,
                "furniture.computer_desk": Capability.COMPUTER,
            }.get(item.id)
            if expected is not None and item.capabilities != (expected,):
                raise ValueError("S15: desks must preserve Option A")
        names = {item.id for item in self.types}
        if {"furniture.writing_desk", "furniture.computer_desk"} <= names:
            writing = self.get("furniture.writing_desk")
            computer = self.get("furniture.computer_desk")
            if set(writing.capabilities) & set(computer.capabilities):
                raise ValueError("S15: desk capabilities must be disjoint")
            if writing.capabilities != (Capability.WRITING_SURFACE,) or computer.capabilities != (
                Capability.COMPUTER,
            ):
                raise ValueError("S15: desks must preserve Option A")

    def get(self, type_id: str) -> ObjectType:
        for item in self.types:
            if item.id == type_id:
                return item
        raise ValueError(f"S17: unknown type {type_id}")


@dataclass(frozen=True, slots=True)
class ObjectInstance:
    id: str
    type_id: str
    room_id: str
    origin: Tile
    orientation: ObjectOrientation
    state: str
    owner: Owner
    slot_overrides: tuple[SlotOverride, ...] = ()
    slot_policies: tuple[SlotPolicyOverride, ...] = ()
    link: str | None = None

    def __post_init__(self) -> None:
        for value in (self.id, self.type_id, self.room_id, self.state):
            identifier(value)
        if not isinstance(self.origin, Tile) or not isinstance(self.orientation, ObjectOrientation):
            raise ValueError("invalid instance geometry")
        if not isinstance(self.owner, Owner):
            raise ValueError("invalid instance owner")
        immutable_tuple(self.slot_overrides, SlotOverride)
        immutable_tuple(self.slot_policies, SlotPolicyOverride)
        unique(tuple(item.slot for item in self.slot_overrides))
        unique(tuple(item.slot for item in self.slot_policies))
        object.__setattr__(
            self, "slot_overrides", tuple(sorted(self.slot_overrides, key=lambda o: o.slot))
        )
        object.__setattr__(
            self, "slot_policies", tuple(sorted(self.slot_policies, key=lambda o: o.slot))
        )
        if self.link is not None and (not isinstance(self.link, str) or not self.link.strip()):
            raise ValueError("invalid soft link")


def turns(orientation: ObjectOrientation) -> int:
    if not isinstance(orientation, ObjectOrientation):
        raise ValueError("invalid orientation")
    return (
        ObjectOrientation.SOUTH,
        ObjectOrientation.WEST,
        ObjectOrientation.NORTH,
        ObjectOrientation.EAST,
    ).index(orientation)


def rotate_local(
    point: LocalPoint, footprint: Footprint, orientation: ObjectOrientation
) -> LocalPoint:
    x, y, w, h = point.x, point.y, footprint.w, footprint.h
    for _ in range(turns(orientation)):
        x, y, w, h = h - 1 - y, x, h, w
    return LocalPoint(x, y)


def rotate_direction(
    direction: CharacterDirection, orientation: ObjectOrientation
) -> CharacterDirection:
    if not isinstance(direction, CharacterDirection):
        raise ValueError("invalid character direction")
    cycle = (
        CharacterDirection.DOWN,
        CharacterDirection.LEFT,
        CharacterDirection.UP,
        CharacterDirection.RIGHT,
    )
    return cycle[(cycle.index(direction) + turns(orientation)) % 4]


def rotate_vector(point: LocalPoint, orientation: ObjectOrientation) -> LocalPoint:
    x, y = point.x, point.y
    for _ in range(turns(orientation)):
        x, y = -y, x
    return LocalPoint(x, y)


def oriented_footprint(item: ObjectType, orientation: ObjectOrientation) -> Footprint:
    if orientation not in item.orientations:
        raise ValueError("S17: unsupported orientation")
    return (
        Footprint(item.footprint.h, item.footprint.w) if turns(orientation) % 2 else item.footprint
    )


def blocking_offsets(item: ObjectType, orientation: ObjectOrientation) -> tuple[LocalPoint, ...]:
    oriented_footprint(item, orientation)
    result = [
        rotate_local(LocalPoint(x, y), item.footprint, orientation)
        for y, row in enumerate(item.blocks)
        for x, c in enumerate(row)
        if c == "#"
    ]
    return tuple(sorted(result, key=lambda point: (point.y, point.x)))


@dataclass(frozen=True, slots=True)
class ResolvedPoint:
    instance_id: str
    template: PointTemplate


@dataclass(frozen=True, slots=True)
class ResolvedSlot:
    instance_id: str
    template: SlotTemplate


@dataclass(frozen=True, slots=True)
class CatalogLayout:
    catalog: Catalog
    instances: tuple[ObjectInstance, ...]
    points: tuple[ResolvedPoint, ...]
    slots: tuple[ResolvedSlot, ...]
    blocking_tiles: tuple[Tile, ...]


def world_approach(local: LocalPoint, item: ObjectType, instance: ObjectInstance) -> LocalPoint:
    offset = rotate_local(local, item.footprint, instance.orientation)
    return LocalPoint(instance.origin.tx + offset.x, instance.origin.ty + offset.y)


def build_catalog_layout(
    catalog: Catalog, instances: tuple[ObjectInstance, ...], world: WorldLayout
) -> CatalogLayout:
    """S6/S7 and metadata S8/S9/S15/S16/S17; no path search/placement or activation."""
    if not isinstance(catalog, Catalog) or not isinstance(world, WorldLayout):
        raise ValueError("expected catalog and world values")
    immutable_tuple(instances, ObjectInstance)
    unique(tuple(instance.id for instance in instances))
    ordered = tuple(sorted(instances, key=lambda instance: instance.id))
    points: list[ResolvedPoint] = []
    slots: list[ResolvedSlot] = []
    blocking: list[Tile] = []
    for instance in ordered:
        item = catalog.get(instance.type_id)
        size = oriented_footprint(item, instance.orientation)
        if instance.state not in item.states:
            raise ValueError("S17: unsupported state")
        if (
            instance.owner is not Owner.PAOLO
            or item.movable_by != (Permission.OWNER,)
            or item.deletable_by != (Permission.OWNER,)
        ):
            raise ValueError("S16: initial furniture must be owner-controlled")
        rooms = [room for room in world.regions if room.id == instance.room_id]
        if not rooms or rooms[0].status is not RegionStatus.OPEN:
            raise ValueError("invalid or closed object room")
        room = rooms[0]
        if item.surface is Surface.FLOOR:
            rect = Rect(instance.origin.tx, instance.origin.ty, size.w, size.h)
            if not all(
                room.floor.contains(Tile(x, y))
                for y in range(rect.y, rect.y + rect.h)
                for x in range(rect.x, rect.x + rect.w)
            ):
                raise ValueError("S6: footprint outside host floor")
            for offset in blocking_offsets(item, instance.orientation):
                tile = Tile(instance.origin.tx + offset.x, instance.origin.ty + offset.y)
                if tile in blocking:
                    raise ValueError("S6: overlapping blocking masks")
                blocking.append(tile)
        else:
            if instance.origin.ty != room.floor.y - 3:
                raise ValueError("S7: mount must use north-band origin")
            for x in range(instance.origin.tx, instance.origin.tx + size.w):
                for y in range(instance.origin.ty, instance.origin.ty + 3):
                    tile = Tile(x, y)
                    if world.structure.cell_at(tile).region_id != room.id or not can_mount(
                        world.structure, world.topology, tile, window=item.id == "window.north_2w"
                    ):
                        raise ValueError("S7: invalid mounted band columns")
        local_points: dict[str, PointTemplate] = {}
        for point in item.points:
            local_points[point.id] = point
            resolved = replace(
                point,
                approach=world_approach(point.approach, item, instance),
                facing=rotate_direction(point.facing, instance.orientation),
                occupy=rotate_vector(point.occupy, instance.orientation)
                if point.occupy is not None
                else None,
                occupy_direction=rotate_direction(point.occupy_direction, instance.orientation),
            )
            if not room.floor.contains(Tile(resolved.approach.x, resolved.approach.y)):
                raise ValueError("S8 metadata: approach outside host floor")
            points.append(ResolvedPoint(instance.id, resolved))
        slot_ids = {slot.id for slot in item.slots}
        if any(override.slot not in slot_ids for override in instance.slot_overrides) or any(
            policy.slot not in slot_ids for policy in instance.slot_policies
        ):
            raise ValueError("unknown slot override")
        for slot in item.slots:
            for override in instance.slot_overrides:
                if override.slot == slot.id:
                    slot = replace(
                        slot,
                        approach=override.approach
                        if override.approach is not None
                        else slot.approach,
                        facing=override.facing if override.facing is not None else slot.facing,
                    )
            for policy in instance.slot_policies:
                if policy.slot == slot.id:
                    slot = replace(
                        slot,
                        accepts=policy.accepts if policy.accepts is not None else slot.accepts,
                        capacity=policy.capacity if policy.capacity is not None else slot.capacity,
                        maple_may_place=policy.maple_may_place
                        if policy.maple_may_place is not None
                        else slot.maple_may_place,
                    )
            if slot.shares_point is not None:
                point = local_points[slot.shares_point]
                if (slot.approach, slot.facing) != (point.approach, point.facing):
                    raise ValueError("S8 metadata: override breaks declared point reuse")
            resolved_slot = replace(
                slot,
                approach=world_approach(slot.approach, item, instance),
                facing=rotate_direction(slot.facing, instance.orientation),
            )
            if not room.floor.contains(Tile(resolved_slot.approach.x, resolved_slot.approach.y)):
                raise ValueError("S8 metadata: slot approach outside host floor")
            slots.append(ResolvedSlot(instance.id, resolved_slot))
    # S8's static coincidence rule; no collision engine or reachability claim.
    approaches: dict[LocalPoint, tuple[str, str]] = {}
    for resolved_point in points:
        point_tile = resolved_point.template.approach
        if point_tile in approaches:
            raise ValueError("S8 metadata: unrelated point approaches coincide")
        approaches[point_tile] = (resolved_point.instance_id, resolved_point.template.id)
    for bound_slot in slots:
        slot = bound_slot.template
        expected = (bound_slot.instance_id, slot.shares_point)
        if slot.approach in approaches:
            if slot.shares_point is None or approaches[slot.approach] != expected:
                raise ValueError("S8 metadata: undeclared approach coincidence")
        elif slot.shares_point is not None:
            raise ValueError("S8 metadata: missing shared point approach")
        else:
            approaches[slot.approach] = (bound_slot.instance_id, slot.id)
    return CatalogLayout(
        catalog,
        ordered,
        tuple(sorted(points, key=lambda p: (p.instance_id, p.template.id))),
        tuple(sorted(slots, key=lambda s: (s.instance_id, s.template.id))),
        tuple(sorted(blocking, key=lambda t: (t.ty, t.tx))),
    )


def validate_provider_metadata(
    layout: CatalogLayout, requirements: tuple[tuple[tuple[Capability, ...], ...], ...]
) -> None:
    """S9 metadata coverage only: no room/path/state/capacity candidate selection."""
    for alternatives in requirements:
        if not alternatives or any(not group for group in alternatives):
            raise ValueError("invalid capability requirements")
        for group in alternatives:
            immutable_tuple(group, Capability)
        if not any(
            set(group) <= set(point.template.provides)
            for group in alternatives
            for point in layout.points
        ):
            raise ValueError("S9 metadata: missing provider")
