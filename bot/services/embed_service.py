import discord
from typing import List, Optional
from datetime import datetime

from bot.services import AudioSource, AudioMetaData


class EmbedService:
    """Service for creating various Discord embeds"""

    @staticmethod
    def create_basic_embed(
        title: str,
        description: Optional[str] = None,
        color: int = 0x3498DB,  # Default blue color
        footer_text: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> discord.Embed:
        """Create a basic Discord embed with common properties"""
        embed = discord.Embed(
            title=title, description=description, color=color, timestamp=datetime.now()
        )

        if footer_text:
            embed.set_footer(text=footer_text)

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        if image_url:
            embed.set_image(url=image_url)

        return embed

    @staticmethod
    def create_added_to_queue_embed(
        metadata: AudioMetaData, position: int, requested_by: Optional[str] = None
    ) -> discord.Embed:
        """Create an embed for when a track is added to the queue"""
        if metadata.source == AudioSource.YOUTUBE:
            color = 0xFF0000
        elif metadata.source == AudioSource.SOUNDCLOUD:
            color = 0xFF7700
        else:
            color = 0x808080
            
        embed = discord.Embed(
            title="Added to Queue",
            description=f"[{metadata.title}]({metadata.url})",
            color=color,
        )

        embed.add_field(name="Channel", value=metadata.author, inline=True)
        embed.add_field(name="Duration", value=metadata.duration, inline=True)
        embed.add_field(name="Position in Queue", value=f"#{position}", inline=True)

        if requested_by:
            embed.set_footer(text=f"Requested by: {requested_by}")

        if metadata.thumbnail_url:
            embed.set_thumbnail(url=metadata.thumbnail_url)

        return embed

    @staticmethod
    def create_now_playing_embed(metadata: AudioMetaData) -> discord.Embed:
        """Create an embed for currently playing track with color based on source"""
        if metadata.source == AudioSource.YOUTUBE:
            color = 0xFF0000
        elif metadata.source == AudioSource.SOUNDCLOUD:
            color = 0xFF7700
        else:
            color = 0x808080
        
        embed = discord.Embed(
            title="Now Playing",
            description=f"[{metadata.title}]({metadata.url})",
            color=color,
        )

        embed.add_field(name="Channel", value=metadata.author, inline=True)
        embed.add_field(name="Duration", value=metadata.duration, inline=True)
        
        if metadata.likes is not None:
            embed.add_field(name="Likes", value=f"👍 {metadata.likes:,}", inline=True)

        if metadata.thumbnail_url:
            embed.set_thumbnail(url=metadata.thumbnail_url)
        
        embed.set_footer(text="Use /skip to skip or /queue to see what's next")

        return embed

    @staticmethod
    def create_queue_embed(
        queue_items: List[dict],
        current_track: Optional[dict] = None,
        page: int = 1,
        items_per_page: int = 5,
    ) -> discord.Embed:
        """Create an embed displaying the music queue"""
        embed = discord.Embed(title="Music Queue", color=0x1DB954)

        if current_track and current_track.get("metadata"):
            metadata = current_track["metadata"]
            embed.add_field(
                name="Currently Playing:",
                value=f"[{metadata.title}]({metadata.url}) | {metadata.duration} | Added by: {current_track.get('requested_by', 'Unknown')}",
                inline=False,
            )

        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page

        if not queue_items:
            embed.description = "The queue is empty! Use /play to add songs."
        else:
            queue_display = []
            for i, item in enumerate(
                queue_items[start_idx:end_idx], start=start_idx + 1
            ):
                metadata = item.get("metadata")
                if metadata:
                    queue_display.append(
                        f"**{i}.** [{metadata.title}]({metadata.url}) | {metadata.duration} | Added by: {item.get('requested_by', 'Unknown')}"
                    )

            embed.description = "\n".join(queue_display)

            # Add pagination info
            total_pages = (len(queue_items) + items_per_page - 1) // items_per_page
            embed.set_footer(
                text=f"Page {page}/{total_pages} | {len(queue_items)} songs in queue"
            )

        return embed

    @staticmethod
    def create_error_embed(error_message: str) -> discord.Embed:
        """Create an embed for displaying errors"""
        return discord.Embed(title="Error", description=error_message, color=0xE74C3C)

    @staticmethod
    def create_success_embed(message: str, title: str = "Success") -> discord.Embed:
        """Create an embed for displaying success messages"""
        return discord.Embed(title=title, description=message, color=0x2ECC71)
