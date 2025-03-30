from discord.ext import commands
from discord import app_commands
import discord
from typing import TYPE_CHECKING, Optional

from bot.services import (
    MusicQueueService,
    AudioService,
    EmbedService,
    FilterPreset,
    QueuePaginationView,
)

if TYPE_CHECKING:
    from bot.juno import Juno


class MusicCog(commands.Cog):
    def __init__(self, bot: "Juno"):
        self.bot = bot

    @app_commands.command(
        name="join", description="Have Juno join the VC you are currently in."
    )
    async def join(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message(
                "You're not in a voice channel! Please join a voice channel and try again."
            )
            return

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
    async def play(
        self, interaction: discord.Interaction, query: str, filter: Optional[str]
    ):
        if not interaction.user.voice:
            await interaction.response.send_message(
                "You're not in a voice channel! Please join a voice channel and try again."
            )
            return

        await interaction.response.defer(ephemeral=True)

        player = self.bot.music_queue_service.get_player(interaction.guild)
        info = self.bot.audio_service.extract_info(query)

        filter_preset = FilterPreset.from_value(filter)
        metadata = self.bot.audio_service.get_metadata(info)
        metadata.filter_preset = filter_preset

        if not player.voice_client:
            channel = interaction.user.voice.channel
            vc = await channel.connect(self_deaf=True)
            player.voice_client = vc

        queue_position = player.queue.qsize() + 1
        await player.enqueue(
            metadata.url, metadata, filter_preset, text_channel=interaction.channel
        )

        if player.voice_client.is_playing() or not player.voice_client.is_connected():
            embed = self.bot.embed_service.create_added_to_queue_embed(
                metadata, queue_position, interaction.user.display_name
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("Starting playback...", ephemeral=True)

    @app_commands.command(name="skip", description="Skip actively playing audio.")
    async def skip(self, interaction: discord.Interaction):
        player = self.bot.music_queue_service.get_player(interaction.guild)
        if player.voice_client and player.voice_client.is_playing():
            player.voice_client.stop()
            await interaction.response.send_message("Skipped.")
        else:
            await interaction.response.send_message(
                "Nothing is playing.", ephemeral=True
            )

    @app_commands.command(
        name="pause", description="Pause the currently playing audio."
    )
    async def pause(self, interaction: discord.Interaction):
        player = self.bot.music_queue_service.get_player(interaction.guild)
        if player.voice_client and player.voice_client.is_playing():
            player.voice_client.pause()
            await interaction.response.send_message("Paused the audio!")
        else:
            await interaction.response.send_message(
                "Nothing is playing.", ephemeral=True
            )

    @app_commands.command(
        name="resume", description="Resume audio that was previously paused."
    )
    async def resume(self, interaction: discord.Interaction):
        player = self.bot.music_queue_service.get_player(interaction.guild)
        if player.voice_client and player.voice_client.is_paused():
            player.voice_client.resume()
            await interaction.response.send_message("Resumed the audio!")
        else:
            await interaction.response.send_message(
                "Nothing is paused.", ephemeral=True
            )

    @app_commands.command(
        name="leave", description="Have Juno leave the voice channel."
    )
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
    async def queue(self, interaction: discord.Interaction):
        player = self.bot.music_queue_service.get_player(interaction.guild)

        queue_items = list(player.queue._queue)

        embed = self.bot.embed_service.create_queue_embed(
            queue_items=queue_items,
            current_track=player.current,
            page=1,
            items_per_page=5,
        )

        view = QueuePaginationView(queue_items, player.current, self.bot.embed_service)

        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: discord.Client):
    await bot.add_cog(MusicCog(bot))
