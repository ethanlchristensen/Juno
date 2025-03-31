import os
import time
import discord
import logging

from discord.ext import commands

from bot.utils import JunoSlash
from bot.services import AiServiceFactory, EmbedService, AudioService, MusicQueueService


class Juno(commands.Bot):
    def __init__(self, intents):
        status = (
            discord.Status.invisible
            if bool(int(os.getenv("INVISIBLE")))
            else discord.Status.online
        )
        super().__init__(
            command_prefix="!", intents=intents, status=status, activity=None
        )
        self.start_time = time.time()
        self.juno_slash = JunoSlash(self.tree)
        self.ai_service = AiServiceFactory.get_service(
            provider=os.getenv("PREFERRED_PROVIDER", "openai")
        )
        self.embed_service = EmbedService()
        self.audio_service = AudioService()
        self.music_queue_service = MusicQueueService(self)
        self.logger = logging.getLogger("bot")
        self.logger.info("Initialization complete!")

    async def setup_hook(self):
        self.juno_slash.load_commands()
        await self.load_cogs()
        await self.tree.sync()

    async def load_cogs(self):
        cogs_dir = os.path.join(os.getcwd(), "bot", "cogs")
        self.logger.info(f"📁 Looking for cogs in: {cogs_dir}")

        cog_files = [
            f[:-3]
            for f in os.listdir(cogs_dir)
            if f.endswith(".py") and f != "__init__.py"
        ]

        total = len(cog_files)
        loaded_successfully = 0

        self.logger.info(f"📁 Found {total} cogs to load")

        for cog_name in cog_files:
            extension_path = f"bot.cogs.{cog_name}"

            try:
                await self.load_extension(extension_path)
                loaded_successfully += 1
                self.logger.info(f"✅ Successfully loaded cog: {cog_name}")
            except Exception as e:
                self.logger.error(f"❌ Failed to load cog {cog_name}: {str(e)}")

        if loaded_successfully == total:
            self.logger.info(f"🎉 All {loaded_successfully} cogs loaded successfully!")
        else:
            self.logger.info(f"📊 Cogs loaded: {loaded_successfully}/{total}")

    async def on_ready(self):
        startup_time = time.time() - self.start_time

        self.logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        self.logger.info(f"Startup completed in {startup_time:.2f} seconds")

        guild_count = len(self.guilds)
        user_count = sum(g.member_count for g in self.guilds)

        self.logger.info(
            f"🌐 Connected to {guild_count} guilds with access to {user_count} users"
        )
        self.logger.info(f"✅ Juno is online!")
