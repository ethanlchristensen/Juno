from typing import TYPE_CHECKING

import discord

from .music_player import MusicPlayer

if TYPE_CHECKING:
    from bot.juno import Juno


class MusicQueueService:
    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.players: dict[int, MusicPlayer] = {}

    def get_player(self, guild: discord.Guild) -> MusicPlayer:
        if guild.id not in self.players:
            player = MusicPlayer(self.bot, guild)
            self.players[guild.id] = player
            self.bot.loop.create_task(player.play_loop())
        return self.players[guild.id]

    def remove_player(self, guild: discord.Guild):
        if guild.id in self.players:
            del self.players[guild.id]
