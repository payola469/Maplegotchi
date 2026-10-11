"""R1A-07 candidate validation, independent Oracle and synthetic proposal negatives."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.rng import RngState
from maplegotchi.core.world.catalog import (
    CatalogLayout,
    Category,
    LocalPoint,
    Owner,
    Permission,
    SlotPolicyOverride,
    build_catalog_layout,
)
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.directions import CharacterDirection
from maplegotchi.core.world.model import RegionStatus
from maplegotchi.core.world.pathfinding import find_route
from maplegotchi.core.world.placement import (
    DisplayItem,
    DisplayPlacement,
    OwnerRemoval,
    PlacementContext,
    PlacementPolicy,
    PlacementReason,
    PlacementRecord,
    PlacementSnapshot,
    SlotKey,
    derive_storage,
    validate_placement,
)
from maplegotchi.core.world.resolution import (
    DecisionContext,
    ResolutionSnapshot,
    allowed_activities,
    resolve,
)
from maplegotchi.core.world.walkability import derive_walkability
from maplegotchi.runtime.world_catalog import load_initial_catalog
from maplegotchi.runtime.world_layout import load_initial_house
from tests.world.oracle import Oracle

AT = datetime(2026, 10, 11, 18, tzinfo=UTC)
SAFE = Tile(21, 15)
SLOT = SlotKey("side_table.library", "top")
ITEM = DisplayItem(
    "creation.one",
    "creation.small",
    Category.CREATION_DISPLAY,
    Owner.MAPLE,
    (Permission.MAPLE,),
    True,
    True,
    link="artifact:one",
)


@pytest.fixture(scope="module")
def context() -> PlacementContext:
    world = load_initial_house()
    snapshot = PlacementSnapshot(world, load_initial_catalog(world))
    return PlacementContext(snapshot, (ITEM,), (), AT, timedelta(hours=7), SAFE)


def check(
    context: PlacementContext,
    actor: Permission = Permission.MAPLE,
    item_id: str = ITEM.id,
    slot: SlotKey = SLOT,
) -> PlacementReason | None:
    return validate_placement(context, item_id, slot, actor).reason


def unsafe_snapshot(context: PlacementContext, catalog: CatalogLayout) -> PlacementSnapshot:
    # Deliberately bypass construction to test the public validator's distrust of derived DTOs.
    result = object.__new__(PlacementSnapshot)
    object.__setattr__(result, "world", context.snapshot.world)
    object.__setattr__(result, "catalog", catalog)
    return result


def test_canonical_slots(context: PlacementContext, spec_oracle: Oracle) -> None:
    catalog = context.snapshot.catalog
    rows = tuple(
        (
            f"{s.instance_id}/{s.template.id}",
            f"{s.template.approach.x};{s.template.approach.y}",
            s.template.facing.value,
            s.template.shares_point or "-",
            ";".join(s.template.accepts),
            str(s.template.capacity),
            str(s.template.maple_may_place).lower(),
            s.template.status.value,
        )
        for s in catalog.slots
    )
    assert sorted(rows) == sorted(spec_oracle.table(5).rows)
    references = [p.template.approach for p in catalog.points]
    references.extend(s.template.approach for s in catalog.slots)
    assert (len(catalog.slots), len(catalog.points), len(references), len(set(references))) == (
        12,
        17,
        29,
        26,
    )
    reused = [s for s in catalog.slots if s.template.shares_point is not None]
    assert len(reused) == 3
    for slot in reused:
        point = next(
            p
            for p in catalog.points
            if p.instance_id == slot.instance_id and p.template.id == slot.template.shares_point
        )
        assert (slot.template.approach, slot.template.facing) == (
            point.template.approach,
            point.template.facing,
        )
    assert all(Permission.MAPLE not in t.movable_by for t in catalog.catalog.types)
    assert derive_storage(replace(context, items=())) == ()


@pytest.mark.parametrize(
    "slot_id",
    [
        "bedside.bedroom/top",
        "side_table.living/top",
        "side_table.library/top",
        "desk.writing/desktop",
        "shelf.studio/display",
        "frame.bedroom/artwork",
        "frame.living/artwork",
        "frame.hall_west/artwork",
        "frame.hall_east/artwork",
    ],
)
def test_all_active_slots(context: PlacementContext, slot_id: str) -> None:
    slot = SlotKey(*slot_id.split("/"))
    item = replace(
        ITEM, item_class="creation.flat" if slot.slot_id == "artwork" else "creation.small"
    )
    result = validate_placement(replace(context, items=(item,)), item.id, slot, Permission.MAPLE)
    assert result.accepted and result.route is not None
    assert result.approach == result.route.destination


@pytest.mark.parametrize(
    "slot_id,item_class",
    [
        ("bookshelf.library_1/books", "library.book"),
        ("bookshelf.library_2/books", "library.book"),
        ("board.studio/cards", "project.card"),
    ],
)
@pytest.mark.parametrize("actor", list(Permission))
def test_hooks_rejected(
    context: PlacementContext, slot_id: str, item_class: str, actor: Permission
) -> None:
    assert (
        check(
            replace(context, items=(replace(ITEM, item_class=item_class),)),
            actor,
            slot=SlotKey(*slot_id.split("/")),
        )
        is PlacementReason.HOOK_ONLY
    )


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("item_class", "creation.flat", PlacementReason.CLASS_REJECTED),
        ("category", Category.FUNCTIONAL, PlacementReason.INELIGIBLE_ITEM),
        ("category", Category.STRUCTURAL, PlacementReason.INELIGIBLE_ITEM),
        ("room_representation", False, PlacementReason.INELIGIBLE_ITEM),
        ("displayable", False, PlacementReason.INELIGIBLE_ITEM),
        ("system_critical", True, PlacementReason.INELIGIBLE_ITEM),
        ("owner", Owner.PAOLO, PlacementReason.INELIGIBLE_ITEM),
        ("movable_by", (), PlacementReason.NOT_MAPLE_MOVABLE),
        ("movable_by", (Permission.OWNER,), PlacementReason.NOT_MAPLE_MOVABLE),
        ("id", "bed.bedroom", PlacementReason.INELIGIBLE_ITEM),
    ],
)
@pytest.mark.parametrize("actor", list(Permission))
def test_item_policy(
    context: PlacementContext, field: str, value: object, reason: PlacementReason, actor: Permission
) -> None:
    item = replace(ITEM, **{field: cast(Any, value)})
    expected = (
        None
        if actor is Permission.OWNER and reason is PlacementReason.NOT_MAPLE_MOVABLE
        else reason
    )
    assert check(replace(context, items=(item,)), actor, item.id) is expected


@pytest.mark.parametrize("kind", ["host", "slot", "item"])
def test_unknown(context: PlacementContext, kind: str) -> None:
    target = SlotKey(
        "missing" if kind == "host" else SLOT.host_id, "missing" if kind == "slot" else SLOT.slot_id
    )
    assert (
        check(context, item_id="missing" if kind == "item" else ITEM.id, slot=target)
        is {
            "host": PlacementReason.UNKNOWN_HOST,
            "slot": PlacementReason.UNKNOWN_SLOT,
            "item": PlacementReason.UNKNOWN_ITEM,
        }[kind]
    )


def test_owner_slot_authority(context: PlacementContext) -> None:
    layout = context.snapshot.catalog
    instances = tuple(
        replace(h, slot_policies=(SlotPolicyOverride("top", maple_may_place=False),))
        if h.id == SLOT.host_id
        else h
        for h in layout.instances
    )
    catalog = build_catalog_layout(layout.catalog, instances, context.snapshot.world)
    changed = replace(context, snapshot=PlacementSnapshot(context.snapshot.world, catalog))
    assert check(changed) is PlacementReason.MAPLE_FORBIDDEN
    assert check(changed, Permission.OWNER) is None


@pytest.mark.parametrize("active_count", [0, 1, 2])
@pytest.mark.parametrize("actor", list(Permission))
def test_capacity(context: PlacementContext, active_count: int, actor: Permission) -> None:
    others = tuple(replace(ITEM, id=f"creation.other{i}") for i in range(active_count))
    placements = tuple(
        DisplayPlacement(f"display.p{i}", item.id, SLOT) for i, item in enumerate(others)
    )
    changed = replace(context, items=(ITEM, *others), placements=placements)
    assert check(changed, actor) is (PlacementReason.CAPACITY_FULL if active_count == 2 else None)


@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("actor", list(Permission))
def test_duplicate(context: PlacementContext, active: bool, actor: Permission) -> None:
    placement = DisplayPlacement("display.one", ITEM.id, SLOT, active)
    changed = replace(context, placements=(placement,))
    assert check(changed, actor) is (PlacementReason.DUPLICATE_ACTIVE if active else None)
    assert derive_storage(changed) == (() if active else (ITEM,))


@pytest.mark.parametrize("match", ["item", "slot", "both", "neither"])
@pytest.mark.parametrize(
    "delta",
    [
        timedelta(days=7) - timedelta(microseconds=1),
        timedelta(days=7),
        timedelta(days=7, microseconds=1),
    ],
)
def test_cooldown_boundary(context: PlacementContext, match: str, delta: timedelta) -> None:
    removal = OwnerRemoval(
        ITEM.id if match in ("item", "both") else "creation.other",
        SLOT if match in ("slot", "both") else SlotKey("other", "top"),
        AT - delta,
    )
    changed = replace(context, removals=(removal,))
    assert check(changed) is (
        PlacementReason.COOLDOWN if match != "neither" and delta < timedelta(days=7) else None
    )
    assert check(changed, Permission.OWNER) is None


@pytest.mark.parametrize("offset", [-7, 0, 7])
@pytest.mark.parametrize("count", [0, 2, 3, 4])
def test_rate_boundary(context: PlacementContext, offset: int, count: int) -> None:
    history = tuple(PlacementRecord(f"history.p{i}", Permission.MAPLE, AT) for i in range(count))
    changed = replace(context, utc_offset=timedelta(hours=offset), history=history)
    assert check(changed) is (PlacementReason.RATE_LIMIT if count >= 3 else None)
    assert check(changed, Permission.OWNER) is None


@pytest.mark.parametrize("microseconds", [-1, 0, 1])
def test_local_day_rollover(context: PlacementContext, microseconds: int) -> None:
    midnight = datetime(2026, 10, 11, 17, tzinfo=UTC)  # midnight at +07
    history = tuple(
        PlacementRecord(
            f"history.p{i}", Permission.MAPLE, midnight + timedelta(microseconds=microseconds)
        )
        for i in range(3)
    )
    assert check(replace(context, history=history)) is (
        None if microseconds < 0 else PlacementReason.RATE_LIMIT
    )


def test_owner_history_and_explicit_policy(context: PlacementContext) -> None:
    records = tuple(PlacementRecord(f"owner.p{i}", Permission.OWNER, AT) for i in range(10))
    assert check(replace(context, history=records)) is None
    assert check(replace(context, policy=PlacementPolicy(0))) is PlacementReason.RATE_LIMIT
    removal = OwnerRemoval(ITEM.id, SLOT, AT)
    assert (
        check(replace(context, removals=(removal,), policy=PlacementPolicy(3, timedelta(0))))
        is None
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", "bad/id"),
        ("item_class", ""),
        ("category", "decorative"),
        ("owner", "maple"),
        ("movable_by", [Permission.MAPLE]),
        ("movable_by", ("maple",)),
        ("movable_by", (Permission.MAPLE, Permission.MAPLE)),
        ("displayable", 1),
        ("room_representation", None),
        ("system_critical", "false"),
        ("link", " "),
    ],
)
def test_item_contract(field: str, value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        replace(ITEM, **{field: cast(Any, value)})


@pytest.mark.parametrize(
    "kind",
    [
        "future_removal",
        "future_record",
        "duplicate_history",
        "duplicate_item",
        "duplicate_relationship",
        "mutable_items",
        "naive_now",
        "offset",
        "bool_limit",
        "negative_limit",
        "negative_cooldown",
        "bad_slot",
        "bad_active",
    ],
)
def test_invalid_context(context: PlacementContext, kind: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        if kind == "future_removal":
            replace(context, removals=(OwnerRemoval(ITEM.id, SLOT, AT + timedelta(seconds=1)),))
        elif kind == "future_record":
            replace(
                context,
                history=(
                    PlacementRecord("record.one", Permission.MAPLE, AT + timedelta(seconds=1)),
                ),
            )
        elif kind == "duplicate_history":
            record = PlacementRecord("record.one", Permission.MAPLE, AT)
            replace(context, history=(record, record))
        elif kind == "duplicate_item":
            replace(context, items=(ITEM, ITEM))
        elif kind == "duplicate_relationship":
            placement = DisplayPlacement("display.one", ITEM.id, SLOT)
            replace(context, placements=(placement, placement))
        elif kind == "mutable_items":
            replace(context, items=cast(Any, [ITEM]))
        elif kind == "naive_now":
            replace(context, now=AT.replace(tzinfo=None))
        elif kind == "offset":
            replace(context, utc_offset=timedelta(days=1))
        elif kind == "bool_limit":
            PlacementPolicy(True)
        elif kind == "negative_limit":
            PlacementPolicy(-1)
        elif kind == "negative_cooldown":
            PlacementPolicy(3, timedelta(seconds=-1))
        elif kind == "bad_slot":
            SlotKey("bad/host", "top")
        else:
            DisplayPlacement("display.one", ITEM.id, SLOT, cast(Any, 1))


@pytest.mark.parametrize("problem", ["missing", "duplicate", "capacity", "hook", "class"])
def test_corrupt_active_relationships(context: PlacementContext, problem: str) -> None:
    items = tuple(replace(ITEM, id=f"creation.p{i}") for i in range(3))
    placements: tuple[DisplayPlacement, ...] = (
        DisplayPlacement("display.one", "missing" if problem == "missing" else items[0].id, SLOT),
    )
    if problem == "duplicate":
        placements += (DisplayPlacement("display.two", items[0].id, SLOT),)
    elif problem == "capacity":
        placements = tuple(
            DisplayPlacement(f"display.p{i}", item.id, SLOT) for i, item in enumerate(items)
        )
    elif problem == "hook":
        placements = (replace(placements[0], slot=SlotKey("bookshelf.library_1", "books")),)
    elif problem == "class":
        items = (replace(items[0], item_class="creation.flat"), *items[1:])
    changed = replace(context, items=(ITEM, *items), placements=placements)
    assert check(changed) is PlacementReason.INVALID_PLACEMENTS
    with pytest.raises(ValueError):
        derive_storage(changed)


@pytest.mark.parametrize(
    "problem",
    [
        "undeclared",
        "cross_host",
        "wrong_tile",
        "wrong_facing",
        "blocked",
        "out_of_grid",
        "non_floor",
        "maple_blocked",
    ],
)
def test_structure_revalidated(context: PlacementContext, problem: str) -> None:
    catalog = context.snapshot.catalog
    target = next(s for s in catalog.slots if s.instance_id == SLOT.host_id)
    if problem == "maple_blocked":
        assert check(replace(context, maple=Tile(1, 4))) is PlacementReason.INVALID_LAYOUT
        return
    if problem in ("undeclared", "cross_host"):
        target = next(s for s in catalog.slots if s.instance_id == "desk.writing")
        template = replace(
            target.template, shares_point=None if problem == "undeclared" else "sleep"
        )
    else:
        template = replace(
            target.template,
            **cast(
                Any,
                {
                    "wrong_tile": {"approach": LocalPoint(24, 8)},
                    "wrong_facing": {"facing": CharacterDirection.DOWN},
                    "blocked": {"approach": LocalPoint(23, 7)},
                    "out_of_grid": {"approach": LocalPoint(-1, 8)},
                    "non_floor": {"approach": LocalPoint(23, 0)},
                }[problem],
            ),
        )
    slots = tuple(replace(s, template=template) if s is target else s for s in catalog.slots)
    changed = replace(context, snapshot=unsafe_snapshot(context, replace(catalog, slots=slots)))
    assert check(changed) is PlacementReason.INVALID_LAYOUT


def test_closed_target(context: PlacementContext) -> None:
    snapshot = unsafe_snapshot(context, context.snapshot.catalog)
    world = snapshot.world
    regions = tuple(
        replace(r, status=RegionStatus.CLOSED) if r.id == "library" else r for r in world.regions
    )
    object.__setattr__(snapshot, "world", replace(world, regions=regions))
    assert check(replace(context, snapshot=snapshot)) is PlacementReason.CLOSED_REGION


@pytest.mark.parametrize(
    "category,owner,movable,representation,displayable,critical,eligible",
    [
        (Category.CREATION_DISPLAY, Owner.MAPLE, (), True, True, False, True),
        (Category.CREATION_DISPLAY, Owner.PAOLO, (Permission.OWNER,), True, True, False, False),
        (Category.DECORATIVE, Owner.PAOLO, (Permission.OWNER,), True, True, False, True),
        (Category.DECORATIVE, Owner.MAPLE, (Permission.MAPLE,), True, True, False, True),
        (Category.DECORATIVE, Owner.MAPLE, (), True, True, False, False),
        (Category.STRUCTURAL, Owner.PAOLO, (Permission.OWNER,), True, True, False, False),
        (Category.FUNCTIONAL, Owner.PAOLO, (Permission.OWNER,), True, True, False, False),
        (Category.CREATION_DISPLAY, Owner.MAPLE, (Permission.MAPLE,), False, True, False, False),
        (Category.CREATION_DISPLAY, Owner.MAPLE, (Permission.MAPLE,), True, False, False, False),
        (Category.DECORATIVE, Owner.MAPLE, (Permission.MAPLE,), True, True, True, False),
    ],
)
def test_storage_eligibility(
    context: PlacementContext,
    category: Category,
    owner: Owner,
    movable: tuple[Permission, ...],
    representation: bool,
    displayable: bool,
    critical: bool,
    eligible: bool,
) -> None:
    item = replace(
        ITEM,
        category=category,
        owner=owner,
        movable_by=movable,
        room_representation=representation,
        displayable=displayable,
        system_critical=critical,
    )
    assert derive_storage(replace(context, items=(item,))) == ((item,) if eligible else ())


def test_ordering_and_no_mutation(context: PlacementContext) -> None:
    other = replace(ITEM, id="creation.another")
    placements = (
        DisplayPlacement("display.z", "retired", SlotKey("removed", "top"), False),
        DisplayPlacement("display.a", ITEM.id, SLOT),
    )
    records = (
        PlacementRecord("record.z", Permission.OWNER, AT),
        PlacementRecord("record.a", Permission.OWNER, AT),
    )
    a = replace(context, items=(ITEM, other), placements=placements, history=records)
    b = replace(context, items=(other, ITEM), placements=placements[::-1], history=records[::-1])
    assert a == b and derive_storage(a) == derive_storage(b) == (other,)
    assert validate_placement(a, other.id, SLOT, Permission.MAPLE) == validate_placement(
        b, other.id, SLOT, Permission.MAPLE
    )
    assert context.items == (ITEM,) and context.placements == ()
    for value, attribute in (
        (ITEM, "id"),
        (SLOT, "host_id"),
        (a, "now"),
        (placements[0], "active"),
        (a.policy, "per_day"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(value, attribute, None)


@pytest.mark.parametrize("activity", list(Activity))
def test_placement_has_no_geometry_or_resolver_effect(
    context: PlacementContext, activity: Activity
) -> None:
    result = validate_placement(context, ITEM.id, SLOT, Permission.MAPLE)
    assert result.accepted
    after = replace(context, placements=(DisplayPlacement("display.one", ITEM.id, SLOT),))
    before_mask = derive_walkability(context.snapshot.world, context.snapshot.catalog)
    after_mask = derive_walkability(after.snapshot.world, after.snapshot.catalog)
    assert before_mask == after_mask and len(after_mask.walkable) == 431
    assert len(after_mask.components) == 1 and len(after_mask.required) == 26
    assert after.snapshot.world.topology == context.snapshot.world.topology
    assert find_route(before_mask, SAFE, Tile(41, 4)) == find_route(after_mask, SAFE, Tile(41, 4))
    decision = DecisionContext(RngState("12" * 32))
    assert resolve(
        activity,
        ResolutionSnapshot(context.snapshot.world, context.snapshot.catalog),
        SAFE,
        decision,
    ) == resolve(
        activity, ResolutionSnapshot(after.snapshot.world, after.snapshot.catalog), SAFE, decision
    )
    assert allowed_activities(
        ResolutionSnapshot(after.snapshot.world, after.snapshot.catalog), SAFE, decision
    ) == tuple(Activity)
    assert derive_storage(after) == () and derive_storage(context) == (ITEM,)


@pytest.mark.parametrize("host", ["desk.writing", "bookshelf.library_1", "bookshelf.library_2"])
@pytest.mark.parametrize("problem", ["missing_point", "wrong_tile", "wrong_facing", "undeclared"])
def test_declared_reuse_failures(context: PlacementContext, host: str, problem: str) -> None:
    catalog = context.snapshot.catalog
    target = next(s for s in catalog.slots if s.instance_id == host)
    template = target.template
    if problem == "missing_point":
        template = replace(template, shares_point="point.other_host")
    elif problem == "wrong_tile":
        template = replace(
            template, approach=LocalPoint(template.approach.x + 1, template.approach.y)
        )
    elif problem == "wrong_facing":
        template = replace(template, facing=CharacterDirection.DOWN)
    else:
        template = replace(template, shares_point=None)
    slots = tuple(replace(s, template=template) if s is target else s for s in catalog.slots)
    changed = replace(context, snapshot=unsafe_snapshot(context, replace(catalog, slots=slots)))
    assert check(changed) is PlacementReason.INVALID_LAYOUT


def test_owner_cannot_bypass_unsafe_layout(context: PlacementContext) -> None:
    assert (
        check(replace(context, maple=Tile(1, 4)), Permission.OWNER)
        is PlacementReason.INVALID_LAYOUT
    )


def test_public_result_is_frozen(context: PlacementContext) -> None:
    result = validate_placement(context, ITEM.id, SLOT, Permission.MAPLE)
    with pytest.raises(FrozenInstanceError):
        cast(Any, result).reason = PlacementReason.UNKNOWN_ITEM
    assert result == validate_placement(context, ITEM.id, SLOT, Permission.MAPLE)
