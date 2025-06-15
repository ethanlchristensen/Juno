import os
import logging
from typing import List, Dict, Optional

from google import genai
from google.genai import types
from google.genai import Client

from .base_service import BaseService
from .types import Message, AIChatResponse, AIServiceConfig


class GoogleAIService(BaseService):
    """
    A service class for interacting with Google's AI API.
    """

    def __init__(self, config: Optional[AIServiceConfig] = None):
        """
        Initializes the GoogleAIService with the necessary API key for authentication.

        Args:
            api_key (str): The Google AI API key.
        """
        if api_key := (config and config.api_key) or os.getenv("GEMINI_API_KEY"):
             self.client = Client(api_key=api_key)
        else:
            raise ValueError("GEMINI_API_KEY is not set")

        self.logger = logging.getLogger(__name__)

        self.default_model = (config and config.model) or os.getenv(
            "PREFERRED_GEMINI_MODEL", "gemini-2.0-flash"
        )
        self.logger.info(f"Intializing GoogleAIService with default_model={self.default_model}")


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
            return {"error": "GoogleAI Service is not initialized. Please set the GEMINI_API_KEY."}

        try:
            model_to_use = model or self.default_model

            gemini_messages = [
                self.map_message_to_provider(message, "google") for message in messages
            ]
            self.logger.info(f"Calling GoogleAIService.chat() with model={model_to_use}")

            raw_response = self.client.models.generate_content(model=model_to_use, contents=gemini_messages)


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
                usage={}
            )