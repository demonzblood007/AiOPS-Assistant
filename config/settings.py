"""Application configuration using Pydantic Settings."""

from typing import Optional, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # LLM
    openai_api_key: Optional[str] = None
    llm_model: str = "gpt-4o-mini"
    
    # GitHub
    github_token: str = ""
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
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


settings = Settings()
