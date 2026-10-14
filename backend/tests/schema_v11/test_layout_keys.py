"""Contract-backed synthetic key rows; no database setup or migration execution."""

from __future__ import annotations

import ast
import builtins
import json
import socket
import sqlite3
from copy import deepcopy
from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from tests.schema_v11 import layout_codec, layout_keys
from tests.schema_v11.layout_codec import (
    CatalogSnapshot,
    LayoutContext,
    LayoutDocument,
    encode_layout_document,
)
from tests.schema_v11.layout_keys import (
    LayoutKeys,
    V11LayoutKeysError,
    project_layout_keys,
    validate_layout_keys,
)
from tests.world.validation_corpus import canonical_candidate

# Independent, reviewed initial-house expectations, not derived by the projector.
HOSTS = (
    "bed.bedroom",
    "bedside.bedroom",
    "window.bedroom",
    "frame.bedroom",
    "sofa.living",
    "side_table.living",
    "lamp.living",
    "rug.living",
    "window.living",
    "plant.living",
    "frame.living",
    "bookshelf.library_1",
    "bookshelf.library_2",
    "window.library",
    "armchair.library",
    "side_table.library",
    "lamp.library",
    "desk.writing",
    "desk.computer",
    "window.studio",
    "shelf.studio",
    "board.studio",
    "rug.hall",
    "idle.hall_west",
    "idle.hall_center",
    "idle.hall_east",
    "frame.hall_west",
    "frame.hall_east",
)
ROOMS = (
    ("bedroom", "bedroom"),
    ("living_room", "living"),
    ("library", "library"),
    ("work_studio", "studio"),
    ("central_hall", "hall"),
    ("future_space", "future"),
    ("creation_room", "creation"),
    ("system_room", "system"),
)
POINTS = (
    ("bed.bedroom", "sleep"),
    ("window.bedroom", "view"),
    ("sofa.living", "seat"),
    ("window.living", "view"),
    ("plant.living", "think"),
    ("bookshelf.library_1", "front_l"),
    ("bookshelf.library_1", "front_r"),
    ("bookshelf.library_2", "front_l"),
    ("bookshelf.library_2", "front_r"),
    ("window.library", "view"),
    ("armchair.library", "seat"),
    ("desk.writing", "chair"),
    ("desk.computer", "operator"),
    ("window.studio", "view"),
    ("idle.hall_west", "idle"),
    ("idle.hall_center", "idle"),
    ("idle.hall_east", "idle"),
)
SLOTS = (
    ("bedside.bedroom", "top"),
    ("frame.bedroom", "artwork"),
    ("side_table.living", "top"),
    ("frame.living", "artwork"),
    ("bookshelf.library_1", "books"),
    ("bookshelf.library_2", "books"),
    ("side_table.library", "top"),
    ("desk.writing", "desktop"),
    ("shelf.studio", "display"),
    ("board.studio", "cards"),
    ("frame.hall_west", "artwork"),
    ("frame.hall_east", "artwork"),
)
TABLES = ("layout_host", "layout_room", "layout_point", "layout_slot")


def expected(revision: int = 7) -> LayoutKeys:
    return LayoutKeys(
        tuple(sorted((revision, host) for host in HOSTS)),
        tuple(sorted((revision, room, kind) for room, kind in ROOMS)),
        tuple(sorted((revision, host, point) for host, point in POINTS)),
        tuple(sorted((revision, host, slot) for host, slot in SLOTS)),
    )


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


@dataclass(frozen=True)
class Fixture:
    wire: dict[str, Any]
    types: list[dict[str, Any]]
    context: LayoutContext
    document: LayoutDocument


@pytest.fixture(scope="module")
def fixture() -> Fixture:
    root = Path(__file__).parents[2] / "src/maplegotchi/world_catalog"
    resource = json.loads((root / "initial_catalog.json").read_text(encoding="utf-8"))
    wire = dict(
        format_version=1,
        house=json.loads((root / "initial_house.json").read_text(encoding="utf-8")),
        instances=resource["instances"],
        themes={},
        lighting_presets={},
    )
    candidate = canonical_candidate()
    context = LayoutContext(candidate.art, candidate.legacy_targets, candidate.maple)
    snapshot = CatalogSnapshot(1, canonical(resource["types"]))
    document = encode_layout_document(
        wire,
        catalog_version=1,
        catalog_hash=snapshot.catalog_hash,
        snapshots=(snapshot,),
        context=context,
    )
    return Fixture(wire, resource["types"], context, document)


def changed(rows: LayoutKeys, table: str, value: object) -> LayoutKeys:
    return replace(rows, **cast(dict[str, Any], {table: value}))


@pytest.mark.parametrize("table", TABLES)
def test_exact_contract_rows(fixture: Fixture, table: str) -> None:
    assert getattr(project_layout_keys(fixture.document, 7), table) == getattr(expected(), table)


@pytest.mark.parametrize("revision", [1, 2, 7, 2**70])
def test_positive_revision_without_new_ceiling(fixture: Fixture, revision: int) -> None:
    rows = project_layout_keys(fixture.document, revision)
    assert rows == expected(revision)
    validate_layout_keys(fixture.document, revision, rows)


@pytest.mark.parametrize("revision", [0, -1, True, False, 1.0, "1", None, [], {}, b"1"])
def test_invalid_revision(fixture: Fixture, revision: Any) -> None:
    for operation in (
        lambda: project_layout_keys(fixture.document, revision),
        lambda: validate_layout_keys(fixture.document, revision, expected()),
    ):
        with pytest.raises(V11LayoutKeysError, match=r"^revision$"):
            operation()


def test_idle_empty_hosts_and_empty_rooms(fixture: Fixture) -> None:
    rows = project_layout_keys(fixture.document, 7)
    for suffix in ("west", "center", "east"):
        host = f"idle.hall_{suffix}"
        assert (7, host) in rows.layout_host and (7, host, "idle") in rows.layout_point
    assert (7, "lamp.living") in rows.layout_host
    assert all(row[1] != "lamp.living" for row in (*rows.layout_point, *rows.layout_slot))
    occupied = {host.room_id for host in fixture.document.instances}
    assert {"future_space", "creation_room", "system_room"}.isdisjoint(occupied)
    assert len(rows.layout_room) == 8
    assert all((7, room, kind) in rows.layout_room for room, kind in ROOMS)


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("operation", ["missing", "extra", "duplicate", "revision", "identity"])
def test_inconsistent_rows(fixture: Fixture, table: str, operation: str) -> None:
    rows = expected()
    original: tuple[tuple[Any, ...], ...] = getattr(rows, table)
    first = original[0]
    category = "mismatch"
    if operation == "missing":
        altered = original[1:]
    elif operation == "extra":
        altered = (*original, (7, "private-extra", *first[2:]))
    elif operation == "duplicate":
        altered = (*original, first)
        category = "duplicate"
    elif operation == "revision":
        altered = ((8, *first[1:]), *original[1:])
    else:
        altered = ((7, "private-wrong-owner", *first[2:]), *original[1:])
    supplied = changed(rows, table, altered)
    before = deepcopy(supplied)
    with pytest.raises(V11LayoutKeysError, match=f"^{category}$"):
        validate_layout_keys(fixture.document, 7, supplied)
    assert supplied == before and rows == expected()


def test_room_kind_and_duplicate_identity(fixture: Fixture) -> None:
    rows = expected()
    first = rows.layout_room[0]
    wrong = (first[0], first[1], "hall")
    for room_rows, category in (
        ((wrong, *rows.layout_room[1:]), "mismatch"),
        ((*rows.layout_room, wrong), "duplicate"),
    ):
        with pytest.raises(V11LayoutKeysError, match=f"^{category}$"):
            validate_layout_keys(fixture.document, 7, replace(rows, layout_room=room_rows))


@pytest.mark.parametrize(
    ("table", "local"),
    [("layout_point", local) for local in ("private-unknown", "bed.bedroom.sleep", "top", "chair")]
    + [
        ("layout_slot", local)
        for local in ("private-unknown", "bed.bedroom.sleep", "sleep", "chair")
    ],
)
def test_wrong_local_namespace(fixture: Fixture, table: str, local: str) -> None:
    rows = expected()
    original: tuple[tuple[int, str, str], ...] = getattr(rows, table)
    first = original[0]
    with pytest.raises(V11LayoutKeysError, match=r"^mismatch$"):
        validate_layout_keys(
            fixture.document,
            7,
            changed(rows, table, ((7, first[1], local), *original[1:])),
        )


def test_point_slot_tables_cannot_be_swapped(fixture: Fixture) -> None:
    rows = expected()
    with pytest.raises(V11LayoutKeysError, match=r"^mismatch$"):
        validate_layout_keys(
            fixture.document,
            7,
            replace(rows, layout_point=rows.layout_slot, layout_slot=rows.layout_point),
        )


def test_shared_local_names_are_valid(fixture: Fixture) -> None:
    rows = expected()
    assert (7, "window.bedroom", "view") in rows.layout_point
    assert (7, "window.library", "view") in rows.layout_point
    # A point and slot may also share a local name on the same host. Resolve the
    # changed catalog through the actual codec before projecting either table.
    types = deepcopy(fixture.types)
    desk = next(item for item in types if item["id"] == "furniture.writing_desk")
    desk["slots"][0]["id"] = "chair"
    snapshot = CatalogSnapshot(3, canonical(types))
    document = encode_layout_document(
        fixture.wire,
        catalog_version=3,
        catalog_hash=snapshot.catalog_hash,
        snapshots=(snapshot,),
        context=fixture.context,
    )
    result = project_layout_keys(document, 7)
    wanted = replace(
        rows,
        layout_slot=tuple(
            sorted(
                (revision, host, "chair" if host == "desk.writing" else local)
                for revision, host, local in rows.layout_slot
            )
        ),
    )
    assert result == wanted
    assert (7, "desk.writing", "chair") in result.layout_point
    assert (7, "desk.writing", "chair") in result.layout_slot
    validate_layout_keys(document, 7, wanted)


@pytest.mark.parametrize("table", TABLES)
def test_row_order_independent(fixture: Fixture, table: str) -> None:
    rows = expected()
    shuffled = changed(rows, table, tuple(reversed(getattr(rows, table))))
    validate_layout_keys(fixture.document, 7, shuffled)
    assert getattr(shuffled, table) == tuple(reversed(getattr(rows, table)))


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("value", [None, [], {}, "rows", ((7,),), ((7, []),), ((7, ""),)])
def test_invalid_collections(table: str, value: object) -> None:
    with pytest.raises(V11LayoutKeysError, match=r"^rows$"):
        changed(expected(), table, value)


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("revision", [True, False, 0, -1, "7", 7.0, None])
def test_row_revision_types(table: str, revision: object) -> None:
    rows = expected()
    first = getattr(rows, table)[0]
    with pytest.raises(V11LayoutKeysError, match=r"^revision$"):
        changed(rows, table, ((revision, *first[1:]),))


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("value", [True, 1, None, b"host", "x" * 129])
def test_identifier_types_and_existing_length_bound(table: str, value: object) -> None:
    first = getattr(expected(), table)[0]
    with pytest.raises(V11LayoutKeysError, match=r"^rows$"):
        changed(expected(), table, ((7, value, *first[2:]),))


@pytest.mark.parametrize("table", ["layout_point", "layout_slot"])
def test_no_added_room_column(table: str) -> None:
    with pytest.raises(V11LayoutKeysError, match=r"^rows$"):
        changed(expected(), table, ((7, "desk.writing", "chair", "work_studio"),))


def test_binary_identity_no_normalization(fixture: Fixture) -> None:
    rows = expected()
    for name in ("Bed.bedroom", "bed.bedroom\x00", "béd.bedroom", "be\u0301d.bedroom"):
        with pytest.raises(V11LayoutKeysError, match=r"^mismatch$"):
            validate_layout_keys(
                fixture.document,
                7,
                replace(rows, layout_host=((7, name), *rows.layout_host[1:])),
            )


@pytest.mark.parametrize("identifier", ["a" * 128, "host_name", "host.name", "host"])
def test_valid_supplied_identity_preserved(fixture: Fixture, identifier: str) -> None:
    wire = deepcopy(fixture.wire)
    lamp = next(host for host in wire["instances"] if host["id"] == "lamp.living")
    lamp["id"] = identifier
    snapshot = CatalogSnapshot(1, canonical(fixture.types))
    document = encode_layout_document(
        wire,
        catalog_version=1,
        catalog_hash=snapshot.catalog_hash,
        snapshots=(snapshot,),
        context=fixture.context,
    )
    rows = project_layout_keys(document, 7)
    wanted = replace(
        expected(),
        layout_host=tuple(
            sorted((7, identifier if host == "lamp.living" else host) for host in HOSTS)
        ),
    )
    assert rows == wanted
    validate_layout_keys(document, 7, wanted)


@pytest.mark.parametrize(
    ("table", "row"),
    [
        ("layout_point", (7, "bedside.bedroom", "sleep")),
        ("layout_slot", (7, "bed.bedroom", "top")),
        ("layout_point", (7, "bedroom", "sleep")),
        ("layout_slot", (7, "bedroom", "top")),
    ],
)
def test_existing_wrong_owner_or_room_refused(
    fixture: Fixture, table: str, row: tuple[int, str, str]
) -> None:
    original = getattr(expected(), table)
    with pytest.raises(V11LayoutKeysError, match=r"^mismatch$"):
        validate_layout_keys(fixture.document, 7, changed(expected(), table, (row, *original[1:])))


def test_deterministic_immutable_and_no_mutation(fixture: Fixture) -> None:
    before = deepcopy(fixture)
    first = project_layout_keys(fixture.document, 7)
    assert first == project_layout_keys(fixture.document, 7) == expected()
    with pytest.raises(FrozenInstanceError):
        first.layout_host = ()  # type: ignore[misc]
    with pytest.raises(TypeError):
        cast(Any, first.layout_point)[0][1] = "changed"
    validate_layout_keys(fixture.document, 7, expected())
    assert fixture == before


@pytest.mark.parametrize("value", [None, {}, (), "private-document", 1])
def test_wrong_document_type(value: Any) -> None:
    with pytest.raises(V11LayoutKeysError, match=r"^document$"):
        project_layout_keys(value, 7)


@pytest.mark.parametrize("value", [None, {}, (), "private-rows", 1])
def test_wrong_row_container_type(fixture: Fixture, value: Any) -> None:
    with pytest.raises(V11LayoutKeysError, match=r"^rows$"):
        validate_layout_keys(fixture.document, 7, value)


def test_safe_deterministic_errors(fixture: Fixture) -> None:
    rows = replace(expected(), layout_host=((7, "private-secret-marker"),))
    for _ in range(2):
        with pytest.raises(V11LayoutKeysError) as failure:
            validate_layout_keys(fixture.document, 7, rows)
        assert failure.value.args == ("mismatch",)
        assert failure.value.__cause__ is None and failure.value.__context__ is None


def test_pure_dependency_isolation(fixture: Fixture, monkeypatch: pytest.MonkeyPatch) -> None:
    source = Path(layout_keys.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports == {"__future__", "dataclasses", "typing", "tests.schema_v11.layout_codec"}
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    wanted = expected()

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("unexpected I/O or reconstruction")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(layout_codec, "decode_layout_document", forbidden)
    monkeypatch.setattr(layout_codec, "build_catalog_layout", forbidden)
    assert project_layout_keys(fixture.document, 7) == wanted
    validate_layout_keys(fixture.document, 7, wanted)


def test_memory_error_is_not_suppressed(fixture: Fixture, monkeypatch: pytest.MonkeyPatch) -> None:
    def exhausted(*args: object, **kwargs: object) -> NoReturn:
        raise MemoryError

    monkeypatch.setattr(layout_keys, "project_layout_keys", exhausted)
    with pytest.raises(MemoryError):
        validate_layout_keys(fixture.document, 7, expected())
