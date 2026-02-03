"""
Celery signal handlers for centralized task execution logging.

This module provides signal handlers that automatically log Celery task
execution events including failures, retries, successes, and pre-run events.
The handlers use the same sanitization logic as the CeleryController to
ensure sensitive data is never logged.

Usage:
    # In your api/celery.py after app initialization:
    from machtms.core.celerycontroller import setup_celery_logging
    setup_celery_logging()

Configuration:
    The following Django settings control optional logging:
    - CELERY_ENABLE_SUCCESS_LOGGING: Log successful task completions (default: False)
    - CELERY_ENABLE_PRERUN_LOGGING: Log task pre-run events (default: False)
"""

import logging
import traceback
from typing import Any

from celery.signals import task_failure, task_prerun, task_retry, task_success

from machtms.core.celerycontroller.controller import sanitize_value


logger = logging.getLogger('machtms.core.celerycontroller.signals')


def _get_setting(name: str, default: Any = None) -> Any:
    """
    Safely retrieve a Django setting with a default fallback.

    Args:
        name: The setting name to retrieve.
        default: The default value if the setting doesn't exist.

    Returns:
        The setting value or the default.
    """
    try:
        from django.conf import settings
        return getattr(settings, name, default)
    except Exception:
        return default


def _format_task_failure_log(
    task_name: str,
    task_id: str,
    args: tuple | None,
    kwargs: dict | None,
    exception: Exception,
    tb: str,
) -> str:
    """
    Format a task failure log message in a consistent format.

    Args:
        task_name: The name of the failed task.
        task_id: The Celery task ID.
        args: The positional arguments passed to the task.
        kwargs: The keyword arguments passed to the task.
        exception: The exception that caused the failure.
        tb: The formatted traceback string.

    Returns:
        A formatted log message string.
    """
    sanitized_args = sanitize_value(list(args)) if args else []
    sanitized_kwargs = sanitize_value(dict(kwargs)) if kwargs else {}

    return (
        f"CeleryController.signals: Task execution failed\n"
        f"  Task: {task_name}\n"
        f"  Task ID: {task_id}\n"
        f"  Args: {sanitized_args}\n"
        f"  Kwargs: {sanitized_kwargs}\n"
        f"  Exception: {type(exception).__name__} - {exception}\n"
        f"  Traceback: {tb}"
    )


def _format_task_retry_log(
    task_name: str,
    task_id: str,
    reason: str,
    args: tuple | None,
    kwargs: dict | None,
) -> str:
    """
    Format a task retry log message.

    Args:
        task_name: The name of the retrying task.
        task_id: The Celery task ID.
        reason: The reason for the retry.
        args: The positional arguments passed to the task.
        kwargs: The keyword arguments passed to the task.

    Returns:
        A formatted log message string.
    """
    sanitized_args = sanitize_value(list(args)) if args else []
    sanitized_kwargs = sanitize_value(dict(kwargs)) if kwargs else {}

    return (
        f"CeleryController.signals: Task retry scheduled\n"
        f"  Task: {task_name}\n"
        f"  Task ID: {task_id}\n"
        f"  Reason: {reason}\n"
        f"  Args: {sanitized_args}\n"
        f"  Kwargs: {sanitized_kwargs}"
    )


def _format_task_success_log(
    task_name: str,
    task_id: str,
    result: Any,
) -> str:
    """
    Format a task success log message.

    Args:
        task_name: The name of the successful task.
        task_id: The Celery task ID.
        result: The result returned by the task (will be sanitized).

    Returns:
        A formatted log message string.
    """
    sanitized_result = sanitize_value(result) if result is not None else None

    return (
        f"CeleryController.signals: Task completed successfully\n"
        f"  Task: {task_name}\n"
        f"  Task ID: {task_id}\n"
        f"  Result: {sanitized_result}"
    )


def _format_task_prerun_log(
    task_name: str,
    task_id: str,
    args: tuple | None,
    kwargs: dict | None,
) -> str:
    """
    Format a task pre-run log message.

    Args:
        task_name: The name of the task about to run.
        task_id: The Celery task ID.
        args: The positional arguments passed to the task.
        kwargs: The keyword arguments passed to the task.

    Returns:
        A formatted log message string.
    """
    sanitized_args = sanitize_value(list(args)) if args else []
    sanitized_kwargs = sanitize_value(dict(kwargs)) if kwargs else {}

    return (
        f"CeleryController.signals: Task starting execution\n"
        f"  Task: {task_name}\n"
        f"  Task ID: {task_id}\n"
        f"  Args: {sanitized_args}\n"
        f"  Kwargs: {sanitized_kwargs}"
    )


@task_failure.connect
def task_failure_handler(
    sender: Any = None,
    task_id: str = None,
    exception: Exception = None,
    args: tuple = None,
    kwargs: dict = None,
    traceback: Any = None,
    einfo: Any = None,
    **kw: Any,
) -> None:
    """
    Handle task failure signals and log detailed error information.

    This handler is automatically called when a Celery task fails. It logs
    comprehensive information about the failure including the task name,
    ID, sanitized arguments, exception details, and full traceback.

    Args:
        sender: The task class that sent the signal.
        task_id: The unique ID of the failed task.
        exception: The exception that caused the failure.
        args: Positional arguments passed to the task.
        kwargs: Keyword arguments passed to the task.
        traceback: The traceback object (not used, we format our own).
        einfo: Exception info object containing exc_info.
        **kw: Additional keyword arguments for forward compatibility.
    """
    try:
        task_name = getattr(sender, 'name', str(sender)) if sender else 'unknown'
        task_id = task_id or 'N/A'

        # Format the traceback from einfo if available
        if einfo is not None:
            tb = str(einfo)
        else:
            tb = 'No traceback available'

        log_message = _format_task_failure_log(
            task_name=task_name,
            task_id=task_id,
            args=args,
            kwargs=kwargs,
            exception=exception or Exception('Unknown error'),
            tb=tb,
        )

        logger.error(log_message)

    except Exception as e:
        # Signal handlers must never raise exceptions
        logger.error(
            f"CeleryController.signals: Error in task_failure_handler: {e}"
        )


@task_retry.connect
def task_retry_handler(
    sender: Any = None,
    reason: Any = None,
    request: Any = None,
    einfo: Any = None,
    **kw: Any,
) -> None:
    """
    Handle task retry signals and log retry information.

    This handler is automatically called when a Celery task is scheduled
    for retry. It logs the task name, ID, retry reason, and sanitized
    arguments.

    Args:
        sender: The task class that sent the signal.
        reason: The reason for the retry (usually an exception).
        request: The task request object containing task context.
        einfo: Exception info object.
        **kw: Additional keyword arguments for forward compatibility.
    """
    try:
        task_name = getattr(sender, 'name', str(sender)) if sender else 'unknown'

        # Extract task ID and arguments from request
        task_id = getattr(request, 'id', 'N/A') if request else 'N/A'
        args = getattr(request, 'args', None) if request else None
        kwargs = getattr(request, 'kwargs', None) if request else None

        # Convert reason to string
        reason_str = str(reason) if reason else 'Unknown reason'

        log_message = _format_task_retry_log(
            task_name=task_name,
            task_id=task_id,
            reason=reason_str,
            args=args,
            kwargs=kwargs,
        )

        logger.warning(log_message)

    except Exception as e:
        # Signal handlers must never raise exceptions
        logger.error(
            f"CeleryController.signals: Error in task_retry_handler: {e}"
        )


@task_success.connect
def task_success_handler(
    sender: Any = None,
    result: Any = None,
    **kw: Any,
) -> None:
    """
    Handle task success signals and optionally log completion information.

    This handler is only active when CELERY_ENABLE_SUCCESS_LOGGING is True
    in Django settings. When enabled, it logs the task name, ID, and
    sanitized result.

    Args:
        sender: The task class that sent the signal.
        result: The return value of the task.
        **kw: Additional keyword arguments for forward compatibility.
    """
    try:
        # Check if success logging is enabled
        if not _get_setting('CELERY_ENABLE_SUCCESS_LOGGING', False):
            return

        task_name = getattr(sender, 'name', str(sender)) if sender else 'unknown'

        # Get task ID from the request context if available
        request = getattr(sender, 'request', None)
        task_id = getattr(request, 'id', 'N/A') if request else 'N/A'

        log_message = _format_task_success_log(
            task_name=task_name,
            task_id=task_id,
            result=result,
        )

        logger.info(log_message)

    except Exception as e:
        # Signal handlers must never raise exceptions
        logger.error(
            f"CeleryController.signals: Error in task_success_handler: {e}"
        )


@task_prerun.connect
def task_prerun_handler(
    sender: Any = None,
    task_id: str = None,
    task: Any = None,
    args: tuple = None,
    kwargs: dict = None,
    **kw: Any,
) -> None:
    """
    Handle task pre-run signals and optionally log execution start.

    This handler is only active when CELERY_ENABLE_PRERUN_LOGGING is True
    in Django settings. When enabled, it logs the task name, ID, and
    sanitized arguments before task execution begins.

    Args:
        sender: The task class that sent the signal.
        task_id: The unique ID of the task.
        task: The task instance.
        args: Positional arguments passed to the task.
        kwargs: Keyword arguments passed to the task.
        **kw: Additional keyword arguments for forward compatibility.
    """
    try:
        # Check if prerun logging is enabled
        if not _get_setting('CELERY_ENABLE_PRERUN_LOGGING', False):
            return

        task_name = getattr(sender, 'name', str(sender)) if sender else 'unknown'
        task_id = task_id or 'N/A'

        log_message = _format_task_prerun_log(
            task_name=task_name,
            task_id=task_id,
            args=args,
            kwargs=kwargs,
        )

        logger.debug(log_message)

    except Exception as e:
        # Signal handlers must never raise exceptions
        logger.error(
            f"CeleryController.signals: Error in task_prerun_handler: {e}"
        )


def setup_celery_logging() -> None:
    """
    Initialize Celery signal handlers for centralized logging.

    Call this function from api/celery.py after the Celery app has been
    initialized. The signal handlers are automatically connected via
    decorators when this module is imported, but this function ensures
    the module is properly imported and can perform additional setup
    if needed in the future.

    Example:
        # In api/celery.py:
        from celery import Celery

        app = Celery("machtms")
        app.config_from_object("django.conf:settings", namespace="CELERY")
        app.autodiscover_tasks()

        # Initialize signal handlers
        from machtms.core.celerycontroller import setup_celery_logging
        setup_celery_logging()

    Note:
        The following Django settings control optional logging behavior:
        - CELERY_ENABLE_SUCCESS_LOGGING (default: False): Log task successes
        - CELERY_ENABLE_PRERUN_LOGGING (default: False): Log task pre-run events
    """
    # Signal handlers are already connected via decorators when this module
    # is imported. This function ensures the module is loaded and provides
    # a clear entry point for initialization.

    # Log that signal handlers have been initialized
    logger.debug(
        "CeleryController.signals: Signal handlers initialized\n"
        f"  Success logging: {_get_setting('CELERY_ENABLE_SUCCESS_LOGGING', False)}\n"
        f"  Prerun logging: {_get_setting('CELERY_ENABLE_PRERUN_LOGGING', False)}"
    )
