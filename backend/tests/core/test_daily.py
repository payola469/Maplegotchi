"""Daily Reflection as a pure function (ADR-0031)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.daily import (
    PROMOTE_IMPORTANCE,
    DayRecords,
    ReflectionOutcome,
    day_window,
    main_sleep_begins,
    reflect,
    reflection_day,
)
from maplegotchi.core.goals import GoalType
from maplegotchi.core.memory import (
    Memory,
    MemoryEventKind,
    MemoryKind,
    MemoryStatus,
    Tier,
    new_preference,
)
from maplegotchi.core.state import MapleState
from tests.core.support import at_local, make_state, needs

OFFSET = timedelta(hours=7)
DAY = date(2026, 1, 1)
NIGHT = at_local(22)  # day 1, 22:00 local


def mem(mid: int, importance: float, kind: MemoryKind = MemoryKind.EVENT) -> Memory:
    return Memory(kind=kind, tier=Tier.SHORT_TERM, status=MemoryStatus.ACTIVE,
                  text=f"Memory number {mid}.", created_at=NIGHT, last_seen_at=NIGHT,
                  importance=importance, id=mid)  # fmt: skip


def test_maple_days_run_from_six_to_six_local() -> None:
    six = datetime(2026, 1, 1, 23, 0, tzinfo=UTC)  # 06:00 on 2 Jan in Bangkok
    assert reflection_day(six, OFFSET) == date(2026, 1, 2)
    assert reflection_day(six - timedelta(seconds=1), OFFSET) == date(2026, 1, 1)
    start, end = day_window(date(2026, 1, 2), OFFSET)
    assert (start, end) == (six, six + timedelta(days=1))


def test_the_nights_sleep_triggers_reflection_but_a_daytime_nap_does_not() -> None:
    awake = make_state(at=NIGHT, activity=Activity.READ)
    asleep = replace(awake, activity=Activity.SLEEP, location=RoomLocation.BED, point_id=None,
                     action_id=awake.action_id + 1)  # fmt: skip
    assert main_sleep_begins(awake, asleep, NIGHT, OFFSET)
    noon = at_local(13)
    nap = replace(
        asleep,
        last_tick_at=noon,
        last_updated_at=noon,
        activity_started_at=noon,
        activity_until=noon + timedelta(hours=2),
    )
    assert not main_sleep_begins(make_state(at=noon), nap, noon, OFFSET)
    assert not main_sleep_begins(asleep, asleep, NIGHT, OFFSET)  # same action continues


def records(**kw: object) -> DayRecords:
    return DayRecords(day=DAY, **kw)  # type: ignore[arg-type]


def run(
    r: DayRecords,
    memories: list[Memory] | None = None,
    prefs: dict[str, Memory] | None = None,
) -> tuple[MapleState, ReflectionOutcome]:
    state = make_state(at=NIGHT, state_needs=needs(mood=70.0))
    out = reflect(
        r,
        state=state,
        memories=memories or [],
        preferences=prefs or {},
        previous_needs=needs(mood=60.0),
        now=NIGHT,
    )
    return state, out


def test_summary_learned_moments_and_intent_come_from_the_days_facts() -> None:
    r = records(
        goals_started=(GoalType.LEARN, GoalType.CREATE),
        goals_completed=(GoalType.LEARN,),
        activities_completed=(Activity.READ, Activity.READ, Activity.WRITE),
        readings=(("Maple's room", "The room has a bed."), ("paolo-core", "It runs backups.")),
        writings=("A research note",),
        interactions=2,
    )
    state, out = run(r, [mem(1, 0.7), mem(2, 0.4)])
    ref = out.reflection
    assert "started 2 goals, finished 1" in ref.summary
    assert "I read Maple's room, paolo-core." in ref.summary
    assert "My mood is better" in ref.summary
    assert ref.learned == (
        "From Maple's room: The room has a bed.",
        "From paolo-core: It runs backups.",
    )
    assert ref.moments == ("Memory number 1.",)
    assert ref.intent_type is GoalType.EXPLORE
    assert ref.needs == state.needs  # recorded, never changed
    assert out == run(r, [mem(1, 0.7), mem(2, 0.4)])[1]  # deterministic


def test_only_the_strongest_candidate_is_promoted() -> None:
    _, out = run(records(), [mem(1, 0.9), mem(2, 0.8), mem(3, 0.7), mem(4, 0.65)])
    ref = out.reflection
    assert [c.memory_id for c in ref.memory_candidates] == [1, 2, 3]
    assert ref.promoted == (1,)
    promoted = [c for c in out.memory_changes if c.event.kind is MemoryEventKind.PROMOTED]
    assert [c.memory.id for c in promoted] == [1] and promoted[0].memory.tier is Tier.LONG_TERM


def test_nothing_is_promoted_on_an_unremarkable_day() -> None:
    _, out = run(records(), [mem(1, PROMOTE_IMPORTANCE - 0.01)])
    assert out.reflection.promoted == ()
    assert out.memory_changes == ()


def test_preferences_get_one_day_of_evidence_never_instant_acceptance() -> None:
    r = records(activities_completed=(Activity.READ, Activity.READ, Activity.SLEEP, Activity.SLEEP))
    _, first = run(r)
    assert first.reflection.preference_candidates == (("prefers:read", "I seem to enjoy reading."),)
    [created] = first.memory_changes
    assert created.memory.status is MemoryStatus.CANDIDATE and created.memory.evidence_days == (
        DAY,
    )
    existing = replace(new_preference("prefers:read", "I seem to enjoy reading.", NIGHT,
                                      DAY - timedelta(days=1)).memory, id=9)  # fmt: skip
    _, second = run(r, prefs={"prefers:read": existing})
    [reinforced] = second.memory_changes
    assert reinforced.memory.id == 9 and reinforced.memory.status is MemoryStatus.CANDIDATE
    same_day = replace(existing, evidence_days=(DAY,))
    _, third = run(r, prefs={"prefers:read": same_day})
    assert third.memory_changes == ()  # the same day never counts twice


def test_intent_rules() -> None:
    assert run(records(failures=2, interruptions=1))[1].reflection.intent_type is GoalType.PLAN
    assert run(records(server_problems=1))[1].reflection.intent_type is GoalType.MONITOR
    assert run(records(goals_abandoned=(GoalType.CREATE,)))[1].reflection.intent_type is (
        GoalType.CREATE
    )
    two_reads = records(readings=(("a", "x"), ("b", "y")), interactions=1)
    assert run(two_reads)[1].reflection.intent_type is GoalType.CREATE
    assert run(records())[1].reflection.intent_type is GoalType.SOCIALIZE
