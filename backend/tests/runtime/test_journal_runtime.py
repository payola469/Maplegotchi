"""The journal in the running system: persisted, grounded, deduplicated, restart-safe."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from maplegotchi.brain.rule_brain import RuleBrain
from maplegotchi.core.journal import (
    BrainContext,
    BrainKind,
    JournalCategory,
    JournalDraft,
    TriggerKind,
)
from maplegotchi.core.observations import Metric, ObservationStatus, ServiceState
from maplegotchi.core.reflection import ReflectionState
from maplegotchi.core.state import InteractionKind
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.demo import at, run_demo_day
from maplegotchi.runtime.life import ExternalBrainNotAllowed, LifeRuntime
from maplegotchi.runtime.senses import Senses
from maplegotchi.sensors.fake import FakeHostProbe
from maplegotchi.sensors.service_health.fake import FakeServiceHealth
from maplegotchi.sensors.service_health.interface import INTENDED_SERVICES, ServiceReading
from maplegotchi.storage.datadir import DataDir
from maplegotchi.storage.repositories import LifeRepository
from tests.persistence_support import PARAMS, TICK, make_data_dir, raw_db

A = ObservationStatus.AVAILABLE
SEED = "7a" * 32


def senses(jellyfin: ServiceState | None = ServiceState.ACTIVE) -> Senses:
    readings = {
        t.service_id: ServiceReading(A, state=ServiceState.ACTIVE) for t in INTENDED_SERVICES
    }
    readings["jellyfin"] = (
        ServiceReading(A, state=jellyfin)
        if jellyfin is not None
        else ServiceReading(ObservationStatus.UNKNOWN, reason="not_surveyed")
    )
    return Senses(FakeHostProbe(), (FakeServiceHealth(readings),))


class Life:
    """A Maple born at 05:00 local on day 1, driven heartbeat by heartbeat."""

    def __init__(self, tmp_path: Path, name: str = "life") -> None:
        self.data_dir = make_data_dir(tmp_path, name)
        self.clock = FakeClock(at(5))
        self.runtime = self.open()

    def open(self) -> LifeRuntime:
        return LifeRuntime.open(self.data_dir, self.clock, PARAMS, new_seed=lambda: SEED)

    def restart(self) -> None:
        self.runtime.close()
        self.runtime = self.open()

    def beat(self, count: int = 1, jellyfin: ServiceState | None = ServiceState.ACTIVE) -> None:
        for _ in range(count):
            now = self.clock.advance(TICK)
            assert self.runtime.heartbeat_if_due(senses(jellyfin).observe(now)) is not None

    def run_until(
        self, moment: datetime, jellyfin: ServiceState | None = ServiceState.ACTIVE
    ) -> None:
        while self.clock.now() + TICK <= moment:
            self.beat(jellyfin=jellyfin)

    def rs(self) -> ReflectionState:
        """Current journal state (a call, so type checkers don't narrow it across steps)."""
        return self.runtime.reflection_state

    def entries(self, trigger: TriggerKind | None = None) -> list:  # type: ignore[type-arg]
        return [s for s in self.runtime.journal() if trigger is None or s.entry.trigger is trigger]


def test_calm_heartbeats_do_not_spam(tmp_path: Path) -> None:
    life = Life(tmp_path)
    life.run_until(at(20.5))  # 15.5 calm hours, ~186 heartbeats
    entries = life.entries()
    beats = life.runtime.state.ticks_lived
    assert beats > 180
    assert len(entries) <= 8, [e.entry.text for e in entries]
    assert not life.entries(TriggerKind.SERVER_PROBLEM)
    kinds = [e.entry.topic for e in life.entries(TriggerKind.ACTIVITY)]
    assert len(kinds) == len(set(kinds))  # each daily-life kind at most once
    life.runtime.close()


def test_persistent_failure_journaled_once_then_recovery_then_again(tmp_path: Path) -> None:
    life = Life(tmp_path)
    life.run_until(at(10))
    life.beat(12, jellyfin=ServiceState.FAILED)  # an hour of failure
    life.restart()  # restart in the middle of it
    life.beat(6, jellyfin=ServiceState.FAILED)
    problems = life.entries(TriggerKind.SERVER_PROBLEM)
    assert len(problems) == 1 and "Jellyfin" in problems[0].entry.text
    life.beat(3, jellyfin=None)  # unknown neither recovers nor re-alerts
    assert len(life.entries(TriggerKind.SERVER_RECOVERY)) == 0
    life.beat(3, jellyfin=ServiceState.ACTIVE)
    recoveries = life.entries(TriggerKind.SERVER_RECOVERY)
    assert len(recoveries) == 1 and "back to normal" in recoveries[0].entry.text
    life.beat(2, jellyfin=ServiceState.FAILED)  # a new failure is a new event
    assert len(life.entries(TriggerKind.SERVER_PROBLEM)) == 2
    life.runtime.close()


def test_entries_reference_the_observations_they_interpret(tmp_path: Path) -> None:
    life = Life(tmp_path)
    life.run_until(at(10))
    life.beat(jellyfin=ServiceState.FAILED)
    [problem] = life.entries(TriggerKind.SERVER_PROBLEM)
    [oid] = problem.observation_ids
    stored = {o.id: o for o in life.runtime.observations(tick_id=problem.entry.tick_id)}
    fact = stored[oid].observation
    assert (fact.metric, fact.subject, fact.state) == (
        Metric.SERVICE_STATE,
        "jellyfin",
        ServiceState.FAILED,
    )
    life.restart()
    [again] = life.entries(TriggerKind.SERVER_PROBLEM)
    assert again.observation_ids == (oid,)  # stable across restarts
    life.runtime.close()


def test_daily_reflection_once_per_day_across_restarts(tmp_path: Path) -> None:
    life = Life(tmp_path)
    life.run_until(at(21 + 10 / 60))
    assert len(life.entries(TriggerKind.DAILY_REFLECTION)) == 1
    life.restart()
    life.run_until(at(23))
    life.restart()
    life.run_until(at(24 + 5.5))  # past midnight, same journal day
    assert len(life.entries(TriggerKind.DAILY_REFLECTION)) == 1
    life.run_until(at(24 + 21.2))  # next evening
    reflections = life.entries(TriggerKind.DAILY_REFLECTION)
    assert len(reflections) == 2
    assert reflections[0].entry.created_at.date() != reflections[1].entry.created_at.date()
    life.runtime.close()


def test_offline_through_the_window_means_no_catch_up(tmp_path: Path) -> None:
    life = Life(tmp_path)
    life.run_until(at(20))
    life.runtime.close()
    life.clock.set(at(24 * 3 + 12))  # back at noon, three days later
    life.runtime = life.open()
    life.beat(3)
    assert life.entries(TriggerKind.DAILY_REFLECTION) == []
    life.run_until(at(24 * 3 + 21.2))
    assert len(life.entries(TriggerKind.DAILY_REFLECTION)) == 1
    life.runtime.close()


def test_interactions_journal_and_rejections_do_not(tmp_path: Path) -> None:
    life = Life(tmp_path)
    life.run_until(at(9))
    assert life.runtime.interact(InteractionKind.PET).__class__.__name__ == "Accepted"
    assert life.runtime.interact(InteractionKind.PET).__class__.__name__ == "Rejected"
    life.clock.advance(timedelta(minutes=1))
    life.runtime.interact(InteractionKind.GREET)  # accepted, but inside the 30-minute gap
    entries = life.entries(TriggerKind.INTERACTION)
    assert [e.entry.text for e in entries] == ["Paolo stopped by and gave me a little pat."]
    assert entries[0].entry.category is JournalCategory.INTERACTION
    assert entries[0].observation_ids == () and entries[0].entry.tick_id is None
    life.runtime.close()


def test_pet_while_sleeping(tmp_path: Path) -> None:
    life = Life(tmp_path)
    life.run_until(at(23.5))
    while life.runtime.state.activity.value != "sleep":
        life.beat()
    life.clock.advance(timedelta(minutes=1))
    life.runtime.interact(InteractionKind.PET)
    last = life.entries(TriggerKind.INTERACTION)[-1].entry
    assert last.text == "I felt a gentle pat while I was sleeping."
    life.runtime.close()


def test_journal_is_append_only_in_the_database(tmp_path: Path) -> None:
    life = Life(tmp_path)
    life.run_until(at(10))
    life.beat(jellyfin=ServiceState.FAILED)
    life.runtime.close()
    with raw_db(life.data_dir) as conn:
        for sql in (
            "UPDATE journal_entry SET text = 'rewritten'",
            "DELETE FROM journal_entry",
            "UPDATE journal_entry_observation SET observation_id = 1",
            "DELETE FROM journal_entry_observation",
            "DELETE FROM journal_state",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(sql)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO journal_entry (maple_id, revision, created_at, category,"
                " trigger_kind, topic, text, importance, brain_kind, brain_name,"
                " brain_version, template_id, activity, expression) VALUES (1, 1,"
                " '2026-01-01T00:00:00+00:00', 'reflection', 'daily_reflection', 't',"
                " 'Day' || char(10) || 'two', 'low', 'rule', 'x', '1', 't', 'idle', 'calm')"
            )


def test_journal_write_failure_rolls_back_the_heartbeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    life = Life(tmp_path)
    life.run_until(at(10))
    before, revision = life.runtime.state, life.runtime.revision

    def explode(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(LifeRepository, "_insert_journal_entry", explode)
    life.clock.advance(TICK)
    with pytest.raises(OSError):
        life.runtime.heartbeat_if_due(senses(ServiceState.FAILED).observe(life.clock.now()))
    assert life.runtime.state == before and life.runtime.revision == revision
    monkeypatch.undo()
    life.restart()
    assert life.entries(TriggerKind.SERVER_PROBLEM) == []
    assert life.rs().active_alerts == ()  # alert state rolled back too
    life.runtime.close()


def test_a_failing_brain_costs_words_not_life(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(self: RuleBrain, context: BrainContext) -> Sequence[JournalDraft]:
        raise RuntimeError("template bug")

    monkeypatch.setattr(RuleBrain, "compose_journal", broken)
    life = Life(tmp_path)
    life.run_until(at(10))
    assert life.runtime.state.ticks_lived > 50
    assert life.entries() == []
    life.runtime.close()


class ExternalStub:
    kind = BrainKind.EXTERNAL
    name = "cloud_llm"
    version = "1"

    def compose_journal(self, context: BrainContext) -> Sequence[JournalDraft]:
        return ()


class Impostor(ExternalStub):
    kind = BrainKind.RULE  # claims to be the RuleBrain


class RuleBrainSubclass(RuleBrain):
    pass


def test_external_brain_may_run(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    runtime = LifeRuntime.open(
        data_dir,
        FakeClock(at(5)),
        PARAMS,
        new_seed=lambda: SEED,
        brain=ExternalStub(),
    )
    runtime.close()


@pytest.mark.parametrize("brain", [Impostor(), RuleBrainSubclass()])
def test_only_builtin_rule_brain_may_claim_rule_kind(tmp_path: Path, brain: object) -> None:
    data_dir = make_data_dir(tmp_path)
    with pytest.raises(ExternalBrainNotAllowed):
        LifeRuntime.open(
            data_dir,
            FakeClock(at(5)),
            PARAMS,
            new_seed=lambda: SEED,
            brain=brain,  # type: ignore[arg-type]
        )
    assert list(data_dir.root.iterdir()) == []


def test_every_entry_is_labelled_with_its_brain(tmp_path: Path) -> None:
    life = Life(tmp_path)
    life.run_until(at(22))
    entries = life.entries()
    assert entries
    assert {(e.entry.brain_kind, e.entry.brain_name, e.entry.brain_version) for e in entries} == {
        (BrainKind.RULE, "rule_brain", "1")
    }
    life.runtime.close()


# ---------------------------------------------------------------- demo day


def _signature(data_dir: DataDir) -> tuple[object, ...]:
    report = run_demo_day(data_dir)
    return (
        tuple((e.entry, e.observation_ids) for e in report.journal),
        tuple(e.event for e in report.timeline),
        len(report.observations),
        report.restarts,
    )


def test_demo_day_is_deterministic_and_shows_the_story(tmp_path: Path) -> None:
    first = run_demo_day(make_data_dir(tmp_path, "a"))
    assert _signature(make_data_dir(tmp_path, "b")) == _signature(make_data_dir(tmp_path, "c"))
    triggers = [e.entry.trigger for e in first.journal]
    assert triggers.count(TriggerKind.SERVER_PROBLEM) == 1  # 18 failing heartbeats, one entry
    assert triggers.count(TriggerKind.SERVER_RECOVERY) == 1
    assert triggers.count(TriggerKind.DAILY_REFLECTION) == 1  # despite a restart after it
    assert TriggerKind.INTERACTION in triggers and TriggerKind.MILESTONE in triggers
    assert first.restarts == 2
    assert len(first.journal) < first.heartbeats / 10  # no spam


def _day_with_restarts(tmp_path: Path, name: str, restart_at: set[int]) -> tuple[object, ...]:
    life = Life(tmp_path, name)
    for step in range(1, 12 * 20):  # 05:00 -> 01:00 next day
        if step in restart_at:
            life.restart()
        now = life.clock.advance(TICK)
        failing = at(13) <= now < at(14)
        life.runtime.heartbeat_if_due(
            senses(ServiceState.FAILED if failing else ServiceState.ACTIVE).observe(now)
        )
        if step in (40, 41, 150):
            life.runtime.interact(InteractionKind.PET)
    journal = tuple((e.entry, e.observation_ids) for e in life.runtime.journal())
    state, reflection = life.runtime.state, life.rs()
    life.runtime.close()
    return journal, state, reflection


def test_journal_with_restarts_equals_journal_without(tmp_path: Path) -> None:
    continuous = _day_with_restarts(tmp_path, "continuous", set())
    assert len(continuous[0]) >= 6  # type: ignore[arg-type]
    for name, plan in {
        "one": {97},
        "many": set(range(10, 240, 23)),
        "around_failure": {95, 96, 110},
    }.items():
        assert _day_with_restarts(tmp_path, name, plan) == continuous, name


# ---------------------------------------------------------------- Brain failure semantics


class BrainSwitch:
    """Makes the built-in RuleBrain fail (raise, or return nothing) on demand."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.mode = "ok"
        original = RuleBrain.compose_journal
        switch = self

        def compose(self: RuleBrain, context: BrainContext) -> Sequence[JournalDraft]:
            if switch.mode == "raise":
                raise RuntimeError("brain failure")
            if switch.mode == "empty":
                return ()
            return original(self, context)

        monkeypatch.setattr(RuleBrain, "compose_journal", compose)


@pytest.mark.parametrize("failure", ["raise", "empty"])
def test_failed_problem_notice_is_not_marked_and_is_written_later(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    brain = BrainSwitch(monkeypatch)
    life = Life(tmp_path)
    life.run_until(at(10))
    ticks_before = life.runtime.state.ticks_lived

    brain.mode = failure
    life.beat(3, jellyfin=ServiceState.FAILED)
    assert life.entries(TriggerKind.SERVER_PROBLEM) == []  # no entry written
    rs = life.rs()
    assert rs.active_alerts == () and rs.notices_today == 0  # dedup not advanced
    assert life.runtime.state.ticks_lived == ticks_before + 3  # life still went on
    failed_facts = [
        o
        for o in life.runtime.observations()
        if o.observation.subject == "jellyfin" and o.observation.state is ServiceState.FAILED
    ]
    assert len(failed_facts) == 3  # observations were still committed

    life.restart()  # the unmarked state survives a restart too
    brain.mode = "ok"
    life.beat(jellyfin=ServiceState.FAILED)
    [problem] = life.entries(TriggerKind.SERVER_PROBLEM)
    assert "Jellyfin" in problem.entry.text
    assert life.rs().active_alerts == (("service:jellyfin", "failed"),)
    life.beat(4, jellyfin=ServiceState.FAILED)
    assert len(life.entries(TriggerKind.SERVER_PROBLEM)) == 1  # then normal dedup
    life.runtime.close()


def test_failed_recovery_notice_keeps_the_alert_until_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    brain = BrainSwitch(monkeypatch)
    life = Life(tmp_path)
    life.run_until(at(10))
    life.beat(jellyfin=ServiceState.FAILED)
    brain.mode = "raise"
    life.beat(2, jellyfin=ServiceState.ACTIVE)
    assert life.entries(TriggerKind.SERVER_RECOVERY) == []
    assert life.rs().active_alerts == (("service:jellyfin", "failed"),)
    brain.mode = "ok"
    life.beat(jellyfin=ServiceState.ACTIVE)
    assert len(life.entries(TriggerKind.SERVER_RECOVERY)) == 1
    assert life.rs().active_alerts == ()
    life.runtime.close()


def test_failed_daily_reflection_is_not_marked_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    brain = BrainSwitch(monkeypatch)
    life = Life(tmp_path)
    life.run_until(at(20.9))
    brain.mode = "raise"
    life.run_until(at(21.5))  # several heartbeats inside the window, brain down
    assert life.entries(TriggerKind.DAILY_REFLECTION) == []
    assert life.rs().last_reflection_day is None
    life.restart()
    brain.mode = "ok"
    life.beat()
    assert len(life.entries(TriggerKind.DAILY_REFLECTION)) == 1
    day = life.rs().last_reflection_day
    assert day is not None
    life.run_until(at(24 + 5))
    assert len(life.entries(TriggerKind.DAILY_REFLECTION)) == 1  # and still once per day
    life.runtime.close()


def test_failed_interaction_entry_does_not_start_the_spacing_timer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    brain = BrainSwitch(monkeypatch)
    life = Life(tmp_path)
    life.run_until(at(9))
    brain.mode = "raise"
    assert life.runtime.interact(InteractionKind.GREET).__class__.__name__ == "Accepted"
    rs = life.rs()
    assert (
        rs.last_interaction_entry_at is None and rs.interactions_today == 1
    )  # counted, not marked
    assert life.entries(TriggerKind.INTERACTION) == []
    brain.mode = "ok"
    life.clock.advance(timedelta(minutes=1))  # well inside the 30-minute gap
    life.runtime.interact(InteractionKind.PET)
    assert len(life.entries(TriggerKind.INTERACTION)) == 1
    assert life.rs().interactions_today == 2
    life.runtime.close()


def test_failed_milestone_and_daily_life_are_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    brain = BrainSwitch(monkeypatch)
    brain.mode = "raise"
    life = Life(tmp_path)
    life.beat(3)
    assert life.entries() == []
    assert life.rs().milestones == frozenset()
    assert life.rs().daily_seen == frozenset()
    brain.mode = "ok"
    life.beat()
    labels = [e.entry.topic for e in life.entries(TriggerKind.MILESTONE)]
    assert labels == ["milestone:first_heartbeat"]
    life.runtime.close()


def test_schema_accepts_grounded_numbers_but_not_multiline_text(tmp_path: Path) -> None:
    life = Life(tmp_path)
    life.beat()
    life.runtime.close()
    insert = (
        "INSERT INTO journal_entry (maple_id, revision, created_at, category, trigger_kind, topic,"
        " text, importance, brain_kind, brain_name, brain_version, template_id, activity,"
        " expression) VALUES (1, 2, '2026-01-01T00:00:00+00:00', 'server_notice',"
        " 'server_problem', 'disk:/', ?, 'high', 'external', 'future_brain', '1', 't', 'idle',"
        " 'calm')"
    )
    with raw_db(life.data_dir) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(insert, ("The disk was at 96% at 21:00.",))  # allowed by schema v3
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(insert, ("two\nlines",))
