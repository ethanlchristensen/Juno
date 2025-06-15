import os
import ollama
import logging
from typing import List, Optional, Any

from .base_service import BaseService
from .types import Message, AIChatResponse, AIServiceConfig

class OllamaService(BaseService):
    def __init__(self, config: Optional[AIServiceConfig] = None):
        self.logger = logging.getLogger(__name__)
        host = (config and config.host) or os.getenv(
            "OLLAMA_ENDPOINT", "localhost:11434"
        )
        self.client = ollama.Client(host=host)
        self.default_model = (config and config.model) or os.getenv(
            "PREFERRED_OLLAMA_MODEL", "llama3.1"
        )
        self.logger.info(f"Intializing OllamaService with host={host} and default_model={self.default_model}")

    async def chat(
        self, messages: List[Message], model: Optional[str] = None
    ) -> AIChatResponse:
        try:
            model_to_use = model or self.default_model

            ollama_messages = [
                self.map_message_to_provider(message, "ollama") for message in messages
            ]

            self.logger.info(f"Calling OllamaService.chat() with model={model_to_use}")

            raw_response = self.client.chat(
                model=model_to_use, messages=ollama_messages
            )

            response = AIChatResponse(
                model=model_to_use,
                content=raw_response.get("message", {}).get("content", ""),
                raw_response=raw_response,
                usage=raw_response.get("usage", None),
            )

            return response
        except Exception as e:
            self.logger.error(f"Error in OllamaService.chat(): {e}")
            return {}
