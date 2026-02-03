"""
Testcontainers infrastructure for integration testing.

This package provides Docker container wrappers for testing Django
applications with real database, message broker, and cache services.
"""

from .base import BaseTestContainer
from .postgres import PostgresTestContainer
from .rabbitmq import RabbitMQTestContainer
from .redis import RedisTestContainer

__all__ = [
    "BaseTestContainer",
    "PostgresTestContainer",
    "RabbitMQTestContainer",
    "RedisTestContainer",
]
