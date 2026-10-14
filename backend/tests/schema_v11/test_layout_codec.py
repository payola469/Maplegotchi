"""Bounded synthetic layout documents; release fixtures are read only at setup."""

from __future__ import annotations

import builtins
import hashlib
import io
import json
import socket
import sqlite3
import time
from copy import deepcopy
from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from maplegotchi.core.world.coordinates import Tile
from tests.schema_v11 import layout_codec
from tests.schema_v11.layout_codec import (
    MAX_LAYOUT_BYTES,
    CatalogSnapshot,
    LayoutContext,
    LayoutDocument,
    V11LayoutFormatError,
    decode_layout_document,
    encode_layout_document,
)
from tests.world.validation_corpus import canonical_candidate


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


@dataclass(frozen=True)
class Fixture:
    document: dict[str, Any]
    types: list[dict[str, Any]]
    snapshot: CatalogSnapshot
    context: LayoutContext


@pytest.fixture(scope="module")
def fixture() -> Fixture:
    # Only checked-in, synthetic release geometry/art. No life/production input.
    root = Path(__file__).parents[2] / "src/maplegotchi/world_catalog"
    house = json.loads((root / "initial_house.json").read_text(encoding="utf-8"))
    resource = json.loads((root / "initial_catalog.json").read_text(encoding="utf-8"))
    candidate = canonical_candidate()
    return Fixture(
        {
            "format_version": 1,
            "house": house,
            "instances": resource["instances"],
            "themes": {},
            "lighting_presets": {},
        },
        resource["types"],
        CatalogSnapshot(1, canonical(resource["types"])),
        LayoutContext(candidate.art, candidate.legacy_targets, candidate.maple),
    )


def decode(fixture: Fixture, text: str | bytes | None = None, **changes: Any) -> LayoutDocument:
    raw = canonical(fixture.document) if text is None else text
    encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
    options: dict[str, Any] = dict(
        validation_digest=hashlib.sha256(encoded).hexdigest(),
        catalog_version=1,
        catalog_hash=fixture.snapshot.catalog_hash,
        snapshots=(fixture.snapshot,),
        context=fixture.context,
    )
    options.update(changes)
    return decode_layout_document(raw, **options)


def encode(fixture: Fixture, value: object, **changes: Any) -> LayoutDocument:
    options: dict[str, Any] = dict(
        catalog_version=1,
        catalog_hash=fixture.snapshot.catalog_hash,
        snapshots=(fixture.snapshot,),
        context=fixture.context,
    )
    options.update(changes)
    return encode_layout_document(value, **options)


def host(document: dict[str, Any], identity: str) -> dict[str, Any]:
    return next(row for row in document["instances"] if row["id"] == identity)


def test_exact_canonical_roundtrip(fixture: Fixture) -> None:
    original = deepcopy(fixture.document)
    raw = canonical(original)
    result = encode(fixture, original)
    assert result.canonical_bytes == raw
    assert raw.startswith(b'{"format_version":1,"house":{"doors":[')
    assert raw.endswith(b'"lighting_presets":{},"themes":{}}')
    assert result.validation_digest == hashlib.sha256(raw).hexdigest()
    assert len(raw) == 7347
    assert (
        result.validation_digest
        == "6b7f3c1e870f81fa5e3f72f52efd3ca9f1545d3753f50cbdcb581c0ca2ac6835"
    )
    assert result.catalog_hash == "5e8f78580c9015cf2c3150eeb608ca5b02303bdb15f6ebbdbd8731def9266c7b"
    assert result.catalog_hash == fixture.snapshot.catalog_hash
    assert decode(fixture) == result
    assert decode(fixture, raw.decode("utf-8")) == result
    assert encode(fixture, result) == result
    assert len(result.world.regions) == 8 and len(result.world.doors) == 7
    assert len(result.instances) == len(result.catalog.instances) == 28
    assert fixture.document == original


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_exact_byte_boundaries(fixture: Fixture, offset: int) -> None:
    document = deepcopy(fixture.document)
    document["instances"][0]["link"] = ""
    padding = MAX_LAYOUT_BYTES + offset - len(canonical(document))
    document["instances"][0]["link"] = "x" * padding
    raw = canonical(document)
    assert len(raw) == MAX_LAYOUT_BYTES + offset
    if offset > 0:
        with pytest.raises(V11LayoutFormatError, match=r"^size$"):
            decode(fixture, raw)
        with pytest.raises(V11LayoutFormatError, match=r"^size$"):
            encode(fixture, document)
    else:
        assert decode(fixture, raw).canonical_bytes == raw
        assert encode(fixture, document).canonical_bytes == raw


@pytest.mark.parametrize("kind", ["bytes", "str", "unicode"])
def test_oversize_before_parser_hash_and_reconstruction(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    raw: str | bytes = b"x" * (MAX_LAYOUT_BYTES + 1)
    if kind == "str":
        raw = "x" * (MAX_LAYOUT_BYTES + 1)
    elif kind == "unicode":
        raw = "é" * (MAX_LAYOUT_BYTES // 2 + 1)
        assert len(raw) < MAX_LAYOUT_BYTES < len(raw.encode("utf-8"))

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        pytest.fail("oversize input reached expensive work")

    monkeypatch.setattr(json, "loads", forbidden)
    monkeypatch.setattr(hashlib, "sha256", forbidden)
    monkeypatch.setattr(layout_codec, "_house", forbidden)
    with pytest.raises(V11LayoutFormatError, match=r"^size$"):
        decode_layout_document(
            raw,
            validation_digest="0" * 64,
            catalog_version=1,
            catalog_hash=fixture.snapshot.catalog_hash,
            snapshots=(fixture.snapshot,),
            context=fixture.context,
        )


def test_unicode_canonical_bytes(fixture: Fixture) -> None:
    document = deepcopy(fixture.document)
    document["instances"][0]["link"] = "private-é-雪"
    raw = canonical(document)
    assert b"\\u00e9-\\u96ea" in raw and raw.isascii()
    assert encode(fixture, document).canonical_bytes == raw
    noncanonical = raw.decode().replace("\\u00e9", "é")
    with pytest.raises(V11LayoutFormatError, match=r"^canonical$"):
        decode(fixture, noncanonical)


@pytest.mark.parametrize(
    "key", ["format_version", "house", "instances", "themes", "lighting_presets"]
)
@pytest.mark.parametrize("operation", ["missing", "unknown"])
def test_envelope_fields(fixture: Fixture, key: str, operation: str) -> None:
    document = deepcopy(fixture.document)
    if operation == "missing":
        del document[key]
    else:
        document[key + "_private"] = document.pop(key)
    with pytest.raises(V11LayoutFormatError, match=r"^fields$"):
        decode(fixture, canonical(document))


@pytest.mark.parametrize("version", [0, -1, 2, 100])
def test_version_refusal(fixture: Fixture, version: int) -> None:
    with pytest.raises(V11LayoutFormatError, match=r"^version$"):
        decode(fixture, canonical(fixture.document | {"format_version": version}))


@pytest.mark.parametrize("field", ["version", "grid", "floor", "origin", "capacity"])
@pytest.mark.parametrize("value", [True, False, 1.0, "1", None, [], {}])
def test_wrong_primitive_types(fixture: Fixture, field: str, value: object) -> None:
    document = deepcopy(fixture.document)
    if field == "version":
        document["format_version"] = value
    elif field == "grid":
        document["house"]["grid"][0] = value
    elif field == "floor":
        document["house"]["regions"][0]["floor"][0] = value
    elif field == "origin":
        document["instances"][0]["origin"][0] = value
    else:
        document["instances"][0]["slot_policies"] = [{"slot": "top", "capacity": value}]
    with pytest.raises(V11LayoutFormatError, match=r"^type$"):
        decode(fixture, canonical(document))


@pytest.mark.parametrize(
    "text",
    [
        "",
        "{",
        "[]",
        "null",
        "true",
        '{"private-secret":1,"private-secret":2}',
        '{"format_version":NaN}',
        '{"format_version":Infinity}',
        '{"format_version":-Infinity}',
    ],
)
def test_malformed_json(fixture: Fixture, text: str) -> None:
    with pytest.raises(V11LayoutFormatError) as failure:
        decode(fixture, text)
    assert str(failure.value) in {"json", "fields"}
    assert "private-secret" not in str(failure.value)


@pytest.mark.parametrize(
    "kind",
    [
        "space",
        "newline",
        "bom",
        "key_order",
        "escape",
        "minus_zero",
        "float",
        "exponent",
        "utf16",
        "invalid_utf8",
        "duplicate_nested",
    ],
)
def test_noncanonical_encodings(fixture: Fixture, kind: str) -> None:
    raw = canonical(fixture.document)
    text = raw.decode()
    cases: dict[str, str | bytes] = {
        "space": " " + text,
        "newline": text + "\n",
        "bom": "\ufeff" + text,
        "key_order": json.dumps(fixture.document, separators=(",", ":")),
        "escape": text.replace('"house"', '"\\u0068ouse"'),
        "minus_zero": text.replace('"grid":[44,26]', '"grid":[-0,26]'),
        "float": text.replace('"grid":[44,26]', '"grid":[44.0,26]'),
        "exponent": text.replace('"grid":[44,26]', '"grid":[4.4e1,26]'),
        "utf16": text.encode("utf-16"),
        "invalid_utf8": b"\xff",
        "duplicate_nested": text.replace('"grid":[44,26]', '"grid":[44,26],"grid":[44,26]'),
    }
    altered = cases[kind]
    with pytest.raises(V11LayoutFormatError) as failure:
        decode(fixture, altered)
    assert str(failure.value) in {"canonical", "json", "type", "fields"}


@pytest.mark.parametrize("field", ["themes", "lighting_presets"])
@pytest.mark.parametrize("value", [None, [], 0, True, {"private-secret": {}}])
def test_no_unreviewed_theme_or_preset(fixture: Fixture, field: str, value: object) -> None:
    with pytest.raises(V11LayoutFormatError, match=r"^fields$"):
        decode(fixture, canonical(fixture.document | {field: value}))


@pytest.mark.parametrize(
    "value", ["", "A" * 64, "g" * 64, "0" * 63, "0" * 65, "0" * 64, None, True]
)
def test_bad_digest(fixture: Fixture, value: object) -> None:
    with pytest.raises(V11LayoutFormatError, match=r"^digest$"):
        decode(fixture, validation_digest=value)


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "type",
        "room",
        "origin",
        "orientation",
        "state",
        "owner",
        "slot_overrides",
        "slot_policies",
        "link",
    ],
)
def test_missing_instance_fields(fixture: Fixture, field: str) -> None:
    document = deepcopy(fixture.document)
    del document["instances"][0][field]
    with pytest.raises(V11LayoutFormatError, match=r"^fields$"):
        decode(fixture, canonical(document))


@pytest.mark.parametrize(
    "field,value",
    [
        ("origin", [1]),
        ("origin", [1, 2, 3]),
        ("origin", None),
        ("link", 1),
        ("orientation", "private-secret"),
        ("state", "private-secret"),
        ("owner", "private-secret"),
        ("slot_overrides", [{"slot": "top"}]),
        ("slot_overrides", [{"slot": "top", "approach": None}]),
        ("slot_overrides", [{"slot": "top", "facing": None}]),
        ("slot_overrides", [{"slot": "top", "capacity": 1}]),
        ("slot_overrides", [{"slot": "missing", "approach": [1, 0]}]),
        ("slot_policies", [{"slot": "top", "capacity": None}]),
        ("slot_policies", [{"slot": "top", "accepts": None}]),
        ("slot_policies", [{"slot": "top", "maple_may_place": 1}]),
        ("slot_policies", [{"slot": "top", "approach": [1, 0]}]),
        ("slot_policies", [{"slot": "missing", "capacity": 1}]),
        ("private-secret", "private-secret"),
        ("id", "a" * 129),
    ],
)
def test_invalid_instance_and_override(fixture: Fixture, field: str, value: object) -> None:
    document = deepcopy(fixture.document)
    host(document, "bedside.bedroom")[field] = value
    with pytest.raises(V11LayoutFormatError) as failure:
        decode(fixture, canonical(document))
    assert str(failure.value) in {"fields", "type", "layout"}
    assert "private-secret" not in str(failure.value)


@pytest.mark.parametrize("rule", [f"S{i}" for i in range(1, 18)])
def test_s_rule_refusal(fixture: Fixture, rule: str) -> None:
    document = deepcopy(fixture.document)
    types = deepcopy(fixture.types)
    context = fixture.context
    if rule == "S1":
        document["house"]["grid"] = [43, 26]
    elif rule == "S2":
        next(r for r in document["house"]["regions"] if r["id"] == "bedroom")["floor"] = [
            2,
            3,
            7,
            7,
        ]
    elif rule in ("S3", "S4", "S5"):
        identity = "door.hall_future" if rule == "S5" else "door.hall_bedroom"
        door = next(d for d in document["house"]["doors"] if d["id"] == identity)
        if rule == "S3":
            door["passage"] = [5, 9, 2, 3]
        else:
            door["state"] = "closed" if rule == "S4" else "open"
    elif rule == "S6":
        host(document, "lamp.living")["origin"] = [11, 5]
    elif rule == "S7":
        host(document, "frame.hall_west")["origin"] = [5, 10]
    elif rule == "S8":
        host(document, "side_table.library")["slot_overrides"] = [
            {"slot": "top", "approach": [-1, 1]}
        ]
    elif rule in ("S9", "S13"):
        identity = "bed.bedroom" if rule == "S9" else "idle.hall_center"
        document["instances"] = [r for r in document["instances"] if r["id"] != identity]
    elif rule == "S10":
        host(document, "lamp.living").update(room="central_hall", origin=[3, 14])
    elif rule == "S11":
        host(document, "bookshelf.library_1")["slot_policies"] = [
            {"slot": "books", "maple_may_place": True}
        ]
    elif rule == "S12":
        document["house"]["regions"][0]["lighting_zone"][2] -= 1
    elif rule == "S14":
        context = replace(
            context, legacy_targets=tuple(t for t in context.legacy_targets if t.id != "bed.side")
        )
    elif rule == "S15":
        item = next(t for t in types if t["id"] == "furniture.writing_desk")
        item["capabilities"] = ["computer"]
        for point in item["points"]:
            point["provides"] = ["computer"]
    elif rule == "S16":
        next(t for t in types if t["id"] == "furniture.lamp_floor")["movable_by"] = ["maple"]
    else:
        context = replace(
            context,
            art=tuple(replace(a, geometry_version=a.geometry_version + 1) for a in context.art),
        )
    with pytest.raises(V11LayoutFormatError) as failure:
        snapshot = CatalogSnapshot(1, canonical(types))
        decode(
            fixture,
            canonical(document),
            snapshots=(snapshot,),
            catalog_hash=snapshot.catalog_hash,
            context=context,
        )
    assert str(failure.value) in {"layout", "catalog"}
    assert rule in failure.value.rules


def test_explicit_catalog_history(fixture: Fixture) -> None:
    types = deepcopy(fixture.types)
    types[0]["states"].append("historical_test_variant")
    newer = CatalogSnapshot(2, canonical(types))
    assert newer.catalog_hash != fixture.snapshot.catalog_hash
    result = decode(fixture, snapshots=(newer, fixture.snapshot))
    assert result.catalog_version == 1 and result.catalog.catalog == fixture.snapshot.catalog
    assert decode(fixture, snapshots=(fixture.snapshot, newer)) == result
    with pytest.raises(V11LayoutFormatError, match=r"^catalog$"):
        decode(fixture, snapshots=(newer,))
    for version, digest in [
        (2, fixture.snapshot.catalog_hash),
        (1, newer.catalog_hash),
        (99, newer.catalog_hash),
    ]:
        with pytest.raises(V11LayoutFormatError, match=r"^catalog$"):
            decode(
                fixture,
                snapshots=(newer, fixture.snapshot),
                catalog_version=version,
                catalog_hash=digest,
            )


@pytest.mark.parametrize("version", [True, 0, -1, "1", None, 1.0])
def test_catalog_version_types(fixture: Fixture, version: object) -> None:
    with pytest.raises(V11LayoutFormatError, match=r"^catalog$"):
        decode(fixture, catalog_version=version)
    with pytest.raises(V11LayoutFormatError, match=r"^catalog$"):
        CatalogSnapshot(cast(int, version), fixture.snapshot.canonical_types)


def test_wire_array_order_and_immutable_output(fixture: Fixture) -> None:
    document = deepcopy(fixture.document)
    document["instances"].reverse()
    document["house"]["regions"].reverse()
    document["house"]["doors"].reverse()
    host(document, "side_table.library")["slot_policies"][0]["accepts"] = ["reports", "books"]
    raw = canonical(document)
    result = decode(fixture, raw)
    assert result.canonical_bytes == raw
    assert tuple(i.id for i in result.instances) == tuple(r["id"] for r in document["instances"])
    assert result.instances != result.catalog.instances
    assert encode(fixture, result).canonical_bytes == raw
    before = deepcopy(result)
    document["instances"].clear()
    assert result == before
    for value, attribute in [
        (result, "catalog_version"),
        (result.world, "regions"),
        (fixture.snapshot, "version"),
        (fixture.context, "maple_tile"),
    ]:
        with pytest.raises(FrozenInstanceError):
            setattr(value, attribute, None)


def test_isolation_and_input_mutation(fixture: Fixture, monkeypatch: pytest.MonkeyPatch) -> None:
    before = deepcopy((fixture.document, fixture.snapshot, fixture.context))
    raw = canonical(fixture.document)
    digest = hashlib.sha256(raw).hexdigest()
    original_import = builtins.__import__

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        pytest.fail("codec attempted a side effect")

    def guarded(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name.startswith(("maplegotchi.runtime", "maplegotchi.storage")):
            forbidden()
        return original_import(name, globals, locals, fromlist, level)

    with monkeypatch.context() as guard:
        for module, attribute in [
            (builtins, "open"),
            (io, "open"),
            (sqlite3, "connect"),
            (socket, "socket"),
            (time, "time"),
            (time, "monotonic"),
        ]:
            guard.setattr(module, attribute, forbidden)
        guard.setattr(builtins, "__import__", guarded)
        result = decode_layout_document(
            raw,
            validation_digest=digest,
            catalog_version=1,
            catalog_hash=fixture.snapshot.catalog_hash,
            snapshots=(fixture.snapshot,),
            context=fixture.context,
        )
        assert encode(fixture, result) == result
        with pytest.raises(V11LayoutFormatError, match=r"^digest$") as failure:
            decode_layout_document(
                raw,
                validation_digest="private-secret",
                catalog_version=1,
                catalog_hash=fixture.snapshot.catalog_hash,
                snapshots=(fixture.snapshot,),
                context=fixture.context,
            )
        assert failure.value.args == ("digest",)
    assert (fixture.document, fixture.snapshot, fixture.context) == before


@pytest.mark.parametrize("value", [0, 1, 1.0, "true", None, [], {}])
def test_boolean_policy_requires_boolean(fixture: Fixture, value: object) -> None:
    document = deepcopy(fixture.document)
    host(document, "bedside.bedroom")["slot_policies"] = [{"slot": "top", "maple_may_place": value}]
    with pytest.raises(V11LayoutFormatError, match=r"^type$"):
        decode(fixture, canonical(document))


def test_oversized_encoding_precedes_hash_and_parse(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = deepcopy(fixture.document)
    document["instances"][0]["link"] = "x" * MAX_LAYOUT_BYTES

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        pytest.fail("oversized encoding reached parser/hash")

    monkeypatch.setattr(json, "loads", forbidden)
    monkeypatch.setattr(hashlib, "sha256", forbidden)
    with pytest.raises(V11LayoutFormatError, match=r"^size$"):
        encode(fixture, document)


@pytest.mark.parametrize("section", ["house", "region", "door"])
@pytest.mark.parametrize("operation", ["missing", "unknown", "wrong_type"])
def test_nested_house_shape(fixture: Fixture, section: str, operation: str) -> None:
    document = deepcopy(fixture.document)
    row = document["house"] if section == "house" else document["house"][section + "s"][0]
    key = {"house": "regions", "region": "floor", "door": "passage"}[section]
    if operation == "missing":
        del row[key]
    elif operation == "unknown":
        row["private-secret"] = 1
    else:
        row[key] = None
    with pytest.raises(V11LayoutFormatError) as failure:
        decode(fixture, canonical(document))
    assert str(failure.value) in {"fields", "type"}


@pytest.mark.parametrize("digest", ["A" * 64, "z" * 64, "0" * 63, None, True])
def test_catalog_hash_format(fixture: Fixture, digest: object) -> None:
    with pytest.raises(V11LayoutFormatError, match=r"^catalog$"):
        decode(fixture, catalog_hash=digest)


@pytest.mark.parametrize(
    "kind", ["missing", "extra", "bool_int", "wrong_bool", "point_id", "slot_id"]
)
def test_catalog_nested_shapes(fixture: Fixture, kind: str) -> None:
    types = deepcopy(fixture.types)
    if kind == "missing":
        del types[0]["geometry_version"]
    elif kind == "extra":
        types[0]["private-secret"] = "private-secret"
    elif kind == "bool_int":
        types[0]["geometry_version"] = True
    elif kind == "wrong_bool":
        next(t for t in types if t["slots"])["slots"][0]["maple_may_place"] = 1
    elif kind == "point_id":
        types[0]["points"][0]["id"] = "a" * 129
    else:
        next(t for t in types if t["slots"])["slots"][0]["id"] = "a" * 129
    with pytest.raises(V11LayoutFormatError) as failure:
        CatalogSnapshot(1, canonical(types))
    assert str(failure.value) in {"fields", "type"}
    assert "private-secret" not in str(failure.value)


def test_catalog_immutability_and_ambiguous_identity(fixture: Fixture) -> None:
    with pytest.raises(V11LayoutFormatError, match=r"^catalog$"):
        decode(fixture, snapshots=[fixture.snapshot])
    with pytest.raises(V11LayoutFormatError, match=r"^catalog$"):
        decode(fixture, snapshots=(fixture.snapshot, fixture.snapshot))
    with pytest.raises(V11LayoutFormatError, match=r"^canonical$"):
        CatalogSnapshot(1, fixture.snapshot.canonical_types + b"\n")
    with pytest.raises(V11LayoutFormatError, match=r"^catalog$"):
        CatalogSnapshot(1, cast(bytes, bytearray(fixture.snapshot.canonical_types)))


def test_explicit_validation_context(fixture: Fixture) -> None:
    with pytest.raises(V11LayoutFormatError, match=r"^context$"):
        decode(fixture, context=None)
    with pytest.raises(V11LayoutFormatError, match=r"^context$"):
        LayoutContext(
            cast(Any, list(fixture.context.art)),
            fixture.context.legacy_targets,
            fixture.context.maple_tile,
        )
    with pytest.raises(V11LayoutFormatError, match=r"^layout$") as failure:
        decode(fixture, context=replace(fixture.context, maple_tile=Tile(1, 20)))
    assert "S13" in failure.value.rules
