"""Single-writer runtime: scheduling, serialization, failures, restarts, downtime."""

from __future__ import annotations

import shutil
import threading
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.heartbeat import evolve_needs
from maplegotchi.core.interactions import Accepted, Rejected, RejectionReason
from maplegotchi.core.state import Expression, InteractionKind
from maplegotchi.core.timeline import DowntimeGap, InteractionAccepted
from maplegotchi.runtime import life as life_module
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.life import LifeRuntime, RuntimeClosedError
from maplegotchi.storage.datadir import DataDir
from maplegotchi.storage.errors import ConcurrentWriteError
from tests.persistence_support import (
    BIRTH,
    PARAMS,
    TICK,
    make_data_dir,
    new_life,
    open_runtime,
    raw_db,
    run_ticks,
)

GREET = InteractionKind.GREET
PET = InteractionKind.PET


def secs(n: float) -> timedelta:
    return timedelta(seconds=n)


# ---------------------------------------------------------------- scheduling


def test_heartbeat_runs_only_when_due(tmp_path: Path) -> None:
    _, clock, runtime = new_life(tmp_path)
    with runtime:
        clock.advance(TICK - secs(1))
        assert runtime.heartbeat_if_due() is None
        clock.advance(secs(1))
        result = runtime.heartbeat_if_due()
        assert result is not None and result.tick_id == 1
        assert runtime.heartbeat_if_due() is None  # not due again yet
        assert runtime.revision == 2


def test_clock_stepping_backwards_never_rewinds_life(tmp_path: Path) -> None:
    _, clock, runtime = new_life(tmp_path)
    with runtime:
        run_ticks(runtime, clock, 3)
        latest = runtime.state.last_updated_at
        clock.set(latest - timedelta(hours=1))
        assert runtime.heartbeat_if_due() is None
        outcome = runtime.interact(GREET)
        assert isinstance(outcome, Accepted)
        assert outcome.state.last_updated_at == latest  # acted at the latest known time


def test_rejections_are_not_persisted(tmp_path: Path) -> None:
    _, _, runtime = new_life(tmp_path)
    with runtime:
        runtime.interact(GREET)
        revision = runtime.revision
        assert isinstance(runtime.interact(GREET), Rejected)
        assert runtime.revision == revision


def test_closed_runtime_refuses_work(tmp_path: Path) -> None:
    _, _, runtime = new_life(tmp_path)
    runtime.close()
    runtime.close()  # idempotent
    with pytest.raises(RuntimeClosedError):
        runtime.interact(GREET)
    with pytest.raises(RuntimeClosedError):
        runtime.heartbeat_if_due()


# ---------------------------------------------------------------- failures


def test_exception_inside_transition_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 2)
    before, revision = runtime.state, runtime.revision

    def broken(*args: object, **kwargs: object) -> None:
        raise ValueError("bug in a transition")

    monkeypatch.setattr(life_module, "heartbeat", broken)
    clock.advance(TICK)
    with pytest.raises(ValueError):
        runtime.heartbeat_if_due()
    assert runtime.state == before and runtime.revision == revision
    monkeypatch.undo()
    assert runtime.heartbeat_if_due() is not None  # lock was released; life goes on
    runtime.close()
    with open_runtime(data_dir, clock) as reloaded:
        assert reloaded.revision == revision + 1


def test_second_writer_on_same_database_fails_loudly(tmp_path: Path) -> None:
    data_dir, clock, first = new_life(tmp_path)
    second = open_runtime(data_dir, clock)
    with first, second:
        assert isinstance(first.interact(GREET), Accepted)
        before = second.state
        with pytest.raises(ConcurrentWriteError):
            second.interact(PET)
        assert second.state == before


class TickingClock(FakeClock):
    """Every read advances one second, so concurrent callers see distinct times."""

    def now(self) -> datetime:
        return self.advance(secs(1))


def test_concurrent_heartbeats_and_interactions_lose_no_updates(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    clock = TickingClock(BIRTH)
    runtime = LifeRuntime.open(data_dir, clock, PARAMS, new_seed=lambda: "ab" * 32)
    accepted: list[Accepted] = []
    ticks: list[int] = []
    guard = threading.Lock()

    def interactor(kind: InteractionKind) -> None:
        for _ in range(150):
            outcome = runtime.interact(kind)
            if isinstance(outcome, Accepted):
                with guard:
                    accepted.append(outcome)

    def ticker() -> None:
        for _ in range(150):
            clock.advance(TICK)
            result = runtime.heartbeat_if_due()
            if result is not None:
                with guard:
                    ticks.append(result.tick_id)

    threads = [threading.Thread(target=interactor, args=(k,)) for k in (GREET, PET, GREET, PET)]
    threads += [threading.Thread(target=ticker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    state = runtime.state
    assert accepted and ticks
    assert sorted(ticks) == list(range(1, len(ticks) + 1))  # no tick id reused or skipped
    assert state.rng.tick_counter == len(ticks)
    assert state.rng.interaction_counter == len(accepted)
    assert runtime.revision == 1 + len(ticks) + len(accepted)
    stored = runtime.timeline()
    assert sum(isinstance(e.event, InteractionAccepted) for e in stored) == len(accepted)
    runtime.close()
    with open_runtime(data_dir, FakeClock(clock.now())) as reloaded:
        assert reloaded.state == state


# ---------------------------------------------------------------- restarts


def restart(runtime: LifeRuntime, data_dir: DataDir, clock: FakeClock) -> LifeRuntime:
    runtime.close()
    return open_runtime(data_dir, clock)


def test_restart_preserves_identity_seed_age_and_counters(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 1500)
    for kind in (GREET, PET):
        runtime.interact(kind)
    before = runtime.state
    runtime = restart(runtime, data_dir, clock)
    with runtime:
        after = runtime.state
        assert after == before
        assert after.identity == before.identity
        assert after.rng == before.rng  # seed and every stream counter
        assert after.age(clock.now()) == before.age(clock.now())


def test_restart_during_active_reaction(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    clock.set(BIRTH + timedelta(hours=5))  # midday, Maple awake
    run_ticks(runtime, clock, 1)
    outcome = runtime.interact(PET)
    assert isinstance(outcome, Accepted) and outcome.reaction.kind.value == "pet_happy"
    petted_at = clock.now()
    clock.advance(secs(3))
    runtime = restart(runtime, data_dir, clock)
    with runtime:
        assert runtime.state.active_reaction(clock.now()) == outcome.reaction
        assert runtime.state.expression_at(clock.now()) is Expression.HAPPY
        until = petted_at + PARAMS.reaction_duration
        assert runtime.state.active_reaction(until) is None
    clock.set(petted_at + secs(9))
    with open_runtime(data_dir, clock) as later:
        now = clock.now()
        assert later.state.reaction is not None  # record still stored...
        assert later.state.active_reaction(now) is None  # ...but no longer presented
        without = replace(later.state, reaction=None)
        assert later.state.expression_at(now) is without.expression_at(now)


def test_restart_during_cooldowns(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    runtime.interact(GREET)
    clock.advance(secs(10))
    runtime.interact(PET)
    clock.advance(secs(10))
    runtime = restart(runtime, data_dir, clock)
    with runtime:
        greet = runtime.interact(GREET)
        pet = runtime.interact(PET)
        assert greet == Rejected(RejectionReason.COOLDOWN, secs(40))
        assert pet == Rejected(RejectionReason.COOLDOWN, secs(20))
        clock.advance(secs(20))
        assert isinstance(runtime.interact(PET), Accepted)


def test_restart_with_full_rate_limit_window(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    start = clock.now()
    for i in range(10):
        clock.set(start + secs(30 * i))
        assert isinstance(runtime.interact(GREET if i % 2 == 0 else PET), Accepted)
    clock.set(start + secs(300))
    runtime = restart(runtime, data_dir, clock)
    with runtime:
        assert runtime.interact(PET) == Rejected(RejectionReason.RATE_LIMIT, secs(300))
        clock.set(start + secs(600))
        assert isinstance(runtime.interact(PET), Accepted)


# ---------------------------------------------------------------- downtime


def test_short_downtime_advances_coherently(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    clock.set(BIRTH + timedelta(hours=5))
    run_ticks(runtime, clock, 1)
    before = runtime.state
    runtime.close()
    clock.advance(timedelta(minutes=8))  # missed one 5-minute tick
    with open_runtime(data_dir, clock) as runtime:
        result = runtime.heartbeat_if_due()
        assert result is not None and result.tick_id == before.rng.tick_counter + 1
        assert not any(isinstance(e, DowntimeGap) for e in result.events)
        expected = evolve_needs(before.needs, before.activity, timedelta(minutes=8))
        assert runtime.state.needs.energy == expected.energy


@pytest.mark.parametrize("downtime", [timedelta(days=3), timedelta(days=3650)])
def test_long_downtime_is_one_bounded_heartbeat(tmp_path: Path, downtime: timedelta) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 5)
    before = runtime.state
    runtime.close()
    stopped_at = clock.now()
    clock.advance(downtime)
    with open_runtime(data_dir, clock) as runtime:
        result = runtime.heartbeat_if_due()
        assert result is not None
        assert runtime.state.rng.tick_counter == before.rng.tick_counter + 1  # not millions
        assert DowntimeGap(since=stopped_at, until=clock.now()) in result.events
        capped = evolve_needs(before.needs, before.activity, PARAMS.max_catchup)
        assert runtime.state.needs.social == capped.social
        assert runtime.heartbeat_if_due() is None
        stored = [e.event for e in runtime.timeline()]
        assert DowntimeGap(since=stopped_at, until=clock.now()) in stored


def test_downtime_recovery_is_deterministic(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path, "original")
    run_ticks(runtime, clock, 40)
    runtime.interact(GREET)
    runtime.close()
    copies = []
    for name in ("copy-a", "copy-b"):
        target = tmp_path / name
        target.mkdir()
        shutil.copy2(data_dir.root / "maple.db", target / "maple.db")
        copies.append(DataDir(target))
    restart_at = clock.now() + timedelta(days=2, minutes=13)
    outcomes = []
    for copy in copies:
        with open_runtime(copy, FakeClock(restart_at)) as runtime:
            result = runtime.heartbeat_if_due()
            outcomes.append((result, runtime.state, [e.event for e in runtime.timeline()]))
    assert outcomes[0] == outcomes[1]


def test_many_restarts_never_rebirth(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    runtime.close()
    for _ in range(25):
        clock.advance(TICK)
        with open_runtime(data_dir, clock) as runtime:
            runtime.heartbeat_if_due()
    with raw_db(data_dir) as conn:
        assert conn.execute("SELECT count(*) FROM maple").fetchone()[0] == 1
        births = conn.execute("SELECT count(*) FROM timeline_event WHERE kind='born'")
        assert births.fetchone()[0] == 1
    with open_runtime(data_dir, clock) as runtime:
        assert runtime.state.ticks_lived == 25
        assert runtime.state.activity in Activity
