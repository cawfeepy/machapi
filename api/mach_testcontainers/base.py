"""
Base class for testcontainers infrastructure.

This module provides an abstract base class that all specific container
implementations should inherit from.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseTestContainer(ABC):
    """
    Abstract base class for test containers.

    Provides a common interface for managing Docker containers used in testing.
    Subclasses must implement container-specific configuration, connection URLs,
    and health checks.
    """

    def __init__(self) -> None:
        """Initialize the base container with an empty container reference."""
        self.container: Any = None

    @abstractmethod
    def configure_container(self) -> None:
        """
        Configure and instantiate the specific container.

        Subclasses must implement this to create the appropriate container
        instance and assign it to self.container.
        """
        pass

    def start(self) -> None:
        """
        Start the container.

        Raises:
            RuntimeError: If the container has not been configured.
        """
        if self.container is None:
            raise RuntimeError(
                "Container not configured. Call configure_container() first."
            )
        self.container.start()

    def stop(self) -> None:
        """
        Stop the container.

        Safely stops the container if it exists and is running.
        """
        if self.container is not None:
            self.container.stop()

    @abstractmethod
    def get_connection_url(self) -> str:
        """
        Get the connection URL for the container.

        Returns:
            str: The connection URL specific to the container type.
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Perform a health check on the container.

        Returns:
            bool: True if the container is healthy and ready for connections.
        """
        pass

    def get_host(self) -> str:
        """
        Get the host IP address of the container.

        Returns:
            str: The container's host IP address.

        Raises:
            RuntimeError: If the container has not been configured.
        """
        if self.container is None:
            raise RuntimeError(
                "Container not configured. Call configure_container() first."
            )
        return self.container.get_container_host_ip()
