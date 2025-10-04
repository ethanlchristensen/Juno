import base64
import logging

import aiohttp
import discord

from bot.services import Message


class MessageService:
    def __init__(self, bot, prompts: dict, ids_to_users: dict):
        self.bot = bot
        self.prompts = prompts
        self.ids_to_users = ids_to_users
        self.logger = logging.getLogger(__name__)

    async def get_reference_message(self, message: discord.Message) -> discord.Message | None:
        """Get the referenced message if this is a reply."""
        if not message.reference:
            return None

        try:
            return await message.channel.fetch_message(message.reference.message_id)
        except discord.NotFound:
            return None

    def should_respond_to_message(self, message: discord.Message, reference_message: discord.Message | None) -> bool:
        """Check if the bot should respond to this message."""
        if not self.bot.user:
            return False

        bot_string = f"<@{self.bot.user.id}>"
        should_respond = bot_string in message.content or (reference_message and reference_message.author.id == self.bot.user.id)
        return should_respond

    async def process_message_images(self, message: discord.Message) -> list[dict]:
        """Process and encode image attachments."""
        images = []
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith("image/"):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(attachment.url) as resp:
                            if resp.status == 200:
                                img_bytes = await resp.read()
                                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                                images.append({"type": attachment.content_type, "data": img_b64})
                except Exception as e:
                    self.logger.error(f"Failed to process image attachment: {e}")
        return images

    async def build_message_context(self, message: discord.Message, reference_message: discord.Message | None, username: str) -> list[Message]:
        """Build the message context for AI processing."""
        images = await self.process_message_images(message)

        messages = []

        # Add system prompt if available
        if main_prompt := self.prompts.get("main"):
            messages.append(Message(role="system", content=main_prompt))

        # Add reference message context if replying
        if reference_message:
            ref_username = self.ids_to_users.get(str(reference_message.author.id), reference_message.author.name)
            ref_content = self.replace_mentions(reference_message.content).strip()
            messages.append(Message(role="user", content=f"{ref_username} said:\n\n{ref_content}"))

        # Add current message
        current_content = f"{username} says:\n\n" + self.replace_mentions(message.content).strip()
        messages.append(Message(role="user", content=current_content, images=images))

        return messages

    def replace_mentions(self, text: str) -> str:
        """Replace bot mentions with empty string or 'Juno'."""
        if not self.bot.user:
            return text

        mention = f"<@{self.bot.user.id}>"
        parts = text.split(mention)
        if len(parts) <= 1:
            return text

        result = parts[0]
        for i, part in enumerate(parts[1:]):
            if i == 0:
                result += "" + part
            else:
                result += "Juno" + part

        return result

    def get_image_attachment(self, message: discord.Message, reference_message: discord.Message | None = None) -> discord.Attachment | None:
        """Get image attachment from message or referenced message.
        Checks in order:
        1. Current message attachments
        2. Referenced message attachments (from any user)
        """
        # Check current message for images
        image_attachment = next(
            (att for att in message.attachments if att.content_type and att.content_type.startswith("image/")),
            None,
        )

        if image_attachment:
            self.logger.info(f"Found image in current message: {image_attachment.filename}")
            return image_attachment

        # Check referenced message for images (from any user, not just bot)
        if reference_message:
            image_attachment = next(
                (att for att in reference_message.attachments if att.content_type and att.content_type.startswith("image/")),
                None,
            )

            if image_attachment:
                author_name = self.ids_to_users.get(str(reference_message.author.id), reference_message.author.name)
                self.logger.info(f"Found image in referenced message from {author_name}: {image_attachment.filename}")
                return image_attachment

        return None

    def is_replying_to_bot_image(self, reference_message: discord.Message | None) -> bool:
        """Check if the user is replying to a bot message with an image."""
        if not reference_message or not self.bot.user:
            return False

        if reference_message.author.id != self.bot.user.id:
            return False

        has_image = any(att.content_type and att.content_type.startswith("image/") for att in reference_message.attachments)

        return has_image
