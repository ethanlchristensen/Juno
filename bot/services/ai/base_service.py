import logging

logger = logging.getLogger(__name__)

from typing import List, Dict, TypeVar, Optional, Type
from abc import ABC, abstractmethod
from pydantic import BaseModel


from .types import Message, AIChatResponse

T = TypeVar('T', bound=BaseModel)


class BaseService(ABC):
    @abstractmethod
    async def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> AIChatResponse:
        pass
    
    @abstractmethod
    async def chat_with_schema(
        self, messages: List[Message], schema: Type[T], model: Optional[str] = None
    ) -> T:
        """
        Sends a chat request with structured output based on a Pydantic schema.
        
        Args:
            messages: List of messages for the conversation
            schema: Pydantic model class defining the expected output structure
            model: Optional model name override
            
        Returns:
            Instance of the provided Pydantic model populated with the response
        """
        pass

    @staticmethod
    def map_message_to_provider(message: Message, provider: str):
        if provider == "ollama":
            mapped_message = {
                "role": message.role,
                "content": message.content,
            }

            if images := message.images:
                mapped_message["images"] = [image["data"] for image in images]

            return mapped_message
        elif provider == "openai":
            mapped_message = {
                "role": message.role,
                "content": [{"type": "text", "text": message.content}],
            }

            if images := message.images:
                mapped_message["content"].extend(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image['type']};base64,{image['data']}"
                        },
                    }
                    for image in message.images
                )

            return mapped_message
        elif provider == "google":
            mapped_message = {
                "role": message.role,
                "parts": [{"text": message.content}]
            }

            if mapped_message["role"] in ["assistant", "system"]:
                mapped_message["role"] = "model"
            
            if images := message.images:
                for image in images:
                    mapped_message["parts"].append({
                        "inline_data": {
                            "mime_type": image.get("type", ""),
                            "data": image.get("data", "")
                        }
                    })

            return mapped_message
