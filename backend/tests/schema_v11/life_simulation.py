"""Diagnostic trace using the existing owned-store digest, never a replacement pin."""

from dataclasses import asdict
from datetime import datetime, timedelta

from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime
from maplegotchi.storage.canonical_v11 import CanonicalSnapshot
from tests.schema_v11.canonical_binding import OwnedBinding, admit, image_of
from tests.schema_v11.restart_worker import birth_snapshot, digest, replace_rows
from tests.schema_v11.test_canonical_runtime import advance

SEGMENT_TICKS = 8


def simulation_initial(binding: OwnedBinding) -> CanonicalSnapshot:
    """Fresh diagnostic seed exercises real writing; no production Birth or repin."""
    base = birth_snapshot()
    identity = base.rows("maple")[0]
    base = replace_rows(base, "maple", ((*identity[:3], f"{5:064x}"),))
    return admit(base, binding.catalogs, binding.contexts)


def segment(runtime: CanonicalPersistenceRuntime, *, first: bool) -> list[dict[str, str | int]]:
    old = runtime.capture()
    start = (
        old.life.identity.born_at + timedelta(minutes=15)
        if first
        else datetime.fromisoformat(old.life.record.last_updated_at) + timedelta(minutes=5)
    )
    trace: list[dict[str, str | int]] = []
    for i in range(SEGMENT_TICKS):
        now = start + timedelta(minutes=5 * i)
        before = runtime.capture()
        saved = advance(runtime, now)
        assert saved.life.record.revision == before.life.record.revision + 1
        assert saved.life.rng.tick_counter == before.life.rng.tick_counter + 1
        assert saved.life.identity_row == old.life.identity_row
        image = image_of(saved)
        trace.append(
            dict(
                at=now.isoformat(),
                digest=digest(image),
                revision=saved.life.record.revision,
                tick=saved.life.rng.tick_counter,
                decision=saved.life.rng.decision_counter,
                action=saved.life.record.action_counter,
                goals=saved.life.record.goal_counter,
                activity=saved.life.activity.value,
                tools=len(image.rows("tool_use")),
                documents=len(image.rows("document")),
                events=len(image.rows("timeline_event")),
            )
        )
    return trace


def boundary_segment(runtime: CanonicalPersistenceRuntime) -> list[dict[str, str | int]]:
    """Two diagnostic ticks; first process exits at a real mid-edge position.

    Reuses the existing store digest. This is additional regression coverage,
    not a proposed replacement simulation pin, clock policy or acceptance corpus.
    """
    from maplegotchi.core.world.coordinates import Tile, tile_to_feet
    from tests.schema_v11.restart_worker import canonical

    trace: list[dict[str, str | int]] = []
    for _ in range(2):
        before = runtime.capture()
        life = before.life
        tick = life.rng.tick_counter
        at = datetime.fromisoformat(life.record.last_updated_at)
        if tick == 0:
            now = life.identity.born_at + timedelta(minutes=15)
        elif tick in (1, 2):
            now = at + timedelta(microseconds=1125000 if tick == 1 else 1250000)
        elif tick == 3:
            assert life.travel is not None
            now = life.travel.arrives_at + timedelta(seconds=1)
        elif tick == 4:
            now = datetime.fromisoformat(life.record.activity_until)
        else:
            now = at + timedelta(minutes=5)
        saved = advance(runtime, now)
        image = image_of(saved)
        assert saved.life.record.revision == life.record.revision + 1
        assert saved.life.rng.tick_counter == tick + 1
        # Observing/repeating the same timestamp must not write or repeat an action.
        assert advance(runtime, now) is saved
        travel = saved.life.travel
        position = (
            travel.position_at(now)
            if travel
            else tile_to_feet(Tile(saved.life.record.tx, saved.life.record.ty))
        )
        trace.append(
            dict(
                at=now.isoformat(),
                digest=digest(image),
                revision=saved.life.record.revision,
                tick=saved.life.rng.tick_counter,
                action=saved.life.record.action_counter,
                decision=saved.life.rng.decision_counter,
                activity=saved.life.activity.value,
                phase=travel.phase_at(now) if travel else "stationary",
                position=canonical(position),
                needs=canonical(asdict(saved.life.needs)),
                goals=canonical(image.rows("goal")),
                tasks=canonical(image.rows("tool_use")),
                table_counts=canonical([(table.name, len(table.rows)) for table in image.tables]),
                sequences=canonical(image.sequences),
            )
        )
    return trace
