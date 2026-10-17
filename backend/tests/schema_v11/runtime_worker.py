"""Owned canonical lifecycle process harness; never starts the default service.

Historical modes preserve checkpoint proof. The explicit life_loop mode executes
ordinary MVP ticks/actions/arrival through the runtime, then a new process continues.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from maplegotchi.core.world.legacy_projection import PointRef
from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime
from tests.schema_v11 import owned_store as store
from tests.schema_v11.canonical_binding import OwnedBinding, admit, image_of
from tests.schema_v11.restart_worker import advanced_snapshot, birth_snapshot, digest, resources
from tests.schema_v11.test_canonical_runtime import advance, facts, movement_proposal


def main() -> int:
    if len(sys.argv) != 7:
        return 2
    operation, root, device, inode, name, mode = sys.argv[1:]
    if operation not in {
        "writer",
        "resave",
        "reader",
        "after_write",
        "before_commit",
        "after_commit",
        "during_commit",
    }:
        return 2
    if mode not in {
        "birth",
        "preflight",
        "stationary",
        "walking",
        "pending",
        "entry_a",
        "entry_b",
        "life_loop",
        "simulation",
        "boundary_simulation",
        "goal_resume",
        "goal_expiry",
        "urgent_critical",
        "urgent_high",
        "urgent_entry_a",
        "urgent_entry_b",
    }:
        return 2
    scope = store.OwnedRoot(Path(root), (int(device), int(inode)))
    catalog, context, _ = resources()

    def interrupt(phase: str) -> None:
        if phase == operation:
            os._exit(73)

    def during_commit() -> int:
        if operation == "during_commit":
            os._exit(73)
        return 0

    binding = OwnedBinding(
        scope,
        name,
        (catalog,),
        ((1, context),),
        inject=interrupt,
        commit_progress=during_commit if operation == "during_commit" else None,
    )
    runtime = None
    trace: list[dict[str, str | int]] = []
    try:
        if operation == "writer":
            base = admit(birth_snapshot(), binding.catalogs, binding.contexts)
            if mode in {"simulation", "boundary_simulation"}:
                from tests.schema_v11.life_simulation import simulation_initial

                base = simulation_initial(binding)
            elif mode in {"goal_resume", "goal_expiry"}:
                from tests.schema_v11.life_interrupt import initial

                base = initial(binding)
            runtime = CanonicalPersistenceRuntime.create(binding, base, schema_version=11)
            before = runtime.capture()
            if mode.startswith("urgent_"):
                from tests.schema_v11.urgent_scenario import interrupt as urgent_interrupt
                from tests.schema_v11.urgent_scenario import prepare as urgent_prepare

                runtime = urgent_prepare(runtime, binding, mode)
                urgent_interrupt(runtime, binding, mode)
            elif mode in {"simulation", "boundary_simulation"}:
                from tests.schema_v11.life_simulation import segment

                if mode == "boundary_simulation":
                    from tests.schema_v11.life_simulation import boundary_segment

                    trace = boundary_segment(runtime)
                else:
                    trace = segment(runtime, first=True)
            elif mode in {"goal_resume", "goal_expiry"}:
                from tests.schema_v11.life_interrupt import interrupt_read

                interrupt_read(runtime, binding)
            elif mode == "life_loop":
                advance(runtime, before.life.identity.born_at + timedelta(hours=4))
            elif mode == "preflight":
                proposal = movement_proposal(binding)
                runtime.preflight_transition(
                    proposal,
                    facts(proposal),
                    datetime.fromisoformat(proposal.life.record.last_updated_at),
                    origin=PointRef("idle.hall_center", "idle"),
                )
                runtime.checkpoint()
            elif mode == "birth":
                runtime.checkpoint()
            else:
                # Rich accepted specimens are explicit test setup, not an invented
                # runtime tick or public runtime state-transition algorithm.
                runtime.close()
                store.save(
                    scope,
                    name,
                    advanced_snapshot(birth_snapshot(), mode),
                    expected_revision=1,
                    catalogs=binding.catalogs,
                    contexts=binding.contexts,
                )
                runtime = CanonicalPersistenceRuntime.restore(binding, schema_version=11)
                before = runtime.capture()
                runtime.checkpoint()
        else:
            runtime = CanonicalPersistenceRuntime.restore(binding, schema_version=11)
            before = runtime.capture()
            if operation != "reader":
                if mode.startswith("urgent_"):
                    assert before.life.travel is not None
                    advance(runtime, before.life.travel.arrives_at)
                    advance(
                        runtime,
                        datetime.fromisoformat(runtime.capture().life.record.activity_until),
                    )
                elif mode in {"simulation", "boundary_simulation"}:
                    from tests.schema_v11.life_simulation import segment

                    if mode == "boundary_simulation":
                        from tests.schema_v11.life_simulation import boundary_segment

                        trace = boundary_segment(runtime)
                    else:
                        trace = segment(runtime, first=False)
                elif mode in {"goal_resume", "goal_expiry"}:
                    from tests.schema_v11.life_interrupt import continue_response

                    continue_response(runtime, expired=mode == "goal_expiry")
                elif mode == "life_loop":
                    travel = before.life.travel
                    if travel is None:
                        return 3
                    advance(runtime, travel.departed_at + timedelta(seconds=1))
                    advance(runtime, travel.arrives_at)
                    advance(runtime, travel.arrives_at + timedelta(seconds=1))
                    advance(
                        runtime,
                        datetime.fromisoformat(runtime.capture().life.record.activity_until),
                    )
                else:
                    runtime.checkpoint()
        after = runtime.capture()
        # No implicit time progression. Derivation can use caller-supplied time
        # while persisted counters/timing remain unchanged.
        result: dict[str, object] = dict(
            pid=os.getpid(),
            before=digest(image_of(before)),
            after=digest(image_of(after)),
            revision=after.life.record.revision,
            fields=len(image_of(after).table("life_state").columns),
            simulation_continuation=(
                "ordinary_mvp_continued"
                if mode == "life_loop"
                else "stationary_goal_continued"
                if mode in {"goal_resume", "goal_expiry"}
                else "blocked:no_canonical_transition_engine"
            ),
            tick_counter=after.life.rng.tick_counter,
            action_counter=after.life.record.action_counter,
        )
        if mode in {"simulation", "boundary_simulation"}:
            result["trace"] = trace
            result["simulation_continuation"] = "extended_simulation_unpinned"
        runtime.close()
        runtime = None
        print(json.dumps(result, sort_keys=True))
        return 0
    except (store.StoreError, ValueError) as error:
        print(json.dumps(dict(error=str(error))))
        return 3
    finally:
        if runtime is not None:
            runtime.close()


if __name__ == "__main__":
    sys.exit(main())
