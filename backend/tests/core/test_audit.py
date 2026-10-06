"""Decision and action audit output (ADR-0026 §8, ADR-0028 §2)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.audit import (
    ActionEventKind,
    DecisionRecord,
    Executed,
    Proposal,
    Verdict,
)
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.direction import DecisionTrigger, decide
from maplegotchi.core.heartbeat import heartbeat
from maplegotchi.core.movement import arrival_actions, begin_activity, settle_movement
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.priority import Priority
from maplegotchi.core.room import POINT_BY_ID
from maplegotchi.core.signals import CRITICAL_ATTENTION
from maplegotchi.core.state import MapleState
from maplegotchi.core.timeline import ActivityChanged
from tests.core.support import PARAMS, at_local, make_state

NOON = at_local(12)
CALM = BehaviorInputs()


def kinds(actions: tuple[object, ...]) -> list[ActionEventKind]:
    return [a.kind for a in actions]  # type: ignore[attr-defined]


def test_rule_decision_records_context_proposal_verdict_and_execution() -> None:
    idle = make_state(at=NOON, activity=Activity.IDLE, until=timedelta(0))
    out = decide(idle, NOON, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS)
    record = out.record
    assert record is not None
    assert (record.director_kind, record.director_name) == ("rule", "rule_director")
    assert record.verdict is Verdict.ACCEPTED and record.reason_code is None
    assert record.trigger == "action_completed"
    assert "trigger=action_completed" in record.context_summary
    assert "activity=idle@open_area.center" in record.context_summary
    assert "\n" not in record.context_summary
    proposal = record.proposal
    assert proposal is not None and proposal.goal_op == "new"
    assert proposal.action is out.plan.action and proposal.reason == out.plan.reason
    executed = record.executed
    assert executed is not None
    assert executed.action is out.state.activity
    assert executed.point == out.state.point.id
    assert executed.action_id == out.state.action_id
    assert executed.goal_id == out.state.goal.id  # type: ignore[union-attr]


def test_decision_actions_end_the_old_action_then_select_and_walk() -> None:
    reading = make_state(at=NOON, activity=Activity.READ, until=timedelta(minutes=20))
    end = reading.activity_until
    out = decide(
        reading, end + timedelta(seconds=3), DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS
    )
    k = kinds(out.actions)
    assert k[0] is ActionEventKind.ACTIVITY_COMPLETED
    assert out.actions[0].at == end and out.actions[0].action_id == reading.action_id
    assert ActionEventKind.DESTINATION_SELECTED in k
    selected = out.actions[k.index(ActionEventKind.DESTINATION_SELECTED)]
    assert selected.action_id == out.state.action_id
    assert selected.payload["point"] == out.state.point.id
    if out.state.route is not None:
        assert k[-1] is ActionEventKind.WALKING_STARTED
    else:
        assert k[-1] is ActionEventKind.ACTIVITY_STARTED


def test_arrival_records_arrived_then_activity_started_at_the_arrival_time() -> None:
    reading = make_state(at=NOON, activity=Activity.READ)
    desk = POINT_BY_ID["writing_desk.chair"]
    walking = begin_activity(reading, NOON, Activity.WRITE, desk, NOON + timedelta(minutes=30))
    route = walking.route
    assert route is not None
    assert arrival_actions(walking.state, route.arrives_at - timedelta(milliseconds=1)) == ()
    arrived = arrival_actions(walking.state, route.arrives_at + timedelta(minutes=2))
    assert kinds(arrived) == [ActionEventKind.ARRIVED, ActionEventKind.ACTIVITY_STARTED]
    assert all(a.at == route.arrives_at for a in arrived)
    assert arrived[1].payload["activity"] == "write"


def test_changing_the_plan_mid_walk_records_the_cancelled_walk() -> None:
    reading = make_state(at=NOON, activity=Activity.READ, until=timedelta(0))
    first = decide(reading, NOON, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS)
    if first.state.route is None:
        pytest.skip("this seed starts in place")
    asked = replace(first.state, reevaluate_since=NOON)
    soon = NOON + timedelta(milliseconds=200)
    second = decide(asked, soon, DecisionTrigger.RE_EVALUATE, CALM, PARAMS)
    k = kinds(second.actions)
    assert ActionEventKind.WALKING_CANCELLED in k
    assert second.actions[k.index(ActionEventKind.WALKING_CANCELLED)].action_id == (
        first.state.action_id
    )


def test_interruption_records_attention_and_the_interrupted_activity() -> None:
    writing = make_state(at=NOON, activity=Activity.WRITE, location=RoomLocation.DESK)
    tick = heartbeat(writing, NOON + PARAMS.heartbeat_interval,
                     BehaviorInputs(CRITICAL_ATTENTION), PARAMS)  # fmt: skip
    k = kinds(tick.actions)
    assert k[:2] == [ActionEventKind.NEEDS_ATTENTION, ActionEventKind.ACTIVITY_INTERRUPTED]
    attention, interrupted = tick.actions[0], tick.actions[1]
    assert attention.priority is Priority.CRITICAL
    assert attention.payload["signal"] == "server_problem"
    assert interrupted.payload == {"activity": "write", "cause": "server_problem"}
    assert interrupted.action_id == writing.action_id
    assert ActionEventKind.DESTINATION_SELECTED in k


def test_overdue_heartbeat_decision_is_recorded_as_a_fallback() -> None:
    params = CoreParameters(decision_grace=timedelta(seconds=120))
    s = make_state(at=NOON, activity=Activity.READ, until=timedelta(minutes=1))
    tick = heartbeat(s, NOON + params.heartbeat_interval, CALM, params)
    assert tick.decision is not None
    assert tick.decision.verdict is Verdict.FALLBACK
    assert tick.decision.reason_code == "timeout"
    assert tick.decision.trigger == "overdue"


def test_heartbeat_within_grace_leaves_the_decision_to_its_own_transition() -> None:
    params = CoreParameters(decision_grace=timedelta(seconds=120))
    s = make_state(at=NOON, activity=Activity.READ, until=params.heartbeat_interval)
    tick = heartbeat(s, NOON + params.heartbeat_interval, CALM, params)
    assert tick.decision is None
    assert tick.state.activity is Activity.READ


def _executed(state: MapleState) -> Executed:
    return Executed("rule", "Because.", None, 1, Activity.READ, "bookshelf.front", 20)


@pytest.mark.parametrize("reason", ["two\nlines", "", " padded", "x" * 241])
def test_records_accept_only_one_concise_reason_line(reason: str) -> None:
    with pytest.raises(ValueError):
        Proposal(reason=reason)


def test_records_require_execution_except_when_stale() -> None:
    base = {
        "at": NOON,
        "trigger": "action_completed",
        "director_kind": "external",
        "director_name": "antigravity",
        "director_version": "1",
        "context_summary": "x",
    }
    with pytest.raises(ValueError):
        DecisionRecord(**base, verdict=Verdict.STALE, executed=_executed(make_state()))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        DecisionRecord(**base, verdict=Verdict.ACCEPTED)  # type: ignore[arg-type]
    DecisionRecord(**base, verdict=Verdict.STALE)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        DecisionRecord(**{**base, "context_summary": "a\nb"}, verdict=Verdict.STALE)  # type: ignore[arg-type]


def test_settled_arrival_and_audit_agree() -> None:
    reading = make_state(at=NOON, activity=Activity.READ)
    walking = begin_activity(reading, NOON, Activity.SLEEP, POINT_BY_ID["bed.side"],
                             NOON + timedelta(hours=2))  # fmt: skip
    route = walking.route
    assert route is not None
    later = route.arrives_at + timedelta(seconds=5)
    settled, events = settle_movement(walking.state, later)
    audit = arrival_actions(walking.state, later)
    changed = events[0]
    assert isinstance(changed, ActivityChanged)
    assert changed.at == audit[0].at == settled.activity_started_at
