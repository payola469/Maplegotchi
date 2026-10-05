"""Gathering a Maple day's facts and deciding when to reflect (ADR-0031).

Pure core writes the reflection (`core.daily.reflect`); this module reads the
day's records from Maple's own database (inside the writer's transition) and
applies the two timing rules: reflect when the night's sleep begins, or recover
the previous day's reflection at the first awake transition after it was missed.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from maplegotchi.core.activities import Activity
from maplegotchi.core.daily import (
    DailyReflection,
    DayRecords,
    ReflectionOutcome,
    day_window,
    main_sleep_begins,
    reflect,
    reflection_day,
)
from maplegotchi.core.goals import GoalType
from maplegotchi.core.memory import Memory, MemoryKind, Tier
from maplegotchi.core.state import MapleState
from maplegotchi.storage.repositories import LifeRepository


def day_records(repo: LifeRepository, day: date, utc_offset: timedelta) -> DayRecords:
    start, end = day_window(day, utc_offset)
    started: list[GoalType] = []
    completed: list[GoalType] = []
    abandoned: list[GoalType] = []
    interactions = 0
    for kind, payload in repo.rows_between("timeline_event", start, end):
        data = json.loads(payload)
        if kind == "goal_started":
            started.append(GoalType(data["goal_type"]))
        elif kind == "goal_completed":
            completed.append(GoalType(data["goal_type"]))
        elif kind == "goal_abandoned":
            abandoned.append(GoalType(data["goal_type"]))
        elif kind == "interaction_accepted":
            interactions += 1
    activities: list[Activity] = []
    server_problems = interruptions = 0
    for kind, payload in repo.rows_between("action_event", start, end):
        data = json.loads(payload)
        if kind == "activity_completed":
            activities.append(Activity(data["activity"]))
        elif kind == "activity_interrupted":
            interruptions += 1
        elif kind == "needs_attention" and data.get("signal") == "server_problem":
            server_problems += 1
    failures = sum(
        1 for (verdict,) in repo.rows_between("decision", start, end)
        if verdict in ("rejected", "fallback")
    )  # fmt: skip
    readings: list[tuple[str, str]] = []
    writings: list[str] = []
    for operation, status, title, detail in repo.rows_between("tool_use", start, end):
        if operation == "read_completed" and status == "success":
            readings.append((title, detail or ""))
        elif operation == "write_completed" and status == "success":
            writings.append(detail or title)
        elif status == "failure" and detail != "interrupted":
            failures += 1
    return DayRecords(
        day=day,
        goals_started=tuple(started),
        goals_completed=tuple(completed),
        goals_abandoned=tuple(abandoned),
        activities_completed=tuple(activities),
        readings=tuple(readings),
        writings=tuple(writings),
        interactions=interactions,
        server_problems=server_problems,
        interruptions=interruptions,
        failures=failures,
    )


def due_day(
    repo: LifeRepository,
    before: MapleState,
    after: MapleState,
    now: datetime,
    utc_offset: timedelta,
) -> tuple[date, bool] | None:
    """(day, recovered) if this transition should write a Daily Reflection."""
    today = reflection_day(now, utc_offset)
    if main_sleep_begins(before, after, now, utc_offset):
        if repo.reflection_for(today) is None:
            return today, False
        return None
    if after.activity is Activity.SLEEP:
        return None  # recover only once Maple is awake again
    yesterday = today - timedelta(days=1)
    _, end = day_window(yesterday, utc_offset)
    lived_through = after.identity.born_at < end
    if lived_through and now >= end and repo.reflection_for(yesterday) is None:
        return yesterday, True
    return None


def reflect_if_due(
    repo: LifeRepository,
    before: MapleState,
    after: MapleState,
    now: datetime,
    utc_offset: timedelta,
) -> ReflectionOutcome | None:
    due = due_day(repo, before, after, now, utc_offset)
    if due is None:
        return None
    day, recovered = due
    start, end = day_window(day, utc_offset)
    everything = repo.memories(limit=2000)
    of_the_day = [m for m in everything if start <= m.created_at < end]
    preferences: dict[str, Memory] = {
        m.key: m for m in everything if m.kind is MemoryKind.PREFERENCE and m.key
    }
    previous = [r for r in repo.reflections(limit=10) if r.reflection.day < day]
    previous_needs = previous[-1].reflection.needs if previous else None
    return reflect(
        day_records(repo, day, utc_offset),
        state=after,
        memories=[m for m in of_the_day if m.tier is Tier.SHORT_TERM],
        preferences=preferences,
        previous_needs=previous_needs,
        now=now,
        recovered=recovered,
    )


def todays_intent(
    repo: LifeRepository, now: datetime, utc_offset: timedelta
) -> DailyReflection | None:
    """Yesterday's reflection, whose intent applies to today."""
    yesterday = reflection_day(now, utc_offset) - timedelta(days=1)
    stored = repo.reflection_for(yesterday)
    return stored.reflection if stored else None
