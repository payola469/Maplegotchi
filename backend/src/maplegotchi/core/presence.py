"""What Maple's speech bubble says (Phase A8), derived from real state at `now`.

The room shows a bubble only for something true in the backend: urgent
attention, the activity Maple is performing (with what it reads/writes), or
waiting for Paolo. `approval_required` is reserved for future privileged
requests (none exist in v0.2), so it is never produced here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from maplegotchi.core.activities import Activity
from maplegotchi.core.goals import GoalType
from maplegotchi.core.priority import Priority
from maplegotchi.core.state import MapleState
from maplegotchi.core.tasks import Tool, one_line


class BubbleKind(StrEnum):
    NEEDS_ATTENTION = "needs_attention"
    THINKING = "thinking"
    READING = "reading"
    WRITING = "writing"
    WAITING_FOR_PAOLO = "waiting_for_paolo"
    LISTENING = "listening"  # Paolo wrote; Maple stopped to listen (ADR-0032)
    APPROVAL_REQUIRED = "approval_required"  # reserved: no approval flow exists yet


@dataclass(frozen=True, slots=True)
class Bubble:
    kind: BubbleKind
    text: str  # one short line


def bubble(state: MapleState, now: datetime) -> Bubble | None:
    """The bubble for `state` at `now`, or None. Pure and total."""
    if state.action_priority is Priority.HIGH and state.activity is Activity.IDLE:
        return Bubble(BubbleKind.LISTENING, "Listening to Paolo")
    if state.action_priority in (Priority.CRITICAL, Priority.HIGH):
        what = "the server" if state.activity is Activity.OBSERVE_SERVER else "myself"
        return Bubble(BubbleKind.NEEDS_ATTENTION, f"Something needs attention: {what}")
    if state.walking_at(now):
        return None  # the walk itself shows where Maple is going
    task = state.task
    if state.activity is Activity.READ and task and task.tool is Tool.READER:
        return Bubble(BubbleKind.READING, one_line(f"Reading “{task.title}”", 80))
    if state.activity is Activity.WRITE and task and task.tool is Tool.WRITER:
        return Bubble(BubbleKind.WRITING, one_line(f"Writing {task.title.lower()}", 80))
    if state.activity is Activity.THINK:
        return Bubble(BubbleKind.THINKING, "Thinking…")
    goal = state.goal
    if (
        goal is not None
        and goal.type in (GoalType.SOCIALIZE, GoalType.WAIT)
        and state.activity in (Activity.IDLE, Activity.WALK)
    ):
        return Bubble(BubbleKind.WAITING_FOR_PAOLO, "Waiting for Paolo")
    return None
