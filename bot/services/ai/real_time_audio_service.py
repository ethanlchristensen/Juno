import discord
from discord.ext import commands, voice_recv
import asyncio
import json
import base64
import numpy as np
import io
from websockets import ClientConnection
import websockets

websockets.co
from typing import Optional

import logging


from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from bot.juno import Juno


class RealTimeAudioService:
    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.model = self.bot.config.aiConfig.realTimeConfig.realTimeModel
        self.apiKey = self.bot.config.aiConfig.realTimeConfig.apiKey
        self.ws: websockets.ClientConnection | None = None
        self.is_running = False
        self.ws_url = f"wss://api.openai.com/v1/realtime?model={self.model}"
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized RealTimeAudioService with model {self.model}")

    async def connect(self):
        headers = {"Authorization": f"Bearer {self.apiKey}"}

        self.ws = await websockets.connect(self.ws_url, additional_headers=headers)

        response = await self.ws.recv()

        event = json.loads(response)
        if event["type"] == "session.created":
            self.logger.info("OpenAI WS session created")

    async def configure_session(
        self,
        instructions: str = "Speak clearly and briefly. Confirm understanding before taking actions.",
        voice: str = "alloy"
    ):
        event = {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": self.model,
                "output_modalities": ["audio"],
                "audio": {
                    "input": {
                        "format": {
                            "type": "audio/pcm",
                            "rate": 24000,
                        },
                        "turn_detection": {"type": "semantic_vad"},
                    },
                    'output': {
                        "format": {
                            "type": "audio/pcmu",
                        },
                        "voice": voice,
                    },
                },
                "instructions": instructions,
            },
        }
        self.ws.send(json.dumps(event))

        response = self.ws.recv()

        self.logger.info(f"Session configuration response: {response}")

    async def send_audio_chunk(self, audio_data: bytes):
        if not audio_data:
            return
        
        base64_audio = base64.b64encode(audio_data).decode("ascii")
        event = {
            "type": "input_audio_buffer.append",
            "audio": base64_audio
        }

        await self.ws.send(json.dumps(event))

    async def listen_for_response(self, audio_queue: asyncio.Queue):
        while self.is_running:
            try:
                response = await asyncio.wait_for(self.ws_recv(), timeout=0.1)
                event = json.loads(response)
                event_type = event.get("type")

                if event_type == "response.audio.delta":
                    audio_b64 = event.get("delta", "")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        await audio_queue.put(audio_bytes)
                
                elif event_type == "response.output_audio.delta":
                    audio_b64 = event.get("delta", "")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        await audio_queue.put(audio_bytes)
                
                elif event_type == "response.output_audio.done":
                    self.logger.info("Audio response complete")
                
                elif event_type == "response.output_audio_transcript.delta":
                    transcript = event.get("delta", "")
                    self.logger.info(f"{transcript}", end='', flush=True)
                
                elif event_type == "response.output_audio_transcript.done":
                    self.logger.info()
                
                elif event_type == "input_audio_buffer.speech_started":
                    self.logger.info("User started speaking")
                
                elif event_type == "input_audio_buffer.speech_stopped":
                    self.logger.info("User stopped speaking")
                
                elif event_type == "error":
                    self.logger.error(f"Error: {event.get('error', {})}")
                    

            except Exception as e:
                self.logger.error(f"Exception encountered while listening for websocket response: {e}")

    async def disconnect(self):
        self.is_running = False
        if self.ws:
            self.ws.close()

class AudioProcessor():
    @staticmethod
    def resample_audio(audio_data: bytes, from_rate: int, to_rate: int, from_channels: int = 2, to_channels: int = 1):
        if not audio_data:
            return b''
        
        audio_np = np.frombuffer(audio_data, dtype=np.int16)

        if from_channels == 2 and to_channels == 1 and len(audio_data) > 0:
            audio_np = audio_np.reshape(-1, 2).mean(axis=1).astype(np.int16)\
        
        if len(audio_np) > 0:
            ratio = to_rate / from_rate
            new_length = int(len(audio_np) * ratio)
            if new_length > 0:
                indicies = np.linspace(0, len(audio_np) - 1, new_length)
                resampled = np.interp(indicies, np.arange(len(audio_np)), audio_np)
                return resampled.astype(np.int16).tobytes()
        return b''
    
    @staticmethod
    def unsample_audio(audio_data: bytes, from_rate: int = 24000, to_rate: int = 48000) -> bytes:
        if not audio_data:
            return b''
        
        audio_np = np.frombuffer(audio_data, dtype=np.int16)

        if len(audio_np) == 0:
            return b''
        
        ratio = int(to_rate / from_rate)
        unsampled = np.repeat(audio_np, ratio)

        stereo = np.column_stack((unsampled, unsampled)).flatten()

        return stereo.astype(np.int16).tobytes()

class VoiceRecieveSink(voice_recv.AudioSink):
    def __init__(self, real_time_audio_service: RealTimeAudioService, target_user_id: Optional[int] = None):
        super().__init__()
        self.real_time_audio_service = real_time_audio_service
        self.target_user_id = target_user_id
        self.audio_processor = AudioProcessor()
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"VoiceRecieveSink initialized. Target user ID: {target_user_id}.")

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_state(self, member: discord.Member, speaking: bool):
        if self.target_user_id and member.id != self.target_user_id:
            return
        
        if speaking:
            self.logger.info(f"{member.display_name} started speaking")
        else:
            print(f"{member.display_name} stopped speaking")
    
    def write(self, user: discord.Member, data: voice_recv.VoiceData):
        if self.target_user_id and user.id != self.target_user_id:
            return
        
        pcm_data = data.pcm

        if pcm_data:
            converted = self.audio_processor.resample_audio(
                pcm_data,
                from_rate=48000,
                to_rate=24000
            )

            if converted:
                asyncio.create_task(self.real_time_audio_service.send_audio_chunk(converted))
        
