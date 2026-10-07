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
import concurrent.futures
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

import httpx2

from maplegotchi.brain.director import Director, DirectorKind
from maplegotchi.config import SensesKind, Settings
from maplegotchi.core.attention import ServerAttention, assess_server_attention
from maplegotchi.core.audit import RULE_DIRECTOR_NAME, RULE_DIRECTOR_VERSION
from maplegotchi.core.conversation import IncomingMessage, ReplyContext, reply_problems, rule_reply
from maplegotchi.core.daytime import DayPhase, day_phase, is_night, local_hour
from maplegotchi.core.direction import RejectionCode
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
from maplegotchi.core.proposal import DecisionContext, DirectorLabel
from maplegotchi.core.reflection import ReflectionState, server_summary
from maplegotchi.core.state import Expression, InteractionKind, MapleState, Reaction
from maplegotchi.runtime.brain_factory import build_brain, build_director, build_replier
from maplegotchi.runtime.brain_health import (
    BrainHealthReport,
    CallerLabel,
    CompanionProbe,
    build_report,
    probe_companion,
)
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
    director: DirectorLabel
    interactions: tuple[InteractionAvailability, ...]


@dataclass(frozen=True)
class InteractionResult:
    outcome: InteractionOutcome
    revision: int  # the interaction's own committed revision (unchanged if rejected)
    snapshot: LiveSnapshot  # read after the commit, so snapshot.revision >= revision


class DirectorNotAllowed(RuntimeError):
    """The configured object is not an external Director (rule direction is core's own)."""


def require_supported_director(director: Director | None) -> Director | None:
    if director is None:
        return None
    if getattr(director, "kind", None) is not DirectorKind.EXTERNAL:
        raise DirectorNotAllowed(
            f"only external Directors can be wired; rule direction is core's own "
            f"(got {type(director).__name__})"
        )
    if not callable(getattr(director, "propose_decision", None)):
        raise DirectorNotAllowed(f"{type(director).__name__} has no propose_decision")
    return director


class Replier(Protocol):
    kind: str
    name: str

    def reply(self, context: ReplyContext) -> str: ...


@dataclass(frozen=True)
class ConversationResult:
    reply: str
    revision: int
    duplicate: bool  # a retried message: the earlier reply is returned
    replier_kind: str
    replier_name: str
    fallback_code: str | None  # why the rule reply was used instead, if it was


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
        director: Director | None = None,
        director_timeout_seconds: float = 15.0,
        replier: Replier | None = None,
        companion_probe: CompanionProbe | None = None,
    ) -> None:
        self.runtime = runtime
        self.senses = senses
        self.clock = clock
        self.params = params
        self.hub = hub or EventHub()
        self.director = require_supported_director(director)
        self.director_timeout_seconds = director_timeout_seconds
        self._director_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="maple-director"
        )
        self._director_call: concurrent.futures.Future[object | None] | None = None
        self.replier = replier
        self.companion_probe = companion_probe  # Brain Health only (ADR-0034)
        self._replier_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="maple-replier"
        )
        # The last replier call that outlived its deadline and may still be running.
        self._replier_stuck: concurrent.futures.Future[str] | None = None
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
        return cls(
            runtime,
            senses,
            clock,
            params,
            director=build_director(settings),
            director_timeout_seconds=settings.director_timeout_seconds,
            replier=build_replier(settings),
            companion_probe=lambda: probe_companion(settings.brain_url),
        )

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
            director=self.director_label,
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
        """Run a due decision transition (ADR-0026 §3): next goal and action.

        With a Director, its proposal is requested OUTSIDE the writer lock, with a
        hard deadline; core then re-validates it against the current state. Any
        failure becomes a recorded rule-direction fallback; it never stops the loop.
        """
        if not self.runtime.decision_is_due():
            return
        director = self.director
        if director is None:
            committed = self.runtime.decide_committed()
        else:
            pending = self.runtime.pending_decision()
            if pending is None:
                return
            raw, failure, latency = self._ask_director(director, pending.context)
            committed = self.runtime.decide_proposal_committed(
                pending,
                director=DirectorLabel(director.kind.value, director.name, director.version),
                raw=raw,
                failure=failure,
                latency_ms=latency,
            )
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

    def _ask_director(
        self, director: Director, context: DecisionContext
    ) -> tuple[object, RejectionCode | None, int]:
        """(raw proposal, failure code, latency ms). Never raises; never holds the lock."""
        started = time.perf_counter()
        if self._director_call is not None and not self._director_call.done():
            # A previous call is still stuck past its deadline: do not pile up.
            return None, RejectionCode.TIMEOUT, 0
        future = self._director_pool.submit(director.propose_decision, context)
        self._director_call = future
        raw: object = None
        failure: RejectionCode | None = None
        try:
            raw = future.result(timeout=self.director_timeout_seconds)
        except (concurrent.futures.TimeoutError, httpx2.TimeoutException):
            failure = RejectionCode.TIMEOUT
        except Exception:  # transport, HTTP status, decoding, contract: all just "no answer"
            failure = RejectionCode.TRANSPORT_ERROR
        if failure is None and raw is None:
            failure = RejectionCode.NO_PROPOSAL
        latency = int((time.perf_counter() - started) * 1000)
        return raw, failure, latency

    def converse(self, message: IncomingMessage) -> ConversationResult:
        """A message from Paolo: record it and its effects, reply truthfully, record the reply.

        The reply is produced outside the writer lock; any replier failure falls back
        to core's rule reply. Retried messages (same id) get the stored reply again.
        """
        received = self.runtime.receive_message_committed(message)
        if not received.duplicate:
            self._publish("movement", {"revision": received.revision, "state": self.runtime.state})
            self._publish_written(received.revision, events=True, journal=False)
        if received.existing_reply is not None:
            return ConversationResult(
                received.existing_reply, received.revision, True, "rule", "stored", None
            )
        text, kind, name, code, latency = self._reply(received.context)
        revision = self.runtime.record_reply_committed(
            received.message_id,
            text,
            replier_kind=kind,
            replier_name=name,
            fallback_code=code,
            latency_ms=latency,
        )
        self._publish_written(revision, events=False, journal=False)
        return ConversationResult(text, revision, received.duplicate, kind, name, code)

    def _reply(self, context: ReplyContext) -> tuple[str, str, str, str | None, int | None]:
        """(text, replier kind, name, fallback code, latency ms of the external attempt)."""
        replier = self.replier
        if replier is None:
            return rule_reply(context), "rule", "rule_replier", None, None
        code: str | None
        started = time.perf_counter()
        stuck = self._replier_stuck
        if stuck is not None and not stuck.done():
            # A previous call is still stuck past its deadline: do not queue behind it.
            # This request never reaches the provider, so it is `busy`, not a timeout.
            latency = int((time.perf_counter() - started) * 1000)
            return rule_reply(context), "rule", "rule_replier", "busy", latency
        future = self._replier_pool.submit(replier.reply, context)
        try:
            text = future.result(timeout=self.director_timeout_seconds)
            code = "invalid_reply" if reply_problems(text) else None
        except (concurrent.futures.TimeoutError, httpx2.TimeoutException):
            if not future.done() and not future.cancel():
                self._replier_stuck = future  # started; may still be running
            text, code = "", "timeout"
        except Exception:  # transport, status, contract: no usable reply
            text, code = "", "transport_error"
        latency = int((time.perf_counter() - started) * 1000)
        if code is not None:
            return rule_reply(context), "rule", "rule_replier", code, latency
        return text.strip(), replier.kind, replier.name, None, latency

    def brain_health(self) -> BrainHealthReport:
        """Read-only Brain Health (ADR-0034): stored audit + one bounded companion probe.

        Never holds the writer lock while probing; never calls a provider.
        """
        today, director_calls, replier_calls = self.runtime.brain_call_stats()
        brain = self.runtime.brain
        director = self.director_label
        replier = self.replier
        return build_report(
            as_of=self.clock.now(),
            today=today,
            journal_brain=CallerLabel(brain.kind.value, brain.name),
            director=CallerLabel(director.kind, director.name),
            replier=CallerLabel(replier.kind, replier.name)
            if replier is not None
            else CallerLabel("rule", "rule_replier"),
            director_calls=director_calls,
            replier_calls=replier_calls,
            probe=self.companion_probe,
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
        """Publish what exactly `revision` committed: timeline, journal, and life events."""
        timeline, entries = self.runtime.written_at(revision) if (events or journal) else ([], [])
        if timeline:
            self._publish("timeline", {"revision": revision, "events": tuple(timeline)})
        if entries:
            self._publish("journal", {"revision": revision, "entries": tuple(entries)})
        records = self.runtime.life_written_at(revision)
        if records:
            # One coherent event model for Web, iOS and Discord (ADR-0028 §2).
            self._publish("life", {"revision": revision, "records": records})

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

    @property
    def director_label(self) -> DirectorLabel:
        director = self.director
        if director is None:
            return DirectorLabel("rule", RULE_DIRECTOR_NAME, RULE_DIRECTOR_VERSION)
        return DirectorLabel(director.kind.value, director.name, director.version)

    def close(self) -> None:
        self._director_pool.shutdown(wait=False, cancel_futures=True)
        self._replier_pool.shutdown(wait=False, cancel_futures=True)
        self.runtime.close()
