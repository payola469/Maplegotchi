"""Pure test-only identity proof; accepts validated layouts, never database handles.

Contract §§5/7/9: these four row shapes contain keys only. Room membership and
point/slot geometry remain in the validated document/catalog, not new columns.
Point and slot local IDs have separate host-scoped namespaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tests.schema_v11.layout_codec import LayoutDocument

HostRow = tuple[int, str]
RoomRow = tuple[int, str, str]
LocalRow = tuple[int, str, str]
ErrorCategory = Literal["document", "revision", "rows", "duplicate", "mismatch"]


class V11LayoutKeysError(ValueError):
    """Refusals expose only a fixed category, never supplied identifiers."""

    def __init__(self, category: ErrorCategory) -> None:
        super().__init__(category)


def _revision(value: object) -> None:
    if type(value) is not int or value < 1:
        raise V11LayoutKeysError("revision")


def _rows(value: object, width: int) -> None:
    # No coercion, iterable consumption, or set conversion of malformed input.
    if type(value) is not tuple:
        raise V11LayoutKeysError("rows")
    for row in value:
        if type(row) is not tuple or len(row) != width:
            raise V11LayoutKeysError("rows")
        _revision(row[0])
        if any(type(cell) is not str or not 1 <= len(cell) <= 128 for cell in row[1:]):
            raise V11LayoutKeysError("rows")


@dataclass(frozen=True, slots=True)
class LayoutKeys:
    """Immutable proof rows in frozen schema column order; not a DB snapshot."""

    layout_host: tuple[HostRow, ...]
    layout_room: tuple[RoomRow, ...]
    layout_point: tuple[LocalRow, ...]
    layout_slot: tuple[LocalRow, ...]

    def __post_init__(self) -> None:
        _rows(self.layout_host, 2)
        _rows(self.layout_room, 3)
        _rows(self.layout_point, 3)
        _rows(self.layout_slot, 3)


def project_layout_keys(document: LayoutDocument, revision: int) -> LayoutKeys:
    """Project keys from already validated immutable values, without reloading.

    This trusts the Layout Codec validation boundary; it grants no database or
    life-state admission and does not authenticate manually forged documents.
    """
    _revision(revision)
    if type(document) is not LayoutDocument:
        raise V11LayoutKeysError("document")
    return LayoutKeys(
        layout_host=tuple(sorted((revision, host.id) for host in document.catalog.instances)),
        layout_room=tuple(
            sorted((revision, room.id, room.kind.value) for room in document.world.regions)
        ),
        layout_point=tuple(
            sorted(
                (revision, point.instance_id, point.template.id)
                for point in document.catalog.points
            )
        ),
        layout_slot=tuple(
            sorted(
                (revision, slot.instance_id, slot.template.id) for slot in document.catalog.slots
            )
        ),
    )


def _compare(
    actual: tuple[tuple[int | str, ...], ...],
    expected: tuple[tuple[int | str, ...], ...],
    identity_width: int,
) -> None:
    # Room kind is a derived value, not part of the room primary key. Detect
    # duplicates before comparing rows so conflicting kinds cannot hide them.
    if len({row[:identity_width] for row in actual}) != len(actual):
        raise V11LayoutKeysError("duplicate")
    if tuple(sorted(actual)) != expected:
        raise V11LayoutKeysError("mismatch")


def validate_layout_keys(document: LayoutDocument, revision: int, rows: LayoutKeys) -> None:
    """Refuse any difference from the exact four projections, ignoring row order.

    Rows are explicitly supplied synthetic values. No pointer, transaction,
    query, catalog discovery, repair, or mutation occurs here.
    """
    expected = project_layout_keys(document, revision)
    if type(rows) is not LayoutKeys:
        raise V11LayoutKeysError("rows")
    _compare(rows.layout_host, expected.layout_host, 2)
    _compare(rows.layout_room, expected.layout_room, 2)
    _compare(rows.layout_point, expected.layout_point, 3)
    _compare(rows.layout_slot, expected.layout_slot, 3)
