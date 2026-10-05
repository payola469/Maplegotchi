"""The single-writer life runtime.

Every change to Maple's life (heartbeats and Greet/Pet) goes through one lock,
reads the clock inside it, computes the transition with pure core, commits it
in one transaction, and only then adopts the new state in memory. A failed
commit leaves both the database and the in-memory state at the last committed
revision, so nothing is lost or half-applied.

Journal entries are part of the same transition: core detects triggers, the
Brain words them, core validates the drafts, and the entries, the journal
state, and the transition commit together. v0.1 accepts only the built-in
RuleBrain; any other Brain is refused (D6, D10).
"""

from __future__ import annotations

import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType

from maplegotchi.brain.interface import Brain
from maplegotchi.brain.rule_brain import RuleBrain
from maplegotchi.core.attention import ServerAttention, assess_server_attention, behavior_inputs
from maplegotchi.core.behavior import BehaviorInputs
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
from maplegotchi.core.state import InteractionKind, MapleState, birth
from maplegotchi.core.timeline import Born, LifeEvent
from maplegotchi.runtime.clock import Clock
from maplegotchi.storage.audit_rows import StoredActionEvent, StoredDecision
from maplegotchi.storage.datadir import DataDir
from maplegotchi.storage.db import open_life_database
from maplegotchi.storage.repositories import (
    LifeRepository,
    PersistedView,
    StoredEvent,
    StoredJournalEntry,
    StoredObservation,
)

DEFAULT_NAME = "Maple"


def new_life_seed() -> str:
    """A fresh 256-bit life seed. Used exactly once, at birth."""
    return secrets.token_hex(32)


def _written(entries: tuple[JournalEntry, ...]) -> set[tuple[TriggerKind, str]]:
    return {(e.trigger, e.topic) for e in entries}


class RuntimeClosedError(RuntimeError):
    pass


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
class LifeRecords:
    """Life events from the three stores (ADR-0028 §2), each oldest first."""

    timeline: tuple[StoredEvent, ...]
    actions: tuple[StoredActionEvent, ...]
    decisions: tuple[StoredDecision, ...]

    def __bool__(self) -> bool:
        return bool(self.timeline or self.actions or self.decisions)


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

    def current(self) -> tuple[MapleState, int]:
        """State and revision read together, consistent with each other."""
        with self._lock:
            return self._state, self._revision

    def timeline(self, *, limit: int | None = None) -> list[StoredEvent]:
        with self._lock:
            return self._repository().events(limit=limit)

    def birth_record(self) -> Born:
        with self._lock:
            return self._repository().birth()

    def observations(self, *, tick_id: int | None = None) -> list[StoredObservation]:
        with self._lock:
            return self._repository().observations(tick_id=tick_id)

    def journal(self, *, limit: int | None = None) -> list[StoredJournalEntry]:
        with self._lock:
            return self._repository().journal(limit=limit)

    def latest_observations(self) -> list[StoredObservation]:
        """The observations stored with the most recent observed heartbeat."""
        with self._lock:
            repo = self._repository()
            tick = repo.latest_observation_tick()
            return [] if tick is None else repo.observations(tick_id=tick)

    def read_view(self, *, recent: int) -> PersistedView:
        """One coherent committed view (single read transaction; no commit can interleave)."""
        with self._lock:
            return self._repository().read_view(recent=recent)

    def written_at(self, revision: int) -> tuple[list[StoredEvent], list[StoredJournalEntry]]:
        """Timeline events and journal entries committed by exactly this revision."""
        with self._lock:
            repo = self._repository()
            return repo.events(revision=revision), repo.journal(revision=revision)

    def life_written_at(self, revision: int) -> LifeRecords:
        """Every life event (timeline, action lifecycle, decisions) of exactly this revision."""
        with self._lock:
            repo = self._repository()
            return LifeRecords(
                tuple(repo.events(revision=revision)),
                tuple(repo.action_events(revision=revision)),
                tuple(repo.decisions(revision=revision)),
            )

    def life_since(self, revision: int, *, limit: int) -> LifeRecords:
        """Life events committed after `revision`, each store capped at `limit` rows."""
        with self._lock:
            repo = self._repository()
            return LifeRecords(
                tuple(repo.events_since(revision, limit=limit)),
                tuple(repo.action_events(since_revision=revision, limit=limit)),
                tuple(repo.decisions(since_revision=revision, limit=limit)),
            )

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
            context = build_context(
                prepared,
                now,
                trigger,
                inputs,
                self._params,
                server_reasons=attention.reasons,
                recent=recent,
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
        with self._lock:
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
                revision = repo.commit(
                    self._state, expected_revision=self._revision, events=(), decisions=(record,)
                )
                self._revision = revision
                return None
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
            )
            return self._commit_decision(repo, outcome, now)

    def _latest_attention(self) -> ServerAttention:
        latest = self.latest_observations()
        if not latest:
            return assess_server_attention(None)
        observed_at = max(s.observation.observed_at for s in latest)
        snapshot = ObservationSnapshot(observed_at, tuple(s.observation for s in latest))
        return assess_server_attention(snapshot)

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
        with self._lock:
            repo = self._repository()
            now = max(self._clock.now(), self._state.last_updated_at)
            trigger = decision_due(self._state, now)
            if trigger is None:
                return None
            outcome = decide(self._state, now, trigger, inputs, self._params)
            return self._commit_decision(repo, outcome, now)

    def _commit_decision(
        self, repo: LifeRepository, outcome: DecisionOutcome, now: datetime
    ) -> CommittedDecision:
        """Commit a decision with its journal, actions and audit row (lock held)."""
        if outcome.record is None:  # pragma: no cover - every decision is recorded
            raise RuntimeError("decision without an audit record")
        triggers, reflection = settle_triggers(
            self._reflection,
            events=outcome.events,
            now=now,
            params=self._params,
            journal=self._journal_params,
        )
        entries = self._write_journal(triggers, outcome.state, now, None, tick_id=None)
        reflection = mark_journaled(reflection, triggers, _written(entries), now)
        revision = repo.commit(
            outcome.state,
            expected_revision=self._revision,
            events=outcome.events,
            journal=entries,
            reflection=reflection,
            actions=outcome.actions,
            decisions=(outcome.record,),
        )
        self._state, self._revision, self._reflection = outcome.state, revision, reflection
        return CommittedDecision(outcome, revision, entries)

    def settle_committed(self) -> CommittedArrival | None:
        """Record an arrival that has happened (ADR-0027 §5): the activity begins.

        Uses no randomness and no Brain decisions; only the journal wording of a
        newly begun notable activity, exactly as a heartbeat would.
        """
        with self._lock:
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
            entries = self._write_journal(triggers, settled, now, None, tick_id=None)
            reflection = mark_journaled(reflection, triggers, _written(entries), now)
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
        with self._lock:
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
            entries = self._write_journal(
                triggers, result.state, now, observations, tick_id=result.tick_id
            )
            reflection = mark_journaled(reflection, triggers, _written(entries), now)
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
            )
            self._state, self._revision, self._reflection = result.state, revision, reflection
            return CommittedTick(result, revision, entries)

    def interact(self, kind: InteractionKind) -> InteractionOutcome:
        """Apply Greet or Pet now. Rejections change nothing and are not persisted."""
        return self.interact_committed(kind).outcome

    def interact_committed(self, kind: InteractionKind) -> CommittedInteraction:
        with self._lock:
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
                entries = self._write_journal(triggers, outcome.state, now, None, tick_id=None)
                reflection = mark_journaled(reflection, triggers, _written(entries), now)
                revision = repo.commit(
                    outcome.state,
                    expected_revision=self._revision,
                    events=(*arrival, outcome.event),
                    journal=entries,
                    reflection=reflection,
                    actions=audit,
                )
                self._state, self._revision, self._reflection = outcome.state, revision, reflection
                return CommittedInteraction(outcome, revision, entries)
            return CommittedInteraction(outcome, self._revision, ())

    def _write_journal(
        self,
        triggers: tuple[Trigger, ...],
        state: MapleState,
        now: datetime,
        snapshot: ObservationSnapshot | None,
        *,
        tick_id: int | None,
    ) -> tuple[JournalEntry, ...]:
        """Ask the Brain to word the triggers, then keep only validated entries."""
        if not triggers:
            return ()
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
        try:
            drafts = self._brain.compose_journal(context)
        except Exception:  # a failing Brain costs the words, never the transition;
            return ()  # nothing is marked as journaled, so the triggers recur
        return accept_drafts(
            context,
            drafts,
            brain_kind=self._brain.kind,
            brain_name=self._brain.name,
            brain_version=self._brain.version,
            tick_id=tick_id,
        )

    # ------------------------------------------------------------ lifecycle

    def _repository(self) -> LifeRepository:
        if self._repo is None:
            raise RuntimeClosedError("life runtime is closed")
        return self._repo

    def close(self) -> None:
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
