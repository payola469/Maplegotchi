"""Director proposals: strict parsing, clamping, validation, fallback (ADR-0026 §4-§5)."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta
from typing import Any

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.audit import Verdict
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.direction import (
    DecisionOutcome,
    DecisionTrigger,
    RejectionCode,
    decide,
    prepare,
)
from maplegotchi.core.goals import GoalSource
from maplegotchi.core.heartbeat import heartbeat
from maplegotchi.core.proposal import (
    CONTRACT,
    DirectorLabel,
    Parsed,
    build_context,
    decide_with_proposal,
    parse_proposal,
)
from maplegotchi.core.signals import CRITICAL_ATTENTION
from maplegotchi.core.state import MapleState
from tests.core.support import PARAMS, at_local, make_state, needs

NOON = at_local(12)
CALM = BehaviorInputs()
AG = DirectorLabel("external", "antigravity", "1")


def proposal(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "goal": {
            "op": "new",
            "type": "learn",
            "summary": "Read about gardens",
            "horizon_minutes": 60,
        },
        "action": {"kind": "read", "duration_minutes": 30},
        "reason": "Curiosity is high and the bookshelf is close.",
    }
    base.update(over)
    return base


def fresh() -> MapleState:
    return make_state(at=NOON, until=timedelta(0))


def run(
    raw: object = None, failure: RejectionCode | None = None, state: MapleState | None = None
) -> DecisionOutcome:
    s = state or fresh()
    return decide_with_proposal(
        s, NOON, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS, director=AG, raw=raw,
        failure=failure, latency_ms=42,
    )  # fmt: skip


# ---------------------------------------------------------------- parsing


def test_a_valid_proposal_parses_into_core_types() -> None:
    parsed = parse_proposal(proposal())
    assert isinstance(parsed, Parsed)
    assert parsed.action is Activity.READ and parsed.duration_minutes == 30


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (None, RejectionCode.MALFORMED),
        ("read", RejectionCode.MALFORMED),
        ({**proposal(), "extra": 1}, RejectionCode.MALFORMED),
        ({"goal": {"op": "keep"}, "action": {"kind": "read", "duration_minutes": 20}},
         RejectionCode.MALFORMED),  # no reason
        (proposal(action={"kind": "dance", "duration_minutes": 20}), RejectionCode.UNKNOWN_ACTION),
        (proposal(action={"kind": "read", "duration_minutes": "20"}), RejectionCode.MALFORMED),
        (proposal(action={"kind": "read", "duration_minutes": True}), RejectionCode.MALFORMED),
        (proposal(action={"kind": "read", "duration_minutes": float("nan")}),
         RejectionCode.MALFORMED),
        (proposal(action={"kind": "read", "duration_minutes": 20, "shell": "rm"}),
         RejectionCode.MALFORMED),
        (proposal(goal={"op": "new", "type": "conquer", "summary": "x", "horizon_minutes": 60}),
         RejectionCode.UNKNOWN_GOAL_TYPE),
        (proposal(goal={"op": "new", "type": "learn", "summary": "a\nb", "horizon_minutes": 60}),
         RejectionCode.TEXT_INVALID),
        (proposal(goal={"op": "keep", "type": "learn"}), RejectionCode.MALFORMED),
        (proposal(goal={"op": "teleport"}), RejectionCode.MALFORMED),
        (proposal(reason="line one\nline two"), RejectionCode.TEXT_INVALID),
        (proposal(reason="x" * 241), RejectionCode.TEXT_INVALID),
        (proposal(reason=""), RejectionCode.TEXT_INVALID),
    ],
)  # fmt: skip
def test_parsing_is_strict(raw: object, code: RejectionCode) -> None:
    assert parse_proposal(raw) is code


# ---------------------------------------------------------------- outcomes


def test_an_accepted_proposal_is_executed_by_core() -> None:
    out = run(proposal())
    record = out.record
    assert record is not None and record.verdict is Verdict.ACCEPTED
    assert out.state.activity is Activity.READ
    assert out.state.goal is not None and out.state.goal.source is GoalSource.EXTERNAL
    assert out.state.goal.summary == "Read about gardens"
    assert record.director_kind == "external" and record.latency_ms == 42
    assert record.proposal is not None
    assert record.proposal.reason == "Curiosity is high and the bookshelf is close."
    assert record.executed is not None and record.executed.by == "external"
    assert out.state.activity_until - out.state.activity_started_at == timedelta(minutes=30)


def test_slightly_out_of_range_durations_are_clamped_and_recorded() -> None:
    out = run(proposal(action={"kind": "read", "duration_minutes": 75},
                       goal={"op": "new", "type": "learn", "summary": "Read",
                             "horizon_minutes": 150}))  # fmt: skip
    record = out.record
    assert record is not None and record.verdict is Verdict.CLAMPED
    assert dict(record.clamped) == {"duration_minutes": 75.0, "horizon_minutes": 150.0}
    assert out.state.activity_until - out.state.activity_started_at == timedelta(minutes=60)
    goal = out.state.goal
    assert goal is not None and goal.horizon_until - goal.started_at == timedelta(minutes=120)


@pytest.mark.parametrize("minutes", [500, 5, 0, -10])
def test_far_out_of_range_durations_are_rejected(minutes: float) -> None:
    out = run(proposal(action={"kind": "read", "duration_minutes": minutes}))
    record = out.record
    assert record is not None and record.verdict is Verdict.REJECTED
    assert record.reason_code == "duration_out_of_range"
    assert record.executed is not None and record.executed.by == "rule"  # fallback executed


def test_unsupported_or_unsafe_proposals_fall_back_to_rule_direction() -> None:
    for raw, code in (
        ({"cmd": "systemctl restart grafana"}, "malformed"),
        (proposal(goal={"op": "keep"}), "goal_operation_invalid"),  # no active goal
        (proposal(goal={"op": "resume"}), "goal_operation_invalid"),
    ):
        out = run(raw)
        record = out.record
        assert record is not None
        assert (record.verdict, record.reason_code) == (Verdict.REJECTED, code)
        assert out.plan.source is GoalSource.RULE
        assert out.plan.reason.startswith("Rule direction:")


def test_hard_rules_override_the_director() -> None:
    tired = make_state(at=NOON, state_needs=needs(energy=5.0), until=timedelta(0))
    out = run(proposal(), state=tired)
    record = out.record
    assert record is not None and record.reason_code == "action_not_allowed"
    assert out.state.activity is Activity.SLEEP


@pytest.mark.parametrize(
    "failure", [RejectionCode.TIMEOUT, RejectionCode.TRANSPORT_ERROR, RejectionCode.NO_PROPOSAL]
)
def test_no_answer_is_a_recorded_fallback(failure: RejectionCode) -> None:
    out = run(failure=failure)
    record = out.record
    assert record is not None and record.verdict is Verdict.FALLBACK
    assert record.reason_code == failure.value and record.proposal is None
    assert out.state.goal is not None and out.state.goal.source is GoalSource.RULE


def test_external_and_rule_decisions_are_both_deterministic() -> None:
    assert run(proposal()) == run(proposal())
    assert run(failure=RejectionCode.TIMEOUT) == run(failure=RejectionCode.TIMEOUT)
    rule = decide(fresh(), NOON, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS)
    fallback = run(failure=RejectionCode.TIMEOUT)
    assert rule.state == fallback.state  # the fallback is exactly rule direction


def test_director_can_resume_a_suspended_goal() -> None:
    s = run(proposal()).state
    s = replace(s, route=None, point_id=None, activity_started_at=s.last_updated_at,
                activity_until=s.last_updated_at + timedelta(minutes=40))  # fmt: skip
    hit = heartbeat(s, s.last_updated_at + PARAMS.heartbeat_interval,
                    BehaviorInputs(CRITICAL_ATTENTION), PARAMS).state  # fmt: skip
    goal = hit.suspended_goal
    assert goal is not None
    done = hit.activity_until
    out = decide_with_proposal(
        replace(hit, critical_since=None), done, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS,
        director=AG, raw=proposal(goal={"op": "resume"}),
    )  # fmt: skip
    assert out.record is not None and out.record.verdict is Verdict.ACCEPTED
    assert out.state.goal == goal


# ---------------------------------------------------------------- context


def test_context_is_frozen_json_and_minimal() -> None:
    s = fresh()
    prepared = prepare(s, NOON, DecisionTrigger.ACTION_COMPLETED, PARAMS)
    ctx = build_context(prepared, NOON, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS,
                        server_reasons=("service_state:backup=failed",))  # fmt: skip
    data = ctx.as_json()
    assert data["contract"] == CONTRACT
    text = json.dumps(data)
    assert s.rng.seed_hex not in text  # never the life seed
    assert "/data" not in text and "maple.db" not in text
    assert set(data) == {
        "contract", "maple", "time", "trigger", "needs", "current", "goal", "suspended_goal",
        "must_resolve_suspended_goal", "signals", "server", "allowed", "recent_decisions",
        "memories",  # ADR-0030: a few relevant memories only
        "intent",  # ADR-0031: yesterday's reflection intent
    }  # fmt: skip
    with pytest.raises(TypeError):
        ctx.data["maple"] = {"name": "Not Maple"}  # type: ignore[index]
    with pytest.raises(TypeError):
        ctx.data["needs"]["energy"] = 100
    tired = make_state(at=NOON, state_needs=needs(energy=5.0), until=timedelta(0))
    p2 = prepare(tired, NOON, DecisionTrigger.ACTION_COMPLETED, PARAMS)
    allowed = build_context(p2, NOON, DecisionTrigger.ACTION_COMPLETED, CALM, PARAMS).as_json()
    assert [a["kind"] for a in allowed["allowed"]["actions"]] == ["sleep"]
