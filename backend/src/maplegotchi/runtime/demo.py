"""A deterministic simulated day, showing timeline vs observations vs journal.

Fake clock, fake senses, fixed seed; the real runtime, storage, and RuleBrain.
Script (Asia/Bangkok local time), starting on 2026-01-01:
  02:00 Maple is born (and sleeps)      08:00 Greet, 08:00:20 Pet
  12:00 the runtime is restarted        14:00-15:30 Jellyfin fails, then recovers
  20:00 Pet                             21:00+ daily reflection (restart at 21:30)
  ends at 23:55
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from maplegotchi.core.observations import Metric, ObservationStatus, ServiceState
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.state import InteractionKind
from maplegotchi.core.timeline import (
    ActivityChanged,
    Born,
    DowntimeGap,
    GoalCompleted,
    GoalResumed,
    GoalStarted,
    GoalSuspended,
    InteractionAccepted,
    LifeEvent,
)
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.life import LifeRuntime
from maplegotchi.runtime.senses import Senses
from maplegotchi.sensors.fake import FakeHostProbe
from maplegotchi.sensors.interface import MetricUnavailable
from maplegotchi.sensors.service_health.fake import FakeServiceHealth
from maplegotchi.sensors.service_health.interface import INTENDED_SERVICES, ServiceReading
from maplegotchi.storage.datadir import DataDir
from maplegotchi.storage.repositories import StoredEvent, StoredJournalEntry, StoredObservation

DEMO_SEED = "d3" * 32
LOCAL_MIDNIGHT = datetime(2025, 12, 31, 17, 0, tzinfo=UTC)  # 2026-01-01 00:00 Asia/Bangkok
PARAMS = CoreParameters()


def at(hour: float) -> datetime:
    """UTC instant for a local (Asia/Bangkok) time on the demo day."""
    return LOCAL_MIDNIGHT + timedelta(hours=hour)


def _senses(jellyfin: ServiceState) -> Senses:
    readings = {
        t.service_id: ServiceReading(ObservationStatus.AVAILABLE, state=ServiceState.ACTIVE)
        for t in INTENDED_SERVICES
    }
    readings["jellyfin"] = ServiceReading(ObservationStatus.AVAILABLE, state=jellyfin)
    host = FakeHostProbe(temperature=MetricUnavailable("no_temperature_sensors"))
    return Senses(host, (FakeServiceHealth(readings),))


@dataclass(frozen=True)
class DemoReport:
    timeline: tuple[StoredEvent, ...]
    observations: tuple[StoredObservation, ...]
    journal: tuple[StoredJournalEntry, ...]
    restarts: int
    heartbeats: int


def run_demo_day(data_dir: DataDir) -> DemoReport:
    clock = FakeClock(at(2))
    healthy, failing = _senses(ServiceState.ACTIVE), _senses(ServiceState.FAILED)
    interactions = {
        at(8): InteractionKind.GREET,
        at(8) + timedelta(seconds=20): InteractionKind.PET,
        at(20): InteractionKind.PET,
    }
    restart_at = {at(12), at(21.5)}

    def open_runtime() -> LifeRuntime:
        return LifeRuntime.open(data_dir, clock, PARAMS, new_seed=lambda: DEMO_SEED)

    runtime = open_runtime()
    restarts = heartbeats = 0
    now = at(2)
    end = at(23 + 55 / 60)
    pending = sorted(interactions)
    while now < end:
        now += PARAMS.heartbeat_interval
        while pending and pending[0] <= now:
            clock.set(pending[0])
            runtime.interact(interactions[pending.pop(0)])
        if now in restart_at:
            runtime.close()
            runtime = open_runtime()
            restarts += 1
        clock.set(now)
        senses = failing if at(14) <= now < at(15.5) else healthy
        if runtime.heartbeat_due():
            runtime.heartbeat_if_due(senses.observe(now))
            heartbeats += 1
    report = DemoReport(
        timeline=tuple(runtime.timeline()),
        observations=tuple(runtime.observations()),
        journal=tuple(runtime.journal()),
        restarts=restarts,
        heartbeats=heartbeats,
    )
    runtime.close()
    return report


def local_clock(moment: datetime) -> str:
    return (moment + PARAMS.utc_offset).strftime("%H:%M")


def _describe(event: LifeEvent) -> tuple[datetime, str]:
    if isinstance(event, Born):
        return event.at, f"born as {event.name}"
    if isinstance(event, InteractionAccepted):
        return event.at, f"{event.kind.value} accepted ({event.reaction.value})"
    if isinstance(event, DowntimeGap):
        return event.until, f"downtime since {local_clock(event.since)}"
    if isinstance(event, ActivityChanged):
        return event.at, f"{event.previous.value} -> {event.current.value}"
    if isinstance(event, GoalStarted):
        return event.at, f"goal {event.goal.id} started: {event.goal.type.value}"
    if isinstance(event, GoalSuspended):
        return event.at, f"goal {event.goal_id} suspended ({event.cause})"
    if isinstance(event, GoalResumed):
        return event.at, f"goal {event.goal_id} resumed"
    if isinstance(event, GoalCompleted):
        return event.at, f"goal {event.goal_id} completed ({event.reason.value})"
    return event.at, f"goal {event.goal_id} abandoned ({event.reason.value})"


def format_report(report: DemoReport) -> str:
    """Human-readable output for the CLI; the three records kept visibly apart."""
    lines = [
        f"Simulated day: {report.heartbeats} heartbeats, {report.restarts} restarts",
        "",
        "TIMELINE (factual lifecycle events)",
    ]
    changes = [e for e in report.timeline if isinstance(e.event, ActivityChanged)]
    for stored in report.timeline:
        if not isinstance(stored.event, ActivityChanged):
            moment, text = _describe(stored.event)
            lines.append(f"  {local_clock(moment)}  {text}")
    lines.append(f"  + {len(changes)} activity changes, first six:")
    for stored in changes[:6]:
        moment, text = _describe(stored.event)
        lines.append(f"  {local_clock(moment)}  {text}")

    lines += ["", "OBSERVATIONS (facts; jellyfin service_state changes shown)"]
    previous = None
    for seen in report.observations:
        o = seen.observation
        if o.metric is Metric.SERVICE_STATE and o.subject == "jellyfin" and o.state != previous:
            state = o.state.value if o.state else o.status.value
            lines.append(f"  {local_clock(o.observed_at)}  #{seen.id} jellyfin {state}")
            previous = o.state
    lines.append(f"  ({len(report.observations)} observations stored in total)")

    lines += ["", "JOURNAL (Maple's interpretation)"]
    for written in report.journal:
        entry = written.entry
        ids = list(written.observation_ids)
        cites = f"  <- observations {ids[:3]}{' ...' if len(ids) > 3 else ''}" if ids else ""
        lines.append(
            f"  {local_clock(entry.created_at)}  [{entry.category.value}, {entry.brain_kind.value}]"
            f" {entry.text}{cites}"
        )
    return "\n".join(lines)
