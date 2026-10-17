"""Private synthetic preview worker; never a shipped runtime or public DTO.

The parent owns the fresh root. Every command runs in a tracked interpreter
which fully exits before another reader/writer can start.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from maplegotchi.core.world.coordinates import GRID_HEIGHT, GRID_WIDTH, T, Tile, tile_to_feet
from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime
from tests.schema_v11 import owned_store as store
from tests.schema_v11.alpha_files import AlphaFiles
from tests.schema_v11.canonical_binding import OwnedBinding, image_of
from tests.schema_v11.life_simulation import simulation_initial
from tests.schema_v11.restart_worker import digest, resources
from tests.schema_v11.test_canonical_runtime import advance, facts


def frame(runtime: CanonicalPersistenceRuntime) -> dict[str, Any]:
    snapshot = runtime.capture()
    life = snapshot.life
    now = datetime.fromisoformat(life.record.last_updated_at)
    document = life.layout.active.layout
    travel = life.travel
    position = (
        travel.position_at(now) if travel else tile_to_feet(Tile(life.record.tx, life.record.ty))
    )
    types = {item.id: item for item in document.catalog.catalog.types}
    point = next(
        item.template
        for item in document.catalog.points
        if item.instance_id == life.record.point_host and item.template.id == life.record.point_id
    )
    return dict(
        label="ISOLATED PREVIEW — synthetic canonical runtime, not production",
        read=runtime.poll(facts(snapshot)).model_dump(mode="json"),
        pid=os.getpid(),
        digest=digest(image_of(snapshot)),
        revision=life.record.revision,
        layout_revision=life.record.layout_revision,
        at=now.isoformat(),
        activity=life.activity.value,
        visual=dict(
            pose=point.pose.value,
            facing=(point.occupy_direction if point.occupy else point.facing).value,
            offset=[point.occupy.x, point.occupy.y] if point.occupy else [0, 0],
        ),
        until=life.record.activity_until,
        needs=asdict(life.needs),
        action=life.record.action_counter,
        tick=life.rng.tick_counter,
        decision=life.rng.decision_counter,
        goal=asdict(life.active_goal) if life.active_goal else None,
        task=asdict(life.task) if life.task else None,
        position=position,
        travel=dict(asdict(travel), arrives_at=travel.arrives_at.isoformat()) if travel else None,
        moving=travel is not None and now < travel.arrives_at,
        destination=[life.record.point_host, life.record.point_id],
        grid=[GRID_WIDTH, GRID_HEIGHT, T],
        rooms=[
            dict(id=region.id, status=region.status.value, **asdict(region.floor))
            for region in document.world.regions
        ],
        doors=[asdict(door.passage) for door in document.world.doors if door.state.value == "open"],
        objects=[
            dict(
                id=item.id,
                type=item.type_id,
                art_id=types[item.type_id].art_id,
                surface=types[item.type_id].surface.value,
                mount_y_px=types[item.type_id].mount_y_px,
                room_id=item.room_id,
                x=item.origin.tx,
                y=item.origin.ty,
                w=types[item.type_id].footprint.w,
                h=types[item.type_id].footprint.h,
            )
            for item in document.catalog.instances
        ],
        events=[
            dict(kind=row[5], at=row[6], action=row[3])
            for row in image_of(snapshot).rows("action_event")[-8:]
        ],
    )


def main() -> int:
    if len(sys.argv) not in {6, 9}:
        return 2
    operation, root, device, inode, expected = sys.argv[1:6]
    if operation not in {"init", "tick", "next", "read"}:
        return 2
    scope: store.OwnedRoot | AlphaFiles
    if len(sys.argv) == 9:
        scope = AlphaFiles(Path(root), pending=operation == "init")
        scope.worker(parent=int(sys.argv[6]), token=sys.argv[7], inherited_lock=int(sys.argv[8]))
        if scope.identity != (int(device), int(inode)):
            return 3
    else:
        scope = store.OwnedRoot(Path(root), (int(device), int(inode)))
    catalog, context, _ = resources()
    binding = OwnedBinding(scope, "maple.db", (catalog,), ((1, context),))
    runtime = None
    try:
        if operation == "init":
            if expected != "new":
                return 2
            runtime = CanonicalPersistenceRuntime.create(
                binding, simulation_initial(binding), schema_version=11
            )
            # Select an actual action using the existing deterministic rule engine.
            advance(runtime, runtime.capture().life.identity.born_at + timedelta(minutes=15))
        else:
            runtime = CanonicalPersistenceRuntime.restore(binding, schema_version=11)
            first_alpha_read = (
                operation == "read" and isinstance(scope, AlphaFiles) and expected == "restore"
            )
            if not first_alpha_read and digest(image_of(runtime.capture())) != expected:
                raise ValueError("unexpected persisted state")
            if operation != "read":
                before = runtime.capture()
                now = datetime.fromisoformat(before.life.record.last_updated_at)
                if operation == "next":
                    if before.life.travel is not None:
                        raise ValueError("finish ordinary movement first")
                    now = max(
                        now + timedelta(seconds=1),
                        datetime.fromisoformat(before.life.record.activity_until),
                    )
                else:
                    now += timedelta(seconds=1)
                advance(runtime, now)
        print(json.dumps(frame(runtime), default=lambda value: value.isoformat(), allow_nan=False))
        return 0
    except (ValueError, OSError):
        print(json.dumps(dict(error="preview refused; state retained")))
        return 3
    finally:
        if runtime is not None:
            runtime.close()


if __name__ == "__main__":
    sys.exit(main())
