import discord

from discord.ext import commands
from discord import app_commands
from typing import TYPE_CHECKING, Optional, List

from bot.services.music.types import FilterPreset
from bot.services.embed_service import QueuePaginationView
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.voice_check import require_voice_channel

if TYPE_CHECKING:
    from bot.juno import Juno


class MusicCog(commands.Cog):
    def __init__(self, bot: "Juno"):
        self.bot = bot

    async def filter_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for filter presets"""
        choices = []
        current_lower = current.lower()
        
        for preset in FilterPreset:
            # Filter based on user input
            if (current_lower in preset.display_name.lower() or 
                current_lower in preset.value.lower()):
                choices.append(
                    app_commands.Choice(name=preset.display_name, value=preset.value)
                )
                
                # Discord limits autocomplete to 25 choices
                if len(choices) >= 25:
                    break
                    
        return choices

    @app_commands.command(
        name="join", description="Have Juno join the VC you are currently in."
    )
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    async def join(self, interaction: discord.Interaction):
        channel = interaction.user.voice.channel
        vc = await channel.connect(self_deaf=True)
        player = self.bot.music_queue_service.get_player(interaction.guild)
        player.voice_client = vc
        await interaction.response.send_message(f"Joined {channel.name}")

    @app_commands.command(name="play", description="Play a song with a link or query.")
    @app_commands.describe(
        query="Song name or YouTube link", filter="Audio filter to apply"
    )
    @app_commands.autocomplete(filter=filter_autocomplete)
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    async def play(
        self, interaction: discord.Interaction, query: str, filter: Optional[str]
    ):
        await interaction.response.defer(ephemeral=True)

        player = self.bot.music_queue_service.get_player(interaction.guild)
        info = self.bot.audio_service.extract_info(query)

        filter_preset = FilterPreset.from_value(filter)
        metadata = self.bot.audio_service.get_metadata(info)
        metadata.filter_preset = filter_preset
        metadata.requested_by = interaction.user.name

        try:
            if not player.voice_client:
                channel = interaction.user.voice.channel
                vc = await channel.connect(self_deaf=True)
                player.voice_client = vc
        except discord.ClientException:
            # If the bot is already connected, let's grab the vc.
            player.voice_client = interaction.guild.voice_client
        except Exception as e:
            await interaction.followup.send(
                f"Failed to join voice channel: {e}", ephemeral=True
            )
            return
        

        queue_position = player.queue.qsize() + 1
        
        should_start_playback = not player.is_playing and player.queue.qsize() == 1

        await player.enqueue(
            metadata.url, metadata, filter_preset, text_channel=interaction.channel
        )

        if should_start_playback:
            await interaction.followup.send("Starting playback...", ephemeral=True)
        else:
            queue_position = player.queue.qsize()
            embed = self.bot.embed_service.create_added_to_queue_embed(
                metadata, queue_position, interaction.user.display_name
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="skip", description="Skip actively playing audio.")
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    async def skip(self, interaction: discord.Interaction):
        player = self.bot.music_queue_service.get_player(interaction.guild)

        if await player.skip():
            await interaction.response.send_message("Skipped to next track.")
        else:
            await interaction.response.send_message(
                "Nothing is playing.", ephemeral=True
            )

    @app_commands.command(
        name="pause", description="Pause the currently playing audio."
    )
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    async def pause(self, interaction: discord.Interaction):
        player = self.bot.music_queue_service.get_player(interaction.guild)

        if await player.pause():
            await interaction.response.send_message("Paused the audio!")
        else:
            await interaction.response.send_message(
                "No audio is playing!", ephemeral=True
            )

    @app_commands.command(
        name="resume", description="Resume audio that was previously paused."
    )
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    async def resume(self, interaction: discord.Interaction):
        player = self.bot.music_queue_service.get_player(interaction.guild)

        if await player.resume():
            await interaction.response.send_message("Resumed the audio!")
        else:
            await interaction.response.send_message(
                "No audio is available to resume!", ephemeral=True
            )

    @app_commands.command(
        name="leave", description="Have Juno leave the voice channel."
    )
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    async def leave(self, interaction: discord.Interaction):
        player = self.bot.music_queue_service.get_player(interaction.guild)
        if player.voice_client:
            await player.voice_client.disconnect()
            self.bot.music_queue_service.remove_player(interaction.guild)
            await interaction.response.send_message("Disconnected.")
        else:
            await interaction.response.send_message(
                "Not connected to a voice channel.", ephemeral=True
            )

    @app_commands.command(name="queue", description="View the current music queue.")
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    async def queue(self, interaction: discord.Interaction):
        player = self.bot.music_queue_service.get_player(interaction.guild)

        # Get a copy of the queue items
        queue_items = list(player.queue._queue)

        embed = self.bot.embed_service.create_queue_embed(
            queue_items=queue_items,
            current_track=player.current,
            page=1,
            items_per_page=5,
        )

        view = QueuePaginationView(queue_items, player.current, self.bot.embed_service)

        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(
        name="filter", description="Apply a new audio filter to the current track."
    )
    @app_commands.autocomplete(new_filter=filter_autocomplete)
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    async def filter(
        self,
        interaction: discord.Interaction,
        new_filter: str,
    ):
        player = self.bot.music_queue_service.get_player(interaction.guild)
        filter_enum = FilterPreset.from_value(new_filter)

        if await player.set_filter(filter_enum):
            await interaction.response.send_message(
                f"Applied filter: `{filter_enum.display_name}`"
            )
        else:
            await interaction.response.send_message(
                "No song is currently playing to apply a filter to.", ephemeral=True
            )


    @app_commands.command(
        name="seek", description="Seek to a specific position in the current song."
    )
    @app_commands.describe(
        hours="Hours (optional)",
        minutes="Minutes (optional)",
        seconds="Seconds (optional)"
    )
    @log_command_usage()
    @require_voice_channel(ephemeral=True, allow_admin_bypass=True)
    async def seek(
        self,
        interaction: discord.Interaction,
        hours: Optional[int] = 0,
        minutes: Optional[int] = 0,
        seconds: Optional[int] = 0,
    ):
        player = self.bot.music_queue_service.get_player(interaction.guild)
        
        if not player.current:
            await interaction.response.send_message(
                "No song is currently playing.", ephemeral=True
            )
            return
        
        # Validate inputs
        if hours < 0 or minutes < 0 or seconds < 0:
            await interaction.response.send_message(
                "Please provide non-negative values for hours, minutes, and seconds.", 
                ephemeral=True
            )
            return
        
        # If no values were provided, default to beginning of the song
        if hours == 0 and minutes == 0 and seconds == 0:
            await interaction.response.send_message(
                "Please specify at least one time value (hours, minutes, or seconds).",
                ephemeral=True
            )
            return
        
        # Calculate total seconds
        total_seconds = (hours * 3600) + (minutes * 60) + seconds
        
        # Check if position exceeds song duration
        duration = player.current.get("metadata").duration
        if duration and total_seconds > duration:
            minutes, seconds = divmod(duration, 60)
            hours, minutes = divmod(minutes, 60)
            time_format = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"
            await interaction.response.send_message(
                f"Cannot seek to {total_seconds} seconds. Song is only {time_format} long.",
                ephemeral=True
            )
            return
        
        if await player.seek(total_seconds):
            # Format time for display
            m, s = divmod(total_seconds, 60)
            h, m = divmod(m, 60)
            time_format = ""
            if h > 0:
                time_format += f"{h}h "
            if m > 0 or h > 0:
                time_format += f"{m}m "
            time_format += f"{s}s"
            
            await interaction.response.send_message(f"Seeked to {time_format}")
        else:
            await interaction.response.send_message(
                "Failed to seek. Make sure a song is playing.", ephemeral=True
            )

async def setup(bot: discord.Client):
    await bot.add_cog(MusicCog(bot))
