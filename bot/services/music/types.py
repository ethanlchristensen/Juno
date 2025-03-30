from typing import Dict, List, Union, Literal, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum


@dataclass
class YouTubeMetaData:
    title: str
    author: str
    duration: str
    likes: int
    url: str
    thumbnail_url: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "YouTubeMetaData":
        return cls(
            title=data["title"],
            author=data["author"],
            duration=data["duration"],
            likes=data["likes"],
            url=data["url"],
            thumbnail_url=data["thumbnail_url"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "duration": self.duration,
            "likes": self.likes,
            "url": self.url,
            "thumbnail_url": self.thumbnail_url,
        }
