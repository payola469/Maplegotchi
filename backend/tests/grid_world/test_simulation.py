"""Independent whole-trace state-machine audit and reviewed long-run pin."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace

import pytest

from maplegotchi.core.activities import SPECS, Activity
from maplegotchi.core.world.layout_validation import LayoutCandidate
from tests.grid_world.fixtures import scenario, snapshot
from tests.grid_world.simulation import LONG_CYCLES, SCHEDULE, Report, simulate

# Reviewed STEP146: all 71,821 events audited before this NEW pin was recorded.
GRID_DIGEST = "b3287b3d13ed406fc98ecc5be58494e9f3ac9df7fc4b0a70cedb6e85ad5500d3"


def audit_trace(report: Report, candidate: LayoutCandidate) -> None:
    data = json.loads(report.trace_bytes())
    state = snapshot(candidate)
    allowed = {(t.tx, t.ty) for t in state.mask.walkable}
    points = {
        (p.instance_id, p.template.id): (p.template.approach.x, p.template.approach.y)
        for p in state.catalog.points
    }
    phase = "initial"
    current = (candidate.maple.tx, candidate.maple.ty)
    now = 0
    active = None
    seen: set[tuple[int, int]] = set()
    counts: Counter[str] = Counter()
    count = arrived = selected = 0
    for e in data["events"]:
        kind = e["kind"]
        tile = tuple(e["tile"])
        key = tuple(e["target"])
        assert tile in allowed and e["at_ms"] >= now
        if kind == "initial":
            assert phase == "initial" and tile == current and e["at_ms"] == 0
            phase = "ready"
        elif kind == "selected":
            assert phase == "ready" and tile == current and e["at_ms"] == now
            assert e["activity"] == SCHEDULE[selected % len(SCHEDULE)].value
            selected += 1
            active = e
            count = 0
            seen = {current}
            phase = "walking"
        elif kind == "step":
            assert phase == "walking" and abs(tile[0] - current[0]) + abs(tile[1] - current[1]) == 1
            assert e["at_ms"] == now + 250 and tile not in seen
            seen.add(tile)
            count += 1
        elif kind == "arrived":
            assert phase == "walking" and active is not None
            assert count == active["steps"] and tile == points[key]
            assert e["at_ms"] == active["at_ms"] + count * 250
            arrived = e["at_ms"]
            phase = "performing"
        elif kind == "completed":
            assert phase == "performing"
            assert e["at_ms"] == arrived + SPECS[Activity(e["activity"])].min_minutes * 60000
            counts[e["activity"]] += 1
            phase = "ready"
        else:
            raise AssertionError("unexpected event: " + kind)
        if active is not None and kind != "selected":
            assert e["activity"] == active["activity"] and e["target"] == active["target"]
        current = tile
        now = e["at_ms"]
    assert phase == "ready" and now == report.logical_ms and current == report.final_tile
    assert selected == report.transitions == report.successful_activities
    assert sum(e.kind == "step" for e in report.events) == report.movement_steps
    assert all(counts[a.value] == report.cycles for a in Activity)


def test_thirty_day_grid_digest_repeats_full_trace_three_times() -> None:
    candidate = scenario("L")
    first = simulate(candidate, cycles=LONG_CYCLES)
    expected = first.trace_bytes()
    assert first.digest == GRID_DIGEST
    assert first.logical_ms == 2608335000 and first.logical_ms >= 30 * 24 * 3600000
    assert first.transitions == first.successful_activities == 2160
    assert first.movement_steps == 65340 and first.max_route_steps == 53
    assert len(first.events) == 71821
    assert first.recovery_count == first.projection_rejections == 0
    assert first.final_tile == (21, 15) and first.final_activity == "idle"
    audit_trace(first, candidate)
    for _ in range(2):
        again = simulate(candidate, cycles=LONG_CYCLES)
        assert again == first and again.trace_bytes() == expected and again.digest == GRID_DIGEST


def test_reversed_release_inputs_give_identical_complete_schedule() -> None:
    candidate = scenario("A")
    shuffled = replace(
        candidate,
        regions=tuple(reversed(candidate.regions)),
        doors=tuple(reversed(candidate.doors)),
        zones=tuple(reversed(candidate.zones)),
        types=tuple(reversed(candidate.types)),
        instances=tuple(reversed(candidate.instances)),
        art=tuple(reversed(candidate.art)),
        legacy_targets=tuple(reversed(candidate.legacy_targets)),
    )
    first = simulate(candidate)
    audit_trace(first, candidate)
    assert simulate(shuffled).trace_bytes() == first.trace_bytes()


@pytest.mark.parametrize("cycles", [0, -1, 271, True])
def test_unbounded_or_invalid_run_rejected(cycles: int) -> None:
    with pytest.raises(ValueError, match="cycles"):
        simulate(scenario("A"), cycles=cycles)


@pytest.mark.parametrize("seed", [-1, 2**256, True])
def test_noncanonical_seed_rejected(seed: int) -> None:
    with pytest.raises(ValueError, match="seed"):
        simulate(scenario("A"), seed=seed)
