"""Short-term goals (ADR-0026 §6): semantic intent over 30-120 minutes.

A goal type says *why* Maple is doing things, never *which* actions in which
order: there is no action sequence per goal type. Rule direction may lean
toward actions that fit a goal (a soft score bias, `AFFINITY`), and an
external Director may choose anything core allows.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType

from maplegotchi.core.activities import Activity
from maplegotchi.core.daytime import require_utc

GOAL_MIN_HORIZON = timedelta(minutes=30)
GOAL_MAX_HORIZON = timedelta(minutes=120)
MAX_GOAL_SUMMARY = 120


class GoalType(StrEnum):
    """The v1 goal types (closed; ADR-0026 §6)."""

    LEARN = "learn"
    CREATE = "create"
    RECOVER = "recover"
    REFLECT = "reflect"
    MONITOR = "monitor"
    SOCIALIZE = "socialize"
    EXPLORE = "explore"
    ORGANIZE = "organize"
    MAINTAIN = "maintain"
    PRACTICE = "practice"
    PLAN = "plan"
    WAIT = "wait"  # wait / anticipate
    PLAY = "play"  # play / relax
    HELP = "help"
    INVESTIGATE = "investigate"
    REMEMBER = "remember"


class GoalSource(StrEnum):
    RULE = "rule"  # core's own rule direction
    EXTERNAL = "external"  # proposed by an external Director, accepted by core


class GoalEndReason(StrEnum):
    """Why a goal ended (closed codes; shown to people as concise reasons)."""

    HORIZON_REACHED = "horizon_reached"  # completed: its time was used
    DIRECTOR_COMPLETED = "director_completed"  # completed: the Director said so
    EXPIRED = "expired"  # abandoned: horizon passed while it was suspended
    SUPERSEDED = "superseded"  # abandoned: replaced by another goal
    NO_LONGER_RELEVANT = "no_longer_relevant"  # abandoned after an interruption
    DIRECTOR_ABANDONED = "director_abandoned"  # abandoned: the Director said so


def summary_problems(text: object) -> list[str]:
    """Structural problems with a goal summary (empty list = acceptable)."""
    if not isinstance(text, str):
        return ["not_text"]
    problems = []
    if not 1 <= len(text) <= MAX_GOAL_SUMMARY or text != text.strip():
        problems.append("length")
    if not text.isprintable():
        problems.append("unprintable")
    return problems


@dataclass(frozen=True, slots=True)
class Goal:
    id: int
    type: GoalType
    summary: str
    source: GoalSource
    started_at: datetime
    horizon_until: datetime

    def __post_init__(self) -> None:
        if isinstance(self.id, bool) or not isinstance(self.id, int) or self.id < 1:
            raise ValueError("goal id must be an int >= 1")
        if not isinstance(self.type, GoalType) or not isinstance(self.source, GoalSource):
            raise TypeError("goal type and source must be enums")
        if summary_problems(self.summary):
            raise ValueError(f"goal summary is not acceptable: {summary_problems(self.summary)}")
        require_utc(self.started_at, "goal.started_at")
        require_utc(self.horizon_until, "goal.horizon_until")
        if not GOAL_MIN_HORIZON <= self.horizon_until - self.started_at <= GOAL_MAX_HORIZON:
            raise ValueError("a goal's horizon must be 30-120 minutes")

    def expired_at(self, now: datetime) -> bool:
        require_utc(now, "now")
        return now >= self.horizon_until


# Rule direction's wording for its own goals (never implies an action sequence).
RULE_SUMMARIES: Mapping[GoalType, str] = MappingProxyType(
    {
        GoalType.LEARN: "Learn something new",
        GoalType.CREATE: "Make something of my own",
        GoalType.RECOVER: "Recover my energy",
        GoalType.REFLECT: "Reflect on how things are going",
        GoalType.MONITOR: "Keep an eye on paolo-core",
        GoalType.SOCIALIZE: "Be around for company",
        GoalType.EXPLORE: "Explore a little",
        GoalType.ORGANIZE: "Put my thoughts in order",
        GoalType.MAINTAIN: "Look after things",
        GoalType.PRACTICE: "Practice something",
        GoalType.PLAN: "Plan what comes next",
        GoalType.WAIT: "Wait and see what comes",
        GoalType.PLAY: "Play and relax",
        GoalType.HELP: "Be helpful",
        GoalType.INVESTIGATE: "Look into something curious",
        GoalType.REMEMBER: "Remember recent moments",
    }
)

# Soft preferences for rule direction: activities that suit a goal score higher.
# A bias, not a plan: any allowed activity can still be chosen.
AFFINITY_BOOST = 1.6
AFFINITY: Mapping[GoalType, tuple[Activity, ...]] = MappingProxyType(
    {
        GoalType.LEARN: (Activity.READ,),
        GoalType.CREATE: (Activity.WRITE,),
        GoalType.RECOVER: (Activity.REST, Activity.SLEEP),
        GoalType.REFLECT: (Activity.THINK, Activity.WRITE),
        GoalType.MONITOR: (Activity.OBSERVE_SERVER,),
        GoalType.SOCIALIZE: (Activity.IDLE, Activity.WALK),
        GoalType.EXPLORE: (Activity.WALK, Activity.READ),
        GoalType.ORGANIZE: (Activity.WRITE,),
        GoalType.MAINTAIN: (Activity.OBSERVE_SERVER,),
        GoalType.PRACTICE: (Activity.WRITE,),
        GoalType.PLAN: (Activity.THINK,),
        GoalType.WAIT: (Activity.IDLE, Activity.THINK),
        GoalType.PLAY: (Activity.WALK, Activity.IDLE),
        GoalType.HELP: (Activity.OBSERVE_SERVER,),
        GoalType.INVESTIGATE: (Activity.OBSERVE_SERVER, Activity.READ),
        GoalType.REMEMBER: (Activity.THINK, Activity.WRITE),
    }
)

if set(RULE_SUMMARIES) != set(GoalType) or set(AFFINITY) != set(GoalType):
    raise RuntimeError("every goal type needs a rule summary and an affinity entry")
