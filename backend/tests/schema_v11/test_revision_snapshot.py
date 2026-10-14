"""Supplied synthetic rows only: no DB, transaction, Travel decoder or runtime."""

from __future__ import annotations

import builtins
import json
import socket
import sqlite3
from copy import deepcopy
from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from maplegotchi.core.world.coordinates import Tile
from tests.schema_v11 import revision_snapshot, travel_codec
from tests.schema_v11.layout_codec import (
    CatalogSnapshot,
    LayoutContext,
    decode_layout_document,
    encode_layout_document,
)
from tests.schema_v11.layout_keys import LayoutKeys, project_layout_keys
from tests.schema_v11.revision_snapshot import (
    LayoutSnapshotProof,
    LifeReference,
    RevisionRow,
    V11SnapshotError,
    validate_layout_append,
    validate_layout_snapshot,
)
from tests.world.validation_corpus import canonical_candidate

AT = "2026-10-14T00:00:00+00:00"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


@dataclass(frozen=True)
class Fixture:
    row: RevisionRow
    keys: LayoutKeys
    snapshot: CatalogSnapshot
    context: LayoutContext
    wire: dict[str, Any]


@pytest.fixture(scope="module")
def fixture() -> Fixture:
    root = Path(__file__).parents[2] / "src/maplegotchi/world_catalog"
    catalog = json.loads((root / "initial_catalog.json").read_text(encoding="utf-8"))
    wire = dict(
        format_version=1,
        house=json.loads((root / "initial_house.json").read_text(encoding="utf-8")),
        instances=catalog["instances"],
        themes={},
        lighting_presets={},
    )
    candidate = canonical_candidate()
    context = LayoutContext(candidate.art, candidate.legacy_targets, candidate.maple)
    snapshot = CatalogSnapshot(1, canonical(catalog["types"]))
    layout = encode_layout_document(
        wire,
        catalog_version=1,
        catalog_hash=snapshot.catalog_hash,
        snapshots=(snapshot,),
        context=context,
    )
    row = RevisionRow(
        1,
        AT,
        "migration",
        None,
        1,
        snapshot.catalog_hash,
        layout.canonical_bytes.decode(),
        layout.validation_digest,
    )
    return Fixture(row, project_layout_keys(layout, 1), snapshot, context, wire)


def proof(fixture: Fixture, **changes: Any) -> LayoutSnapshotProof:
    arguments: dict[str, Any] = dict(
        revisions=(fixture.row,),
        world_state=((1, 1),),
        life_references=(LifeReference(1, 1, "idle.hall_center", "idle"),),
        keys=fixture.keys,
        snapshots=(fixture.snapshot,),
    )
    arguments.update(changes)
    if "contexts" not in arguments:
        arguments["contexts"] = (
            tuple(
                (row.id, fixture.context)
                for row in arguments["revisions"]
                if type(row) is RevisionRow
            )
            if type(arguments["revisions"]) is tuple
            else ()
        )
    return validate_layout_snapshot(**arguments)


def keys_for(fixture: Fixture, revision: int) -> LayoutKeys:
    return replace(
        fixture.keys,
        layout_host=tuple((revision, host) for _, host in fixture.keys.layout_host),
        layout_room=tuple((revision, room, kind) for _, room, kind in fixture.keys.layout_room),
        layout_point=tuple((revision, host, point) for _, host, point in fixture.keys.layout_point),
        layout_slot=tuple((revision, host, slot) for _, host, slot in fixture.keys.layout_slot),
    )


def at_revision(
    fixture: Fixture, revisions: tuple[RevisionRow, ...], active: int
) -> LayoutSnapshotProof:
    return proof(
        fixture,
        revisions=revisions,
        world_state=((1, active),),
        life_references=(LifeReference(1, active, "idle.hall_center", "idle"),),
        keys=keys_for(fixture, active),
    )


def test_valid_initial_snapshot_and_repeatable_reconstruction(fixture: Fixture) -> None:
    before = deepcopy(fixture)
    result = proof(fixture)
    assert result.active_revision == 1
    assert result.active.row == fixture.row
    assert result.active.layout.canonical_bytes == fixture.row.document.encode()
    assert result.active.layout.validation_digest == fixture.row.validation_digest
    assert result.life_reference == LifeReference(1, 1, "idle.hall_center", "idle")
    assert proof(fixture) == result and fixture == before
    with pytest.raises(FrozenInstanceError):
        result.active_revision = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value", "category"),
    [
        ("id", True, "revision"),
        ("id", 0, "revision"),
        ("id", -1, "revision"),
        ("id", "1", "revision"),
        ("catalog_version", False, "revision"),
        ("catalog_version", 0, "revision"),
        ("author", "owner", "revision"),
        ("author", None, "revision"),
        ("base_revision", True, "parent"),
        ("base_revision", 0, "parent"),
        ("base_revision", 1, "parent"),
        ("created_at", None, "time"),
        ("created_at", "2026-02-30T00:00:00+00:00", "time"),
        ("created_at", "2026-10-14T00:00:00Z", "time"),
        ("created_at", "2026-10-14 00:00:00+00:00", "time"),
        ("created_at", "2026-10-14T00:00:00+07:00", "time"),
        ("document", b"{}", "rows"),
        ("catalog_hash", None, "rows"),
        ("validation_digest", 3, "rows"),
        ("author", "paolo", "parent"),
        ("catalog_version", 2, "parent"),
    ],
)
def test_revision_metadata_refusal(fixture: Fixture, field: str, value: Any, category: str) -> None:
    with pytest.raises(V11SnapshotError, match=f"^{category}$"):
        replace(fixture.row, **{field: value})


def test_metadata_preserves_exact_utc_text_and_has_no_new_id_ceiling(fixture: Fixture) -> None:
    text = "2026-10-14T00:00:00.123456+00:00"
    row = replace(fixture.row, id=2**70, base_revision=1, author="paolo", created_at=text)
    assert row.id == 2**70 and row.created_at == text


@pytest.mark.parametrize("rows", [(), [], None, (None,), ("private-row",)])
def test_missing_or_malformed_revisions(fixture: Fixture, rows: Any) -> None:
    with pytest.raises(V11SnapshotError, match=r"^rows$"):
        proof(fixture, revisions=rows)


def test_duplicate_missing_initial_and_missing_parent(fixture: Fixture) -> None:
    second = replace(fixture.row, id=2, base_revision=1, author="paolo")
    third = replace(second, id=3, base_revision=2)
    for rows, category in [
        ((fixture.row, fixture.row), "revision"),
        ((second,), "revision"),
        ((fixture.row, third), "parent"),
    ]:
        with pytest.raises(V11SnapshotError, match=f"^{category}$"):
            proof(fixture, revisions=rows)


@pytest.mark.parametrize(
    "pointer",
    [
        (),
        [],
        None,
        ((1, 1), (1, 1)),
        ((2, 1),),
        ((True, 1),),
        ((1, True),),
        ((1, 0),),
        ((1, "1"),),
        ((1, 99),),
        ([1, 1],),
        ((1,),),
        ((1, 1, 1),),
    ],
)
def test_pointer_refusal_no_fallback(fixture: Fixture, pointer: Any) -> None:
    with pytest.raises(V11SnapshotError, match=r"^pointer$"):
        proof(fixture, world_state=pointer)


@pytest.mark.parametrize("rows", [(), [], None, (None,), ("private-reference",)])
def test_life_reference_singleton(fixture: Fixture, rows: Any) -> None:
    with pytest.raises(V11SnapshotError, match=r"^life$"):
        proof(fixture, life_references=rows)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("maple_id", True),
        ("maple_id", 2),
        ("layout_revision", 0),
        ("layout_revision", True),
        ("point_host", ""),
        ("point_host", []),
        ("point_id", 1),
        ("point_id", "x" * 129),
    ],
)
def test_life_reference_strict_types(field: str, value: Any) -> None:
    with pytest.raises(V11SnapshotError, match=r"^life$"):
        replace(LifeReference(1, 1, "idle.hall_center", "idle"), **{field: value})


@pytest.mark.parametrize(
    ("revision", "host", "point"),
    [
        (2, "idle.hall_center", "idle"),
        (1, "central_hall", "idle"),
        (1, "desk.computer", "chair"),
        (1, "desk.writing", "desktop"),
        (1, "private-secret", "idle"),
    ],
)
def test_life_revision_and_host_local_namespace(
    fixture: Fixture, revision: int, host: str, point: str
) -> None:
    with pytest.raises(V11SnapshotError, match=r"^life$"):
        proof(fixture, life_references=(LifeReference(1, revision, host, point),))


@pytest.mark.parametrize("table", ["layout_host", "layout_room", "layout_point", "layout_slot"])
def test_keys_missing_extra_duplicate_wrong_revision(fixture: Fixture, table: str) -> None:
    original = getattr(fixture.keys, table)
    for rows in [
        original[1:],
        (*original, original[0]),
        ((2, *original[0][1:]), *original[1:]),
        (*original, (1, "private-extra", *original[0][2:])),
    ]:
        with pytest.raises(V11SnapshotError, match=r"^keys$"):
            proof(fixture, keys=replace(fixture.keys, **{table: rows}))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("validation_digest", "0" * 64),
        ("catalog_hash", "0" * 64),
        ("document", "{}"),
        ("document", "private-secret"),
    ],
)
def test_layout_fail_closed_and_safe_errors(fixture: Fixture, field: str, value: str) -> None:
    with pytest.raises(V11SnapshotError, match=r"^layout$") as failure:
        proof(fixture, revisions=(replace(fixture.row, **cast(dict[str, Any], {field: value})),))
    assert failure.value.args == ("layout",) and failure.value.__suppress_context__


def test_explicit_catalog_history_for_each_revision(fixture: Fixture) -> None:
    types = json.loads(fixture.snapshot.canonical_types)
    types[0]["states"].append("historical_test_state")
    newer = CatalogSnapshot(2, canonical(types))
    layout = encode_layout_document(
        fixture.wire,
        catalog_version=2,
        catalog_hash=newer.catalog_hash,
        snapshots=(newer,),
        context=fixture.context,
    )
    second = RevisionRow(
        2,
        AT,
        "paolo",
        1,
        2,
        newer.catalog_hash,
        layout.canonical_bytes.decode(),
        layout.validation_digest,
    )
    result = proof(fixture, revisions=(second, fixture.row), snapshots=(newer, fixture.snapshot))
    assert result.active_revision == 1 and result.revisions[1].row.catalog_version == 2
    assert result.revisions[0].layout.catalog_hash == fixture.snapshot.catalog_hash
    with pytest.raises(V11SnapshotError, match=r"^layout$"):
        proof(fixture, revisions=(fixture.row, second), snapshots=(newer,))


def test_pointer_is_not_latest_and_input_order_is_irrelevant(fixture: Fixture) -> None:
    second = replace(fixture.row, id=2, base_revision=1, author="paolo")
    left = proof(fixture, revisions=(fixture.row, second))
    right = proof(fixture, revisions=(second, fixture.row))
    assert left == right and right.active.row.id == 1


@pytest.mark.parametrize("contexts", [None, [], (), ((1, None),), ((True, None),), ((1,),)])
def test_missing_or_malformed_validation_context(fixture: Fixture, contexts: Any) -> None:
    with pytest.raises(V11SnapshotError, match=r"^rows$"):
        proof(fixture, contexts=contexts)


def test_context_duplicates_extra_and_wrong_revision_refused(fixture: Fixture) -> None:
    for contexts in (
        ((1, fixture.context), (1, fixture.context)),
        ((2, fixture.context),),
        ((1, fixture.context), (2, fixture.context)),
        ((True, fixture.context),),
    ):
        with pytest.raises(V11SnapshotError, match=r"^rows$"):
            proof(fixture, contexts=contexts)


def test_historical_context_is_explicit_per_revision(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    second = replace(fixture.row, id=2, base_revision=1, author="paolo")
    historical = replace(fixture.context, maple_tile=Tile(3, 4))
    seen: list[Tile] = []
    original = decode_layout_document

    def recording(*args: Any, **kwargs: Any) -> Any:
        seen.append(kwargs["context"].maple_tile)
        return original(*args, **kwargs)

    monkeypatch.setattr(revision_snapshot, "decode_layout_document", recording)
    result = proof(
        fixture, revisions=(second, fixture.row), contexts=((2, fixture.context), (1, historical))
    )
    assert result.active_revision == 1
    assert seen == [Tile(3, 4), Tile(21, 15)]


def test_append_and_revert_content_postconditions(fixture: Fixture) -> None:
    first = proof(fixture)
    second = replace(fixture.row, id=2, base_revision=1, author="paolo")
    after = at_revision(fixture, (fixture.row, second), 2)
    validate_layout_append(first, after)
    # Revert is an appended copy with current active as parent, not UPDATE.
    third = replace(second, id=3, base_revision=2)
    restored = at_revision(fixture, (third, second, fixture.row), 3)
    validate_layout_append(after, restored)
    assert restored.active.layout == first.active.layout
    assert restored != first  # Revision identity is intentionally different.


def test_append_parent_is_previous_active_not_max(fixture: Fixture) -> None:
    second = replace(fixture.row, id=2, base_revision=1, author="paolo")
    before = proof(fixture, revisions=(fixture.row, second))
    third = replace(second, id=3, base_revision=1)
    validate_layout_append(before, at_revision(fixture, (fixture.row, second, third), 3))
    with pytest.raises(V11SnapshotError, match=r"^transition$"):
        validate_layout_append(
            before, at_revision(fixture, (fixture.row, second, replace(third, base_revision=2)), 3)
        )


@pytest.mark.parametrize(
    "case", ["same", "old_changed", "deleted", "gap", "two_added", "wrong_pointer"]
)
def test_append_only_refusal(fixture: Fixture, case: str) -> None:
    first = proof(fixture)
    second = replace(fixture.row, id=2, base_revision=1, author="paolo")
    before = at_revision(fixture, (fixture.row, second), 2)
    third = replace(second, id=3, base_revision=2)
    if case == "same":
        after = before
    elif case == "old_changed":
        after = at_revision(
            fixture,
            (fixture.row, replace(second, created_at="2026-10-14T01:00:00+00:00"), third),
            3,
        )
    elif case == "deleted":
        after = first
    elif case == "gap":
        after = at_revision(fixture, (fixture.row, second, replace(third, id=4)), 4)
    elif case == "two_added":
        after = at_revision(
            fixture, (fixture.row, second, third, replace(third, id=4, base_revision=3)), 4
        )
    else:
        after = at_revision(fixture, (fixture.row, second, third), 2)
    with pytest.raises(V11SnapshotError, match=r"^transition$"):
        validate_layout_append(before, after)


def test_no_io_runtime_travel_or_database(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("unexpected side effect or Travel integration")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(travel_codec, "decode_travel_path", forbidden)
    assert proof(fixture).active.row.id == 1
