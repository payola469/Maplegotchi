"""Consistency proofs: coherent snapshots, and SSE describing committed transitions only."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from maplegotchi.api.app import create_app
from maplegotchi.core.interactions import Accepted
from maplegotchi.core.state import InteractionKind
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.events import LiveEvent
from maplegotchi.runtime.service import LiveSnapshot, MapleService
from maplegotchi.storage import repositories
from maplegotchi.storage.repositories import LifeRepository
from tests.api.support import TRUSTED, make_client, make_service, make_settings
from tests.persistence_support import BIRTH, TICK


def rev(event: LiveEvent) -> int:
    value = event.data["revision"]
    assert isinstance(value, int)
    return value


def db_revision(data_root: Path) -> int:
    """The committed revision as seen by an independent connection (another reader)."""
    conn = sqlite3.connect(data_root / "maple.db")
    try:
        return int(conn.execute("SELECT revision FROM life_state").fetchone()[0])
    finally:
        conn.close()


def assert_coherent(snap: LiveSnapshot, data_root: Path) -> None:
    """Every persisted part of the snapshot belongs to the committed state at snap.revision."""
    n = snap.revision
    parts = (
        [e.revision for e in snap.journal]
        + [e.revision for e in snap.timeline]
        + [o.revision for o in snap.server.observations]
    )
    assert all(r <= n for r in parts), f"parts from after revision {n}: {parts}"
    conn = sqlite3.connect(data_root / "maple.db")
    try:
        expected_journal = [
            r[0]
            for r in conn.execute(
                "SELECT id FROM journal_entry WHERE revision <= ? ORDER BY id DESC LIMIT 10", (n,)
            )
        ][::-1]
        expected_timeline = [
            r[0]
            for r in conn.execute(
                "SELECT id FROM timeline_event WHERE revision <= ? ORDER BY id DESC LIMIT 10", (n,)
            )
        ][::-1]
        tick = conn.execute(
            "SELECT max(tick_id) FROM observation WHERE revision <= ?", (n,)
        ).fetchone()[0]
    finally:
        conn.close()
    assert [e.id for e in snap.journal] == expected_journal
    assert [e.id for e in snap.timeline] == expected_timeline
    assert {o.tick_id for o in snap.server.observations} <= {tick}
    assert snap.state.rng.tick_counter == (tick or 0) or not snap.server.observations


def prepared(tmp_path: Path) -> tuple[MapleService, FakeClock, Path]:
    """A Maple with some history: heartbeats with observations, an interaction."""
    clock = FakeClock(BIRTH)
    root = tmp_path / "data"
    service = make_service(root, clock)
    for _ in range(3):
        clock.advance(TICK)
        service.tick()
    service.interact(InteractionKind.GREET)
    clock.advance(TICK)
    return service, clock, root


# ---------------------------------------------------------------- 1. coherent snapshot


class PauseInside:
    """Pause read_view after it has read the state, before journal/timeline are read."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.paused = threading.Event()
        self.release = threading.Event()
        original = LifeRepository.journal
        pause = self

        def journal(self: LifeRepository, **kwargs: Any) -> Any:
            if kwargs.get("limit") is not None and not pause.paused.is_set():
                pause.paused.set()
                assert pause.release.wait(10)
            return original(self, **kwargs)

        monkeypatch.setattr(LifeRepository, "journal", journal)


def test_writer_through_the_runtime_waits_for_an_in_progress_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _, root = prepared(tmp_path)
    before = service.runtime.revision
    pause = PauseInside(monkeypatch)
    result: dict[str, object] = {}
    reader = threading.Thread(target=lambda: result.update(snap=service.snapshot()))
    reader.start()
    assert pause.paused.wait(10)  # snapshot is mid-read: state read, journal not yet
    writer = threading.Thread(target=lambda: result.update(tick=service.tick()))
    writer.start()
    writer.join(0.3)
    assert writer.is_alive()  # the heartbeat cannot commit into the middle of the read
    pause.release.set()
    reader.join(10)
    writer.join(10)
    snap = result["snap"]
    assert isinstance(snap, LiveSnapshot)
    assert snap.revision == before  # complete "before" snapshot
    assert_coherent(snap, root)
    monkeypatch.undo()
    after = service.snapshot()
    assert after.revision == before + 1  # complete "after" snapshot
    assert_coherent(after, root)
    service.close()


@pytest.mark.parametrize("read_transaction_enabled", [True, False])
def test_one_read_transaction_isolates_the_view_even_from_another_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, read_transaction_enabled: bool
) -> None:
    """Even a writer that does not share the runtime lock (another process on the same
    file) cannot mix into a snapshot: the read is one SQLite snapshot. The negative
    control (read transaction disabled) shows the mixture this prevents."""
    service, clock, root = prepared(tmp_path)
    other = make_service(root, clock)  # an independent writer on the same database file
    before = db_revision(root)
    if not read_transaction_enabled:

        @contextmanager
        def no_transaction(conn: sqlite3.Connection) -> Iterator[None]:
            yield

        monkeypatch.setattr(repositories, "read_transaction", no_transaction)
    pause = PauseInside(monkeypatch)
    result: dict[str, object] = {}
    reader = threading.Thread(target=lambda: result.update(snap=service.snapshot()))
    reader.start()
    assert pause.paused.wait(10)
    committed = other.runtime.interact_committed(InteractionKind.PET)  # commits now
    assert isinstance(committed.outcome, Accepted) and db_revision(root) == before + 1
    pause.release.set()
    reader.join(10)
    snap = result["snap"]
    assert isinstance(snap, LiveSnapshot)
    newest = max([e.revision for e in snap.timeline] + [e.revision for e in snap.journal])
    if read_transaction_enabled:
        assert snap.revision == before and newest <= before  # whole snapshot from before
        assert_coherent(snap, root)
    else:
        assert snap.revision == before and newest == before + 1  # the mixture it prevents
    other.close()
    service.runtime.close()


def test_writer_committing_after_the_read_cannot_leak_into_assembly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, clock, root = prepared(tmp_path)
    before = service.runtime.revision
    original = service.runtime.read_view

    def read_then_let_a_writer_commit(*, recent: int) -> Any:
        view = original(recent=recent)
        clock.advance(TICK)
        assert service.runtime.heartbeat_committed(service.senses.observe(clock.now()))
        service.runtime.interact_committed(InteractionKind.PET)
        return view

    monkeypatch.setattr(service.runtime, "read_view", read_then_let_a_writer_commit)
    snap = service.snapshot()
    assert snap.revision == before and service.runtime.revision == before + 2
    assert_coherent(snap, root)  # assembled only from the view, never re-read
    service.close()


def test_concurrent_snapshots_under_load_are_always_coherent(tmp_path: Path) -> None:
    service, clock, root = prepared(tmp_path)
    stop = threading.Event()
    snaps: list[LiveSnapshot] = []

    def read() -> None:
        while not stop.is_set():
            snaps.append(service.snapshot())

    readers = [threading.Thread(target=read) for _ in range(3)]
    for r in readers:
        r.start()
    for i in range(40):
        clock.advance(TICK)
        service.tick()
        service.interact(InteractionKind.GREET if i % 2 else InteractionKind.PET)
    stop.set()
    for r in readers:
        r.join(10)
    assert len(snaps) > 20
    for snap in snaps[:: max(1, len(snaps) // 40)]:
        assert_coherent(snap, root)
    service.close()


# ---------------------------------------------------------------- 2. SSE = committed only


def events(service: MapleService) -> list[LiveEvent]:
    return list(service.hub.since(0).events)


def test_rolled_back_heartbeat_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _, root = prepared(tmp_path)
    seq, revision = service.hub.last_seq, db_revision(root)

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(LifeRepository, "_insert_observations", fail)
    with pytest.raises(OSError):
        service.tick()
    assert service.hub.last_seq == seq  # no heartbeat/observations/journal/timeline events
    assert db_revision(root) == revision
    monkeypatch.undo()
    assert service.tick() is not None  # the retry commits, and only then publishes
    published = [e.kind for e in service.hub.since(seq).events]
    assert published[:2] == ["heartbeat", "observations"]
    assert {rev(e) for e in service.hub.since(seq).events} == {revision + 1}
    service.close()


def test_rolled_back_interaction_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = FakeClock(BIRTH)
    root = tmp_path / "data"
    service = make_service(root, clock)

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(LifeRepository, "_insert_journal_entry", fail)
    with pytest.raises(OSError):
        service.interact(InteractionKind.GREET)  # the greet's journal write fails
    assert service.hub.last_seq == 0 and db_revision(root) == 1
    app = create_app(service, make_settings(tmp_path), run_life_loop=False)
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post("/api/interactions/greet", headers=TRUSTED).status_code == 500
    assert service.hub.last_seq == 0 and db_revision(root) == 1  # HTTP path: same
    service.close()


def test_events_are_published_after_the_durable_commit_and_outside_the_lock(
    tmp_path: Path,
) -> None:
    service, clock, root = prepared(tmp_path)
    original = service.hub.publish
    checks: list[tuple[str, int, int, bool]] = []

    def observing_publish(kind: str, data: Any) -> LiveEvent:
        lock_free = service.runtime._lock.acquire(blocking=False)
        if lock_free:
            service.runtime._lock.release()
        checks.append((kind, int(data["revision"]), db_revision(root), lock_free))
        return original(kind, data)

    service.hub.publish = observing_publish  # type: ignore[method-assign]
    clock.advance(TICK)
    service.tick()
    clock.advance(TICK)
    service.interact(InteractionKind.PET)
    assert {c[0] for c in checks} >= {"heartbeat", "observations", "interaction", "timeline"}
    for kind, event_revision, committed_revision, lock_free in checks:
        # Another connection already sees the transition when its event is published.
        assert committed_revision >= event_revision, kind
        assert lock_free, f"{kind} published while holding the writer lock"
    service.close()


def test_a_client_reading_after_an_event_sees_at_least_that_revision(tmp_path: Path) -> None:
    service, clock, _ = prepared(tmp_path)
    client = make_client(service, tmp_path)
    seen = service.hub.last_seq
    clock.advance(TICK)
    service.tick()
    service.interact(InteractionKind.PET)
    for event in service.hub.since(seen).events:
        revision = rev(event)
        assert client.get("/api/snapshot").json()["revision"] >= revision
        assert service.snapshot().revision >= revision
    service.close()


def test_http_response_revision_matches_its_sse_event_under_concurrent_heartbeats(
    tmp_path: Path,
) -> None:
    service, clock, root = prepared(tmp_path)
    client = make_client(service, tmp_path)
    responses: list[dict[str, Any]] = []
    stop = threading.Event()

    def heartbeats() -> None:
        while not stop.is_set():
            clock.advance(TICK / 3)
            service.tick()

    ticker = threading.Thread(target=heartbeats)
    ticker.start()
    for i in range(24):
        route = "greet" if i % 2 == 0 else "pet"
        clock.advance(TICK / 5)
        responses.append(client.post(f"/api/interactions/{route}", headers=TRUSTED).json())
    stop.set()
    ticker.join(10)

    interaction_events = {
        rev(e): str(e.data["kind"]) for e in events(service) if e.kind == "interaction"
    }
    accepted = [r for r in responses if r["accepted"]]
    assert len(accepted) >= 10
    conn = sqlite3.connect(root / "maple.db")
    try:
        for r in accepted:
            assert interaction_events[r["revision"]] == r["interaction"]  # same transition
            row = conn.execute(
                "SELECT payload FROM timeline_event WHERE kind = 'interaction_accepted'"
                " AND revision = ?",
                (r["revision"],),
            ).fetchone()
            assert row is not None and f'"kind":"{r["interaction"]}"' in row[0]
            assert r["maple"]["revision"] >= r["revision"]
    finally:
        conn.close()
    service.close()


def test_a_broken_hub_can_never_block_or_roll_back_maple(tmp_path: Path) -> None:
    service, clock, root = prepared(tmp_path)

    def broken(kind: str, data: Any) -> LiveEvent:
        raise RuntimeError("subscriber machinery exploded")

    service.hub.publish = broken  # type: ignore[method-assign]
    before = db_revision(root)
    clock.advance(TICK)
    assert service.tick() is not None
    result = service.interact(InteractionKind.PET)
    assert isinstance(result.outcome, Accepted)
    assert db_revision(root) == before + 2 == result.revision
    service.close()
