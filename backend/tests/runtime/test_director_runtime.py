"""The Director through the service (ADR-0026 §2-§3): outside the lock, failure-safe."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from maplegotchi.brain.director import DirectorKind
from maplegotchi.brain.rule_brain import RuleBrain
from maplegotchi.config import DirectorMode, Settings, SettingsError
from maplegotchi.core.audit import DecisionRecord, Verdict
from maplegotchi.core.goals import GoalSource
from maplegotchi.core.proposal import CONTRACT, DecisionContext
from maplegotchi.runtime.brain_factory import build_director
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.external_director import ExternalHttpDirector
from maplegotchi.runtime.service import (
    DirectorNotAllowed,
    MapleService,
    fake_senses,
    require_supported_director,
)
from tests.persistence_support import BIRTH, PARAMS, make_data_dir, open_runtime

GOOD = {
    "goal": {
        "op": "new",
        "type": "create",
        "summary": "Write a small poem",
        "horizon_minutes": 45,
    },
    "action": {"kind": "write", "duration_minutes": 20},
    "reason": "A calm afternoon suits writing.",
}


class FakeDirector:
    kind = DirectorKind.EXTERNAL
    name = "fake"
    version = "1"

    def __init__(self, answer: Callable[[DecisionContext], object | None]) -> None:
        self.answer = answer
        self.contexts: list[DecisionContext] = []

    def propose_decision(self, context: DecisionContext) -> object | None:
        self.contexts.append(context)
        return self.answer(context)


def service_with(
    tmp_path: Path, director: Any, timeout: float = 2.0, name: str = "maple-data"
) -> MapleService:
    data_dir = make_data_dir(tmp_path, name)
    clock = FakeClock(BIRTH)
    runtime = open_runtime(data_dir, clock)
    return MapleService(
        runtime, fake_senses(), clock, PARAMS, director=director, director_timeout_seconds=timeout
    )


def due(service: MapleService) -> None:
    service.clock.advance(timedelta(minutes=16))  # type: ignore[attr-defined]
    assert service.runtime.decision_is_due()


def last_decision(service: MapleService) -> DecisionRecord:
    return service.runtime.decisions(limit=1)[-1].record


def test_an_accepted_proposal_becomes_maples_next_action(tmp_path: Path) -> None:
    director = FakeDirector(lambda ctx: GOOD)
    service = service_with(tmp_path, director)
    due(service)
    service.decide()
    state = service.runtime.state
    assert state.activity.value == "write"
    assert state.goal is not None and state.goal.source is GoalSource.EXTERNAL
    record = last_decision(service)
    assert record.verdict is Verdict.ACCEPTED and record.director_name == "fake"
    assert record.latency_ms is not None
    assert director.contexts[0].as_json()["contract"] == CONTRACT
    assert service.snapshot().director.name == "fake"
    service.close()


def test_the_director_is_called_outside_the_writer_lock(tmp_path: Path) -> None:
    held: list[bool] = []
    service: MapleService

    def answer(ctx: DecisionContext) -> object:
        lock = service.runtime._lock
        free = lock.acquire(blocking=False)
        if free:
            lock.release()
        held.append(not free)
        return GOOD

    service = service_with(tmp_path, FakeDirector(answer))
    due(service)
    service.decide()
    assert held == [False]
    service.close()


def test_a_failing_director_never_stops_maple(tmp_path: Path) -> None:
    def explode(ctx: DecisionContext) -> object:
        raise RuntimeError("companion crashed")

    service = service_with(tmp_path, FakeDirector(explode))
    due(service)
    service.step()  # must not raise
    record = last_decision(service)
    assert (record.verdict, record.reason_code) == (Verdict.FALLBACK, "transport_error")
    assert service.runtime.state.goal is not None  # rule direction took over
    service.close()


def test_a_slow_director_times_out_into_a_fallback(tmp_path: Path) -> None:
    release = threading.Event()

    def slow(ctx: DecisionContext) -> object:
        release.wait(5)
        return GOOD

    service = service_with(tmp_path, FakeDirector(slow), timeout=0.2)
    due(service)
    started = time.perf_counter()
    service.decide()
    assert time.perf_counter() - started < 3
    record = last_decision(service)
    assert (record.verdict, record.reason_code) == (Verdict.FALLBACK, "timeout")
    release.set()
    service.close()


def test_no_proposal_and_invalid_proposals_fall_back(tmp_path: Path) -> None:
    service = service_with(tmp_path, FakeDirector(lambda ctx: None))
    due(service)
    service.decide()
    assert last_decision(service).reason_code == "no_proposal"
    service.close()
    other = service_with(tmp_path, FakeDirector(lambda ctx: {"run": "rm -rf /"}), name="b")
    due(other)
    other.decide()
    record = last_decision(other)
    assert (record.verdict, record.reason_code) == (Verdict.REJECTED, "malformed")
    other.close()


def test_a_hostile_director_cannot_change_the_context_or_state(tmp_path: Path) -> None:
    def hostile(ctx: DecisionContext) -> object:
        ctx.data["needs"]["energy"] = 100.0
        return GOOD

    service = service_with(tmp_path, FakeDirector(hostile))
    before = service.runtime.state
    due(service)
    service.decide()
    record = last_decision(service)
    assert (record.verdict, record.reason_code) == (Verdict.FALLBACK, "transport_error")
    assert service.runtime.state.needs.energy <= before.needs.energy  # evolved, not set
    service.close()


def test_a_proposal_that_arrives_after_the_decision_is_recorded_stale(tmp_path: Path) -> None:
    service: MapleService

    def late(ctx: DecisionContext) -> object:
        service.runtime.decide_committed()  # someone else decided meanwhile
        return GOOD

    service = service_with(tmp_path, FakeDirector(late))
    due(service)
    service.decide()
    record = last_decision(service)
    assert record.verdict is Verdict.STALE and record.executed is None
    assert record.proposal is not None and record.proposal.reason == GOOD["reason"]
    assert service.runtime.state.goal is not None
    assert service.runtime.state.goal.source is GoalSource.RULE  # the stale one changed nothing
    service.close()


def test_only_external_directors_can_be_wired() -> None:
    with pytest.raises(DirectorNotAllowed):
        require_supported_director(RuleBrain())  # type: ignore[arg-type]

    class Impostor:
        kind = "rule"
        name = "rule_director"
        version = "1"

        def propose_decision(self, ctx: DecisionContext) -> object:
            return GOOD

    with pytest.raises(DirectorNotAllowed):
        require_supported_director(Impostor())  # type: ignore[arg-type]
    assert require_supported_director(None) is None


def test_settings_select_the_director(tmp_path: Path) -> None:
    rule = Settings(data_dir=tmp_path)
    assert rule.director is DirectorMode.RULE and build_director(rule) is None
    ag = Settings(data_dir=tmp_path, director=DirectorMode.ANTIGRAVITY)
    director = build_director(ag)
    assert isinstance(director, ExternalHttpDirector)
    with pytest.raises(SettingsError):
        Settings(data_dir=tmp_path, director=DirectorMode.ANTIGRAVITY,
                 brain_url="http://example.com:8471")  # fmt: skip
    with pytest.raises(SettingsError):
        Settings(data_dir=tmp_path, director_timeout_seconds=60)


class FakeResponse:
    def __init__(self, payload: object, size: int = 100) -> None:
        self.payload = payload
        self.content = b"x" * size

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


def test_http_director_posts_the_contract_to_decide(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def post(url: str, **kwargs: Any) -> FakeResponse:
        captured.update(url=url, **kwargs)
        return FakeResponse({"contract": CONTRACT, "proposal": GOOD})

    monkeypatch.setattr("maplegotchi.runtime.external_director.httpx2.post", post)
    director = ExternalHttpDirector(base_url="http://127.0.0.1:8471/", timeout_seconds=15)
    from maplegotchi.core.proposal import DecisionContext as Ctx

    assert director.propose_decision(Ctx({"contract": CONTRACT})) == GOOD
    assert captured["url"] == "http://127.0.0.1:8471/decide"
    assert captured["json"]["contract"] == CONTRACT
    assert captured["timeout"] == 15 and captured["follow_redirects"] is False


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse({"proposal": GOOD}),  # no contract
        FakeResponse({"contract": "other.v9", "proposal": GOOD}),
        FakeResponse({"contract": CONTRACT, "proposal": GOOD, "debug": "thoughts"}),
        FakeResponse({"contract": CONTRACT, "proposal": GOOD}, size=20_000),
        FakeResponse(["not", "an", "object"]),
    ],
)
def test_http_director_refuses_unusable_responses(
    monkeypatch: pytest.MonkeyPatch, response: FakeResponse
) -> None:
    monkeypatch.setattr(
        "maplegotchi.runtime.external_director.httpx2.post", lambda url, **kw: response
    )
    director = ExternalHttpDirector(base_url="http://127.0.0.1:8471")
    from maplegotchi.core.proposal import DecisionContext as Ctx
    from maplegotchi.runtime.external_director import DirectorResponseError

    with pytest.raises(DirectorResponseError):
        director.propose_decision(Ctx({}))
