"""Offline DTO snapshots for future renderer scripts; never imported by the frontend."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from maplegotchi.api.world_fixtures import FixtureScenario, build_fixture
from maplegotchi.api.world_models import (
    EdgePositionOut,
    PixelPositionOut,
    TilePositionOut,
    WorldMapleOut,
    WorldOut,
    WorldPointRefOut,
    WorldRouteOut,
    WorldSnapshotOut,
)
from maplegotchi.core.activities import Activity
from maplegotchi.core.daytime import DayPhase
from maplegotchi.core.rng import RngState
from maplegotchi.core.state import Expression, Needs
from maplegotchi.core.world.catalog import PointPose
from maplegotchi.core.world.coordinates import Tile, tile_to_feet
from maplegotchi.core.world.directions import CharacterDirection, to_legacy_facing
from maplegotchi.core.world.legacy_projection import (
    DevelopmentWorld,
    PointRef,
    Presentation,
    project,
)
from maplegotchi.core.world.movement import Travel
from maplegotchi.core.world.pathfinding import find_route
from maplegotchi.core.world.recovery import Position, recover
from maplegotchi.core.world.resolution import DecisionContext, resolve
from tests.grid_world.fixtures import scenario, snapshot
from tests.grid_world.simulation import SEED, START, VERSION


def render_artifacts() -> dict[str, Any]:
    base = build_fixture(FixtureScenario.IDLE)
    state = snapshot(scenario("A"))
    result = resolve(
        Activity.OBSERVE_SERVER, state, Tile(3, 4), DecisionContext(RngState(f"{SEED:064x}"))
    )
    legacy_context = DevelopmentWorld(state.world, state.catalog)
    chosen = result.selected
    assert chosen is not None
    travel = Travel(chosen.route, START)
    frames: list[dict[str, Any]] = []

    def frame(
        name: str,
        elapsed_ms: int,
        phase: DayPhase,
        movement: Travel | None = None,
        tile: Tile | None = None,
        recovery: bool = False,
    ) -> None:
        tile = tile or Tile(21, 15)
        now = START + timedelta(milliseconds=elapsed_ms)
        current = movement.current_at(now) if movement else tile
        pixels = movement.position_at(now) if movement else tile_to_feet(tile)
        walking = movement is not None and now < movement.arrives_at
        direction = chosen.point.template.facing if movement else CharacterDirection.DOWN
        if walking:
            assert movement is not None
            tiles = movement.route.tiles()
            i = min(elapsed_ms // movement.ms_per_step, len(tiles) - 2)
            a, b = tiles[i : i + 2]
            direction = (
                CharacterDirection.RIGHT
                if b.tx > a.tx
                else CharacterDirection.LEFT
                if b.tx < a.tx
                else CharacterDirection.DOWN
                if b.ty > a.ty
                else CharacterDirection.UP
            )
        actor = WorldMapleOut(
            destination_point=WorldPointRefOut(
                instance_id=chosen.key.instance_id if movement else "idle.hall_center",
                point_id=chosen.key.point_id if movement else PointPose.IDLE,
            ),
            position=TilePositionOut(tile=current)
            if isinstance(current, Tile)
            else EdgePositionOut(edge=current),
            derived_pixels=PixelPositionOut(x_px=pixels[0], y_px=pixels[1]),
            facing=direction,
            legacy_facing=to_legacy_facing(direction),
            pose="walk" if walking else chosen.point.template.pose if movement else PointPose.IDLE,
            expression=Expression.FOCUSED if movement else Expression.CALM,
            route=WorldRouteOut(
                departed_at=movement.departed_at,
                arrives_at=movement.arrives_at,
                ms_per_step=movement.ms_per_step,
                waypoints=movement.route.waypoints,
                entry=movement.entry,
            )
            if movement
            else None,
        )
        snap = WorldSnapshotOut(
            generated_at=now,
            world_revision=base.world.layout_revision,
            day_phase=phase,
            maple=actor,
        )
        # Validate the complete WorldOut without changing its release geometry or contract.
        payload = base.world.model_dump(mode="json")
        payload["snapshot"] = snap.model_dump(mode="json")
        checked = WorldOut.model_validate(payload)
        shown_activity = Activity.OBSERVE_SERVER if movement else Activity.IDLE
        ref = PointRef(actor.destination_point.instance_id, actor.destination_point.point_id)
        started = movement.arrives_at if movement else now
        facts = Presentation(
            shown_activity,
            started,
            started + timedelta(minutes=5),
            Needs(50, 50, 50, 50),
            None,
            actor.expression,
            chosen.point.template.pose if movement else PointPose.IDLE,
            phase,
            "development_fixture",
        )
        projected = project(
            legacy_context,
            ref,
            facts,
            now,
            travel=movement,
            origin=PointRef("bed.bedroom", "sleep") if movement else None,
            from_activity=Activity.SLEEP if movement else None,
        )
        legacy_output = {
            "point_id": projected.point.id,
            "position": list(projected.position),
            "departed_at": projected.route.departed_at.isoformat() if projected.route else None,
            "arrives_at": projected.route.arrives_at.isoformat() if projected.route else None,
        }
        frames.append(
            {
                "name": name,
                "source": "development_fixture",
                "label": "SIMULATION - synthetic R1A-17 fixture; not live Maple",
                "snapshot": checked.snapshot.model_dump(mode="json"),
                "camera_follow_target": list(pixels),
                "legacy_projection": legacy_output,
                "activity": Activity.OBSERVE_SERVER.value if movement else Activity.IDLE.value,
                "phase": "walking" if walking else "performing",
                "recovery": recovery,
            }
        )

    frame("initial", 0, DayPhase.MORNING)
    frame("distant_departure", 0, DayPhase.MORNING, travel)
    frame("distant_mid_edge", 125, DayPhase.MORNING, travel)
    arrival = travel.route.total_steps * travel.ms_per_step
    frame("arrival_observe", arrival, DayPhase.MORNING, travel)
    frame("activity_observe", arrival + 1000, DayPhase.MORNING, travel)
    for phase in DayPhase:
        frame(
            "lighting_" + phase.value,
            {DayPhase.MORNING: 0, DayPhase.AFTERNOON: 5, DayPhase.EVENING: 11, DayPhase.NIGHT: 17}[
                phase
            ]
            * 3600000,
            phase,
        )
    recovered = recover(state.mask, Position(1, 20))
    assert recovered.destination is not None and recovered.event is not None
    frame("recovered", 0, DayPhase.MORNING, tile=recovered.destination, recovery=True)
    unavailable = find_route(state.mask, Tile(21, 15), Tile(6, 18))
    assert unavailable.route is None
    return {
        "scenario_version": VERSION,
        "seed": SEED,
        "source": "development_fixture",
        "label": "SIMULATION - synthetic R1A-17 fixture; not live Maple",
        "base_world": base.world.model_dump(mode="json"),
        "catalog": base.catalog.model_dump(mode="json"),
        "states": frames,
        "snapshot_semantics": "Independent cases; interpolate only within travel_sequence.",
        "travel_sequence": [
            "distant_departure",
            "distant_mid_edge",
            "arrival_observe",
            "activity_observe",
        ],
        "closed_door_attempt": {
            "target": [6, 18],
            "error": unavailable.error,
            "reason": unavailable.reason,
        },
        "recovery_event": {
            "kind": recovered.event.kind,
            "original": [1, 20],
            "destination": [recovered.destination.tx, recovered.destination.ty],
            "reason": recovered.event.reason.value,
        },
    }


def artifact_text() -> str:
    return (
        json.dumps(render_artifacts(), sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    )
