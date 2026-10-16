"""Pure ordinary-life MVP. Unsupported priority transitions are explicit blockers.

No clocks, storage, Legacy MapleState construction or autonomous retry. Ordinary
selection uses a bounded activity profile; this is not full R1B-04 acceptance.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from maplegotchi.core.activities import Activity
from maplegotchi.core.audit import ActionEvent, ActionEventKind
from maplegotchi.core.behavior import (
    FORCED_SLEEP_ENERGY,
    BehaviorInputs,
    sample_activity,
    sample_duration,
    score_facts,
)
from maplegotchi.core.daytime import local_hour, require_utc
from maplegotchi.core.direction import allowed_energy
from maplegotchi.core.heartbeat import wakes_rested_facts
from maplegotchi.core.movement import activity_window
from maplegotchi.core.needs import evolve_segments
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.rng import RngState, RngStream
from maplegotchi.core.signals import SignalKind, signals_from_needs
from maplegotchi.core.state import Needs
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.movement import Travel
from maplegotchi.core.world.resolution import (
    DecisionContext,
    PointKey,
    ResolutionSnapshot,
    candidates_for,
    resolve,
)

PROFILE = (Activity.IDLE, Activity.WALK, Activity.SLEEP, Activity.REST)


class LifeLoopBlocked(ValueError):
    """Fixed reason only. No candidate state is installed on failure."""


@dataclass(frozen=True, slots=True)
class LifeFrame:
    needs: Needs
    activity: Activity
    started_at: datetime
    until: datetime
    last_tick: datetime
    updated_at: datetime
    needs_at: datetime
    rng: RngState
    action_id: int
    point: PointKey
    tile: Tile
    travel: Travel | None
    from_activity: Activity | None


@dataclass(frozen=True, slots=True)
class LifeStep:
    frame: LifeFrame
    actions: tuple[ActionEvent, ...]
    previous: Activity | None = None
    changed_at: datetime | None = None
    minutes: int | None = None
    downtime_since: datetime | None = None


def step(
    before: LifeFrame,
    world: ResolutionSnapshot,
    now: datetime,
    inputs: BehaviorInputs,
    params: CoreParameters,
) -> LifeStep | None:
    """One explicit due heartbeat and, if due, an ordinary action selection.

    Priority responses are deliberately BLOCKED before any mutation, never
    queued until arrival or disguised as a successful heartbeat.
    """
    require_utc(now)
    if now < before.updated_at:
        raise LifeLoopBlocked("time")
    travel = before.travel
    needs = evolve_segments(
        before.needs,
        before.activity,
        now,
        min(now - before.needs_at, params.max_catchup),
        departed_at=travel.departed_at if travel else None,
        arrives_at=travel.arrives_at if travel else None,
        from_activity=before.from_activity,
    )
    signals = signals_from_needs(needs, inputs)
    if any(s.kind is SignalKind.SERVER_PROBLEM for s in signals):
        raise LifeLoopBlocked("critical_interrupt")
    if needs.energy <= FORCED_SLEEP_ENERGY and before.activity is not Activity.SLEEP:
        raise LifeLoopBlocked("high_interrupt")
    if now == before.updated_at or now - before.last_tick < params.heartbeat_interval:
        return None
    frame = replace(
        before,
        needs=needs,
        last_tick=now,
        updated_at=now,
        needs_at=now,
        rng=replace(before.rng, tick_counter=before.rng.tick_counter + 1),
    )
    actions: list[ActionEvent] = []
    previous = None
    changed_at = None
    if travel is not None and now >= travel.arrives_at:
        frame = replace(frame, tile=travel.route.destination, travel=None, from_activity=None)
        actions.extend(
            (
                ActionEvent(ActionEventKind.ARRIVED, travel.arrives_at, before.action_id),
                ActionEvent(ActionEventKind.ACTIVITY_STARTED, travel.arrives_at, before.action_id),
            )
        )
        if before.from_activity is not before.activity:
            previous, changed_at = before.from_activity, travel.arrives_at
    downtime = before.last_tick if now - before.last_tick > params.heartbeat_interval * 2 else None
    if wakes_rested_facts(frame.activity, frame.needs, frame.travel is not None, now, params):
        frame = replace(frame, until=now)
    # No ordinary switch while pending/in-flight, or before activity completion.
    if frame.travel is not None or now < frame.until:
        return LifeStep(frame, tuple(actions), previous, changed_at, downtime_since=downtime)
    # A single step cannot silently skip an arrival's activity to fabricate history.
    if travel is not None:
        raise LifeLoopBlocked("arrival_and_overdue")
    if frame.activity not in PROFILE:
        raise LifeLoopBlocked("activity_profile")
    context = DecisionContext(frame.rng, current_point=frame.point)
    scores = score_facts(needs, frame.activity, local_hour(now, params.utc_offset), inputs)
    eligible_scores = {
        a: scores[a]
        for a in PROFILE
        if a in allowed_energy(needs.energy) and candidates_for(a, world, frame.tile, context)
    }
    if not eligible_scores or max(eligible_scores.values()) <= 0:
        raise LifeLoopBlocked("no_eligible_activity")
    rng = RngStream(frame.rng.seed_hex, "decision", frame.rng.decision_counter + 1)
    activity = sample_activity(eligible_scores, rng)
    minutes = sample_duration(activity, rng)
    resolved = resolve(activity, world, frame.tile, replace(context, draw_offset=2))
    selected = resolved.selected
    if selected is None:
        raise LifeLoopBlocked("no_destination")
    new_travel = Travel(selected.route, now)
    action_id = frame.action_id + 1
    actions.append(ActionEvent(ActionEventKind.ACTIVITY_COMPLETED, frame.until, frame.action_id))
    actions.append(ActionEvent(ActionEventKind.DESTINATION_SELECTED, now, action_id))
    if new_travel.duration_us:
        actions.append(ActionEvent(ActionEventKind.WALKING_STARTED, now, action_id))
    else:
        actions.append(ActionEvent(ActionEventKind.ACTIVITY_STARTED, now, action_id))
        if activity is not frame.activity:
            previous, changed_at = frame.activity, now
    started, until = activity_window(
        frame.activity,
        frame.started_at,
        activity,
        now,
        new_travel.arrives_at,
        timedelta(minutes=minutes),
        starts_walk=new_travel.duration_us > 0,
    )
    result = replace(
        frame,
        activity=activity,
        point=selected.key,
        started_at=started,
        until=until,
        travel=new_travel if new_travel.duration_us else None,
        from_activity=frame.activity if new_travel.duration_us else None,
        tile=selected.route.origin,
        action_id=action_id,
        rng=replace(frame.rng, decision_counter=frame.rng.decision_counter + 1),
    )
    return LifeStep(result, tuple(actions), previous, changed_at, minutes, downtime)
