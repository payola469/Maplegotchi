"""Persisted audit and the one life-event model over REST and SSE (ADR-0026 §8, ADR-0028 §2)."""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

from maplegotchi.api import views
from maplegotchi.core.state import InteractionKind
from maplegotchi.runtime.clock import FakeClock
from tests.api.support import make_client, make_service
from tests.persistence_support import BIRTH

TICK = timedelta(seconds=300)

ACTION_KINDS = {
    "destination_selected",
    "walking_started",
    "walking_cancelled",
    "arrived",
    "activity_started",
    "activity_completed",
    "activity_interrupted",
    "activity_resumed",
    "needs_attention",
}


def lived(tmp_path: Path, minutes: int = 90):  # type: ignore[no-untyped-def]
    clock = FakeClock(BIRTH)
    service = make_service(tmp_path / "data", clock)
    for _ in range(minutes):
        clock.advance(timedelta(minutes=1))
        service.step()
    return service, clock


def test_decisions_are_persisted_and_served(tmp_path: Path) -> None:
    service, _ = lived(tmp_path)
    client = make_client(service, tmp_path)
    body = client.get("/api/decisions?limit=5").json()
    assert 1 <= len(body) <= 5
    d = body[-1]
    assert d["director"] == {"kind": "rule", "name": "rule_director", "version": "1"}
    assert d["verdict"] == "accepted"
    assert d["context_summary"].startswith("trigger=")
    assert d["executed"]["action"] and d["executed"]["point"]
    assert [x["id"] for x in body] == sorted(x["id"] for x in body)
    service.close()


def test_goal_rows_name_the_decision_that_started_them(tmp_path: Path) -> None:
    service, _ = lived(tmp_path)
    conn = sqlite3.connect(tmp_path / "data" / "maple.db")
    try:
        rows = conn.execute(
            "SELECT g.id, d.goal_id, d.proposed_goal_op FROM goal g JOIN decision d"
            " ON d.id = g.decision_id"
        ).fetchall()
        assert rows and all(goal == decided and op == "new" for goal, decided, op in rows)
    finally:
        conn.close()
    service.close()


def test_life_events_cover_walking_arrival_and_starting(tmp_path: Path) -> None:
    service, _ = lived(tmp_path)
    client = make_client(service, tmp_path)
    body = client.get("/api/life-events?after_revision=0&limit=500").json()
    events = body["events"]
    types = [e["type"] for e in events]
    assert "goal_started" in types and "born" in types
    assert {"destination_selected", "activity_started"} <= set(types)
    if "walking_started" in types:
        assert "arrived" in types
    keys = [(e["revision"], e["id"].split(":")[0]) for e in events]
    order = {"decision": 0, "timeline": 1, "action": 2, "tool": 3, "memory": 4}
    assert keys == sorted(keys, key=lambda k: (k[0], order[k[1]]))
    assert body["last_revision"] == events[-1]["revision"]
    for e in events:
        assert set(e) == {"id", "type", "at", "revision", "goal_id", "action_id", "priority",
                          "payload"}  # fmt: skip
        if e["id"].startswith("action:"):
            assert e["type"] in ACTION_KINDS and e["action_id"] is not None
    service.close()


def test_life_events_cursor_continues_without_gaps(tmp_path: Path) -> None:
    service, _ = lived(tmp_path, minutes=120)
    client = make_client(service, tmp_path)
    everything = client.get("/api/life-events?after_revision=0&limit=500").json()["events"]
    seen: list[str] = []
    cursor = 0
    for _ in range(100):
        page = client.get(f"/api/life-events?after_revision={cursor}&limit=7").json()
        if not page["events"]:
            break
        seen += [e["id"] for e in page["events"]]
        cursor = page["last_revision"]
    assert seen == [e["id"] for e in everything]
    service.close()


def test_sse_life_event_carries_the_commit_envelopes(tmp_path: Path) -> None:
    service, _ = lived(tmp_path, minutes=20)
    seen = service.hub.last_seq
    service.interact(InteractionKind.GREET)
    life = [e for e in service.hub.since(seen).events if e.kind == "life"]
    assert len(life) == 1
    payload = views.live_event("life", life[0].data)
    assert payload["revision"] == service.runtime.revision
    events = payload["events"]
    assert isinstance(events, list)
    assert "interaction_accepted" in [e["type"] for e in events]
    service.close()


def test_the_decision_table_cannot_hold_model_reasoning(tmp_path: Path) -> None:
    service, _ = lived(tmp_path, minutes=5)
    conn = sqlite3.connect(tmp_path / "data" / "maple.db")
    try:
        columns = {r[1] for r in conn.execute("PRAGMA table_info(decision)").fetchall()}
    finally:
        conn.close()
    banned = {"prompt", "raw", "response", "thought", "thinking", "chain", "reasoning"}
    assert not any(word in column for column in columns for word in banned)
    assert "proposed_reason" in columns  # the one concise, validated line
    service.close()
