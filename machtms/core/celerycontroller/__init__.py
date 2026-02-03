"""
CeleryController module for centralized Celery task execution.

This module provides the CeleryController class and a pre-configured
singleton instance for convenient task execution throughout the application.

Usage:
    # Using the singleton instance (recommended)
    from machtms.core.celerycontroller import controller
    from machtms.core.services.cache.tasks import task_update_cache

    result = controller.delay(task_update_cache, organization_id='org_123')

    # Or create your own instance with custom logger
    from machtms.core.celerycontroller import CeleryController

    my_controller = CeleryController(logger_name='myapp.celery')
    result = my_controller.delay(task_update_cache, organization_id='org_123')

    # Initialize Celery signal handlers for centralized logging
    from machtms.core.celerycontroller import setup_celery_logging
    setup_celery_logging()
"""

from machtms.core.celerycontroller.controller import (
    CeleryController,
    sanitize_value,
)
from machtms.core.celerycontroller.signals import setup_celery_logging

# Module-level singleton instance for convenient access
controller = CeleryController()

__all__ = [
    'CeleryController',
    'controller',
    'sanitize_value',
    'setup_celery_logging',
]
