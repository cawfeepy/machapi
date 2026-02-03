"""Meilisearch configuration settings."""

from typing import Optional

from pydantic import BaseModel, Field, SecretStr


class MeilisearchConfig(BaseModel):
    """Meilisearch configuration when USE_MEILISEARCH=True."""

    HOST: str = Field(default="http://localhost")
    PORT: int = Field(default=7700)
    API_KEY: Optional[SecretStr] = None

    # Search settings
    SEARCH_LIMIT: int = Field(default=20)
    TIMEOUT: int = Field(default=5000)  # milliseconds

    @property
    def URL(self) -> str:
        """Generate Meilisearch URL from host and port."""
        return f"{self.HOST}:{self.PORT}"

    model_config = {"extra": "ignore"}


MEILISEARCH_REQUIRED_VARS = ["MEILISEARCH_HOST"]
