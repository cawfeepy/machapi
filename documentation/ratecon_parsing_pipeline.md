# The RateCon Parsing Pipeline

## So, what are we actually building here?

Imagine you are a trucking company. A broker sends you a Rate Confirmation PDF -- a document that says "pick up at warehouse A, deliver to warehouse B, we will pay you $X." Right now, a human reads that PDF, squints at the fonts, and manually types the load details into the TMS. What if we could hand the PDF to an AI agent and get a fully-formed `Load` record back, with legs, stops, addresses, and customer links already wired up?

That is what the RateCon Parsing Pipeline does. It accepts one or more PDF uploads, runs them through an AI-powered extraction and classification step, creates structured `Load` records in the database, and reports the results back to the frontend.

But here is the interesting part: **the AI agents are not in charge of anything.** They do the thinking. The Celery task code does the bookkeeping. Why? Because we learned the hard way that LLMs cannot be trusted to manage system state. More on that later.

---

## Table of Contents

- [Pipeline Overview](#pipeline-overview)
- [API Endpoints -- What Does the Frontend Call?](#api-endpoints----what-does-the-frontend-call)
- [The Status State Machine](#the-status-state-machine)
- [Task Responsibilities -- Who Is Really in Charge?](#task-responsibilities----who-is-really-in-charge)
- [The Agent Reliability Problem](#the-agent-reliability-problem)
- [The PARSED Invariant](#the-parsed-invariant)
- [Load Linking -- Why Not Let the Agent Do It?](#load-linking----why-not-let-the-agent-do-it)
- [Processing Modes -- Sync vs. Async](#processing-modes----sync-vs-async)
- [Data Models](#data-models)
- [The AI Agents](#the-ai-agents)
- [End-to-End Testing](#end-to-end-testing)
- [The Teardown Order Bug](#the-teardown-order-bug)

---

## Pipeline Overview

What does the journey of a PDF look like, from the moment a user drags it into the browser to the moment a `Load` appears in the system?

```
Frontend                          Backend (Django)                    Background (Celery)
--------                          ----------------                    -------------------
1. Create session         --->    ParsingSession created (UPLOADING)
2. Register document      --->    RateConDocument created (UPLOADING)
   (get presigned URL)            Presigned S3 URL returned
3. Upload PDF to S3       --->    (direct S3 PUT via presigned URL)
4. Confirm upload         --->    Document -> PENDING
5. Trigger processing     --->    Celery task dispatched
                                                                      6. Download PDF from S3
                                                                      7. Extract text (pymupdf)
                                                                      8. AI Agent #1: classify + extract
                                                                      9. Create ParsedRateCon record
                                                                      10. AI Agent #2: create Load
                                                                      11. Auto-link Load to ParsedRateCon
                                                                      12. Set document -> PARSED
6. Poll session/document  --->    Return current status + data
```

Every numbered step has a clear owner. The frontend owns steps 1-5 and 6 (polling). The Celery task code owns steps 6-12. The AI agents are called *within* steps 8 and 10, but they do not control the flow. They are tools, not managers.

---

## API Endpoints -- What Does the Frontend Call?

All endpoints live under the `ratecon/` URL namespace. The frontend interacts with five endpoints in a specific sequence.

### Step 1: Create a Session

```
POST /ratecon/sessions/
```

Creates a `ParsingSession` scoped to the user's organization. The session groups multiple document uploads into a single batch. Returns a `session_id`.

**Request body:** empty (or `{}`)

**Response (201):**
```json
{
  "session_id": 42
}
```

### Step 2: Register a Document (Get a Presigned URL)

```
POST /ratecon/documents/upload/
```

Why not upload the file directly to Django? Because PDFs can be large, and we do not want to tie up a Django worker streaming bytes. Instead, the backend generates a presigned S3 URL, and the frontend uploads directly to S3.

**Request body:**
```json
{
  "session_id": 42,
  "filename": "ratecon_ABC123.pdf",
  "mime_type": "application/pdf"
}
```

**Response (201):**
```json
{
  "document_id": 99,
  "original_filename": "ratecon_ABC123.pdf",
  "s3_key": "a1b2c3d4-e5f6-7890-abcd-ef1234567890.pdf",
  "presigned_url": "https://s3.amazonaws.com/..."
}
```

What happens if two documents have the same filename? The backend appends a counter suffix: `ratecon_ABC123-1.pdf`, `ratecon_ABC123-2.pdf`, and so on. Duplicate detection is scoped to the organization.

### Step 3: Upload to S3

The frontend performs a `PUT` request directly to the `presigned_url` with the PDF bytes. This is a browser-to-S3 operation; Django is not involved.

### Step 4: Confirm Upload Complete

```
POST /ratecon/documents/upload-complete/
```

Transitions the document from `UPLOADING` to `PENDING`. Optionally records the file size.

**Request body:**
```json
{
  "document_id": 99,
  "file_size": 245760
}
```

### Step 5: Trigger Processing

```
POST /ratecon/sessions/<session_id>/process/
```

Kicks off the Celery pipeline for all `PENDING` documents in the session.

**Request body:**
```json
{
  "mode": "sync"
}
```

`mode` can be `"sync"` (sequential processing) or `"async"` (parallel workers). See [Processing Modes](#processing-modes----sync-vs-async) below.

**Response (202):**
```json
{
  "session_id": 42,
  "mode": "sync",
  "message": "Processing started for 3 document(s)."
}
```

### Polling Endpoints

After triggering processing, the frontend polls for status:

| Endpoint | Purpose |
|---|---|
| `GET /ratecon/sessions/list/` | List all sessions for the organization |
| `GET /ratecon/sessions/<session_id>/` | Session detail with nested document statuses |
| `GET /ratecon/documents/<document_id>/` | Document detail with parsed content |

### URL Routing Summary

All routes are defined in `machtms/backend/RateConParser/urls.py`:

```python
urlpatterns = [
    path('ratecon/sessions/',                          CreateSessionView),
    path('ratecon/sessions/list/',                     SessionListView),
    path('ratecon/sessions/<int:session_id>/',         SessionDetailView),
    path('ratecon/sessions/<int:session_id>/process/', ProcessSessionView),
    path('ratecon/documents/upload/',                  DocumentUploadView),
    path('ratecon/documents/upload-complete/',          DocumentUploadCompleteView),
    path('ratecon/documents/<int:document_id>/',       DocumentDetailView),
]
```

---

## The Status State Machine

### Document Status

What states can a document be in, and what transitions are valid?

```
                         upload-complete
    UPLOADING  ───────────────────────>  PENDING
        |                                   |
        |  (stale cleanup)                  |  process_single_document()
        v                                   v
      FAILED                            PROCESSING
                                       /    |     \
                   classification      /     |      \  exception
                   == 'FAIL'          /      |       \
                                     v       v        v
                             MISCLASSIFIED  PARSED   FAILED
```

| Status | What it means |
|---|---|
| `UPLOADING` | Document record created, waiting for S3 upload confirmation |
| `PENDING` | Upload confirmed, waiting for processing to begin |
| `PROCESSING` | Celery task has picked up the document and is working on it |
| `PARSED` | Fully processed: `ParsedRateCon` record AND linked `Load` exist |
| `MISCLASSIFIED` | The AI determined this is not a valid rate confirmation |
| `FAILED` | Something went wrong (extraction, agent error, load creation error) |

> **Key rule:** `PARSED`, `MISCLASSIFIED`, and `FAILED` are *terminal* states. Once a document reaches one of these, it stays there.

### Session Status

What about the session that groups multiple documents?

```python
class SessionStatus(models.TextChoices):
    UPLOADING        = 'uploading'
    PROCESSING       = 'processing'
    COMPLETED        = 'completed'
    PARTIALLY_FAILED = 'partially_failed'
    FAILED           = 'failed'
```

Session status is *derived*, not directly set by the pipeline. After each document finishes, the task calls `session.recompute_status()`:

- **COMPLETED** -- All documents are either `PARSED` or `MISCLASSIFIED` (no failures).
- **PARTIALLY_FAILED** -- Some documents succeeded and some failed.
- **FAILED** -- Every document failed.

---

## Task Responsibilities -- Who Is Really in Charge?

Here is the core question: **Who decides when a document's status changes?**

Answer: **The Celery task code. Always. Only.**

Look at `process_single_document()` in `machtms/backend/RateConParser/tasks.py`. This is a plain Python function (not a Celery task itself) that contains the entire processing logic for a single document. The Celery task `process_document` is just a thin wrapper:

```python
@shared_task
def process_document(document_id: int):
    """Celery task wrapper around process_single_document."""
    process_single_document(document_id)
```

Inside `process_single_document()`, every status transition is explicit:

```python
# Entry: set PROCESSING
doc.status = DocumentStatus.PROCESSING
doc.save(update_fields=['status', 'updated_at'])

# ... call AI agent #1 (rate_con_processor) ...
# ... create ParsedRateCon record ...

if parsed_data.classification == 'PASS':
    # ... call AI agent #2 (ratecon_load_creator) ...
    # Load created and linked -- NOW set PARSED
    doc.status = DocumentStatus.PARSED
    doc.save(...)
else:
    doc.status = DocumentStatus.MISCLASSIFIED
    doc.save(...)
```

Notice the comment: *"Load created and linked -- NOW set PARSED."* The document is not marked `PARSED` until:

1. The `ParsedRateCon` record exists in the database.
2. The `ratecon_load_creator` agent has finished executing.
3. The load has been auto-linked to the `ParsedRateCon` record.

Why is this ordering so important? Read on.

---

## The Agent Reliability Problem

What happens when you give an AI agent the power to change database state?

We found out. The `rate_con_processor` agent originally had a `DocumentParsingToolkit` with an `update_document_status` tool. The agent's instructions said something like: "After you finish extracting data, call `update_document_status(status='parsed')`."

**What actually happened:** The AI agent would call `update_document_status(status='parsed')` *on its own initiative*, immediately after extraction, **before** the `ParsedRateCon` record was even created by the task code. From the frontend's perspective, the document was `PARSED`. But when the frontend fetched the document detail, there was no `ParsedRateCon` record, no linked `Load`. The `PARSED` status was a lie.

> **Warning:** AI agents (LLMs) cannot be trusted to manage system state. They will call tools when they feel like it, skip instructions, call things out of order, or call the same tool twice. An LLM following a numbered instruction list will not reliably execute step 8 after step 7. It might skip step 8 entirely. It might do step 8 before step 5.

**The fix was architectural:**

1. **Remove all state-management tools from the agents.** The `rate_con_processor` agent has zero tools -- it only uses `output_schema` to return structured data. The `ratecon_load_creator` agent has tools for *creating* things (addresses, customers, loads), but no tools for updating document status.

2. **Make the task code the single source of truth.** All status transitions happen in `process_single_document()`, in a deterministic order that the task code controls completely.

The agents are still valuable -- they do the hard work of understanding PDFs and assembling load payloads. But they are treated like pure functions: data in, data out. The task code handles all side effects.

---

## The PARSED Invariant

This is the most important guarantee in the system:

> **When a document reaches `PARSED` status, it is guaranteed that both a `ParsedRateCon` record AND a linked `Load` (with legs, stops, and addresses) exist in the database.**

Why does this matter? Because the frontend relies on it. When the frontend sees `PARSED`, it can safely fetch the document detail and display the parsed data and the associated load. If `PARSED` could mean "maybe there is a load, maybe not," the frontend would need defensive checks everywhere.

How does the task code enforce this? By controlling the ordering:

```python
# Step 1: Create ParsedRateCon record (always, even for MISCLASSIFIED)
ParsedRateCon.objects.create(
    organization=organization,
    document=doc,
    raw_text=parsed_data.model_dump_json(),
    structured_data=parsed_data.model_dump(),
    classification_passed=(parsed_data.classification == 'PASS'),
    classification_reason=parsed_data.classification_reason,
)

# Step 2: If classification passed, create the load
if parsed_data.classification == 'PASS':
    try:
        ratecon_load_creator.run(creator_prompt, ...)
        # Step 3: ONLY NOW set PARSED
        doc.status = DocumentStatus.PARSED
        doc.save(...)
    except Exception as load_err:
        # Load creation failed -> FAILED, not PARSED
        doc.status = DocumentStatus.FAILED
        doc.error_message = f"Parsed OK but load creation failed: ..."
        doc.save(...)
```

If the load creator agent throws an exception, the document goes to `FAILED` with a descriptive error message. It never reaches `PARSED` in a half-baked state.

---

## Load Linking -- Why Not Let the Agent Do It?

The `ratecon_load_creator` agent's instructions include this step:

> **8. LINK LOAD TO DOCUMENT:** After the load is created, call `assign_load_to_parsed_ratecon()` with the newly created load ID.

But what if the agent does not follow step 8? What if it creates the load successfully, feels satisfied, and stops? Then the `ParsedRateCon.load` field would be `null`, even though a `Load` exists somewhere in the database with no connection back to the rate con.

**The fix:** The `create_load_from_parsed()` toolkit method now auto-links the load to the `ParsedRateCon` record internally:

```python
def create_load_from_parsed(self, run_context: RunContext, payload_json: str) -> str:
    # ... validate, create load via serializer ...
    load = serializer.save()

    # Auto-link load to ParsedRateCon if ratecon_id is in the run context
    ratecon_id = run_context.dependencies.get("ratecon_id")
    if ratecon_id:
        from machtms.backend.RateConParser.models import ParsedRateCon
        try:
            parsed = ParsedRateCon.objects.get(document_id=ratecon_id)
            parsed.load_id = load.pk
            parsed.save(update_fields=['load_id'])
        except ParsedRateCon.DoesNotExist:
            pass

    # ... return confirmation ...
```

The `ratecon_id` comes from the `run_context.dependencies` dict, which the task code passes when calling the agent. The agent does not need to do anything special -- the linking happens automatically as a side effect of `create_load_from_parsed()`.

The `assign_load_to_parsed_ratecon()` tool still exists in the `DocumentParsingToolkit` as a fallback (the agent's instructions still mention it), but the system no longer *depends* on the agent calling it. Belt and suspenders.

---

## Processing Modes -- Sync vs. Async

What if a session has 20 documents? Do we process them one at a time, or fan out?

### Mode A: Sync (Sequential)

```python
@shared_task
def process_session_sync(session_id: int):
    """Process all pending documents in a session sequentially."""
    for doc in pending_docs:
        process_single_document(doc.pk)
    session.recompute_status()
```

Simple. Predictable. Slow for large batches.

### Mode B: Async (Parallel Workers)

```python
@shared_task
def process_session_async(session_id: int, max_workers: int = 5):
    """Process all pending documents in parallel."""
    job = group(
        process_document_worker.s(session_id) for _ in range(worker_count)
    )
    job.apply_async()
```

What does each worker do? It runs a loop:

```python
@shared_task
def process_document_worker(session_id: int):
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

How do multiple workers avoid processing the same document? Via `SELECT FOR UPDATE SKIP LOCKED`. Each worker atomically claims one `PENDING` document. If another worker already locked a row, it skips to the next one. When no more `PENDING` documents remain, the worker exits.

Why process outside the transaction? Because the LLM call inside `process_single_document()` is long-running (potentially 30+ seconds). Holding a database transaction open that long would block other queries and risk deadlocks.

---

## Data Models

### ParsingSession

The container for a batch upload. Created by the frontend before uploading any documents.

```python
class ParsingSession(TMSModel):
    status     = CharField(choices=SessionStatus.choices, default='uploading')
    created_at = DateTimeField(default=timezone.now)
    updated_at = DateTimeField(auto_now=True)
```

Notable properties:
- `total_documents` -- count of all child documents
- `completed_documents` -- count of documents in terminal states
- `progress` -- percentage complete (0-100)
- `recompute_status()` -- derives session status from child document statuses

### RateConDocument

A single uploaded PDF within a session.

```python
class RateConDocument(TMSModel):
    session           = ForeignKey(ParsingSession, related_name='documents')
    status            = CharField(choices=DocumentStatus.choices, default='uploading')
    original_filename = TextField()
    s3_key            = TextField()
    file_size         = PositiveIntegerField(default=0)
    mime_type         = CharField(default='application/pdf')
    error_message     = TextField(blank=True)
    celery_task_id    = CharField(blank=True)
    processed_at      = DateTimeField(null=True)
    created_at        = DateTimeField(default=timezone.now)
    updated_at        = DateTimeField(auto_now=True)
```

### ParsedRateCon

The parsed output from a rate confirmation. Created by the task code *after* the AI agent returns structured data.

```python
class ParsedRateCon(TMSModel):
    document            = OneToOneField(RateConDocument, related_name='parsed_content')
    raw_text            = TextField(blank=True)       # JSON dump of agent output
    structured_data     = JSONField(null=True)         # Dict of agent output
    load                = ForeignKey('machtms.Load', null=True, blank=True)
    classification_passed = BooleanField(default=True)
    classification_reason = TextField(blank=True)
    created_at          = DateTimeField(default=timezone.now)
```

The relationship chain: `ParsingSession` -> `RateConDocument` -> `ParsedRateCon` -> `Load`.

---

## The AI Agents

### Agent 1: rate_con_processor

**File:** `machtms/agents/members/rate_con_processor.py`

What does this agent do? Two things:

1. **Classify** -- Is this PDF actually a rate confirmation, or did someone upload their grocery list?
2. **Extract** -- If it passes classification, pull out every field: reference number, stops, addresses, appointment times, customer name, trailer type, etc.

How does it return data? Via Agno's `output_schema` feature. The agent is configured with `output_schema=ParsedRateConData`, which forces the LLM to return a structured Pydantic model instead of free-form text.

```python
rate_con_processor = Agent(
    name="Rate Con Processor",
    model=OpenAIChat(id="gpt-5.2"),
    add_history_to_context=False,
    output_schema=ParsedRateConData,
    instructions=[...],
)
```

Notice: **this agent has no tools.** It receives text, it returns structured data. No side effects. No database writes. The task code calls it like a function:

```python
response = rate_con_processor.run(text, session_id=..., dependencies={...})
parsed_data = response.content  # ParsedRateConData instance
```

### Agent 2: ratecon_load_creator

**File:** `machtms/agents/members/ratecon_load_creator.py`

What does this agent do? It takes the structured data from Agent 1 and turns it into an actual `Load` record by:

1. Resolving (or creating) the customer
2. Resolving (or creating) addresses for each stop
3. Determining the correct action code for each stop (using historical stop data)
4. Mapping trailer type descriptions to system codes
5. Parsing appointment times to ISO8601 UTC
6. Assembling the payload and calling `create_load_from_parsed()`

This agent *does* have tools:

```python
ratecon_load_creator = Agent(
    tools=[
        LoadToolkit(),
        AddressToolkit(),
        CustomerToolkit(),
        StopHistoryToolkit(),
        DocumentParsingToolkit(),
    ],
    ...
)
```

It uses these tools to search for existing customers, create addresses, look up stop history at known addresses, and ultimately create the load.

### The Pydantic Models

**File:** `machtms/agents/models/ratecon_payload.py`

Two key models:

- **`ParsedRateConData`** -- The output schema for Agent 1. Contains classification result, reference number, stops (with addresses and appointments), customer name, trailer type, and more.

- **`RateConLoadPayload`** -- The structure that Agent 2 assembles and passes to `create_load_from_parsed()`. Mirrors the `LoadSerializer` input format, with integer FK IDs for addresses and customers (resolved by the agent's toolkit calls).

---

## End-to-End Testing

### How do you test a pipeline that involves S3, Celery, PostgreSQL, RabbitMQ, Redis, and OpenAI?

**File:** `machtms/backend/agents/tests/test_integrated_parser.py`

The integration test class `IntegratedRateConParserTest` acts as the frontend. It walks through the entire flow:

```python
def test_full_celery_pipeline(self):
    # 1. Create session
    resp = self.client.post(reverse('ratecon-create-session'), ...)

    # 2. Register document (get presigned URL)
    resp = self.client.post(reverse('ratecon-document-upload'), ...)

    # 3. Upload to S3 via presigned URL
    upload_resp = requests.put(presigned_url, data=pdf_bytes, ...)

    # 4. Mark upload complete
    resp = self.client.post(reverse('ratecon-upload-complete'), ...)

    # 5. Trigger processing
    resp = self.client.post(reverse('ratecon-process-session', ...), data={'mode': 'sync'})

    # 6. Poll for completion (up to 60 seconds)
    while elapsed < max_wait:
        doc = RateConDocument.objects.get(pk=document_id)
        if doc.status in terminal_statuses:
            break

    # 7. Assert the PARSED invariant
    self.assertEqual(doc.status, DocumentStatus.PARSED)
    parsed = ParsedRateCon.objects.get(document=doc)
    self.assertIsNotNone(parsed.load)  # Load must be linked
```

### Skip conditions

The test requires real credentials:

```python
@skipUnless(
    HAS_OPENAI and HAS_AWS and HAS_TEST_DOCS,
    "Requires OPENAI_API_KEY, AWS credentials, and test_documents/ directory"
)
```

You need `OPENAI_API_KEY`, `AWS_ACCESS_KEY` environment variables, and a `test_documents/` directory containing at least one PDF rate confirmation.

### The test runner: `--use-celery`

**File:** `api/runner.py`

How do you run a Celery worker during tests? The custom `TestContainerRunner` adds a `--use-celery` flag:

```bash
uv run python manage.py test --testrunner=api.runner.TestContainerRunner --use-celery
```

What does this set up?

1. **Testcontainers** spin up Docker containers for PostgreSQL, RabbitMQ, and Redis.
2. Django settings are patched to point at the container endpoints.
3. After `setup_databases()` creates the test database, a **Celery worker subprocess** is spawned.
4. The worker subprocess receives environment variables pointing it at the test database, test RabbitMQ, and test Redis.
5. The worker runs with `--concurrency=1 --pool=solo` (single-threaded, no forking).

```python
cmd = [
    sys.executable, '-m', 'celery',
    '-A', 'api',
    'worker',
    '--loglevel=info',
    '--concurrency=1',
    '--pool=solo',
]
```

Why `--pool=solo`? Because the worker needs to share the same test database. Forked processes would inherit the DB connection but might cause issues with Django's test database isolation.

Worker output is streamed to stdout on a daemon thread, prefixed with `[celery]`, so you can see agent logs interleaved with test output.

### Cleanup

The test's `tearDown()` method cleans up S3 objects uploaded during the test:

```python
def tearDown(self):
    for key in self._uploaded_s3_keys:
        s3_client.delete_object(Bucket=bucket, Key=key)
```

---

## The Teardown Order Bug

What happens when a Celery worker is still connected to a database and Django tries to `DROP` it?

```
ERROR: database "test_machapi" is being accessed by other users
DETAIL: There is 1 other session using the database.
```

PostgreSQL refuses to drop a database with active connections. The default Django test runner calls `teardown_databases()` which does `DROP DATABASE test_machapi`. But the Celery worker subprocess is still alive with an open connection. Deadlock.

### What was the fix?

Stop the Celery worker **before** dropping the database:

```python
def teardown_databases(self, old_config, **kwargs):
    """Stop the Celery worker first so its DB connection is closed
    before Django attempts to DROP the test database."""
    self._stop_celery_worker()
    super().teardown_databases(old_config, **kwargs)
```

The `_stop_celery_worker()` method sends `SIGTERM`, waits up to 5 seconds for graceful shutdown, and `SIGKILL`s if needed:

```python
def _stop_celery_worker(self):
    if self.celery_worker_process is not None:
        self.celery_worker_process.terminate()
        try:
            self.celery_worker_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.celery_worker_process.kill()
            self.celery_worker_process.wait()
        self.celery_worker_process = None
```

Why does this have to happen in `teardown_databases()` specifically, and not in `teardown_test_environment()`? Because `teardown_databases()` is called *first*. By the time `teardown_test_environment()` runs, Django has already tried to drop the database.

The full teardown order is:
1. `teardown_databases()` -- stop worker, then drop test DB
2. `teardown_test_environment()` -- stop containers, restore settings

---

## Stale Upload Cleanup

What if a user starts an upload and never finishes? Documents stuck in `UPLOADING` for more than an hour get cleaned up by a periodic task:

```python
@shared_task
def cleanup_stale_uploads():
    """Periodic cleanup of documents stuck in UPLOADING for more than 1 hour."""
    cutoff = timezone.now() - timedelta(hours=1)
    stale_qs = RateConDocument.objects.filter(
        status=DocumentStatus.UPLOADING,
        created_at__lt=cutoff,
    )
    count = stale_qs.update(
        status=DocumentStatus.FAILED,
        error_message='Upload timed out.',
    )
```

After bulk-updating stale documents, it recomputes the status of any affected sessions.

---

## Key File Reference

| File | Purpose |
|---|---|
| `machtms/backend/RateConParser/models.py` | `ParsingSession`, `RateConDocument`, `ParsedRateCon` models |
| `machtms/backend/RateConParser/views.py` | API endpoints (session CRUD, upload, process trigger) |
| `machtms/backend/RateConParser/urls.py` | URL routing |
| `machtms/backend/RateConParser/serializers.py` | DRF serializers for request/response |
| `machtms/backend/RateConParser/tasks.py` | Celery tasks and `process_single_document()` |
| `machtms/agents/members/rate_con_processor.py` | AI Agent 1: classify + extract |
| `machtms/agents/members/ratecon_load_creator.py` | AI Agent 2: create load from parsed data |
| `machtms/agents/toolkit/document_parsing.py` | `DocumentParsingToolkit` (assign load to parsed ratecon) |
| `machtms/agents/toolkit/loads.py` | `LoadToolkit` with `create_load_from_parsed()` |
| `machtms/agents/models/ratecon_payload.py` | Pydantic models: `ParsedRateConData`, `RateConLoadPayload` |
| `machtms/backend/agents/tests/test_integrated_parser.py` | End-to-end integration test |
| `api/runner.py` | Custom test runner with testcontainers and `--use-celery` |

---

## Design Principles -- A Summary

1. **Agents are tools, not managers.** They transform data. They do not control flow or manage state.
2. **The task code is the single source of truth** for document status transitions.
3. **The PARSED invariant is sacred.** `PARSED` means `ParsedRateCon` + linked `Load` exist. Always.
4. **Auto-link over agent-link.** Critical side effects happen in deterministic code, not in LLM instruction lists.
5. **Teardown order matters.** Kill the worker before dropping the database.
6. **Parallel safety via `SKIP LOCKED`.** Multiple workers claim documents without conflicts.
