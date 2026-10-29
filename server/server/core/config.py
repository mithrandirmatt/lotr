"""
Core configuration management for the LOTR TCG server.
Handles environment variables, secrets, and application settings.
"""

import os
import secrets
from pathlib import Path
from typing import Optional
from functools import lru_cache


def _load_or_create_secret_key() -> str:
    """Return SECRET_KEY from the environment, or a persisted local fallback.

    LOT-6.5: previously routes generated `secrets.token_urlsafe(32)` fresh on
    every process start, invalidating all issued JWTs on every restart. If no
    SECRET_KEY env var is set (dev/local use), generate one once and persist
    it next to this file so it survives restarts. Production deployments
    should set the SECRET_KEY env var explicitly.
    """
    env_value = os.getenv("SECRET_KEY")
    if env_value:
        return env_value
    secret_path = Path(__file__).resolve().parent / ".jwt_secret_key"
    if secret_path.exists():
        return secret_path.read_text(encoding="utf-8").strip()
    generated = secrets.token_urlsafe(32)
    secret_path.write_text(generated, encoding="utf-8")
    return generated


class Settings:
    """Application settings with environment variable fallbacks."""

    # Server Configuration
    APP_NAME: str = "LOTR TCG Server"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Database Configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://lotr_user:lotr_password@localhost:5432/lotr_tcg"
    )
    DATABASE_POOL_SIZE: int = int(os.getenv("DATABASE_POOL_SIZE", "5"))
    DATABASE_MAX_OVERFLOW: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "10"))

    # Security Configuration
    SECRET_KEY: str = _load_or_create_secret_key()
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")
    CORS_ALLOW_CREDENTIALS: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds

    # Payment Configuration
    PAYMENT_PROVIDER: str = os.getenv("PAYMENT_PROVIDER", "stripe")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    # Redis Configuration (for caching and sessions)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_POOL_SIZE: int = int(os.getenv("REDIS_POOL_SIZE", "10"))

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Admin Configuration
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "matthew.l.cline@gmail.com")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "AdminLOTR1!")

    @classmethod
    def get_database_url(cls) -> str:
        """Get the database URL with proper formatting."""
        return cls.DATABASE_URL

    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production environment."""
        return cls.ENVIRONMENT == "production"

    @classmethod
    def get_cors_origins(cls) -> list:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in cls.CORS_ORIGINS.split(",") if origin.strip()]


# Cache settings for quick access
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
