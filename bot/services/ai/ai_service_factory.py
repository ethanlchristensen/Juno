from .base_service import BaseService
from .ollama_service import OllamaService
from .openai_service import OpenAIService


class AiServiceFactory:
    @staticmethod
    def get_service(provider: str) -> BaseService:
        if provider == "ollama":
            return OllamaService()
        elif provider == "openai":
            return OpenAIService()
        else:
            raise ValueError(f"Invalid provider: {provider}")
