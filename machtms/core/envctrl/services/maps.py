"""Google Maps API configuration settings."""

from pydantic import BaseModel, Field, SecretStr


class MapsConfig(BaseModel):
    """Google Maps API configuration when USE_MAPS=True."""

    API_KEY: SecretStr = Field(...)

    # Rate limiting
    REQUESTS_PER_SECOND: int = Field(default=50)

    # Caching
    CACHE_RESULTS: bool = Field(default=True)
    CACHE_TTL: int = Field(default=86400)  # 24 hours in seconds

    model_config = {"extra": "ignore"}


MAPS_REQUIRED_VARS = ["GOOGLE_MAPS_API_KEY"]
