"""Pure test-only format-1 layout codec; no storage, resource lookup or activation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal, NoReturn, cast

from maplegotchi.core.room import InteractionPoint
from maplegotchi.core.world.catalog import (
    Capability,
    Catalog,
    CatalogLayout,
    Category,
    Footprint,
    LocalPoint,
    ObjectInstance,
    ObjectType,
    Owner,
    Permission,
    PointPose,
    PointTemplate,
    SlotOverride,
    SlotPolicyOverride,
    SlotStatus,
    SlotTemplate,
    Surface,
    build_catalog_layout,
)
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.directions import CharacterDirection, ObjectOrientation
from maplegotchi.core.world.layout import WorldLayout, build_layout
from maplegotchi.core.world.layout_validation import ArtGeometry, LayoutCandidate, validate_layout
from maplegotchi.core.world.lighting import LightingZone
from maplegotchi.core.world.model import Door, DoorState, Rect, Region, RegionKind, RegionStatus

MAX_LAYOUT_BYTES = 262144
ErrorCategory = Literal[
    "size",
    "json",
    "canonical",
    "fields",
    "type",
    "version",
    "digest",
    "catalog",
    "context",
    "layout",
]


class V11LayoutFormatError(ValueError):
    """Messages contain only a fixed category; optional rule codes are also fixed."""

    def __init__(self, category: ErrorCategory, rules: tuple[str, ...] = ()) -> None:
        super().__init__(category)
        self.rules = rules


def _core_failure(error: Exception, category: ErrorCategory) -> V11LayoutFormatError:
    prefix = str(error).split(":", 1)[0]
    rules = (prefix,) if prefix in tuple(f"S{i}" for i in range(1, 18)) else ()
    return V11LayoutFormatError(category, rules)


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise V11LayoutFormatError("fields")
        result[key] = value
    return result


def _constant(value: str) -> NoReturn:
    raise V11LayoutFormatError("json")


def _parse(raw: bytes) -> object:
    try:
        # Explicit UTF-8 decoding prevents json.loads(bytes) from admitting UTF-16/32.
        result: object = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
        return result
    except V11LayoutFormatError:
        raise
    except (ValueError, TypeError, RecursionError):
        raise V11LayoutFormatError("json") from None


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")
    except (ValueError, TypeError, RecursionError):
        raise V11LayoutFormatError("json") from None


def _layout_bytes(text: str | bytes) -> bytes:
    if type(text) not in (str, bytes):
        raise V11LayoutFormatError("type")
    # UTF-8 bytes cannot be fewer than Unicode characters. Reject before allocating
    # an encoding for an already oversized string; check exact bytes below.
    if len(text) > MAX_LAYOUT_BYTES:
        raise V11LayoutFormatError("size")
    try:
        raw = text.encode("utf-8") if isinstance(text, str) else text
    except UnicodeError:
        raise V11LayoutFormatError("json") from None
    if len(raw) > MAX_LAYOUT_BYTES:
        raise V11LayoutFormatError("size")
    return raw


def _record(
    value: object, required: set[str], optional: set[str] | None = None
) -> dict[str, object]:
    if not isinstance(value, dict) or not required <= value.keys() <= required | (
        optional or set()
    ):
        raise V11LayoutFormatError("fields")
    return cast(dict[str, object], value)


def _array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise V11LayoutFormatError("type")
    return cast(list[object], value)


def _text(value: object) -> str:
    if type(value) is not str:
        raise V11LayoutFormatError("type")
    return value


def _key(value: object) -> str:
    result = _text(value)
    if not 1 <= len(result) <= 128:
        raise V11LayoutFormatError("fields")
    return result


def _integer(value: object) -> int:
    if type(value) is not int:
        raise V11LayoutFormatError("type")
    return value


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise V11LayoutFormatError("type")
    return value


def _integers(value: object, length: int) -> tuple[int, ...]:
    items = _array(value)
    if len(items) != length:
        raise V11LayoutFormatError("fields")
    return tuple(_integer(item) for item in items)


def _local(value: object) -> LocalPoint:
    return LocalPoint(*_integers(value, 2))


def _optional_text(value: object) -> str | None:
    return None if value is None else _text(value)


def _point(value: object) -> PointTemplate:
    row = _record(
        value,
        {"id", "approach", "facing", "occupy", "pose", "occupy_direction", "provides", "capacity"},
    )
    return PointTemplate(
        _key(row["id"]),
        _local(row["approach"]),
        CharacterDirection(_text(row["facing"])),
        None if row["occupy"] is None else _local(row["occupy"]),
        PointPose(_text(row["pose"])),
        CharacterDirection(_text(row["occupy_direction"])),
        tuple(Capability(_text(item)) for item in _array(row["provides"])),
        _integer(row["capacity"]),
    )


def _slot(value: object) -> SlotTemplate:
    row = _record(
        value,
        {
            "id",
            "approach",
            "facing",
            "shares_point",
            "accepts",
            "capacity",
            "maple_may_place",
            "status",
        },
    )
    return SlotTemplate(
        _key(row["id"]),
        _local(row["approach"]),
        CharacterDirection(_text(row["facing"])),
        None if row["shares_point"] is None else _key(row["shares_point"]),
        tuple(_text(item) for item in _array(row["accepts"])),
        _integer(row["capacity"]),
        _boolean(row["maple_may_place"]),
        SlotStatus(_text(row["status"])),
    )


def _object_type(value: object) -> ObjectType:
    row = _record(
        value,
        {
            "id",
            "category",
            "geometry_version",
            "footprint",
            "blocks",
            "orientations",
            "capabilities",
            "points",
            "slots",
            "states",
            "movable_by",
            "deletable_by",
            "surface",
            "mount_y_px",
            "art_id",
        },
    )
    return ObjectType(
        _text(row["id"]),
        Category(_text(row["category"])),
        _integer(row["geometry_version"]),
        Footprint(*_integers(row["footprint"], 2)),
        tuple(_text(item) for item in _array(row["blocks"])),
        tuple(ObjectOrientation(_text(item)) for item in _array(row["orientations"])),
        tuple(Capability(_text(item)) for item in _array(row["capabilities"])),
        tuple(_point(item) for item in _array(row["points"])),
        tuple(_slot(item) for item in _array(row["slots"])),
        tuple(_text(item) for item in _array(row["states"])),
        tuple(Permission(_text(item)) for item in _array(row["movable_by"])),
        tuple(Permission(_text(item)) for item in _array(row["deletable_by"])),
        Surface(_text(row["surface"])),
        None if row["mount_y_px"] is None else _integer(row["mount_y_px"]),
        _optional_text(row["art_id"]),
    )


def _geometry_override(value: object) -> SlotOverride:
    row = _record(value, {"slot"}, {"approach", "facing"})
    return SlotOverride(
        _key(row["slot"]),
        _local(row["approach"]) if "approach" in row else None,
        CharacterDirection(_text(row["facing"])) if "facing" in row else None,
    )


def _policy_override(value: object) -> SlotPolicyOverride:
    row = _record(value, {"slot"}, {"accepts", "capacity", "maple_may_place"})
    return SlotPolicyOverride(
        _key(row["slot"]),
        tuple(_text(item) for item in _array(row["accepts"])) if "accepts" in row else None,
        _integer(row["capacity"]) if "capacity" in row else None,
        _boolean(row["maple_may_place"]) if "maple_may_place" in row else None,
    )


def _instance(value: object) -> ObjectInstance:
    row = _record(
        value,
        {
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
        },
    )
    return ObjectInstance(
        _key(row["id"]),
        _key(row["type"]),
        _key(row["room"]),
        Tile(*_integers(row["origin"], 2)),
        ObjectOrientation(_text(row["orientation"])),
        _text(row["state"]),
        Owner(_text(row["owner"])),
        tuple(_geometry_override(item) for item in _array(row["slot_overrides"])),
        tuple(_policy_override(item) for item in _array(row["slot_policies"])),
        _optional_text(row["link"]),
    )


def _house(
    value: object,
) -> tuple[tuple[int, ...], tuple[Region, ...], tuple[Door, ...], tuple[LightingZone, ...]]:
    row = _record(value, {"grid", "regions", "doors"})
    grid = _integers(row["grid"], 2)
    regions = []
    zones = []
    for value in _array(row["regions"]):
        region = _record(value, {"id", "kind", "floor", "status", "lighting_zone"})
        identity = _key(region["id"])
        regions.append(
            Region(
                identity,
                RegionKind(_text(region["kind"])),
                Rect(*_integers(region["floor"], 4)),
                RegionStatus(_text(region["status"])),
            )
        )
        zones.append(LightingZone(identity, Rect(*_integers(region["lighting_zone"], 4))))
    doors = []
    for value in _array(row["doors"]):
        door = _record(value, {"id", "north_room", "south_room", "passage", "state"})
        doors.append(
            Door(
                _key(door["id"]),
                _key(door["north_room"]),
                _key(door["south_room"]),
                Rect(*_integers(door["passage"], 4)),
                DoorState(_text(door["state"])),
            )
        )
    return grid, tuple(regions), tuple(doors), tuple(zones)


def _hash_text(value: str, category: ErrorCategory) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise V11LayoutFormatError(category)


@dataclass(frozen=True, slots=True)
class CatalogSnapshot:
    """Caller-supplied immutable release types; bytes preserve original array order.

    This is not a persisted catalog table or a resource reader. Types must be the
    canonical JSON array from a release's `types` field, not a catalog envelope.
    """

    version: int
    canonical_types: bytes
    catalog_hash: str = field(init=False)
    catalog: Catalog = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.version) is not int
            or self.version <= 0
            or type(self.canonical_types) is not bytes
        ):
            raise V11LayoutFormatError("catalog")
        data = _parse(self.canonical_types)
        if _canonical(data) != self.canonical_types:
            raise V11LayoutFormatError("canonical")
        try:
            catalog = Catalog(tuple(_object_type(item) for item in _array(data)))
        except V11LayoutFormatError:
            raise
        except (ValueError, TypeError) as error:
            raise _core_failure(error, "catalog") from None
        object.__setattr__(self, "catalog", catalog)
        object.__setattr__(self, "catalog_hash", hashlib.sha256(self.canonical_types).hexdigest())


@dataclass(frozen=True, slots=True)
class LayoutContext:
    art: tuple[ArtGeometry, ...]
    legacy_targets: tuple[InteractionPoint, ...]
    maple_tile: Tile

    def __post_init__(self) -> None:
        if (
            not isinstance(self.art, tuple)
            or any(not isinstance(item, ArtGeometry) for item in self.art)
            or not isinstance(self.legacy_targets, tuple)
            or any(not isinstance(item, InteractionPoint) for item in self.legacy_targets)
            or not isinstance(self.maple_tile, Tile)
        ):
            raise V11LayoutFormatError("context")


@dataclass(frozen=True, slots=True)
class LayoutDocument:
    """Verified layout only, not a life snapshot or database-admission decision."""

    canonical_bytes: bytes
    validation_digest: str
    catalog_version: int
    catalog_hash: str
    world: WorldLayout
    catalog: CatalogLayout
    instances: tuple[
        ObjectInstance, ...
    ]  # Wire order; core catalog layout derives sorted instances.


def decode_layout_document(
    text: str | bytes,
    *,
    validation_digest: str,
    catalog_version: int,
    catalog_hash: str,
    snapshots: tuple[CatalogSnapshot, ...],
    context: LayoutContext,
) -> LayoutDocument:
    raw = _layout_bytes(text)  # Before parser, hashing or domain reconstruction.
    _hash_text(validation_digest, "digest")
    if hashlib.sha256(raw).hexdigest() != validation_digest:
        raise V11LayoutFormatError("digest")
    data = _parse(raw)
    if _canonical(data) != raw:
        raise V11LayoutFormatError("canonical")
    root = _record(data, {"format_version", "house", "instances", "themes", "lighting_presets"})
    if _integer(root["format_version"]) != 1:
        raise V11LayoutFormatError("version")
    _record(root["themes"], set())
    _record(root["lighting_presets"], set())
    _hash_text(catalog_hash, "catalog")
    if type(catalog_version) is not int or catalog_version <= 0:
        raise V11LayoutFormatError("catalog")
    if not isinstance(snapshots, tuple) or any(
        not isinstance(s, CatalogSnapshot) for s in snapshots
    ):
        raise V11LayoutFormatError("catalog")
    matches = tuple(
        s for s in snapshots if (s.version, s.catalog_hash) == (catalog_version, catalog_hash)
    )
    if len(matches) != 1:
        raise V11LayoutFormatError("catalog")
    if not isinstance(context, LayoutContext):
        raise V11LayoutFormatError("context")
    snapshot = matches[0]
    try:
        grid, regions, doors, zones = _house(root["house"])
        instances = tuple(_instance(item) for item in _array(root["instances"]))
        candidate = LayoutCandidate(
            regions,
            doors,
            zones,
            snapshot.catalog.types,
            instances,
            context.art,
            context.legacy_targets,
            context.maple_tile,
            grid[0],
            grid[1],
        )
        validation = validate_layout(candidate)
        if not validation.valid:
            raise V11LayoutFormatError(
                "layout",
                tuple(sorted({e.code for e in validation.errors}, key=lambda code: int(code[1:]))),
            )
        world = build_layout(regions, doors, zones)
        catalog = build_catalog_layout(snapshot.catalog, instances, world)
    except V11LayoutFormatError:
        raise
    except (ValueError, TypeError, KeyError) as error:
        raise _core_failure(error, "layout") from None
    return LayoutDocument(
        raw, validation_digest, catalog_version, catalog_hash, world, catalog, instances
    )


def encode_layout_document(
    document: object,
    *,
    catalog_version: int,
    catalog_hash: str,
    snapshots: tuple[CatalogSnapshot, ...],
    context: LayoutContext,
) -> LayoutDocument:
    """Encode JSON-shaped input or revalidate a decoded result without losing wire order.

    The returned frozen result includes the encoded bytes and computed digest.
    Raw source arrays survive in those bytes, even where core values are sorted.
    """
    raw = _layout_bytes(
        document.canonical_bytes if isinstance(document, LayoutDocument) else _canonical(document)
    )
    return decode_layout_document(
        raw,
        validation_digest=hashlib.sha256(raw).hexdigest(),
        catalog_version=catalog_version,
        catalog_hash=catalog_hash,
        snapshots=snapshots,
        context=context,
    )
