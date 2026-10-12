"""Timing evidence uses actual accepted routes and full activity-cycle denominators."""

from __future__ import annotations

from tests.grid_world.report import timing_evidence
from tests.world.pathfinding_tuning import report


def test_all_timing_candidates_keep_original_pin_and_cycle_arithmetic() -> None:
    runs, digest = report()
    evidence = timing_evidence()
    assert digest == "722a4e5359852fa4c049a985210e6a8f07a663df86bdf6c4a0a8218e8c51c936"
    assert evidence["original_r1a05_digest"] == digest
    assert len(runs) == len(evidence["runs"]) == 8
    for run, row in zip(runs, evidence["runs"], strict=True):
        assert run.differences == 0 and len(run.legs) == 49
        assert run.longest_walk_ms == 53 * run.ms_per_step
        assert row["max_walking_cycle_basis_points"] == max(
            10000 * leg.duration_ms // (leg.duration_ms + leg.target_min_activity_ms)
            for leg in run.legs
        )
        assert run.total_turns == (166 if run.turn_penalty == 0 else 130)
    examples = evidence["examples"]
    assert [case["steps"] for case in examples] == [5, 18, 52, 53]
    assert [case["movement_ms"] for case in examples] == [1250, 4500, 13000, 13250]
    assert examples[-1]["walking_cycle_basis_points"] == 422
