import logging
import time
from collections import defaultdict


class CooldownService:
    def __init__(self, cooldown_duration: float, bypass_ids: set[int]):
        self.cooldown_duration = cooldown_duration
        self.bypass_ids = bypass_ids
        self.user_cooldowns = defaultdict(float)
        self.logger = logging.getLogger(__name__)

    def check_cooldown(self, user_id: int, username: str) -> bool:
        """Check if user is on cooldown. Returns True if can proceed."""
        if user_id in self.bypass_ids:
            return True

        current_time = time.time()
        last_interaction = self.user_cooldowns[user_id]
        time_since_last = current_time - last_interaction

        if time_since_last < self.cooldown_duration:
            remaining_time = int(self.cooldown_duration - time_since_last)
            self.logger.info(f"⏰ Slow down! {username} is on cooldown for {remaining_time} seconds.")
            return False

        return True

    def update_cooldown(self, user_id: int):
        """Update the last interaction time for a user."""
        self.user_cooldowns[user_id] = time.time()
