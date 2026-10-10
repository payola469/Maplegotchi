"""Catalog metadata acceptance, independent T3/T4/T5 equality and negative schema cases."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from importlib.resources import files
from typing import Any, cast

import pytest

from maplegotchi.core.world.catalog import (
    Capability,
    Catalog,
    CatalogLayout,
    Footprint,
    LocalPoint,
    Owner,
    Permission,
    SlotOverride,
    SlotPolicyOverride,
    Surface,
    blocking_offsets,
    build_catalog_layout,
    oriented_footprint,
    rotate_direction,
    rotate_local,
    rotate_vector,
    validate_provider_metadata,
)
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.directions import CharacterDirection, ObjectOrientation
from maplegotchi.core.world.layout import WorldLayout
from maplegotchi.runtime.world_catalog import load_initial_catalog, parse_catalog
from maplegotchi.runtime.world_layout import load_initial_house
from tests.world.oracle import Oracle, Table


@pytest.fixture(scope="module")
def world() -> WorldLayout:
    return load_initial_house()


@pytest.fixture(scope="module")
def house(world: WorldLayout) -> CatalogLayout:
    return load_initial_catalog(world)


def resource() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            files("maplegotchi.world_catalog")
            .joinpath("initial_catalog.json")
            .read_text(encoding="utf-8")
        ),
    )


def row(data: dict[str, Any], section: str, id: str) -> dict[str, Any]:
    return next(cast(dict[str, Any], item) for item in data[section] if item["id"] == id)


def test_exact_t3_t4_t5_equality(house: CatalogLayout, spec_oracle: Oracle) -> None:
    instances = {instance.id: instance for instance in house.instances}
    points = {f"{point.instance_id}/{point.template.id}": point.template for point in house.points}
    slots = {f"{slot.instance_id}/{slot.template.id}": slot.template for slot in house.slots}
    t3 = []
    for approved in spec_oracle.table(3).rows:
        instance = instances[approved[0]]
        item = house.catalog.get(instance.type_id)
        if item.surface is Surface.NORTH_BAND:
            end = instance.origin.tx + item.footprint.w - 1
            origin = f"band x{instance.origin.tx}" + (f"-{end}" if item.footprint.w > 1 else "")
            footprint, mask = f"wall {item.footprint.w}", "-"
        else:
            origin = f"{instance.origin.tx};{instance.origin.ty}"
            footprint = f"{item.footprint.w}x{item.footprint.h}"
            mask = "all" if any("#" in line for line in item.blocks) else "none"
        t3.append(
            (
                instance.id,
                item.id,
                instance.room_id,
                origin,
                footprint,
                mask,
                ";".join(item.capabilities) or "-",
                str(item.mount_y_px) if item.mount_y_px is not None else "-",
            )
        )
    t4 = []
    for approved in spec_oracle.table(4).rows:
        point = points[approved[0]]
        occupy = f"{point.occupy.x};{point.occupy.y}" if point.occupy else "null"
        t4.append(
            (
                approved[0],
                f"{point.approach.x};{point.approach.y}",
                point.facing.value,
                occupy,
                point.pose.value,
                point.occupy_direction.value,
                ";".join(point.provides),
            )
        )
    t5 = []
    for approved in spec_oracle.table(5).rows:
        slot = slots[approved[0]]
        t5.append(
            (
                approved[0],
                f"{slot.approach.x};{slot.approach.y}",
                slot.facing.value,
                slot.shares_point or "-",
                ";".join(slot.accepts),
                str(slot.capacity),
                str(slot.maple_may_place).lower(),
                slot.status.value,
            )
        )
    assert len(instances) == len(t3) == 28
    assert len(points) == len(t4) == 17
    assert len(slots) == len(t5) == 12
    for number, actual in ((3, t3), (4, t4), (5, t5)):
        assert Table(spec_oracle.table(number).columns, tuple(actual)) == spec_oracle.table(number)


def test_initial_metadata_counts_and_owner(house: CatalogLayout, world: WorldLayout) -> None:
    assert len(house.catalog.types) == 15
    assert len(house.blocking_tiles) == 34
    for room, expected in (
        ("bedroom", 7),
        ("living_room", 6),
        ("library", 7),
        ("work_studio", 14),
        ("central_hall", 0),
    ):
        floor = next(item.floor for item in world.regions if item.id == room)
        assert sum(floor.contains(tile) for tile in house.blocking_tiles) == expected
    assert all(instance.owner is Owner.PAOLO for instance in house.instances)
    assert all(
        item.movable_by == item.deletable_by == (Permission.OWNER,) for item in house.catalog.types
    )
    marker = house.catalog.get("marker.idle_spot")
    assert marker.art_id is None and marker.blocks == (".",)
    assert all(
        item.art_id == item.id and item.geometry_version == 1
        for item in house.catalog.types
        if item.id != marker.id
    )


def test_option_a_and_poses(house: CatalogLayout) -> None:
    assert house.catalog.get("furniture.writing_desk").capabilities == (Capability.WRITING_SURFACE,)
    assert house.catalog.get("furniture.computer_desk").capabilities == (Capability.COMPUTER,)
    points = {p.instance_id: p.template for p in house.points if p.instance_id.startswith("desk.")}
    assert points["desk.writing"].pose.value == "sit_write"
    assert points["desk.computer"].pose.value == "sit_monitor"
    assert points["desk.writing"].occupy == points["desk.computer"].occupy == LocalPoint(24, -6)
    assert points["desk.writing"].provides == (Capability.WRITING_SURFACE,)
    assert points["desk.computer"].provides == (Capability.COMPUTER,)


def test_override_is_explicit_local_and_does_not_mutate_type(house: CatalogLayout) -> None:
    default = house.catalog.get("furniture.side_table").slots[0]
    assert (default.approach, default.facing.value, default.capacity) == (LocalPoint(0, 1), "up", 1)
    slots = {s.instance_id: s.template for s in house.slots if s.template.id == "top"}
    assert slots["bedside.bedroom"].approach == LocalPoint(4, 3)
    assert slots["bedside.bedroom"].facing is CharacterDirection.LEFT
    assert slots["side_table.living"].approach == LocalPoint(10, 6)
    assert slots["side_table.library"].approach == LocalPoint(23, 8)
    assert slots["side_table.library"].capacity == 2
    assert slots["side_table.library"].accepts == ("creation.small", "document.stack")
    assert slots["bedside.bedroom"].capacity == default.capacity
    assert slots["bedside.bedroom"].accepts == default.accepts
    assert slots["bedside.bedroom"].maple_may_place == default.maple_may_place


def test_no_position_inferred_override(world: WorldLayout) -> None:
    data = resource()
    row(data, "instances", "bedside.bedroom")["slot_overrides"] = []
    # The default would be (3,4), up, coinciding with the bed's point.
    # Do not infer the approved (4,3), left override from the instance position.
    with pytest.raises(ValueError, match="undeclared approach coincidence"):
        parse_catalog(json.dumps(data), world)


@pytest.mark.parametrize("field,value", [("approach", [1, 0]), ("facing", "left")])
def test_partial_geometry_override(world: WorldLayout, field: str, value: object) -> None:
    data = resource()
    item = row(data, "instances", "bedside.bedroom")
    item["origin"] = [5, 5]
    item["slot_overrides"] = [{"slot": "top", field: value}]
    parsed = parse_catalog(json.dumps(data), world)
    slot = next(s.template for s in parsed.slots if s.instance_id == "bedside.bedroom")
    assert slot.approach == (LocalPoint(6, 5) if field == "approach" else LocalPoint(5, 6))
    assert slot.facing is (CharacterDirection.LEFT if field == "facing" else CharacterDirection.UP)


def test_immutable_and_order_independent(house: CatalogLayout, world: WorldLayout) -> None:
    data = resource()
    data["types"].reverse()
    data["instances"].reverse()
    assert parse_catalog(json.dumps(data), world) == house
    parsed = parse_catalog(json.dumps(data), world)
    data["types"][0]["blocks"][0] = "wrong"
    assert parsed == house
    with pytest.raises(FrozenInstanceError):
        house.instances[0].id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        house.catalog.types[0].footprint.w = 99  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        house.slots[0].template.approach.x = 99  # type: ignore[misc]
    assert tuple(item.id for item in house.catalog.types) == tuple(
        sorted(item.id for item in house.catalog.types)
    )
    assert tuple(item.id for item in house.instances) == tuple(
        sorted(item.id for item in house.instances)
    )


@pytest.mark.parametrize(
    "orientation,size,local,direction,vector,blocks",
    [
        (
            ObjectOrientation.SOUTH,
            (3, 2),
            (1, 2),
            CharacterDirection.UP,
            (24, -6),
            ((0, 0), (2, 1)),
        ),
        (
            ObjectOrientation.WEST,
            (2, 3),
            (-1, 1),
            CharacterDirection.RIGHT,
            (6, 24),
            ((1, 0), (0, 2)),
        ),
        (
            ObjectOrientation.NORTH,
            (3, 2),
            (1, -1),
            CharacterDirection.DOWN,
            (-24, 6),
            ((0, 0), (2, 1)),
        ),
        (
            ObjectOrientation.EAST,
            (2, 3),
            (2, 1),
            CharacterDirection.LEFT,
            (-6, -24),
            ((1, 0), (0, 2)),
        ),
    ],
)
def test_quarter_turns(
    house: CatalogLayout,
    orientation: ObjectOrientation,
    size: tuple[int, int],
    local: tuple[int, int],
    direction: CharacterDirection,
    vector: tuple[int, int],
    blocks: tuple[tuple[int, int], ...],
) -> None:
    item = replace(
        house.catalog.get("furniture.writing_desk"),
        blocks=("#..", "..#"),
        orientations=tuple(ObjectOrientation),
    )
    assert oriented_footprint(item, orientation) == Footprint(*size)
    assert rotate_local(LocalPoint(1, 2), item.footprint, orientation) == LocalPoint(*local)
    assert rotate_direction(CharacterDirection.UP, orientation) is direction
    assert rotate_vector(LocalPoint(24, -6), orientation) == LocalPoint(*vector)
    assert blocking_offsets(item, orientation) == tuple(LocalPoint(*xy) for xy in blocks)


@pytest.mark.parametrize("orientation", list(ObjectOrientation))
def test_rotated_override_uses_same_transform(
    world: WorldLayout, house: CatalogLayout, orientation: ObjectOrientation
) -> None:
    item = replace(house.catalog.get("furniture.side_table"), orientations=tuple(ObjectOrientation))
    original = next(i for i in house.instances if i.id == "side_table.living")
    instance = replace(
        original,
        origin=Tile(15, 7),
        orientation=orientation,
        slot_overrides=(SlotOverride("top", LocalPoint(1, 0), CharacterDirection.LEFT),),
    )
    layout = build_catalog_layout(Catalog((item,)), (instance,), world)
    offset = rotate_local(LocalPoint(1, 0), item.footprint, orientation)
    assert layout.slots[0].template.approach == LocalPoint(15 + offset.x, 7 + offset.y)
    assert layout.slots[0].template.facing is rotate_direction(CharacterDirection.LEFT, orientation)


@pytest.mark.parametrize(
    "target,id,field,value",
    [
        ("types", "furniture.rug", "id", "invalid/id"),
        ("types", "furniture.rug", "category", "bad"),
        ("types", "furniture.rug", "geometry_version", 0),
        ("types", "furniture.rug", "geometry_version", True),
        ("types", "furniture.rug", "geometry_version", 1.0),
        ("types", "furniture.rug", "footprint", [0, 2]),
        ("types", "furniture.rug", "footprint", [45, 2]),
        ("types", "furniture.rug", "footprint", [3, -1]),
        ("types", "furniture.rug", "footprint", [True, 2]),
        ("types", "furniture.rug", "blocks", ["..."]),
        ("types", "furniture.rug", "blocks", ["..", "..."]),
        ("types", "furniture.rug", "blocks", ["???", "..."]),
        ("types", "furniture.rug", "orientations", []),
        ("types", "furniture.rug", "orientations", ["front"]),
        ("types", "furniture.rug", "orientations", ["south", "south"]),
        ("types", "furniture.rug", "capabilities", ["unapproved"]),
        ("types", "furniture.rug", "capabilities", ["seat", "seat"]),
        ("types", "furniture.rug", "states", []),
        ("types", "furniture.rug", "states", ["off"]),
        ("types", "furniture.rug", "states", ["default", "default"]),
        ("types", "furniture.rug", "movable_by", ["maple"]),
        ("types", "furniture.rug", "deletable_by", ["maple"]),
        ("types", "furniture.rug", "movable_by", []),
        ("types", "furniture.rug", "movable_by", ["owner", "owner"]),
        ("types", "furniture.rug", "mount_y_px", 8),
        ("types", "furniture.rug", "surface", "side_wall"),
        ("types", "furniture.rug", "art_id", None),
        ("types", "furniture.rug", "art_id", "bad/path.png"),
        ("types", "furniture.writing_desk", "capabilities", ["writing_surface", "seat"]),
        ("types", "furniture.computer_desk", "capabilities", ["computer", "seat"]),
        ("types", "window.north_2w", "mount_y_px", None),
        ("types", "window.north_2w", "mount_y_px", 0),
        ("types", "window.north_2w", "mount_y_px", False),
        ("types", "window.north_2w", "blocks", ["##"]),
        ("instances", "rug.living", "type", "missing.type"),
        ("instances", "rug.living", "id", ""),
        ("instances", "rug.living", "room", "missing"),
        ("instances", "rug.living", "room", "future_space"),
        ("instances", "rug.living", "orientation", "east"),
        ("instances", "rug.living", "state", "missing"),
        ("instances", "rug.living", "owner", "maple"),
        ("instances", "rug.living", "owner", "owner"),
        ("instances", "rug.living", "origin", [43, 25]),
        ("instances", "rug.living", "origin", [0, 0]),
        ("instances", "rug.living", "origin", [-1, 0]),
        ("instances", "rug.living", "origin", [True, 6]),
        ("instances", "rug.living", "origin", [11.0, 6]),
        ("instances", "rug.living", "origin", [11, 6, 0]),
        ("instances", "window.studio", "origin", [36, 1]),
        ("instances", "window.studio", "origin", [43, 0]),
        ("instances", "window.studio", "origin", [36, 10]),
        ("instances", "frame.hall_west", "origin", [15, 10]),
        ("instances", "lamp.living", "origin", [10, 5]),
        (
            "instances",
            "bedside.bedroom",
            "slot_overrides",
            [{"slot": "unknown", "approach": [1, 0]}],
        ),
        ("instances", "bedside.bedroom", "slot_overrides", [{"slot": "top"}]),
        ("instances", "bedside.bedroom", "slot_overrides", [{"slot": "top", "approach": None}]),
        ("instances", "bedside.bedroom", "slot_overrides", [{"slot": "top", "facing": "north"}]),
        (
            "instances",
            "bedside.bedroom",
            "slot_overrides",
            [{"slot": "top", "approach": [True, 0]}],
        ),
        ("instances", "bedside.bedroom", "slot_overrides", [{"slot": "top", "approach": [-4, 0]}]),
        ("instances", "bedside.bedroom", "slot_overrides", [{"slot": "top", "approach": [6, 0]}]),
        (
            "instances",
            "bedside.bedroom",
            "slot_overrides",
            [{"slot": "top", "facing": "left", "capacity": 9}],
        ),
        (
            "instances",
            "bedside.bedroom",
            "slot_overrides",
            [{"slot": "top", "facing": "left", "owner": "maple"}],
        ),
        ("instances", "bedside.bedroom", "slot_policies", [{"slot": "missing", "capacity": 1}]),
        ("instances", "bedside.bedroom", "slot_policies", [{"slot": "top", "capacity": 0}]),
        ("instances", "bedside.bedroom", "slot_policies", [{"slot": "top", "accepts": []}]),
        ("instances", "bedside.bedroom", "slot_policies", [{"slot": "top", "maple_may_place": 1}]),
        ("instances", "bedside.bedroom", "slot_policies", [{"slot": "top", "approach": [1, 0]}]),
        ("instances", "desk.writing", "slot_overrides", [{"slot": "desktop", "approach": [2, 2]}]),
        (
            "instances",
            "bookshelf.library_1",
            "slot_policies",
            [{"slot": "books", "maple_may_place": True}],
        ),
    ],
)
def test_invalid_resource(
    world: WorldLayout, target: str, id: str, field: str, value: object
) -> None:
    data = resource()
    row(data, target, id)[field] = value
    with pytest.raises(ValueError):
        parse_catalog(json.dumps(data), world)


@pytest.mark.parametrize("section", ["types", "instances"])
def test_duplicate_ids(world: WorldLayout, section: str) -> None:
    data = resource()
    data[section].append(data[section][0])
    with pytest.raises(ValueError, match="duplicate"):
        parse_catalog(json.dumps(data), world)


@pytest.mark.parametrize("field", ["slot_overrides", "slot_policies"])
def test_duplicate_overrides(world: WorldLayout, field: str) -> None:
    data = resource()
    row(data, "instances", "bedside.bedroom")[field] = (
        [{"slot": "top", "facing": "up"}] * 2
        if field == "slot_overrides"
        else [{"slot": "top", "capacity": 1}] * 2
    )
    with pytest.raises(ValueError, match="duplicate"):
        parse_catalog(json.dumps(data), world)


@pytest.mark.parametrize(
    "field,value",
    [
        ("approach", [1.0, 2]),
        ("facing", "front"),
        ("occupy", [24, False]),
        ("pose", "sit"),
        ("occupy_direction", "north"),
        ("capacity", 0),
        ("capacity", True),
        ("provides", []),
        ("provides", ["seat"]),
        ("provides", ["writing_surface", "writing_surface"]),
    ],
)
def test_invalid_point(world: WorldLayout, field: str, value: object) -> None:
    data = resource()
    row(data, "types", "furniture.writing_desk")["points"][0][field] = value
    with pytest.raises(ValueError):
        parse_catalog(json.dumps(data), world)


@pytest.mark.parametrize(
    "field,value",
    [
        ("approach", [100, 0]),
        ("facing", "front"),
        ("shares_point", "missing"),
        ("capacity", 0),
        ("capacity", True),
        ("accepts", []),
        ("accepts", ["creation.small", "creation.small"]),
        ("maple_may_place", 1),
        ("status", "missing"),
    ],
)
def test_invalid_slot(world: WorldLayout, field: str, value: object) -> None:
    data = resource()
    row(data, "types", "furniture.writing_desk")["slots"][0][field] = value
    with pytest.raises(ValueError):
        parse_catalog(json.dumps(data), world)


@pytest.mark.parametrize(
    "text",
    [
        "{}",
        '{"types":[],"instances":[]}',
        '{"types":[],"types":[],"instances":[]}',
        '{"types":{},"instances":[]}',
        "[1]",
        "{",
    ],
)
def test_malformed_root(world: WorldLayout, text: str) -> None:
    with pytest.raises(ValueError):
        parse_catalog(text, world)


@pytest.mark.parametrize("kind", ["point", "slot"])
def test_duplicate_templates(world: WorldLayout, kind: str) -> None:
    data = resource()
    field = "points" if kind == "point" else "slots"
    item = row(data, "types", "furniture.writing_desk")
    item[field].append(item[field][0])
    with pytest.raises(ValueError, match="duplicate"):
        parse_catalog(json.dumps(data), world)


def test_reader_env_isolation(
    world: WorldLayout, house: CatalogLayout, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAPLE_DATA_DIR", "/must-not-be-read")
    assert load_initial_catalog(world) == house


def test_metadata_provider_coverage_only(house: CatalogLayout, spec_oracle: Oracle) -> None:
    requirements = tuple(
        tuple(tuple(Capability(cap) for cap in group.split("&")) for group in row[1].split("|"))
        for row in spec_oracle.table(6).rows
    )
    validate_provider_metadata(house, requirements)
    with pytest.raises(ValueError, match="missing provider"):
        validate_provider_metadata(house, (((Capability.SYSTEM_CONSOLE,),),))
    with pytest.raises(ValueError, match="invalid"):
        validate_provider_metadata(house, ((),))


def test_direct_constructor_rejects_mutable_metadata(house: CatalogLayout) -> None:
    with pytest.raises(ValueError, match="immutable"):
        Catalog(cast(Any, list(house.catalog.types)))
    with pytest.raises(ValueError, match="immutable"):
        replace(house.catalog.get("furniture.rug"), blocks=cast(Any, ["...", "..."]))
    with pytest.raises(ValueError):
        LocalPoint(True, 0)
    with pytest.raises(ValueError):
        SlotOverride("top")
    with pytest.raises(ValueError):
        SlotPolicyOverride("top")


def test_unknown_type_lookup(house: CatalogLayout) -> None:
    with pytest.raises(ValueError, match="S17"):
        house.catalog.get("missing.type")


@pytest.mark.parametrize(
    "scenario",
    [
        "point_point",
        "point_slot",
        "slot_slot",
        "unknown_root",
        "unknown_instance",
        "unknown_type",
        "unknown_point",
        "unknown_slot",
    ],
)
def test_coincidence_and_unknown_fields(world: WorldLayout, scenario: str) -> None:
    data = resource()
    if scenario == "point_point":
        row(data, "instances", "idle.hall_east")["origin"] = [21, 15]
    elif scenario == "point_slot":
        row(data, "instances", "bedside.bedroom")["slot_overrides"] = [
            {"slot": "top", "approach": [0, 1]}
        ]
    elif scenario == "slot_slot":
        row(data, "instances", "frame.hall_east")["origin"] = [10, 10]
    elif scenario == "unknown_root":
        data["new"] = 0
    elif scenario == "unknown_instance":
        row(data, "instances", "desk.writing")["approach"] = [34, 5]
    elif scenario == "unknown_type":
        row(data, "types", "furniture.writing_desk")["new"] = 0
    elif scenario == "unknown_point":
        row(data, "types", "furniture.writing_desk")["points"][0]["new"] = 0
    else:
        row(data, "types", "furniture.writing_desk")["slots"][0]["new"] = 0
    with pytest.raises(ValueError):
        parse_catalog(json.dumps(data), world)


def test_exact_approach_reference_accounting(house: CatalogLayout) -> None:
    references = [p.template.approach for p in house.points] + [
        s.template.approach for s in house.slots
    ]
    assert len(references) == 29 and len(set(references)) == 26
    assert sum(s.template.shares_point is not None for s in house.slots) == 3
    assert all(i.orientation is ObjectOrientation.SOUTH for i in house.instances)


def test_template_order_is_canonical(world: WorldLayout, house: CatalogLayout) -> None:
    data = resource()
    for item in data["types"]:
        item["points"].reverse()
        item["slots"].reverse()
    assert parse_catalog(json.dumps(data), world) == house
