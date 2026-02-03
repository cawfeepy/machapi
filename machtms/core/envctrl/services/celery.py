"""Celery configuration settings."""

from typing import List, Optional

from pydantic import BaseModel, Field


class CeleryConfig(BaseModel):
    """Celery configuration when USE_CELERY=True."""

    BROKER_URL: str = Field(..., min_length=1)
    RESULT_BACKEND: Optional[str] = None
    ACCEPT_CONTENT: List[str] = Field(default=["application/json"])
    TASK_SERIALIZER: str = "json"
    RESULT_SERIALIZER: str = "json"
    TIMEZONE: str = "UTC"
    TASK_TRACK_STARTED: bool = True
    TASK_TIME_LIMIT: int = 1800  # 30 minutes

    model_config = {"extra": "ignore"}


CELERY_REQUIRED_VARS = ["CELERY_BROKER_URL"]
