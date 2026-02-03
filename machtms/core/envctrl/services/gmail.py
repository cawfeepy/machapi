"""Gmail API configuration settings."""

from typing import Optional

from pydantic import BaseModel, Field, SecretStr


class GmailConfig(BaseModel):
    """Gmail API configuration when USE_GMAIL=True."""

    CLIENT_ID: str = Field(..., min_length=1)
    CLIENT_SECRET: SecretStr = Field(...)
    REFRESH_TOKEN: SecretStr = Field(...)
    REDIRECT_URI: str = Field(default="http://localhost:8000/oauth2callback")
    SENDER_EMAIL: Optional[str] = None

    model_config = {"extra": "ignore"}


GMAIL_REQUIRED_VARS = [
    "GMAIL_CLIENT_ID",
    "GMAIL_CLIENT_SECRET",
    "GMAIL_REFRESH_TOKEN",
]
