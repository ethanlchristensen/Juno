import logging

import discord

from bot import settings
from bot.juno import Juno
from bot.services import get_config_service

logger = logging.getLogger("bot")

settings.print_startup_banner()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

config = get_config_service("config.json").load()

client = Juno(intents=intents, config=config)
client.run(config.discordToken, root_logger=True)
