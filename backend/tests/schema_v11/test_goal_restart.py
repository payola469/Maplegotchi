"""Real-process goal/task continuity and atomic interrupt completion evidence."""

import json
from datetime import datetime

import pytest

from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime
from tests.schema_v11 import owned_store as store
from tests.schema_v11.canonical_binding import image_of
from tests.schema_v11.life_interrupt import continue_response, initial, interrupt_read
from tests.schema_v11.restart_worker import digest, resources
from tests.schema_v11.test_canonical_boundary import scope as scope
from tests.schema_v11.test_canonical_runtime import advance, facts, port
from tests.schema_v11.test_runtime_restart import child


def reference_images(*, expired: bool) -> tuple[store.Snapshot, store.Snapshot]:
    owned = store.OwnedRoot.new()
    try:
        binding = port(owned)
        runtime = CanonicalPersistenceRuntime.create(binding, initial(binding), schema_version=11)
        try:
            before = interrupt_read(runtime, binding)
            after = continue_response(runtime, expired=expired)
            # Retrying the observed timestamp is a no-op, not a second resume.
            assert (
                advance(runtime, datetime.fromisoformat(after.life.record.last_updated_at)) is after
            )
            return image_of(before), image_of(after)
        finally:
            runtime.close()
    finally:
        owned.cleanup()


@pytest.mark.parametrize("expired", [False, True], ids=["resume", "expiry"])
def test_suspended_goal_and_interrupted_task_continue_in_independent_processes(
    scope: store.OwnedRoot, expired: bool
) -> None:
    before, expected = reference_images(expired=expired)
    mode = "goal_expiry" if expired else "goal_resume"
    writer, _, written = child(scope, "writer", mode)
    assert written["after"] == digest(before)
    continuation, _, continued = child(scope, "resave", mode)
    assert continuation != writer and continued["before"] == written["after"]
    assert continued["after"] == digest(expected)
    reader, _, read = child(scope, "reader", mode)
    assert reader not in (writer, continuation)
    assert read["before"] == read["after"] == continued["after"]
    catalog, context, _ = resources()
    actual, life = store.load(scope, "maple.db", (catalog,), ((1, context),))
    assert store.exact(actual) == store.exact(expected)
    for name in ("goal", "decision", "action_event", "timeline_event", "tool_use", "document"):
        old = before.rows(name)
        assert actual.rows(name)[: len(old)] == old, f"lost or rewritten {name} history"
    assert life.suspended_goal is None
    events = actual.rows("timeline_event")
    assert sum(r[4] == "goal_suspended" for r in events) == 1
    outcome = [r for r in events if r[4] in ("goal_resumed", "goal_abandoned")]
    assert len(outcome) == 1
    assert outcome[0][4] == ("goal_abandoned" if expired else "goal_resumed")
    if expired:
        assert json.loads(str(outcome[0][6]))["reason"] == "expired"
    failed = [r for r in actual.rows("tool_use") if r[4] == 1 and r[7] == "read_failed"]
    assert len(failed) == 1 and failed[0][12] == "interrupted"
    # Compatibility reads use the same restored truth and do not advance it.
    runtime = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    try:
        saved = runtime.capture()
        at = datetime.fromisoformat(saved.life.record.last_updated_at)
        from maplegotchi.core.world.legacy_projection import PointRef

        prior = dict(
            zip(before.table("life_state").columns, before.rows("life_state")[0], strict=True)
        )
        origin = PointRef(str(prior["point_host"]), str(prior["point_id"])) if life.travel else None
        projection = runtime.legacy(facts(saved), at, origin=origin)
        assert (
            projection.presentation.goal == life.active_goal
            and projection.presentation.task == life.task
        )
        assert runtime.capture() is saved
    finally:
        runtime.close()


@pytest.mark.parametrize("phase", ["after_write", "before_commit", "during_commit", "after_commit"])
def test_response_completion_crash_retains_only_complete_goal_and_task_history(
    scope: store.OwnedRoot, phase: str
) -> None:
    before, after = reference_images(expired=False)
    writer, _, written = child(scope, "writer", "goal_resume")
    assert written["after"] == digest(before)
    interrupted, code, _ = child(scope, phase, "goal_resume")
    assert code == 73 and interrupted != writer
    reader, _, read = child(scope, "reader", "goal_resume")
    assert reader not in (writer, interrupted)
    catalog, context, _ = resources()
    actual, _ = store.load(scope, "maple.db", (catalog,), ((1, context),))
    allowed = (
        [before]
        if phase in {"after_write", "before_commit"}
        else [after]
        if phase == "after_commit"
        else [before, after]
    )
    assert any(store.exact(actual) == store.exact(candidate) for candidate in allowed)
    assert read["before"] == read["after"] == digest(actual)
