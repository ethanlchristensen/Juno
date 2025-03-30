import discord

from discord import app_commands

from bot.services import AIChatResponse, Message

class ChatCommand(app_commands.Command):
    def __init__(self, tree: app_commands.CommandTree, args=None):
        @tree.command(name="chat", description="Command to chat will llms")
        async def chat(interaction: discord.Interaction, message: str):
            await interaction.response.defer(ephemeral=False)

            response: AIChatResponse = interaction.client.ai_service.chat(messages=[Message(role="user", content=message)])

            await interaction.followup.send(response.content)
