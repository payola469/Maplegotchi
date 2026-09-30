"""Continuity proofs: a life with restarts is identical to a life without them.

Three ways to live the same script of heartbeats and Greet/Pet:
  pure      core only, in memory, never persisted
  runtime   the persisted single-writer runtime, never restarted
  restarts  the persisted runtime, closed and reopened at chosen steps
All three must end in the same canonical state with the same RNG counters and
the same timeline.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import cache
from pathlib import Path

import pytest

from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.heartbeat import heartbeat
from maplegotchi.core.interactions import Accepted, Rejected, apply_interaction
from maplegotchi.core.simulation import daily_owner_routine
from maplegotchi.core.state import InteractionKind, MapleState, birth
from maplegotchi.core.timeline import Born, LifeEvent
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.life import LifeRuntime
from tests.persistence_support import BIRTH, PARAMS, SEED, TICK, make_data_dir, open_runtime

DAYS = 3
N_TICKS = DAYS * 288  # 864 heartbeats
Step = tuple[datetime, InteractionKind | None]  # None = heartbeat


@cache
def script() -> tuple[Step, ...]:
    ticks: list[Step] = [(BIRTH + TICK * i, None) for i in range(1, N_TICKS + 1)]
    owner: list[Step] = [(s.at, s.kind) for s in daily_owner_routine(BIRTH, DAYS, PARAMS)]
    # Extra pressure on the limits: a burst that hits cooldowns and the global cap.
    burst_start = BIRTH + timedelta(days=1, hours=5, seconds=7)

    # Alternating Greet/Pet every 31 s respects both cooldowns, so the 11th hits the
    # global cap; a same-kind retry 5 s after the first few hits the cooldowns.
    def kind_at(i: int) -> InteractionKind:
        return InteractionKind.GREET if i % 2 == 0 else InteractionKind.PET

    owner += [(burst_start + timedelta(seconds=31 * i), kind_at(i)) for i in range(24)]
    owner += [(burst_start + timedelta(seconds=31 * i + 5), kind_at(i)) for i in range(3)]
    # Interactions sort before a heartbeat at the same instant (None sorts last).
    return tuple(sorted(ticks + owner, key=lambda s: (s[0], s[1] is None)))


Outcome = tuple[str, object]


def live_pure() -> tuple[MapleState, list[LifeEvent], list[Outcome]]:
    state = birth(name="Maple", born_at=BIRTH, seed_hex=SEED)
    events: list[LifeEvent] = [Born(at=BIRTH, name="Maple")]
    outcomes: list[Outcome] = []
    for at, kind in script():
        if kind is None:
            result = heartbeat(state, at, BehaviorInputs(), PARAMS)
            state = result.state
            events.extend(result.events)
            outcomes.append(("tick", result.tick_id))
        else:
            outcome = apply_interaction(state, kind, at, PARAMS)
            if isinstance(outcome, Accepted):
                state = outcome.state
                events.append(outcome.event)
            outcomes.append((kind.value, outcome if isinstance(outcome, Rejected) else "ok"))
    return state, events, outcomes


def live_runtime(
    tmp_path: Path, restart_before: set[int]
) -> tuple[MapleState, list[LifeEvent], list[Outcome], int, int]:
    data_dir = make_data_dir(tmp_path)
    clock = FakeClock(BIRTH)
    runtime: LifeRuntime = open_runtime(data_dir, clock)
    outcomes: list[Outcome] = []
    restarts = 0
    for index, (at, kind) in enumerate(script()):
        if index in restart_before:
            runtime.close()
            runtime = open_runtime(data_dir, clock)
            restarts += 1
        clock.set(at)
        if kind is None:
            result = runtime.heartbeat_if_due()
            assert result is not None, f"heartbeat not due at step {index}"
            outcomes.append(("tick", result.tick_id))
        else:
            outcome = runtime.interact(kind)
            outcomes.append((kind.value, outcome if isinstance(outcome, Rejected) else "ok"))
    state, revision = runtime.state, runtime.revision
    events = [e.event for e in runtime.timeline()]
    runtime.close()
    with open_runtime(data_dir, clock) as reloaded:  # the final state also survives a restart
        assert reloaded.state == state
    return state, events, outcomes, revision, restarts


@cache
def pure() -> tuple[MapleState, list[LifeEvent], list[Outcome]]:
    return live_pure()


def test_script_exercises_ticks_and_limits() -> None:
    _, _, outcomes = pure()
    assert sum(o[0] == "tick" for o in outcomes) == N_TICKS
    rejected = [o for o in outcomes if isinstance(o[1], Rejected)]
    reasons = {o[1].reason.value for o in rejected if isinstance(o[1], Rejected)}
    assert reasons == {"cooldown", "rate_limit"}


def test_continuous_runtime_equals_pure_core(tmp_path: Path) -> None:
    state, events, outcomes, revision, _ = live_runtime(tmp_path, set())
    p_state, p_events, p_outcomes = pure()
    assert state == p_state
    assert events == p_events
    assert outcomes == p_outcomes
    accepted = sum(o[1] == "ok" for o in outcomes)
    assert revision == 1 + N_TICKS + accepted


STEPS = len(script())
RESTART_PLANS = {
    "after first step": {1},
    "after 7 steps": {7},
    "after one day": {290},
    "during the burst": {
        next(i for i, s in enumerate(script()) if s[1] and s[0].hour == 5 and s[0].day == 2) + 3
    },
    "one before the end": {STEPS - 1},
    "every 97 steps": set(range(97, STEPS, 97)),
    "every 5 steps": set(range(5, STEPS, 5)),
}


@pytest.mark.parametrize("plan", sorted(RESTART_PLANS))
def test_restarted_life_is_identical(tmp_path: Path, plan: str) -> None:
    state, events, outcomes, _, restarts = live_runtime(tmp_path, RESTART_PLANS[plan])
    assert restarts == len(RESTART_PLANS[plan])
    p_state, p_events, p_outcomes = pure()
    assert state == p_state
    assert state.rng == p_state.rng  # seed, tick counter, interaction counter
    assert events == p_events
    assert outcomes == p_outcomes  # including every cooldown / rate-limit rejection


def test_rng_continues_across_restart_after_many_draws(tmp_path: Path) -> None:
    from maplegotchi.core.rng import RngStream

    state, _, _, _, _ = live_runtime(tmp_path, {STEPS // 2})
    p_state, _, _ = pure()
    assert state.rng.tick_counter == N_TICKS
    nxt = state.rng.tick_counter + 1
    after_restart = [RngStream(state.rng.seed_hex, "tick", nxt).random() for _ in range(5)]
    continuous = [RngStream(p_state.rng.seed_hex, "tick", nxt).random() for _ in range(5)]
    assert after_restart == continuous
