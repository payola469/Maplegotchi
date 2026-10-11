"""Candidate-only slot validation and derived Storage; no execution or persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from maplegotchi.core.daytime import require_utc
from maplegotchi.core.memory import local_day
from maplegotchi.core.world.catalog import (
    CatalogLayout,
    Category,
    ObjectInstance,
    Owner,
    Permission,
    ResolvedPoint,
    ResolvedSlot,
    SlotStatus,
    build_catalog_layout,
    identifier,
    immutable_tuple,
    unique,
)
from maplegotchi.core.world.coordinates import Tile, require_integer
from maplegotchi.core.world.layout import WorldLayout, build_layout
from maplegotchi.core.world.lighting import LightingPartition, LightingZone
from maplegotchi.core.world.model import Door, Region, RegionStatus
from maplegotchi.core.world.pathfinding import Route, find_route
from maplegotchi.core.world.walkability import Walkability, derive_walkability, validate_safe_layout


@dataclass(frozen=True, slots=True)
class PlacementSnapshot:
    """Strict saved-layout boundary; isolated from the capability resolver."""

    world: WorldLayout
    catalog: CatalogLayout

    def __post_init__(self) -> None:
        if not isinstance(self.world, WorldLayout) or not isinstance(self.catalog, CatalogLayout):
            raise ValueError("invalid world/catalog")
        immutable_tuple(self.world.regions, Region)
        immutable_tuple(self.world.doors, Door)
        if not isinstance(self.world.lighting, LightingPartition):
            raise ValueError("invalid lighting")
        immutable_tuple(self.world.lighting.zones, LightingZone)
        immutable_tuple(self.catalog.instances, ObjectInstance)
        immutable_tuple(self.catalog.points, ResolvedPoint)
        immutable_tuple(self.catalog.slots, ResolvedSlot)
        immutable_tuple(self.catalog.blocking_tiles, Tile)
        if self.world != build_layout(
            self.world.regions, self.world.doors, self.world.lighting.zones
        ):
            raise ValueError("inconsistent derived world")
        if self.catalog != build_catalog_layout(
            self.catalog.catalog, self.catalog.instances, self.world
        ):
            raise ValueError("inconsistent derived catalog")

    @property
    def mask(self) -> Walkability:
        return derive_walkability(self.world, self.catalog)


@dataclass(frozen=True, slots=True, order=True)
class SlotKey:
    host_id: str
    slot_id: str

    def __post_init__(self) -> None:
        identifier(self.host_id)
        identifier(self.slot_id)


def soft_link(value: str | None) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError("invalid soft link")


@dataclass(frozen=True, slots=True)
class DisplayItem:
    """Metadata for an already existing item, never a new furniture instance."""

    id: str
    item_class: str
    category: Category
    owner: Owner
    movable_by: tuple[Permission, ...]
    room_representation: bool
    displayable: bool
    system_critical: bool = False
    link: str | None = None

    def __post_init__(self) -> None:
        identifier(self.id)
        identifier(self.item_class)
        if not isinstance(self.category, Category) or not isinstance(self.owner, Owner):
            raise ValueError("invalid item category/owner")
        immutable_tuple(self.movable_by, Permission)
        unique(self.movable_by)
        for value in (self.room_representation, self.displayable, self.system_critical):
            if type(value) is not bool:
                raise ValueError("item flags must be bool")
        soft_link(self.link)

    @property
    def eligible(self) -> bool:
        return (
            not self.system_critical
            and self.displayable
            and self.room_representation
            and (
                (self.category is Category.CREATION_DISPLAY and self.owner is Owner.MAPLE)
                or (self.category is Category.DECORATIVE and bool(self.movable_by))
            )
        )


@dataclass(frozen=True, slots=True)
class DisplayPlacement:
    """Current relationship candidate; inactive rows reserve nothing, not audit history."""

    id: str
    item_id: str
    slot: SlotKey
    active: bool = True
    link: str | None = None

    def __post_init__(self) -> None:
        identifier(self.id)
        identifier(self.item_id)
        if not isinstance(self.slot, SlotKey) or type(self.active) is not bool:
            raise ValueError("invalid placement relationship")
        soft_link(self.link)


@dataclass(frozen=True, slots=True)
class OwnerRemoval:
    item_id: str
    slot: SlotKey
    at: datetime

    def __post_init__(self) -> None:
        identifier(self.item_id)
        if not isinstance(self.slot, SlotKey):
            raise ValueError("invalid removal slot")
        require_utc(self.at)


@dataclass(frozen=True, slots=True)
class PlacementRecord:
    """Caller-supplied successful placement history, including later removed displays."""

    id: str
    actor: Permission
    at: datetime

    def __post_init__(self) -> None:
        identifier(self.id)
        if not isinstance(self.actor, Permission):
            raise ValueError("invalid actor")
        require_utc(self.at)


@dataclass(frozen=True, slots=True)
class PlacementPolicy:
    per_day: int = 3
    cooldown: timedelta = timedelta(days=7)

    def __post_init__(self) -> None:
        require_integer(self.per_day, "placements per day")
        if self.per_day < 0 or not isinstance(self.cooldown, timedelta):
            raise ValueError("invalid placement policy")
        if self.cooldown < timedelta(0):
            raise ValueError("negative cooldown")


@dataclass(frozen=True, slots=True)
class PlacementContext:
    snapshot: PlacementSnapshot
    items: tuple[DisplayItem, ...]
    placements: tuple[DisplayPlacement, ...]
    now: datetime
    utc_offset: timedelta
    maple: Tile
    removals: tuple[OwnerRemoval, ...] = ()
    history: tuple[PlacementRecord, ...] = ()
    policy: PlacementPolicy = PlacementPolicy()

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, PlacementSnapshot) or not isinstance(self.maple, Tile):
            raise ValueError("invalid snapshot/position")
        require_utc(self.now)
        if not isinstance(self.utc_offset, timedelta) or not (
            -timedelta(days=1) < self.utc_offset < timedelta(days=1)
        ):
            raise ValueError("invalid local UTC offset")
        if not isinstance(self.policy, PlacementPolicy):
            raise ValueError("invalid policy")
        immutable_tuple(self.items, DisplayItem)
        immutable_tuple(self.placements, DisplayPlacement)
        immutable_tuple(self.removals, OwnerRemoval)
        immutable_tuple(self.history, PlacementRecord)
        unique(tuple(item.id for item in self.items))
        unique(tuple(item.id for item in self.placements))
        unique(tuple(item.id for item in self.history))
        if any(item.at > self.now for item in self.history) or any(
            item.at > self.now for item in self.removals
        ):
            raise ValueError("future placement/removal history")
        object.__setattr__(self, "items", tuple(sorted(self.items, key=lambda item: item.id)))
        object.__setattr__(self, "placements", tuple(sorted(self.placements, key=lambda p: p.id)))
        object.__setattr__(self, "history", tuple(sorted(self.history, key=lambda p: p.id)))
        object.__setattr__(
            self,
            "removals",
            tuple(sorted(self.removals, key=lambda r: (r.at, r.item_id, r.slot))),
        )


class PlacementReason(StrEnum):
    UNKNOWN_HOST = "unknown_host"
    UNKNOWN_SLOT = "unknown_slot"
    UNKNOWN_ITEM = "unknown_item"
    INELIGIBLE_ITEM = "ineligible_item"
    CLASS_REJECTED = "class_rejected"
    HOOK_ONLY = "hook_only"
    MAPLE_FORBIDDEN = "maple_forbidden"
    NOT_MAPLE_MOVABLE = "not_maple_movable"
    DUPLICATE_ACTIVE = "duplicate_active"
    CAPACITY_FULL = "capacity_full"
    COOLDOWN = "owner_removal_cooldown"
    RATE_LIMIT = "rate_limit"
    CLOSED_REGION = "closed_region"
    INVALID_LAYOUT = "invalid_layout"
    INVALID_PLACEMENTS = "invalid_placements"
    UNREACHABLE_APPROACH = "unreachable_approach"


@dataclass(frozen=True, slots=True)
class PlacementResult:
    """Validation only: no record/event is created and no capacity is reserved."""

    reason: PlacementReason | None
    approach: Tile | None = None
    route: Route | None = None

    @property
    def accepted(self) -> bool:
        return self.reason is None


def validate_active_placements(context: PlacementContext) -> None:
    """Reject corrupt current relationships rather than derive misleading Storage."""
    items = {item.id: item for item in context.items}
    hosts = {host.id: host for host in context.snapshot.catalog.instances}
    slots = {
        SlotKey(slot.instance_id, slot.template.id): slot.template
        for slot in context.snapshot.catalog.slots
    }
    rooms = {room.id: room for room in context.snapshot.world.regions}
    occupied: dict[SlotKey, int] = {}
    displayed: set[str] = set()
    for placement in context.placements:
        if not placement.active:
            continue
        item = items.get(placement.item_id)
        slot = slots.get(placement.slot)
        host = hosts.get(placement.slot.host_id)
        if (
            item is None
            or slot is None
            or host is None
            or not item.eligible
            or item.id in hosts
            or slot.status is not SlotStatus.ACTIVE
            or item.item_class not in slot.accepts
            or rooms[host.room_id].status is not RegionStatus.OPEN
            or placement.item_id in displayed
        ):
            raise ValueError("invalid active placement")
        displayed.add(placement.item_id)
        occupied[placement.slot] = occupied.get(placement.slot, 0) + 1
        if occupied[placement.slot] > slot.capacity:
            raise ValueError("active placements exceed capacity")


def validate_structure(context: PlacementContext) -> None:
    """Revalidate even a manually replaced snapshot; prevention never invokes recovery."""
    snapshot = context.snapshot
    PlacementSnapshot(snapshot.world, snapshot.catalog)
    validate_safe_layout(snapshot.world, snapshot.catalog, context.maple)


def validate_placement(
    context: PlacementContext, item_id: str, slot_key: SlotKey, actor: Permission
) -> PlacementResult:
    """First-failure order is stable. Owner bypasses only autonomous permission/tuning."""
    identifier(item_id)
    if not isinstance(slot_key, SlotKey) or not isinstance(actor, Permission):
        raise ValueError("invalid target/actor")
    hosts = {host.id: host for host in context.snapshot.catalog.instances}
    host = hosts.get(slot_key.host_id)
    if host is None:
        return PlacementResult(PlacementReason.UNKNOWN_HOST)
    slot = next(
        (
            s.template
            for s in context.snapshot.catalog.slots
            if (s.instance_id, s.template.id) == (slot_key.host_id, slot_key.slot_id)
        ),
        None,
    )
    if slot is None:
        return PlacementResult(PlacementReason.UNKNOWN_SLOT)
    item = next((item for item in context.items if item.id == item_id), None)
    if item is None:
        return PlacementResult(PlacementReason.UNKNOWN_ITEM)
    if not item.eligible or item.id in hosts:
        return PlacementResult(PlacementReason.INELIGIBLE_ITEM)
    rooms = {room.id: room for room in context.snapshot.world.regions}
    if host.room_id not in rooms:
        return PlacementResult(PlacementReason.INVALID_LAYOUT)
    if rooms[host.room_id].status is not RegionStatus.OPEN:
        return PlacementResult(PlacementReason.CLOSED_REGION)
    if slot.status is not SlotStatus.ACTIVE:
        return PlacementResult(PlacementReason.HOOK_ONLY)
    if item.item_class not in slot.accepts:
        return PlacementResult(PlacementReason.CLASS_REJECTED)
    try:
        validate_structure(context)
    except ValueError:
        return PlacementResult(PlacementReason.INVALID_LAYOUT)
    try:
        validate_active_placements(context)
    except ValueError:
        return PlacementResult(PlacementReason.INVALID_PLACEMENTS)
    if any(p.active and p.item_id == item_id for p in context.placements):
        return PlacementResult(PlacementReason.DUPLICATE_ACTIVE)
    if sum(p.active and p.slot == slot_key for p in context.placements) >= slot.capacity:
        return PlacementResult(PlacementReason.CAPACITY_FULL)
    if actor is Permission.MAPLE:
        if not slot.maple_may_place:
            return PlacementResult(PlacementReason.MAPLE_FORBIDDEN)
        if Permission.MAPLE not in item.movable_by:
            return PlacementResult(PlacementReason.NOT_MAPLE_MOVABLE)
        if any(
            (r.item_id == item_id or r.slot == slot_key)
            and context.now - r.at < context.policy.cooldown
            for r in context.removals
        ):
            return PlacementResult(PlacementReason.COOLDOWN)
        day = local_day(context.now, context.utc_offset)
        if (
            sum(
                r.actor is Permission.MAPLE and local_day(r.at, context.utc_offset) == day
                for r in context.history
            )
            >= context.policy.per_day
        ):
            return PlacementResult(PlacementReason.RATE_LIMIT)
    approach = Tile(slot.approach.x, slot.approach.y)
    # Re-derive the mask above; never trust a caller-replaced cached mask.
    mask = validate_safe_layout(context.snapshot.world, context.snapshot.catalog, context.maple)
    path = find_route(mask, context.maple, approach)
    if path.route is None:
        return PlacementResult(PlacementReason.UNREACHABLE_APPROACH)
    return PlacementResult(None, approach, path.route)


def derive_storage(context: PlacementContext) -> tuple[DisplayItem, ...]:
    """Existing eligible objects without an active display; no inventory mutation."""
    validate_structure(context)
    validate_active_placements(context)
    displayed = {p.item_id for p in context.placements if p.active}
    hosts = {host.id for host in context.snapshot.catalog.instances}
    return tuple(
        item
        for item in context.items
        if item.eligible and item.id not in displayed and item.id not in hosts
    )
