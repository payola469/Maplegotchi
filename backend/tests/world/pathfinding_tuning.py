"""Bounded R1A-17 support: independent T6 fixtures and deterministic grid timing report.

Run with python -m tests.world.pathfinding_tuning. No legacy simulation pin changes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from maplegotchi.core.activities import SPECS, Activity
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.pathfinding import find_route
from maplegotchi.core.world.walkability import Walkability, validate_safe_layout
from maplegotchi.runtime.world_catalog import load_initial_catalog
from maplegotchi.runtime.world_layout import load_initial_house
from tests.world.oracle import Oracle, load_spec


def canonical_fixture() -> tuple[Walkability, tuple[Tile, ...], Oracle]:
    spec = load_spec()
    world = load_initial_house()
    catalog = load_initial_catalog(world)
    points = {
        p.instance_id + "/" + p.template.id: Tile(p.template.approach.x, p.template.approach.y)
        for p in catalog.points
    }
    rows = {row[0]: row for row in spec.table(6).rows}
    t4 = {row[0]: row for row in spec.table(4).rows}
    selected: list[Tile] = []
    for activity in spec.walks.columns[1:]:
        key = {"observe": "observe_server", "idle": "idle|walk"}.get(activity, activity)
        point_id = "idle.hall_center/idle" if activity == "idle" else rows[key][2].split(";")[0]
        expected = tuple(int(value) for value in t4[point_id][1].split(";"))
        tile = points[point_id]
        if (tile.tx, tile.ty) != expected:
            raise ValueError("canonical fixture differs from approved T4")
        selected.append(tile)
    return validate_safe_layout(world, catalog), tuple(selected), spec


@dataclass(frozen=True)
class Leg:
    source: str
    target: str
    steps: int
    turns: int
    duration_ms: int
    target_min_activity_ms: int
    movement_basis_points: int
    waypoints: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True)
class TuningRun:
    ms_per_step: int
    turn_penalty: int
    differences: int
    total_turns: int
    longest_walk_ms: int
    legs: tuple[Leg, ...]


def evaluate(speed: int, penalty: int) -> TuningRun:
    mask, points, spec = canonical_fixture()
    legs: list[Leg] = []
    differences = 0
    for i, source in enumerate(spec.walks.columns[1:]):
        for j, target in enumerate(spec.walks.columns[1:]):
            result = find_route(mask, points[i], points[j], penalty)
            if result.route is None:
                raise ValueError("canonical path unexpectedly unavailable")
            route = result.route
            differences += int(route.total_steps != int(spec.walks.rows[i][j + 1]))
            activity = Activity.OBSERVE_SERVER if target == "observe" else Activity(target)
            minimum_ms = SPECS[activity].min_minutes * 60000
            duration = route.total_steps * speed
            legs.append(
                Leg(
                    source,
                    target,
                    route.total_steps,
                    route.turns,
                    duration,
                    minimum_ms,
                    duration * 10000 // minimum_ms,
                    tuple((p.tx, p.ty, p.cumulative_steps) for p in route.waypoints),
                )
            )
    return TuningRun(
        speed,
        penalty,
        differences,
        sum(leg.turns for leg in legs),
        max(leg.duration_ms for leg in legs),
        tuple(legs),
    )


def report() -> tuple[tuple[TuningRun, ...], str]:
    runs = tuple(evaluate(speed, penalty) for speed in (250, 300) for penalty in (0, 1, 2, 4))
    data = json.dumps([asdict(run) for run in runs], sort_keys=True, separators=(",", ":")).encode()
    return runs, hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    results, digest = report()
    print(
        json.dumps(
            {
                "sha256": digest,
                "runs": [
                    {
                        "speed": run.ms_per_step,
                        "penalty": run.turn_penalty,
                        "differences": run.differences,
                        "total_turns": run.total_turns,
                        "longest_ms": run.longest_walk_ms,
                        "max_activity_basis_points": max(
                            leg.movement_basis_points for leg in run.legs
                        ),
                    }
                    for run in results
                ],
            },
            indent=2,
        )
    )
