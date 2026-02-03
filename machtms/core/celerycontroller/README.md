# CeleryController

A centralized orchestration layer for Celery task execution in machTMS.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Usage Patterns](#usage-patterns)
4. [View Integration Examples](#view-integration-examples)
5. [Migration Guide](#migration-guide)
6. [Exception Handling](#exception-handling)
7. [Execution-Time Error Handling](#execution-time-error-handling)
8. [Logging Configuration](#logging-configuration)
9. [API Reference](#api-reference)
10. [Best Practices](#best-practices)

---

## Overview

### Purpose

CeleryController provides a unified interface for executing Celery tasks throughout the machTMS application. Instead of calling tasks directly with `.delay()` or `.apply_async()`, all task invocations flow through this controller, which acts as a single orchestration point.

### Benefits

| Benefit | Description |
|---------|-------------|
| **Centralized Exception Handling** | All task execution errors are caught, logged with full context, and re-raised consistently. No more scattered try/except blocks. |
| **Single Orchestration Point** | One location to add cross-cutting concerns like metrics, rate limiting, or task filtering. |
| **Better Logging** | Automatic structured logging with task name, arguments, and full exception details. |
| **Cleaner Views** | Eliminates repetitive try/except patterns in views and serializers. |
| **Testability** | Easy to mock for unit testing without Celery infrastructure. |

### The Problem It Solves

Without CeleryController, task execution often looks like this throughout the codebase:

```python
# Repetitive pattern in every view
try:
    result = send_notification_task.delay(user_id, message)
except Exception as e:
    logger.error(f"Failed to queue notification: {e}")
    raise

# Same pattern repeated elsewhere
try:
    result = process_document_task.delay(document_id)
except Exception as e:
    logger.error(f"Failed to queue document processing: {e}")
    raise
```

This leads to:
- Inconsistent error handling across the codebase
- Duplicated logging logic
- Difficulty adding global task execution policies
- Verbose view code

---

## Quick Start

### Basic Import

```python
from machtms.core.celerycontroller import controller
```

### Minimal Example

```python
from machtms.core.celerycontroller import controller
from .tasks import send_email_task

# In your view or service:
async_result = controller.delay(send_email_task, user_id, email_body)
```

That is all you need. The controller handles logging and exception management automatically.

---

## Usage Patterns

### Basic delay() Usage

The `delay()` method is the most common way to execute tasks asynchronously.

```python
from machtms.core.celerycontroller import controller
from .tasks import send_email_task, generate_report_task

# Pattern 1: Direct task reference (recommended)
# Pass the task and its arguments separately
controller.delay(send_email_task, user_id, email_body)

# Pattern 2: With keyword arguments
controller.delay(send_email_task, user_id, subject="Welcome", body=email_body)

# Pattern 3: Lambda wrapper (use sparingly)
# Useful when you need to defer argument evaluation
controller.delay(lambda: send_email_task.delay(user_id, email_body))
```

### apply_async() with Options

The `apply_async()` method provides full control over task execution options.

```python
from datetime import datetime, timedelta
from machtms.core.celerycontroller import controller
from .tasks import send_email_task, generate_report, sync_data

# Delayed execution (60 seconds from now)
controller.apply_async(
    send_email_task,
    args=[user_id, email_body],
    countdown=60
)

# Scheduled execution at a specific time
controller.apply_async(
    generate_report,
    args=[org_id],
    eta=datetime(2024, 1, 1, 9, 0)
)

# With retry configuration
controller.apply_async(
    sync_data,
    args=[data_payload],
    retry=True,
    retry_policy={
        'max_retries': 3,
        'interval_start': 0,
        'interval_step': 0.2,
        'interval_max': 0.5,
    }
)

# Route to a specific queue
controller.apply_async(
    process_heavy_task,
    args=[large_dataset],
    queue='heavy_processing'
)

# With expiration (task will not run if not picked up in time)
controller.apply_async(
    time_sensitive_task,
    args=[data],
    expires=timedelta(minutes=30)
)
```

### Synchronous Execution with apply()

The `apply()` method executes tasks synchronously. Primarily useful for testing.

```python
from machtms.core.celerycontroller import controller
from .tasks import process_data_task

# Synchronous execution - blocks until complete
result = controller.apply(process_data_task, args=[data])

# Access the result directly
processed_data = result.get()
```

**Warning:** Avoid using `apply()` in production code paths as it blocks the request thread.

### Fire-and-Forget with safe_execute()

The `safe_execute()` method is designed for optional tasks where failure is acceptable.

```python
from machtms.core.celerycontroller import controller
from .tasks import send_analytics_event, update_cache

# Returns a tuple: (success: bool, result_or_error)
success, result = controller.safe_execute(
    send_analytics_event,
    user_id,
    event_type="page_view",
    suppress_exceptions=True
)

if not success:
    # Log but continue - analytics failure should not break the request
    # The error is already logged by the controller
    pass

# Continue with main business logic
return Response({"status": "ok"})
```

Use `safe_execute()` when:
- The task is for analytics, logging, or other non-critical operations
- Task failure should not affect the main request flow
- You want explicit success/failure feedback without exceptions

---

## View Integration Examples

### APIView Class

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from machtms.core.celerycontroller import controller
from .tasks import process_document, send_notification
from .models import Document

class DocumentUploadView(APIView):
    """
    Handle document uploads with async processing.
    """

    def post(self, request):
        # Save the document
        document = Document.objects.create(
            file=request.FILES['file'],
            uploaded_by=request.user
        )

        # Queue async processing - no try/except needed
        async_result = controller.delay(process_document, document.id)

        # Optionally notify the user (fire-and-forget)
        controller.safe_execute(
            send_notification,
            request.user.id,
            message="Your document is being processed",
            suppress_exceptions=True
        )

        return Response(
            {
                'document_id': document.id,
                'task_id': async_result.id,
                'status': 'processing'
            },
            status=status.HTTP_202_ACCEPTED
        )
```

### ModelViewSet

```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from machtms.core.celerycontroller import controller
from .models import Order
from .serializers import OrderSerializer
from .tasks import process_order, generate_invoice, notify_warehouse

class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Order management with async task integration.
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def perform_create(self, serializer):
        order = serializer.save()
        # Queue order processing
        controller.delay(process_order, order.id)

    @action(detail=True, methods=['post'])
    def finalize(self, request, pk=None):
        order = self.get_object()
        order.status = 'finalized'
        order.save()

        # Queue multiple related tasks
        controller.delay(generate_invoice, order.id)
        controller.apply_async(
            notify_warehouse,
            args=[order.id],
            countdown=5  # Small delay to ensure DB commit
        )

        return Response({'status': 'order finalized'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()

        # Schedule cancellation processing
        controller.apply_async(
            process_cancellation,
            args=[order.id],
            kwargs={'reason': request.data.get('reason', 'User requested')}
        )

        return Response({'status': 'cancellation initiated'})
```

### Function-Based View with @api_view

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from machtms.core.celerycontroller import controller
from .tasks import sync_external_data, send_confirmation_email

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_data_sync(request):
    """
    Trigger an external data synchronization.
    """
    org_id = request.user.organization_id
    sync_type = request.data.get('sync_type', 'full')

    # Queue the sync task with options
    async_result = controller.apply_async(
        sync_external_data,
        args=[org_id],
        kwargs={'sync_type': sync_type},
        queue='data_sync'
    )

    # Send confirmation (non-critical)
    controller.safe_execute(
        send_confirmation_email,
        request.user.email,
        subject="Data sync initiated",
        suppress_exceptions=True
    )

    return Response({
        'task_id': async_result.id,
        'message': f'{sync_type} sync initiated'
    })
```

---

## Migration Guide

### Before: Repetitive try/except Pattern

```python
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from .tasks import send_email_task, process_data_task, update_cache_task

logger = logging.getLogger(__name__)

class MyView(APIView):
    def post(self, request):
        # Repetitive error handling for each task
        try:
            email_result = send_email_task.delay(
                request.user.id,
                request.data['message']
            )
        except Exception as e:
            logger.error(f"Failed to queue email task: {e}")
            raise

        try:
            process_result = process_data_task.delay(
                request.data['payload']
            )
        except Exception as e:
            logger.error(f"Failed to queue processing task: {e}")
            raise

        try:
            cache_result = update_cache_task.delay(
                request.user.organization_id
            )
        except Exception as e:
            # Sometimes we just log and continue
            logger.warning(f"Cache update failed: {e}")

        return Response({'status': 'ok'})
```

### After: Clean, Centralized Approach

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from machtms.core.celerycontroller import controller
from .tasks import send_email_task, process_data_task, update_cache_task

class MyView(APIView):
    def post(self, request):
        # Clean task execution - controller handles logging
        email_result = controller.delay(
            send_email_task,
            request.user.id,
            request.data['message']
        )

        process_result = controller.delay(
            process_data_task,
            request.data['payload']
        )

        # For optional tasks, use safe_execute
        controller.safe_execute(
            update_cache_task,
            request.user.organization_id,
            suppress_exceptions=True
        )

        return Response({'status': 'ok'})
```

### Migration Checklist

1. **Import the controller**
   ```python
   from machtms.core.celerycontroller import controller
   ```

2. **Replace direct `.delay()` calls**
   ```python
   # Before
   my_task.delay(arg1, arg2)

   # After
   controller.delay(my_task, arg1, arg2)
   ```

3. **Replace `.apply_async()` calls**
   ```python
   # Before
   my_task.apply_async(args=[arg1], countdown=60)

   # After
   controller.apply_async(my_task, args=[arg1], countdown=60)
   ```

4. **Remove try/except blocks** around task calls (unless you need custom handling)

5. **Convert optional tasks** to use `safe_execute()`
   ```python
   # Before
   try:
       optional_task.delay(arg1)
   except Exception:
       pass  # Swallow error

   # After
   controller.safe_execute(optional_task, arg1, suppress_exceptions=True)
   ```

---

## Exception Handling

### How It Works

The CeleryController catches all exceptions during task dispatch, logs them with full context, and re-raises them. This ensures:

1. **Consistent Logging**: Every failure is logged with the same format
2. **Preserved Behavior**: Exceptions bubble up normally for Celery retry mechanisms
3. **Full Context**: Task name, arguments, and stack trace are captured

### Exception Flow

```
View calls controller.delay(task, args)
    |
    v
Controller attempts task.delay(*args)
    |
    +-- Success --> Returns AsyncResult
    |
    +-- Exception caught
            |
            v
        Log error with context:
        - Task name
        - Arguments (sanitized)
        - Full exception details
            |
            v
        Re-raise exception
            |
            v
        Exception propagates to view
```

### Example Log Output

When an exception occurs, the controller logs structured information:

```
ERROR machtms.core.celerycontroller [2024-01-15 10:23:45,123]
Task execution failed
Task: myapp.tasks.send_email_task
Args: (42, 'user@example.com')
Kwargs: {'subject': 'Welcome'}
Exception: ConnectionError: Unable to connect to broker
Traceback (most recent call last):
  File "/app/machtms/core/celerycontroller/controller.py", line 45, in delay
    return task.delay(*args, **kwargs)
  File "/app/.venv/lib/python3.11/site-packages/celery/app/task.py", line 425, in delay
    return self.apply_async(args, kwargs)
  ...
ConnectionError: Unable to connect to broker
```

### Handling Exceptions in Views

Since exceptions are re-raised, you can still catch them when needed:

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from machtms.core.celerycontroller import controller
from machtms.core.celerycontroller.exceptions import TaskDispatchError
from .tasks import critical_task

class MyView(APIView):
    def post(self, request):
        try:
            controller.delay(critical_task, request.data)
        except TaskDispatchError:
            # Custom handling for this specific view
            return Response(
                {'error': 'Service temporarily unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        return Response({'status': 'queued'})
```

---

## Execution-Time Error Handling

### Dispatch-Time vs Execution-Time Errors

CeleryController handles two distinct categories of errors:

| Error Type | When It Occurs | Handled By | Example |
|------------|----------------|------------|---------|
| **Dispatch-Time** | When queuing the task (before worker picks it up) | Controller's try/except in `delay()`/`apply_async()` | Broker connection failure, serialization error |
| **Execution-Time** | When the worker runs the task | Celery signals (`task_failure`, `task_retry`) | Task code raises exception, database timeout |

**Dispatch-time errors** occur immediately when you call `controller.delay()`. These are caught by the controller's exception handling and logged before re-raising.

**Execution-time errors** occur later, when a Celery worker actually executes the task. By the time these happen, your view has already returned a response. These errors are captured through Celery signals.

### How Celery Signals Capture Execution-Time Errors

CeleryController registers signal handlers to capture task execution events:

```python
# Signals registered by CeleryController
from celery.signals import task_failure, task_retry, task_success, task_prerun

@task_failure.connect
def handle_task_failure(sender, task_id, exception, traceback, **kwargs):
    """Logs when a task fails during execution."""
    logger.error(
        f"Task {sender.name}[{task_id}] failed: {exception}",
        exc_info=(type(exception), exception, traceback)
    )

@task_retry.connect
def handle_task_retry(sender, task_id, reason, **kwargs):
    """Logs when a task is being retried."""
    logger.warning(f"Task {sender.name}[{task_id}] retrying: {reason}")
```

These signals fire automatically when tasks fail or retry, regardless of how the task was queued.

### Log File Location

Execution-time errors are written to:

```
machtms/logs/celery_logs.txt
```

This file uses `RotatingFileHandler` with:
- **Max size:** 10 MB per file
- **Backup count:** 5 files (total ~50 MB max)
- **Log level:** ERROR

### Configuration Settings

Control signal logging behavior in your Django settings:

```python
# settings/components/celery.py

# Log successful task completions (default: False)
# Enable for debugging or audit trails
CELERY_ENABLE_SUCCESS_LOGGING = False

# Log before task execution starts (default: False)
# Enable to trace task execution flow
CELERY_ENABLE_PRERUN_LOGGING = False
```

| Setting | Default | When to Enable |
|---------|---------|----------------|
| `CELERY_ENABLE_SUCCESS_LOGGING` | `False` | Debugging, audit trails, monitoring task completion rates |
| `CELERY_ENABLE_PRERUN_LOGGING` | `False` | Tracing execution flow, debugging task pickup delays |

**Note:** Keep these disabled in production unless actively debugging, as they can generate significant log volume.

### Example Log Output Format

**Task Failure (Execution-Time Error):**
```
ERROR machtms.core.celerycontroller.signals [2024-01-15 14:32:18,456]
Task execution failed
Task: myapp.tasks.process_document
Task ID: 8f4e2a1b-9c3d-4e5f-a6b7-c8d9e0f1a2b3
Exception: ValueError: Document not found with ID 12345
Traceback (most recent call last):
  File "/app/.venv/lib/python3.11/site-packages/celery/app/trace.py", line 477, in trace_task
    R = retval = fun(*args, **kwargs)
  File "/app/myapp/tasks.py", line 42, in process_document
    document = Document.objects.get(pk=document_id)
  File "/app/.venv/lib/python3.11/site-packages/django/db/models/manager.py", line 87, in manager_method
    return getattr(self.get_queryset(), name)(*args, **kwargs)
  ...
ValueError: Document not found with ID 12345
```

**Task Retry:**
```
WARNING machtms.core.celerycontroller.signals [2024-01-15 14:32:19,789]
Task retry scheduled
Task: myapp.tasks.sync_external_api
Task ID: 1a2b3c4d-5e6f-7a8b-9c0d-e1f2a3b4c5d6
Reason: ConnectionError: API timeout after 30s
Retry: 2 of 3
ETA: 2024-01-15 14:33:19 UTC
```

**Task Success (when CELERY_ENABLE_SUCCESS_LOGGING=True):**
```
INFO machtms.core.celerycontroller.signals [2024-01-15 14:32:20,123]
Task completed successfully
Task: myapp.tasks.send_email
Task ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
Runtime: 1.234s
Result: {'status': 'sent', 'recipient': 'user@example.com'}
```

**Task Prerun (when CELERY_ENABLE_PRERUN_LOGGING=True):**
```
INFO machtms.core.celerycontroller.signals [2024-01-15 14:32:17,001]
Task starting execution
Task: myapp.tasks.process_document
Task ID: 8f4e2a1b-9c3d-4e5f-a6b7-c8d9e0f1a2b3
Args: (12345,)
Kwargs: {'priority': 'high'}
```

---

## Logging Configuration

### Django Settings Configuration

Add the CeleryController logger to your Django `LOGGING` configuration:

```python
# settings.py or settings/components/logging.py

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {name} [{asctime}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/celery_controller.log',
            'maxBytes': 10485760,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'machtms.core.celerycontroller': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
```

### Log Level Recommendations

| Environment | Recommended Level | Rationale |
|-------------|-------------------|-----------|
| Development | `DEBUG` | See all task dispatch activity |
| Staging | `INFO` | Monitor task flow without noise |
| Production | `ERROR` | Only capture failures |

### Structured Logging with JSON

For production environments using log aggregation:

```python
LOGGING = {
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
        },
    },
    'handlers': {
        'json_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/celery_controller.json',
            'formatter': 'json',
        },
    },
    'loggers': {
        'machtms.core.celerycontroller': {
            'handlers': ['json_file'],
            'level': 'ERROR',
        },
    },
}
```

---

## API Reference

### Methods

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `delay` | `delay(task, *args, **kwargs)` | `AsyncResult` | Execute task asynchronously with positional and keyword arguments |
| `apply_async` | `apply_async(task, args=None, kwargs=None, **options)` | `AsyncResult` | Execute task asynchronously with full Celery options |
| `apply` | `apply(task, args=None, kwargs=None)` | `EagerResult` | Execute task synchronously (blocking) |
| `safe_execute` | `safe_execute(task, *args, suppress_exceptions=False, **kwargs)` | `tuple[bool, Any]` | Execute with optional exception suppression |

### Method Details

#### delay(task, *args, **kwargs)

Execute a Celery task asynchronously.

**Parameters:**
- `task`: The Celery task to execute
- `*args`: Positional arguments to pass to the task
- `**kwargs`: Keyword arguments to pass to the task

**Returns:** `AsyncResult` - Celery async result object

**Raises:** Re-raises any exception from task dispatch

```python
result = controller.delay(my_task, arg1, arg2, keyword=value)
task_id = result.id
```

#### apply_async(task, args=None, kwargs=None, **options)

Execute a Celery task with full async options.

**Parameters:**
- `task`: The Celery task to execute
- `args`: List/tuple of positional arguments (default: None)
- `kwargs`: Dictionary of keyword arguments (default: None)
- `**options`: Celery apply_async options (countdown, eta, queue, etc.)

**Common Options:**
| Option | Type | Description |
|--------|------|-------------|
| `countdown` | `int` | Seconds to wait before executing |
| `eta` | `datetime` | Absolute time to execute |
| `queue` | `str` | Queue name to route task to |
| `expires` | `int/datetime/timedelta` | Task expiration |
| `retry` | `bool` | Whether to retry on failure |
| `retry_policy` | `dict` | Retry configuration |

**Returns:** `AsyncResult`

```python
result = controller.apply_async(
    my_task,
    args=[arg1, arg2],
    kwargs={'key': 'value'},
    countdown=60,
    queue='priority'
)
```

#### apply(task, args=None, kwargs=None)

Execute a Celery task synchronously.

**Parameters:**
- `task`: The Celery task to execute
- `args`: List/tuple of positional arguments (default: None)
- `kwargs`: Dictionary of keyword arguments (default: None)

**Returns:** `EagerResult` - Result object with immediate access to return value

**Note:** Blocks the current thread. Use for testing only.

```python
result = controller.apply(my_task, args=[arg1])
value = result.get()
```

#### safe_execute(task, *args, suppress_exceptions=False, **kwargs)

Execute a task with controlled exception handling.

**Parameters:**
- `task`: The Celery task to execute
- `*args`: Positional arguments to pass to the task
- `suppress_exceptions`: If True, exceptions are caught and returned (default: False)
- `**kwargs`: Keyword arguments to pass to the task

**Returns:** `tuple[bool, Any]`
- `(True, AsyncResult)` on success
- `(False, Exception)` on failure (when suppress_exceptions=True)

**Raises:** Exception if suppress_exceptions=False and task dispatch fails

```python
success, result = controller.safe_execute(
    optional_task,
    arg1,
    suppress_exceptions=True
)
if success:
    print(f"Task queued: {result.id}")
else:
    print(f"Task failed: {result}")  # result is the exception
```

---

## Best Practices

### When to Use Each Method

| Scenario | Method | Example |
|----------|--------|---------|
| Standard async execution | `delay()` | Processing uploads, sending emails |
| Need execution options | `apply_async()` | Scheduled tasks, specific queues |
| Testing without Celery | `apply()` | Unit tests, debugging |
| Optional/non-critical tasks | `safe_execute()` | Analytics, cache warming |

### Prefer Direct Task Reference

```python
# Preferred: Direct reference
controller.delay(my_task, arg1, arg2)

# Avoid: Lambda wrapper (harder to debug, inspect)
controller.delay(lambda: my_task.delay(arg1, arg2))
```

Use lambda wrappers only when you need to defer argument evaluation.

### Avoid in Time-Critical Paths

The controller adds minimal overhead (logging, exception handling). For extremely time-sensitive code paths where microseconds matter, consider direct task calls:

```python
# For 99% of cases, use the controller
controller.delay(my_task, arg)

# For rare, ultra-time-critical paths (measure first!)
my_task.delay(arg)
```

### Batch Related Tasks

When queuing multiple related tasks, consider task grouping:

```python
from celery import group
from machtms.core.celerycontroller import controller

# Good: Related tasks as a group
task_group = group([
    process_item.s(item_id) for item_id in item_ids
])
controller.delay(task_group)

# Also fine: Individual calls for unrelated tasks
controller.delay(send_email, user_id)
controller.delay(update_cache, cache_key)
```

### Use Appropriate Timeouts

For tasks with known execution bounds, set expiration:

```python
controller.apply_async(
    time_sensitive_task,
    args=[data],
    expires=300  # 5 minutes
)
```

### Testing Guidelines

In tests, you can mock the controller:

```python
from unittest.mock import patch, MagicMock
from machtms.core.celerycontroller import controller

class TestMyView:
    @patch.object(controller, 'delay')
    def test_task_is_queued(self, mock_delay):
        mock_delay.return_value = MagicMock(id='fake-task-id')

        response = self.client.post('/api/endpoint/', data={...})

        mock_delay.assert_called_once_with(
            expected_task,
            expected_arg1,
            expected_arg2
        )
```

Or use Celery's eager mode in test settings:

```python
# settings/test.py
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
```

---

## Troubleshooting

### Common Issues

**Task not executing:**
- Check Celery worker is running
- Verify task is registered (`celery -A api inspect registered`)
- Check queue routing configuration

**Exception not being logged:**
- Verify logging configuration includes the controller logger
- Check log level is appropriate for your environment

**safe_execute always returning (False, ...):**
- Check broker connectivity
- Verify task module is importable by workers

---

## Related Documentation

- [Celery Documentation](https://docs.celeryq.dev/)
- [Django Celery Integration](https://docs.celeryq.dev/en/stable/django/)
