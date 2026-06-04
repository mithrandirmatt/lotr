"""
Core configuration for the LotR TCG Server.
"""
import os
from functools import lru_cache
from typing import Dict, Any


class Settings:
    """Application settings with environment variable support."""

    # Application
    APP_NAME: str = "LotR TCG Server"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./lotr_tcg.db"
    )

    # CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080")

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds

    # Payment
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    # Redis (for caching and rate limiting)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    @classmethod
    def get_settings(cls) -> "Settings":
        """Get singleton settings instance."""
        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reload(cls) -> "Settings":
        """Reload settings from environment variables."""
        cls._instance = None
        return cls.get_settings()


@lru_cache()
def get_settings() -> Settings:
    """Cached access to settings."""
    return Settings.get_settings()


# Global settings instance
settings = get_settings()
