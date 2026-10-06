"""Memory lifecycle, preferences by evidence, and relevant retrieval (ADR-0030)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from maplegotchi.core.goals import GoalEndReason, GoalType
from maplegotchi.core.memory import (
    PREFERENCE_DAYS,
    SHORT_TERM_TTL,
    Memory,
    MemoryEventKind,
    MemoryKind,
    MemoryQuery,
    MemoryStatus,
    Tier,
    confirm_preference,
    consolidate,
    memories_from,
    new_preference,
    promote,
    reinforce_preference,
    reject_preference,
    retrieve,
    search,
)
from maplegotchi.core.state import InteractionKind, ReactionKind
from maplegotchi.core.tasks import (
    DocumentDraft,
    Task,
    Tool,
    ToolOp,
    ToolRecord,
    WriteKind,
    write_task,
)
from maplegotchi.core.timeline import (
    GoalCompleted,
    GoalSuspended,
    InteractionAccepted,
)

NOW = datetime(2026, 3, 1, 5, tzinfo=UTC)  # 12:00 in Bangkok
OFFSET = timedelta(hours=7)
DAY = date(2026, 3, 1)


def memory(text: str, *, tier: Tier = Tier.SHORT_TERM, age: timedelta = timedelta(0),
           importance: float = 0.3, mid: int = 1) -> Memory:  # fmt: skip
    return Memory(
        kind=MemoryKind.EVENT,
        tier=tier,
        status=MemoryStatus.ACTIVE,
        text=text,
        created_at=NOW - age,
        last_seen_at=NOW - age,
        importance=importance,
        id=mid,
    )


def test_transitions_create_short_term_memories() -> None:
    reading = ToolRecord(ToolOp.READ_COMPLETED, NOW, 4, 2,
                         Task(Tool.READER, "library:the_room", "Maple's room", "home"), True,
                         detail="The room has a bed.", chars=300)  # fmt: skip
    draft = DocumentDraft(WriteKind.NOTE, "A small note", "Body.", ())
    writing = ToolRecord(ToolOp.WRITE_COMPLETED, NOW, 5, 2, write_task(WriteKind.NOTE), True,
                         document=draft)  # fmt: skip
    events = (
        GoalCompleted(NOW, 2, GoalType.LEARN, GoalEndReason.HORIZON_REACHED),
        GoalSuspended(NOW, 3, GoalType.CREATE, "server_problem"),
        InteractionAccepted(NOW, InteractionKind.GREET, ReactionKind.GREET_HAPPY),
        InteractionAccepted(NOW, InteractionKind.GREET, ReactionKind.GREET_HAPPY),  # same day
    )
    made = memories_from(events, (reading, writing), NOW, OFFSET)
    kinds = [m.kind for m in made]
    assert kinds == [MemoryKind.GOAL_OUTCOME, MemoryKind.EVENT, MemoryKind.INTERACTION,
                     MemoryKind.READING, MemoryKind.WRITING]  # fmt: skip
    assert all(m.tier is Tier.SHORT_TERM and m.status is MemoryStatus.ACTIVE for m in made)
    assert made[2].key == "interaction:greet:2026-03-01"  # one per kind per local day
    assert made[3].text == "I read Maple's room: The room has a bed."
    assert made[4].text == "I wrote A small note."
    assert all("\n" not in m.text and len(m.text) <= 240 for m in made)


def test_consolidation_archives_expired_short_term_and_never_promotes() -> None:
    fresh = memory("fresh", age=timedelta(hours=1), mid=1)
    old = memory("old", age=SHORT_TERM_TTL, mid=2)
    kept = memory("long", tier=Tier.LONG_TERM, age=timedelta(days=30), mid=3)
    pref = new_preference("prefers:read", "I seem to like reading.", NOW - SHORT_TERM_TTL * 2,
                          DAY).memory  # fmt: skip
    changes = consolidate([fresh, old, kept, replace(pref, id=4)], NOW)
    assert [(c.memory.id, c.memory.tier, c.event.kind) for c in changes] == [
        (2, Tier.ARCHIVE, MemoryEventKind.ARCHIVED)
    ]


def test_promotion_is_explicit_and_not_for_preferences() -> None:
    change = promote(memory("I learned the room layout."), NOW, "chosen by daily reflection")
    assert change.memory.tier is Tier.LONG_TERM
    assert change.event.kind is MemoryEventKind.PROMOTED
    with pytest.raises(ValueError):
        promote(new_preference("prefers:read", "Reading", NOW, DAY).memory, NOW, "no")
    with pytest.raises(ValueError):
        promote(change.memory, NOW, "twice")


def test_a_single_statement_never_becomes_a_permanent_preference() -> None:
    created = new_preference("prefers:read", "I seem to enjoy reading.", NOW, DAY)
    pref = replace(created.memory, id=1)
    assert pref.status is MemoryStatus.CANDIDATE and pref.tier is Tier.SHORT_TERM
    assert reinforce_preference(pref, NOW, DAY) is None  # same day: no new evidence
    days = [DAY + timedelta(days=i) for i in range(1, PREFERENCE_DAYS)]
    for i, day in enumerate(days, start=2):
        change = reinforce_preference(pref, NOW + timedelta(days=i - 1), day)
        assert change is not None
        pref = change.memory
        if i < PREFERENCE_DAYS:
            assert pref.status is MemoryStatus.CANDIDATE
            assert change.event.kind is MemoryEventKind.REINFORCED
    assert pref.status is MemoryStatus.ACCEPTED and pref.tier is Tier.LONG_TERM
    assert len(pref.evidence_days) == PREFERENCE_DAYS


def test_explicit_confirmation_or_denial() -> None:
    pref = replace(new_preference("prefers:walk", "I like walking.", NOW, DAY).memory, id=7)
    confirmed = confirm_preference(pref, NOW)
    assert confirmed.memory.status is MemoryStatus.ACCEPTED
    assert confirmed.event.kind is MemoryEventKind.CONFIRMED
    rejected = reject_preference(pref, NOW)
    assert (rejected.memory.status, rejected.memory.tier) == (MemoryStatus.REJECTED, Tier.ARCHIVE)
    with pytest.raises(ValueError):
        confirm_preference(rejected.memory, NOW)


def test_retrieval_is_relevant_small_and_never_the_archive() -> None:
    items = [
        memory("I read about the server's disk today.", mid=1),
        memory("Paolo greeted me in the morning.", mid=2),
        memory("I wrote a note about the server load.", tier=Tier.LONG_TERM, mid=3),
        memory("The server disk was nearly full last month.", tier=Tier.ARCHIVE, mid=4),
        *[memory(f"Filler memory number {i}.", mid=10 + i) for i in range(10)],
    ]
    query = MemoryQuery(text="watch the server disk", goal_type=GoalType.MONITOR)
    found = retrieve(items, query, NOW, limit=3)
    assert [m.id for m in found][:2] == [1, 3]
    assert len(found) == 3 and all(m.tier is not Tier.ARCHIVE for m in found)
    assert found == retrieve(items, query, NOW, limit=3)  # deterministic
    rejected = replace(new_preference("prefers:x", "server disk fan", NOW, DAY).memory, id=99)
    rejected = reject_preference(rejected, NOW).memory
    assert rejected not in retrieve([*items, rejected], MemoryQuery(text="server disk"), NOW)


def test_search_covers_the_archive() -> None:
    items = [
        memory("The server disk was nearly full last month.", tier=Tier.ARCHIVE, mid=4),
        memory("Paolo greeted me.", mid=2),
    ]
    assert [m.id for m in search(items, "disk")] == [4]
    assert search(items, "") == ()


@pytest.mark.parametrize("text", ["", "two\nlines", "x" * 241])
def test_memory_text_is_one_short_line(text: str) -> None:
    with pytest.raises(ValueError):
        memory(text)


def test_only_preferences_have_preference_status() -> None:
    with pytest.raises(ValueError):
        replace(memory("x"), status=MemoryStatus.CANDIDATE)
    pref = new_preference("prefers:read", "Reading", NOW, DAY).memory
    with pytest.raises(ValueError):
        replace(pref, status=MemoryStatus.ACTIVE)
    with pytest.raises(ValueError):  # accepted lives in long-term
        replace(pref, status=MemoryStatus.ACCEPTED)
