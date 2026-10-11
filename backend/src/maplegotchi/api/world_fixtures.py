"""Explicit standalone synthetic app; never used by create_app or shipped startup.

No service, life loop, database, event hub, static frontend or environment switch.
Offline exports and this local-only factory share canonical serializers.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from maplegotchi.api.security import BodyLimitMiddleware, SecurityHeadersMiddleware
from maplegotchi.api.world_models import (
    DisplayItemOut,
    DisplayPlacementOut,
    EdgePositionOut,
    GridOut,
    LightingZoneOut,
    PixelPositionOut,
    TilePositionOut,
    WorldCatalogOut,
    WorldMapleOut,
    WorldObjectOut,
    WorldOut,
    WorldPlacementsOut,
    WorldPointOut,
    WorldPointRefOut,
    WorldRouteOut,
    WorldSlotOut,
    WorldSnapshotOut,
    WorldTypeOut,
)
from maplegotchi.config import (
    DEV_ORIGINS,
    BrainMode,
    DirectorMode,
    Mode,
    ReplierMode,
    SensesKind,
    Settings,
    SettingsError,
)
from maplegotchi.core.daytime import DayPhase
from maplegotchi.core.room import Facing
from maplegotchi.core.state import Expression
from maplegotchi.core.world.catalog import Category, Owner, Permission, PointPose
from maplegotchi.core.world.coordinates import (
    FEET_IN_TILE,
    GRID_HEIGHT,
    GRID_WIDTH,
    T,
    Tile,
    tile_to_feet,
)
from maplegotchi.core.world.directions import CharacterDirection, to_legacy_facing
from maplegotchi.core.world.model import Door, Region
from maplegotchi.core.world.movement import Travel
from maplegotchi.core.world.pathfinding import find_route
from maplegotchi.core.world.placement import (
    DisplayItem,
    DisplayPlacement,
    PlacementContext,
    PlacementSnapshot,
    SlotKey,
    derive_storage,
    validate_active_placements,
)
from maplegotchi.core.world.walkability import validate_safe_layout
from maplegotchi.runtime.world_catalog import load_initial_catalog
from maplegotchi.runtime.world_layout import load_initial_house

FIXTURE_TIME = datetime(2026, 10, 11, 0, 0, tzinfo=UTC)


class FixtureScenario(StrEnum):
    IDLE = "idle"
    WALKING = "walking"
    DISPLAY = "display"
    EMPTY = "empty"


@dataclass(frozen=True, slots=True)
class WorldFixture:
    world: WorldOut
    catalog: WorldCatalogOut
    placements: WorldPlacementsOut


def _digest(parts: tuple[BaseModel, ...]) -> str:
    text = "\n".join(part.model_dump_json() for part in parts)
    return "fixture-sha256:" + hashlib.sha256(text.encode()).hexdigest()


def build_fixture(scenario: FixtureScenario = FixtureScenario.IDLE) -> WorldFixture:
    """Read validated release data; all Maple/display values explicitly synthetic."""
    if not isinstance(scenario, FixtureScenario):
        raise ValueError("expected FixtureScenario")
    world = load_initial_house()
    catalog = load_initial_catalog(world)
    snapshot = PlacementSnapshot(world, catalog)
    maple = Tile(21, 15)
    mask = validate_safe_layout(world, catalog, maple)
    # Validation returns the canonical mask, not a live runtime state.
    types = tuple(WorldTypeOut.model_validate(item) for item in catalog.catalog.types)
    objects = tuple(WorldObjectOut.model_validate(item) for item in catalog.instances)
    points = tuple(WorldPointOut.model_validate(item) for item in catalog.points)
    slots = tuple(WorldSlotOut.model_validate(item) for item in catalog.slots)
    zones = tuple(LightingZoneOut.model_validate(zone) for zone in world.lighting.zones)
    catalog_version = _digest(types)
    # Include full validated geometry, doors, overrides and type identity in revision.
    geometry = WorldGeometryHash(
        regions=tuple(sorted(world.regions, key=lambda r: r.id)),
        doors=tuple(sorted(world.doors, key=lambda d: d.id)),
        objects=objects,
        points=points,
        slots=slots,
        zones=zones,
        catalog_version=catalog_version,
    )
    revision = _digest((geometry,))
    now = FIXTURE_TIME
    travel: Travel | None = None
    direction = CharacterDirection.DOWN
    if scenario is FixtureScenario.WALKING:
        found = find_route(mask, maple, Tile(32, 15))
        if found.route is None:
            raise ValueError("canonical synthetic route is unavailable")
        travel = Travel(found.route, FIXTURE_TIME)
        now += timedelta(milliseconds=125)
        direction = CharacterDirection.RIGHT
    current = travel.current_at(now) if travel else maple
    pixels = travel.position_at(now) if travel else tile_to_feet(maple)
    legacy: Facing = to_legacy_facing(direction)
    actor = WorldMapleOut(
        destination_point=WorldPointRefOut(
            instance_id="idle.hall_east" if travel else "idle.hall_center",
            point_id="idle",
        ),
        position=TilePositionOut(tile=current)
        if isinstance(current, Tile)
        else EdgePositionOut(edge=current),
        derived_pixels=PixelPositionOut(x_px=pixels[0], y_px=pixels[1]),
        facing=direction,
        legacy_facing=legacy,
        pose="walk" if travel else PointPose.IDLE,
        expression=Expression.CALM,
        route=WorldRouteOut(
            departed_at=travel.departed_at,
            arrives_at=travel.arrives_at,
            ms_per_step=travel.ms_per_step,
            waypoints=travel.route.waypoints,
            entry=travel.entry,
        )
        if travel
        else None,
    )
    items: tuple[DisplayItem, ...] = ()
    placements: tuple[DisplayPlacement, ...] = ()
    if scenario is FixtureScenario.DISPLAY:
        items = (
            DisplayItem(
                "fixture.creation.small",
                "creation.small",
                Category.CREATION_DISPLAY,
                Owner.MAPLE,
                (Permission.MAPLE,),
                True,
                True,
            ),
        )
        placements = (
            DisplayPlacement(
                "fixture.display.small",
                items[0].id,
                SlotKey("bedside.bedroom", "top"),
            ),
        )
    context = PlacementContext(snapshot, items, placements, now, timedelta(), maple)
    validate_active_placements(context)
    return WorldFixture(
        WorldOut(
            layout_revision=revision,
            catalog_version=catalog_version,
            grid=GridOut(
                width_tiles=GRID_WIDTH,
                height_tiles=GRID_HEIGHT,
                tile_size_px=T,
                feet_in_tile_px=FEET_IN_TILE,
            ),
            regions=geometry.regions,
            doors=geometry.doors,
            structure=world.structure.cells,
            passages=world.topology.passages,
            room_graph=world.topology.graph,
            lighting_zones=zones,
            objects=objects,
            points=points,
            slots=slots,
            walkable=mask.walkable,
            snapshot=WorldSnapshotOut(
                generated_at=now, world_revision=revision, day_phase=DayPhase.MORNING, maple=actor
            ),
        ),
        WorldCatalogOut(layout_revision=revision, catalog_version=catalog_version, types=types),
        WorldPlacementsOut(
            layout_revision=revision,
            catalog_version=catalog_version,
            items=tuple(DisplayItemOut.model_validate(item) for item in items),
            placements=tuple(
                DisplayPlacementOut(
                    id=p.id,
                    item_id=p.item_id,
                    host_id=p.slot.host_id,
                    slot_id=p.slot.slot_id,
                )
                for p in placements
            ),
            storage_item_ids=tuple(item.id for item in derive_storage(context)),
        ),
    )


# Hash input is an API-only helper; it fixes no persistence fields.
class WorldGeometryHash(BaseModel):
    regions: tuple[Region, ...]
    doors: tuple[Door, ...]
    objects: tuple[WorldObjectOut, ...]
    points: tuple[WorldPointOut, ...]
    slots: tuple[WorldSlotOut, ...]
    zones: tuple[LightingZoneOut, ...]
    catalog_version: str


def validate_fixture_settings(settings: Settings) -> None:
    """Require explicit typed local fakes; reject production-shaped combinations."""
    if type(settings) is not Settings:
        raise SettingsError("fixture app requires Settings")
    # Run all existing settings validation again (including forged frozen instances).
    if not (
        settings.mode is Mode.DEVELOPMENT
        and settings.senses is SensesKind.FAKE
        and settings.brain is BrainMode.RULE
        and settings.director is DirectorMode.RULE
        and settings.replier is ReplierMode.RULE
        and settings.allowed_origins == DEV_ORIGINS
        and settings.static_dir is None
        and settings.gateway_token is None
    ):
        raise SettingsError("fixture app requires an isolated local development/fake profile")
    Settings(**{field.name: getattr(settings, field.name) for field in fields(Settings)})


def create_fixture_app(
    settings: Settings, *, scenario: FixtureScenario = FixtureScenario.IDLE
) -> FastAPI:
    """Programmatic fixture host only; no live-service argument or server entry point."""
    validate_fixture_settings(settings)
    fixture = build_fixture(scenario)
    app = FastAPI(
        title="Maplegotchi synthetic world fixtures",
        version="r1a-10.v1",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    router = APIRouter(prefix="/api/world", tags=["world"])

    @router.get("", response_model=WorldOut, operation_id="read_world")
    def world() -> WorldOut:
        return fixture.world

    @router.get("/catalog", response_model=WorldCatalogOut, operation_id="read_world_catalog")
    def catalog() -> WorldCatalogOut:
        return fixture.catalog

    @router.get(
        "/placements", response_model=WorldPlacementsOut, operation_id="read_world_placements"
    )
    def placements() -> WorldPlacementsOut:
        return fixture.placements

    app.include_router(router)
    app.openapi()
    return app
