"""Decisions and goals through the persisted single-writer runtime (ADR-0026)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.observations import (
    Metric,
    Observation,
    ObservationSnapshot,
    ObservationStatus,
    ServiceState,
)
from maplegotchi.core.priority import Priority
from maplegotchi.core.timeline import GoalStarted, GoalSuspended
from maplegotchi.storage.db import PRE_MIGRATION_DIR
from maplegotchi.storage.migrations import MIGRATIONS, migrate, schema_version
from tests.persistence_support import new_life, open_runtime, raw_db

TICK = timedelta(seconds=300)


def test_decision_persists_its_goal_and_survives_a_restart(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    clock.advance(timedelta(minutes=16))  # the first 15-minute idle has ended
    assert runtime.decision_is_due()
    committed = runtime.decide_committed(BehaviorInputs())
    assert committed is not None
    goal = committed.outcome.started_goal
    assert goal is not None and runtime.state.goal == goal
    assert not runtime.decision_is_due()
    assert runtime.decide_committed() is None  # nothing due: nothing written
    started = [e.event for e in runtime.timeline() if isinstance(e.event, GoalStarted)]
    assert [e.goal for e in started] == [goal]
    state = runtime.state
    runtime.close()
    with open_runtime(data_dir, clock) as reopened:
        assert reopened.state == state
        assert reopened.state.goal == goal
    with raw_db(data_dir) as conn:
        row = conn.execute("SELECT id, goal_type, source FROM goal").fetchall()
        assert row == [(goal.id, goal.type.value, "rule")]


def test_heartbeats_and_decisions_interleave_coherently(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    for _ in range(60):
        clock.advance(timedelta(minutes=1))
        if runtime.arrival_due():
            runtime.settle_committed()
        if runtime.decision_is_due():
            runtime.decide_committed(BehaviorInputs())
        runtime.heartbeat_if_due()
    state = runtime.state
    assert state.goal is not None
    assert state.rng.decision_counter >= 2
    runtime.close()
    with open_runtime(data_dir, clock) as reopened:
        assert reopened.state == state


def test_critical_interruption_is_persisted(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    clock.advance(timedelta(minutes=16))
    runtime.decide_committed(BehaviorInputs())
    clock.advance(TICK)
    alarm = _alarm_snapshot(clock.now())
    tick = runtime.heartbeat_if_due(alarm)
    assert tick is not None
    assert runtime.state.action_priority is Priority.CRITICAL
    assert any(isinstance(e, GoalSuspended) for e in tick.events)
    state = runtime.state
    runtime.close()
    with open_runtime(data_dir, clock) as reopened:
        assert reopened.state == state
        assert reopened.state.critical_since == state.critical_since


def test_v4_database_upgrades_to_v5_with_a_snapshot(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    runtime.close()
    with raw_db(data_dir) as conn:  # take this database back to exactly v4
        conn.execute("DROP TABLE memory_event")  # v7
        conn.execute("DROP TABLE memory")
        for trigger in ("document_append_only_update", "document_append_only_delete",
                        "tool_use_append_only_update", "tool_use_append_only_delete"):  # fmt: skip
            conn.execute(f"DROP TRIGGER {trigger}")
        conn.execute("DROP TABLE tool_use")
        conn.execute("DROP TABLE document")
        for column in ("task_tool", "task_target", "task_title", "task_category",
                       "critical_since"):  # fmt: skip
            conn.execute(f"ALTER TABLE life_state DROP COLUMN {column}")
        conn.execute("PRAGMA user_version = 4")
    with open_runtime(data_dir, clock) as reopened:
        assert reopened.state.critical_since is None
    with raw_db(data_dir) as conn:
        assert schema_version(conn) == len(MIGRATIONS)
    copies = list((data_dir.root / PRE_MIGRATION_DIR).glob("maple.v4.*.db"))
    assert len(copies) == 1
    copy = sqlite3.connect(copies[0], isolation_level=None)
    try:
        assert schema_version(copy) == 4
        assert migrate(copy, MIGRATIONS[:4]) == 4
    finally:
        copy.close()


def _alarm_snapshot(now: datetime) -> ObservationSnapshot:
    failed = Observation(
        metric=Metric.SERVICE_STATE,
        subject="backup",
        status=ObservationStatus.AVAILABLE,
        observed_at=now,
        source="fake",
        state=ServiceState.FAILED,
    )
    return ObservationSnapshot(now, (failed,))
