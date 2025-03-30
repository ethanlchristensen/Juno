import os
import openai
import logging
from typing import List, Optional, Any

from .base_service import BaseService
from .types import Message, AIChatResponse, AIServiceConfig


class OpenAIService(BaseService):
    def __init__(self, config: Optional[AIServiceConfig] = None):
        self.logger = logging.getLogger(__name__)

        api_key = (config and config.api_key) or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is not set")

        self.client = openai.Client(api_key=api_key)
        self.default_model = (config and config.model) or os.getenv(
            "PREFERRED_OPENAI_MODEL", "gpt-4o-mini"
        )

    def chat(
        self, messages: List[Message], model: Optional[str] = None
    ) -> AIChatResponse:
        try:
            model_to_use = model or self.default_model

            openai_messages = [
                self.map_message_to_provider(message, "openai") for message in messages
            ]

            raw_response = self.client.chat.completions.create(
                model=model_to_use, messages=messages
            )

            return AIChatResponse(
                model=model_to_use,
                content=raw_response.choices[0].message.content,
                raw_response=raw_response,
                usage={
                    "prompt_tokens": raw_response.usage.prompt_tokens,
                    "completion_tokens": raw_response.usage.completion_tokens,
                    "total_tokens": raw_response.usage.total_tokens,
                },
            )
        except Exception as e:
            self.logger.error(f"Error in OpenAIService.chat(): {e}")
            return {}
