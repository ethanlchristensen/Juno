import datetime
import logging
from typing import TYPE_CHECKING, List

import discord
import pymongo
from bson import Int64

from .ai.types import Message

if TYPE_CHECKING:
    from bot.juno import Juno


class DiscordMessagesService:
    def __init__(self, bot: "Juno"):
        self.bot = bot
        self.mongo_client = pymongo.MongoClient(self.bot.config.mongoUri)
        self.db = self.mongo_client[self.bot.config.mongoDbName]
        self.messages_collection = self.db[self.bot.config.mongoMessagesCollectionName]
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized DiscordMessagesService with collection {self.messages_collection.name}")

    def get_last_n_messages_within_n_minutes(self, message: discord.Message, n: int, minutes: int) -> List[Message]:
        time_threshold = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes)).replace(tzinfo=None)
        query = {
            "guild_id": Int64(message.guild.id),
            "channel_id": Int64(message.channel.id),
            "timestamp": {"$gte": time_threshold},
            "message_id": {"$ne": Int64(message.id)},
            "deleted": False
        }
        messages = list(self.messages_collection.find(query).sort({"timestamp": 1}).limit(n))
        self.logger.info(f"Fetched {len(messages)} messages for guild_id {message.guild.id}:{message.channel.id} since {time_threshold.isoformat()}")
        return [self.convert_db_message_to_ai_message(msg) for msg in reversed(messages)]

    def convert_db_message_to_ai_message(self, db_message) -> Message:
        role = "user" if db_message["author_id"] != self.bot.user.id else "assistant"
        user = self.bot.config.usersToId.get(db_message["author_id"], db_message["author_name"])
        return Message(role=role, content=f"{user}: {db_message['content']}")