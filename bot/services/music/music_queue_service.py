import asyncio
import discord

from typing import Dict

class MusicPlayer:
    def __init__(self, bot: discord.Client, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.queue = asyncio.Queue()
        self.voice_client: discord.VoiceClient = None
        self.next = asyncio.Event()
        self.current = None
    
    async def play_loop(self):
        while True:
            self.next.clear()
            self.current = await self.queue.get()
            self.voice_client.play(
                self.current["source"],
                after=lambda x: self.bot.loop.call_soon_threadsafe(self.next.set)
            )

            await self.next.wait()
    
    async def enqueue(self, source, metadata):
        await self.queue.put({"source": source, "metadata": metadata})


class MusicQueueService:
    def __init__(self, bot):
        self.bot = bot
        self.players: Dict[int, MusicPlayer]  = {}
    
    def get_player(self, guild: discord.Guild) -> MusicPlayer:
        if guild.id not in self.players:
            player = MusicPlayer(self.bot, guild)
            self.players[guild.id] = player
            self.bot.loop.create_task(player.play_loop())
        return self.players[guild.id]

    def remove_player(self, guild: discord.Guild):
        if guild.id in self.players:
            del self.players[guild.id]