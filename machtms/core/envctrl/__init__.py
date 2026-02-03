"""
Environment configuration module with graceful degradation.

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

from typing import TYPE_CHECKING

from .controller import EnvironmentController
from .services.base import ServiceResult, ServiceStatus

# Global singleton - lazy initialization to avoid import-time issues
_env: EnvironmentController = None


def get_env() -> EnvironmentController:
    """
    Get the global EnvironmentController singleton.

    Uses lazy initialization to avoid issues during Django setup.
    """
    global _env
    if _env is None:
        _env = EnvironmentController()
    return _env


class _EnvProxy:
    """
    Proxy class that provides attribute access to the lazy-loaded env singleton.

    This allows using `from machtms.core.envctrl import env` and then
    accessing `env.django.DEBUG` directly, while still supporting
    lazy initialization.
    """

    def __getattr__(self, name):
        return getattr(get_env(), name)

    def __repr__(self):
        return repr(get_env())


# Export `env` with proper typing for language servers
# At type-check time: env appears as EnvironmentController (full autocomplete)
# At runtime: env is _EnvProxy (lazy initialization)
if TYPE_CHECKING:
    env: EnvironmentController
else:
    env = _EnvProxy()

__all__ = [
    "env",
    "get_env",
    "EnvironmentController",
    "ServiceResult",
    "ServiceStatus",
]
