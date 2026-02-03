"""
API package initialization.

This module ensures the Celery app is loaded when Django starts,
enabling the @shared_task decorator to work correctly.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
