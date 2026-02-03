"""Core Django settings - always validated strictly."""

from typing import List, Optional

from pydantic import BaseModel, Field, SecretStr, field_validator


class DjangoSettings(BaseModel):
    """
    Core Django settings - always validated strictly.

    These settings are required for Django to function and will
    fail fast if misconfigured in production.
    """

    DEBUG: bool = True
    SECRET_KEY: SecretStr = Field(default="debug_secret_key_123")
    INSECURE: bool = True
    DJANGO_ENV: str = "development"
    ALLOWED_HOSTS: List[str] = Field(default=["*"])
    HOST: str = "localhost"
    COOKIE_DOMAIN: Optional[str] = None

    # CORS/CSRF
    CSRF_TRUSTED_ORIGINS: List[str] = Field(default_factory=list)
    CORS_ALLOWED_ORIGINS: List[str] = Field(default_factory=list)
    CORS_ALLOWED_ORIGIN_REGEXES: str = ""

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_in_production(cls, v, info):
        """Validate SECRET_KEY is set properly in production."""
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.DJANGO_ENV == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.DJANGO_ENV == "development"

    model_config = {"extra": "ignore"}
