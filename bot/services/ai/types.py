from pydantic import BaseModel, Field
from typing import Dict, List, Union, Literal, Optional, Any, ClassVar
from dataclasses import dataclass, asdict, field
from enum import Enum
from PIL.Image import Image as PILImage


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Image:
    type: str
    data: str


@dataclass
class Message:
    role: Role
    content: str
    images: Optional[List[Image]] = None
    name: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            name=data.get("name"),
            images=data.get("images", []),
        )

    def to_dict(self) -> Dict[str, Any]:
        result = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        if self.images:
            result["images"] = self.images
        return result


@dataclass
class AIChatResponse:
    model: str
    content: str
    raw_response: Any
    usage: Optional[Dict[str, int]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIChatResponse":
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AIServiceConfig:
    host: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


class UserIntent(BaseModel):
    """Structured output for user intent classification"""

    intent: Literal["chat", "image_generation"] = Field(
        description="The user's intent: chat for conversation or image_generation for creating images"
    )

    reasoning: str = Field(
        description="Brief explanation of why this intent was chosen"
    )


@dataclass
class ImageGenerationResponse:
    text_response: str = "Here is your generated image"
    generated_image: PILImage | None = None
