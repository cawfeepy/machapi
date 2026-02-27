# Celery Worker — Production Configuration

## Basic Command

```bash
celery -A api worker --loglevel=info --concurrency=5 --pool=threads
```

- `-A api` — points to the Celery app defined in the `api` module
- `--concurrency=5` — spawns 5 worker threads to process tasks in parallel
- `--pool=threads` — uses thread-based concurrency (ideal for I/O-bound tasks like OpenAI API calls and S3 downloads)

## Why `threads` Pool

Rate con parsing is I/O-bound — each task spends most of its time waiting on:
- OpenAI API responses (~3-8s per document)
- S3 presigned URL generation and PDF downloads

The `threads` pool allows multiple tasks to wait on these external calls simultaneously without the memory overhead of separate OS processes (`prefork`).

## Pool Types

| Pool | Best For | Trade-offs |
|---|---|---|
| `threads` | I/O-bound work (API calls, network requests) | Lightweight, shares memory, subject to GIL for CPU work |
| `prefork` | CPU-bound work (image processing, computation) | Heavier memory usage, full process isolation |
| `solo` | Testing only | Single-threaded, no parallelism |

## Key Flags

| Flag | Purpose | Example |
|---|---|---|
| `--concurrency` | Number of parallel worker threads/processes | `5`, `10`, `20` |
| `--pool` | Execution pool strategy | `threads`, `prefork` |
| `-Q` | Queue(s) to consume from | `celery`, `celery,ratecon` |
| `--loglevel` | Log verbosity | `info`, `warning` |
| `--hostname` | Worker identity for monitoring | `worker1@%h` |
| `--max-tasks-per-child` | Restart after N tasks (prefork only, prevents memory leaks) | `100` |

## Example Configurations

### Standard Production

```bash
celery -A api worker \
  --loglevel=warning \
  --concurrency=5 \
  --pool=threads
```

### Higher Throughput

```bash
celery -A api worker \
  --loglevel=warning \
  --concurrency=10 \
  --pool=threads
```

### Dedicated Rate Con Parsing Queue

```bash
# Worker that only handles rate con tasks
celery -A api worker \
  --loglevel=warning \
  --concurrency=5 \
  --pool=threads \
  -Q ratecon_parsing \
  --hostname=ratecon@%h
```

### Multiple Workers with Different Roles

```bash
# General worker
celery -A api worker \
  --loglevel=warning \
  --concurrency=3 \
  --pool=threads \
  -Q celery \
  --hostname=general@%h

# Rate con parsing worker (higher concurrency)
celery -A api worker \
  --loglevel=warning \
  --concurrency=10 \
  --pool=threads \
  -Q ratecon_parsing \
  --hostname=ratecon@%h
```

## Concurrency Benchmarks

From test results with 2 documents (CRST + RXO rate confirmations):

| Mode | Concurrency | Total Time | Notes |
|---|---|---|---|
| sync | 1 | 12.03s | Sequential, one document at a time |
| async | 1 (solo) | 9.03s | No real parallelism |
| async | 2 (threads) | **6.07s** | True parallelism, both docs processed simultaneously |

With `concurrency=2`, the async mode processed both documents in parallel and finished in the time it took to process the slower document alone — a **50% speedup** over sync mode.

## Choosing Concurrency

- **Start with `--concurrency=5`** — matches the default `max_workers` in `process_session_async`
- The bottleneck is the OpenAI API, not CPU or memory
- Each thread holds a database connection, so ensure your DB connection pool can handle the concurrency level
- Monitor OpenAI rate limits — too many concurrent requests may trigger throttling

## Test Runner Configuration

The test runner in `api/runner.py` uses:

```python
'--concurrency=2',
'--pool=threads',
```

This gives enough parallelism to validate async behavior without overwhelming test infrastructure.
