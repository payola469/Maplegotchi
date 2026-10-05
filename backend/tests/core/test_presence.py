"""The speech bubble says only what is true in Maple's state (Phase A8)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.goals import Goal, GoalSource, GoalType
from maplegotchi.core.movement import begin_activity
from maplegotchi.core.presence import BubbleKind, bubble
from maplegotchi.core.priority import Priority
from maplegotchi.core.room import POINT_BY_ID
from maplegotchi.core.tasks import Task, Tool, WriteKind, write_task
from tests.core.support import at_local, make_state

NOON = at_local(12)


def test_reading_and_writing_say_what() -> None:
    reading = replace(
        make_state(at=NOON, activity=Activity.READ),
        task=Task(Tool.READER, "library:the_room", "Maple's room", "home"),
    )
    assert bubble(reading, NOON) == bubble(reading, NOON + timedelta(minutes=1))
    found = bubble(reading, NOON)
    assert found is not None and found.kind is BubbleKind.READING
    assert found.text == "Reading “Maple's room”"
    writing = replace(
        make_state(at=NOON, activity=Activity.WRITE, location=RoomLocation.DESK),
        task=write_task(WriteKind.REFLECTION),
    )
    written = bubble(writing, NOON)
    assert written is not None and written.kind is BubbleKind.WRITING
    assert written.text == "Writing a reflection"


def test_thinking_and_attention() -> None:
    thinking = make_state(at=NOON, activity=Activity.THINK, location=RoomLocation.WINDOW)
    assert bubble(thinking, NOON).kind is BubbleKind.THINKING  # type: ignore[union-attr]
    urgent = replace(
        make_state(at=NOON, activity=Activity.OBSERVE_SERVER, location=RoomLocation.TERMINAL),
        action_priority=Priority.CRITICAL,
    )
    alarm = bubble(urgent, NOON)
    assert alarm is not None and alarm.kind is BubbleKind.NEEDS_ATTENTION


def test_waiting_for_paolo_only_with_a_social_goal_while_idle() -> None:
    goal = Goal(1, GoalType.SOCIALIZE, "Be around", GoalSource.RULE, NOON,
                NOON + timedelta(minutes=60))  # fmt: skip
    idle = replace(make_state(at=NOON, activity=Activity.IDLE), goal=goal, goal_counter=1)
    waiting = bubble(idle, NOON)
    assert waiting is not None and waiting.kind is BubbleKind.WAITING_FOR_PAOLO
    assert bubble(make_state(at=NOON, activity=Activity.IDLE), NOON) is None


def test_no_bubble_while_walking_or_resting_and_never_approval() -> None:
    reading = make_state(at=NOON, activity=Activity.READ)
    walking = begin_activity(reading, NOON, Activity.THINK, POINT_BY_ID["window.view"],
                             NOON + timedelta(minutes=10)).state  # fmt: skip
    assert bubble(walking, NOON) is None
    assert bubble(make_state(at=NOON, activity=Activity.REST, location=RoomLocation.SOFA),
                  NOON) is None  # fmt: skip
    for activity in Activity:
        state = make_state(at=NOON, activity=activity)
        found = bubble(state, NOON)
        assert found is None or found.kind is not BubbleKind.APPROVAL_REQUIRED
