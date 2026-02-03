"""
CeleryController - A centralized controller for Celery task execution.

This module provides a unified interface for executing Celery tasks with
comprehensive logging, exception handling, and support for multiple
execution patterns (delay, apply_async, apply, safe_execute).

Example usage:
    from machtms.core.celerycontroller import controller
    from machtms.core.services.cache.tasks import task_update_cache

    # Using delay (async execution)
    controller.delay(task_update_cache, organization_id='org_123')

    # Using apply_async with options
    controller.apply_async(
        task_update_cache,
        kwargs={'organization_id': 'org_123'},
        countdown=60
    )

    # Fire-and-forget with exception suppression
    controller.safe_execute(
        task_update_cache,
        organization_id='org_123',
        suppress_exceptions=True
    )
"""

import logging
import traceback
from typing import Any, TypeVar
from collections.abc import Mapping, Sequence

from celery import Task
from celery.result import AsyncResult, EagerResult


T = TypeVar('T')

# Sensitive keys that should be sanitized in logs
SENSITIVE_KEYS = frozenset({
    'password',
    'token',
    'api_key',
    'apikey',
    'secret',
    'credentials',
    'credential',
    'auth',
    'authorization',
    'private_key',
    'privatekey',
    'access_token',
    'refresh_token',
    'bearer',
})


def is_sensitive_key(key: str) -> bool:
    """
    Check if a key name indicates sensitive data.

    This is a module-level function that can be shared across modules
    for consistent sanitization behavior.

    Args:
        key: The key name to check.

    Returns:
        True if the key is considered sensitive, False otherwise.

    Example:
        >>> is_sensitive_key('password')
        True
        >>> is_sensitive_key('username')
        False
    """
    if not isinstance(key, str):
        return False
    key_lower = key.lower()
    return any(sensitive in key_lower for sensitive in SENSITIVE_KEYS)


def sanitize_value(value: Any) -> Any:
    """
    Recursively sanitize sensitive values from data structures.

    This is a module-level function that can be shared across modules
    for consistent sanitization behavior.

    Args:
        value: The value to sanitize (can be dict, list, or primitive).

    Returns:
        The sanitized value with sensitive data replaced by '[REDACTED]'.

    Example:
        >>> sanitize_value({'password': 'secret123', 'username': 'john'})
        {'password': '[REDACTED]', 'username': 'john'}
    """
    if isinstance(value, Mapping):
        return {
            k: '[REDACTED]' if is_sensitive_key(k) else sanitize_value(v)
            for k, v in value.items()
        }
    elif isinstance(value, (list, tuple)):
        return [sanitize_value(item) for item in value]
    elif isinstance(value, set):
        return {sanitize_value(item) for item in value}
    return value


class CeleryController:
    """
    A centralized controller for executing Celery tasks with comprehensive
    logging and exception handling.

    This controller provides a unified interface for task execution with:
    - Structured logging for all task executions
    - Automatic sanitization of sensitive data in logs
    - Exception logging with full tracebacks
    - Multiple execution modes (async, sync, fire-and-forget)

    Attributes:
        logger: The logger instance used for task execution logging.

    Example:
        >>> from machtms.core.celerycontroller import CeleryController
        >>> controller = CeleryController()
        >>> from myapp.tasks import my_task
        >>> result = controller.delay(my_task, arg1, arg2)
    """

    def __init__(self, logger_name: str = 'machtms.core.celerycontroller') -> None:
        """
        Initialize the CeleryController with a logger.

        Args:
            logger_name: The name of the logger to use for task execution logging.
                        Defaults to 'machtms.core.celerycontroller'.

        Example:
            >>> controller = CeleryController('myapp.tasks')
        """
        self.logger = logging.getLogger(logger_name)

    def _sanitize_value(self, value: Any) -> Any:
        """
        Recursively sanitize sensitive values from data structures.

        This method delegates to the module-level sanitize_value function
        for consistent sanitization behavior across the codebase.

        Args:
            value: The value to sanitize (can be dict, list, or primitive).

        Returns:
            The sanitized value with sensitive data replaced by '[REDACTED]'.
        """
        return sanitize_value(value)

    def _is_sensitive_key(self, key: str) -> bool:
        """
        Check if a key name indicates sensitive data.

        This method delegates to the module-level is_sensitive_key function
        for consistent sanitization behavior across the codebase.

        Args:
            key: The key name to check.

        Returns:
            True if the key is considered sensitive, False otherwise.
        """
        return is_sensitive_key(key)

    def _extract_task_info(
        self,
        task: Task,
        args: Sequence[Any] | None = None,
        kwargs: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Extract metadata from a Celery task for logging purposes.

        Args:
            task: The Celery Task to extract info from.
            args: Positional arguments passed to the task.
            kwargs: Keyword arguments passed to the task.

        Returns:
            A dictionary containing:
                - name: The task name
                - module: The module containing the task
                - full_name: The fully qualified task name
                - args: Sanitized positional arguments
                - kwargs: Sanitized keyword arguments

        Example:
            >>> info = controller._extract_task_info(my_task, ('arg1',), {'key': 'value'})
            >>> print(info['name'])
            'myapp.tasks.my_task'
        """
        args = args or ()
        kwargs = kwargs or {}

        task_name = task.name
        task_module = getattr(task, '__module__', 'unknown')

        return {
            'name': task_name,
            'module': task_module,
            'full_name': task_name,
            'args': self._sanitize_value(list(args)),
            'kwargs': self._sanitize_value(dict(kwargs)),
        }

    def _log_exception(
        self,
        task_info: dict[str, Any],
        exception: Exception,
        task_id: str | None = None,
    ) -> None:
        """
        Log an exception with structured task information.

        This method logs detailed information about task failures including
        the task name, ID, arguments, exception details, and full traceback.

        Args:
            task_info: Dictionary containing task metadata from _extract_task_info.
            exception: The exception that occurred during task execution.
            task_id: The Celery task ID, if available.

        Example:
            >>> try:
            ...     result = controller.delay(my_task)
            ... except Exception as e:
            ...     controller._log_exception(task_info, e, result.id)
        """
        tb = traceback.format_exc()

        log_message = (
            f"CeleryController: Task execution failed\n"
            f"  Task: {task_info['full_name']}\n"
            f"  Task ID: {task_id or 'N/A'}\n"
            f"  Args: {task_info['args']}\n"
            f"  Kwargs: {task_info['kwargs']}\n"
            f"  Exception: {type(exception).__name__} - {exception}\n"
            f"  Traceback: {tb}"
        )

        self.logger.error(log_message)

    def _log_task_dispatch(
        self,
        task_info: dict[str, Any],
        task_id: str | None = None,
        execution_mode: str = 'async',
    ) -> None:
        """
        Log task dispatch information for debugging purposes.

        Args:
            task_info: Dictionary containing task metadata.
            task_id: The Celery task ID, if available.
            execution_mode: The mode of execution (async, sync, safe).
        """
        self.logger.debug(
            f"CeleryController: Task dispatched\n"
            f"  Task: {task_info['full_name']}\n"
            f"  Task ID: {task_id or 'N/A'}\n"
            f"  Mode: {execution_mode}\n"
            f"  Args: {task_info['args']}\n"
            f"  Kwargs: {task_info['kwargs']}"
        )

    def delay(
        self,
        task: Task,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncResult:
        """
        Execute a Celery task asynchronously using delay().

        Args:
            task: The Celery task to execute.
            *args: Positional arguments to pass to the task.
            **kwargs: Keyword arguments to pass to the task.

        Returns:
            AsyncResult from the task dispatch.

        Raises:
            TypeError: If task is not a Celery Task.
            Exception: Re-raises any exception after logging it.

        Example:
            >>> result = controller.delay(task_update_cache, organization_id='org_123')
            >>> print(result.id)
        """
        if not isinstance(task, Task):
            raise TypeError(
                f"delay() requires a Celery Task, got {type(task).__name__}"
            )

        task_info = self._extract_task_info(task, args, kwargs)
        task_id: str | None = None

        try:
            result = task.delay(*args, **kwargs)
            task_id = result.id
            self._log_task_dispatch(task_info, task_id, 'async (delay)')
            return result

        except Exception as e:
            self._log_exception(task_info, e, task_id)
            raise

    def apply_async(
        self,
        task: Task,
        args: Sequence[Any] | None = None,
        kwargs: Mapping[str, Any] | None = None,
        **options: Any,
    ) -> AsyncResult:
        """
        Execute a Celery task asynchronously with full Celery options support.

        This method provides access to all Celery apply_async options such as
        countdown, eta, expires, queue, etc.

        Args:
            task: The Celery task to execute.
            args: Positional arguments to pass to the task.
            kwargs: Keyword arguments to pass to the task.
            **options: Additional Celery options (countdown, eta, expires,
                      queue, priority, etc.)

        Returns:
            AsyncResult from the task dispatch.

        Raises:
            TypeError: If task is not a Celery Task.
            Exception: Re-raises any exception after logging it.

        Example:
            >>> # Execute with a 60-second delay
            >>> result = controller.apply_async(
            ...     task_update_cache,
            ...     kwargs={'organization_id': 'org_123'},
            ...     countdown=60
            ... )

            >>> # Execute at a specific time
            >>> from datetime import datetime, timedelta
            >>> eta = datetime.utcnow() + timedelta(hours=1)
            >>> result = controller.apply_async(
            ...     task_update_cache,
            ...     kwargs={'organization_id': 'org_123'},
            ...     eta=eta
            ... )

            >>> # Execute on a specific queue
            >>> result = controller.apply_async(
            ...     task_update_cache,
            ...     kwargs={'organization_id': 'org_123'},
            ...     queue='high_priority'
            ... )
        """
        if not isinstance(task, Task):
            raise TypeError(
                f"apply_async() requires a Celery Task, got {type(task).__name__}"
            )

        args = args or ()
        kwargs = kwargs or {}
        task_info = self._extract_task_info(task, args, kwargs)
        task_id: str | None = None

        try:
            result = task.apply_async(args=args, kwargs=kwargs, **options)
            task_id = result.id

            # Log with options info
            options_str = ', '.join(f"{k}={v}" for k, v in options.items()) if options else 'none'
            self.logger.debug(
                f"CeleryController: Task dispatched via apply_async\n"
                f"  Task: {task_info['full_name']}\n"
                f"  Task ID: {task_id}\n"
                f"  Args: {task_info['args']}\n"
                f"  Kwargs: {task_info['kwargs']}\n"
                f"  Options: {options_str}"
            )

            return result

        except Exception as e:
            self._log_exception(task_info, e, task_id)
            raise

    def apply(
        self,
        task: Task,
        args: Sequence[Any] | None = None,
        kwargs: Mapping[str, Any] | None = None,
    ) -> EagerResult:
        """
        Execute a Celery task synchronously.

        This method executes the task in the current process, blocking until
        completion. Useful for testing or when immediate execution is required.

        Args:
            task: The Celery task to execute.
            args: Positional arguments to pass to the task.
            kwargs: Keyword arguments to pass to the task.

        Returns:
            EagerResult from synchronous task execution.

        Raises:
            TypeError: If task is not a Celery Task.
            Exception: Re-raises any exception after logging it.

        Example:
            >>> # Synchronous execution
            >>> result = controller.apply(
            ...     task_update_cache,
            ...     kwargs={'organization_id': 'org_123'}
            ... )
            >>> print(result.result)  # Access the actual return value
        """
        if not isinstance(task, Task):
            raise TypeError(
                f"apply() requires a Celery Task, got {type(task).__name__}"
            )

        args = args or ()
        kwargs = kwargs or {}
        task_info = self._extract_task_info(task, args, kwargs)
        task_id: str | None = None

        try:
            result = task.apply(args=args, kwargs=kwargs)
            task_id = result.id
            self._log_task_dispatch(task_info, task_id, 'sync (apply)')
            return result

        except Exception as e:
            self._log_exception(task_info, e, task_id)
            raise

    def safe_execute(
        self,
        task: Task,
        *args: Any,
        suppress_exceptions: bool = False,
        **kwargs: Any,
    ) -> tuple[bool, AsyncResult | Exception]:
        """
        Execute a task with optional exception suppression (fire-and-forget).

        This method is ideal for non-critical background tasks where you want
        to ensure the main execution flow continues even if the task fails.

        Args:
            task: The Celery task to execute.
            *args: Positional arguments to pass to the task.
            suppress_exceptions: If True, exceptions are logged but not re-raised.
                                If False (default), exceptions are re-raised after logging.
            **kwargs: Keyword arguments to pass to the task (excluding suppress_exceptions).

        Returns:
            A tuple of (success: bool, result_or_error):
            - (True, AsyncResult) on successful task dispatch
            - (False, Exception) on failure when suppress_exceptions=True

        Raises:
            TypeError: If task is not a Celery Task.
            Exception: Re-raises any exception after logging (unless suppress_exceptions=True).

        Example:
            >>> # Fire-and-forget: exceptions won't propagate
            >>> success, result = controller.safe_execute(
            ...     task_update_cache,
            ...     organization_id='org_123',
            ...     suppress_exceptions=True
            ... )
            >>> if not success:
            ...     print(f"Task failed: {result}")  # result is the exception

            >>> # Log exceptions but still raise them
            >>> success, result = controller.safe_execute(
            ...     task_update_cache,
            ...     organization_id='org_123',
            ...     suppress_exceptions=False
            ... )
        """
        if not isinstance(task, Task):
            raise TypeError(
                f"safe_execute() requires a Celery Task, got {type(task).__name__}"
            )

        task_info = self._extract_task_info(task, args, kwargs)
        task_id: str | None = None

        try:
            result = task.delay(*args, **kwargs)
            task_id = result.id
            self._log_task_dispatch(task_info, task_id, 'safe (delay)')
            return (True, result)

        except Exception as e:
            self._log_exception(task_info, e, task_id)
            if suppress_exceptions:
                self.logger.warning(
                    f"CeleryController: Exception suppressed for task {task_info['full_name']}"
                )
                return (False, e)
            raise
