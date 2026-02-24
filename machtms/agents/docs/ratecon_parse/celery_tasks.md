# Celery Tasks: The Orchestration Layer

> Agents are smart, but they can't start themselves. Someone has to hand them documents, manage their results, handle failures, and make sure the whole pipeline doesn't fall apart when one PDF is unreadable. That someone is the Celery task layer.

**File:** `machtms/backend/RateConParser/tasks.py`

**Models:** `machtms/backend/RateConParser/models.py`

---

## The Cast of Characters

Before diving into the tasks, let's meet the database models they interact with:

### ParsingSession

A batch upload. When a user uploads 10 rate confirmations at once, they all belong to one `ParsingSession`.

| Field        | Type               | Description                                   |
|-------------|-------------------|-----------------------------------------------|
| `status`    | `SessionStatus`    | Overall session state (see status table below) |
| `created_at`| `DateTimeField`    | When the session was created                   |
| `updated_at`| `DateTimeField`    | Auto-updated on save                           |

**Properties:**
- `total_documents` -- count of all documents in the session
- `completed_documents` -- count of documents in a terminal state
- `progress` -- percentage complete (0-100)

### RateConDocument

A single uploaded PDF file within a session.

| Field               | Type              | Description                                |
|--------------------|-------------------|--------------------------------------------|
| `session`          | FK to Session      | Which upload batch this belongs to          |
| `status`           | `DocumentStatus`   | Current processing state                    |
| `original_filename`| `TextField`        | Original file name from the upload          |
| `s3_key`           | `TextField`        | S3 storage path                             |
| `file_size`        | `PositiveInteger`  | File size in bytes                          |
| `mime_type`        | `CharField`        | MIME type (default: `application/pdf`)      |
| `error_message`    | `TextField`        | Error details if processing failed          |
| `celery_task_id`   | `CharField`        | The Celery task ID processing this document |
| `processed_at`     | `DateTimeField`    | When processing completed                   |

### ParsedRateCon

The output of processing -- links a document to its parsed results and (optionally) the load that was created from it.

| Field                  | Type              | Description                                      |
|-----------------------|-------------------|--------------------------------------------------|
| `document`            | OneToOne to Doc    | Source document (one parse per document)           |
| `raw_text`            | `TextField`        | The full text response from the processor agent    |
| `structured_data`     | `JSONField`        | Parsed key-value data extracted from the response  |
| `load`                | FK to Load (null)  | The load created from this data (if any)           |
| `classification_passed`| `BooleanField`    | Whether the document passed classification         |
| `classification_reason`| `TextField`        | Reason for FAIL classification                     |

> **Why is `load` nullable?** Because not every document results in a load. If classification fails, or if load creation errors out, the `ParsedRateCon` record still exists as a record of what was attempted. The load FK gets filled in later by `update_ratecon_document_status()` (see [toolkit_functions.md](toolkit_functions.md)).

---

## Status Machines

### DocumentStatus

```
UPLOADING --> PENDING --> PROCESSING --> PARSED
                |              |
                |              +--> MISCLASSIFIED
                |              |
                |              +--> FAILED
                |
                +--> FAILED (via cleanup_stale_uploads)
```

| Status           | Meaning                                              |
|-----------------|------------------------------------------------------|
| `UPLOADING`     | File is being uploaded to S3                          |
| `PENDING`       | Upload complete, waiting for processing               |
| `PROCESSING`    | Agent is actively working on this document            |
| `PARSED`        | Successfully extracted and classified as PASS          |
| `MISCLASSIFIED` | Classification returned FAIL (not a valid rate con)   |
| `FAILED`        | An error occurred during processing                    |

### SessionStatus

| Status             | Meaning                                                      |
|-------------------|--------------------------------------------------------------|
| `UPLOADING`       | Documents are still being uploaded                            |
| `PROCESSING`      | At least one document is being processed                      |
| `COMPLETED`       | All documents are PARSED or MISCLASSIFIED (no failures)       |
| `PARTIALLY_FAILED`| Some documents parsed, some failed                            |
| `FAILED`          | All documents failed                                          |

The session status is *recomputed* from its documents' statuses via `recompute_status()`. It's not set directly -- it's derived.

> **What does recompute_status() solve?** It prevents status drift. Instead of manually updating the session every time a document changes, the session recalculates its own status based on reality. If all children are terminal (parsed, misclassified, or failed), the session figures out its own final state.

---

## The Functions and Tasks

### extract_text_from_pdf() -- The PDF Reader

```python
def extract_text_from_pdf(file_buffer: BytesIO) -> str
```

**Not a Celery task.** A plain utility function.

**What it does:** Takes a `BytesIO` buffer containing PDF bytes, opens it with `pymupdf`, extracts text from every page, and joins them with newlines.

**Why pymupdf?** It's fast, doesn't require system-level dependencies like `poppler`, and handles the vast majority of PDF formats well.

> **What if the PDF has no text?** This happens with scanned documents that are pure images. The function returns an empty string, and `process_single_document` catches this and marks the document as FAILED with the message "No text could be extracted from the PDF."

---

### parse_agent_response() -- The Template Parser

```python
def parse_agent_response(response_text: str) -> dict
```

**Not a Celery task.** A plain utility function.

**What it does:** Takes the raw text response from the Rate Con Processor agent and converts it into a structured dictionary. Remember, the processor outputs a text template (not JSON), so this function handles the parsing.

**Return structure:**
```python
{
    'classification': 'PASS',        # or 'FAIL'
    'classification_reason': '',      # why it failed
    'raw_text': '...',               # full agent response
    'structured_data': {             # parsed key-value pairs
        'Reference Number': 'RC-2025-001',
        'BOL Number': 'BOL-789',
        'Customer Name': 'ACME Corp',
        'stops': [
            {
                'stop_number': 1,
                'type': 'PICKUP',
                'street_address': '123 Main St',
                ...
            }
        ]
    }
}
```

**How the parsing works:**

1. Splits the response into lines
2. Detects `CLASSIFICATION:` and `REASON:` lines
3. Tracks section headers (lines wrapped in `---`)
4. Detects stop headers like `Stop 1:`
5. Parses `Key: Value` pairs, routing them to either the top-level `data` dict or the current stop dict
6. Collects all stops into a list

> **Why parse text instead of asking the agent to output JSON?** Text templates are more reliable from LLMs than structured JSON. LLMs sometimes produce invalid JSON (missing quotes, trailing commas), but they're very consistent with simple key-value templates. The parsing step is deterministic and testable -- the non-deterministic part (the LLM) produces the easiest possible format to parse.

---

### process_single_document() -- The Core Pipeline

```python
def process_single_document(document_id: int)
```

**Not a Celery task** -- it's a plain function. But it's the single most important function in the entire ratecon pipeline. Every processing path eventually calls this.

**Here's what it does, step by step:**

```
1. Load the RateConDocument from DB
   (with session and organization via select_related)
        |
2. Guard: skip if status is not PENDING or PROCESSING
        |
3. Set status to PROCESSING
        |
4. Download file from S3 into BytesIO buffer
        |
5. Extract text from PDF (pymupdf)
        |
   [If text is empty → mark FAILED, return]
        |
6. Run rate_con_processor agent with the text
        |
7. Parse agent response into structured data
        |
8. Create ParsedRateCon record in DB
        |
9. Check classification:
   ├── PASS → set doc status to PARSED
   |          └── Try to create a load (see below)
   └── FAIL → set doc status to MISCLASSIFIED
        |
10. Always: session.recompute_status() in finally block
```

#### The Load Creation Sub-Pipeline (Step 9, PASS branch)

When a document passes classification, the function immediately tries to create a load:

```python
creator_prompt = (
    f"Create a load from this parsed rate confirmation data:\n\n"
    f"{response_text}\n\n"
    f"Metadata:\n"
    f"  celery_task_id: {doc.celery_task_id}\n"
    f"  ratecon_document_id: {doc.pk}"
)

ratecon_load_creator.run(
    creator_prompt,
    session_id=str(uuid.uuid4()),
    dependencies={"organization": organization},
)
```

Notice how metadata is injected into the prompt:

- **`celery_task_id`**: The Celery task ID from the document record, providing traceability back to the async job
- **`ratecon_document_id`**: The document's primary key, so the load creator can link the created load back to its source

> **What does the metadata solve?** Without it, the load creator would create a load that floats in the database with no connection to the rate confirmation that produced it. The metadata creates a traceable chain: Celery Task --> RateConDocument --> ParsedRateCon --> Load.

#### The Critical Error Isolation

Look at this pattern carefully:

```python
if parsed['classification'] == 'PASS':
    doc.status = DocumentStatus.PARSED
    doc.processed_at = timezone.now()
    doc.save(...)

    # Load creation in a try/except
    try:
        ratecon_load_creator.run(...)
    except Exception as load_err:
        logger.exception(f"Load creation failed for document {document_id}: {load_err}")
```

> **What if load creation failed the whole pipeline?** The document has already been marked as `PARSED` and the `ParsedRateCon` record already exists. If load creation blows up, the document status stays `PARSED` -- it doesn't revert to FAILED. This is intentional.

**Why?** Because parsing succeeded. The PDF was read, the data was extracted, and classification passed. That work has value even if load creation fails. A user can review the parsed data and manually create the load. The error is logged, but the parsing results are preserved.

This is a **fail-forward** design -- don't throw away good work just because a later step failed.

#### The Outer Error Handler

The entire function is wrapped in a try/except:

```python
except Exception as e:
    doc.status = DocumentStatus.FAILED
    doc.error_message = str(e)[:500]  # Truncated to prevent DB bloat
    doc.processed_at = timezone.now()
    doc.save(...)
```

This catches failures in S3 download, text extraction, agent execution, or response parsing. The error message is stored on the document (truncated to 500 chars) for debugging.

#### The Finally Block

```python
finally:
    session.recompute_status()
```

No matter what happens -- success, failure, classification pass or fail -- the session always recalculates its status. This ensures the session status is always consistent with reality.

---

### process_document() -- The Celery Wrapper

```python
@shared_task
def process_document(document_id: int):
    """Celery task wrapper around process_single_document."""
    process_single_document(document_id)
```

That's the entire function. It's a one-line wrapper that makes `process_single_document` callable as a Celery task.

> **Why not just decorate process_single_document with @shared_task?** Because `process_single_document` is also called directly by the synchronous processing mode and the worker tasks. Keeping it as a plain function means it can be called from anywhere -- Celery tasks, synchronous code, tests -- without Celery overhead.

---

### process_session_sync() -- Mode A: Sequential Processing

```python
@shared_task
def process_session_sync(session_id: int):
```

**What it does:** Processes all pending documents in a session one at a time, in order of creation.

```
Session (10 documents)
  |
  +-> Doc 1: process_single_document(1)  ← waits until done
  +-> Doc 2: process_single_document(2)  ← waits until done
  +-> Doc 3: process_single_document(3)  ← waits until done
  ...
  +-> Doc 10: process_single_document(10)
  |
  +-> session.recompute_status()
```

**When to use it:** When you want predictable, ordered processing. Good for small batches or debugging. Each document is fully processed before the next one starts.

**Trade-off:** Slower, but simpler. No concurrency issues. Easy to reason about.

---

### process_session_async() -- Mode B: Parallel Processing

```python
@shared_task
def process_session_async(session_id: int, max_workers: int = 5):
```

**What it does:** Spawns up to `max_workers` worker tasks that process documents in parallel.

```
Session (10 documents)
  |
  +-> Worker 1: grabs Doc 1, processes it, grabs Doc 6, processes it...
  +-> Worker 2: grabs Doc 2, processes it, grabs Doc 7, processes it...
  +-> Worker 3: grabs Doc 3, processes it, grabs Doc 8, processes it...
  +-> Worker 4: grabs Doc 4, processes it, grabs Doc 9, processes it...
  +-> Worker 5: grabs Doc 5, processes it, grabs Doc 10, processes it...
```

**How it works:**

1. Counts pending documents
2. Spawns `min(pending_count, max_workers)` worker tasks using Celery's `group`
3. Each worker is a `process_document_worker` task

**When to use it:** When you have a large batch and want faster throughput. The default `max_workers=5` provides a good balance between speed and resource consumption.

---

### process_document_worker() -- The Parallel Worker

```python
@shared_task
def process_document_worker(session_id: int):
```

This is where the concurrency magic happens. Each worker runs a loop:

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
        doc.save(...)

    process_single_document(doc.pk)
```

**The key technique: `select_for_update(skip_locked=True)`**

> **What does this solve?** The classic problem with parallel workers is: what if two workers grab the same document? With `SELECT FOR UPDATE SKIP LOCKED`, each worker locks a row when it claims it. If another worker tries to claim the same row, it skips it and grabs the next available one. No duplicate processing, no race conditions, no distributed locks needed.

**Why process outside the transaction?** The `process_single_document` call involves an LLM API call, which could take 10-30 seconds. Holding a database transaction open for that long would block other queries and risk timeouts. Instead, the document is claimed inside a short transaction (milliseconds), then processed outside of it.

**The loop:** Workers don't process just one document. They keep looping, claiming and processing documents until there are none left. This is more efficient than spawning a new task for each document.

After the loop exits (no more pending documents), `session.recompute_status()` is called.

---

### cleanup_stale_uploads() -- The Janitor

```python
@shared_task
def cleanup_stale_uploads():
```

**What it does:** Finds documents stuck in `UPLOADING` state for more than 1 hour and marks them as `FAILED` with the error message "Upload timed out."

**Why does this exist?** Uploads can fail silently. A user might start uploading, lose their connection, and never complete the upload. Without cleanup, these ghost documents would sit in `UPLOADING` forever, and their parent sessions would never reach a terminal status.

**How it works:**

1. Queries for documents in `UPLOADING` state created more than 1 hour ago
2. Captures the affected session IDs before updating (so we can recompute their statuses)
3. Bulk updates all stale documents to `FAILED`
4. Recomputes status for each affected session
5. Logs the count if any documents were cleaned up

> **Why capture session IDs before the update?** Because after the bulk update, the documents' status has changed and we can't easily trace back which sessions were affected. Capturing the IDs first ensures we recompute the right sessions.

This task is designed to be scheduled periodically (e.g., every 15 minutes via Celery Beat).

---

## The Complete Flow: From Upload to Load

Here's everything stitched together:

```
User uploads 5 PDFs
        |
        v
ParsingSession created (status: UPLOADING)
5x RateConDocument created (status: UPLOADING)
        |
        v
Files uploaded to S3
Documents set to PENDING
        |
        v
process_session_sync(session_id)    or    process_session_async(session_id)
        |                                          |
        v                                          v
Sequential loop                              group of workers
        |                                          |
        +---------> process_single_document() <----+
                           |
                    Download from S3
                    Extract text (pymupdf)
                    Run rate_con_processor agent
                    Parse response
                    Create ParsedRateCon
                           |
                    Classification?
                    /              \
                PASS              FAIL
                  |                 |
           Status: PARSED    Status: MISCLASSIFIED
                  |
           Try load creation:
             ratecon_load_creator.run()
               -> Resolve customer
               -> Resolve addresses
               -> Check stop history
               -> Create load
               -> Link load to document
                  |
           (failure logged, doesn't affect doc status)
                  |
           session.recompute_status()
```

---

## Key Design Patterns

1. **Plain function + Celery wrapper**: `process_single_document` is a plain function. `process_document` is the Celery wrapper. This separation allows the core logic to be called from both async and sync contexts.

2. **Fail-forward**: Parsing success is preserved even if load creation fails. Each stage's results are saved independently.

3. **Optimistic concurrency**: Workers use `SELECT FOR UPDATE SKIP LOCKED` to claim documents without conflicting with each other.

4. **Status derivation**: Session status is always derived from document statuses via `recompute_status()`, never set independently.

5. **Metadata threading**: The `celery_task_id` and `ratecon_document_id` flow from the document record into the agent prompt and eventually into the toolkit calls, maintaining traceability across the entire pipeline.
