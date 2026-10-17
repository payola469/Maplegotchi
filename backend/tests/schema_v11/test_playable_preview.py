"""Actual owned preview runtime and local transport admission regressions."""

from email.message import Message
from http.server import HTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from tests.schema_v11.owned_store import OwnedRoot
from tests.schema_v11.playable_preview import Preview, handler


def test_playable_tick_movement_activity_and_process_restart() -> None:
    preview = Preview()
    try:
        initial = preview.state.copy()
        assert initial["activity"] == "write" and initial["moving"]
        assert initial["revision"] == 2
        assert initial["visual"]["pose"] == "sit_write"
        assert initial["visual"]["facing"] == "up"
        assert len(initial["visual"]["offset"]) == 2
        assert initial["travel"]["arrives_at"]
        assert any(item["art_id"] for item in initial["objects"])
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
        assert isinstance(preview.scope, OwnedRoot)
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


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/", 200),
        ("/technical", 200),
        ("/room-ui/assets/room-test.js", 200),
        ("/room-ui/assets/../secret.js", 404),
        ("/room-ui/assets/raw.meta.json", 404),
        ("/room-ui/assets/room-test.js?token=anything", 404),
        ("/art/export/test.png", 404),
    ],
)
def test_room_ui_serves_only_processed_bundle_and_keeps_technical_transport(
    tmp_path: Path, path: str, expected: int
) -> None:
    assets = tmp_path / "frontend/tools/life-preview"
    assets.mkdir(parents=True)
    (assets / "index.html").write_text("technical TOKEN", encoding="utf-8")
    bundle = tmp_path / "frontend/dist/local-alpha"
    (bundle / "assets").mkdir(parents=True)
    (bundle / "index.html").write_text("room TOKEN", encoding="utf-8")
    (bundle / "assets/room-test.js").write_text("// processed", encoding="utf-8")
    (bundle / "assets/raw.meta.json").write_text("{}", encoding="utf-8")
    cls = handler(cast(Preview, None), assets, tmp_path / "unused", "test-token")
    request: Any = object.__new__(cls)
    request.server = cast(HTTPServer, SimpleNamespace(server_port=8473))
    request.headers = {"Host": "127.0.0.1:8473"}
    request.path = path
    replies: list[tuple[int, bytes, str]] = []
    request.reply = lambda code, body, kind: replies.append((code, body, kind))
    request.do_GET()
    assert replies[0][0] == expected
    if path in ("/", "/technical"):
        assert b"test-token" in replies[0][1]
        assert (b"technical" if path == "/technical" else b"room") in replies[0][1]
