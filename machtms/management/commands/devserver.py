import signal
import sys
import threading
import time
from typing import Any

import httpx
from django.conf import settings
from django.core.management import call_command
from django.core.management.commands.runserver import Command as RunserverCommand
from django.db import connections

from api.mach_testcontainers import (
    PostgresTestContainer,
    RabbitMQTestContainer,
    RedisTestContainer,
)
from machtms.management.devserver_environ import DevEnvironmentDataCreator


class Command(RunserverCommand):
    help = "Launch a dev server with testcontainers and seeded weekly loads."

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.postgres: PostgresTestContainer | None = None
        self.rabbitmq: RabbitMQTestContainer | None = None
        self.redis: RedisTestContainer | None = None
        self._original_databases: dict | None = None
        self._original_celery_broker: str | None = None
        self._original_celery_result_backend: str | None = None
        self._original_redis_url: str | None = None

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--loads-per-week",
            type=int,
            default=100,
            help="Number of loads per week (default: 100)",
        )
        parser.add_argument(
            "--offset",
            type=int,
            default=0,
            help="Week offset: 0=current week only, 1=current+next, etc. (default: 0)",
        )
        parser.add_argument(
            "--stops",
            type=int,
            default=2,
            help="Stops per load, 2 or 3 (default: 2)",
        )
        parser.add_argument(
            "--host",
            type=str,
            default="0.0.0.0",
            dest="server_host",
            help="Dev server bind address (default: 0.0.0.0)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=8000,
            dest="server_port",
            help="Dev server port (default: 8000)",
        )

    def handle(self, *args: Any, **options: Any):
        self._server_host = options["server_host"]
        self._server_port = options["server_port"]
        self._base_url = f"http://127.0.0.1:{self._server_port}"

        signal.signal(signal.SIGINT, self._signal_handler)

        try:
            self._start_containers()
            self._run_migrations()
            self._seed_data(options)
            self._start_server(**options)
            self._wait_for_server()
            self.stdout.write(
                f"\nDev server running at {self._base_url}"
                "\nPress Ctrl+C to stop.\n"
            )
            self._server_thread.join()
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _start_containers(self):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("Starting testcontainers...")
        self.stdout.write("=" * 60)

        self._original_databases = dict(settings.DATABASES)
        self._original_celery_broker = getattr(settings, "CELERY_BROKER_URL", None)
        self._original_celery_result_backend = getattr(settings, "CELERY_RESULT_BACKEND", None)
        self._original_redis_url = getattr(settings, "REDIS_URL", None)

        self.postgres = PostgresTestContainer()
        self.rabbitmq = RabbitMQTestContainer()
        self.redis = RedisTestContainer()

        self.stdout.write("Starting PostgreSQL container...")
        self.postgres.start()
        self.stdout.write(f"  -> PostgreSQL URL: {self.postgres.get_connection_url()}")

        self.stdout.write("Starting RabbitMQ container...")
        self.rabbitmq.start()
        self.stdout.write(f"  -> RabbitMQ URL: {self.rabbitmq.get_connection_url()}")

        self.stdout.write("Starting Redis container...")
        self.redis.start()
        self.stdout.write(f"  -> Redis URL: {self.redis.get_connection_url()}")

        self._wait_for_health_checks()
        self._apply_container_settings()

        self.stdout.write("=" * 60)
        self.stdout.write("All containers are ready!")
        self.stdout.write("=" * 60 + "\n")

    def _wait_for_health_checks(self, timeout: int = 30):
        start_time = time.time()
        containers = [
            ("PostgreSQL", self.postgres),
            ("RabbitMQ", self.rabbitmq),
            ("Redis", self.redis),
        ]
        for name, container in containers:
            if container is None:
                continue
            self.stdout.write(f"Waiting for {name} health check...")
            while True:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(
                        f"Container health checks timed out after {timeout}s. Failed on: {name}"
                    )
                try:
                    if container.health_check():
                        self.stdout.write(f"  -> {name} is healthy!")
                        break
                except Exception:
                    pass
                time.sleep(0.5)

    def _apply_container_settings(self):
        db_settings = self.postgres.get_django_db_settings()
        settings.DATABASES["default"] = db_settings
        connections.close_all()
        if hasattr(connections._connections, 'default'):
            del connections._connections.default
        connections._settings = connections.configure_settings(settings.DATABASES)
        self.stdout.write("Updated DATABASES['default'] with container settings")

        broker_url = self.rabbitmq.get_broker_url()
        settings.CELERY_BROKER_URL = broker_url
        self.stdout.write(f"Updated CELERY_BROKER_URL: {broker_url}")

        result_backend = self.redis.get_redis_url()
        settings.CELERY_RESULT_BACKEND = result_backend
        self.stdout.write(f"Updated CELERY_RESULT_BACKEND: {result_backend}")

        try:
            from api.celery import app as celery_app
            celery_app.config_from_object("django.conf:settings", namespace="CELERY")
            self.stdout.write("Reconfigured Celery app with test container settings")
        except ImportError:
            self.stdout.write("Warning: Could not import Celery app for reconfiguration")

        redis_url = self.redis.get_redis_url()
        settings.REDIS_URL = redis_url
        self.stdout.write(f"Updated REDIS_URL: {redis_url}")

    def _run_migrations(self):
        self.stdout.write("\nRunning migrations...")
        call_command("migrate", verbosity=0)
        self.stdout.write("Migrations complete.")

    def _seed_data(self, options: dict):
        self.stdout.write("\nSeeding weekly load data...")
        creator = DevEnvironmentDataCreator(
            loads_per_week=options["loads_per_week"],
            offset=options["offset"],
            stops_per_load=options["stops"],
        )
        data = creator.create_all()
        creator.print_summary(data)

    def _start_server(self, **options):
        self.stdout.write(f"\nStarting dev server on {self._server_host}:{self._server_port}...")
        self.addr = self._server_host
        self.port = str(self._server_port)
        self.use_ipv6 = False
        self._raw_ipv6 = False

        self._server_thread = threading.Thread(
            target=self.inner_run,
            args=(None,),
            kwargs={**options, 'use_reloader': False},
            daemon=True,
        )
        self._server_thread.start()

    def _wait_for_server(self, timeout: int = 30):
        self.stdout.write("Waiting for dev server to be ready...")
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = httpx.get(f"{self._base_url}/api/docs/", timeout=2)
                if resp.status_code < 500:
                    self.stdout.write(f"  -> Dev server ready at {self._base_url}")
                    return
            except (httpx.ConnectError, httpx.ReadTimeout):
                pass
            time.sleep(0.5)

        raise TimeoutError(
            f"Dev server did not start within {timeout}s."
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _signal_handler(self, signum, frame):
        self.stdout.write("\nReceived interrupt, shutting down...")
        self._cleanup()
        sys.exit(0)

    def _cleanup(self):
        containers = [
            ("PostgreSQL", self.postgres),
            ("RabbitMQ", self.rabbitmq),
            ("Redis", self.redis),
        ]
        for name, container in containers:
            if container is not None:
                try:
                    self.stdout.write(f"Stopping {name} container...")
                    container.stop()
                except Exception as exc:
                    self.stdout.write(f"Warning: Error stopping {name}: {exc}")

        self._restore_settings()

    def _restore_settings(self):
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
