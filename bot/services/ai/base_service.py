import logging

logger = logging.getLogger(__name__)

from typing import List, Dict
from abc import ABC, abstractmethod

from .types import Message, AIChatResponse


class BaseService(ABC):
    @abstractmethod
    async def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> AIChatResponse:
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
