"""Pure supplied-row layout snapshot proof (Contract §§5-7/9, T05/T12).

No database snapshot is acquired here. LifeReference is only the four-column
projection needed for layout FK checks, never a reconstructed or admitted life.
Complete life/Travel validation and transaction acquisition remain mandatory
separate prerequisites. These functions perform no writer/editor operations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from maplegotchi.persistence.layout_codec import (
    CatalogSnapshot,
    LayoutContext,
    LayoutDocument,
    V11LayoutFormatError,
    decode_layout_document,
)
from maplegotchi.persistence.layout_keys import (
    LayoutKeys,
    V11LayoutKeysError,
    validate_layout_keys,
)

ErrorCategory = Literal[
    "rows", "revision", "time", "parent", "layout", "pointer", "life", "keys", "transition"
]


class V11SnapshotError(ValueError):
    """Fixed categories only; no row values, document text or private identifiers."""

    def __init__(self, category: ErrorCategory) -> None:
        super().__init__(category)


def _positive(value: object, category: ErrorCategory) -> None:
    if type(value) is not int or value < 1:
        raise V11SnapshotError(category)


@dataclass(frozen=True, slots=True)
class RevisionRow:
    """Exact layout_revision columns, immutable synthetic values, not a new format."""

    id: int
    created_at: str
    author: str
    base_revision: int | None
    catalog_version: int
    catalog_hash: str
    document: str
    validation_digest: str

    def __post_init__(self) -> None:
        _positive(self.id, "revision")
        _positive(self.catalog_version, "revision")
        if self.base_revision is not None:
            _positive(self.base_revision, "parent")
            if self.base_revision >= self.id:
                raise V11SnapshotError("parent")
        if self.author not in ("paolo", "migration") or type(self.author) is not str:
            raise V11SnapshotError("revision")
        if (
            type(self.created_at) is not str
            or re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}.*\+00:00", self.created_at
            )
            is None
        ):
            raise V11SnapshotError("time")
        try:
            datetime.fromisoformat(self.created_at)
        except ValueError:
            raise V11SnapshotError("time") from None
        if any(
            type(value) is not str
            for value in (self.catalog_hash, self.document, self.validation_digest)
        ):
            raise V11SnapshotError("rows")
        if (
            self.id == 1
            and (
                self.base_revision is not None
                or self.author != "migration"
                or self.catalog_version != 1
            )
        ) or (self.id != 1 and (self.base_revision is None or self.author != "paolo")):
            raise V11SnapshotError("parent")


@dataclass(frozen=True, slots=True)
class LifeReference:
    maple_id: int
    layout_revision: int
    point_host: str
    point_id: str

    def __post_init__(self) -> None:
        if type(self.maple_id) is not int or self.maple_id != 1:
            raise V11SnapshotError("life")
        _positive(self.layout_revision, "life")
        if any(
            type(value) is not str or not 1 <= len(value) <= 128
            for value in (self.point_host, self.point_id)
        ):
            raise V11SnapshotError("life")


@dataclass(frozen=True, slots=True)
class ValidatedRevision:
    row: RevisionRow
    layout: LayoutDocument


@dataclass(frozen=True, slots=True)
class LayoutSnapshotProof:
    """Layout-side proof only. Not CandidateLife, Save/Load, or DB admission."""

    revisions: tuple[ValidatedRevision, ...]
    active_revision: int
    life_reference: LifeReference

    @property
    def active(self) -> ValidatedRevision:
        return next(
            revision for revision in self.revisions if revision.row.id == self.active_revision
        )


def validate_layout_snapshot(
    revisions: tuple[RevisionRow, ...],
    world_state: tuple[tuple[int, int], ...],
    life_references: tuple[LifeReference, ...],
    keys: LayoutKeys,
    *,
    snapshots: tuple[CatalogSnapshot, ...],
    contexts: tuple[tuple[int, LayoutContext], ...],
) -> LayoutSnapshotProof:
    """Validate explicitly supplied rows; never select latest or repair a pointer.

    Catalog snapshots and per-revision validation contexts are supplied, with
    no resource lookup. Historical layouts must not inherit a current Maple
    tile/context that was never valid in that revision. Every supplied revision
    is decoded against its exact catalog identity and explicit context.
    The caller must acquire one consistent DB read transaction in a future
    authorized adapter; this pure proof cannot establish that acquisition.
    """
    if (
        type(revisions) is not tuple
        or not revisions
        or any(type(row) is not RevisionRow for row in revisions)
    ):
        raise V11SnapshotError("rows")
    ids = {row.id for row in revisions}
    if len(ids) != len(revisions) or 1 not in ids:
        raise V11SnapshotError("revision")
    if any(row.base_revision is not None and row.base_revision not in ids for row in revisions):
        raise V11SnapshotError("parent")
    if type(world_state) is not tuple or len(world_state) != 1:
        raise V11SnapshotError("pointer")
    pointer = world_state[0]
    if (
        type(pointer) is not tuple
        or len(pointer) != 2
        or type(pointer[0]) is not int
        or pointer[0] != 1
    ):
        raise V11SnapshotError("pointer")
    _positive(pointer[1], "pointer")
    if pointer[1] not in ids:
        raise V11SnapshotError("pointer")
    if (
        type(life_references) is not tuple
        or len(life_references) != 1
        or type(life_references[0]) is not LifeReference
    ):
        raise V11SnapshotError("life")
    life = life_references[0]
    if life.layout_revision != pointer[1]:
        raise V11SnapshotError("life")
    if type(contexts) is not tuple or any(
        type(item) is not tuple
        or len(item) != 2
        or type(item[0]) is not int
        or type(item[1]) is not LayoutContext
        for item in contexts
    ):
        raise V11SnapshotError("rows")
    supplied_contexts = dict(contexts)
    if len(supplied_contexts) != len(contexts) or set(supplied_contexts) != ids:
        raise V11SnapshotError("rows")
    decoded: list[ValidatedRevision] = []
    for row in sorted(revisions, key=lambda row: row.id):
        try:
            layout = decode_layout_document(
                row.document,
                validation_digest=row.validation_digest,
                catalog_version=row.catalog_version,
                catalog_hash=row.catalog_hash,
                snapshots=snapshots,
                context=supplied_contexts[row.id],
            )
        except V11LayoutFormatError:
            raise V11SnapshotError("layout") from None
        decoded.append(ValidatedRevision(row, layout))
    proof = LayoutSnapshotProof(tuple(decoded), pointer[1], life)
    try:
        validate_layout_keys(proof.active.layout, proof.active_revision, keys)
    except V11LayoutKeysError:
        raise V11SnapshotError("keys") from None
    if (life.layout_revision, life.point_host, life.point_id) not in keys.layout_point:
        raise V11SnapshotError("life")
    return proof


def validate_layout_append(before: LayoutSnapshotProof, after: LayoutSnapshotProof) -> None:
    """Check §7 append-only metadata between two already validated proofs.

    This checks writer postconditions only; it does not allocate IDs, perform
    an owner edit/revert, change the life, or make a transaction durable.
    """
    if type(before) is not LayoutSnapshotProof or type(after) is not LayoutSnapshotProof:
        raise V11SnapshotError("transition")
    old = {revision.row.id: revision.row for revision in before.revisions}
    new = {revision.row.id: revision.row for revision in after.revisions}
    next_id = max(old) + 1
    if set(new) != set(old) | {next_id} or any(new[id] != row for id, row in old.items()):
        raise V11SnapshotError("transition")
    added = new[next_id]
    if (
        after.active_revision != next_id
        or added.base_revision != before.active_revision
        or added.author != "paolo"
    ):
        raise V11SnapshotError("transition")
