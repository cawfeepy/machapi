# Synchronous vs. Asynchronous Processing: Two Ways to Eat a Stack of Pancakes

> You have 20 rate confirmations to process. Do you eat them one at a time, in order, carefully finishing each before starting the next? Or do you invite four friends to the table and divide the stack? Both approaches work. Both have trade-offs. The ratecon pipeline supports both.

**File:** `machtms/backend/RateConParser/tasks.py`

---

## The Two Modes at a Glance

| Aspect               | Mode A: Synchronous              | Mode B: Asynchronous                   |
|----------------------|---------------------------------|----------------------------------------|
| **Task**             | `process_session_sync`           | `process_session_async`                 |
| **Processing**       | One document at a time           | Multiple documents in parallel           |
| **Concurrency**      | None                             | Up to `max_workers` (default: 5)        |
| **Order**            | Guaranteed (creation order)      | Non-deterministic                        |
| **Complexity**       | Simple loop                      | Workers with row locking                 |
| **Best for**         | Small batches, debugging         | Large batches, production throughput     |
| **Risk of conflicts**| Zero                             | Handled by `SELECT FOR UPDATE SKIP LOCKED` |

---

## Mode A: Synchronous Processing (process_session_sync)

```python
@shared_task
def process_session_sync(session_id: int):
    session = ParsingSession.objects.get(pk=session_id)
    session.status = SessionStatus.PROCESSING
    session.save(update_fields=['status', 'updated_at'])

    pending_docs = session.documents.filter(
        status=DocumentStatus.PENDING
    ).order_by('created_at')

    for doc in pending_docs:
        process_single_document(doc.pk)

    session.recompute_status()
```

### How it works

This is the straightforward approach. It's a `for` loop:

```
Document 1: Download → Extract → Agent (structured output) → Save ✓
Document 2: Download → Extract → Agent (structured output) → Save ✓
Document 3: Download → Extract → Agent (structured output) → Save ✓
...
Document N: Download → Extract → Agent (structured output) → Save ✓
Session: recompute_status()
```

Each document is fully processed before the next one begins. Documents are processed in `created_at` order, so the order is deterministic and predictable.

### When should you use sync mode?

- **Small batches** (1-5 documents): The overhead of spinning up parallel workers isn't worth it
- **Debugging**: When something is going wrong, sequential processing makes it easy to identify which document caused the issue
- **Resource-constrained environments**: If your Celery workers are limited, sequential processing uses just one worker
- **Order matters**: If you need documents processed in a specific order (rare, but possible)

### What are the downsides?

**Speed.** Each `process_single_document` call involves an LLM API call that takes 10-30 seconds. For 20 documents, that's 200-600 seconds (3-10 minutes) of sequential waiting. The next document in line just sits there while the current one is being processed.

> **What if one document takes forever?** It blocks everything behind it. A single problematic PDF (huge file, complex layout, slow API response) holds up the entire batch. The user watches progress crawl.

---

## Mode B: Asynchronous Processing (process_session_async)

```python
@shared_task
def process_session_async(session_id: int, max_workers: int = 5):
    session = ParsingSession.objects.get(pk=session_id)
    session.status = SessionStatus.PROCESSING
    session.save(update_fields=['status', 'updated_at'])

    pending_count = session.documents.filter(status=DocumentStatus.PENDING).count()
    worker_count = min(pending_count, max_workers)

    if worker_count > 0:
        job = group(
            process_document_worker.s(session_id) for _ in range(worker_count)
        )
        job.apply_async()
```

### How it works

Instead of one loop, this mode spawns multiple **worker tasks** that process documents in parallel:

```
Worker 1: Doc 1 → Doc 6 → Doc 11 → ...
Worker 2: Doc 2 → Doc 7 → Doc 12 → ...
Worker 3: Doc 3 → Doc 8 → Doc 13 → ...
Worker 4: Doc 4 → Doc 9 → Doc 14 → ...
Worker 5: Doc 5 → Doc 10 → Doc 15 → ...
```

(The exact assignment depends on which worker finishes first and grabs the next available document.)

### The worker count calculation

```python
worker_count = min(pending_count, max_workers)
```

If you have 3 pending documents and `max_workers=5`, you get 3 workers. No point having 2 idle workers. If you have 50 documents and `max_workers=5`, you get 5 workers. More workers means more concurrent LLM API calls and more resource usage.

> **Why default to 5?** It's a balance between throughput and resource consumption. LLM API calls are the bottleneck, and most API providers have rate limits. 5 concurrent calls is aggressive enough to be fast, conservative enough to avoid hitting rate limits or overwhelming the Celery broker.

### Celery group

```python
job = group(
    process_document_worker.s(session_id) for _ in range(worker_count)
)
job.apply_async()
```

Celery's `group` primitive dispatches multiple tasks in parallel. Each task is a `process_document_worker` instance with the same `session_id`. They all start roughly at the same time and race to claim documents.

---

## The Worker: process_document_worker

This is where the concurrency really happens.

```python
@shared_task
def process_document_worker(session_id: int):
    session = ParsingSession.objects.get(pk=session_id)

    while True:
        with transaction.atomic():
            doc = (
                RateConDocument.objects
                .select_for_update(skip_locked=True)
                .filter(session=session, status=DocumentStatus.PENDING)
                .first()
            )
            if doc is None:
                break
            doc.status = DocumentStatus.PROCESSING
            doc.save(update_fields=['status', 'updated_at'])

        process_single_document(doc.pk)

    session.recompute_status()
```

### The Claim-and-Process Loop

Each worker runs an infinite loop:

1. **Claim**: Inside a database transaction, grab the next available PENDING document
2. **Process**: Outside the transaction, process it fully
3. **Repeat**: Go back to step 1
4. **Stop**: When there are no more PENDING documents, break and exit

> **Why a loop instead of one document per worker?** Efficiency. If Worker 1 finishes its document in 10 seconds but Worker 3 takes 30 seconds, Worker 1 can immediately grab another document rather than sitting idle. The work naturally redistributes to whichever workers are fastest.

### SELECT FOR UPDATE SKIP LOCKED -- The Secret Sauce

```python
doc = (
    RateConDocument.objects
    .select_for_update(skip_locked=True)
    .filter(session=session, status=DocumentStatus.PENDING)
    .first()
)
```

This is a PostgreSQL feature that solves the fundamental problem of parallel processing: **how do you prevent two workers from grabbing the same document?**

Here's what happens at the database level:

```sql
SELECT * FROM ratecon_document
WHERE session_id = 42 AND status = 'pending'
ORDER BY id
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

**`FOR UPDATE`**: Locks the selected row. No other transaction can modify or lock it until this transaction commits.

**`SKIP LOCKED`**: If a row is already locked by another transaction, skip it and move to the next one. Don't wait, don't block, just skip.

> **What if two workers grabbed the same document?** Without `SKIP LOCKED`, Worker B would have two options when it encounters a locked row: wait (which defeats the purpose of parallelism) or fail (which is wasteful). With `SKIP LOCKED`, Worker B simply skips to the next unlocked row. It's like a buffet line where you skip the dish someone else is serving themselves from and grab the next one.

> **What if there are no unlocked rows?** `first()` returns `None`, the `if doc is None: break` kicks in, and the worker exits gracefully. No errors, no retries, just done.

### Why Process Outside the Transaction?

```python
with transaction.atomic():
    doc = ...  # Claim (milliseconds)
    doc.status = DocumentStatus.PROCESSING
    doc.save(...)

# Transaction is committed here. Lock is released.

process_single_document(doc.pk)  # Process (10-30 seconds)
```

The transaction scope is deliberately small. It only covers the claim operation (a quick SELECT + UPDATE). The actual processing -- which involves downloading from S3, calling an LLM API, and creating database records -- happens outside the transaction.

> **What if we kept the transaction open during processing?** Disaster. A transaction holding a row lock for 30 seconds would:
> - Block other queries that touch that row
> - Risk database connection pool exhaustion
> - Risk transaction timeout errors
> - Potentially cause deadlocks with other operations
>
> By committing the transaction immediately after claiming, the lock is released and the row is visible to other queries with its new `PROCESSING` status.

---

## The Double-Processing Guard

Even with `SKIP LOCKED`, there's one more safety net in `process_single_document`:

```python
def process_single_document(document_id: int):
    doc = RateConDocument.objects.select_related(...).get(pk=document_id)

    # Guard against double-processing
    if doc.status not in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
        return
```

> **What does this guard solve?** Edge cases. What if a document was already processed by the time the function runs? What if a race condition slipped through? What if someone manually changed the status? This guard is the last line of defense -- if the document isn't in a processable state, bail out immediately.

This is a belt-and-suspenders approach. `SKIP LOCKED` prevents double-claiming at the database level. The status guard prevents double-processing at the application level. Together, they make accidental double-processing virtually impossible.

---

## Session Status Recomputation

After processing completes (whether sync or async), the session recalculates its status:

```python
def recompute_status(self):
    docs = self.documents.all()
    if not docs.exists():
        return
    statuses = set(docs.values_list('status', flat=True))
    terminal = {
        DocumentStatus.PARSED,
        DocumentStatus.MISCLASSIFIED,
        DocumentStatus.FAILED,
    }
    if statuses <= terminal:
        if statuses == {DocumentStatus.PARSED} or statuses <= {
            DocumentStatus.PARSED,
            DocumentStatus.MISCLASSIFIED,
        }:
            self.status = SessionStatus.COMPLETED
        elif DocumentStatus.PARSED in statuses or DocumentStatus.MISCLASSIFIED in statuses:
            self.status = SessionStatus.PARTIALLY_FAILED
        else:
            self.status = SessionStatus.FAILED
        self.save(update_fields=['status', 'updated_at'])
```

### The Decision Tree

The logic only fires when ALL documents are in a terminal state (parsed, misclassified, or failed). If any document is still pending or processing, the session stays in `PROCESSING`.

```
All documents terminal?
├── No → stay in PROCESSING (wait for them to finish)
└── Yes → evaluate:
    ├── All PARSED (or PARSED + MISCLASSIFIED) → COMPLETED
    ├── Mix of PARSED/MISCLASSIFIED and FAILED → PARTIALLY_FAILED
    └── All FAILED → FAILED
```

> **Why is MISCLASSIFIED treated as a success?** Because the system did its job correctly. It identified the document as not being a rate confirmation. That's not a failure -- that's accurate classification. A MISCLASSIFIED document just means the user uploaded the wrong file.

### When does recomputation happen?

Three places:

1. **`process_single_document`**: Called in the `finally` block, so it runs after every document regardless of success or failure
2. **`process_document_worker`**: Called after the worker's loop ends (all documents claimed)
3. **`cleanup_stale_uploads`**: Called for every session that had stale documents cleaned up

---

## Choosing Between Modes: A Decision Guide

```
How many documents?
├── 1-3 → Use sync (process_session_sync)
|         Simple, fast enough, easy to debug
|
├── 4-20 → Either works, lean toward async
|          Async will be noticeably faster
|
└── 20+ → Use async (process_session_async)
          Sequential processing will be painfully slow
          5 workers = ~5x throughput
```

```
Need predictable ordering?
├── Yes → Use sync
└── No → Use async (documents complete in whatever order)
```

```
Debugging an issue?
├── Yes → Use sync (easier to follow one document at a time)
└── No → Use async for throughput
```

---

## The Cleanup Safety Net

One more piece of the puzzle: what about documents that never make it past `UPLOADING`?

```python
@shared_task
def cleanup_stale_uploads():
    cutoff = timezone.now() - timedelta(hours=1)
    stale_qs = RateConDocument.objects.filter(
        status=DocumentStatus.UPLOADING,
        created_at__lt=cutoff,
    )
    session_ids = set(stale_qs.values_list('session_id', flat=True))
    count = stale_qs.update(
        status=DocumentStatus.FAILED,
        error_message='Upload timed out.',
    )
    for sid in session_ids:
        try:
            session = ParsingSession.objects.get(pk=sid)
            session.recompute_status()
        except ParsingSession.DoesNotExist:
            pass
```

This periodic task (designed for Celery Beat) handles the scenario where an upload starts but never completes. After 1 hour, the document is marked as FAILED and the session status is recomputed.

> **What if we didn't have cleanup?** Sessions with abandoned uploads would be stuck in `UPLOADING` or `PROCESSING` forever. The progress indicator would never reach 100%. Users would see phantom "in progress" sessions that are actually dead. The cleanup task is the janitor that keeps the house clean.

---

## Summary: The Safety Layers

The system uses multiple overlapping safety mechanisms to prevent data corruption:

| Layer                         | What It Prevents                     | Where It Lives                   |
|------------------------------|--------------------------------------|----------------------------------|
| `select_for_update(skip_locked)` | Two workers claiming same document | `process_document_worker`        |
| Status guard                  | Processing a non-processable doc    | `process_single_document`        |
| Try/except on load creation   | Load failure affecting parse status | `process_single_document`        |
| `recompute_status()`          | Session status drift                | Called in `finally`, workers, cleanup |
| `cleanup_stale_uploads()`     | Ghost uploads stuck forever         | Periodic Celery Beat task         |
| Error message truncation      | DB bloat from huge tracebacks       | `str(e)[:500]`                   |

Each layer addresses a different failure mode. Together, they create a resilient pipeline that degrades gracefully rather than catastrophically.
