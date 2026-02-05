"""Application configuration using Pydantic Settings."""

from typing import Optional, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # LLM Provider Configuration
    llm_provider: Literal["openai", "anthropic", "google", "azure", "ollama", "groq"] = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    
    # OpenAI
    openai_api_key: Optional[str] = None
    
    # Anthropic (Claude)
    anthropic_api_key: Optional[str] = None
    
    # Google (Gemini)
    google_api_key: Optional[str] = None
    
    # Azure OpenAI
    azure_api_key: Optional[str] = None
    azure_endpoint: Optional[str] = None
    azure_api_version: str = "2024-02-15-preview"
    
    # Ollama (Local)
    ollama_base_url: str = "http://localhost:11434"
    
    # Groq (Fast inference)
    groq_api_key: Optional[str] = None
    
    # GitHub
    github_token: str = ""
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # PostgreSQL
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/aiops"
    
    # Langfuse (optional)
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"
    
    # App
    log_level: str = "INFO"
    max_retries: int = 3
    task_timeout: int = 300
    
    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)
    
    @property
    def is_local_llm(self) -> bool:
        """Check if using a local LLM (Ollama)."""
        return self.llm_provider == "ollama"
    
    def get_provider_key(self) -> Optional[str]:
        """Get the API key for the configured provider."""
        key_map = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "google": self.google_api_key,
            "azure": self.azure_api_key,
            "groq": self.groq_api_key,
            "ollama": None,  # No key needed for local
        }
        return key_map.get(self.llm_provider)


settings = Settings()
