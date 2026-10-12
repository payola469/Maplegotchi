"""Independent T7/S14 cases and explicit unmappable-route rejection; no live integration."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.daytime import DayPhase
from maplegotchi.core.goals import Goal, GoalSource, GoalType
from maplegotchi.core.room import ADJACENCY, POINT_BY_ID, POINTS, Facing, Pose, shortest_path
from maplegotchi.core.state import Expression, Needs, Reaction, ReactionKind, birth
from maplegotchi.core.tasks import Task, Tool
from maplegotchi.core.world import legacy_projection
from maplegotchi.core.world.catalog import (
    Capability,
    Catalog,
    ObjectInstance,
    ObjectType,
    PointPose,
    build_catalog_layout,
)
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.legacy_projection import (
    DevelopmentWorld,
    PointRef,
    Presentation,
    project,
    project_point,
)
from maplegotchi.core.world.movement import EdgeStart, Entry, Travel
from maplegotchi.core.world.pathfinding import Route, Waypoint, find_route
from maplegotchi.runtime.world_catalog import load_initial_catalog
from maplegotchi.runtime.world_layout import load_initial_house
from tests.world.oracle import Oracle

AT = datetime(2026, 10, 11, tzinfo=UTC)
# Independently transcribed T4 providers and T7 targets, not projection implementation data.
CASES: tuple[tuple[Activity, str, str], ...] = (
    (Activity.SLEEP, "bed.bedroom/sleep", "bed.side"),
    (Activity.REST, "sofa.living/seat", "sofa.seat"),
    (Activity.READ, "bookshelf.library_1/front_l", "bookshelf.front"),
    (Activity.READ, "bookshelf.library_1/front_r", "bookshelf.front"),
    (Activity.READ, "bookshelf.library_2/front_l", "bookshelf.front"),
    (Activity.READ, "bookshelf.library_2/front_r", "bookshelf.front"),
    (Activity.READ, "armchair.library/seat", "bookshelf.front"),
    (Activity.THINK, "window.bedroom/view", "window.view"),
    (Activity.THINK, "window.living/view", "window.view"),
    (Activity.THINK, "window.library/view", "window.view"),
    (Activity.THINK, "window.studio/view", "window.view"),
    (Activity.THINK, "plant.living/think", "window.view"),
    (Activity.WRITE, "desk.writing/chair", "writing_desk.chair"),
    (Activity.OBSERVE_SERVER, "desk.computer/operator", "computer_desk.chair"),
    (Activity.IDLE, "idle.hall_west/idle", "open_area.west"),
    (Activity.IDLE, "idle.hall_center/idle", "open_area.center"),
    (Activity.IDLE, "idle.hall_east/idle", "open_area.east"),
    (Activity.WALK, "idle.hall_west/idle", "open_area.west"),
    (Activity.WALK, "idle.hall_center/idle", "open_area.center"),
    (Activity.WALK, "idle.hall_east/idle", "open_area.east"),
)
ANCHORS: dict[str, tuple[int, int, RoomLocation]] = {
    "bed.side": (150, 455, RoomLocation.BED),
    "sofa.seat": (150, 560, RoomLocation.SOFA),
    "bookshelf.front": (330, 500, RoomLocation.BOOKSHELF),
    "window.view": (500, 470, RoomLocation.WINDOW),
    "writing_desk.chair": (640, 470, RoomLocation.DESK),
    "computer_desk.chair": (840, 470, RoomLocation.TERMINAL),
    "open_area.west": (400, 550, RoomLocation.RUG),
    "open_area.center": (480, 545, RoomLocation.RUG),
    "open_area.east": (580, 550, RoomLocation.RUG),
}


def anchor_xy(target: str) -> tuple[float, float]:
    x, y, _ = ANCHORS[target]
    return float(x), float(y)


def ref(text: str) -> PointRef:
    return PointRef(*text.split("/"))


@pytest.fixture(scope="module")
def context() -> DevelopmentWorld:
    world = load_initial_house()
    return DevelopmentWorld(world, load_initial_catalog(world))


def payload(activity: Activity, start: datetime = AT) -> Presentation:
    return Presentation(
        activity,
        start,
        start + timedelta(minutes=7),
        Needs(21, 32, 43, 54),
        Reaction(ReactionKind.PET_HAPPY, 2, AT, AT + timedelta(seconds=10)),
        Expression.CURIOUS,
        PointPose.SIT_READ,
        DayPhase.EVENING,
        "fixture-connected",
    )


def tile(context: DevelopmentWorld, text: str) -> Tile:
    key = ref(text)
    point = next(
        p
        for p in context.catalog.points
        if (p.instance_id, p.template.id) == (key.instance_id, key.point_id)
    )
    return Tile(point.template.approach.x, point.template.approach.y)


def travel_between(context: DevelopmentWorld, origin: str, destination: str) -> Travel:
    result = find_route(context.mask, tile(context, origin), tile(context, destination))
    assert result.route is not None
    return Travel(result.route, AT, ms_per_step=317)


@pytest.mark.parametrize("activity,source,target", CASES)
def test_t7_and_s14(
    context: DevelopmentWorld, spec_oracle: Oracle, activity: Activity, source: str, target: str
) -> None:
    before = tuple(POINTS)
    point = project_point(context, ref(source), activity)
    x, y, location = ANCHORS[target]
    assert point is POINT_BY_ID[target]
    assert (point.x, point.y, point.location) == (x, y, location)
    assert activity in point.allowed_actions
    assert isinstance(point.facing, Facing)
    # Existing constructor and validated canonical snapshot location/action contract.
    assert replace(point) == point
    native = birth(name="Fixture", born_at=AT, seed_hex="12" * 32)
    assert replace(native, activity=activity, location=location, point_id=point.id).point is point
    row = next(row for row in spec_oracle.table(7).rows if row[2] == target)
    assert row[3] == f"{x};{y}"
    assert tuple(POINTS) == before
    result = project(context, ref(source), payload(activity), AT)
    assert result.point is point and result.position == (float(x), float(y))
    assert result.presentation.activity is activity
    assert result.route is None


def test_all_capability_providers_are_covered(context: DevelopmentWorld) -> None:
    for activity, capabilities in (
        (Activity.READ, {Capability.READING_SPOT}),
        (Activity.THINK, {Capability.WINDOW_VIEW, Capability.QUIET_SPOT}),
    ):
        actual = {
            f"{p.instance_id}/{p.template.id}"
            for p in context.catalog.points
            if set(p.template.provides) & capabilities
        }
        expected = {source for action, source, _ in CASES if action is activity}
        assert actual == expected and len(actual) == 5


@pytest.mark.parametrize(
    "activity,capability,target",
    (
        (Activity.READ, Capability.READING_SPOT, "bookshelf.front"),
        (Activity.THINK, Capability.WINDOW_VIEW, "window.view"),
        (Activity.THINK, Capability.QUIET_SPOT, "window.view"),
    ),
)
@pytest.mark.parametrize("mode", ("usable", "unavailable", "blocked"))
def test_new_provider_uses_capability_not_name(
    context: DevelopmentWorld, activity: Activity, capability: Capability, target: str, mode: str
) -> None:
    marker = context.catalog.catalog.get("marker.idle_spot")
    template = replace(marker.points[0], provides=(capability,), pose=PointPose.STAND_READ)
    new_type = replace(
        marker,
        id="fixture.provider",
        capabilities=(capability,),
        points=(template,),
        states=("default", "disabled"),
    )
    host = next(p for p in context.catalog.instances if p.id == "idle.hall_center")
    new_host = replace(
        host, id="fixture.provider", type_id=new_type.id, room_id="library", origin=Tile(29, 8)
    )
    extra_types: tuple[ObjectType, ...] = (new_type,)
    extra_hosts: tuple[ObjectInstance, ...] = (new_host,)
    if mode == "unavailable":
        extra_hosts = (replace(new_host, state="disabled"),)
    elif mode == "blocked":
        blocker = replace(marker, id="fixture.blocker", blocks=("#",), points=())
        extra_types += (blocker,)
        extra_hosts += (replace(new_host, id="fixture.blocker", type_id=blocker.id),)
    catalog = Catalog((*context.catalog.catalog.types, *extra_types))
    layout = build_catalog_layout(
        catalog, (*context.catalog.instances, *extra_hosts), context.world
    )
    expanded = DevelopmentWorld(context.world, layout)
    if mode == "usable":
        assert project_point(expanded, PointRef(new_host.id, template.id), activity).id == target
    else:
        with pytest.raises(ValueError, match=r"unavailable|not walkable"):
            project_point(expanded, PointRef(new_host.id, template.id), activity)


INVALID_PAIRS = tuple(
    (activity, source)
    for activity in Activity
    for _, source, _ in CASES
    if not any(action is activity and candidate == source for action, candidate, _ in CASES)
)


@pytest.mark.parametrize("activity,source", sorted(set(INVALID_PAIRS)))
def test_invalid_activity_point_rejected(
    context: DevelopmentWorld, activity: Activity, source: str
) -> None:
    with pytest.raises(ValueError, match="unmapped"):
        project_point(context, ref(source), activity)


@pytest.mark.parametrize("source", ("unknown/point", "bed.bedroom/unknown", "system.room/console"))
def test_unknown_unmapped_and_closed_placeholder_requests(
    context: DevelopmentWorld, source: str
) -> None:
    with pytest.raises(ValueError, match="unknown source"):
        project_point(context, ref(source), Activity.OBSERVE_SERVER)


@pytest.mark.parametrize("origin_case", CASES)
@pytest.mark.parametrize("destination_case", CASES)
def test_all_provider_pairs_timing_boundaries_and_determinism(
    context: DevelopmentWorld,
    origin_case: tuple[Activity, str, str],
    destination_case: tuple[Activity, str, str],
) -> None:
    previous, origin, legacy_origin = origin_case
    activity, destination, legacy_destination = destination_case
    travel = travel_between(context, origin, destination)
    presentation = payload(activity, travel.arrives_at)
    inputs = (context, presentation, travel)
    kwargs: dict[str, Any] = {"travel": travel, "origin": ref(origin), "from_activity": previous}
    if travel.route.total_steps and legacy_origin == legacy_destination:
        with pytest.raises(ValueError, match="collapses"):
            project(context, ref(destination), presentation, AT, **kwargs)
        return
    moments = (
        AT - timedelta(microseconds=1),
        AT,
        AT + (travel.arrives_at - AT) / 2,
        travel.arrives_at,
        travel.arrives_at + timedelta(microseconds=1),
    )
    for moment in moments:
        projected = project(context, ref(destination), presentation, moment, **kwargs)
        assert projected == project(context, ref(destination), presentation, moment, **kwargs)
        assert projected.presentation is presentation
        assert (context, presentation, travel) == inputs
        assert projected.point is POINT_BY_ID[legacy_destination]
        if travel.route.total_steps == 0:
            assert projected.route is None and travel.departed_at == travel.arrives_at
            assert projected.position == anchor_xy(legacy_destination)
            continue
        route = projected.route
        assert route is not None
        assert route.departed_at == travel.departed_at
        assert route.arrives_at == travel.arrives_at == presentation.started_at
        assert route.from_activity is previous
        assert (
            tuple(p.node for p in route.path) == shortest_path(legacy_origin, legacy_destination)[0]
        )
        for a, b in zip(route.path, route.path[1:], strict=False):
            assert a.node is not None
            assert b.distance - a.distance == next(
                n for node, n in ADJACENCY[a.node] if node == b.node
            )
        assert projected.position == route.position_at(moment)
        if moment <= AT:
            assert projected.position == anchor_xy(legacy_origin)
        elif moment >= travel.arrives_at:
            assert projected.position == anchor_xy(legacy_destination)
        else:
            assert route.progress_at(moment) == pytest.approx(route.length / 2)


@pytest.mark.parametrize(
    "field",
    ("activity", "needs", "reaction", "expression", "pose", "day_phase", "status", "goal", "task"),
)
def test_passthrough_and_immutable(context: DevelopmentWorld, field: str) -> None:
    presentation = payload(Activity.READ)
    output = project(context, ref("armchair.library/seat"), presentation, AT)
    assert getattr(output.presentation, field) is getattr(presentation, field)
    assert output.presentation.until - output.presentation.started_at == timedelta(minutes=7)
    assert output.presentation.pose is PointPose.SIT_READ  # no anchor-pose substitution
    assert {item.name for item in fields(output)} == {
        "presentation",
        "point",
        "route",
        "position",
        "facing",
    }  # no events or rewritten decisions
    for value, attr in (
        (presentation, "status"),
        (output, "position"),
        (context, "world"),
        (ref("idle.hall_center/idle"), "point_id"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(value, attr, None)


@pytest.mark.parametrize(
    "field,value",
    (
        ("activity", "read"),
        ("needs", None),
        ("reaction", "pet_happy"),
        ("expression", "happy"),
        ("pose", "unknown"),
        ("day_phase", "night"),
        ("status", []),
        ("goal", []),
        ("task", []),
        ("until", AT - timedelta(seconds=1)),
        ("started_at", AT.replace(tzinfo=None)),
    ),
)
def test_invalid_presentation(field: str, value: object) -> None:
    with pytest.raises((ValueError, TypeError)):
        replace(payload(Activity.IDLE), **{field: cast(Any, value)})


@pytest.mark.parametrize(
    "problem",
    (
        "missing_origin",
        "missing_activity",
        "wrong_destination",
        "wrong_origin",
        "wrong_start",
        "forbidden_path",
        "mid_edge",
        "origin_without_travel",
        "future_stationary",
        "bad_time",
        "bad_travel",
        "bad_presentation",
    ),
)
def test_invalid_travel_or_inputs(context: DevelopmentWorld, problem: str) -> None:
    origin, destination = "idle.hall_center/idle", "desk.writing/chair"
    travel = travel_between(context, origin, destination)
    presentation = payload(Activity.WRITE, travel.arrives_at)
    kwargs: dict[str, Any] = {
        "travel": travel,
        "origin": ref(origin),
        "from_activity": Activity.IDLE,
    }
    now = AT
    if problem == "missing_origin":
        kwargs.pop("origin")
    elif problem == "missing_activity":
        kwargs.pop("from_activity")
    elif problem == "wrong_destination":
        destination = "desk.computer/operator"
        presentation = payload(Activity.OBSERVE_SERVER, travel.arrives_at)
    elif problem == "wrong_origin":
        kwargs["origin"] = ref("idle.hall_west/idle")
    elif problem == "wrong_start":
        presentation = replace(presentation, started_at=AT)
    elif problem == "forbidden_path":
        # Orthogonal compressed path with valid endpoints but through wall/blocked cells.
        route = Route(
            (Waypoint(21, 15, 0), Waypoint(21, 0, 15), Waypoint(34, 0, 28), Waypoint(34, 5, 33))
        )
        kwargs["travel"] = Travel(route, AT)
        presentation = payload(Activity.WRITE, kwargs["travel"].arrives_at)
    elif problem == "mid_edge":
        start = EdgeStart(Tile(20, 15), Tile(21, 15), 1000, travel.step_us)
        kwargs["travel"] = replace(travel, entry=Entry(start, Tile(21, 15)))
        presentation = payload(Activity.WRITE, kwargs["travel"].arrives_at)
    elif problem == "origin_without_travel":
        kwargs["travel"] = None
    elif problem == "future_stationary":
        kwargs = {}
    elif problem == "bad_time":
        now = AT.replace(tzinfo=None)
    elif problem == "bad_travel":
        kwargs["travel"] = "not travel"
    elif problem == "bad_presentation":
        presentation = cast(Presentation, "not presentation")
    with pytest.raises((ValueError, TypeError)):
        project(context, ref(destination), presentation, now, **kwargs)


@pytest.mark.parametrize(
    "problem",
    (
        "catalog_points",
        "catalog_blocks",
        "world_owners",
        "closed_host",
        "mutable_regions",
        "bad_context",
        "unknown_capability",
    ),
)
def test_forged_context_rejected(context: DevelopmentWorld, problem: str) -> None:
    world, layout = context.world, context.catalog
    with pytest.raises((ValueError, TypeError)):
        if problem == "catalog_points":
            layout = replace(layout, points=layout.points[:-1])
        elif problem == "catalog_blocks":
            layout = replace(layout, blocking_tiles=())
        elif problem == "world_owners":
            world = replace(world, lighting=replace(world.lighting, owners=()))
        elif problem == "closed_host":
            host = layout.instances[0]
            instances = tuple(
                replace(p, room_id="system_room") if p is host else p for p in layout.instances
            )
            layout = replace(layout, instances=instances)
        elif problem == "mutable_regions":
            world = replace(world, regions=cast(Any, list(world.regions)))
        elif problem == "bad_context":
            world = cast(Any, None)
        elif problem == "unknown_capability":
            marker = layout.catalog.get("marker.idle_spot")
            replace(marker, capabilities=cast(Any, ("invented",)))
        DevelopmentWorld(world, layout)


def test_production_source_and_frontend_have_no_projection_callers() -> None:
    root = Path(__file__).resolve().parents[3]
    own = Path(legacy_projection.__file__)
    # R1A-16 composes projection only inside the isolated pure validator.
    # Neither library may gain a production caller.
    validator = own.with_name("layout_validation.py")
    for path in (root / "backend/src").rglob("*.py"):
        if path not in (own, validator):
            source = path.read_text(encoding="utf-8")
            assert "legacy_projection" not in source
            assert "layout_validation" not in source
    for path in (root / "frontend/src").rglob("*"):
        if path.suffix in (".ts", ".tsx"):
            assert "legacy_projection" not in path.read_text(encoding="utf-8")
    assert set(POINT_BY_ID) == set(ANCHORS)


def test_legacy_pose_passthrough(context: DevelopmentWorld) -> None:
    presentation = replace(payload(Activity.WRITE), pose=Pose.SIT_WRITE)
    result = project(context, ref("desk.writing/chair"), presentation, AT)
    assert result.presentation.pose is Pose.SIT_WRITE


@pytest.mark.parametrize("pose", (*Pose, *PointPose))
def test_all_pose_classes_pass_through(context: DevelopmentWorld, pose: Pose | PointPose) -> None:
    presentation = replace(payload(Activity.READ), pose=pose)
    result = project(context, ref("armchair.library/seat"), presentation, AT)
    assert result.presentation.pose is pose


def test_real_goal_task_identity_passes_through(context: DevelopmentWorld) -> None:
    goal = Goal(
        1, GoalType.LEARN, "Learn from a book", GoalSource.EXTERNAL, AT, AT + timedelta(hours=1)
    )
    task = Task(Tool.READER, "library:fixture", "Fixture title", "fixture")
    presentation = replace(payload(Activity.READ), goal=goal, task=task)
    result = project(context, ref("armchair.library/seat"), presentation, AT)
    assert result.presentation.goal is goal
    assert result.presentation.task is task


@pytest.mark.parametrize(
    "instance,point", (("", "idle"), ("idle.hall_center", ""), ("bad/instance", "idle"))
)
def test_invalid_point_reference(instance: str, point: str) -> None:
    with pytest.raises(ValueError):
        PointRef(instance, point)
