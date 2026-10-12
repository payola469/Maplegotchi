"""Deterministic measurement correctness; no hosted-runner timing budgets."""

from collections.abc import Iterator

import pytest

from maplegotchi.core.world.coordinates import Tile
from tests.world import performance_benchmark as benchmark


def test_diameter_searches_all_components() -> None:
    cells = (*(Tile(x, 0) for x in range(4)), Tile(10, 10))
    start, end, steps = benchmark.diameter(cells)
    assert (start, end, steps) == (Tile(0, 0), Tile(3, 0), 3)


def test_measure_preserves_outliers_and_untimed_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    samples = [n * 1_000_000 for n in range(1, 30)] + [999_000_000]
    clock: Iterator[int] = iter(value for n in samples for value in (0, n))
    monkeypatch.setattr(benchmark, "perf_counter_ns", lambda: next(clock))
    calls = []

    def work() -> int:
        calls.append(1)
        return 7

    result = benchmark.measure("controlled", work)
    assert len(calls) == 34
    assert result["raw_ns"] == samples
    assert result["p95_ms"] == 29
    assert result["max_ms"] == 999


def test_measure_rejects_changed_results() -> None:
    values = iter([1, 1, 1, 1, 2])
    with pytest.raises(AssertionError, match="unstable"):
        benchmark.measure("unstable", lambda: next(values), runs=1)
