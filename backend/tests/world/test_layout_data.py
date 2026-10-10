"""Independent initial-house Oracle equality and isolated reader acceptance."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from importlib.resources import files
from typing import Any, cast

import pytest

from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.lighting import can_mount
from maplegotchi.core.world.model import DoorState, RegionStatus
from maplegotchi.runtime.world_layout import load_initial_house, parse_layout
from tests.world.oracle import Oracle, Table


def data() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files("maplegotchi.world_catalog").joinpath("initial_house.json").read_text()),
    )


def test_exact_t1_t2_oracle_equality(spec_oracle: Oracle) -> None:
    layout = load_initial_house()
    zones = {zone.region_id: zone.bounds for zone in layout.lighting.zones}
    t1 = []
    for region in layout.regions:
        rect = region.floor
        zone = zones[region.id]
        t1.append(
            tuple(
                map(
                    str,
                    (
                        region.id,
                        region.kind.value,
                        rect.x,
                        rect.y,
                        rect.w,
                        rect.h,
                        rect.area,
                        region.status.value,
                        f"x{zone.x}-{zone.x + zone.w - 1}:y{zone.y}-{zone.y + zone.h - 1}",
                    ),
                )
            )
        )
    t2 = []
    for door in layout.doors:
        rect = door.passage
        t2.append(
            tuple(
                map(
                    str,
                    (
                        door.id,
                        door.north_room,
                        door.south_room,
                        rect.x,
                        rect.x + rect.w - 1,
                        rect.y,
                        rect.y + rect.h - 1,
                        door.state.value,
                    ),
                )
            )
        )
    assert Table(
        ("id", "kind", "x", "y", "w", "h", "floor_tiles", "status", "lighting_zone"), tuple(t1)
    ) == spec_oracle.table(1)
    assert Table(
        ("id", "north_room", "south_room", "x0", "x1", "y0", "y1", "state"), tuple(t2)
    ) == spec_oracle.table(2)


def test_house_acceptance_graph_floor_counts_and_ownership() -> None:
    layout = load_initial_house()
    assert len(layout.regions) == 8 and len(layout.doors) == 7
    assert tuple(r.floor.area for r in layout.regions) == (56, 70, 70, 77, 168, 65, 70, 65)
    graph = {node.region_id: node.neighbors for node in layout.topology.graph}
    assert graph["central_hall"] == ("bedroom", "library", "living_room", "work_studio")
    assert sum(map(len, graph.values())) // 2 == 4
    for name in ("future_space", "creation_room", "system_room"):
        assert graph[name] == ()
    assert sum(r.status is RegionStatus.CLOSED for r in layout.regions) == 3
    assert sum(d.state is DoorState.CLOSED for d in layout.doors) == 3
    assert len(layout.lighting.owners) == len(layout.structure.cells) == 1144
    for passage in layout.topology.passages:
        assert len(passage.cells) == 6
        for tile in passage.cells:
            assert layout.lighting.zone_at(tile) == passage.region_id
            assert not can_mount(layout.structure, layout.topology, tile)


@pytest.mark.parametrize(
    "x,y,owner",
    [
        (9, 0, "bedroom"),
        (10, 0, "living_room"),
        (31, 9, "library"),
        (32, 9, "work_studio"),
        (0, 10, "central_hall"),
        (43, 16, "central_hall"),
        (14, 17, "future_space"),
        (15, 17, "creation_room"),
        (29, 25, "creation_room"),
        (30, 25, "system_room"),
    ],
)
def test_house_zone_boundaries(x: int, y: int, owner: str) -> None:
    assert load_initial_house().lighting.zone_at(Tile(x, y)) == owner


@pytest.mark.parametrize(
    "tile,window,expected",
    [
        (Tile(1, 0), True, True),
        (Tile(2, 11), False, True),
        (Tile(2, 11), True, False),
        (Tile(2, 18), True, False),
        (Tile(5, 11), False, False),
        (Tile(6, 18), False, False),
        (Tile(0, 4), False, False),
        (Tile(2, 25), False, False),
        (Tile(2, 3), False, False),
    ],
)
def test_house_s7_band_predicates(tile: Tile, window: bool, expected: bool) -> None:
    layout = load_initial_house()
    assert can_mount(layout.structure, layout.topology, tile, window=window) is expected


def test_reader_ignores_environment_and_freezes_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAPLE_DATA_DIR", "/must-not-be-opened")
    layout = load_initial_house()
    assert layout == parse_layout(json.dumps(data()))
    with pytest.raises(FrozenInstanceError):
        layout.regions = ()  # type: ignore[misc]
    changed = data()
    parsed = parse_layout(json.dumps(changed))
    changed["regions"][0]["floor"][0] = 99
    assert parsed == layout


@pytest.mark.parametrize(
    "target,field,value",
    [
        ("root", "grid", [43, 26]),
        ("root", "grid", [True, 26]),
        ("root", "grid", [44.0, 26]),
        ("root", "regions", []),
        ("root", "regions", {}),
        ("root", "unexpected", 1),
        ("region", "floor", [0, 3, 9, 7]),
        ("region", "floor", [1, 3, 0, 7]),
        ("region", "floor", [1, 3, 44, 7]),
        ("region", "floor", [1, 3, 8]),
        ("region", "floor", [1.0, 3, 8, 7]),
        ("region", "kind", "unknown"),
        ("region", "status", "unknown"),
        ("region", "id", ""),
        ("region", "lighting_zone", [0, 0, 9, 10]),
        ("region", "lighting_zone", [0, 0, 11, 10]),
        ("region", "lighting_zone", [-1, 0, 10, 10]),
        ("door", "state", "closed"),
        ("door", "passage", [5, 10, 1, 3]),
        ("door", "passage", [5, 9, 2, 3]),
        ("door", "north_room", "system_room"),
        ("door", "south_room", "bedroom"),
        ("door", "north_room", "missing"),
        ("door", "state", "unknown"),
    ],
)
def test_rejects_invalid_data(target: str, field: str, value: Any) -> None:
    candidate = data()
    row = (
        candidate
        if target == "root"
        else candidate["regions" if target == "region" else "doors"][0]
    )
    row[field] = value
    with pytest.raises(ValueError):
        parse_layout(json.dumps(candidate))


@pytest.mark.parametrize("target", ["regions", "doors"])
def test_duplicate_entities_rejected(target: str) -> None:
    candidate = data()
    candidate[target].append(candidate[target][0])
    with pytest.raises(ValueError, match="duplicate"):
        parse_layout(json.dumps(candidate))


def test_overlapping_passages_and_missing_connection_rejected() -> None:
    candidate = data()
    candidate["doors"][1]["passage"] = [5, 10, 2, 3]
    candidate["doors"][1]["north_room"] = "bedroom"
    with pytest.raises(ValueError, match="overlap"):
        parse_layout(json.dumps(candidate))
    candidate = data()
    candidate["doors"].pop(0)
    with pytest.raises(ValueError, match="S4"):
        parse_layout(json.dumps(candidate))


@pytest.mark.parametrize("text", ['{"grid": [44,26], "grid": [44,26]}', "[]", "{"])
def test_malformed_json_and_duplicate_fields(text: str) -> None:
    with pytest.raises(ValueError):
        parse_layout(text)
