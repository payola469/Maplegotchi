"""Extended synthetic diagnostics. No new pinned digest or operational policy."""

import json

import pytest

from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime
from tests.schema_v11 import owned_store as store
from tests.schema_v11.canonical_binding import image_of
from tests.schema_v11.life_simulation import segment, simulation_initial
from tests.schema_v11.restart_worker import digest, resources
from tests.schema_v11.test_canonical_boundary import scope as scope
from tests.schema_v11.test_canonical_runtime import port
from tests.schema_v11.test_runtime_restart import child


def test_three_continuous_traces_and_cross_process_restart_are_identical(
    scope: store.OwnedRoot,
) -> None:
    # Four independent roots. No wall clock, old fixtures, reused databases or pin update.
    reference = []
    final = None
    for repetition in range(3):
        owned = store.OwnedRoot.new()
        try:
            binding = port(owned)
            runtime = CanonicalPersistenceRuntime.create(
                binding, simulation_initial(binding), schema_version=11
            )
            try:
                trace = []
                for chunk in range(3):
                    trace.extend(segment(runtime, first=chunk == 0))
                image = image_of(runtime.capture())
                if repetition == 0:
                    reference, final = trace, image
                else:
                    assert trace == reference
                    assert final is not None and store.exact(image) == store.exact(final)
            finally:
                runtime.close()
        finally:
            owned.cleanup()
    assert final is not None
    actual_trace = []
    pids = []
    for chunk in range(3):
        pid, _, result = child(scope, "writer" if chunk == 0 else "resave", "simulation")
        assert pid not in pids
        pids.append(pid)
        actual_trace.extend(result["trace"])
        assert actual_trace == reference[: len(actual_trace)]
    pid, _, read = child(scope, "reader", "simulation")
    assert pid not in pids
    assert read["before"] == read["after"] == digest(final)
    catalog, context, _ = resources()
    actual, life = store.load(scope, "maple.db", (catalog,), ((1, context),))
    assert store.exact(actual) == store.exact(final)
    assert actual_trace == reference and life.rng.tick_counter == 24
    assert life.record.action_counter > 2 and life.record.goal_counter > 1
    assert actual.rows("tool_use") and actual.rows("document")
    assert actual.rows("world_event") == ()
    pairs = [
        (row[3], row[5])
        for row in actual.rows("action_event")
        if row[5] in ("arrived", "activity_started")
    ]
    assert len(pairs) == len(set(pairs))
    print(
        json.dumps(
            dict(
                diagnostic_only=True,
                ticks=24,
                continuous_runs=3,
                worker_pids=pids,
                reader_pid=pid,
                actions=life.record.action_counter,
                goals=life.record.goal_counter,
                tools=len(actual.rows("tool_use")),
                documents=len(actual.rows("document")),
                existing_store_digest=digest(actual),
            ),
            sort_keys=True,
        )
    )


@pytest.mark.parametrize("phase", ["after_write", "before_commit", "during_commit", "after_commit"])
def test_actual_life_commit_interruption_reopens_only_a_complete_image(
    scope: store.OwnedRoot,
    phase: str,
) -> None:
    # Establish one real eight-tick segment, then kill only its next owned writer.
    from tests.schema_v11.canonical_binding import admit
    from tests.schema_v11.restart_worker import resources

    first, _, initial_result = child(scope, "writer", "simulation")
    catalog, context, _ = resources()
    before, _ = store.load(scope, "maple.db", (catalog,), ((1, context),))
    owned = store.OwnedRoot.new()
    try:
        # The reference starts from its own normal fresh fixture; no database adoption.
        binding = port(owned)
        reference = CanonicalPersistenceRuntime.create(
            binding, simulation_initial(binding), schema_version=11
        )
        try:
            segment(reference, first=True)
            start = reference.capture()
            from datetime import datetime, timedelta

            from tests.schema_v11.test_canonical_runtime import advance

            once = advance(
                reference,
                datetime.fromisoformat(start.life.record.last_updated_at) + timedelta(minutes=5),
            )
            expected_after = image_of(once)
        finally:
            reference.close()
    finally:
        owned.cleanup()
    interrupted, code, _ = child(scope, phase, "simulation")
    assert code == 73 and interrupted != first
    reader, _, restored = child(scope, "reader", "simulation")
    assert reader not in (first, interrupted)
    after, life = store.load(scope, "maple.db", (catalog,), ((1, context),))
    allowed = (
        {digest(before)}
        if phase in ("after_write", "before_commit")
        else {digest(expected_after)}
        if phase == "after_commit"
        else {digest(before), digest(expected_after)}
    )
    assert restored["after"] in allowed and digest(after) == restored["after"]
    reference_image = before if digest(after) == digest(before) else expected_after
    assert store.exact(after) == store.exact(reference_image)
    assert life.identity_row == admit(before, (catalog,), ((1, context),)).life.identity_row
    assert initial_result["tick_counter"] == 8
    print(
        json.dumps(
            dict(
                phase=phase,
                writer=interrupted,
                reader=reader,
                revision=life.record.revision,
                full_image=digest(after),
            )
        )
    )
