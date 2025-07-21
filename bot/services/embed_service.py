import os
import random
import discord
import logging
from typing import List, Optional
from datetime import datetime

from bot.services import AudioSource, AudioMetaData


class EmbedService:
    """Service for creating various Discord embeds"""

    logger = logging.getLogger(__name__)
    source_labels = {AudioSource.SOUNDCLOUD: "Artist", AudioSource.YOUTUBE: "Channel"}

    def create_basic_embed(
        self,
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

    def create_added_to_queue_embed(
        self, metadata: AudioMetaData, position: int, requested_by: Optional[str] = None
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
            description=f"[{metadata.title}]({metadata.webpage_url})",
            color=color,
        )

        embed.add_field(
            name=self.source_labels.get(metadata.source, "Source"),
            value=(
                metadata.author
                if not metadata.author_url
                else f"[{metadata.author}]({metadata.author_url})"
            ),
            inline=True,
        )
        embed.add_field(
            name="Duration", value=self.format_duration(metadata.duration), inline=True
        )
        embed.add_field(name="Position in Queue", value=f"#{position}", inline=True)

        if requested_by:
            embed.set_footer(text=f"Requested by: {requested_by}")

        if metadata.thumbnail_url:
            embed.set_thumbnail(url=metadata.thumbnail_url)

        if metadata.filter_preset:
            embed.add_field(
                name="Filter", value=metadata.filter_preset.display_name, inline=False
            )

        return embed

    def create_now_playing_embed(self, metadata: AudioMetaData) -> discord.Embed:
        """Create an embed for currently playing track with color based on source"""
        if metadata.source == AudioSource.YOUTUBE:
            color = 0xFF0000
        elif metadata.source == AudioSource.SOUNDCLOUD:
            color = 0xFF7700
        else:
            color = 0x808080

        embed = discord.Embed(
            title="Now Playing",
            description=f"[{metadata.title}]({metadata.webpage_url})",
            color=color,
        )

        embed.add_field(
            name=self.source_labels.get(metadata.source, "Source"),
            value=(
                metadata.author
                if not metadata.author_url
                else f"[{metadata.author}]({metadata.author_url})"
            ),
            inline=False,
        )
        embed.add_field(
            name="Duration", value=self.format_duration(metadata.duration), inline=False
        )

        if metadata.likes is not None:
            embed.add_field(name="Likes :thumbsup:", value=metadata.likes, inline=False)

        if metadata.thumbnail_url:
            embed.set_thumbnail(url=metadata.thumbnail_url)

        if metadata.filter_preset:
            embed.add_field(
                name="Filter", value=metadata.filter_preset.display_name, inline=False
            )

        embed.set_footer(text="Use /skip to skip or /queue to see what's next")

        return embed

    def create_queue_embed(
        self,
        queue_items: List[dict],
        current_track: Optional[dict] = None,
        page: int = 1,
        items_per_page: int = 5,
    ) -> discord.Embed:
        """Create an embed displaying the music queue"""
        embed = discord.Embed(title="Music Queue", color=0x1DB954)

        if current_track and current_track.get("metadata"):
            metadata = current_track["metadata"]
            author_text = (
                metadata.author
                if not metadata.author_url
                else f"[{metadata.author}]({metadata.author_url})"
            )
            embed.add_field(
                name="Currently Playing:",
                value=f"[{metadata.title}]({metadata.webpage_url}) - {author_text}",
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
                metadata: AudioMetaData = item.get("metadata")
                author_text = (
                    metadata.author
                    if not metadata.author_url
                    else f"[{metadata.author}]({metadata.author_url})"
                )
                if metadata:
                    queue_display.append(
                        f"- **{i}.** [{metadata.title}]({metadata.webpage_url}) - {author_text}\n  - {self.format_duration(metadata.duration)}\n  - Requested by: **{metadata.requested_by}**"
                    )

            embed.description = "\n".join(queue_display)

            embed.add_field(name="Songs in Queue", value={len(queue_items)}, inline=False)

            total_pages = (len(queue_items) + items_per_page - 1) // items_per_page
            embed.set_footer(
                text=f"Page {page} / {total_pages}"
            )

        return embed

    def create_error_embed(self, error_message: str) -> discord.Embed:
        """Create an embed for displaying errors"""
        return discord.Embed(title="Error", description=error_message, color=0xE74C3C)

    def create_success_embed(
        self, message: str, title: str = "Success"
    ) -> discord.Embed:
        """Create an embed for displaying success messages"""
        return discord.Embed(title=title, description=message, color=0x2ECC71)
    
    def create_morning_embed(self, message: str, title: str = "🌅 Good Morning!") -> discord.Embed:
        """Create an embed for morning messages"""
        embed = discord.Embed(title=title, description=message, color=0xF1C40F)
        embed.set_footer(text="Have a great day!")
        embed.timestamp = datetime.now()
        embed.set_thumbnail(url=f"attachment://{random.choice(os.listdir(os.path.join(os.getcwd(), 'emojis')))}")
        return embed

    @staticmethod
    def format_duration(seconds: int) -> str:
        """Convert seconds to a friendly readable format with proper singular/plural forms"""
        if not seconds or seconds <= 0:
            return "Unknown"

        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, remainder = divmod(remainder, 60)
        seconds = remainder

        parts = []
        if days > 0:
            parts.append(f"{int(days)} {'day' if days == 1 else 'days'}")
        if hours > 0:
            parts.append(f"{int(hours)} {'hour' if hours == 1 else 'hours'}")
        if minutes > 0:
            parts.append(f"{int(minutes)} {'minute' if minutes == 1 else 'minutes'}")
        if (
            seconds > 0 or not parts
        ):  # Always include seconds if it's the only component
            parts.append(f"{int(seconds)} {'second' if seconds == 1 else 'seconds'}")

        if len(parts) > 1:
            result = ", ".join(parts[:-1]) + f" and {parts[-1]}"
        else:
            result = parts[0]

        return result


class QueuePaginationView(discord.ui.View):
    def __init__(self, queue_items, current_track, embed_service):
        super().__init__(timeout=60)
        self.queue_items = queue_items
        self.current_track = current_track
        self.embed_service = embed_service
        self.current_page = 1
        self.items_per_page = 5
        self.total_pages = max(
            1, (len(queue_items) + self.items_per_page - 1) // self.items_per_page
        )

        self.update_button_states()

    def update_button_states(self):
        self.previous_button.disabled = self.current_page == 1
        self.next_button.disabled = self.current_page == self.total_pages

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current_page = max(1, self.current_page - 1)
        self.update_button_states()

        embed = self.embed_service.create_queue_embed(
            queue_items=self.queue_items,
            current_track=self.current_track,
            page=self.current_page,
            items_per_page=self.items_per_page,
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current_page = min(self.total_pages, self.current_page + 1)
        self.update_button_states()

        embed = self.embed_service.create_queue_embed(
            queue_items=self.queue_items,
            current_track=self.current_track,
            page=self.current_page,
            items_per_page=self.items_per_page,
        )

        await interaction.response.edit_message(embed=embed, view=self)
