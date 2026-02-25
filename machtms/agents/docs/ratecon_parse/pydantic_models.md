# Pydantic Models: The Contracts That Keep Everything Honest

> What if the Rate Con Processor produces data in one format and the Load Creator expects another? What if an appointment time is missing and nobody notices until the database throws a 500? What if po_numbers is sometimes a list and sometimes a string? Chaos. Pydantic models prevent that chaos.

**File:** `machtms/agents/models/ratecon_payload.py`

---

## Why Pydantic?

The ratecon pipeline involves two AI agents passing structured data between them. AI agents are clever, but they're also unpredictable. Sometimes they add extra fields. Sometimes they forget required ones. Sometimes they return a string where you expected an integer.

Pydantic models act as **data contracts** -- strict schemas that validate data at the boundary between components. If the data doesn't match the contract, you get a clear, immediate error instead of a mysterious failure three layers deeper.

> **What if we didn't have Pydantic validation?** The load creator would receive a Python dict of unknown shape. It might have `reference_number` or it might have `ref_num`. The `po_numbers` might be a list or a comma-separated string or None. Every consumer of this data would need defensive checks everywhere. Pydantic centralizes that validation into one place.

Think of these models as customs declarations at a border crossing. Before data crosses from one agent to the next, it has to declare exactly what it's carrying. If it doesn't match the form, it doesn't get through.

---

## The Dual Role of ParsedRateConData

Here's what makes this setup interesting: `ParsedRateConData` is both the **data contract** between agents AND the **LLM extraction guide**. How?

When `output_schema=ParsedRateConData` is set on the Rate Con Processor agent, Agno serializes the Pydantic model's JSON schema and sends it to the LLM as part of the structured output specification. The LLM sees every field name, type, default value, and -- crucially -- every `Field(description=...)`.

This means:
- The field descriptions **are** the extraction instructions
- Change a description, and the LLM adapts automatically
- No separate template or instruction set to keep in sync

> **What problem does this solve?** Previously, extraction instructions lived in the agent's `instructions` list (a text template) while the data contract lived in the Pydantic model. These could drift apart. Now they're the same thing.

---

## Model 1: ParsedStop

```python
class ParsedStop(BaseModel):
    stop_type: str = Field(default="PICKUP", description="PICKUP or DELIVERY...")
    street_address: str = Field(default="", description="Full street address...")
    city: str = Field(default="", description="City name")
    state: str = Field(default="", description="Two-letter US state abbreviation...")
    zip_code: str = Field(default="", description="ZIP code (5-digit or ZIP+4)")
    appointment: str = Field(default="", description="...in MM/DD/YYYY HH:MM format...")
    po_numbers: list[str] = Field(default_factory=list, description="List of PO numbers...")
    notes: str = Field(default="", description="Special instructions, dock numbers...")
```

**Purpose:** Represents a single stop as extracted from the rate confirmation text. This is the *raw parsed* representation -- it hasn't been resolved into database IDs yet.

### Field-by-Field Breakdown

| Field            | Type       | Default     | Description                                                       |
|-----------------|-----------|-------------|-------------------------------------------------------------------|
| `stop_type`     | `str`      | `"PICKUP"`  | Either `"PICKUP"` or `"DELIVERY"` -- the high-level classification |
| `street_address`| `str`      | `""`        | Full street address, no city/state/zip                             |
| `city`          | `str`      | `""`        | City name                                                          |
| `state`         | `str`      | `""`        | Two-letter state abbreviation (e.g., `"CA"`, `"TX"`)              |
| `zip_code`      | `str`      | `""`        | ZIP code (5-digit or ZIP+4)                                        |
| `appointment`   | `str`      | `""`        | Date/time in MM/DD/YYYY HH:MM format, or `"UNKNOWN"`              |
| `po_numbers`    | `list[str]`| `[]`        | List of PO numbers for this stop                                   |
| `notes`         | `str`      | `""`        | Special instructions, gate info, contact details, etc.             |

### The stop_type Field Description

The `stop_type` field carries an unusually detailed description because it tells the **load creator** agent how to interpret the value and what default action codes to apply. It's documentation and instruction in one:

```python
"PICKUP or DELIVERY. Used to infer the action code for load creation.
 First stop: default Live Load (LL); check stop history for address if found.
 Middle stops (3+ stops): default Live Load (LL); check stop history.
 Last stop: default Live Unload (LU); check stop history."
```

### Why po_numbers Is a List

Rate confirmations often list multiple PO numbers per stop: `"PO-1234, PO-5678, PO-9012"`. With structured output, the LLM naturally returns these as a JSON array:

```python
["PO-1234", "PO-5678", "PO-9012"]
```

> **Why default_factory=list instead of default=[]?** This is a classic Python gotcha. If you write `default=[]`, every instance shares the same list object. `default_factory=list` creates a new empty list for each instance.

---

## Model 2: ParsedFinancialInfo

```python
class ParsedFinancialInfo(BaseModel):
    line_haul_rate: str = Field(default="UNKNOWN", description="Flat rate line haul charge...")
    fuel_surcharge: str = Field(default="UNKNOWN", description="Fuel surcharge amount...")
    total_rate: str = Field(default="UNKNOWN", description="Total rate (informational only)...")
```

**Purpose:** Holds the financial data extracted from a rate confirmation.

**Current status:** Defined but not actively used. The `ParsedRateConData` model has this field commented out:

```python
# financial: ParsedFinancialInfo = ParsedFinancialInfo()  # Not used by rate con load creator yet
```

### Why keep it around?

This model is a placeholder for planned financial processing. When the financial serializers and `IncomeLineItem` creation are ready, this model will be uncommented and integrated. Having it already defined with field descriptions means the extraction logic will be ready to go.

### Why strings instead of Decimal or float?

Rate values come from PDF text extraction, which means they arrive as things like `"$2,500.00"` or `"2500"` or `"UNKNOWN"`. Storing them as strings preserves the raw extracted value without premature parsing.

---

## Model 3: ParsedRateConData

```python
class ParsedRateConData(BaseModel):
    classification: str = Field(default="PASS", description="PASS if valid rate con... FAIL otherwise.")
    classification_reason: str = Field(default="", description="If FAIL, explain why...")
    reference_number: str = Field(default="UNKNOWN", description="The primary reference or load number...")
    bol_number: str = Field(default="UNKNOWN", description="A single identifier for the full shipment...")
    customer_name: str = Field(default="UNKNOWN", description="The broker or customer company name...")
    trailer_type: str = Field(default="UNKNOWN", description="The trailer type/size...")
    stops: list[ParsedStop] = Field(default_factory=list, description="All pickup and delivery stops...")
    invoice_email_standard_pay: str = Field(default="UNKNOWN", description="Email for standard payment...")
    invoice_email_quick_pay: str = Field(default="UNKNOWN", description="Email for quick pay...")
    celery_task_id: str = ""
    ratecon_document_id: Optional[int] = None
```

**Purpose:** This is the main data contract between the Rate Con Processor and the Rate Con Load Creator. It's also the `output_schema` for the processor agent, making it both the extraction guide and the validation layer.

### Field Descriptions as LLM Instructions

Every field that the LLM should extract has a rich `Field(description=...)`. These descriptions:

- Tell the LLM what to look for (`"Often labeled as Reference #, Load #, or Shipment #"`)
- Clarify ambiguities (`"This is NOT a PO number (PO numbers relate to individual items/stops)"`)
- Specify fallback behavior (`"Use 'UNKNOWN' if not found"`)

Fields that are metadata (not LLM-extracted) -- `celery_task_id` and `ratecon_document_id` -- have no descriptions. They're injected by the pipeline, not the agent.

### The UNKNOWN Convention

Most string fields default to `"UNKNOWN"` rather than empty strings:

- `""` (empty string) means "this field exists but has no value"
- `"UNKNOWN"` means "we couldn't find this on the document"

The distinction matters for downstream processing. If `reference_number` is `"UNKNOWN"`, the load creator knows it needs to handle a missing reference number.

### Dual Invoice Emails

```python
invoice_email_standard_pay: str = Field(default="UNKNOWN", description="...standard payment terms (e.g., Net 30)...")
invoice_email_quick_pay: str = Field(default="UNKNOWN", description="...quick pay terms...")
```

Many brokers offer two payment tracks. Capturing both means the financial team can choose the right one later.

### Metadata Fields: celery_task_id and ratecon_document_id

These two fields don't come from the PDF at all. They're injected by the Celery task layer to maintain traceability:

- `celery_task_id`: Links back to the async task that initiated the parsing
- `ratecon_document_id`: Links back to the uploaded document record

These fields travel through the pipeline and eventually reach `RateConLoadPayload`, where they're stripped before the load is created.

---

## Model 4: RateConLoadPayload

```python
class RateConLoadPayload(BaseModel):
    class StopPayload(BaseModel):
        stop_number: int
        address: int          # FK ID
        action: str           # LL, LU, HL, LD, EMPP, EMPD, HUBP, HUBD
        start_range: str      # ISO8601 UTC
        end_range: Optional[str] = None
        po_numbers: str = ""
        driver_notes: str = ""

    class LegPayload(BaseModel):
        stops: list["RateConLoadPayload.StopPayload"]

    customer: Optional[int] = None
    reference_number: str = ""
    bol_number: str = ""
    trailer_type: str = ""
    status: str = "pending"
    billing_status: str = "pending_delivery"
    legs: list[LegPayload] = Field(default_factory=list)
    celery_task_id: str = ""
    ratecon_document_id: Optional[int] = None
```

**Purpose:** This is the *final* data shape before a load is created in the database. It mirrors the structure expected by Django's `LoadSerializer`, with two extra metadata fields.

### How Is This Different from ParsedRateConData?

| Aspect          | ParsedRateConData               | RateConLoadPayload               |
|----------------|--------------------------------|----------------------------------|
| Customer        | `customer_name: str` (human)   | `customer: int` (FK ID)          |
| Addresses       | `street_address`, `city`, etc. | `address: int` (FK ID)           |
| Stop actions    | `stop_type: "PICKUP"`          | `action: "LL"` (specific code)   |
| Appointments    | `appointment: "06/15/2025 08:00"` | `start_range: "2025-06-15T15:00:00Z"` |
| PO numbers      | `po_numbers: ["PO-1", "PO-2"]`| `po_numbers: "PO-1, PO-2"`      |
| Structure       | Flat list of stops             | Nested: legs > stops             |

`ParsedRateConData` is what the *processor* produces (human-readable, unresolved). `RateConLoadPayload` is what the *load creator* produces (database-ready, fully resolved).

### The Metadata Strip

When `create_load_from_parsed()` receives a `RateConLoadPayload`, it strips metadata before sending to Django:

```python
stripped = payload.model_dump(exclude={'celery_task_id', 'ratecon_document_id'})
return self.create_load(run_context, json.dumps(stripped))
```

> **Why include them in the payload model at all?** Because they need to travel through the pipeline alongside the load data. The load creator agent needs `ratecon_document_id` for Step 8 (linking the load back to its source document).

---

## How the Models Flow Through the Pipeline

```
PDF Text
   |
   v
Rate Con Processor (agent, output_schema=ParsedRateConData)
   |
   v
ParsedRateConData  <--- Validated Pydantic instance
   |                     (human-readable names, raw dates, PO lists)
   |
   +-- ParsedStop[]
   |
   v
Rate Con Load Creator (agent)
   |  resolves customers, addresses, action codes
   |  converts dates, joins PO numbers
   v
RateConLoadPayload  <--- "Here's what goes in the database"
   |                      (FK IDs, action codes, ISO dates)
   |
   +-- LegPayload[]
   |     +-- StopPayload[]
   |
   v
LoadSerializer (Django)
   |
   v
Load + Legs + Stops (database records)
```

Each model in this chain enforces a tighter contract than the last. `ParsedRateConData` is loose (strings, UNKNOWN defaults). `RateConLoadPayload` is strict (integer IDs, specific action codes). The `LoadSerializer` is strictest of all (foreign key validation, choice field validation, required field checks).

---

## Quick Reference: All Models in ratecon_payload.py

| Model                 | Role                     | Used By                     | Key Characteristic                    |
|----------------------|--------------------------|-----------------------------|-----------------------------------------|
| `ParsedStop`         | Raw stop from PDF         | Rate Con Processor (schema) | Human-readable, list PO numbers         |
| `ParsedFinancialInfo`| Financial data from PDF   | (Future use)                | All strings, defaults to UNKNOWN        |
| `ParsedRateConData`  | Complete parsed document  | Processor output_schema     | Flat structure, UNKNOWN defaults, LLM guide |
| `RateConLoadPayload` | DB-ready load payload     | Load Creator -> LoadToolkit | Nested legs/stops, FK IDs               |
