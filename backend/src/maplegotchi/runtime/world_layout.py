"""Isolated release-data reader; no startup/life-loop integration."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import cast

from maplegotchi.core.world.coordinates import GRID_HEIGHT, GRID_WIDTH
from maplegotchi.core.world.layout import WorldLayout, build_layout
from maplegotchi.core.world.lighting import LightingZone
from maplegotchi.core.world.model import Door, DoorState, Rect, Region, RegionKind, RegionStatus


def _mapping(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("layout: missing or unknown object fields")
    return cast(dict[str, object], value)


def _sequence(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("layout: expected array")
    return cast(list[object], value)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("layout: expected nonempty text")
    return value


def _integer(value: object) -> int:
    if type(value) is not int:
        raise ValueError("layout: expected integer")
    return value


def _rect(value: object) -> Rect:
    values = _sequence(value)
    if len(values) != 4:
        raise ValueError("layout: rectangle requires four integers")
    return Rect(*(_integer(item) for item in values))


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"layout: duplicate field {key}")
        result[key] = value
    return result


def parse_layout(text: str) -> WorldLayout:
    """Strictly parse trusted declarative data, freeze and validate S1-S4/S12."""
    root = _mapping(
        json.loads(text, object_pairs_hook=_unique_object), {"grid", "regions", "doors"}
    )
    grid = tuple(_integer(value) for value in _sequence(root["grid"]))
    if grid != (GRID_WIDTH, GRID_HEIGHT):
        raise ValueError("S1: grid must be 44 x 26")
    regions: list[Region] = []
    zones: list[LightingZone] = []
    for value in _sequence(root["regions"]):
        row = _mapping(value, {"id", "kind", "floor", "status", "lighting_zone"})
        region = Region(
            _text(row["id"]),
            RegionKind(_text(row["kind"])),
            _rect(row["floor"]),
            RegionStatus(_text(row["status"])),
        )
        regions.append(region)
        zones.append(LightingZone(region.id, _rect(row["lighting_zone"])))
    doors: list[Door] = []
    for value in _sequence(root["doors"]):
        row = _mapping(value, {"id", "north_room", "south_room", "passage", "state"})
        doors.append(
            Door(
                _text(row["id"]),
                _text(row["north_room"]),
                _text(row["south_room"]),
                _rect(row["passage"]),
                DoorState(_text(row["state"])),
            )
        )
    return build_layout(tuple(regions), tuple(doors), tuple(zones))


def load_initial_house() -> WorldLayout:
    """Read only this shipped resource; never environment paths or live state."""
    text = (
        files("maplegotchi.world_catalog")
        .joinpath("initial_house.json")
        .read_text(encoding="utf-8")
    )
    return parse_layout(text)
