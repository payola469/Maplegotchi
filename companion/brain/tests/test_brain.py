"""maple-brain: safe configuration, the provider run, and the three contracts (ADR-0033)."""

from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from maple_brain.config import BrainConfigError, BrainSettings, ProviderKind, settings_from_env
from maple_brain.prompts import GUARDRAILS, decide_prompt, first_json_object, reply_prompt
from maple_brain.provider import ProviderError, command_provider, none_provider
from maple_brain.server import BrainService, serve

PROPOSAL = {
    "goal": {"op": "keep"},
    "action": {"kind": "read", "duration_minutes": 25, "target": "library:the_room"},
    "reason": "The room guide looks useful.",
}


def settings(**over: Any) -> BrainSettings:
    return BrainSettings(**over)


# ---------------------------------------------------------------- configuration


def test_defaults_are_loopback_and_no_provider() -> None:
    s = settings_from_env({})
    assert (s.host, s.port, s.provider) == ("127.0.0.1", 8471, ProviderKind.NONE)


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "example.com", "::"])  # noqa: S104
def test_the_listener_is_loopback_only(host: str) -> None:
    with pytest.raises(BrainConfigError):
        settings(host=host)


@pytest.mark.parametrize(
    "command",
    [
        '["/usr/local/bin/agy", "--yolo"]',
        '["/usr/local/bin/agy", "--dangerously-skip-permissions"]',
        '["/usr/local/bin/agy", "--approval-mode=yolo"]',
        '["/usr/local/bin/agy", "--approval-mode", "yolo"]',
        '["/usr/local/bin/agy", "-y"]',
        '["/usr/local/bin/agy", "--AUTO-APPROVE"]',
        '["agy", "--print"]',  # not an absolute path
        '"/usr/local/bin/agy --print"',  # a string, not an argv array
        "[]",
    ],
)
def test_dangerous_or_ambiguous_commands_are_refused(command: str) -> None:
    with pytest.raises(BrainConfigError):
        settings_from_env({"MAPLE_BRAIN_PROVIDER": "command", "MAPLE_BRAIN_COMMAND": command})


def test_a_command_provider_needs_a_command() -> None:
    with pytest.raises(BrainConfigError):
        settings_from_env({"MAPLE_BRAIN_PROVIDER": "command"})


# ---------------------------------------------------------------- the provider run


def script(tmp_path: Path, body: str) -> tuple[str, ...]:
    path = tmp_path / "provider.py"
    path.write_text(body, encoding="utf-8")
    return (sys.executable, str(path))


def test_the_prompt_goes_on_stdin_and_stdout_is_the_answer(tmp_path: Path) -> None:
    argv = script(tmp_path, "import sys, os\nprint(sys.stdin.read().upper(), os.getcwd())\n")
    run = command_provider(settings(provider=ProviderKind.COMMAND, command=argv),
                           environ={"PATH": "/usr/bin", "SECRET": "x"})  # fmt: skip
    out = run("hello", 10)
    assert out is not None and out.startswith("HELLO")
    assert str(tmp_path) not in out  # an empty scratch directory, not the repo


def test_the_provider_sees_only_a_minimal_environment(tmp_path: Path) -> None:
    argv = script(tmp_path, "import os\nprint(sorted(os.environ))\n")
    run = command_provider(settings(provider=ProviderKind.COMMAND, command=argv),
                           environ={"PATH": "/usr/bin", "MAPLE_GATEWAY_TOKEN": "nope"})  # fmt: skip
    out = run("", 10) or ""
    assert "MAPLE_GATEWAY_TOKEN" not in out


def test_provider_failures_and_timeouts_are_errors(tmp_path: Path) -> None:
    fail_argv = script(tmp_path, "raise SystemExit(3)" + chr(10))
    failing = command_provider(settings(provider=ProviderKind.COMMAND, command=fail_argv))
    with pytest.raises(ProviderError):
        failing("x", 10)
    slow_argv = script(tmp_path, "import time\ntime.sleep(5)\n")
    slow = command_provider(settings(provider=ProviderKind.COMMAND, command=slow_argv))
    with pytest.raises(ProviderError, match="timed out"):
        slow("x", 0.5)
    assert none_provider("x", 1) is None


# ---------------------------------------------------------------- contracts


def test_prompts_carry_the_guardrails_and_the_facts() -> None:
    context = {"maple": {"name": "Maple"}, "message": {"text": "สวัสดี", "language": "th"}}
    for prompt in (decide_prompt(context), reply_prompt(context)):
        assert GUARDRAILS in prompt and "Do not run commands." in prompt
    assert "Reply in Thai." in reply_prompt(context)
    assert "สวัสดี" in reply_prompt(context)
    assert "Return ONLY one JSON object" in decide_prompt(context)


def test_first_json_object_tolerates_prose_and_fences() -> None:
    text = "Sure!\n```json\n" + json.dumps(PROPOSAL) + "\n```"
    assert first_json_object(text) == PROPOSAL
    assert first_json_object("no json here") is None


def service(answer: Any) -> BrainService:
    def provider(prompt: str, timeout: float) -> str | None:
        if isinstance(answer, Exception):
            raise answer
        return str(answer) if answer is not None else None

    return BrainService(settings(), provider)


def test_decide_returns_the_contract_shape() -> None:
    status, body = service(json.dumps(PROPOSAL)).decide(
        {"contract": "maple.decision.v1", "context": {"trigger": "action_completed"}}
    )
    assert status == 200 and body == {"contract": "maple.decision.v1", "proposal": PROPOSAL}
    status, body = service("I would read.").decide({"contract": "maple.decision.v1", "context": {}})
    assert body["proposal"] is None  # Maple then falls back
    assert service("x").decide({"contract": "other", "context": {}})[0] == 400


def test_reply_and_generate() -> None:
    status, body = service("  Hello Paolo!  ").reply({"contract": "maple.reply.v1", "context": {}})
    assert (status, body) == (200, {"contract": "maple.reply.v1", "reply": "Hello Paolo!"})
    assert service(None).reply({"contract": "maple.reply.v1", "context": {}})[0] == 503
    assert (
        service(ProviderError("down")).reply({"contract": "maple.reply.v1", "context": {}})[0]
        == 503
    )
    assert service("[]").generate({"prompt": "Write."}) == (200, {"response": "[]"})
    assert service("x").generate({"prompt": "", "extra": 1})[0] == 400


def test_http_plumbing_limits_and_routes() -> None:
    server = serve(settings(port=0), lambda prompt, timeout: json.dumps(PROPOSAL))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"

    def post(path: str, payload: bytes) -> tuple[int, Any]:
        request = urllib.request.Request(base + path, data=payload, method="POST",  # noqa: S310
                                         headers={"content-type": "application/json"})  # fmt: skip
        try:
            with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, None

    try:
        body = json.dumps({"contract": "maple.decision.v1", "context": {}}).encode()
        assert post("/decide", body) == (
            200,
            {"contract": "maple.decision.v1", "proposal": PROPOSAL},
        )
        assert post("/decide", b"not json")[0] == 400
        assert post("/decide", b"x" * (64 * 1024 + 1))[0] == 413
        assert post("/anything", body)[0] == 404
        with urllib.request.urlopen(base + "/health", timeout=5) as response:  # noqa: S310
            expected = {"status": "ok", "provider": "none", "model": None}
            assert json.loads(response.read()) == expected
    finally:
        server.shutdown()
        server.server_close()


def test_health_reports_provider_and_model_but_never_the_command() -> None:
    secret_argv = ("/usr/local/bin/agy", "--token=SECRET-TOKEN", "--model", "{model}")
    configured = settings(
        provider=ProviderKind.COMMAND, command=secret_argv, model="gemini-3.8-flash-medium"
    )
    body = BrainService(configured, none_provider).health()
    assert body == {"status": "ok", "provider": "command", "model": "gemini-3.8-flash-medium"}
    text = json.dumps(body)
    assert "agy" not in text and "SECRET-TOKEN" not in text and "--model" not in text


def test_health_over_http_includes_the_model() -> None:
    configured = settings(port=0, provider=ProviderKind.COMMAND,
                          command=("/usr/local/bin/agy", "--print"), model="m-1")  # fmt: skip
    server = serve(configured, none_provider)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/health"
        with urllib.request.urlopen(url, timeout=5) as response:
            raw = response.read().decode()
        assert json.loads(raw) == {"status": "ok", "provider": "command", "model": "m-1"}
        assert "/usr/local/bin/agy" not in raw
    finally:
        server.shutdown()
        server.server_close()
