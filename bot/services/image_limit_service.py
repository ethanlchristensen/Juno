import json
import logging
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import discord


class ImageLimitService:
    def __init__(self, max_daily_images: int, data_file: str = "image_limits.json"):
        self.max_daily_images = max_daily_images
        self.data_file = data_file
        self.user_usage = {}
        self.timezone = ZoneInfo("America/Chicago")  # Central Time
        self.logger = logging.getLogger(__name__)

        # Load existing data
        self._load_data()

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

    def _load_data(self):
        """Load usage data from JSON file."""
        if not os.path.exists(self.data_file):
            self.logger.info(f"No existing image limits file found at {self.data_file}")
            return

        try:
            with open(self.data_file) as f:
                data = json.load(f)

            # Convert string keys back to tuples and ISO strings to datetime
            for key_str, value in data.items():
                guild_id, user_id = map(int, key_str.split(","))
                self.user_usage[(guild_id, user_id)] = {"count": value["count"], "reset_time": datetime.fromisoformat(value["reset_time"])}

            self.logger.info(f"Loaded image limit data for {len(self.user_usage)} users from {self.data_file}")
        except Exception as e:
            self.logger.error(f"Failed to load image limits data: {e}")

    def _save_data(self):
        """Save usage data to JSON file."""
        try:
            # Convert tuple keys to strings and datetime to ISO format
            data = {}
            for (guild_id, user_id), value in self.user_usage.items():
                key_str = f"{guild_id},{user_id}"
                data[key_str] = {"count": value["count"], "reset_time": value["reset_time"].isoformat()}

            with open(self.data_file, "w") as f:
                json.dump(data, f, indent=2)

            self.logger.debug(f"Saved image limit data to {self.data_file}")
        except Exception as e:
            self.logger.error(f"Failed to save image limits data: {e}")

    def can_generate_image(self, user: discord.User, guild: discord.Guild) -> tuple[bool, str]:
        """Check if user can generate an image. Returns (can_generate, message)."""
        now = datetime.now(self.timezone)
        key = (guild.id, user.id)

        # Get or initialize user usage
        if key not in self.user_usage:
            self.user_usage[key] = {"count": 0, "reset_time": self._get_next_reset_time()}
            self._save_data()

        user_data = self.user_usage[key]

        # Reset if past reset time
        if now >= user_data["reset_time"]:
            user_data["count"] = 0
            user_data["reset_time"] = self._get_next_reset_time()
            self.logger.info(f"Reset daily image count for {user.name} in guild {guild.name}")
            self._save_data()

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
            self._save_data()

    def get_remaining_images(self, user_id: int, guild_id: int) -> int:
        """Get the number of remaining images for a user."""
        key = (guild_id, user_id)
        if key not in self.user_usage:
            return self.max_daily_images

        return max(0, self.max_daily_images - self.user_usage[key]["count"])
