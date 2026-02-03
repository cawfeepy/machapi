"""
Custom Django test runner with testcontainers support.

This module provides a test runner that automatically sets up PostgreSQL,
RabbitMQ, and Redis containers for integration testing.
"""

import time
from typing import Any

from django.conf import settings
from django.test.runner import DiscoverRunner

from .mach_testcontainers import (
    PostgresTestContainer,
    RabbitMQTestContainer,
    RedisTestContainer,
)


class TestContainerRunner(DiscoverRunner):
    """
    Django test runner that uses testcontainers for database and services.

    Automatically starts PostgreSQL, RabbitMQ, and Redis containers before
    running tests and tears them down afterward.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the test runner."""
        super().__init__(*args, **kwargs)
        self.postgres_container: PostgresTestContainer | None = None
        self.rabbitmq_container: RabbitMQTestContainer | None = None
        self.redis_container: RedisTestContainer | None = None
        self._original_databases: dict[str, Any] | None = None
        self._original_celery_broker: str | None = None
        self._original_celery_result_backend: str | None = None
        self._original_redis_url: str | None = None

    def setup_test_environment(self, **kwargs: Any) -> None:
        """
        Set up the test environment with containers.

        Starts all containers and performs health checks with a 30-second timeout.

        Args:
            **kwargs: Additional arguments passed to parent method.

        Raises:
            TimeoutError: If containers fail health checks within 30 seconds.
        """
        super().setup_test_environment(**kwargs)

        # Store original settings
        self._original_databases = dict(settings.DATABASES)
        self._original_celery_broker = getattr(settings, "CELERY_BROKER_URL", None)
        self._original_celery_result_backend = getattr(
            settings, "CELERY_RESULT_BACKEND", None
        )
        self._original_redis_url = getattr(settings, "REDIS_URL", None)

        print("\n" + "=" * 60)
        print("Starting testcontainers...")
        print("=" * 60)

        try:
            # Initialize and start containers
            self.postgres_container = PostgresTestContainer()
            self.rabbitmq_container = RabbitMQTestContainer()
            self.redis_container = RedisTestContainer()

            print("Starting PostgreSQL container...")
            self.postgres_container.start()
            print(f"  -> PostgreSQL URL: {self.postgres_container.get_connection_url()}")

            print("Starting RabbitMQ container...")
            self.rabbitmq_container.start()
            print(f"  -> RabbitMQ URL: {self.rabbitmq_container.get_connection_url()}")

            print("Starting Redis container...")
            self.redis_container.start()
            print(f"  -> Redis URL: {self.redis_container.get_connection_url()}")

            # Perform health checks with timeout
            self._wait_for_health_checks(timeout=30)

            # Update settings
            self.update_celery_settings()
            self.update_redis_settings()

            print("=" * 60)
            print("All containers are ready!")
            print("=" * 60 + "\n")

        except Exception as e:
            # Clean up on failure
            print(f"\nError starting containers: {e}")
            self._cleanup_containers()
            raise

    def _wait_for_health_checks(self, timeout: int = 30) -> None:
        """
        Wait for all containers to pass health checks.

        Args:
            timeout: Maximum time in seconds to wait for health checks.

        Raises:
            TimeoutError: If health checks don't pass within the timeout.
        """
        start_time = time.time()
        containers = [
            ("PostgreSQL", self.postgres_container),
            ("RabbitMQ", self.rabbitmq_container),
            ("Redis", self.redis_container),
        ]

        for name, container in containers:
            if container is None:
                continue

            print(f"Waiting for {name} health check...")
            while True:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(
                        f"Container health checks timed out after {timeout} seconds. "
                        f"Failed on: {name}"
                    )

                try:
                    if container.health_check():
                        print(f"  -> {name} is healthy!")
                        break
                except Exception:
                    time.sleep(0.5)

    def setup_databases(self, **kwargs: Any) -> list[tuple[Any, ...]]:
        """
        Set up test databases using the PostgreSQL container.

        Args:
            **kwargs: Additional arguments passed to parent method.

        Returns:
            list: Database configuration returned by parent method.
        """
        if self.postgres_container is not None:
            from django.db import connections

            db_settings = self.postgres_container.get_django_db_settings()
            settings.DATABASES["default"] = db_settings

            # Reset Django's connection handler to pick up new settings
            connections.close_all()
            del connections._connections.default
            connections._settings = connections.configure_settings(settings.DATABASES)

            print(f"Updated DATABASES['default'] with container settings")

        return super().setup_databases(**kwargs)

    def update_celery_settings(self) -> None:
        """Update Celery settings to use the RabbitMQ and Redis containers."""
        if self.rabbitmq_container is not None:
            broker_url = self.rabbitmq_container.get_broker_url()
            settings.CELERY_BROKER_URL = broker_url
            print(f"Updated CELERY_BROKER_URL: {broker_url}")

        if self.redis_container is not None:
            result_backend = self.redis_container.get_redis_url()
            settings.CELERY_RESULT_BACKEND = result_backend
            print(f"Updated CELERY_RESULT_BACKEND: {result_backend}")

        self._reconfigure_celery()

    def _reconfigure_celery(self) -> None:
        """Reconfigure the Celery app with updated settings."""
        try:
            from api.celery import app as celery_app

            celery_app.config_from_object("django.conf:settings", namespace="CELERY")
            print("Reconfigured Celery app with test container settings")
        except ImportError:
            print("Warning: Could not import Celery app for reconfiguration")

    def update_redis_settings(self) -> None:
        """Update Redis settings to use the Redis container."""
        if self.redis_container is not None:
            redis_url = self.redis_container.get_redis_url()
            settings.REDIS_URL = redis_url
            print(f"Updated REDIS_URL: {redis_url}")

    def _cleanup_containers(self) -> None:
        """Stop and clean up all containers."""
        containers = [
            ("PostgreSQL", self.postgres_container),
            ("RabbitMQ", self.rabbitmq_container),
            ("Redis", self.redis_container),
        ]

        for name, container in containers:
            if container is not None:
                try:
                    print(f"Stopping {name} container...")
                    container.stop()
                except Exception as e:
                    print(f"Warning: Error stopping {name} container: {e}")

    def _restore_original_settings(self) -> None:
        """Restore original Django settings."""
        if self._original_databases is not None:
            settings.DATABASES = self._original_databases

        if self._original_celery_broker is not None:
            settings.CELERY_BROKER_URL = self._original_celery_broker
        elif hasattr(settings, "CELERY_BROKER_URL"):
            delattr(settings, "CELERY_BROKER_URL")

        if self._original_celery_result_backend is not None:
            settings.CELERY_RESULT_BACKEND = self._original_celery_result_backend
        elif hasattr(settings, "CELERY_RESULT_BACKEND"):
            delattr(settings, "CELERY_RESULT_BACKEND")

        if self._original_redis_url is not None:
            settings.REDIS_URL = self._original_redis_url
        elif hasattr(settings, "REDIS_URL"):
            delattr(settings, "REDIS_URL")

    def teardown_databases(self, old_config: Any, **kwargs: Any) -> None:
        """
        Tear down the test databases.

        Args:
            old_config: Database configuration from setup_databases.
            **kwargs: Additional arguments passed to parent method.
        """
        super().teardown_databases(old_config, **kwargs)

    def teardown_test_environment(self, **kwargs: Any) -> None:
        """
        Tear down the test environment.

        Stops all containers and restores original settings.

        Args:
            **kwargs: Additional arguments passed to parent method.
        """
        print("\n" + "=" * 60)
        print("Tearing down testcontainers...")
        print("=" * 60)

        self._cleanup_containers()
        self._restore_original_settings()

        print("All containers stopped and settings restored.")
        print("=" * 60 + "\n")

        super().teardown_test_environment(**kwargs)
