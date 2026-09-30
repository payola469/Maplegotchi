"""Maple's journal: subjective interpretation, kept apart from facts (D8).

Division of labour:
- core decides WHETHER to write (triggers, deduplication, daily window — see
  core/reflection.py) and WHAT each entry may refer to (a trigger's
  observation keys, taken from real observations);
- a Brain decides only HOW to say it (JournalDraft text per trigger);
- `accept_drafts` validates every draft before it becomes a JournalEntry.

Grounding rules enforced here:
- an entry's observation references come from its trigger, never the Brain;
- trigger references must exist in the snapshot the Brain was shown;
- journal text names no service that its trigger does not reference;
- one entry per trigger at most; the category follows the trigger kind.

Journal text itself is only structurally constrained (bounded, one printable
line). Numbers are not banned here: a future grounded entry may legitimately
say "96%" or "21:00". The built-in RuleBrain's templates are digit-free as a
v0.1 *template policy* (brain/rule_brain.py), not as a journal invariant.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from maplegotchi.core.activities import Activity
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.observations import Metric, ObservationSnapshot
from maplegotchi.core.state import Expression, MapleState, ReactionKind


class JournalCategory(StrEnum):
    DAILY_LIFE = "daily_life"
    SERVER_NOTICE = "server_notice"
    INTERACTION = "interaction"
    REFLECTION = "reflection"
    MILESTONE = "milestone"


class Importance(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class BrainKind(StrEnum):
    RULE = "rule"  # the built-in, offline, deterministic RuleBrain
    EXTERNAL = "external"  # reserved for a future provider; never wired in v0.1


class TriggerKind(StrEnum):
    ACTIVITY = "activity"
    INTERACTION = "interaction"
    SERVER_PROBLEM = "server_problem"
    SERVER_RECOVERY = "server_recovery"
    DAILY_REFLECTION = "daily_reflection"
    MILESTONE = "milestone"


class ServerSummary(StrEnum):
    """What the daily reflection may truthfully say about the server."""

    CALM = "calm"  # everything relevant observed and fine
    UNCLEAR = "unclear"  # nothing wrong among what was seen, but some things were not seen
    TROUBLED_EARLIER = "troubled_earlier"  # a problem was noticed today and has cleared
    STILL_TROUBLED = "still_troubled"  # a problem is still active
    NO_DATA = "no_data"  # no usable observations


CATEGORY_FOR_TRIGGER: Mapping[TriggerKind, JournalCategory] = MappingProxyType(
    {
        TriggerKind.ACTIVITY: JournalCategory.DAILY_LIFE,
        TriggerKind.INTERACTION: JournalCategory.INTERACTION,
        TriggerKind.SERVER_PROBLEM: JournalCategory.SERVER_NOTICE,
        TriggerKind.SERVER_RECOVERY: JournalCategory.SERVER_NOTICE,
        TriggerKind.DAILY_REFLECTION: JournalCategory.REFLECTION,
        TriggerKind.MILESTONE: JournalCategory.MILESTONE,
    }
)

# How Maple refers to the D12 services. Used by the Brain for wording and by the
# validator to catch mentions of services a trigger does not reference.
SERVICE_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "maplegotchi": "my own service",
        "metrics_collector": "the metrics collector",
        "grafana": "Grafana",
        "lycan_watch": "Lycan Watch",
        "qbittorrent": "qBittorrent",
        "jellyfin": "Jellyfin",
        "backup": "the backups",
    }
)

MAX_TEXT_LENGTH = 240
_TOPIC = re.compile(r"[a-z0-9_:./-]{1,80}")
_LABEL = re.compile(r"[a-z0-9_]{0,40}")
_NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")
_VERSION = re.compile(r"[a-z0-9._-]{1,16}")

ObservationKey = tuple[Metric, str]


def text_problems(text: object) -> list[str]:
    """Structural problems with journal text (empty list = acceptable).

    Bounded length, trimmed, one printable line (no newlines or control
    characters). Content rules belong to Brain policies, not to the journal.
    """
    if not isinstance(text, str):
        return ["not_text"]
    problems = []
    if not 1 <= len(text) <= MAX_TEXT_LENGTH or text != text.strip():
        problems.append("length")
    if not text.isprintable():
        problems.append("unprintable")  # includes line breaks
    return problems


def mentioned_services(text: str) -> frozenset[str]:
    lowered = text.lower()
    return frozenset(sid for sid, name in SERVICE_NAMES.items() if name.lower() in lowered)


@dataclass(frozen=True, slots=True)
class Trigger:
    """A reason to write, detected by core. The Brain only words it."""

    kind: TriggerKind
    topic: str  # stable dedup key, e.g. "service:jellyfin", "daily:read", "reflection"
    label: str = ""  # e.g. "failed", "woke", "greet", "one_week"
    subject: str = ""  # service id, mount, or ""
    observation_keys: tuple[ObservationKey, ...] = ()
    reaction: ReactionKind | None = None  # interactions
    summary: ServerSummary | None = None  # daily reflection
    day_activities: tuple[str, ...] = ()  # daily reflection: notable things done today
    interactions_today: int = 0  # daily reflection

    def __post_init__(self) -> None:
        if not isinstance(self.kind, TriggerKind):
            raise TypeError("kind must be a TriggerKind")
        if not _TOPIC.fullmatch(self.topic) or not _LABEL.fullmatch(self.label):
            raise ValueError("invalid trigger topic or label")
        if self.interactions_today < 0:
            raise ValueError("interactions_today must be >= 0")

    def referenced_services(self) -> frozenset[str]:
        services = {s for m, s in self.observation_keys if m is Metric.SERVICE_STATE}
        if self.kind in (TriggerKind.SERVER_PROBLEM, TriggerKind.SERVER_RECOVERY) and self.subject:
            services.add(self.subject)
        return frozenset(services)


@dataclass(frozen=True, slots=True)
class BrainContext:
    """Everything a Brain may see: plain data, no handles or capabilities."""

    now: datetime
    local_hour: float
    owner_name: str
    state: MapleState
    expression: Expression
    snapshot: ObservationSnapshot | None
    triggers: tuple[Trigger, ...]

    def __post_init__(self) -> None:
        require_utc(self.now, "now")


@dataclass(frozen=True, slots=True)
class JournalDraft:
    """A Brain's proposed wording for one trigger. Untrusted until accepted."""

    trigger_index: int
    text: str
    importance: Importance
    template_id: str


@dataclass(frozen=True, slots=True)
class JournalEntry:
    created_at: datetime
    category: JournalCategory
    trigger: TriggerKind
    topic: str
    text: str
    importance: Importance
    brain_kind: BrainKind
    brain_name: str
    brain_version: str
    template_id: str
    activity: Activity  # Maple's context when writing
    expression: Expression
    observation_keys: tuple[ObservationKey, ...]  # facts this entry interprets
    tick_id: int | None  # heartbeat that produced it; None for interactions

    def __post_init__(self) -> None:
        require_utc(self.created_at, "created_at")
        if CATEGORY_FOR_TRIGGER.get(self.trigger) is not self.category:
            raise ValueError("category does not match trigger kind")
        if problems := text_problems(self.text):
            raise ValueError(f"invalid journal text: {problems}")
        if not isinstance(self.importance, Importance) or not isinstance(
            self.brain_kind, BrainKind
        ):
            raise TypeError("importance and brain_kind must be enums")
        if not _NAME.fullmatch(self.brain_name) or not _VERSION.fullmatch(self.brain_version):
            raise ValueError("invalid brain name or version")
        if not _TOPIC.fullmatch(self.topic) or not _TOPIC.fullmatch(self.template_id):
            raise ValueError("invalid topic or template id")
        if not isinstance(self.activity, Activity) or not isinstance(self.expression, Expression):
            raise TypeError("activity and expression must be enums")
        if self.tick_id is not None and self.tick_id < 1:
            raise ValueError("tick_id must be >= 1")
        if self.observation_keys and self.tick_id is None:
            raise ValueError("observation references belong to a heartbeat")


def accept_drafts(
    context: BrainContext,
    drafts: Sequence[object],
    *,
    brain_kind: BrainKind,
    brain_name: str,
    brain_version: str,
    tick_id: int | None,
) -> tuple[JournalEntry, ...]:
    """Validate a Brain's drafts against the triggers it was given.

    Invalid drafts are dropped, never repaired: out-of-range or duplicate
    trigger, malformed text, digits, or naming an unreferenced service.
    """
    available_keys = (
        {(o.metric, o.subject) for o in context.snapshot.observations}
        if context.snapshot is not None
        else set()
    )
    accepted: dict[int, JournalEntry] = {}
    for draft in drafts:
        if not isinstance(draft, JournalDraft):
            continue
        index = draft.trigger_index
        if isinstance(index, bool) or not isinstance(index, int):
            continue
        if not 0 <= index < len(context.triggers) or index in accepted:
            continue
        trigger = context.triggers[index]
        if any(key not in available_keys for key in trigger.observation_keys):
            continue  # a reference to something not actually observed
        if text_problems(draft.text) or not isinstance(draft.importance, Importance):
            continue
        if not mentioned_services(draft.text) <= trigger.referenced_services():
            continue  # names a service the facts do not concern
        try:
            accepted[index] = JournalEntry(
                created_at=context.now,
                category=CATEGORY_FOR_TRIGGER[trigger.kind],
                trigger=trigger.kind,
                topic=trigger.topic,
                text=draft.text,
                importance=draft.importance,
                brain_kind=brain_kind,
                brain_name=brain_name,
                brain_version=brain_version,
                template_id=draft.template_id,
                activity=context.state.activity,
                expression=context.expression,
                observation_keys=trigger.observation_keys,
                tick_id=tick_id,
            )
        except (TypeError, ValueError):
            continue
    return tuple(accepted[i] for i in sorted(accepted))
