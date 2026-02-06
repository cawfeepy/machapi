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
from machtms.agents.chat import ChatUI, NonStreamingChatController, StreamingChatController
from machtms.management.ai_environ import AIEnvironmentDataCreator

SERVER_PORT = 8877
SERVER_HOST = "0.0.0.0"
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"


class Command(RunserverCommand):
    help = "Launch an AI agent chat environment with testcontainers and fake data."

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.postgres: PostgresTestContainer | None = None
        self.rabbitmq: RabbitMQTestContainer | None = None
        self.redis: RedisTestContainer | None = None
        self._original_databases: dict | None = None
        self._original_celery_broker: str | None = None
        self._original_celery_result_backend: str | None = None
        self._original_redis_url: str | None = None

    def handle(self, *args: Any, **options: Any):
        # Register cleanup handler
        signal.signal(signal.SIGINT, self._signal_handler)

        try:
            mode = self._prompt_mode()
            self._start_containers()
            self._run_migrations()
            self._seed_data()
            self._start_server(**options)
            self._wait_for_server()
            self._launch_chat(mode)
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _prompt_mode(self) -> str:
        self.stdout.write("\nSelect chat mode:")
        self.stdout.write("  1) streaming")
        self.stdout.write("  2) non-streaming")
        choice = input("Enter 1 or 2 [1]: ").strip() or "1"
        return "streaming" if choice == "1" else "non-streaming"

    def _start_containers(self):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("Starting testcontainers...")
        self.stdout.write("=" * 60)

        # Store originals
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
        # Database
        db_settings = self.postgres.get_django_db_settings()
        settings.DATABASES["default"] = db_settings
        connections.close_all()
        if hasattr(connections._connections, 'default'):
            del connections._connections.default
        connections._settings = connections.configure_settings(settings.DATABASES)
        self.stdout.write("Updated DATABASES['default'] with container settings")

        # Celery
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

        # Redis
        redis_url = self.redis.get_redis_url()
        settings.REDIS_URL = redis_url
        self.stdout.write(f"Updated REDIS_URL: {redis_url}")

    def _run_migrations(self):
        self.stdout.write("\nRunning migrations...")
        call_command("migrate", verbosity=0)
        self.stdout.write("Migrations complete.")

    def _seed_data(self):
        self.stdout.write("\nSeeding fake data...")
        creator = AIEnvironmentDataCreator()
        data = creator.create_all()
        creator.print_summary(data)

    def _start_server(self, **options):
        self.stdout.write(f"\nStarting dev server on {SERVER_HOST}:{SERVER_PORT}...")
        self.addr = SERVER_HOST
        self.port = str(SERVER_PORT)
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
                resp = httpx.get(f"{BASE_URL}/api/docs/", timeout=2)
                if resp.status_code < 500:
                    self.stdout.write(f"  -> Dev server ready at {BASE_URL}")
                    return
            except (httpx.ConnectError, httpx.ReadTimeout):
                pass
            time.sleep(0.5)

        raise TimeoutError(
            f"Dev server did not start within {timeout}s."
        )

    def _launch_chat(self, mode: str):
        if mode == "streaming":
            controller = StreamingChatController(BASE_URL)
        else:
            controller = NonStreamingChatController(BASE_URL)

        ui = ChatUI(controller)
        ui.run()

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
