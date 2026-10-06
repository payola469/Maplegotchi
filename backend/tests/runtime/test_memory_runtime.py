"""Memory through the runtime and API (ADR-0030): Maple's data, relevant, consolidated."""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest

from maplegotchi.core.memory import Tier
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.service import MapleService
from tests.api.support import make_client, make_service
from tests.persistence_support import BIRTH

Life = tuple[MapleService, FakeClock, Path]


@pytest.fixture(scope="module")
def life(tmp_path_factory: pytest.TempPathFactory) -> Life:
    root = tmp_path_factory.mktemp("memory") / "data"
    clock = FakeClock(BIRTH)
    service = make_service(root, clock)
    for _ in range(14 * 12):
        clock.advance(timedelta(minutes=5))
        service.step()
    return service, clock, root


def test_living_creates_memories_in_maples_own_database(life: Life) -> None:
    service, _, root = life
    found = service.runtime.memories(limit=500)
    kinds = {m.kind.value for m in found}
    assert {"reading", "goal_outcome"} <= kinds
    assert all(m.tier is Tier.SHORT_TERM for m in found)
    conn = sqlite3.connect(root / "maple.db")
    try:
        assert conn.execute("SELECT count(*) FROM memory").fetchone()[0] == len(found)
        events = conn.execute("SELECT DISTINCT kind FROM memory_event").fetchall()
        assert ("created",) in events
    finally:
        conn.close()


def test_decision_context_carries_only_a_few_relevant_memories(life: Life) -> None:
    service, clock, _ = life
    runtime = service.runtime
    for _ in range(200):
        clock.advance(timedelta(minutes=1))
        pending = runtime.pending_decision()
        if pending is not None:
            break
        service.step()
    assert pending is not None
    memories = pending.context.as_json()["memories"]
    assert 1 <= len(memories) <= 5
    assert all(set(m) == {"kind", "tier", "text"} for m in memories)
    assert all(m["tier"] != "archive" for m in memories)


def test_memory_api_lists_and_searches(life: Life, tmp_path: Path) -> None:
    service, _, _ = life
    client = make_client(service, tmp_path)
    listed = client.get("/api/memory?tier=short_term&limit=10").json()
    assert listed and all(m["tier"] == "short_term" for m in listed)
    word = listed[-1]["text"].split()[-1].strip(".:")
    hits = client.get(f"/api/memory/search?q={word}").json()
    assert hits
    assert client.get("/api/memory?tier=forever").status_code == 422
    assert client.get("/api/memory/search?q=").status_code == 422


def test_expired_short_term_memories_are_archived_not_deleted(tmp_path: Path) -> None:
    clock = FakeClock(BIRTH)
    service = make_service(tmp_path / "data", clock)
    for _ in range(8 * 12):
        clock.advance(timedelta(minutes=5))
        service.step()
    before = {m.id for m in service.runtime.memories(limit=500)}
    assert before
    clock.advance(timedelta(hours=37))
    service.step()  # one bounded catch-up heartbeat consolidates
    after = service.runtime.memories(limit=1000)
    assert before <= {m.id for m in after}  # nothing deleted
    archived = {m.id for m in after if m.tier is Tier.ARCHIVE}
    assert before <= archived
    assert not any(m.tier is Tier.LONG_TERM for m in after)  # never promoted automatically
    service.close()


def test_memories_are_maples_not_the_providers(tmp_path: Path) -> None:
    """Switching the Director/Brain changes nothing in memory: it is Maple's data."""
    from maplegotchi.runtime.service import fake_senses
    from tests.persistence_support import PARAMS, make_data_dir, open_runtime
    from tests.runtime.test_director_runtime import GOOD, FakeDirector

    data_dir = make_data_dir(tmp_path)
    clock = FakeClock(BIRTH)
    first = MapleService(open_runtime(data_dir, clock), fake_senses(), clock, PARAMS)
    for _ in range(4 * 12):
        clock.advance(timedelta(minutes=5))
        first.step()
    remembered = first.runtime.memories(limit=500)
    first.close()
    second = MapleService(open_runtime(data_dir, clock), fake_senses(), clock, PARAMS,
                          director=FakeDirector(lambda ctx: GOOD))  # fmt: skip
    assert second.runtime.memories(limit=500) == remembered
    second.close()
