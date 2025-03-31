import time
import discord
import logging
import asyncio

from typing import Optional, TYPE_CHECKING

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
        # i.e. did the song end on its own, or did we end it to start it up again with /pause+resume or /filter
        self.manual_stop = False
        self.logger = logging.getLogger(__name__)

    async def play_loop(self) -> None:
        """Keep playing while items are in the queue"""
        while True:
            self.next.clear()

            if self.manual_stop:
                self.logger.info("[PLAY_LOOP] Manual stop set — waiting for resume/filter change.")
                self.manual_stop = False
                await self.next.wait()
                continue

            if not self.is_playing:
                if not self.queue.empty():
                    self.current = await self.queue.get()
                    self.logger.info(f"[PLAY_LOOP] Got next song from queue: {self.current['metadata'].title}")
                else:
                    try:
                        self.logger.info("[PLAY_LOOP] Queue is empty — waiting up to 300s for new song.")
                        self.current = await asyncio.wait_for(self.queue.get(), timeout=300)
                        self.logger.info(f"[PLAY_LOOP] Got song after waiting: {self.current['metadata'].title}")
                    except asyncio.TimeoutError:
                        self.logger.info("[PLAY_LOOP] Timed out waiting for song. Retrying...")
                        await asyncio.sleep(1)
                        continue

            if not self.voice_client or not self.voice_client.is_connected():
                self.logger.error(f"[PLAY_LOOP] Voice client not connected for guild {self.guild.id}")
                await asyncio.sleep(1)
                continue

            try:
                url = self.current["url"]
                filter_preset = self.current.get("filter_preset")

                if self.voice_client.is_playing():
                    self.voice_client.stop()

                self.logger.info(f"[PLAY_LOOP] Starting playback for: {self.current['metadata'].title}")
                self.is_playing = True

                audio_service = self.bot.audio_service
                source = audio_service.get_audio_source(url, filter_preset)

                current_track = self.current

                def _after_play(err):
                    if self.current == current_track:
                        self.bot.loop.call_soon_threadsafe(self._song_finished)

                self.voice_client.play(source, after=_after_play)

                self.play_start_time = time.time()
                self.paused_at = None

                if self.text_channel:
                    embed = self.bot.embed_service.create_now_playing_embed(
                        self.current["metadata"]
                    )
                    await self.text_channel.send(embed=embed)

                await self.next.wait()

            except Exception as e:
                self.logger.error(f"[PLAY_LOOP] Exception during playback: {e}")
                import traceback
                traceback.print_exc()
                self.is_playing = False
                await asyncio.sleep(1)

    def _song_finished(self) -> None:
        """Callback for when a song is finished"""
        self.logger.info(f"[SONG_FINISHED] Finished: {self.current['metadata'].title if self.current else 'Unknown'}")

        if self.manual_stop:
            self.manual_stop = False
        else:
            self.is_playing = False
            self.current = None
            self.next.set()

    async def enqueue(self, url, metadata, filter_preset=None, text_channel=None) -> None:
        """Add a new song to the queue"""
        if text_channel:
            self.text_channel = text_channel

        self.logger.info(f"[ENQUEUE] Adding song to queue: {metadata.title}")
        await self.queue.put(
            {"url": url, "metadata": metadata, "filter_preset": filter_preset}
        )

    async def skip(self) -> bool:
        """Skip the currently playing song"""
        self.logger.info("[SKIP] Skip command received.")
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()
            return True
        return False

    async def pause(self) -> bool:
        """Pause the currently playing audio"""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            if self.play_start_time:
                self.paused_at = time.time() - self.play_start_time
            else:
                self.paused_at = 0
            return True
        return False

    async def resume(self) -> bool:
        """Resume a song that was paused"""
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
    
    async def set_filter(self, new_filter: FilterPreset) -> bool:
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