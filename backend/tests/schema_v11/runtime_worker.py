"""Owned STEP 225 process harness for the shipped canonical lifecycle adapter.

No service or simulation engine is started. Only the explicit 'preflight' case
checks a synthetic movement proposal without installing it; re-save is a checkpoint, not a tick.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from maplegotchi.core.world.legacy_projection import PointRef
from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime
from tests.schema_v11 import owned_store as store
from tests.schema_v11.canonical_binding import OwnedBinding, admit, image_of
from tests.schema_v11.restart_worker import advanced_snapshot, birth_snapshot, digest, resources
from tests.schema_v11.test_canonical_runtime import facts, movement_proposal


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
    }:
        return 2
    if mode not in {"birth", "preflight", "stationary", "walking", "pending", "entry_a", "entry_b"}:
        return 2
    scope = store.OwnedRoot(Path(root), (int(device), int(inode)))
    catalog, context, _ = resources()

    def interrupt(phase: str) -> None:
        if phase == operation:
            os._exit(73)

    binding = OwnedBinding(scope, name, (catalog,), ((1, context),), inject=interrupt)
    runtime = None
    try:
        if operation == "writer":
            base = admit(birth_snapshot(), binding.catalogs, binding.contexts)
            runtime = CanonicalPersistenceRuntime.create(binding, base, schema_version=11)
            before = runtime.capture()
            if mode == "preflight":
                proposal = movement_proposal(binding)
                from datetime import datetime

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
                runtime.checkpoint()
        after = runtime.capture()
        # No implicit time progression. Derivation can use caller-supplied time
        # while persisted counters/timing remain unchanged.
        result = dict(
            pid=os.getpid(),
            before=digest(image_of(before)),
            after=digest(image_of(after)),
            revision=after.life.record.revision,
            fields=len(image_of(after).table("life_state").columns),
            simulation_continuation="blocked:no_canonical_transition_engine",
        )
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
