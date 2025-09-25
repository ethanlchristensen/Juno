import discord
from discord.ext import commands, tasks  # Add tasks import
from discord import app_commands
from datetime import datetime, time, timezone
import json
import os
from bot.services.ai.types import Message
from bot.utils.decarators.admin_check import is_admin
from bot.utils.decarators.command_logging import log_command_usage


class SchedulerCog(commands.Cog):  # Should be commands.Cog, not app_commands.Cog
    def __init__(self, bot):
        self.bot = bot
        self.morning_channels = self._load_morning_channels()
        self.morning_message.start()

    def _load_morning_channels(self):
        """Load morning channels from environment variable"""
        channels_str = os.getenv("MORNING_CHANNEL_IDS", "{}")
        try:
            # Parse JSON and convert keys to integers
            channels_data = json.loads(channels_str)
            return {
                int(guild_id): int(channel_id)
                for guild_id, channel_id in channels_data.items()
            }
        except (json.JSONDecodeError, ValueError) as e:
            self.bot.logger.error(f"Error parsing MORNING_CHANNEL_IDS: {e}")
            return {}

    def cog_unload(self):
        self.morning_message.cancel()

    @tasks.loop(time=time(12, 0, tzinfo=timezone.utc))
    async def morning_message(self):
        """Send motivational morning messages to all configured channels"""
        if not self.morning_channels:
            return

        for guild_id, channel_id in self.morning_channels.items():
            try:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    self.bot.logger.warning(f"Could not find guild with ID {guild_id}")
                    continue

                channel = guild.get_channel(channel_id)
                if not channel:
                    self.bot.logger.warning(
                        f"Could not find channel {channel_id} in guild {guild.name}"
                    )
                    continue

                # Generate motivational message
                messages = [
                    Message(
                        role="user",
                        content="Generate a motivational morning message for a server or users. Feel free to thrown on curve ball quotes that don't really make sense.",
                    ),
                ]

                if main_prompt := self.bot.prompts.get("main"):
                    self.bot.logger.info("Using main prompt for morning message")
                    messages.insert(0, Message(role="system", content=main_prompt))

                response = await self.bot.ai_service.chat(messages=messages)

                embed, emoji_file = self.bot.embed_service.create_morning_embed(
                    message=response.content
                )
                await channel.send(
                    embed=embed,
                    file=discord.File(
                        os.path.join(os.getcwd(), "emojis", emoji_file), emoji_file
                    ),
                )
                self.bot.logger.info(
                    f"Sent morning message to {channel.name} in {guild.name}"
                )

            except Exception as e:
                self.bot.logger.error(
                    f"Error sending morning message to guild {guild_id}: {e}"
                )

    @morning_message.before_loop
    async def before_morning_message(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="set_morning_channel",
        description="Set the morning message channel for this server",
    )
    @app_commands.describe(
        channel="The channel where morning messages will be sent (defaults to current channel)"
    )
    @log_command_usage()
    @is_admin()
    async def set_morning_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel = None
    ):
        """Set the morning message channel for this guild"""
        if channel is None:
            channel = interaction.channel

        # Update the in-memory dictionary
        self.morning_channels[interaction.guild.id] = channel.id

        await interaction.followup.send(
            content=f"Morning messages will be sent to {channel.mention}",
            ephemeral=True,
        )

        self.bot.logger.info(
            f"Set morning channel for {interaction.guild.name} to {channel.name}"
        )

    @app_commands.command(
        name="remove_morning_channel",
        description="Remove morning messages for this server",
    )
    @log_command_usage()
    @is_admin()
    async def remove_morning_channel(self, interaction: discord.Interaction):
        """Remove morning messages for this guild"""
        if interaction.guild.id in self.morning_channels:
            del self.morning_channels[interaction.guild.id]
            await interaction.followup.send(
                content="Morning messages disabled for this server.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                content="Morning messages are not configured for this server.",
                ephemeral=True,
            )

    @app_commands.command(
        name="test_morning", description="Test the morning message functionality"
    )
    @log_command_usage()
    @is_admin()
    async def test_morning_message(self, interaction: discord.Interaction):
        """Test the morning message functionality"""
        await interaction.followup.send(
            content="Sending test morning message...", ephemeral=True
        )

        try:
            # Generate motivational message
            messages = [
                Message(
                    role="user",
                    content="Generate a motivational morning message for a server or users. Feel free to thrown on curve ball quotes that don't really make sense.",
                ),
            ]

            if main_prompt := self.bot.prompts.get("main"):
                self.bot.logger.info("Using main prompt for morning message")
                messages.insert(0, Message(role="system", content=main_prompt))

            response = await self.bot.ai_service.chat(messages=messages)

            embed, emoji_file = self.bot.embed_service.create_morning_embed(
                message=response.content
            )

            await interaction.channel.send(
                embed=embed,
                file=discord.File(
                    os.path.join(os.getcwd(), "emojis", emoji_file), emoji_file
                ),
            )
            self.bot.logger.info(
                f"Sent test morning message to {interaction.channel.name} in {interaction.guild.name}"
            )

        except Exception as e:
            await interaction.followup.send(f"Error testing morning message: {e}")
            self.bot.logger.error(f"Error in test morning message: {e}")


async def setup(bot):
    await bot.add_cog(SchedulerCog(bot))
