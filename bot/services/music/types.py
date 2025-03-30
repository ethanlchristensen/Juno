from typing import Dict, List, Union, Literal, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum


class AudioSource(Enum):
    YOUTUBE = "youtube"
    SOUNDCLOUD = "soundcloud"
    DIRECT_URL = "direct_url"


@dataclass
class AudioMetaData:
    title: str
    author: str
    duration: int
    url: str
    thumbnail_url: Optional[str] = None
    source: AudioSource = AudioSource.YOUTUBE
    likes: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioMetaData":
        return cls(
            title=data["title"],
            author=data["author"],
            duration=data["duration"],
            url=data["url"],
            thumbnail_url=data.get("thumbnail_url"),
            source=AudioSource(data.get("source", "youtube")),
            likes=data.get("likes"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "duration": self.duration,
            "url": self.url,
            "thumbnail_url": self.thumbnail_url,
            "source": self.source.value,
            "likes": self.likes,
        }


YouTubeMetaData = AudioMetaData
