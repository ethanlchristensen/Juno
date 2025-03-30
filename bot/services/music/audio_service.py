import yt_dlp
import discord
import os
from typing import Optional, Dict, Any, Union
from urllib.parse import urlparse

from .types import AudioMetaData, AudioSource, FilterPreset


class AudioService:
    def __init__(self):
        self.ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "noplaylist": True,
            "extract_flat": False,
        }

    def is_direct_media_url(self, url: str) -> bool:
        """Check if the URL is a direct link to a media file."""
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        media_extensions = [".mov", ".mp4", ".mp3", ".wav", ".ogg", ".m4a", ".webm"]
        return any(path.endswith(ext) for ext in media_extensions)

    def extract_info(self, query: str) -> Dict[str, Any]:
        if query.startswith("http") and self.is_direct_media_url(query):
            parsed_url = urlparse(query)
            filename = os.path.basename(parsed_url.path)
            info = {
                "title": filename,
                "uploader": "Direct URL",
                "duration": 0,
                "webpage_url": query,
                "url": query,
                "thumbnail": None,
                "_direct_url": True,
            }
            return info

        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            if query.startswith("http"):
                try:
                    return ydl.extract_info(query, download=False)
                except yt_dlp.utils.DownloadError as e:
                    print(f"Error extracting info: {e}")
                    raise
            else:
                try:
                    info = ydl.extract_info(f"ytsearch:{query}", download=False)
                    if info.get("entries"):
                        info = info["entries"][0]
                    return info
                except yt_dlp.utils.DownloadError:
                    try:
                        info = ydl.extract_info(f"scsearch:{query}", download=False)
                        if info.get("entries"):
                            info = info["entries"][0]
                        return info
                    except yt_dlp.utils.DownloadError as e:
                        print(f"Error searching: {e}")
                        raise

    def get_audio_source(
        self, url: str, filter_preset: Optional[FilterPreset] = None
    ) -> discord.FFmpegPCMAudio:
        before_options = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        options = "-vn"

        if filter_preset and filter_preset != FilterPreset.NONE:
            if ffmpeg_filter := filter_preset.ffmpeg_filter:
                options += f" -af {ffmpeg_filter}"

        return discord.FFmpegPCMAudio(
            url, before_options=before_options, options=options
        )

    def get_metadata(self, info: Dict[str, Any]) -> AudioMetaData:
        source_type = AudioSource.YOUTUBE

        if info.get("_direct_url"):
            source_type = AudioSource.DIRECT_URL
        elif info.get("extractor") and "soundcloud" in info.get("extractor").lower():
            source_type = AudioSource.SOUNDCLOUD

        if info.get("_type") == "playlist" and info.get("entries"):
            info = info["entries"][0]

        return AudioMetaData(
            title=info.get("title", "Unknown Title"),
            author=info.get("uploader", info.get("artist", "Unknown Artist")),
            duration=info.get("duration", 0),
            likes=info.get("like_count"),
            url=info.get("url", info.get("webpage_url", "")),
            webpage_url=info.get("webpage_url", ""),
            thumbnail_url=info.get("thumbnail"),
            source=source_type,
        )
