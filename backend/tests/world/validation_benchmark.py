"""Reproduce bounded R1A-16 costs: uv run python -m tests.world.validation_benchmark."""

from __future__ import annotations

import platform
from statistics import median
from time import perf_counter_ns

from maplegotchi.core.world.layout_validation import validate_layout
from tests.world.validation_corpus import canonical_candidate, mutate


def main() -> None:
    candidate = canonical_candidate()
    print(platform.platform(), platform.python_version())
    print(
        f"grid=44x26 regions={len(candidate.regions)} doors={len(candidate.doors)} "
        f"instances={len(candidate.instances)} types={len(candidate.types)} "
        f"art={len(candidate.art)}"
    )
    cases = (
        ("valid", candidate),
        ("invalid-S10", mutate(candidate, "S10")),
        ("multi-S1-S15-S17", mutate(mutate(mutate(candidate, "S1"), "S15"), "S17")),
    )
    for name, changed in cases:
        expected = validate_layout(changed)
        durations = []
        for _ in range(20):
            start = perf_counter_ns()
            result = validate_layout(changed)
            durations.append((perf_counter_ns() - start) / 1_000_000)
            if result != expected:
                raise AssertionError("Non-deterministic validation result")
        print(
            f"{name}: runs=20 errors={len(expected.errors)} ordering=stable "
            f"ms min={min(durations):.3f} median={median(durations):.3f} max={max(durations):.3f}"
        )


if __name__ == "__main__":
    main()
