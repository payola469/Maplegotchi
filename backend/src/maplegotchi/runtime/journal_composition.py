"""One outstanding, storage-free external journal request per runtime.

The deadline bounds caller waiting, not worker termination or process shutdown.
Expired requests retain the slot until the daemon finishes resource cleanup.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from maplegotchi.brain.interface import Brain
from maplegotchi.core.journal import BrainContext, JournalDraft


@dataclass
class _Attempt:
    deadline: float
    done: bool = False
    drafts: Sequence[JournalDraft] = field(default_factory=tuple)


class JournalComposer:
    def __init__(
        self,
        brain: Brain,
        *,
        timeout: float = 30.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._brain = brain
        self._timeout = timeout
        self._monotonic = monotonic
        self._condition = threading.Condition()
        self._attempt: _Attempt | None = None
        self._stopping = False

    def compose(self, context: BrainContext) -> Sequence[JournalDraft]:
        with self._condition:
            if self._stopping or self._attempt is not None:
                return ()
            attempt = _Attempt(self._monotonic() + self._timeout)
            self._attempt = attempt
            # The target captures the Brain and immutable context, never a runtime
            # or repository. Coordination contains no storage/commit capability.
            try:
                worker = threading.Thread(
                    target=self._compose,
                    args=(self._brain, context, attempt),
                    name="maple-journal",
                    daemon=True,
                )
                worker.start()
            except Exception:
                self._attempt = None
                return ()
            while not self._is_stopping():
                remaining = attempt.deadline - self._monotonic()
                if remaining <= 0:
                    return ()
                if attempt.done:
                    return attempt.drafts
                self._condition.wait(remaining)
            return ()

    def _compose(self, brain: Brain, context: BrainContext, attempt: _Attempt) -> None:
        drafts: Sequence[JournalDraft] = ()
        try:
            drafts = tuple(brain.compose_journal(context))
        except Exception:
            drafts = ()  # failure costs wording, never a life transition
        finally:
            # compose_journal must close its transport before returning/raising.
            with self._condition:
                if not self._stopping and self._monotonic() < attempt.deadline:
                    attempt.drafts = drafts
                attempt.done = True
                self._attempt = None
                self._condition.notify_all()

    def _is_stopping(self) -> bool:
        return self._stopping

    def stop(self) -> None:
        with self._condition:
            self._stopping = True
            self._condition.notify_all()
