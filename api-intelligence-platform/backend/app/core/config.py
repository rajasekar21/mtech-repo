"""Application configuration using pydantic-settings."""
from __future__ import annotations

import os
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/api_intelligence",
        description="Async PostgreSQL connection string",
    )
    PGVECTOR_ENABLED: bool = Field(
        default=False,
        description="Enable pgvector-specific database types and operators",
    )

    # ------------------------------------------------------------------ #
    # Neo4j
    # ------------------------------------------------------------------ #
    NEO4J_URI: str = Field(default="bolt://localhost:7687")
    NEO4J_USER: str = Field(default="neo4j")
    NEO4J_PASSWORD: str = Field(default="neo4j")

    # ------------------------------------------------------------------ #
    # Redis
    # ------------------------------------------------------------------ #
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # ------------------------------------------------------------------ #
    # Security / JWT
    # ------------------------------------------------------------------ #
    SECRET_KEY: str = Field(
        default="CHANGE-ME-IN-PRODUCTION-use-secrets-token-hex-32",
        description="Secret key for JWT signing — override in production",
    )
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 8)  # 8 hours

    # ------------------------------------------------------------------ #
    # AI Backend selection
    # ------------------------------------------------------------------ #
    AI_BACKEND: str = Field(default="ollama", description="openai or ollama")

    # OpenAI
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    OPENAI_MODEL: str = Field(default="gpt-4.1")
    OPENAI_EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")

    # Ollama
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="llama3.2")
    OLLAMA_EMBEDDING_MODEL: str = Field(default="nomic-embed-text")

    # ------------------------------------------------------------------ #
    # File storage
    # ------------------------------------------------------------------ #
    UPLOAD_DIR: str = Field(default="./uploads")

    # ------------------------------------------------------------------ #
    # Environment
    # ------------------------------------------------------------------ #
    ENVIRONMENT: str = Field(default="development", description="development or production")

    # ------------------------------------------------------------------ #
    # CORS
    # ------------------------------------------------------------------ #
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
    )

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    LOG_LEVEL: str = Field(default="INFO")

    # ------------------------------------------------------------------ #
    # Celery / Worker
    # ------------------------------------------------------------------ #
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/2")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


settings = Settings()
