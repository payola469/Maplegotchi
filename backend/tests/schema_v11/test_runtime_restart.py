"""A → B → C real processes through the canonical runtime adapter, not MapleService."""

from __future__ import annotations

import hashlib
import json
import subprocess  # noqa: TID251 -- STEP 225 permits bounded owned processes
from pathlib import Path
from threading import Thread
from typing import Any

import pytest

from tests.schema_v11 import owned_store as store
from tests.schema_v11.restart_worker import (
    advanced_snapshot,
    birth_snapshot,
    digest,
    life_changes,
    resources,
)
from tests.schema_v11.test_canonical_boundary import scope as scope
from tests.schema_v11.test_restart_process import worker_interpreter


def child(root: store.OwnedRoot, operation: str, mode: str) -> tuple[int, int, dict[str, Any]]:
    root._root()
    executable, env = worker_interpreter()
    argv = [
        executable,
        "-B",
        "-m",
        "tests.schema_v11.runtime_worker",
        operation,
        str(root.path),
        str(root.identity[0]),
        str(root.identity[1]),
        "maple.db",
        mode,
    ]
    process = subprocess.Popen(  # noqa: S603 -- fixed worker and explicit owned capability
        argv,
        cwd=Path(__file__).parents[2],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    chunks: list[bytes] = []

    def drain() -> None:
        assert process.stdout is not None
        data = process.stdout.read(8193)
        chunks.append(data[:8192])
        if len(data) > 8192:
            process.kill()
        process.stdout.close()

    thread = Thread(target=drain, daemon=True)
    thread.start()
    try:
        code = process.wait(timeout=60)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
        raise AssertionError("owned canonical worker timeout") from None
    finally:
        thread.join(timeout=10)
    assert not thread.is_alive()
    output = b"".join(chunks).decode("utf-8", errors="replace")
    if code == 73:
        return process.pid, code, {}
    assert code == 0, output
    result = json.loads(output.splitlines()[-1])
    assert result["pid"] == process.pid, "must track actual interpreter, not a Windows launcher"
    return process.pid, code, result


def expected(scope: store.OwnedRoot, mode: str) -> store.Snapshot:
    base = birth_snapshot()
    if mode in {"birth", "preflight"}:
        return life_changes(base, revision=2)
    return life_changes(advanced_snapshot(base, mode), revision=3)


@pytest.mark.parametrize(
    "mode", ["birth", "preflight", "stationary", "walking", "pending", "entry_a", "entry_b"]
)
def test_three_process_save_restore_checkpoint_durability(
    scope: store.OwnedRoot, mode: str
) -> None:
    a, _, written = child(scope, "writer", mode)
    reference = expected(scope, mode)
    assert written["after"] == digest(reference)
    # child() waited for the actual worker to exit before returning.
    b, _, resaved = child(scope, "resave", mode)
    assert b != a and resaved["before"] == written["after"]
    reference = life_changes(reference, revision=written["revision"] + 1)
    assert resaved["after"] == digest(reference)
    before_bytes = hashlib.sha256(scope.check("maple.db").read_bytes()).hexdigest()
    c, _, restored = child(scope, "reader", mode)
    assert c not in (a, b)
    assert restored["before"] == restored["after"] == resaved["after"]
    assert restored["fields"] == 40 and restored["revision"] == resaved["revision"]
    assert hashlib.sha256(scope.check("maple.db").read_bytes()).hexdigest() == before_bytes
    catalog, context, _ = resources()
    actual, life = store.load(scope, "maple.db", (catalog,), ((1, context),))
    assert store.exact(actual) == store.exact(reference)
    assert len(actual.rows("timeline_event")) == 1 and actual.sequences == reference.sequences
    assert life.rng.tick_counter == reference.rows("life_state")[0][11]
    assert restored["simulation_continuation"] == "blocked:no_canonical_transition_engine"
    print(
        json.dumps(
            dict(
                mode=mode,
                writer_pid=a,
                resave_pid=b,
                reader_pid=c,
                revision=restored["revision"],
                digest=restored["after"],
            ),
            sort_keys=True,
        )
    )


@pytest.mark.parametrize("phase", ["after_write", "before_commit", "after_commit"])
def test_interrupted_runtime_save_classified_by_new_process(
    scope: store.OwnedRoot, phase: str
) -> None:
    a, _, written = child(scope, "writer", "birth")
    interrupted, code, _ = child(scope, phase, "birth")
    assert code == 73 and interrupted != a
    c, _, restored = child(scope, "reader", "birth")
    assert c not in (a, interrupted)
    revision = written["revision"] + int(phase == "after_commit")
    assert restored["revision"] == revision
    assert restored["after"] == digest(life_changes(birth_snapshot(), revision=revision))
    print(
        json.dumps(
            dict(checkpoint=phase, writer_pid=interrupted, reader_pid=c, durable_revision=revision),
            sort_keys=True,
        )
    )
