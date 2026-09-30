"""Observations in the runtime: stored with their heartbeat, steering attention only."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from pathlib import Path

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.attention import behavior_inputs
from maplegotchi.core.heartbeat import heartbeat
from maplegotchi.core.observations import Metric, ObservationStatus, ServiceState
from maplegotchi.core.state import birth
from maplegotchi.runtime.senses import Senses
from maplegotchi.sensors.fake import FakeHostProbe
from maplegotchi.sensors.interface import MetricUnavailable
from maplegotchi.sensors.service_health.fake import FakeServiceHealth
from maplegotchi.sensors.service_health.interface import INTENDED_SERVICES, ServiceReading
from maplegotchi.storage.repositories import LifeRepository
from tests.persistence_support import BIRTH, PARAMS, SEED, TICK, new_life, open_runtime, raw_db

A = ObservationStatus.AVAILABLE


def senses(*, jellyfin: ServiceState = ServiceState.ACTIVE, disk: float = 62.0) -> Senses:
    readings = {
        t.service_id: ServiceReading(A, state=ServiceState.ACTIVE) for t in INTENDED_SERVICES
    }
    readings["jellyfin"] = ServiceReading(A, state=jellyfin)
    return Senses(
        FakeHostProbe(temperature=MetricUnavailable("no_temperature_sensors"), disks={"/": disk}),
        (FakeServiceHealth(readings),),
    )


def test_observations_are_stored_with_their_heartbeat(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    clock.advance(TICK)
    snapshot = senses().observe(clock.now())
    result = runtime.heartbeat_if_due(snapshot)
    assert result is not None
    stored = runtime.observations(tick_id=result.tick_id)
    assert [s.observation for s in stored] == list(snapshot.observations)
    assert {s.revision for s in stored} == {runtime.revision}
    temp = next(s.observation for s in stored if s.observation.metric is Metric.TEMPERATURE)
    assert temp.status is ObservationStatus.UNAVAILABLE and temp.reason == "no_temperature_sensors"
    runtime.close()
    with open_runtime(data_dir, clock) as reloaded:  # survives restart, exactly
        assert [s.observation for s in reloaded.observations()] == list(snapshot.observations)


def test_heartbeat_without_observations_stores_none(tmp_path: Path) -> None:
    _, clock, runtime = new_life(tmp_path)
    with runtime:
        clock.advance(TICK)
        assert runtime.heartbeat_if_due() is not None
        assert runtime.observations() == []


def test_future_observations_are_refused(tmp_path: Path) -> None:
    _, clock, runtime = new_life(tmp_path)
    with runtime:
        clock.advance(TICK)
        future = senses().observe(clock.now() + timedelta(seconds=1))
        with pytest.raises(ValueError):
            runtime.heartbeat_if_due(future)
        assert runtime.revision == 1


def test_observation_write_failure_rolls_back_the_heartbeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    before = runtime.state

    def explode(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(LifeRepository, "_insert_observations", explode)
    clock.advance(TICK)
    with pytest.raises(OSError):
        runtime.heartbeat_if_due(senses().observe(clock.now()))
    assert runtime.state == before and runtime.revision == 1
    with raw_db(data_dir) as conn:
        assert conn.execute("SELECT count(*) FROM observation").fetchone()[0] == 0
        assert conn.execute("SELECT tick_counter FROM life_state").fetchone()[0] == 0
    runtime.close()


def test_stored_observations_are_append_only(tmp_path: Path) -> None:
    import sqlite3

    data_dir, clock, runtime = new_life(tmp_path)
    clock.advance(TICK)
    runtime.heartbeat_if_due(senses().observe(clock.now()))
    runtime.close()
    with raw_db(data_dir) as conn:
        for sql in ("UPDATE observation SET value = 0", "DELETE FROM observation"):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(sql)


def test_heartbeat_due_matches_heartbeat_if_due(tmp_path: Path) -> None:
    _, clock, runtime = new_life(tmp_path)
    with runtime:
        assert not runtime.heartbeat_due()
        clock.advance(TICK)
        assert runtime.heartbeat_due()
        runtime.heartbeat_if_due()
        assert not runtime.heartbeat_due()


def test_failed_service_draws_maple_to_the_terminal_but_never_forces_it(tmp_path: Path) -> None:
    def live(sense: Senses, name: str) -> Counter[Activity]:
        _, clock, runtime = new_life(tmp_path, name)
        seen: Counter[Activity] = Counter()
        with runtime:
            clock.set(BIRTH + timedelta(hours=1))  # 08:00 local: daytime
            for _ in range(12 * 12):  # 12 daytime hours
                clock.advance(TICK)
                runtime.heartbeat_if_due(sense.observe(clock.now()))
                seen[runtime.state.activity] += 1
        return seen

    calm = live(senses(), "calm")
    alarmed = live(senses(jellyfin=ServiceState.FAILED), "alarmed")
    assert alarmed[Activity.OBSERVE_SERVER] > calm[Activity.OBSERVE_SERVER]
    assert len(alarmed) > 2  # attention biases the choice; it does not dictate it


def test_runtime_with_observations_equals_pure_core(tmp_path: Path) -> None:
    sense = senses(disk=96.0)  # disk nearly full -> attention 0.8
    _, clock, runtime = new_life(tmp_path)
    state = birth(name="Maple", born_at=BIRTH, seed_hex=SEED)
    for i in range(1, 300):
        clock.set(BIRTH + TICK * i)
        snapshot = sense.observe(clock.now())
        runtime.heartbeat_if_due(snapshot)
        state = heartbeat(state, clock.now(), behavior_inputs(snapshot), PARAMS).state
    assert runtime.state == state
    runtime.close()
