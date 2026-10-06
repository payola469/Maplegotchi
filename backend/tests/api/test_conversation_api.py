"""The conversation endpoint: gateway-only, idempotent, truthful, failure-safe (ADR-0032)."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from maplegotchi.api.app import create_app
from maplegotchi.core.conversation import ReplyContext
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.service import MapleService, fake_senses
from tests.api.support import make_settings
from tests.persistence_support import BIRTH, PARAMS, make_data_dir, open_runtime

TOKEN = "t" * 40
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def message(mid: str = "111", text: str = "What are you doing?") -> dict[str, str]:
    return {"message_id": mid, "channel": "discord", "speaker": "paolo", "text": text}


class FakeReplier:
    kind = "external"
    name = "fake"

    def __init__(self, answer: Any) -> None:
        self.answer = answer
        self.contexts: list[ReplyContext] = []

    def reply(self, context: ReplyContext) -> str:
        self.contexts.append(context)
        if isinstance(self.answer, Exception):
            raise self.answer
        if callable(self.answer):
            return str(self.answer())
        return str(self.answer)


def client(tmp_path: Path, *, token: str | None = TOKEN, replier: Any = None,
           timeout: float = 2.0) -> tuple[TestClient, MapleService]:  # fmt: skip
    clock = FakeClock(BIRTH)
    runtime = open_runtime(make_data_dir(tmp_path), clock)
    service = MapleService(runtime, fake_senses(), clock, PARAMS, replier=replier,
                           director_timeout_seconds=timeout)  # fmt: skip
    app = create_app(service, make_settings(tmp_path, gateway_token=token), run_life_loop=False)
    return TestClient(app), service


def rows(tmp_path: Path) -> list[tuple[str, str]]:
    conn = sqlite3.connect(tmp_path / "maple-data" / "maple.db")
    try:
        return conn.execute(
            "SELECT direction, text FROM conversation_message ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def test_disabled_without_a_gateway_token(tmp_path: Path) -> None:
    c, service = client(tmp_path, token=None)
    assert c.post("/api/conversation/messages", json=message(), headers=AUTH).status_code == 404
    service.close()


def test_only_the_gateway_may_post(tmp_path: Path) -> None:
    c, service = client(tmp_path)
    assert c.post("/api/conversation/messages", json=message()).status_code == 401
    wrong = {"Authorization": "Bearer " + "x" * 40}
    assert c.post("/api/conversation/messages", json=message(), headers=wrong).status_code == 401
    browser = {**AUTH, "Origin": "http://127.0.0.1:5173"}
    assert c.post("/api/conversation/messages", json=message(), headers=browser).status_code == 403
    assert rows(tmp_path) == []
    service.close()


@pytest.mark.parametrize(
    "body",
    [
        {**message(), "speaker": "stranger"},
        {**message(), "channel": "email"},
        {**message(), "extra": "field"},
        {**message(), "message_id": "../../etc"},
        {**message(), "text": ""},
        {**message(), "text": "x" * 2001},
    ],
)
def test_malformed_messages_are_refused(tmp_path: Path, body: dict[str, str]) -> None:
    c, service = client(tmp_path)
    assert c.post("/api/conversation/messages", json=body, headers=AUTH).status_code == 422
    service.close()


def test_oversized_bodies_are_refused_before_routing(tmp_path: Path) -> None:
    c, service = client(tmp_path)
    huge = message(text="x" * 9000)
    assert c.post("/api/conversation/messages", json=huge, headers=AUTH).status_code == 413
    service.close()


def test_a_message_gets_a_truthful_reply_and_both_are_recorded(tmp_path: Path) -> None:
    c, service = client(tmp_path)
    before = service.runtime.state
    response = c.post("/api/conversation/messages", json=message(), headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["reply"].startswith("Right now I'm")
    assert body["replier"] == {"kind": "rule", "name": "rule_replier"}
    assert body["duplicate"] is False and body["fallback_code"] is None
    assert service.runtime.state.needs.social > before.needs.social
    assert rows(tmp_path) == [("in", "What are you doing?"), ("out", body["reply"])]
    history = c.get("/api/conversation").json()
    assert [m["speaker"] for m in history] == ["paolo", "maple"]
    events = c.get("/api/life-events?after_revision=0&limit=500").json()["events"]
    types = [e["type"] for e in events]
    assert "conversation_received" in types and "conversation_replied" in types
    memories = c.get("/api/memory?tier=short_term").json()
    assert any(m["kind"] == "conversation" for m in memories)
    service.close()


def test_a_retried_message_is_answered_once(tmp_path: Path) -> None:
    c, service = client(tmp_path)
    first = c.post("/api/conversation/messages", json=message(), headers=AUTH).json()
    again = c.post("/api/conversation/messages", json=message(), headers=AUTH).json()
    assert again["reply"] == first["reply"] and again["duplicate"] is True
    assert len(rows(tmp_path)) == 2
    service.close()


def test_external_replies_are_used_when_valid(tmp_path: Path) -> None:
    replier = FakeReplier("I'm reading by the shelf, thanks for asking!")
    c, service = client(tmp_path, replier=replier)
    body = c.post("/api/conversation/messages", json=message(), headers=AUTH).json()
    assert body["reply"] == "I'm reading by the shelf, thanks for asking!"
    assert body["replier"] == {"kind": "external", "name": "fake"}
    ctx = replier.contexts[0].as_json()
    assert ctx["message"]["text"] == "What are you doing?" and ctx["activity"]
    service.close()


@pytest.mark.parametrize(
    ("answer", "code"),
    [(RuntimeError("down"), "transport_error"), ("", "invalid_reply"),
     ("bad\x00reply", "invalid_reply")],
)  # fmt: skip
def test_replier_failures_fall_back_to_a_rule_reply(tmp_path: Path, answer: Any, code: str) -> None:
    c, service = client(tmp_path, replier=FakeReplier(answer))
    body = c.post("/api/conversation/messages", json=message(), headers=AUTH).json()
    assert body["fallback_code"] == code
    assert body["reply"].startswith("Right now I'm")
    assert body["replier"]["kind"] == "rule"
    service.close()


def test_a_slow_replier_times_out_and_maple_still_answers(tmp_path: Path) -> None:
    release = threading.Event()
    c, service = client(tmp_path, replier=FakeReplier(lambda: release.wait(5) or "late"),
                        timeout=0.2)  # fmt: skip
    body = c.post("/api/conversation/messages", json=message(), headers=AUTH).json()
    assert body["fallback_code"] == "timeout"
    release.set()
    service.close()


def latencies(tmp_path: Path) -> list[tuple[str, int | None]]:
    conn = sqlite3.connect(tmp_path / "maple-data" / "maple.db")
    try:
        return conn.execute(
            "SELECT direction, latency_ms FROM conversation_message ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def test_external_reply_latency_is_stored_with_the_reply(tmp_path: Path) -> None:
    def slow() -> str:
        time.sleep(0.05)
        return "I'm reading, thanks!"

    c, service = client(tmp_path, replier=FakeReplier(slow))
    c.post("/api/conversation/messages", json=message(), headers=AUTH)
    (incoming, in_latency), (outgoing, out_latency) = latencies(tmp_path)
    assert (incoming, in_latency) == ("in", None)  # only Maple's reply carries a latency
    assert outgoing == "out" and out_latency is not None and 50 <= out_latency < 5000
    assert service.runtime.messages(limit=1)[-1].latency_ms == out_latency
    service.close()


def test_a_failed_attempt_stores_its_latency_too(tmp_path: Path) -> None:
    release = threading.Event()
    c, service = client(tmp_path, replier=FakeReplier(lambda: release.wait(5) or "late"),
                        timeout=0.2)  # fmt: skip
    c.post("/api/conversation/messages", json=message(), headers=AUTH)
    release.set()
    latency = latencies(tmp_path)[-1][1]
    assert latency is not None and latency >= 200  # the time spent before falling back
    service.close()


def test_rule_replies_have_no_latency(tmp_path: Path) -> None:
    c, service = client(tmp_path)
    c.post("/api/conversation/messages", json=message(), headers=AUTH)
    assert latencies(tmp_path) == [("in", None), ("out", None)]
    service.close()


class StuckOnceReplier:
    """The first call hangs until released; later calls answer at once."""

    kind = "external"
    name = "fake"

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.calls = 0

    def reply(self, context: ReplyContext) -> str:
        self.calls += 1
        if self.calls == 1:
            self.started.set()
            self.release.wait(5)
            self.finished.set()
            return "late"
        return "I'm back, thanks for waiting!"


def audit(tmp_path: Path) -> list[tuple[str | None, str | None, int | None]]:
    conn = sqlite3.connect(tmp_path / "maple-data" / "maple.db")
    try:
        return conn.execute(
            "SELECT replier_kind, fallback_code, latency_ms FROM conversation_message"
            " WHERE direction = 'out' ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def test_a_stuck_replier_call_is_never_stacked(tmp_path: Path) -> None:
    replier = StuckOnceReplier()
    c, service = client(tmp_path, replier=replier, timeout=1.0)
    first = c.post("/api/conversation/messages", json=message("1"), headers=AUTH).json()
    assert first["fallback_code"] == "timeout"
    assert replier.started.is_set() and not replier.finished.is_set()  # still running

    started = time.perf_counter()
    second = c.post("/api/conversation/messages", json=message("2"), headers=AUTH).json()
    assert time.perf_counter() - started < 1.0  # no wait for a deadline behind the stuck call
    assert second["fallback_code"] == "timeout"
    assert second["reply"].startswith("Right now I'm")
    assert second["replier"] == {"kind": "rule", "name": "rule_replier"}

    replier.release.set()
    assert replier.finished.wait(5)
    service._replier_pool.submit(lambda: None).result(timeout=5)  # drain the worker
    assert replier.calls == 1  # the second message never reached the provider

    third = c.post("/api/conversation/messages", json=message("3"), headers=AUTH).json()
    assert third["reply"] == "I'm back, thanks for waiting!" and third["fallback_code"] is None
    assert third["replier"] == {"kind": "external", "name": "fake"}
    assert replier.calls == 2

    (k1, f1, l1), (k2, f2, l2), (k3, f3, l3) = audit(tmp_path)
    assert (k1, f1) == ("rule", "timeout") and l1 is not None and l1 >= 1000
    assert (k2, f2) == ("rule", "timeout") and l2 is not None and l2 < 1000
    assert (k3, f3) == ("external", None) and l3 is not None and l3 < 5000
    service.close()
