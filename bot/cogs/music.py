import discord

from discord.ext import commands
from discord import app_commands
from typing import TYPE_CHECKING, Optional

from bot.services.music.types import FilterPreset
from bot.services.embed_service import QueuePaginationView
from bot.utils.decarators.command_logging import log_command_usage
from bot.utils.decarators.voice_check import require_voice_channel

if TYPE_CHECKING:
    from bot.juno import Juno


class MusicCog(commands.Cog):
    def __init__(self, bot: "Juno"):
        self.bot = bot

    @app_commands.command(
        name="join", description="Have Juno join the VC you are currently in."
    )
    @log_command_usage()
    @require_voice_channel(ephemeral=True)
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
    @app_commands.choices(filter=FilterPreset.get_choices())
    @log_command_usage()
    @require_voice_channel(ephemeral=True)
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

        if not player.voice_client:
            channel = interaction.user.voice.channel
            vc = await channel.connect(self_deaf=True)
            player.voice_client = vc

        queue_position = player.queue.qsize() + 1
        await player.enqueue(
            metadata.url, metadata, filter_preset, text_channel=interaction.channel
        )

        if player.is_playing:
            embed = self.bot.embed_service.create_added_to_queue_embed(
                metadata, queue_position, interaction.user.display_name
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("Starting playback...", ephemeral=True)

    @app_commands.command(name="skip", description="Skip actively playing audio.")
    @log_command_usage()
    @require_voice_channel(ephemeral=True)
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
    @require_voice_channel(ephemeral=True)
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
    @require_voice_channel(ephemeral=True)
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
    @require_voice_channel(ephemeral=True)
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
    @require_voice_channel(ephemeral=True)
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
    @app_commands.choices(new_filter=FilterPreset.get_choices())
    @log_command_usage()
    @require_voice_channel(ephemeral=True)
    async def filter(
        self,
        interaction: discord.Interaction,
        new_filter: app_commands.Choice[str],
    ):
        player = self.bot.music_queue_service.get_player(interaction.guild)
        filter_enum = FilterPreset.from_value(new_filter.value)

        if await player.set_filter(filter_enum):
            await interaction.response.send_message(
                f"Applied filter: `{filter_enum.display_name}`"
            )
        else:
            await interaction.response.send_message(
                "No song is currently playing to apply a filter to.", ephemeral=True
            )


async def setup(bot: discord.Client):
    await bot.add_cog(MusicCog(bot))
