import json
import os
from datetime import UTC, datetime

import discord
import pytz
from discord import app_commands
from discord.ext import commands, tasks

from bot.services.ai.types import Message
from bot.utils.decarators.admin_check import is_admin
from bot.utils.decarators.command_logging import log_command_usage


class SchedulerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.morning_configs = self._load_morning_configs()
        self.check.start()

    def _load_morning_configs(self):
        """Load morning configurations from environment variable"""
        configs_path = os.getenv("MORNING_CONFIGS_PATH", "morning_configs.json")

        if not os.path.exists(configs_path):
            # create the file
            with open(configs_path, "w") as f:
                json.dump({}, f)

        try:
            with open(configs_path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.bot.logger.error(f"Error loading morning configs: {e}")
            return {}

    def _save_morning_configs(self):
        """Save morning configurations to JSON file"""
        configs_path = os.getenv("MORNING_CONFIGS_PATH", "morning_configs.json")
        try:
            with open(configs_path, "w") as f:
                json.dump(self.morning_configs, f, indent=4)
            self.bot.logger.info(f"Morning configs saved to {configs_path}")
        except Exception as e:
            self.bot.logger.error(f"Error saving morning configs: {e}")

    def cog_unload(self):
        self.check.cancel()

    @tasks.loop(minutes=1)
    async def check(self):
        """Check each guild's configured time and send messages when appropriate"""
        if not self.morning_configs:
            return

        now_utc = datetime.now(UTC)

        for guild_id, config in self.morning_configs.items():
            try:
                # Get the configured time in the configured timezone
                guild_tz = config.get("timezone", "UTC")
                try:
                    tz = pytz.timezone(guild_tz)
                except pytz.exceptions.UnknownTimeZoneError:
                    self.bot.logger.warning(f"Unknown timezone for guild {guild_id}: {guild_tz}, defaulting to UTC")
                    tz = pytz.UTC

                # Get current time in the guild's timezone
                now_in_guild_tz = now_utc.astimezone(tz)

                # Check if it's time to send the message
                if now_in_guild_tz.hour == config.get("hour", 12) and now_in_guild_tz.minute < config.get("minute", 0) + 1:  # 1-minute window to account for loop interval
                    channel_id = config.get("channel_id")
                    if not channel_id:
                        continue

                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        self.bot.logger.warning(f"Could not find guild with ID {guild_id}")
                        continue

                    channel = guild.get_channel(int(channel_id))
                    if not channel:
                        self.bot.logger.warning(f"Could not find channel {channel_id} in guild {guild.name}")
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

                    embed, emoji_file = self.bot.embed_service.create_morning_embed(message=response.content)
                    await channel.send(
                        embed=embed,
                        file=discord.File(os.path.join(os.getcwd(), "emojis", emoji_file), emoji_file),
                    )
                    self.bot.logger.info(f"Sent morning message to {channel.name} in {guild.name}")
            except Exception as e:
                self.bot.logger.error(f"Error sending morning message to guild {guild_id}: {e}")

    @check.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="set_morning_channel",
        description="Set the morning message channel for this server",
    )
    @app_commands.describe(channel="The channel where morning messages will be sent (defaults to current channel)")
    @log_command_usage()
    @is_admin()
    async def set_morning_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Set the morning message channel for this guild"""
        if channel is None:
            channel = interaction.channel

        # Get existing config or create new one
        guild_id = str(interaction.guild.id)
        config = self.morning_configs.get(guild_id, {"hour": 12, "minute": 0, "timezone": "UTC"})

        # Update channel
        config["channel_id"] = channel.id
        self.morning_configs[guild_id] = config

        # Save configs
        self._save_morning_configs()

        timezone = config.get("timezone", "UTC")
        await interaction.followup.send(
            content=f"Morning messages will be sent to {channel.mention} at {config['hour']}:{config['minute']:02d} {timezone}",
            ephemeral=True,
        )

        self.bot.logger.info(f"Set morning channel for {interaction.guild.name} to {channel.name}")

    @app_commands.command(
        name="set_morning_time",
        description="Set the time for morning messages",
    )
    @app_commands.describe(
        hour="Hour (0-23)",
        minute="Minute (0-59)",
        timezone="Timezone (e.g., 'US/Eastern', 'Europe/London', defaults to UTC)",
    )
    @log_command_usage()
    @is_admin()
    async def set_morning_time(
        self,
        interaction: discord.Interaction,
        hour: int,
        minute: int = 0,
        timezone: str = "UTC",
    ):
        """Set the time for morning messages"""
        # Validate input
        if hour < 0 or hour > 23:
            await interaction.followup.send(content="Hour must be between 0 and 23.", ephemeral=True)
            return

        if minute < 0 or minute > 59:
            await interaction.followup.send(content="Minute must be between 0 and 59.", ephemeral=True)
            return

        # Validate timezone
        try:
            pytz.timezone(timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            await interaction.followup.send(
                content=f"Unknown timezone: '{timezone}'. Please use a valid timezone like 'US/Eastern' or 'Europe/London'.",
                ephemeral=True,
            )
            return

        # Get existing config or create new one
        guild_id = interaction.guild.id
        config = self.morning_configs.get(str(guild_id), {})

        # Update time and timezone
        config["hour"] = hour
        config["minute"] = minute
        config["timezone"] = timezone
        self.morning_configs[str(guild_id)] = config

        # Save configs
        self._save_morning_configs()

        # Format response based on whether channel is set
        if "channel_id" in config and config["channel_id"]:
            channel = interaction.guild.get_channel(config["channel_id"])
            channel_mention = channel.mention if channel else "unknown channel"
            await interaction.followup.send(
                content=f"Morning messages will be sent to {channel_mention} at {hour}:{minute:02d} {timezone}",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                content=f"Morning message time set to {hour}:{minute:02d} {timezone}, but no channel has been set yet. Use /set_morning_channel to complete setup.",
                ephemeral=True,
            )

        self.bot.logger.info(f"Set morning time for {interaction.guild.name} to {hour}:{minute:02d} {timezone}")

    @app_commands.command(
        name="remove_morning_channel",
        description="Remove morning messages for this server",
    )
    @log_command_usage()
    @is_admin()
    async def remove_morning_channel(self, interaction: discord.Interaction):
        """Remove morning messages for this guild"""
        if interaction.guild.id in self.morning_configs:
            del self.morning_configs[interaction.guild.id]
            self._save_morning_configs()
            await interaction.followup.send(content="Morning messages disabled for this server.", ephemeral=True)
        else:
            await interaction.followup.send(
                content="Morning messages are not configured for this server.",
                ephemeral=True,
            )

    @app_commands.command(name="test_morning", description="Test the morning message functionality")
    @log_command_usage()
    @is_admin()
    async def test_morning_message(self, interaction: discord.Interaction):
        """Test the morning message functionality"""
        await interaction.followup.send(content="Sending test morning message...", ephemeral=True)

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

            embed, emoji_file = self.bot.embed_service.create_morning_embed(message=response.content)

            await interaction.channel.send(
                embed=embed,
                file=discord.File(os.path.join(os.getcwd(), "emojis", emoji_file), emoji_file),
            )
            self.bot.logger.info(f"Sent test morning message to {interaction.channel.name} in {interaction.guild.name}")

        except Exception as e:
            await interaction.followup.send(f"Error testing morning message: {e}")
            self.bot.logger.error(f"Error in test morning message: {e}")

    @app_commands.command(
        name="list_timezones",
        description="List available timezones for morning message scheduling",
    )
    @log_command_usage()
    @is_admin()
    async def list_timezones(self, interaction: discord.Interaction):
        """List common timezones that can be used"""
        common_timezones = [
            "UTC",
            "US/Eastern",
            "US/Central",
            "US/Mountain",
            "US/Pacific",
            "Europe/London",
            "Europe/Berlin",
            "Europe/Moscow",
            "Asia/Tokyo",
            "Asia/Shanghai",
            "Australia/Sydney",
            "Pacific/Auckland",
        ]

        timezone_text = "**Available Timezones:**\n" + "\n".join(common_timezones)
        timezone_text += "\n\nFor a full list of timezones, see: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"

        await interaction.followup.send(content=timezone_text, ephemeral=True)


async def setup(bot):
    await bot.add_cog(SchedulerCog(bot))
