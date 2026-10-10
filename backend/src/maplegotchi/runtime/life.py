"""The single-writer life runtime.

Every change to Maple's life (heartbeats and Greet/Pet) goes through one lock,
reads the clock inside it, computes the transition with pure core, commits it
in one transaction, and only then adopts the new state in memory. A failed
commit leaves both the database and the in-memory state at the last committed
revision, so nothing is lost or half-applied.

Journal entries are part of the same transition: core detects triggers, the
Brain words them, core validates the drafts, and the entries, the journal
state, and the transition commit together. The built-in RuleBrain is the
default; since v0.2 an external Brain (`BrainKind.EXTERNAL`, ADR-0025) is also
accepted, while any other class claiming `kind=rule` is refused
(`require_supported_brain`).

External journal wording is prepared under the lock, composed by a bounded
daemon worker outside it, then revision/lifecycle checked before one atomic
commit. Stale preparations are recomputed without wording. RuleBrain keeps its
synchronous deterministic path. Every persistence path obtains a commit permit
serialized with shutdown; admitted transactions finish before storage closes.
There is no durable journal queue.
"""

from __future__ import annotations

import secrets
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from types import TracebackType
from typing import cast

from maplegotchi.brain.interface import Brain
from maplegotchi.brain.rule_brain import RuleBrain
from maplegotchi.core.attention import ServerAttention, assess_server_attention, behavior_inputs
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.brain_health import CallStats, MapleDay, maple_today
from maplegotchi.core.conversation import (
    Channel,
    IncomingMessage,
    ReplyContext,
    Speaker,
    build_reply_context,
    receive_message,
)
from maplegotchi.core.direction import (
    DecisionOutcome,
    DecisionTrigger,
    RejectionCode,
    decide,
    decision_due,
    prepare,
)
from maplegotchi.core.heartbeat import TickResult, heartbeat
from maplegotchi.core.interactions import Accepted, InteractionOutcome, apply_interaction
from maplegotchi.core.journal import (
    BrainContext,
    BrainKind,
    JournalEntry,
    Trigger,
    TriggerKind,
    accept_drafts,
)
from maplegotchi.core.memory import (
    Memory,
    MemoryChange,
    MemoryEvent,
    MemoryEventKind,
    MemoryKind,
    MemoryStatus,
    Tier,
    memories_from,
)
from maplegotchi.core.memory import consolidate as consolidate_memories
from maplegotchi.core.memory import search as search_memories
from maplegotchi.core.movement import arrival_actions, settle_movement
from maplegotchi.core.observations import ObservationSnapshot
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.proposal import (
    DecisionContext,
    DirectorLabel,
    build_context,
    decide_with_proposal,
    stale_record,
)
from maplegotchi.core.reflection import (
    JournalParameters,
    ReflectionState,
    heartbeat_triggers,
    interaction_triggers,
    local_time,
    mark_journaled,
    settle_triggers,
)
from maplegotchi.core.rng import RngStream
from maplegotchi.core.state import InteractionKind, MapleState, birth
from maplegotchi.core.tasks import ToolRecord, one_line
from maplegotchi.core.timeline import Born, LifeEvent
from maplegotchi.runtime.clock import Clock
from maplegotchi.runtime.daily import reflect_if_due, todays_intent
from maplegotchi.runtime.journal_composition import JournalComposer
from maplegotchi.runtime.lifecycle import CallGate, admitted
from maplegotchi.runtime.lifecycle import RuntimeClosedError as RuntimeClosedError
from maplegotchi.runtime.tasks import TaskWorker, relevant_memories
from maplegotchi.storage.audit_rows import StoredActionEvent, StoredDecision
from maplegotchi.storage.conversation_rows import MessageRecord, StoredMessage
from maplegotchi.storage.daily_rows import StoredReflection
from maplegotchi.storage.datadir import DataDir
from maplegotchi.storage.db import open_life_database
from maplegotchi.storage.memory_rows import StoredMemoryEvent
from maplegotchi.storage.repositories import (
    LifeRepository,
    PersistedView,
    StoredEvent,
    StoredJournalEntry,
    StoredObservation,
)
from maplegotchi.storage.tool_rows import StoredDocument, StoredToolUse

DEFAULT_NAME = "Maple"
MESSAGE_WINDOW = timedelta(minutes=10)  # repeated messages within this have less effect


def new_life_seed() -> str:
    """A fresh 256-bit life seed. Used exactly once, at birth."""
    return secrets.token_hex(32)


def _written(entries: tuple[JournalEntry, ...]) -> set[tuple[TriggerKind, str]]:
    return {(e.trigger, e.topic) for e in entries}


@dataclass(frozen=True)
class _JournalTransition[T]:
    context: BrainContext
    tick_id: int | None
    reflection: ReflectionState
    finish: Callable[[tuple[JournalEntry, ...], ReflectionState], T]


@dataclass(frozen=True)
class CommittedTick:
    """A heartbeat exactly as committed: its result, revision, and journal entries."""

    result: TickResult
    revision: int
    journal: tuple[JournalEntry, ...]


@dataclass(frozen=True)
class CommittedInteraction:
    """An interaction attempt. `revision` is its own commit if accepted, else unchanged."""

    outcome: InteractionOutcome
    revision: int
    journal: tuple[JournalEntry, ...]


@dataclass(frozen=True)
class CommittedArrival:
    """A walk's arrival recorded between heartbeats: the activity has begun."""

    state: MapleState
    revision: int
    events: tuple[LifeEvent, ...]
    journal: tuple[JournalEntry, ...]


@dataclass(frozen=True)
class CommittedDecision:
    """A decision transition exactly as committed (ADR-0026 §3)."""

    outcome: DecisionOutcome
    revision: int
    journal: tuple[JournalEntry, ...]


@dataclass(frozen=True)
class PendingDecision:
    """A due decision, handed to a Director outside the lock (ADR-0026 §3)."""

    revision: int
    trigger: DecisionTrigger
    inputs: BehaviorInputs
    context: DecisionContext


@dataclass(frozen=True)
class ReceivedMessage:
    """A message from Paolo as committed, with the context for replying (ADR-0032)."""

    message_id: int
    revision: int
    context: ReplyContext
    existing_reply: str | None  # set when this message was already answered (a retry)
    duplicate: bool
    interrupted: bool


@dataclass(frozen=True)
class LifeRecords:
    """Life events from the three stores (ADR-0028 §2), each oldest first."""

    timeline: tuple[StoredEvent, ...]
    actions: tuple[StoredActionEvent, ...]
    decisions: tuple[StoredDecision, ...]
    tools: tuple[StoredToolUse, ...] = ()
    memory: tuple[StoredMemoryEvent, ...] = ()
    reflections: tuple[StoredReflection, ...] = ()
    messages: tuple[StoredMessage, ...] = ()

    def __bool__(self) -> bool:
        return bool(
            self.timeline
            or self.actions
            or self.decisions
            or self.tools
            or self.memory
            or self.reflections
            or self.messages
        )


class ExternalBrainNotAllowed(RuntimeError):
    """The configured Brain is not a supported Maple Brain."""


def require_supported_brain(brain: Brain) -> Brain:
    if brain.kind is BrainKind.RULE:
        if type(brain) is not RuleBrain:
            raise ExternalBrainNotAllowed(
                f"only the built-in RuleBrain may claim kind=rule, got {type(brain).__name__}"
            )
        return brain

    if brain.kind is BrainKind.EXTERNAL:
        return brain

    raise ExternalBrainNotAllowed(f"unsupported Brain kind from {type(brain).__name__}")


class LifeRuntime:
    def __init__(
        self,
        repository: LifeRepository,
        clock: Clock,
        params: CoreParameters,
        *,
        brain: Brain | None = None,
        journal: JournalParameters | None = None,
    ) -> None:
        self._brain = require_supported_brain(brain if brain is not None else RuleBrain())
        self._repo: LifeRepository | None = repository
        self._clock = clock
        self._params = params
        self._journal_params = journal or JournalParameters()
        self._lock = threading.Lock()
        self._calls = CallGate()
        self._composer = JournalComposer(self._brain)
        self._stopping = False
        self._generation = 0
        self._tasks = TaskWorker()
        stored = repository.load()
        self._state = stored.state
        self._revision = stored.revision
        self._reflection = repository.reflection_state()

    @classmethod
    def open(
        cls,
        data_dir: DataDir,
        clock: Clock,
        params: CoreParameters | None = None,
        *,
        name: str = DEFAULT_NAME,
        new_seed: Callable[[], str] = new_life_seed,
        brain: Brain | None = None,
        journal: JournalParameters | None = None,
    ) -> LifeRuntime:
        """Load Maple's life, or give birth once if there is none yet.

        `name` and `new_seed` are used only at birth; an existing Maple keeps its
        own identity and seed.
        """
        require_supported_brain(
            brain if brain is not None else RuleBrain()
        )  # refuse before opening

        def first_life() -> tuple[MapleState, Born]:
            born_at = clock.now()
            state = birth(name=name, born_at=born_at, seed_hex=new_seed())
            return state, Born(at=born_at, name=name)

        repository = LifeRepository(open_life_database(data_dir, first_life, now=clock.now))
        try:
            return cls(repository, clock, params or CoreParameters(), brain=brain, journal=journal)
        except BaseException:
            repository.close()
            raise

    # ------------------------------------------------------------ reads

    @property
    def state(self) -> MapleState:
        """The last committed state (immutable)."""
        return self._state

    @property
    def revision(self) -> int:
        return self._revision

    @admitted
    def current(self) -> tuple[MapleState, int]:
        """State and revision read together, consistent with each other."""
        with self._lock:
            return self._state, self._revision

    @admitted
    def timeline(self, *, limit: int | None = None) -> list[StoredEvent]:
        with self._lock:
            return self._repository().events(limit=limit)

    @admitted
    def birth_record(self) -> Born:
        with self._lock:
            return self._repository().birth()

    @admitted
    def observations(self, *, tick_id: int | None = None) -> list[StoredObservation]:
        with self._lock:
            return self._repository().observations(tick_id=tick_id)

    @admitted
    def journal(self, *, limit: int | None = None) -> list[StoredJournalEntry]:
        with self._lock:
            return self._repository().journal(limit=limit)

    @admitted
    def latest_observations(self) -> list[StoredObservation]:
        """The observations stored with the most recent observed heartbeat."""
        with self._lock:
            repo = self._repository()
            tick = repo.latest_observation_tick()
            return [] if tick is None else repo.observations(tick_id=tick)

    @admitted
    def read_view(self, *, recent: int) -> PersistedView:
        """One coherent committed view (single read transaction; no commit can interleave)."""
        with self._lock:
            return self._repository().read_view(recent=recent)

    @admitted
    def written_at(self, revision: int) -> tuple[list[StoredEvent], list[StoredJournalEntry]]:
        """Timeline events and journal entries committed by exactly this revision."""
        with self._lock:
            repo = self._repository()
            return repo.events(revision=revision), repo.journal(revision=revision)

    @admitted
    def life_written_at(self, revision: int) -> LifeRecords:
        """Every life event (timeline, actions, decisions, tools, memory) of this revision."""
        with self._lock:
            repo = self._repository()
            return LifeRecords(
                tuple(repo.events(revision=revision)),
                tuple(repo.action_events(revision=revision)),
                tuple(repo.decisions(revision=revision)),
                tuple(repo.tool_uses(revision=revision)),
                tuple(repo.memory_events(revision=revision)),
                tuple(repo.reflections(revision=revision)),
                tuple(repo.messages(revision=revision)),
            )

    @admitted
    def life_since(self, revision: int, *, limit: int) -> LifeRecords:
        """Life events committed after `revision`, each store capped at `limit` rows."""
        with self._lock:
            repo = self._repository()
            return LifeRecords(
                tuple(repo.events_since(revision, limit=limit)),
                tuple(repo.action_events(since_revision=revision, limit=limit)),
                tuple(repo.decisions(since_revision=revision, limit=limit)),
                tuple(repo.tool_uses(since_revision=revision, limit=limit)),
                tuple(repo.memory_events(since_revision=revision, limit=limit)),
                tuple(repo.reflections(since_revision=revision, limit=limit)),
                tuple(repo.messages(since_revision=revision, limit=limit)),
            )

    @admitted
    def documents(self, *, limit: int) -> list[StoredDocument]:
        with self._lock:
            return self._repository().documents(limit=limit)

    @admitted
    def document(self, document_id: int) -> StoredDocument | None:
        with self._lock:
            return self._repository().document(document_id)

    @admitted
    def tool_uses(self, *, limit: int) -> list[StoredToolUse]:
        with self._lock:
            return self._repository().tool_uses(limit=limit)

    @admitted
    def decisions(self, *, limit: int) -> list[StoredDecision]:
        with self._lock:
            return self._repository().decisions(limit=limit)

    @property
    def reflection_state(self) -> ReflectionState:
        return self._reflection

    @property
    def brain(self) -> Brain:
        """The Brain that writes this life's journal (always the built-in RuleBrain in v0.1)."""
        return self._brain

    def heartbeat_due(self) -> bool:
        """Whether a heartbeat would run now. Lets callers observe only when it will be used."""
        state = self._state
        now = self._clock.now()
        return now >= state.last_tick_at + self._params.heartbeat_interval and (
            now >= state.last_updated_at
        )

    def arrival_due(self) -> bool:
        """Whether a walk has reached its destination and is not yet recorded."""
        route = self._state.route
        return route is not None and self._clock.now() >= route.arrives_at

    def decision_is_due(self) -> bool:
        """Whether a decision transition would run now."""
        state = self._state
        now = self._clock.now()
        return now >= state.last_updated_at and decision_due(state, now) is not None

    @admitted
    def pending_decision(self) -> PendingDecision | None:
        """The context for a due decision, or None. Reads only; commits nothing."""
        attention = self._latest_attention()
        inputs = BehaviorInputs(server_attention=attention.level)
        with self._lock:
            repo = self._repository()
            now = max(self._clock.now(), self._state.last_updated_at)
            trigger = decision_due(self._state, now)
            if trigger is None:
                return None
            prepared = prepare(self._state, now, trigger, self._params)
            recent = [d.record for d in repo.decisions(limit=3)]
            memories = relevant_memories(repo, prepared.state, now)
            intent = todays_intent(repo, now, self._params.utc_offset)
            context = build_context(
                prepared,
                now,
                trigger,
                inputs,
                self._params,
                server_reasons=attention.reasons,
                recent=recent,
                catalog=self._tasks.catalog(repo),
                memories=memories,
                intent=(intent.intent_type, intent.intent_summary) if intent else None,
            )
            return PendingDecision(self._revision, trigger, inputs, context)

    def decide_proposal_committed(
        self,
        pending: PendingDecision,
        *,
        director: DirectorLabel,
        raw: object = None,
        failure: RejectionCode | None = None,
        latency_ms: int | None = None,
    ) -> CommittedDecision | None:
        """Apply a Director's answer: re-validated against the state as it is NOW.

        If the decision stopped being due while the Director was thinking (a
        heartbeat or an interruption handled it), the proposal is recorded as
        stale and nothing else changes. Returns None only if there was no answer
        and nothing is due any more.
        """

        def build() -> _JournalTransition[CommittedDecision | None] | CommittedDecision | None:
            repo = self._repository()
            now = max(self._clock.now(), self._state.last_updated_at)
            trigger = decision_due(self._state, now)
            if trigger is None:
                if failure is not None:
                    return None
                record = stale_record(
                    self._state,
                    now,
                    pending.inputs,
                    self._params,
                    director=director,
                    raw=raw,
                    latency_ms=latency_ms,
                )
                with self._calls.commit():
                    revision = repo.commit(
                        self._state,
                        expected_revision=self._revision,
                        events=(),
                        decisions=(record,),
                    )
                self._revision = revision
                return None
            intent = todays_intent(repo, now, self._params.utc_offset)
            outcome = decide_with_proposal(
                self._state,
                now,
                trigger,
                pending.inputs,
                self._params,
                director=director,
                raw=raw,
                failure=failure,
                latency_ms=latency_ms,
                catalog=self._tasks.catalog(repo),  # as it is now, not when asked
                intent=intent.intent_type if intent else None,
            )
            return self._prepare_decision(repo, outcome, now)

        return self._run_transition(build)

    def _latest_attention(self) -> ServerAttention:
        latest = self.latest_observations()
        if not latest:
            return assess_server_attention(None)
        observed_at = max(s.observation.observed_at for s in latest)
        snapshot = ObservationSnapshot(observed_at, tuple(s.observation for s in latest))
        return assess_server_attention(snapshot)

    def _memory_changes(
        self,
        repo: LifeRepository,
        events: Sequence[LifeEvent],
        tools: Sequence[ToolRecord],
        now: datetime,
        *,
        consolidate: bool = False,
    ) -> tuple[MemoryChange, ...]:
        """New memories from this transition, and (on heartbeats) consolidation (ADR-0030)."""
        created = tuple(
            MemoryChange(m, MemoryEvent(MemoryEventKind.CREATED, now))
            for m in memories_from(events, tools, now, self._params.utc_offset)
        )
        if not consolidate:
            return created
        short = repo.memories(tiers=(Tier.SHORT_TERM,), limit=1000)
        return created + consolidate_memories(short, now)

    @admitted
    def memories(self, *, tiers: Sequence[Tier] | None = None, limit: int) -> list[Memory]:
        with self._lock:
            return self._repository().memories(tiers=tiers, limit=limit)

    @admitted
    def receive_message_committed(self, message: IncomingMessage) -> ReceivedMessage:
        """Record a message from Paolo and apply its effects; idempotent by message id."""
        with self._lock:
            self._require_running()
            repo = self._repository()
            now = max(self._clock.now(), self._state.last_updated_at)
            existing = repo.message_by_external_id(message.channel, message.external_id)
            if existing is not None:
                answered = repo.reply_to(existing.id)
                context = self._reply_context(repo, self._state, now, message)
                return ReceivedMessage(
                    existing.id,
                    self._revision,
                    context,
                    answered.text if answered else None,
                    duplicate=True,
                    interrupted=False,
                )
            audit = arrival_actions(self._state, now)
            settled, arrival = settle_movement(self._state, now)
            counter = settled.rng.interaction_counter + 1
            rng = RngStream(settled.rng.seed_hex, "interaction", counter)
            recent = repo.recent_incoming(now - MESSAGE_WINDOW)
            outcome = receive_message(settled, now, recent, rng)
            state = replace(
                outcome.state, rng=replace(outcome.state.rng, interaction_counter=counter)
            )
            remembered = (
                MemoryChange(
                    Memory(
                        kind=MemoryKind.CONVERSATION,
                        tier=Tier.SHORT_TERM,
                        status=MemoryStatus.ACTIVE,
                        text=one_line(f"Paolo wrote to me: {message.text}", 240),
                        created_at=now,
                        last_seen_at=now,
                        key=f"conversation:{message.channel.value}:{message.external_id}",
                        source=f"{message.channel.value}:{message.external_id}",
                        importance=0.6,
                    ),
                    MemoryEvent(MemoryEventKind.CREATED, now),
                ),
            )
            with self._calls.commit():
                revision = repo.commit(
                    state,
                    expected_revision=self._revision,
                    events=(*arrival, *outcome.events),
                    actions=(*audit, *outcome.actions),
                    memories=remembered,
                    message=MessageRecord(
                        at=now,
                        channel=message.channel,
                        speaker=message.speaker,
                        text=message.text,
                        external_id=message.external_id,
                    ),
                )
            self._state, self._revision = state, revision
            message_id = repo.last_message_id
            if message_id is None:  # pragma: no cover - the commit wrote it
                raise RuntimeError("message row id missing")
            context = self._reply_context(repo, state, now, message)
            return ReceivedMessage(
                message_id, revision, context, None, duplicate=False,
                interrupted=outcome.interrupted,
            )  # fmt: skip

    @admitted
    def record_reply_committed(
        self,
        message_id: int,
        text: str,
        *,
        replier_kind: str,
        replier_name: str,
        fallback_code: str | None,
        latency_ms: int | None = None,
    ) -> int:
        """Store Maple's reply to a message; changes no state. Returns the revision."""
        with self._lock:
            self._require_running()
            repo = self._repository()
            now = max(self._clock.now(), self._state.last_updated_at)
            with self._calls.commit():
                revision = repo.commit(
                    self._state,
                    expected_revision=self._revision,
                    events=(),
                    message=MessageRecord(
                        at=now,
                        channel=Channel.DISCORD,
                        speaker=Speaker.MAPLE,
                        text=text,
                        reply_to=message_id,
                        replier_kind=replier_kind,
                        replier_name=replier_name,
                        fallback_code=fallback_code,
                        latency_ms=latency_ms,
                    ),
                )
            self._revision = revision
            return revision

    def _reply_context(
        self, repo: LifeRepository, state: MapleState, now: datetime, message: IncomingMessage
    ) -> ReplyContext:
        server = self._server_line(repo) or "I have no observations of the server yet"
        return build_reply_context(
            state,
            now,
            message,
            utc_offset=self._params.utc_offset,
            expression=state.expression_at(max(now, state.last_updated_at)).value,
            server_summary=server,
            memories=[m.text for m in relevant_memories(repo, state, now)],
            conversation=[(m.speaker.value, m.text) for m in repo.messages(limit=6)],
        )

    @admitted
    def brain_call_stats(self) -> tuple[MapleDay, CallStats, CallStats]:
        """Today's Maple day and the stored Director and Replier call stats (ADR-0034).

        Reads only; nothing here calls a Brain or the companion.
        """
        today = maple_today(self._clock.now(), self._params.utc_offset)
        with self._lock:
            repo = self._repository()
            director = repo.director_call_stats(today.start, today.end)
            replier = repo.replier_call_stats(today.start, today.end)
        return today, director, replier

    @admitted
    def messages(self, *, limit: int) -> list[StoredMessage]:
        with self._lock:
            return self._repository().messages(limit=limit)

    @admitted
    def reflections(self, *, limit: int) -> list[StoredReflection]:
        with self._lock:
            return self._repository().reflections(limit=limit)

    @admitted
    def memory_search(self, text: str, *, limit: int) -> tuple[Memory, ...]:
        with self._lock:
            everything = self._repository().memories(limit=5000)
        return search_memories(everything, text, limit)

    @staticmethod
    def _server_line(repo: LifeRepository) -> str | None:
        """One factual line about the server for documents (lock held by the caller)."""
        tick = repo.latest_observation_tick()
        if tick is None:
            return None
        stored = repo.observations(tick_id=tick)
        snapshot = ObservationSnapshot(
            max(s.observation.observed_at for s in stored), tuple(s.observation for s in stored)
        )
        attention = assess_server_attention(snapshot)
        if not attention.reasons:
            return "nothing notable in the latest observations"
        return "noticed " + ", ".join(attention.reasons[:3])

    @admitted
    def latest_inputs(self) -> BehaviorInputs:
        """Behavior inputs from the most recent stored observations (facts only)."""
        latest = self.latest_observations()
        if not latest:
            return BehaviorInputs()
        observed_at = max(s.observation.observed_at for s in latest)
        return behavior_inputs(
            ObservationSnapshot(observed_at, tuple(s.observation for s in latest))
        )

    # ------------------------------------------------------------ transitions

    def decide_committed(self, inputs: BehaviorInputs | None = None) -> CommittedDecision | None:
        """Choose and begin Maple's next goal/action if a decision is due (rule direction)."""
        inputs = inputs if inputs is not None else self.latest_inputs()

        def build() -> _JournalTransition[CommittedDecision | None] | CommittedDecision | None:
            repo = self._repository()
            now = max(self._clock.now(), self._state.last_updated_at)
            trigger = decision_due(self._state, now)
            if trigger is None:
                return None
            intent = todays_intent(repo, now, self._params.utc_offset)
            outcome = decide(
                self._state,
                now,
                trigger,
                inputs,
                self._params,
                catalog=self._tasks.catalog(repo),
                intent=intent.intent_type if intent else None,
            )
            return self._prepare_decision(repo, outcome, now)

        return self._run_transition(build)

    def _prepare_decision(
        self, repo: LifeRepository, outcome: DecisionOutcome, now: datetime
    ) -> _JournalTransition[CommittedDecision]:
        """Prepare a decision with journal context; the caller owns the lock."""
        if outcome.record is None:  # pragma: no cover - every decision is recorded
            raise RuntimeError("decision without an audit record")
        record = outcome.record
        triggers, reflection = settle_triggers(
            self._reflection,
            events=outcome.events,
            now=now,
            params=self._params,
            journal=self._journal_params,
        )

        def finish(
            entries: tuple[JournalEntry, ...], reflection: ReflectionState
        ) -> CommittedDecision:
            tools = self._tasks.effects(
                repo, self._state, outcome.state, now, server_line=self._server_line(repo)
            )
            remembered = self._memory_changes(repo, outcome.events, tools, now)
            daily = reflect_if_due(repo, self._state, outcome.state, now, self._params.utc_offset)
            if daily is not None:
                remembered += daily.memory_changes
            with self._calls.commit():
                revision = repo.commit(
                    outcome.state,
                    expected_revision=self._revision,
                    events=outcome.events,
                    journal=entries,
                    reflection=reflection,
                    actions=outcome.actions,
                    decisions=(record,),
                    tools=tools,
                    memories=remembered,
                    daily=daily.reflection if daily else None,
                )
            self._state, self._revision, self._reflection = outcome.state, revision, reflection
            return CommittedDecision(outcome, revision, entries)

        return self._pending(triggers, outcome.state, now, None, None, reflection, finish)

    def settle_committed(self) -> CommittedArrival | None:
        """Record an arrival that has happened (ADR-0027 §5): the activity begins.

        Uses no randomness and no Brain decisions; only the journal wording of a
        newly begun notable activity, exactly as a heartbeat would.
        """

        def build() -> _JournalTransition[CommittedArrival | None] | CommittedArrival | None:
            repo = self._repository()
            now = max(self._clock.now(), self._state.last_updated_at)
            arrived = arrival_actions(self._state, now)
            settled, events = settle_movement(self._state, now)
            if settled is self._state:
                return None
            triggers, reflection = settle_triggers(
                self._reflection,
                events=events,
                now=now,
                params=self._params,
                journal=self._journal_params,
            )

            def finish(
                entries: tuple[JournalEntry, ...], reflection: ReflectionState
            ) -> CommittedArrival:
                with self._calls.commit():
                    revision = repo.commit(
                        settled,
                        expected_revision=self._revision,
                        events=events,
                        journal=entries,
                        reflection=reflection,
                        actions=arrived,
                    )
                self._state, self._revision, self._reflection = settled, revision, reflection
                return CommittedArrival(settled, revision, events, entries)

            return self._pending(triggers, settled, now, None, None, reflection, finish)

        return self._run_transition(build)

    def heartbeat_if_due(
        self, observations: ObservationSnapshot | None = None
    ) -> TickResult | None:
        committed = self.heartbeat_committed(observations)
        return committed.result if committed is not None else None

    def heartbeat_committed(
        self, observations: ObservationSnapshot | None = None
    ) -> CommittedTick | None:
        """Run one heartbeat at the current time if the interval has elapsed.

        `observations` (taken just before, outside the lock) feed server_attention
        and are stored with this heartbeat in the same transaction. After
        downtime this is a single heartbeat: core applies bounded catch-up and
        records the gap, rather than replaying every missed tick.
        """

        def build() -> _JournalTransition[CommittedTick | None] | CommittedTick | None:
            repo = self._repository()
            now = self._clock.now()
            state = self._state
            due = state.last_tick_at + self._params.heartbeat_interval
            if now < due or now < state.last_updated_at:
                return None
            if observations is not None and observations.observed_at > now:
                raise ValueError("observations cannot come from the future")
            result = heartbeat(state, now, behavior_inputs(observations), self._params)
            triggers, reflection = heartbeat_triggers(
                self._reflection,
                previous=state,
                result=result,
                snapshot=observations,
                now=now,
                params=self._params,
                journal=self._journal_params,
            )

            def finish(
                entries: tuple[JournalEntry, ...], reflection: ReflectionState
            ) -> CommittedTick:
                tools = self._tasks.effects(
                    repo, state, result.state, now, server_line=self._server_line(repo)
                )
                remembered = self._memory_changes(repo, result.events, tools, now, consolidate=True)
                daily = reflect_if_due(repo, state, result.state, now, self._params.utc_offset)
                if daily is not None:
                    remembered += daily.memory_changes
                with self._calls.commit():
                    revision = repo.commit(
                        result.state,
                        expected_revision=self._revision,
                        events=result.events,
                        tick_id=result.tick_id,
                        observations=observations.observations if observations else (),
                        journal=entries,
                        reflection=reflection,
                        actions=result.actions,
                        decisions=(result.decision,) if result.decision else (),
                        tools=tools,
                        memories=remembered,
                        daily=daily.reflection if daily else None,
                    )
                self._state, self._revision, self._reflection = result.state, revision, reflection
                return CommittedTick(result, revision, entries)

            return self._pending(
                triggers, result.state, now, observations, result.tick_id, reflection, finish
            )

        return self._run_transition(build)

    def interact(self, kind: InteractionKind) -> InteractionOutcome:
        """Apply Greet or Pet now. Rejections change nothing and are not persisted."""
        return self.interact_committed(kind).outcome

    def interact_committed(self, kind: InteractionKind) -> CommittedInteraction:
        def build() -> _JournalTransition[CommittedInteraction] | CommittedInteraction:
            repo = self._repository()
            # If the wall clock stepped backwards, act at the latest known time
            # rather than before it; core forbids going back in time.
            now = max(self._clock.now(), self._state.last_updated_at)
            # A finished walk is recorded first, so drowsiness reflects arrival in bed.
            audit = arrival_actions(self._state, now)
            settled, arrival = settle_movement(self._state, now)
            outcome = apply_interaction(settled, kind, now, self._params)
            if isinstance(outcome, Accepted):
                arrived, reflection = settle_triggers(
                    self._reflection,
                    events=arrival,
                    now=now,
                    params=self._params,
                    journal=self._journal_params,
                )
                interacted, reflection = interaction_triggers(
                    reflection,
                    accepted=outcome,
                    now=now,
                    params=self._params,
                    journal=self._journal_params,
                )
                triggers = arrived + interacted

                def finish(
                    entries: tuple[JournalEntry, ...], reflection: ReflectionState
                ) -> CommittedInteraction:
                    with self._calls.commit():
                        revision = repo.commit(
                            outcome.state,
                            expected_revision=self._revision,
                            events=(*arrival, outcome.event),
                            journal=entries,
                            reflection=reflection,
                            actions=audit,
                            memories=self._memory_changes(repo, (*arrival, outcome.event), (), now),
                        )
                    self._state, self._revision, self._reflection = (
                        outcome.state,
                        revision,
                        reflection,
                    )
                    return CommittedInteraction(outcome, revision, entries)

                return self._pending(triggers, outcome.state, now, None, None, reflection, finish)
            return CommittedInteraction(outcome, self._revision, ())

        return self._run_transition(build)

    def _pending[T](
        self,
        triggers: tuple[Trigger, ...],
        state: MapleState,
        now: datetime,
        snapshot: ObservationSnapshot | None,
        tick_id: int | None,
        reflection: ReflectionState,
        finish: Callable[[tuple[JournalEntry, ...], ReflectionState], T],
    ) -> _JournalTransition[T]:
        local = local_time(now, self._params)
        context = BrainContext(
            now=now,
            local_hour=local.hour + local.minute / 60,
            owner_name=self._journal_params.owner_name,
            state=state,
            expression=state.expression_at(now),
            snapshot=snapshot,
            triggers=triggers,
        )
        return _JournalTransition(context, tick_id, reflection, finish)

    def _run_transition[T](self, build: Callable[[], _JournalTransition[T] | T]) -> T:
        with self._calls.enter():
            with self._lock:
                self._require_running()
                prepared = build()
                if not isinstance(prepared, _JournalTransition):
                    return prepared
                prepared = cast(_JournalTransition[T], prepared)
                if not prepared.context.triggers:
                    return self._finish(prepared, ())
                if self._brain.kind is BrainKind.RULE:
                    try:
                        drafts = self._brain.compose_journal(prepared.context)
                    except Exception:
                        drafts = ()
                    return self._finish(prepared, drafts)
                revision, generation = self._revision, self._generation
            # No writer lock or SQLite transaction is held during external I/O.
            drafts = self._composer.compose(prepared.context)
            with self._lock:
                self._require_running()
                if generation != self._generation:
                    raise RuntimeClosedError("journal preparation invalidated")
                if revision != self._revision:
                    # Recompute from current state. Never reuse stale drafts/RNG
                    # outcomes, and never issue another request in this invocation.
                    prepared = build()
                    drafts = ()
                    if not isinstance(prepared, _JournalTransition):
                        return prepared
                return self._finish(cast(_JournalTransition[T], prepared), drafts)

    def _finish[T](self, prepared: _JournalTransition[T], drafts: Sequence[object]) -> T:
        entries = accept_drafts(
            prepared.context,
            drafts,
            brain_kind=self._brain.kind,
            brain_name=self._brain.name,
            brain_version=self._brain.version,
            tick_id=prepared.tick_id,
        )
        reflection = mark_journaled(
            prepared.reflection, prepared.context.triggers, _written(entries), prepared.context.now
        )
        return prepared.finish(entries, reflection)

    def _require_running(self) -> None:
        if self._stopping or self._calls.stopping:
            raise RuntimeClosedError("life runtime is shutting down")
        self._repository()

    # ------------------------------------------------------------ lifecycle

    def _repository(self) -> LifeRepository:
        if self._repo is None:
            raise RuntimeClosedError("life runtime is closed")
        return self._repo

    def begin_shutdown(self) -> None:
        self._calls.stop()
        with self._lock:
            if not self._stopping:
                self._stopping = True
                self._generation += 1
        self._composer.stop()

    def close(self) -> None:
        self.begin_shutdown()
        self._calls.drain()
        with self._lock:
            if self._repo is not None:
                self._repo.close()
                self._repo = None

    def __enter__(self) -> LifeRuntime:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
