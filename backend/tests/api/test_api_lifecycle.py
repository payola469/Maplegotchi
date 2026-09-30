"""The life loop inside the app, and continuity across process restarts via the API."""

from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from maplegotchi.api.app import create_app
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.senses import Senses
from tests.api.support import TRUSTED, make_client, make_service, make_settings
from tests.persistence_support import BIRTH, TICK


def wait_until(condition, timeout: float = 10.0) -> None:  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached")
        time.sleep(0.02)


def test_life_loop_runs_with_the_app_and_stops_with_it(tmp_path: Path) -> None:
    clock = FakeClock(BIRTH)
    service = make_service(tmp_path / "data", clock)
    app = create_app(service, make_settings(tmp_path, loop_poll_seconds=0.01))
    with TestClient(app) as client:
        assert client.get("/api/status").json()["freshness"]["life_loop_running"] is True
        clock.advance(TICK)
        wait_until(lambda: service.runtime.state.ticks_lived == 1)
        clock.advance(TICK)
        wait_until(lambda: service.runtime.state.ticks_lived == 2)
        status = client.get("/api/status").json()["freshness"]
        assert status["heartbeat_status"] == "fresh" and status["sensor_status"] == "fresh"
    assert service.snapshot().freshness.life_loop_running is False
    service.close()


def test_life_loop_fails_soft_and_reports_the_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = FakeClock(BIRTH)
    service = make_service(tmp_path / "data", clock)

    def broken(self: Senses, now: object) -> object:
        raise RuntimeError("sensor bus exploded")

    monkeypatch.setattr(Senses, "observe", broken)
    app = create_app(service, make_settings(tmp_path, loop_poll_seconds=0.01))
    with TestClient(app) as client:
        clock.advance(TICK)
        wait_until(
            lambda: client.get("/api/status").json()["freshness"]["life_loop_error"] is not None
        )
        freshness = client.get("/api/status").json()["freshness"]
        assert freshness["life_loop_error"] == "RuntimeError"
        assert freshness["life_loop_running"] is True  # still alive, still trying
        clock.advance(TICK + timedelta(minutes=2))
        assert client.get("/api/status").json()["freshness"]["heartbeat_status"] == "overdue"
        monkeypatch.undo()
        wait_until(lambda: service.runtime.state.ticks_lived == 1)
        assert client.get("/api/status").json()["freshness"]["life_loop_error"] is None
    service.close()


def test_same_maple_continues_after_restart_through_the_api(tmp_path: Path) -> None:
    clock = FakeClock(BIRTH)
    first = make_service(tmp_path / "data", clock)
    client = make_client(first, tmp_path)
    clock.advance(TICK)
    first.tick()
    client.post("/api/interactions/greet", headers=TRUSTED)  # cooldown runs into the restart
    before = client.get("/api/snapshot").json()
    first.close()

    clock.advance(timedelta(seconds=10))
    second = make_service(tmp_path / "data", clock)
    client = make_client(second, tmp_path)
    after = client.get("/api/snapshot").json()
    assert after["maple"]["identity"]["name"] == before["maple"]["identity"]["name"]
    assert after["maple"]["identity"]["born_at"] == before["maple"]["identity"]["born_at"]
    assert after["revision"] == before["revision"]
    assert after["maple"]["needs"] == before["maple"]["needs"]
    assert after["journal"] == before["journal"] and after["timeline"] == before["timeline"]
    greet = client.post("/api/interactions/greet", headers=TRUSTED)
    assert greet.status_code == 429  # the cooldown came back with Maple
    clock.advance(timedelta(minutes=1))
    assert (
        client.post("/api/interactions/greet", headers=TRUSTED).json()["revision"]
        == before["revision"] + 1
    )
    second.close()
