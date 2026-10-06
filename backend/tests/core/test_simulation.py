"""30-day fake-time simulation: reproducibility, day/night, invariants."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from functools import cache

import pytest

from maplegotchi.cli import main
from maplegotchi.core.activities import Activity
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.simulation import (
    ScheduledInteraction,
    SimulationReport,
    daily_owner_routine,
    simulate,
)
from maplegotchi.core.state import InteractionKind, birth
from tests.core.support import OTHER_SEED, PARAMS, SEED

START = datetime(2026, 1, 1, tzinfo=UTC)
DAYS = 30


def run(seed: str = SEED, *, owner: bool = True, attention: float = 0.0) -> SimulationReport:
    maple = birth(name="Maple", born_at=START, seed_hex=seed)
    plan = daily_owner_routine(START, DAYS, PARAMS) if owner else ()
    inputs = BehaviorInputs(server_attention=attention)
    return simulate(maple, days=DAYS, params=PARAMS, inputs=inputs, interactions=plan)


@cache
def baseline() -> SimulationReport:
    return run()


def test_thirty_days_is_reproducible() -> None:
    again = run()
    assert again.digest == baseline().digest
    assert again.final_state == baseline().final_state
    assert again == baseline()


def test_thirty_day_digest_is_pinned() -> None:
    # Pinned so CI proves the same life on Linux (paolo-core) and Windows (dev).
    # Any intentional change to behavior rules or rates must update this value.
    assert baseline().digest == "458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917"


def test_different_seed_gives_a_different_life() -> None:
    assert run(OTHER_SEED).digest != baseline().digest


def test_owner_interactions_change_the_life() -> None:
    assert run(owner=False).digest != baseline().digest


def test_thirty_days_runs_quickly_without_waiting() -> None:
    began = time.perf_counter()
    run(OTHER_SEED)
    assert time.perf_counter() - began < 20  # ~0.5 s in practice; generous for CI


def test_tick_count_and_duration() -> None:
    r = baseline()
    assert r.ticks == DAYS * 24 * 12
    assert r.final_state.ticks_lived == r.ticks
    assert r.ended_at - r.started_at == timedelta(days=DAYS)
    assert r.final_state.age(r.ended_at) == timedelta(days=DAYS)
    assert sum(n for _, n in r.activity_ticks) == r.ticks


def test_day_night_rhythm() -> None:
    r = baseline()
    assert r.night_sleep_ratio > 0.85
    assert r.day_sleep_ratio < 0.10


def test_every_activity_occurs_and_transitions_happen() -> None:
    r = baseline()
    assert all(n > 0 for _, n in r.activity_ticks), r.activity_ticks
    assert r.activity_changes > DAYS * 10


def test_needs_evolve_and_stay_in_range() -> None:
    for report in (baseline(), run(owner=False), run(attention=1.0)):
        for name, span in report.need_ranges:
            assert 0.0 <= span.minimum <= span.maximum <= 100.0, name
            assert span.maximum - span.minimum > 5.0, f"{name} never changed"


def test_owner_routine_exercises_limits() -> None:
    r = baseline()
    assert r.interactions_accepted == 4 * DAYS
    assert r.interactions_rejected == DAYS  # the too-early evening pet
    assert r.final_state.rng.interaction_counter == r.interactions_accepted


def test_lonely_maple_social_settles_at_floor() -> None:
    r = run(owner=False)
    social = dict(r.need_ranges)["social"]
    assert social.minimum >= 20.0
    assert r.final_state.needs.social < 25.0


def test_server_attention_increases_observing() -> None:
    calm = dict(baseline().activity_ticks)[Activity.OBSERVE_SERVER]
    alert = dict(run(attention=1.0).activity_ticks)[Activity.OBSERVE_SERVER]
    assert alert > calm * 2


def test_shorter_interval_works() -> None:
    params = CoreParameters(heartbeat_interval=timedelta(seconds=60))
    maple = birth(name="Maple", born_at=START, seed_hex=SEED)
    r = simulate(maple, days=2, params=params)
    assert r.ticks == 2 * 24 * 60


def test_simulate_validates_arguments() -> None:
    maple = birth(name="Maple", born_at=START, seed_hex=SEED)
    with pytest.raises(ValueError):
        simulate(maple, days=0, params=PARAMS)
    outside = [ScheduledInteraction(START + timedelta(days=2), InteractionKind.GREET)]
    with pytest.raises(ValueError):
        simulate(maple, days=1, params=PARAMS, interactions=outside)


def test_cli_simulate_is_reproducible(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["simulate", "--days", "2"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert main(["simulate", "--days", "2"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert first == second
    assert first["ticks"] == 2 * 288
