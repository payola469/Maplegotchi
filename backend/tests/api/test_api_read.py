"""Read endpoints: snapshot contract, freshness, honesty about unknown data."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from maplegotchi.core.observations import ObservationStatus
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.senses import Senses
from maplegotchi.runtime.service import HEARTBEAT_GRACE
from maplegotchi.sensors.fake import FakeHostProbe
from maplegotchi.sensors.interface import MetricUnavailable
from maplegotchi.sensors.service_health.fake import FakeServiceHealth
from maplegotchi.sensors.service_health.interface import INTENDED_SERVICES, ServiceReading
from tests.api.support import TRUSTED, make_client, make_service
from tests.persistence_support import BIRTH, TICK

SNAPSHOT_KEYS = {
    "revision",
    "generated_at",
    "maple",
    "day",
    "server",
    "journal",
    "timeline",
    "freshness",
    "brain",
    "director",
}  # fmt: skip  -- director: additive, ADR-0026


def honest_senses() -> Senses:
    """Like paolo-core today: host readable, temperature missing, services not surveyed."""
    unknown = ServiceReading(ObservationStatus.UNKNOWN, reason="not_surveyed")
    return Senses(
        FakeHostProbe(temperature=MetricUnavailable("no_temperature_sensors")),
        (FakeServiceHealth({t.service_id: unknown for t in INTENDED_SERVICES}),),
    )


def test_snapshot_contract_and_values(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    client = make_client(service, tmp_path)
    service.clock.advance(TICK)  # type: ignore[attr-defined]
    service.tick()
    body = client.get("/api/snapshot").json()
    assert set(body) == SNAPSHOT_KEYS
    state = service.runtime.state
    maple = body["maple"]
    assert body["revision"] == service.runtime.revision == maple["revision"]
    assert maple["identity"]["name"] == "Maple"
    assert maple["identity"]["ticks_lived"] == 1
    assert maple["needs"]["energy"] == state.needs.energy
    activity = maple["activity"]
    assert {k: activity[k] for k in ("kind", "location", "started_at", "until")} == {
        "kind": state.activity.value,
        "location": state.location.value,
        "started_at": state.activity_started_at.isoformat().replace("+00:00", "Z"),
        "until": state.activity_until.isoformat().replace("+00:00", "Z"),
    }
    # Additive movement fields (ADR-0027): exactly these, all from backend state.
    assert set(activity) == {
        "kind", "location", "started_at", "until",
        "phase", "point", "furniture", "pose", "facing", "position", "route",
        "task",  # ADR-0029: what is being read/written
    }  # fmt: skip
    assert activity["point"] == state.point.id
    assert activity["furniture"] == state.point.furniture.value
    assert maple["expression"] == state.expression_at(service.clock.now()).value
    assert body["brain"] == {"kind": "rule", "name": "rule_brain", "version": "1"}
    assert body["day"]["timezone"] == "Asia/Bangkok" and body["day"]["utc_offset_minutes"] == 420
    assert body["day"]["local_time"].startswith("2026-01-01T07:05") and body["day"][
        "local_time"
    ].endswith("+07:00")
    assert body["day"]["phase"] == "morning" and body["day"]["is_night"] is False
    assert [e["kind"] for e in body["timeline"]] == ["born"]
    assert [e["trigger"] for e in body["journal"]] == ["milestone"]
    service.close()


def test_freshness_distinguishes_fresh_overdue_and_sensor_states(tmp_path: Path) -> None:
    clock = FakeClock(BIRTH)
    service = make_service(tmp_path / "data", clock)
    client = make_client(service, tmp_path)
    fresh = client.get("/api/status").json()["freshness"]
    assert fresh["heartbeat_status"] == "fresh" and fresh["sensor_status"] == "none"
    assert fresh["life_loop_running"] is False  # tests drive ticks by hand
    clock.advance(TICK)
    service.tick()
    after_tick = client.get("/api/status").json()["freshness"]
    assert after_tick["sensor_status"] == "fresh" and after_tick["heartbeat_age_seconds"] == 0
    clock.advance(TICK + HEARTBEAT_GRACE + timedelta(seconds=1))  # no heartbeat ran
    overdue = client.get("/api/status").json()["freshness"]
    assert overdue["heartbeat_status"] == "overdue"
    assert overdue["sensor_status"] == "stale"  # old data is never presented as current
    server = client.get("/api/server").json()
    assert server["sensor_status"] == "stale"
    service.close()


def test_unknown_and_unavailable_sensors_are_shown_honestly(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data", senses=honest_senses())
    client = make_client(service, tmp_path)
    service.clock.advance(TICK)  # type: ignore[attr-defined]
    service.tick()
    server = client.get("/api/server").json()
    services = {s["service_id"]: s for s in server["services"]}
    assert services["jellyfin"] == {
        "service_id": "jellyfin", "status": "unknown", "state": None, "source": "service_health",
        "reason": "fake:not_surveyed", "observed_at": services["jellyfin"]["observed_at"],
    }  # fmt: skip
    temperature = next(h for h in server["host"] if h["metric"] == "temperature")
    assert temperature["status"] == "unavailable" and temperature["value"] is None
    assert temperature["reason"] == "no_temperature_sensors"
    assert server["summary"] == "unclear"  # never "calm" while services are unknown
    assert server["counts"]["unknown"] == 7 and server["counts"]["unavailable"] == 1
    latest = client.get("/api/observations/latest").json()
    assert {o["metric"] for o in latest} >= {"cpu_usage", "service_state", "temperature"}
    service.close()


def test_no_observations_yet_means_no_data(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    server = make_client(service, tmp_path).get("/api/server").json()
    assert server["summary"] == "no_data" and server["observed_at"] is None
    assert server["services"] == [] and server["sensor_status"] == "none"
    service.close()


def test_expression_and_reaction_expire_without_a_heartbeat(tmp_path: Path) -> None:
    clock = FakeClock(BIRTH)
    service = make_service(tmp_path / "data", clock)
    client = make_client(service, tmp_path)
    petted = client.post("/api/interactions/pet", headers=TRUSTED).json()
    assert petted["maple"]["expression"] == "happy"
    assert petted["reaction"]["kind"] == "pet_happy"
    until = petted["reaction"]["until"]
    clock.advance(timedelta(seconds=7))
    during = client.get("/api/maple").json()
    assert during["expression"] == "happy" and during["reaction"]["until"] == until
    clock.advance(timedelta(seconds=2))  # past `until`; no heartbeat has run
    after = client.get("/api/maple").json()
    assert after["reaction"] is None and after["expression"] == "calm"
    assert after["revision"] == petted["revision"]  # nothing was written to expire it
    service.close()


def test_journal_and_timeline_serialization(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    client = make_client(service, tmp_path)
    client.post("/api/interactions/greet", headers=TRUSTED)
    service.clock.advance(TICK)  # type: ignore[attr-defined]
    service.tick()
    journal = client.get("/api/journal?limit=5").json()
    greet = next(e for e in journal if e["trigger"] == "interaction")
    assert greet["text"].startswith("Paolo")
    assert greet["brain"] == {"kind": "rule", "name": "rule_brain", "version": "1"}
    assert greet["observation_ids"] == [] and greet["tick_id"] is None
    timeline = client.get("/api/timeline?limit=5").json()
    kinds = [e["kind"] for e in timeline]
    assert kinds[:2] == ["born", "interaction_accepted"]
    assert timeline[1]["details"] == {"kind": "greet", "reaction": "greet_happy"}
    assert [e["id"] for e in timeline] == sorted(e["id"] for e in timeline)
    service.close()


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=-1", "limit=abc", "limit=1.5"])
def test_bad_query_parameters_are_rejected(tmp_path: Path, query: str) -> None:
    service = make_service(tmp_path / "data")
    client = make_client(service, tmp_path)
    assert client.get(f"/api/journal?{query}").status_code == 422
    assert client.get(f"/api/timeline?{query}").status_code == 422
    service.close()
