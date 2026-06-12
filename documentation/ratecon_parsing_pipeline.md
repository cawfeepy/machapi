# The RateCon Parsing Pipeline

## So, what are we actually building here?

Imagine you are a trucking company. A broker sends you a Rate Confirmation PDF — a document that says "pick up at warehouse A, deliver to warehouse B, we will pay you $X." Right now, a human reads that PDF, squints at the fonts, and manually types the load details into the TMS. What if we could hand the PDF to an AI agent and get a fully-formed `Load` record back, with legs, stops, addresses, and customer links already wired up?

That is what the RateCon Parsing Pipeline does. It accepts one or more PDF uploads, runs them through an AI-powered extraction and classification step, creates structured `Load` records in the database, and reports the results back to the frontend.

But here is the interesting part: **the AI agents are not in charge of anything.** They do the thinking. The Celery task code does the bookkeeping. Why? Because we learned the hard way that LLMs cannot be trusted to manage system state. More on that later.

---

## Table of Contents

- [Pipeline Overview](#pipeline-overview)
- [API Endpoints — What Does the Frontend Call?](#api-endpoints--what-does-the-frontend-call)
- [The Orphan Recovery Safety Net](#the-orphan-recovery-safety-net)
- [The Status State Machine](#the-status-state-machine)
- [Task Responsibilities — Who Is Really in Charge?](#task-responsibilities--who-is-really-in-charge)
- [The Agent Reliability Problem](#the-agent-reliability-problem)
- [The PARSED Invariant](#the-parsed-invariant)
- [Processing Modes — Sync vs. Async](#processing-modes--sync-vs-async)
- [Data Models](#data-models)
- [The AI Agent](#the-ai-agent)
- [End-to-End Testing](#end-to-end-testing)
- [The Teardown Order Bug](#the-teardown-order-bug)

---

## Pipeline Overview

What does the journey of a PDF look like, from the moment a user drags it into the browser to the moment a `Load` appears in the system?

```
Frontend                          Backend (Django)                    Background (Celery / S3)
--------                          ----------------                    ------------------------
1. Request presigned URLs  --->   Generate S3 PUT URLs
   (batch, all files)             Create PresignedURLEntryPoint(s)
                                  (status: ORPHANED)
                           <---   Return [{id, presigned_url, s3_key}]

2. Upload PDFs to S3       --->   (direct S3 PUT per file — Django not involved)

3. Create session          --->   Create ParsingSession (UPLOADING)
   (send entrypoint IDs)          Create RateConDocument(s) (PENDING)
                                  Mark entrypoints PROCESSED
                           <---   Return {session_id, documents}

4. Trigger processing      --->   Dispatch Celery task → 202 Accepted
                                                          5. Set session → PROCESSING
                                                          6. Fan out worker tasks (parallel)
                                                          7. Each worker claims a PENDING doc
                                                             (SELECT FOR UPDATE SKIP LOCKED)
                                                          8. Generate presigned GET URL for PDF
                                                          9. Send PDF to rate_con_processor agent
                                                          10. Agent: classify + extract fields
                                                          11. Store classification on document
                                                          12. If PASS: create Load
                                                              link load to document → PARSED
                                                              If FAIL: → MISCLASSIFIED
                                                              On error: → FAILED
                                                          13. recompute_status() on session

5. Poll sessions list      --->   Return up to 8 non-hidden sessions
6. Poll session detail     --->   Return session + all nested documents
7. Hide session            --->   Mark session is_hidden=True
```

Every numbered step has a clear owner. The frontend owns steps 1–4 (upload flow) and 5–7 (polling and cleanup). The Celery task code owns steps 5–13 in the background. The AI agent is called within step 10, but it does not control flow. It is a tool, not a manager.

---

## API Endpoints — What Does the Frontend Call?

All endpoints live under the `ratecon/` URL namespace.

### Step 1: Request Presigned Upload URLs (Batch)

```
POST /ratecon/presigned-urls/
```

The frontend sends the filenames and MIME types for all files it wants to upload **in a single request**. The backend generates a presigned S3 PUT URL for each file, creates a `PresignedURLEntryPoint` record (status: `ORPHANED`), and returns everything.

Why `ORPHANED`? Because at this moment the files have not yet been uploaded to S3, and no session exists yet. If the user navigates away after this step, the orphan recovery mechanism can rescue those files.

**Request body:**
```json
{
  "files": [
    { "filename": "ratecon_abc.pdf", "mime_type": "application/pdf" },
    { "filename": "ratecon_def.pdf", "mime_type": "application/pdf" }
  ]
}
```

**Response (201):**
```json
[
  {
    "id": 1,
    "presigned_url": "https://s3.amazonaws.com/...",
    "s3_key": "a1b2c3d4-e5f6-7890-abcd-ef1234567890.pdf",
    "filename": "ratecon_abc.pdf",
    "expiration": "2026-03-01T10:15:00Z",
    "status": "orphaned"
  },
  {
    "id": 2,
    "presigned_url": "https://s3.amazonaws.com/...",
    "s3_key": "b2c3d4e5-f6a7-8901-bcde-f12345678901.pdf",
    "filename": "ratecon_def.pdf",
    "expiration": "2026-03-01T10:15:00Z",
    "status": "orphaned"
  }
]
```

What happens if two files have the same filename? The backend appends a counter suffix: `ratecon_abc.pdf`, `ratecon_abc-2.pdf`, and so on. Deduplication is scoped within the batch.

The presigned URLs expire after **15 minutes**.

### Step 2: Upload PDFs to S3

For each file, the frontend performs a `PUT` request directly to the `presigned_url` with the PDF bytes. This is a browser-to-S3 operation; Django is not involved.

### Step 3: Create a Session from Uploaded Entrypoints

```
POST /ratecon/sessions/from-presigned/
```

Once the S3 uploads are complete, the frontend tells the backend which entrypoint IDs were successfully uploaded. The backend:

1. Creates a `ParsingSession` (status: `UPLOADING`)
2. Creates a `RateConDocument` for each entrypoint (status: `PENDING`)
3. Marks the `PresignedURLEntryPoint` records as `PROCESSED`

**Request body:**
```json
{
  "entrypoint_ids": [1, 2]
}
```

**Response (201):**
```json
{
  "session_id": 42,
  "documents": [
    {
      "id": 10,
      "session": 42,
      "status": "pending",
      "original_filename": "ratecon_abc.pdf",
      "s3_key": "a1b2c3d4-e5f6-7890-abcd-ef1234567890.pdf",
      ...
    },
    {
      "id": 11,
      "session": 42,
      "status": "pending",
      "original_filename": "ratecon_def.pdf",
      "s3_key": "b2c3d4e5-f6a7-8901-bcde-f12345678901.pdf",
      ...
    }
  ]
}
```

### Step 4: Trigger Processing

```
POST /ratecon/sessions/<session_id>/process-pdf/
```

Kicks off the Celery pipeline for all `PENDING` documents in the session. Uses direct PDF mode: the worker generates a presigned GET URL for the S3 object and sends the PDF straight to the AI agent (no text extraction step).

> **SDK operation ID:** `rateConProcessSessionPdf`
>
> **Alternative processing endpoints** (see URL Routing Summary below):
> - `rateConProcessSessionTextMode` — text-extraction mode via `POST /ratecon/sessions/<id>/process/`
> - `rateConProcessDocumentPdfMode` — per-document retry via `POST /ratecon/documents/<id>/process-pdf/`

**Request body:**
```json
{
  "mode": "async"
}
```

`mode` can be `"sync"` (sequential) or `"async"` (parallel workers). See [Processing Modes](#processing-modes--sync-vs-async) below. For production use, always use `"async"`.

**Response (202):**
```json
{
  "session_id": 42,
  "mode": "async",
  "message": "PDF processing started for 2 document(s)."
}
```

### Polling Endpoints

After triggering processing, the frontend polls for status:

| Endpoint | Purpose |
|---|---|
| `GET /ratecon/sessions/list/` | List up to 8 non-hidden sessions for the org, newest first |
| `GET /ratecon/sessions/<session_id>/` | Session detail with nested document statuses |
| `GET /ratecon/documents/<document_id>/` | Single document detail |

### Session Management

```
POST /ratecon/sessions/<session_id>/hide/
```

Hides a completed session from the session list. The session and its documents remain in the database but `is_hidden` is set to `True` so they no longer appear in `GET /ratecon/sessions/list/`.

### URL Routing Summary

All routes are defined in `machtms/backend/RateConParser/urls.py`:

```python
urlpatterns = [
    # Presigned URL flow
    path('ratecon/presigned-urls/',              PresignedURLEntryPointView),
    path('ratecon/sessions/from-presigned/',      CreateSessionFromPresignedView),

    # Processing
    path('ratecon/sessions/<id>/process/',        ProcessSessionView),       # text extraction mode  | SDK: rateConProcessSessionTextMode
    path('ratecon/sessions/<id>/process-pdf/',    ProcessSessionPdfView),    # direct PDF mode (preferred)  | SDK: rateConProcessSessionPdf
    path('ratecon/documents/<id>/process-pdf/',   ProcessDocumentPdfView),   # single-doc retry  | SDK: rateConProcessDocumentPdfMode

    # Polling
    path('ratecon/sessions/list/',                SessionListView),
    path('ratecon/sessions/<id>/',                SessionDetailView),
    path('ratecon/documents/<id>/',               DocumentDetailView),

    # Management
    path('ratecon/sessions/<id>/hide/',           HideSessionView),
    path('ratecon/orphaned/pre-check/',           OrphanedDocumentCheckView),
]
```

---

## The Orphan Recovery Safety Net

What if the user uploads files to S3 in step 2 but then closes the browser tab before completing step 3? The S3 objects exist, the `PresignedURLEntryPoint` records are still `ORPHANED`, but no session was ever created.

The frontend can call:

```
POST /ratecon/orphaned/pre-check/
```

This dispatches a Celery task (`run_orphan_check_for_org`) scoped to the requesting organization. The task:

1. **Expired + orphaned** — deletes the S3 object (best-effort) and the entrypoint record.
2. **Unexpired + orphaned** — creates a new `ParsingSession`, attaches the uploaded files as `RateConDocument` records (status: `PENDING`), marks entrypoints `PROCESSED`, and auto-dispatches `process_session_async`.
3. **Already processed** — deletes the stale entrypoint records (session already exists).

The response is always `202 Accepted`. The frontend should then poll `GET /ratecon/sessions/list/` to discover the newly created session, if any.

This endpoint is most useful to call on page load, before showing the upload UI, so that any files from a previous interrupted session appear automatically.

---

## The Status State Machine

### Document Status

What states can a document be in, and what transitions are valid?

```
   PENDING
      |
      |  process_single_document() called
      v
  PROCESSING
   /   |    \
  /    |     \  exception
 v     v      v
PARSED  MISCLASSIFIED  FAILED
```

| Status | What it means |
|---|---|
| `PENDING` | Documents start here after session creation; waiting for a Celery worker to pick them up |
| `PROCESSING` | A Celery worker has claimed this document and is working on it |
| `PARSED` | Successfully processed: classification passed AND a linked `Load` exists |
| `MISCLASSIFIED` | The AI determined this is not a valid rate confirmation |
| `FAILED` | Something went wrong (agent error, load creation error, etc.) |

> **Key rule:** `PARSED`, `MISCLASSIFIED`, and `FAILED` are *terminal* states. Once a document reaches one of these, it stays there.

There is also an `UPLOADING` document status defined in the model for legacy compatibility, but in the current presigned-URL flow, documents are created directly as `PENDING`.

### Session Status

```python
class SessionStatus(models.TextChoices):
    UPLOADING        = 'uploading'
    PROCESSING       = 'processing'
    COMPLETED        = 'completed'
    PARTIALLY_FAILED = 'partially_failed'
    FAILED           = 'failed'
```

Session status is *derived*, not directly set by the pipeline (except the initial `UPLOADING` → `PROCESSING` transition when a Celery task starts). After each document finishes, the task calls `session.recompute_status()`:

- **COMPLETED** — All documents are either `PARSED` or `MISCLASSIFIED` (no failures).
- **PARTIALLY_FAILED** — Some documents succeeded (`PARSED` or `MISCLASSIFIED`) and some `FAILED`.
- **FAILED** — Every document failed.

---

## Task Responsibilities — Who Is Really in Charge?

Here is the core question: **Who decides when a document's status changes?**

Answer: **The Celery task code. Always. Only.**

Look at `process_single_document()` in `machtms/backend/RateConParser/tasks.py`. This is a plain Python function (not a Celery task itself) that contains the entire processing logic for a single document. The Celery task `process_document` is just a thin wrapper:

```python
@shared_task
def process_document(document_id: int, use_raw_text: bool = True):
    """Celery task wrapper around process_single_document."""
    process_single_document(document_id, use_raw_text=use_raw_text)
```

Inside `process_single_document()`, every status transition is explicit:

```python
# Entry: set PROCESSING
doc.status = DocumentStatus.PROCESSING
doc.save(update_fields=['status', 'updated_at'])

# Call agent (via presigned URL in PDF mode)
response = send_pdf_url_to_agent(s3_key=doc.s3_key, agent=rate_con_processor, ...)
parsed_data = response.content  # ParsedRateConData instance

# Store classification result on the document
doc.classification_passed = (parsed_data.classification == 'PASS')
doc.classification_reason = parsed_data.classification_reason
doc.save(update_fields=['classification_passed', 'classification_reason', 'updated_at'])

if parsed_data.classification == 'PASS':
    create_load_from_ratecon_data(parsed_data, organization, doc.pk)
    # Load created and linked — NOW set PARSED
    doc.status = DocumentStatus.PARSED
    doc.save(...)
else:
    doc.status = DocumentStatus.MISCLASSIFIED
    doc.save(...)
```

Notice the comment: *"Load created and linked — NOW set PARSED."* The document is not marked `PARSED` until the load exists and is linked.

---

## The Agent Reliability Problem

What happens when you give an AI agent the power to change database state?

We found out. The original design had the agent calling an `update_document_status` tool after finishing. The agent would call it *on its own initiative*, immediately after extraction, **before** related records were created. From the frontend's perspective, the document was `PARSED`. But when it fetched the document detail, there was no linked `Load`.

> **Warning:** AI agents (LLMs) cannot be trusted to manage system state. They will call tools when they feel like it, skip instructions, call things out of order, or call the same tool twice. An LLM following a numbered instruction list will not reliably execute step 8 after step 7.

**The fix was architectural:**

1. **Remove all state-management tools from the agent.** `rate_con_processor` has zero tools — it only uses `output_schema` to return structured data. No side effects. No database writes.

2. **Make the task code the single source of truth.** All status transitions happen in `process_single_document()`, in a deterministic order that the task code controls completely.

The agent is still valuable — it does the hard work of understanding PDFs. But it is treated like a pure function: data in, data out. The task code handles all side effects.

---

## The PARSED Invariant

This is the most important guarantee in the system:

> **When a document reaches `PARSED` status, it is guaranteed that a linked `Load` (with legs, stops, and addresses) exists in the database and is attached to the document via the `load` FK.**

Why does this matter? Because the frontend relies on it. When the frontend sees `PARSED`, it can safely fetch the document detail and navigate to the associated load. If `PARSED` could mean "maybe there is a load, maybe not," the frontend would need defensive checks everywhere.

How does the task code enforce this? By controlling the ordering in `process_single_document()`:

```python
if parsed_data.classification == 'PASS':
    try:
        create_load_from_ratecon_data(parsed_data, organization, doc.pk)
        # ONLY NOW set PARSED
        doc.status = DocumentStatus.PARSED
        doc.processed_at = timezone.now()
        doc.save(update_fields=['status', 'processed_at', 'updated_at'])
    except Exception as load_err:
        # Load creation failed -> FAILED, not PARSED
        doc.status = DocumentStatus.FAILED
        doc.error_message = f"Parsed OK but load creation failed: {str(load_err)[:400]}"
        doc.save(...)
```

If `create_load_from_ratecon_data()` raises an exception, the document goes to `FAILED` with a descriptive error message. It never reaches `PARSED` in a half-baked state.

The `create_load_from_ratecon_data()` function in `tasks.py` auto-links the load to the document by setting `doc.load = load` internally, so linking is deterministic and never depends on the agent.

---

## Processing Modes — Sync vs. Async

What if a session has many documents? Do we process them one at a time, or fan out?

### Mode A: Sync (Sequential)

```python
@shared_task
def process_session_sync(session_id: int, use_raw_text: bool = True):
    for doc in pending_docs:
        process_single_document(doc.pk, use_raw_text=use_raw_text)
    session.recompute_status()
```

Simple. Predictable. Slow for large batches.

### Mode B: Async (Parallel Workers) — Preferred

```python
@shared_task
def process_session_async(session_id: int, max_workers: int = 5, use_raw_text: bool = True):
    job = group(
        process_document_worker.s(session_id, use_raw_text) for _ in range(worker_count)
    )
    job.apply_async()
```

Up to 5 `process_document_worker` tasks run in parallel. Each worker runs a claim loop:

```python
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

    process_single_document(doc.pk, use_raw_text=use_raw_text)
```

How do multiple workers avoid processing the same document? Via `SELECT FOR UPDATE SKIP LOCKED`. Each worker atomically claims one `PENDING` document. When no more `PENDING` documents remain, the worker exits.

Why process outside the transaction? Because the AI agent call inside `process_single_document()` can take 10–30 seconds. Holding a database transaction open that long would block other queries and risk deadlocks.

### Rescue Workers

Workers are configured with `acks_late=True` and `task_reject_on_worker_lost=True`. If a worker is hard-killed (OOM, SIGKILL) mid-processing, the task is re-queued to the `rescue` queue. A `rescue_document_worker` handles this queue and also claims documents stuck in `PROCESSING` for more than 15 minutes.

---

## Data Models

### ParsingSession

The container for a batch upload. Created by the backend when the frontend calls `POST /ratecon/sessions/from-presigned/`.

```python
class ParsingSession(TMSModel):
    status     = CharField(choices=SessionStatus.choices, default='uploading')
    is_hidden  = BooleanField(default=False)
    created_at = DateTimeField(default=timezone.now)
    updated_at = DateTimeField(auto_now=True)
```

Notable properties:
- `total_documents` — count of all child documents
- `documents` — nested list of `RateConDocument` objects belonging to this session
- `progress` — percentage complete (0.0–100.0)
- `recompute_status()` — derives session status from child document statuses

### RateConDocument

A single uploaded PDF within a session.

```python
class RateConDocument(TMSModel):
    session                = ForeignKey(ParsingSession, related_name='documents')
    status                 = CharField(choices=DocumentStatus.choices, default='uploading')
    original_filename      = TextField()
    s3_key                 = TextField()
    file_size              = PositiveIntegerField(default=0)
    mime_type              = CharField(default='application/pdf')
    error_message          = TextField(blank=True)
    celery_task_id         = CharField(blank=True)
    processed_at           = DateTimeField(null=True)
    load                   = ForeignKey('machtms.Load', null=True, blank=True)
    classification_passed  = BooleanField(null=True, default=None)
    classification_reason  = TextField(blank=True)
    created_at             = DateTimeField(default=timezone.now)
    updated_at             = DateTimeField(auto_now=True)
```

The `load` FK is the success signal: when a document is `PARSED`, `load` will point to the created `Load` record.

### PresignedURLEntryPoint

A lightweight pre-session record tracking each presigned upload slot.

```python
class PresignedURLEntryPoint(TMSModel):
    presigned_url = TextField()
    s3_key        = TextField()
    filename      = TextField()
    expiration    = DateTimeField()
    status        = CharField(choices=['orphaned', 'processed'], default='orphaned')
    created_at    = DateTimeField(default=timezone.now)
    updated_at    = DateTimeField(auto_now=True)
```

Lifecycle: created as `ORPHANED` when presigned URLs are generated → marked `PROCESSED` when the session is created → deleted after the session exists.

---

## The AI Agent

### rate_con_processor

**File:** `machtms/agents/members/rate_con_processor.py`

What does this agent do? Two things:

1. **Classify** — Is this PDF actually a rate confirmation, or did someone upload an invoice?
2. **Extract** — If it passes classification, pull out every field: reference number, stops, addresses, appointment times, customer name, trailer type, etc.

How does it return data? Via Agno's `output_schema` feature. The agent is configured with `output_schema=ParsedRateConData`, which forces the LLM to return a structured Pydantic model instead of free-form text.

```python
rate_con_processor = Agent(
    name="Rate Con Processor",
    model=OpenAIChat(id="gpt-4o"),
    add_history_to_context=False,
    output_schema=ParsedRateConData,
    instructions=[...],
)
```

**This agent has no tools.** It receives a PDF (via presigned URL in PDF mode, or extracted text in text mode), and returns structured data. No side effects. No database writes.

In PDF mode, the task code calls it like this:

```python
response = send_pdf_url_to_agent(
    s3_key=doc.s3_key,
    agent=rate_con_processor,
    session_id=str(uuid.uuid4()),
    dependencies=agent_dependencies,
)
parsed_data = response.content  # ParsedRateConData instance
```

### Load Creation (Deterministic Code, Not an Agent)

Once the agent returns `ParsedRateConData`, the task code calls `create_load_from_ratecon_data()` — a plain Python function in `tasks.py`. This function:

1. Resolves or creates the `Customer` by name
2. Resolves or creates `Address` records for each stop via `get_or_create`
3. Infers stop actions from historical stop data (`_get_suggested_action`)
4. Parses appointment strings to ISO8601 UTC (`_parse_appointment`)
5. Maps trailer type descriptions to system codes (`_map_trailer_type`)
6. Assembles the full load payload and validates + saves via `LoadSerializer`
7. Links the created load back to the document: `doc.load = load`

This is deterministic code, not an LLM. It will either succeed or raise an exception — no ambiguity.

### The Pydantic Models

**File:** `machtms/agents/toolkit/document_parsing.py` and related

`ParsedRateConData` is the output schema for the agent. It contains:
- `classification`: `'PASS'` or `'FAIL'`
- `classification_reason`: explanation if `FAIL`
- `reference_number`, `bol_number`, `customer_name`, `trailer_type`
- `stops`: list of stop objects with `street_address`, `city`, `state`, `zip_code`, `place_name`, `appointment`, `po_numbers`, `notes`

---

## End-to-End Testing

### How do you test a pipeline that involves S3, Celery, PostgreSQL, RabbitMQ, Redis, and OpenAI?

**File:** `machtms/backend/agents/tests/test_integrated_parser.py`

The integration test class walks through the presigned-URL flow end to end:

```python
def test_full_celery_pipeline(self):
    # 1. Get presigned URLs
    resp = self.client.post('/ratecon/presigned-urls/', {'files': [{'filename': 'test.pdf'}]})
    entrypoint_id = resp.data[0]['id']
    presigned_url = resp.data[0]['presigned_url']

    # 2. Upload to S3
    requests.put(presigned_url, data=pdf_bytes, headers={'Content-Type': 'application/pdf'})

    # 3. Create session
    resp = self.client.post('/ratecon/sessions/from-presigned/', {'entrypoint_ids': [entrypoint_id]})
    session_id = resp.data['session_id']

    # 4. Trigger PDF processing
    resp = self.client.post(f'/ratecon/sessions/{session_id}/process-pdf/', {'mode': 'async'})

    # 5. Poll for completion (up to 60 seconds)
    while elapsed < max_wait:
        doc = RateConDocument.objects.get(pk=document_id)
        if doc.status in terminal_statuses:
            break

    # 6. Assert the PARSED invariant
    self.assertEqual(doc.status, DocumentStatus.PARSED)
    self.assertIsNotNone(doc.load)  # Load must be linked
```

### Skip conditions

```python
@skipUnless(
    HAS_OPENAI and HAS_AWS and HAS_TEST_DOCS,
    "Requires OPENAI_API_KEY, AWS credentials, and test_documents/ directory"
)
```

You need `OPENAI_API_KEY`, AWS credentials, and a `test_documents/` directory containing at least one PDF rate confirmation.

### The test runner: `--use-celery`

**File:** `api/runner.py`

```bash
uv run python manage.py test --testrunner=api.runner.TestContainerRunner --use-celery
```

What does this set up?

1. **Testcontainers** spin up Docker containers for PostgreSQL, RabbitMQ, and Redis.
2. Django settings are patched to point at the container endpoints.
3. After `setup_databases()` creates the test database, a **Celery worker subprocess** is spawned.
4. The worker subprocess receives environment variables pointing it at the test database, RabbitMQ, and Redis.
5. The worker runs with `--concurrency=1 --pool=solo` (single-threaded, no forking).

---

## The Teardown Order Bug

What happens when a Celery worker is still connected to a database and Django tries to `DROP` it?

```
ERROR: database "test_machapi" is being accessed by other users
DETAIL: There is 1 other session using the database.
```

PostgreSQL refuses to drop a database with active connections. The fix is stopping the Celery worker **before** dropping the database:

```python
def teardown_databases(self, old_config, **kwargs):
    """Stop the Celery worker first so its DB connection is closed
    before Django attempts to DROP the test database."""
    self._stop_celery_worker()
    super().teardown_databases(old_config, **kwargs)
```

The full teardown order is:
1. `teardown_databases()` — stop worker, then drop test DB
2. `teardown_test_environment()` — stop containers, restore settings

---

## Key File Reference

| File | Purpose |
|---|---|
| `machtms/backend/RateConParser/models.py` | `ParsingSession`, `RateConDocument`, `PresignedURLEntryPoint` models |
| `machtms/backend/RateConParser/views.py` | API endpoints (presigned URLs, session creation, processing, polling, hide, orphan check) |
| `machtms/backend/RateConParser/urls.py` | URL routing |
| `machtms/backend/RateConParser/serializers.py` | DRF serializers for request/response |
| `machtms/backend/RateConParser/tasks.py` | Celery tasks, `process_single_document()`, `create_load_from_ratecon_data()` |
| `machtms/agents/members/rate_con_processor.py` | AI Agent: classify + extract structured data |
| `machtms/backend/agents/tests/test_integrated_parser.py` | End-to-end integration test |
| `api/runner.py` | Custom test runner with testcontainers and `--use-celery` |

---

## Design Principles — A Summary

1. **Agents are tools, not managers.** They transform data. They do not control flow or manage state.
2. **The task code is the single source of truth** for document status transitions.
3. **The PARSED invariant is sacred.** `PARSED` means a linked `Load` exists on the document. Always.
4. **Presigned URLs first, session second.** The frontend requests upload slots, uploads to S3, then commits the session — decoupling upload from session creation.
5. **Orphan recovery is a safety net.** `PresignedURLEntryPoint` records survive browser crashes and are recovered automatically.
6. **Parallel safety via `SKIP LOCKED`.** Multiple workers claim documents without conflicts.
7. **Teardown order matters.** Kill the worker before dropping the database.
