"""Explicit development/fixture projection only; no production caller or state transition."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from maplegotchi.core.activities import Activity
from maplegotchi.core.daytime import DayPhase, require_utc
from maplegotchi.core.goals import Goal
from maplegotchi.core.room import (
    ADJACENCY,
    POINT_BY_ID,
    Facing,
    InteractionPoint,
    PathPoint,
    Pose,
    Route,
    node_xy,
    shortest_path,
)
from maplegotchi.core.state import Expression, Needs, Reaction
from maplegotchi.core.tasks import Task
from maplegotchi.core.world.catalog import (
    Capability,
    CatalogLayout,
    PointPose,
    ResolvedPoint,
    build_catalog_layout,
    identifier,
    immutable_tuple,
)
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.layout import WorldLayout, build_layout
from maplegotchi.core.world.lighting import LightingPartition, LightingZone
from maplegotchi.core.world.model import Door, Region, RegionStatus
from maplegotchi.core.world.movement import Travel
from maplegotchi.core.world.walkability import Walkability, derive_walkability


@dataclass(frozen=True, slots=True)
class PointRef:
    instance_id: str
    point_id: str

    def __post_init__(self) -> None:
        identifier(self.instance_id)
        identifier(self.point_id)


@dataclass(frozen=True, slots=True)
class DevelopmentWorld:
    """Explicit validated canonical inputs, never loaded or activated by projection."""

    world: WorldLayout
    catalog: CatalogLayout
    mask: Walkability = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.world, WorldLayout) or not isinstance(self.catalog, CatalogLayout):
            raise ValueError("projection requires explicit world/catalog inputs")
        immutable_tuple(self.world.regions, Region)
        immutable_tuple(self.world.doors, Door)
        if not isinstance(self.world.lighting, LightingPartition):
            raise ValueError("projection: invalid lighting partition")
        immutable_tuple(self.world.lighting.zones, LightingZone)
        rebuilt = build_layout(self.world.regions, self.world.doors, self.world.lighting.zones)
        if rebuilt != self.world:
            raise ValueError("projection: inconsistent world derivations")
        if (
            build_catalog_layout(self.catalog.catalog, self.catalog.instances, rebuilt)
            != self.catalog
        ):
            raise ValueError("projection: inconsistent catalog derivations")
        object.__setattr__(self, "mask", derive_walkability(rebuilt, self.catalog))


@dataclass(frozen=True, slots=True)
class Presentation:
    """Caller-supplied facts, not independently inferred behavior or stored world state."""

    activity: Activity
    started_at: datetime
    until: datetime
    needs: Needs
    reaction: Reaction | None
    expression: Expression
    pose: Pose | PointPose
    day_phase: DayPhase
    status: str
    goal: Goal | None = None
    task: Task | None = None

    def __post_init__(self) -> None:
        require_utc(self.started_at, "activity start")
        require_utc(self.until, "activity end")
        if self.until < self.started_at:
            raise ValueError("projection: activity end precedes start")
        for value, expected in (
            (self.activity, Activity),
            (self.needs, Needs),
            (self.expression, Expression),
            (self.day_phase, DayPhase),
            (self.status, str),
        ):
            if not isinstance(value, expected):
                raise ValueError("projection: invalid presentation field")
        if not isinstance(self.pose, Pose | PointPose):
            raise ValueError("projection: invalid pose class")
        for optional, optional_type in (
            (self.reaction, Reaction),
            (self.goal, Goal),
            (self.task, Task),
        ):
            if optional is not None and not isinstance(optional, optional_type):
                raise ValueError("projection: invalid optional presentation field")
        if self.task is not None and not self.task.fits(self.activity):
            raise ValueError("projection: task/activity mismatch")


@dataclass(frozen=True, slots=True)
class LegacyProjection:
    presentation: Presentation
    point: InteractionPoint
    route: Route | None
    position: tuple[float, float]
    facing: Facing


def _source(context: DevelopmentWorld, reference: PointRef) -> ResolvedPoint:
    if not isinstance(context, DevelopmentWorld) or not isinstance(reference, PointRef):
        raise ValueError("projection: expected explicit context and point reference")
    host = next(
        (item for item in context.catalog.instances if item.id == reference.instance_id), None
    )
    point = next(
        (
            item
            for item in context.catalog.points
            if item.instance_id == reference.instance_id and item.template.id == reference.point_id
        ),
        None,
    )
    if host is None or point is None:
        raise ValueError("projection: unknown source point")
    room = next(item for item in context.world.regions if item.id == host.room_id)
    if room.status is not RegionStatus.OPEN:
        raise ValueError("projection: closed-room point has no legacy mapping")
    if host.state != "default":
        raise ValueError("projection: unavailable source instance")
    approach = point.template.approach
    if Tile(approach.x, approach.y) not in context.mask.walkable:
        raise ValueError("projection: source approach is not walkable")
    return point


def project_point(
    context: DevelopmentWorld, reference: PointRef, activity: Activity
) -> InteractionPoint:
    """T7/S14: capability expansion for read/think, exact named mappings otherwise."""
    point = _source(context, reference)
    if not isinstance(activity, Activity):
        raise ValueError("projection: expected Activity")
    provides = point.template.provides
    target: str | None = None
    if activity is Activity.READ and Capability.READING_SPOT in provides:
        target = "bookshelf.front"
    elif activity is Activity.THINK and (
        Capability.WINDOW_VIEW in provides or Capability.QUIET_SPOT in provides
    ):
        target = "window.view"
    else:
        named = (
            (Activity.SLEEP, "bed.bedroom", "sleep", Capability.SLEEP_SPOT, "bed.side"),
            (Activity.REST, "sofa.living", "seat", Capability.SEAT_SOFT, "sofa.seat"),
            (
                Activity.WRITE,
                "desk.writing",
                "chair",
                Capability.WRITING_SURFACE,
                "writing_desk.chair",
            ),
            (
                Activity.OBSERVE_SERVER,
                "desk.computer",
                "operator",
                Capability.COMPUTER,
                "computer_desk.chair",
            ),
        )
        for action, instance, local, capability, legacy in named:
            if (activity, reference.instance_id, reference.point_id) == (action, instance, local):
                if capability in provides:
                    target = legacy
        if activity in (Activity.IDLE, Activity.WALK) and reference.point_id == "idle":
            halls = (
                ("idle.hall_west", "open_area.west"),
                ("idle.hall_center", "open_area.center"),
                ("idle.hall_east", "open_area.east"),
            )
            for instance, legacy in halls:
                if reference.instance_id == instance and Capability.OPEN_FLOOR in provides:
                    target = legacy
    if target is None:
        raise ValueError("projection: unmapped source point/activity")
    legacy_point = POINT_BY_ID[target]
    if activity not in legacy_point.allowed_actions:
        raise ValueError("S14: legacy target does not allow activity")
    return legacy_point


def _approach(context: DevelopmentWorld, reference: PointRef) -> Tile:
    approach = _source(context, reference).template.approach
    return Tile(approach.x, approach.y)


def _project_route(
    context: DevelopmentWorld,
    destination: PointRef,
    activity: Activity,
    travel: Travel,
    origin: PointRef,
    from_activity: Activity,
) -> Route | None:
    if not isinstance(travel, Travel):
        raise ValueError("projection: expected canonical Travel")
    if travel.entry is not None:
        raise ValueError("projection: mid-edge origin has no unambiguous legacy anchor")
    if travel.route.destination != _approach(context, destination):
        raise ValueError("projection: route destination disagrees with point")
    if travel.route.origin != _approach(context, origin):
        raise ValueError("projection: route origin disagrees with point")
    allowed = frozenset(context.mask.walkable)
    if any(tile not in allowed for tile in travel.route.tiles()):
        raise ValueError("projection: route traverses forbidden cells")
    start = project_point(context, origin, from_activity)
    end = project_point(context, destination, activity)
    if travel.route.total_steps == 0:
        if start.id != end.id:
            raise ValueError("projection: zero-step route has different legacy anchors")
        return None
    if start.id == end.id:
        raise ValueError("projection: nonzero route collapses to one legacy anchor")
    nodes, _ = shortest_path(start.id, end.id)
    distance = 0
    path = [PathPoint(start.x, start.y, 0, start.id)]
    for index, b in enumerate(nodes[1:]):
        a = nodes[index]
        distance += next(length for neighbor, length in ADJACENCY[a] if neighbor == b)
        x, y = node_xy(b)
        path.append(PathPoint(x, y, distance, b))
    return Route(travel.departed_at, travel.arrives_at, tuple(path), from_activity)


def project(
    context: DevelopmentWorld,
    destination: PointRef,
    presentation: Presentation,
    now: datetime,
    *,
    travel: Travel | None = None,
    origin: PointRef | None = None,
    from_activity: Activity | None = None,
) -> LegacyProjection:
    """Project explicitly supplied facts; never emit events, change input or restart travel."""
    require_utc(now, "projection time")
    if not isinstance(presentation, Presentation):
        raise ValueError("projection: expected immutable presentation")
    point = project_point(context, destination, presentation.activity)
    route = None
    if travel is None:
        if origin is not None or from_activity is not None:
            raise ValueError("projection: origin metadata without travel")
        if now < presentation.started_at:
            raise ValueError("projection: stationary activity has not started")
    else:
        if origin is None or from_activity is None:
            raise ValueError("projection: travel requires explicit origin semantics")
        if not isinstance(travel, Travel) or presentation.started_at != travel.arrives_at:
            raise ValueError("projection: activity must start at canonical arrival")
        route = _project_route(
            context, destination, presentation.activity, travel, origin, from_activity
        )
    position = route.position_at(now) if route is not None else (point.x, point.y)
    return LegacyProjection(presentation, point, route, position, point.facing)
