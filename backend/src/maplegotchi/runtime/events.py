"""Live events for SSE: a bounded, thread-safe, publish-only ring buffer.

- Publishing never blocks: it appends to a fixed-size buffer and pokes waiting
  subscribers. A slow or gone client can never hold up Maple's life loop.
- Event ids are "<boot>-<seq>". The boot id changes every process start, so a
  client reconnecting with an id from an older process, an id that has fallen
  out of the buffer, or a malformed id is told to resync (refetch a snapshot)
  instead of silently missing events.
- Clients only read; there is no way to publish through the stream.
"""

from __future__ import annotations

import asyncio
import re
import secrets
import threading
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_CAPACITY = 512  # ~100 commits: each publishes a few kinds incl. `life` (ADR-0028)
_EVENT_ID = re.compile(r"([0-9a-f]{16})-([0-9]{1,18})")


@dataclass(frozen=True)
class LiveEvent:
    seq: int
    kind: str
    data: Mapping[str, object]

    def event_id(self, boot: str) -> str:
        return f"{boot}-{self.seq}"


@dataclass(frozen=True)
class Catchup:
    events: tuple[LiveEvent, ...]
    resync: bool  # the client missed events it can no longer get: send a snapshot


class EventHub:
    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.boot = secrets.token_hex(8)
        self._lock = threading.Lock()
        self._events: deque[LiveEvent] = deque(maxlen=capacity)
        self._next_seq = 1
        self._waiters: set[tuple[asyncio.AbstractEventLoop, asyncio.Event]] = set()

    @property
    def last_seq(self) -> int:
        with self._lock:
            return self._next_seq - 1

    def publish(self, kind: str, data: Mapping[str, object]) -> LiveEvent:
        with self._lock:
            event = LiveEvent(self._next_seq, kind, dict(data))
            self._next_seq += 1
            self._events.append(event)
            waiters = list(self._waiters)
        for loop, flag in waiters:
            try:
                loop.call_soon_threadsafe(flag.set)
            except RuntimeError:  # that client's loop is gone; it will be dropped
                pass
        return event

    def parse_last_event_id(self, value: str | None) -> int | None:
        """The sequence number to resume after, or None if absent/foreign/malformed."""
        if not value:
            return None
        match = _EVENT_ID.fullmatch(value.strip())
        if match is None or match.group(1) != self.boot:
            return None
        return int(match.group(2))

    def since(self, last_seq: int | None) -> Catchup:
        """Events after `last_seq`. `None` means "new client": resync, no replay."""
        with self._lock:
            if last_seq is None or last_seq >= self._next_seq:
                return Catchup((), resync=True)
            oldest = self._events[0].seq if self._events else self._next_seq
            missed = last_seq < oldest - 1
            return Catchup(tuple(e for e in self._events if e.seq > last_seq), resync=missed)

    def subscribe(self) -> asyncio.Event:
        flag = asyncio.Event()
        with self._lock:
            self._waiters.add((asyncio.get_running_loop(), flag))
        return flag

    def unsubscribe(self, flag: asyncio.Event) -> None:
        with self._lock:
            self._waiters = {w for w in self._waiters if w[1] is not flag}

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._waiters)
