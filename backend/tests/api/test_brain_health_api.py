"""GET /api/brain-health (ADR-0034): read-only, from stored audit rows, honest when unknown."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient

from maplegotchi.api.app import create_app
from maplegotchi.brain.director import DirectorKind
from maplegotchi.core.proposal import DecisionContext
from maplegotchi.runtime.brain_health import (
    PROBE_TIMEOUT_SECONDS,
    CompanionHealth,
    probe_companion,
)
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.service import MapleService, fake_senses
from tests.api.support import make_settings
from tests.api.test_conversation_api import AUTH, TOKEN, FakeReplier, message
from tests.persistence_support import BIRTH, PARAMS, make_data_dir, open_runtime

GOOD = {
    "goal": {"op": "new", "type": "create", "summary": "Write a poem", "horizon_minutes": 45},
    "action": {"kind": "write", "duration_minutes": 20},
    "reason": "A calm afternoon suits writing.",
}
REACHABLE = CompanionHealth(reachable=True, provider="command", model="gemini-3.8-flash-medium")


class FakeDirector:
    kind = DirectorKind.EXTERNAL
    name = "fake_director"
    version = "1"

    def __init__(self) -> None:
        self.answer: Callable[[], object | None] = lambda: GOOD

    def propose_decision(self, context: DecisionContext) -> object | None:
        return self.answer()


class Probe:
    def __init__(self, result: CompanionHealth = REACHABLE) -> None:
        self.result = result
        self.calls = 0

    def __call__(self) -> CompanionHealth:
        self.calls += 1
        return self.result


def setup(
    tmp_path: Path,
    *,
    director: Any = None,
    replier: Any = None,
    probe: Probe | None = None,
    clock: FakeClock | None = None,
) -> tuple[TestClient, MapleService]:
    clock = clock or FakeClock(BIRTH)
    runtime = open_runtime(make_data_dir(tmp_path), clock)
    service = MapleService(runtime, fake_senses(), clock, PARAMS, director=director,
                           replier=replier, director_timeout_seconds=2.0,
                           companion_probe=probe)  # fmt: skip
    app = create_app(service, make_settings(tmp_path, gateway_token=TOKEN), run_life_loop=False)
    return TestClient(app), service


def next_decision(service: MapleService) -> None:
    """Advance fake time until a decision is due, then make it through the Director."""
    clock: FakeClock = service.clock  # type: ignore[assignment]
    for _ in range(600):
        clock.advance(timedelta(minutes=1))
        service.settle()
        if service.runtime.decision_is_due():
            service.decide()
            return
    raise AssertionError("no decision became due")


def health(c: TestClient) -> dict[str, Any]:
    response = c.get("/api/brain-health")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body: dict[str, Any] = response.json()
    return body


def test_all_rule_modes_are_unknown_and_the_companion_is_not_probed(tmp_path: Path) -> None:
    probe = Probe()
    c, service = setup(tmp_path, probe=probe)
    body = health(c)
    assert (body["status"], body["status_reason"]) == ("unknown", "not_configured")
    assert body["companion"] == {"probed": False, "reachable": None, "error": None}
    assert body["provider"] is None and body["model"] is None
    assert body["director"]["mode"] == "rule" and body["replier"]["mode"] == "rule"
    assert body["journal_brain"] == "rule"
    assert probe.calls == 0
    service.close()


def test_reachable_without_calls_is_unknown_not_a_failure(tmp_path: Path) -> None:
    c, service = setup(tmp_path, director=FakeDirector(), probe=Probe())
    body = health(c)
    assert (body["status"], body["status_reason"]) == ("unknown", "no_calls_yet")
    assert body["provider"] == "command" and body["model"] == "gemini-3.8-flash-medium"
    assert body["director"] == {
        "mode": "external",
        "name": "fake_director",
        "last_call": None,
        "last_success_at": None,
        "fallbacks_today": 0,
        "timeouts_today": 0,
    }
    assert body["last_success_at"] is None
    service.close()


def test_unreachable_companion_is_offline(tmp_path: Path) -> None:
    director = FakeDirector()
    probe = Probe(CompanionHealth(reachable=False, error="timeout"))
    c, service = setup(tmp_path, director=director, probe=probe)
    next_decision(service)
    body = health(c)
    assert (body["status"], body["status_reason"]) == ("offline", "companion_unreachable")
    assert body["companion"] == {"probed": True, "reachable": False, "error": "timeout"}
    assert body["provider"] is None and body["model"] is None  # never guessed
    assert body["director"]["last_call"]["ok"] is True  # history is still shown
    service.close()


def test_director_history_drives_healthy_and_degraded(tmp_path: Path) -> None:
    director = FakeDirector()
    c, service = setup(tmp_path, director=director, probe=Probe())
    next_decision(service)
    body = health(c)
    assert body["status"] == "healthy"
    last = body["director"]["last_call"]
    assert last["ok"] is True and last["code"] is None and last["latency_ms"] is not None
    assert body["director"]["last_success_at"] == last["at"] == body["last_success_at"]

    director.answer = lambda: None  # no proposal: rule fallback
    next_decision(service)
    body = health(c)
    assert (body["status"], body["status_reason"]) == ("degraded", "latest_call_failed")
    assert body["director"]["last_call"]["code"] == "no_proposal"
    assert (body["director"]["fallbacks_today"], body["director"]["timeouts_today"]) == (1, 0)

    def unreachable() -> object:
        raise httpx2.ConnectError("refused")

    def slow() -> object:
        raise httpx2.ReadTimeout("slow")

    for answer in (unreachable, slow):
        director.answer = answer
        next_decision(service)
    body = health(c)
    assert body["director"]["last_call"]["code"] == "timeout"
    assert (body["director"]["fallbacks_today"], body["director"]["timeouts_today"]) == (3, 2)

    director.answer = lambda: GOOD
    next_decision(service)
    body = health(c)
    assert body["status"] == "healthy"
    assert body["director"]["fallbacks_today"] == 3  # today's counts are kept
    service.close()


def test_replier_history_and_the_latest_call_across_callers(tmp_path: Path) -> None:
    director, replier = FakeDirector(), FakeReplier(RuntimeError("down"))
    c, service = setup(tmp_path, director=director, replier=replier, probe=Probe())
    next_decision(service)  # Director ok
    c.post("/api/conversation/messages", json=message("1"), headers=AUTH)  # then reply fails
    body = health(c)
    assert body["status"] == "degraded"
    assert body["replier"]["mode"] == "external" and body["replier"]["name"] == "fake"
    last = body["replier"]["last_call"]
    assert last["ok"] is False and last["code"] == "transport_error"
    assert last["latency_ms"] is not None
    assert (body["replier"]["fallbacks_today"], body["replier"]["timeouts_today"]) == (1, 1)

    replier.answer = "All quiet here, thanks!"
    c.post("/api/conversation/messages", json=message("2"), headers=AUTH)
    body = health(c)
    assert body["status"] == "healthy"
    assert body["replier"]["last_success_at"] == body["replier"]["last_call"]["at"]
    assert body["last_success_at"] == body["replier"]["last_success_at"]
    service.close()


def test_rule_replies_are_not_ai_calls(tmp_path: Path) -> None:
    c, service = setup(tmp_path, director=FakeDirector(), probe=Probe())
    c.post("/api/conversation/messages", json=message(), headers=AUTH)
    body = health(c)
    assert body["replier"]["last_call"] is None and body["status"] == "unknown"
    service.close()


def test_today_resets_at_the_maple_day_boundary(tmp_path: Path) -> None:
    # BIRTH is 07:00 local (+07:00); the Maple day ends at 06:00 local = 23:00 UTC.
    clock = FakeClock(BIRTH)
    replier = FakeReplier(RuntimeError("down"))
    c, service = setup(tmp_path, replier=replier, probe=Probe(), clock=clock)
    clock.advance(timedelta(hours=22, minutes=59, seconds=59))  # 05:59:59 local
    c.post("/api/conversation/messages", json=message("1"), headers=AUTH)
    body = health(c)
    assert body["today"]["day"] == "2026-01-01"
    assert body["today"]["start"] == "2025-12-31T23:00:00Z"
    assert body["today"]["end"] == "2026-01-01T23:00:00Z"
    assert body["replier"]["fallbacks_today"] == 1

    clock.advance(timedelta(seconds=2))  # 06:00:01 local: a new Maple day
    body = health(c)
    assert body["today"]["day"] == "2026-01-02"
    assert body["replier"]["fallbacks_today"] == 0
    assert body["replier"]["last_call"]["ok"] is False  # the latest call is still shown
    assert body["status"] == "degraded"
    service.close()


def test_brain_health_is_read_only(tmp_path: Path) -> None:
    c, service = setup(tmp_path, director=FakeDirector(), probe=Probe())
    next_decision(service)
    db = tmp_path / "maple-data" / "maple.db"

    def counts() -> tuple[int, ...]:
        conn = sqlite3.connect(db)
        try:
            tables = ("decision", "conversation_message", "timeline_event", "life_state")
            return tuple(conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables)  # noqa: S608
        finally:
            conn.close()

    revision, before = service.runtime.revision, counts()
    for _ in range(3):
        health(c)
    assert service.runtime.revision == revision and counts() == before
    assert c.post("/api/brain-health").status_code == 405
    service.close()


def test_no_secrets_or_extra_companion_fields_are_exposed(tmp_path: Path) -> None:
    leaky = {
        "status": "ok",
        "provider": "command",
        "model": "m-1",
        "command": ["/usr/local/bin/agy", "--token=SECRET"],
        "oauth": {"refresh_token": "SECRET"},
        "prompt": "SECRET",
    }
    health_result = probe_companion("http://127.0.0.1:8471", get=lambda *a, **k: _resp(200, leaky))
    c, service = setup(tmp_path, director=FakeDirector(), probe=Probe(health_result))
    raw = c.get("/api/brain-health").text
    assert "SECRET" not in raw and "agy" not in raw and "oauth" not in raw
    assert json.loads(raw)["model"] == "m-1"
    service.close()


# ---------------------------------------------------------------- the probe


class _Resp:
    def __init__(self, status: int, body: bytes) -> None:
        self.status_code = status
        self.content = body

    def json(self) -> Any:
        return json.loads(self.content)


def _resp(status: int, payload: Any) -> _Resp:
    return _Resp(status, json.dumps(payload).encode())


def _raises(exc: Exception) -> Callable[..., Any]:
    def get(*args: Any, **kwargs: Any) -> Any:
        raise exc

    return get


@pytest.mark.parametrize(
    ("get", "error"),
    [
        (_raises(httpx2.ConnectTimeout("slow")), "timeout"),
        (_raises(httpx2.ConnectError("refused")), "unreachable"),
        (_raises(OSError("boom")), "unreachable"),
        (lambda *a, **k: _resp(500, {"status": "ok"}), "http_status"),
        (lambda *a, **k: _Resp(200, b"not json"), "invalid_response"),
        (lambda *a, **k: _resp(200, ["ok"]), "invalid_response"),
        (lambda *a, **k: _resp(200, {"status": "starting"}), "invalid_response"),
        (lambda *a, **k: _Resp(200, b" " * 5000), "invalid_response"),
    ],
)
def test_probe_failures_are_reported_never_raised(get: Callable[..., Any], error: str) -> None:
    assert probe_companion("http://127.0.0.1:8471", get=get) == CompanionHealth(
        reachable=False, error=error
    )


def test_probe_is_one_bounded_get_without_redirects() -> None:
    seen: list[tuple[str, dict[str, Any]]] = []

    def get(url: str, **kwargs: Any) -> _Resp:
        seen.append((url, kwargs))
        return _resp(200, {"status": "ok", "provider": "command", "model": None})

    result = probe_companion("http://127.0.0.1:8471/", get=get)
    assert result == CompanionHealth(reachable=True, provider="command", model=None)
    assert seen == [
        (
            "http://127.0.0.1:8471/health",
            {"timeout": PROBE_TIMEOUT_SECONDS, "follow_redirects": False},
        )
    ]
    assert PROBE_TIMEOUT_SECONDS <= 2.0


@pytest.mark.parametrize("value", ["/usr/bin/agy --token=x", "", 7, "x" * 65, "a\nb", None])
def test_only_short_identifiers_pass_as_provider_or_model(value: object) -> None:
    payload = {"status": "ok", "provider": value, "model": value}
    result = probe_companion("http://127.0.0.1:8471", get=lambda *a, **k: _resp(200, payload))
    assert result == CompanionHealth(reachable=True, provider=None, model=None)


def test_a_closed_loopback_port_is_offline_quickly() -> None:
    result = probe_companion("http://127.0.0.1:9", timeout_seconds=1.0)
    assert result.reachable is False and result.error in ("unreachable", "timeout")
