"""Decisions: Maple's next goal and action, chosen and then executed by core (ADR-0026).

A decision is its own life transition (never part of an ordinary heartbeat's
Director-free path):

    prepare  -> needs evolved to `now`, arrival settled, an expired goal completed
    plan     -> a `Plan`: goal operation + action + duration + concise reason,
                from rule direction (here) or a validated Director proposal
    check    -> core's legality rules (`check_plan`), shared by every planner
    execute  -> goal events, destination, walk (ADR-0027), counters

Interruptions (`interrupt`) are the other way an action ends early: a critical
or high-priority signal (core/signals.py) suspends the active goal and starts
core's own response action. After the interrupting action, the next decision
must resume the suspended goal (if still relevant) or abandon it with an
explicit reason.

Everything here is pure: time and randomness are supplied by the caller.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from maplegotchi.core.activities import SPECS, Activity
from maplegotchi.core.audit import (
    RULE_DIRECTOR_NAME,
    RULE_DIRECTOR_VERSION,
    ActionEvent,
    ActionEventKind,
    DecisionRecord,
    Executed,
    Proposal,
    Verdict,
    context_summary,
)
from maplegotchi.core.behavior import (
    FORCED_SLEEP_ENERGY,
    LOW_ENERGY,
    BehaviorInputs,
    choose_next_activity,
)
from maplegotchi.core.daytime import is_night, local_hour, require_utc
from maplegotchi.core.goals import (
    AFFINITY,
    AFFINITY_BOOST,
    GOAL_MAX_HORIZON,
    GOAL_MIN_HORIZON,
    RULE_SUMMARIES,
    Goal,
    GoalEndReason,
    GoalSource,
    GoalType,
    summary_problems,
)
from maplegotchi.core.journal import text_problems
from maplegotchi.core.movement import (
    MovementResult,
    arrival_actions,
    begin_activity,
    choose_point,
    performed_activity,
    settle_movement,
    start_actions,
)
from maplegotchi.core.needs import evolve_through, needs_since
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.priority import Priority
from maplegotchi.core.rng import RngStream
from maplegotchi.core.room import POINT_BY_ID
from maplegotchi.core.signals import CRITICAL_ATTENTION, NOTABLE_ATTENTION, Signal, SignalKind
from maplegotchi.core.state import MapleState
from maplegotchi.core.tasks import LIBRARY_CATALOG, SourceRef, Task, rule_task
from maplegotchi.core.timeline import (
    GoalAbandoned,
    GoalCompleted,
    GoalResumed,
    GoalStarted,
    GoalSuspended,
    LifeEvent,
)

CURIOUS_GOAL = 70.0
INTENT_WEIGHT = 4.0  # how strongly the daily intent leans everyday goal choices
LONELY_GOAL = 30.0
HAPPY_GOAL = 70.0


class DecisionTrigger(StrEnum):
    ACTION_COMPLETED = "action_completed"
    RE_EVALUATE = "re_evaluate"  # a high-priority input asked for a new decision
    NO_PLAN = "no_plan"
    OVERDUE = "overdue"  # the heartbeat applied rule direction after the grace period
    CRITICAL = "critical"


class GoalOp(StrEnum):
    KEEP = "keep"
    NEW = "new"
    COMPLETE = "complete"
    RESUME = "resume"
    ABANDON = "abandon"


class RejectionCode(StrEnum):
    """Why core refused a plan (closed codes, recorded in the audit)."""

    MALFORMED = "malformed"
    UNKNOWN_GOAL_TYPE = "unknown_goal_type"
    UNKNOWN_ACTION = "unknown_action"
    TEXT_INVALID = "text_invalid"
    GOAL_OPERATION_INVALID = "goal_operation_invalid"
    ACTION_NOT_ALLOWED = "action_not_allowed"
    NO_DESTINATION = "no_destination"
    DURATION_OUT_OF_RANGE = "duration_out_of_range"  # far outside; slightly outside is clamped
    UNKNOWN_TARGET = "unknown_target"  # a read/write target not in the approved catalog
    STALE = "stale"
    TIMEOUT = "timeout"
    TRANSPORT_ERROR = "transport_error"
    NO_PROPOSAL = "no_proposal"


@dataclass(frozen=True, slots=True)
class Plan:
    """What to do next, already in core's own types (never raw Director output)."""

    goal_op: GoalOp
    action: Activity
    duration: timedelta
    reason: str  # one concise, human-readable line; never model reasoning
    source: GoalSource
    goal_type: GoalType | None = None  # NEW only
    goal_summary: str | None = None  # NEW only
    horizon: timedelta | None = None  # NEW only
    end_reason: GoalEndReason | None = None  # ABANDON, or how to end a suspended goal
    task: Task | None = None  # what to read or write (ADR-0029); None for other actions

    def __post_init__(self) -> None:
        if not isinstance(self.goal_op, GoalOp) or not isinstance(self.action, Activity):
            raise TypeError("plan goal_op and action must be enums")
        if self.task is not None and not self.task.fits(self.action):
            raise ValueError("plan task does not fit its action")
        if self.duration <= timedelta(0):
            raise ValueError("plan duration must be positive")
        if text_problems(self.reason):
            raise ValueError("plan reason must be one short printable line")


@dataclass(frozen=True, slots=True)
class Prepared:
    """State made current for a decision at `now`, and what that already recorded."""

    state: MapleState
    events: tuple[LifeEvent, ...]
    resolving_suspension: bool  # this decision must resume or abandon the suspended goal
    actions: tuple[ActionEvent, ...] = ()  # e.g. an arrival recorded by preparing


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    state: MapleState
    events: tuple[LifeEvent, ...]
    trigger: DecisionTrigger
    plan: Plan
    movement: MovementResult
    started_goal: Goal | None
    resumed_action: bool  # the resumed goal continues the interrupted action kind
    actions: tuple[ActionEvent, ...] = ()
    record: DecisionRecord | None = None


@dataclass(frozen=True, slots=True)
class InterruptOutcome:
    state: MapleState
    events: tuple[LifeEvent, ...]
    signal: Signal
    interrupted: Activity  # what Maple was doing
    movement: MovementResult
    actions: tuple[ActionEvent, ...] = ()


# ---------------------------------------------------------------- helpers


def advance_needs(state: MapleState, now: datetime, params: CoreParameters) -> MapleState:
    """Evolve needs from when they were last evolved up to `now` (bounded catch-up)."""
    since = needs_since(state)
    if now <= since:
        return state
    elapsed = min(now - since, params.max_catchup)
    return replace(
        state,
        needs=evolve_through(state, now, elapsed),
        needs_at=now,
        last_updated_at=max(state.last_updated_at, now),
    )


def decision_due(state: MapleState, now: datetime) -> DecisionTrigger | None:
    """Whether a decision is due at `now` (never while walking to an action)."""
    require_utc(now, "now")
    if state.reevaluate_since is not None:
        return DecisionTrigger.RE_EVALUATE
    if state.walking_at(now):
        return None
    if now >= state.activity_until:
        return DecisionTrigger.ACTION_COMPLETED
    return None


def allowed_actions(state: MapleState) -> tuple[Activity, ...]:
    """Core's hard rules on what may be chosen now (ADR-0026 §5)."""
    energy = state.needs.energy
    if energy <= FORCED_SLEEP_ENERGY:
        return (Activity.SLEEP,)
    if energy < LOW_ENERGY:
        return (Activity.SLEEP, Activity.REST)
    return tuple(Activity)


def prepare(
    state: MapleState, now: datetime, trigger: DecisionTrigger, params: CoreParameters
) -> Prepared:
    require_utc(now, "now")
    if now < state.last_updated_at:
        raise ValueError("a decision cannot precede the latest state update")
    state = advance_needs(state, now, params)
    arrived = arrival_actions(state, now)
    state, arrival = settle_movement(state, now)
    events: list[LifeEvent] = list(arrival)
    goal = state.goal
    if goal is not None and goal.expired_at(now):
        events.append(GoalCompleted(now, goal.id, goal.type, GoalEndReason.HORIZON_REACHED))
        state = replace(state, goal=None)
    interruption_over = trigger in (
        DecisionTrigger.ACTION_COMPLETED,
        DecisionTrigger.OVERDUE,
        DecisionTrigger.NO_PLAN,
    )
    resolving = (
        state.suspended_goal is not None
        and state.action_priority in (Priority.CRITICAL, Priority.HIGH)
        and interruption_over
    )
    return Prepared(state, tuple(events), resolving, arrived)


def check_plan(prepared: Prepared, now: datetime, plan: Plan) -> RejectionCode | None:
    """Core's legality rules for any plan, from any planner. None = acceptable."""
    state = prepared.state
    if plan.action not in allowed_actions(state):
        return RejectionCode.ACTION_NOT_ALLOWED
    if not any(plan.action in p.allowed_actions for p in POINT_BY_ID.values()):
        return RejectionCode.NO_DESTINATION
    op = plan.goal_op
    if op in (GoalOp.KEEP, GoalOp.COMPLETE, GoalOp.ABANDON) and state.goal is None:
        return RejectionCode.GOAL_OPERATION_INVALID
    if op is GoalOp.RESUME:
        suspended = state.suspended_goal
        if not prepared.resolving_suspension or suspended is None or suspended.expired_at(now):
            return RejectionCode.GOAL_OPERATION_INVALID
    if op is GoalOp.NEW:
        if plan.goal_type is None or plan.horizon is None:
            return RejectionCode.MALFORMED
        if not GOAL_MIN_HORIZON <= plan.horizon <= GOAL_MAX_HORIZON:
            return RejectionCode.MALFORMED
        if summary_problems(plan.goal_summary):
            return RejectionCode.TEXT_INVALID
    spec = SPECS[plan.action]
    if (
        not timedelta(minutes=spec.min_minutes)
        <= plan.duration
        <= timedelta(minutes=spec.max_minutes)
    ):
        return RejectionCode.MALFORMED  # proposals are clamped before they get here
    return None


# ---------------------------------------------------------------- rule direction


def resume_is_relevant(state: MapleState, now: datetime, inputs: BehaviorInputs) -> bool:
    """Rule direction resumes a suspended goal if it has time left and the cause cleared."""
    suspended = state.suspended_goal
    if suspended is None or suspended.expired_at(now):
        return False
    return state.needs.energy >= LOW_ENERGY and inputs.server_attention < CRITICAL_ATTENTION


def rule_goal_type(
    state: MapleState,
    now: datetime,
    inputs: BehaviorInputs,
    params: CoreParameters,
    rng: RngStream,
    intent: GoalType | None = None,
) -> GoalType:
    needs = state.needs
    if needs.energy < LOW_ENERGY or is_night(local_hour(now, params.utc_offset)):
        return GoalType.RECOVER
    if inputs.server_attention >= NOTABLE_ATTENTION:
        return GoalType.MONITOR
    if needs.curiosity >= CURIOUS_GOAL:
        return rng.weighted_choice([GoalType.LEARN, GoalType.EXPLORE], [2.0, 1.0])
    if needs.social < LONELY_GOAL:
        return GoalType.SOCIALIZE
    if needs.mood >= HAPPY_GOAL:
        return rng.weighted_choice([GoalType.CREATE, GoalType.PLAY], [1.0, 1.0])
    everyday: list[GoalType] = [
        t for t in GoalType if t not in (GoalType.RECOVER, GoalType.MONITOR)
    ]
    if intent is not None and intent not in everyday:
        everyday.append(intent)
    # Yesterday's reflection leans today's choices toward its intent (ADR-0031 §5).
    weights = [INTENT_WEIGHT if t is intent else 1.0 for t in everyday]
    return rng.weighted_choice(everyday, weights)


def rule_plan(
    prepared: Prepared,
    now: datetime,
    inputs: BehaviorInputs,
    params: CoreParameters,
    rng: RngStream,
    catalog: Sequence[SourceRef] = LIBRARY_CATALOG,
    intent: GoalType | None = None,
) -> Plan:
    """Core's own direction: the fallback that is always available (ADR-0026 §1)."""
    state = prepared.state
    suspended = state.suspended_goal
    goal_type: GoalType
    if prepared.resolving_suspension and suspended and resume_is_relevant(state, now, inputs):
        op, goal_type = GoalOp.RESUME, suspended.type
    elif state.goal is not None:
        op, goal_type = GoalOp.KEEP, state.goal.type
    else:
        op, goal_type = GoalOp.NEW, rule_goal_type(state, now, inputs, params, rng, intent)
    bias = dict.fromkeys(AFFINITY[goal_type], AFFINITY_BOOST)
    choice = choose_next_activity(state, now, inputs, params, rng, bias=bias)
    horizon = None
    if op is GoalOp.NEW:
        horizon = timedelta(
            minutes=rng.randint(
                int(GOAL_MIN_HORIZON.total_seconds()) // 60,
                int(GOAL_MAX_HORIZON.total_seconds()) // 60,
            )
        )
    verb = {GoalOp.RESUME: "resume", GoalOp.KEEP: "keep", GoalOp.NEW: "start"}[op]
    task = rule_task(choice.activity, goal_type, catalog, rng)
    return Plan(
        goal_op=op,
        action=choice.activity,
        duration=choice.until - now,
        reason=f"Rule direction: {verb} the {goal_type.value} goal with {choice.activity.value}.",
        source=GoalSource.RULE,
        goal_type=goal_type if op is GoalOp.NEW else None,
        goal_summary=RULE_SUMMARIES[goal_type] if op is GoalOp.NEW else None,
        horizon=horizon,
        task=task,
    )


# ---------------------------------------------------------------- execution


def execute(
    prepared: Prepared,
    now: datetime,
    trigger: DecisionTrigger,
    plan: Plan,
    rng: RngStream,
) -> DecisionOutcome:
    """Apply a plan that passed `check_plan`. Raises if it did not."""
    problem = check_plan(prepared, now, plan)
    if problem is not None:
        raise ValueError(f"plan refused: {problem}")
    state = prepared.state
    events: list[LifeEvent] = list(prepared.events)
    goal, suspended, suspended_action = state.goal, state.suspended_goal, state.suspended_action
    counter = state.goal_counter
    resumed_action = False

    if prepared.resolving_suspension and suspended is not None:
        if plan.goal_op is GoalOp.RESUME:
            goal = suspended
            resumed_action = suspended_action is plan.action
            events.append(GoalResumed(now, suspended.id, suspended.type))
        else:
            reason = plan.end_reason if plan.end_reason in _ABANDON_REASONS else None
            if reason is None:
                reason = (
                    GoalEndReason.EXPIRED
                    if suspended.expired_at(now)
                    else GoalEndReason.NO_LONGER_RELEVANT
                )
            events.append(GoalAbandoned(now, suspended.id, suspended.type, reason))
        suspended, suspended_action = None, None

    if plan.goal_op is GoalOp.COMPLETE and goal is not None:
        events.append(GoalCompleted(now, goal.id, goal.type, GoalEndReason.DIRECTOR_COMPLETED))
        goal = None
    elif plan.goal_op is GoalOp.ABANDON and goal is not None:
        reason = plan.end_reason if plan.end_reason in _ABANDON_REASONS else None
        events.append(
            GoalAbandoned(now, goal.id, goal.type, reason or GoalEndReason.DIRECTOR_ABANDONED)
        )
        goal = None
    started: Goal | None = None
    if plan.goal_op is GoalOp.NEW:
        if goal is not None:
            events.append(GoalAbandoned(now, goal.id, goal.type, GoalEndReason.SUPERSEDED))
        if plan.goal_type is None or plan.goal_summary is None or plan.horizon is None:
            raise ValueError("a new goal needs a type, summary, and horizon")
        counter += 1
        started = Goal(
            id=counter,
            type=plan.goal_type,
            summary=plan.goal_summary,
            source=plan.source,
            started_at=now,
            horizon_until=now + plan.horizon,
        )
        goal = started
        events.append(GoalStarted(now, started))

    location = SPECS[plan.action].locations[0]
    if plan.action is state.activity and state.point.location is location:
        point = state.point  # continuing in place
    else:
        point = choose_point(plan.action, location, rng)
    moved = begin_activity(state, now, plan.action, point, now + plan.duration)
    events.extend(moved.events)
    action_id = state.action_id + 1
    goal_id = goal.id if goal else None
    actions = list(prepared.actions) + _ending_actions(state, now, trigger, moved)
    if resumed_action:
        actions.append(
            ActionEvent(
                ActionEventKind.ACTIVITY_RESUMED,
                now,
                action_id,
                goal_id,
                payload={"activity": plan.action.value},
            )
        )
    actions += start_actions(moved, action_id, goal_id, now)
    new_state = replace(
        moved.state,
        goal=goal,
        suspended_goal=suspended,
        suspended_action=suspended_action,
        goal_counter=counter,
        action_id=action_id,
        action_priority=Priority.NORMAL,
        reevaluate_since=None,
        task=plan.task,
        rng=replace(state.rng, decision_counter=state.rng.decision_counter + 1),
    )
    return DecisionOutcome(
        state=new_state,
        events=tuple(events),
        trigger=trigger,
        plan=plan,
        movement=moved,
        started_goal=started,
        resumed_action=resumed_action,
        actions=tuple(actions),
    )


def _ending_actions(
    previous: MapleState, now: datetime, trigger: DecisionTrigger, moved: MovementResult
) -> list[ActionEvent]:
    """How the previous action ended, as seen by this decision."""
    goal_id = previous.goal.id if previous.goal else None
    if moved.cancelled is not None:
        old = moved.cancelled.destination
        return [
            ActionEvent(
                ActionEventKind.WALKING_CANCELLED,
                now,
                previous.action_id,
                goal_id,
                payload={"activity": previous.activity.value, "point": old.id},
            )
        ]
    if previous.walking_at(now):
        return []
    if now >= previous.activity_until:
        return [
            ActionEvent(
                ActionEventKind.ACTIVITY_COMPLETED,
                previous.activity_until,
                previous.action_id,
                goal_id,
                payload={"activity": previous.activity.value},
            )
        ]
    return [
        ActionEvent(
            ActionEventKind.ACTIVITY_INTERRUPTED,
            now,
            previous.action_id,
            goal_id,
            payload={"activity": previous.activity.value, "cause": trigger.value},
        )
    ]


def decision_record(
    prepared: Prepared,
    outcome: DecisionOutcome,
    now: datetime,
    inputs: BehaviorInputs,
    params: CoreParameters,
    *,
    director: tuple[str, str, str] = ("rule", RULE_DIRECTOR_NAME, RULE_DIRECTOR_VERSION),
    verdict: Verdict = Verdict.ACCEPTED,
    proposal: Proposal | None = None,
    reason_code: str | None = None,
    clamped: dict[str, float] | None = None,
    latency_ms: int | None = None,
) -> DecisionRecord:
    """The audit record of an executed decision (ADR-0026 §8)."""
    plan = outcome.plan
    state = outcome.state
    if proposal is None and plan.source is GoalSource.RULE and verdict is Verdict.ACCEPTED:
        proposal = Proposal(
            goal_op=plan.goal_op.value,
            goal_type=plan.goal_type,
            goal_summary=plan.goal_summary,
            horizon_minutes=plan.horizon.total_seconds() / 60 if plan.horizon else None,
            action=plan.action,
            duration_minutes=plan.duration.total_seconds() / 60,
            reason=plan.reason,
        )
    return DecisionRecord(
        at=now,
        trigger=outcome.trigger.value,
        director_kind=director[0],
        director_name=director[1],
        director_version=director[2],
        context_summary=context_summary(
            prepared.state, now, inputs, outcome.trigger.value, params.utc_offset
        ),
        verdict=verdict,
        proposal=proposal,
        reason_code=reason_code,
        clamped=clamped or {},
        executed=Executed(
            by=plan.source.value,
            reason=plan.reason,
            goal_id=state.goal.id if state.goal else None,
            action_id=state.action_id,
            action=plan.action,
            point=state.point.id,
            duration_minutes=max(1, round(plan.duration.total_seconds() / 60)),
        ),
        latency_ms=latency_ms,
    )


_ABANDON_REASONS = frozenset(
    {
        GoalEndReason.EXPIRED,
        GoalEndReason.SUPERSEDED,
        GoalEndReason.NO_LONGER_RELEVANT,
        GoalEndReason.DIRECTOR_ABANDONED,
    }
)

Planner = Callable[[Prepared, RngStream], Plan]


def decision_rng(state: MapleState) -> RngStream:
    return RngStream(state.rng.seed_hex, "decision", state.rng.decision_counter + 1)


def decide(
    state: MapleState,
    now: datetime,
    trigger: DecisionTrigger,
    inputs: BehaviorInputs,
    params: CoreParameters,
    *,
    fallback_code: RejectionCode | None = None,
    catalog: Sequence[SourceRef] = LIBRARY_CATALOG,
    intent: GoalType | None = None,
) -> DecisionOutcome:
    """A rule-direction decision at `now` (deterministic for a given state and time).

    `fallback_code` marks it as a fallback for a Director that gave no usable
    answer (e.g. the heartbeat stepping in after `decision_grace`).
    """
    prepared = prepare(state, now, trigger, params)
    rng = decision_rng(state)
    plan = rule_plan(prepared, now, inputs, params, rng, catalog, intent)
    outcome = execute(prepared, now, trigger, plan, rng)
    record = decision_record(
        prepared,
        outcome,
        now,
        inputs,
        params,
        verdict=Verdict.FALLBACK if fallback_code else Verdict.ACCEPTED,
        reason_code=fallback_code.value if fallback_code else None,
    )
    return replace(outcome, record=record)


# ---------------------------------------------------------------- interruption

RESPONSES = {
    SignalKind.SERVER_PROBLEM: Activity.OBSERVE_SERVER,
    SignalKind.EXHAUSTED: Activity.SLEEP,
    SignalKind.OWNER_MESSAGE: Activity.IDLE,  # stop and listen (ADR-0032)
}


def interrupt(state: MapleState, now: datetime, signal: Signal, rng: RngStream) -> InterruptOutcome:
    """Suspend the active goal and start core's response to an urgent signal.

    The caller has already decided that `signal` interrupts (core/signals.py).
    """
    response = RESPONSES.get(signal.kind)
    if response is None:
        raise ValueError(f"{signal.kind} has no immediate response action")
    events: list[LifeEvent] = []
    interrupted = performed_activity(state, now)
    goal, suspended, suspended_action = state.goal, state.suspended_goal, state.suspended_action
    if goal is not None:
        if suspended is not None:
            events.append(
                GoalAbandoned(now, suspended.id, suspended.type, GoalEndReason.SUPERSEDED)
            )
        events.append(GoalSuspended(now, goal.id, goal.type, signal.kind.value))
        suspended, suspended_action, goal = goal, interrupted, None
    spec = SPECS[response]
    minutes = rng.randint(spec.min_minutes, spec.max_minutes)
    point = choose_point(response, spec.locations[0], rng)
    moved = begin_activity(state, now, response, point, now + timedelta(minutes=minutes))
    events.extend(moved.events)
    old_goal = state.goal.id if state.goal else None
    attention = ActionEvent(
        ActionEventKind.NEEDS_ATTENTION,
        now,
        state.action_id,
        old_goal,
        signal.priority,
        payload={"signal": signal.kind.value},
    )
    ended = (
        ActionEvent(
            ActionEventKind.WALKING_CANCELLED,
            now,
            state.action_id,
            old_goal,
            signal.priority,
            payload={"activity": state.activity.value, "cause": signal.kind.value},
        )
        if moved.cancelled is not None
        else ActionEvent(
            ActionEventKind.ACTIVITY_INTERRUPTED,
            now,
            state.action_id,
            old_goal,
            signal.priority,
            payload={"activity": interrupted.value, "cause": signal.kind.value},
        )
    )
    actions = [attention, ended, *start_actions(moved, state.action_id + 1, None, now)]
    new_state = replace(
        moved.state,
        goal=goal,
        suspended_goal=suspended,
        suspended_action=suspended_action,
        action_id=state.action_id + 1,
        action_priority=signal.priority,
        critical_since=now if signal.priority is Priority.CRITICAL else state.critical_since,
        task=None,  # response actions are not reading or writing
    )
    return InterruptOutcome(new_state, tuple(events), signal, interrupted, moved, tuple(actions))
