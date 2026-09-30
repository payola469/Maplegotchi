"""Owner interactions — Greet and Pet only (D3) — as pure state transitions.

Limits are FIXED (D14): Greet 60 s, Pet 30 s, global 10 per 10 minutes. The
cooldown and rate-limit state is MapleState.recent_interactions, which Phase 2
persists with the rest of the state, so a restart cannot reset it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType

from maplegotchi.core.daytime import require_utc
from maplegotchi.core.parameters import (
    GLOBAL_INTERACTION_LIMIT,
    GLOBAL_INTERACTION_WINDOW,
    GREET_COOLDOWN,
    PET_COOLDOWN,
    CoreParameters,
)
from maplegotchi.core.rng import RngStream
from maplegotchi.core.state import (
    REACTION_VARIANTS,
    InteractionKind,
    InteractionRecord,
    MapleState,
    Needs,
    Reaction,
    ReactionKind,
    prune_interactions,
)
from maplegotchi.core.timeline import InteractionAccepted

COOLDOWNS = MappingProxyType(
    {InteractionKind.GREET: GREET_COOLDOWN, InteractionKind.PET: PET_COOLDOWN}
)
# Cooldowns are checked against records inside the global window, so no
# cooldown may be longer than that window.
if max(COOLDOWNS.values()) > GLOBAL_INTERACTION_WINDOW:
    raise RuntimeError("cooldowns must not exceed the global interaction window")


@dataclass(frozen=True, slots=True)
class Effect:
    social: float
    mood: float


EFFECTS = MappingProxyType(
    {
        InteractionKind.GREET: Effect(social=12.0, mood=4.0),
        InteractionKind.PET: Effect(social=8.0, mood=6.0),
    }
)

_REACTIONS = MappingProxyType(
    {
        (InteractionKind.GREET, False): ReactionKind.GREET_HAPPY,
        (InteractionKind.GREET, True): ReactionKind.GREET_SLEEPY,
        (InteractionKind.PET, False): ReactionKind.PET_HAPPY,
        (InteractionKind.PET, True): ReactionKind.PET_SLEEPY,
    }
)

# Each earlier same-kind interaction in the window halves the effect; a drowsy
# Maple takes in half as much.
REPEAT_FACTOR = 0.5
DROWSY_FACTOR = 0.5


class RejectionReason(StrEnum):
    COOLDOWN = "cooldown"
    RATE_LIMIT = "rate_limit"


@dataclass(frozen=True, slots=True)
class Accepted:
    state: MapleState
    reaction: Reaction
    event: InteractionAccepted


@dataclass(frozen=True, slots=True)
class Rejected:
    reason: RejectionReason
    retry_after: timedelta


InteractionOutcome = Accepted | Rejected


def check_limits(state: MapleState, kind: InteractionKind, now: datetime) -> Rejected | None:
    """Return a rejection if a cooldown or the global limit blocks `kind` at `now`."""
    window = prune_interactions(state.recent_interactions, now)
    blocks: list[Rejected] = []

    last_same = max((r.at for r in window if r.kind is kind), default=None)
    cooldown = COOLDOWNS[kind]
    if last_same is not None and now - last_same < cooldown:
        blocks.append(Rejected(RejectionReason.COOLDOWN, last_same + cooldown - now))

    if len(window) >= GLOBAL_INTERACTION_LIMIT:
        oldest = window[0].at
        blocks.append(
            Rejected(RejectionReason.RATE_LIMIT, oldest + GLOBAL_INTERACTION_WINDOW - now)
        )

    return max(blocks, key=lambda r: r.retry_after, default=None)


def apply_interaction(
    state: MapleState,
    kind: InteractionKind,
    now: datetime,
    params: CoreParameters,
) -> InteractionOutcome:
    if not isinstance(kind, InteractionKind):
        raise TypeError("kind must be an InteractionKind")
    require_utc(now, "now")
    if now < state.last_updated_at:
        raise ValueError("interaction time must not precede the latest state update")

    rejected = check_limits(state, kind, now)
    if rejected is not None:
        return rejected

    counter = state.rng.interaction_counter + 1
    rng = RngStream(state.rng.seed_hex, "interaction", counter)
    window = prune_interactions(state.recent_interactions, now)
    drowsy = state.is_drowsy()

    repeats = sum(1 for r in window if r.kind is kind)
    factor = REPEAT_FACTOR**repeats * (DROWSY_FACTOR if drowsy else 1.0)
    effect = EFFECTS[kind]
    needs = state.needs
    new_needs = Needs.clamped(
        mood=needs.mood + effect.mood * factor,
        energy=needs.energy,
        curiosity=needs.curiosity,
        social=needs.social + effect.social * factor,
    )

    reaction = Reaction(
        kind=_REACTIONS[(kind, drowsy)],
        variant=rng.randint(0, REACTION_VARIANTS - 1),
        started_at=now,
        until=now + params.reaction_duration,
    )
    new_state = replace(
        state,
        needs=new_needs,
        recent_interactions=(*window, InteractionRecord(kind=kind, at=now)),
        reaction=reaction,
        last_updated_at=now,
        rng=replace(state.rng, interaction_counter=counter),
    )
    event = InteractionAccepted(at=now, kind=kind, reaction=reaction.kind)
    return Accepted(state=new_state, reaction=reaction, event=event)
