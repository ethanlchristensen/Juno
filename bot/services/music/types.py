from typing import Dict, List, Union, Literal, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
from discord import app_commands


class AudioSource(Enum):
    YOUTUBE = "youtube"
    SOUNDCLOUD = "soundcloud"
    DIRECT_URL = "direct_url"


class FilterPreset(Enum):
    NONE = ("none", "None", None)
    BASSBOOST = ("bassboost", "Bass Boost", "bass=g=10")
    NIGHTCORE = (
        "nightcore",
        "Nightcore",
        "asetrate=48000*1.25,aresample=48000,atempo=0.8",
    )
    VAPORWAVE = (
        "vaporwave",
        "Vaporwave",
        "asetrate=48000*0.8,aresample=48000,atempo=1.1",
    )
    TREBLE = ("treble", "Treble Boost", "treble=g=5")
    ECHO = ("echo", "Echo", "aecho=0.8:0.88:60:0.4")
    VIBRATO = ("vibrato", "Vibrato", "vibrato=f=6.5:d=0.5")
    TREMOLO = ("tremolo", "Tremolo", "tremolo=f=6.5:d=0.5")
    DISTORTION = ("distortion", "Distortion", "areverse,areverse")
    KARAOKE = ("karaoke", "Karaoke", "stereotools=mlev=0.015625")
    MONO = ("mono", "Mono", "pan=mono|c0=0.5*c0+0.5*c1")
    VOLUME_BOOST = ("volume_boost", "Volume Boost", "volume=2.0")
    LOFI = ("lofi", "Lo-Fi", "aresample=8000,aresample=44100")
    CHORUS = (
        "chorus",
        "Chorus",
        "chorus=0.5:0.9:50|60|40:0.4|0.32|0.3:0.25|0.4|0.3:2|2.3|1.3",
    )

    def __init__(self, value: str, display_name: str, ffmpeg_filter: Optional[str]):
        self._value_ = value
        self.display_name = display_name
        self.ffmpeg_filter = ffmpeg_filter

    @classmethod
    def get_choices(cls) -> List[app_commands.Choice[str]]:
        """Convert the enum members to app_commands.Choice objects for use with slash commands"""
        return [
            app_commands.Choice(name=preset.display_name, value=preset.value)
            for preset in cls
        ]

    @classmethod
    def from_value(cls, value: str) -> "FilterPreset":
        """Get a FilterPreset from its string value"""
        for preset in cls:
            if preset.value == value:
                return preset
        return cls.NONE


@dataclass
class AudioMetaData:
    title: str
    author: str
    author_url: str
    duration: int
    url: str
    webpage_url: str
    thumbnail_url: Optional[str] = None
    source: AudioSource = AudioSource.YOUTUBE
    likes: Optional[int] = None
    filter_preset: Optional[FilterPreset] = FilterPreset.NONE
    requested_by: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioMetaData":
        filter_preset = (
            FilterPreset(data.get("filter_preset", "none"))
            if data.get("filter_preset")
            else FilterPreset.NONE
        )

        return cls(
            title=data["title"],
            author=data["author"],
            author_url=data["author_url"],
            duration=data["duration"],
            url=data["url"],
            webpage_url=data["webpage_url"],
            thumbnail_url=data.get("thumbnail_url"),
            source=AudioSource(data.get("source", "youtube")),
            likes=data.get("likes"),
            filter_preset=filter_preset,
            requested_by=data["requested_by"]
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "author_url": self.author_url,
            "duration": self.duration,
            "url": self.url,
            "webpage_url": self.webpage_url,
            "thumbnail_url": self.thumbnail_url,
            "source": self.source.value,
            "likes": self.likes,
            "filter_preset": self.filter_preset.value if self.filter_preset else None,
            "requested_by": self.requested_by
        }
