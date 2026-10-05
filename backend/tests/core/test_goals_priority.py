"""Goals, priority and interruption (ADR-0026 §6-§7), as pure core rules."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.direction import (
    DecisionTrigger,
    GoalOp,
    Plan,
    RejectionCode,
    check_plan,
    decide,
    decision_due,
    execute,
    prepare,
)
from maplegotchi.core.goals import Goal, GoalEndReason, GoalSource, GoalType
from maplegotchi.core.heartbeat import heartbeat
from maplegotchi.core.interactions import Accepted, apply_interaction
from maplegotchi.core.movement import settle_movement
from maplegotchi.core.priority import Priority
from maplegotchi.core.rng import RngStream
from maplegotchi.core.signals import (
    CRITICAL_ATTENTION,
    Signal,
    SignalKind,
    classify_signals,
    interrupts,
)
from maplegotchi.core.state import InteractionKind, MapleState
from maplegotchi.core.timeline import (
    GoalAbandoned,
    GoalCompleted,
    GoalResumed,
    GoalStarted,
    GoalSuspended,
)
from tests.core.support import OTHER_SEED, PARAMS, SEED, at_local, make_state, needs

NOON = at_local(12)
TICK = PARAMS.heartbeat_interval
CALM = BehaviorInputs()
ALARM = BehaviorInputs(server_attention=CRITICAL_ATTENTION)


def first_decision(state: MapleState | None = None) -> MapleState:
    s = state or make_state(at=NOON, activity=Activity.IDLE, until=timedelta(0))
    out = decide(s, NOON, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS)
    assert out.started_goal is not None
    return out.state


def settled(state: MapleState) -> MapleState:
    if state.route is None:
        return state
    s, _ = settle_movement(state, state.route.arrives_at)
    return s


# ---------------------------------------------------------------- goals


def test_the_v1_goal_types_are_exactly_these() -> None:
    assert {g.value for g in GoalType} == {
        "learn", "create", "recover", "reflect", "monitor", "socialize", "explore",
        "organize", "maintain", "practice", "plan", "wait", "play", "help",
        "investigate", "remember",
    }  # fmt: skip


@pytest.mark.parametrize("minutes", [29, 121])
def test_goal_horizon_is_bounded(minutes: int) -> None:
    with pytest.raises(ValueError):
        Goal(1, GoalType.LEARN, "Learn", GoalSource.RULE, NOON, NOON + timedelta(minutes=minutes))


@pytest.mark.parametrize("summary", ["", " padded", "two\nlines", "x" * 121])
def test_goal_summary_is_one_short_line(summary: str) -> None:
    with pytest.raises(ValueError):
        Goal(1, GoalType.LEARN, summary, GoalSource.RULE, NOON, NOON + timedelta(minutes=60))


def test_a_decision_starts_a_short_term_goal_and_an_action() -> None:
    idle = make_state(at=NOON, activity=Activity.IDLE, until=timedelta(0))
    out = decide(idle, NOON, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS)
    goal = out.started_goal
    assert goal is not None and goal.id == 1 and goal.source is GoalSource.RULE
    assert timedelta(minutes=30) <= goal.horizon_until - goal.started_at <= timedelta(minutes=120)
    assert GoalStarted(NOON, goal) in out.events
    assert out.state.goal == goal and out.state.goal_counter == 1
    assert out.state.action_id == idle.action_id + 1
    assert out.state.rng.decision_counter == idle.rng.decision_counter + 1
    assert out.plan.reason.startswith("Rule direction:")


def test_goal_type_does_not_fix_an_action_sequence() -> None:
    actions: dict[GoalType, set[Activity]] = {}
    for seed in (SEED, OTHER_SEED, "12" * 32, "34" * 32, "56" * 32, "78" * 32, "9a" * 32):
        for hour in (9, 11, 15, 17, 19):
            s = make_state(at=at_local(hour), activity=Activity.IDLE, seed=seed, until=timedelta(0))
            out = decide(s, at_local(hour), DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS)
            assert out.started_goal is not None
            actions.setdefault(out.started_goal.type, set()).add(out.plan.action)
    assert any(len(a) > 1 for a in actions.values())  # same intent, different actions


def test_an_active_goal_is_kept_by_later_decisions() -> None:
    first = settled(first_decision())
    later = first.activity_until
    out = decide(first, later, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS)
    assert out.plan.goal_op is GoalOp.KEEP
    assert out.state.goal == first.goal
    assert not any(isinstance(e, GoalStarted) for e in out.events)


def test_goal_completes_at_its_horizon() -> None:
    first = settled(first_decision())
    goal = first.goal
    assert goal is not None
    out = decide(first, goal.horizon_until, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS)
    assert (
        GoalCompleted(goal.horizon_until, goal.id, goal.type, GoalEndReason.HORIZON_REACHED)
        in out.events
    )
    assert out.state.goal is not None and out.state.goal.id == goal.id + 1


def test_decisions_are_deterministic() -> None:
    idle = make_state(at=NOON, activity=Activity.IDLE, until=timedelta(0))
    a = decide(idle, NOON, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS)
    b = decide(idle, NOON, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS)
    assert a == b


def test_no_decision_while_walking_or_before_the_action_ends() -> None:
    walking = first_decision()
    if walking.route is not None:
        assert decision_due(walking, NOON) is None
    s = settled(walking)
    assert decision_due(s, s.activity_until - timedelta(seconds=1)) is None
    assert decision_due(s, s.activity_until) is DecisionTrigger.ACTION_COMPLETED
    asked = replace(s, reevaluate_since=s.last_updated_at)
    assert decision_due(asked, s.last_updated_at) is DecisionTrigger.RE_EVALUATE


# ---------------------------------------------------------------- plan legality


def plan(action: Activity, op: GoalOp = GoalOp.KEEP, **kw: object) -> Plan:
    return Plan(
        goal_op=op,
        action=action,
        duration=timedelta(minutes=10),
        reason="Testing.",
        source=GoalSource.EXTERNAL,
        **kw,  # type: ignore[arg-type]
    )


def test_core_refuses_illegal_plans() -> None:
    idle = make_state(at=NOON, activity=Activity.IDLE, until=timedelta(0))
    prepared = prepare(idle, NOON, DecisionTrigger.ACTION_COMPLETED, PARAMS)
    assert check_plan(prepared, NOON, plan(Activity.THINK)) is RejectionCode.GOAL_OPERATION_INVALID
    assert (
        check_plan(prepared, NOON, plan(Activity.THINK, GoalOp.RESUME))
        is RejectionCode.GOAL_OPERATION_INVALID
    )
    tired = make_state(at=NOON, state_needs=needs(energy=5.0), until=timedelta(0))
    p = prepare(tired, NOON, DecisionTrigger.ACTION_COMPLETED, PARAMS)
    new = {"goal_type": GoalType.RECOVER, "goal_summary": "Rest", "horizon": timedelta(hours=1)}
    assert check_plan(p, NOON, plan(Activity.THINK, GoalOp.NEW, **new)) is (
        RejectionCode.ACTION_NOT_ALLOWED
    )
    with pytest.raises(ValueError, match="refused"):
        execute(prepared, NOON, DecisionTrigger.ACTION_COMPLETED, plan(Activity.THINK),
                RngStream(SEED, "decision", 1))  # fmt: skip


# ---------------------------------------------------------------- priority


def test_signal_priorities() -> None:
    s = make_state(at=NOON, state_needs=needs(energy=8.0, curiosity=90.0, social=10.0, mood=20.0))
    found = classify_signals(s, NOON, ALARM)
    assert [x.kind for x in found] == [
        SignalKind.SERVER_PROBLEM,
        SignalKind.EXHAUSTED,
        SignalKind.CURIOUS,
        SignalKind.LONELY,
        SignalKind.LOW_MOOD,
    ]
    assert [x.priority for x in found] == [
        Priority.CRITICAL, Priority.HIGH, Priority.NORMAL, Priority.NORMAL, Priority.LOW,
    ]  # fmt: skip
    mild = classify_signals(make_state(at=NOON), NOON, BehaviorInputs(server_attention=0.4))
    assert [x.kind for x in mild] == [SignalKind.SERVER_NOTABLE]
    assert mild[0].priority is Priority.NORMAL


@pytest.mark.parametrize(
    ("kind", "current", "expected"),
    [
        (SignalKind.SERVER_PROBLEM, Priority.LOW, True),
        (SignalKind.SERVER_PROBLEM, Priority.NORMAL, True),
        (SignalKind.SERVER_PROBLEM, Priority.HIGH, True),
        (SignalKind.SERVER_PROBLEM, Priority.CRITICAL, False),
        (SignalKind.OWNER_MESSAGE, Priority.NORMAL, True),
        (SignalKind.OWNER_MESSAGE, Priority.HIGH, False),
        (SignalKind.OWNER_MESSAGE, Priority.CRITICAL, False),
        (SignalKind.EXHAUSTED, Priority.CRITICAL, True),  # the hard forced-sleep rule
        (SignalKind.CURIOUS, Priority.LOW, False),
        (SignalKind.SERVER_NOTABLE, Priority.NORMAL, False),
        (SignalKind.LONELY, Priority.LOW, False),
        (SignalKind.LOW_MOOD, Priority.LOW, False),
    ],
)
def test_interruption_policy(kind: SignalKind, current: Priority, expected: bool) -> None:
    assert interrupts(Signal(kind), current) is expected


def writing_with_goal() -> MapleState:
    """Maple at the writing desk, mid-action, with an active goal."""
    first = settled(first_decision())
    goal = first.goal
    assert goal is not None
    return replace(
        first,
        activity=Activity.WRITE,
        location=RoomLocation.DESK,
        point_id=None,
        activity_started_at=first.last_updated_at,
        activity_until=first.last_updated_at + timedelta(minutes=40),
    )


def test_critical_interrupts_immediately_and_suspends_the_goal() -> None:
    s = writing_with_goal()
    goal = s.goal
    assert goal is not None
    now = s.last_updated_at + TICK
    tick = heartbeat(s, now, ALARM, PARAMS)
    after = tick.state
    assert after.activity is Activity.OBSERVE_SERVER
    assert after.action_priority is Priority.CRITICAL
    assert after.critical_since == now
    assert after.goal is None and after.suspended_goal == goal
    assert after.suspended_action is Activity.WRITE
    assert GoalSuspended(now, goal.id, goal.type, "server_problem") in tick.events
    # The same, still-present problem does not interrupt again.
    again = heartbeat(settled(after), now + TICK, ALARM, PARAMS)
    assert again.state.action_id == after.action_id
    assert again.state.critical_since == now


def test_problem_clearing_resets_critical_tracking() -> None:
    s = writing_with_goal()
    now = s.last_updated_at + TICK
    after = heartbeat(s, now, ALARM, PARAMS).state
    calm = heartbeat(settled(after), now + TICK, CALM, PARAMS).state
    assert calm.critical_since is None


def end_of_interruption(attention: BehaviorInputs) -> tuple[MapleState, Goal]:
    s = writing_with_goal()
    goal = s.goal
    assert goal is not None
    now = s.last_updated_at + TICK
    interrupted = settled(heartbeat(s, now, ALARM, PARAMS).state)
    return replace(interrupted, critical_since=None if attention is CALM else now), goal


def test_after_the_interruption_a_relevant_goal_is_resumed() -> None:
    interrupted, goal = end_of_interruption(CALM)
    when = interrupted.activity_until
    assert when < goal.horizon_until
    out = decide(interrupted, when, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS)
    assert GoalResumed(when, goal.id, goal.type) in out.events
    assert out.state.goal == goal and out.state.suspended_goal is None
    assert out.state.action_priority is Priority.NORMAL
    assert out.resumed_action is (out.plan.action is Activity.WRITE)


def test_an_expired_goal_is_abandoned_with_an_explicit_reason() -> None:
    interrupted, goal = end_of_interruption(CALM)
    when = goal.horizon_until + timedelta(minutes=1)
    out = decide(interrupted, when, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS)
    assert GoalAbandoned(when, goal.id, goal.type, GoalEndReason.EXPIRED) in out.events
    assert out.state.suspended_goal is None
    assert out.started_goal is not None  # Maple moves on with a new goal


def test_a_goal_whose_cause_has_not_cleared_is_abandoned() -> None:
    interrupted, goal = end_of_interruption(ALARM)
    when = interrupted.activity_until
    out = decide(interrupted, when, DecisionTrigger.ACTION_COMPLETED, ALARM, PARAMS)
    assert GoalAbandoned(when, goal.id, goal.type, GoalEndReason.NO_LONGER_RELEVANT) in out.events


def test_a_second_interruption_supersedes_the_older_suspended_goal() -> None:
    interrupted, old = end_of_interruption(CALM)
    # While the older goal is suspended, Maple holds a newer active goal.
    started = interrupted.last_updated_at
    newer = Goal(old.id + 1, GoalType.PLAN, "Plan", GoalSource.RULE, started,
                 started + timedelta(minutes=60))  # fmt: skip
    s = replace(interrupted, goal=newer, goal_counter=newer.id, needs=needs(energy=9.0))
    now = s.last_tick_at + TICK
    tick = heartbeat(s, now, CALM, PARAMS)
    assert tick.state.activity is Activity.SLEEP
    assert tick.state.action_priority is Priority.HIGH
    assert GoalAbandoned(now, old.id, old.type, GoalEndReason.SUPERSEDED) in tick.events
    assert GoalSuspended(now, newer.id, newer.type, "exhausted") in tick.events
    assert tick.state.suspended_goal == newer


def test_normal_and_low_signals_never_interrupt() -> None:
    s = writing_with_goal()
    restless = replace(s, needs=needs(curiosity=95.0, social=5.0, mood=20.0, energy=60.0))
    tick = heartbeat(restless, s.last_updated_at + TICK, BehaviorInputs(0.5), PARAMS)
    assert tick.state.activity is Activity.WRITE
    assert tick.state.action_id == s.action_id
    assert tick.state.goal == s.goal


def test_greet_and_pet_never_interrupt() -> None:
    s = writing_with_goal()
    for kind in (InteractionKind.GREET, InteractionKind.PET):
        out = apply_interaction(s, kind, s.last_updated_at + timedelta(seconds=40), PARAMS)
        assert isinstance(out, Accepted)
        after = out.state
        assert (after.activity, after.goal, after.action_id, after.action_priority) == (
            s.activity, s.goal, s.action_id, s.action_priority,
        )  # fmt: skip


def test_exhaustion_interrupts_even_a_critical_response() -> None:
    s = writing_with_goal()
    now = s.last_updated_at + TICK
    critical = settled(heartbeat(s, now, ALARM, PARAMS).state)
    drained = replace(critical, needs=needs(energy=10.1))
    tick = heartbeat(drained, now + TICK, ALARM, PARAMS)
    assert tick.state.activity is Activity.SLEEP
    assert tick.state.action_priority is Priority.HIGH
