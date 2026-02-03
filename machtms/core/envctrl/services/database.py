"""Database configuration settings."""

from typing import Optional

from pydantic import BaseModel, Field


class DatabaseSettings(BaseModel):
    """PostgreSQL database configuration."""

    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="machtms")
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgres")

    # Connection pool settings
    CONN_MAX_AGE: Optional[int] = Field(default=None)
    CONN_HEALTH_CHECKS: bool = Field(default=True)

    @property
    def DATABASE_URL(self) -> str:
        """Generate a database URL from individual settings."""
        return (
            f"postgres://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = {"extra": "ignore"}


DATABASE_REQUIRED_VARS = [
    "POSTGRES_HOST",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
]
