"""Strict isolated release catalog reader; never called by production startup."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import cast

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
from maplegotchi.core.world.layout import WorldLayout


def _record(
    value: object, required: set[str], optional: set[str] | None = None
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("catalog: expected object")
    result = cast(dict[str, object], value)
    if not required <= result.keys() or not result.keys() <= required | (optional or set()):
        raise ValueError("catalog: missing or unknown fields")
    return result


def _array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("catalog: expected array")
    return cast(list[object], value)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("catalog: expected text")
    return value


def _integer(value: object) -> int:
    if type(value) is not int:
        raise ValueError("catalog: expected integer")
    return value


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError("catalog: expected boolean")
    return value


def _pair(value: object) -> tuple[int, int]:
    items = _array(value)
    if len(items) != 2:
        raise ValueError("catalog: expected coordinate pair")
    return _integer(items[0]), _integer(items[1])


def _local(value: object) -> LocalPoint:
    return LocalPoint(*_pair(value))


def _optional_text(value: object) -> str | None:
    return None if value is None else _text(value)


def _point(value: object) -> PointTemplate:
    row = _record(
        value,
        {"id", "approach", "facing", "occupy", "pose", "occupy_direction", "provides", "capacity"},
    )
    return PointTemplate(
        _text(row["id"]),
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
        _text(row["id"]),
        _local(row["approach"]),
        CharacterDirection(_text(row["facing"])),
        _optional_text(row["shares_point"]),
        tuple(_text(item) for item in _array(row["accepts"])),
        _integer(row["capacity"]),
        _boolean(row["maple_may_place"]),
        SlotStatus(_text(row["status"])),
    )


def _type(value: object) -> ObjectType:
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
        Footprint(*_pair(row["footprint"])),
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
    # Present nulls are invalid; omission is the only way to retain a default.
    return SlotOverride(
        _text(row["slot"]),
        _local(row["approach"]) if "approach" in row else None,
        CharacterDirection(_text(row["facing"])) if "facing" in row else None,
    )


def _policy_override(value: object) -> SlotPolicyOverride:
    row = _record(value, {"slot"}, {"accepts", "capacity", "maple_may_place"})
    return SlotPolicyOverride(
        _text(row["slot"]),
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
        _text(row["id"]),
        _text(row["type"]),
        _text(row["room"]),
        Tile(*_pair(row["origin"])),
        ObjectOrientation(_text(row["orientation"])),
        _text(row["state"]),
        Owner(_text(row["owner"])),
        tuple(_geometry_override(item) for item in _array(row["slot_overrides"])),
        tuple(_policy_override(item) for item in _array(row["slot_policies"])),
        _optional_text(row["link"]),
    )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"catalog: duplicate field {key}")
        result[key] = value
    return result


def parse_catalog(text: str, world: WorldLayout) -> CatalogLayout:
    root = _record(json.loads(text, object_pairs_hook=_unique_object), {"types", "instances"})
    catalog = Catalog(tuple(_type(value) for value in _array(root["types"])))
    instances = tuple(_instance(value) for value in _array(root["instances"]))
    return build_catalog_layout(catalog, instances, world)


def load_initial_catalog(world: WorldLayout) -> CatalogLayout:
    text = (
        files("maplegotchi.world_catalog")
        .joinpath("initial_catalog.json")
        .read_text(encoding="utf-8")
    )
    return parse_catalog(text, world)
