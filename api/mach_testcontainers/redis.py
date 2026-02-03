"""
Redis testcontainer implementation.

This module provides a Redis container for integration testing
with caching and Celery result backend functionality.
"""

import time

from testcontainers.redis import RedisContainer

from .base import BaseTestContainer


class RedisTestContainer(BaseTestContainer):
    """
    Redis test container for caching and Celery result backend testing.

    Provides a Redis container with connection settings compatible
    with Django cache and Celery result backend configurations.
    """

    def __init__(self, image: str = "redis:7-alpine") -> None:
        """
        Initialize the Redis container.

        Args:
            image: Docker image to use for Redis. Defaults to redis:7-alpine.
        """
        super().__init__()
        self.image = image
        self.configure_container()

    def configure_container(self) -> None:
        """Configure and instantiate the Redis container."""
        self.container: RedisContainer = RedisContainer(image=self.image)

    def get_connection_url(self) -> str:
        """
        Get the Redis connection URL.

        Returns:
            str: The Redis connection URL in the format:
                 redis://host:port/0
        """
        host = self.get_host()
        port = self.container.get_exposed_port(6379)
        return f"redis://{host}:{port}/0"

    def get_redis_url(self) -> str:
        """
        Get the Redis URL (alias for get_connection_url).

        Returns:
            str: The Redis connection URL for cache/result backend configuration.
        """
        return self.get_connection_url()

    def health_check(self) -> bool:
        """
        Perform a health check on the Redis container.

        Attempts to connect to Redis with retry logic using redis-py.

        Returns:
            bool: True if Redis is ready for connections.

        Raises:
            Exception: If the health check fails after all retries.
        """
        import redis

        max_retries = 3
        retry_delay = 1  # seconds

        host = self.get_host()
        port = int(self.container.get_exposed_port(6379))

        for attempt in range(max_retries):
            try:
                client = redis.Redis(host=host, port=port, db=0)
                client.ping()
                client.close()
                return True
            except redis.ConnectionError as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise Exception(
                        f"Redis health check failed after {max_retries} attempts: {e}"
                    )
        return False
