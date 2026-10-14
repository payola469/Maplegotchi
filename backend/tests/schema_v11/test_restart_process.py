"""Real OS writer exit / distinct reader, all paths owned by this execution."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess  # noqa: TID251 -- STEP 220 authorizes bounded owned children
import sys
from collections.abc import Iterator
from pathlib import Path
from threading import Thread
from typing import Any

import pytest

from tests.schema_v11.owned_store import OwnedRoot, StoreError, create, load
from tests.schema_v11.restart_worker import advanced_snapshot, birth_snapshot, digest, resources


@pytest.fixture
def scope() -> Iterator[OwnedRoot]:
    owned = OwnedRoot.new()
    try:
        yield owned
    finally:
        try:
            owned.cleanup()
        except (StoreError, FileNotFoundError):
            print("Owned failure artifacts retained:", owned.path)


def worker_interpreter() -> tuple[str, dict[str, str]]:
    """Bypass Windows venv trampolines while retaining their venv context.

    uv's Windows python.exe spawns the base interpreter, so its Popen PID is
    not the worker PID. CPython getpath uses __PYVENV_LAUNCHER__ to retain
    the venv while sys._base_executable identifies the actual interpreter.
    Calling it directly makes wait/kill apply to the worker itself.
    """
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    executable = sys.executable
    if sys.platform == "win32":
        base_executable = getattr(sys, "_base_executable", None)
        assert isinstance(base_executable, str) and base_executable
        executable = base_executable
        env["__PYVENV_LAUNCHER__"] = sys.executable
    return executable, env


def child(owned: OwnedRoot, operation: str, mode: str = "stationary") -> tuple[int, int, str]:
    """Track exactly this child; bounded time, output and termination scope."""
    owned._root()
    executable, env = worker_interpreter()
    argv = [
        executable,
        "-B",
        "-m",
        "tests.schema_v11.restart_worker",
        operation,
        str(owned.path),
        str(owned.identity[0]),
        str(owned.identity[1]),
        "maple.db",
        mode,
    ]
    process = subprocess.Popen(  # noqa: S603 -- exact owned child argv
        argv,
        cwd=Path(__file__).parents[2],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    chunks: list[bytes] = []

    def drain() -> None:
        assert process.stdout is not None
        # Read at most 8193 diagnostic bytes; terminate this child on overflow.
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
        raise AssertionError("owned child timeout") from None
    finally:
        thread.join(timeout=10)
    assert not thread.is_alive(), "diagnostic reader did not finish"
    return process.pid, code, b"".join(chunks).decode("utf-8", errors="replace")


def result(output: str) -> dict[str, Any]:
    return json.loads(output.splitlines()[-1])  # type: ignore[no-any-return]


@pytest.mark.parametrize("mode", ["stationary", "walking", "pending", "entry_a", "entry_b"])
def test_writer_exits_then_distinct_reader_restores_exact_state(
    scope: OwnedRoot, mode: str
) -> None:
    writer, code, output = child(scope, "writer", mode)
    assert code == 0, output
    written = result(output)
    assert written["pid"] == writer
    before_bytes = hashlib.sha256(scope.check("maple.db").read_bytes()).hexdigest()
    reader, code, output = child(scope, "reader", mode)
    assert hashlib.sha256(scope.check("maple.db").read_bytes()).hexdigest() == before_bytes
    assert code == 0, output
    restored = result(output)
    assert reader != writer and restored["pid"] == reader
    assert (
        restored["digest"] == written["digest"] == digest(advanced_snapshot(birth_snapshot(), mode))
    )
    assert restored["fields"] == 40 and restored["revision"] == 2
    catalog, context, _ = resources()
    snapshot, life = load(scope, "maple.db", (catalog,), ((1, context),))
    assert digest(snapshot) == restored["digest"]
    assert len(snapshot.rows("timeline_event")) == 1
    assert life.record.tick_counter == 5 and life.record.interaction_counter == 3
    print(
        json.dumps(dict(mode=mode, writer_pid=writer, reader_pid=reader, digest=restored["digest"]))
    )


@pytest.mark.parametrize(
    "checkpoint,expected_revision",
    [("after_write", 1), ("before_commit", 1), ("during_commit", 1), ("after_commit", 2)],
)
def test_owned_process_loss_classifies_durable_state(
    scope: OwnedRoot, checkpoint: str, expected_revision: int
) -> None:
    catalog, context, _ = resources()
    create(scope, "maple.db", birth_snapshot(), (catalog,), ((1, context),))
    writer, code, output = child(scope, checkpoint)
    assert code == 73, output
    reader, code, output = child(scope, "reader")
    assert code == 0, output
    restored = result(output)
    assert reader != writer and restored["revision"] == expected_revision
    expected = birth_snapshot() if expected_revision == 1 else advanced_snapshot(birth_snapshot())
    assert restored["digest"] == digest(expected)
    print(
        json.dumps(
            dict(
                checkpoint=checkpoint,
                writer_pid=writer,
                reader_pid=reader,
                recovered_revision=expected_revision,
            )
        )
    )


def test_reader_never_creates_missing_database(scope: OwnedRoot) -> None:
    _, code, output = child(scope, "reader")
    assert code == 3 and result(output) == {"error": "ownership"}
    assert not (scope.path / "maple.db").exists()


def test_direct_interpreter_retains_venv_and_real_restart(
    scope: OwnedRoot, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Exercise the Windows launch configuration with actual child processes on
    # Linux too. Only platform selection is overridden; storage/processes are real.
    with monkeypatch.context() as selection:
        selection.setattr(sys, "platform", "win32")
        executable, env = worker_interpreter()
    assert executable == getattr(sys, "_base_executable", None)
    assert env["__PYVENV_LAUNCHER__"] == sys.executable
    monkeypatch.setattr(sys.modules[__name__], "worker_interpreter", lambda: (executable, env))
    test_writer_exits_then_distinct_reader_restores_exact_state(scope, "stationary")
