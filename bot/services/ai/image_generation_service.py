import asyncio
import logging
from io import BytesIO
from typing import TYPE_CHECKING

import aiohttp
from google.genai import Client
from google.genai.types import HarmBlockThreshold, HarmCategory
from PIL import Image

from .types import ImageGenerationResponse, Message, Role

if TYPE_CHECKING:
    from bot.juno import Juno

logger = logging.getLogger(__name__)


class ImageGenerationService:
    """Service for generating and editing images using Gemini AI."""

    def __init__(self, bot: "Juno", model: str = "gemini-2.5-flash-image"):
        """
        Initialize the image generation service.

        Args:
            model: The Gemini model to use for image generation
        """
        SAFETY_SETTINGS = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        }
        self.bot = bot
        self.client = Client(api_key=bot.config.aiConfig.gemini.apiKey, safety_settings=SAFETY_SETTINGS)
        self.model = model
        self.base_prompt = "You must generate an image with the following user prompt. Do not ask follow questions to get the user to refine the prompt."

    async def boost_prompt(self, user_prompt: str, image_description: str | None = None) -> str:
        """
        Enhance the user's prompt using AI to create more detailed image generation instructions.

        Args:
            user_prompt: The original user prompt
            image_description: Optional description of an existing image for context

        Returns:
            Enhanced prompt string
        """
        try:
            logger.info(f"Boosting prompt: {user_prompt}")

            system_message = Message(
                role=Role.SYSTEM,
                content="""You are a prompt enhancement specialist for image generation AI.
Your job is to take user prompts and enhance them with specific details about composition,
lighting, style, colors, mood, and technical aspects that will help generate better images.
Keep the core intent of the user's request while adding helpful details.
Return ONLY the enhanced prompt, no explanations or commentary.""",
            )

            if image_description:
                user_message = Message(
                    role=Role.USER,
                    content=f"""Original image description: {image_description}

User's edit request: {user_prompt}

Please enhance this edit request with specific details while maintaining the context of the original image.""",
                )
            else:
                user_message = Message(
                    role=Role.USER,
                    content=f"User prompt: {user_prompt}\n\nPlease enhance this prompt with specific details for image generation.",
                )

            response = await self.bot.ai_service.chat(messages=[system_message, user_message])
            boosted_prompt = response.content.strip()

            logger.info(f"Boosted prompt: {boosted_prompt}")
            return boosted_prompt

        except Exception as e:
            logger.error(f"Error boosting prompt: {e}", exc_info=True)
            # Return original prompt if boosting fails
            return user_prompt

    async def describe_image(self, image: Image.Image) -> str:
        """
        Generate a detailed description of an image using AI.

        Args:
            image: The PIL Image to describe

        Returns:
            Description string
        """
        try:
            logger.info("Generating image description")

            # Convert image to base64 for sending to AI
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            import base64

            img_str = base64.b64encode(buffered.getvalue()).decode()

            system_message = Message(
                role=Role.SYSTEM,
                content="""You are an image analysis expert. Describe the image in detail,
including composition, subjects, colors, lighting, mood, style, and any notable elements.
Be specific and thorough as this description will be used for image editing context.""",
            )

            user_message = Message(
                role=Role.USER,
                content="Please describe this image in detail.",
                images=[{"type": "image/png", "data": img_str}],
            )

            response = await self.bot.ai_service.chat(messages=[system_message, user_message])
            description = response.content.strip()

            logger.info(f"Generated description: {description[:100]}...")
            return description

        except Exception as e:
            logger.error(f"Error describing image: {e}", exc_info=True)
            return "Unable to describe image"

    async def download_image_from_url(self, url: str) -> Image.Image | None:
        """
        Download an image from a URL.

        Args:
            url: The URL of the image to download

        Returns:
            PIL Image object if successful, None otherwise
        """
        try:
            logger.info(f"Downloading image from: {url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        image_data = await resp.read()
                        image = Image.open(BytesIO(image_data))
                        logger.info("Image downloaded successfully")
                        return image
                    else:
                        logger.error(f"Failed to download image: HTTP {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Error downloading image: {e}", exc_info=True)
            return None

    async def generate_image(self, prompt: str) -> ImageGenerationResponse:
        """
        Generate an image from a text prompt.

        Args:
            prompt: The text description of the image to generate

        Returns:
            ImageGenerationResponse with generated image and optional text
        """
        try:
            # Boost the prompt for better results
            boosted_prompt = prompt
            if self.bot.config.aiConfig.boostImagePrompts:
                boosted_prompt = await self.boost_prompt(prompt)

            logger.info(f"Generating image with {'boosted ' if self.bot.config.aiConfig.boostImagePrompts else ''}prompt: {boosted_prompt}")

            # Use asyncio.to_thread to avoid blocking
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=[self.base_prompt, boosted_prompt],
            )

            image_generation_response = ImageGenerationResponse()

            # Extract image from response
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image = Image.open(BytesIO(part.inline_data.data))
                    image_generation_response.generated_image = image
                    logger.info("Image generated successfully")
                elif part.text is not None:
                    image_generation_response.text_response = part.text
                    logger.info(f"Received text response: {part.text}")

            return image_generation_response

        except Exception as e:
            logger.error(f"Error generating image: {e}", exc_info=True)
            return None

    async def edit_image(self, prompt: str, source_image: Image.Image) -> ImageGenerationResponse:
        """
        Edit an existing image based on a text prompt.

        Args:
            prompt: The text description of how to modify the image
            source_image: The PIL Image to edit

        Returns:
            ImageGenerationResponse with edited image and optional text
        """
        try:
            # Describe the image first
            if self.bot.config.aiConfig.boostImagePrompts:
                image_description = await self.describe_image(source_image)
                boosted_prompt = await self.boost_prompt(prompt, image_description)
                logger.info(f"Editing image with boosted prompt: {boosted_prompt}")
            else:
                boosted_prompt = prompt

            # Use asyncio.to_thread to avoid blocking
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=[self.base_prompt, boosted_prompt, source_image],
            )

            image_generation_response = ImageGenerationResponse()

            # Extract edited image from response
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image = Image.open(BytesIO(part.inline_data.data))
                    image_generation_response.generated_image = image
                    logger.info("Image edited successfully")
                elif part.text is not None:
                    image_generation_response.text_response = part.text
                    logger.info(f"Received text response: {part.text}")

            return image_generation_response

        except Exception as e:
            logger.error(f"Error editing image: {e}", exc_info=True)
            return None

    async def edit_image_from_url(self, prompt: str, image_url: str) -> ImageGenerationResponse:
        """
        Download and edit an image from a URL.

        Args:
            prompt: The text description of how to modify the image
            image_url: The URL of the image to download and edit

        Returns:
            ImageGenerationResponse with edited image and optional text
        """
        source_image = await self.download_image_from_url(image_url)
        if source_image is None:
            return None

        return await self.edit_image(prompt, source_image)

    def image_to_bytes(self, image: Image.Image, format: str = "PNG") -> BytesIO:
        """
        Convert a PIL Image to BytesIO for sending via Discord.

        Args:
            image: The PIL Image to convert
            format: The image format (PNG, JPEG, etc.)

        Returns:
            BytesIO object containing the image data
        """
        output = BytesIO()
        image.save(output, format=format)
        output.seek(0)
        return output

    async def save_image(self, image: Image.Image, filepath: str) -> bool:
        """
        Save a PIL Image to a file.

        Args:
            image: The PIL Image to save
            filepath: The path where to save the image

        Returns:
            True if successful, False otherwise
        """
        try:
            image.save(filepath)
            logger.info(f"Image saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving image to {filepath}: {e}", exc_info=True)
            return False
