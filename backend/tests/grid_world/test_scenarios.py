"""A-N fixtures reject invalid states before accepting any engine execution."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.rng import RngState
from maplegotchi.core.world.catalog import Category, Owner, Permission
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.layout_validation import LayoutCandidate, validate_layout
from maplegotchi.core.world.model import RegionStatus
from maplegotchi.core.world.pathfinding import find_route
from maplegotchi.core.world.placement import (
    DisplayItem,
    DisplayPlacement,
    PlacementContext,
    PlacementReason,
    PlacementSnapshot,
    SlotKey,
    validate_active_placements,
    validate_placement,
)
from maplegotchi.core.world.recovery import Position, recover
from maplegotchi.core.world.resolution import DecisionContext, resolve
from maplegotchi.storage.errors import MigrationError
from maplegotchi.storage.migrations import latest_version, schema_version
from tests.grid_world.fixtures import scenario, snapshot
from tests.grid_world.simulation import SEED, START, simulate
from tests.persistence_support import BIRTH
from tests.rehearsal.fixtures import Scenario, synthetic_life
from tests.rehearsal.v11 import capture, load_candidate, rehearse
from tests.world.oracle import load_spec

EXPECTED = {
    "A": (),
    "B": (),
    "C": ("S10",),
    "D": (),
    "E": (),
    "F": ("S9",),
    "G": ("S8", "S10"),
    "H": ("S13",),
    "I": (),
    "J": ("S10",),
    "K": (),
    "L": (),
    "M": (),
    "N": (),
}


@pytest.mark.parametrize("name", tuple(EXPECTED))
def test_named_scenario_validity_and_repeatability(name: str) -> None:
    candidate = scenario(name)
    before = repr(candidate)
    first = validate_layout(candidate)
    assert tuple(e.code for e in first.errors) == EXPECTED[name]
    assert validate_layout(candidate) == first and candidate == scenario(name)
    assert repr(candidate) == before
    if not first.valid:
        with pytest.raises(ValueError, match="invalid_layout"):
            simulate(candidate)


def test_canonical_fixture_against_independent_oracle() -> None:
    candidate = scenario("A")
    state = snapshot(candidate)
    oracle = load_spec()
    assert (candidate.grid_width, candidate.grid_height) == (44, 26)
    assert len(candidate.regions) == 8 and len(candidate.doors) == 7
    assert sum(r.status is RegionStatus.OPEN for r in candidate.regions) == 5
    assert sum(r.status is RegionStatus.CLOSED for r in candidate.regions) == 3
    assert len(state.mask.walkable) == 431 and len(state.mask.components) == 1
    assert len(state.catalog.instances) == 28 and len(state.catalog.catalog.types) == 15
    assert len(state.catalog.points) == 17 and len(state.catalog.slots) == 12
    assert len(state.world.lighting.zones) == 8 and candidate.maple == Tile(21, 15)
    assert {
        (r.id, r.floor.x, r.floor.y, r.floor.w, r.floor.h, r.status.value)
        for r in candidate.regions
    } == {(r[0], int(r[2]), int(r[3]), int(r[4]), int(r[5]), r[7]) for r in oracle.table(1).rows}
    assert {
        (p.instance_id + "/" + p.template.id, p.template.approach.x, p.template.approach.y)
        for p in state.catalog.points
    } == {(r[0], *(int(v) for v in r[1].split(";"))) for r in oracle.table(4).rows}
    assert {
        (s.instance_id + "/" + s.template.id, s.template.approach.x, s.template.approach.y)
        for s in state.catalog.slots
    } == {(r[0], *(int(v) for v in r[1].split(";"))) for r in oracle.table(5).rows}


def test_noncritical_obstruction_detours_and_simulates() -> None:
    state = snapshot(scenario("B"))
    assert Tile(5, 6) not in state.mask.walkable
    assert Tile(14, 5) in state.mask.walkable  # Moving the lamp frees its old tile.
    assert len(state.mask.walkable) == 431 and len(state.mask.components) == 1
    route = find_route(state.mask, Tile(5, 7), Tile(5, 5)).route
    assert route is not None and route.total_steps > 2 and Tile(5, 6) not in route.tiles()
    assert simulate(scenario("B")).successful_activities == 8


@pytest.mark.parametrize("name", ["D", "E"])
def test_closed_and_hypothetically_opened_access(name: str) -> None:
    state = snapshot(scenario(name))
    found = find_route(state.mask, Tile(21, 15), Tile(6, 20))
    if name == "D":
        assert found.route is None and found.error == "no_destination"
        assert recover(state.mask, Position(6, 18)).destination == Tile(21, 15)
    else:
        assert found.route is not None and Tile(6, 18) in found.route.tiles()
        assert len(state.mask.walkable) == 502
        # The accepted initial world is reloaded unchanged after the isolated opening.
        assert len(snapshot(scenario("A")).mask.walkable) == 431
    assert all(Tile(30, 20) not in component for component in state.mask.components)


@pytest.mark.parametrize("name", ["F", "G"])
def test_missing_or_unreachable_provider_has_no_candidate(name: str) -> None:
    state = snapshot(scenario(name))
    result = resolve(Activity.SLEEP, state, Tile(21, 15), DecisionContext(RngState(f"{SEED:064x}")))
    assert result.selected is None and result.error == "no_candidate"


@pytest.mark.parametrize("source", [Position(1, 20), Position(1, 3), Position(-1, 0)])
def test_explicit_recovery_is_separate_from_invalid_layout_acceptance(source: Position) -> None:
    candidate = scenario("I")
    state = snapshot(candidate)
    result = recover(state.mask, source)
    assert result.event is not None
    assert result == recover(state.mask, source) and result.destination in state.mask.walkable
    repaired = replace(candidate, maple=result.destination)
    assert validate_layout(repaired).valid
    run = simulate(candidate, initial=source)
    assert run.recovery_count == 1 and run.successful_activities == 8
    assert run.events[0].kind == "maple_relocated"


def placement_context(candidate: LayoutCandidate) -> PlacementContext:
    state = snapshot(candidate)
    item = DisplayItem(
        "fixture.creation",
        "creation.small",
        Category.CREATION_DISPLAY,
        Owner.MAPLE,
        (Permission.MAPLE,),
        True,
        True,
    )
    return PlacementContext(
        PlacementSnapshot(state.world, state.catalog),
        (item,),
        (),
        START,
        timedelta(hours=7),
        candidate.maple,
    )


@pytest.mark.parametrize("name", ["J", "K"])
def test_placement_safety_and_connectivity(name: str) -> None:
    context = placement_context(scenario(name))
    key = SlotKey("bedside.bedroom", "top")
    result = validate_placement(context, context.items[0].id, key, Permission.MAPLE)
    if name == "J":
        assert not result.accepted and result.reason is PlacementReason.INVALID_LAYOUT
    else:
        assert result.accepted and result.route is not None
        before = context.snapshot.mask
        placed = replace(
            context, placements=(DisplayPlacement("fixture.placement", context.items[0].id, key),)
        )
        validate_active_placements(placed)
        assert placed.snapshot.mask == before and len(before.components) == 1


@pytest.mark.parametrize("kind", ["fresh", "demo", "aged", "active", "suspended", "walking"])
def test_synthetic_v10_setup_and_rehearsal_repeatability(kind: str) -> None:
    records = []
    spec = (
        Scenario(
            kind,
            point="computer_desk.chair",
            location=RoomLocation.TERMINAL,
            activity=Activity.OBSERVE_SERVER,
        )
        if kind == "walking"
        else Scenario(kind)
    )
    for _ in range(2):
        with synthetic_life(spec) as life:
            assert schema_version(life.conn) == latest_version() == 10
            source = capture(life.conn)
            result = rehearse(life, BIRTH + timedelta(days=90))
            converted = load_candidate(life)
            assert schema_version(life.conn) == 11
            assert len(converted.world.regions) == 8
            assert life.conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            records.append((source, result.validation_digest, converted.tile))
    assert records[0] == records[1]
    assert latest_version() == 10


def test_corrupt_disposable_v10_rejected_without_conversion() -> None:
    with synthetic_life() as life:
        life.conn.execute("PRAGMA application_id=0")
        before = capture(life.conn)
        with pytest.raises(MigrationError, match="application_id"):
            rehearse(life, BIRTH + timedelta(days=90))
        assert schema_version(life.conn) == 10 and capture(life.conn) == before
