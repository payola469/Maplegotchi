"""Flat deterministic A* over the canonical mask; no recovery or runtime integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from maplegotchi.core.world.coordinates import GRID_HEIGHT, GRID_WIDTH, Tile, require_integer
from maplegotchi.core.world.walkability import Walkability, neighbors

STEP_COST: Final = 4 * GRID_WIDTH * GRID_HEIGHT
TURN_PENALTY: Final = 1


def distance(a: Tile, b: Tile) -> int:
    return abs(a.tx - b.tx) + abs(a.ty - b.ty)


def heading(a: Tile, b: Tile) -> int:
    """Canonical up, left, right, down ordering; 4 denotes no previous heading."""
    return ((0, -1), (-1, 0), (1, 0), (0, 1)).index((b.tx - a.tx, b.ty - a.ty))


@dataclass(frozen=True, slots=True)
class Waypoint:
    tx: int
    ty: int
    cumulative_steps: int

    def __post_init__(self) -> None:
        Tile(self.tx, self.ty)
        require_integer(self.cumulative_steps, "cumulative_steps")
        if self.cumulative_steps < 0:
            raise ValueError("cumulative_steps must be nonnegative")

    @property
    def tile(self) -> Tile:
        return Tile(self.tx, self.ty)


@dataclass(frozen=True, slots=True)
class Route:
    waypoints: tuple[Waypoint, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.waypoints, tuple) or not self.waypoints:
            raise ValueError("route requires an immutable nonempty waypoint tuple")
        if any(not isinstance(point, Waypoint) for point in self.waypoints):
            raise ValueError("route requires Waypoint values")
        if self.waypoints[0].cumulative_steps != 0:
            raise ValueError("origin cumulative_steps must be zero")
        previous_direction: tuple[int, int] | None = None
        for a, b in zip(self.waypoints, self.waypoints[1:], strict=False):
            if (a.tx == b.tx) == (a.ty == b.ty):
                raise ValueError("segments must be nonzero and orthogonal")
            if b.cumulative_steps - a.cumulative_steps != distance(a.tile, b.tile):
                raise ValueError("segment cumulative_steps must equal grid distance")
            length = distance(a.tile, b.tile)
            direction = ((b.tx - a.tx) // length, (b.ty - a.ty) // length)
            if direction == previous_direction:
                raise ValueError("straight segments must be compressed")
            previous_direction = direction

    @property
    def origin(self) -> Tile:
        return self.waypoints[0].tile

    @property
    def destination(self) -> Tile:
        return self.waypoints[-1].tile

    @property
    def total_steps(self) -> int:
        return self.waypoints[-1].cumulative_steps

    def tiles(self) -> tuple[Tile, ...]:
        result = [self.origin]
        for a, b in zip(self.waypoints, self.waypoints[1:], strict=False):
            length = distance(a.tile, b.tile)
            dx, dy = (b.tx - a.tx) // length, (b.ty - a.ty) // length
            result.extend(Tile(a.tx + dx * i, a.ty + dy * i) for i in range(1, length + 1))
        return tuple(result)

    @property
    def turns(self) -> int:
        return max(0, len(self.waypoints) - 2)


def compress(tiles: tuple[Tile, ...]) -> Route:
    if not isinstance(tiles, tuple) or not tiles:
        raise ValueError("cannot compress an empty or mutable path")
    if any(not isinstance(tile, Tile) for tile in tiles):
        raise ValueError("path requires Tile values")
    if any(distance(tiles[i], tiles[i + 1]) != 1 for i in range(len(tiles) - 1)):
        raise ValueError("path must consist of orthogonally adjacent tiles")
    points = [Waypoint(tiles[0].tx, tiles[0].ty, 0)]
    for i in range(1, len(tiles) - 1):
        if heading(tiles[i - 1], tiles[i]) != heading(tiles[i], tiles[i + 1]):
            points.append(Waypoint(tiles[i].tx, tiles[i].ty, i))
    if len(tiles) > 1:
        points.append(Waypoint(tiles[-1].tx, tiles[-1].ty, len(tiles) - 1))
    return Route(tuple(points))


@dataclass(frozen=True, slots=True)
class PathResult:
    route: Route | None
    error: str | None = None
    reason: str | None = None


def find_route(
    mask: Walkability,
    start: Tile,
    target: Tile,
    turn_penalty: int = TURN_PENALTY,
    initial_heading: int = 4,
) -> PathResult:
    """Primary minimum grid steps, secondary turns; exact integer A* tie keys.

    Each state includes incoming heading, needed for correct turn costs. The fixed
    step cost exceeds every simple shortest path's total turn surcharge (0..4 per
    turn), so smoothing cannot purchase an extra step. Remaining ties use heading
    then g; equal-cost parents retain the first canonical discovery. No hash order
    controls traversal. A linear frontier minimum preserves the core allowlist.
    """
    require_integer(turn_penalty, "turn_penalty")
    require_integer(initial_heading, "initial_heading")
    if not 0 <= turn_penalty <= 4 or not 0 <= initial_heading <= 4:
        raise ValueError("turn_penalty and initial_heading must be in 0..4")
    allowed = frozenset(mask.walkable)
    if not isinstance(start, Tile) or start not in allowed:
        return PathResult(None, "no_destination", "invalid_start")
    if not isinstance(target, Tile) or target not in allowed:
        return PathResult(None, "no_destination", "invalid_target")
    # Frontier tuple: (f, h, ty, tx, incoming_heading, g).
    h = distance(start, target) * STEP_COST
    frontier = [(h, h, start.ty, start.tx, initial_heading, 0)]
    origin = (start.tx, start.ty, initial_heading)
    best = {origin: 0}
    parents: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    while frontier:
        entry = min(frontier)
        frontier.remove(entry)
        _, _, y, x, incoming, cost = entry
        state = (x, y, incoming)
        if best.get(state) != cost:
            continue
        tile = Tile(x, y)
        if tile == target:
            path = [tile]
            while state != origin:
                state = parents[state]
                path.append(Tile(state[0], state[1]))
            return PathResult(compress(tuple(reversed(path))))
        for neighbor in neighbors(tile):
            if neighbor not in allowed:
                continue
            direction = heading(tile, neighbor)
            extra = turn_penalty if incoming != 4 and direction != incoming else 0
            candidate = cost + STEP_COST + extra
            next_state = (neighbor.tx, neighbor.ty, direction)
            if candidate >= best.get(next_state, candidate + 1):
                continue
            best[next_state] = candidate
            parents[next_state] = state
            heuristic = distance(neighbor, target) * STEP_COST
            frontier.append(
                (candidate + heuristic, heuristic, neighbor.ty, neighbor.tx, direction, candidate)
            )
    return PathResult(None, "no_destination", "unreachable")
