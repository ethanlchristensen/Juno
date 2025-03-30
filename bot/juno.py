import os
import discord

from discord import app_commands
from discord.ext import commands

from bot.utils import JunoSlash
from bot.services import AiServiceFactory, EmbedService


class Juno(commands.Bot):
    def __init__(self, intents):
        super().__init__(command_prefix="!", intents=intents)
        self.juno_slash = JunoSlash(self.tree)
        self.ai_service = AiServiceFactory.get_service(
            provider=os.getenv("PREFERRED_PROVIDER", "openai")
        )
        self.embed_service = EmbedService()

    async def setup_hook(self):
        self.juno_slash.load_commands()
        await self.load_extension("bot.cogs.music")

    async def on_ready(self):
        print(f"✅ Logged in as {self.user} ({self.user.id})")
