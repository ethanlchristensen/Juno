import logging 

logger = logging.getLogger(__name__)

from .base_service import BaseService
from .ollama_service import OllamaService
from .openai_service import OpenAIService
from .google_service import GoogleAIService


class AiServiceFactory:
    @staticmethod
    def get_service(provider: str) -> BaseService:
        logger.info(f"Getting AI Service for provider={provider}")
        if provider == "ollama":
            return OllamaService()
        elif provider == "openai":
            return OpenAIService()
        elif provider == "google":
            return GoogleAIService()
        else:
            raise ValueError(f"Invalid provider: {provider}")
