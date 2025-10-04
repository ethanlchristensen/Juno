import asyncio
import logging
from io import BytesIO

import aiohttp
from google.genai import Client
from PIL import Image

from ..config_service import Config
from .types import ImageGenerationResponse

logger = logging.getLogger(__name__)


class ImageGenerationService:
    """Service for generating and editing images using Gemini AI."""

    def __init__(self, config: Config, model: str = "gemini-2.5-flash-image"):
        """
        Initialize the image generation service.

        Args:
            model: The Gemini model to use for image generation
        """
        self.client = Client(api_key=config.aiConfig.gemini.apiKey)
        self.model = model
        self.base_prompt = (
            "You must generate an image with the following user prompt. Do not ask follow questions to get the user to refine the prompt."
        )

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
            PIL Image object if successful, None otherwise
        """
        try:
            logger.info(f"Generating image with prompt: {prompt}")

            # Use asyncio.to_thread to avoid blocking
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=[self.base_prompt, prompt],
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
            PIL Image object if successful, None otherwise
        """
        try:
            logger.info(f"Editing image with prompt: {prompt}")

            # Use asyncio.to_thread to avoid blocking
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=[self.base_prompt, prompt, source_image],
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
            PIL Image object if successful, None otherwise
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
