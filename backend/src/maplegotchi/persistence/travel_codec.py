"""Pure isolated format-1 Travel codec; synthetic budgets only, no runtime admission."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from itertools import pairwise
from typing import Literal, NoReturn, cast

from maplegotchi.core.daytime import require_utc
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.movement import EdgeStart, Entry, Travel
from maplegotchi.core.world.pathfinding import Route, Waypoint, distance
from maplegotchi.core.world.walkability import Walkability

Category = Literal[
    "json",
    "canonical",
    "fields",
    "version",
    "integer",
    "route",
    "entry",
    "walkability",
    "origin",
    "timing",
    "travel",
    "bytes",
    "waypoints",
    "work",
]


class V11TravelFormatError(ValueError):
    """Fixed category only; stored content never appears in the message."""

    def __init__(self, category: Category) -> None:
        super().__init__(category)


# STEP 220 synthetic-test policy only, never production configuration.
MAX_BYTES = 65_536
MAX_WAYPOINTS = 2_048
MAX_WORK = 32_768


def _byte_gate(text: str) -> None:
    """Count actual UTF-8 bytes before JSON parsing; lone surrogates refuse."""
    try:
        if len(text.encode("utf-8")) > MAX_BYTES:
            raise V11TravelFormatError("bytes")
    except UnicodeError:
        raise V11TravelFormatError("json") from None


def _waypoint_gate(count: int) -> None:
    if count > MAX_WAYPOINTS:
        raise V11TravelFormatError("waypoints")


def _work_gate(count: int) -> None:
    if count > MAX_WORK:
        raise V11TravelFormatError("work")


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise V11TravelFormatError("fields")
        result[key] = value
    return result


def _constant(value: str) -> NoReturn:
    raise V11TravelFormatError("json")


def _canonical(value: object) -> str:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
    except (ValueError, TypeError, RecursionError):
        raise V11TravelFormatError("json") from None


def _fields(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or value.keys() != keys:
        raise V11TravelFormatError("fields")
    return cast(dict[str, object], value)


def _integer(value: object) -> int:
    if type(value) is not int:
        raise V11TravelFormatError("integer")
    return value


def _array(value: object, size: int) -> list[object]:
    if not isinstance(value, list) or len(value) != size:
        raise V11TravelFormatError("fields")
    return cast(list[object], value)


def _tile(value: object) -> Tile:
    x, y = _array(value, 2)
    return Tile(_integer(x), _integer(y))


def _travel(value: object, departed_at: datetime) -> Travel:
    data = _fields(value, {"format_version", "ms_per_step", "waypoints", "entry"})
    if _integer(data["format_version"]) != 1:
        raise V11TravelFormatError("version")
    speed = _integer(data["ms_per_step"])
    if speed <= 0:
        raise V11TravelFormatError("integer")
    points = data["waypoints"]
    if not isinstance(points, list):
        raise V11TravelFormatError("fields")
    _waypoint_gate(len(points))
    try:
        waypoints = []
        for point in points:
            x, y, steps = _array(point, 3)
            waypoints.append(Waypoint(_integer(x), _integer(y), _integer(steps)))
        route = Route(tuple(waypoints))
    except V11TravelFormatError:
        raise
    except (ValueError, TypeError):
        raise V11TravelFormatError("route") from None
    entry = None
    if data["entry"] is not None:
        raw = _fields(data["entry"], {"a", "b", "progress_us", "endpoint"})
        try:
            start = EdgeStart(
                _tile(raw["a"]), _tile(raw["b"]), _integer(raw["progress_us"]), speed * 1000
            )
            entry = Entry(start, _tile(raw["endpoint"]))
            if entry.endpoint != route.origin:
                raise V11TravelFormatError("entry")
        except V11TravelFormatError:
            raise
        except (ValueError, TypeError):
            raise V11TravelFormatError("entry") from None
    try:
        return Travel(route, departed_at, speed, entry)
    except (ValueError, TypeError):
        raise V11TravelFormatError("timing") from None


def _route_tiles(route: Route) -> Iterator[Tile]:
    """Match Route.tiles() for a validated route, with constant traversal state."""
    yield route.origin
    for a, b in pairwise(route.waypoints):
        length = distance(a.tile, b.tile)
        dx, dy = (b.tx - a.tx) // length, (b.ty - a.ty) // length
        for step in range(1, length + 1):
            yield Tile(a.tx + dx * step, a.ty + dy * step)


def _walkable(travel: Travel, walkability: Walkability) -> None:
    if not isinstance(walkability, Walkability):
        raise V11TravelFormatError("walkability")
    allowed = frozenset(walkability.walkable)
    # Work counts each origin/edge tile generated/examined, including repeated
    # visits, plus both Entry endpoint examinations. No unique-tile shortcut.
    # Check the next unit BEFORE asking the generator to create another tile.
    work = 0
    tiles = _route_tiles(travel.route)
    expected = 1 + travel.route.waypoints[-1].cumulative_steps
    for _ in range(expected):
        _work_gate(work + 1)
        tile = next(tiles)
        work += 1
        if tile not in allowed:
            raise V11TravelFormatError("walkability")
    if travel.entry is not None:
        for tile in (travel.entry.start.a, travel.entry.start.b):
            _work_gate(work + 1)
            work += 1
            if tile not in allowed:
                raise V11TravelFormatError("walkability")


def _arrival(travel: Travel) -> datetime:
    try:
        return travel.arrives_at
    except (OverflowError, ValueError):
        raise V11TravelFormatError("timing") from None


def encode_travel_path(travel: Travel, *, walkability: Walkability) -> str:
    """Validate and encode an immutable Travel; times stay outside the JSON."""
    if not isinstance(travel, Travel):
        raise V11TravelFormatError("travel")
    _waypoint_gate(len(travel.route.waypoints))
    entry = travel.entry
    data = {
        "format_version": 1,
        "ms_per_step": travel.ms_per_step,
        "waypoints": [[p.tx, p.ty, p.cumulative_steps] for p in travel.route.waypoints],
        "entry": None
        if entry is None
        else {
            "a": [entry.start.a.tx, entry.start.a.ty],
            "b": [entry.start.b.tx, entry.start.b.ty],
            "progress_us": entry.start.progress_us,
            "endpoint": [entry.endpoint.tx, entry.endpoint.ty],
        },
    }
    validated = _travel(data, travel.departed_at)
    # step_us is derived in JSON; refusing a mismatched input avoids silent repair.
    if validated != travel:
        raise V11TravelFormatError("entry")
    _walkable(validated, walkability)
    _arrival(validated)
    text = _canonical(data)
    _byte_gate(text)
    return text


def decode_travel_path(
    text: str,
    *,
    departed_at: datetime,
    route_arrives_at: datetime,
    activity_started_at: datetime,
    stored_origin: Tile,
    walkability: Walkability,
) -> Travel:
    """Refuse noncanonical text and inconsistent UTC columns, without repair.

    The caller supplies parsed UTC datetimes and the stored integer origin Tile.
    No evaluation time is needed: pending and completed Travel remain reconstructible.
    """
    if type(text) is not str:
        raise V11TravelFormatError("json")
    _byte_gate(text)
    try:
        data: object = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except V11TravelFormatError:
        raise
    except (ValueError, TypeError, RecursionError):
        raise V11TravelFormatError("json") from None
    travel = _travel(data, departed_at)
    if _canonical(data) != text:
        raise V11TravelFormatError("canonical")
    if not isinstance(stored_origin, Tile) or travel.route.origin != stored_origin:
        raise V11TravelFormatError("origin")
    _walkable(travel, walkability)
    try:
        require_utc(route_arrives_at)
        require_utc(activity_started_at)
    except (ValueError, TypeError):
        raise V11TravelFormatError("timing") from None
    if _arrival(travel) != route_arrives_at or route_arrives_at != activity_started_at:
        raise V11TravelFormatError("timing")
    return travel
