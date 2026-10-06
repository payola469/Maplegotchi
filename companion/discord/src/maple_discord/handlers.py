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

HELP = "\n".join(
    [
        "Talk to Maple by writing in this channel.",
        "Commands (read-only):",
        "/status — what Maple is doing and how it feels",
        "/goal — Maple's current short-term goal",
        "/journal — Maple's latest journal lines",
        "/server — what Maple sees on paolo-core",
        "/memory — things Maple remembers",
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


def format_status(snapshot: dict[str, Any]) -> str:
    maple = snapshot["maple"]
    needs = maple["needs"]
    return "\n".join(
        [
            f"{maple['identity']['name']} is {_activity(maple)}.",
            f"Mood {needs['mood']:.0f} · Energy {needs['energy']:.0f} · "
            f"Social {needs['social']:.0f} · Curiosity {needs['curiosity']:.0f}",
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


async def command(name: str, maple: MapleClient) -> str:
    """The text for a read-only slash command."""
    try:
        if name == "status":
            return format_status(await maple.snapshot())
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
