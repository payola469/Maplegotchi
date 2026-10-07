"""Conversations with Paolo (ADR-0032), as pure rules.

- `receive_message`: a real message from Paolo is a social interaction (explicit
  need effects) and a high-priority signal: it interrupts a normal/low action so
  Maple stops to listen, but never wakes Maple and never overrides an urgent response.
- `build_reply_context`: the frozen `maple.reply.v1` context, built from real state
  and records only.
- `rule_reply`: a short deterministic answer to what Paolo said (English, or Thai for
  Thai messages): Maple's state only when asked about, from those facts only.
- `reply_problems`: the checks any reply (e.g. from an external replier) must pass.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from maplegotchi.core.activities import Activity
from maplegotchi.core.audit import ActionEvent
from maplegotchi.core.daytime import local_hour, require_utc
from maplegotchi.core.direction import interrupt
from maplegotchi.core.rng import RngStream
from maplegotchi.core.signals import Signal, SignalKind, interrupts
from maplegotchi.core.state import MapleState, Needs
from maplegotchi.core.timeline import LifeEvent

REPLY_CONTRACT = "maple.reply.v1"
MAX_MESSAGE = 2000
MAX_REPLY = 1500
MESSAGE_SOCIAL = 6.0
MESSAGE_MOOD = 2.0
_EXTERNAL_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
_THAI = re.compile(r"[฀-๿]")


class Channel(StrEnum):
    DISCORD = "discord"


class Speaker(StrEnum):
    PAOLO = "paolo"
    MAPLE = "maple"


def _text_problems(text: object, limit: int) -> list[str]:
    if not isinstance(text, str):
        return ["not_text"]
    problems = []
    if not 1 <= len(text.strip()) or len(text) > limit:
        problems.append("length")
    if any(not (c.isprintable() or c in "\n\t") for c in text):
        problems.append("unprintable")
    return problems


def message_problems(text: object) -> list[str]:
    return _text_problems(text, MAX_MESSAGE)


def reply_problems(text: object) -> list[str]:
    """What any reply must satisfy before it is stored or sent (empty = acceptable)."""
    return _text_problems(text, MAX_REPLY)


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    external_id: str  # the channel's message id (idempotency)
    channel: Channel
    speaker: Speaker
    text: str
    at: datetime

    def __post_init__(self) -> None:
        require_utc(self.at, "message.at")
        if not _EXTERNAL_ID.fullmatch(self.external_id):
            raise ValueError("bad external message id")
        if self.speaker is not Speaker.PAOLO:
            raise ValueError("only Paolo's messages are conversations")
        if message_problems(self.text):
            raise ValueError(f"message is not acceptable: {message_problems(self.text)}")


@dataclass(frozen=True, slots=True)
class MessageOutcome:
    state: MapleState
    events: tuple[LifeEvent, ...]
    actions: tuple[ActionEvent, ...]
    interrupted: bool


def receive_message(
    state: MapleState, now: datetime, recent_messages: int, rng: RngStream
) -> MessageOutcome:
    """Apply a message from Paolo at `now` (the caller settled any finished walk)."""
    require_utc(now, "now")
    if now < state.last_updated_at:
        raise ValueError("a message cannot precede the latest state update")
    factor = 0.5 ** max(0, recent_messages)
    needs = state.needs
    touched = replace(
        state,
        needs=Needs.clamped(
            mood=needs.mood + MESSAGE_MOOD * factor,
            energy=needs.energy,
            curiosity=needs.curiosity,
            social=needs.social + MESSAGE_SOCIAL * factor,
        ),
        last_updated_at=now,
    )
    asleep = touched.activity is Activity.SLEEP and touched.route is None
    signal = Signal(SignalKind.OWNER_MESSAGE)
    if asleep or not interrupts(signal, touched.action_priority):
        return MessageOutcome(touched, (), (), False)
    out = interrupt(touched, now, signal, rng)
    return MessageOutcome(out.state, out.events, out.actions, True)


# ---------------------------------------------------------------- replies


@dataclass(frozen=True, slots=True)
class ReplyContext:
    """Everything a replier may know; immutable and JSON-ready (maple.reply.v1)."""

    data: Mapping[str, Any]

    def as_json(self) -> dict[str, Any]:
        def thaw(value: Any) -> Any:
            if isinstance(value, Mapping):
                return {k: thaw(v) for k, v in value.items()}
            if isinstance(value, tuple):
                return [thaw(v) for v in value]
            return value

        out: dict[str, Any] = thaw(self.data)
        return out


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(v) for v in value)
    return value


def is_thai(text: str) -> bool:
    return bool(_THAI.search(text))


ACTIVITY_EN = {
    Activity.READ: "reading",
    Activity.WRITE: "writing",
    Activity.OBSERVE_SERVER: "checking on the server",
    Activity.THINK: "thinking by the window",
    Activity.REST: "resting on the sofa",
    Activity.WALK: "walking around the room",
    Activity.IDLE: "pottering about",
    Activity.SLEEP: "sleeping",
}
# Whole Thai sentences: natural word order, no particle forced onto each one.
ACTIVITY_TH = {
    Activity.READ: "ตอนนี้กำลังอ่านหนังสืออยู่",
    Activity.WRITE: "ตอนนี้กำลังเขียนบันทึกอยู่",
    Activity.OBSERVE_SERVER: "ตอนนี้กำลังดูเซิร์ฟเวอร์อยู่",
    Activity.THINK: "ตอนนี้นั่งคิดอะไรเพลิน ๆ อยู่ริมหน้าต่าง",
    Activity.REST: "ตอนนี้นอนพักอยู่บนโซฟา",
    Activity.WALK: "ตอนนี้เดินเล่นอยู่ในห้อง",
    Activity.IDLE: "ตอนนี้ว่าง ๆ ไม่ได้ทำอะไรเป็นพิเศษ",
    Activity.SLEEP: "ตอนนี้กำลังนอนอยู่",
}
TASK_TH = {Activity.READ: "ตอนนี้กำลังอ่าน “{}” อยู่", Activity.WRITE: "ตอนนี้กำลังเขียน “{}” อยู่"}


def build_reply_context(
    state: MapleState,
    now: datetime,
    message: IncomingMessage,
    *,
    utc_offset: timedelta,
    expression: str,
    server_summary: str,
    memories: Sequence[str] = (),
    conversation: Sequence[tuple[str, str]] = (),  # (speaker, text), oldest first
) -> ReplyContext:
    """Facts for a reply, from real state and records only."""
    require_utc(now, "now")
    goal = state.goal
    task = state.task
    data = {
        "contract": REPLY_CONTRACT,
        "maple": {"name": state.identity.name},
        "local_hour": round(local_hour(now, utc_offset), 2),
        "activity": state.activity.value,
        "walking": state.walking_at(now),
        "task": {"tool": task.tool.value, "title": task.title} if task else None,
        "goal": {"type": goal.type.value, "summary": goal.summary} if goal else None,
        "priority": state.action_priority.value,
        "expression": expression,
        "needs": {
            "mood": round(state.needs.mood),
            "energy": round(state.needs.energy),
            "social": round(state.needs.social),
            "curiosity": round(state.needs.curiosity),
        },
        "server": server_summary,
        "memories": list(memories)[:5],
        "conversation": [{"speaker": s, "text": t[:500]} for s, t in list(conversation)[-6:]],
        "message": {"text": message.text, "language": "th" if is_thai(message.text) else "en"},
    }
    return ReplyContext(_freeze(data))


# What a message is about, for the rule replier. Narrow keyword rules on purpose:
# the rule replier answers about Maple from the facts, does a little arithmetic, and
# otherwise says honestly and briefly that it has no answer; it is not a chatbot.
TIMES, DIVIDE = "×", "÷"  # noqa: RUF001 (the multiplication and division signs)
_ARITHMETIC = re.compile(
    r"\s*(-?\d{1,9})\s*([-+*/x×÷])\s*(-?\d{1,9})\s*(?:=|เท่ากับ|ได้)?\s*"  # noqa: RUF001
    r"(?:เท่าไหร่|เท่าไร|อะไร)?\s*(?:\?|？)*\s*"  # noqa: RUF001
)
_SERVER = re.compile(r"\bserver\b|เซิร์ฟเวอร์|เซิฟ")
_DOING = re.compile(r"\bwhat\b.*\b(doing|up to)\b|\bwhat'?s up\b|ทำอะไร|ทําอะไร")
_GOAL = re.compile(r"\bgoals?\b|\bplans?\b|เป้าหมาย|ตั้งใจ|แผน")
_FEELING = re.compile(
    r"\bhow are you\b|\bhow'?re you\b|\bfeel(ing)?\b|\btired\b"
    r"|สบายดี|เป็นไง|เป็นยังไง|เหนื่อย|โอเคไหม|โอเคมั้ย"
)
_THANKS = re.compile(r"\bthanks?\b|\bthank you\b|\bty\b|ขอบคุณ|ขอบใจ")
_GREETING = re.compile(r"^\s*(hi|hello|hey|yo|good (morning|afternoon|evening))\b|สวัสดี|หวัดดี|ดีจ้า")
_QUESTION = re.compile(
    r"\?|？|^\s*(what|who|why|when|where|how|which|do|does|did|are|is|can|could|will|would)\b"  # noqa: RUF001
    r"|ไหม|มั้ย|อะไร|ยังไง|อย่างไร|เท่าไหร่|เท่าไร|ทำไม|ที่ไหน|เมื่อไหร่|ใคร|หรือเปล่า|รึเปล่า|ป่าว"
)


def _arithmetic(text: str, thai: bool) -> str | None:
    """`a op b` with small integers, e.g. "1+1=?" or "6 x 7 เท่ากับเท่าไหร่"."""
    m = _ARITHMETIC.fullmatch(text)
    if m is None:
        return None
    a, op, b = int(m[1]), m[2], int(m[3])
    times, divide = op in ("*", "x", TIMES), op in ("/", DIVIDE)
    shown = TIMES if times else DIVIDE if divide else op
    if not (times or divide):
        value = str(a + b if op == "+" else a - b)
    elif times:
        value = str(a * b)
    elif b == 0:
        return "หารด้วยศูนย์ไม่ได้นะ" if thai else "You can't divide by zero."
    elif a % b == 0:
        value = str(a // b)
    else:
        value = f"{a / b:.6g}"
    return f"{a} {shown} {b} = {value}"


def _doing(c: Mapping[str, Any], thai: bool) -> str:
    activity, task, goal = Activity(c["activity"]), c["task"], c["goal"]
    if thai:
        if task is not None and activity in TASK_TH:
            line = TASK_TH[activity].format(task["title"])
        else:
            line = ACTIVITY_TH[activity]
            if task is not None:
                line += f" (“{task['title']}”)"
        return line + (f" ตั้งใจไว้ว่า {goal['summary']}" if goal else "")
    doing = ACTIVITY_EN[activity]
    if task is not None:
        doing += f" “{task['title']}”"
    goal_line = f" My goal at the moment: {goal['summary']}." if goal else ""
    return f"Right now I'm {doing}.{goal_line}"


def _goal(c: Mapping[str, Any], thai: bool) -> str:
    goal = c["goal"]
    if thai:
        return f"ตอนนี้ตั้งใจไว้ว่า {goal['summary']}" if goal else "ตอนนี้ยังไม่ได้ตั้งเป้าอะไรเป็นพิเศษ"
    return (
        f"My goal at the moment: {goal['summary']}." if goal else "I don't have a goal right now."
    )


def _feeling(needs: Mapping[str, Any], thai: bool) -> str:
    tired, happy = int(needs["energy"]) < 30, int(needs["mood"]) >= 60
    if thai:
        body = "ค่อนข้างเหนื่อยนิดหน่อย" if tired else "ยังมีแรงดีอยู่"
        mood = "อารมณ์ดีด้วย" if happy else "อารมณ์ก็เรื่อย ๆ"
        return f"{body} {mood}"
    body = "a bit tired" if tired else "fairly rested"
    mood = "in a good mood" if happy else "in a calm mood"
    return f"I'm {body} and {mood}."


def _server(c: Mapping[str, Any], thai: bool) -> str:
    if thai:
        return f"จากที่ฉันเห็น เซิร์ฟเวอร์ตอนนี้: {c['server']}"
    return f"From what I can see, the server: {c['server']}."


def rule_reply(context: ReplyContext) -> str:
    """A short, truthful reply to what Paolo said. Deterministic.

    Maple's state is mentioned only when the message asks about it; anything about
    Maple or the server comes from the context's facts only. Paolo is greeted back
    only when Paolo greeted.
    """
    c = context.data
    raw = str(c["message"]["text"])
    text = raw.lower()
    thai = c["message"]["language"] == "th"
    maths = _arithmetic(raw, thai)
    if maths is not None:
        return maths
    if _SERVER.search(text):
        answer = _server(c, thai)
    elif _DOING.search(text):
        answer = _doing(c, thai)
    elif _GOAL.search(text):
        answer = _goal(c, thai)
    elif _FEELING.search(text):
        answer = _feeling(c["needs"], thai)
    elif _THANKS.search(text):
        answer = "ยินดีเลย" if thai else "Anytime."
    elif _GREETING.search(text):
        return "หวัดดี" if thai else "Hi, Paolo."
    elif _QUESTION.search(text):
        answer = "อันนี้ไม่แน่ใจเหมือนกัน" if thai else "I'm not sure about that one."
    else:
        answer = "อืม ฟังอยู่นะ" if thai else "I hear you."
    if _GREETING.search(text):
        return f"{'หวัดดี' if thai else 'Hi!'} {answer}"
    return answer
