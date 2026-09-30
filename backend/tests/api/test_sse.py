"""SSE: bounded, ordered, reconnect-friendly, read-only, never blocking Maple's life."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from maplegotchi.api.stream import event_stream
from maplegotchi.core.state import InteractionKind
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.events import EventHub
from maplegotchi.runtime.service import MapleService
from tests.api.support import make_client, make_service
from tests.persistence_support import BIRTH, TICK

# ---------------------------------------------------------------- hub


def test_new_clients_resync_and_known_clients_replay() -> None:
    hub = EventHub(capacity=5)
    assert hub.since(None).resync is True
    for i in range(3):
        hub.publish("x", {"i": i})
    catch = hub.since(1)
    assert not catch.resync and [e.seq for e in catch.events] == [2, 3]
    assert hub.since(3).events == () and not hub.since(3).resync


def test_buffer_is_bounded_and_falling_behind_means_resync() -> None:
    hub = EventHub(capacity=5)
    for i in range(20):
        hub.publish("x", {"i": i})
    assert hub.last_seq == 20
    kept = hub.since(15)
    assert [e.seq for e in kept.events] == [16, 17, 18, 19, 20] and not kept.resync
    behind = hub.since(3)  # events 4..15 are gone
    assert behind.resync and [e.seq for e in behind.events] == [16, 17, 18, 19, 20]


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "garbage",
        "12",
        "-",
        "zzzzzzzzzzzzzzzz-3",
        "0123456789abcdef-",
        "0123456789abcdef--1",
        "0123456789abcdef-3",
        "0123456789abcdef-99999999999999999999",
        " \n ",
    ],
)
def test_malformed_or_foreign_last_event_ids_mean_resync(value: str | None) -> None:
    hub = EventHub()
    hub.publish("x", {})
    seq = hub.parse_last_event_id(value)
    assert seq is None or hub.since(seq).resync


def test_own_ids_parse_and_future_ids_resync() -> None:
    hub = EventHub()
    event = hub.publish("x", {})
    assert hub.parse_last_event_id(event.event_id(hub.boot)) == 1
    assert hub.since(hub.parse_last_event_id(f"{hub.boot}-999")).resync  # from the future


def test_publishing_never_blocks_on_subscribers() -> None:
    hub = EventHub(capacity=16)

    async def idle_subscriber() -> None:
        hub.subscribe()  # registered, never reads
        started = time.perf_counter()
        for i in range(10_000):
            hub.publish("x", {"i": i})
        assert time.perf_counter() - started < 5

    asyncio.run(idle_subscriber())
    assert hub.last_seq == 10_000


# ---------------------------------------------------------------- stream generator


class Connection:
    """Drives event_stream like a client would, with a controllable disconnect."""

    def __init__(self, service: MapleService, last_event_id: str | None = None) -> None:
        self.disconnected = False
        self.stream: AsyncIterator[str] = event_stream(
            service, last_event_id, self.is_disconnected, keepalive_seconds=0.05
        )

    async def is_disconnected(self) -> bool:
        return self.disconnected

    async def next_frame(self) -> dict[str, object]:
        deadline = asyncio.get_running_loop().time() + 5
        while True:
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError("no event arrived (only keepalives)")
            chunk = await asyncio.wait_for(anext(self.stream), timeout=5)
            if chunk.startswith((":", "retry:")):
                continue
            fields = dict(line.split(": ", 1) for line in chunk.strip().splitlines())
            return {
                "id": fields["id"],
                "event": fields["event"],
                "data": json.loads(fields["data"]),
            }


def test_connect_gets_snapshot_then_live_events_in_order(tmp_path: Path) -> None:
    clock = FakeClock(BIRTH)
    service = make_service(tmp_path / "data", clock)

    async def scenario() -> list[dict[str, object]]:
        conn = Connection(service)
        first = await conn.next_frame()
        clock.advance(TICK)
        await asyncio.to_thread(service.tick)
        await asyncio.to_thread(service.interact, InteractionKind.PET)
        frames = [first] + [await conn.next_frame() for _ in range(6)]
        conn.disconnected = True
        return frames

    frames = asyncio.run(scenario())
    kinds = [f["event"] for f in frames]
    assert kinds[0] == "snapshot"
    assert kinds[1:] == [
        "heartbeat",
        "observations",
        "journal",
        "interaction",
        "timeline",
        "journal",
    ]
    seqs = [int(str(f["id"]).rsplit("-", 1)[1]) for f in frames[1:]]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    heartbeat = frames[1]["data"]
    assert isinstance(heartbeat, dict) and heartbeat["tick_id"] == 1
    interaction = frames[4]["data"]
    assert isinstance(interaction, dict) and interaction["reaction"]["kind"] == "pet_happy"
    revisions = [f["data"]["revision"] for f in frames[1:]]  # type: ignore[index]
    assert revisions == sorted(revisions)
    service.close()


def test_reconnect_with_last_event_id_replays_only_what_was_missed(tmp_path: Path) -> None:
    clock = FakeClock(BIRTH)
    service = make_service(tmp_path / "data", clock)

    async def scenario() -> tuple[list[str], list[str]]:
        first = Connection(service)
        await first.next_frame()  # snapshot
        service.interact(InteractionKind.GREET)
        seen = [await first.next_frame() for _ in range(3)]  # interaction, timeline, journal
        first.disconnected = True
        last_id = str(seen[0]["id"])  # the client only processed the first one
        service.interact(InteractionKind.PET)  # happens while disconnected
        second = Connection(service, last_id)
        replay = [await second.next_frame() for _ in range(4)]
        second.disconnected = True
        return [str(f["event"]) for f in seen], [str(f["event"]) for f in replay]

    seen, replay = asyncio.run(scenario())
    assert seen == ["interaction", "timeline", "journal"]
    # No snapshot; and no journal event for the Pet (inside the 30-minute journal gap).
    assert replay == ["timeline", "journal", "interaction", "timeline"]
    service.close()


@pytest.mark.parametrize("last_event_id", ["garbage", "0123456789abcdef-1", ""])
def test_malformed_or_old_process_ids_get_a_snapshot(tmp_path: Path, last_event_id: str) -> None:
    service = make_service(tmp_path / "data")

    async def scenario() -> str:
        conn = Connection(service, last_event_id)
        frame = await conn.next_frame()
        conn.disconnected = True
        return str(frame["event"])

    assert asyncio.run(scenario()) == "snapshot"
    service.close()


def test_slow_consumer_falls_behind_and_resyncs(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    service.hub = EventHub(capacity=4)

    async def scenario() -> dict[str, object]:
        conn = Connection(service)
        await conn.next_frame()  # snapshot
        for _ in range(3):  # six interactions: far more events than the 4-slot buffer
            service.interact(InteractionKind.GREET)
            service.interact(InteractionKind.PET)
            service.clock.advance(TICK)  # type: ignore[attr-defined]
        frame = await conn.next_frame()
        conn.disconnected = True
        return frame

    frame = asyncio.run(scenario())
    # Told to refetch rather than silently missing events, with the state as it is now.
    assert frame["event"] == "snapshot"
    assert frame["data"]["revision"] == service.runtime.revision == 7  # type: ignore[index]
    service.close()


def test_disconnect_ends_the_stream_and_unsubscribes(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")

    async def scenario() -> int:
        conn = Connection(service)
        await conn.next_frame()
        assert service.hub.subscriber_count == 1
        conn.disconnected = True
        with pytest.raises(StopAsyncIteration):
            while True:
                await asyncio.wait_for(anext(conn.stream), timeout=5)
        return service.hub.subscriber_count

    assert asyncio.run(scenario()) == 0
    service.close()


def test_waiting_client_does_not_hold_the_writer_lock(tmp_path: Path) -> None:
    clock = FakeClock(BIRTH)
    service = make_service(tmp_path / "data", clock)

    async def scenario() -> None:
        conn = Connection(service)
        await conn.next_frame()  # snapshot; now the stream is waiting for events
        waiting = asyncio.ensure_future(conn.next_frame())
        await asyncio.sleep(0.1)
        assert service.runtime._lock.acquire(blocking=False)  # free while a client waits
        service.runtime._lock.release()
        done = threading.Event()

        def act() -> None:
            clock.advance(TICK)
            service.tick()
            service.interact(InteractionKind.PET)
            done.set()

        await asyncio.to_thread(act)
        assert done.is_set()
        assert (await waiting)["event"] == "heartbeat"
        conn.disconnected = True

    asyncio.run(scenario())
    service.close()


# ---------------------------------------------------------------- over HTTP


def test_sse_over_http_is_read_only_and_well_formed(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    client = make_client(service, tmp_path, sse_max_events=1)
    response = client.get("/api/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    body = response.text
    assert body.startswith("retry: 3000\n\n")
    assert f"id: {service.hub.boot}-0\nevent: snapshot\ndata: " in body
    for method in ("POST", "PUT", "DELETE"):
        assert client.request(method, "/api/events", content=b"event: interaction").status_code in (
            404,
            405,
        )
    assert service.runtime.revision == 1
    service.close()
