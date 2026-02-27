# Multi-Document Workflow Tests

## Overview

These tests validate the full end-to-end rate confirmation parsing pipeline with **multiple documents** uploaded in a single session. The workflow mirrors what a frontend client does:

1. **Create Session** - `POST /ratecon/sessions/`
2. **Request Presigned URLs** - `POST /ratecon/documents/upload/` (per document)
3. **Upload to S3** - `PUT` to presigned URL with PDF bytes
4. **Mark Upload Complete** - `POST /ratecon/documents/upload-complete/` (per document)
5. **Trigger Processing** - `POST /ratecon/sessions/<id>/process/` (raw text) or `/process-pdf/` (PDF mode)
6. **Poll for Completion** - Wait for all documents to reach terminal status
7. **Verify Results** - Assert PARSED status, session COMPLETED, loads linked

### Test Documents

| Document | Size | Description |
|---|---|---|
| CRST_34279_57329910.pdf | 337 KB | CRST rate confirmation with 2 stops (Ontario, CA -> Rialto, CA) |
| RXO_34058_16654538.pdf | 45 KB | RXO rate confirmation with 2 stops (Fontana, CA -> Pomona, CA) |

### Processing Modes

- **Raw Text** (`use_raw_text=True`): Downloads PDF from S3, extracts text via pymupdf, sends plain text to the AI agent
- **PDF Mode** (`use_raw_text=False`): Generates a presigned GET URL and sends the PDF file directly to the AI agent
- **Sync**: Documents processed sequentially via `process_session_sync`
- **Async**: Documents dispatched to parallel workers via `process_session_async` with `process_document_worker`

### Celery Worker Configuration

The test runner uses `--concurrency=2 --pool=threads`, giving 2 parallel worker threads. This allows async mode to process both documents simultaneously. See [celery_production.md](celery_production.md) for production configuration details.

---

## Test Results

### Test 1: `test_multi_document_raw_text_sync`

**Mode:** sync | **use_raw_text:** True

| Document | Status | Processing Time | Load ID | Reference # |
|---|---|---|---|---|
| CRST_34279_57329910.pdf | PARSED | 6.0s | 7 | 57329910 |
| RXO_34058_16654538.pdf | PARSED | 12.0s | 8 | 16654538 |

**Total Time:** 12.03s | **Session Status:** COMPLETED

#### Load: CRST_34279_57329910.pdf

```
Reference #:  57329910
BOL #:        4518755845
Customer:     CRST The Transportation Solution, Inc.
Trailer Type: (not specified)
Status:       pending
```

| Stop # | Action | Address | Place Name | Appointment (UTC) |
|---|---|---|---|---|
| 1 | LL (Live Load) | 2590 Lindsay Privado Dr, ONTARIO, CA 91761 | ACCELERATE360 DISTRIBUTION LLC | 2025-06-26 18:00 |
| 2 | LU (Live Unload) | 1960 Miro Way, RIALTO, CA 92376 | Medline Industries | 2025-06-27 14:00 |

**Notes:**
- Stop 1: Drvr Ld/Unld: Customer Live Load
- Stop 2: Drvr Ld/Unld: Customer Live Unload

#### Load: RXO_34058_16654538.pdf

```
Reference #:  16654538
BOL #:        6671075
Customer:     RXO, Inc.
Trailer Type: LARGE_53
Status:       pending
```

| Stop # | Action | Address | Place Name | Appointment (UTC) | PO Numbers |
|---|---|---|---|---|---|
| 1 | LL (Live Load) | 5309 SIERRA AVENUE, Fontana, CA 92336 | DCG FULFILLMENT - CUTIE PIE BABY | 2025-04-28 19:00 | 30548251, 40547072, 60547072, 70547072, 80547072 |
| 2 | LU (Live Unload) | 2849 FICUS STREET, Pomona, CA 91766 | GILBERT WEST - POMONA | 2025-04-28 23:00 | 30548251, 40547072, 60547072, 70547072, 80547072 |

**Notes:**
- Stop 1: Closes @ 3pm
- Stop 2: THE DRIVER IS REQUIRED TO DROP THE TRAILER FOR A MINIMUIM OF 48-72 HOURS AT DELIVERY. Driver MUST check in at receiver as an RXO Brokerage driver and provide the BM number upon arrival.

---

### Test 2: `test_multi_document_pdf_mode_sync`

**Mode:** sync | **use_raw_text:** False

| Document | Status | Processing Time | Load ID | Reference # |
|---|---|---|---|---|
| CRST_34279_57329910.pdf | PARSED | 6.0s | 3 | 57329910 |
| RXO_34058_16654538.pdf | PARSED | 15.0s | 4 | 16654538 |

**Total Time:** 15.03s | **Session Status:** COMPLETED

#### Load: CRST_34279_57329910.pdf

```
Reference #:  57329910
BOL #:        4518755845
Customer:     CRST The Transportation Solution, Inc.
Trailer Type: (not specified)
Status:       pending
```

| Stop # | Action | Address | Place Name | Appointment (UTC) |
|---|---|---|---|---|
| 1 | LL (Live Load) | 2590 Lindsay Privado Dr, Ontario, CA 91761 | ACCELERATE360 DISTRIBUTION LLC | 2025-06-26 18:00 |
| 2 | LU (Live Unload) | 1960 Miro Way, Rialto, CA 92376 | Medline Industries | 2025-06-27 14:00 |

**Notes:**
- Stop 1: Drvr Ld/Unld: Customer Live Load. Reference Number: 0626251100
- Stop 2: Drvr Ld/Unld: Customer Live Unload

#### Load: RXO_34058_16654538.pdf

```
Reference #:  16654538
BOL #:        6671075
Customer:     RXO, Inc.
Trailer Type: LARGE_53
Status:       pending
```

| Stop # | Action | Address | Place Name | Appointment (UTC) | PO Numbers |
|---|---|---|---|---|---|
| 1 | LL (Live Load) | 5309 Sierra Avenue, Fontana, CA 92336 | DCG FULFILLMENT - CUTIE PIE BABY | 2025-04-28 19:00 | 30548251, 40547072, 60547072, 70547072, 80547072 |
| 2 | LU (Live Unload) | 2849 Ficus Street, Pomona, CA 91766 | GILBERT WEST - POMONA | 2025-04-28 23:00 | 30548251, 40547072, 60547072, 70547072, 80547072 |

**Notes:**
- Stop 2: Driver required to drop trailer for a minimum of 48-72 hours at delivery (drop trailer 2-3 days). Driver must check in as RXO Brokerage driver and provide BM# at delivery.

---

### Test 3: `test_multi_document_raw_text_async`

**Mode:** async | **use_raw_text:** True | **Concurrency:** 2 threads

| Document | Status | Processing Time | Load ID | Reference # |
|---|---|---|---|---|
| CRST_34279_57329910.pdf | PARSED | 6.1s | 1 | 57329910 |
| RXO_34058_16654538.pdf | PARSED | 6.1s | 2 | 16654538 |

**Total Time:** 6.07s | **Session Status:** COMPLETED

Both documents finished at the same time — true parallel processing.

#### Load: CRST_34279_57329910.pdf

```
Reference #:  57329910
BOL #:        4518755845
Customer:     CRST The Transportation Solution, Inc.
Trailer Type: (not specified)
Status:       pending
```

| Stop # | Action | Address | Place Name | Appointment (UTC) |
|---|---|---|---|---|
| 1 | LL (Live Load) | 2590 Lindsay Privado Dr, ONTARIO, CA 91761 | ACCELERATE360 DISTRIBUTION LLC | 2025-06-26 18:00 |
| 2 | LU (Live Unload) | 1960 Miro Way, RIALTO, CA 92376 | Medline Industries | 2025-06-27 14:00 |

**Notes:**
- Stop 1: Drvr Ld/Unld: Customer Live Load; Reference Number: 0626251100
- Stop 2: Drvr Ld/Unld: Customer Live Unload

#### Load: RXO_34058_16654538.pdf

```
Reference #:  16654538
BOL #:        6671075
Customer:     RXO, Inc.
Trailer Type: LARGE_53
Status:       pending
```

| Stop # | Action | Address | Place Name | Appointment (UTC) | PO Numbers |
|---|---|---|---|---|---|
| 1 | LL (Live Load) | 5309 SIERRA AVENUE, Fontana, CA 92336 | DCG FULFILLMENT - CUTIE PIE BABY | 2025-04-28 19:00 | 30548251, 40547072, 60547072, 70547072, 80547072 |
| 2 | LU (Live Unload) | 2849 FICUS STREET, Pomona, CA 91766 | GILBERT WEST - POMONA | 2025-04-28 23:00 | 30548251, 40547072, 60547072, 70547072, 80547072 |

**Notes:**
- Stop 1: Closes @ 3pm. BM number is the pick up number to be used at the shipper and receiver, unless otherwise stated by RXO.
- Stop 2: THE DRIVER IS REQUIRED TO DROP THE TRAILER FOR A MINIMUIM OF 48-72 HOURS AT DELIVERY. Driver MUST check in at receiver as an RXO Brokerage driver and provide the BM number upon arrival.

---

### Test 4: `test_multi_document_pdf_mode_async`

**Mode:** async | **use_raw_text:** False | **Concurrency:** 2 threads

| Document | Status | Processing Time | Load ID | Reference # |
|---|---|---|---|---|
| CRST_34279_57329910.pdf | PARSED | 6.0s | 3 | 57329910 |
| RXO_34058_16654538.pdf | PARSED | 9.0s | 4 | 16654538 |

**Total Time:** 9.02s | **Session Status:** COMPLETED

#### Load: CRST_34279_57329910.pdf

```
Reference #:  57329910
BOL #:        4518755845
Customer:     CRST The Transportation Solution, Inc.
Trailer Type: (not specified)
Status:       pending
```

| Stop # | Action | Address | Place Name | Appointment (UTC) |
|---|---|---|---|---|
| 1 | LL (Live Load) | 2590 Lindsay Privado Dr, ONTARIO, CA 91761 | ACCELERATE360 DISTRIBUTION LLC | 2025-06-26 18:00 |
| 2 | LU (Live Unload) | 1960 Miro Way, RIALTO, CA 92376 | Medline Industries | 2025-06-27 14:00 |

**Notes:**
- Stop 1: Drvr Ld/Unld: Customer Live Load. Reference Number: 0626251100
- Stop 2: Drvr Ld/Unld: Customer Live Unload.

#### Load: RXO_34058_16654538.pdf

```
Reference #:  16654538
BOL #:        BM 6671075
Customer:     RXO, Inc.
Trailer Type: LARGE_53
Status:       pending
```

| Stop # | Action | Address | Place Name | Appointment (UTC) | PO Numbers |
|---|---|---|---|---|---|
| 1 | LL (Live Load) | 5309 SIERRA AVENUE, Fontana, CA 92336 | DCG FULFILLMENT - CUTIE PIE BABY | 2025-04-28 19:00 | 30548251, 40547072, 60547072, 70547072, 80547072 |
| 2 | LU (Live Unload) | 2849 FICUS STREET, Pomona, CA 91766 | GILBERT WEST - POMONA | 2025-04-28 23:00 | 30548251, 40547072, 60547072, 70547072, 80547072 |

**Notes:**
- Stop 2: THE DRIVER IS REQUIRED TO DROP THE TRAILER FOR A MINIMUIM OF 48-72 HOURS AT DELIVERY. Driver MUST check in at receiver as an RXO Brokerage driver and provide the BM number upon arrival. Drop Trailer at Delivery: MINIMUM 2-3 days.

---

## Summary Table

| Test | Mode | use_raw_text | Concurrency | CRST Time | RXO Time | Total Time | Result |
|---|---|---|---|---|---|---|---|
| test_multi_document_raw_text_sync | sync | True | — | 6.0s | 12.0s | 12.03s | PASS |
| test_multi_document_pdf_mode_sync | sync | False | — | 6.0s | 15.0s | 15.03s | PASS |
| test_multi_document_raw_text_async | async | True | 2 threads | 6.1s | 6.1s | **6.07s** | PASS |
| test_multi_document_pdf_mode_async | async | False | 2 threads | 6.0s | 9.0s | 9.02s | PASS |

### Sync vs Async Comparison

| Processing Type | Raw Text Total | PDF Mode Total | Notes |
|---|---|---|---|
| Sync (sequential) | 12.03s | 15.03s | Documents processed one after the other |
| Async (2 threads) | **6.07s** | **9.02s** | Documents processed in parallel |
| **Speedup** | **50%** | **40%** | Async cuts total time roughly in half |

### Observations

- **Async with concurrency=2 is the fastest mode** — raw_text async finished in 6.07s (vs 12.03s sync), a 50% speedup
- **Both documents finish simultaneously in raw_text async** — CRST and RXO both completed at 6.1s, proving true parallelism
- **Raw text mode is consistently faster than PDF mode** — extracting text locally with pymupdf and sending plain text is cheaper than having the LLM process a full PDF binary
- **CRST document** (~6s) always processes faster than RXO (~6-15s), despite being 7x larger by file size — the CRST PDF has a simpler layout
- **Sync mode ignores concurrency** — sync processes documents sequentially regardless of worker count
- Minor variation in BOL extraction between modes: raw text extracted `6671075`, PDF mode sometimes extracted `BM 6671075` for the RXO document
- All sessions reached COMPLETED status with 100% document parse rate

---

## Running the Tests

```bash
# Run all multi-document workflow tests (requires celery)
uv run python manage.py test machtms.backend.RateConParser.tests.test_parsing_workflow --use-celery -v 2

# Run individual tests
uv run python manage.py test machtms.backend.RateConParser.tests.test_parsing_workflow.MultiDocumentWorkflowTests.test_multi_document_raw_text_sync --use-celery -v 2
uv run python manage.py test machtms.backend.RateConParser.tests.test_parsing_workflow.MultiDocumentWorkflowTests.test_multi_document_pdf_mode_sync --use-celery -v 2
uv run python manage.py test machtms.backend.RateConParser.tests.test_parsing_workflow.MultiDocumentWorkflowTests.test_multi_document_raw_text_async --use-celery -v 2
uv run python manage.py test machtms.backend.RateConParser.tests.test_parsing_workflow.MultiDocumentWorkflowTests.test_multi_document_pdf_mode_async --use-celery -v 2
```

### Requirements
- `OPENAI_API_KEY` environment variable
- `AWS_ACCESS_KEY` environment variable
- `test_documents/` directory with PDF files at the project root
- Celery broker (started automatically via `--use-celery` flag)
- Test runner configured with `--concurrency=2 --pool=threads` in `api/runner.py`
