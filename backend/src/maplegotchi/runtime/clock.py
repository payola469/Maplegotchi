"""Clocks. Runtime is the only layer that reads time; core receives it as a value."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Protocol

from maplegotchi.core.daytime import require_utc


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FakeClock:
    """Manually driven clock for tests and simulations. Thread-safe."""

    def __init__(self, start: datetime) -> None:
        require_utc(start, "start")
        self._now = start
        self._lock = threading.Lock()

    def now(self) -> datetime:
        with self._lock:
            return self._now

    def set(self, value: datetime) -> None:
        require_utc(value, "value")
        with self._lock:
            self._now = value

    def advance(self, delta: timedelta) -> datetime:
        with self._lock:
            self._now += delta
            return self._now
