import logging

import discord

from bot import settings
from bot.juno import Juno
from bot.services import get_config_service

logger = logging.getLogger("bot")

settings.print_startup_banner()

config = get_config_service("config/config.json").load()

client = Juno(intents=discord.Intents.all(), config=config)
client.run(config.discordToken, root_logger=True)
