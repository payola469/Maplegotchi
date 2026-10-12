"""Local evidence CLI; measurements stay outside deterministic trace serialization.

uv run python -m tests.grid_world.report [--repeat 3] [--memory] [--write-fixtures]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import time
import tracemalloc
from pathlib import Path
from typing import Any

from tests.grid_world.fixtures import scenario
from tests.grid_world.renderer import artifact_text
from tests.grid_world.simulation import LONG_CYCLES, simulate
from tests.world.pathfinding_tuning import report as timing_report


def timing_evidence() -> dict[str, Any]:
    runs, original_digest = timing_report()
    choices = []
    for run in runs:
        choices.append(
            {
                "ms_per_step": run.ms_per_step,
                "turn_penalty": run.turn_penalty,
                "t6_differences": run.differences,
                "total_turns": run.total_turns,
                "max_walk_ms": run.longest_walk_ms,
                "max_walking_cycle_basis_points": max(
                    leg.duration_ms * 10000 // (leg.duration_ms + leg.target_min_activity_ms)
                    for leg in run.legs
                ),
            }
        )
    selected = next(r for r in runs if (r.ms_per_step, r.turn_penalty) == (250, 1))
    examples = []
    for source, target in (
        ("write", "observe"),
        ("idle", "rest"),
        ("sleep", "write"),
        ("sleep", "observe"),
    ):
        leg = next(item for item in selected.legs if (item.source, item.target) == (source, target))
        examples.append(
            {
                "source": source,
                "target": target,
                "steps": leg.steps,
                "turns": leg.turns,
                "ms_per_step": 250,
                "turn_penalty": 1,
                "movement_ms": leg.duration_ms,
                "activity_ms": leg.target_min_activity_ms,
                "walking_cycle_basis_points": leg.duration_ms
                * 10000
                // (leg.duration_ms + leg.target_min_activity_ms),
            }
        )
    repeated = max(selected.legs, key=lambda leg: leg.turns)
    return {
        "original_r1a05_digest": original_digest,
        "runs": choices,
        "examples": examples,
        "most_turns": {
            "source": repeated.source,
            "target": repeated.target,
            "steps": repeated.steps,
            "turns": repeated.turns,
        },
        "turn_penalty_units": "integer path cost; no extra elapsed turn delay",
        "recommendation": "Retain provisional 250 ms/step, penalty1; no production changes.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--memory", action="store_true")
    parser.add_argument("--write-fixtures", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.repeat <= 5:
        parser.error("repeat must be 1..5")
    root = Path(__file__).resolve().parents[3]
    fixture = root / "docs/fixtures/maple-room/r1a-17/scripted-room-states.json"
    text = artifact_text()
    if args.write_fixtures:
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_text(text, encoding="utf-8", newline="\n")
    if not fixture.exists() or fixture.read_bytes() != text.encode("utf-8"):
        raise ValueError("fixture export differs; inspect before using --write-fixtures")
    candidate = scenario("L")
    durations = []
    first = None
    expected = b""
    for _ in range(args.repeat):
        began = time.perf_counter()
        result = simulate(candidate, cycles=LONG_CYCLES)
        trace = result.trace_bytes()
        durations.append(time.perf_counter() - began)
        if first is None:
            first = result
            expected = trace
        elif result != first or trace != expected:
            raise AssertionError("full repeated event trace changed")
    assert first is not None
    peak = None
    if args.memory:
        tracemalloc.start()
        measured = simulate(candidate, cycles=LONG_CYCLES)
        measured_bytes = measured.trace_bytes()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert measured_bytes == expected
    summary = {
        "version": first.version,
        "seed": first.seed,
        "cycles": first.cycles,
        "logical_ms": first.logical_ms,
        "transitions": first.transitions,
        "successful_activities": first.successful_activities,
        "movement_steps": first.movement_steps,
        "max_route_steps": first.max_route_steps,
        "recovery_count": first.recovery_count,
        "projection_rejections": first.projection_rejections,
        "final_tile": first.final_tile,
        "final_activity": first.final_activity,
        "event_count": len(first.events),
        "trace_bytes": len(expected),
        "sha256": hashlib.sha256(expected).hexdigest(),
        "repeat_count": args.repeat,
        "bitwise_equal": True,
        "execution_seconds_including_serialization": durations,
        "median_seconds": statistics.median(durations),
        "peak_python_allocations_bytes": peak,
        "memory_method": "tracemalloc isolated run; Python allocations only, not process RSS"
        if peak is not None
        else "not measured",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "fixture_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "timing": timing_evidence(),
    }
    print(json.dumps(summary, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
