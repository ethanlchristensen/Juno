from discord.ext import commands
from discord import app_commands
import discord

from bot.services import MusicQueueService, YouTubeSerivce, EmbedService


class MusicCog(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.queue_service = MusicQueueService(bot)
        self.youtube_service = YouTubeSerivce()

    @app_commands.command(name="join", description="Have Juno join the VC you are currently in.")
    async def join(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message(
                "You're not in a voice channel! Please join a voice channel and try again."
            )
            return

        channel = interaction.user.voice.channel
        vc = await channel.connect()
        player = self.queue_service.get_player(interaction.guild)
        player.voice_client = vc
        await interaction.response.send_message(f"Joined {channel.name}")

    @app_commands.command(name="play", description="Play a song with a link or query.")
    @app_commands.describe(query="Song name or YouTube link")
    async def play(self, interaction: discord.Interaction, query: str):
        if not interaction.user.voice:
            await interaction.response.send_message(
                "You're not in a voice channel! Please join a voice channel and try again."
            )
            return
        
        await interaction.response.defer()

        player = self.queue_service.get_player(interaction.guild)
        info = self.youtube_service.extract_info(query)
        stream_url = info["url"]
        source = self.youtube_service.get_audio_source(stream_url)
        metadata = self.youtube_service.get_metadata(info)

        if not player.voice_client:
            channel = interaction.user.voice.channel
            vc = await channel.connect()
            player.voice_client = vc

        queue_position = player.queue.qsize() + 1
        await player.enqueue(source, metadata)

        embed_service: EmbedService = interaction.client.embed_service

        if player.voice_client.is_playing() or not player.voice_client.is_connected():
            embed = embed_service.create_added_to_queue_embed(
                metadata, queue_position, interaction.user.display_name
            )
        else:
            embed = embed_service.create_now_playing_embed(metadata)
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="skip", description="Skip actively playing audio.")
    async def skip(self, interaction: discord.Interaction):
        player = self.queue_service.get_player(interaction.guild)
        if player.voice_client and player.voice_client.is_playing():
            player.voice_client.stop()
            await interaction.response.send_message("Skipped.")
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @app_commands.command(name="pause", description="Pause the currently playing audio.")
    async def pause(self, interaction: discord.Interaction):
        player = self.queue_service.get_player(interaction.guild)
        if player.voice_client and player.voice_client.is_playing():
            player.voice_client.pause()
            await interaction.response.send_message("Paused the audio!")
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume audio that was previously paused.")
    async def pause(self, interaction: discord.Interaction):
        player = self.queue_service.get_player(interaction.guild)
        if player.voice_client and player.voice_client.is_paused():
            player.voice_client.resume()
            await interaction.response.send_message("Resumed the audio!")
        else:
            await interaction.response.send_message("Nothing is paused.", ephemeral=True)

    @app_commands.command(name="leave", description="Have Juno leave the voice channel.")
    async def leave(self, interaction: discord.Interaction):
        player = self.queue_service.get_player(interaction.guild)
        if player.voice_client:
            await player.voice_client.disconnect()
            self.queue_service.remove_player(interaction.guild)
            await interaction.response.send_message("Disconnected.")
        else:
            await interaction.response.send_message("Not connected to a voice channel.", ephemeral=True)

async def setup(bot: discord.Client):
    await bot.add_cog(MusicCog(bot))
