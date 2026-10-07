"""The Discord wiring: a thin adapter over `handlers` (ADR-0032).

Needs the privileged "Message Content" intent to read Paolo's messages in
#maple-chat. Slash commands are registered to the one configured guild only.
"""

from __future__ import annotations

from typing import Any

import discord
from discord import app_commands

from maple_discord.config import GatewaySettings
from maple_discord.handlers import (
    COMMANDS,
    OWNER_ONLY,
    ChatMessage,
    answer,
    command,
    is_conversation,
    may_use_commands,
    split_for_discord,
)
from maple_discord.maple_client import MapleClient


class MapleBot(discord.Client):
    def __init__(self, settings: GatewaySettings, maple: MapleClient) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self.settings = settings
        self.maple = maple
        self.tree = app_commands.CommandTree(self)
        guild = discord.Object(id=settings.guild_id)
        for name, description in COMMANDS.items():
            self.tree.add_command(self._make_command(name, description), guild=guild)

    def _make_command(self, name: str, description: str) -> app_commands.Command[Any, ..., None]:
        async def run(interaction: discord.Interaction) -> None:
            if not may_use_commands(interaction.user.id, self.settings):
                await interaction.response.send_message(OWNER_ONLY, ephemeral=True)
                return
            await interaction.response.defer(thinking=True)
            text = await command(name, self.maple)
            chunks = split_for_discord(text) or ["…"]
            await interaction.followup.send(chunks[0])
            for chunk in chunks[1:]:
                await interaction.followup.send(chunk)

        return app_commands.Command(name=name, description=description, callback=run)

    async def setup_hook(self) -> None:
        await self.tree.sync(guild=discord.Object(id=self.settings.guild_id))

    async def on_message(self, message: discord.Message) -> None:
        incoming = ChatMessage(
            id=message.id,
            channel_id=message.channel.id,
            author_id=message.author.id,
            author_is_bot=message.author.bot,
            content=message.content,
        )
        if not is_conversation(incoming, self.settings):
            return
        async with message.channel.typing():
            reply = await answer(incoming, self.maple)
        for chunk in split_for_discord(reply):
            await message.reply(chunk, mention_author=False)

    async def close(self) -> None:
        await self.maple.aclose()
        await super().close()
