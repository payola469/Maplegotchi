"""Daily Reflection (ADR-0031), as a pure function of one Maple day's facts.

summarize the day -> choose memory candidates -> set tomorrow's intent.

It never changes needs, mood or energy. Its effects are: one reflection record,
at most one explicit promotion to long-term memory, preference *candidates*
(evidence only; acceptance needs ADR-0030's distinct-day rule), and an intent
that tomorrow's rule direction and Director context lean on.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from maplegotchi.core.activities import Activity
from maplegotchi.core.daytime import local_hour, require_utc
from maplegotchi.core.goals import GoalType, summary_problems
from maplegotchi.core.memory import (
    Memory,
    MemoryChange,
    MemoryKind,
    MemoryStatus,
    Tier,
    new_preference,
    promote,
    reinforce_preference,
)
from maplegotchi.core.state import MapleState, Needs
from maplegotchi.core.tasks import one_line

DAY_STARTS_AT = time(6, 0)  # a Maple day runs from 06:00 to 06:00, local time
MAIN_SLEEP_FROM_HOUR = 20.0  # a sleep that begins from 20:00 (to 06:00) is the night's sleep
MAX_SUMMARY = 1000
PROMOTE_IMPORTANCE = 0.6
MAX_CANDIDATES = 3
PREFERENCE_REPEATS = 2  # completed this often in a day -> evidence for a preference

ACTIVITY_WORDS = {
    Activity.READ: "reading",
    Activity.WRITE: "writing",
    Activity.OBSERVE_SERVER: "watching the server",
    Activity.THINK: "thinking by the window",
    Activity.REST: "resting on the sofa",
    Activity.WALK: "walking around",
    Activity.IDLE: "pottering about",
    Activity.SLEEP: "sleeping",
}


def reflection_day(now: datetime, utc_offset: timedelta) -> date:
    """The Maple day `now` belongs to (local 06:00 to 06:00)."""
    require_utc(now, "now")
    local = now + utc_offset
    return (local - timedelta(hours=DAY_STARTS_AT.hour)).date()


def day_window(day: date, utc_offset: timedelta) -> tuple[datetime, datetime]:
    """[start, end) of a Maple day in UTC."""
    start_local = datetime.combine(day, DAY_STARTS_AT, tzinfo=UTC)
    start = start_local - utc_offset
    return start, start + timedelta(days=1)


def main_sleep_begins(
    before: MapleState, after: MapleState, now: datetime, utc_offset: timedelta
) -> bool:
    """A new `sleep` action starting at night: time for the day's reflection."""
    if after.activity is not Activity.SLEEP or after.action_id == before.action_id:
        return False
    hour = local_hour(now, utc_offset)
    return hour >= MAIN_SLEEP_FROM_HOUR or hour < DAY_STARTS_AT.hour


@dataclass(frozen=True, slots=True)
class DayRecords:
    """The facts of one Maple day, gathered by the runtime from Maple's records."""

    day: date
    goals_started: tuple[GoalType, ...] = ()
    goals_completed: tuple[GoalType, ...] = ()
    goals_abandoned: tuple[GoalType, ...] = ()
    activities_completed: tuple[Activity, ...] = ()
    readings: tuple[tuple[str, str], ...] = ()  # (title, extract)
    writings: tuple[str, ...] = ()  # document titles
    interactions: int = 0
    conversations: int = 0
    server_problems: int = 0
    interruptions: int = 0
    failures: int = 0  # refused/fallback decisions, failed reads/writes (not interruptions)


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    memory_id: int
    text: str
    reason: str


@dataclass(frozen=True, slots=True)
class DailyReflection:
    day: date
    created_at: datetime
    recovered: bool  # written late, after a restart/failure/oversleep
    summary: str
    learned: tuple[str, ...]
    moments: tuple[str, ...]
    memory_candidates: tuple[MemoryCandidate, ...]
    promoted: tuple[int, ...]  # memory ids promoted to long-term (at most one)
    preference_candidates: tuple[tuple[str, str], ...]  # (key, text)
    intent_type: GoalType
    intent_summary: str
    needs: Needs  # at reflection time (for tomorrow's comparison)

    def __post_init__(self) -> None:
        require_utc(self.created_at, "reflection.created_at")
        if not 1 <= len(self.summary) <= MAX_SUMMARY:
            raise ValueError("summary must be 1-1000 characters")
        if summary_problems(self.intent_summary):
            raise ValueError("intent summary must be one short line")
        if len(self.promoted) > 1:
            raise ValueError("at most one promotion per day")


@dataclass(frozen=True, slots=True)
class ReflectionOutcome:
    reflection: DailyReflection
    memory_changes: tuple[MemoryChange, ...]


_REASONS = {
    MemoryKind.EVENT: "a serious moment",
    MemoryKind.GOAL_OUTCOME: "how a goal ended",
    MemoryKind.READING: "something I learned",
    MemoryKind.WRITING: "something I made",
    MemoryKind.INTERACTION: "time with Paolo",
    MemoryKind.CONVERSATION: "a conversation with Paolo",
}


def _mood_line(now_needs: Needs, before: Needs | None) -> str | None:
    if before is None:
        return None
    delta = now_needs.mood - before.mood
    if delta >= 5:
        return "My mood is better than at my last reflection."
    if delta <= -5:
        return "My mood is lower than at my last reflection."
    return "My mood is about where it was at my last reflection."


def _intent(records: DayRecords) -> tuple[GoalType, str]:
    if records.failures + records.interruptions >= 3:
        return GoalType.PLAN, "Make tomorrow calmer and more deliberate"
    if records.server_problems:
        return GoalType.MONITOR, "Keep a closer eye on paolo-core"
    if records.goals_abandoned:
        goal = records.goals_abandoned[-1]
        return goal, f"Come back to the {goal.value} goal I set aside"
    if len(records.readings) >= 2 and not records.writings:
        return GoalType.CREATE, "Write about what I read"
    if records.interactions + records.conversations == 0:
        return GoalType.SOCIALIZE, "Be around in case Paolo visits"
    return GoalType.EXPLORE, "Try something a little new"


def reflect(
    records: DayRecords,
    *,
    state: MapleState,
    memories: Sequence[Memory],
    preferences: Mapping[str, Memory],
    previous_needs: Needs | None,
    now: datetime,
    recovered: bool = False,
) -> ReflectionOutcome:
    """The day's reflection and its memory changes. Pure; never touches needs."""
    require_utc(now, "now")
    done = Counter(records.activities_completed)
    top = [ACTIVITY_WORDS[a] for a, _ in done.most_common(2) if a in ACTIVITY_WORDS]
    lines = [
        f"Today I started {len(records.goals_started)} goals, finished"
        f" {len(records.goals_completed)} and set {len(records.goals_abandoned)} aside."
    ]
    if top:
        lines.append(f"I spent the most time {' and '.join(top)}.")
    if records.readings:
        lines.append(f"I read {', '.join(t for t, _ in records.readings[:3])}.")
    if records.writings:
        lines.append(f"I wrote {', '.join(records.writings[:3])}.")
    if records.interactions or records.conversations:
        lines.append(
            f"Paolo spent time with me ({records.interactions} greetings or pats,"
            f" {records.conversations} conversations)."
        )
    if records.server_problems:
        lines.append(f"The server needed serious attention {records.server_problems} times.")
    if records.interruptions or records.failures:
        lines.append(
            f"Some things did not go as planned: {records.interruptions} interruptions,"
            f" {records.failures} other hiccups."
        )
    mood = _mood_line(state.needs, previous_needs)
    if mood:
        lines.append(mood)
    summary = one_line(" ".join(lines), MAX_SUMMARY)

    learned = tuple(one_line(f"From {t}: {x}", 200) for t, x in records.readings[:5] if x)
    day_memories = sorted(
        (m for m in memories if m.tier is Tier.SHORT_TERM and m.id is not None
         and m.status is MemoryStatus.ACTIVE),
        key=lambda m: (-m.importance, -(m.id or 0)),
    )  # fmt: skip
    moments = tuple(m.text for m in day_memories if m.importance >= 0.5)[:5]
    candidates = tuple(
        MemoryCandidate(m.id or 0, m.text, _REASONS.get(m.kind, "worth keeping"))
        for m in day_memories[:MAX_CANDIDATES]
    )
    changes: list[MemoryChange] = []
    promoted: tuple[int, ...] = ()
    if day_memories and day_memories[0].importance >= PROMOTE_IMPORTANCE:
        best = day_memories[0]
        changes.append(promote(best, now, "chosen by my daily reflection"))
        promoted = (best.id or 0,)

    pref_candidates: list[tuple[str, str]] = []
    for activity, count in sorted(done.items(), key=lambda item: item[0].value):
        if count < PREFERENCE_REPEATS or activity in (Activity.SLEEP, Activity.IDLE):
            continue
        key = f"prefers:{activity.value}"
        text = f"I seem to enjoy {ACTIVITY_WORDS[activity]}."
        pref_candidates.append((key, text))
        existing = preferences.get(key)
        if existing is None:
            changes.append(new_preference(key, text, now, records.day))
        else:
            reinforced = reinforce_preference(existing, now, records.day)
            if reinforced is not None:
                changes.append(reinforced)

    intent_type, intent_summary = _intent(records)
    reflection = DailyReflection(
        day=records.day,
        created_at=now,
        recovered=recovered,
        summary=summary,
        learned=learned,
        moments=moments,
        memory_candidates=candidates,
        promoted=promoted,
        preference_candidates=tuple(pref_candidates),
        intent_type=intent_type,
        intent_summary=intent_summary,
        needs=state.needs,
    )
    return ReflectionOutcome(reflection, tuple(changes))
