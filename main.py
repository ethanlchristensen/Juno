import os
import dotenv
import discord
import logging

from bot import settings
from bot.juno import Juno

dotenv.load_dotenv(override=True)

logger = logging.getLogger("bot")

settings.print_startup_banner()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

client = Juno(intents=intents)
client.run(os.getenv("TOKEN"), root_logger=True)