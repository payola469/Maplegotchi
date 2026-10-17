"""Pure opt-in canonical life transitions with approved exact urgent rerouting.

No clock/storage/Legacy MapleState construction. Behavioral rules are shared;
world routing remains canonical. Unsupported equal-time/reevaluation stays closed.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from maplegotchi.core.activities import Activity
from maplegotchi.core.audit import ActionEvent, ActionEventKind
from maplegotchi.core.behavior import BehaviorInputs, sample_activity, sample_duration, score_facts
from maplegotchi.core.daytime import local_hour, require_utc
from maplegotchi.core.direction import (
    RESPONSES,
    allowed_energy,
    expire_goal,
    resume_goal_is_relevant,
    rule_goal_from_needs,
    sample_goal_horizon,
    suspend_goal,
)
from maplegotchi.core.goals import (
    AFFINITY,
    AFFINITY_BOOST,
    RULE_SUMMARIES,
    Goal,
    GoalEndReason,
    GoalSource,
)
from maplegotchi.core.heartbeat import wakes_rested_facts
from maplegotchi.core.movement import activity_window
from maplegotchi.core.needs import evolve_segments
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.priority import Priority
from maplegotchi.core.rng import RngState, RngStream
from maplegotchi.core.signals import Signal, SignalKind, interrupts, signals_from_needs
from maplegotchi.core.state import Needs
from maplegotchi.core.tasks import LIBRARY_CATALOG, SourceRef, Task, rule_task
from maplegotchi.core.timeline import (
    ActivityChanged,
    DowntimeGap,
    GoalAbandoned,
    GoalResumed,
    GoalStarted,
    LifeEvent,
)
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.movement import Travel
from maplegotchi.core.world.resolution import (
    DecisionContext,
    PointKey,
    ResolutionSnapshot,
    candidates_for,
    resolve,
    resolve_urgent,
)

PROFILE = tuple(Activity)


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
    priority: Priority = Priority.NORMAL
    critical_since: datetime | None = None
    goal: Goal | None = None
    suspended_goal: Goal | None = None
    suspended_action: Activity | None = None
    goal_counter: int = 0
    task: Task | None = None


@dataclass(frozen=True, slots=True)
class LifeStep:
    frame: LifeFrame
    actions: tuple[ActionEvent, ...]
    events: tuple[LifeEvent, ...] = ()
    minutes: int | None = None
    interruption: Signal | None = None
    goal_op: str | None = None


def _start(
    frame: LifeFrame,
    world: ResolutionSnapshot,
    activity: Activity,
    now: datetime,
    minutes: int,
    offset: int,
    *,
    urgent: bool = False,
) -> tuple[LifeFrame, tuple[ActionEvent, ...], tuple[LifeEvent, ...], int]:
    context = DecisionContext(frame.rng, frame.point, draw_offset=offset)
    if urgent and frame.travel is not None:
        selected_urgent = resolve_urgent(activity, world, frame.travel, now, context)
        candidate_urgent = selected_urgent.selected
        if candidate_urgent is None:
            raise LifeLoopBlocked("no_destination")
        travel, key, draws = (
            candidate_urgent.travel,
            candidate_urgent.key,
            selected_urgent.decision_draws,
        )
    else:
        selected = resolve(activity, world, frame.tile, context)
        candidate = selected.selected
        if candidate is None:
            raise LifeLoopBlocked("no_destination")
        travel, key, draws = Travel(candidate.route, now), candidate.key, selected.decision_draws
    started, until = activity_window(
        frame.activity,
        frame.started_at,
        activity,
        now,
        travel.arrives_at,
        timedelta(minutes=minutes),
        starts_walk=travel.duration_us > 0,
    )
    action_id = frame.action_id + 1
    performed = frame.from_activity if frame.travel is not None else frame.activity
    if performed is None:
        raise LifeLoopBlocked("provenance")
    goal_id = frame.goal.id if frame.goal else None
    actions = [ActionEvent(ActionEventKind.DESTINATION_SELECTED, now, action_id, goal_id)]
    events: tuple[LifeEvent, ...] = ()
    if travel.duration_us:
        actions.append(ActionEvent(ActionEventKind.WALKING_STARTED, now, action_id, goal_id))
    else:
        actions.append(ActionEvent(ActionEventKind.ACTIVITY_STARTED, now, action_id, goal_id))
        if activity is not performed:
            events = (ActivityChanged(now, performed, activity),)
    return (
        replace(
            frame,
            activity=activity,
            point=key,
            started_at=started,
            until=until,
            travel=travel if travel.duration_us else None,
            from_activity=performed if travel.duration_us else None,
            tile=travel.route.origin,
            action_id=action_id,
        ),
        tuple(actions),
        events,
        draws,
    )


def step(
    before: LifeFrame,
    world: ResolutionSnapshot,
    now: datetime,
    inputs: BehaviorInputs,
    params: CoreParameters,
    catalog: Sequence[SourceRef] = LIBRARY_CATALOG,
) -> LifeStep | None:
    """Due heartbeat, original-time arrival, and rule action/goal lifecycle.

    Urgent detection never waits for the ordinary tick interval. Exact Entry
    rerouting follows STEP249. Unsupported time/provenance is refused rather
    than recorded as a successful tick or queued for after arrival.
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
    kinds = {s.kind for s in signals}
    urgent = None
    for signal in signals:
        if signal.kind is SignalKind.EXHAUSTED and before.activity is Activity.SLEEP:
            continue
        if signal.kind is SignalKind.SERVER_PROBLEM and before.critical_since is not None:
            continue
        if interrupts(signal, before.priority):
            urgent = signal
            break
    if urgent is None and (
        now == before.updated_at or now - before.last_tick < params.heartbeat_interval
    ):
        return None
    if now == before.updated_at:
        raise LifeLoopBlocked("same_time_interrupt")
    frame = replace(
        before,
        needs=needs,
        last_tick=now,
        updated_at=now,
        needs_at=now,
        rng=replace(before.rng, tick_counter=before.rng.tick_counter + 1),
        critical_since=before.critical_since if SignalKind.SERVER_PROBLEM in kinds else None,
    )
    events: list[LifeEvent] = []
    actions: list[ActionEvent] = []
    if now - before.last_tick > params.heartbeat_interval * 2:
        events.append(DowntimeGap(before.last_tick, now))
    if travel is not None and now >= travel.arrives_at:
        frame = replace(frame, tile=travel.route.destination, travel=None, from_activity=None)
        goal_id = before.goal.id if before.goal else None
        actions.extend(
            (
                ActionEvent(ActionEventKind.ARRIVED, travel.arrives_at, before.action_id, goal_id),
                ActionEvent(
                    ActionEventKind.ACTIVITY_STARTED, travel.arrives_at, before.action_id, goal_id
                ),
            )
        )
        if before.from_activity is not before.activity and before.from_activity is not None:
            events.append(ActivityChanged(travel.arrives_at, before.from_activity, before.activity))
    if urgent is not None:
        response = RESPONSES.get(urgent.kind)
        if response is None:
            raise LifeLoopBlocked("interrupt_kind")
        performed = frame.from_activity if frame.travel is not None else frame.activity
        if performed is None:
            raise LifeLoopBlocked("provenance")
        goal, suspended, suspended_action, goal_events = suspend_goal(
            frame.goal,
            frame.suspended_goal,
            frame.suspended_action,
            performed,
            now,
            urgent,
        )
        old_goal = frame.goal.id if frame.goal else None
        attention = ActionEvent(
            ActionEventKind.NEEDS_ATTENTION,
            now,
            frame.action_id,
            old_goal,
            urgent.priority,
            {"signal": urgent.kind.value},
        )
        ended = ActionEvent(
            ActionEventKind.WALKING_CANCELLED
            if frame.travel is not None
            else ActionEventKind.ACTIVITY_INTERRUPTED,
            now,
            frame.action_id,
            old_goal,
            urgent.priority,
            {"activity": frame.activity.value, "cause": urgent.kind.value},
        )
        events.extend(goal_events)
        frame = replace(
            frame,
            goal=goal,
            suspended_goal=suspended,
            suspended_action=suspended_action,
            task=None,
            priority=urgent.priority,
            critical_since=now if urgent.priority is Priority.CRITICAL else frame.critical_since,
        )
        rng = RngStream(frame.rng.seed_hex, "tick", frame.rng.tick_counter)
        minutes = sample_duration(response, rng)
        frame, started, changed, draws = _start(
            frame, world, response, now, minutes, 0, urgent=True
        )
        frame = replace(
            frame, rng=replace(frame.rng, decision_counter=frame.rng.decision_counter + draws)
        )
        events.extend(changed)
        return LifeStep(
            frame, (*actions, attention, ended, *started), tuple(events), minutes, urgent
        )
    if wakes_rested_facts(frame.activity, frame.needs, frame.travel is not None, now, params):
        frame = replace(frame, until=now)
    if frame.travel is not None or now < frame.until:
        return LifeStep(frame, tuple(actions), tuple(events))
    goal, expired = expire_goal(frame.goal, now)
    events.extend(expired)
    suspended, suspended_action = frame.suspended_goal, frame.suspended_action
    resolving = suspended is not None and frame.priority in (Priority.CRITICAL, Priority.HIGH)
    goal_op = "keep"
    if resolving and suspended is not None:
        if resume_goal_is_relevant(suspended, needs, now, inputs):
            goal = suspended
            goal_op = "resume"
            events.append(GoalResumed(now, goal.id, goal.type))
        else:
            reason = (
                GoalEndReason.EXPIRED
                if suspended.expired_at(now)
                else GoalEndReason.NO_LONGER_RELEVANT
            )
            events.append(GoalAbandoned(now, suspended.id, suspended.type, reason))
        suspended, suspended_action = None, None
    rng = RngStream(frame.rng.seed_hex, "decision", frame.rng.decision_counter + 1)
    goal_type = goal.type if goal else rule_goal_from_needs(needs, now, inputs, params, rng)
    bias = dict.fromkeys(AFFINITY[goal_type], AFFINITY_BOOST)
    context = DecisionContext(frame.rng, frame.point)
    scores = score_facts(needs, frame.activity, local_hour(now, params.utc_offset), inputs, bias)
    eligible = {
        a: scores[a]
        for a in PROFILE
        if a in allowed_energy(needs.energy) and candidates_for(a, world, frame.tile, context)
    }
    if not eligible or max(eligible.values()) <= 0:
        raise LifeLoopBlocked("no_eligible_activity")
    activity = sample_activity(eligible, rng)
    minutes = sample_duration(activity, rng)
    frame = replace(frame, goal=goal, suspended_goal=suspended, suspended_action=suspended_action)
    # Resolve first so the existing decision stream can advance past point tie draws.
    moved, started, changed, draws = _start(frame, world, activity, now, minutes, rng.draw_count)
    for _ in range(draws):
        rng.random()
    if goal is None:
        goal_op = "new"
        goal = Goal(
            frame.goal_counter + 1,
            goal_type,
            RULE_SUMMARIES[goal_type],
            GoalSource.RULE,
            now,
            now + sample_goal_horizon(rng),
        )
        events.append(GoalStarted(now, goal))
    task = rule_task(activity, goal_type, catalog, rng)
    goal_id = goal.id
    started = tuple(replace(a, goal_id=goal_id) for a in started)
    old_goal = before.goal.id if before.goal else None
    actions.append(
        ActionEvent(
            ActionEventKind.ACTIVITY_COMPLETED,
            frame.until,
            frame.action_id,
            old_goal,
            payload={"activity": frame.activity.value},
        )
    )
    if goal_op == "resume" and before.suspended_action is activity:
        actions.append(
            ActionEvent(
                ActionEventKind.ACTIVITY_RESUMED,
                now,
                moved.action_id,
                goal_id,
                payload={"activity": activity.value},
            )
        )
    events.extend(changed)
    moved = replace(
        moved,
        goal=goal,
        goal_counter=max(frame.goal_counter, goal.id),
        task=task,
        priority=Priority.NORMAL,
        rng=replace(frame.rng, decision_counter=frame.rng.decision_counter + 1),
    )
    return LifeStep(moved, (*actions, *started), tuple(events), minutes, goal_op=goal_op)
