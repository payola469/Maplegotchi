"""Life events produced by core transitions. Storage persists them append-only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from maplegotchi.core.activities import Activity
from maplegotchi.core.goals import Goal, GoalEndReason, GoalType
from maplegotchi.core.state import InteractionKind, ReactionKind


@dataclass(frozen=True, slots=True)
class Born:
    """Maple's life began. Recorded exactly once per life."""

    at: datetime
    name: str


@dataclass(frozen=True, slots=True)
class ActivityChanged:
    at: datetime
    previous: Activity
    current: Activity


@dataclass(frozen=True, slots=True)
class InteractionAccepted:
    at: datetime
    kind: InteractionKind
    reaction: ReactionKind


@dataclass(frozen=True, slots=True)
class DowntimeGap:
    """No heartbeat ran between `since` and `until` (e.g. the service was down)."""

    since: datetime
    until: datetime


# Goal-level significant events (ADR-0028 §2). Fine-grained action lifecycle
# events are kept out of the timeline (action_event, Phase A3).


@dataclass(frozen=True, slots=True)
class GoalStarted:
    at: datetime
    goal: Goal


@dataclass(frozen=True, slots=True)
class GoalSuspended:
    """An interruption paused the goal; it will be resumed or abandoned afterwards."""

    at: datetime
    goal_id: int
    goal_type: GoalType
    cause: str  # the interrupting signal, e.g. "server_problem"


@dataclass(frozen=True, slots=True)
class GoalResumed:
    at: datetime
    goal_id: int
    goal_type: GoalType


@dataclass(frozen=True, slots=True)
class GoalCompleted:
    at: datetime
    goal_id: int
    goal_type: GoalType
    reason: GoalEndReason


@dataclass(frozen=True, slots=True)
class GoalAbandoned:
    at: datetime
    goal_id: int
    goal_type: GoalType
    reason: GoalEndReason


GoalEvent = GoalStarted | GoalSuspended | GoalResumed | GoalCompleted | GoalAbandoned

LifeEvent = (
    Born
    | ActivityChanged
    | InteractionAccepted
    | DowntimeGap
    | GoalStarted
    | GoalSuspended
    | GoalResumed
    | GoalCompleted
    | GoalAbandoned
)
