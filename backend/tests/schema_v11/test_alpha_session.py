"""Persistent local-alpha ownership and complete controller-process restart."""

from __future__ import annotations

import json
import subprocess  # noqa: TID251 -- bounded test-owned controllers
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from tests.schema_v11.alpha_files import AlphaFiles
from tests.schema_v11.owned_store import StoreError
from tests.schema_v11.playable_preview import Preview
from tests.schema_v11.test_restart_process import worker_interpreter

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="Linux-only persistent alpha file ownership/locking"
)


def start(root: Path, *, initialize: bool) -> tuple[subprocess.Popen[bytes], str, str]:
    executable, env = worker_interpreter()
    log = root.parent / ("initialize.log" if initialize else "restore.log")
    argv = [
        executable,
        "-B",
        "-m",
        "tests.schema_v11.playable_preview",
        "--alpha-root",
        str(root),
        "--port",
        "0",
    ]
    if initialize:
        argv.append("--initialize")
    with log.open("xb") as output:
        process = subprocess.Popen(  # noqa: S603 -- fixed owned controller module
            argv, cwd=Path(__file__).parents[2], env=env, stdout=output, stderr=subprocess.STDOUT
        )
    deadline = time.monotonic() + 60
    try:
        while time.monotonic() < deadline:
            text = log.read_text(encoding="utf-8")
            if "ISOLATED PREVIEW http://" in text:
                url = text.split("ISOLATED PREVIEW ", 1)[1].split(" ", 1)[0]
                with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310 -- owned loopback
                    html = response.read().decode()
                token = html.split('name="preview-token" content="', 1)[1].split('"', 1)[0]
                return process, url, token
            assert process.poll() is None, text
            time.sleep(0.05)  # Process readiness, never simulated heartbeat progression.
        raise AssertionError("owned alpha controller startup timeout")
    except BaseException:
        stop(process)
        raise


def stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def request(url: str, token: str, operation: str = "state") -> dict[str, Any]:
    value = urllib.request.Request(url + "/" + operation)  # noqa: S310 -- owned loopback
    if operation != "state":
        value = urllib.request.Request(  # noqa: S310 -- owned loopback
            url + "/" + operation,
            method="POST",
            data=b"",
            headers={"Origin": url, "X-Preview-Token": token},
        )
    with urllib.request.urlopen(value, timeout=60) as response:  # noqa: S310 -- fixed owned loopback
        result = json.load(response)
    assert type(result) is dict
    return result


def test_entire_controller_exits_reopens_exact_life_then_continues(tmp_path: Path) -> None:
    root = tmp_path / "local-alpha"
    old, url, token = start(root, initialize=True)
    try:
        initial = request(url, token)
        before = request(url, token, "tick")
        assert before["position"] != initial["position"]
        assert before["controller_pid"] == old.pid
    finally:
        stop(old)
    assert old.returncode == 0 and old.poll() is not None
    db_identity = (root / "maple.db").stat()
    new, url, token = start(root, initialize=False)
    try:
        restored = request(url, token)
        assert new.pid != old.pid and restored["controller_pid"] == new.pid
        for key in (
            "digest",
            "revision",
            "tick",
            "action",
            "decision",
            "session",
            "database_identity",
            "position",
            "activity",
            "needs",
            "goal",
            "task",
            "events",
        ):
            assert restored[key] == before[key], key
        assert restored["database_identity"] == [db_identity.st_dev, db_identity.st_ino]
        continued = request(url, token, "tick")
        assert continued["tick"] == before["tick"] + 1
        assert continued["revision"] == before["revision"] + 1
        assert continued["action"] == before["action"]
        assert continued["position"] != before["position"]
        while continued["moving"]:
            continued = request(url, token, "tick")
            assert continued["tick"] < 25
        arrived = [e for e in continued["events"] if e["kind"] == "arrived"]
        assert len(arrived) == 1 and arrived[0]["action"] == initial["action"]
        next_action = request(url, token, "next")
        assert next_action["action"] == initial["action"] + 1
        stopped = request(url, token, "shutdown")
        assert stopped["digest"] == next_action["digest"]
        assert new.wait(timeout=15) == 0
        print(
            json.dumps(
                dict(
                    old_controller_pid=old.pid,
                    old_exit=old.returncode,
                    new_controller_pid=new.pid,
                    before=before,
                    restored=restored,
                    continued=continued,
                    next_action=next_action,
                ),
                sort_keys=True,
            )
        )
    finally:
        stop(new)
    assert new.returncode == 0 and (root / "maple.db").is_file()


def test_alpha_lock_admission_and_initialize_never_overwrite(tmp_path: Path) -> None:
    root = tmp_path / "local-alpha"
    preview = Preview(root, initialize=True)
    try:
        raw = (root / "maple.db").read_bytes()
        with pytest.raises(FileExistsError):
            Preview(root, initialize=True)
        contender = AlphaFiles(root)
        with pytest.raises(StoreError, match="ownership"):
            contender.check("maple.db")
        with pytest.raises(StoreError, match="ownership"):
            contender.lock()
        assert (root / "maple.db").read_bytes() == raw
    finally:
        preview.close()
    assert (root / "maple.db").is_file()


@pytest.mark.parametrize("bad", ["foreign", "symlink", "permissions", "database_inode", "corrupt"])
def test_alpha_refuses_unsafe_or_corrupt_state_without_rebirth(tmp_path: Path, bad: str) -> None:
    root = tmp_path / "local-alpha"
    if bad == "foreign":
        root.mkdir()
        (root / "maple.db").write_bytes(b"foreign")
    else:
        preview = Preview(root, initialize=True)
        preview.close()
        if bad == "symlink":
            alias = tmp_path / "alias"
            alias.symlink_to(root, target_is_directory=True)
            root = alias
        elif bad == "permissions":
            root.chmod(0o755)
        elif bad == "database_inode":
            db = root / "maple.db"
            data = db.read_bytes()
            db.rename(tmp_path / "original.db")
            db.write_bytes(data)
        else:
            with (root / "maple.db").open("r+b") as output:
                output.write(b"not a sqlite database")
    before = (root / "maple.db").read_bytes()
    with pytest.raises((ValueError, OSError)):
        Preview(root)
    assert (root / "maple.db").read_bytes() == before
