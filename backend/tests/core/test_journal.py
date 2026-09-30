"""JournalEntry invariants and draft validation (grounding)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.journal import (
    BrainContext,
    BrainKind,
    Importance,
    JournalCategory,
    JournalDraft,
    JournalEntry,
    Trigger,
    TriggerKind,
    accept_drafts,
    mentioned_services,
    text_problems,
)
from maplegotchi.core.observations import (
    Metric,
    Observation,
    ObservationSnapshot,
    ObservationStatus,
    ServiceState,
)
from maplegotchi.core.state import Expression
from tests.core.support import at_local, make_state

T = at_local(14)
JELLYFIN_KEY = (Metric.SERVICE_STATE, "jellyfin")


def failed(service: str) -> Observation:
    return Observation(
        Metric.SERVICE_STATE,
        service,
        ObservationStatus.AVAILABLE,
        T,
        "fake",
        state=ServiceState.FAILED,
    )


SNAPSHOT = ObservationSnapshot(T, (failed("jellyfin"),))
PROBLEM = Trigger(
    TriggerKind.SERVER_PROBLEM, "service:jellyfin", "failed", "jellyfin", (JELLYFIN_KEY,)
)


def ctx(*triggers: Trigger, snapshot: ObservationSnapshot | None = SNAPSHOT) -> BrainContext:
    state = make_state(at=T)
    return BrainContext(T, 14.0, "Paolo", state, state.expression_at(T), snapshot, triggers)


def accept(context: BrainContext, *drafts: object) -> tuple[JournalEntry, ...]:
    return accept_drafts(
        context,
        drafts,
        brain_kind=BrainKind.RULE,
        brain_name="rule_brain",
        brain_version="1",
        tick_id=7,
    )


def draft(text: str, index: int = 0) -> JournalDraft:
    return JournalDraft(index, text, Importance.HIGH, "server.test")


GOOD = "I noticed Jellyfin isn't doing well. I'll keep an eye on it."


def test_valid_draft_becomes_grounded_entry() -> None:
    [entry] = accept(ctx(PROBLEM), draft(GOOD))
    assert entry.category is JournalCategory.SERVER_NOTICE
    assert entry.observation_keys == (JELLYFIN_KEY,)  # from the trigger, not the brain
    assert (entry.brain_kind, entry.brain_name, entry.brain_version) == (
        BrainKind.RULE,
        "rule_brain",
        "1",
    )
    assert entry.topic == "service:jellyfin" and entry.tick_id == 7
    assert entry.activity is Activity.IDLE and entry.expression is Expression.CALM


@pytest.mark.parametrize(
    "text",
    [
        "I noticed Grafana isn't doing well.",  # names a service the trigger is not about
        "Jellyfin and qBittorrent are down.",
        "",
        " padded ",
        "line\nbreak",
        "x" * 241,
    ],
)
def test_ungrounded_or_malformed_text_is_dropped(text: str) -> None:
    assert accept(ctx(PROBLEM), draft(text)) == ()


def test_drafts_for_missing_duplicate_or_foreign_triggers_are_dropped() -> None:
    context = ctx(PROBLEM)
    assert accept(context, draft(GOOD, index=1)) == ()
    assert accept(context, draft(GOOD, index=-1)) == ()
    assert len(accept(context, draft(GOOD), draft(GOOD))) == 1  # one entry per trigger
    assert accept(context, "a plain string", {"text": GOOD}) == ()
    assert accept(context, JournalDraft(True, GOOD, Importance.HIGH, "x")) == ()


def test_trigger_citing_unobserved_fact_is_dropped() -> None:
    ghost = replace(PROBLEM, observation_keys=((Metric.SERVICE_STATE, "grafana"),))
    assert accept(ctx(ghost), draft(GOOD)) == ()
    assert accept(ctx(PROBLEM, snapshot=None), draft(GOOD)) == ()


def test_text_rules() -> None:
    assert text_problems("A calm day.") == []
    # Numbers are not a journal-level problem; future grounded entries may use them.
    assert text_problems("Day 2 at 21:00, disk at 96%.") == []
    assert "unprintable" in text_problems("two\nlines")
    assert mentioned_services("Grafana and the backups were fine.") == {"grafana", "backup"}


def entry(**overrides: Any) -> JournalEntry:
    fields: dict[str, Any] = {
        "created_at": T,
        "category": JournalCategory.DAILY_LIFE,
        "trigger": TriggerKind.ACTIVITY,
        "topic": "daily:read",
        "text": "I read.",
        "importance": Importance.LOW,
        "brain_kind": BrainKind.RULE,
        "brain_name": "rule_brain",
        "brain_version": "1",
        "template_id": "daily.read.0",
        "activity": Activity.READ,
        "expression": Expression.FOCUSED,
        "observation_keys": (),
        "tick_id": 3,
    }
    fields.update(overrides)
    return JournalEntry(**fields)


def test_entry_invariants() -> None:
    assert entry().text == "I read."
    bad: list[dict[str, Any]] = [
        {"category": JournalCategory.SERVER_NOTICE},  # does not match the trigger kind
        {"text": "two\nlines"},
        {"created_at": datetime(2026, 1, 1)},  # noqa: DTZ001
        {"brain_name": "Rule Brain"},
        {"tick_id": 0},
        {"observation_keys": (JELLYFIN_KEY,), "tick_id": None},
        {"topic": "Has Spaces"},
    ]
    for override in bad:
        with pytest.raises((ValueError, TypeError)):
            entry(**override)


def test_entries_are_immutable() -> None:
    with pytest.raises(AttributeError):
        entry().text = "rewritten"  # type: ignore[misc]


def test_created_at_is_utc() -> None:
    assert entry().created_at.tzinfo is UTC or entry().created_at.utcoffset() is not None


def test_generic_validation_permits_grounded_numbers() -> None:
    # The generic journal does not ban digits (RuleBrain's digit-free output is its
    # own template policy). Grounding still applies: only referenced services.
    [entry] = accept(ctx(PROBLEM), draft("Jellyfin stopped at 14:00."))
    assert entry.text == "Jellyfin stopped at 14:00."
    assert accept(ctx(PROBLEM), draft("Grafana stopped at 14:00.")) == ()
