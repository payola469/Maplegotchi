"""What the gateway does, separated from Discord's library so it can be tested.

- Ordinary messages from Paolo in #maple-chat are conversations with Maple.
- Slash commands are read-only utilities (no mutation, no admin).
- If Maple cannot be reached, the gateway says so; Maple is never affected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from maple_discord.config import GatewaySettings
from maple_discord.maple_client import MapleClient, MapleUnavailable

DISCORD_LIMIT = 2000
UNREACHABLE = "Maple can't be reached right now. I'll be here when Maple is back."
OWNER_ONLY = "Only Paolo can ask me that."

# Slash commands as registered with Discord (all read-only, owner-only).
COMMANDS = {
    "status": "What Maple is doing and how it feels",
    "needs": "Maple's mood, energy, social and curiosity",
    "goal": "Maple's current short-term goal",
    "journal": "Maple's latest journal lines",
    "server": "What Maple sees on paolo-core",
    "memory": "Things Maple remembers",
    "brain": "How Maple's AI brain is doing",
    "help": "What you can do here",
}

HELP = "\n".join(
    [
        "Talk to Maple by writing in this channel.",
        "Commands (read-only):",
        "/status — what Maple is doing and how it feels",
        "/needs — Maple's mood, energy, social and curiosity",
        "/goal — Maple's current short-term goal",
        "/journal — Maple's latest journal lines",
        "/server — what Maple sees on paolo-core",
        "/memory — things Maple remembers",
        "/brain — how Maple's AI brain is doing",
        "/help — this list",
    ]
)


@dataclass(frozen=True)
class ChatMessage:
    """The parts of a Discord message the gateway uses."""

    id: int
    channel_id: int
    author_id: int
    author_is_bot: bool
    content: str


def is_conversation(message: ChatMessage, settings: GatewaySettings) -> bool:
    """Only Paolo's own, non-empty messages in #maple-chat."""
    return (
        not message.author_is_bot
        and message.channel_id == settings.channel_id
        and message.author_id == settings.owner_id
        and bool(message.content.strip())
    )


def may_use_commands(user_id: int, settings: GatewaySettings) -> bool:
    return user_id == settings.owner_id


def split_for_discord(text: str, limit: int = DISCORD_LIMIT) -> list[str]:
    """Discord messages are at most 2000 characters; split on line breaks when possible."""
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip("\n")
    chunks.append(text)
    return chunks


async def answer(message: ChatMessage, maple: MapleClient) -> str:
    """Maple's reply to one of Paolo's messages (or a short notice if Maple is down)."""
    text = message.content.strip()[:2000]
    try:
        result = await maple.converse(str(message.id), text)
    except MapleUnavailable:
        return UNREACHABLE
    return str(result["reply"])


# ---------------------------------------------------------------- commands


def _activity(maple: dict[str, Any]) -> str:
    activity = maple.get("activity", {})
    kind = str(activity.get("kind", "something")).replace("_", " ")
    task = activity.get("task")
    if task:
        kind += f" “{task.get('title', '')}”"
    if activity.get("phase") == "walking":
        return (
            f"on the way to {str(activity.get('furniture', '')).replace('_', ' ')} to start {kind}"
        )
    return kind


def format_needs(snapshot: dict[str, Any]) -> str:
    needs = snapshot["maple"]["needs"]
    return (
        f"Mood {needs['mood']:.0f} · Energy {needs['energy']:.0f} · "
        f"Social {needs['social']:.0f} · Curiosity {needs['curiosity']:.0f}"
    )


def format_status(snapshot: dict[str, Any]) -> str:
    maple = snapshot["maple"]
    return "\n".join(
        [
            f"{maple['identity']['name']} is {_activity(maple)}.",
            format_needs(snapshot),
            f"Expression: {maple['expression']}.",
        ]
    )


def format_goal(snapshot: dict[str, Any]) -> str:
    goal = snapshot["maple"].get("goal")
    if not goal:
        return "Maple has no goal at the moment."
    return f"Goal: {goal['summary']} ({goal['type']}, until {goal['horizon_until'][11:16]} UTC)."


def format_journal(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "Maple hasn't written in the journal yet."
    return "\n".join(f"• {e['text']}" for e in entries[-5:])


def format_server(snapshot: dict[str, Any]) -> str:
    server = snapshot["server"]
    lines = [f"Server summary: {str(server['summary']).replace('_', ' ')}."]
    for service in server.get("services", []):
        state = service.get("state") or service.get("status")
        lines.append(f"• {service['service_id']}: {state}")
    return "\n".join(lines)


def format_memory(memories: list[dict[str, Any]]) -> str:
    if not memories:
        return "Maple has no long-term memories yet."
    return "\n".join(f"• {m['text']}" for m in memories[-8:])


def _short(value: object, limit: int = 48) -> str:
    """A short identifier from the API, or "unknown"; never more than `limit` chars."""
    text = str(value).strip() if value is not None else ""
    return text[:limit] if text.isprintable() and text else "unknown"


def _caller(label: str, caller: dict[str, Any]) -> str:
    mode = _short(caller.get("mode"))
    if mode != "external":
        return f"{label}: {mode}"
    line = f"{label}: external ({_short(caller.get('name'))})"
    last = caller.get("last_call")
    if not last:
        line += " — no calls yet"
    else:
        result = "ok" if last.get("ok") else f"fell back ({_short(last.get('code'))})"
        line += f" — last call {result}"
        if isinstance(last.get("latency_ms"), int):
            line += f", {last['latency_ms'] / 1000:.1f} s"
        line += f", {str(last.get('at', ''))[11:16]} UTC"
    counts = [caller.get(k) for k in ("fallbacks_today", "timeouts_today")]
    fallbacks, timeouts = (c if isinstance(c, int) else 0 for c in counts)
    if fallbacks or timeouts:
        line += f" · today {fallbacks} fallback(s), {timeouts} timeout(s)"
    return line


def format_brain(health: dict[str, Any]) -> str:
    """Brain Health in a few lines. Only these allowlisted fields are ever shown."""
    lines = [f"Brain: {_short(health.get('status'))} ({_short(health.get('status_reason'))})"]
    if health.get("provider") or health.get("model"):
        provider, model = _short(health.get("provider")), _short(health.get("model"))
        lines.append(f"Provider {provider} · model {model}")
    companion = health.get("companion") or {}
    if companion.get("probed") and not companion.get("reachable"):
        lines.append(f"Companion unreachable ({_short(companion.get('error'))})")
    lines.append(_caller("Director", health.get("director") or {}))
    lines.append(_caller("Replier", health.get("replier") or {}))
    return "\n".join(lines)


async def command(name: str, maple: MapleClient) -> str:
    """The text for a read-only slash command."""
    try:
        if name == "status":
            return format_status(await maple.snapshot())
        if name == "needs":
            return format_needs(await maple.snapshot())
        if name == "brain":
            return format_brain(await maple.brain_health())
        if name == "goal":
            return format_goal(await maple.snapshot())
        if name == "journal":
            return format_journal(await maple.journal())
        if name == "server":
            return format_server(await maple.snapshot())
        if name == "memory":
            return format_memory(await maple.memory())
    except MapleUnavailable:
        return UNREACHABLE
    return HELP
