import discord
from discord import app_commands

class PingCommand(app_commands.Command):
    def __init__(self, tree: app_commands.CommandTree, args=None):
        @tree.command(name="ping",description="Ping the bot to get it's latency.")
        async def ping(interaction: discord.Interaction):
            await interaction.response.send_message(f"Pong! {round(interaction.client.latency * 1000)}ms")
