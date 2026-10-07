"""maple-discord without Discord: config, the Maple client, and the handlers (ADR-0032)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from maple_discord.config import GatewayConfigError, GatewaySettings, settings_from_env
from maple_discord.handlers import (
    COMMANDS,
    HELP,
    UNREACHABLE,
    ChatMessage,
    answer,
    command,
    format_brain,
    format_goal,
    format_needs,
    format_status,
    is_conversation,
    may_use_commands,
    split_for_discord,
)
from maple_discord.maple_client import MapleClient

TOKEN = "g" * 40
SETTINGS = GatewaySettings(
    bot_token="bot-secret",
    gateway_token=TOKEN,
    guild_id=1,
    channel_id=10,
    owner_id=42,
)
SNAPSHOT: dict[str, Any] = {
    "maple": {
        "identity": {"name": "Maple"},
        "needs": {"mood": 70.2, "energy": 61.0, "social": 55.4, "curiosity": 48.0},
        "expression": "happy",
        "activity": {
            "kind": "read",
            "phase": "performing",
            "furniture": "bookshelf",
            "task": {"title": "Maple's room"},
        },
        "goal": {
            "summary": "Learn about the room",
            "type": "learn",
            "horizon_until": "2026-10-06T05:30:00Z",
        },
    },
    "server": {"summary": "calm", "services": [{"service_id": "backup", "state": "active"}]},
}


def message(**kw: Any) -> ChatMessage:
    base: dict[str, Any] = {"id": 99, "channel_id": 10, "author_id": 42, "author_is_bot": False,
                            "content": "วันนี้ทำอะไรอยู่"}  # fmt: skip
    base.update(kw)
    return ChatMessage(**base)


def maple(handler: Any) -> MapleClient:
    return MapleClient("http://127.0.0.1:8470", TOKEN, transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------- config


def env(tmp_path: Path, **over: str) -> dict[str, str]:
    (tmp_path / "bot").write_text("bot-token\n", encoding="utf-8")
    (tmp_path / "gw").write_text(TOKEN, encoding="utf-8")
    base = {
        "CREDENTIALS_DIRECTORY": str(tmp_path),
        "DISCORD_BOT_TOKEN_FILE": "bot",
        "MAPLE_GATEWAY_TOKEN_FILE": "gw",
        "MAPLE_DISCORD_GUILD_ID": "1",
        "MAPLE_DISCORD_CHANNEL_ID": "10",
        "MAPLE_DISCORD_OWNER_ID": "42",
    }
    base.update(over)
    return base


def test_settings_read_secrets_from_credential_files(tmp_path: Path) -> None:
    settings = settings_from_env(env(tmp_path))
    assert settings.bot_token == "bot-token" and settings.gateway_token == TOKEN
    assert settings.maple_api_url == "http://127.0.0.1:8470"
    assert "bot-token" not in repr(settings) and TOKEN not in repr(settings)


@pytest.mark.parametrize(
    "over",
    [
        {"MAPLE_API_URL": "http://example.com:8470"},
        {"MAPLE_API_URL": "https://127.0.0.1:8470"},
        {"MAPLE_DISCORD_OWNER_ID": "paolo"},
        {"DISCORD_BOT_TOKEN_FILE": "missing"},
    ],
)
def test_settings_refuse_unsafe_or_incomplete_config(tmp_path: Path, over: dict[str, str]) -> None:
    with pytest.raises(GatewayConfigError):
        settings_from_env(env(tmp_path, **over))


def test_a_short_gateway_token_is_refused() -> None:
    with pytest.raises(GatewayConfigError):
        GatewaySettings(bot_token="b", gateway_token="short", guild_id=1, channel_id=1, owner_id=1)


# ---------------------------------------------------------------- conversations


def test_only_paolos_messages_in_maple_chat_are_conversations() -> None:
    assert is_conversation(message(), SETTINGS)
    assert not is_conversation(message(author_id=7), SETTINGS)  # someone else
    assert not is_conversation(message(channel_id=11), SETTINGS)  # another channel
    assert not is_conversation(message(author_is_bot=True), SETTINGS)
    assert not is_conversation(message(content="   "), SETTINGS)
    assert may_use_commands(42, SETTINGS) and not may_use_commands(7, SETTINGS)


async def test_a_message_is_relayed_with_the_gateway_token_and_maple_replies() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["origin"] = request.headers.get("origin")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"reply": "ตอนนี้ฉันกำลังอ่านหนังสืออยู่"})

    reply = await answer(message(), maple(handler))
    assert reply == "ตอนนี้ฉันกำลังอ่านหนังสืออยู่"
    assert seen["auth"] == f"Bearer {TOKEN}" and seen["origin"] is None
    assert seen["body"] == {"message_id": "99", "channel": "discord", "speaker": "paolo",
                            "text": "วันนี้ทำอะไรอยู่"}  # fmt: skip


@pytest.mark.parametrize("status", [401, 500, 503])
async def test_maple_being_unreachable_is_reported_not_hidden(status: int) -> None:
    reply = await answer(message(), maple(lambda r: httpx.Response(status)))
    assert reply == UNREACHABLE


async def test_network_failure_is_reported() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    assert await answer(message(), maple(boom)) == UNREACHABLE


# ---------------------------------------------------------------- commands


async def test_commands_are_read_only_gets() -> None:
    methods: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append((request.method, request.url.path))
        if request.url.path == "/api/brain-health":
            return httpx.Response(200, json=BRAIN_HEALTH)
        if request.url.path == "/api/snapshot":
            return httpx.Response(200, json=SNAPSHOT)
        return httpx.Response(200, json=[{"text": "A line."}])

    client = maple(handler)
    for name in ("status", "needs", "goal", "journal", "server", "memory", "brain", "help"):
        await command(name, client)
    assert {m for m, _ in methods} == {"GET"}
    assert await command("help", client) == HELP
    assert await command("anything-else", client) == HELP


def test_command_texts_come_from_maples_state() -> None:
    status = format_status(SNAPSHOT)
    assert status.startswith("Maple is read “Maple's room”.")
    assert "Mood 70 · Energy 61" in status
    assert format_goal(SNAPSHOT) == "Goal: Learn about the room (learn, until 05:30 UTC)."
    assert format_goal({"maple": {"goal": None}}) == "Maple has no goal at the moment."


def test_long_replies_are_split_for_discord() -> None:
    text = ("line\n" * 900).strip()
    chunks = split_for_discord(text)
    assert all(len(c) <= 2000 for c in chunks) and "".join(chunks).count("line") == 900
    assert split_for_discord("x" * 4500) == ["x" * 2000, "x" * 2000, "x" * 500]
    assert split_for_discord("  ") == []


# ---------------------------------------------------------------- /needs and /brain

BRAIN_HEALTH: dict[str, Any] = {
    "as_of": "2026-10-07T03:00:00Z",
    "status": "degraded",
    "status_reason": "latest_call_failed",
    "provider": "command",
    "model": "gemini-3.8-flash-medium",
    "companion": {"probed": True, "reachable": True, "error": None},
    "journal_brain": "external",
    "director": {
        "mode": "external",
        "name": "antigravity",
        "last_call": {"at": "2026-10-07T02:58:00Z", "ok": True, "code": None,
                      "latency_ms": 20200},
        "last_success_at": "2026-10-07T02:58:00Z",
        "fallbacks_today": 0,
        "timeouts_today": 0,
    },
    "replier": {
        "mode": "external",
        "name": "antigravity",
        "last_call": {"at": "2026-10-07T02:59:00Z", "ok": False, "code": "busy",
                      "latency_ms": 0},
        "last_success_at": None,
        "fallbacks_today": 2,
        "timeouts_today": 1,
    },
    "last_success_at": "2026-10-07T02:58:00Z",
    "today": {"day": "2026-10-07", "start": "2026-10-06T23:00:00Z",
              "end": "2026-10-07T23:00:00Z"},
}  # fmt: skip


def test_needs_come_from_the_snapshot() -> None:
    assert format_needs(SNAPSHOT) == "Mood 70 · Energy 61 · Social 55 · Curiosity 48"


def test_brain_is_compact_and_from_brain_health() -> None:
    assert format_brain(BRAIN_HEALTH).splitlines() == [
        "Brain: degraded (latest_call_failed)",
        "Provider command · model gemini-3.8-flash-medium",
        "Director: external (antigravity) — last call ok, 20.2 s, 02:58 UTC",
        "Replier: external (antigravity) — last call fell back (busy), 0.0 s, 02:59 UTC"
        " · today 2 fallback(s), 1 timeout(s)",
    ]


def test_brain_when_offline_or_all_rule() -> None:
    offline = {**BRAIN_HEALTH, "status": "offline", "status_reason": "companion_unreachable",
               "provider": None, "model": None,
               "companion": {"probed": True, "reachable": False, "error": "timeout"},
               "director": {**BRAIN_HEALTH["director"], "last_call": None,
                            "fallbacks_today": 0, "timeouts_today": 0}}  # fmt: skip
    text = format_brain(offline)
    assert text.splitlines()[:2] == [
        "Brain: offline (companion_unreachable)",
        "Companion unreachable (timeout)",
    ]
    assert "Director: external (antigravity) — no calls yet" in text
    rule = {"status": "unknown", "status_reason": "not_configured", "provider": None,
            "model": None, "companion": {"probed": False, "reachable": None, "error": None},
            "director": {"mode": "rule", "name": "rule_director"},
            "replier": {"mode": "rule", "name": "rule_replier"}}  # fmt: skip
    assert format_brain(rule) == "Brain: unknown (not_configured)\nDirector: rule\nReplier: rule"


def test_brain_shows_only_allowlisted_fields() -> None:
    leaky = {
        **BRAIN_HEALTH,
        "command": ["/usr/bin/gemini", "--api-key", "sk-SECRET"],
        "prompt": "You are Maple... SECRET PROMPT",
        "token": "tok-SECRET",
        "raw_output": "SECRET OUTPUT",
        "reasoning": "SECRET THOUGHTS",
        "director": {**BRAIN_HEALTH["director"], "argv": "sk-SECRET"},
        "model": "x" * 500,
    }
    text = format_brain(leaky)
    assert "SECRET" not in text and "/usr/bin" not in text
    assert "x" * 49 not in text  # identifiers are capped


async def test_needs_and_brain_are_get_only_and_reach_the_right_endpoints() -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        assert request.headers.get("authorization") is None  # reads carry no gateway token
        if request.url.path == "/api/brain-health":
            return httpx.Response(200, json=BRAIN_HEALTH)
        return httpx.Response(200, json=SNAPSHOT)

    client = maple(handler)
    assert await command("needs", client) == format_needs(SNAPSHOT)
    assert await command("brain", client) == format_brain(BRAIN_HEALTH)
    assert seen == [("GET", "/api/snapshot"), ("GET", "/api/brain-health")]


async def test_brain_when_maple_is_unreachable() -> None:
    assert await command("brain", maple(lambda r: httpx.Response(503))) == UNREACHABLE


def test_help_lists_needs_and_brain() -> None:
    assert "/needs" in HELP and "/brain" in HELP
    assert set(COMMANDS) == {"status", "needs", "goal", "journal", "server", "memory", "brain",
                             "help"}  # fmt: skip
    for name in COMMANDS:
        assert f"/{name} " in HELP
