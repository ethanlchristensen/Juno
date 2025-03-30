import asyncio
import discord

from typing import Dict, TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from bot.juno import Juno


class MusicPlayer:
    def __init__(self, bot: "Juno", guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.queue = asyncio.Queue()
        self.voice_client: discord.VoiceClient = None
        self.next = asyncio.Event()
        self.current = None
        self.text_channel: Optional[discord.TextChannel] = None

    async def play_loop(self):
        while True:
            self.next.clear()
            try:
                self.current = await self.queue.get()

                if not self.voice_client or not self.voice_client.is_connected():
                    print(f"Voice client not connected for guild {self.guild.id}")
                    continue

                try:
                    url = self.current["url"]
                    filter_preset = self.current.get("filter_preset")

                    audio_service = self.bot.audio_service
                    source = audio_service.get_audio_source(url, filter_preset)

                    self.voice_client.play(
                        source,
                        after=lambda x: self.bot.loop.call_soon_threadsafe(
                            self.next.set
                        ),
                    )

                    if self.text_channel:
                        embed = self.bot.embed_service.create_now_playing_embed(
                            self.current["metadata"]
                        )
                        await self.text_channel.send(embed=embed)

                except Exception as e:
                    print(f"Error creating audio source: {e}")
                    import traceback

                    traceback.print_exc()
                    self.next.set()
                    continue

                await self.next.wait()
            except Exception as e:
                print(f"Error in play_loop for guild {self.guild.id}: {e}")

    async def enqueue(self, url, metadata, filter_preset=None, text_channel=None):
        # Store the text channel to send notifications to
        if text_channel:
            self.text_channel = text_channel

        await self.queue.put(
            {"url": url, "metadata": metadata, "filter_preset": filter_preset}
        )


class MusicQueueService:
    def __init__(self, bot):
        self.bot = bot
        self.players: Dict[int, MusicPlayer] = {}

    def get_player(self, guild: discord.Guild) -> MusicPlayer:
        if guild.id not in self.players:
            player = MusicPlayer(self.bot, guild)
            self.players[guild.id] = player
            self.bot.loop.create_task(player.play_loop())
        return self.players[guild.id]

    def remove_player(self, guild: discord.Guild):
        if guild.id in self.players:
            del self.players[guild.id]