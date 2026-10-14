"""Explicit dormant canonical Save/Load port, not a shipped SQLite implementation.

No path discovery, birth, schema upgrade, retry, clock, fallback or lifecycle
activation. A binding MUST admit all rows/schema/catalog in one consistent read
and MUST atomically commit the full image with optimistic life revision checks.
Only the synthetic-owned test binding exists. STEP 225 permits an explicitly
selected canonical lifecycle; default integration and operational gates remain
closed. No production budget policy is selected by this interface.
"""

import math
from dataclasses import dataclass
from typing import Literal, Protocol

from maplegotchi.persistence.boundary import capture_life
from maplegotchi.persistence.life_record import CanonicalLife, Cell, life_fields

Failure = Literal["version", "revision", "invalid", "ownership", "storage", "uncertain"]
TableRows = tuple[str, tuple[str, ...], tuple[tuple[Cell, ...], ...]]
TABLE_NAMES = frozenset(
    """activity_kind room_kind layout_revision world_state layout_host layout_room
layout_point layout_slot world_event display_placement maple life_state interaction_ledger
observation journal_entry journal_entry_observation journal_state timeline_event goal decision
action_event tool_use memory memory_event conversation_message document daily_reflection""".split()
)


class PersistenceError(ValueError):
    """Fixed category only. Uncertain commit acknowledgement requires inspection.

    Callers must not retry automatically, infer rollback or replace current state
    after this failure. A binding distinguishes definite rejection from uncertain
    durable outcomes; this port never attempts to recover either.
    """

    def __init__(self, category: Failure) -> None:
        super().__init__(category)


@dataclass(frozen=True, slots=True)
class CanonicalSnapshot:
    """Full immutable SQL image plus admitted life, no additional persisted format.

    Container shape is checked here; the binding validates schema and every row,
    FK, history, sequence and catalog before returning or saving this value.
    """

    life: CanonicalLife
    tables: tuple[TableRows, ...]
    sequences: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if type(self.tables) is not tuple or type(self.sequences) is not tuple:
            raise PersistenceError("invalid")
        names = []
        for table in self.tables:
            if type(table) is not tuple or len(table) != 3:
                raise PersistenceError("invalid")
            name, columns, rows = table
            if (
                type(name) is not str
                or type(columns) is not tuple
                or not columns
                or any(type(column) is not str for column in columns)
                or len(set(columns)) != len(columns)
                or type(rows) is not tuple
            ):
                raise PersistenceError("invalid")
            names.append(name)
            for row in rows:
                if type(row) is not tuple or len(row) != len(columns):
                    raise PersistenceError("invalid")
                if any(type(cell) not in (int, float, str, type(None)) for cell in row):
                    raise PersistenceError("invalid")
                if any(type(cell) is float and not math.isfinite(cell) for cell in row):
                    raise PersistenceError("invalid")
        if len(names) != len(TABLE_NAMES) or set(names) != TABLE_NAMES:
            raise PersistenceError("invalid")
        sequence_names = []
        for row in self.sequences:
            if (
                type(row) is not tuple
                or len(row) != 2
                or type(row[0]) is not str
                or type(row[1]) is not int
                or row[1] < 0
            ):
                raise PersistenceError("invalid")
            sequence_names.append(row[0])
        if len(set(sequence_names)) != len(sequence_names):
            raise PersistenceError("invalid")
        try:
            capture_life(self.life)
        except ValueError:
            raise PersistenceError("invalid") from None
        _, columns, rows = next(table for table in self.tables if table[0] == "life_state")
        values = dict(life_fields(self.life.record))
        if set(columns) != set(values) or len(rows) != 1:
            raise PersistenceError("invalid")
        expected = tuple(values[column] for column in columns)
        if tuple((type(v), v.hex() if type(v) is float else v) for v in rows[0]) != tuple(
            (type(v), v.hex() if type(v) is float else v) for v in expected
        ):
            raise PersistenceError("invalid")


class PersistencePort(Protocol):
    """Binding owns its explicitly supplied handle; load never creates a database."""

    def load(self, *, schema_version: int) -> CanonicalSnapshot: ...

    def save(
        self, snapshot: CanonicalSnapshot, *, schema_version: int, expected_revision: int
    ) -> None: ...


class LifecyclePort(PersistencePort, Protocol):
    """Explicit fresh creation and handle release, never load-as-create.

    The caller supplies a synthetic-owned binding. create MUST refuse any
    existing file; close MUST release all connections owned by that binding.
    Normal startup never selects this protocol automatically.
    """

    def create(self, snapshot: CanonicalSnapshot, *, schema_version: int) -> None: ...

    def close(self) -> None: ...


def _version(version: int) -> None:
    if type(version) is not int or version != 11:
        raise PersistenceError("version")


def load(port: PersistencePort, *, schema_version: int) -> CanonicalSnapshot:
    """Explicit restore only; no heartbeat, settling or downtime evolution."""
    _version(schema_version)
    result = port.load(schema_version=schema_version)
    if type(result) is not CanonicalSnapshot:
        raise PersistenceError("invalid")
    # Recheck admission at this boundary, including accidental mutable containers.
    return CanonicalSnapshot(result.life, result.tables, result.sequences)


def save(
    port: PersistencePort,
    snapshot: CanonicalSnapshot,
    *,
    schema_version: int,
    expected_revision: int,
) -> None:
    """One explicit atomic save attempt; acknowledge only the binding's success."""
    _version(schema_version)
    if type(expected_revision) is not int or expected_revision < 1:
        raise PersistenceError("revision")
    if type(snapshot) is not CanonicalSnapshot:
        raise PersistenceError("invalid")
    admitted = CanonicalSnapshot(snapshot.life, snapshot.tables, snapshot.sequences)
    if admitted.life.record.revision != expected_revision + 1:
        raise PersistenceError("revision")
    port.save(admitted, schema_version=schema_version, expected_revision=expected_revision)
