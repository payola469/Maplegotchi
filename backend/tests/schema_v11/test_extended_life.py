"""Extended canonical life on newly created, current-execution owned roots only."""

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.tasks import ToolRecord
from maplegotchi.core.world.canonical_lifecycle import LifeLoopBlocked
from maplegotchi.persistence.life_record import CanonicalLife
from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime
from maplegotchi.storage.canonical_v11 import CanonicalSnapshot, PersistenceError
from tests.schema_v11 import owned_store as store
from tests.schema_v11.canonical_binding import admit, image_of
from tests.schema_v11.restart_worker import birth_snapshot, life_changes, replace_rows
from tests.schema_v11.test_canonical_boundary import scope as scope
from tests.schema_v11.test_canonical_runtime import advance, facts, port

CASES = (
    (Activity.READ, 0, 80.0, 900),
    (Activity.WRITE, 5, 80.0, 900),
    (Activity.THINK, 7, 80.0, 900),
    (Activity.WALK, 11, 80.0, 900),
    (Activity.IDLE, 12, 80.0, 900),
    (Activity.OBSERVE_SERVER, 13, 80.0, 900),
    (Activity.SLEEP, 0, 80.0, 14400),
    (Activity.REST, 0, 20.0, 900),
)


def seeded(scope: store.OwnedRoot, seed: int, energy: float = 80.0) -> CanonicalPersistenceRuntime:
    binding = port(scope)
    raw = birth_snapshot()
    identity = raw.rows("maple")[0]
    raw = replace_rows(raw, "maple", ((*identity[:3], f"{seed:064x}"),))
    runtime = CanonicalPersistenceRuntime.create(
        binding, admit(raw, binding.catalogs, binding.contexts), schema_version=11
    )
    if energy != 80.0:
        runtime.close()
        store.save(
            scope,
            binding.name,
            life_changes(raw, revision=2, energy=energy),
            expected_revision=1,
            catalogs=binding.catalogs,
            contexts=binding.contexts,
        )
        runtime = CanonicalPersistenceRuntime.restore(binding, schema_version=11)
    return runtime


@pytest.mark.parametrize("activity,seed,energy,seconds", CASES)
def test_all_eight_activities_actual_goal_task_and_restart(
    scope: store.OwnedRoot,
    activity: Activity,
    seed: int,
    energy: float,
    seconds: int,
) -> None:
    runtime = seeded(scope, seed, energy)
    before = runtime.capture()
    started = advance(runtime, before.life.identity.born_at + timedelta(seconds=seconds))
    assert started.life.activity is activity
    assert started.life.active_goal is not None and started.life.record.goal_counter == 1
    assert started.life.record.action_counter == started.life.rng.decision_counter == 1
    assert (
        started.life.task is not None
        if activity in (Activity.READ, Activity.WRITE)
        else started.life.task is None
    )
    saved = store.exact(image_of(started))
    runtime.close()
    runtime = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    assert store.exact(image_of(runtime.capture())) == saved
    # Late arrival and activity completion can share one real transition. No replayed actions.
    until = datetime.fromisoformat(started.life.record.activity_until)
    continued = advance(runtime, until)
    assert continued.life.record.action_counter == 2
    assert started.life.goal_rows[0] in continued.life.goal_rows
    if started.life.travel is not None:
        arrivals = [
            r for r in image_of(continued).rows("action_event") if r[3] == 1 and r[5] == "arrived"
        ]
        assert len(arrivals) == 1 and arrivals[0][6] == started.life.travel.arrives_at.isoformat()
    if activity in (Activity.READ, Activity.WRITE):
        tool_rows = image_of(continued).rows("tool_use")
        completed = [r for r in tool_rows if r[4] == 1 and str(r[7]).endswith("_completed")]
        assert len(completed) == 1
        if activity is Activity.WRITE:
            documents = image_of(continued).rows("document")
            assert len(documents) == 1 and documents[0][5]
    after_bytes = scope.check("maple.db").read_bytes()
    assert advance(runtime, until) is continued
    assert scope.check("maple.db").read_bytes() == after_bytes
    runtime.close()
    reopened = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    assert reopened.capture() == continued
    reopened.close()


def test_stationary_critical_suspends_goal_and_finishes_old_task_once(
    scope: store.OwnedRoot,
) -> None:
    runtime = seeded(scope, 0)
    started = advance(runtime, runtime.capture().life.identity.born_at + timedelta(minutes=15))
    assert started.life.task is not None and started.life.travel is not None
    arrived = advance(runtime, started.life.travel.arrives_at)
    before_goal = arrived.life.active_goal
    assert before_goal is not None
    binding = port(scope)
    now = datetime.fromisoformat(arrived.life.record.last_updated_at) + timedelta(
        microseconds=100000
    )
    interrupted = runtime.step(
        now,
        BehaviorInputs(server_attention=1),
        CoreParameters(),
        facts(arrived),
        expected_revision=arrived.life.record.revision,
        task_effects=binding.task_effects,
    )
    assert interrupted.life.active_goal is None and interrupted.life.suspended_goal == before_goal
    assert interrupted.life.record.action_priority == "critical"
    assert interrupted.life.task is None
    failed = [
        r for r in image_of(interrupted).rows("tool_use") if r[4] == 1 and r[7] == "read_failed"
    ]
    assert len(failed) == 1 and failed[0][12] == "interrupted"
    runtime.close()
    runtime = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    assert runtime.capture() == interrupted
    finished = advance(runtime, datetime.fromisoformat(interrupted.life.record.activity_until))
    assert finished.life.suspended_goal is None
    events = image_of(finished).rows("timeline_event")
    assert sum(r[4] == "goal_suspended" for r in events) == 1
    assert sum(r[4] in ("goal_resumed", "goal_abandoned") for r in events) == 1
    assert before_goal.id in {g.id for g in finished.life.goals}
    runtime.close()


def test_task_read_context_cannot_use_a_stale_revision(scope: store.OwnedRoot) -> None:
    runtime = seeded(scope, 0)
    stale = runtime.capture()
    after = advance(runtime, stale.life.identity.born_at + timedelta(minutes=15))
    binding = port(scope)
    with pytest.raises(PersistenceError, match="revision"):
        binding.task_catalog(stale)
    with pytest.raises(PersistenceError, match="revision"):
        binding.task_effects(stale, after.life, after.life.identity.born_at)
    assert runtime.capture() == after
    runtime.close()


def test_missing_task_effects_fails_before_save(scope: store.OwnedRoot) -> None:
    runtime = seeded(scope, 0)
    before = runtime.capture()
    with pytest.raises(LifeLoopBlocked, match="task_effects"):
        runtime.step(
            before.life.identity.born_at + timedelta(minutes=15),
            BehaviorInputs(),
            CoreParameters(),
            facts(before),
            expected_revision=before.life.record.revision,
        )
    assert runtime.capture() is before
    assert port(scope).load(schema_version=11) == before
    runtime.close()


@pytest.mark.parametrize("activity,seed,energy,seconds", CASES)
def test_legacy_read_projection_is_truthful_readonly_and_needs_explicit_origin(
    scope: store.OwnedRoot,
    activity: Activity,
    seed: int,
    energy: float,
    seconds: int,
) -> None:
    from maplegotchi.core.world.legacy_projection import PointRef
    from maplegotchi.persistence.legacy_admission import CompatibilityRefusal

    runtime = seeded(scope, seed, energy)
    old = runtime.capture()
    origin = PointRef(old.life.record.point_host, old.life.record.point_id)
    started = advance(runtime, old.life.identity.born_at + timedelta(seconds=seconds))
    travel = started.life.travel
    now = datetime.fromisoformat(started.life.record.last_updated_at)
    before_bytes = scope.check("maple.db").read_bytes()
    projected = runtime.legacy(facts(started), now, origin=origin if travel else None)
    assert projected.presentation == facts(started)
    assert projected.presentation.goal == started.life.active_goal
    assert projected.presentation.task == started.life.task
    if travel is not None:
        assert projected.route is not None
        assert projected.route.departed_at == travel.departed_at
        assert projected.route.arrives_at == travel.arrives_at
        with pytest.raises(CompatibilityRefusal, match="projection"):
            runtime.legacy(facts(started), now)
    assert runtime.capture() is started
    assert scope.check("maple.db").read_bytes() == before_bytes
    runtime.close()
    reopened = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    assert reopened.legacy(facts(started), now, origin=origin if travel else None) == projected
    assert reopened.capture() == started
    reopened.close()


@pytest.mark.parametrize("phase", ["before_commit", "after_commit"])
def test_writer_task_document_provenance_and_state_commit_atomically(
    scope: store.OwnedRoot,
    phase: str,
) -> None:
    runtime = seeded(scope, 5)
    started = advance(runtime, runtime.capture().life.identity.born_at + timedelta(minutes=15))
    assert started.life.activity is Activity.WRITE and started.life.task is not None
    runtime.close()

    def fail(at: str) -> None:
        if at == phase:
            raise PersistenceError("uncertain")

    binding = port(scope, inject=fail)
    runtime = CanonicalPersistenceRuntime.restore(binding, schema_version=11)
    with pytest.raises(PersistenceError, match="uncertain"):
        advance(runtime, datetime.fromisoformat(started.life.record.activity_until))
    with pytest.raises(PersistenceError, match="uncertain"):
        runtime.capture()
    runtime.close()
    reopened = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    after = reopened.capture()
    documents = image_of(after).rows("document")
    completed = [
        r for r in image_of(after).rows("tool_use") if r[4] == 1 and r[7] == "write_completed"
    ]
    assert len(documents) == len(completed) == int(phase == "after_commit")
    if phase == "before_commit":
        assert store.exact(image_of(after)) == store.exact(image_of(started))
    else:
        assert after.life.record.revision == started.life.record.revision + 1
        assert completed[0][14] == documents[0][0]
    reopened.close()


@pytest.mark.parametrize("corruption", ["missing", "duplicate", "foreign_action", "foreign_goal"])
def test_bad_task_capability_cannot_install_state_without_correct_provenance(
    scope: store.OwnedRoot,
    corruption: str,
) -> None:
    runtime = seeded(scope, 0)
    binding = port(scope)
    before = runtime.capture()
    old_bytes = scope.check("maple.db").read_bytes()

    def bad(old: CanonicalSnapshot, after: CanonicalLife, now: datetime) -> tuple[ToolRecord, ...]:
        records = binding.task_effects(old, after, now)
        assert records
        if corruption == "missing":
            return ()
        if corruption == "duplicate":
            return (*records, *records)
        if corruption == "foreign_action":
            return (replace(records[0], action_id=999),)
        return (replace(records[0], goal_id=999),)

    with pytest.raises(PersistenceError, match="invalid"):
        runtime.step(
            before.life.identity.born_at + timedelta(minutes=15),
            BehaviorInputs(),
            CoreParameters(),
            facts(before),
            expected_revision=before.life.record.revision,
            task_effects=bad,
        )
    assert runtime.capture() is before
    assert scope.check("maple.db").read_bytes() == old_bytes
    runtime.close()


def test_expired_suspended_goal_is_abandoned_once_after_response(scope: store.OwnedRoot) -> None:
    runtime = seeded(scope, 0)
    started = advance(runtime, runtime.capture().life.identity.born_at + timedelta(minutes=15))
    assert started.life.travel is not None
    arrived = advance(runtime, started.life.travel.arrives_at)
    goal = arrived.life.active_goal
    assert goal is not None
    now = datetime.fromisoformat(arrived.life.record.last_updated_at) + timedelta(seconds=1)
    binding = port(scope)
    response = runtime.step(
        now,
        BehaviorInputs(server_attention=1),
        CoreParameters(),
        facts(arrived),
        expected_revision=arrived.life.record.revision,
        task_effects=binding.task_effects,
    )
    assert response.life.suspended_goal == goal
    runtime.close()
    runtime = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    after = advance(
        runtime,
        max(goal.horizon_until, datetime.fromisoformat(response.life.record.activity_until))
        + timedelta(seconds=1),
    )
    assert after.life.suspended_goal is None
    abandoned = [r for r in image_of(after).rows("timeline_event") if r[4] == "goal_abandoned"]
    assert len(abandoned) == 1 and '"reason":"expired"' in str(abandoned[0][6])
    assert goal.id in {g.id for g in after.life.goals}
    assert advance(runtime, datetime.fromisoformat(after.life.record.last_updated_at)) is after
    runtime.close()


@pytest.mark.parametrize("late_seconds", [0, 1], ids=["on_time", "late"])
def test_arrival_and_critical_in_one_tick_keep_original_action_audit(
    scope: store.OwnedRoot, late_seconds: int
) -> None:
    """Known arrival origin: preserve old READ facts when starting the urgent response."""
    from maplegotchi.core.world.legacy_projection import PointRef

    runtime = seeded(scope, 0)
    try:
        first = runtime.capture()
        selected = advance(runtime, first.life.identity.born_at + timedelta(minutes=15))
        assert selected.life.activity is Activity.READ and selected.life.travel is not None
        arrival = selected.life.travel.arrives_at
        now = arrival + timedelta(seconds=late_seconds)
        original = runtime.legacy(
            facts(selected),
            now,
            origin=PointRef(first.life.record.point_host, first.life.record.point_id),
        ).point
        changed = runtime.step(
            now,
            BehaviorInputs(server_attention=1),
            CoreParameters(),
            facts(selected),
            expected_revision=selected.life.record.revision,
            task_effects=port(scope).task_effects,
        )
        assert changed.life.record.action_priority == "critical"
        assert changed.life.activity is Activity.OBSERVE_SERVER
        assert changed.life.record.action_counter == selected.life.record.action_counter + 1
        rows = [
            r
            for r in image_of(changed).rows("action_event")
            if r[3] == selected.life.record.action_counter
        ]
        arrivals = [r for r in rows if r[5] == "arrived"]
        starts = [r for r in rows if r[5] == "activity_started"]
        import json

        assert len(arrivals) == len(starts) == 1
        assert arrivals[0][6] == starts[0][6] == arrival.isoformat()
        assert json.loads(str(arrivals[0][8]))["point"] == original.id
        assert json.loads(str(starts[0][8]))["point"] == original.id
        assert json.loads(str(starts[0][8]))["activity"] == "read"
        assert changed.life.suspended_goal == selected.life.active_goal
        failed = [
            r
            for r in image_of(changed).rows("tool_use")
            if r[4] == selected.life.record.action_counter and r[7] == "read_failed"
        ]
        assert len(failed) == 1 and failed[0][12] == "interrupted"
        assert (
            runtime.step(
                now,
                BehaviorInputs(server_attention=1),
                CoreParameters(),
                facts(changed),
                expected_revision=changed.life.record.revision,
                task_effects=port(scope).task_effects,
            )
            is changed
        )
        runtime.close()
        runtime = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
        assert runtime.capture() == changed
    finally:
        runtime.close()


def test_late_arrival_and_ordinary_completion_keep_old_activity_payload(
    scope: store.OwnedRoot,
) -> None:
    import json

    from maplegotchi.core.world.legacy_projection import PointRef

    runtime = seeded(scope, 0)
    try:
        first = runtime.capture()
        selected = advance(runtime, first.life.identity.born_at + timedelta(minutes=15))
        assert selected.life.activity is Activity.READ and selected.life.travel is not None
        now = datetime.fromisoformat(selected.life.record.activity_until)
        point = runtime.legacy(
            facts(selected),
            now,
            origin=PointRef(first.life.record.point_host, first.life.record.point_id),
        ).point
        changed = advance(runtime, now)
        assert changed.life.record.action_counter == 2
        for kind in ("arrived", "activity_started"):
            rows = [r for r in image_of(changed).rows("action_event") if r[3] == 1 and r[5] == kind]
            assert len(rows) == 1 and rows[0][6] == selected.life.travel.arrives_at.isoformat()
            payload = json.loads(str(rows[0][8]))
            assert payload["point"] == point.id
            if kind == "activity_started":
                assert payload["activity"] == "read"
        completed = [
            r for r in image_of(changed).rows("tool_use") if r[4] == 1 and r[7] == "read_completed"
        ]
        assert len(completed) == 1
    finally:
        runtime.close()
