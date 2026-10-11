"""R1A-10 truthfulness, additive contracts, isolation and reproducible handoff."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from maplegotchi.api import views
from maplegotchi.api.app import create_app
from maplegotchi.api.security import SECURITY_HEADERS
from maplegotchi.api.world_fixtures import (
    FixtureScenario,
    WorldFixture,
    build_fixture,
    create_fixture_app,
    validate_fixture_settings,
)
from maplegotchi.api.world_models import (
    EdgePositionOut,
    WorldCatalogOut,
    WorldOut,
    WorldPlacementsOut,
    WorldUnavailableOut,
)
from maplegotchi.config import (
    BrainMode,
    DirectorMode,
    Mode,
    ReplierMode,
    SensesKind,
    Settings,
    SettingsError,
)
from maplegotchi.core.world.coordinates import FEET_IN_TILE, Tile
from maplegotchi.core.world.model import RegionStatus
from maplegotchi.core.world.walkability import components
from tests.api.support import make_service, make_settings, production
from tests.api.world_contract_export import ROOT, render_artifacts, typescript

PATHS = ("/api/world", "/api/world/catalog", "/api/world/placements")


@pytest.fixture(scope="module")
def fixture() -> WorldFixture:
    return build_fixture()


def fixture_settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "never-created", senses=SensesKind.FAKE)


@pytest.mark.parametrize("scenario", tuple(FixtureScenario))
@pytest.mark.parametrize(
    "path,model,field",
    [
        (PATHS[0], WorldOut, "world"),
        (PATHS[1], WorldCatalogOut, "catalog"),
        (PATHS[2], WorldPlacementsOut, "placements"),
    ],
)
def test_synthetic_routes_are_explicit_and_deterministic(
    tmp_path: Path, scenario: FixtureScenario, path: str, model: Any, field: str
) -> None:
    settings = fixture_settings(tmp_path)
    app = create_fixture_app(settings, scenario=scenario)
    expected = getattr(build_fixture(scenario), field)
    with TestClient(app) as client:
        first = client.get(path)
        assert first.status_code == 200
        assert first.content == client.get(path).content
        assert model.model_validate_json(first.content) == expected
        body = first.json()
        assert body["source"] == "development_fixture"
        assert body["status"] == "synthetic"
        assert body["layout_revision"].startswith("fixture-sha256:")
        for key, value in SECURITY_HEADERS:
            assert first.headers[key.decode()] == value.decode()
        assert first.headers["cache-control"] == "no-store"
        assert "access-control-allow-origin" not in first.headers
        assert str(tmp_path) not in first.text
    assert not settings.data_dir.exists()  # no DB, file, history or life created


@pytest.mark.parametrize("profile", ["default", "fake", "production"])
@pytest.mark.parametrize("path", PATHS)
def test_live_v10_never_exposes_fixtures(tmp_path: Path, profile: str, path: str) -> None:
    service = make_service(tmp_path / "data")
    overrides = production(tmp_path) if profile == "production" else {}
    if profile == "fake":
        overrides = {"senses": SensesKind.FAKE}
    settings = make_settings(tmp_path, **overrides)
    app = create_app(service, settings, run_life_loop=False)
    with TestClient(app) as client:
        snapshot = client.get("/api/snapshot").content
        legacy_room = client.get("/api/room").content
        expected = views.snapshot(service.snapshot()).model_dump(mode="json")
        before_state, before_seq = service.runtime.state, service.hub.last_seq
        response = client.get(path)
        assert service.runtime.state is before_state
        assert service.hub.last_seq == before_seq
        assert response.status_code == 503
        assert response.json() == WorldUnavailableOut().model_dump()
        assert "development_fixture" not in response.text
        assert "source" not in response.json()
        assert client.get("/api/snapshot").content == snapshot
        assert client.get("/api/room").content == legacy_room
        assert json.loads(snapshot) == expected
        assert "world_revision" not in json.loads(snapshot)
        assert set(json.loads(snapshot)["maple"]["activity"]["position"]) == {"x", "y"}
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert response.headers["cache-control"] == "no-store"
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "HEAD"])
@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("synthetic", [False, True])
def test_get_only_surface(tmp_path: Path, method: str, path: str, synthetic: bool) -> None:
    if synthetic:
        app = create_fixture_app(fixture_settings(tmp_path))
        service = None
    else:
        service = make_service(tmp_path / "data")
        app = create_app(service, make_settings(tmp_path), run_life_loop=False)
    with TestClient(app) as client:
        response = client.request(method, path, headers={"Origin": "http://evil.example"})
        assert response.status_code == 405
        assert "access-control-allow-origin" not in response.headers
    assert service is None or service.runtime is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "mode": Mode.PRODUCTION,
            "senses": SensesKind.PAOLO_CORE,
            "allowed_origins": ("https://maple.tailnet.example",),
        },
        {"senses": SensesKind.PAOLO_CORE},
        {"mode": "development"},  # strings must not bypass typed configuration boundary
        {"senses": "fake"},
        {"brain": "rule"},
        {"director": "rule"},
        {"replier": "rule"},
        {"brain": BrainMode.ANTIGRAVITY},
        {"director": DirectorMode.ANTIGRAVITY},
        {"replier": ReplierMode.ANTIGRAVITY},
        {"allowed_origins": ("https://maple.tailnet.example",)},
        {"allowed_origins": ()},
        {"gateway_token": "x" * 32},
        {"static_dir": Path("production-dist")},
    ],
)
def test_production_shaped_and_invalid_profiles_reject(
    tmp_path: Path, overrides: dict[str, Any]
) -> None:
    profile = fixture_settings(tmp_path)
    if any(type(value) is str for value in overrides.values()):
        for key, value in overrides.items():
            object.__setattr__(profile, key, value)  # malformed typed settings
    else:
        profile = replace(profile, **overrides)
    with pytest.raises(SettingsError):
        create_fixture_app(profile)
    assert not profile.data_dir.exists()


def test_existing_settings_validation_is_reapplied(tmp_path: Path) -> None:
    profile = fixture_settings(tmp_path)
    object.__setattr__(profile, "host", "0.0.0.0")  # noqa: S104 - forged profile, never bound
    with pytest.raises(SettingsError, match="loopback"):
        validate_fixture_settings(profile)
    with pytest.raises(SettingsError):
        validate_fixture_settings(cast(Settings, None))


def test_fixture_context_cannot_be_injected_into_live_app(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    try:
        with pytest.raises(TypeError):
            cast(Any, create_app)(service, make_settings(tmp_path), world_fixture=build_fixture())
    finally:
        service.close()


def test_fixture_app_has_no_live_state_or_event_surface(tmp_path: Path) -> None:
    app = create_fixture_app(fixture_settings(tmp_path))
    assert set(app.openapi()["paths"]) == set(PATHS)
    with TestClient(app) as client:
        for path in (
            "/api/snapshot",
            "/api/events",
            "/api/room",
            "/api/world/history",
            "/api/world/layout",
            "/api/interactions/greet",
        ):
            assert client.get(path).status_code == 404
        preflight = client.options(
            PATHS[0],
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert preflight.status_code == 405
        assert "access-control-allow-origin" not in preflight.headers


def test_canonical_geometry_counts_and_identities(fixture: WorldFixture) -> None:
    world = fixture.world
    assert (world.grid.width_tiles, world.grid.height_tiles, world.grid.tile_size_px) == (
        44,
        26,
        16,
    )
    assert world.grid.feet_in_tile_px == FEET_IN_TILE
    assert len(world.regions) == 8
    assert sum(r.status is RegionStatus.OPEN for r in world.regions) == 5
    assert len(world.doors) == 7
    assert sum(len(n.neighbors) for n in world.room_graph) == 8  # four undirected edges
    assert len(world.objects) == 28
    assert len(world.points) == 17
    assert len(world.slots) == 12
    assert len(world.walkable) == 431
    assert len(components(world.walkable)) == 1
    assert len(world.structure) == 1144
    assert sum(z.bounds.w * z.bounds.h for z in world.lighting_zones) == 1144
    assert len(fixture.catalog.types) == 15
    assert {o.type_id for o in world.objects} <= {t.id for t in fixture.catalog.types}
    objects = {o.id for o in world.objects}
    assert all(p.instance_id in objects for p in world.points)
    assert all(s.instance_id in objects for s in world.slots)
    assert world.walkable == tuple(sorted(world.walkable, key=lambda t: (t.ty, t.tx)))
    for room in world.regions:
        if room.status is RegionStatus.CLOSED:
            assert all(not room.floor.contains(tile) for tile in world.walkable)
    for passage in world.passages:
        assert passage.region_id == next(
            d.south_room for d in world.doors if d.id == passage.door_id
        )
        if passage.state.value == "closed":
            assert not set(passage.cells) & set(world.walkable)


def test_shared_identity_idle_route_and_immutability(fixture: WorldFixture) -> None:
    world = fixture.world
    assert (
        world.layout_revision
        == fixture.catalog.layout_revision
        == fixture.placements.layout_revision
    )
    assert world.snapshot.world_revision == world.layout_revision
    assert world.snapshot.maple.route is None
    assert world.snapshot.maple.position.model_dump()["tile"] == {"tx": 21, "ty": 15}
    assert world.snapshot.maple.derived_pixels.model_dump() == {"x_px": 344, "y_px": 253}
    assert world.snapshot.maple.legacy_facing.value == "front"
    with pytest.raises(ValidationError):
        world.status = "live"  # type: ignore[assignment]
    with pytest.raises(FrozenInstanceError):
        world.regions[0].id = "other"  # type: ignore[misc]
    with pytest.raises(ValueError):
        build_fixture(cast(FixtureScenario, "idle"))


def test_walking_exact_edge_pixels_and_timing(fixture: WorldFixture) -> None:
    world = build_fixture(FixtureScenario.WALKING).world
    actor = world.snapshot.maple
    route = actor.route
    assert route is not None
    assert isinstance(actor.position, EdgePositionOut)
    edge = actor.position.edge
    assert (edge.a, edge.b, edge.progress_us, edge.step_us) == (
        Tile(21, 15),
        Tile(22, 15),
        125000,
        250000,
    )
    assert actor.derived_pixels.model_dump() == {"x_px": 352, "y_px": 253}
    assert route.waypoints[0].cumulative_steps == 0
    assert route.waypoints[-1].cumulative_steps == 11
    assert (route.arrives_at - route.departed_at).total_seconds() == 2.75
    assert actor.facing.value == actor.legacy_facing.value == "right"
    assert actor.pose == "walk"
    assert world.layout_revision == fixture.world.layout_revision


def test_display_and_empty_are_synthetic_candidates(fixture: WorldFixture) -> None:
    assert fixture.placements.items == ()
    assert fixture.placements.placements == ()
    assert fixture.placements.storage_item_ids == ()
    display = build_fixture(FixtureScenario.DISPLAY)
    assert len(display.placements.items) == len(display.placements.placements) == 1
    placement = display.placements.placements[0]
    assert placement.item_id == display.placements.items[0].id
    assert (placement.host_id, placement.slot_id) == ("bedside.bedroom", "top")
    assert display.placements.storage_item_ids == ()
    assert display.world == fixture.world  # display does not alter geometry/life


def test_exports_reproducible_and_production_schema_consistent(tmp_path: Path) -> None:
    artifacts = render_artifacts()
    assert artifacts == render_artifacts()
    for path, expected in artifacts.items():
        assert path.read_text(encoding="utf-8") == expected, str(path.relative_to(ROOT))
    service = make_service(tmp_path / "data")
    try:
        app = create_app(service, make_settings(tmp_path), run_life_loop=False)
        schema = app.openapi()
        exported = json.loads(artifacts[ROOT / "docs/api/world-openapi.json"])
        for route_path in PATHS:
            assert schema["paths"][route_path] == exported["paths"][route_path]
            assert set(schema["paths"][route_path]) == {"get"}
            assert "503" in schema["paths"][route_path]["get"]["responses"]
        for name, model in exported["components"]["schemas"].items():
            assert schema["components"]["schemas"][name] == model
    finally:
        service.close()


@pytest.mark.parametrize(
    "name,model",
    [
        ("world-idle", WorldOut),
        ("world-walking", WorldOut),
        ("catalog", WorldCatalogOut),
        ("placements-empty", WorldPlacementsOut),
        ("placements-display", WorldPlacementsOut),
    ],
)
def test_exported_json_validates(name: str, model: Any) -> None:
    payload = (ROOT / f"docs/fixtures/maple-room/r1a-10/{name}.json").read_text()
    parsed = model.model_validate_json(payload)
    assert parsed.model_dump(mode="json") == json.loads(payload)


@pytest.mark.parametrize("schema", [{}, {"type": "object"}, {"type": "mystery"}])
def test_generator_rejects_unknown_schema(schema: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        typescript(schema)


def test_dtos_reject_wrong_source_and_unknown_fields(fixture: WorldFixture) -> None:
    payload = fixture.world.model_dump(mode="json")
    payload["source"] = "production"
    with pytest.raises(ValidationError):
        WorldOut.model_validate(payload)
    payload["source"] = "development_fixture"
    payload["internal_config"] = "/private/should-never-exist"
    with pytest.raises(ValidationError):
        WorldOut.model_validate(payload)
