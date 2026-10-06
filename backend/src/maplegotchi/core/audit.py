"""Decision and action audit records (ADR-0026 §8, ADR-0028 §2), built by pure core.

- A `DecisionRecord` says, for one decision transition: the context core
  summarised, what was proposed, core's verdict (accepted / clamped / rejected /
  fallback / stale) with a closed reason code, and what was executed. The only
  free text from a Director is its concise, validated `proposed_reason`. No
  prompt, raw response, or model reasoning ever reaches a record.
- An `ActionEvent` is one step of an action's lifecycle: destination selected,
  walking started / cancelled, arrived, activity started / completed /
  interrupted / resumed, or a signal that needs attention.

Goal-level events stay on the timeline (core/timeline.py).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType

from maplegotchi.core.activities import Activity
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.daytime import local_hour, require_utc
from maplegotchi.core.goals import GoalEndReason, GoalType
from maplegotchi.core.journal import text_problems
from maplegotchi.core.priority import Priority
from maplegotchi.core.state import MapleState

MAX_CONTEXT_SUMMARY = 400
RULE_DIRECTOR_NAME = "rule_director"
RULE_DIRECTOR_VERSION = "1"


class Verdict(StrEnum):
    ACCEPTED = "accepted"  # executed as proposed
    CLAMPED = "clamped"  # executed with numbers clamped into range (originals recorded)
    REJECTED = "rejected"  # proposal refused; rule direction executed instead
    FALLBACK = "fallback"  # no usable proposal (timeout, error, none); rule direction executed
    STALE = "stale"  # proposal arrived after the decision stopped being due; nothing executed


class ActionEventKind(StrEnum):
    DESTINATION_SELECTED = "destination_selected"
    WALKING_STARTED = "walking_started"
    WALKING_CANCELLED = "walking_cancelled"
    ARRIVED = "arrived"
    ACTIVITY_STARTED = "activity_started"
    ACTIVITY_COMPLETED = "activity_completed"
    ACTIVITY_INTERRUPTED = "activity_interrupted"
    ACTIVITY_RESUMED = "activity_resumed"
    NEEDS_ATTENTION = "needs_attention"


Payload = Mapping[str, str | int | float | None]


@dataclass(frozen=True, slots=True)
class ActionEvent:
    kind: ActionEventKind
    at: datetime
    action_id: int
    goal_id: int | None = None
    priority: Priority | None = None
    payload: Payload = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        require_utc(self.at, "action_event.at")
        if not isinstance(self.kind, ActionEventKind):
            raise TypeError("kind must be an ActionEventKind")
        if isinstance(self.action_id, bool) or self.action_id < 0:
            raise ValueError("action_id must be >= 0")


@dataclass(frozen=True, slots=True)
class Proposal:
    """A proposal as core understood it (already parsed into core types)."""

    goal_op: str | None = None  # keep | new | complete | resume | abandon
    goal_type: GoalType | None = None
    goal_summary: str | None = None
    horizon_minutes: float | None = None
    abandon_reason: GoalEndReason | None = None
    action: Activity | None = None
    duration_minutes: float | None = None
    reason: str | None = None  # the Director's concise reason, validated

    def __post_init__(self) -> None:
        if self.reason is not None and text_problems(self.reason):
            raise ValueError("a recorded reason must be one short printable line")


@dataclass(frozen=True, slots=True)
class Executed:
    by: str  # rule | external
    reason: str
    goal_id: int | None
    action_id: int
    action: Activity
    point: str
    duration_minutes: int


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    at: datetime
    trigger: str
    director_kind: str  # rule | external
    director_name: str
    director_version: str
    context_summary: str
    verdict: Verdict
    proposal: Proposal | None = None
    reason_code: str | None = None
    clamped: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({}))
    executed: Executed | None = None
    priority: Priority | None = None
    latency_ms: int | None = None

    def __post_init__(self) -> None:
        require_utc(self.at, "decision.at")
        if not isinstance(self.verdict, Verdict):
            raise TypeError("verdict must be a Verdict")
        summary = self.context_summary
        if not 1 <= len(summary) <= MAX_CONTEXT_SUMMARY or not summary.isprintable():
            raise ValueError("context summary must be one printable line of 1-400 chars")
        if (self.executed is None) != (self.verdict is Verdict.STALE):
            raise ValueError("every decision executes something, except a stale one")


def context_summary(
    state: MapleState, now: datetime, inputs: BehaviorInputs, trigger: str, utc_offset: timedelta
) -> str:
    """Core's own one-line summary of what a decision was based on (no Director text)."""
    n = state.needs
    hour = local_hour(now, utc_offset)
    goal = state.goal
    goal_text = "none"
    if goal is not None:
        left = max(0, int((goal.horizon_until - now).total_seconds() // 60))
        goal_text = f"{goal.type.value}#{goal.id} ({left} min left)"
    suspended = state.suspended_goal
    parts = [
        f"trigger={trigger}",
        f"local={int(hour):02d}:{int(hour % 1 * 60):02d}",
        f"activity={state.activity.value}@{state.point.id}",
        f"energy={n.energy:.0f} mood={n.mood:.0f} curiosity={n.curiosity:.0f}"
        f" social={n.social:.0f}",
        f"goal={goal_text}",
        f"suspended={suspended.type.value + '#' + str(suspended.id) if suspended else 'none'}",
        f"server_attention={inputs.server_attention:.2f}",
    ]
    return "; ".join(parts)[:MAX_CONTEXT_SUMMARY]
