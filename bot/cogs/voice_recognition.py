import discord
from discord.ext import commands, voice_recv
from discord import app_commands
import asyncio
import io
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import audioop
import wave
import os
import time
from typing import Optional
from openai import OpenAI
import whisper
import torch
from elevenlabs.client import ElevenLabs, AsyncElevenLabs

from bot.utils.decarators.voice_check import require_voice_channel
from bot.utils.decarators.admin_check import is_admin


class SpeechRecognitionSink(voice_recv.AudioSink):
    """Custom AudioSink for speech recognition"""

    def __init__(self, bot_instance, guild_id, max_duration=10, max_concurrent_users=5):
        super().__init__()
        self.bot = bot_instance
        self.guild_id = guild_id
        self.audio_buffers = {}  # Store audio per user

        # Configurable settings
        self.max_duration = max_duration  # Maximum seconds to record
        self.max_buffer_size = 48000 * 2 * self.max_duration  # Maximum buffer size
        self.voice_threshold = 500  # Voice detection threshold
        self.silence_threshold = 100  # Silence detection threshold (lower than voice)
        self.silence_duration = 0.5  # Seconds of silence before processing

        # Timing tracking for silence detection
        self.user_last_speech = {}  # Track last time user had speech
        self.user_silence_start = {}  # Track when silence started

        self.loop = None
        # Separate executors for different tasks
        self.transcription_executor = ThreadPoolExecutor(
            max_workers=6, thread_name_prefix="whisper"
        )
        self.audio_executor = ThreadPoolExecutor(
            max_workers=max_concurrent_users, thread_name_prefix="audio"
        )

        # Initialize Whisper model and OpenAI TTS client
        self.whisper_model = None
        self.whisper_model_name = "tiny"  # Options: tiny, base, small, medium, large
        self.tts_client = OpenAI()
        self.model_loading = False

        # Load Whisper model in background
        self._load_whisper_model()

        # Track active processing to avoid spam
        self.processing_users = set()

        if elk := os.getenv("ELEVENLABS_API_KEY"):
            self.elevenlabs_client = ElevenLabs(api_key=elk)

    def _load_whisper_model(self):
        """Load Whisper model in a separate thread"""
        if self.model_loading:
            return

        self.model_loading = True

        def load_model():
            try:
                self.bot.logger.info(
                    f"Loading Whisper model '{self.whisper_model_name}'..."
                )
                # Check if CUDA is available
                device = "cuda" if torch.cuda.is_available() else "cpu"
                self.bot.logger.info(f"Using device: {device}")

                self.whisper_model = whisper.load_model(
                    self.whisper_model_name, device=device
                )
                self.bot.logger.info(
                    f"Whisper model '{self.whisper_model_name}' loaded successfully on {device}"
                )
            except Exception as e:
                self.bot.logger.error(f"Failed to load Whisper model: {e}")
                self.whisper_model = None
            finally:
                self.model_loading = False

        # Load model in background thread
        threading.Thread(target=load_model, daemon=True).start()

    def wants_opus(self) -> bool:
        return False  # We want PCM data for speech recognition

    def write(self, user, data: voice_recv.VoiceData):
        """Called when audio data is received - keep this fast and non-blocking"""
        if not user or user.bot:  # Ignore bot audio or unknown users
            return

        user_id = user.id
        current_time = time.time()

        # Skip if already processing this user's audio
        if user_id in self.processing_users:
            return

        # Initialize buffer and timing for new users
        if user_id not in self.audio_buffers:
            self.audio_buffers[user_id] = []
            self.user_last_speech[user_id] = current_time
            self.user_silence_start[user_id] = None

        # Add PCM data to user's buffer
        if data.pcm:
            self.audio_buffers[user_id].extend(data.pcm)

            # Quick speech detection (keep this fast)
            try:
                chunk_bytes = bytes(data.pcm)
                if len(chunk_bytes) >= 2:
                    rms = audioop.rms(chunk_bytes, 2)
                    has_speech = rms > self.voice_threshold
                    is_silent = rms <= self.silence_threshold

                    if has_speech:
                        # Reset silence tracking - user is speaking
                        self.user_last_speech[user_id] = current_time
                        self.user_silence_start[user_id] = None
                    elif is_silent:
                        # Start tracking silence if not already
                        if self.user_silence_start[user_id] is None:
                            self.user_silence_start[user_id] = current_time

                        # Check if we've had enough silence to process
                        silence_duration = (
                            current_time - self.user_silence_start[user_id]
                        )
                        if (
                            silence_duration >= self.silence_duration
                            and len(self.audio_buffers[user_id]) > 0
                        ):
                            self.schedule_buffer_processing(user, user_id)
                    else:
                        # Not quite silent enough, reset silence tracking
                        self.user_silence_start[user_id] = None
            except Exception as e:
                # Don't let audio processing errors break the write loop
                pass

        # Also process if buffer gets too large (failsafe)
        if len(self.audio_buffers[user_id]) >= self.max_buffer_size:
            self.schedule_buffer_processing(user, user_id)

    def schedule_buffer_processing(self, user, user_id):
        """Schedule buffer processing without blocking"""
        if not self.audio_buffers[user_id] or user_id in self.processing_users:
            return

        # Mark user as being processed
        self.processing_users.add(user_id)

        # Copy buffer data
        audio_data = self.audio_buffers[user_id].copy()

        # Clear the buffer and reset timing immediately
        self.audio_buffers[user_id] = []
        self.user_silence_start[user_id] = None

        # Get the event loop from the bot
        if self.loop is None:
            self.loop = self.bot.loop

        # Schedule the coroutine to run in the event loop (non-blocking)
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self.process_user_audio_async(user, audio_data), self.loop
            )

    async def process_user_audio_async(self, user, audio_data):
        """Process audio data for speech recognition - fully async"""
        try:
            # Convert list of bytes to bytes object in executor
            audio_bytes = await asyncio.get_event_loop().run_in_executor(
                self.audio_executor, lambda: bytes(audio_data)
            )

            # Check if there's actual speech in the entire buffer (in executor)
            has_speech = await asyncio.get_event_loop().run_in_executor(
                self.audio_executor, self._check_speech_in_buffer, audio_bytes
            )

            if not has_speech:
                self.bot.logger.debug(
                    f"No speech detected in {user.display_name}'s audio buffer"
                )
                return

            # Run speech recognition (in separate executor)
            text = await self.recognize_speech_async(audio_bytes)
            if text:
                self.bot.logger.info(f"Recognized from {user.display_name}: {text}")

                # Check for wake word
                if self.contains_wake_word(text):
                    # Remove wake word from text
                    clean_text = (
                        text.lower()
                        .replace("jade", "")
                        .replace("hey", "")
                        .replace("ok", "")
                        .replace("clem", "klim")
                        .strip()
                    )
                    if clean_text:
                        # Process the request asynchronously
                        await self._handle_voice_request(user, clean_text)
                    else:
                        self.bot.logger.debug(
                            f"No content after wake word removal: '{text}'"
                        )
                else:
                    self.bot.logger.debug(f"No wake word detected in: '{text}'")

        except Exception as e:
            self.bot.logger.error(
                f"Error processing audio from {user.display_name}: {e}"
            )
        finally:
            # Remove user from processing set when done
            self.processing_users.discard(user.id)

    def _check_speech_in_buffer(self, audio_bytes):
        """Check if there's speech in the buffer (runs in executor)"""
        try:
            if len(audio_bytes) < 2:
                return False
            rms = audioop.rms(audio_bytes, 2)
            return rms > self.voice_threshold
        except:
            return False

    async def _handle_voice_request(self, user, clean_text):
        """Handle the voice request asynchronously"""
        try:
            # Get AI response
            response = await self.get_ai_response(clean_text, user.display_name)

            # Generate speech and play audio concurrently with sending text
            audio_task = asyncio.create_task(self._generate_and_play_speech(response))
            text_task = asyncio.create_task(self._send_text_response(user, response))

            # Wait for both to complete
            await asyncio.gather(audio_task, text_task, return_exceptions=True)
            # await asyncio.gather(audio_task, return_exceptions=True)

        except Exception as e:
            self.bot.logger.error(f"Error handling voice request: {e}")

    async def _generate_and_play_speech(self, text):
        """Generate and play speech audio"""
        try:
            audio_bytes = await self.generate_speech(text)
            if audio_bytes:
                voice_client = self.bot.voice_connections.get(self.guild_id)
                if voice_client:
                    await self.play_audio_in_voice(voice_client, audio_bytes)
        except Exception as e:
            self.bot.logger.error(f"Error generating/playing speech: {e}")

    async def _send_text_response(self, user, response):
        """Send text response to channel"""
        try:
            text_channel = self.bot.current_channels.get(self.guild_id)
            if text_channel:
                chunks = None
                if len(response) <= 2000:
                    await text_channel.send(
                        f"🎤 **Jade** responding to **{user.display_name}**: {response}"
                    )
                    return
                
                chunks = []
                while len(response) > 2000:
                    chunk = response[:2000]
                    last_space = chunk.rfind(' ')
                    
                    if last_space != -1:
                        chunks.append(response[:last_space])
                        response = response[last_space + 1:]
                    else:
                        chunks.append(response[:2000])
                        response = response[2000:]
                
                if response:
                    chunks.append(response)
                
                for idx, chunk in enumerate(chunks):
                    await text_channel.send(chunk)
        except Exception as e:
            self.bot.logger.error(f"Error sending text response: {e}")

    async def recognize_speech_async(self, audio_bytes):
        """Run speech recognition using local Whisper model - fully async"""
        try:
            # Check if Whisper model is loaded
            if self.whisper_model is None:
                self.bot.logger.warning(
                    "Whisper model not loaded yet, skipping transcription"
                )
                return None

            # Minimum audio length check (at least 0.5 seconds)
            min_audio_length = 48000 * 2 * 0.5  # 0.5 seconds
            if len(audio_bytes) < min_audio_length:
                self.bot.logger.debug("Audio too short for transcription")
                return None

            # Create temporary file in executor
            temp_path = await asyncio.get_event_loop().run_in_executor(
                self.audio_executor, self._create_temp_audio_file, audio_bytes
            )

            if not temp_path:
                return None

            try:
                # Run Whisper transcription in dedicated executor
                result = await asyncio.get_event_loop().run_in_executor(
                    self.transcription_executor, self._transcribe_audio, temp_path
                )

                return result

            finally:
                # Clean up temp file in executor
                asyncio.get_event_loop().run_in_executor(
                    self.audio_executor, self._cleanup_temp_file, temp_path
                )

        except Exception as e:
            self.bot.logger.error(f"Local Whisper transcription error: {e}")
            return None

    def _create_temp_audio_file(self, audio_bytes):
        """Create temporary audio file (runs in executor)"""
        try:
            temp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            # Convert raw PCM to WAV format
            with wave.open(temp_audio.name, "wb") as wav_file:
                wav_file.setnchannels(2)  # Stereo
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(48000)  # 48kHz
                wav_file.writeframes(audio_bytes)

            temp_audio.close()
            return temp_audio.name
        except Exception as e:
            self.bot.logger.error(f"Error creating temp audio file: {e}")
            return None

    def _cleanup_temp_file(self, temp_path):
        """Clean up temporary file (runs in executor)"""
        try:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
        except Exception as e:
            self.bot.logger.debug(f"Error cleaning up temp file: {e}")

    def _transcribe_audio(self, audio_path):
        """Transcribe audio using Whisper (runs in dedicated transcription executor)"""
        try:
            # Transcribe using local Whisper model
            result = self.whisper_model.transcribe(
                audio_path,
                language="en",
                fp16=torch.cuda.is_available(),  # Use fp16 if CUDA available
                task="transcribe",
            )

            text = result["text"].strip()
            self.bot.logger.debug(f"Whisper transcription: '{text}'")
            return text

        except Exception as e:
            self.bot.logger.error(f"Error in Whisper transcription: {e}")
            return None

    def has_speech(self, audio_bytes, threshold=None):
        """Simple voice activity detection - keep this fast"""
        try:
            if len(audio_bytes) < 2:
                return False

            # Use instance threshold if not provided
            if threshold is None:
                threshold = self.voice_threshold

            rms = audioop.rms(audio_bytes, 2)
            return rms > threshold
        except:
            return False

    def contains_wake_word(self, text):
        """Check if text contains the bot's name"""
        if not text:
            return False
        wake_words = ["jade", "hey jade", "ok jade"]
        text_lower = text.lower()
        return any(wake_word in text_lower for wake_word in wake_words)

    async def get_ai_response(self, user_input, user_name):
        """Get response from AI service"""
        try:
            # Use the existing AI service with a simple prompt
            from bot.services.ai.types import Message

            messages = [
                Message(role="system", content="You are a helpful assistant named Jade. Follow the instructions carefully. Be as detailed as possible."),
                Message(role="user", content=f"{user_name}: {user_input}"),
            ]

            if main_prompt := self.bot.prompts.get("main"):
                messages.insert(0, Message(role="system", content=main_prompt))

            response = await self.bot.ai_service.chat(messages=messages)
            return response.content

        except Exception as e:
            self.bot.logger.error(f"Error getting AI response: {e}")
            return "Sorry, I encountered an error processing your request."

    async def generate_speech(self, text):
        """Generate speech using OpenAI TTS - async"""
        try:
            self.bot.logger.info(f"Generating speech for: {text[:50]}...")

            # Run TTS in executor to avoid blocking
            audio_content = await asyncio.get_event_loop().run_in_executor(
                self.audio_executor, self._generate_tts, text
            )

            return audio_content

        except Exception as e:
            self.bot.logger.error(f"Error generating speech: {e}")
            return None

    def _generate_tts(self, text: str):
        """Generate TTS (runs in executor)"""
        try:
#             response = self.tts_client.audio.speech.create(
#                 model="gpt-4o-mini-tts",
#                 voice="coral",
#                 input=text.lower()
#                 .replace("etchris", "e-t-chris")
#                 .replace("Etchris", "e-t-chris"),
#                 response_format="mp3",
#             )
#             return response.content

            response = self.elevenlabs_client.text_to_speech.convert(
                voice_id="cgSgspJ2msm6clMCkdW9",
                output_format="mp3_44100_128",
                text=text.lower().replace("etchris", "e-t-chris").replace("Etchris", "e-t-chris"),
                model_id="eleven_flash_v2_5",
            )
            return b"".join(response)
        except Exception as e:
            self.bot.logger.error(f"TTS generation error: {e}")
            return None

    async def play_audio_in_voice(self, voice_client, audio_bytes):
        """Play audio in Discord voice channel - async"""
        try:
            # Create temporary file in executor
            temp_path = await asyncio.get_event_loop().run_in_executor(
                self.audio_executor, self._create_temp_mp3_file, audio_bytes
            )

            if not temp_path:
                return

            try:
                # Create audio source and play
                audio_source = discord.FFmpegPCMAudio(temp_path)
                if not voice_client.is_playing():
                    voice_client.play(audio_source)

                # Wait for playback to complete (with timeout)
                timeout = 60  # Max 60 seconds
                elapsed = 0
                while voice_client.is_playing() and elapsed < timeout:
                    await asyncio.sleep(0.1)
                    elapsed += 0.1

            finally:
                # Clean up temp file
                asyncio.get_event_loop().run_in_executor(
                    self.audio_executor, self._cleanup_temp_file, temp_path
                )

        except Exception as e:
            self.bot.logger.error(f"Error playing audio: {e}")

    def _create_temp_mp3_file(self, audio_bytes):
        """Create temporary MP3 file (runs in executor)"""
        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            temp_file.write(audio_bytes)
            temp_file.close()
            return temp_file.name
        except Exception as e:
            self.bot.logger.error(f"Error creating temp MP3 file: {e}")
            return None

    def cleanup(self):
        """Clean up when sink is done"""
        self.bot.logger.info("Speech recognition sink cleaned up")
        if self.transcription_executor:
            self.transcription_executor.shutdown(wait=False)
        if self.audio_executor:
            self.audio_executor.shutdown(wait=False)

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_start(self, member):
        """Called when a member starts speaking"""
        self.bot.logger.debug(f"{member.display_name} started speaking")

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_stop(self, member):
        """Called when a member stops speaking"""
        self.bot.logger.debug(f"{member.display_name} stopped speaking")

    @voice_recv.AudioSink.listener()
    def on_voice_member_disconnect(self, member, ssrc):
        """Called when a member disconnects"""
        self.bot.logger.info(f"{member.display_name} disconnected from voice")
        # Clean up their audio buffer and timing
        if hasattr(member, "id") and member.id in self.audio_buffers:
            del self.audio_buffers[member.id]
            if member.id in self.user_last_speech:
                del self.user_last_speech[member.id]
            if member.id in self.user_silence_start:
                del self.user_silence_start[member.id]
        # Remove from processing set
        if hasattr(member, "id"):
            self.processing_users.discard(member.id)


class VoiceRecognition(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Voice connection management
        self.bot.voice_connections = getattr(bot, "voice_connections", {})
        self.bot.audio_sinks = getattr(bot, "audio_sinks", {})
        self.bot.current_channels = getattr(bot, "current_channels", {})

    @app_commands.command(
        name="voice_join",
        description="Join your voice channel and start voice recognition",
    )
    @require_voice_channel()
    async def voice_join(self, interaction: discord.Interaction):
        """Join the user's voice channel and start voice recording"""
        channel = interaction.user.voice.channel

        if interaction.guild.id in self.bot.voice_connections:
            await interaction.response.send_message(
                "❌ I'm already connected to a voice channel!", ephemeral=True
            )
            return

        try:
            await interaction.response.defer()

            # Connect with VoiceRecvClient for voice receiving capabilities
            voice_client = await channel.connect(cls=voice_recv.VoiceRecvClient)
            self.bot.voice_connections[interaction.guild.id] = voice_client
            self.bot.current_channels[interaction.guild.id] = interaction.channel

            # Create and start audio sink for speech recognition
            audio_sink = SpeechRecognitionSink(self.bot, interaction.guild.id)
            self.bot.audio_sinks[interaction.guild.id] = audio_sink

            # Start listening with the sink
            voice_client.listen(audio_sink)

            embed = discord.Embed(
                title="🎤 Voice Recognition Active",
                description=f"I've joined **{channel.name}** and I'm now listening for voice commands!",
                color=0x00FF00,
            )
            embed.add_field(
                name="🎤 How to use",
                value="Simply say: **'Jade, what's the weather?'**\nI'll listen, process your speech, and respond with voice!",
                inline=False,
            )

            # Check Whisper model status
            sink = audio_sink
            whisper_status = "✅ Loaded" if sink.whisper_model else "⏳ Loading..."
            device = "🚀 CUDA" if torch.cuda.is_available() else "💻 CPU"

            embed.add_field(
                name="⚙️ Settings",
                value=f"• Max Duration: **10 seconds**\n• Silence Detection: **0.5 seconds**\n• Voice Threshold: **500**\n• Whisper Model: **{sink.whisper_model_name}** ({whisper_status})\n• Device: **{device}**",
                inline=False,
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Error joining voice channel: {e}")

    @app_commands.command(
        name="voice_leave",
        description="Leave the voice channel and stop voice recognition",
    )
    async def voice_leave(self, interaction: discord.Interaction):
        """Leave the voice channel and stop recording"""
        if interaction.guild.id not in self.bot.voice_connections:
            await interaction.response.send_message(
                "❌ I'm not connected to a voice channel!", ephemeral=True
            )
            return

        try:
            await interaction.response.defer()

            voice_client = self.bot.voice_connections[interaction.guild.id]

            # Stop listening
            if voice_client.is_listening():
                voice_client.stop_listening()

            # Clean up sink
            if interaction.guild.id in self.bot.audio_sinks:
                self.bot.audio_sinks[interaction.guild.id].cleanup()
                del self.bot.audio_sinks[interaction.guild.id]

            # Clean up channels
            if interaction.guild.id in self.bot.current_channels:
                del self.bot.current_channels[interaction.guild.id]

            # Disconnect
            await voice_client.disconnect()
            del self.bot.voice_connections[interaction.guild.id]

            embed = discord.Embed(
                title="👋 Voice Recognition Stopped",
                description="I've left the voice channel and stopped listening. Use `/voice_join` to invite me back!",
                color=0xFF6B6B,
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Error leaving voice channel: {e}")

    @app_commands.command(
        name="voice_status", description="Check voice recognition status"
    )
    async def voice_status(self, interaction: discord.Interaction):
        """Show voice recognition status"""
        guild_id = interaction.guild.id
        is_connected = guild_id in self.bot.voice_connections
        is_listening = False

        if is_connected:
            voice_client = self.bot.voice_connections[guild_id]
            is_listening = voice_client.is_listening()

        embed = discord.Embed(
            title="🎤 Voice Recognition Status",
            color=0x00FF00 if is_connected and is_listening else 0x95A5A6,
        )

        embed.add_field(
            name="Voice Connection",
            value="🟢 Connected" if is_connected else "🔴 Not Connected",
            inline=True,
        )

        embed.add_field(
            name="Voice Recognition",
            value="🎤 Listening" if is_listening else "🔇 Not Listening",
            inline=True,
        )

        if is_connected:
            voice_client = self.bot.voice_connections[guild_id]
            channel_name = (
                voice_client.channel.name if voice_client.channel else "Unknown"
            )
            embed.add_field(
                name="Voice Channel", value=f"📻 {channel_name}", inline=False
            )

            # Show current settings
            if guild_id in self.bot.audio_sinks:
                sink = self.bot.audio_sinks[guild_id]
                whisper_status = "✅ Ready" if sink.whisper_model else "⏳ Loading..."
                device = "🚀 CUDA" if torch.cuda.is_available() else "💻 CPU"

                embed.add_field(
                    name="Current Settings",
                    value=f"• Max Duration: **{sink.max_duration}s**\n• Voice Threshold: **{sink.voice_threshold}**\n• Silence Duration: **{sink.silence_duration}s**\n• Active Users: **{len(sink.processing_users)}**\n• Whisper: **{sink.whisper_model_name}** ({whisper_status})\n• Device: **{device}**",
                    inline=False,
                )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="voice_config", description="Configure voice recognition settings"
    )
    @app_commands.describe(
        max_duration="Maximum recording duration (3-10 seconds)",
        silence_duration="Silence duration before processing (0.5-5 seconds)",
        threshold="Voice detection sensitivity (100-2000, higher = less sensitive)",
        whisper_model="Whisper model size (tiny/base/small/medium/large)",
    )
    @app_commands.choices(
        whisper_model=[
            app_commands.Choice(name="Tiny (fastest)", value="tiny"),
            app_commands.Choice(name="Base (recommended)", value="base"),
            app_commands.Choice(name="Small (better accuracy)", value="small"),
            app_commands.Choice(name="Medium (high accuracy)", value="medium"),
            app_commands.Choice(name="Large (best accuracy)", value="large"),
        ]
    )
    async def voice_config(
        self,
        interaction: discord.Interaction,
        max_duration: Optional[int] = None,
        silence_duration: Optional[float] = None,
        threshold: Optional[int] = None,
        whisper_model: Optional[app_commands.Choice[str]] = None,
    ):
        """Configure voice recognition settings"""
        if interaction.guild.id not in self.bot.audio_sinks:
            await interaction.response.send_message(
                "❌ Voice recognition is not active! Use `/voice_join` first.",
                ephemeral=True,
            )
            return

        sink = self.bot.audio_sinks[interaction.guild.id]
        changes_made = []

        if max_duration is not None:
            if 3 <= max_duration <= 10:
                sink.max_duration = max_duration
                sink.max_buffer_size = 48000 * 2 * max_duration
                changes_made.append(f"Max Duration: **{max_duration} seconds**")
            else:
                await interaction.response.send_message(
                    "❌ Max duration must be between 3-10 seconds!", ephemeral=True
                )
                return

        if silence_duration is not None:
            if 0.5 <= silence_duration <= 5.0:
                sink.silence_duration = silence_duration
                changes_made.append(f"Silence Duration: **{silence_duration} seconds**")
            else:
                await interaction.response.send_message(
                    "❌ Silence duration must be between 0.5-5 seconds!", ephemeral=True
                )
                return

        if threshold is not None:
            if 100 <= threshold <= 2000:
                sink.voice_threshold = threshold
                changes_made.append(f"Voice Threshold: **{threshold}**")
            else:
                await interaction.response.send_message(
                    "❌ Threshold must be between 100-2000!", ephemeral=True
                )
                return

        if whisper_model is not None:
            if sink.whisper_model_name != whisper_model.value:
                sink.whisper_model_name = whisper_model.value
                sink.whisper_model = None  # Reset model to trigger reload
                sink._load_whisper_model()  # Load new model
                changes_made.append(
                    f"Whisper Model: **{whisper_model.value}** (loading...)"
                )

        if not changes_made:
            await interaction.response.send_message(
                "❌ Please specify at least one setting to change!", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🔧 Voice Configuration Updated",
            description="Settings have been updated successfully!",
            color=0x00FF00,
        )

        embed.add_field(
            name="Changes Made", value="\n".join(changes_made), inline=False
        )

        whisper_status = "✅ Ready" if sink.whisper_model else "⏳ Loading..."
        device = "🚀 CUDA" if torch.cuda.is_available() else "💻 CPU"

        embed.add_field(
            name="Current Settings",
            value=f"• Max Duration: **{sink.max_duration} seconds**\n• Silence Duration: **{sink.silence_duration} seconds**\n• Voice Threshold: **{sink.voice_threshold}**\n• Whisper Model: **{sink.whisper_model_name}** ({whisper_status})\n• Device: **{device}**",
            inline=False,
        )

        embed.add_field(
            name="💡 Tips",
            value="• **Tiny/Base**: Fast, good for simple speech\n• **Small/Medium**: Better accuracy, slower\n• **Large**: Best accuracy, requires more resources\n• **CUDA**: Much faster if available",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(VoiceRecognition(bot))
