"""Opt-in reads use one committed capture; only fresh synthetic owned roots."""

import json
import sys
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from maplegotchi.core.state import Needs
from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime
from tests.schema_v11 import owned_store as store
from tests.schema_v11.canonical_binding import admit, image_of
from tests.schema_v11.playable_preview import Preview
from tests.schema_v11.restart_worker import advanced_snapshot, birth_snapshot
from tests.schema_v11.test_alpha_session import request, start, stop
from tests.schema_v11.test_canonical_boundary import scope as scope
from tests.schema_v11.test_canonical_runtime import facts, port


@pytest.mark.parametrize("mode", ["stationary", "walking", "pending", "entry_a", "entry_b"])
def test_poll_reads_committed_state_without_writes_or_invented_projection(
    scope: store.OwnedRoot, mode: str
) -> None:
    binding = port(scope)
    birth = admit(birth_snapshot(), binding.catalogs, binding.contexts)
    runtime = CanonicalPersistenceRuntime.create(binding, birth, schema_version=11)
    proposed = admit(advanced_snapshot(image_of(birth), mode), binding.catalogs, binding.contexts)
    runtime.close()
    store.save(
        scope,
        "maple.db",
        image_of(proposed),
        expected_revision=1,
        catalogs=binding.catalogs,
        contexts=binding.contexts,
    )
    runtime = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    try:
        before = runtime.capture()
        raw = scope.check("maple.db").read_bytes()
        reply = runtime.poll(facts(before))
        assert reply.contract_version == "maple-canonical-poll.v1"
        assert reply.snapshot.life_revision == before.life.record.revision
        assert reply.snapshot.layout_revision == before.life.record.layout_revision
        assert reply.snapshot.identity.maple_id == before.life.record.maple_id
        assert reply.snapshot.committed_at.isoformat() == before.life.record.last_updated_at
        assert reply.snapshot.activity == before.life.activity.value
        assert reply.snapshot.tick_counter == before.life.rng.tick_counter
        if before.life.travel is not None:
            assert reply.snapshot.position == before.life.travel.position_at(
                reply.snapshot.committed_at
            )
            # A read without authoritative origin must never invent Legacy provenance.
            assert reply.legacy.status == "unavailable"
        else:
            assert reply.legacy.status == "available"
        assert runtime.poll(facts(before)) == reply
        refused = runtime.poll(replace(facts(before), needs=Needs(1, 2, 3, 4)))
        assert refused.legacy.status == "unavailable"
        assert refused.snapshot == reply.snapshot
        assert runtime.capture() is before
        assert scope.check("maple.db").read_bytes() == raw
    finally:
        runtime.close()


def test_local_poll_reopens_readonly_worker_and_never_installs_or_retries_state() -> None:
    preview = Preview()
    try:
        before = preview.state.copy()
        raw = preview.scope.check("maple.db").read_bytes()
        first = preview.poll()
        second = preview.poll()
        assert first["status"] == second["status"] == "available"
        assert first["snapshot"] == second["snapshot"]
        assert first["display"]["pid"] != second["display"]["pid"]
        assert first["display"]["revision"] == first["snapshot"]["life_revision"]
        assert preview.state == before and preview.previous_pid is None
        assert preview.scope.check("maple.db").read_bytes() == raw
        preview.state["digest"] = "incorrect"
        denied = preview.poll()
        assert denied["status"] == "unavailable" and denied["snapshot"] is None
        assert "display" not in denied and preview.state["digest"] == "incorrect"
        preview.error = "stopped"
        assert preview.poll()["reason"] == "runtime_stopped"
        assert preview.scope.check("maple.db").read_bytes() == raw
    finally:
        assert isinstance(preview.scope, store.OwnedRoot)
        preview.scope.cleanup()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux alpha controller ownership")
def test_versioned_http_poll_restores_same_life_across_controller_exit(tmp_path: Path) -> None:
    # start() owns a new synthetic root and bounded subprocess. No historic alpha data.
    def read(url: str) -> dict[str, Any]:
        with urllib.request.urlopen(  # noqa: S310 -- test-owned loopback controller
            url + "/local-alpha/v1/state", timeout=60
        ) as response:
            result = json.load(response)
        assert type(result) is dict and result["status"] == "available"
        return result

    root = tmp_path / "polling-alpha"
    old, url, token = start(root, initialize=True)
    try:
        request(url, token, "tick")
        before = read(url)
    finally:
        stop(old)
    assert old.poll() is not None and old.returncode == 0
    new, url, token = start(root, initialize=False)
    try:
        restored = read(url)
        assert new.pid != old.pid and restored["snapshot"] == before["snapshot"]
        assert restored["display"]["digest"] == before["display"]["digest"]
        continued = request(url, token, "tick")
        after = read(url)
        assert after["snapshot"]["life_revision"] == continued["revision"]
        assert continued["revision"] == before["snapshot"]["life_revision"] + 1
    finally:
        stop(new)
