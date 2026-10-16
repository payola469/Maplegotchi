"""Fresh source creation/conversion A exits, distinct B verifies full committed state."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import subprocess  # noqa: TID251 -- STEP230 owned bounded conversion workers authorized
from pathlib import Path
from threading import Thread
from typing import Any

import pytest

from tests.schema_v11.owned_store import OwnedRoot
from tests.schema_v11.test_restart_process import worker_interpreter

_ROOTS: dict[int, tuple[OwnedRoot, str]] = {}


def process_root() -> OwnedRoot:
    scope = OwnedRoot.new()
    _ROOTS[id(scope)] = (scope, secrets.token_hex(32))
    return scope


def close_root(scope: OwnedRoot) -> None:
    scope.cleanup()
    del _ROOTS[id(scope)]


def child(
    scope: OwnedRoot,
    operation: str,
    *,
    point: str = "writing_desk.chair",
    travel: bool = False,
    variant: int = 1,
    tamper: bool = False,
) -> tuple[int, int, dict[str, Any]]:
    registered = _ROOTS.get(id(scope))
    if registered is None or registered[0] is not scope:
        raise ValueError("unregistered process root")
    scope._root()
    secret = registered[1]
    packet = dict(
        root=str(scope.path),
        identity=scope.identity,
        parent=os.getpid(),
        point=point,
        travel=travel,
        variant=variant,
    )
    nonce = hmac.new(
        bytes.fromhex(secret), json.dumps(packet, sort_keys=True).encode(), hashlib.sha256
    ).hexdigest()
    packet["nonce"] = nonce
    if tamper:
        packet["root"] = "/data/maple"
    executable, env = worker_interpreter()
    env["MAPLEGOTCHI_STEP230_HANDOFF"] = secret
    # Ensure both worker and imported production source come from this worktree.
    env["PYTHONPATH"] = str(Path(__file__).parents[2] / "src")
    process = subprocess.Popen(  # noqa: S603 -- fixed module/operation; parent-owned stdin only
        [executable, "-B", "-m", "tests.schema_v11.converter_worker", operation],
        cwd=Path(__file__).parents[2],
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert process.stdin is not None
    process.stdin.write(json.dumps(packet).encode())
    process.stdin.close()
    chunks = []

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
        code = process.wait(timeout=75)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
        raise AssertionError("owned conversion worker timeout") from None
    finally:
        thread.join(timeout=10)
    assert not thread.is_alive()
    output = b"".join(chunks).decode("utf-8", errors="replace")
    if code == 73:
        return process.pid, code, {}
    if tamper:
        assert code == 3 and json.loads(output) == {"error": "refused"}
        return process.pid, code, {"error": "refused"}
    assert code == 0, output
    result = json.loads(output.splitlines()[-1])
    assert result["pid"] == process.pid and result["nonce"] == nonce
    return process.pid, code, result


@pytest.mark.parametrize("travel", [False, True])
@pytest.mark.parametrize("point", ["writing_desk.chair", "bed.side", "open_area.east"])
def test_real_writer_exit_before_reader(point: str, travel: bool) -> None:
    scope = process_root()
    try:
        a, _, written = child(scope, "writer", point=point, travel=travel)
        before = scope.check("target.db").read_bytes()
        b, _, read = child(scope, "reader", point=point, travel=travel)
        assert a != b and written["version"] == read["version"] == 11
        assert written["digest"] == read["digest"]
        assert scope.check("target.db").read_bytes() == before
        print(json.dumps(dict(writer_pid=a, reader_pid=b, version=read["version"], travel=travel)))
    finally:
        close_root(scope)


@pytest.mark.parametrize("checkpoint", ["before_commit", "during_commit", "after_commit"])
def test_interrupted_conversion_reopened_by_distinct_reader(checkpoint: str) -> None:
    scope = process_root()
    try:
        a, code, _ = child(scope, checkpoint, travel=True)
        assert code == 73
        b, _, read = child(scope, "reader", travel=True)
        assert a != b
        expected = (
            {10}
            if checkpoint == "before_commit"
            else {11}
            if checkpoint == "after_commit"
            else {10, 11}
        )
        assert read["version"] in expected
        print(
            json.dumps(
                dict(checkpoint=checkpoint, writer_pid=a, reader_pid=b, version=read["version"])
            )
        )
    finally:
        close_root(scope)


def test_handoff_binds_fresh_root_before_database_access() -> None:
    scope = process_root()
    try:
        _, code, _ = child(scope, "writer", tamper=True)
        assert code == 3 and scope._registry() == {}
        assert {p.name for p in scope.path.iterdir()} == {"ownership.json"}
    finally:
        close_root(scope)


def test_reconstructed_or_expired_process_capability_refused() -> None:
    scope = process_root()
    fake = OwnedRoot(scope.path, scope.identity)
    try:
        with pytest.raises(ValueError, match="unregistered"):
            child(fake, "reader")
    finally:
        close_root(scope)
    with pytest.raises(ValueError, match="unregistered"):
        child(scope, "reader")
