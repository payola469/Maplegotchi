"""Admission and draining of complete service operations, including final reads."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from typing import Protocol, cast


class RuntimeClosedError(RuntimeError):
    """The life runtime is closed or shutting down."""


class CallGate:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._local = threading.local()
        self._active = 0
        self._stopping = False

    @contextmanager
    def enter(self) -> Iterator[None]:
        with self._condition:
            depth = getattr(self._local, "depth", 0)
            if not depth:
                if self._stopping:
                    raise RuntimeClosedError("service is shutting down")
                self._active += 1
            self._local.depth = depth + 1
        try:
            yield
        finally:
            with self._condition:
                self._local.depth -= 1
                if not self._local.depth:
                    self._active -= 1
                    self._condition.notify_all()

    def stop(self) -> None:
        with self._condition:
            self._stopping = True

    @property
    def stopping(self) -> bool:
        with self._condition:
            return self._stopping

    def drain(self) -> None:
        with self._condition:
            if getattr(self._local, "depth", 0):
                raise RuntimeError("cannot close from an admitted operation")
            self._condition.wait_for(lambda: self._active == 0)


class _HasCalls(Protocol):
    _calls: CallGate


def admitted[**P, T](method: Callable[P, T]) -> Callable[P, T]:
    @wraps(method)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        owner = cast(_HasCalls, args[0])
        with owner._calls.enter():
            return method(*args, **kwargs)

    return wrapped
