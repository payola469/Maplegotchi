"""Isolated capability resolution; no Director transitions, persistence or movement execution."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Final

from maplegotchi.core.activities import Activity
from maplegotchi.core.memory import Memory, MemoryKind, MemoryStatus, Tier
from maplegotchi.core.rng import RngState, RngStream
from maplegotchi.core.world.catalog import (
    Capability,
    Catalog,
    CatalogLayout,
    ObjectInstance,
    PointTemplate,
    ResolvedPoint,
    ResolvedSlot,
    SlotTemplate,
    blocking_offsets,
    build_catalog_layout,
    identifier,
    immutable_tuple,
    rotate_direction,
    rotate_vector,
    unique,
    world_approach,
)
from maplegotchi.core.world.coordinates import Tile, require_integer
from maplegotchi.core.world.layout import WorldLayout, build_layout
from maplegotchi.core.world.lighting import LightingPartition, LightingZone
from maplegotchi.core.world.model import Door, Region, RegionKind, RegionStatus
from maplegotchi.core.world.movement import EdgeStart, Travel, reroute
from maplegotchi.core.world.pathfinding import Route, find_route
from maplegotchi.core.world.walkability import Walkability, derive_walkability, validate_safe_layout

REQUIREMENTS_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class ActivityRequirement:
    activity: Activity
    alternatives: tuple[tuple[Capability, ...], ...]
    tiers: tuple[RegionKind, ...]
    other_tier: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.activity, Activity):
            raise ValueError("expected Activity")
        immutable_tuple(self.alternatives, tuple)
        immutable_tuple(self.tiers, RegionKind)
        unique(self.tiers)
        if not self.alternatives or not self.tiers:
            raise ValueError("empty requirement/tiers")
        for group in self.alternatives:
            immutable_tuple(group, Capability)
            unique(group)
            if not group:
                raise ValueError("empty requirement group")
        if self.other_tier is not None:
            require_integer(self.other_tier, "other tier")
            if self.other_tier < len(self.tiers):
                raise ValueError("invalid other tier")

    def room_tier(self, kind: RegionKind) -> int | None:
        return self.tiers.index(kind) if kind in self.tiers else self.other_tier


# Versioned activity -> capabilities -> room kinds, never furniture types or identities.
REQUIREMENTS: Final = (
    ActivityRequirement(Activity.IDLE, ((Capability.OPEN_FLOOR,),), (RegionKind.HALL,)),
    ActivityRequirement(Activity.WALK, ((Capability.OPEN_FLOOR,),), (RegionKind.HALL,)),
    ActivityRequirement(Activity.SLEEP, ((Capability.SLEEP_SPOT,),), (RegionKind.BEDROOM,)),
    ActivityRequirement(
        Activity.READ, ((Capability.READING_SPOT,),), (RegionKind.LIBRARY, RegionKind.LIVING)
    ),
    ActivityRequirement(Activity.WRITE, ((Capability.WRITING_SURFACE,),), (RegionKind.STUDIO,)),
    ActivityRequirement(
        Activity.OBSERVE_SERVER,
        ((Capability.SYSTEM_CONSOLE,), (Capability.COMPUTER,)),
        (RegionKind.SYSTEM, RegionKind.STUDIO),
    ),
    ActivityRequirement(Activity.REST, ((Capability.SEAT_SOFT,),), (RegionKind.LIVING,)),
    ActivityRequirement(
        Activity.THINK,
        ((Capability.WINDOW_VIEW,), (Capability.QUIET_SPOT,)),
        (RegionKind.LIVING, RegionKind.LIBRARY),
        2,
    ),
)


def requirement_for(activity: Activity) -> ActivityRequirement:
    if not isinstance(activity, Activity):
        raise ValueError("expected Activity")
    return next(item for item in REQUIREMENTS if item.activity is activity)


@dataclass(frozen=True, slots=True, order=True)
class PointKey:
    instance_id: str
    point_id: str

    def __post_init__(self) -> None:
        identifier(self.instance_id)
        identifier(self.point_id)


@dataclass(frozen=True, slots=True)
class InstanceUse:
    instance_id: str
    usable: bool

    def __post_init__(self) -> None:
        identifier(self.instance_id)
        if type(self.usable) is not bool:
            raise ValueError("usable must be bool")


@dataclass(frozen=True, slots=True)
class PointUse:
    point: PointKey
    available: bool = True
    occupied: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.point, PointKey) or type(self.available) is not bool:
            raise ValueError("invalid point availability")
        require_integer(self.occupied, "occupied")
        if self.occupied < 0:
            raise ValueError("negative occupancy")


def point_key(point: ResolvedPoint) -> PointKey:
    return PointKey(point.instance_id, point.template.id)


@dataclass(frozen=True, slots=True)
class ResolutionSnapshot:
    """Validated geometry plus transient use inputs; canonical mask derived internally.

    Closed-room metadata can remain in a transient snapshot but is never eligible.
    This is not saved-layout acceptance: use validate_activity_coverage for that.
    """

    world: WorldLayout
    catalog: CatalogLayout
    instances: tuple[InstanceUse, ...] = ()
    points: tuple[PointUse, ...] = ()
    mask: Walkability = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.world, WorldLayout) or not isinstance(self.catalog, CatalogLayout):
            raise ValueError("expected validated world/catalog layout")
        if not isinstance(self.world.lighting, LightingPartition):
            raise ValueError("expected LightingPartition")
        immutable_tuple(self.world.lighting.zones, LightingZone)
        immutable_tuple(self.world.regions, Region)
        immutable_tuple(self.world.doors, Door)
        if not isinstance(self.catalog.catalog, Catalog):
            raise ValueError("expected Catalog")
        if self.world != build_layout(
            self.world.regions, self.world.doors, self.world.lighting.zones
        ):
            raise ValueError("inconsistent derived world metadata")
        immutable_tuple(self.instances, InstanceUse)
        immutable_tuple(self.points, PointUse)
        unique(tuple(item.instance_id for item in self.instances))
        if len({item.point for item in self.points}) != len(self.points):
            raise ValueError("duplicate point use")
        layout = self.catalog
        immutable_tuple(layout.instances, ObjectInstance)
        immutable_tuple(layout.points, ResolvedPoint)
        immutable_tuple(layout.slots, ResolvedSlot)
        immutable_tuple(layout.blocking_tiles, Tile)
        if any(not isinstance(point.template, PointTemplate) for point in layout.points) or any(
            not isinstance(slot.template, SlotTemplate) for slot in layout.slots
        ):
            raise ValueError("invalid resolved point/slot template")
        unique(tuple(item.id for item in layout.instances))
        hosts = {item.id: item for item in layout.instances}
        slot_keys = tuple((slot.instance_id, slot.template.id) for slot in layout.slots)
        if len(set(slot_keys)) != len(slot_keys) or any(host not in hosts for host, _ in slot_keys):
            raise ValueError("duplicate or unknown slot host")
        rooms = {room.id: room for room in self.world.regions}
        expected_points: list[ResolvedPoint] = []
        expected_blocks: list[Tile] = []
        for host in layout.instances:
            item = layout.catalog.get(host.type_id)
            if host.room_id not in rooms or host.state not in item.states:
                raise ValueError("unknown instance room/state")
            for template in item.points:
                expected_points.append(
                    ResolvedPoint(
                        host.id,
                        replace(
                            template,
                            approach=world_approach(template.approach, item, host),
                            facing=rotate_direction(template.facing, host.orientation),
                            occupy=rotate_vector(template.occupy, host.orientation)
                            if template.occupy is not None
                            else None,
                            occupy_direction=rotate_direction(
                                template.occupy_direction, host.orientation
                            ),
                        ),
                    )
                )
            expected_blocks.extend(
                Tile(host.origin.tx + offset.x, host.origin.ty + offset.y)
                for offset in blocking_offsets(item, host.orientation)
            )

        def sort_point(p: ResolvedPoint | ResolvedSlot) -> tuple[str, str]:
            return p.instance_id, p.template.id

        if tuple(sorted(layout.points, key=sort_point)) != tuple(
            sorted(expected_points, key=sort_point)
        ) or sorted(layout.blocking_tiles, key=lambda t: (t.ty, t.tx)) != sorted(
            expected_blocks, key=lambda t: (t.ty, t.tx)
        ):
            raise ValueError("inconsistent derived catalog metadata")
        open_hosts = tuple(
            host for host in layout.instances if rooms[host.room_id].status is RegionStatus.OPEN
        )
        rebuilt = build_catalog_layout(layout.catalog, open_hosts, self.world)
        open_ids = {host.id for host in open_hosts}
        if tuple(
            sorted((p for p in layout.slots if p.instance_id in open_ids), key=sort_point)
        ) != (rebuilt.slots):
            raise ValueError("inconsistent derived slot metadata")
        capacities = {point_key(p): p.template.capacity for p in layout.points}
        if any(item.instance_id not in hosts for item in self.instances) or any(
            item.point not in capacities or item.occupied > capacities[item.point]
            for item in self.points
        ):
            raise ValueError("unknown use reference or excess occupancy")
        object.__setattr__(self, "mask", derive_walkability(self.world, layout))


@dataclass(frozen=True, slots=True)
class AcceptedPointPreference:
    """Caller-explicit association, supported only by an accepted ADR-0030 memory."""

    point: PointKey
    memory: Memory

    def __post_init__(self) -> None:
        if not isinstance(self.point, PointKey) or not isinstance(self.memory, Memory):
            raise ValueError("invalid preference association")
        if (
            self.memory.kind is not MemoryKind.PREFERENCE
            or self.memory.status is not MemoryStatus.ACCEPTED
            or self.memory.tier is not Tier.LONG_TERM
        ):
            raise ValueError("preference must be accepted long-term evidence")


@dataclass(frozen=True, slots=True)
class DecisionContext:
    rng: RngState
    current_point: PointKey | None = None
    preferences: tuple[AcceptedPointPreference, ...] = ()
    draw_offset: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.rng, RngState) or (
            self.current_point is not None and not isinstance(self.current_point, PointKey)
        ):
            raise ValueError("invalid decision context")
        immutable_tuple(self.preferences, AcceptedPointPreference)
        if len({item.point for item in self.preferences}) != len(self.preferences):
            raise ValueError("duplicate point preference")
        require_integer(self.draw_offset, "draw offset")
        if self.draw_offset < 0:
            raise ValueError("negative draw offset")


@dataclass(frozen=True, slots=True)
class Score:
    room_tier: int
    path_steps: int
    sticky: int
    preference: int

    def __post_init__(self) -> None:
        for value in (self.room_tier, self.path_steps, self.sticky, self.preference):
            require_integer(value, "score input")
        if min(self.room_tier, self.path_steps) < 0 or any(
            value not in (0, 1) for value in (self.sticky, self.preference)
        ):
            raise ValueError("invalid score input")

    @property
    def total(self) -> int:
        return 1000 * self.room_tier + self.path_steps - 50 * self.sticky - 200 * self.preference


@dataclass(frozen=True, slots=True)
class Candidate:
    point: ResolvedPoint
    route: Route
    score: Score

    @property
    def key(self) -> PointKey:
        return point_key(self.point)

    @property
    def approach(self) -> Tile:
        return self.route.destination


@dataclass(frozen=True, slots=True)
class Resolution:
    activity: Activity
    candidates: tuple[Candidate, ...]
    selected: Candidate | None
    tied: tuple[PointKey, ...]
    decision_draws: int

    @property
    def error(self) -> str | None:
        return "no_candidate" if self.selected is None else None


def _providers(
    activity: Activity, snapshot: ResolutionSnapshot
) -> tuple[tuple[ResolvedPoint, int], ...]:
    """Shared capability/admission filters, independent of movement origin."""
    requirement = requirement_for(activity)
    rooms = {room.id: room for room in snapshot.world.regions}
    hosts = {host.id: host for host in snapshot.catalog.instances}
    use = {item.instance_id: item.usable for item in snapshot.instances}
    availability = {item.point: item for item in snapshot.points}
    result: list[tuple[ResolvedPoint, int]] = []
    for point in snapshot.catalog.points:
        host = hosts[point.instance_id]
        room = rooms[host.room_id]
        tier = requirement.room_tier(room.kind)
        key = point_key(point)
        status = availability.get(key, PointUse(key))
        if (
            room.status is not RegionStatus.OPEN
            or tier is None
            or not use.get(host.id, host.state == "default")
            or not status.available
            or status.occupied >= point.template.capacity
            or not any(
                all(capability in point.template.provides for capability in group)
                for group in requirement.alternatives
            )
        ):
            continue
        result.append((point, tier))
    return tuple(result)


def candidates_for(
    activity: Activity, snapshot: ResolutionSnapshot, position: Tile, context: DecisionContext
) -> tuple[Candidate, ...]:
    """Canonical score ordering; no RNG draw, mutation, recovery or type-name inference."""
    if not isinstance(snapshot, ResolutionSnapshot) or not isinstance(position, Tile):
        raise ValueError("expected ResolutionSnapshot and Tile")
    if not isinstance(context, DecisionContext):
        raise ValueError("expected DecisionContext")
    preferred = {item.point for item in context.preferences}
    result: list[Candidate] = []
    for point, tier in _providers(activity, snapshot):
        key = point_key(point)
        target = Tile(point.template.approach.x, point.template.approach.y)
        route = find_route(snapshot.mask, position, target).route
        if route is not None:
            result.append(
                Candidate(
                    point,
                    route,
                    Score(
                        tier,
                        route.total_steps,
                        int(key == context.current_point),
                        int(key in preferred),
                    ),
                )
            )
    return tuple(sorted(result, key=lambda item: (item.score.total, item.key)))


@dataclass(frozen=True, slots=True)
class UrgentCandidate:
    point: ResolvedPoint
    travel: Travel
    score: int

    @property
    def key(self) -> PointKey:
        return point_key(self.point)


@dataclass(frozen=True, slots=True)
class UrgentResolution:
    candidates: tuple[UrgentCandidate, ...]
    selected: UrgentCandidate | None
    decision_draws: int


def resolve_urgent(
    activity: Activity,
    snapshot: ResolutionSnapshot,
    previous: Travel,
    now: datetime,
    context: DecisionContext,
) -> UrgentResolution:
    """STEP249 exact cost; endpoint path choice stays inside existing reroute.

    Enumerate providers without inventing a Tile origin. A mid-edge plan is not
    an occupied interaction point, so stickiness is zero. One decision draw at
    offset zero only for equal best scores; caller atomically owns its counter.
    """
    if context.draw_offset != 0:
        raise ValueError("urgent decision offset must be zero")
    current = previous.current_at(now)
    preferred = {item.point for item in context.preferences}
    result: list[UrgentCandidate] = []
    for point, tier in _providers(activity, snapshot):
        target = Tile(point.template.approach.x, point.template.approach.y)
        travel = reroute(snapshot.mask, previous, target, now).travel
        if travel is None:
            continue
        key = point_key(point)
        sticky = int(not isinstance(current, EdgeStart) and key == context.current_point)
        weighted = Score(tier, travel.route.total_steps, sticky, int(key in preferred))
        score = weighted.total * travel.step_us + (travel.entry.duration_us if travel.entry else 0)
        result.append(UrgentCandidate(point, travel, score))
    ordered = tuple(sorted(result, key=lambda item: (item.score, item.key)))
    if not ordered:
        return UrgentResolution((), None, 0)
    tied = tuple(item for item in ordered if item.score == ordered[0].score)
    selected = tied[0]
    if len(tied) > 1:
        rng = RngStream(context.rng.seed_hex, "decision", context.rng.decision_counter + 1)
        selected = tied[rng.randint(0, len(tied) - 1)]
    return UrgentResolution(ordered, selected, int(len(tied) > 1))


def resolve(
    activity: Activity, snapshot: ResolutionSnapshot, position: Tile, context: DecisionContext
) -> Resolution:
    candidates = candidates_for(activity, snapshot, position, context)
    if not candidates:
        return Resolution(activity, (), None, (), 0)
    tied = tuple(item for item in candidates if item.score.total == candidates[0].score.total)
    selected = tied[0]
    if len(tied) > 1:
        rng = RngStream(context.rng.seed_hex, "decision", context.rng.decision_counter + 1)
        for _ in range(context.draw_offset):
            rng.random()
        selected = tied[rng.randint(0, len(tied) - 1)]
    return Resolution(
        activity, candidates, selected, tuple(item.key for item in tied), int(len(tied) > 1)
    )


def allowed_activities(
    snapshot: ResolutionSnapshot, position: Tile, context: DecisionContext
) -> tuple[Activity, ...]:
    return tuple(
        activity for activity in Activity if candidates_for(activity, snapshot, position, context)
    )


def validate_activity_coverage(snapshot: ResolutionSnapshot) -> None:
    """Reusable S9 saved-layout gate, after existing prevention checks; never recovery."""
    if not isinstance(snapshot, ResolutionSnapshot):
        raise ValueError("expected ResolutionSnapshot")
    mask = validate_safe_layout(snapshot.world, snapshot.catalog)
    if mask.safe_tile is None:
        raise ValueError("S9: missing safe origin")
    context = DecisionContext(RngState("00" * 32))  # eligibility is RNG-free
    missing = tuple(
        activity
        for activity in Activity
        if not candidates_for(activity, snapshot, mask.safe_tile, context)
    )
    if missing:
        raise ValueError("S9: no reachable usable provider for " + ", ".join(missing))
