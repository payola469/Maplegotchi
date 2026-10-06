"""Maple's room as data: interaction points, the walking graph, and routes (ADR-0027).

Pure and deterministic. Geometry uses the room's logical units (1000 x 600,
the same units the frontend draws in); the frontend reads this table from the
API instead of keeping its own anchors.

- An `InteractionPoint` is where Maple stands/sits/lies to do something: a real
  room position, a facing, a pose, and the actions allowed there. Destination
  resolution is a lookup over this table, never furniture-specific code.
- Walking follows a fixed waypoint graph. Edge lengths are declared integer
  constants (a test checks them against the geometry), so no square roots are
  computed at runtime; interpolation uses only + - * / (CLAUDE.md §5).
- A `Route` is a path with departure/arrival times. Where Maple is at any `now`
  is derived from it, so arrival needs no timer (like transient reactions, D17).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.daytime import require_utc

ROOM_WIDTH = 1000
ROOM_HEIGHT = 600
FLOOR_Y = 380  # where the back wall meets the floor

# Logical units per second. Typical walks across the room take a few seconds.
WALK_SPEED = 120


class Facing(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    FRONT = "front"  # toward the viewer
    BACK = "back"  # toward the wall / furniture


class Pose(StrEnum):
    STAND = "stand"
    WALK = "walk"
    SLEEP = "sleep"
    SIT_WRITE = "sit_write"
    SIT_MONITOR = "sit_monitor"
    READ = "read"
    REST = "rest"
    THINK = "think"


class Furniture(StrEnum):
    """Display identity of each location (ids stay as persisted, ADR-0027)."""

    BED = "bed"
    WRITING_DESK = "writing_desk"
    COMPUTER_DESK = "computer_desk"
    BOOKSHELF = "bookshelf"
    SOFA = "sofa"
    WINDOW_PLANT_CORNER = "window_plant_corner"
    OPEN_AREA = "open_area"


FURNITURE_AT: Mapping[RoomLocation, Furniture] = MappingProxyType(
    {
        RoomLocation.BED: Furniture.BED,
        RoomLocation.DESK: Furniture.WRITING_DESK,
        RoomLocation.TERMINAL: Furniture.COMPUTER_DESK,
        RoomLocation.BOOKSHELF: Furniture.BOOKSHELF,
        RoomLocation.SOFA: Furniture.SOFA,
        RoomLocation.WINDOW: Furniture.WINDOW_PLANT_CORNER,
        RoomLocation.RUG: Furniture.OPEN_AREA,
    }
)

FURNITURE_LABEL: Mapping[Furniture, str] = MappingProxyType(
    {
        Furniture.BED: "Bed",
        Furniture.WRITING_DESK: "Writing Desk",
        Furniture.COMPUTER_DESK: "Computer Desk",
        Furniture.BOOKSHELF: "Bookshelf",
        Furniture.SOFA: "Sofa",
        Furniture.WINDOW_PLANT_CORNER: "Window / Plant Corner",
        Furniture.OPEN_AREA: "Open Area",
    }
)


@dataclass(frozen=True, slots=True)
class InteractionPoint:
    id: str
    location: RoomLocation
    x: float
    y: float
    facing: Facing
    pose: Pose
    allowed_actions: tuple[Activity, ...]  # ordered, never a set

    def __post_init__(self) -> None:
        if not 0 <= self.x <= ROOM_WIDTH or not FLOOR_Y <= self.y <= ROOM_HEIGHT:
            raise ValueError(f"{self.id}: point must lie on the floor")
        if not self.allowed_actions or len(set(self.allowed_actions)) != len(self.allowed_actions):
            raise ValueError(f"{self.id}: allowed_actions must be non-empty and unique")

    @property
    def furniture(self) -> Furniture:
        return FURNITURE_AT[self.location]


_A = Activity
POINTS: tuple[InteractionPoint, ...] = (
    InteractionPoint("bed.side", RoomLocation.BED, 150, 455, Facing.RIGHT, Pose.SLEEP, (_A.SLEEP,)),
    InteractionPoint("sofa.seat", RoomLocation.SOFA, 150, 560, Facing.FRONT, Pose.REST, (_A.REST,)),
    InteractionPoint(
        "bookshelf.front", RoomLocation.BOOKSHELF, 330, 500, Facing.BACK, Pose.READ, (_A.READ,)
    ),
    InteractionPoint(
        "window.view", RoomLocation.WINDOW, 500, 470, Facing.BACK, Pose.THINK, (_A.THINK,)
    ),
    InteractionPoint(
        "writing_desk.chair", RoomLocation.DESK, 640, 470, Facing.BACK, Pose.SIT_WRITE, (_A.WRITE,)
    ),
    InteractionPoint(
        "computer_desk.chair",
        RoomLocation.TERMINAL,
        840,
        470,
        Facing.BACK,
        Pose.SIT_MONITOR,
        (_A.OBSERVE_SERVER,),
    ),
    InteractionPoint(
        "open_area.center", RoomLocation.RUG, 480, 545, Facing.FRONT, Pose.STAND, (_A.IDLE, _A.WALK)
    ),
    InteractionPoint(
        "open_area.west", RoomLocation.RUG, 400, 550, Facing.FRONT, Pose.STAND, (_A.IDLE, _A.WALK)
    ),
    InteractionPoint(
        "open_area.east", RoomLocation.RUG, 580, 550, Facing.FRONT, Pose.STAND, (_A.IDLE, _A.WALK)
    ),
)

POINT_BY_ID: Mapping[str, InteractionPoint] = MappingProxyType({p.id: p for p in POINTS})

# Lane nodes along the open floor in front of the furniture.
LANES: Mapping[str, tuple[float, float]] = MappingProxyType(
    {
        "lane.bed": (150, 520),
        "lane.bookshelf": (330, 520),
        "lane.window": (500, 520),
        "lane.desk": (640, 520),
        "lane.terminal": (840, 520),
    }
)

# Undirected edges with declared integer lengths (checked against geometry by a test).
EDGES: tuple[tuple[str, str, int], ...] = (
    ("bed.side", "lane.bed", 65),
    ("sofa.seat", "lane.bed", 40),
    ("bookshelf.front", "lane.bookshelf", 20),
    ("window.view", "lane.window", 50),
    ("writing_desk.chair", "lane.desk", 50),
    ("computer_desk.chair", "lane.terminal", 50),
    ("open_area.west", "lane.bookshelf", 76),
    ("open_area.center", "lane.window", 32),
    ("open_area.east", "lane.desk", 67),
    ("open_area.west", "open_area.center", 80),
    ("open_area.center", "open_area.east", 100),
    ("lane.bed", "lane.bookshelf", 180),
    ("lane.bookshelf", "lane.window", 170),
    ("lane.window", "lane.desk", 140),
    ("lane.desk", "lane.terminal", 200),
)


def node_xy(node: str) -> tuple[float, float]:
    if node in POINT_BY_ID:
        p = POINT_BY_ID[node]
        return (p.x, p.y)
    return LANES[node]


def _adjacency() -> Mapping[str, tuple[tuple[str, int], ...]]:
    adjacency: dict[str, list[tuple[str, int]]] = {}
    for a, b, length in EDGES:
        adjacency.setdefault(a, []).append((b, length))
        adjacency.setdefault(b, []).append((a, length))
    return MappingProxyType({k: tuple(sorted(v)) for k, v in sorted(adjacency.items())})


ADJACENCY = _adjacency()


def _validate_room() -> None:
    nodes = set(POINT_BY_ID) | set(LANES)
    if len(POINT_BY_ID) != len(POINTS) or set(POINT_BY_ID) & set(LANES):
        raise RuntimeError("room node ids must be unique")
    for a, b, length in EDGES:
        if a not in nodes or b not in nodes or length <= 0:
            raise RuntimeError(f"bad room edge {a}-{b}")
    if set(ADJACENCY) != nodes:
        raise RuntimeError("every room node must be connected")
    for activity in Activity:
        if not any(activity in p.allowed_actions for p in POINTS):
            raise RuntimeError(f"no interaction point allows {activity}")


_validate_room()


def points_for(
    activity: Activity, location: RoomLocation | None = None
) -> tuple[InteractionPoint, ...]:
    """Every point where `activity` can happen (optionally at one location), in table order."""
    return tuple(
        p
        for p in POINTS
        if activity in p.allowed_actions and (location is None or p.location is location)
    )


def canonical_point(activity: Activity, location: RoomLocation) -> InteractionPoint:
    """The first point for `activity` at `location`: where a state without an explicit point is."""
    candidates = points_for(activity, location)
    if not candidates:
        raise ValueError(f"{activity} has no interaction point at {location}")
    return candidates[0]


# ---------------------------------------------------------------- routes


@dataclass(frozen=True, slots=True)
class PathPoint:
    """A corner of a walking path. `distance` is cumulative from the path start.

    `node` is the graph node at this corner; only a path's first corner may be
    None (a reroute that starts part-way along an edge).
    """

    x: float
    y: float
    distance: float
    node: str | None

    def __post_init__(self) -> None:
        for name in ("x", "y", "distance"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise TypeError(f"{name} must be a number")
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.distance < 0:
            raise ValueError("distance must be >= 0")
        if self.node is not None and self.node not in ADJACENCY:
            raise ValueError(f"unknown room node {self.node!r}")


@dataclass(frozen=True, slots=True)
class Route:
    """Maple walking to an interaction point. The activity begins at `arrives_at`."""

    departed_at: datetime
    arrives_at: datetime
    path: tuple[PathPoint, ...]
    from_activity: Activity  # the last activity Maple actually performed

    def __post_init__(self) -> None:
        require_utc(self.departed_at, "route.departed_at")
        require_utc(self.arrives_at, "route.arrives_at")
        if not self.departed_at < self.arrives_at:
            raise ValueError("a route must arrive after it departs")
        if not isinstance(self.from_activity, Activity):
            raise TypeError("from_activity must be an Activity")
        path = self.path
        if len(path) < 2:
            raise ValueError("a route needs at least two path points")
        if path[0].distance != 0:
            raise ValueError("a route starts at distance 0")
        for i in range(1, len(path)):
            if path[i].node is None:
                raise ValueError("only the first path point may be off the graph")
            if not path[i].distance > path[i - 1].distance:
                raise ValueError("path distances must strictly increase")
        if path[-1].node not in POINT_BY_ID:
            raise ValueError("a route must end at an interaction point")

    @property
    def destination(self) -> InteractionPoint:
        node = self.path[-1].node
        if node is None:  # unreachable: __post_init__ requires a final point node
            raise ValueError("route has no destination node")
        return POINT_BY_ID[node]

    @property
    def length(self) -> float:
        return self.path[-1].distance

    def progress_at(self, now: datetime) -> float:
        """Distance walked at `now`, in [0, length]."""
        require_utc(now, "now")
        if now <= self.departed_at:
            return 0.0
        if now >= self.arrives_at:
            return self.length
        return self.length * ((now - self.departed_at) / (self.arrives_at - self.departed_at))

    def position_at(self, now: datetime) -> tuple[float, float]:
        walked = self.progress_at(now)
        for a, b in zip(self.path, self.path[1:], strict=False):
            if walked <= b.distance:
                fraction = (walked - a.distance) / (b.distance - a.distance)
                return (a.x + (b.x - a.x) * fraction, a.y + (b.y - a.y) * fraction)
        last = self.path[-1]
        return (last.x, last.y)


def travel_time(length: float) -> timedelta:
    """Walking time for `length` units, rounded up to whole milliseconds."""
    if not math.isfinite(length) or length <= 0:
        raise ValueError("length must be positive")
    return timedelta(milliseconds=math.ceil(length * 1000.0 / WALK_SPEED))


def shortest_path(start: str, goal: str) -> tuple[tuple[str, ...], float]:
    """Dijkstra over the (small) room graph; ties break on node id, so it is deterministic."""
    if start not in ADJACENCY or goal not in ADJACENCY:
        raise ValueError("unknown room node")
    best: dict[str, float] = {start: 0.0}
    previous: dict[str, str] = {}
    done: set[str] = set()
    while True:
        frontier = [(d, n) for n, d in best.items() if n not in done]
        if not frontier:
            break
        distance, node = min(frontier)
        done.add(node)
        if node == goal:
            break
        for neighbour, length in ADJACENCY[node]:
            candidate = distance + length
            if neighbour not in done and candidate < best.get(neighbour, math.inf):
                best[neighbour] = candidate
                previous[neighbour] = node
    if goal not in best:
        raise ValueError(f"no path from {start} to {goal}")
    nodes = [goal]
    while nodes[-1] != start:
        nodes.append(previous[nodes[-1]])
    return tuple(reversed(nodes)), best[goal]


@dataclass(frozen=True, slots=True)
class Whereabouts:
    """Where Maple is at an instant, in graph terms, for planning a walk from there.

    At a node: `node` set, no edge. Part-way along a path segment: the position,
    plus the segment's end node (`ahead`, distance `to_ahead`) and, if the
    segment started at a node, that node (`behind`, distance `to_behind`).
    """

    x: float
    y: float
    node: str | None = None
    ahead: str | None = None
    to_ahead: float = 0.0
    behind: str | None = None
    to_behind: float = 0.0


def whereabouts(route: Route | None, point: InteractionPoint, now: datetime) -> Whereabouts:
    """Maple's position at `now`: on `route` if still walking, else at `point`."""
    if route is None or now >= route.arrives_at:
        return Whereabouts(point.x, point.y, node=point.id)
    walked = route.progress_at(now)
    for a, b in zip(route.path, route.path[1:], strict=False):
        if walked < b.distance:
            if walked == a.distance and a.node is not None:
                return Whereabouts(a.x, a.y, node=a.node)
            x, y = route.position_at(now)
            return Whereabouts(
                x,
                y,
                ahead=b.node,
                to_ahead=b.distance - walked,
                behind=a.node,
                to_behind=walked - a.distance,
            )
    return Whereabouts(point.x, point.y, node=point.id)


def plan_route(
    start: Whereabouts,
    destination: InteractionPoint,
    departed_at: datetime,
    from_activity: Activity,
) -> Route | None:
    """The shortest walk from `start` to `destination`; None if Maple is already there."""
    require_utc(departed_at, "departed_at")
    if start.node == destination.id:
        return None
    if start.node is not None:
        nodes, _ = shortest_path(start.node, destination.id)
        corners = [PathPoint(start.x, start.y, 0.0, start.node)]
        offset = 0.0
        rest = nodes[1:]
    else:
        # Part-way along a segment: continue to the node ahead, or turn back to the
        # node behind if that is strictly shorter overall.
        options: list[tuple[float, int, str, float]] = []
        if start.ahead is not None:
            _, length = shortest_path(start.ahead, destination.id)
            options.append((start.to_ahead + length, 0, start.ahead, start.to_ahead))
        if start.behind is not None:
            _, length = shortest_path(start.behind, destination.id)
            options.append((start.to_behind + length, 1, start.behind, start.to_behind))
        if not options:
            raise ValueError("whereabouts off the graph need a node ahead or behind")
        _, _, via, offset = min(options)
        nodes, _ = shortest_path(via, destination.id)
        corners = [PathPoint(start.x, start.y, 0.0, None)]
        rest = nodes
        if offset == 0.0:  # exactly on a node after all
            corners = [PathPoint(start.x, start.y, 0.0, via)]
            rest = nodes[1:]
    distance = offset
    previous = corners[0].node
    for node in rest:
        if previous is not None:
            distance += _edge_length(previous, node)
        x, y = node_xy(node)
        corners.append(PathPoint(x, y, distance, node))
        previous = node
    path = tuple(corners)
    return Route(
        departed_at=departed_at,
        arrives_at=departed_at + travel_time(path[-1].distance),
        path=path,
        from_activity=from_activity,
    )


def _edge_length(a: str, b: str) -> int:
    for neighbour, length in ADJACENCY[a]:
        if neighbour == b:
            return length
    raise ValueError(f"{a} and {b} are not adjacent")
