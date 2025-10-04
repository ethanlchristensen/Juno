import json
import logging
import os
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger("bot.config")


@dataclass
class OllamaConfig:
    endpoint: str
    preferredModel: str


@dataclass
class OpenAIConfig:
    apiKey: str
    preferredModel: str


@dataclass
class AntropicConfig:
    apiKey: str
    preferredModel: str


@dataclass
class GeminiConfig:
    apiKey: str
    preferredModel: str


@dataclass
class ElevenLabsConfig:
    apiKey: str


@dataclass
class OrchestratorConfig:
    preferredAiProvider: Literal["ollama", "openai", "antropic", "gemini"]
    preferredModel: str = None


@dataclass
class AIConfig:
    preferredAiProvider: Literal["ollama", "openai", "antropic", "gemini"]
    ollama: OllamaConfig | None = None
    openai: OpenAIConfig | None = None
    antropic: AntropicConfig | None = None
    gemini: GeminiConfig | None = None
    elevenlabs: ElevenLabsConfig | None = None
    orchestrator: OrchestratorConfig | None = None


@dataclass
class Config:
    discordToken: str
    adminIds: list[int]
    invisible: bool
    aiConfig: AIConfig
    usersToId: dict[str, str]
    idToUsers: dict[str, str]
    mentionCooldown: int
    cooldownBypassList: list[int]
    promptsPath: str


class ConfigService:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config: Config | None = None

    def load(self) -> Config:
        """Load and validate configuration from JSON file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}. Please copy config.sample.json to config.json and configure it.")

        with open(self.config_path) as file:
            raw_config = json.load(file)

        self.config = self._validate_config(raw_config)
        logger.info(f"Configuration loaded successfully from {self.config_path}")
        return self.config

    def _validate_config(self, raw: dict) -> Config:
        """Validate and transform raw config dict into Config object."""
        # Validate required fields
        if not raw.get("discordToken"):
            raise ValueError("discordToken is missing or empty in the configuration.")

        if not raw.get("adminIds"):
            raise ValueError("adminIds is missing in the configuration.")

        if not raw.get("aiConfig"):
            raise ValueError("aiConfig is missing in the configuration.")

        ai_config_raw = raw["aiConfig"]
        if not ai_config_raw.get("preferredAiProvider"):
            raise ValueError("preferredAiProvider is missing in aiConfig.")

        # Build AI provider configs
        ai_config = AIConfig(
            preferredAiProvider=ai_config_raw["preferredAiProvider"],
            ollama=self._parse_ollama_config(ai_config_raw.get("ollama")),
            openai=self._parse_openai_config(ai_config_raw.get("openai")),
            antropic=self._parse_antropic_config(ai_config_raw.get("antropic")),
            gemini=self._parse_gemini_config(ai_config_raw.get("gemini")),
            elevenlabs=self._parse_elevenlabs_config(ai_config_raw.get("elevenlabs")),
            orchestrator=self._parse_orchestrator_config(ai_config_raw.get("orchestrator")),
        )

        # Validate that the preferred provider is configured
        self._validate_preferred_provider(ai_config)

        return Config(
            discordToken=raw["discordToken"],
            adminIds=raw.get("adminIds", []),
            invisible=raw.get("invisible", False),
            aiConfig=ai_config,
            usersToId=raw.get("usersToId", {}),
            idToUsers=raw.get("idToUsers", {}),
            mentionCooldown=raw.get("mentionCooldown", 20),
            cooldownBypassList=raw.get("cooldownBypassList", []),
            promptsPath=raw.get("promptsPath", "prompts.json"),
        )

    def _parse_ollama_config(self, data: dict | None) -> OllamaConfig | None:
        if not data:
            return None
        return OllamaConfig(endpoint=data.get("endpoint", "localhost:11434"), preferredModel=data.get("preferredModel", "llama3.1"))

    def _parse_openai_config(self, data: dict | None) -> OpenAIConfig | None:
        if not data or not data.get("apiKey"):
            return None
        return OpenAIConfig(apiKey=data["apiKey"], preferredModel=data.get("preferredModel", "gpt-4"))

    def _parse_antropic_config(self, data: dict | None) -> AntropicConfig | None:
        if not data or not data.get("apiKey"):
            return None
        return AntropicConfig(apiKey=data["apiKey"], preferredModel=data.get("preferredModel", "claude-3-sonnet"))

    def _parse_gemini_config(self, data: dict | None) -> GeminiConfig | None:
        if not data or not data.get("apiKey"):
            return None
        return GeminiConfig(apiKey=data["apiKey"], preferredModel=data.get("preferredModel", "gemini-pro"))

    def _parse_elevenlabs_config(self, data: dict | None) -> ElevenLabsConfig | None:
        if not data or not data.get("apiKey"):
            return None
        return ElevenLabsConfig(apiKey=data["apiKey"])

    def _parse_orchestrator_config(self, data: dict | None) -> OrchestratorConfig | None:
        if not data or not data.get("preferredAiProvider") or not data.get("preferredModel"):
            return None
        return OrchestratorConfig(preferredAiProvider=data.get("preferredAiProvider"), preferredModel=data.get("preferredModel"))

    def _validate_preferred_provider(self, ai_config: AIConfig):
        """Ensure the preferred AI provider is properly configured."""
        provider = ai_config.preferredAiProvider.lower()

        provider_map = {
            "ollama": ai_config.ollama,
            "openai": ai_config.openai,
            "antropic": ai_config.antropic,
            "anthropic": ai_config.antropic,
            "gemini": ai_config.gemini,
            "google": ai_config.gemini,
        }

        if provider not in provider_map:
            raise ValueError(f"Invalid preferredAiProvider: {provider}. Must be one of: {', '.join(provider_map.keys())}")

        if provider_map[provider] is None:
            raise ValueError(f"Preferred AI provider '{provider}' is not configured. Please add configuration for {provider} in aiConfig.")

    def get_config(self) -> Config:
        """Get the loaded configuration."""
        if self.config is None:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self.config


# Singleton instance
_config_service: ConfigService | None = None


def get_config_service(config_path: str = "config.json") -> ConfigService:
    """Get or create the ConfigService singleton."""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService(config_path)
    return _config_service
