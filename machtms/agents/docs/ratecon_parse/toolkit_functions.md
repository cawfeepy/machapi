# Toolkit Functions: stops.py & loads.py

> The toolkits are the hands and feet of the agent system. They reach into the database, pull out the data the agents need, and push new records back in. Without them, the agents would be all brains and no muscle.

---

## What Are Toolkits?

In the Agno framework, a **Toolkit** is a class that bundles related functions together and registers them so that agents can call them as tools. Think of a toolkit as a specialized employee at a company -- each one has a job title and a set of skills.

Every toolkit:

1. Extends `agno.tools.Toolkit`
2. Registers its methods in `__init__` via `self.register(self.method_name)`
3. Accepts a `RunContext` as the first argument to each registered method, which provides organizational scoping and session metadata

**Why does this matter?** Because agents don't have direct database access. They describe *what* they want (in natural language), and the toolkit methods are the bridge that translates those intentions into actual Django ORM queries.

---

## StopHistoryToolkit (stops.py)

**File:** `machtms/agents/toolkit/stops.py`

**Registered name:** `stop_history_toolkit`

This toolkit answers a deceptively important question: *"What usually happens at this address?"*

### Why does stop history matter?

Imagine a warehouse at 123 Industrial Blvd. Every single time a truck goes there, it's for a LIVE LOAD (LL). A rate confirmation PDF won't always spell out "this is a live load" -- it might just list the address and a date. The stop history toolkit lets agents look at past behavior and say, "Every time we've been here, it's been a live load. Let's go with that."

Without stop history, the agent would have to guess. With it, the agent has data-driven confidence.

---

### get_similar_stops_for_address()

**What it does:** Fetches the most recent stops at a given address, formatted as human-readable text.

**When is it called?** During rate con parsing, when the agent needs to figure out what action code to assign to a stop. This is the "let me check the records" step.

```python
def get_similar_stops_for_address(
    self,
    run_context: RunContext,
    address_id: int,
    limit: int = 5,
) -> str
```

| Parameter    | Type         | Default | Description                                    |
|-------------|-------------|---------|------------------------------------------------|
| run_context | RunContext   | --      | Provides `organization` for scoping queries     |
| address_id  | int          | --      | The address ID to look up                       |
| limit       | int          | 5       | Maximum number of recent stops to return        |

**Returns:** A formatted string listing recent stops, including stop number, action display name, action code, and date. If no stops are found, returns a "no previous stops" message.

**Example output:**
```
Recent stops at address ID 42:
  Stop #1: LIVE LOAD (LL) | Date: 01/15/2025 08:00 AM
  Stop #2: LIVE LOAD (LL) | Date: 01/10/2025 09:30 AM
  Stop #1: LIVE LOAD (LL) | Date: 01/05/2025 07:00 AM
```

**How the query works:**

1. Filters `Stop` objects by `organization` and `address_id`
2. Uses `select_related('address')` to avoid N+1 queries
3. Orders by `-timestamp` (most recent first) and slices by `limit`
4. Formats each stop into a human-readable line

> **What if the address has never been visited before?** The method returns `"No previous stops found at address ID {address_id}."` -- and the agent falls back to default logic (first stop = LL, last stop = LU).

---

### get_action_code_frequency()

**What it does:** Counts how often each action code has been used at an address and suggests the most common one. This is the statistical sibling of `get_similar_stops_for_address`.

**What problem does this solve?** Sometimes an address has been visited 50 times -- 47 times as LIVE LOAD and 3 times as HOOK LOADED. Rather than listing all 50, this method distills it down to: "LL has been used 47 times, HL 3 times. Suggested action: LL."

```python
def get_action_code_frequency(
    self,
    run_context: RunContext,
    address_id: int,
    limit: int = 10,
) -> str
```

| Parameter    | Type         | Default | Description                                          |
|-------------|-------------|---------|------------------------------------------------------|
| run_context | RunContext   | --      | Provides `organization` for scoping queries           |
| address_id  | int          | --      | The address ID to look up                             |
| limit       | int          | 10      | Number of recent stops to consider for the frequency  |

**Returns:** A JSON string with the following structure:

```json
{
    "address_id": 42,
    "has_history": true,
    "suggested_action": "LL",
    "action_counts": {
        "LL": 8,
        "HL": 2
    }
}
```

**How the query works (and why it's a two-step process):**

1. **Step 1:** Fetches the PKs of the most recent `limit` stops at the address. This is a separate query because Django doesn't allow `.annotate()` on a sliced queryset directly.
2. **Step 2:** Filters by those PKs, groups by `action`, counts each group, and orders by most common.
3. The most common action becomes `suggested_action`.

> **Why return JSON instead of formatted text?** Because this method is designed for *agents* to consume programmatically. The agent parses the JSON, reads `suggested_action`, and uses it to make decisions. Contrast this with `get_similar_stops_for_address`, which is more of a "show me the details" function.

---

### Quick Reference: Action Codes

These are the action codes used in the Stop model, and they show up constantly in toolkit return values:

| Code   | Display Name   | Meaning                                |
|--------|---------------|----------------------------------------|
| `LL`   | LIVE LOAD      | Driver waits while trailer is loaded    |
| `LU`   | LIVE UNLOAD    | Driver waits while trailer is unloaded  |
| `HL`   | HOOK LOADED    | Pick up a pre-loaded trailer            |
| `LD`   | DROP LOADED    | Drop off a loaded trailer               |
| `EMPP` | EMPTY PICKUP   | Pick up an empty trailer                |
| `EMPD` | EMPTY DROP     | Drop off an empty trailer               |
| `HUBP` | HUB PICKUP     | Pick up from a hub location             |
| `HUBD` | HUB DROPOFF    | Drop off at a hub location              |

---

## LoadToolkit (loads.py)

**File:** `machtms/agents/toolkit/loads.py`

**Registered name:** `load_toolkit`

The LoadToolkit is the workhorse of the agent system. It handles everything from browsing today's schedule to creating brand-new loads from parsed rate confirmations. For the ratecon parsing pipeline, two methods are especially important: `create_load_from_parsed` and `update_ratecon_document_status`.

> Think of the LoadToolkit as the "shipping desk" -- it can look up loads, create new ones, and stamp documents as processed.

---

### Helper: _format_load() (private)

Before diving into the registered methods, it's worth understanding this private helper that several methods rely on.

```python
@staticmethod
def _format_load(load, display_tz, include_date=False) -> str
```

**What it does:** Takes a Load instance (with prefetched legs, stops, and assignments) and turns it into a nicely formatted string. It's the "pretty printer" for loads.

**Output structure:**
```
Load REF-123 | Customer: ACME Corp | Status: Pending | Billing: Pending Delivery
  Leg 1: Driver: John Doe | Carrier: Swift Transport
    Stop 1: LIVE LOAD @ 123 Main St, Chicago, IL 60601 | 08:00 AM PST
    Stop 2: LIVE UNLOAD @ 456 Oak Ave, Dallas, TX 75201 | 04:00 PM PST
```

---

### Helper: _base_queryset() (private)

```python
@staticmethod
def _base_queryset(organization) -> QuerySet
```

**What it does:** Returns a reusable, organization-scoped queryset with all the right `select_related` and `prefetch_related` calls baked in. Every public query method calls this to avoid duplicating prefetch logic.

**Why is this important?** Without these prefetches, displaying a load with 2 legs and 4 stops would trigger dozens of individual database queries. This method ensures everything gets loaded in a handful of efficient queries.

---

### create_load_from_parsed()

This is the star of the ratecon pipeline. It's how a parsed rate confirmation becomes an actual load in the system.

**What problem does it solve?** After the ratecon agents have parsed a PDF, resolved addresses, identified customers, and figured out stop actions, they need to actually *create* the load. This method is the final handoff from "parsed data" to "real database record."

```python
def create_load_from_parsed(
    self,
    run_context: RunContext,
    payload_json: str,
) -> str
```

| Parameter     | Type        | Description                                           |
|--------------|------------|-------------------------------------------------------|
| run_context  | RunContext  | Provides `organization` for scoping                    |
| payload_json | str         | JSON string matching the `RateConLoadPayload` schema   |

**Returns:** A confirmation string with formatted load details on success, or validation error messages on failure.

**How it works, step by step:**

1. **Validate with Pydantic:** The JSON string is parsed through `RateConLoadPayload.model_validate_json()`. This catches structural issues early -- missing fields, wrong types, etc.
2. **Strip metadata fields:** `celery_task_id` and `ratecon_document_id` are excluded from the payload via `model_dump(exclude=...)`. These fields are metadata about the parsing process, not part of the load itself.
3. **Delegate to `create_load()`:** The cleaned payload is serialized back to JSON and passed to the general-purpose `create_load()` method, which handles the Django serializer validation and database write.

> **Why the two-step validation?** Pydantic validates the *shape* of the data (correct types, required fields). The Django serializer validates the *business logic* (does this customer ID exist? Is "LL" a valid action?). Together, they form a validation sandwich that catches errors at both the structural and domain levels.

**Example payload:**
```json
{
    "customer": 5,
    "reference_number": "RC-2025-001",
    "bol_number": "BOL-789",
    "trailer_type": "LARGE_53",
    "status": "pending",
    "billing_status": "pending_delivery",
    "legs": [{
        "stops": [
            {
                "stop_number": 1,
                "address": 12,
                "action": "LL",
                "start_range": "2025-06-15T08:00:00Z",
                "po_numbers": "PO-1234, PO-5678",
                "driver_notes": ""
            },
            {
                "stop_number": 2,
                "address": 34,
                "action": "LU",
                "start_range": "2025-06-16T14:00:00Z",
                "po_numbers": "",
                "driver_notes": "Call receiver 30 min before arrival"
            }
        ]
    }],
    "celery_task_id": "abc-123-def",
    "ratecon_document_id": 42
}
```

---

### update_ratecon_document_status()

**What it does:** After a load is successfully created from a rate confirmation, this method links the two together by updating the `ParsedRateCon` record with the new load's ID.

**Why does this matter?** Without this link, you'd have no way to trace a load back to the rate confirmation that created it. It's the "receipt" step -- proof that this load came from that document.

```python
def update_ratecon_document_status(
    self,
    run_context: RunContext,
    ratecon_document_id: int,
    load_id: int,
) -> str
```

| Parameter            | Type        | Description                                                |
|---------------------|------------|------------------------------------------------------------|
| run_context         | RunContext  | Provides organizational context (not directly used here)    |
| ratecon_document_id | int         | The RateConDocument ID whose ParsedRateCon should be updated |
| load_id             | int         | The Load ID to associate with the parsed content             |

**Returns:** A success confirmation or error message if the `ParsedRateCon` record doesn't exist.

**How it works:**

1. Looks up `ParsedRateCon` by `document_id`
2. Sets its `load_id` field to the newly created load
3. Saves only the `load_id` field (via `update_fields` for efficiency)

> **What if the ParsedRateCon doesn't exist?** The method returns a clear error string rather than raising an exception. This is important because toolkit methods are called by AI agents -- exceptions would crash the agent run, while error strings let the agent handle the situation gracefully.

---

### create_load() (general purpose)

While not specific to ratecon parsing, this is the underlying method that `create_load_from_parsed` delegates to. It's the general-purpose load creation tool.

```python
def create_load(
    self,
    run_context: RunContext,
    payload_json: str,
) -> str
```

**What it does:**

1. Parses the JSON string
2. Creates a mock `request` object with the organization ID (needed by `CurrentOrganizationDefault` in the serializer)
3. Validates through `LoadSerializer`
4. Saves the load and all nested relations (legs, stops, shipment assignments)
5. Returns a formatted confirmation or validation errors

> **Why the mock request?** Django REST Framework serializers typically get organization context from `request.user` or `request.organization`. Since toolkit calls come from agents (not HTTP requests), a `SimpleNamespace` mock stands in with just enough attributes to satisfy the serializer's `CurrentOrganizationDefault` field.

---

### Other LoadToolkit Methods (non-ratecon)

For completeness, here are the other registered methods. They're not part of the ratecon pipeline but are available to agents:

**`get_todays_loads(run_context)`** -- Fetches all loads with a pickup stop scheduled for today (Pacific Time). Useful for the dispatch agent's daily overview.

**`search_loads(run_context, ...)`** -- Multi-criteria search supporting customer name, carrier name, driver name, street address, load status, and billing status. Returns up to 25 results. All text filters are case-insensitive partial matches.

---

## How These Toolkits Fit in the Ratecon Pipeline

Here's where each ratecon-relevant toolkit method gets called in the overall parsing flow:

```
PDF uploaded
    |
    v
Rate Con Processor Agent (parses text into ParsedRateConData)
    |
    v
Rate Con Load Creator Agent
    |
    +---> StopHistoryToolkit.get_action_code_frequency()
    |         "What action code is most common at this address?"
    |
    +---> StopHistoryToolkit.get_similar_stops_for_address()
    |         "Show me recent stops at this address for context"
    |
    +---> LoadToolkit.create_load_from_parsed()
    |         "Create the load from the resolved data"
    |
    +---> LoadToolkit.update_ratecon_document_status()
              "Link the new load back to the source document"
```

> **The big picture:** The StopHistoryToolkit provides *intelligence* (what should we do at this address?), while the LoadToolkit provides *action* (create the load, update the record). Together, they're the execution layer that turns parsed PDFs into real, trackable shipments.
