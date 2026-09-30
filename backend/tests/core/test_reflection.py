"""When Maple writes: day boundaries, dedup/hysteresis, daily reflection, milestones."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.heartbeat import TickResult, heartbeat
from maplegotchi.core.interactions import Accepted, apply_interaction
from maplegotchi.core.journal import ServerSummary, Trigger, TriggerKind
from maplegotchi.core.observations import (
    Metric,
    Observation,
    ObservationSnapshot,
    ObservationStatus,
    ServiceState,
    measured,
    not_measured,
)
from maplegotchi.core.reflection import (
    INITIAL_REFLECTION,
    JournalParameters,
    ReflectionState,
    evaluate_conditions,
    heartbeat_triggers,
    in_reflection_window,
    interaction_triggers,
    journal_day,
    mark_journaled,
    server_summary,
)
from maplegotchi.core.state import InteractionKind, MapleState
from maplegotchi.core.timeline import ActivityChanged
from tests.core.support import BORN, PARAMS, at_local, make_state

J = JournalParameters()
A = ObservationStatus.AVAILABLE


def svc(name: str, state: ServiceState | None, at: datetime) -> Observation:
    if state is None:
        return not_measured(
            Metric.SERVICE_STATE,
            name,
            ObservationStatus.UNKNOWN,
            "not_surveyed",
            observed_at=at,
            source="fake",
        )
    return Observation(Metric.SERVICE_STATE, name, A, at, "fake", state=state)


def snap(at: datetime, *obs: Observation) -> ObservationSnapshot:
    return ObservationSnapshot(at, obs)


# ---------------------------------------------------------------- day and window


@pytest.mark.parametrize(
    ("hour", "day"),
    [
        (5.99, date(2026, 1, 1)),
        (6.0, date(2026, 1, 2)),
        (12, date(2026, 1, 2)),
        (23.9, date(2026, 1, 2)),
        (24 + 5.9, date(2026, 1, 2)),
    ],
)
def test_journal_day_runs_six_to_six_bangkok(hour: float, day: date) -> None:
    assert journal_day(at_local(hour, day=1), PARAMS, J) == day


@pytest.mark.parametrize(
    ("hour", "inside"),
    [(20.99, False), (21, True), (23.5, True), (5.99, True), (6, False), (12, False)],
)
def test_reflection_window(hour: float, inside: bool) -> None:
    assert in_reflection_window(at_local(hour), PARAMS, J) is inside


# ---------------------------------------------------------------- server conditions


def test_failure_is_noticed_once_and_recovery_once() -> None:
    t = at_local(14)
    alerts, problems, recoveries = evaluate_conditions(
        (), snap(t, svc("jellyfin", ServiceState.FAILED, t))
    )
    assert [p.topic for p in problems] == ["service:jellyfin"] and not recoveries
    assert alerts == (("service:jellyfin", "failed"),)
    for state in (ServiceState.FAILED, None, ServiceState.ACTIVATING, ServiceState.INACTIVE):
        again, p2, r2 = evaluate_conditions(alerts, snap(t, svc("jellyfin", state, t)))
        assert again == alerts and not p2 and not r2  # persists, or unknown/ambiguous: silent
    cleared, p3, r3 = evaluate_conditions(alerts, snap(t, svc("jellyfin", ServiceState.ACTIVE, t)))
    assert cleared == () and not p3 and [r.label for r in r3] == ["failed"]
    assert r3[0].observation_keys == ((Metric.SERVICE_STATE, "jellyfin"),)


def test_unknown_data_never_starts_a_problem() -> None:
    t = at_local(14)
    _, problems, _ = evaluate_conditions((), snap(t, svc("jellyfin", None, t)))
    assert problems == []


def test_numeric_conditions_have_hysteresis() -> None:
    t = at_local(14)

    def disk(v: float) -> ObservationSnapshot:
        return snap(t, measured(Metric.DISK_USAGE, "/", v, observed_at=t, source="fake"))

    alerts, problems, _ = evaluate_conditions((), disk(94.9))
    assert not problems
    alerts, problems, _ = evaluate_conditions((), disk(95.0))
    assert [p.label for p in problems] == ["nearly_full"]
    for value in (99.0, 92.0, 90.0):  # still at or above the clear threshold
        alerts2, p, r = evaluate_conditions(alerts, disk(value))
        assert alerts2 == alerts and not p and not r
    _, _, recoveries = evaluate_conditions(alerts, disk(89.9))
    assert [r.topic for r in recoveries] == ["disk:/"]


# ---------------------------------------------------------------- summaries


def test_by_design_gaps_do_not_make_the_picture_unclear() -> None:
    t = at_local(21)
    cpu = measured(Metric.CPU_USAGE, "cpu", 10, observed_at=t, source="fake")

    def gap(name: str, reason: str) -> Observation:
        return not_measured(
            Metric.SERVICE_STATE, name, ObservationStatus.UNKNOWN, reason,
            observed_at=t, source="service_health",
        )  # fmt: skip

    docker = gap("grafana", "not_observable:docker_container")
    assert docker.unobservable_by_design
    calm = snap(t, cpu, svc("backup", ServiceState.ACTIVE, t), docker)
    assert server_summary(INITIAL_REFLECTION, calm)[0] is ServerSummary.CALM
    # A real gap (stale collector data, a bus error) still leaves Maple unsure.
    stale = gap("metrics_collector", "monitor_db:stale_data;systemd_dbus:dbus_timeout")
    assert not stale.unobservable_by_design
    unsure = snap(t, cpu, docker, stale)
    assert server_summary(INITIAL_REFLECTION, unsure)[0] is ServerSummary.UNCLEAR


@pytest.mark.parametrize(
    "real_gap",
    [
        ("service_state", "maplegotchi", "monitor_db:not_recorded;systemd_dbus:dbus_timeout"),
        ("service_state", "backup", "monitor_db:not_recorded;systemd_dbus:permission_denied"),
        (
            "service_state",
            "metrics_collector",
            "monitor_db:stale_data;systemd_dbus:unit_not_loaded",
        ),
        ("memory_usage", "memory", "provider_error:oserror"),
        ("disk_usage", "/", "not_supported_on_platform"),
    ],
)
def test_approved_rule_only_by_design_gaps_are_excused(real_gap: tuple[str, str, str]) -> None:
    """ADR-0021 (APPROVED): not_observable gaps never block calm; real gaps always count."""
    t = at_local(21)
    metric, subject, reason = real_gap
    by_design = [
        not_measured(Metric.SERVICE_STATE, name, ObservationStatus.UNKNOWN,
                     f"not_observable:{why}", observed_at=t, source="service_health")
        for name, why in (("grafana", "docker_container"), ("lycan_watch", "no_systemd_unit"))
    ]  # fmt: skip
    cpu = measured(Metric.CPU_USAGE, "cpu", 10, observed_at=t, source="fake")
    healthy = snap(t, cpu, svc("backup", ServiceState.ACTIVE, t), *by_design)
    assert server_summary(INITIAL_REFLECTION, healthy)[0] is ServerSummary.CALM
    gap = not_measured(
        Metric(metric), subject, ObservationStatus.UNKNOWN, reason, observed_at=t, source="x"
    )
    others = [svc("backup", ServiceState.ACTIVE, t)] if subject != "backup" else []
    assert server_summary(INITIAL_REFLECTION, snap(t, cpu, *others, *by_design, gap))[0] is (
        ServerSummary.UNCLEAR
    )


def test_a_failed_required_service_still_troubles_the_summary() -> None:
    t = at_local(21)
    docker = not_measured(
        Metric.SERVICE_STATE, "grafana", ObservationStatus.UNKNOWN,
        "not_observable:docker_container", observed_at=t, source="service_health",
    )  # fmt: skip
    failed = snap(t, svc("backup", ServiceState.FAILED, t), docker)
    alerts, problems, _ = evaluate_conditions((), failed)
    assert [p.topic for p in problems] == ["service:backup"]
    troubled = replace(INITIAL_REFLECTION, active_alerts=alerts)
    assert server_summary(troubled, failed)[0] is ServerSummary.STILL_TROUBLED


def test_server_summary_is_honest() -> None:
    t = at_local(21)
    calm = snap(
        t,
        measured(Metric.CPU_USAGE, "cpu", 10, observed_at=t, source="fake"),
        svc("jellyfin", ServiceState.ACTIVE, t),
    )
    unclear = snap(
        t,
        measured(Metric.CPU_USAGE, "cpu", 10, observed_at=t, source="fake"),
        svc("jellyfin", None, t),
    )
    nothing = snap(t, svc("jellyfin", None, t))
    assert server_summary(INITIAL_REFLECTION, calm)[0] is ServerSummary.CALM
    assert server_summary(INITIAL_REFLECTION, unclear)[0] is ServerSummary.UNCLEAR
    assert server_summary(INITIAL_REFLECTION, nothing)[0] is ServerSummary.NO_DATA
    assert server_summary(INITIAL_REFLECTION, None)[0] is ServerSummary.NO_DATA
    earlier = replace(INITIAL_REFLECTION, notices_today=1)
    assert server_summary(earlier, calm)[0] is ServerSummary.TROUBLED_EARLIER
    still = replace(INITIAL_REFLECTION, active_alerts=(("service:jellyfin", "failed"),))
    summary, keys = server_summary(still, snap(t, svc("jellyfin", ServiceState.FAILED, t)))
    assert summary is ServerSummary.STILL_TROUBLED and keys == ((Metric.SERVICE_STATE, "jellyfin"),)


# ---------------------------------------------------------------- heartbeat triggers


def tick(
    state_at: datetime,
    *,
    activity: Activity = Activity.IDLE,
    tick_counter: int = 5,
    events: tuple[ActivityChanged, ...] = (),
) -> tuple[MapleState, TickResult, datetime]:
    state = make_state(at=state_at, activity=activity)
    state = replace(state, rng=replace(state.rng, tick_counter=tick_counter))
    now = state_at + PARAMS.heartbeat_interval
    result = heartbeat(state, now, BehaviorInputs(), PARAMS)
    return state, replace(result, events=events or result.events), now


def written_all(triggers: tuple[Trigger, ...]) -> set[tuple[TriggerKind, str]]:
    return {(t.kind, t.topic) for t in triggers}


def triggers_for(rs: ReflectionState, state_at: datetime, **kw: object) -> tuple:  # type: ignore[type-arg]
    """Detect triggers, then mark them all as written (a Brain that always succeeds)."""
    snapshot = kw.pop("snapshot", None)
    state, result, now = tick(state_at, **kw)  # type: ignore[arg-type]
    triggers, detected = heartbeat_triggers(
        rs,
        previous=state,
        result=result,
        snapshot=snapshot,  # type: ignore[arg-type]
        now=now,
        params=PARAMS,
        journal=J,
    )
    return triggers, mark_journaled(detected, triggers, written_all(triggers), now)


def test_first_heartbeat_is_a_milestone() -> None:
    state = make_state(at=BORN)
    result = heartbeat(state, BORN + PARAMS.heartbeat_interval, BehaviorInputs(), PARAMS)
    triggers, rs = heartbeat_triggers(
        INITIAL_REFLECTION,
        previous=state,
        result=result,
        snapshot=None,
        now=BORN + PARAMS.heartbeat_interval,
        params=PARAMS,
        journal=J,
    )
    assert [t.label for t in triggers] == ["first_heartbeat"]
    assert "first_heartbeat" not in rs.milestones  # detection alone marks nothing
    marked = mark_journaled(rs, triggers, written_all(triggers), BORN)
    assert "first_heartbeat" in marked.milestones


def test_long_downtime_writes_only_the_largest_new_milestone() -> None:
    triggers, rs = triggers_for(INITIAL_REFLECTION, BORN + timedelta(days=40, hours=5))
    milestones = [t.label for t in triggers if t.kind is TriggerKind.MILESTONE]
    assert milestones == ["one_month"]
    assert {"one_day", "one_week", "one_month"} <= rs.milestones
    again, _ = triggers_for(rs, BORN + timedelta(days=40, hours=6))
    assert not [t for t in again if t.kind is TriggerKind.MILESTONE]


def woke_event(at: datetime) -> tuple[ActivityChanged, ...]:
    return (ActivityChanged(at, Activity.SLEEP, Activity.READ),)


def test_daily_life_once_per_kind_per_day_and_one_per_heartbeat() -> None:
    rs = replace(INITIAL_REFLECTION, milestones=frozenset({"one_day", "first_heartbeat"}))
    t0 = at_local(7, day=2)
    first, rs = triggers_for(rs, t0, events=woke_event(t0))
    assert [t.label for t in first] == ["woke"]  # "woke" wins; "read" waits (one per heartbeat)
    second, rs = triggers_for(rs, t0 + timedelta(hours=1), events=woke_event(t0))
    assert [t.label for t in second] == []  # already woke today
    reading = (ActivityChanged(t0, Activity.IDLE, Activity.READ),)
    third, rs = triggers_for(rs, t0 + timedelta(hours=2), events=reading)
    assert [t.label for t in third] == ["read"]
    fourth, rs = triggers_for(rs, t0 + timedelta(hours=3), events=reading)
    assert fourth == ()
    next_day, _ = triggers_for(rs, t0 + timedelta(days=1), events=reading)
    assert [t.label for t in next_day] == ["read"]  # new journal day resets


def test_daily_reflection_once_per_day_only_in_window() -> None:
    rs = replace(INITIAL_REFLECTION, milestones=frozenset({"first_heartbeat", "one_day"}))
    before, rs = triggers_for(rs, at_local(20.5, day=2))
    assert not [t for t in before if t.kind is TriggerKind.DAILY_REFLECTION]
    during, rs = triggers_for(rs, at_local(21, day=2))
    assert [t.kind for t in during] == [TriggerKind.DAILY_REFLECTION]
    for hour in (21.5, 23, 24 + 2, 24 + 5.5):  # same journal day, still in the window
        later, rs = triggers_for(rs, at_local(hour, day=2))
        assert not [t for t in later if t.kind is TriggerKind.DAILY_REFLECTION]


def test_no_catch_up_reflections_after_being_offline() -> None:
    rs = replace(
        INITIAL_REFLECTION,
        milestones=frozenset({"first_heartbeat", "one_day", "one_week"}),
        last_reflection_day=date(2026, 1, 2),
        journal_day=date(2026, 1, 2),
    )
    # Offline for days; back at 22:00 on day 9: exactly one reflection, for today.
    triggers, rs = triggers_for(rs, at_local(22, day=9))
    reflections = [t for t in triggers if t.kind is TriggerKind.DAILY_REFLECTION]
    assert len(reflections) == 1 and rs.last_reflection_day == journal_day(
        at_local(22.1, day=9), PARAMS, J
    )
    # Back at noon instead: yesterday's window is gone; nothing is written for it.
    noon, _ = triggers_for(replace(rs, last_reflection_day=None), at_local(12, day=12))
    assert not [t for t in noon if t.kind is TriggerKind.DAILY_REFLECTION]


def test_no_reflection_for_a_day_maple_did_not_live() -> None:
    # Born 02:00 local on day 1 = during journal day 0's window.
    born_night = BORN + timedelta(hours=2)
    state = replace(
        make_state(at=born_night), identity=replace(make_state().identity, born_at=born_night)
    )
    result = heartbeat(state, born_night + timedelta(minutes=5), BehaviorInputs(), PARAMS)
    triggers, _ = heartbeat_triggers(
        INITIAL_REFLECTION,
        previous=state,
        result=result,
        snapshot=None,
        now=born_night + timedelta(minutes=5),
        params=PARAMS,
        journal=J,
    )
    assert not [t for t in triggers if t.kind is TriggerKind.DAILY_REFLECTION]


# ---------------------------------------------------------------- interactions


def accepted(kind: InteractionKind, at: datetime) -> Accepted:
    outcome = apply_interaction(make_state(at=at), kind, at, PARAMS)
    assert isinstance(outcome, Accepted)
    return outcome


def test_interaction_entries_are_spaced_out() -> None:
    t = at_local(8)
    first, rs = interaction_triggers(
        INITIAL_REFLECTION,
        accepted=accepted(InteractionKind.GREET, t),
        now=t,
        params=PARAMS,
        journal=J,
    )
    assert [x.label for x in first] == ["greet"]
    rs = mark_journaled(rs, first, written_all(first), t)
    soon, rs = interaction_triggers(
        rs,
        accepted=accepted(InteractionKind.PET, t),
        now=t + timedelta(minutes=5),
        params=PARAMS,
        journal=J,
    )
    assert soon == () and rs.interactions_today == 2  # counted for the reflection, not journaled
    later, rs = interaction_triggers(
        rs,
        accepted=accepted(InteractionKind.PET, t),
        now=t + timedelta(minutes=30),
        params=PARAMS,
        journal=J,
    )
    assert [x.label for x in later] == ["pet"]


# ---------------------------------------------------------------- detection vs marking


def test_markers_advance_only_for_written_triggers() -> None:
    t = at_local(21, day=2)
    rs = replace(INITIAL_REFLECTION, milestones=frozenset({"first_heartbeat", "one_day"}))
    reading = (ActivityChanged(t, Activity.IDLE, Activity.READ),)
    failed_now = snap(t, svc("jellyfin", ServiceState.FAILED, t))
    triggers, detected = triggers_for_raw(rs, t, events=reading, snapshot=failed_now)
    kinds = {x.kind for x in triggers}
    assert kinds == {TriggerKind.SERVER_PROBLEM, TriggerKind.ACTIVITY, TriggerKind.DAILY_REFLECTION}
    untouched = mark_journaled(detected, triggers, set(), t)
    assert untouched.active_alerts == () and untouched.notices_today == 0
    assert "read" not in untouched.daily_seen and untouched.last_reflection_day is None
    only_problem = mark_journaled(
        detected, triggers, {(TriggerKind.SERVER_PROBLEM, "service:jellyfin")}, t
    )
    assert only_problem.active_alerts == (("service:jellyfin", "failed"),)
    assert only_problem.notices_today == 1
    assert "read" not in only_problem.daily_seen and only_problem.last_reflection_day is None


def test_unwritten_triggers_recur_at_the_next_opportunity() -> None:
    t = at_local(21, day=2)
    rs = replace(INITIAL_REFLECTION, milestones=frozenset({"first_heartbeat", "one_day"}))
    failed_now = snap(t, svc("jellyfin", ServiceState.FAILED, t))
    first, detected = triggers_for_raw(rs, t, snapshot=failed_now)
    rs = mark_journaled(detected, first, set(), t)  # the Brain produced nothing
    t2 = t + PARAMS.heartbeat_interval
    again, _ = triggers_for_raw(rs, t2, snapshot=snap(t2, svc("jellyfin", ServiceState.FAILED, t2)))
    assert {x.kind for x in again} == {TriggerKind.SERVER_PROBLEM, TriggerKind.DAILY_REFLECTION}


def test_marking_a_large_milestone_implies_the_smaller_ones() -> None:
    trigger = Trigger(TriggerKind.MILESTONE, "milestone:one_month", "one_month")
    marked = mark_journaled(INITIAL_REFLECTION, (trigger,), written_all((trigger,)), BORN)
    assert {"one_day", "one_week", "one_month"} <= marked.milestones
    assert "one_year" not in marked.milestones


def triggers_for_raw(rs: ReflectionState, state_at: datetime, **kw: object) -> tuple:  # type: ignore[type-arg]
    snapshot = kw.pop("snapshot", None)
    state, result, now = tick(state_at, **kw)  # type: ignore[arg-type]
    return heartbeat_triggers(
        rs,
        previous=state,
        result=result,
        snapshot=snapshot,  # type: ignore[arg-type]
        now=now,
        params=PARAMS,
        journal=J,
    )


def test_reflection_state_invariants() -> None:
    with pytest.raises(ValueError):
        ReflectionState(interactions_today=-1)
    with pytest.raises(ValueError):
        ReflectionState(active_alerts=(("b", "x"), ("a", "y")))
    with pytest.raises(ValueError):
        JournalParameters(owner_name="R2D2")


def test_unused_tick_result_type_is_exported() -> None:
    assert TickResult.__name__ == "TickResult"
