"""Conversation rules: effects, high priority, truthful replies (ADR-0032)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.conversation import (
    MESSAGE_SOCIAL,
    Channel,
    IncomingMessage,
    ReplyContext,
    Speaker,
    build_reply_context,
    receive_message,
    reply_problems,
    rule_reply,
)
from maplegotchi.core.goals import Goal, GoalSource, GoalType
from maplegotchi.core.presence import BubbleKind, bubble
from maplegotchi.core.priority import Priority
from maplegotchi.core.rng import RngStream
from maplegotchi.core.state import MapleState
from maplegotchi.core.tasks import Task, Tool
from tests.core.support import PARAMS, SEED, at_local, make_state, needs

NOON = at_local(12)
RNG = RngStream(SEED, "interaction", 1)


def message(text: str = "What are you doing?") -> IncomingMessage:
    return IncomingMessage("123456789", Channel.DISCORD, Speaker.PAOLO, text, NOON)


def reading_with_goal() -> MapleState:
    goal = Goal(1, GoalType.LEARN, "Learn about the room", GoalSource.RULE, NOON,
                NOON + timedelta(minutes=60))  # fmt: skip
    return replace(
        make_state(at=NOON, activity=Activity.READ, state_needs=needs(social=40.0)),
        goal=goal,
        goal_counter=1,
        task=Task(Tool.READER, "library:the_room", "Maple's room", "home"),
    )


def test_a_message_is_social_and_repeated_messages_matter_less() -> None:
    s = reading_with_goal()
    first = receive_message(s, NOON, 0, RNG)
    assert first.state.needs.social == pytest.approx(s.needs.social + MESSAGE_SOCIAL)
    third = receive_message(s, NOON, 2, RNG)
    assert third.state.needs.social == pytest.approx(s.needs.social + MESSAGE_SOCIAL / 4)


def test_a_message_from_paolo_is_high_priority_and_interrupts_to_listen() -> None:
    s = reading_with_goal()
    out = receive_message(s, NOON, 0, RNG)
    assert out.interrupted
    assert out.state.activity is Activity.IDLE
    assert out.state.action_priority is Priority.HIGH
    assert out.state.suspended_goal == s.goal and out.state.goal is None
    assert out.state.task is None
    listening = bubble(out.state, out.state.activity_started_at)
    if out.state.route is None:
        assert listening is not None and listening.kind is BubbleKind.LISTENING


def test_a_message_never_wakes_maple_or_overrides_urgent_work() -> None:
    asleep = make_state(at=NOON, activity=Activity.SLEEP, location=RoomLocation.BED)
    out = receive_message(asleep, NOON, 0, RNG)
    assert not out.interrupted and out.state.activity is Activity.SLEEP
    urgent = replace(
        make_state(at=NOON, activity=Activity.OBSERVE_SERVER, location=RoomLocation.TERMINAL),
        action_priority=Priority.CRITICAL,
    )
    assert not receive_message(urgent, NOON, 0, RNG).interrupted


def context_for(state: MapleState, text: str) -> ReplyContext:
    return build_reply_context(
        state, NOON, message(text), utc_offset=PARAMS.utc_offset, expression="focused",
        server_summary="nothing notable in the latest observations",
        memories=["I read Maple's room: The room has a bed."],
    )  # fmt: skip


STATUS_WORDS = ("reading", "Maple's room", "Learn about the room", "mood", "อ่าน", "อารมณ์")
FORCED_PARTICLES = ("จ้ะ", "จ๊ะ", "นะจ๊ะ", "เลยจ้ะ")


def test_rule_replies_use_the_real_context() -> None:
    s = reading_with_goal()
    en = rule_reply(context_for(s, "What are you doing?"))
    assert (
        en == "Right now I'm reading “Maple's room”. My goal at the moment: Learn about the room."
    )
    server = rule_reply(context_for(s, "How is the server?"))
    assert server == "From what I can see, the server: nothing notable in the latest observations."
    idle = rule_reply(context_for(make_state(at=NOON), "what are you up to?"))
    assert "pottering about" in idle and "reading" not in idle  # never invents an activity


def test_thai_activity_question_is_grounded_and_not_a_greeting() -> None:
    th = rule_reply(context_for(reading_with_goal(), "ตอนนี้ทำอะไรอยู่?"))
    assert th == "ตอนนี้กำลังอ่าน “Maple's room” อยู่ ตั้งใจไว้ว่า Learn about the room"
    assert "สวัสดี" not in th and "Paolo" not in th
    assert not any(p in th for p in FORCED_PARTICLES)
    idle = rule_reply(context_for(make_state(at=NOON), "ทำอะไรอยู่"))
    assert idle == "ตอนนี้ว่าง ๆ ไม่ได้ทำอะไรเป็นพิเศษ"  # never invents an activity


def test_thai_server_question_stays_on_the_server_facts() -> None:
    th = rule_reply(context_for(reading_with_goal(), "เซิร์ฟเวอร์เป็นไงบ้าง"))
    assert th == "จากที่ฉันเห็น เซิร์ฟเวอร์ตอนนี้: nothing notable in the latest observations"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("อายุเท่าไหร่", "อันนี้ไม่แน่ใจเหมือนกัน"), ("How old are you?", "I'm not sure about that one."),
     ("วันนี้ฝนตกหนักมาก", "อืม ฟังอยู่นะ"), ("I had a long day.", "I hear you."),
     ("ขอบคุณนะ", "ยินดีเลย"), ("thanks!", "Anytime.")],
)  # fmt: skip
def test_unrelated_messages_get_no_status_dump(text: str, expected: str) -> None:
    reply = rule_reply(context_for(reading_with_goal(), text))
    assert reply == expected
    assert not any(word in reply for word in STATUS_WORDS)


def test_greeting_only_when_paolo_greets() -> None:
    s = reading_with_goal()
    assert rule_reply(context_for(s, "สวัสดี")) == "หวัดดี"
    assert rule_reply(context_for(s, "hello")) == "Hi, Paolo."
    both = rule_reply(context_for(s, "หวัดดี ทำอะไรอยู่"))
    assert both.startswith("หวัดดี ตอนนี้กำลังอ่าน")
    for text in ("ตอนนี้ทำอะไรอยู่?", "อายุเท่าไหร่", "What are you doing?", "1+1=?"):
        reply = rule_reply(context_for(s, text))
        assert not reply.startswith(("หวัดดี", "สวัสดี", "Hi", "Hello", "Thanks for"))


@pytest.mark.parametrize(
    ("text", "expected"),
    [("1+1=?", "1 + 1 = 2"), ("12 - 20", "12 - 20 = -8"), ("6 x 7 เท่ากับเท่าไหร่", "6 × 7 = 42"),  # noqa: RUF001
     ("9*9", "9 × 9 = 81"), ("10/4=?", "10 ÷ 4 = 2.5"), ("8 / 2", "8 ÷ 2 = 4"),  # noqa: RUF001
     ("1/0", "You can't divide by zero."), ("1/0 เท่ากับเท่าไหร่", "หารด้วยศูนย์ไม่ได้นะ")],
)  # fmt: skip
def test_simple_arithmetic_is_answered_deterministically(text: str, expected: str) -> None:
    assert rule_reply(context_for(reading_with_goal(), text)) == expected


def test_feelings_come_from_the_needs_only() -> None:
    s = reading_with_goal()
    assert rule_reply(context_for(s, "how are you?")).startswith("I'm ")
    th = rule_reply(context_for(s, "สบายดีไหม"))
    assert "อ่าน" not in th and not any(p in th for p in FORCED_PARTICLES)


def test_rule_replies_are_deterministic() -> None:
    s = reading_with_goal()
    for text in ("ตอนนี้ทำอะไรอยู่?", "อายุเท่าไหร่", "1+1=?", "hello", "server?"):
        assert rule_reply(context_for(s, text)) == rule_reply(context_for(s, text))


def test_reply_context_is_frozen_and_minimal() -> None:
    ctx = context_for(reading_with_goal(), "hi")
    data = ctx.as_json()
    assert data["contract"] == "maple.reply.v1"
    assert data["message"] == {"text": "hi", "language": "en"}
    assert SEED not in str(data)
    with pytest.raises(TypeError):
        ctx.data["activity"] = "sleep"  # type: ignore[index]


@pytest.mark.parametrize(
    ("text", "ok"),
    [("Fine, thanks!", True), ("line one\nline two", True), ("", False), ("   ", False),
     ("x" * 1501, False), ("bad\x00byte", False)],
)  # fmt: skip
def test_reply_problems(text: str, ok: bool) -> None:
    assert (reply_problems(text) == []) is ok


@pytest.mark.parametrize(
    ("external_id", "speaker", "text"),
    [("bad id!", Speaker.PAOLO, "hi"), ("1", Speaker.MAPLE, "hi"), ("1", Speaker.PAOLO, ""),
     ("1", Speaker.PAOLO, "x" * 2001)],
)  # fmt: skip
def test_only_valid_messages_from_paolo(external_id: str, speaker: Speaker, text: str) -> None:
    with pytest.raises(ValueError):
        IncomingMessage(external_id, Channel.DISCORD, speaker, text, NOON)
