import os
import ollama
import logging
from typing import List, Optional, Any, TypeVar, Type, Optional
from pydantic import BaseModel

from .base_service import BaseService
from .types import Message, AIChatResponse, AIServiceConfig
from ..config_service import Config

T = TypeVar("T", bound=BaseModel)


class OllamaService(BaseService):
    def __init__(self, config: Config):
        self.logger = logging.getLogger(__name__)
        self.client = ollama.Client(host=config.aiConfig.ollama.endpoint)
        self.default_model = config.aiConfig.ollama.preferredModel
        self.logger.info(
            f"Intializing OllamaService with host={config.aiConfig.ollama.endpoint} and default_model={self.default_model}"
        )

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

    async def chat_with_schema(
        self, messages: List[Message], schema: Type[T], model: Optional[str] = None
    ) -> T:
        try:
            model_to_use = model or self.default_model

            ollama_messages = [
                self.map_message_to_provider(message, "ollama") for message in messages
            ]

            self.logger.info(
                f"Calling OllamaService.chat_with_schema() with model={model_to_use} and schema={schema.__name__}"
            )

            raw_response = self.client.chat(
                model=model_to_use,
                messages=ollama_messages,
                format=schema.model_json_schema(),
            )

            return schema.model_validate_json(raw_response.message.content)
        except Exception as e:
            self.logger.error(f"Error in OllamaService.chat_with_schema(): {e}")
            raise
