import os
import re
import time
import json
import discord
import logging
import aiohttp
import base64
from collections import defaultdict

from discord.ext import commands

from bot.utils import JunoSlash
from bot.services import (
    AiServiceFactory,
    AiOrchestrator,
    ImageGenerationService,
    EmbedService,
    AudioService,
    MusicQueueService,
    Message,
    Config,
)


class Juno(commands.Bot):
    def __init__(self, intents, config: Config):
        status = discord.Status.invisible if config.invisible else discord.Status.online
        super().__init__(
            command_prefix="!", intents=intents, status=status, activity=None
        )
        self.start_time = time.time()
        self.juno_slash = JunoSlash(self.tree)
        self.ai_service = AiServiceFactory.get_service(
            provider=config.aiConfig.preferredAiProvider,
            config=config
        )
        self.embed_service = EmbedService()
        self.audio_service = AudioService()
        self.music_queue_service = MusicQueueService(self)
        self.names_to_ats = config.usersToId
        self.ids_to_users = config.idToUsers
        self.user_cooldowns = defaultdict(float)
        self.cooldown_duration = config.mentionCooldown
        self.cooldown_bypass_ids = config.cooldownBypassList
        self.ai_orchestrator = AiOrchestrator(config=config)
        self.image_generation_service = ImageGenerationService(config=config)
        self.logger = logging.getLogger(__name__)

        try:
            with open(os.path.join(os.getcwd(), config.promptsPath), "r") as f:
                self.prompts = json.load(f)
                self.logger.info(
                    f"Loaded {len(self.prompts)} prompts from prompts_path={config.promptsPath}"
                )
        except Exception as e:
            self.logger.error(f"Failed to load prompts from {config.promptsPath}: {e}")
            self.prompts = {}

    async def setup_hook(self):
        await self.juno_slash.load_commands()
        await self.load_cogs()

    async def load_cogs(self):
        cogs_dir = os.path.join(os.getcwd(), "bot", "cogs")
        self.logger.info(f"📁 Looking for cogs in: {cogs_dir}")

        cog_files = [
            f[:-3]
            for f in os.listdir(cogs_dir)
            if f.endswith(".py") and f != "__init__.py"
        ]

        total = len(cog_files)
        loaded_successfully = 0

        self.logger.info(f"📁 Found {total} cogs to load")

        for cog_name in cog_files:
            extension_path = f"bot.cogs.{cog_name}"

            try:
                await self.load_extension(extension_path)
                loaded_successfully += 1
                self.logger.info(f"✅ Successfully loaded cog: {cog_name}")
            except Exception as e:
                self.logger.error(f"❌ Failed to load cog {cog_name}: {str(e)}")

        if loaded_successfully == total:
            self.logger.info(f"🎉 All {loaded_successfully} cogs loaded successfully!")
        else:
            self.logger.info(f"📊 Cogs loaded: {loaded_successfully}/{total}")

    async def on_ready(self):
        startup_time = time.time() - self.start_time

        self.logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        self.logger.info(f"Startup completed in {startup_time:.2f} seconds")

        guild_count = len(self.guilds)
        user_count = sum(g.member_count for g in self.guilds)

        self.logger.info(
            f"🌐 Connected to {guild_count} guilds with access to {user_count} users"
        )
        self.logger.info(f"✅ Juno is online!")

    async def on_message(self, message: discord.Message):
        # Early returns for invalid messages
        if message.author == self.user or message.author.bot:
            return

        # Check if bot is mentioned or message is a reply to the bot
        reference_message = await self._get_reference_message(message)
        if not self._should_respond_to_message(message, reference_message):
            return

        # Apply cooldown check
        if not self._check_cooldown(message.author.id, message.author.name):
            return

        # Update cooldown and log interaction
        self.user_cooldowns[message.author.id] = time.time()
        username = self.ids_to_users.get(str(message.author.id), message.author.name)
        self.logger.info(
            f"📝 {username} mentioned Juno in {message.channel.name}: {message.content}"
        )
        # Process and respond
        async with message.channel.typing():
            # Determine the intent
            is_replying_to_bot_image = False
            if reference_message and reference_message.author.id == self.user.id:
                has_image = any(
                    att.content_type and att.content_type.startswith("image/")
                    for att in reference_message.attachments
                )
                is_replying_to_bot_image = has_image

            user_intent = await self.ai_orchestrator.detect_intent(
                user_message=message.content,
                is_replying_to_bot_image=is_replying_to_bot_image,
            )

            if user_intent.intent == "chat":
                self.logger.info(
                    f"Chatting with intent: {user_intent.intent} for reason of: {user_intent.reasoning}"
                )
                messages = await self._build_message_context(
                    message, reference_message, username
                )
                response = await self.ai_service.chat(messages=messages)
                await self._send_response(message, response.content)
            elif user_intent.intent == "image_generation":
                # Check if the message has an IMAGE attachment
                image_attachment = next(
                    (
                        att
                        for att in message.attachments
                        if att.content_type and att.content_type.startswith("image/")
                    ),
                    None,
                )

                # If no attachment, check if replying to a bot message with an image
                if (
                    not image_attachment
                    and reference_message
                    and reference_message.author.id == self.user.id
                ):
                    image_attachment = next(
                        (
                            att
                            for att in reference_message.attachments
                            if att.content_type
                            and att.content_type.startswith("image/")
                        ),
                        None,
                    )
                    if image_attachment:
                        self.logger.info(
                            f"Found image in referenced bot message: {image_attachment.filename}"
                        )

                if image_attachment:
                    self.logger.info(f"Editing image: {image_attachment.filename}")
                    image_generation_response = (
                        await self.image_generation_service.edit_image_from_url(
                            prompt=message.content, image_url=image_attachment.url
                        )
                    )
                    image_bytes = self.image_generation_service.image_to_bytes(
                        image=image_generation_response.generated_image
                    )
                    image_file = discord.File(image_bytes, filename="edited_image.png")
                    await self._send_response(
                        message, image_generation_response.text_response, image_file
                    )
                else:
                    self.logger.info(
                        "No image attachment found, generating image with user prompt."
                    )
                    image_generation_response = (
                        await self.image_generation_service.generate_image(
                            prompt=message.content
                        )
                    )
                    image_bytes = self.image_generation_service.image_to_bytes(
                        image=image_generation_response.generated_image
                    )
                    image_file = discord.File(
                        image_bytes, filename="generated_image.png"
                    )
                    await self._send_response(
                        message, image_generation_response.text_response, image_file
                    )

    async def _get_reference_message(self, message: discord.Message):
        """Get the referenced message if this is a reply."""
        if not message.reference:
            return None

        try:
            return await message.channel.fetch_message(message.reference.message_id)
        except discord.NotFound:
            return None

    def _should_respond_to_message(self, message: discord.Message, reference_message):
        """Check if the bot should respond to this message."""
        if not self.user:
            return False

        bot_string = f"<@{self.user.id}>"
        should_respond = bot_string in message.content or (
            reference_message and reference_message.author.id == self.user.id
        )
        return should_respond

    def _check_cooldown(self, user_id: int, username: str) -> bool:
        """Check if user is on cooldown. Returns True if can proceed."""
        if user_id in self.cooldown_bypass_ids:
            return True

        current_time = time.time()
        last_interaction = self.user_cooldowns[user_id]
        time_since_last = current_time - last_interaction

        if time_since_last < self.cooldown_duration:
            remaining_time = int(self.cooldown_duration - time_since_last)
            self.logger.info(
                f"⏰ Slow down! {username} is on cooldown for {remaining_time} seconds."
            )
            return False

        return True

    async def _process_message_images(self, message: discord.Message) -> list:
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
                                images.append(
                                    {"type": attachment.content_type, "data": img_b64}
                                )
                except Exception as e:
                    self.logger.error(f"Failed to process image attachment: {e}")
        return images

    async def _build_message_context(
        self, message: discord.Message, reference_message, username: str
    ) -> list:
        """Build the message context for AI processing."""
        images = await self._process_message_images(message)

        messages = []

        # Add system prompt if available
        if main_prompt := self.prompts.get("main"):
            messages.append(Message(role="system", content=main_prompt))

        # Add reference message context if replying
        if reference_message:
            ref_username = self.ids_to_users.get(
                str(reference_message.author.id), reference_message.author.name
            )
            ref_content = self.replace_mentions(reference_message.content).strip()
            messages.append(
                Message(role="user", content=f"{ref_username} said:\n\n{ref_content}")
            )

        # Add current message
        current_content = (
            f"{username} says:\n\n" + self.replace_mentions(message.content).strip()
        )
        messages.append(Message(role="user", content=current_content, images=images))

        return messages

    def _process_mentions_in_response(self, content: str) -> str:
        """Replace name mentions with Discord user IDs."""
        for name, user_id in self.names_to_ats.items():
            pattern = re.compile(re.escape(name), re.IGNORECASE)
            content = pattern.sub(f"{user_id}", content)
        return content

    def _split_long_message(self, content: str) -> list:
        """Split messages longer than 2000 characters."""
        if len(content) <= 2000:
            return [content]

        chunks = []
        while len(content) > 2000:
            chunk = content[:2000]
            last_space = chunk.rfind(" ")

            if last_space != -1:
                chunks.append(content[:last_space])
                content = content[last_space + 1 :]
            else:
                chunks.append(content[:2000])
                content = content[2000:]

        if content:
            chunks.append(content)

        return chunks

    async def _send_response(
        self, message: discord.Message, content: str, image_file: discord.File = None
    ):
        """Send the AI response, splitting if necessary."""
        processed_content = self._process_mentions_in_response(content)
        chunks = self._split_long_message(processed_content)

        if image_file:
            await message.reply(content=content, file=image_file)
        else:
            for idx, chunk in enumerate(chunks):
                if idx == 0:
                    await message.reply(chunk)
                else:
                    await message.channel.send("...")
                    await message.channel.send(chunk)

    def replace_mentions(self, text):
        mention = f"<@{self.user.id}>"
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
