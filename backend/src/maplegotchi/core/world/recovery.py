"""Emergency-only deterministic relocation; no movement execution or persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from maplegotchi.core.world.coordinates import Tile, require_integer
from maplegotchi.core.world.walkability import Walkability, neighbors, ordered


@dataclass(frozen=True, slots=True)
class Position:
    """An exceptional source may be outside the grid; ordinary Tile remains strict."""

    tx: int
    ty: int

    def __post_init__(self) -> None:
        require_integer(self.tx, "tx")
        require_integer(self.ty, "ty")


class RelocationReason(StrEnum):
    BLOCKED_SOURCE = "blocked_source"
    NO_REACHABLE_CANDIDATE = "no_reachable_candidate"
    INVALID_SOURCE = "invalid_source"


@dataclass(frozen=True, slots=True)
class Relocation:
    original: Position
    destination: Tile
    reason: RelocationReason
    kind: str = field(default="maple_relocated", init=False)


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    destination: Tile | None
    event: Relocation | None
    error: str | None = None


def recover(mask: Walkability, source: Position) -> RecoveryResult:
    """ADR-0035 STEP 103: initialize once at blocked eligible source, then walkable only.

    Every valid neighbor is a destination, so BFS's first nonempty walkable layer
    is also its final layer. It cannot tunnel through a second blocked cell.
    Invalid sources never seed a search. Recovery is separate from validation.
    """
    try:
        tile = Tile(source.tx, source.ty)
    except ValueError:
        tile = None
    if tile is not None and tile in mask.walkable:
        return RecoveryResult(tile, None)
    reason = RelocationReason.INVALID_SOURCE
    if tile is not None and tile in mask.permitted and tile in mask.blocked:
        candidates = ordered(set(neighbors(tile)) & set(mask.walkable))
        if candidates:
            destination = candidates[0]
            return RecoveryResult(
                destination, Relocation(source, destination, RelocationReason.BLOCKED_SOURCE)
            )
        reason = RelocationReason.NO_REACHABLE_CANDIDATE
    fallback = mask.safe_tile
    if fallback is None or fallback not in mask.walkable or fallback not in mask.keep_clear:
        return RecoveryResult(None, None, "unsafe_fallback")
    return RecoveryResult(fallback, Relocation(source, fallback, reason))
