import os
import dotenv
import discord
import logging

from bot.juno import Juno

dotenv.load_dotenv(override=True)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

client = Juno(intents=intents)

client.run(os.getenv("TOKEN"))
