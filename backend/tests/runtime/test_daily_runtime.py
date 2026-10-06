"""Daily Reflection through the runtime (ADR-0031): at night's sleep, or recovered."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from maplegotchi.core.daily import reflection_day
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.service import MapleService, fake_senses
from tests.api.support import make_client
from tests.persistence_support import BIRTH, PARAMS, make_data_dir, open_runtime

STEP = timedelta(minutes=5)


def live(service: MapleService, clock: FakeClock, hours: float) -> None:
    for _ in range(int(hours * 12)):
        clock.advance(STEP)
        service.step()


def test_reflection_is_written_when_the_nights_sleep_begins(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    clock = FakeClock(BIRTH)  # 07:00 local
    service = MapleService(open_runtime(data_dir, clock), fake_senses(), clock, PARAMS)
    live(service, clock, 20)  # through the evening into the night
    found = service.runtime.reflections(limit=5)
    assert len(found) == 1
    ref = found[0].reflection
    assert ref.day == reflection_day(BIRTH, PARAMS.utc_offset)
    assert not ref.recovered
    assert ref.summary.startswith("Today I started")
    assert service.runtime.state.activity.value == "sleep"
    client = make_client(service, tmp_path)
    body = client.get("/api/reflections").json()
    assert body[0]["day"] == ref.day.isoformat() and body[0]["intent"]["type"]
    events = client.get("/api/life-events?after_revision=0&limit=500").json()["events"]
    assert any(e["type"] == "daily_reflection" for e in events)
    live(service, clock, 14)  # next morning: no second reflection for the same day
    days = [r.reflection.day for r in service.runtime.reflections(limit=5)]
    assert len(days) == len(set(days))
    service.close()


def test_the_next_days_decisions_see_the_intent(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    clock = FakeClock(BIRTH)
    service = MapleService(open_runtime(data_dir, clock), fake_senses(), clock, PARAMS)
    live(service, clock, 26)  # into day 2's morning
    [ref] = [r.reflection for r in service.runtime.reflections(limit=5)]
    pending = None
    for _ in range(600):
        clock.advance(timedelta(minutes=1))
        pending = service.runtime.pending_decision()
        if pending is not None:
            break
        service.step()
    assert pending is not None
    assert pending.context.as_json()["intent"] == {
        "type": ref.intent_type.value,
        "summary": ref.intent_summary,
    }
    service.close()


def test_a_missed_reflection_is_recovered_after_restart(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    clock = FakeClock(BIRTH)
    service = MapleService(open_runtime(data_dir, clock), fake_senses(), clock, PARAMS)
    live(service, clock, 10)  # until 17:00: no night yet
    service.close()
    clock.advance(timedelta(hours=16))  # Maple was down through the night
    revived = MapleService(open_runtime(data_dir, clock), fake_senses(), clock, PARAMS)
    live(revived, clock, 2)
    found = [r.reflection for r in revived.runtime.reflections(limit=5)]
    assert [r.day for r in found] == [reflection_day(BIRTH, PARAMS.utc_offset)]
    assert found[0].recovered
    revived.close()


def test_no_reflection_for_a_day_maple_was_not_alive(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    clock = FakeClock(BIRTH)
    service = MapleService(open_runtime(data_dir, clock), fake_senses(), clock, PARAMS)
    live(service, clock, 3)
    assert service.runtime.reflections(limit=5) == []
    service.close()
