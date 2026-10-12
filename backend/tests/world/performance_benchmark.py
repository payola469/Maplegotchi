"""Offline R1A-19 timings; run: uv run python -m tests.world.performance_benchmark.

No production imports beyond isolated pure core modules; no database/network.
Setup, independent BFS diameter discovery, correctness and warmup are untimed.
Observed measurements have no invented backend pass/fail latency threshold.
"""

from __future__ import annotations

import json
import math
import platform
import sys
from collections import deque
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from functools import partial
from pathlib import Path
from statistics import median
from time import perf_counter_ns
from typing import Any

from maplegotchi.core.activities import Activity
from maplegotchi.core.rng import RngState
from maplegotchi.core.world.catalog import Permission
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.layout_validation import validate_layout
from maplegotchi.core.world.pathfinding import find_route
from maplegotchi.core.world.placement import PlacementContext, PlacementSnapshot, validate_placement
from maplegotchi.core.world.recovery import Position, recover
from maplegotchi.core.world.resolution import (
    DecisionContext,
    InstanceUse,
    allowed_activities,
    resolve,
)
from maplegotchi.core.world.walkability import components
from tests.grid_world.fixtures import scenario, snapshot
from tests.world.test_placement import AT, ITEM, SAFE, SLOT
from tests.world.validation_corpus import mutate


def diameter(cells: tuple[Tile, ...]) -> tuple[Tile, Tile, int]:
    """Independent exhaustive unweighted BFS, not the A* under measurement."""
    allowed = {(t.tx, t.ty) for t in cells}
    best = ((0, 0), (0, 0), -1)
    for start in sorted(allowed):
        pending = deque([start])
        distances = {start: 0}
        while pending:
            x, y = pending.popleft()
            for other in ((x, y - 1), (x - 1, y), (x + 1, y), (x, y + 1)):
                if other in allowed and other not in distances:
                    distances[other] = distances[x, y] + 1
                    pending.append(other)
        for end, steps in distances.items():
            if steps > best[2]:
                best = (start, end, steps)
    return Tile(*best[0]), Tile(*best[1]), best[2]


def measure(name: str, work: Callable[[], Any], runs: int = 30) -> dict[str, Any]:
    expected = work()
    for _ in range(3):
        assert work() == expected
    raw = []
    for _ in range(runs):
        began = perf_counter_ns()
        result = work()
        raw.append(perf_counter_ns() - began)
        assert result == expected, name
    ordered = sorted(raw)
    return {
        "name": name,
        "runs": runs,
        "raw_ns": raw,
        "min_ms": min(raw) / 1e6,
        "median_ms": median(raw) / 1e6,
        "p95_ms": ordered[math.ceil(0.95 * runs) - 1] / 1e6,
        "max_ms": max(raw) / 1e6,
        "stable_result": repr(expected),
    }


def main() -> None:
    base = scenario("A")
    state = snapshot(base)
    mask = state.mask
    start, end, steps = diameter(mask.walkable)
    route = find_route(mask, start, end).route
    assert route is not None and route.total_steps == steps
    assert find_route(mask, Tile(3, 4), Tile(39, 5)).route.total_steps == 53  # type: ignore[union-attr]
    split_cells = tuple(t for t in mask.walkable if t.tx != 22)
    split = replace(mask, walkable=split_cells, components=components(split_cells))
    assert find_route(split, Tile(3, 4), Tile(39, 5)).route is None
    closed = next(r for r in state.world.regions if r.status.value == "closed")
    closed_tile = Tile(closed.floor.x, closed.floor.y)
    assert find_route(mask, start, closed_tile).route is None
    assert find_route(mask, start, mask.blocked[0]).route is None
    context = DecisionContext(RngState("12" * 32))
    none_available = replace(
        state, instances=tuple(InstanceUse(i.id, False) for i in state.catalog.instances)
    )
    assert resolve(Activity.OBSERVE_SERVER, none_available, start, context).selected is None
    placement = PlacementContext(
        PlacementSnapshot(state.world, state.catalog), (ITEM,), (), AT, timedelta(hours=7), SAFE
    )
    assert validate_placement(placement, ITEM.id, SLOT, Permission.MAPLE).reason is None
    assert validate_placement(placement, "missing.item", SLOT, Permission.MAPLE).reason is not None
    cases: list[tuple[str, Callable[[], Any]]] = [
        ("path.initial-house-BFS-diameter", lambda: find_route(mask, start, end)),
        ("path.accepted-53-step-travel", lambda: find_route(mask, Tile(3, 4), Tile(39, 5))),
        ("path.closed-region", lambda: find_route(mask, start, closed_tile)),
        ("path.blocked-target", lambda: find_route(mask, start, mask.blocked[0])),
        (
            "path.synthetic-disconnected-exhaustion",
            lambda: find_route(split, Tile(3, 4), Tile(39, 5)),
        ),
        (
            "recovery.blocked-source",
            lambda: recover(mask, Position(mask.blocked[0].tx, mask.blocked[0].ty)),
        ),
        ("recovery.invalid-source-fallback", lambda: recover(mask, Position(-1, -1))),
        ("resolution.allowed-all-eight", lambda: allowed_activities(state, start, context)),
        (
            "resolution.no-eligible-candidate",
            lambda: resolve(Activity.OBSERVE_SERVER, none_available, start, context),
        ),
        ("placement.valid", lambda: validate_placement(placement, ITEM.id, SLOT, Permission.MAPLE)),
        (
            "placement.invalid-item",
            lambda: validate_placement(placement, "missing.item", SLOT, Permission.MAPLE),
        ),
        ("layout.valid", lambda: validate_layout(base)),
        ("layout.invalid-S10", lambda: validate_layout(mutate(base, "S10"))),
        (
            "layout.multi-S1-S15-S17",
            lambda: validate_layout(mutate(mutate(mutate(base, "S1"), "S15"), "S17")),
        ),
    ]
    for activity in Activity:
        cases.append(
            (
                "resolution." + activity.value,
                partial(resolve, activity, state, start, context),
            )
        )
    # Candidate mutation is fixture preparation: keep it outside the timed validation calls.
    bad = mutate(base, "S10")
    multi = mutate(mutate(mutate(base, "S1"), "S15"), "S17")
    cases[12] = ("layout.invalid-S10", lambda: validate_layout(bad))
    cases[13] = ("layout.multi-S1-S15-S17", lambda: validate_layout(multi))
    rows = [measure(name, work) for name, work in cases]
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "method": (
            "perf_counter_ns synchronous pure call; 3 warmups + 30 raw trials; no backend budget"
        ),
        "fixture": {
            "grid": [44, 26],
            "regions": len(base.regions),
            "doors": len(base.doors),
            "objects": len(base.instances),
            "walkable": len(mask.walkable),
            "diameter_steps": steps,
            "diameter_start": [start.tx, start.ty],
            "diameter_end": [end.tx, end.ty],
        },
        "rows": rows,
    }
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "../var/r1a19/backend.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        print(row["name"], "p95_ms=", round(row["p95_ms"], 4), "max_ms=", round(row["max_ms"], 4))


if __name__ == "__main__":
    main()
