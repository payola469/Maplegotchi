"""Counter-based deterministic RNG."""

from __future__ import annotations

from collections import Counter

import pytest

from maplegotchi.core.rng import RngStream
from tests.core.support import OTHER_SEED, SEED


def draws(stream: RngStream, n: int = 20) -> list[float]:
    return [stream.random() for _ in range(n)]


def test_known_answer_vector() -> None:
    # Pinned: if this changes, every persisted Maple would replay differently.
    r = RngStream(SEED, "tick", 1)
    assert [r.random() for _ in range(3)] == [
        0.7415451079513956,
        0.8878129361609476,
        0.8788256691126085,
    ]


def test_same_inputs_same_sequence() -> None:
    assert draws(RngStream(SEED, "tick", 7)) == draws(RngStream(SEED, "tick", 7))


@pytest.mark.parametrize(
    "other",
    [(OTHER_SEED, "tick", 7), (SEED, "interaction", 7), (SEED, "tick", 8), (SEED, "tick", 0)],
)
def test_any_input_change_changes_sequence(other: tuple[str, str, int]) -> None:
    assert draws(RngStream(SEED, "tick", 7)) != draws(RngStream(*other))


def test_counter_and_draw_index_cannot_collide() -> None:
    # "tick:1:" + draw 12 must differ from "tick:11:" + draw 2.
    a = RngStream(SEED, "tick", 1)
    b = RngStream(SEED, "tick", 11)
    assert draws(a, 13)[12] != draws(b, 3)[2]


def test_random_range_and_spread() -> None:
    values = [v for c in range(200) for v in draws(RngStream(SEED, "tick", c), 10)]
    assert all(0.0 <= v < 1.0 for v in values)
    assert 0.45 < sum(values) / len(values) < 0.55


def test_randint_is_inclusive_and_covers_range() -> None:
    seen = Counter(RngStream(SEED, "t", c).randint(3, 7) for c in range(2000))
    assert set(seen) == {3, 4, 5, 6, 7}
    assert RngStream(SEED, "t", 0).randint(5, 5) == 5
    with pytest.raises(ValueError):
        RngStream(SEED, "t", 0).randint(6, 5)


def test_weighted_choice_respects_weights() -> None:
    picks = Counter(
        RngStream(SEED, "t", c).weighted_choice(["a", "b", "c"], [1.0, 3.0, 0.0])
        for c in range(4000)
    )
    assert picks["c"] == 0
    assert 0.70 < picks["b"] / 4000 < 0.80


def test_weighted_choice_single_positive_weight() -> None:
    for c in range(50):
        assert RngStream(SEED, "t", c).weighted_choice(["x", "y"], [0.0, 2.0]) == "y"


@pytest.mark.parametrize(
    ("items", "weights"),
    [
        ([], []),
        (["a"], []),
        (["a", "b"], [1.0]),
        (["a"], [0.0]),
        (["a"], [-1.0]),
        (["a"], [float("nan")]),
        (["a"], [float("inf")]),
    ],
)
def test_weighted_choice_rejects_bad_weights(items: list[str], weights: list[float]) -> None:
    with pytest.raises(ValueError):
        RngStream(SEED, "t", 0).weighted_choice(items, weights)


@pytest.mark.parametrize(("stream", "counter"), [("", 0), ("a:b", 0), ("tick", -1)])
def test_stream_rejects_bad_identity(stream: str, counter: int) -> None:
    with pytest.raises(ValueError):
        RngStream(SEED, stream, counter)


def test_stream_rejects_bad_seed() -> None:
    with pytest.raises(ValueError):
        RngStream("00", "tick", 0)
