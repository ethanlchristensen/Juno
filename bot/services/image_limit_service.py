import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import discord


class ImageLimitService:
    def __init__(self, max_daily_images: int):
        self.max_daily_images = max_daily_images
        self.user_usage = {}
        self.timezone = ZoneInfo("America/Chicago")  # Central Time
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"ImageLimitService initialized with max daily limit of {self.max_daily_images} images")

    def _get_next_reset_time(self) -> datetime:
        """Get the next midnight Central time."""
        now = datetime.now(self.timezone)

        # Get today's midnight
        today_midnight = datetime.combine(now.date(), time(0, 0, 0), tzinfo=self.timezone)

        # If we're past midnight today, get tomorrow's midnight
        if now >= today_midnight:
            next_midnight = today_midnight + timedelta(days=1)
        else:
            next_midnight = today_midnight

        return next_midnight

    def can_generate_image(self, user: discord.User, guild: discord.Guild) -> tuple[bool, str]:
        """Check if user can generate an image. Returns (can_generate, message)."""
        now = datetime.now(self.timezone)
        key = (guild.id, user.id)

        # Get or initialize user usage
        if key not in self.user_usage:
            self.user_usage[key] = {"count": 0, "reset_time": self._get_next_reset_time()}

        user_data = self.user_usage[key]

        # Reset if past reset time
        if now >= user_data["reset_time"]:
            user_data["count"] = 0
            user_data["reset_time"] = self._get_next_reset_time()
            self.logger.info(f"Reset daily image count for {user.name} in guild {guild.name}")

        # Check limit
        self.logger.info(f"[CAN GENERATE IMAGE] - {user.name} has generated {user_data['count']}/{self.max_daily_images} images today")
        if user_data["count"] >= self.max_daily_images:
            time_until_reset = user_data["reset_time"] - now
            hours = int(time_until_reset.total_seconds() // 3600)
            minutes = int((time_until_reset.total_seconds() % 3600) // 60)
            return False, f"Daily image limit reached ({self.max_daily_images} images). Resets in {hours}h {minutes}m."

        return True, ""

    def increment_usage(self, user_id: int, guild_id: int):
        """Increment the user's daily image count."""
        key = (guild_id, user_id)
        if key in self.user_usage:
            self.user_usage[key]["count"] += 1
            self.logger.info(f"Incremented image count for user {user_id} in guild {guild_id} to {self.user_usage[key]['count']}")

    def get_remaining_images(self, user_id: int, guild_id: int) -> int:
        """Get the number of remaining images for a user."""
        key = (guild_id, user_id)
        if key not in self.user_usage:
            return self.max_daily_images

        return max(0, self.max_daily_images - self.user_usage[key]["count"])
