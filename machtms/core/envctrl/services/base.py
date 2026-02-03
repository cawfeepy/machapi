"""Base classes for service configuration with graceful degradation."""

from enum import Enum
from typing import Generic, TypeVar, Optional, List

from pydantic import BaseModel


class ServiceStatus(str, Enum):
    """Status of an optional service."""

    DISABLED = "disabled"  # USE_* is False (not enabled)
    AVAILABLE = "available"  # USE_* is True, properly configured
    UNAVAILABLE = "unavailable"  # USE_* is True, missing required vars


T = TypeVar("T", bound=BaseModel)


class ServiceResult(Generic[T]):
    """
    Wrapper for optional service configuration with status tracking.

    Provides graceful degradation - services can be enabled but unavailable
    if required configuration is missing.

    Examples:
        >>> result = ServiceResult(enabled=True, config=CeleryConfig(...))
        >>> result.available  # True
        >>> result.config.BROKER_URL  # Access config

        >>> result = ServiceResult(enabled=True, missing_vars=["BROKER_URL"])
        >>> result.available  # False
        >>> result.config  # None
    """

    def __init__(
        self,
        enabled: bool,
        config: Optional[T] = None,
        missing_vars: Optional[List[str]] = None,
    ):
        self.enabled = enabled
        self._config = config
        self.missing_vars = missing_vars or []

    @property
    def status(self) -> ServiceStatus:
        """Get the current status of the service."""
        if not self.enabled:
            return ServiceStatus.DISABLED
        return ServiceStatus.AVAILABLE if self._config else ServiceStatus.UNAVAILABLE

    @property
    def available(self) -> bool:
        """Check if the service is available for use."""
        return self.status == ServiceStatus.AVAILABLE

    @property
    def config(self) -> Optional[T]:
        """
        Get the service configuration if available.

        Returns None if the service is disabled or unavailable.
        """
        if not self.available:
            return None
        return self._config

    def __repr__(self) -> str:
        return f"ServiceResult(status={self.status.value}, enabled={self.enabled})"
