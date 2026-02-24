# The Agent Pipeline: How Rate Cons Become Loads

> Someone uploads a PDF. Moments later, a fully structured load appears in the system -- addresses resolved, stop actions inferred, customer matched. How does that happen? Two AI agents, working in sequence, each with a very specific job.

---

## The Big Picture

The ratecon parsing pipeline has two agents that run back-to-back:

```
                    PDF Text
                       |
                       v
            +-----------------------+
            | Rate Con Processor    |
            | (the reader)          |
            +-----------------------+
                       |
              ParsedRateConData
                       |
                       v
            +-----------------------+
            | Rate Con Load Creator |
            | (the builder)         |
            +-----------------------+
                       |
                       v
                  Load in DB
```

**Why two agents instead of one?** Separation of concerns. The processor is a text extraction specialist -- it reads PDFs and pulls out structured data. The load creator is a database operations specialist -- it resolves foreign keys, checks historical data, and creates records. Combining them into one agent would create a monolith that's harder to test, debug, and improve.

Think of it like a restaurant: the processor is the prep cook (clean, chop, organize the ingredients), and the load creator is the line cook (take those prepped ingredients and turn them into a finished dish).

---

## Agent 1: Rate Con Processor

**File:** `machtms/agents/members/rate_con_processor.py`

**Model:** `gpt-5.2` (OpenAI)

**Toolkits:** None -- this agent is purely text-in, text-out.

**History:** Disabled (`add_history_to_context=False`) -- each document is processed independently.

### What does it solve?

Rate confirmation PDFs come in every imaginable format. Some are clean and structured. Others look like someone typed them in Word, printed them, scanned them, and then faxed them. The Rate Con Processor takes raw text extracted from these documents and normalizes it into a consistent, predictable structure.

### The Two-Task Approach

The processor performs exactly two tasks on every document, in order:

#### Task 1: Classification -- Is This Actually a Rate Confirmation?

Before extracting anything, the agent first asks: *"Is this document even a rate confirmation?"*

A valid rate confirmation typically contains:
- A reference or load number
- Pickup and delivery addresses
- Appointment times or dates
- Rate/payment information
- Carrier or broker information

**Output:** Either `CLASSIFICATION: PASS` or `CLASSIFICATION: FAIL` with a reason.

> **What if we skipped classification?** We'd waste processing time on insurance certificates, BOL copies, delivery receipts, and other documents that people accidentally upload. Worse, the load creator would try to create loads from nonsensical data. Classification is the bouncer at the door.

**If FAIL:** The agent stops here. No extraction. No load creation. The document is flagged and the reason is recorded.

#### Task 2: Extraction -- Pull Out the Data

If the document passes classification, the agent extracts data into a rigid template. The template has four sections:

**Basic Info:**
```
Reference Number: RC-2025-001
BOL Number: BOL-789
Customer Name: ACME Freight Solutions
Trailer Type: 53' Dry Van
```

**Financial Info:**
```
Line Haul Rate: $2,500.00
Fuel Surcharge: $375.00
Total Rate: $2,875.00
```

> Note: The agent is instructed to only include *confirmed, real charges*. No speculative accessorials, no "possible detention" fees. If it's not explicitly on the rate con, it doesn't get extracted.

**Stops:**
```
Stop 1:
  Type: PICKUP
  Street Address: 1234 Distribution Way
  City: Los Angeles
  State: CA
  Zip: 90001
  Appointment: 06/15/2025 08:00
  PO Numbers: PO-1234, PO-5678
  Notes: Check in at Gate B

Stop 2:
  Type: DELIVERY
  Street Address: 5678 Warehouse Blvd
  City: Dallas
  State: TX
  Zip: 75201
  Appointment: 06/16/2025 14:00
  PO Numbers: NONE
  Notes: Call receiver 30 min before arrival
```

**Invoicing:**
```
Invoice Email (Standard Pay): ap@customer.com
Invoice Email (Quick Pay): quickpay@customer.com
```

### Key Design Decisions

**Why UNKNOWN instead of empty strings?** It makes it explicitly clear to the downstream agent that a value was not found, rather than leaving ambiguity about whether it was empty on the document or simply missed.

**Why a rigid template instead of JSON?** The processor outputs text, not structured data. This is intentional. The text template is easier for the LLM to produce reliably and is parsed downstream into the `ParsedRateConData` Pydantic model (see [pydantic_models.md](pydantic_models.md)).

**Why no tools?** The processor only reads text. It doesn't need to query the database, search for addresses, or create records. Giving it tools would introduce unnecessary complexity and the risk of unintended side effects during what should be a pure extraction step.

---

## Agent 2: Rate Con Load Creator

**File:** `machtms/agents/members/ratecon_load_creator.py`

**Model:** `gpt-5.2` (OpenAI)

**History:** Disabled (`add_history_to_context=False`)

**Toolkits:** Four of them -- this agent is fully armed.

| Toolkit              | Purpose                                          |
|---------------------|--------------------------------------------------|
| `LoadToolkit`        | Create loads, update document status              |
| `AddressToolkit`     | Search for and create addresses                   |
| `CustomerToolkit`    | Search for customers by name                      |
| `StopHistoryToolkit` | Check what action codes are common at an address   |

### What does it solve?

The processor gave us raw data: "Customer Name: ACME Freight Solutions", "Street Address: 1234 Distribution Way", "Type: PICKUP". But the database doesn't store customer names -- it stores customer IDs. It doesn't store street addresses as strings -- it stores address foreign keys. And it doesn't understand "PICKUP" -- it needs "LL" or "HL" or "EMPP".

The load creator bridges that gap. It takes human-readable parsed data and resolves everything into database-ready values.

> **What if we didn't have this agent?** Someone would have to manually look up every customer, every address, and decide every action code. For a single load with 2 stops, that's a minimum of 5 database lookups and 2 judgment calls. Multiply that by dozens of rate cons per day, and you've got a full-time job that's now automated.

---

### The 8-Step Workflow

This is the heart of the load creation process. Each step is explicitly defined in the agent's instructions:

#### Step 1: Resolve Customer

```
Parsed data says:  "Customer Name: ACME Freight Solutions"
Agent calls:       search_customers(name="ACME Freight Solutions")
Result:            Customer ID 5, or null if not found
```

The agent uses `CustomerToolkit.search_customers()` with a case-insensitive partial match. If the customer exists, it grabs the ID. If not, the customer field is set to `null` -- the load still gets created, it just won't be linked to a customer yet.

> **Why not auto-create missing customers?** Because customer creation involves details beyond a name (payment terms, contact info, billing addresses). Creating a half-empty customer record would cause more problems than it solves.

#### Step 2: Resolve Addresses

For each stop in the parsed data:

```
1. Search: search_addresses(street="1234 Distribution Way", city="Los Angeles", state="CA", zip="90001")
2. If not found: ensure_address(street="1234 Distribution Way", city="Los Angeles", state="CA", zip_code="90001")
3. Result: Address ID 12
```

`ensure_address()` is a `get_or_create` operation -- it either finds an exact match or creates a new one. This prevents duplicate addresses from piling up while still handling new locations automatically.

#### Step 3: Determine Stop Actions

This is where it gets interesting. Rate confirmations speak in simple terms: "PICKUP" or "DELIVERY." But the TMS has 8 different action codes:

| Code   | When It's Used                              |
|--------|---------------------------------------------|
| `LL`   | Driver waits at dock while trailer is loaded  |
| `LU`   | Driver waits at dock while trailer is unloaded|
| `HL`   | Driver hooks up a pre-loaded trailer          |
| `LD`   | Driver drops off a loaded trailer             |
| `EMPP` | Pick up an empty trailer                      |
| `EMPD` | Drop off an empty trailer                     |
| `HUBP` | Pick up from a hub/yard                       |
| `HUBD` | Drop off at a hub/yard                        |

**How does the agent decide?** With a priority system:

1. **Primary: Check history.** Call `get_action_code_frequency(address_id)` -- if this address has been visited before, the most common action code is probably correct.
2. **Secondary: Get details.** If needed, call `get_similar_stops_for_address(address_id)` for more context.
3. **Fallback: Positional defaults.** If there's no history at all:
   - First stop --> `LL` (Live Load)
   - Middle stops (when 3+ stops) --> `LL` (Live Load)
   - Last stop --> `LU` (Live Unload)

> **Why are positional defaults LL and LU?** Because in the vast majority of shipments, the first stop is a pickup (loading) and the last is a delivery (unloading). Live operations (driver waits) are more common than drop-and-hook. It's the safest statistical bet when there's no other information to go on.

#### Step 4: Map Trailer Type

Rate cons describe trailers in all sorts of ways: "53-foot dry van", "53' reefer", "48ft flatbed". The agent maps these to system codes:

| Contains | Maps To      |
|----------|-------------|
| `53`     | `LARGE_53`  |
| `48`     | `LARGE_48`  |
| `45`     | `MEDIUM_45` |
| `40`     | `MEDIUM_40` |
| `28`     | `SMALL_28`  |
| `20`     | `SMALL_20`  |
| Other    | `""` (empty) |

#### Step 5: Parse Appointment Times

Convert human-readable dates like `06/15/2025 08:00` into ISO8601 UTC: `2025-06-15T15:00:00Z`.

The key assumption: **if no timezone is specified, assume America/Los_Angeles (Pacific Time).** This makes sense for a California-based TMS where most rate cons come from West Coast brokers.

#### Step 6: Assemble Payload

The agent constructs a JSON object matching the `RateConLoadPayload` Pydantic model. Important details:

- **PO numbers** are converted from lists to comma-separated strings (e.g., `['PO-1', 'PO-2']` becomes `"PO-1, PO-2"`)
- **Status** is always `"pending"` -- loads start in pending state
- **Billing status** is always `"pending_delivery"` -- can't bill before delivery
- **No shipment_assignment** -- rate cons don't assign carriers/drivers to loads
- **All stops in a single leg** -- multi-leg loads are handled differently

#### Step 7: Create the Load

```python
create_load_from_parsed(payload_json="{ ... }")
```

This calls `LoadToolkit.create_load_from_parsed()`, which:
1. Validates through Pydantic (`RateConLoadPayload`)
2. Strips metadata fields (`celery_task_id`, `ratecon_document_id`)
3. Validates through Django's `LoadSerializer`
4. Creates the load with all nested relations

**If validation fails**, the agent reads the error messages, attempts to fix the payload, and retries. This self-healing behavior is built into the instructions: *"If create_load_from_parsed() returns validation errors, try to fix the payload and retry."*

#### Step 8: Update Document Status

If a `ratecon_document_id` was provided:

```python
update_ratecon_document_status(ratecon_document_id=42, load_id=new_load.id)
```

This links the newly created load back to the `ParsedRateCon` record, completing the traceability chain: **PDF --> ParsedRateCon --> Load**.

---

## How the Two Agents Chain Together

The agents don't call each other directly. Instead, the pipeline is orchestrated by the Celery task layer (see [celery_tasks.md](celery_tasks.md)):

```
1. Celery task extracts text from PDF
2. Celery task runs rate_con_processor with the text
3. Processor output is parsed into ParsedRateConData (Pydantic)
4. If classification == PASS:
     - ParsedRateConData is serialized to JSON
     - Celery task (or synchronous caller) runs ratecon_load_creator with that JSON
5. Load creator resolves all references and creates the load
6. Load creator links load back to source document
```

The data contract between the two agents is the `ParsedRateConData` model. The processor produces data that fits this shape; the load creator consumes it. As long as both sides respect this contract, the agents can be developed, tested, and improved independently.

---

## A Note on Financial Processing

You might have noticed some commented-out code in the load creator's instructions (lines 61-76). This is a planned feature for creating `IncomeLineItem` records from rate con financial data. The mapping is defined but not yet active:

| Rate Con Field    | Category Code | Description |
|------------------|--------------|-------------|
| Line Haul Rate   | `FR`          | Flat Rate    |
| Fuel Surcharge   | `FR`          | Flat Rate    |
| Detention        | `DT`          | Detention    |
| Layover          | `LO`          | Layover      |
| Lumper           | `LF`          | Lumper Fee   |
| TONU             | `TONU`        | Truck Order Not Used |
| Storage          | `TS`          | Storage      |
| Stop Off         | `SO`          | Stop Off     |
| Deadhead         | `DH`          | Deadhead     |

This will be enabled once the financial serializers are production-ready.

---

## Summary Table

| Aspect               | Rate Con Processor           | Rate Con Load Creator             |
|-----------------------|-----------------------------|-----------------------------------|
| **Role**              | Read and extract             | Resolve and create                 |
| **Input**             | Raw PDF text                 | ParsedRateConData (JSON)           |
| **Output**            | Structured text template     | Load record in database            |
| **Toolkits**          | None                         | Load, Address, Customer, StopHistory |
| **Makes DB changes?** | No                           | Yes                                |
| **Can fail gracefully?** | Yes (CLASSIFICATION: FAIL) | Yes (retries on validation errors) |
| **Model**             | gpt-5.2                      | gpt-5.2                           |
| **History**           | Disabled                     | Disabled                           |
