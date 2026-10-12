"""Independent T6 capability acceptance and explicit synthetic/invalid snapshot cases."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.memory import Memory, MemoryKind, MemoryStatus, Tier
from maplegotchi.core.rng import RngState, RngStream
from maplegotchi.core.world import resolution
from maplegotchi.core.world.catalog import (
    Capability,
    Catalog,
    CatalogLayout,
    Footprint,
    LocalPoint,
    ObjectInstance,
    build_catalog_layout,
)
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.layout import build_layout
from maplegotchi.core.world.model import DoorState, RegionKind, RegionStatus
from maplegotchi.core.world.pathfinding import find_route
from maplegotchi.core.world.resolution import (
    REQUIREMENTS,
    REQUIREMENTS_VERSION,
    AcceptedPointPreference,
    ActivityRequirement,
    DecisionContext,
    InstanceUse,
    PointKey,
    PointUse,
    ResolutionSnapshot,
    Score,
    allowed_activities,
    candidates_for,
    requirement_for,
    resolve,
    validate_activity_coverage,
)
from maplegotchi.runtime.world_catalog import load_initial_catalog
from maplegotchi.runtime.world_layout import load_initial_house
from tests.world.oracle import Oracle

AT = datetime(2026, 10, 11, tzinfo=UTC)
CONTEXT = DecisionContext(RngState("12" * 32))
SAFE = Tile(21, 15)
EXTRA_TILE = Tile(29, 8)


@pytest.fixture(scope="module")
def snapshot() -> ResolutionSnapshot:
    world = load_initial_house()
    return ResolutionSnapshot(world, load_initial_catalog(world))


def key(text: str) -> PointKey:
    return PointKey(*text.split("/"))


def identity(point: PointKey) -> str:
    return f"{point.instance_id}/{point.point_id}"


def memory(status: MemoryStatus = MemoryStatus.ACCEPTED, tier: Tier = Tier.LONG_TERM) -> Memory:
    return Memory(MemoryKind.PREFERENCE, tier, status, "Explicit test preference", AT, AT)


def preference(point: str) -> AcceptedPointPreference:
    return AcceptedPointPreference(key(point), memory())


def rebuild(snapshot: ResolutionSnapshot, instances: tuple[ObjectInstance, ...]) -> CatalogLayout:
    return build_catalog_layout(snapshot.catalog.catalog, instances, snapshot.world)


def extra(
    snapshot: ResolutionSnapshot,
    capability: Capability = Capability.READING_SPOT,
    room: str = "library",
    tile: Tile = EXTRA_TILE,
) -> ResolutionSnapshot:
    """New synthetic type/instance, no new production furniture or approved fixture edit."""
    marker = snapshot.catalog.catalog.get("marker.idle_spot")
    point = replace(marker.points[0], provides=(capability,), capacity=2)
    item = replace(marker, id="fixture.flexible", capabilities=(capability,), points=(point,))
    catalog = Catalog((*snapshot.catalog.catalog.types, item))
    host = next(i for i in snapshot.catalog.instances if i.id == "idle.hall_center")
    instance = replace(host, id="fixture.extra", type_id=item.id, room_id=room, origin=tile)
    layout = build_catalog_layout(catalog, (*snapshot.catalog.instances, instance), snapshot.world)
    return ResolutionSnapshot(snapshot.world, layout)


@pytest.mark.parametrize("activity", tuple(Activity))
@pytest.mark.parametrize(
    "position", [SAFE, Tile(3, 4), Tile(12, 6), Tile(21, 4), Tile(18, 3), Tile(34, 5), Tile(39, 5)]
)
def test_t6_candidates_real_paths_and_metadata(
    snapshot: ResolutionSnapshot, spec_oracle: Oracle, activity: Activity, position: Tile
) -> None:
    row = next(row for row in spec_oracle.table(6).rows if activity.value in row[0].split("|"))
    result = resolve(activity, snapshot, position, CONTEXT)
    assert {identity(c.key) for c in result.candidates} == set(row[2].split(";"))
    assert result.selected is not None and result.error is None
    expected_groups = tuple(tuple(group.split("+")) for group in row[1].split("|"))
    assert requirement_for(activity).alternatives == expected_groups
    for c in result.candidates:
        assert c.route == find_route(snapshot.mask, position, c.approach).route
        assert c.score.path_steps == c.route.total_steps
        assert set(c.route.tiles()) <= set(snapshot.mask.walkable)
        approved = next(r for r in spec_oracle.table(4).rows if r[0] == identity(c.key))
        assert f"{c.approach.tx};{c.approach.ty}" == approved[1]
        assert c.point.template.facing == approved[2]
        occupy = c.point.template.occupy
        assert (f"{occupy.x};{occupy.y}" if occupy else "null") == approved[3]
        assert c.point.template.pose == approved[4]
        assert c.point.template.occupy_direction == approved[5]
        assert c.score.total == 1000 * c.score.room_tier + c.route.total_steps
    assert result.candidates == tuple(
        sorted(result.candidates, key=lambda c: (c.score.total, c.key))
    )
    if activity is Activity.THINK:
        assert result.selected.key.instance_id in ("window.living", "plant.living")
    if activity is Activity.READ:
        assert result.selected.score.room_tier == 0
    if activity is Activity.OBSERVE_SERVER:
        assert result.selected.key == key("desk.computer/operator")
        assert result.selected.score.room_tier == 1


def test_initial_allowed_s9_and_narrowings(snapshot: ResolutionSnapshot) -> None:
    assert REQUIREMENTS_VERSION == 1 and tuple(r.activity for r in REQUIREMENTS) == tuple(Activity)
    assert allowed_activities(snapshot, SAFE, CONTEXT) == tuple(Activity)
    validate_activity_coverage(snapshot)
    assert requirement_for(Activity.REST).alternatives == ((Capability.SEAT_SOFT,),)
    assert requirement_for(Activity.WRITE).alternatives == ((Capability.WRITING_SURFACE,),)
    catalog = snapshot.catalog.catalog
    assert catalog.get("furniture.bed_single").capabilities == (Capability.SLEEP_SPOT,)
    assert Capability.SEAT_SOFT not in catalog.get("furniture.armchair").capabilities
    writing = catalog.get("furniture.writing_desk")
    computer = catalog.get("furniture.computer_desk")
    assert not set(writing.capabilities) & set(computer.capabilities)
    assert writing.capabilities == (Capability.WRITING_SURFACE,)
    assert computer.capabilities == (Capability.COMPUTER,)


@pytest.mark.parametrize(
    "capability,activity,room,tile",
    [
        (Capability.READING_SPOT, Activity.READ, "library", Tile(29, 8)),
        (Capability.READING_SPOT, Activity.READ, "living_room", Tile(16, 8)),
        (Capability.WRITING_SURFACE, Activity.WRITE, "work_studio", Tile(36, 8)),
        (Capability.SEAT_SOFT, Activity.REST, "living_room", Tile(16, 8)),
        (Capability.SLEEP_SPOT, Activity.SLEEP, "bedroom", Tile(8, 8)),
        (Capability.QUIET_SPOT, Activity.THINK, "bedroom", Tile(8, 8)),
        (Capability.COMPUTER, Activity.OBSERVE_SERVER, "work_studio", Tile(36, 8)),
    ],
)
def test_new_provider_discovered_without_type_mapping(
    snapshot: ResolutionSnapshot, capability: Capability, activity: Activity, room: str, tile: Tile
) -> None:
    changed = extra(snapshot, capability, room, tile)
    assert key("fixture.extra/idle") in {
        c.key for c in candidates_for(activity, changed, SAFE, CONTEXT)
    }
    validate_activity_coverage(changed)


@pytest.mark.parametrize(
    "room,tile,activity,capability",
    [
        ("bedroom", Tile(8, 8), Activity.READ, Capability.READING_SPOT),
        ("library", Tile(29, 8), Activity.REST, Capability.SEAT_SOFT),
        ("living_room", Tile(16, 8), Activity.WRITE, Capability.WRITING_SURFACE),
        ("library", Tile(29, 8), Activity.OBSERVE_SERVER, Capability.COMPUTER),
    ],
)
def test_unsupported_destination_rooms_excluded(
    snapshot: ResolutionSnapshot, room: str, tile: Tile, activity: Activity, capability: Capability
) -> None:
    changed = extra(snapshot, capability, room, tile)
    assert key("fixture.extra/idle") not in {
        c.key for c in candidates_for(activity, changed, SAFE, CONTEXT)
    }


def test_removal_and_final_provider_s9(snapshot: ResolutionSnapshot) -> None:
    one_less = tuple(i for i in snapshot.catalog.instances if i.id != "bookshelf.library_1")
    changed = ResolutionSnapshot(snapshot.world, rebuild(snapshot, one_less))
    assert len(candidates_for(Activity.READ, changed, SAFE, CONTEXT)) == 3
    validate_activity_coverage(changed)
    no_sofa = tuple(i for i in snapshot.catalog.instances if i.id != "sofa.living")
    changed = ResolutionSnapshot(snapshot.world, rebuild(snapshot, no_sofa))
    assert resolve(Activity.REST, changed, SAFE, CONTEXT).error == "no_candidate"
    assert Activity.REST not in allowed_activities(changed, SAFE, CONTEXT)
    with pytest.raises(ValueError, match=r"S9.*rest"):
        validate_activity_coverage(changed)


@pytest.mark.parametrize("mode", ["instance", "unavailable", "full"])
def test_temporarily_unusable_and_capacity(snapshot: ResolutionSnapshot, mode: str) -> None:
    changed = replace(
        snapshot,
        instances=(InstanceUse("sofa.living", False),) if mode == "instance" else (),
        points=(
            PointUse(
                key("sofa.living/seat"),
                available=mode != "unavailable",
                occupied=int(mode == "full"),
            ),
        )
        if mode != "instance"
        else (),
    )
    result = resolve(Activity.REST, changed, SAFE, CONTEXT)
    assert result.error == "no_candidate" and result.selected is None
    assert result.candidates == () and result.tied == () and result.decision_draws == 0
    with pytest.raises(ValueError, match=r"S9.*rest"):
        validate_activity_coverage(changed)


def test_partial_capacity_and_optional_candidate(snapshot: ResolutionSnapshot) -> None:
    changed = extra(snapshot)
    changed = replace(
        changed,
        points=(
            PointUse(key("fixture.extra/idle"), occupied=1),
            PointUse(key("window.library/view"), False),
        ),
    )
    assert key("fixture.extra/idle") in {
        c.key for c in candidates_for(Activity.READ, changed, SAFE, CONTEXT)
    }
    assert len(candidates_for(Activity.THINK, changed, SAFE, CONTEXT)) == 4
    validate_activity_coverage(changed)


def test_declared_nondefault_state_requires_explicit_usability(
    snapshot: ResolutionSnapshot,
) -> None:
    types = tuple(
        replace(t, states=("default", "disabled")) if t.id == "furniture.sofa" else t
        for t in snapshot.catalog.catalog.types
    )
    catalog = Catalog(types)
    instances = tuple(
        replace(i, state="disabled") if i.id == "sofa.living" else i
        for i in snapshot.catalog.instances
    )
    layout = build_catalog_layout(catalog, instances, snapshot.world)
    changed = ResolutionSnapshot(snapshot.world, layout)
    assert resolve(Activity.REST, changed, SAFE, CONTEXT).error == "no_candidate"
    assert (
        resolve(
            Activity.REST,
            replace(changed, instances=(InstanceUse("sofa.living", True),)),
            SAFE,
            CONTEXT,
        ).selected
        is not None
    )


@pytest.mark.parametrize("close_region", [False, True])
def test_closed_access_never_candidates(snapshot: ResolutionSnapshot, close_region: bool) -> None:
    doors = tuple(
        replace(d, state=DoorState.CLOSED) if d.north_room == "library" else d
        for d in snapshot.world.doors
    )
    regions = tuple(
        replace(r, status=RegionStatus.CLOSED) if close_region and r.id == "library" else r
        for r in snapshot.world.regions
    )
    if not close_region:
        # S4 already rejects a closed sole door while its endpoint remains open.
        with pytest.raises(ValueError, match="S4"):
            build_layout(regions, doors, snapshot.world.lighting.zones)
        return
    world = build_layout(regions, doors, snapshot.world.lighting.zones)
    # Transient invalid saved-layout snapshot: closing a furnished room is not placement acceptance.
    changed = ResolutionSnapshot(world, snapshot.catalog)
    assert resolve(Activity.READ, changed, SAFE, CONTEXT).error == "no_candidate"
    for activity in Activity:
        for c in candidates_for(activity, changed, SAFE, CONTEXT):
            assert c.approach.ty < 20
            assert all(
                not r.floor.contains(tile)
                for r in world.regions
                if r.status is RegionStatus.CLOSED
                for tile in c.route.tiles()
            )
    with pytest.raises(ValueError):
        validate_activity_coverage(changed)


def test_opened_system_room_tier(snapshot: ResolutionSnapshot) -> None:
    regions = tuple(
        replace(r, status=RegionStatus.OPEN) if r.kind is RegionKind.SYSTEM else r
        for r in snapshot.world.regions
    )
    doors = tuple(
        replace(d, state=DoorState.OPEN) if d.south_room == "system_room" else d
        for d in snapshot.world.doors
    )
    world = build_layout(regions, doors, snapshot.world.lighting.zones)
    changed = extra(
        ResolutionSnapshot(world, snapshot.catalog),
        Capability.SYSTEM_CONSOLE,
        "system_room",
        Tile(34, 22),
    )
    result = resolve(Activity.OBSERVE_SERVER, changed, SAFE, CONTEXT)
    assert result.selected is not None and result.selected.key == key("fixture.extra/idle")
    assert result.selected.score.room_tier == 0
    validate_activity_coverage(changed)


def test_blocked_approach_not_saved_layout(snapshot: ResolutionSnapshot) -> None:
    # Explicit invalid geometry proposal: no safe-layout validator is bypassed for acceptance.
    table = next(i for i in snapshot.catalog.instances if i.id == "bedside.bedroom")
    blocker = replace(table, id="fixture.blocker", origin=Tile(3, 4))
    layout = rebuild(snapshot, (*snapshot.catalog.instances, blocker))
    changed = ResolutionSnapshot(snapshot.world, layout)
    assert resolve(Activity.SLEEP, changed, SAFE, CONTEXT).error == "no_candidate"
    with pytest.raises(ValueError, match="S10"):
        validate_activity_coverage(changed)


@pytest.mark.parametrize("position", [Tile(0, 0), Tile(1, 3), Tile(31, 22)])
def test_invalid_current_walkable_position_never_recovers(
    snapshot: ResolutionSnapshot, position: Tile
) -> None:
    assert allowed_activities(snapshot, position, CONTEXT) == ()
    assert resolve(Activity.SLEEP, snapshot, position, CONTEXT).error == "no_candidate"


def test_sticky_preference_exact_integer_scores(snapshot: ResolutionSnapshot) -> None:
    target = "bookshelf.library_1/front_l"
    context = replace(CONTEXT, current_point=key(target), preferences=(preference(target),))
    result = resolve(Activity.READ, snapshot, SAFE, context)
    assert result.selected is not None and result.selected.key == key(target)
    assert result.selected.score.sticky == result.selected.score.preference == 1
    assert result.selected.score.total == result.selected.route.total_steps - 250
    assert all(
        c.score.sticky == c.score.preference == 0 for c in result.candidates if c.key != key(target)
    )
    assert Score(2, 13, 1, 1).total == 1763
    # Tier advantage wins even against an accepted preference/stickiness for another room.
    changed = extra(snapshot, Capability.READING_SPOT, "living_room", Tile(16, 8))
    context = replace(
        CONTEXT,
        current_point=key("fixture.extra/idle"),
        preferences=(preference("fixture.extra/idle"),),
    )
    selected = resolve(Activity.READ, changed, SAFE, context).selected
    assert selected is not None and selected.score.room_tier == 0


@pytest.mark.parametrize(
    "status,tier",
    [
        (MemoryStatus.CANDIDATE, Tier.SHORT_TERM),
        (MemoryStatus.REJECTED, Tier.LONG_TERM),
        (MemoryStatus.CANDIDATE, Tier.ARCHIVE),
    ],
)
def test_unaccepted_memory_cannot_grant_preference(status: MemoryStatus, tier: Tier) -> None:
    with pytest.raises(ValueError, match="accepted"):
        AcceptedPointPreference(key("sofa.living/seat"), memory(status, tier))


@pytest.mark.parametrize("counter", range(12))
@pytest.mark.parametrize("offset", [0, 3])
def test_ties_seeded_stream_canonical_order_no_mutation(
    snapshot: ResolutionSnapshot, counter: int, offset: int
) -> None:
    changed = replace(snapshot, points=(PointUse(key("idle.hall_center/idle"), False),))
    context = replace(
        CONTEXT, rng=replace(CONTEXT.rng, decision_counter=counter), draw_offset=offset
    )
    result = resolve(Activity.IDLE, changed, SAFE, context)
    tied = (key("idle.hall_east/idle"), key("idle.hall_west/idle"))
    assert result.tied == tied and result.decision_draws == 1
    rng = RngStream(context.rng.seed_hex, "decision", counter + 1)
    for _ in range(offset):
        rng.random()
    assert result.selected is not None and result.selected.key == tied[rng.randint(0, 1)]
    shuffled = replace(
        changed,
        catalog=replace(
            changed.catalog,
            instances=tuple(reversed(changed.catalog.instances)),
            points=tuple(reversed(changed.catalog.points)),
            slots=tuple(reversed(changed.catalog.slots)),
            blocking_tiles=tuple(reversed(changed.catalog.blocking_tiles)),
        ),
    )
    assert resolve(Activity.IDLE, shuffled, SAFE, context) == result
    assert resolve(Activity.IDLE, changed, SAFE, context) == result
    assert context.rng.decision_counter == counter and context.draw_offset == offset
    assert resolve(Activity.SLEEP, snapshot, SAFE, context).decision_draws == 0
    before = context
    allowed_activities(changed, SAFE, context)
    assert context == before


@pytest.mark.parametrize("value", [-1, True, 1.5])
def test_bad_integer_inputs(value: Any) -> None:
    with pytest.raises(ValueError):
        PointUse(key("sofa.living/seat"), occupied=value)
    with pytest.raises(ValueError):
        DecisionContext(CONTEXT.rng, draw_offset=value)


@pytest.mark.parametrize(
    "case",
    [
        "unknown_instance",
        "unknown_point",
        "excess",
        "duplicate_instance",
        "duplicate_point",
        "unknown_state",
        "fake_point",
        "fake_mask",
        "mutable",
        "fake_slots",
    ],
)
def test_malformed_snapshot_rejected(snapshot: ResolutionSnapshot, case: str) -> None:
    kwargs: dict[str, Any] = {}
    if case == "unknown_instance":
        kwargs["instances"] = (InstanceUse("missing.host", False),)
    elif case == "unknown_point":
        kwargs["points"] = (PointUse(key("sofa.living/missing")),)
    elif case == "excess":
        kwargs["points"] = (PointUse(key("sofa.living/seat"), occupied=2),)
    elif case == "duplicate_instance":
        kwargs["instances"] = (InstanceUse("sofa.living", True),) * 2
    elif case == "duplicate_point":
        kwargs["points"] = (PointUse(key("sofa.living/seat")),) * 2
    elif case == "unknown_state":
        kwargs["catalog"] = replace(
            snapshot.catalog,
            instances=tuple(
                replace(i, state="invalid") if i.id == "sofa.living" else i
                for i in snapshot.catalog.instances
            ),
        )
    elif case == "fake_point":
        point = snapshot.catalog.points[0]
        kwargs["catalog"] = replace(
            snapshot.catalog,
            points=(
                replace(point, template=replace(point.template, provides=(Capability.COMPUTER,))),
                *snapshot.catalog.points[1:],
            ),
        )
    elif case == "fake_mask":
        kwargs["catalog"] = replace(snapshot.catalog, blocking_tiles=())
    elif case == "fake_slots":
        kwargs["catalog"] = replace(snapshot.catalog, slots=())
    else:
        kwargs["points"] = []
    with pytest.raises(ValueError):
        replace(snapshot, **kwargs)


def test_bad_context_requirements_and_activity(snapshot: ResolutionSnapshot) -> None:
    with pytest.raises(ValueError):
        resolve(cast(Activity, "read"), snapshot, SAFE, CONTEXT)
    with pytest.raises(ValueError):
        resolve(Activity.READ, snapshot, cast(Tile, (21, 15)), CONTEXT)
    with pytest.raises(ValueError):
        replace(CONTEXT, preferences=(preference("sofa.living/seat"),) * 2)
    with pytest.raises(ValueError):
        ActivityRequirement(Activity.READ, ((),), (RegionKind.LIBRARY,))
    with pytest.raises(ValueError):
        Score(0, 1, 2, 0)


def test_frozen_results_and_inputs(snapshot: ResolutionSnapshot) -> None:
    result = resolve(Activity.SLEEP, snapshot, SAFE, CONTEXT)
    assert result.selected is not None
    for value, attribute, new_value in [
        (snapshot, "points", ()),
        (CONTEXT, "draw_offset", 2),
        (result, "decision_draws", 8),
        (result.selected, "route", None),
        (result.selected.score, "sticky", 1),
        (REQUIREMENTS[0], "other_tier", 3),
    ]:
        with pytest.raises(FrozenInstanceError):
            setattr(value, attribute, new_value)


def test_structural_no_object_type_dispatch_or_live_callers() -> None:
    source = Path(resolution.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not any(
        isinstance(n, ast.Attribute) and n.attr == "type_id"
        for f in tree.body
        if isinstance(f, ast.FunctionDef)
        and f.name in {"resolve", "candidates_for", "requirement_for", "allowed_activities"}
        for n in ast.walk(f)
    )
    assert not any(
        isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and any(
            prefix in n.value for prefix in ("furniture.", "desk.", "bookshelf.", "sofa.", "bed.")
        )
        for n in ast.walk(tree)
    )
    root = Path(__file__).resolve().parents[3]
    for path in (root / "backend/src").rglob("*.py"):
        if path in (
            Path(resolution.__file__),
            Path(resolution.__file__).with_name("layout_validation.py"),
        ):
            # R1A-16 composes pure validation; the projection guard separately
            # proves the aggregate validator has no production callers.
            continue
        assert "core.world.resolution" not in path.read_text(encoding="utf-8")
    for path in (root / "frontend/src").rglob("*"):
        if path.suffix in (".ts", ".tsx"):
            assert "core.world.resolution" not in path.read_text(encoding="utf-8")


def test_unreachable_approaches_rejected_without_fabricated_mask(
    snapshot: ResolutionSnapshot,
) -> None:
    # Explicit invalid saved-layout proposal, derived through real catalog transforms.
    table = snapshot.catalog.catalog.get("furniture.side_table")
    barrier = replace(
        table, id="fixture.barrier", footprint=Footprint(10, 1), blocks=("##########",), slots=()
    )
    catalog = Catalog((*snapshot.catalog.catalog.types, barrier))
    host = next(i for i in snapshot.catalog.instances if i.id == "side_table.library")
    instance = replace(
        host,
        id="fixture.barrier",
        type_id=barrier.id,
        origin=Tile(21, 5),
        slot_overrides=(),
        slot_policies=(),
    )
    layout = build_catalog_layout(catalog, (*snapshot.catalog.instances, instance), snapshot.world)
    changed = ResolutionSnapshot(snapshot.world, layout)
    assert tuple(c.key for c in candidates_for(Activity.READ, changed, SAFE, CONTEXT)) == (
        key("armchair.library/seat"),
    )
    with pytest.raises(ValueError, match="S10/K4"):
        validate_activity_coverage(changed)


@pytest.mark.parametrize(
    "activity,selected,steps,tier",
    [
        (Activity.SLEEP, "bed.bedroom/sleep", 29, 0),
        (Activity.REST, "sofa.living/seat", 18, 0),
        (Activity.READ, "armchair.library/seat", 14, 0),
        (Activity.THINK, "plant.living/think", 19, 0),
        (Activity.WRITE, "desk.writing/chair", 27, 0),
        (Activity.OBSERVE_SERVER, "desk.computer/operator", 28, 1),
        (Activity.IDLE, "idle.hall_center/idle", 0, 0),
        (Activity.WALK, "idle.hall_center/idle", 0, 0),
    ],
)
def test_canonical_safe_origin_choice(
    snapshot: ResolutionSnapshot, activity: Activity, selected: str, steps: int, tier: int
) -> None:
    result = resolve(activity, snapshot, SAFE, CONTEXT)
    assert result.selected is not None
    assert result.selected.key == key(selected)
    assert result.selected.score.path_steps == steps
    assert result.selected.score.room_tier == tier


@pytest.mark.parametrize("sticky,preferred", [(False, True), (True, False), (True, True)])
def test_each_bonus_can_change_choice(
    snapshot: ResolutionSnapshot, sticky: bool, preferred: bool
) -> None:
    target = "bookshelf.library_2/front_r"
    context = replace(
        CONTEXT,
        current_point=key(target) if sticky else None,
        preferences=(preference(target),) if preferred else (),
    )
    result = resolve(Activity.READ, snapshot, SAFE, context)
    assert result.selected is not None and result.selected.key == key(target)
    assert result.selected.score.total == result.selected.route.total_steps - 50 * int(
        sticky
    ) - 200 * int(preferred)


def test_allowed_s9_and_unique_selection_never_draw(
    snapshot: ResolutionSnapshot, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("unexpected RNG use")

    monkeypatch.setattr(resolution, "RngStream", forbidden)
    assert allowed_activities(snapshot, SAFE, CONTEXT) == tuple(Activity)
    validate_activity_coverage(snapshot)
    assert resolve(Activity.SLEEP, snapshot, SAFE, CONTEXT).decision_draws == 0


def test_runtime_input_errors_and_stale_associations(snapshot: ResolutionSnapshot) -> None:
    for value in (1, "yes", None):
        with pytest.raises(ValueError):
            InstanceUse("sofa.living", cast(bool, value))
        with pytest.raises(ValueError):
            PointUse(key("sofa.living/seat"), available=cast(bool, value))
    with pytest.raises(ValueError):
        replace(snapshot, world=replace(snapshot.world, structure=cast(Any, None)))
    with pytest.raises(ValueError):
        replace(snapshot, points=cast(Any, ("unknown",)))
    with pytest.raises(ValueError):
        replace(
            snapshot,
            catalog=replace(
                snapshot.catalog, points=(*snapshot.catalog.points, snapshot.catalog.points[0])
            ),
        )
    with pytest.raises(ValueError):
        replace(CONTEXT, preferences=cast(Any, [preference("sofa.living/seat")]))
    # Stored associations can outlive removed points. They never fabricate providers.
    context = replace(
        CONTEXT,
        current_point=key("removed.host/point"),
        preferences=(preference("removed.host/point"),),
    )
    assert candidates_for(Activity.REST, snapshot, SAFE, context) == candidates_for(
        Activity.REST, snapshot, SAFE, CONTEXT
    )


def test_any_of_all_of_requirement_groups() -> None:
    requirement = ActivityRequirement(
        Activity.READ,
        ((Capability.READING_SPOT, Capability.SEAT), (Capability.BOOK_SOURCE,)),
        (RegionKind.LIBRARY,),
    )
    assert requirement.alternatives == (
        (Capability.READING_SPOT, Capability.SEAT),
        (Capability.BOOK_SOURCE,),
    )
    for alternatives in ((), ((),), ((Capability.READING_SPOT, Capability.READING_SPOT),)):
        with pytest.raises(ValueError):
            replace(requirement, alternatives=alternatives)


def test_wrong_room_approach_is_malformed(snapshot: ResolutionSnapshot) -> None:
    point = snapshot.catalog.points[0]
    bad = replace(point, template=replace(point.template, approach=LocalPoint(21, 15)))
    with pytest.raises(ValueError, match="metadata"):
        replace(
            snapshot, catalog=replace(snapshot.catalog, points=(bad, *snapshot.catalog.points[1:]))
        )
