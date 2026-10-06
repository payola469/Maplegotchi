"""Conversations with Paolo (ADR-0032), as pure rules.

- `receive_message`: a real message from Paolo is a social interaction (explicit
  need effects) and a high-priority signal: it interrupts a normal/low action so
  Maple stops to listen, but never wakes Maple and never overrides an urgent response.
- `build_reply_context`: the frozen `maple.reply.v1` context, built from real state
  and records only.
- `rule_reply`: an answer from those facts only (English, or Thai for Thai messages).
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
ACTIVITY_TH = {
    Activity.READ: "อ่านหนังสือ",
    Activity.WRITE: "เขียนบันทึก",
    Activity.OBSERVE_SERVER: "ดูแลเซิร์ฟเวอร์",
    Activity.THINK: "นั่งคิดอยู่ริมหน้าต่าง",
    Activity.REST: "พักผ่อนบนโซฟา",
    Activity.WALK: "เดินเล่นในห้อง",
    Activity.IDLE: "อยู่เฉย ๆ",
    Activity.SLEEP: "นอนหลับ",
}


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


def _feeling(needs: Mapping[str, Any], thai: bool) -> str:
    energy, mood = int(needs["energy"]), int(needs["mood"])
    if thai:
        tired = "ค่อนข้างเหนื่อย" if energy < 30 else "มีแรงดี"
        happy = "อารมณ์ดี" if mood >= 60 else "อารมณ์เรื่อย ๆ"
        return f"ตอนนี้{tired}และ{happy}"
    tired = "a bit tired" if energy < 30 else "fairly rested"
    happy = "in a good mood" if mood >= 60 else "in a calm mood"
    return f"I'm {tired} and {happy}"


def rule_reply(context: ReplyContext) -> str:
    """A truthful reply from the context's facts only. Deterministic."""
    c = context.data
    text = str(c["message"]["text"]).lower()
    thai = c["message"]["language"] == "th"
    activity = Activity(c["activity"])
    task = c["task"]
    goal = c["goal"]
    if thai:
        doing = ACTIVITY_TH[activity]
        if task is not None:
            doing += f" ({task['title']})"
        now_line = f"ตอนนี้ฉันกำลัง{doing}อยู่"
        goal_line = f" เป้าหมายตอนนี้คือ: {goal['summary']}" if goal else ""
        if "เซิร์ฟเวอร์" in text or "server" in text:
            return f"เรื่องเซิร์ฟเวอร์: {c['server']} {now_line}"
        if "สบายดี" in text or "เป็นไง" in text or "เหนื่อย" in text:
            return f"{_feeling(c['needs'], True)} {now_line}"
        return f"{now_line}{goal_line}"
    doing = ACTIVITY_EN[activity]
    if task is not None:
        doing += f" “{task['title']}”"
    now_line = f"Right now I'm {doing}."
    goal_line = f" My goal at the moment: {goal['summary']}." if goal else ""
    if "server" in text:
        return f"About the server: {c['server']}. {now_line}"
    if "how are you" in text or "feeling" in text or "tired" in text:
        return f"{_feeling(c['needs'], False)}. {now_line}"
    if "what" in text and ("doing" in text or "up to" in text):
        return f"{now_line}{goal_line}"
    return f"Thanks for the message, Paolo! {now_line}{goal_line}"
