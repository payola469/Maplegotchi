"""When Maple writes in its journal: triggers, deduplication, the daily window.

Pure and deterministic. `ReflectionState` is persisted with each transition,
so every rule below survives restarts.

v0.1 rules (tunable; see docs/journal.md):
- Maple's journal day runs 06:00-06:00 Asia/Bangkok (D16 offset). Daily
  counters reset when a new journal day starts.
- Daily life: at most one entry per kind per journal day, for waking up,
  going to sleep, reading, writing, and checking the server.
- Interactions: an accepted Greet/Pet is journaled unless another interaction
  entry was written within the last 30 minutes. Rejections never journal.
- Server: a condition (service failed, disk nearly full, memory high, running
  hot, CPU very busy) is journaled once when it starts and once when it
  clears. Clearing needs an available observation below a lower threshold
  (hysteresis). Unknown/unavailable/error data neither starts nor clears one.
- Daily reflection: once per journal day, during 21:00-06:00 local. If Maple
  was offline through the whole window, that day has no reflection; there is
  never catch-up for past days.
- Milestones: the first heartbeat, and ages of one day, week, month, year.
  After long downtime only the largest newly reached milestone is written.

Detection and marking are separate: the functions below only detect triggers;
`mark_journaled` advances a trigger's marker (alert, daily kind, reflection day,
milestone, interaction spacing) only when an entry for it was actually written.
If the Brain fails or declines, nothing is marked and the trigger recurs.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta

from maplegotchi.core.activities import Activity
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.heartbeat import TickResult
from maplegotchi.core.interactions import Accepted
from maplegotchi.core.journal import ObservationKey, ServerSummary, Trigger, TriggerKind
from maplegotchi.core.observations import (
    Metric,
    Observation,
    ObservationSnapshot,
    ObservationStatus,
    ServiceState,
)
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.state import MapleState
from maplegotchi.core.timeline import ActivityChanged


@dataclass(frozen=True, slots=True)
class JournalParameters:
    owner_name: str = "Paolo"
    day_start_hour: int = 6  # journal day boundary, local time
    reflection_start_hour: int = 21  # daily reflection window opens (until day_start_hour)
    interaction_entry_gap: timedelta = timedelta(minutes=30)

    def __post_init__(self) -> None:
        if not 0 <= self.day_start_hour < self.reflection_start_hour <= 23:
            raise ValueError("need 0 <= day_start_hour < reflection_start_hour <= 23")
        if not self.owner_name.strip() or any(ch.isdigit() for ch in self.owner_name):
            raise ValueError("owner_name must be a non-empty name without digits")
        if self.interaction_entry_gap < timedelta(0):
            raise ValueError("interaction_entry_gap must be >= 0")


@dataclass(frozen=True, slots=True)
class ReflectionState:
    journal_day: date | None = None  # day the daily counters refer to
    daily_seen: frozenset[str] = frozenset()  # daily-life kinds already journaled today
    interactions_today: int = 0
    notices_today: int = 0  # server problems noticed today
    last_interaction_entry_at: datetime | None = None
    active_alerts: tuple[tuple[str, str], ...] = ()  # (topic, condition), sorted by topic
    last_reflection_day: date | None = None
    milestones: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.interactions_today < 0 or self.notices_today < 0:
            raise ValueError("counters must be >= 0")
        if self.last_interaction_entry_at is not None:
            require_utc(self.last_interaction_entry_at, "last_interaction_entry_at")
        topics = [t for t, _ in self.active_alerts]
        if topics != sorted(set(topics)):
            raise ValueError("active alerts must be unique and sorted by topic")


INITIAL_REFLECTION = ReflectionState()

MILESTONES: tuple[tuple[str, int], ...] = (
    ("one_day", 1),
    ("one_week", 7),
    ("one_month", 30),
    ("one_year", 365),
)

# (metric, condition, start threshold, clear threshold): starts at >= start, clears at < clear.
NUMERIC_CONDITIONS: tuple[tuple[Metric, str, float, float], ...] = (
    (Metric.DISK_USAGE, "nearly_full", 95.0, 90.0),
    (Metric.MEMORY_USAGE, "high", 90.0, 85.0),
    (Metric.TEMPERATURE, "hot", 85.0, 80.0),
    (Metric.CPU_USAGE, "busy", 90.0, 75.0),
)
_TOPIC_PREFIX = {
    Metric.DISK_USAGE: "disk",
    Metric.MEMORY_USAGE: "memory",
    Metric.TEMPERATURE: "temperature",
    Metric.CPU_USAGE: "cpu",
    Metric.SERVICE_STATE: "service",
}
# Core host readings whose absence makes the server picture "unclear".
_ESSENTIAL = (Metric.CPU_USAGE, Metric.MEMORY_USAGE, Metric.DISK_USAGE, Metric.SERVICE_STATE)


def local_time(now: datetime, params: CoreParameters) -> datetime:
    require_utc(now, "now")
    return now + params.utc_offset


def journal_day(now: datetime, params: CoreParameters, journal: JournalParameters) -> date:
    return (local_time(now, params) - timedelta(hours=journal.day_start_hour)).date()


def day_start(day: date, params: CoreParameters, journal: JournalParameters) -> datetime:
    """UTC instant when a journal day begins (day_start_hour local time)."""
    local_start = datetime(day.year, day.month, day.day, journal.day_start_hour, tzinfo=UTC)
    return local_start - params.utc_offset


def in_reflection_window(now: datetime, params: CoreParameters, journal: JournalParameters) -> bool:
    hour = local_time(now, params).hour
    return hour >= journal.reflection_start_hour or hour < journal.day_start_hour


def roll_day(rs: ReflectionState, day: date) -> ReflectionState:
    if rs.journal_day == day:
        return rs
    return replace(
        rs, journal_day=day, daily_seen=frozenset(), interactions_today=0, notices_today=0
    )


def _topic(observation: Observation) -> str:
    return f"{_TOPIC_PREFIX[observation.metric]}:{observation.subject}"


def _key(observation: Observation) -> ObservationKey:
    return (observation.metric, observation.subject)


def evaluate_conditions(
    active: tuple[tuple[str, str], ...], snapshot: ObservationSnapshot | None
) -> tuple[tuple[tuple[str, str], ...], list[Trigger], list[Trigger]]:
    """New active alerts, plus problem and recovery triggers, from one snapshot."""
    alerts = dict(active)
    problems: list[Trigger] = []
    recoveries: list[Trigger] = []
    if snapshot is None:
        return active, problems, recoveries
    for observation in sorted(snapshot.observations, key=lambda o: (o.metric, o.subject)):
        if observation.status is not ObservationStatus.AVAILABLE:
            continue  # unknown data neither starts nor clears a condition
        topic = _topic(observation) if observation.metric in _TOPIC_PREFIX else None
        if topic is None:
            continue
        starts = clears = False
        condition = ""
        if observation.metric is Metric.SERVICE_STATE:
            condition = "failed"
            starts = observation.state is ServiceState.FAILED
            clears = observation.state is ServiceState.ACTIVE
        else:
            for metric, name, start, clear in NUMERIC_CONDITIONS:
                if metric is observation.metric and observation.value is not None:
                    condition = name
                    starts = observation.value >= start
                    clears = observation.value < clear
        if not condition:
            continue
        if topic not in alerts and starts:
            alerts[topic] = condition
            problems.append(
                Trigger(
                    TriggerKind.SERVER_PROBLEM,
                    topic,
                    label=condition,
                    subject=observation.subject,
                    observation_keys=(_key(observation),),
                )
            )
        elif topic in alerts and clears:
            label = alerts.pop(topic)
            recoveries.append(
                Trigger(
                    TriggerKind.SERVER_RECOVERY,
                    topic,
                    label=label,
                    subject=observation.subject,
                    observation_keys=(_key(observation),),
                )
            )
    return tuple(sorted(alerts.items())), problems, recoveries


def server_summary(
    rs: ReflectionState, snapshot: ObservationSnapshot | None
) -> tuple[ServerSummary, tuple[ObservationKey, ...]]:
    """What may truthfully be said about the server, with the facts behind it."""
    observations = snapshot.observations if snapshot is not None else ()
    available = [o for o in observations if o.status is ObservationStatus.AVAILABLE]
    if not available:
        return ServerSummary.NO_DATA, ()
    if rs.active_alerts:
        topics = {t for t, _ in rs.active_alerts}
        return ServerSummary.STILL_TROUBLED, tuple(
            _key(o) for o in available if o.metric in _TOPIC_PREFIX and _topic(o) in topics
        )
    evidence = tuple(_key(o) for o in available if o.metric in _ESSENTIAL)
    if rs.notices_today:
        return ServerSummary.TROUBLED_EARLIER, evidence
    unseen = [
        o
        for o in observations
        if o.metric in _ESSENTIAL
        and o.status is not ObservationStatus.AVAILABLE
        and not o.unobservable_by_design  # a known limit of Maple's senses, not a doubt
    ]
    if unseen:
        return ServerSummary.UNCLEAR, evidence
    return ServerSummary.CALM, evidence


def _daily_kind(event: ActivityChanged) -> str | None:
    if event.previous is Activity.SLEEP and event.current is not Activity.SLEEP:
        return "woke"
    return {
        Activity.SLEEP: "sleep",
        Activity.READ: "read",
        Activity.WRITE: "write",
        Activity.OBSERVE_SERVER: "observe",
    }.get(event.current)


def heartbeat_triggers(
    rs: ReflectionState,
    *,
    previous: MapleState,
    result: TickResult,
    snapshot: ObservationSnapshot | None,
    now: datetime,
    params: CoreParameters,
    journal: JournalParameters,
) -> tuple[tuple[Trigger, ...], ReflectionState]:
    """Triggers for one heartbeat, and the state with only the day rolled over.

    Journal markers (alerts, daily kinds seen, reflection day, milestones) are
    NOT advanced here; `mark_journaled` advances them only for triggers that
    actually produced an entry, so a failed or declined wording is retried.
    """
    rs = roll_day(rs, journal_day(now, params, journal))
    triggers: list[Trigger] = []

    # Milestones. The first-heartbeat milestone stays open for the first day, so a
    # failed wording is retried rather than lost.
    age = now - previous.identity.born_at
    if "first_heartbeat" not in rs.milestones and age < timedelta(days=1):
        triggers.append(
            Trigger(TriggerKind.MILESTONE, "milestone:first_heartbeat", "first_heartbeat")
        )
    crossed = [
        name
        for name, days in MILESTONES
        if age >= timedelta(days=days) and name not in rs.milestones
    ]
    if crossed:
        triggers.append(Trigger(TriggerKind.MILESTONE, f"milestone:{crossed[-1]}", crossed[-1]))

    # Server conditions: journal changes, not persistence.
    alerts, problems, recoveries = evaluate_conditions(rs.active_alerts, snapshot)
    triggers += problems + recoveries

    # Daily life: first of each notable kind per journal day, at most one per heartbeat.
    for event in result.events:
        if isinstance(event, ActivityChanged):
            kind = _daily_kind(event)
            if kind is not None and kind not in rs.daily_seen:
                triggers.append(Trigger(TriggerKind.ACTIVITY, f"daily:{kind}", kind))
                break

    # Daily reflection: once per journal day, inside the window, and only for a day
    # Maple was alive for from its start (no reflection on a day it never lived).
    day = rs.journal_day
    lived_whole_day = day is not None and previous.identity.born_at <= day_start(
        day, params, journal
    )
    if (
        in_reflection_window(now, params, journal)
        and rs.last_reflection_day != day
        and lived_whole_day
    ):
        # The server description uses the facts as they are now, whether or not
        # this heartbeat's own notices get written.
        facts = replace(rs, active_alerts=alerts, notices_today=rs.notices_today + len(problems))
        summary, evidence = server_summary(facts, snapshot)
        triggers.append(
            Trigger(
                TriggerKind.DAILY_REFLECTION,
                "reflection",
                summary=summary,
                observation_keys=evidence,
                day_activities=tuple(k for k in ("read", "write", "observe") if k in rs.daily_seen),
                interactions_today=rs.interactions_today,
            )
        )

    return tuple(triggers), rs


def interaction_triggers(
    rs: ReflectionState,
    *,
    accepted: Accepted,
    now: datetime,
    params: CoreParameters,
    journal: JournalParameters,
) -> tuple[tuple[Trigger, ...], ReflectionState]:
    """Triggers for an accepted interaction; the count is a fact and always advances."""
    rs = roll_day(rs, journal_day(now, params, journal))
    rs = replace(rs, interactions_today=rs.interactions_today + 1)
    last = rs.last_interaction_entry_at
    if last is not None and now - last < journal.interaction_entry_gap:
        return (), rs
    kind = accepted.event.kind
    trigger = Trigger(
        TriggerKind.INTERACTION,
        f"interaction:{kind.value}",
        kind.value,
        reaction=accepted.reaction.kind,
    )
    return (trigger,), rs


def mark_journaled(
    rs: ReflectionState,
    triggers: Sequence[Trigger],
    written: Collection[tuple[TriggerKind, str]],
    now: datetime,
) -> ReflectionState:
    """Advance journal markers for the triggers that produced an entry, and no others.

    `written` holds (trigger kind, topic) of the entries actually accepted. A
    trigger without an entry leaves its marker untouched, so the same trigger
    fires again at the next opportunity under the normal rules.
    """
    alerts = dict(rs.active_alerts)
    milestones = set(rs.milestones)
    daily_seen = set(rs.daily_seen)
    notices = rs.notices_today
    last_reflection_day = rs.last_reflection_day
    last_interaction = rs.last_interaction_entry_at
    for trigger in triggers:
        if (trigger.kind, trigger.topic) not in written:
            continue
        if trigger.kind is TriggerKind.SERVER_PROBLEM:
            alerts[trigger.topic] = trigger.label
            notices += 1
        elif trigger.kind is TriggerKind.SERVER_RECOVERY:
            alerts.pop(trigger.topic, None)
        elif trigger.kind is TriggerKind.ACTIVITY:
            daily_seen.add(trigger.label)
        elif trigger.kind is TriggerKind.DAILY_REFLECTION:
            last_reflection_day = rs.journal_day
        elif trigger.kind is TriggerKind.INTERACTION:
            last_interaction = now
        elif trigger.kind is TriggerKind.MILESTONE:
            milestones.add(trigger.label)
            limit = dict(MILESTONES).get(trigger.label)
            if limit is not None:  # reaching a larger milestone implies the smaller ones
                milestones.update(name for name, days in MILESTONES if days <= limit)
    return replace(
        rs,
        active_alerts=tuple(sorted(alerts.items())),
        milestones=frozenset(milestones),
        daily_seen=frozenset(daily_seen),
        notices_today=notices,
        last_reflection_day=last_reflection_day,
        last_interaction_entry_at=last_interaction,
    )
