import logging
import os

import discord

from bot import settings
from bot.juno import Juno
from bot.services import get_config_service

logger = logging.getLogger("bot")

settings.print_startup_banner()

environment = os.getenv("ENVIRONMENT", "dev").lower()

config = get_config_service("config/config.yaml").load(environment=environment)

client = Juno(intents=discord.Intents.all(), config=config)
client.status = discord.Status.invisible if environment == "dev" else discord.Status.online
client.run(config.discordToken, root_logger=True)
