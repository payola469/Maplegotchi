"""Real writer exit/read/continuation and commit faults on fresh owned roots."""

from datetime import datetime, timedelta

import pytest

from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.world.canonical_lifecycle import LifeLoopBlocked
from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime
from tests.schema_v11 import owned_store as store
from tests.schema_v11.canonical_binding import image_of
from tests.schema_v11.playable_worker import frame
from tests.schema_v11.restart_worker import digest, life_changes
from tests.schema_v11.test_canonical_boundary import scope as scope
from tests.schema_v11.test_canonical_runtime import facts, port
from tests.schema_v11.test_runtime_restart import child


@pytest.mark.parametrize(
    "mode", ["urgent_critical", "urgent_high", "urgent_entry_a", "urgent_entry_b"]
)
def test_urgent_writer_exits_exact_restore_ui_then_independent_continuation(
    scope: store.OwnedRoot, mode: str
) -> None:
    writer, _, written = child(scope, "writer", mode)
    runtime = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    try:
        saved = runtime.capture()
        assert digest(image_of(saved)) == written["after"]
        view = frame(runtime)
        assert view["read"]["legacy"]["status"] == "unavailable"
        assert list(view["position"]) == view["read"]["snapshot"]["position"]
        assert view["revision"] == view["read"]["snapshot"]["life_revision"]
        cancelled = saved.life.record.action_counter - 1
        assert saved.life.record.action_priority == (
            "high" if mode == "urgent_high" else "critical"
        )
    finally:
        runtime.close()
    reader, _, read = child(scope, "reader", mode)
    assert reader != writer and read["before"] == read["after"] == written["after"]
    continuation, _, continued = child(scope, "resave", mode)
    assert continuation not in {writer, reader}
    assert continued["before"] == written["after"]
    runtime = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    try:
        events = image_of(runtime.capture()).rows("action_event")
        assert sum(row[3] == cancelled and row[5] == "walking_cancelled" for row in events) == 1
        assert not any(
            row[3] == cancelled and row[5] in {"arrived", "activity_started"} for row in events
        )
        arrivals = [(row[3], row[5]) for row in events if row[5] == "arrived"]
        assert len(arrivals) == len(set(arrivals))
    finally:
        runtime.close()


@pytest.mark.parametrize("phase", ["before_commit", "after_commit"])
def test_urgent_continuation_crash_has_one_authoritative_image(
    scope: store.OwnedRoot, phase: str
) -> None:
    writer, _, written = child(scope, "writer", "urgent_critical")
    failed, code, _ = child(scope, phase, "urgent_critical")
    assert failed != writer and code == 73
    reader, _, restored = child(scope, "reader", "urgent_critical")
    assert reader not in {writer, failed}
    assert restored["before"] == restored["after"]
    if phase == "before_commit":
        assert restored["after"] == written["after"]
    else:
        assert restored["revision"] == written["revision"] + 1


@pytest.mark.parametrize("boundary", ["same_time_interrupt", "reevaluation_policy"])
def test_unsupported_boundary_refuses_without_save_or_counter_change(
    scope: store.OwnedRoot, boundary: str
) -> None:
    child(scope, "writer", "urgent_high")
    binding = port(scope)
    runtime = CanonicalPersistenceRuntime.restore(binding, schema_version=11)
    if boundary == "reevaluation_policy":
        old = runtime.capture()
        raw = life_changes(
            image_of(old),
            revision=old.life.record.revision + 1,
            decision_due_since=old.life.record.last_updated_at,
        )
        runtime.close()
        store.save(
            scope,
            binding.name,
            raw,
            expected_revision=old.life.record.revision,
            catalogs=binding.catalogs,
            contexts=binding.contexts,
        )
        runtime = CanonicalPersistenceRuntime.restore(binding, schema_version=11)
    try:
        before = runtime.capture()
        raw_bytes = scope.check("maple.db").read_bytes()
        now = datetime.fromisoformat(before.life.record.last_updated_at)
        if boundary == "reevaluation_policy":
            now += timedelta(seconds=1)
        with pytest.raises(LifeLoopBlocked, match=boundary):
            runtime.step(
                now,
                BehaviorInputs(server_attention=1),
                CoreParameters(),
                facts(before),
                expected_revision=before.life.record.revision,
            )
        assert runtime.capture() is before
        assert scope.check("maple.db").read_bytes() == raw_bytes
    finally:
        runtime.close()
