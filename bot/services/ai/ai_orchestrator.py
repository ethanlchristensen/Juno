import os
import logging
from typing import Literal
from pydantic import BaseModel, Field

from bot.services  import AiServiceFactory
from .types import Message, UserIntent

logger = logging.getLogger(__name__)


class AiOrchestrator:
    def __init__(self):
        preferred_provider = os.getenv("PREFERRED_ORCHESTRATOR_PROVIDER", None)

        if not preferred_provider:
            preferred_provider = "google"
            self.model = "gemini-2.5-flash"
        else:
            self.model = os.getenv("PREFERRED_ORCHESTRATOR_MODEL", "gemini-2.5-flash")

        self.ai_service = AiServiceFactory.get_service(preferred_provider)
        logger.info(f"Initialized AiOrchestrator with provider={preferred_provider}, model={self.model}")
    
    async def detect_intent(self, user_message: str) -> UserIntent:
        """
        Detect if the user wants to chat or generate an image.
        
        Args:
            user_message: The user's message
            
        Returns:
            UserIntent: Either "chat" or "image_generation"
        """
        system_prompt = """You are an intent classifier. Determine if the user wants to:
- chat: Have a conversation, ask questions, get information
- image_generation: Create, generate, or make an image/picture/photo

Examples of image_generation:
- "generate an image of a cat"
- "create a picture of a sunset"
- "make me a logo"
- "draw a dragon"

Everything else is chat."""

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_message)
        ]
        
        try:
            intent = await self.ai_service.chat_with_schema(
                messages=messages,
                schema=UserIntent,
                model=self.model
            )
            
            logger.info(f"Detected intent: {intent.intent}")
            return intent
            
        except Exception as e:
            logger.error(f"Error detecting intent: {e}")
            # Default to chat on error
            return UserIntent(
                intent="chat",
                reasoning="Fallback due to error in intent detection"
            )