"""Diagnostic artifacts do not grant D05 approval or fabricate native evidence."""

from copy import deepcopy
from typing import Any

import pytest

from tests.schema_v11.life_evidence import FORMAT, collect, compare


def evidence(platform: str) -> dict[str, Any]:
    return dict(
        format=FORMAT,
        diagnostic_only=True,
        source_sha="1" * 40,
        checkout_sha="2" * 40,
        runtime=dict(platform=platform),
        portable=dict(
            trace=[dict(tick=i, revision=i + 1, digest=f"{i:064x}") for i in range(1, 13)],
            final_digest=f"{12:064x}",
            final_revision=13,
            ticks=12,
            continuous_runs=3,
            restarted_segments=6,
            exact_typed_image_equal=True,
            duplicate_arrivals=0,
            mid_edge_restore_verified=True,
            critical_mid_edge="persisted_exact_entry:D01_APPROVED",
        ),
        processes=dict(writers=list(range(10, 16)), reader=16, exit_order_verified=True),
    )


def test_diagnostic_comparison_requires_same_revisions_and_full_trace() -> None:
    left, right = evidence("Linux"), evidence("Windows")
    before = deepcopy((left, right))
    compare(left, right)
    assert (left, right) == before


@pytest.mark.parametrize(
    "bad",
    ["source", "checkout", "trace", "digest", "empty", "native", "pin", "process", "invariant"],
)
def test_diagnostic_comparison_refuses_incomplete_or_mismatched_evidence(bad: str) -> None:
    left, right = evidence("Linux"), evidence("Windows")
    if bad in {"source", "checkout"}:
        right[bad + "_sha"] = "3" * 40
    elif bad == "trace":
        right["portable"]["trace"][0]["revision"] = 99  # same final hash cannot hide trace mismatch
    elif bad == "digest":
        right["portable"]["final_digest"] = "different"
    elif bad == "empty":
        right["portable"]["trace"] = []
    elif bad == "native":
        right["runtime"]["platform"] = "Linux"  # two Linux artifacts are not native proof
    elif bad == "process":
        right["processes"]["reader"] = right["processes"]["writers"][0]
    elif bad == "invariant":
        right["portable"]["exact_typed_image_equal"] = False
    else:
        right["diagnostic_only"] = False
    with pytest.raises(ValueError):
        compare(left, right)


def test_mid_edge_restarts_and_three_continuous_runs_have_exact_typed_images() -> None:
    actual = collect()
    portable = actual["portable"]
    assert portable["ticks"] == 12 and len(portable["trace"]) == 12
    assert portable["mid_edge_restore_verified"] is True
    assert portable["critical_mid_edge"] == "persisted_exact_entry:D01_APPROVED"
    assert portable["duplicate_arrivals"] == 0
    assert len(actual["processes"]["writers"]) == 6
    assert actual["processes"]["exit_order_verified"] is True
