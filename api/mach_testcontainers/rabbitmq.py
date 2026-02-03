"""
RabbitMQ testcontainer implementation.

This module provides a RabbitMQ container for integration testing
with Celery and message queue functionality.
"""

import time

from testcontainers.rabbitmq import RabbitMqContainer

from .base import BaseTestContainer


class RabbitMQTestContainer(BaseTestContainer):
    """
    RabbitMQ test container for Celery integration testing.

    Provides a RabbitMQ message broker container with AMQP connection
    settings compatible with Celery.
    """

    def __init__(self, image: str = "rabbitmq:3.9-management") -> None:
        """
        Initialize the RabbitMQ container.

        Args:
            image: Docker image to use for RabbitMQ. Defaults to rabbitmq:3.9-management.
        """
        super().__init__()
        self.image = image
        self.configure_container()

    def configure_container(self) -> None:
        """Configure and instantiate the RabbitMQ container."""
        self.container: RabbitMqContainer = RabbitMqContainer(image=self.image)

    def get_connection_url(self) -> str:
        """
        Get the RabbitMQ AMQP connection URL.

        Returns:
            str: The AMQP connection URL in the format:
                 amqp://guest:guest@host:port//
        """
        host = self.get_host()
        port = self.container.get_exposed_port(5672)
        return f"amqp://guest:guest@{host}:{port}//"

    def get_broker_url(self) -> str:
        """
        Get the Celery broker URL (alias for get_connection_url).

        Returns:
            str: The AMQP connection URL for Celery broker configuration.
        """
        return self.get_connection_url()

    def health_check(self) -> bool:
        """
        Perform a health check on the RabbitMQ container.

        Attempts to connect to the broker with retry logic using pika.

        Returns:
            bool: True if the broker is ready for connections.

        Raises:
            Exception: If the health check fails after all retries.
        """
        import pika

        max_retries = 5
        retry_delay = 1  # seconds

        host = self.get_host()
        port = int(self.container.get_exposed_port(5672))

        for attempt in range(max_retries):
            try:
                credentials = pika.PlainCredentials("guest", "guest")
                parameters = pika.ConnectionParameters(
                    host=host,
                    port=port,
                    credentials=credentials,
                    connection_attempts=1,
                    retry_delay=0,
                )
                connection = pika.BlockingConnection(parameters)
                connection.close()
                return True
            except pika.exceptions.AMQPConnectionError as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise Exception(
                        f"RabbitMQ health check failed after {max_retries} attempts: {e}"
                    )
        return False
