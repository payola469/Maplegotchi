"""Director proposals (ADR-0026 §4-§5): the context out, the proposal in, core decides.

`maple.decision.v1`:

- core builds a `DecisionContext` — plain, frozen, JSON-ready data: no handles,
  paths, config, journal text, seed, or sensor objects;
- a Director returns one JSON object, which core parses strictly
  (`parse_proposal`): unknown keys, wrong types, unknown enums, or text that is
  not one short printable line are rejected with a closed code;
- numbers slightly outside their range are clamped and the original recorded
  (verdict `clamped`); far outside, or non-finite, is rejected;
- the resulting `Plan` must still pass `check_plan` against the *current* state;
- anything rejected, missing, late or failed falls back to rule direction in
  the same transition, and the audit records why.

A Director's output is data only. Nothing here executes it, and it never reaches
storage except as validated, typed fields of a `DecisionRecord`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any

from maplegotchi.core.activities import SPECS, Activity
from maplegotchi.core.audit import DecisionRecord, Proposal, Verdict, context_summary
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.daytime import day_phase, local_hour, require_utc
from maplegotchi.core.direction import (
    DecisionOutcome,
    DecisionTrigger,
    GoalOp,
    Plan,
    Prepared,
    RejectionCode,
    allowed_actions,
    check_plan,
    decision_record,
    decision_rng,
    execute,
    prepare,
    rule_plan,
)
from maplegotchi.core.goals import (
    GOAL_MAX_HORIZON,
    GOAL_MIN_HORIZON,
    GoalEndReason,
    GoalSource,
    GoalType,
    summary_problems,
)
from maplegotchi.core.journal import text_problems
from maplegotchi.core.memory import RETRIEVE_LIMIT, Memory
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.room import FURNITURE_AT
from maplegotchi.core.signals import classify_signals
from maplegotchi.core.state import MapleState
from maplegotchi.core.tasks import (
    LIBRARY_CATALOG,
    SourceRef,
    Task,
    WriteKind,
    proposed_task,
    rule_task,
)

CONTRACT = "maple.decision.v1"
# "Slightly" out of range: within this factor of the bound is clamped; beyond is refused.
CLAMP_FACTOR = 2.0
MAX_RECENT_DECISIONS = 3

_TOP_KEYS = frozenset({"goal", "action", "reason"})
_GOAL_KEYS = frozenset({"op", "type", "summary", "horizon_minutes", "end_reason"})
_ACTION_KEYS = frozenset({"kind", "duration_minutes", "target"})
_ABANDON_REASONS = (
    GoalEndReason.DIRECTOR_ABANDONED,
    GoalEndReason.NO_LONGER_RELEVANT,
    GoalEndReason.SUPERSEDED,
    GoalEndReason.EXPIRED,
)


@dataclass(frozen=True, slots=True)
class DirectorLabel:
    kind: str  # rule | external
    name: str
    version: str


@dataclass(frozen=True, slots=True)
class DecisionContext:
    """Everything a Director may know for one decision; immutable and JSON-ready."""

    data: Mapping[str, Any]

    def as_json(self) -> dict[str, Any]:
        thawed: dict[str, Any] = _thaw(self.data)
        return thawed


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(v) for v in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


def _minutes(delta: timedelta) -> int:
    return max(0, int(delta.total_seconds() // 60))


def build_context(
    prepared: Prepared,
    now: datetime,
    trigger: DecisionTrigger,
    inputs: BehaviorInputs,
    params: CoreParameters,
    *,
    server_reasons: Sequence[str] = (),
    recent: Sequence[DecisionRecord] = (),
    catalog: Sequence[SourceRef] = LIBRARY_CATALOG,
    memories: Sequence[Memory] = (),
) -> DecisionContext:
    """The `maple.decision.v1` context core shows a Director (ADR-0026 §4)."""
    require_utc(now, "now")
    state = prepared.state
    hour = local_hour(now, params.utc_offset)
    point = state.point
    goal = state.goal
    suspended = state.suspended_goal
    actions = allowed_actions(state)
    data = {
        "contract": CONTRACT,
        "maple": {"name": state.identity.name},
        "time": {
            "now": now.isoformat(),
            "local_hour": round(hour, 2),
            "day_phase": day_phase(hour).value,
        },
        "trigger": trigger.value,
        "needs": {
            "mood": round(state.needs.mood, 1),
            "energy": round(state.needs.energy, 1),
            "curiosity": round(state.needs.curiosity, 1),
            "social": round(state.needs.social, 1),
        },
        "current": {
            "activity": state.activity.value,
            "walking": state.walking_at(now),
            "point": point.id,
            "furniture": point.furniture.value,
            "minutes_remaining": _minutes(state.activity_until - now),
            "priority": state.action_priority.value,
        },
        "goal": (
            {
                "id": goal.id,
                "type": goal.type.value,
                "summary": goal.summary,
                "minutes_left": _minutes(goal.horizon_until - now),
            }
            if goal
            else None
        ),
        "suspended_goal": (
            {
                "id": suspended.id,
                "type": suspended.type.value,
                "summary": suspended.summary,
                "minutes_left": _minutes(suspended.horizon_until - now),
                "interrupted_activity": (
                    state.suspended_action.value if state.suspended_action else None
                ),
            }
            if suspended
            else None
        ),
        "must_resolve_suspended_goal": prepared.resolving_suspension,
        "signals": [
            {"kind": s.kind.value, "priority": s.priority.value}
            for s in classify_signals(state, now, inputs)
        ],
        "server": {
            "attention": round(inputs.server_attention, 2),
            "reasons": list(server_reasons)[:10],
        },
        "allowed": {
            "goal_ops": [op.value for op in GoalOp],
            "goal_types": [t.value for t in GoalType],
            "horizon_minutes": [
                _minutes(GOAL_MIN_HORIZON),
                _minutes(GOAL_MAX_HORIZON),
            ],
            "actions": [
                {
                    "kind": a.value,
                    "min_minutes": SPECS[a].min_minutes,
                    "max_minutes": SPECS[a].max_minutes,
                    "furniture": FURNITURE_AT[SPECS[a].locations[0]].value,
                }
                for a in actions
            ],
            "end_reasons": [r.value for r in _ABANDON_REASONS],
            # Optional `action.target` (ADR-0029): what to read / which kind to write.
            "read_sources": [
                {"id": s.id, "title": s.title, "category": s.category} for s in catalog
            ],
            "write_kinds": [k.value for k in WriteKind],
        },
        # A few relevant memories, never the archive or the whole history (ADR-0030).
        "memories": [
            {"kind": m.kind.value, "tier": m.tier.value, "text": m.text}
            for m in list(memories)[:RETRIEVE_LIMIT]
        ],
        "recent_decisions": [
            {
                "at": r.at.isoformat(),
                "verdict": r.verdict.value,
                "action": r.executed.action.value if r.executed else None,
                "by": r.executed.by if r.executed else None,
            }
            for r in list(recent)[-MAX_RECENT_DECISIONS:]
        ],
    }
    return DecisionContext(_freeze(data))


# ---------------------------------------------------------------- parsing


@dataclass(frozen=True, slots=True)
class Parsed:
    """A structurally valid proposal, in core types, before range checks."""

    goal_op: GoalOp
    action: Activity
    duration_minutes: float
    reason: str
    goal_type: GoalType | None = None
    goal_summary: str | None = None
    horizon_minutes: float | None = None
    end_reason: GoalEndReason | None = None
    target: str | None = None  # what to read (catalog id) or write (document kind)

    def as_proposal(self) -> Proposal:
        return Proposal(
            goal_op=self.goal_op.value,
            goal_type=self.goal_type,
            goal_summary=self.goal_summary,
            horizon_minutes=self.horizon_minutes,
            abandon_reason=self.end_reason,
            action=self.action,
            duration_minutes=self.duration_minutes,
            reason=self.reason,
        )


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def parse_proposal(raw: object) -> Parsed | RejectionCode:
    """Strictly parse a `maple.decision.v1` proposal object. Never raises."""
    if not isinstance(raw, dict) or set(raw) != _TOP_KEYS:
        return RejectionCode.MALFORMED
    goal, action, reason = raw.get("goal"), raw.get("action"), raw.get("reason")
    if not isinstance(goal, dict) or not isinstance(action, dict):
        return RejectionCode.MALFORMED
    if not set(goal) <= _GOAL_KEYS or "op" not in goal:
        return RejectionCode.MALFORMED
    if not {"kind", "duration_minutes"} <= set(action) <= _ACTION_KEYS:
        return RejectionCode.MALFORMED
    target = action.get("target")
    if target is not None and (not isinstance(target, str) or not 1 <= len(target) <= 60):
        return RejectionCode.MALFORMED
    if text_problems(reason) or not isinstance(reason, str):
        return RejectionCode.TEXT_INVALID
    try:
        op = GoalOp(goal["op"])
    except (ValueError, TypeError):
        return RejectionCode.MALFORMED
    try:
        kind = Activity(action["kind"])
    except (ValueError, TypeError):
        return RejectionCode.UNKNOWN_ACTION
    duration = _number(action["duration_minutes"])
    if duration is None:
        return RejectionCode.MALFORMED
    allowed_goal_keys = {
        GoalOp.NEW: {"op", "type", "summary", "horizon_minutes"},
        GoalOp.ABANDON: {"op", "end_reason"},
    }.get(op, {"op"})
    if not set(goal) <= allowed_goal_keys:
        return RejectionCode.MALFORMED
    goal_type = summary = horizon = end_reason = None
    if op is GoalOp.NEW:
        if not {"type", "summary", "horizon_minutes"} <= set(goal):
            return RejectionCode.MALFORMED
        try:
            goal_type = GoalType(goal["type"])
        except (ValueError, TypeError):
            return RejectionCode.UNKNOWN_GOAL_TYPE
        summary = goal["summary"]
        if summary_problems(summary) or not isinstance(summary, str):
            return RejectionCode.TEXT_INVALID
        horizon = _number(goal["horizon_minutes"])
        if horizon is None:
            return RejectionCode.MALFORMED
    if op is GoalOp.ABANDON and "end_reason" in goal:
        try:
            end_reason = GoalEndReason(goal["end_reason"])
        except (ValueError, TypeError):
            return RejectionCode.MALFORMED
        if end_reason not in _ABANDON_REASONS:
            return RejectionCode.MALFORMED
    return Parsed(
        goal_op=op,
        action=kind,
        duration_minutes=duration,
        reason=reason,
        goal_type=goal_type,
        goal_summary=summary,
        horizon_minutes=horizon,
        end_reason=end_reason,
        target=target,
    )


def _clamp(value: float, low: float, high: float) -> tuple[float, bool] | None:
    """Clamp `value` into [low, high] if only slightly outside; None if far outside."""
    if low <= value <= high:
        return value, False
    if value < low / CLAMP_FACTOR or value > high * CLAMP_FACTOR:
        return None
    return min(high, max(low, value)), True


@dataclass(frozen=True, slots=True)
class Validated:
    plan: Plan
    verdict: Verdict  # accepted or clamped
    clamped: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({}))


def validate_proposal(
    prepared: Prepared,
    now: datetime,
    parsed: Parsed,
    catalog: Sequence[SourceRef] = LIBRARY_CATALOG,
) -> Validated | RejectionCode:
    """Range checks, clamping, then core's legality rules against the current state."""
    task = proposed_task(parsed.action, parsed.target, catalog)
    if task == "unknown_target":
        return RejectionCode.UNKNOWN_TARGET
    if task == "malformed":
        if parsed.target is not None:
            return RejectionCode.MALFORMED
        task = None  # read/write without a target: no task named; core picks one below
    clamped: dict[str, float] = {}
    spec = SPECS[parsed.action]
    fitted = _clamp(parsed.duration_minutes, spec.min_minutes, spec.max_minutes)
    if fitted is None:
        return RejectionCode.DURATION_OUT_OF_RANGE
    duration, was_clamped = fitted
    if was_clamped:
        clamped["duration_minutes"] = parsed.duration_minutes
    horizon = None
    if parsed.horizon_minutes is not None:
        low = GOAL_MIN_HORIZON.total_seconds() / 60
        high = GOAL_MAX_HORIZON.total_seconds() / 60
        fitted_horizon = _clamp(parsed.horizon_minutes, low, high)
        if fitted_horizon is None:
            return RejectionCode.DURATION_OUT_OF_RANGE
        horizon_minutes, horizon_clamped = fitted_horizon
        if horizon_clamped:
            clamped["horizon_minutes"] = parsed.horizon_minutes
        horizon = timedelta(minutes=horizon_minutes)
    plan = Plan(
        goal_op=parsed.goal_op,
        action=parsed.action,
        # Whole seconds, so stored and replayed plans are exact.
        duration=timedelta(seconds=round(duration * 60)),
        reason=parsed.reason,
        source=GoalSource.EXTERNAL,
        goal_type=parsed.goal_type,
        goal_summary=parsed.goal_summary,
        horizon=timedelta(seconds=round(horizon.total_seconds())) if horizon else None,
        end_reason=parsed.end_reason,
        task=task if isinstance(task, Task) else None,
    )
    problem = check_plan(prepared, now, plan)
    if problem is not None:
        return problem
    verdict = Verdict.CLAMPED if clamped else Verdict.ACCEPTED
    return Validated(plan, verdict, MappingProxyType(clamped))


# ---------------------------------------------------------------- deciding


def decide_with_proposal(
    state: MapleState,
    now: datetime,
    trigger: DecisionTrigger,
    inputs: BehaviorInputs,
    params: CoreParameters,
    *,
    director: DirectorLabel,
    raw: object = None,
    failure: RejectionCode | None = None,
    latency_ms: int | None = None,
    catalog: Sequence[SourceRef] = LIBRARY_CATALOG,
) -> DecisionOutcome:
    """Execute a Director's proposal if core accepts it, else rule direction.

    `raw` is the decoded JSON proposal (or None); `failure` says why there is
    none (timeout, transport error, no proposal). Deterministic for given inputs.
    """
    prepared = prepare(state, now, trigger, params)
    rng = decision_rng(state)
    label = (director.kind, director.name, director.version)
    parsed: Parsed | RejectionCode = failure if failure is not None else parse_proposal(raw)
    proposal = parsed.as_proposal() if isinstance(parsed, Parsed) else None
    checked = (
        validate_proposal(prepared, now, parsed, catalog) if isinstance(parsed, Parsed) else parsed
    )
    if isinstance(checked, Validated):
        plan = checked.plan
        if plan.task is None and plan.action in (Activity.READ, Activity.WRITE):
            goal = prepared.state.goal
            goal_type = plan.goal_type or (goal.type if goal else None)
            plan = replace(plan, task=rule_task(plan.action, goal_type, catalog, rng))
        outcome = execute(prepared, now, trigger, plan, rng)
        record = decision_record(
            prepared,
            outcome,
            now,
            inputs,
            params,
            director=label,
            verdict=checked.verdict,
            proposal=proposal,
            clamped=dict(checked.clamped),
            latency_ms=latency_ms,
        )
        return replace(outcome, record=record)
    # Refused or missing: rule direction decides, and the audit says why.
    plan = rule_plan(prepared, now, inputs, params, rng, catalog)
    outcome = execute(prepared, now, trigger, plan, rng)
    transport = checked in (
        RejectionCode.TIMEOUT,
        RejectionCode.TRANSPORT_ERROR,
        RejectionCode.NO_PROPOSAL,
    )
    record = decision_record(
        prepared,
        outcome,
        now,
        inputs,
        params,
        director=label,
        verdict=Verdict.FALLBACK if transport else Verdict.REJECTED,
        proposal=proposal,
        reason_code=checked.value,
        latency_ms=latency_ms,
    )
    return replace(outcome, record=record)


def stale_record(
    state: MapleState,
    now: datetime,
    inputs: BehaviorInputs,
    params: CoreParameters,
    *,
    director: DirectorLabel,
    raw: object,
    latency_ms: int | None,
) -> DecisionRecord:
    """A proposal that arrived after the decision stopped being due: recorded, not executed."""
    parsed = parse_proposal(raw)
    return DecisionRecord(
        at=now,
        trigger=DecisionTrigger.ACTION_COMPLETED.value,
        director_kind=director.kind,
        director_name=director.name,
        director_version=director.version,
        context_summary=context_summary(state, now, inputs, "stale", params.utc_offset),
        verdict=Verdict.STALE,
        proposal=parsed.as_proposal() if isinstance(parsed, Parsed) else None,
        reason_code=RejectionCode.STALE.value,
        latency_ms=latency_ms,
    )
