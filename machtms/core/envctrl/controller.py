"""Main environment controller with graceful degradation."""

import logging
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from .loader import load_environment
from .services.base import ServiceResult
from .services.django import DjangoSettings
from .services.database import DatabaseSettings
from .services.celery import CeleryConfig
from .services.aws import AWSConfig
from .services.gmail import GmailConfig
from .services.redis import RedisConfig
from .services.meilisearch import MeilisearchConfig
from .services.maps import MapsConfig

logger = logging.getLogger(__name__)


class EnvironmentController:
    """
    Central environment configuration with graceful degradation.

    Provides a unified interface for accessing all environment configuration
    with automatic service availability tracking.

    Usage:
        from machtms.core.envctrl import env

        # Core Django settings (always available)
        DEBUG = env.django.DEBUG

        # Optional services (check availability first)
        if env.celery.available:
            CELERY_BROKER_URL = env.celery.config.BROKER_URL

        # Quick availability checks
        if env.USE_AWS and env.aws.available:
            # Use AWS services
            pass
    """

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            # Default to project root (4 levels up from this file)
            base_dir = Path(__file__).resolve().parent.parent.parent.parent

        self._env = load_environment(base_dir)
        self._base_dir = base_dir

        # Initialize all configurations
        self._django: Optional[DjangoSettings] = None
        self._database: Optional[DatabaseSettings] = None
        self._celery: Optional[ServiceResult[CeleryConfig]] = None
        self._aws: Optional[ServiceResult[AWSConfig]] = None
        self._gmail: Optional[ServiceResult[GmailConfig]] = None
        self._redis: Optional[ServiceResult[RedisConfig]] = None
        self._meilisearch: Optional[ServiceResult[MeilisearchConfig]] = None
        self._maps: Optional[ServiceResult[MapsConfig]] = None

        self._initialize()

    def _initialize(self):
        """Initialize all configurations with graceful error handling."""
        self._django = self._load_django_settings()
        self._database = self._load_database_settings()
        self._celery = self._load_celery()
        self._aws = self._load_aws()
        self._gmail = self._load_gmail()
        self._redis = self._load_redis()
        self._meilisearch = self._load_meilisearch()
        self._maps = self._load_maps()

        # Log startup summary
        self._log_service_status()

    def _load_optional_service(
        self,
        name: str,
        enabled: bool,
        config_class: type,
        values: dict,
        required_vars: list,
    ) -> ServiceResult:
        """
        Load optional service with graceful degradation.

        Args:
            name: Service name for logging
            enabled: Whether the service is enabled (USE_* flag)
            config_class: Pydantic model class for the config
            values: Dictionary of values to pass to the config
            required_vars: List of required environment variable names

        Returns:
            ServiceResult with status and optional config
        """
        if not enabled:
            logger.debug(f"[{name}] Service disabled")
            return ServiceResult(enabled=False)

        try:
            config = config_class(**values)
            logger.info(f"[{name}] Service configured successfully")
            return ServiceResult(enabled=True, config=config)
        except ValidationError as e:
            missing = [
                str(err["loc"][0]) for err in e.errors() if err["type"] == "missing"
            ]
            invalid = [
                str(err["loc"][0]) for err in e.errors() if err["type"] != "missing"
            ]

            all_issues = missing + invalid
            logger.warning(
                f"[{name}] Service enabled but configuration invalid. "
                f"Missing/invalid: {all_issues}. Service will be UNAVAILABLE."
            )
            return ServiceResult(enabled=True, missing_vars=all_issues)

    def _log_service_status(self):
        """Log summary of all service statuses on startup."""
        services = {
            "Celery": self._celery,
            "AWS": self._aws,
            "Gmail": self._gmail,
            "Redis": self._redis,
            "Meilisearch": self._meilisearch,
            "Maps": self._maps,
        }

        unavailable = [
            f"{name} (missing: {svc.missing_vars})"
            for name, svc in services.items()
            if svc.enabled and not svc.available
        ]

        if unavailable:
            logger.warning(
                f"Services enabled but UNAVAILABLE due to missing config: {unavailable}"
            )

    # ─── Service Loaders ───────────────────────────────────────────

    def _load_django_settings(self) -> DjangoSettings:
        """Load core Django settings (always required)."""
        return DjangoSettings(
            DEBUG=self._env.bool("DEBUG", default=True),
            SECRET_KEY=self._env.str("SECRET_KEY", default="debug_secret_key_123"),
            INSECURE=self._env.bool("INSECURE", default=True),
            DJANGO_ENV=self._env.str("DJANGO_ENV", default="development"),
            ALLOWED_HOSTS=self._env.list("ALLOWED_HOSTS", default=["*"]),
            HOST=self._env.str("HOST", default="localhost"),
            COOKIE_DOMAIN=self._env.str("COOKIE_DOMAIN", default=None),
            CSRF_TRUSTED_ORIGINS=self._env.list("CSRF_TRUSTED_ORIGINS", default=[]),
            CORS_ALLOWED_ORIGINS=self._env.list("CORS_ALLOWED_ORIGINS", default=[]),
            CORS_ALLOWED_ORIGIN_REGEXES=self._env.str(
                "CORS_ALLOWED_ORIGIN_REGEXES", default=""
            ),
        )

    def _load_database_settings(self) -> DatabaseSettings:
        """Load database settings."""
        return DatabaseSettings(
            POSTGRES_HOST=self._env.str("POSTGRES_HOST", default="localhost"),
            POSTGRES_PORT=self._env.int("POSTGRES_PORT", default=5432),
            POSTGRES_DB=self._env.str("POSTGRES_DB", default="machtms"),
            POSTGRES_USER=self._env.str("POSTGRES_USER", default="postgres"),
            POSTGRES_PASSWORD=self._env.str("POSTGRES_PASSWORD", default="postgres"),
            CONN_MAX_AGE=self._env.int("CONN_MAX_AGE", default=None),
            CONN_HEALTH_CHECKS=self._env.bool("CONN_HEALTH_CHECKS", default=True),
        )

    def _load_celery(self) -> ServiceResult[CeleryConfig]:
        """Load Celery configuration."""
        return self._load_optional_service(
            name="Celery",
            enabled=self._env.bool("USE_CELERY", default=False),
            config_class=CeleryConfig,
            values={
                "BROKER_URL": self._env.str("CELERY_BROKER_URL", default=""),
                "RESULT_BACKEND": self._env.str("CELERY_RESULT_BACKEND", default=None),
                "ACCEPT_CONTENT": self._env.list(
                    "CELERY_ACCEPT_CONTENT", default=["application/json"]
                ),
                "TASK_SERIALIZER": self._env.str(
                    "CELERY_TASK_SERIALIZER", default="json"
                ),
                "RESULT_SERIALIZER": self._env.str(
                    "CELERY_RESULT_SERIALIZER", default="json"
                ),
                "TIMEZONE": self._env.str("CELERY_TIMEZONE", default="UTC"),
                "TASK_TRACK_STARTED": self._env.bool(
                    "CELERY_TASK_TRACK_STARTED", default=True
                ),
                "TASK_TIME_LIMIT": self._env.int(
                    "CELERY_TASK_TIME_LIMIT", default=1800
                ),
            },
            required_vars=["CELERY_BROKER_URL"],
        )

    def _load_aws(self) -> ServiceResult[AWSConfig]:
        """Load AWS configuration."""
        # AWS doesn't have a USE_AWS flag, check if any AWS var is set
        has_aws = bool(self._env.str("AWS_ACCESS_KEY", default=""))
        return self._load_optional_service(
            name="AWS",
            enabled=has_aws,
            config_class=AWSConfig,
            values={
                "ACCESS_KEY": self._env.str("AWS_ACCESS_KEY", default=""),
                "SECRET_KEY": self._env.str("AWS_SECRET_KEY", default=""),
                "REGION_NAME": self._env.str("AWS_REGION_NAME", default="us-west-1"),
                "UPLOAD_BUCKET": self._env.str("AWS_UPLOAD_BUCKET", default=""),
                "POST_SHIPMENT_BUCKET": self._env.str(
                    "AWS_POST_SHIPMENT_BUCKET", default=""
                ),
            },
            required_vars=[
                "AWS_ACCESS_KEY",
                "AWS_SECRET_KEY",
                "AWS_UPLOAD_BUCKET",
                "AWS_POST_SHIPMENT_BUCKET",
            ],
        )

    def _load_gmail(self) -> ServiceResult[GmailConfig]:
        """Load Gmail API configuration."""
        return self._load_optional_service(
            name="Gmail",
            enabled=self._env.bool("USE_GMAIL", default=False),
            config_class=GmailConfig,
            values={
                "CLIENT_ID": self._env.str("GMAIL_CLIENT_ID", default=""),
                "CLIENT_SECRET": self._env.str("GMAIL_CLIENT_SECRET", default=""),
                "REFRESH_TOKEN": self._env.str("GMAIL_REFRESH_TOKEN", default=""),
                "REDIRECT_URI": self._env.str(
                    "GMAIL_REDIRECT_URI", default="http://localhost:8000/oauth2callback"
                ),
                "SENDER_EMAIL": self._env.str("GMAIL_SENDER_EMAIL", default=None),
            },
            required_vars=["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"],
        )

    def _load_redis(self) -> ServiceResult[RedisConfig]:
        """Load Redis configuration."""
        return self._load_optional_service(
            name="Redis",
            enabled=self._env.bool("USE_REDIS", default=False),
            config_class=RedisConfig,
            values={
                "HOST": self._env.str("REDIS_HOST", default="localhost"),
                "PORT": self._env.int("REDIS_PORT", default=6379),
                "DB": self._env.int("REDIS_DB", default=0),
                "PASSWORD": self._env.str("REDIS_PASSWORD", default=None),
                "SOCKET_TIMEOUT": self._env.int("REDIS_SOCKET_TIMEOUT", default=5),
                "SOCKET_CONNECT_TIMEOUT": self._env.int(
                    "REDIS_SOCKET_CONNECT_TIMEOUT", default=5
                ),
            },
            required_vars=["REDIS_HOST"],
        )

    def _load_meilisearch(self) -> ServiceResult[MeilisearchConfig]:
        """Load Meilisearch configuration."""
        return self._load_optional_service(
            name="Meilisearch",
            enabled=self._env.bool("USE_MEILISEARCH", default=False),
            config_class=MeilisearchConfig,
            values={
                "HOST": self._env.str("MEILISEARCH_HOST", default="http://localhost"),
                "PORT": self._env.int("MEILISEARCH_PORT", default=7700),
                "API_KEY": self._env.str("MEILISEARCH_API_KEY", default=None),
                "SEARCH_LIMIT": self._env.int("MEILISEARCH_SEARCH_LIMIT", default=20),
                "TIMEOUT": self._env.int("MEILISEARCH_TIMEOUT", default=5000),
            },
            required_vars=["MEILISEARCH_HOST"],
        )

    def _load_maps(self) -> ServiceResult[MapsConfig]:
        """Load Google Maps API configuration."""
        return self._load_optional_service(
            name="Maps",
            enabled=self._env.bool("USE_MAPS", default=False),
            config_class=MapsConfig,
            values={
                "API_KEY": self._env.str("GOOGLE_MAPS_API_KEY", default=""),
                "REQUESTS_PER_SECOND": self._env.int(
                    "GOOGLE_MAPS_REQUESTS_PER_SECOND", default=50
                ),
                "CACHE_RESULTS": self._env.bool(
                    "GOOGLE_MAPS_CACHE_RESULTS", default=True
                ),
                "CACHE_TTL": self._env.int("GOOGLE_MAPS_CACHE_TTL", default=86400),
            },
            required_vars=["GOOGLE_MAPS_API_KEY"],
        )

    # ─── Properties ────────────────────────────────────────────────

    @property
    def django(self) -> DjangoSettings:
        """Access core Django settings."""
        return self._django

    @property
    def database(self) -> DatabaseSettings:
        """Access database settings."""
        return self._database

    @property
    def celery(self) -> ServiceResult[CeleryConfig]:
        """Access Celery configuration."""
        return self._celery

    @property
    def aws(self) -> ServiceResult[AWSConfig]:
        """Access AWS configuration."""
        return self._aws

    @property
    def gmail(self) -> ServiceResult[GmailConfig]:
        """Access Gmail API configuration."""
        return self._gmail

    @property
    def redis(self) -> ServiceResult[RedisConfig]:
        """Access Redis configuration."""
        return self._redis

    @property
    def meilisearch(self) -> ServiceResult[MeilisearchConfig]:
        """Access Meilisearch configuration."""
        return self._meilisearch

    @property
    def maps(self) -> ServiceResult[MapsConfig]:
        """Access Google Maps API configuration."""
        return self._maps

    # ─── Convenience Properties ────────────────────────────────────

    @property
    def USE_CELERY(self) -> bool:
        """Check if Celery is enabled."""
        return self._celery.enabled

    @property
    def USE_REDIS(self) -> bool:
        """Check if Redis is enabled."""
        return self._redis.enabled

    @property
    def USE_MEILISEARCH(self) -> bool:
        """Check if Meilisearch is enabled."""
        return self._meilisearch.enabled

    @property
    def USE_AWS(self) -> bool:
        """Check if AWS is enabled."""
        return self._aws.enabled

    @property
    def USE_GMAIL(self) -> bool:
        """Check if Gmail is enabled."""
        return self._gmail.enabled

    @property
    def USE_MAPS(self) -> bool:
        """Check if Google Maps is enabled."""
        return self._maps.enabled

    @property
    def BASE_DIR(self) -> Path:
        """Get the base directory of the project."""
        return self._base_dir
