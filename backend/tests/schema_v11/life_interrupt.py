"""Shared synthetic scenario: real read, arrival, stationary urgency, continuation.

No invented transition, new priority policy or digest pin. All writes use the
existing owned canonical runtime; unknown origins remain refused.
"""

from datetime import datetime, timedelta

from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime
from maplegotchi.storage.canonical_v11 import CanonicalSnapshot
from tests.schema_v11.canonical_binding import OwnedBinding, admit
from tests.schema_v11.restart_worker import birth_snapshot, replace_rows
from tests.schema_v11.test_canonical_runtime import advance, facts


def initial(binding: OwnedBinding) -> CanonicalSnapshot:
    raw = birth_snapshot()
    identity = raw.rows("maple")[0]
    raw = replace_rows(raw, "maple", ((*identity[:3], f"{0:064x}"),))
    return admit(raw, binding.catalogs, binding.contexts)


def interrupt_read(
    runtime: CanonicalPersistenceRuntime, binding: OwnedBinding
) -> CanonicalSnapshot:
    selected = advance(runtime, runtime.capture().life.identity.born_at + timedelta(minutes=15))
    assert selected.life.travel is not None and selected.life.task is not None
    arrived = advance(runtime, selected.life.travel.arrives_at)
    assert arrived.life.travel is None and arrived.life.active_goal is not None
    return runtime.step(
        datetime.fromisoformat(arrived.life.record.last_updated_at)
        + timedelta(microseconds=100000),
        BehaviorInputs(server_attention=1),
        CoreParameters(),
        facts(arrived),
        expected_revision=arrived.life.record.revision,
        task_effects=binding.task_effects,
    )


def continue_response(runtime: CanonicalPersistenceRuntime, *, expired: bool) -> CanonicalSnapshot:
    before = runtime.capture()
    goal = before.life.suspended_goal
    assert goal is not None
    now = datetime.fromisoformat(before.life.record.activity_until)
    if expired:
        now = max(now, goal.horizon_until) + timedelta(seconds=1)
    return advance(runtime, now)
