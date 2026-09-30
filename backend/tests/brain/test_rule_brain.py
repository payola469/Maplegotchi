"""RuleBrain: deterministic, bounded wording that always passes grounding."""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta

import pytest

from maplegotchi.brain import rule_brain as rule_brain_module
from maplegotchi.brain.rule_brain import RuleBrain, follows_template_policy
from maplegotchi.core.activities import Activity
from maplegotchi.core.journal import (
    SERVICE_NAMES,
    BrainContext,
    BrainKind,
    JournalCategory,
    ServerSummary,
    Trigger,
    TriggerKind,
    accept_drafts,
)
from maplegotchi.core.observations import (
    Metric,
    Observation,
    ObservationSnapshot,
    ObservationStatus,
    ServiceState,
)
from maplegotchi.core.state import ReactionKind
from tests.core.support import at_local, make_state

BRAIN = RuleBrain()
T = at_local(14)


def context(
    *triggers: Trigger,
    activity: Activity = Activity.IDLE,
    now: datetime = T,
    snapshot: ObservationSnapshot | None = None,
) -> BrainContext:
    state = make_state(at=now, activity=activity)
    return BrainContext(now, 14.0, "Paolo", state, state.expression_at(now), snapshot, triggers)


def words(*triggers: Trigger, **kw: object) -> list[str]:
    ctx = context(*triggers, **kw)  # type: ignore[arg-type]
    entries = accept_drafts(
        ctx,
        BRAIN.compose_journal(ctx),
        brain_kind=BRAIN.kind,
        brain_name=BRAIN.name,
        brain_version=BRAIN.version,
        tick_id=1,
    )
    return [e.text for e in entries]


def service_snapshot(name: str, state: ServiceState) -> ObservationSnapshot:
    return ObservationSnapshot(
        T,
        (
            Observation(
                Metric.SERVICE_STATE, name, ObservationStatus.AVAILABLE, T, "fake", state=state
            ),
        ),
    )


def test_identity() -> None:
    assert (BRAIN.kind, BRAIN.name, BRAIN.version) == (BrainKind.RULE, "rule_brain", "1")


def test_same_input_same_output() -> None:
    trigger = Trigger(TriggerKind.ACTIVITY, "daily:read", "read")
    assert BRAIN.compose_journal(context(trigger)) == BRAIN.compose_journal(context(trigger))
    variants = {
        BRAIN.compose_journal(context(trigger, now=T + timedelta(minutes=m)))[0].text
        for m in range(0, 300, 5)
    }
    assert 1 < len(variants) <= 2  # bounded, template-driven variety


def test_interaction_wording_follows_state() -> None:
    pet = Trigger(
        TriggerKind.INTERACTION, "interaction:pet", "pet", reaction=ReactionKind.PET_HAPPY
    )
    assert words(pet) == ["Paolo stopped by and gave me a little pat."]
    sleepy_pet = Trigger(
        TriggerKind.INTERACTION, "interaction:pet", "pet", reaction=ReactionKind.PET_SLEEPY
    )
    assert words(sleepy_pet, activity=Activity.SLEEP) == [
        "I felt a gentle pat while I was sleeping."
    ]
    assert words(sleepy_pet) == ["Paolo gave me a pat while I was feeling drowsy."]


def test_server_notice_names_only_the_affected_service() -> None:
    problem = Trigger(
        TriggerKind.SERVER_PROBLEM,
        "service:jellyfin",
        "failed",
        "jellyfin",
        ((Metric.SERVICE_STATE, "jellyfin"),),
    )
    snap = service_snapshot("jellyfin", ServiceState.FAILED)
    assert words(problem, snapshot=snap) == [
        "I noticed Jellyfin isn't doing well. I'll keep an eye on it."
    ]
    recovery = Trigger(
        TriggerKind.SERVER_RECOVERY,
        "service:jellyfin",
        "failed",
        "jellyfin",
        ((Metric.SERVICE_STATE, "jellyfin"),),
    )
    assert words(recovery, snapshot=service_snapshot("jellyfin", ServiceState.ACTIVE)) == [
        "Jellyfin seems to be back to normal. That's a relief."
    ]


def test_unknown_service_subject_is_not_worded() -> None:
    odd = Trigger(
        TriggerKind.SERVER_PROBLEM,
        "service:mystery",
        "failed",
        "mystery",
        ((Metric.SERVICE_STATE, "mystery"),),
    )
    assert words(odd, snapshot=service_snapshot("mystery", ServiceState.FAILED)) == []


@pytest.mark.parametrize("summary", list(ServerSummary))
def test_reflection_claims_only_what_the_summary_allows(summary: ServerSummary) -> None:
    trigger = Trigger(
        TriggerKind.DAILY_REFLECTION, "reflection", summary=summary, day_activities=("read",)
    )
    [text] = words(trigger)
    calm_words = ("calm", "healthy", "fine")
    trouble_words = ("fail", "rough", "wrong", "need watching")
    if summary is not ServerSummary.CALM:
        assert not any(w in text.lower() for w in calm_words), text
    if summary not in (ServerSummary.TROUBLED_EARLIER, ServerSummary.STILL_TROUBLED):
        assert not any(w in text.lower() for w in trouble_words), text


def test_every_trigger_shape_yields_accepted_grounded_text() -> None:
    triggers: list[tuple[Trigger, ObservationSnapshot | None]] = []
    for label in ("woke", "sleep", "read", "write", "observe"):
        triggers.append((Trigger(TriggerKind.ACTIVITY, f"daily:{label}", label), None))
    for reaction in ReactionKind:
        triggers.append(
            (Trigger(TriggerKind.INTERACTION, "interaction:x", "x", reaction=reaction), None)
        )
    for kind, service in itertools.product(
        (TriggerKind.SERVER_PROBLEM, TriggerKind.SERVER_RECOVERY), SERVICE_NAMES
    ):
        key = (Metric.SERVICE_STATE, service)
        triggers.append(
            (
                Trigger(kind, f"service:{service}", "failed", service, (key,)),
                service_snapshot(service, ServiceState.FAILED),
            )
        )
    for label, _metric in (
        ("nearly_full", Metric.DISK_USAGE),
        ("high", Metric.MEMORY_USAGE),
        ("hot", Metric.TEMPERATURE),
        ("busy", Metric.CPU_USAGE),
    ):
        for kind in (TriggerKind.SERVER_PROBLEM, TriggerKind.SERVER_RECOVERY):
            triggers.append((Trigger(kind, f"x:{label}", label, "s"), None))
    for label in ("first_heartbeat", "one_day", "one_week", "one_month", "one_year"):
        triggers.append((Trigger(TriggerKind.MILESTONE, f"milestone:{label}", label), None))
    for summary, acts, company in itertools.product(
        ServerSummary, ((), ("write",), ("read", "observe")), (0, 3)
    ):
        triggers.append(
            (
                Trigger(
                    TriggerKind.DAILY_REFLECTION,
                    "reflection",
                    summary=summary,
                    day_activities=acts,
                    interactions_today=company,
                ),
                None,
            )
        )

    for trigger, snap in triggers:
        for activity in (Activity.IDLE, Activity.SLEEP):
            for minutes in range(0, 60, 7):
                ctx = context(
                    trigger, activity=activity, now=T + timedelta(minutes=minutes), snapshot=snap
                )
                drafts = BRAIN.compose_journal(ctx)
                entries = accept_drafts(
                    ctx,
                    drafts,
                    brain_kind=BRAIN.kind,
                    brain_name=BRAIN.name,
                    brain_version=BRAIN.version,
                    tick_id=1,
                )
                assert len(entries) == len(drafts) == 1, (trigger, drafts)
                assert entries[0].category is not None
                assert not any(ch.isdigit() for ch in entries[0].text)


def test_brain_cannot_choose_references_or_category() -> None:
    fields = set(
        RuleBrain()
        .compose_journal(context(Trigger(TriggerKind.ACTIVITY, "daily:read", "read")))[0]
        .__dataclass_fields__
    )
    assert fields == {"trigger_index", "text", "importance", "template_id"}
    assert JournalCategory.DAILY_LIFE  # category comes from the trigger, in core


def test_template_policy_every_template_is_digit_free() -> None:
    tables = [
        rule_brain_module._DAILY,
        rule_brain_module._PROBLEM,
        rule_brain_module._RECOVERY,
    ]
    texts = [t for table in tables for options in table.values() for t in options]
    texts += list(rule_brain_module._MILESTONE.values())
    texts += list(rule_brain_module._SERVER_SENTENCE.values())
    texts += list(rule_brain_module._ACTIVITY_SENTENCE.values())
    texts += list(SERVICE_NAMES.values())
    assert texts and all(follows_template_policy(t) for t in texts)


def test_template_policy_is_enforced_even_if_input_carries_digits() -> None:
    pet = Trigger(
        TriggerKind.INTERACTION, "interaction:pet", "pet", reaction=ReactionKind.PET_HAPPY
    )
    state = make_state(at=T)
    ctx = BrainContext(T, 14.0, "R2D2", state, state.expression_at(T), None, (pet,))
    assert BRAIN.compose_journal(ctx) == ()  # would contain digits: not written
