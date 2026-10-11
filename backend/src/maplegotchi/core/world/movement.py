"""Supplied-time grid travel and temporary mid-edge replanning; never persisted here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from maplegotchi.core.daytime import require_utc
from maplegotchi.core.world.coordinates import Tile, require_integer, tile_to_feet
from maplegotchi.core.world.pathfinding import TURN_PENALTY, Route, distance, find_route, heading
from maplegotchi.core.world.walkability import Walkability

MS_PER_STEP: Final = 250


def microseconds(delta: timedelta) -> int:
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


@dataclass(frozen=True, slots=True)
class EdgeStart:
    """Transient temporal progress on a unit edge, not a persisted fractional tile."""

    a: Tile
    b: Tile
    progress_us: int
    step_us: int

    def __post_init__(self) -> None:
        if not isinstance(self.a, Tile) or not isinstance(self.b, Tile):
            raise ValueError("temporary edge endpoints must be Tiles")
        require_integer(self.progress_us, "progress_us")
        require_integer(self.step_us, "step_us")
        if distance(self.a, self.b) != 1 or not 0 < self.progress_us < self.step_us:
            raise ValueError("temporary start requires an adjacent edge and interior progress")

    def pixels(self, progress_us: int) -> tuple[int, int]:
        ax, ay = tile_to_feet(self.a)
        bx, by = tile_to_feet(self.b)
        return (
            (ax * self.step_us + (bx - ax) * progress_us) // self.step_us,
            (ay * self.step_us + (by - ay) * progress_us) // self.step_us,
        )


@dataclass(frozen=True, slots=True)
class Entry:
    start: EdgeStart
    endpoint: Tile

    def __post_init__(self) -> None:
        if not isinstance(self.start, EdgeStart) or not isinstance(self.endpoint, Tile):
            raise ValueError("entry requires an EdgeStart and Tile endpoint")
        if self.endpoint not in (self.start.a, self.start.b):
            raise ValueError("temporary entry must end at a current-edge endpoint")

    @property
    def duration_us(self) -> int:
        return (
            self.start.progress_us
            if self.endpoint == self.start.a
            else self.start.step_us - self.start.progress_us
        )

    def progress_at(self, elapsed_us: int) -> int:
        sign = -1 if self.endpoint == self.start.a else 1
        return self.start.progress_us + sign * min(max(0, elapsed_us), self.duration_us)


@dataclass(frozen=True, slots=True)
class Travel:
    route: Route
    departed_at: datetime
    ms_per_step: int = MS_PER_STEP
    entry: Entry | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.route, Route):
            raise ValueError("travel requires a validated Route")
        if self.entry is not None and not isinstance(self.entry, Entry):
            raise ValueError("travel entry must be Entry or None")
        require_utc(self.departed_at, "departed_at")
        require_integer(self.ms_per_step, "ms_per_step")
        if self.ms_per_step <= 0:
            raise ValueError("ms_per_step must be positive")
        if self.entry is not None and (
            self.entry.endpoint != self.route.origin or self.entry.start.step_us != self.step_us
        ):
            raise ValueError("entry must join route origin at the same movement speed")

    @property
    def step_us(self) -> int:
        return self.ms_per_step * 1000

    @property
    def duration_us(self) -> int:
        return self.route.total_steps * self.step_us + (self.entry.duration_us if self.entry else 0)

    @property
    def arrives_at(self) -> datetime:
        return self.departed_at + timedelta(microseconds=self.duration_us)

    @property
    def activity_started_at(self) -> datetime:
        return self.arrives_at

    def phase_at(self, now: datetime) -> str:
        require_utc(now, "now")
        if now < self.departed_at:
            return "pending"
        return "walking" if now < self.arrives_at else "performing"

    def current_at(self, now: datetime) -> Tile | EdgeStart:
        require_utc(now, "now")
        elapsed = max(0, microseconds(now - self.departed_at))
        if self.entry is not None:
            if elapsed < self.entry.duration_us:
                start = self.entry.start
                return EdgeStart(start.a, start.b, self.entry.progress_at(elapsed), start.step_us)
            elapsed -= self.entry.duration_us
        index, progress = divmod(elapsed, self.step_us)
        tiles = self.route.tiles()
        if index >= self.route.total_steps:
            return self.route.destination
        if progress == 0:
            return tiles[index]
        return EdgeStart(tiles[index], tiles[index + 1], progress, self.step_us)

    def position_at(self, now: datetime) -> tuple[int, int]:
        current = self.current_at(now)
        return (
            tile_to_feet(current)
            if isinstance(current, Tile)
            else current.pixels(current.progress_us)
        )


@dataclass(frozen=True, slots=True)
class TravelResult:
    travel: Travel | None
    error: str | None = None
    reason: str | None = None


def reroute(
    mask: Walkability,
    previous: Travel,
    target: Tile,
    now: datetime,
    turn_penalty: int = TURN_PENALTY,
) -> TravelResult:
    """Replace destination from the exact current position, never rounded pixel state.

    ADR-0027 connects a temporary start to both unit-edge endpoints. Compare exact
    remaining travel microseconds, then turns and endpoint (ty,tx). Partial entry
    time plus integer grid-step time replaces the ordinary whole-step duration.
    Returning a replacement logically cancels the prior destination; no events or
    state writes are executed. Failure leaves the previous plan with its caller.
    """
    require_utc(now, "now")
    if now < previous.departed_at:
        raise ValueError("cannot reroute before the previous departure")
    current = previous.current_at(now)
    if isinstance(current, Tile):
        result = find_route(mask, current, target, turn_penalty)
        return TravelResult(
            Travel(result.route, now, previous.ms_per_step) if result.route is not None else None,
            result.error,
            result.reason,
        )
    if current.a not in mask.walkable or current.b not in mask.walkable:
        return TravelResult(None, "no_destination", "invalid_current_edge")
    choices: list[tuple[tuple[int, int, int, int], Travel]] = []
    for endpoint in (current.a, current.b):
        entry = Entry(current, endpoint)
        incoming = (
            heading(current.b, current.a)
            if endpoint == current.a
            else heading(current.a, current.b)
        )
        found = find_route(mask, endpoint, target, turn_penalty, incoming)
        if found.route is None:
            continue
        travel = Travel(found.route, now, previous.ms_per_step, entry)
        tiles = found.route.tiles()
        turn = int(len(tiles) > 1 and heading(tiles[0], tiles[1]) != incoming)
        choices.append(
            ((travel.duration_us, found.route.turns + turn, endpoint.ty, endpoint.tx), travel)
        )
    if not choices:
        return TravelResult(None, "no_destination", "unreachable_or_invalid_target")
    return TravelResult(min(choices, key=lambda choice: choice[0])[1])
