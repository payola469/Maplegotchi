"""Counter-based deterministic randomness (CLAUDE.md §3.7, ADR-0007).

Every random decision is drawn from a stream derived from
(life_seed, stream name, counter). Counters live in Maple's state and are
persisted with it, so a restart continues the exact same sequence and any
event can be replayed from stored inputs. Python's global `random` is never used.

Draws use keyed BLAKE2b and integer arithmetic only, so results are
bit-identical on every platform.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

SEED_HEX_LENGTH = 64  # 256-bit life seed
_MANTISSA_SCALE = float(1 << 53)


def validate_seed_hex(seed_hex: str) -> bytes:
    """Return the seed bytes, or raise if seed_hex is not 64 lowercase hex chars."""
    if not isinstance(seed_hex, str) or len(seed_hex) != SEED_HEX_LENGTH:
        raise ValueError("life seed must be 64 hex characters")
    if seed_hex != seed_hex.lower():
        raise ValueError("life seed must be lowercase hex")
    try:
        return bytes.fromhex(seed_hex)
    except ValueError as exc:
        raise ValueError("life seed must be hex") from exc


def _validate_counter(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")


@dataclass(frozen=True, slots=True)
class RngState:
    """The persisted part of Maple's randomness: the seed and per-stream counters."""

    seed_hex: str
    tick_counter: int = 0
    interaction_counter: int = 0
    decision_counter: int = 0  # stream "decision" (ADR-0026 §9)

    def __post_init__(self) -> None:
        validate_seed_hex(self.seed_hex)
        _validate_counter("tick_counter", self.tick_counter)
        _validate_counter("interaction_counter", self.interaction_counter)
        _validate_counter("decision_counter", self.decision_counter)


class RngStream:
    """Deterministic draws for a single event, derived from (seed, stream, counter)."""

    __slots__ = ("_draws", "_key", "_prefix")

    def __init__(self, seed_hex: str, stream: str, counter: int) -> None:
        if not stream or ":" in stream:
            raise ValueError("stream must be a non-empty name without ':'")
        _validate_counter("counter", counter)
        self._key = validate_seed_hex(seed_hex)
        self._prefix = f"{stream}:{counter}:".encode()
        self._draws = 0

    def random(self) -> float:
        """Uniform float in [0.0, 1.0)."""
        digest = hashlib.blake2b(
            self._prefix + str(self._draws).encode(), key=self._key, digest_size=8
        ).digest()
        self._draws += 1
        return (int.from_bytes(digest, "big") >> 11) / _MANTISSA_SCALE

    def randint(self, low: int, high: int) -> int:
        """Uniform int in [low, high], both inclusive."""
        if low > high:
            raise ValueError("low must be <= high")
        return low + int(self.random() * (high - low + 1))

    def weighted_choice(self, items: Sequence[T], weights: Sequence[float]) -> T:
        """Pick one item with probability proportional to its weight."""
        if not items or len(items) != len(weights):
            raise ValueError("items and weights must be non-empty and equal length")
        for w in weights:
            if not math.isfinite(w) or w < 0:
                raise ValueError("weights must be finite and >= 0")
        total = sum(weights)
        if total <= 0:
            raise ValueError("at least one weight must be positive")
        target = self.random() * total
        cumulative = 0.0
        chosen = None
        for item, weight in zip(items, weights, strict=True):
            if weight <= 0:
                continue
            cumulative += weight
            chosen = item
            if target < cumulative:
                return item
        # Floating-point rounding can leave target == total; fall back to the last positive item.
        if chosen is None:  # unreachable: total > 0 guarantees a positive weight
            raise AssertionError("no positive weight")
        return chosen
