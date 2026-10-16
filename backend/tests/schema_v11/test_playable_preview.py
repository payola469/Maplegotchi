"""Actual owned preview runtime and local transport admission regressions."""

from email.message import Message
from http.server import HTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from tests.schema_v11.playable_preview import Preview, handler


def test_playable_tick_movement_activity_and_process_restart() -> None:
    preview = Preview()
    try:
        initial = preview.state.copy()
        assert initial["activity"] == "write" and initial["moving"]
        assert initial["revision"] == 2
        walking_bytes = preview.scope.check("maple.db").read_bytes()
        with pytest.raises(ValueError, match="finish ordinary movement first"):
            preview.act("next")
        assert preview.state == initial and preview.error is None
        assert preview.scope.check("maple.db").read_bytes() == walking_bytes
        preview.act("tick")
        advanced = preview.state.copy()
        assert advanced["pid"] != initial["pid"]
        assert advanced["position"] != initial["position"]
        assert advanced["needs"] != initial["needs"]
        assert advanced["tick"] == initial["tick"] + 1
        assert advanced["revision"] == initial["revision"] + 1
        old_bytes = preview.scope.check("maple.db").read_bytes()
        preview.act("restart")
        assert preview.state["pid"] != advanced["pid"]
        assert preview.previous_pid == advanced["pid"]
        for name in ("digest", "revision", "tick", "action", "position", "needs", "goal", "task"):
            assert preview.state[name] == advanced[name]
        assert preview.scope.check("maple.db").read_bytes() == old_bytes
        assert preview.paused and preview.restarts == 1
        # Ordinary movement is completed by real ticks before advancing activity time.
        while preview.state["moving"]:
            preview.act("tick")
            assert preview.state["tick"] <= initial["tick"] + 20
        arrived = preview.state.copy()
        arrivals = [e for e in arrived["events"] if e["kind"] == "arrived"]
        assert len(arrivals) == 1 and arrivals[0]["action"] == initial["action"]
        preview.act("next")
        assert preview.state["action"] == initial["action"] + 1
        assert preview.state["revision"] == arrived["revision"] + 1
        assert preview.state["goal"] is not None
    finally:
        preview.close()


def test_preview_state_mismatch_stops_without_retry_reset_or_database_mutation() -> None:
    preview = Preview()
    try:
        before_bytes = preview.scope.check("maple.db").read_bytes()
        preview.state["digest"] = "unexpected"
        with pytest.raises(ValueError, match="worker refused"):
            preview.act("tick")
        assert preview.error is not None and preview.paused
        with pytest.raises(ValueError, match="stopped after failure"):
            preview.act("play")
        assert preview.scope.check("maple.db").read_bytes() == before_bytes
    finally:
        # This test owns the fresh capability; the preview itself retains failed artifacts.
        preview.scope.cleanup()


@pytest.mark.parametrize("change", ["host", "origin", "token", "body", "chunked"])
def test_preview_mutations_require_exact_local_origin_and_capability(change: str) -> None:
    # Transport policy only; no sockets, worker, database or external paths.
    cls = handler(cast(Preview, None), Path("unused"), Path("unused"), "test-token")
    request: Any = object.__new__(cls)
    request.server = cast(HTTPServer, SimpleNamespace(server_port=8473))
    headers = {
        "Host": "127.0.0.1:8473",
        "Origin": "http://127.0.0.1:8473",
        "X-Preview-Token": "test-token",
        "Content-Length": "0",
    }
    request.headers = Message()
    for key, value in headers.items():
        request.headers[key] = value
    assert request.admitted(mutation=True)
    key, value = {
        "host": ("Host", "foreign.example"),
        "origin": ("Origin", "https://foreign.example"),
        "token": ("X-Preview-Token", "wrong"),
        "body": ("Content-Length", "1"),
        "chunked": ("Transfer-Encoding", "chunked"),
    }[change]
    if key in request.headers:
        del request.headers[key]
    request.headers[key] = value
    assert not request.admitted(mutation=True)
