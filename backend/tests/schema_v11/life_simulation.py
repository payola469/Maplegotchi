"""Diagnostic trace using the existing owned-store digest, never a replacement pin."""

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
