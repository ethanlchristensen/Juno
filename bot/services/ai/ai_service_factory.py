import logging 

logger = logging.getLogger(__name__)

from .base_service import BaseService
from .ollama_service import OllamaService
from .openai_service import OpenAIService
from .google_service import GoogleAIService
from .anthropic_service import AnthropicService
from ..config_service import Config

class AiServiceFactory:
    _service_cache = {}
    
    @staticmethod
    def get_service(provider: str, config: Config) -> BaseService:
        logger.info(f"Getting AI Service for provider={provider}")
        
        if provider in AiServiceFactory._service_cache:
            logger.debug(f"Returning cached service for provider={provider}")
            return AiServiceFactory._service_cache[provider]
        
        if provider == "ollama":
            service = OllamaService(config)
        elif provider == "openai":
            service = OpenAIService(config)
        elif provider == "google":
            service = GoogleAIService(config)
        elif provider == "anthropic":
            service = AnthropicService(config)
        else:
            raise ValueError(f"Invalid provider: {provider}")
        
        AiServiceFactory._service_cache[provider] = service
        logger.debug(f"Cached new service for provider={provider}")
        
        return service