"""The single-writer life runtime.

Every change to Maple's life (heartbeats and Greet/Pet) goes through one lock,
reads the clock inside it, computes the transition with pure core, commits it
in one transaction, and only then adopts the new state in memory. A failed
commit leaves both the database and the in-memory state at the last committed
revision, so nothing is lost or half-applied.
"""

from __future__ import annotations

import secrets
import threading
from collections.abc import Callable
from types import TracebackType

from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.heartbeat import TickResult, heartbeat
from maplegotchi.core.interactions import Accepted, InteractionOutcome, apply_interaction
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.state import InteractionKind, MapleState, birth
from maplegotchi.core.timeline import Born
from maplegotchi.runtime.clock import Clock
from maplegotchi.storage.datadir import DataDir
from maplegotchi.storage.db import open_life_database
from maplegotchi.storage.repositories import LifeRepository, StoredEvent

DEFAULT_NAME = "Maple"


def new_life_seed() -> str:
    """A fresh 256-bit life seed. Used exactly once, at birth."""
    return secrets.token_hex(32)


class RuntimeClosedError(RuntimeError):
    pass


class LifeRuntime:
    def __init__(
        self,
        repository: LifeRepository,
        clock: Clock,
        params: CoreParameters,
    ) -> None:
        self._repo: LifeRepository | None = repository
        self._clock = clock
        self._params = params
        self._lock = threading.Lock()
        stored = repository.load()
        self._state = stored.state
        self._revision = stored.revision

    @classmethod
    def open(
        cls,
        data_dir: DataDir,
        clock: Clock,
        params: CoreParameters | None = None,
        *,
        name: str = DEFAULT_NAME,
        new_seed: Callable[[], str] = new_life_seed,
    ) -> LifeRuntime:
        """Load Maple's life, or give birth once if there is none yet.

        `name` and `new_seed` are used only at birth; an existing Maple keeps its
        own identity and seed.
        """

        def first_life() -> tuple[MapleState, Born]:
            born_at = clock.now()
            state = birth(name=name, born_at=born_at, seed_hex=new_seed())
            return state, Born(at=born_at, name=name)

        repository = LifeRepository(open_life_database(data_dir, first_life))
        try:
            return cls(repository, clock, params or CoreParameters())
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

    def timeline(self) -> list[StoredEvent]:
        with self._lock:
            return self._repository().events()

    def birth_record(self) -> Born:
        with self._lock:
            return self._repository().birth()

    # ------------------------------------------------------------ transitions

    def heartbeat_if_due(self, inputs: BehaviorInputs | None = None) -> TickResult | None:
        """Run one heartbeat at the current time if the interval has elapsed.

        After downtime this is a single heartbeat: core applies bounded
        catch-up and records the gap, rather than replaying every missed tick.
        """
        with self._lock:
            repo = self._repository()
            now = self._clock.now()
            state = self._state
            due = state.last_tick_at + self._params.heartbeat_interval
            if now < due or now < state.last_updated_at:
                return None
            result = heartbeat(state, now, inputs or BehaviorInputs(), self._params)
            revision = repo.commit(
                result.state,
                expected_revision=self._revision,
                events=result.events,
                tick_id=result.tick_id,
            )
            self._state, self._revision = result.state, revision
            return result

    def interact(self, kind: InteractionKind) -> InteractionOutcome:
        """Apply Greet or Pet now. Rejections change nothing and are not persisted."""
        with self._lock:
            repo = self._repository()
            # If the wall clock stepped backwards, act at the latest known time
            # rather than before it; core forbids going back in time.
            now = max(self._clock.now(), self._state.last_updated_at)
            outcome = apply_interaction(self._state, kind, now, self._params)
            if isinstance(outcome, Accepted):
                revision = repo.commit(
                    outcome.state, expected_revision=self._revision, events=(outcome.event,)
                )
                self._state, self._revision = outcome.state, revision
            return outcome

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
