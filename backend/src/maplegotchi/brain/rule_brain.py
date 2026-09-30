"""RuleBrain: Maple's built-in, offline, deterministic voice (v0.1 default, D10).

Every sentence comes from a fixed template chosen by the trigger and Maple's
state; the variant is picked by hashing the trigger topic and time, so the same
input always yields the same words. It only names things its trigger is about.
It is not a text generator.

v0.1 template policy: RuleBrain output never contains digits, so it can never
quote (or misquote) a value. This is a policy of this Brain, enforced here and
by tests; the journal itself allows grounded numbers from future Brains.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from maplegotchi.core.activities import Activity
from maplegotchi.core.journal import (
    SERVICE_NAMES,
    BrainContext,
    BrainKind,
    Importance,
    JournalDraft,
    ServerSummary,
    Trigger,
    TriggerKind,
)
from maplegotchi.core.state import ReactionKind

_DAILY: dict[str, tuple[str, ...]] = {
    "woke": ("I woke up and stretched.", "Morning. I'm awake and ready to look around."),
    "sleep": ("I curled up in bed for some sleep.", "Time to rest my eyes for a while."),
    "read": (
        "I spent some time reading at the bookshelf.",
        "I found something interesting to read.",
    ),
    "write": ("I sat at my desk and wrote for a while.", "I wrote down a few thoughts at my desk."),
    "observe": (
        "I checked on the server from my terminal.",
        "I took a look at how the server is doing.",
    ),
}
_PROBLEM: dict[str, tuple[str, ...]] = {
    "failed": ("I noticed {name} isn't doing well. I'll keep an eye on it.",),
    "nearly_full": ("The disk is getting very full. I'll keep watching it.",),
    "high": ("The server's memory looks very full right now.",),
    "hot": ("The server is running hot. I hope it cools down soon.",),
    "busy": ("The server is working very hard right now.",),
}
_RECOVERY: dict[str, tuple[str, ...]] = {
    "failed": ("{name} seems to be back to normal. That's a relief.",),
    "nearly_full": ("The disk has a little more room again.",),
    "high": ("The server's memory has settled down.",),
    "hot": ("The server has cooled down again.",),
    "busy": ("The server is taking it easier now.",),
}
_MILESTONE: dict[str, str] = {
    "first_heartbeat": "Everything feels new. This little room is my home now.",
    "one_day": "I've been alive for a whole day now.",
    "one_week": "A whole week in this room already.",
    "one_month": "A month has passed since I first woke up here.",
    "one_year": "A whole year has gone by. What a journey.",
}
_SERVER_SENTENCE: dict[ServerSummary, str] = {
    ServerSummary.CALM: "The server seemed calm today.",
    ServerSummary.UNCLEAR: "I couldn't see everything on the server clearly today.",
    ServerSummary.TROUBLED_EARLIER: "The server had a rough moment today, but it's steadier now.",
    ServerSummary.STILL_TROUBLED: "Some things on the server still need watching.",
    ServerSummary.NO_DATA: "I didn't get a good look at the server today.",
}
_ACTIVITY_SENTENCE = {
    "read": "I spent some time reading.",
    "write": "I wrote a little.",
    "observe": "I checked on the server now and then.",
}


def follows_template_policy(text: str) -> bool:
    """v0.1 RuleBrain policy: no digits in anything it writes."""
    return not any(ch.isdigit() for ch in text)


def _pick(options: Sequence[str], context: BrainContext, trigger: Trigger) -> tuple[int, str]:
    digest = hashlib.sha256(f"{trigger.topic}|{context.now.isoformat()}".encode()).digest()
    index = digest[0] % len(options)
    return index, options[index]


class RuleBrain:
    kind = BrainKind.RULE
    name = "rule_brain"
    version = "1"

    def compose_journal(self, context: BrainContext) -> tuple[JournalDraft, ...]:
        drafts = []
        for index, trigger in enumerate(context.triggers):
            worded = self._word(trigger, context)
            if worded is not None and follows_template_policy(worded[0]):
                text, importance, template = worded
                drafts.append(JournalDraft(index, text, importance, template))
        return tuple(drafts)

    def _word(self, t: Trigger, ctx: BrainContext) -> tuple[str, Importance, str] | None:
        if t.kind is TriggerKind.ACTIVITY and t.label in _DAILY:
            n, text = _pick(_DAILY[t.label], ctx, t)
            return text, Importance.LOW, f"daily.{t.label}.{n}"
        if t.kind is TriggerKind.INTERACTION and t.reaction is not None:
            return self._interaction(t.reaction, t, ctx)
        if t.kind in (TriggerKind.SERVER_PROBLEM, TriggerKind.SERVER_RECOVERY):
            table = _PROBLEM if t.kind is TriggerKind.SERVER_PROBLEM else _RECOVERY
            if t.label not in table:
                return None
            name = SERVICE_NAMES.get(t.subject, "")
            if t.label == "failed" and not name:
                return None  # no safe way to name it
            n, text = _pick(table[t.label], ctx, t)
            text = text.format(name=name)
            text = text[0].upper() + text[1:]
            problem = t.kind is TriggerKind.SERVER_PROBLEM
            importance = Importance.HIGH if problem else Importance.NORMAL
            return text, importance, f"server.{t.kind.value}.{t.label}.{n}"
        if t.kind is TriggerKind.MILESTONE and t.label in _MILESTONE:
            return _MILESTONE[t.label], Importance.NORMAL, f"milestone.{t.label}"
        if t.kind is TriggerKind.DAILY_REFLECTION and t.summary is not None:
            return self._reflection(t.summary, t, ctx)
        return None

    def _interaction(
        self, reaction: ReactionKind, t: Trigger, ctx: BrainContext
    ) -> tuple[str, Importance, str]:
        owner = ctx.owner_name
        asleep = ctx.state.activity is Activity.SLEEP
        options: dict[ReactionKind, tuple[str, ...]] = {
            ReactionKind.GREET_HAPPY: (
                f"{owner} said hello. It made me happy.",
                f"{owner} stopped by to say hi.",
            ),
            ReactionKind.GREET_SLEEPY: (
                (f"I think I heard {owner} say hello while I was sleeping.",)
                if asleep
                else (f"{owner} said hello, but I was too drowsy to say much.",)
            ),
            ReactionKind.PET_HAPPY: (f"{owner} stopped by and gave me a little pat.",),
            ReactionKind.PET_SLEEPY: (
                ("I felt a gentle pat while I was sleeping.",)
                if asleep
                else (f"{owner} gave me a pat while I was feeling drowsy.",)
            ),
        }
        n, text = _pick(options[reaction], ctx, t)
        state = "asleep" if asleep else "awake"
        return text, Importance.NORMAL, f"interaction.{reaction.value}.{state}.{n}"

    def _reflection(
        self, summary: ServerSummary, t: Trigger, ctx: BrainContext
    ) -> tuple[str, Importance, str]:
        sentences = [_SERVER_SENTENCE[summary]]
        doing = next((k for k in ("read", "write", "observe") if k in t.day_activities), None)
        if doing:
            sentences.append(_ACTIVITY_SENTENCE[doing])
        if t.interactions_today:
            sentences.append(f"{ctx.owner_name} stopped by, which was nice.")
        else:
            sentences.append("It was a quiet day on my own.")
        company = "owner" if t.interactions_today else "alone"
        template = f"reflection.{summary.value}.{doing or 'none'}.{company}"
        return " ".join(sentences), Importance.NORMAL, template
