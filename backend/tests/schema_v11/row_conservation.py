"""Pure full-row history conservation oracle (Contract §§3/5/10, T01/T08).

Inputs are explicitly captured synthetic values, not handles or paths. All 16
existing tables other than life_state are compared. life_state's reviewed
location/point/Travel mapping and complete reconstruction are deliberately NOT
proved here. This cannot establish FK/integrity, migration or durable recovery.
No conversion, row rewriting or new persisted serialization is performed.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

from tests.schema_v11.declarations import V10_TABLES

Cell = int | float | str | None
Row = tuple[Cell, ...]
ErrorCategory = Literal["image", "columns", "rows", "identity", "values", "provenance", "sequence"]
DECISION_REFS = ("executed_layout_revision", "executed_point_host", "executed_point_id")


class V11ConservationError(ValueError):
    """Fixed refusal categories only, never private history or seed values."""

    def __init__(self, category: ErrorCategory) -> None:
        super().__init__(category)


@dataclass(frozen=True, slots=True)
class TableSchema:
    name: str
    columns: tuple[str, ...]
    primary_key: tuple[str, ...]
    autoincrement: bool


def _schema(name: str, sql: str) -> TableSchema:
    # Inspect only trusted frozen declaration text. Never execute DDL or import
    # the rehearsal converter. This is not a parser for arbitrary SQL inputs.
    columns = tuple(re.findall(r"^ ([a-z_]+) (?:INTEGER|TEXT|REAL)\b", sql, re.MULTILINE))
    composite = re.search(r"PRIMARY KEY \(([^)]+)\)", sql)
    if composite:
        key = tuple(part.strip() for part in composite[1].split(","))
    else:
        key = tuple(
            column
            for column in columns
            if re.search(rf"^ {column} .*PRIMARY KEY", sql, re.MULTILINE)
        )
    return TableSchema(name, columns, key, "AUTOINCREMENT" in sql)


HISTORY_SCHEMA = tuple(
    _schema(name, sql) for name, sql in sorted(V10_TABLES.items()) if name != "life_state"
)


@dataclass(frozen=True, slots=True)
class TableImage:
    name: str
    columns: tuple[str, ...]
    rows: tuple[Row, ...]

    def __post_init__(self) -> None:
        if (
            type(self.name) is not str
            or type(self.columns) is not tuple
            or any(type(column) is not str for column in self.columns)
        ):
            raise V11ConservationError("image")
        if type(self.rows) is not tuple:
            raise V11ConservationError("rows")
        for row in self.rows:
            if type(row) is not tuple or len(row) != len(self.columns):
                raise V11ConservationError("rows")
            for cell in row:
                if type(cell) not in (int, float, str, type(None)) or (
                    type(cell) is float and not math.isfinite(cell)
                ):
                    raise V11ConservationError("rows")


@dataclass(frozen=True, slots=True)
class HistoryImage:
    """Complete supplied rows for the 16 compared tables, plus old sequences."""

    tables: tuple[TableImage, ...]
    sequences: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if type(self.tables) is not tuple or any(
            type(table) is not TableImage for table in self.tables
        ):
            raise V11ConservationError("image")
        if type(self.sequences) is not tuple:
            raise V11ConservationError("sequence")
        for row in self.sequences:
            if (
                type(row) is not tuple
                or len(row) != 2
                or type(row[0]) is not str
                or type(row[1]) is not int
                or row[1] < 0
            ):
                raise V11ConservationError("sequence")


def _exact(row: Row) -> tuple[tuple[type[object], Cell], ...]:
    # Equality must not hide bool/int/float coercion, signed-zero changes, or
    # rewriting old JSON/UTC text. Floats compare by their exact finite value.
    return tuple((type(cell), cell.hex() if type(cell) is float else cell) for cell in row)


def _keyed(table: TableImage, schema: TableSchema) -> dict[tuple[Cell, ...], Row]:
    positions = tuple(table.columns.index(column) for column in schema.primary_key)
    result: dict[tuple[Cell, ...], Row] = {}
    for row in table.rows:
        key = tuple(row[index] for index in positions)
        if any(type(cell) is not int or cell < 0 for cell in key) or key in result:
            raise V11ConservationError("identity")
        result[key] = row
    return result


def _tables(image: HistoryImage, target: bool) -> dict[str, TableImage]:
    if type(image) is not HistoryImage:
        raise V11ConservationError("image")
    tables = {table.name: table for table in image.tables}
    if len(tables) != len(image.tables) or set(tables) != {
        schema.name for schema in HISTORY_SCHEMA
    }:
        raise V11ConservationError("image")
    for schema in HISTORY_SCHEMA:
        columns = schema.columns + (DECISION_REFS if target and schema.name == "decision" else ())
        if tables[schema.name].columns != columns:
            raise V11ConservationError("columns")
    return tables


def _sequences(image: HistoryImage, tables: dict[str, TableImage]) -> dict[str, int]:
    sequences = dict(image.sequences)
    names = {schema.name for schema in HISTORY_SCHEMA if schema.autoincrement}
    if len(sequences) != len(image.sequences) or not set(sequences) <= names:
        raise V11ConservationError("sequence")
    for schema in HISTORY_SCHEMA:
        if schema.autoincrement:
            rows = tables[schema.name].rows
            ids = [row[schema.columns.index("id")] for row in rows]
            if ids and (
                schema.name not in sequences
                or any(type(id) is not int or id > sequences[schema.name] for id in ids)
            ):
                raise V11ConservationError("sequence")
    return sequences


def validate_history_conservation(source: HistoryImage, target: HistoryImage) -> None:
    """Compare every old cell and keyed row; preserve all old sequence entries.

    Row and table iteration order are irrelevant; semantic ordering columns
    (e.g. ledger/association positions) remain exact. Historical decision rows
    retain every old value and gain only the three approved NULL references.
    Sequence high-water values may exceed MAX(id), even for an empty table.
    Neither supplied image is a database-validity or complete-life certificate.
    """
    old = _tables(source, False)
    new = _tables(target, True)
    for schema in HISTORY_SCHEMA:
        left = _keyed(old[schema.name], schema)
        right = _keyed(new[schema.name], schema)
        if set(left) != set(right):
            raise V11ConservationError("identity")
        for key, before in left.items():
            after = right[key]
            if schema.name == "decision":
                if after[-3:] != (None, None, None):
                    raise V11ConservationError("provenance")
                after = after[:-3]
            if _exact(before) != _exact(after):
                raise V11ConservationError("values")
    if _sequences(source, old) != _sequences(target, new):
        raise V11ConservationError("sequence")
