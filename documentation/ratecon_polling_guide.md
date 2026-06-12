# Rate Con Polling Guide

> How the frontend keeps tabs on document processing without losing its mind.

---

## The Big Picture

When a user uploads rate confirmation PDFs, each document gets parsed by an AI agent running in a Celery worker. That takes a few seconds per document — an eternity in browser-time. So the frontend needs to **poll** the backend until every document reaches a terminal state.

Here is the full lifecycle in one breath:

```
Request Presigned URLs
  → Upload PDFs to S3
    → Create Session (send entrypoint IDs)
      → Trigger Processing
        → Poll Sessions List  →  Poll Session Detail  →  All done? Stop.
```

---

## The Upload Flow (Before Polling Starts)

Before any polling happens, the frontend completes a 4-step upload flow.

```
Step 1  POST /ratecon/presigned-urls/
        Body: { "files": [{ "filename": "rc.pdf", "mime_type": "application/pdf" }] }
        → Returns: [{ "id": 1, "presigned_url": "https://s3...", "s3_key": "uuid.pdf", ... }]

Step 2  PUT <presigned_url>   (one per file — direct to S3, Django not involved)

Step 3  POST /ratecon/sessions/from-presigned/
        Body: { "entrypoint_ids": [1, 2, 3] }
        → Returns: { "session_id": 42, "documents": [...] }

Step 4  POST /ratecon/sessions/42/process-pdf/
        Body: { "mode": "async" }
        → Returns: 202 Accepted
```

After step 4, Celery workers pick up the documents and polling begins.

---

## The Two Polling Endpoints

### 1. Session List — for showing the upload panel

```
GET /ratecon/sessions/list/
```

Returns up to **8 non-hidden sessions**, newest first, each with nested `documents`. Use this to populate the upload panel sidebar or history view. Because documents are included, polling this endpoint is sufficient for showing per-document status without a separate detail request.

**Response shape:**
```json
[
  {
    "id": 42,
    "organization": 5,
    "status": "processing",
    "is_hidden": false,
    "created_at": "2026-03-01T10:00:00Z",
    "updated_at": "2026-03-01T10:01:00Z",
    "total_documents": 3,
    "progress": 33.3,
    "documents": [
      {
        "id": 10,
        "status": "parsed",
        "original_filename": "ratecon_abc.pdf",
        "load": 88,
        "classification_passed": true
      }
    ]
  },
  {
    "id": 41,
    "organization": 5,
    "status": "completed",
    "is_hidden": false,
    "created_at": "2026-03-01T09:00:00Z",
    "updated_at": "2026-03-01T09:05:00Z",
    "total_documents": 2,
    "progress": 100.0,
    "documents": []
  }
]
```

### 2. Session Detail — for showing individual document statuses

```
GET /ratecon/sessions/<session_id>/
```

Returns the session plus all its nested documents. Use this when you need to show per-document status, load links, or error messages.

**Response shape:**
```json
{
  "id": 42,
  "organization": 5,
  "status": "processing",
  "is_hidden": false,
  "created_at": "2026-03-01T10:00:00Z",
  "updated_at": "2026-03-01T10:01:00Z",
  "total_documents": 3,
  "progress": 33.3,
  "documents": [
    {
      "id": 10,
      "organization": 5,
      "session": 42,
      "status": "parsed",
      "original_filename": "ratecon_abc.pdf",
      "s3_key": "a1b2c3d4-uuid.pdf",
      "file_size": 204800,
      "mime_type": "application/pdf",
      "error_message": "",
      "celery_task_id": "task-uuid-123",
      "processed_at": "2026-03-01T10:03:00Z",
      "created_at": "2026-03-01T10:00:30Z",
      "updated_at": "2026-03-01T10:03:00Z",
      "load": 88,
      "classification_passed": true,
      "classification_reason": ""
    },
    {
      "id": 11,
      "organization": 5,
      "session": 42,
      "status": "processing",
      "original_filename": "ratecon_def.pdf",
      "s3_key": "b2c3d4e5-uuid.pdf",
      "file_size": 153600,
      "mime_type": "application/pdf",
      "error_message": "",
      "celery_task_id": "task-uuid-456",
      "processed_at": null,
      "created_at": "2026-03-01T10:00:35Z",
      "updated_at": "2026-03-01T10:01:00Z",
      "load": null,
      "classification_passed": null,
      "classification_reason": ""
    },
    {
      "id": 12,
      "organization": 5,
      "session": 42,
      "status": "misclassified",
      "original_filename": "invoice_xyz.pdf",
      "s3_key": "c3d4e5f6-uuid.pdf",
      "file_size": 102400,
      "mime_type": "application/pdf",
      "error_message": "",
      "celery_task_id": "task-uuid-789",
      "processed_at": "2026-03-01T10:04:00Z",
      "created_at": "2026-03-01T10:00:45Z",
      "updated_at": "2026-03-01T10:04:00Z",
      "load": null,
      "classification_passed": false,
      "classification_reason": "This document appears to be an invoice, not a rate confirmation."
    }
  ]
}
```

---

## Key Fields for Polling Logic

### Session-level fields

| Field | What It Tells You |
|---|---|
| `status` | `"uploading"`, `"processing"`, `"completed"`, `"partially_failed"`, `"failed"` |
| `progress` | 0.0 to 100.0 — percentage of docs in a terminal state |
| `total_documents` | Total number of documents in this session |
| `is_hidden` | Whether this session is hidden from the list view |

### Document-level fields

| Field | What It Tells You |
|---|---|
| `status` | `"pending"`, `"processing"`, `"parsed"`, `"misclassified"`, `"failed"` |
| `load` | Integer FK to the created Load, or `null` if not yet linked |
| `classification_passed` | `true` = valid rate con, `false` = rejected, `null` = not yet processed |
| `classification_reason` | Why the agent rejected the doc (empty string if passed) |
| `error_message` | Set if `status` is `"failed"` — explains what went wrong |
| `processed_at` | Timestamp when processing completed, or `null` if still in progress |

---

## Terminal States

**Session-level** — stop polling when `status` is one of:
- `"completed"` — all docs parsed or misclassified (none failed)
- `"partially_failed"` — some succeeded, some failed
- `"failed"` — everything failed

**Document-level** — a doc is done when its `status` is one of:
- `"parsed"` — successfully parsed, load created and linked (`load` FK is set)
- `"misclassified"` — the agent decided this is not a rate con
- `"failed"` — something went wrong (check `error_message`)

> **Pro tip:** You can also check `progress === 100.0` to know all docs are done, regardless of individual outcomes.

---

## When to Stop Polling

```js
const SESSION_TERMINAL = ["completed", "partially_failed", "failed"];

const isSessionDone = (session) =>
  SESSION_TERMINAL.includes(session.status) || session.progress === 100.0;
```

---

## Polling Strategy: Which Endpoint to Use When

| Scenario | Endpoint | Reason |
|---|---|---|
| Showing the upload panel with multiple sessions | `GET /sessions/list/` | One request covers all active sessions with nested documents |
| Tracking progress of the session the user just submitted | `GET /sessions/list/` | Contains `progress` and `documents` for all sessions |
| Showing per-document breakdown for a specific session | `GET /sessions/list/` | Documents are now nested in the list response |
| Navigating back to a completed session | `GET /sessions/<id>/` | Detail view returns the same shape; useful for direct deep-links |

**Avoid polling `GET /sessions/<id>/` for multiple sessions at once** — that would be N+1 requests. Use `GET /sessions/list/` to monitor all sessions, including per-document status, in a single request.

---

## React Implementation Examples

### Example 1: TanStack Query (Recommended)

TanStack Query makes polling almost embarrassingly easy. The `refetchInterval` option accepts a function — return `false` to stop, return a number to keep going.

```tsx
import { useQuery } from "@tanstack/react-query";

const SESSION_TERMINAL = ["completed", "partially_failed", "failed"];

// Poll the session list (for the upload panel)
function useSessionListPolling() {
  return useQuery({
    queryKey: ["ratecon-sessions"],
    queryFn: () =>
      fetch("/api/ratecon/sessions/list/").then((r) => r.json()),

    // Poll every 3 seconds while any session is still processing
    refetchInterval: (query) => {
      const sessions: Session[] = query.state.data ?? [];
      const anyActive = sessions.some(
        (s) => !SESSION_TERMINAL.includes(s.status)
      );
      return anyActive ? 3_000 : false;
    },

    refetchIntervalInBackground: true,
  });
}

// Poll a specific session detail (when user drills in)
function useSessionDetailPolling(sessionId: number) {
  return useQuery({
    queryKey: ["ratecon-session", sessionId],
    queryFn: () =>
      fetch(`/api/ratecon/sessions/${sessionId}/`).then((r) => r.json()),

    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return SESSION_TERMINAL.includes(status) ? false : 3_000;
    },

    refetchIntervalInBackground: true,
  });
}
```

**Upload panel component:**
```tsx
function UploadPanel() {
  const { data: sessions = [], isLoading } = useSessionListPolling();

  if (isLoading) return <p>Loading...</p>;

  return (
    <div>
      {sessions.map((session) => (
        <SessionRow key={session.id} session={session} />
      ))}
    </div>
  );
}

function SessionRow({ session }: { session: Session }) {
  return (
    <div>
      <span>Session {session.id}</span>
      <span>{session.status}</span>
      <progress value={session.progress} max={100} />
      <span>
        {session.documents.filter(d => ["parsed","misclassified","failed"].includes(d.status)).length} / {session.total_documents} documents
      </span>
    </div>
  );
}
```

**Session detail component (with per-document view):**
```tsx
function SessionDetail({ sessionId }: { sessionId: number }) {
  const { data, isLoading } = useSessionDetailPolling(sessionId);

  if (isLoading || !data) return <p>Loading...</p>;

  return (
    <div>
      <h2>Session {sessionId}</h2>
      <p>Status: {data.status}</p>
      <progress value={data.progress} max={100} />

      {data.documents.map((doc) => (
        <div key={doc.id}>
          <span>{doc.original_filename}</span>
          <span>{doc.status}</span>

          {doc.status === "parsed" && doc.load && (
            <a href={`/loads/${doc.load}`}>View Load #{doc.load}</a>
          )}

          {doc.status === "misclassified" && (
            <span title={doc.classification_reason}>Not a rate con</span>
          )}

          {doc.status === "failed" && (
            <span title={doc.error_message}>Failed</span>
          )}

          {doc.classification_passed === null && doc.status === "processing" && (
            <span>Processing...</span>
          )}
        </div>
      ))}
    </div>
  );
}
```

### Example 2: SWR

```tsx
import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then((r) => r.json());
const TERMINAL = ["completed", "partially_failed", "failed"];

function useSessionListPolling() {
  return useSWR("/api/ratecon/sessions/list/", fetcher, {
    refreshInterval: (sessions) => {
      if (!sessions) return 3_000;
      const anyActive = sessions.some((s) => !TERMINAL.includes(s.status));
      return anyActive ? 3_000 : 0;
    },
  });
}

function useSessionDetailPolling(sessionId: number) {
  return useSWR(`/api/ratecon/sessions/${sessionId}/`, fetcher, {
    refreshInterval: (data) => {
      if (data && TERMINAL.includes(data.status)) return 0;
      return 3_000;
    },
  });
}
```

### Example 3: Custom Hook (Zero Dependencies)

```tsx
import { useState, useEffect, useRef, useCallback } from "react";

function usePolling<T>(
  fetchFn: () => Promise<T>,
  interval: number,
  shouldStop: (data: T) => boolean
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const stopped = useRef(false);

  const poll = useCallback(async () => {
    try {
      const result = await fetchFn();
      setData(result);
      setLoading(false);
      if (shouldStop(result)) stopped.current = true;
    } catch (err) {
      setError(err as Error);
      setLoading(false);
    }
  }, [fetchFn, shouldStop]);

  useEffect(() => {
    stopped.current = false;
    poll();
    const id = setInterval(() => {
      if (!stopped.current) poll();
    }, interval);
    return () => clearInterval(id);
  }, [poll, interval]);

  return { data, loading, error };
}

// Usage
const TERMINAL = ["completed", "partially_failed", "failed"];

function UploadPanel() {
  const { data: sessions, loading } = usePolling(
    () => fetch("/api/ratecon/sessions/list/").then((r) => r.json()),
    3_000,
    (sessions) => sessions.every((s) => TERMINAL.includes(s.status))
  );

  if (loading || !sessions) return <p>Loading...</p>;

  return (
    <ul>
      {sessions.map((s) => (
        <li key={s.id}>
          {s.id} — {s.status} — {s.progress}%
        </li>
      ))}
    </ul>
  );
}
```

---

## Hiding a Completed Session

When the user dismisses a session from the upload panel:

```
POST /ratecon/sessions/<session_id>/hide/
```

**Response (200):**
```json
{
  "session_id": 42,
  "is_hidden": true
}
```

The session no longer appears in `GET /ratecon/sessions/list/`. The session and its documents are not deleted — they remain in the database for audit purposes.

---

## Library Comparison

| Library | Polling Config | Dynamic Stop | Bundle | Best For |
|---|---|---|---|---|
| **TanStack Query** | `refetchInterval: (query) => ...` | Return `false` | ~13 KB | Full-featured apps |
| **SWR** | `refreshInterval: (data) => ...` | Return `0` | ~12 KB | Lightweight / Next.js |
| **RTK Query** | `pollingInterval: 3000` | Via component state only | Part of RTK | Redux apps |
| **Custom hook** | `setInterval` | Full control | 0 KB | Minimal dependencies |

**Recommendation:** TanStack Query. Its `refetchInterval` function signature was designed for exactly this use case — "poll until some condition is met, then stop."

---

## Tips and Gotchas

**Use `GET /sessions/list/` for the panel, `GET /sessions/<id>/` for the detail.**
The list endpoint covers all active sessions in one request. Only fetch session detail when the user needs to see individual document status.

**Pick the right interval.** 3 seconds is a solid default. Each document takes 5–15 seconds with the AI agent, so polling faster than 2 s wastes bandwidth; slower than 5 s makes the UI feel laggy.

**Handle partial failures gracefully.** When `status` is `"partially_failed"`, some documents succeeded and some did not. Show the user which ones worked (check each doc's `status`) and consider offering a reprocess option for the failed ones.

**The `classification_passed` field has three states.** `null` means the document has not been processed yet. `true` means it is a valid rate con. `false` means the AI rejected it — check `classification_reason` for the explanation.

**The `load` field is your success signal.** When a document has `status: "parsed"` and `load: 88`, a Load was created in the system. Link the user directly to that load's detail page.

**Progress bar math is done server-side.** The `progress` field (0.0 to 100.0) is computed by the backend. Just plug it into a `<progress>` element.

**Poll in the background.** Set `refetchIntervalInBackground: true` (TanStack Query) so polling continues while the user switches tabs. They come back to a finished result instead of a stale spinner.
