"""Every approved cell is protected independently of future world implementations."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from tests.world.harness import cell_cases
from tests.world.oracle import SPEC, Oracle, load_spec, parse_spec, require_approved


def test_approved_spec_and_coverage(spec_oracle: Oracle) -> None:
    assert tuple(len(table.rows) for table in spec_oracle.tables) == (8, 7, 28, 17, 12, 7, 10)
    assert spec_oracle.walks.columns == (
        "activity",
        "sleep",
        "rest",
        "read",
        "think",
        "write",
        "observe",
        "idle",
    )
    assert len(spec_oracle.walks.rows) == 7
    assert max(int(cell) for row in spec_oracle.walks.rows for cell in row[1:]) == 53
    assert load_spec() == spec_oracle


@pytest.mark.parametrize("number", range(1, 8))
def test_every_table_cell_mutation_is_rejected(spec_oracle: Oracle, number: int) -> None:
    table = spec_oracle.table(number)
    for table_number, row_index, column_index in cell_cases(spec_oracle):
        if table_number != number:
            continue
        cells = list(table.rows[row_index])
        cells[column_index] += "__changed"
        rows = list(table.rows)
        rows[row_index] = tuple(cells)
        tables = list(spec_oracle.tables)
        tables[number - 1] = replace(table, rows=tuple(rows))
        with pytest.raises(ValueError, match=f"T{number}:"):
            require_approved(replace(spec_oracle, tables=tuple(tables)))


def test_every_walk_length_mutation_is_rejected(spec_oracle: Oracle) -> None:
    for row_index, row in enumerate(spec_oracle.walks.rows):
        for column_index in range(1, len(row)):
            cells = list(row)
            cells[column_index] = str(int(cells[column_index]) + 1)
            rows = list(spec_oracle.walks.rows)
            rows[row_index] = tuple(cells)
            with pytest.raises(ValueError, match="T6 walks"):
                require_approved(
                    replace(spec_oracle, walks=replace(spec_oracle.walks, rows=tuple(rows)))
                )


@pytest.mark.parametrize(
    "old,new",
    [
        ("bedroom,bedroom,1,3,8,7,56", "bedroom,bedroom,1,3,9,7,63"),
        (
            "door.hall_bedroom,bedroom,central_hall,5,6",
            "door.hall_bedroom,bedroom,central_hall,5,7",
        ),
        ("### T4.", "### T9."),
        ("bedroom,bedroom,1,3,8,7,56,open,x0-9:y0-9", "bedroom,bedroom,1"),
        ("### T7.", "### T6."),
        ("| **sleep** | 0 | 31", "| **sleep** | 0 | 32"),
        ("| **idle** | 29 | 18 | 19 | 19 | 27 | 28 | 0 |", ""),
        (
            "bedroom,bedroom,1,3,8,7,56,open,x0-9:y0-9",
            "bedroom,bedroom,1,3,8,7,56,open,x0-9:y0-9\nbedroom,bedroom,1,3,8,7,56,open,x0-9:y0-9",
        ),
    ],
)
def test_modified_markdown_is_rejected(old: str, new: str) -> None:
    text = SPEC.read_text(encoding="utf-8")
    assert old in text
    with pytest.raises(ValueError):
        require_approved(parse_spec(text.replace(old, new, 1)))


def test_oracle_is_immutable(spec_oracle: Oracle) -> None:
    with pytest.raises(FrozenInstanceError):
        # Deliberately violate the frozen dataclass.
        spec_oracle.tables = ()  # type: ignore[misc]


def test_nonsemantic_markdown_change_is_accepted(spec_oracle: Oracle) -> None:
    require_approved(parse_spec(SPEC.read_text(encoding="utf-8") + "\nCommentary only.\n"))
    assert parse_spec(SPEC.read_text(encoding="utf-8").replace("\n", "\r\n")) == spec_oracle
