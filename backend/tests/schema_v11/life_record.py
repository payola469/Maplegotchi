"""Compatibility imports for the accepted pure implementation."""

from __future__ import annotations

import json
from typing import cast

from maplegotchi.persistence.life_record import (
    INTEGER_FIELDS as INTEGER_FIELDS,
)
from maplegotchi.persistence.life_record import (
    LIFE_FIELDS as LIFE_FIELDS,
)
from maplegotchi.persistence.life_record import (
    NEED_FIELDS as NEED_FIELDS,
)
from maplegotchi.persistence.life_record import (
    NULLABLE_FIELDS as NULLABLE_FIELDS,
)
from maplegotchi.persistence.life_record import (
    TIME_FIELDS as TIME_FIELDS,
)
from maplegotchi.persistence.life_record import (
    CanonicalLife as CanonicalLife,
)
from maplegotchi.persistence.life_record import (
    CanonicalLifeRecord as CanonicalLifeRecord,
)
from maplegotchi.persistence.life_record import (
    Cell as Cell,
)
from maplegotchi.persistence.life_record import (
    DecisionReference as DecisionReference,
)
from maplegotchi.persistence.life_record import (
    ErrorCategory as ErrorCategory,
)
from maplegotchi.persistence.life_record import (
    GoalRow as GoalRow,
)
from maplegotchi.persistence.life_record import (
    IdentityRow as IdentityRow,
)
from maplegotchi.persistence.life_record import (
    LedgerRow as LedgerRow,
)
from maplegotchi.persistence.life_record import (
    V11LifeError as V11LifeError,
)
from maplegotchi.persistence.life_record import _utc
from maplegotchi.persistence.life_record import (
    life_fields as life_fields,
)
from maplegotchi.persistence.life_record import (
    reconstruct_life as reconstruct_life,
)
from tests.schema_v11.row_conservation import (
    HistoryImage,
    V11ConservationError,
    validate_history_conservation,
)


def _exact(values: tuple[tuple[str, Cell], ...]) -> tuple[tuple[str, type[object], Cell], ...]:
    return tuple(
        (name, type(value), value.hex() if type(value) is float else value)
        for name, value in values
    )


def validate_restart_equivalence(
    before: CanonicalLife,
    after: CanonicalLife,
    *,
    source_history: HistoryImage,
    target_history: HistoryImage,
) -> None:
    """Pure exact reconstruction + existing history conservation, never a restart.

    Source/target HistoryImages use the existing conservation proof's documented
    old/new decision-column convention. No converter is implemented here.
    """
    if type(before) is not CanonicalLife or type(after) is not CanonicalLife:
        raise V11LifeError("conservation")
    if _exact(life_fields(before.record)) != _exact(life_fields(after.record)) or before != after:
        raise V11LifeError("conservation")
    try:
        validate_history_conservation(source_history, target_history)
    except V11ConservationError:
        raise V11LifeError("conservation") from None
    # Tie the conserved facts back to the reconstructed life, rather than
    # accepting two individually valid but unrelated proofs.
    tables = {table.name: table for table in target_history.tables}
    if (
        tables["maple"].rows != (after.identity_row,)
        or tuple(sorted(tables["interaction_ledger"].rows, key=lambda row: cast(int, row[1])))
        != after.ledger_rows
    ):
        raise V11LifeError("conservation")
    born_rows = tuple(row for row in tables["timeline_event"].rows if row[4] == "born")
    if (
        len(born_rows) != 1
        or born_rows[0][1] != after.record.maple_id
        or _utc(cast(str, born_rows[0][5])) != after.identity.born_at
    ):
        raise V11LifeError("conservation")
    try:
        payload = json.loads(cast(str, born_rows[0][6]), object_pairs_hook=lambda pairs: pairs)
    except (ValueError, TypeError):
        raise V11LifeError("conservation") from None
    if payload != [("name", after.identity.name)]:
        raise V11LifeError("conservation")
    history_goals = {row[0]: row for row in tables["goal"].rows}
    if any(history_goals.get(row[0]) != row for row in after.goal_rows):
        raise V11LifeError("conservation")
    columns = tables["decision"].columns
    decision_refs = {
        (row[columns.index("id")], row[columns.index("maple_id")], row[columns.index("revision")])
        for row in tables["decision"].rows
    }
    if not set(after.decisions) <= decision_refs:
        raise V11LifeError("conservation")
