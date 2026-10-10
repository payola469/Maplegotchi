"""Read the approved Markdown tables, comparing every cell to a reviewed test snapshot.

No geometry, routing or capability algorithm lives here. Changes to the snapshot
require spec/ADR review; do not regenerate it to make a failing test pass.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "docs/architecture/maple-room-final-design-spec.md"
SNAPSHOT = Path(__file__).with_name("approved_tables.json")


@dataclass(frozen=True)
class Table:
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class Oracle:
    tables: tuple[Table, ...]
    walks: Table

    def table(self, number: int) -> Table:
        if not 1 <= number <= 7:
            raise ValueError("table number must be T1..T7")
        return self.tables[number - 1]


def _table(lines: list[list[str]], label: str) -> Table:
    if len(lines) < 2:
        raise ValueError(f"{label}: missing header or rows")
    width = len(lines[0])
    if any(len(row) != width or any(not cell for cell in row) for row in lines):
        raise ValueError(f"{label}: empty cell or wrong column count")
    # T7 intentionally repeats idle|walk; its key is (activity, new_points).
    keys = {tuple(row[:2] if label == "T7" else row[:1]) for row in lines[1:]}
    if len(set(lines[0])) != width or len(keys) != len(lines) - 1:
        raise ValueError(f"{label}: duplicate column or row key")
    return Table(tuple(lines[0]), tuple(tuple(row) for row in lines[1:]))


def parse_spec(text: str) -> Oracle:
    """Parse T1..T7 and the Markdown walk matrix, without approving new values."""
    text = text.replace("\r\n", "\n")
    sections = re.findall(r"^### T(\d+)\.[^\n]*\n(.*?)(?=^### |^## |\Z)", text, re.M | re.S)
    if [number for number, _ in sections] != [str(i) for i in range(1, 8)]:
        raise ValueError("expected exactly T1..T7 in order")
    tables: list[Table] = []
    for number, section in sections:
        blocks = re.findall(r"^```\n(.*?)^```", section, re.M | re.S)
        if len(blocks) != 1:
            raise ValueError(f"T{number}: expected one CSV block")
        try:
            rows = list(csv.reader(blocks[0].splitlines(), strict=True))
        except csv.Error as exc:
            raise ValueError(f"T{number}: invalid CSV") from exc
        tables.append(_table(rows, f"T{number}"))
    matrix = re.search(
        r"\*\*Walk lengths between the canonical activity points\*\*[^\n]*\n\n"
        r"((?:\|[^\n]+\n)+)",
        sections[5][1],
    )
    if matrix is None:
        raise ValueError("T6: missing walk matrix")
    lines = [
        [cell.strip().strip("*") for cell in row.strip().strip("|").split("|")]
        for row in matrix[1].splitlines()
    ]
    if not all(re.fullmatch(r":?-+:?", cell) for cell in lines[1]):
        raise ValueError("T6: invalid Markdown separator")
    if lines[0][0] != "":
        raise ValueError("T6: unexpected walk header")
    lines[0][0] = "activity"
    walks = _table([lines[0], *lines[2:]], "T6 walks")
    return Oracle(tuple(tables), walks)


def approved_oracle() -> Oracle:
    """Load the independent, version-controlled test expectation, never production data."""
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    tables = tuple(_table(data[f"T{i}"], f"T{i}") for i in range(1, 8))
    return Oracle(tables, _table(data["walks"], "walks"))


def require_approved(candidate: Oracle) -> None:
    expected = approved_oracle()
    for number, (actual, approved) in enumerate(
        zip(candidate.tables, expected.tables, strict=True), 1
    ):
        if actual != approved:
            raise ValueError(f"T{number}: differs from approved snapshot")
    if candidate.walks != expected.walks:
        raise ValueError("T6 walks: differs from approved snapshot")


def load_spec() -> Oracle:
    result = parse_spec(SPEC.read_text(encoding="utf-8"))
    require_approved(result)
    return result
