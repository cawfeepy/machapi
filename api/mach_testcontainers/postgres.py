"""
PostgreSQL testcontainer implementation.

This module provides a PostgreSQL container for integration testing
with Django applications.
"""

import time
from typing import Any

from testcontainers.postgres import PostgresContainer

from .base import BaseTestContainer


class PostgresTestContainer(BaseTestContainer):
    """
    PostgreSQL test container for Django integration testing.

    Provides a PostgreSQL database container with Django-compatible
    connection settings.
    """

    def __init__(self, image: str = "postgres:15-alpine") -> None:
        """
        Initialize the PostgreSQL container.

        Args:
            image: Docker image to use for PostgreSQL. Defaults to postgres:15-alpine.
        """
        super().__init__()
        self.image = image
        self.configure_container()

    def configure_container(self) -> None:
        """Configure and instantiate the PostgreSQL container."""
        self.container: PostgresContainer = PostgresContainer(image=self.image)

    def get_connection_url(self) -> str:
        """
        Get the PostgreSQL connection URL.

        Returns:
            str: The PostgreSQL connection URL in the format:
                 postgresql://user:password@host:port/dbname
        """
        host = self.get_host()
        port = self.container.get_exposed_port(5432)
        username = self.container.username
        password = self.container.password
        dbname = self.container.dbname
        return f"postgresql://{username}:{password}@{host}:{port}/{dbname}"

    def get_django_db_settings(self) -> dict[str, Any]:
        """
        Get Django-compatible database settings.

        Returns:
            dict: A dictionary containing Django DATABASE settings.
        """
        host = self.get_host()
        port = self.container.get_exposed_port(5432)

        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": self.container.dbname,
            "USER": self.container.username,
            "PASSWORD": self.container.password,
            "HOST": host,
            "PORT": port,
        }

    def health_check(self) -> bool:
        """
        Perform a health check on the PostgreSQL container.

        Attempts to connect to the database with retry logic.

        Returns:
            bool: True if the database is ready for connections.

        Raises:
            Exception: If the health check fails after all retries.
        """
        import psycopg2

        max_retries = 3
        retry_delay = 1  # seconds

        host = self.get_host()
        port = self.container.get_exposed_port(5432)

        for attempt in range(max_retries):
            try:
                conn = psycopg2.connect(
                    host=host,
                    port=port,
                    user=self.container.username,
                    password=self.container.password,
                    dbname=self.container.dbname,
                )
                conn.close()
                return True
            except psycopg2.OperationalError as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise Exception(
                        f"PostgreSQL health check failed after {max_retries} attempts: {e}"
                    )
        return False
