"""
Custom Django test runner with testcontainers support.

This module provides a test runner that automatically sets up PostgreSQL,
RabbitMQ, and Redis containers for integration testing.
"""

import os
import subprocess
import sys
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

    @classmethod
    def add_arguments(cls, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--use-celery',
            action='store_true',
            default=False,
            help='Start a Celery worker subprocess for integration tests',
        )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the test runner."""
        self.use_celery = kwargs.pop('use_celery', False)
        super().__init__(*args, **kwargs)
        self.postgres_container: PostgresTestContainer | None = None
        self.rabbitmq_container: RabbitMQTestContainer | None = None
        self.redis_container: RedisTestContainer | None = None
        self._original_databases: dict[str, Any] | None = None
        self._original_celery_broker: str | None = None
        self._original_celery_result_backend: str | None = None
        self._original_redis_url: str | None = None
        self.celery_worker_process: subprocess.Popen | None = None
        self._celery_log_file = None

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

        # Expose --use-celery flag so tests can skip when no worker is running
        if self.use_celery:
            os.environ['USE_CELERY_TESTS'] = '1'
        else:
            os.environ.pop('USE_CELERY_TESTS', None)

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

        result = super().setup_databases(**kwargs)
        if self.use_celery:
            self._start_celery_worker()
        return result

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

    def _start_celery_worker(self) -> None:
        """Start a Celery worker subprocess pointing at the test database."""
        print("\n" + "=" * 60)
        print("Starting Celery worker subprocess...")
        print("=" * 60)

        # Build environment for the worker process
        worker_env = os.environ.copy()

        # Database settings (test DB name is already set by this point)
        db = settings.DATABASES['default']
        worker_env['POSTGRES_HOST'] = db['HOST']
        worker_env['POSTGRES_PORT'] = str(db['PORT'])
        worker_env['POSTGRES_DB'] = db['NAME']  # This is the test_ prefixed name
        worker_env['POSTGRES_USER'] = db['USER']
        worker_env['POSTGRES_PASSWORD'] = db['PASSWORD']

        # Celery settings
        worker_env['USE_CELERY'] = 'True'
        worker_env['CELERY_BROKER_URL'] = getattr(settings, 'CELERY_BROKER_URL', '')
        worker_env['CELERY_RESULT_BACKEND'] = getattr(
            settings, 'CELERY_RESULT_BACKEND', ''
        )

        # Django settings module
        worker_env['DJANGO_SETTINGS_MODULE'] = 'api.settings'

        # AWS credentials if available
        for attr in [
            'AWS_ACCESS_KEY', 'AWS_SECRET_KEY', 'AWS_REGION_NAME',
            'AWS_UPLOAD_BUCKET', 'AWS_POST_SHIPMENT_BUCKET',
            'AWS_RATECON_PARSE_BUCKET',
        ]:
            val = getattr(settings, attr, None)
            if val:
                worker_env[attr] = str(val)

        # OpenAI key for agent processing
        openai_key = os.environ.get('OPENAI_API_KEY', '')
        if openai_key:
            worker_env['OPENAI_API_KEY'] = openai_key

        cmd = [
            sys.executable, '-m', 'celery',
            '-A', 'api',
            'worker',
            '--loglevel=info',
            '--concurrency=2',
            '--pool=threads',
        ]

        print(f"  -> Command: {' '.join(cmd)}")
        print(f"  -> Test DB: {db['NAME']}")
        print(f"  -> Worker POSTGRES_DB: {worker_env.get('POSTGRES_DB')}")
        print(f"  -> Worker POSTGRES_HOST: {worker_env.get('POSTGRES_HOST')}")
        print(f"  -> Worker POSTGRES_PORT: {worker_env.get('POSTGRES_PORT')}")

        log_path = os.path.join(settings.BASE_DIR, 'machtms', 'logs', 'celery.txt')
        self._celery_log_file = open(log_path, 'w')
        print(f"  -> Celery worker logs: {log_path}")

        self.celery_worker_process = subprocess.Popen(
            cmd,
            env=worker_env,
            stdout=self._celery_log_file,
            stderr=subprocess.STDOUT,
        )

        # Wait briefly and verify process is alive
        time.sleep(3)
        if self.celery_worker_process.poll() is not None:
            raise RuntimeError(
                f"Celery worker exited immediately with code "
                f"{self.celery_worker_process.returncode}"
            )

        print(f"  -> Celery worker started (PID: {self.celery_worker_process.pid})")
        print("=" * 60 + "\n")

    def _stop_celery_worker(self) -> None:
        """Stop the Celery worker subprocess if it is running."""
        if self.celery_worker_process is not None:
            print("Stopping Celery worker...")
            self.celery_worker_process.terminate()
            try:
                self.celery_worker_process.wait(timeout=5)
                print("  -> Celery worker stopped gracefully")
            except subprocess.TimeoutExpired:
                print("  -> Celery worker did not stop, killing...")
                self.celery_worker_process.kill()
                self.celery_worker_process.wait()
                print("  -> Celery worker killed")
            self.celery_worker_process = None

        if self._celery_log_file is not None:
            self._celery_log_file.close()
            self._celery_log_file = None

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

        Stops the Celery worker first so its DB connection is closed
        before Django attempts to DROP the test database.

        Args:
            old_config: Database configuration from setup_databases.
            **kwargs: Additional arguments passed to parent method.
        """
        self._stop_celery_worker()
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

        self._stop_celery_worker()
        self._cleanup_containers()
        self._restore_original_settings()

        print("All containers stopped and settings restored.")
        print("=" * 60 + "\n")

        super().teardown_test_environment(**kwargs)
