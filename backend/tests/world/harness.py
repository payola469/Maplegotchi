"""Reproducible test cases and allowlisted evidence summaries, with no live state."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from random import Random
from typing import Literal

from tests.world.oracle import Oracle


def cell_cases(oracle: Oracle, seed: int = 101) -> tuple[tuple[int, int, int], ...]:
    """Seeded ordering of an exhaustive cell corpus; no global or production RNG."""
    cases = [
        (number, row, column)
        for number, table in enumerate(oracle.tables, 1)
        for row, cells in enumerate(table.rows)
        for column in range(len(cells))
    ]
    Random(seed).shuffle(cases)  # noqa: S311 -- test-only, not security randomness
    return tuple(cases)


@dataclass(frozen=True)
class Evidence:
    check: Literal["oracle", "contracts", "fixtures"]
    passed: int
    failed: int


def capture_evidence(scratch_root: Path, evidence: Evidence) -> Path:
    """Exclusive scratch artifact; never accepts prompts, rows, seeds or credentials."""
    if evidence.check not in ("oracle", "contracts", "fixtures"):
        raise ValueError("unknown evidence check")
    if evidence.passed < 0 or evidence.failed < 0:
        raise ValueError("negative result count")
    path = scratch_root / "evidence.json"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(asdict(evidence), sort_keys=True) + "\n")
    return path
