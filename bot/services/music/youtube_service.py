import yt_dlp
import discord

from .types import YouTubeMetaData


class YouTubeSerivce:
    def __init__(self):
        self.ydl_opts = {"format": "bestaudio", "quiet": True, "noplaylist": True}

    def extract_info(self, query: str):
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            if query.startswith("http"):
                return ydl.extract_info(query, download=False)
            else:
                return ydl.extract_info(f"ytsearch:{query}", download=False)

    def get_audio_source(self, url: str):
        return discord.FFmpegPCMAudio(url)

    def get_metadata(self, info) -> YouTubeMetaData:
        return YouTubeMetaData(
            title=info.get("title"),
            author=info.get("uploader"),
            duration=info.get("duration"),
            likes=info.get("like_count"),
            url=info.get("webpage_url"),
            thumbnail_url=info.get("thumbnail")
        )
