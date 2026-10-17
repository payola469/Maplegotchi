"""Owned synthetic urgent scenarios; real canonical commits, no live data."""

from datetime import datetime, timedelta

from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.world.movement import EdgeStart
from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime
from tests.schema_v11 import owned_store as store
from tests.schema_v11.canonical_binding import OwnedBinding, image_of
from tests.schema_v11.restart_worker import advanced_snapshot, life_changes
from tests.schema_v11.test_canonical_runtime import advance, facts


def prepare(
    runtime: CanonicalPersistenceRuntime, binding: OwnedBinding, mode: str
) -> CanonicalPersistenceRuntime:
    if mode in {"urgent_entry_a", "urgent_entry_b"}:
        raw = advanced_snapshot(image_of(runtime.capture()), mode.removeprefix("urgent_"))
        raw = life_changes(
            raw, action_priority="normal", decision_due_since=None, critical_since=None
        )
    else:
        selected = advance(runtime, runtime.capture().life.identity.born_at + timedelta(minutes=15))
        raw = image_of(selected)
        if mode == "urgent_high":
            raw = life_changes(raw, revision=selected.life.record.revision + 1, energy=9.0)
        else:
            return runtime
    revision = runtime.capture().life.record.revision
    runtime.close()
    store.save(
        binding.scope,
        binding.name,
        raw,
        expected_revision=revision,
        catalogs=binding.catalogs,
        contexts=binding.contexts,
    )
    return CanonicalPersistenceRuntime.restore(binding, schema_version=11)


def interrupt(runtime: CanonicalPersistenceRuntime, binding: OwnedBinding, mode: str) -> None:
    before = runtime.capture()
    travel = before.life.travel
    assert travel is not None
    at = datetime.fromisoformat(before.life.record.last_updated_at) + timedelta(microseconds=50000)
    exact = travel.current_at(at)
    assert isinstance(exact, EdgeStart)
    after = runtime.step(
        at,
        BehaviorInputs(server_attention=0 if mode == "urgent_high" else 1),
        CoreParameters(),
        facts(before),
        expected_revision=before.life.record.revision,
        task_effects=binding.task_effects,
    )
    assert after.life.travel is not None and after.life.travel.current_at(at) == exact
    assert after.life.travel.entry is not None
    assert after.life.record.route_from_activity == before.life.record.route_from_activity
    assert after.life.record.action_counter == before.life.record.action_counter + 1
    assert after.life.suspended_goal == before.life.active_goal
    assert runtime.poll(facts(after)).legacy.status == "unavailable"
    assert len(image_of(after).rows("decision")) == len(image_of(before).rows("decision"))
    assert (
        runtime.step(
            at,
            BehaviorInputs(server_attention=0 if mode == "urgent_high" else 1),
            CoreParameters(),
            facts(after),
            expected_revision=after.life.record.revision,
            task_effects=binding.task_effects,
        )
        is after
    )
