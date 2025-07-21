import discord

from discord import app_commands

from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.admin_check import is_admin

class EchoCommand(app_commands.Command):
    def __init__(self, tree: app_commands.CommandTree, args=None):
        @tree.command(name="echo", description="Send a message as the bot with optional attachment")
        @log_command_usage()
        @is_admin()
        async def echo(interaction: discord.Interaction, message: str, attachment: discord.Attachment = None):
            await interaction.response.defer(ephemeral=True)
            
            # Send the message to the same channel
            if attachment:
                await interaction.followup.send(message, file=await attachment.to_file())
            else:
                await interaction.followup.send(message)