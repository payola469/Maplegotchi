"""Supplied schedule and logical time only; no behavior policy or application writes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta

from maplegotchi.core.activities import SPECS, Activity
from maplegotchi.core.daytime import day_phase, local_hour
from maplegotchi.core.rng import RngState
from maplegotchi.core.state import Expression, Needs
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.layout_validation import LayoutCandidate, validate_layout
from maplegotchi.core.world.legacy_projection import (
    DevelopmentWorld,
    PointRef,
    Presentation,
    project,
    project_point,
)
from maplegotchi.core.world.model import RegionStatus
from maplegotchi.core.world.movement import MS_PER_STEP, EdgeStart, Travel
from maplegotchi.core.world.pathfinding import distance
from maplegotchi.core.world.recovery import Position, recover
from maplegotchi.core.world.resolution import DecisionContext, PointKey, requirement_for, resolve
from tests.grid_world.fixtures import snapshot

VERSION = "r1a17-grid-v1"
SEED = 146
START = datetime(2026, 10, 12, tzinfo=UTC)
SCHEDULE = (
    Activity.SLEEP,
    Activity.OBSERVE_SERVER,
    Activity.REST,
    Activity.WRITE,
    Activity.READ,
    Activity.THINK,
    Activity.WALK,
    Activity.IDLE,
)
LONG_CYCLES = 270  # 270 * 160 minimum-activity minutes = 30 days, plus real walking.


@dataclass(frozen=True, slots=True)
class Event:
    kind: str
    at_ms: int
    activity: str
    tile: tuple[int, int]
    target: tuple[str, str]
    steps: int = 0
    turns: int = 0
    detail: str = ""


@dataclass(frozen=True, slots=True)
class Report:
    version: str
    seed: int
    cycles: int
    logical_ms: int
    transitions: int
    successful_activities: int
    movement_steps: int
    max_route_steps: int
    recovery_count: int
    projection_rejections: int
    final_tile: tuple[int, int]
    final_activity: str
    events: tuple[Event, ...]

    def trace_bytes(self) -> bytes:
        return (
            json.dumps(
                asdict(self),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.trace_bytes()).hexdigest()


def simulate(
    candidate: LayoutCandidate,
    *,
    cycles: int = 1,
    seed: int = SEED,
    initial: Position | None = None,
) -> Report:
    if type(cycles) is not int or not 1 <= cycles <= LONG_CYCLES:
        raise ValueError("cycles must be 1..270")
    if type(seed) is not int or not 0 <= seed < 2**256:
        raise ValueError("seed must be an unsigned 256-bit integer")
    validity = validate_layout(candidate)
    if not validity.valid:
        raise ValueError("invalid_layout:" + ",".join(error.code for error in validity.errors))
    state = snapshot(candidate)
    legacy = DevelopmentWorld(state.world, state.catalog)
    allowed = frozenset(state.mask.walkable)
    closed = tuple(r.floor for r in state.world.regions if r.status is RegionStatus.CLOSED)
    current = candidate.maple
    key = PointKey("idle.hall_center", "idle")
    previous_activity = Activity.IDLE
    rng = RngState(f"{seed:064x}")
    at_ms = steps = max_steps = recoveries = rejects = 0
    events: list[Event] = []

    def event(
        kind: str,
        activity: Activity,
        tile: Tile,
        target: PointKey,
        count: int = 0,
        turns: int = 0,
        detail: str = "",
    ) -> None:
        assert tile in allowed and not any(room.contains(tile) for room in closed)
        events.append(
            Event(
                kind,
                at_ms,
                activity.value,
                (tile.tx, tile.ty),
                (target.instance_id, target.point_id),
                count,
                turns,
                detail,
            )
        )

    if initial is not None:
        recovered = recover(state.mask, initial)
        if recovered.destination is None:
            raise ValueError("unsafe_recovery")
        current = recovered.destination
        if recovered.event is not None:
            recoveries += 1
            event(
                "maple_relocated",
                Activity.IDLE,
                current,
                key,
                detail=f"{initial.tx},{initial.ty}:{recovered.event.reason.value}",
            )
    event("initial", Activity.IDLE, current, key)
    for index in range(cycles * len(SCHEDULE)):
        activity = SCHEDULE[index % len(SCHEDULE)]
        resolution = resolve(activity, state, current, DecisionContext(rng, key))
        chosen = resolution.selected
        if chosen is None:
            raise ValueError("no_candidate:" + activity.value)
        rng = replace(rng, decision_counter=rng.decision_counter + 1)
        requirement = requirement_for(activity)
        assert any(
            all(c in chosen.point.template.provides for c in group)
            for group in requirement.alternatives
        )
        route = chosen.route
        assert route.origin == current and route.destination == chosen.approach
        assert route.total_steps < len(allowed)  # Bounded simple shortest path.
        assert set(route.tiles()) <= allowed
        assert recover(state.mask, Position(current.tx, current.ty)).event is None
        event("selected", activity, current, chosen.key, route.total_steps, route.turns)
        travel = Travel(route, START + timedelta(milliseconds=at_ms))
        assert travel.ms_per_step == MS_PER_STEP and travel.activity_started_at == travel.arrives_at
        duration_ms = SPECS[activity].min_minutes * 60000
        presentation = Presentation(
            activity,
            travel.arrives_at,
            travel.arrives_at + timedelta(milliseconds=duration_ms),
            Needs(50, 50, 50, 50),
            None,
            Expression.CALM,
            chosen.point.template.pose,
            day_phase(local_hour(travel.arrives_at, timedelta(hours=7))),
            "development_fixture",
        )
        destination = PointRef(chosen.key.instance_id, chosen.key.point_id)
        origin = PointRef(key.instance_id, key.point_id)
        source_tile = next(
            Tile(p.template.approach.x, p.template.approach.y)
            for p in state.catalog.points
            if (p.instance_id, p.template.id) == (key.instance_id, key.point_id)
        )
        collapsed = (
            route.total_steps > 0
            and project_point(legacy, origin, previous_activity).id
            == project_point(legacy, destination, activity).id
        )
        if source_tile != current or collapsed:
            # Accepted R1A-09 limitations: explicit failure, never fabricated motion.
            try:
                project(
                    legacy,
                    destination,
                    presentation,
                    travel.departed_at,
                    travel=travel,
                    origin=origin,
                    from_activity=previous_activity,
                )
            except ValueError as exc:
                assert "collapses" in str(exc) or "origin" in str(exc)
            else:
                raise AssertionError("unmappable projection was accepted")
            rejects += 1
            event(
                "projection_rejected",
                activity,
                current,
                chosen.key,
                detail="collapsed_anchor" if collapsed else "recovered_non_anchor",
            )
        else:
            for now in (
                travel.departed_at,
                travel.departed_at + (travel.arrives_at - travel.departed_at) / 2,
                travel.arrives_at,
            ):
                projected = project(
                    legacy,
                    destination,
                    presentation,
                    now,
                    travel=travel,
                    origin=origin,
                    from_activity=previous_activity,
                )
                assert projected.presentation is presentation
                if projected.route is not None:
                    assert projected.route.departed_at == travel.departed_at
                    assert projected.route.arrives_at == travel.arrives_at
                if now == travel.arrives_at:
                    assert projected.position == (projected.point.x, projected.point.y)
        previous = current
        for step, tile in enumerate(route.tiles()[1:], 1):
            assert distance(previous, tile) == 1
            boundary = travel.departed_at + timedelta(milliseconds=step * MS_PER_STEP)
            assert travel.current_at(boundary) == tile
            assert travel.phase_at(boundary - timedelta(microseconds=1)) == "walking"
            before = travel.current_at(boundary - timedelta(microseconds=1))
            assert isinstance(before, EdgeStart)
            assert (before.a, before.b, before.progress_us) == (previous, tile, travel.step_us - 1)
            at_ms += MS_PER_STEP
            event("step", activity, tile, chosen.key)
            previous = tile
        assert START + timedelta(milliseconds=at_ms) == travel.arrives_at
        assert travel.phase_at(travel.arrives_at) == "performing"
        current = route.destination
        key = chosen.key
        event("arrived", activity, current, key)
        at_ms += duration_ms
        event("completed", activity, current, key)
        previous_activity = activity
        steps += route.total_steps
        max_steps = max(max_steps, route.total_steps)
    return Report(
        VERSION,
        seed,
        cycles,
        at_ms,
        cycles * len(SCHEDULE),
        cycles * len(SCHEDULE),
        steps,
        max_steps,
        recoveries,
        rejects,
        (current.tx, current.ty),
        previous_activity.value,
        tuple(events),
    )
