"""Maple's state and its invariants.

Every dataclass here validates its invariants in __post_init__, and
dataclasses.replace() re-runs that validation, so an invalid state cannot be
constructed. Expression is derived from state, never stored.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from maplegotchi.core.activities import SPECS, Activity, RoomLocation
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.identity import Identity
from maplegotchi.core.parameters import GLOBAL_INTERACTION_LIMIT, GLOBAL_INTERACTION_WINDOW
from maplegotchi.core.rng import RngState

NEED_MIN = 0.0
NEED_MAX = 100.0

# Below this energy Maple is drowsy: sleepy expression and sleepy reactions.
SLEEPY_ENERGY = 20.0
HAPPY_MOOD = 70.0
CURIOUS_CURIOSITY = 75.0
CURIOUS_READING_CURIOSITY = 60.0

REACTION_VARIANTS = 3


def clamp_need(value: float) -> float:
    return min(NEED_MAX, max(NEED_MIN, value))


@dataclass(frozen=True, slots=True)
class Needs:
    """Maple's needs, each in [0, 100]. Higher is better for every need."""

    mood: float
    energy: float
    curiosity: float  # appetite for novelty; reading/observing satisfies it
    social: float  # social fulfilment; owner interactions raise it

    def __post_init__(self) -> None:
        for name in ("mood", "energy", "curiosity", "social"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise TypeError(f"{name} must be a number")
            if not math.isfinite(value) or not NEED_MIN <= value <= NEED_MAX:
                raise ValueError(f"{name}={value!r} outside [{NEED_MIN}, {NEED_MAX}]")

    @classmethod
    def clamped(cls, *, mood: float, energy: float, curiosity: float, social: float) -> Needs:
        return cls(
            mood=clamp_need(mood),
            energy=clamp_need(energy),
            curiosity=clamp_need(curiosity),
            social=clamp_need(social),
        )


class Expression(StrEnum):
    CALM = "calm"
    HAPPY = "happy"
    CURIOUS = "curious"
    SLEEPY = "sleepy"
    FOCUSED = "focused"


class InteractionKind(StrEnum):
    """The only owner interactions in v0.1 (D3). Do not add members."""

    GREET = "greet"
    PET = "pet"


class ReactionKind(StrEnum):
    GREET_HAPPY = "greet_happy"
    GREET_SLEEPY = "greet_sleepy"
    PET_HAPPY = "pet_happy"
    PET_SLEEPY = "pet_sleepy"


HAPPY_REACTIONS = frozenset({ReactionKind.GREET_HAPPY, ReactionKind.PET_HAPPY})


@dataclass(frozen=True, slots=True)
class Reaction:
    kind: ReactionKind
    variant: int  # which of the REACTION_VARIANTS presentations to show
    started_at: datetime
    until: datetime  # exclusive: the reaction is over at exactly `until`

    def __post_init__(self) -> None:
        require_utc(self.started_at, "reaction.started_at")
        require_utc(self.until, "reaction.until")
        if not self.started_at < self.until:
            raise ValueError("reaction must end after it starts")
        if isinstance(self.variant, bool) or not 0 <= self.variant < REACTION_VARIANTS:
            raise ValueError(f"reaction variant must be in [0, {REACTION_VARIANTS})")

    def is_active(self, now: datetime) -> bool:
        require_utc(now, "now")
        return self.started_at <= now < self.until


@dataclass(frozen=True, slots=True)
class InteractionRecord:
    kind: InteractionKind
    at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.kind, InteractionKind):
            raise TypeError("kind must be an InteractionKind")
        require_utc(self.at, "interaction.at")


@dataclass(frozen=True, slots=True)
class MapleState:
    identity: Identity
    needs: Needs
    activity: Activity
    location: RoomLocation
    activity_started_at: datetime
    activity_until: datetime  # planned end; the heartbeat picks a new activity at/after it
    last_tick_at: datetime  # time of the last heartbeat (or birth)
    last_updated_at: datetime  # latest time this state reflects (heartbeat or interaction)
    rng: RngState
    # Accepted interactions inside the global rate-limit window, oldest first.
    # This is the persisted cooldown/rate-limit state (D14).
    recent_interactions: tuple[InteractionRecord, ...] = ()
    reaction: Reaction | None = None

    def __post_init__(self) -> None:
        for name in ("activity_started_at", "activity_until", "last_tick_at", "last_updated_at"):
            require_utc(getattr(self, name), name)
        if not isinstance(self.activity, Activity):
            raise TypeError("activity must be an Activity")
        if not isinstance(self.location, RoomLocation):
            raise TypeError("location must be a RoomLocation")

        born = self.identity.born_at
        if not born <= self.activity_started_at <= self.activity_until:
            raise ValueError("require born_at <= activity_started_at <= activity_until")
        if not born <= self.last_tick_at <= self.last_updated_at:
            raise ValueError("require born_at <= last_tick_at <= last_updated_at")
        if self.activity_started_at > self.last_updated_at:
            raise ValueError("activity cannot start after last_updated_at")
        if self.location not in SPECS[self.activity].locations:
            raise ValueError(f"{self.activity} cannot happen at {self.location}")

        records = self.recent_interactions
        if len(records) > GLOBAL_INTERACTION_LIMIT:
            raise ValueError("more recent interactions than the global limit allows")
        for i, record in enumerate(records):
            if not born <= record.at <= self.last_updated_at:
                raise ValueError("interaction time outside Maple's life so far")
            if self.last_updated_at - record.at >= GLOBAL_INTERACTION_WINDOW:
                raise ValueError("interaction record outside the rate-limit window")
            if i and records[i - 1].at > record.at:
                raise ValueError("recent_interactions must be oldest first")

        if self.reaction is not None:
            if not born <= self.reaction.started_at <= self.last_updated_at:
                raise ValueError("reaction time outside Maple's life so far")

    def active_reaction(self, now: datetime) -> Reaction | None:
        """The transient reaction showing at `now`, if any. No heartbeat needed to expire it."""
        self._require_presentable(now)
        if self.reaction is not None and self.reaction.is_active(now):
            return self.reaction
        return None

    def expression_at(self, now: datetime) -> Expression:
        """Maple's expression as presented at `now` (>= last_updated_at)."""
        self._require_presentable(now)
        return derive_expression(self, now)

    def _require_presentable(self, now: datetime) -> None:
        require_utc(now, "now")
        if now < self.last_updated_at:
            raise ValueError("cannot present state at a time before its latest update")

    @property
    def ticks_lived(self) -> int:
        return self.rng.tick_counter

    def age(self, now: datetime) -> timedelta:
        require_utc(now, "now")
        if now < self.identity.born_at:
            raise ValueError("now is before Maple was born")
        return now - self.identity.born_at

    def is_drowsy(self) -> bool:
        return self.activity is Activity.SLEEP or self.needs.energy < SLEEPY_ENERGY


def prune_interactions(
    records: tuple[InteractionRecord, ...], now: datetime
) -> tuple[InteractionRecord, ...]:
    """Keep only interactions still inside the global rate-limit window."""
    return tuple(r for r in records if now - r.at < GLOBAL_INTERACTION_WINDOW)


def derive_expression(state: MapleState, now: datetime) -> Expression:
    """Maple's face follows its real state and activity at `now`, in priority order.

    A transient reaction only counts while it is active, so it ends at its
    `until` without waiting for a heartbeat.
    """
    needs = state.needs
    if state.is_drowsy():
        return Expression.SLEEPY
    reaction = state.reaction
    if reaction is not None and reaction.is_active(now) and reaction.kind in HAPPY_REACTIONS:
        return Expression.HAPPY
    if state.activity in (Activity.WRITE, Activity.OBSERVE_SERVER):
        return Expression.FOCUSED
    if state.activity is Activity.READ:
        if needs.curiosity >= CURIOUS_READING_CURIOSITY:
            return Expression.CURIOUS
        return Expression.FOCUSED
    if needs.mood >= HAPPY_MOOD:
        return Expression.HAPPY
    if needs.curiosity >= CURIOUS_CURIOSITY:
        return Expression.CURIOUS
    return Expression.CALM


INITIAL_NEEDS = Needs(mood=60.0, energy=80.0, curiosity=60.0, social=50.0)
FIRST_ACTIVITY_DURATION = timedelta(minutes=15)


def birth(*, name: str, born_at: datetime, seed_hex: str) -> MapleState:
    """Maple's initial state. The caller supplies the time and the life seed."""
    return MapleState(
        identity=Identity(name=name, born_at=born_at),
        needs=INITIAL_NEEDS,
        activity=Activity.IDLE,
        location=RoomLocation.RUG,
        activity_started_at=born_at,
        activity_until=born_at + FIRST_ACTIVITY_DURATION,
        last_tick_at=born_at,
        last_updated_at=born_at,
        rng=RngState(seed_hex=seed_hex),
    )
