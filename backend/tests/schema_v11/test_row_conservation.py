"""Complete synthetic historical rows and high-water marks; no SQL execution."""

from __future__ import annotations

import builtins
import sqlite3
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any, NoReturn

import pytest

from tests.schema_v11.row_conservation import (
    DECISION_REFS,
    HISTORY_SCHEMA,
    HistoryImage,
    Row,
    TableImage,
    V11ConservationError,
    validate_history_conservation,
)

TABLE_NAMES = {
    "maple",
    "interaction_ledger",
    "observation",
    "journal_entry_observation",
    "journal_state",
    "goal",
    "decision",
    "action_event",
    "timeline_event",
    "journal_entry",
    "document",
    "tool_use",
    "memory",
    "memory_event",
    "daily_reflection",
    "conversation_message",
}
SEQUENCE_NAMES = {
    "observation",
    "decision",
    "action_event",
    "timeline_event",
    "journal_entry",
    "document",
    "tool_use",
    "memory",
    "memory_event",
    "daily_reflection",
    "conversation_message",
}


def image(target: bool = False) -> HistoryImage:
    tables = []
    for schema in HISTORY_SCHEMA:
        # These are raw row-comparison specimens, NOT valid domain snapshots.
        # Every field has a distinguishable value, including mutable cursors.
        row: Row = tuple(
            1 if column in schema.primary_key else f"exact:{schema.name}:{column}"
            for column in schema.columns
        )
        columns = schema.columns
        if target and schema.name == "decision":
            columns += DECISION_REFS
            row += (None, None, None)
        tables.append(TableImage(schema.name, columns, (row,)))
    return HistoryImage(tuple(tables), tuple((name, 1001) for name in sorted(SEQUENCE_NAMES)))


def table(image: HistoryImage, name: str) -> TableImage:
    return next(value for value in image.tables if value.name == name)


def replace_table(image: HistoryImage, changed: TableImage) -> HistoryImage:
    return replace(
        image, tables=tuple(changed if old.name == changed.name else old for old in image.tables)
    )


def cell(image: HistoryImage, name: str, column: str, value: Any) -> HistoryImage:
    old = table(image, name)
    row = list(old.rows[0])
    row[old.columns.index(column)] = value
    return replace_table(image, replace(old, rows=(tuple(row),)))


def test_exact_contract_inventory_and_all_old_fields() -> None:
    assert {schema.name for schema in HISTORY_SCHEMA} == TABLE_NAMES
    assert (
        sum(len(schema.columns) for schema in HISTORY_SCHEMA) == 177
    )  # 213 minus 36 life_state fields.
    assert {schema.name for schema in HISTORY_SCHEMA if schema.autoincrement} == SEQUENCE_NAMES
    assert next(
        schema.primary_key for schema in HISTORY_SCHEMA if schema.name == "interaction_ledger"
    ) == ("maple_id", "position")
    assert next(
        schema.primary_key
        for schema in HISTORY_SCHEMA
        if schema.name == "journal_entry_observation"
    ) == ("entry_id", "position")
    assert table(image(True), "decision").columns[-3:] == DECISION_REFS
    validate_history_conservation(image(), image(True))


@pytest.mark.parametrize(
    ("name", "column"),
    [(schema.name, column) for schema in HISTORY_SCHEMA for column in schema.columns],
)
def test_each_of_177_old_cells_must_be_preserved(name: str, column: str) -> None:
    target = image(True)
    schema = next(schema for schema in HISTORY_SCHEMA if schema.name == name)
    value = 2 if column in schema.primary_key else "changed-private-content"
    category = "identity" if column in schema.primary_key else "values"
    with pytest.raises(V11ConservationError, match=f"^{category}$"):
        validate_history_conservation(image(), cell(target, name, column, value))


@pytest.mark.parametrize("name", sorted(TABLE_NAMES))
@pytest.mark.parametrize("case", ["missing", "extra", "duplicate"])
def test_exact_row_identity_and_count(name: str, case: str) -> None:
    target = image(True)
    old = table(target, name)
    rows: tuple[Row, ...]
    if case == "missing":
        rows = ()
    elif case == "duplicate":
        rows = (*old.rows, old.rows[0])
    else:
        changed = list(old.rows[0])
        schema = next(schema for schema in HISTORY_SCHEMA if schema.name == name)
        changed[old.columns.index(schema.primary_key[0])] = 2
        rows = (*old.rows, tuple(changed))
    with pytest.raises(V11ConservationError, match=r"^identity$"):
        validate_history_conservation(image(), replace_table(target, replace(old, rows=rows)))


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (None, ""),
        (1, 1.0),
        (0.0, -0.0),
        ("é", "e\u0301"),
        ("Case", "case"),
        ('{"a":1,"b":2}', '{"b":2,"a":1}'),
        ("2026-10-14T00:00:00+00:00", "2026-10-14T00:00:00Z"),
        ("a\x00b", "ab"),
        ("line\n", "line"),
    ],
)
def test_exact_types_nulls_json_time_unicode_and_signed_zero(before: Any, after: Any) -> None:
    source = cell(image(), "memory", "text", before)
    matching = cell(image(True), "memory", "text", before)
    validate_history_conservation(source, matching)
    with pytest.raises(V11ConservationError, match=r"^values$"):
        validate_history_conservation(source, cell(matching, "memory", "text", after))


@pytest.mark.parametrize("column", DECISION_REFS)
def test_historical_decision_provenance_must_remain_null(column: str) -> None:
    with pytest.raises(V11ConservationError, match=r"^provenance$"):
        validate_history_conservation(image(), cell(image(True), "decision", column, 1))


@pytest.mark.parametrize(
    "case",
    [
        "missing_table",
        "duplicate_table",
        "extra_table",
        "missing_column",
        "extra_column",
        "reordered_column",
    ],
)
def test_complete_image_shape_required(case: str) -> None:
    source = image()
    if case == "missing_table":
        bad = replace(source, tables=source.tables[1:])
    elif case == "duplicate_table":
        bad = replace(source, tables=(*source.tables, source.tables[0]))
    elif case == "extra_table":
        bad = replace(source, tables=(*source.tables, TableImage("private-extra", (), ())))
    else:
        old = table(source, "maple")
        if case == "missing_column":
            changed = TableImage(old.name, old.columns[:-1], (old.rows[0][:-1],))
        elif case == "extra_column":
            changed = TableImage(old.name, (*old.columns, "extra"), ((*old.rows[0], None),))
        else:
            changed = TableImage(
                old.name, tuple(reversed(old.columns)), (tuple(reversed(old.rows[0])),)
            )
        bad = replace_table(source, changed)
    with pytest.raises(V11ConservationError, match=r"^image|columns$"):
        validate_history_conservation(bad, image(True))


@pytest.mark.parametrize("name", sorted(SEQUENCE_NAMES))
@pytest.mark.parametrize("case", ["missing", "changed", "duplicate", "below_max"])
def test_sequence_high_water_preservation(name: str, case: str) -> None:
    target = image(True)
    if case == "missing":
        values = tuple(row for row in target.sequences if row[0] != name)
    elif case == "duplicate":
        values = (*target.sequences, (name, 1001))
    else:
        values = tuple(
            (key, (0 if case == "below_max" else 1000) if key == name else value)
            for key, value in target.sequences
        )
    with pytest.raises(V11ConservationError, match=r"^sequence$"):
        validate_history_conservation(image(), replace(target, sequences=values))


def test_empty_table_keeps_high_water_and_absent_unused_sequence_is_valid() -> None:
    source, target = image(), image(True)
    source = replace_table(source, replace(table(source, "memory"), rows=()))
    target = replace_table(target, replace(table(target, "memory"), rows=()))
    validate_history_conservation(source, target)  # 1001 remains despite no rows.
    with pytest.raises(V11ConservationError, match=r"^sequence$"):
        validate_history_conservation(
            source,
            replace(target, sequences=tuple(row for row in target.sequences if row[0] != "memory")),
        )
    source = replace(source, sequences=tuple(row for row in source.sequences if row[0] != "memory"))
    target = replace(target, sequences=tuple(row for row in target.sequences if row[0] != "memory"))
    validate_history_conservation(source, target)


def test_unknown_sequence_refused() -> None:
    with pytest.raises(V11ConservationError, match=r"^sequence$"):
        validate_history_conservation(
            image(), replace(image(True), sequences=(*image(True).sequences, ("private-extra", 10)))
        )


def test_iteration_order_independent_but_semantic_positions_preserved() -> None:
    source, target = image(), image(True)
    for name in ("interaction_ledger", "journal_entry_observation"):
        for is_target in (False, True):
            current = target if is_target else source
            old = table(current, name)
            second = list(old.rows[0])
            second[old.columns.index("position")] = 2
            current = replace_table(current, replace(old, rows=(*old.rows, tuple(second))))
            if is_target:
                target = current
            else:
                source = current
    reversed_target = replace(
        target,
        tables=tuple(
            replace(item, rows=tuple(reversed(item.rows))) for item in reversed(target.tables)
        ),
        sequences=tuple(reversed(target.sequences)),
    )
    validate_history_conservation(source, reversed_target)
    with pytest.raises(V11ConservationError, match=r"^identity$"):
        validate_history_conservation(
            source, cell(reversed_target, "interaction_ledger", "position", 3)
        )


@pytest.mark.parametrize("value", [True, [], {}, b"value", float("nan"), float("inf")])
def test_non_sqlite_primitives_refused(value: Any) -> None:
    with pytest.raises(V11ConservationError, match=r"^rows$"):
        TableImage("maple", ("id",), ((value,),))


@pytest.mark.parametrize("value", [True, -1, "1001", None])
def test_sequence_value_types(value: Any) -> None:
    with pytest.raises(V11ConservationError, match=r"^sequence$"):
        HistoryImage((), (("memory", value),))


def test_deterministic_frozen_inputs_and_safe_refusal() -> None:
    source, target = image(), image(True)
    for _ in range(2):
        validate_history_conservation(source, target)
        with pytest.raises(V11ConservationError) as failure:
            validate_history_conservation(
                source, cell(target, "maple", "life_seed", "private-seed-marker")
            )
        assert failure.value.args == ("values",)
    assert source == image() and target == image(True)
    with pytest.raises(FrozenInstanceError):
        source.tables = ()  # type: ignore[misc]


def test_no_file_database_or_migration_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    source, target = image(), image(True)

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("unexpected I/O")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    validate_history_conservation(source, target)
