import time
import asyncio
import discord
import logging

from typing import Dict, TYPE_CHECKING, Optional

from .types import FilterPreset

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
        self.play_start_time = None
        self.paused_at = None
        self.is_playing = False
        # Flag to distinguish between normal song end and manual operations
        self.manual_stop = False
        self.logger = logging.getLogger(__name__)

    async def play_loop(self):
        while True:
            self.next.clear()
            
            # If we've manually stopped for filter/pause but not advancing queue
            if self.manual_stop:
                # Wait for the next action but don't get a new song
                self.manual_stop = False
                await self.next.wait()
                continue
                
            # If nothing is playing or we need the next song
            if not self.is_playing:
                # Get the next song if queue isn't empty
                if not self.queue.empty():
                    self.current = await self.queue.get()
                else:
                    # Wait for something to be added to the queue
                    try:
                        self.current = await asyncio.wait_for(self.queue.get(), timeout=300)
                    except asyncio.TimeoutError:
                        await asyncio.sleep(1)
                        continue

            # Check if voice client is valid
            if not self.voice_client or not self.voice_client.is_connected():
                self.logger.error(f"Voice client not connected for guild {self.guild.id}")
                await asyncio.sleep(1)
                continue

            try:
                url = self.current["url"]
                filter_preset = self.current.get("filter_preset")
                
                # Start playback
                audio_service = self.bot.audio_service
                source = audio_service.get_audio_source(url, filter_preset)
                
                # Stop any existing playback
                if self.voice_client.is_playing():
                    self.voice_client.stop()
                
                self.is_playing = True
                self.voice_client.play(
                    source,
                    after=lambda x: self.bot.loop.call_soon_threadsafe(
                        self._song_finished
                    ),
                )
                self.play_start_time = time.time()
                self.paused_at = None
                
                # Send now playing message
                if self.text_channel:
                    embed = self.bot.embed_service.create_now_playing_embed(
                        self.current["metadata"]
                    )
                    await self.text_channel.send(embed=embed)
                    
                # Wait for the song to finish or be interrupted
                await self.next.wait()
                
            except Exception as e:
                self.logger.error(f"Error in play_loop for guild {self.guild.id}: {e}")
                import traceback
                traceback.print_exc()
                self.is_playing = False
                await asyncio.sleep(1)

    def _song_finished(self):
        """Called when a song finishes playing naturally"""
        if not self.manual_stop:
            # Only mark as not playing if we didn't manually stop
            self.is_playing = False
        self.next.set()

    async def enqueue(self, url, metadata, filter_preset=None, text_channel=None):
        if text_channel:
            self.text_channel = text_channel

        await self.queue.put(
            {"url": url, "metadata": metadata, "filter_preset": filter_preset}
        )

    async def skip(self):
        """Skip the current song and move to the next in queue"""
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            # Don't set manual_stop because we want to advance the queue
            self.is_playing = False
            self.voice_client.stop()
            self.next.set()
            return True
        return False

    async def pause(self):
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            if self.play_start_time:
                self.paused_at = time.time() - self.play_start_time
            else:
                self.paused_at = 0
            return True
        return False

    async def resume(self):
        if not self.current:
            return False

        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            if self.paused_at is not None:
                self.play_start_time = time.time() - self.paused_at
                self.paused_at = None
            return True
        elif self.paused_at is not None:
            # Need to restart from a specific position
            # Set manual_stop flag to prevent queue advancing
            self.manual_stop = True
            
            # Create new source at the paused position
            audio_service = self.bot.audio_service
            url = self.current["url"]
            filter_preset = self.current.get("filter_preset")
            
            source = audio_service.get_audio_source(
                url, filter_preset, position=self.paused_at
            )
            
            # Stop and restart
            if self.voice_client.is_playing():
                self.voice_client.stop()
                
            self.voice_client.play(
                source, 
                after=lambda e: self.bot.loop.call_soon_threadsafe(self._song_finished)
            )
            
            self.play_start_time = time.time() - self.paused_at
            self.paused_at = None
            self.is_playing = True
            return True
        return False
    
    async def set_filter(self, new_filter: FilterPreset):
        """Apply a filter to the current song without advancing the queue"""
        if not self.current:
            return False

        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            # Set the manual_stop flag to prevent queue advancement
            self.manual_stop = True
            
            # Calculate current position
            if self.voice_client.is_paused() and self.paused_at is not None:
                elapsed = self.paused_at
            else:
                elapsed = time.time() - self.play_start_time if self.play_start_time else 0
            
            # Remember if it was paused
            was_paused = self.voice_client.is_paused()
            
            # Stop current playback but don't advance queue
            self.voice_client.stop()
            
            # Update filter in current track
            self.current["filter_preset"] = new_filter
            
            # Create new source with updated filter and position
            url = self.current["url"]
            audio_service = self.bot.audio_service
            source = audio_service.get_audio_source(url, new_filter, position=elapsed)
            
            # Play with the new filter
            self.voice_client.play(
                source, 
                after=lambda e: self.bot.loop.call_soon_threadsafe(self._song_finished)
            )
            
            # Update timing info
            self.play_start_time = time.time() - elapsed
            
            # If it was paused before, pause it again (i.e. can change the filter when the audio is paused)
            if was_paused:
                self.voice_client.pause()
                self.paused_at = elapsed
            else:
                self.paused_at = None
            
            return True
        return False


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