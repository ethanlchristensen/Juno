import discord

from discord import app_commands

from bot.utils import is_admin


class SyncCommand(app_commands.Group):
    def __init__(self, tree: discord.app_commands.CommandTree, args=None):
        @tree.command(
            name="sync",
            description="Command to sync the slash commands with the guild.",
        )
        @is_admin()
        async def sync(interaction: discord.Interaction):
            print("Sync command called!")
            try:
                await tree.sync()
                embed = discord.Embed()
                embed.color = 0x00FF00
                embed.title = "Command Tree synced!"
                embed.description = ""
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                embed = discord.Embed()
                embed.color = 0xFF0000
                embed.title = "Command Tree failed to sync!"
                embed.description = str(e)
                await interaction.followup.send(embed=embed, ephemeral=True)
