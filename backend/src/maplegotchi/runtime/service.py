"""The application layer between HTTP and Maple's life.

`MapleService` owns the single-writer `LifeRuntime`, Maple's senses, the clock,
and the live-event hub. Routes call only this service; every rule it applies
(expression, reaction, cooldown availability, server summary, attention,
day/night) comes from core. It adds nothing but assembly and freshness.

Heartbeats run in a background loop: senses are read outside the writer lock,
then the heartbeat commits through the same serialized path as Greet/Pet.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from maplegotchi.config import SensesKind, Settings
from maplegotchi.core.attention import ServerAttention, assess_server_attention
from maplegotchi.core.daytime import DayPhase, day_phase, is_night, local_hour
from maplegotchi.core.heartbeat import TickResult
from maplegotchi.core.interactions import (
    Accepted,
    InteractionOutcome,
    RejectionReason,
    check_limits,
)
from maplegotchi.core.journal import BrainKind, ServerSummary
from maplegotchi.core.observations import (
    ObservationSnapshot,
    ObservationStatus,
    ServiceState,
)
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.reflection import ReflectionState, server_summary
from maplegotchi.core.state import Expression, InteractionKind, MapleState, Reaction
from maplegotchi.runtime.brain_factory import build_brain
from maplegotchi.runtime.clock import Clock, SystemClock
from maplegotchi.runtime.events import EventHub
from maplegotchi.runtime.life import LifeRuntime
from maplegotchi.runtime.senses import Senses, paolo_core_senses
from maplegotchi.sensors.fake import FakeHostProbe
from maplegotchi.sensors.service_health.fake import FakeServiceHealth
from maplegotchi.sensors.service_health.interface import INTENDED_SERVICES, ServiceReading
from maplegotchi.storage.datadir import DataDir
from maplegotchi.storage.repositories import StoredEvent, StoredJournalEntry, StoredObservation

HEARTBEAT_GRACE = timedelta(seconds=60)
DECISION_GRACE = timedelta(seconds=120)
RECENT_LIMIT = 10
SSE_KEEPALIVE_SECONDS = 15


class HeartbeatStatus(StrEnum):
    FRESH = "fresh"  # a heartbeat ran within interval + grace
    OVERDUE = "overdue"  # connected, but the life loop has not beaten in time


class SensorStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"  # the latest observations are older than a heartbeat + grace
    NONE = "none"  # nothing has been observed yet


@dataclass(frozen=True)
class InteractionAvailability:
    kind: InteractionKind
    available: bool
    reason: RejectionReason | None
    retry_after: timedelta | None


@dataclass(frozen=True)
class Freshness:
    last_heartbeat_at: datetime
    next_heartbeat_due_at: datetime
    heartbeat_interval: timedelta
    heartbeat_status: HeartbeatStatus
    life_loop_running: bool
    life_loop_error: str | None
    sensor_status: SensorStatus
    observations_at: datetime | None


@dataclass(frozen=True)
class ServerView:
    observed_at: datetime | None
    observations: tuple[StoredObservation, ...]
    summary: ServerSummary
    attention: ServerAttention


@dataclass(frozen=True)
class BrainLabel:
    kind: BrainKind
    name: str
    version: str


@dataclass(frozen=True)
class LiveSnapshot:
    now: datetime
    revision: int
    state: MapleState
    expression: Expression
    reaction: Reaction | None
    local_time: datetime
    local_hour: float
    day_phase: DayPhase
    is_night: bool
    utc_offset: timedelta
    server: ServerView
    journal: tuple[StoredJournalEntry, ...]
    timeline: tuple[StoredEvent, ...]
    freshness: Freshness
    brain: BrainLabel
    interactions: tuple[InteractionAvailability, ...]


@dataclass(frozen=True)
class InteractionResult:
    outcome: InteractionOutcome
    revision: int  # the interaction's own committed revision (unchanged if rejected)
    snapshot: LiveSnapshot  # read after the commit, so snapshot.revision >= revision


def fake_senses() -> Senses:
    """Deterministic senses for development: a calm host and healthy services."""
    readings = {
        t.service_id: ServiceReading(ObservationStatus.AVAILABLE, state=ServiceState.ACTIVE)
        for t in INTENDED_SERVICES
    }
    return Senses(FakeHostProbe(), (FakeServiceHealth(readings),))


class MapleService:
    def __init__(
        self,
        runtime: LifeRuntime,
        senses: Senses,
        clock: Clock,
        params: CoreParameters,
        hub: EventHub | None = None,
    ) -> None:
        self.runtime = runtime
        self.senses = senses
        self.clock = clock
        self.params = params
        self.hub = hub or EventHub()
        self._loop_task: asyncio.Task[None] | None = None
        self._loop_error: str | None = None
        self._stop = asyncio.Event()

    @classmethod
    def open(
        cls,
        settings: Settings,
        *,
        clock: Clock | None = None,
        senses: Senses | None = None,
    ) -> MapleService:
        clock = clock or SystemClock()
        params = CoreParameters(
            heartbeat_interval=timedelta(seconds=settings.heartbeat_seconds),
            # Decisions have their own transition; the heartbeat steps in only if one
            # is overdue (ADR-0026 §3).
            decision_grace=DECISION_GRACE,
        )
        if senses is None:
            senses = (
                fake_senses()
                if settings.senses is SensesKind.FAKE
                else paolo_core_senses(settings.monitor_db)
            )
        brain = build_brain(settings)
        runtime = LifeRuntime.open(DataDir(settings.data_dir), clock, params, brain=brain)
        return cls(runtime, senses, clock, params)

    # ------------------------------------------------------------ reads

    def interaction_availability(
        self, state: MapleState, now: datetime
    ) -> tuple[InteractionAvailability, ...]:
        moment = max(now, state.last_updated_at)
        result = []
        for kind in InteractionKind:
            blocked = check_limits(state, kind, moment)
            result.append(
                InteractionAvailability(
                    kind=kind,
                    available=blocked is None,
                    reason=blocked.reason if blocked else None,
                    retry_after=blocked.retry_after if blocked else None,
                )
            )
        return tuple(result)

    def _server_view(
        self, latest: tuple[StoredObservation, ...], reflection: ReflectionState
    ) -> ServerView:
        if not latest:
            return ServerView(None, (), ServerSummary.NO_DATA, assess_server_attention(None))
        observed_at = max(s.observation.observed_at for s in latest)
        snap = ObservationSnapshot(observed_at, tuple(s.observation for s in latest))
        summary, _ = server_summary(reflection, snap)
        return ServerView(observed_at, latest, summary, assess_server_attention(snap))

    def freshness(
        self, state: MapleState, now: datetime, observed_at: datetime | None
    ) -> Freshness:
        interval = self.params.heartbeat_interval
        due = state.last_tick_at + interval
        if observed_at is None:
            sensors = SensorStatus.NONE
        elif now - observed_at <= interval + HEARTBEAT_GRACE:
            sensors = SensorStatus.FRESH
        else:
            sensors = SensorStatus.STALE
        return Freshness(
            last_heartbeat_at=state.last_tick_at,
            next_heartbeat_due_at=due,
            heartbeat_interval=interval,
            heartbeat_status=HeartbeatStatus.FRESH
            if now <= due + HEARTBEAT_GRACE
            else HeartbeatStatus.OVERDUE,
            life_loop_running=self._loop_task is not None and not self._loop_task.done(),
            life_loop_error=self._loop_error,
            sensor_status=sensors,
            observations_at=observed_at,
        )

    def snapshot(self, *, recent: int = RECENT_LIMIT) -> LiveSnapshot:
        """A snapshot whose persisted parts all come from ONE committed database view.

        `read_view` reads state, revision, journal state, the latest
        observations, journal and timeline inside a single SQLite read
        transaction. Only derived-at-read values (time, expression, active
        reaction, availability, freshness) use the current clock; they never write.
        """
        runtime = self.runtime
        view = runtime.read_view(recent=recent)
        state, revision = view.life.state, view.life.revision
        now = max(self.clock.now(), state.last_updated_at)
        server = self._server_view(view.observations, view.reflection)
        local = now + self.params.utc_offset
        hour = local_hour(now, self.params.utc_offset)
        brain = runtime.brain
        return LiveSnapshot(
            now=now,
            revision=revision,
            state=state,
            expression=state.expression_at(now),
            reaction=state.active_reaction(now),
            local_time=local,
            local_hour=hour,
            day_phase=day_phase(hour),
            is_night=is_night(hour),
            utc_offset=self.params.utc_offset,
            server=server,
            journal=view.journal,
            timeline=view.timeline,
            freshness=self.freshness(state, now, server.observed_at),
            brain=BrainLabel(brain.kind, brain.name, brain.version),
            interactions=self.interaction_availability(state, now),
        )

    # ------------------------------------------------------------ transitions

    def settle(self) -> None:
        """Record a walk's arrival between heartbeats, so the activity begins on time."""
        if not self.runtime.arrival_due():
            return
        committed = self.runtime.settle_committed()
        if committed is None:
            return
        self._publish("movement", {"revision": committed.revision, "state": committed.state})
        self._publish_written(
            committed.revision, events=bool(committed.events), journal=bool(committed.journal)
        )

    def decide(self) -> None:
        """Run a due decision transition (ADR-0026 §3): next goal and action."""
        if not self.runtime.decision_is_due():
            return
        committed = self.runtime.decide_committed()
        if committed is None:
            return
        self._publish(
            "movement", {"revision": committed.revision, "state": committed.outcome.state}
        )
        self._publish_written(
            committed.revision,
            events=bool(committed.outcome.events),
            journal=bool(committed.journal),
        )

    def step(self) -> None:
        """One life-loop pass: record arrivals, make due decisions, heartbeat if due."""
        self.settle()
        self.decide()
        self.tick()

    def tick(self) -> TickResult | None:
        """Observe (outside the lock) and heartbeat if due.

        Events are published only after the runtime has durably committed the
        transition and released its lock; if the commit fails, nothing is published.
        """
        if not self.runtime.heartbeat_due():
            return None
        observations = self.senses.observe(self.clock.now())
        committed = self.runtime.heartbeat_committed(observations)
        if committed is None:
            return None
        revision, result = committed.revision, committed.result
        self._publish(
            "heartbeat", {"revision": revision, "tick_id": result.tick_id, "state": result.state}
        )
        self._publish("observations", {"revision": revision, "snapshot": observations})
        self._publish_written(revision, events=bool(result.events), journal=bool(committed.journal))
        return result

    def interact(self, kind: InteractionKind) -> InteractionResult:
        committed = self.runtime.interact_committed(kind)
        outcome = committed.outcome
        if isinstance(outcome, Accepted):
            revision = committed.revision
            self._publish(
                "interaction", {"revision": revision, "kind": kind, "reaction": outcome.reaction}
            )
            self._publish_written(revision, events=True, journal=bool(committed.journal))
        return InteractionResult(outcome, committed.revision, self.snapshot())

    def _publish_written(self, revision: int, *, events: bool, journal: bool) -> None:
        """Publish the timeline events and journal entries committed by exactly `revision`."""
        if not (events or journal):
            return
        timeline, entries = self.runtime.written_at(revision)
        if timeline:
            self._publish("timeline", {"revision": revision, "events": tuple(timeline)})
        if entries:
            self._publish("journal", {"revision": revision, "entries": tuple(entries)})

    def _publish(self, kind: str, data: dict[str, object]) -> None:
        """Best-effort notice of an already-committed fact; it can never undo or block it."""
        try:
            self.hub.publish(kind, data)
        except Exception:  # noqa: S110 - a broken hub must not affect Maple's life
            pass

    # ------------------------------------------------------------ life loop

    async def _life_loop(self, poll_seconds: float) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.to_thread(self.step)
                self._loop_error = None
            except Exception as exc:  # fail soft: record, keep living, try again
                self._loop_error = type(exc).__name__
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=poll_seconds)
            except TimeoutError:
                pass

    def start_life_loop(self, poll_seconds: float) -> None:
        self._stop = asyncio.Event()
        self._loop_task = asyncio.get_running_loop().create_task(self._life_loop(poll_seconds))

    async def stop_life_loop(self) -> None:
        self._stop.set()
        if self._loop_task is not None:
            await self._loop_task
            self._loop_task = None

    def close(self) -> None:
        self.runtime.close()
