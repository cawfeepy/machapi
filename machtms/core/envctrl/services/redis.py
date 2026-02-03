"""Redis configuration settings."""

from typing import Optional

from pydantic import BaseModel, Field


class RedisConfig(BaseModel):
    """Redis configuration when USE_REDIS=True."""

    HOST: str = Field(default="localhost")
    PORT: int = Field(default=6379)
    DB: int = Field(default=0)
    PASSWORD: Optional[str] = None

    # Connection settings
    SOCKET_TIMEOUT: int = Field(default=5)
    SOCKET_CONNECT_TIMEOUT: int = Field(default=5)

    @property
    def URL(self) -> str:
        """Generate Redis URL from individual settings."""
        auth = f":{self.PASSWORD}@" if self.PASSWORD else ""
        return f"redis://{auth}{self.HOST}:{self.PORT}/{self.DB}"

    model_config = {"extra": "ignore"}


REDIS_REQUIRED_VARS = ["REDIS_HOST"]
