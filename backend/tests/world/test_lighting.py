"""Synthetic lighting partition and band-side predicate acceptance cases."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Any

import pytest

from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.geometry import derive_structure
from maplegotchi.core.world.lighting import LightingZone, can_mount, derive_lighting
from maplegotchi.core.world.model import Door, DoorState, Rect, Region, RegionKind, RegionStatus
from maplegotchi.core.world.topology import derive_topology


def rooms() -> tuple[Region, ...]:
    return (
        Region("n", RegionKind.HALL, Rect(1, 3, 42, 7), RegionStatus.OPEN),
        Region("s", RegionKind.FUTURE, Rect(1, 13, 42, 12), RegionStatus.CLOSED),
    )


def doors(state: DoorState = DoorState.CLOSED) -> tuple[Door, ...]:
    return (Door("d", "n", "s", Rect(5, 10, 2, 3), state),)


def zones() -> tuple[LightingZone, ...]:
    return (LightingZone("n", Rect(0, 0, 44, 10)), LightingZone("s", Rect(0, 10, 44, 16)))


def test_partition_exact_coverage_ownership_and_determinism() -> None:
    values = rooms()
    first = derive_lighting(values, doors(), zones())
    assert len(first.owners) == 1144
    for y in range(26):
        for x in range(44):
            assert first.zone_at(Tile(x, y)) == ("n" if y < 10 else "s")
    assert first == derive_lighting(tuple(reversed(values)), doors(), tuple(reversed(zones())))
    assert hash(first) == hash(derive_lighting(values, doors(), zones()))
    with pytest.raises(FrozenInstanceError):
        first.owners = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        first.zones[0].region_id = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    "values,message",
    [
        ((), "missing"),
        ((zones()[0],), "missing"),
        ((zones()[0], zones()[0]), "duplicate"),
        ((zones()[0], LightingZone("unknown", Rect(0, 10, 44, 16))), "unknown"),
        ((LightingZone("n", Rect(0, 0, 44, 9)), zones()[1]), "has 0 zones"),
        ((LightingZone("n", Rect(0, 0, 44, 11)), zones()[1]), "has 2 zones"),
        (
            (LightingZone("n", Rect(0, 0, 44, 11)), LightingZone("s", Rect(1, 10, 43, 16))),
            "incorrect owner",
        ),
        (
            (LightingZone("s", Rect(0, 0, 44, 10)), LightingZone("n", Rect(0, 10, 44, 16))),
            "incorrect owner",
        ),
    ],
)
def test_s12_invalid_partition(values: tuple[LightingZone, ...], message: str) -> None:
    with pytest.raises(ValueError, match=f"S12: .*{message}"):
        derive_lighting(rooms(), doors(), values)


def test_equal_area_overlap_plus_gap_is_rejected() -> None:
    # Add 16 overlapping cells while removing 16 different cells: total remains 1144.
    values = (LightingZone("n", Rect(0, 0, 42, 12)), LightingZone("s", Rect(4, 10, 40, 16)))
    assert sum(zone.bounds.area for zone in values) == 1144
    with pytest.raises(ValueError, match=r"S12: .*zones"):
        derive_lighting(rooms(), doors(), values)


@pytest.mark.parametrize("bounds", [(-1, 0, 44, 10), (0, 0, 45, 10), (0, 20, 44, 7), (0, 0, 0, 10)])
def test_invalid_zone_bounds(bounds: tuple[int, int, int, int]) -> None:
    with pytest.raises(ValueError):
        LightingZone("n", Rect(*bounds))


@pytest.mark.parametrize(
    "region_id,bounds", [("", Rect(0, 0, 1, 1)), (None, Rect(0, 0, 1, 1)), ("n", None)]
)
def test_invalid_zone_value(region_id: Any, bounds: Any) -> None:
    with pytest.raises(ValueError, match="S12"):
        LightingZone(region_id, bounds)


@pytest.mark.parametrize("state", list(DoorState))
@pytest.mark.parametrize(
    "tile,plain,window",
    [
        (Tile(3, 0), True, True),
        (Tile(3, 2), True, True),
        (Tile(3, 10), True, False),
        (Tile(3, 12), True, False),
        (Tile(5, 10), False, False),
        (Tile(6, 12), False, False),
        (Tile(0, 5), False, False),
        (Tile(3, 3), False, False),
        (Tile(0, 25), False, False),
        (Tile(3, 13), False, False),
    ],
)
def test_mount_predicates(tile: Tile, plain: bool, window: bool, state: DoorState) -> None:
    values = rooms()
    structure = derive_structure(values)
    topology = derive_topology(values, doors(state))
    assert can_mount(structure, topology, tile) is plain
    assert can_mount(structure, topology, tile, window=True) is window


def test_shared_side_and_band_corner_zone_ownership() -> None:
    values = (
        Region("west", RegionKind.HALL, Rect(1, 3, 20, 22), RegionStatus.OPEN),
        Region("east", RegionKind.FUTURE, Rect(22, 3, 21, 22), RegionStatus.CLOSED),
    )
    lighting = derive_lighting(
        values,
        (),
        (
            LightingZone("west", Rect(0, 0, 22, 26)),
            LightingZone("east", Rect(22, 0, 22, 26)),
        ),
    )
    for y in range(26):
        assert lighting.zone_at(Tile(21, y)) == "west"
        assert lighting.zone_at(Tile(22, y)) == "east"


def test_partition_state_change_does_not_change_ownership() -> None:
    values = rooms()
    changed = (values[0], replace(values[1], status=RegionStatus.OPEN))
    assert derive_lighting(values, doors(), zones()) == derive_lighting(
        changed, doors(DoorState.OPEN), zones()
    )
