"""Greet/Pet over HTTP: explicit outcomes, cooldowns, Origin rules, races."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest

from maplegotchi.core.interactions import Accepted
from maplegotchi.core.state import InteractionKind
from maplegotchi.runtime.clock import FakeClock
from tests.api.support import ORIGIN, TRUSTED, make_client, make_service
from tests.persistence_support import BIRTH, TICK


def test_accepted_greet_and_pet(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    client = make_client(service, tmp_path)
    greet = client.post("/api/interactions/greet", headers=TRUSTED)
    assert greet.status_code == 200
    body = greet.json()
    assert (
        body["accepted"] is True and body["reason"] is None and body["retry_after_seconds"] is None
    )
    assert body["reaction"]["kind"] == "greet_happy" and body["revision"] == 2
    availability = {a["kind"]: a for a in body["maple"]["interactions"]}
    assert availability["greet"] == {"kind": "greet", "available": False, "reason": "cooldown",
                                     "retry_after_seconds": 60.0}  # fmt: skip
    pet = client.post("/api/interactions/pet", headers=TRUSTED).json()
    assert pet["accepted"] is True and pet["revision"] == 3
    service.close()


def test_rejected_greet_reports_cooldown_and_changes_nothing(tmp_path: Path) -> None:
    clock = FakeClock(BIRTH)
    service = make_service(tmp_path / "data", clock)
    client = make_client(service, tmp_path)
    client.post("/api/interactions/greet", headers=TRUSTED)
    before = service.runtime.current()
    clock.advance(timedelta(seconds=10))
    rejected = client.post("/api/interactions/greet", headers=TRUSTED)
    assert rejected.status_code == 429
    assert rejected.headers["retry-after"] == "50"
    body = rejected.json()
    assert body["accepted"] is False and body["reason"] == "cooldown"
    assert body["retry_after_seconds"] == 50.0 and body["revision"] == before[1]
    assert service.runtime.current() == before  # no partial mutation
    service.close()


def test_global_rate_limit_through_the_api(tmp_path: Path) -> None:
    clock = FakeClock(BIRTH)
    service = make_service(tmp_path / "data", clock)
    client = make_client(service, tmp_path)
    start = clock.now()
    for i in range(10):
        clock.set(start + timedelta(seconds=30 * i))
        route = "greet" if i % 2 == 0 else "pet"
        assert client.post(f"/api/interactions/{route}", headers=TRUSTED).status_code == 200
    clock.set(start + timedelta(seconds=300))
    limited = client.post("/api/interactions/pet", headers=TRUSTED)
    assert limited.status_code == 429 and limited.json()["reason"] == "rate_limit"
    assert limited.json()["retry_after_seconds"] == 300.0
    service.close()


def test_cooldown_survives_a_restart_through_the_api(tmp_path: Path) -> None:
    clock = FakeClock(BIRTH)
    first = make_service(tmp_path / "data", clock)
    make_client(first, tmp_path).post("/api/interactions/greet", headers=TRUSTED)
    first.close()
    clock.advance(timedelta(seconds=20))
    second = make_service(tmp_path / "data", clock)
    again = make_client(second, tmp_path).post("/api/interactions/greet", headers=TRUSTED)
    assert again.status_code == 429 and again.json()["retry_after_seconds"] == 40.0
    second.close()


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "http://evil.example"},
        {"Origin": "null"},
        {"Origin": ORIGIN + "/"},
        {"Origin": ORIGIN.upper()},
        {"Origin": "http://127.0.0.1:5174"},
        {"Referer": ORIGIN + "/"},  # a Referer is not an Origin
    ],
)
def test_untrusted_origins_are_refused_without_side_effects(
    tmp_path: Path, headers: dict[str, str]
) -> None:
    service = make_service(tmp_path / "data")
    client = make_client(service, tmp_path)
    for route in ("greet", "pet"):
        assert client.post(f"/api/interactions/{route}", headers=headers).status_code == 403
    assert service.runtime.revision == 1
    service.close()


@pytest.mark.parametrize(
    ("body", "headers", "status"),
    [
        (b"feed", {}, 400),
        (b'{"kind": "feed"}', {"content-type": "application/json"}, 400),
        (b'{"message": "hello"}', {"content-type": "application/json"}, 400),
        (b"x" * 5000, {}, 413),
        (b"{}", {"content-type": "application/json"}, 200),
        (b"", {}, 200),
    ],
)
def test_interaction_bodies(
    tmp_path: Path, body: bytes, headers: dict[str, str], status: int
) -> None:
    service = make_service(tmp_path / "data")
    client = make_client(service, tmp_path)
    response = client.post("/api/interactions/greet", content=body, headers={**TRUSTED, **headers})
    assert response.status_code == status
    service.close()


@pytest.mark.parametrize(
    ("method", "path", "status"),
    [
        ("GET", "/api/interactions/greet", 405),
        ("PUT", "/api/interactions/pet", 405),
        ("POST", "/api/interactions/feed", 404),
        ("POST", "/api/interactions/chat", 404),
        ("POST", "/api/interactions", 404),
        ("POST", "/api/snapshot", 405),
        ("POST", "/api/events", 405),
        ("DELETE", "/api/journal", 405),
    ],
)
def test_no_other_mutations_exist(tmp_path: Path, method: str, path: str, status: int) -> None:
    service = make_service(tmp_path / "data")
    client = make_client(service, tmp_path)
    response = client.request(method, path, headers=TRUSTED)
    assert response.status_code in (status, 404)  # refused either way; never a 2xx
    assert service.runtime.revision == 1
    service.close()


# ---------------------------------------------------------------- races


def race(*calls: object, rounds: int = 1) -> list[object]:
    barrier = threading.Barrier(len(calls))

    def run(fn):  # type: ignore[no-untyped-def]
        barrier.wait()
        return fn()

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        return list(pool.map(run, calls))


@pytest.mark.parametrize("attempt", range(5))
def test_two_simultaneous_greets_accept_exactly_one(tmp_path: Path, attempt: int) -> None:
    service = make_service(tmp_path / f"data{attempt}")
    results = race(lambda: service.interact(InteractionKind.GREET),
                   lambda: service.interact(InteractionKind.GREET))  # fmt: skip
    accepted = [r for r in results if isinstance(r.outcome, Accepted)]  # type: ignore[attr-defined]
    assert len(accepted) == 1
    assert service.runtime.state.rng.interaction_counter == 1 and service.runtime.revision == 2
    service.close()


def test_simultaneous_greet_and_pet_both_accepted(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    results = race(lambda: service.interact(InteractionKind.GREET),
                   lambda: service.interact(InteractionKind.PET))  # fmt: skip
    assert all(isinstance(r.outcome, Accepted) for r in results)  # type: ignore[attr-defined]
    assert service.runtime.state.rng.interaction_counter == 2 and service.runtime.revision == 3
    assert len(service.runtime.state.recent_interactions) == 2
    service.close()


def test_heartbeat_and_pet_arriving_together_lose_nothing(tmp_path: Path) -> None:
    clock = FakeClock(BIRTH)
    service = make_service(tmp_path / "data", clock)
    clock.advance(TICK)
    results = race(service.tick, lambda: service.interact(InteractionKind.PET))
    tick, pet = results
    assert tick is not None and isinstance(pet.outcome, Accepted)  # type: ignore[attr-defined]
    state, revision = service.runtime.current()
    assert revision == 3 and state.rng.tick_counter == 1 and state.rng.interaction_counter == 1
    service.runtime.close()
    reopened = make_service(tmp_path / "data", clock)
    assert reopened.runtime.current() == (state, revision)
    reopened.close()


def test_two_greets_over_http_concurrently(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    clients = [make_client(service, tmp_path), make_client(service, tmp_path)]
    codes = race(
        *(
            lambda c=c: c.post("/api/interactions/greet", headers=TRUSTED).status_code
            for c in clients
        )
    )
    assert sorted(codes) == [200, 429]  # type: ignore[type-var]
    service.close()
