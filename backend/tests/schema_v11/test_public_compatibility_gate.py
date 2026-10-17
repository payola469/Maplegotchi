"""No implicit D03 activation: canonical values cannot masquerade as shipped SSE state."""

from datetime import timedelta

import pytest

from maplegotchi.api.views import live_event
from tests.schema_v11 import owned_store as store
from tests.schema_v11.canonical_binding import image_of
from tests.schema_v11.restart_worker import digest
from tests.schema_v11.test_canonical_boundary import scope as scope
from tests.schema_v11.test_canonical_runtime import advance
from tests.schema_v11.test_extended_life import CASES, seeded


@pytest.mark.parametrize("activity,seed,energy,seconds", CASES)
def test_all_activities_remain_readonly_at_existing_public_state_gate(
    scope: store.OwnedRoot, activity: object, seed: int, energy: float, seconds: int
) -> None:
    runtime = seeded(scope, seed, energy)
    try:
        before = runtime.capture()
        saved = advance(runtime, before.life.identity.born_at + timedelta(seconds=seconds))
        assert saved.life.activity is activity
        raw = scope.check("maple.db").read_bytes()
        image = image_of(saved)
        for kind in ("heartbeat", "movement"):
            with pytest.raises(TypeError, match="not MapleState"):
                live_event(
                    kind, dict(state=saved.life, revision=saved.life.record.revision, tick_id=1)
                )
        assert runtime.capture() is saved
        assert digest(image_of(runtime.capture())) == digest(image)
        assert scope.check("maple.db").read_bytes() == raw
    finally:
        runtime.close()
