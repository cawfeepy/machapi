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
              (Pydantic instance)
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

**Toolkits:** None -- this agent is purely text-in, structured-data-out.

**Output Schema:** `ParsedRateConData` -- the agent returns a validated Pydantic model directly.

**History:** Disabled (`add_history_to_context=False`) -- each document is processed independently.

### What problem does it solve?

Rate confirmation PDFs come in every imaginable format. Some are clean and structured. Others look like someone typed them in Word, printed them, scanned them, and then faxed them. The Rate Con Processor takes raw text extracted from these documents and normalizes it into a consistent, predictable structure.

### Why Pydantic over templates?

Previously, the agent output a rigid text template with `--- SECTION ---` headers and `Key: Value` lines. A regex parser (`parse_agent_response()`) then converted this text into a dict. This had problems:

- **Key mismatch**: The template used mixed-case keys like `"Reference Number"` that didn't match the Pydantic model's snake_case fields (`reference_number`).
- **Fragile parsing**: Any deviation in the LLM's output format would break the regex parser.
- **Extra code**: A 70-line parser function that existed solely to bridge two incompatible formats.

Now, with `output_schema=ParsedRateConData`, the agent returns a validated Pydantic instance directly. No parsing step. No format mismatch. The field descriptions on the Pydantic model replace the template instructions -- they guide the LLM on what to extract and how.

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

**Output:** The `classification` field is set to either `"PASS"` or `"FAIL"`, with `classification_reason` explaining any failure.

> **What if we skipped classification?** We'd waste processing time on insurance certificates, BOL copies, delivery receipts, and other documents that people accidentally upload. Worse, the load creator would try to create loads from nonsensical data. Classification is the bouncer at the door.

**If FAIL:** All other fields stay at their defaults. No extraction. No load creation. The document is flagged and the reason is recorded.

#### Task 2: Extraction -- Pull Out the Data

If the document passes classification, the agent populates the `ParsedRateConData` fields. The field descriptions guide extraction:

- **reference_number**: "The primary reference or load number for the shipment..."
- **bol_number**: "A single identifier for the full shipment. May be labeled BOL#, PU#, BM#..."
- **stops**: Each stop gets a `ParsedStop` with street_address, city, state, zip_code, appointment, po_numbers, notes
- **invoice emails**: Separate fields for standard pay and quick pay

> Note: Financial data fields exist in the model but are commented out. The agent is still instructed to only recognize *confirmed, real charges* for when financial processing is enabled.

### Key Design Decisions

**Why UNKNOWN instead of empty strings?** It makes it explicitly clear to the downstream agent that a value was not found, rather than leaving ambiguity about whether it was empty on the document or simply missed.

**Why no tools?** The processor only reads text. It doesn't need to query the database, search for addresses, or create records. Giving it tools would introduce unnecessary complexity and the risk of unintended side effects during what should be a pure extraction step.

**Why field descriptions as LLM instructions?** When Agno serializes a Pydantic `output_schema`, the field descriptions become part of the schema sent to the LLM. This means the data contract and the extraction instructions live in one place -- the Pydantic model. Change the model, and the agent automatically adapts.

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

### What problem does it solve?

The processor gave us structured data: `customer_name: "ACME Freight Solutions"`, `street_address: "1234 Distribution Way"`, `stop_type: "PICKUP"`. But the database doesn't store customer names -- it stores customer IDs. It doesn't store street addresses as strings -- it stores address foreign keys. And it doesn't understand "PICKUP" -- it needs "LL" or "HL" or "EMPP".

The load creator bridges that gap. It takes the `ParsedRateConData` JSON and resolves everything into database-ready values.

> **What if we didn't have this agent?** Someone would have to manually look up every customer, every address, and decide every action code. For a single load with 2 stops, that's a minimum of 5 database lookups and 2 judgment calls. Multiply that by dozens of rate cons per day, and you've got a full-time job that's now automated.

---

### The 8-Step Workflow

This is the heart of the load creation process. Each step is explicitly defined in the agent's instructions:

#### Step 1: Resolve Customer

```
Parsed JSON says:   "customer_name": "ACME Freight Solutions"
Agent calls:        search_customers(name="ACME Freight Solutions")
Result:             Customer ID 5, or null if not found
```

The agent uses `CustomerToolkit.search_customers()` with a case-insensitive partial match. If the customer exists, it grabs the ID. If not, the customer field is set to `null`.

> **Why not auto-create missing customers?** Because customer creation involves details beyond a name (payment terms, contact info, billing addresses). Creating a half-empty customer record would cause more problems than it solves.

#### Step 2: Resolve Addresses

For each stop in the `stops` list:

```
1. Search: search_addresses(street="1234 Distribution Way", city="Los Angeles", state="CA", zip="90001")
2. If not found: ensure_address(street="1234 Distribution Way", city="Los Angeles", state="CA", zip_code="90001")
3. Result: Address ID 12
```

`ensure_address()` is a `get_or_create` operation -- it either finds an exact match or creates a new one.

#### Step 3: Determine Stop Actions

Rate confirmations speak in simple terms: "PICKUP" or "DELIVERY." But the TMS has 8 different action codes:

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

**Priority system:**

1. **Primary: Check history.** Call `get_action_code_frequency(address_id)` -- if this address has been visited before, the most common action code is probably correct.
2. **Secondary: Get details.** If needed, call `get_similar_stops_for_address(address_id)` for more context.
3. **Fallback: Positional defaults.** If there's no history at all:
   - First stop --> `LL` (Live Load)
   - Middle stops (when 3+ stops) --> `LL` (Live Load)
   - Last stop --> `LU` (Live Unload)

#### Step 4: Map Trailer Type

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

The key assumption: **if no timezone is specified, assume America/Los_Angeles (Pacific Time).**

#### Step 6: Assemble Payload

The agent constructs a JSON object matching the `RateConLoadPayload` Pydantic model. Important details:

- **PO numbers** are converted from JSON lists to comma-separated strings (e.g., `["PO-1", "PO-2"]` becomes `"PO-1, PO-2"`)
- **Status** is always `"pending"`
- **Billing status** is always `"pending_delivery"`
- **No shipment_assignment** -- rate cons don't assign carriers/drivers to loads
- **All stops in a single leg**

#### Step 7: Create the Load

Calls `LoadToolkit.create_load_from_parsed()`, which validates through Pydantic, strips metadata fields, validates through Django's `LoadSerializer`, and creates the load.

#### Step 8: Update Document Status

If a `ratecon_document_id` was provided, calls `update_ratecon_document_status()` to link the newly created load back to the `ParsedRateCon` record, completing the traceability chain: **PDF --> ParsedRateCon --> Load**.

---

## How the Two Agents Chain Together

The agents don't call each other directly. Instead, the pipeline is orchestrated by the Celery task layer (see [celery_tasks.md](celery_tasks.md)):

```
1. Celery task extracts text from PDF
2. Celery task runs rate_con_processor with the text
3. response.content is a ParsedRateConData instance (via output_schema)
4. If classification == PASS:
     - ParsedRateConData is serialized to JSON
     - Celery task runs ratecon_load_creator with that JSON + metadata
5. Load creator resolves all references and creates the load
6. Load creator links load back to source document
```

The data contract between the two agents is the `ParsedRateConData` model. The processor produces it directly via `output_schema`; the load creator consumes its JSON representation. As long as both sides respect this contract, the agents can be developed, tested, and improved independently.

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

| Aspect               | Rate Con Processor              | Rate Con Load Creator             |
|-----------------------|--------------------------------|-----------------------------------|
| **Role**              | Read and extract                | Resolve and create                 |
| **Input**             | Raw PDF text                    | ParsedRateConData (JSON)           |
| **Output**            | ParsedRateConData (Pydantic)    | Load record in database            |
| **Mechanism**         | `output_schema`                 | Toolkit function calls             |
| **Toolkits**          | None                            | Load, Address, Customer, StopHistory |
| **Makes DB changes?** | No                              | Yes                                |
| **Can fail gracefully?** | Yes (classification: FAIL)   | Yes (retries on validation errors) |
| **Model**             | gpt-5.2                         | gpt-5.2                           |
| **History**           | Disabled                        | Disabled                           |
