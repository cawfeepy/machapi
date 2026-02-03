"""Service configuration exports."""

from .base import ServiceResult, ServiceStatus
from .django import DjangoSettings
from .database import DatabaseSettings, DATABASE_REQUIRED_VARS
from .aws import AWSConfig, AWS_REQUIRED_VARS
from .celery import CeleryConfig, CELERY_REQUIRED_VARS
from .gmail import GmailConfig, GMAIL_REQUIRED_VARS
from .redis import RedisConfig, REDIS_REQUIRED_VARS
from .meilisearch import MeilisearchConfig, MEILISEARCH_REQUIRED_VARS
from .maps import MapsConfig, MAPS_REQUIRED_VARS

__all__ = [
    # Base
    "ServiceResult",
    "ServiceStatus",
    # Django (always required)
    "DjangoSettings",
    # Database
    "DatabaseSettings",
    "DATABASE_REQUIRED_VARS",
    # Optional services
    "AWSConfig",
    "AWS_REQUIRED_VARS",
    "CeleryConfig",
    "CELERY_REQUIRED_VARS",
    "GmailConfig",
    "GMAIL_REQUIRED_VARS",
    "RedisConfig",
    "REDIS_REQUIRED_VARS",
    "MeilisearchConfig",
    "MEILISEARCH_REQUIRED_VARS",
    "MapsConfig",
    "MAPS_REQUIRED_VARS",
]
