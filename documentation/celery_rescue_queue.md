# Celery — Worker Fault Tolerance & Rescue Queue

## Overview

`process_document_worker` is configured with two layers of fault tolerance:

1. **Exception-based retry** — Celery automatically retries on unexpected errors
2. **Hard-kill protection** — tasks are re-queued if the worker process is killed before finishing

An optional **rescue queue** can be used to route retried tasks to dedicated workers, isolating retry traffic from the main processing queue.

---

## Task Configuration

```python
@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    task_reject_on_worker_lost=True,
)
def process_document_worker(self, session_id: int, use_raw_text: bool = True):
    try:
        ...
    except Exception as exc:
        raise self.retry(exc=exc)
```

| Option | Value | Purpose |
|---|---|---|
| `bind=True` | — | Gives the task access to `self` (the task instance) |
| `max_retries` | `3` | Retries up to 3 times before giving up and re-raising |
| `default_retry_delay` | `60` | Waits 60 seconds between retries |
| `acks_late=True` | — | Task is acknowledged **after** completion, not on receipt |
| `task_reject_on_worker_lost=True` | — | Re-queues the task if the worker process is hard-killed |

---

## What Each Layer Covers

### Exception-based retry (`max_retries` + `self.retry`)

Handles recoverable errors raised during the worker loop — e.g.:

- Database connection drops
- `ParsingSession.DoesNotExist` (transient DB lag)
- Unexpected runtime errors in the task scaffolding

`process_single_document` handles its own exceptions internally (sets `FAILED` status, logs). The retry mechanism catches errors that escape the task loop itself.

### Hard-kill protection (`acks_late` + `task_reject_on_worker_lost`)

By default, RabbitMQ marks a task as acknowledged the moment the worker receives it. If the worker process is killed (OOM, SIGKILL, container restart) before finishing, the task is lost.

With `acks_late=True`, the acknowledgement is deferred until the task completes. Combined with `task_reject_on_worker_lost=True`, an unacknowledged task is rejected back to the queue and re-dispatched to another worker.

---

## Known Edge Case

If the worker is hard-killed **mid-LLM-call** (inside `process_single_document`), the re-queued worker will restart the task from scratch. It claims `PENDING` documents only — so the document that was in `PROCESSING` when the kill happened will remain stuck in that state.

In this case, a manual re-trigger via `POST /ratecon/sessions/<id>/process/` is required. The view dispatches fresh workers which will pick up any remaining `PENDING` documents. The stuck `PROCESSING` document must be manually reset to `PENDING` via the Django admin or a management command before it can be retried.

---

## Rescue Queue (Optional)

To prevent retry storms from consuming capacity on the main processing queue, retried tasks can be routed to a dedicated `rescue` queue.

### Enable in the task

```python
except Exception as exc:
    raise self.retry(exc=exc, queue='rescue')
```

### Worker commands

```bash
# Main processing workers
celery -A api worker \
  --loglevel=warning \
  --concurrency=10 \
  --pool=threads \
  -Q celery \
  --hostname=main@%h

# Rescue workers (lower concurrency — handles stragglers only)
celery -A api worker \
  --loglevel=warning \
  --concurrency=2 \
  --pool=threads \
  -Q rescue \
  --hostname=rescue@%h
```

### When to use the rescue queue

| Scenario | Recommendation |
|---|---|
| Low/moderate document volume | Single queue is fine — retry traffic is negligible |
| High volume with frequent worker restarts | Add rescue queue to protect main throughput |
| Container environment with OOM kills | `acks_late` + rescue queue is strongly recommended |
| Stable, long-running workers | Exception retry alone is usually sufficient |

> If the rescue queue has no worker listening, retried tasks will queue indefinitely. Make sure the rescue worker is running before enabling this routing.
