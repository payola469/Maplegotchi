"""Exact offline fixture export, typed DTOs, truthful phase/pose/source and closed doors."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from maplegotchi.api.world_models import WorldOut, WorldSnapshotOut
from maplegotchi.core.daytime import DayPhase, day_phase, local_hour
from tests.grid_world.renderer import artifact_text, render_artifacts

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT = ROOT / "docs/fixtures/maple-room/r1a-17/scripted-room-states.json"
NAMES = (
    "initial",
    "distant_departure",
    "distant_mid_edge",
    "arrival_observe",
    "activity_observe",
    "lighting_night",
    "lighting_morning",
    "lighting_afternoon",
    "lighting_evening",
    "recovered",
)


def test_offline_renderer_export_is_exact_and_reproducible() -> None:
    assert ARTIFACT.read_bytes() == artifact_text().encode("utf-8")
    assert artifact_text() == artifact_text()


@pytest.mark.parametrize("name", NAMES)
def test_renderer_state_contract_and_source(name: str) -> None:
    data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    base = WorldOut.model_validate(data["base_world"])
    frame = next(s for s in data["states"] if s["name"] == name)
    snap = WorldSnapshotOut.model_validate(frame["snapshot"])
    assert data["source"] == frame["source"] == base.source == "development_fixture"
    assert "SIMULATION" in frame["label"] and "not live Maple" in frame["label"]
    assert frame["camera_follow_target"] == [
        snap.maple.derived_pixels.x_px,
        snap.maple.derived_pixels.y_px,
    ]
    assert snap.day_phase == day_phase(local_hour(snap.generated_at, timedelta(hours=7)))
    assert snap.world_revision == base.layout_revision
    if name == "distant_mid_edge":
        assert snap.maple.position.kind == "edge" and snap.maple.pose == "walk"
    if name.startswith(("arrival_", "activity_")):
        assert snap.maple.route is not None
        assert snap.generated_at >= snap.maple.route.arrives_at
        assert snap.maple.pose == "sit_monitor" and frame["phase"] == "performing"
    if name == "recovered":
        assert frame["recovery"] and snap.maple.position.kind == "tile"
    legacy = frame["legacy_projection"]
    if snap.maple.route is not None:
        assert legacy["departed_at"] == snap.maple.route.departed_at.isoformat()
        assert legacy["arrives_at"] == snap.maple.route.arrives_at.isoformat()
        if frame["phase"] == "performing":
            assert legacy["point_id"] == "computer_desk.chair"
            assert legacy["position"] == [840, 470]
    else:
        assert legacy["point_id"] == "open_area.center"
    assert len(base.walkable) == 431


def test_phases_closed_door_and_recovery_payloads() -> None:
    data = render_artifacts()
    assert {s["snapshot"]["day_phase"] for s in data["states"]} == {p.value for p in DayPhase}
    assert data["closed_door_attempt"]["error"] == "no_destination"
    assert data["recovery_event"] == {
        "kind": "maple_relocated",
        "original": [1, 20],
        "destination": [21, 15],
        "reason": "invalid_source",
    }
    assert len(data["states"]) == 10
