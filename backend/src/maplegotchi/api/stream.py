"""Server-Sent Events: a read-only live stream of Maple's changes.

Wire format per event:
    id: <boot>-<seq>
    event: <snapshot|heartbeat|observations|interaction|journal|timeline>
    data: <one line of JSON>

- On connect (no/foreign/malformed Last-Event-ID) and whenever the client has
  fallen behind the bounded buffer, a `snapshot` event carries a full snapshot;
  otherwise missed events are replayed from the buffer.
- A comment line `: keepalive` is sent every SSE_KEEPALIVE_SECONDS of silence,
  so clients can detect a dead connection.
- The generator only reads the hub; it never holds the writer lock while
  waiting, and the stream accepts no input.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable

from maplegotchi.api import views
from maplegotchi.runtime.events import LiveEvent
from maplegotchi.runtime.service import SSE_KEEPALIVE_SECONDS, MapleService

RETRY_MILLISECONDS = 3000


def _frame(event_id: str, kind: str, payload: object) -> str:
    data = json.dumps(payload, separators=(",", ":"), default=str)
    return f"id: {event_id}\nevent: {kind}\ndata: {data}\n\n"


async def _snapshot_frame(service: MapleService) -> tuple[int, str]:
    seq = service.hub.last_seq  # taken before the snapshot, so nothing after it is lost
    snap = await asyncio.to_thread(service.snapshot)
    payload = views.snapshot(snap).model_dump(mode="json")
    return seq, _frame(f"{service.hub.boot}-{seq}", "snapshot", payload)


def _event_frame(service: MapleService, event: LiveEvent) -> str:
    payload = views.live_event(event.kind, event.data)
    return _frame(event.event_id(service.hub.boot), event.kind, payload)


async def event_stream(
    service: MapleService,
    last_event_id: str | None,
    is_disconnected: Callable[[], Awaitable[bool]],
    *,
    keepalive_seconds: float = SSE_KEEPALIVE_SECONDS,
    max_events: int | None = None,
) -> AsyncIterator[str]:
    hub = service.hub
    flag = hub.subscribe()
    sent = 0
    try:
        yield f"retry: {RETRY_MILLISECONDS}\n\n"
        last = hub.parse_last_event_id(last_event_id)
        while max_events is None or sent < max_events:
            if await is_disconnected():
                return
            flag.clear()
            catchup = hub.since(last)
            if catchup.resync:
                last, frame = await _snapshot_frame(service)
                yield frame
                sent += 1
                continue
            for event in catchup.events:
                if max_events is not None and sent >= max_events:
                    return
                yield _event_frame(service, event)
                last = event.seq
                sent += 1
            if not catchup.events:
                try:
                    await asyncio.wait_for(flag.wait(), timeout=keepalive_seconds)
                except TimeoutError:
                    yield ": keepalive\n\n"
    finally:
        hub.unsubscribe(flag)
