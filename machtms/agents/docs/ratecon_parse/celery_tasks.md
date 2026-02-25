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
| `raw_text`            | `TextField`        | JSON dump of the ParsedRateConData model           |
| `structured_data`     | `JSONField`        | Dict dump of ParsedRateConData (for easy querying) |
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

---

## The Functions and Tasks

### extract_text_from_pdf() -- The PDF Reader

```python
def extract_text_from_pdf(file_buffer: BytesIO) -> str
```

**Not a Celery task.** A plain utility function.

**What it does:** Takes a `BytesIO` buffer containing PDF bytes, opens it with `pymupdf`, extracts text from every page, and joins them with newlines.

> **What if the PDF has no text?** This happens with scanned documents that are pure images. The function returns an empty string, and `process_single_document` catches this and marks the document as FAILED.

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
   [If text is empty -> mark FAILED, return]
        |
6. Run rate_con_processor agent with the text
   (returns ParsedRateConData via output_schema)
        |
7. Store ParsedRateConData as raw_text (JSON) and structured_data (dict)
        |
8. Create ParsedRateCon record in DB
        |
9. Check parsed_data.classification:
   +-- PASS -> set doc status to PARSED
   |          +-- Try to create a load (see below)
   +-- FAIL -> set doc status to MISCLASSIFIED
        |
10. Always: session.recompute_status() in finally block
```

> **What changed from the old pipeline?** Previously, step 6 returned raw text that step 7 parsed via a regex function (`parse_agent_response()`). Now, step 6 returns a validated `ParsedRateConData` instance directly via Agno's `output_schema`. No parsing step needed.

#### The Load Creation Sub-Pipeline (Step 9, PASS branch)

When a document passes classification, the function immediately tries to create a load:

```python
creator_prompt = (
    f"Create a load from this parsed rate confirmation data (JSON):\n\n"
    f"{parsed_data.model_dump_json(indent=2)}\n\n"
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

The load creator receives clean JSON from `model_dump_json()` instead of raw template text. Metadata is injected separately in the prompt (not embedded in the JSON) because `celery_task_id` and `ratecon_document_id` come from the document record, not the parser.

#### The Critical Error Isolation

```python
if parsed_data.classification == 'PASS':
    doc.status = DocumentStatus.PARSED
    doc.save(...)

    try:
        ratecon_load_creator.run(...)
    except Exception as load_err:
        logger.exception(...)
```

> **Why is load creation failure isolated?** Because parsing succeeded. The PDF was read, the data was extracted, and classification passed. That work has value even if load creation fails. A user can review the parsed data and manually create the load. This is a **fail-forward** design.

#### The Outer Error Handler

The entire function is wrapped in a try/except that catches S3 download failures, text extraction errors, agent execution failures, etc. The error message is stored on the document (truncated to 500 chars).

#### The Finally Block

```python
finally:
    session.recompute_status()
```

No matter what happens, the session always recalculates its status.

---

### process_document() -- The Celery Wrapper

```python
@shared_task
def process_document(document_id: int):
    process_single_document(document_id)
```

A one-line wrapper that makes `process_single_document` callable as a Celery task.

> **Why not just decorate process_single_document with @shared_task?** Because `process_single_document` is also called directly by the synchronous processing mode and the worker tasks.

---

### process_session_sync() -- Mode A: Sequential Processing

Processes all pending documents one at a time, in creation order. See [sync_async_processing.md](sync_async_processing.md) for details.

---

### process_session_async() -- Mode B: Parallel Processing

Spawns up to `max_workers` worker tasks that process documents in parallel using `SELECT FOR UPDATE SKIP LOCKED`. See [sync_async_processing.md](sync_async_processing.md) for details.

---

### cleanup_stale_uploads() -- The Janitor

Finds documents stuck in `UPLOADING` state for more than 1 hour and marks them as `FAILED`. Designed to be scheduled periodically via Celery Beat.

---

## The Complete Flow: From Upload to Load

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
                    -> returns ParsedRateConData (Pydantic)
                    Store as ParsedRateCon record
                           |
                    Classification?
                    /              \
                PASS              FAIL
                  |                 |
           Status: PARSED    Status: MISCLASSIFIED
                  |
           Try load creation:
             ratecon_load_creator.run()
               -> Receives ParsedRateConData as JSON
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

2. **Structured output, no parsing**: The rate_con_processor agent returns a `ParsedRateConData` instance directly via `output_schema`. No regex parsing step.

3. **Fail-forward**: Parsing success is preserved even if load creation fails. Each stage's results are saved independently.

4. **Optimistic concurrency**: Workers use `SELECT FOR UPDATE SKIP LOCKED` to claim documents without conflicting with each other.

5. **Status derivation**: Session status is always derived from document statuses via `recompute_status()`, never set independently.

6. **Metadata threading**: The `celery_task_id` and `ratecon_document_id` flow from the document record into the agent prompt and eventually into the toolkit calls, maintaining traceability across the entire pipeline.
