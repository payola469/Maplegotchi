"""Maple's memory (ADR-0030), as pure rules.

- `memories_from` turns what a transition produced (life events, reader/writer
  records) into new short-term memories, with dedup keys.
- `consolidate` moves expired short-term memories to the archive; nothing is
  promoted automatically.
- `promote`, `reinforce_preference`, `confirm_preference`, `reject_preference`
  are the only ways into long-term memory: explicit promotion, or a preference
  with evidence on enough distinct days (or an explicit confirmation).
- `retrieve` returns a few relevant memories (never the archive) for decisions
  and writing; `search` covers every tier for people looking back.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import StrEnum

from maplegotchi.core.daytime import require_utc
from maplegotchi.core.goals import GoalType
from maplegotchi.core.tasks import ToolOp, ToolRecord, one_line
from maplegotchi.core.timeline import (
    GoalAbandoned,
    GoalCompleted,
    GoalSuspended,
    InteractionAccepted,
    LifeEvent,
)

SHORT_TERM_TTL = timedelta(hours=36)
PREFERENCE_DAYS = 3  # distinct local days of evidence before a preference is accepted
MAX_MEMORY_TEXT = 240
RETRIEVE_LIMIT = 5
_WORD = re.compile(r"[a-z][a-z-]{3,}")
_STOP = frozenset({"this", "that", "with", "from", "have", "about", "what", "when", "into",
                   "again", "some", "while", "been", "were", "they", "their", "there"})  # fmt: skip


class MemoryKind(StrEnum):
    EVENT = "event"
    GOAL_OUTCOME = "goal_outcome"
    READING = "reading"
    WRITING = "writing"
    INTERACTION = "interaction"
    CONVERSATION = "conversation"
    KNOWLEDGE = "knowledge"
    MOMENT = "moment"
    PREFERENCE = "preference"


class Tier(StrEnum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    ARCHIVE = "archive"


class MemoryStatus(StrEnum):
    ACTIVE = "active"
    CANDIDATE = "candidate"  # preferences only: not yet believed
    ACCEPTED = "accepted"  # preferences only: evidence or confirmation
    REJECTED = "rejected"  # preferences only: explicitly denied


class MemoryEventKind(StrEnum):
    CREATED = "created"
    REINFORCED = "reinforced"
    PROMOTED = "promoted"
    ARCHIVED = "archived"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class Memory:
    """One memory. `id` is None until stored."""

    kind: MemoryKind
    tier: Tier
    status: MemoryStatus
    text: str
    created_at: datetime
    last_seen_at: datetime
    key: str | None = None  # dedup / identity, e.g. "goal:3" or "prefers:read"
    source: str | None = None  # where it came from, e.g. "tool:12", "goal:3"
    importance: float = 0.3
    evidence_days: tuple[date, ...] = ()  # distinct local days with evidence
    id: int | None = None

    def __post_init__(self) -> None:
        require_utc(self.created_at, "memory.created_at")
        require_utc(self.last_seen_at, "memory.last_seen_at")
        if not 1 <= len(self.text) <= MAX_MEMORY_TEXT or not self.text.isprintable():
            raise ValueError("memory text must be one printable line of 1-240 chars")
        if not 0.0 <= self.importance <= 1.0:
            raise ValueError("importance must be within [0, 1]")
        is_pref = self.kind is MemoryKind.PREFERENCE
        if is_pref == (self.status is MemoryStatus.ACTIVE):
            raise ValueError("only preferences have candidate/accepted/rejected status")
        if self.status is MemoryStatus.ACCEPTED and self.tier is not Tier.LONG_TERM:
            raise ValueError("an accepted preference lives in long-term memory")
        if list(self.evidence_days) != sorted(set(self.evidence_days)):
            raise ValueError("evidence days must be distinct and ordered")


@dataclass(frozen=True, slots=True)
class MemoryEvent:
    kind: MemoryEventKind
    at: datetime
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryChange:
    """A new or updated memory and what happened to it (both stored together)."""

    memory: Memory
    event: MemoryEvent


def local_day(now: datetime, utc_offset: timedelta) -> date:
    return (now + utc_offset).date()


# ---------------------------------------------------------------- creation


def memories_from(
    events: Sequence[LifeEvent],
    tools: Sequence[ToolRecord],
    now: datetime,
    utc_offset: timedelta,
) -> tuple[Memory, ...]:
    """New short-term memories for what one transition produced (pure)."""
    require_utc(now, "now")
    day = local_day(now, utc_offset).isoformat()
    out: list[Memory] = []

    def add(kind: MemoryKind, text: str, key: str, source: str, importance: float) -> None:
        out.append(
            Memory(
                kind=kind,
                tier=Tier.SHORT_TERM,
                status=MemoryStatus.ACTIVE,
                text=one_line(text, MAX_MEMORY_TEXT),
                created_at=now,
                last_seen_at=now,
                key=key,
                source=source,
                importance=importance,
            )
        )

    for event in events:
        if isinstance(event, GoalCompleted | GoalAbandoned):
            how = event.reason.value.replace("_", " ")
            goal = f"a {event.goal_type.value} goal"
            done = isinstance(event, GoalCompleted)
            text = f"I finished {goal} ({how})." if done else f"I set {goal} aside ({how})."
            key = f"goal:{event.goal_id}"
            add(MemoryKind.GOAL_OUTCOME, text, key, key, 0.5 if done else 0.4)
        elif isinstance(event, GoalSuspended) and event.cause == "server_problem":
            text = "Something was seriously wrong with the server, so I went to look."
            add(MemoryKind.EVENT, text, f"server_problem:{day}", f"goal:{event.goal_id}", 0.7)
        elif isinstance(event, InteractionAccepted):
            verb = "greeted" if event.kind.value == "greet" else "petted"
            key = f"interaction:{event.kind.value}:{day}"
            add(MemoryKind.INTERACTION, f"Paolo {verb} me today.", key, "interaction", 0.5)
    for record in tools:
        if record.op is ToolOp.READ_COMPLETED and record.success:
            gist = f": {record.detail}" if record.detail else "."
            key = f"read:{record.task.target}:{day}"
            add(MemoryKind.READING, f"I read {record.task.title}{gist}", key, record.task.target,
                0.4)  # fmt: skip
        elif record.op is ToolOp.WRITE_COMPLETED and record.success:
            title = record.document.title if record.document else record.task.title
            source = f"action:{record.action_id}"
            add(MemoryKind.WRITING, f"I wrote {title}.", f"write:{record.action_id}", source, 0.4)
    # One memory per key within a transition.
    unique: dict[str | None, Memory] = {}
    for m in out:
        unique.setdefault(m.key, m)
    return tuple(unique.values())


# ---------------------------------------------------------------- lifecycle


def consolidate(items: Sequence[Memory], now: datetime) -> tuple[MemoryChange, ...]:
    """Expired short-term memories go to the archive. Nothing is promoted here."""
    require_utc(now, "now")
    changes = []
    for m in items:
        if m.tier is Tier.SHORT_TERM and now - m.created_at >= SHORT_TERM_TTL:
            if m.kind is MemoryKind.PREFERENCE:
                continue  # candidates wait for evidence; they are not "recent events"
            changes.append(
                MemoryChange(
                    replace(m, tier=Tier.ARCHIVE), MemoryEvent(MemoryEventKind.ARCHIVED, now)
                )
            )
    return tuple(changes)


def promote(memory: Memory, now: datetime, reason: str) -> MemoryChange:
    """Explicitly move a memory into long-term memory (e.g. chosen by Daily Reflection)."""
    if memory.kind is MemoryKind.PREFERENCE:
        raise ValueError("preferences are promoted by evidence or confirmation, not directly")
    if memory.tier is Tier.LONG_TERM:
        raise ValueError("already in long-term memory")
    promoted = replace(memory, tier=Tier.LONG_TERM, last_seen_at=max(memory.last_seen_at, now))
    return MemoryChange(promoted, MemoryEvent(MemoryEventKind.PROMOTED, now, one_line(reason, 200)))


def new_preference(key: str, text: str, now: datetime, day: date) -> MemoryChange:
    """A preference starts as a candidate, with one day of evidence."""
    memory = Memory(
        kind=MemoryKind.PREFERENCE,
        tier=Tier.SHORT_TERM,
        status=MemoryStatus.CANDIDATE,
        text=one_line(text, MAX_MEMORY_TEXT),
        created_at=now,
        last_seen_at=now,
        key=key,
        source="behavior",
        importance=0.5,
        evidence_days=(day,),
    )
    return MemoryChange(memory, MemoryEvent(MemoryEventKind.CREATED, now))


def reinforce_preference(memory: Memory, now: datetime, day: date) -> MemoryChange | None:
    """Evidence on another day; accepted once it holds on PREFERENCE_DAYS distinct days."""
    if memory.kind is not MemoryKind.PREFERENCE or memory.status is not MemoryStatus.CANDIDATE:
        return None
    if day in memory.evidence_days:
        return None  # one statement or one busy day never counts twice
    days = tuple(sorted((*memory.evidence_days, day)))
    if len(days) >= PREFERENCE_DAYS:
        accepted = replace(memory, evidence_days=days, status=MemoryStatus.ACCEPTED,
                           tier=Tier.LONG_TERM, last_seen_at=now)  # fmt: skip
        return MemoryChange(accepted, MemoryEvent(MemoryEventKind.PROMOTED, now, "evidence"))
    reinforced = replace(memory, evidence_days=days, last_seen_at=now)
    return MemoryChange(reinforced, MemoryEvent(MemoryEventKind.REINFORCED, now))


def confirm_preference(memory: Memory, now: datetime) -> MemoryChange:
    """An explicit confirmation (e.g. Paolo says so) accepts a candidate."""
    if memory.kind is not MemoryKind.PREFERENCE or memory.status is MemoryStatus.REJECTED:
        raise ValueError("only a non-rejected preference can be confirmed")
    accepted = replace(memory, status=MemoryStatus.ACCEPTED, tier=Tier.LONG_TERM, last_seen_at=now)
    return MemoryChange(accepted, MemoryEvent(MemoryEventKind.CONFIRMED, now))


def reject_preference(memory: Memory, now: datetime) -> MemoryChange:
    if memory.kind is not MemoryKind.PREFERENCE:
        raise ValueError("only preferences can be rejected")
    rejected = replace(memory, status=MemoryStatus.REJECTED, tier=Tier.ARCHIVE, last_seen_at=now)
    return MemoryChange(rejected, MemoryEvent(MemoryEventKind.REJECTED, now))


# ---------------------------------------------------------------- retrieval


def words(text: str) -> frozenset[str]:
    return frozenset(w for w in _WORD.findall(text.lower()) if w not in _STOP)


@dataclass(frozen=True, slots=True)
class MemoryQuery:
    text: str = ""  # e.g. goal summary + current activity
    goal_type: GoalType | None = None
    include_archive: bool = False


def _score(m: Memory, query_words: frozenset[str], now: datetime) -> float:
    overlap = len(words(m.text) & query_words)
    tier = {Tier.LONG_TERM: 1.0, Tier.SHORT_TERM: 0.8, Tier.ARCHIVE: 0.3}[m.tier]
    hours = max(0.0, (now - m.last_seen_at).total_seconds() / 3600)
    recency = 1.0 / (1.0 + hours / 24.0)
    evidence = min(len(m.evidence_days), PREFERENCE_DAYS) * 0.1
    return overlap * 1.0 + tier * 0.5 + m.importance * 0.6 + recency * 0.4 + evidence


def retrieve(
    items: Sequence[Memory], query: MemoryQuery, now: datetime, limit: int = RETRIEVE_LIMIT
) -> tuple[Memory, ...]:
    """The few most relevant memories (archive excluded unless asked). Deterministic."""
    require_utc(now, "now")
    terms = words(query.text) | (words(query.goal_type.value) if query.goal_type else frozenset())
    usable = [
        m
        for m in items
        if (query.include_archive or m.tier is not Tier.ARCHIVE)
        and m.status is not MemoryStatus.REJECTED
    ]
    ranked = sorted(usable, key=lambda m: (-_score(m, terms, now), -(m.id or 0), m.text))
    return tuple(ranked[:limit])


def search(items: Sequence[Memory], text: str, limit: int = 20) -> tuple[Memory, ...]:
    """Keyword search across every tier, for people looking back (archive included)."""
    terms = words(text)
    if not terms:
        return ()
    hits = [m for m in items if words(m.text) & terms]
    hits.sort(key=lambda m: (-len(words(m.text) & terms), -(m.id or 0)))
    return tuple(hits[:limit])
