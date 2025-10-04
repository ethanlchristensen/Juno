import os
import logging
from typing import List, Dict, Optional, Type, TypeVar, Optional
from pydantic import BaseModel

from google import genai
from google.genai import types
from google.genai import Client

from .base_service import BaseService
from .types import Message, AIChatResponse, AIServiceConfig
from ..config_service import Config

T = TypeVar("T", bound=BaseModel)


class GoogleAIService(BaseService):
    """
    A service class for interacting with Google's AI API.
    """

    def __init__(self, config: Config):
        """
        Initializes the GoogleAIService with the necessary API key for authentication.

        Args:
            api_key (str): The Google AI API key.
        """

        self.logger = logging.getLogger(__name__)

        self.client = Client(api_key=config.aiConfig.gemini.apiKey)
        self.default_model = config.aiConfig.gemini.preferredModel
        self.logger.info(
            f"Intializing GoogleAIService with default_model={self.default_model}"
        )

    async def chat(self, messages: List[Message], model: Optional[str] = None) -> Dict:
        """
        Sends a chat request to the Google AI API.

        Args:
            model (str): The name of the model to use.
            messages (List[Dict[str, str]]): Messages for the conversation.
                Each message should include 'role' and 'content'.

        Returns:
            Dict: API response containing chat completion data.
        """
        if not self.client:
            return {
                "error": "GoogleAI Service is not initialized. Please set the GEMINI_API_KEY."
            }

        try:
            model_to_use = model or self.default_model

            gemini_messages = [
                self.map_message_to_provider(message, "google") for message in messages
            ]
            self.logger.info(
                f"Calling GoogleAIService.chat() with model={model_to_use}"
            )

            raw_response = self.client.models.generate_content(
                model=model_to_use, contents=gemini_messages
            )

            return AIChatResponse(
                model=model_to_use,
                content=raw_response.candidates[0].content.parts[0].text,
                raw_response=raw_response,
                usage={},
            )
        except Exception as e:
            self.logger.error(f"Error in GoogleAIService: {e}")
            return AIChatResponse(
                model=model_to_use,
                content=f"Chat, we ran into an error: {e}",
                raw_response=None,
                usage={},
            )

    async def chat_with_schema(
        self, messages: List[Message], schema: Type[T], model: Optional[str] = None
    ) -> T:
        if not self.client:
            return {
                "error": "GoogleAI Service is not initialized. Please set the GEMINI_API_KEY."
            }

        try:
            model_to_use = model or self.default_model

            gemini_messages = [
                self.map_message_to_provider(message, "google") for message in messages
            ]

            self.logger.info(
                f"Calling GoogleAIService.chat_with_schema() with model={model_to_use} and schema={schema.__name__}"
            )

            raw_response = self.client.models.generate_content(
                model=model_to_use,
                contents=gemini_messages,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                },
            )

            return raw_response.parsed
        except Exception as e:
            self.logger.error(f"Error in GoogleAIService.chat_with_schema(): {e}")
            raise
