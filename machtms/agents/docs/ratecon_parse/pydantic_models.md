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

## Model 1: ParsedStop

```python
class ParsedStop(BaseModel):
    stop_type: str = "PICKUP"
    street_address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    appointment: str = ""
    po_numbers: list[str] = Field(default_factory=list)
    notes: str = ""
```

**Purpose:** Represents a single stop as extracted from the rate confirmation text. This is the *raw parsed* representation -- it hasn't been resolved into database IDs yet.

### Field-by-Field Breakdown

| Field            | Type       | Default     | Description                                                       |
|-----------------|-----------|-------------|-------------------------------------------------------------------|
| `stop_type`     | `str`      | `"PICKUP"`  | Either `"PICKUP"` or `"DELIVERY"` -- the high-level classification |
| `street_address`| `str`      | `""`        | Full street address as written on the rate con                     |
| `city`          | `str`      | `""`        | City name                                                          |
| `state`         | `str`      | `""`        | State abbreviation (e.g., `"CA"`, `"TX"`)                         |
| `zip_code`      | `str`      | `""`        | ZIP code                                                           |
| `appointment`   | `str`      | `""`        | Date/time as it appears on the document (e.g., `"06/15/2025 08:00"`) |
| `po_numbers`    | `list[str]`| `[]`        | List of PO numbers for this stop                                   |
| `notes`         | `str`      | `""`        | Special instructions, gate info, contact details, etc.             |

### The stop_type Field Description

The `stop_type` field carries an unusually detailed `description` in its `Field()` definition:

```python
stop_type: str = Field(
    default="PICKUP",
    description=(
        "PICKUP or DELIVERY. Used to infer the action code for load creation. "
        "First stop: default Live Load (LL); check stop history for address if found. "
        "Middle stops (3+ stops): default Live Load (LL); check stop history. "
        "Last stop: default Live Unload (LU); check stop history."
    ),
)
```

> **Why so verbose?** Because this description is visible to the AI agents. When Pydantic models are passed as tool schemas or response models, the field descriptions become part of the agent's instructions. This description tells the load creator agent how to interpret `stop_type` and what default action codes to apply. It's documentation and instruction in one.

### Why po_numbers Is a List

```python
po_numbers: list[str] = Field(default_factory=list)
```

Rate confirmations often list multiple PO numbers per stop: `"PO-1234, PO-5678, PO-9012"`. During extraction, these are parsed into a list for clean handling:

```python
["PO-1234", "PO-5678", "PO-9012"]
```

> **What does the list solve?** It eliminates ambiguity. If `po_numbers` were a raw string, you'd have to guess the delimiter. Commas? Semicolons? Spaces? Newlines? By the time the data reaches this model, it's already a proper list. The load creator agent later joins them back into a comma-separated string for the database field, but the intermediate representation is clean and unambiguous.

> **Why default_factory=list instead of default=[]?** This is a classic Python gotcha. If you write `default=[]`, every instance shares the same list object. Mutating one mutates all of them. `default_factory=list` creates a new empty list for each instance. Pydantic enforces this, but it's good to see it done correctly.

---

## Model 2: ParsedFinancialInfo

```python
class ParsedFinancialInfo(BaseModel):
    line_haul_rate: str = "UNKNOWN"
    fuel_surcharge: str = "UNKNOWN"
    total_rate: str = "UNKNOWN"
```

**Purpose:** Holds the financial data extracted from a rate confirmation.

**Current status:** Defined but not actively used. The `ParsedRateConData` model has this field commented out:

```python
# financial: ParsedFinancialInfo = ParsedFinancialInfo()  # Not used by rate con load creator yet
```

### Why keep it around?

This model is a placeholder for planned financial processing. When the financial serializers and `IncomeLineItem` creation are ready, this model will be uncommented and integrated. Having it already defined means the extraction logic (in the Rate Con Processor agent) is already capturing financial data -- it just isn't being acted on yet.

### Why strings instead of Decimal or float?

Rate values come from PDF text extraction, which means they arrive as things like `"$2,500.00"` or `"2500"` or `"UNKNOWN"`. Storing them as strings preserves the raw extracted value without premature parsing. The conversion to numeric types will happen in the financial processing layer when it's implemented.

---

## Model 3: ParsedRateConData

```python
class ParsedRateConData(BaseModel):
    classification: str = "PASS"
    classification_reason: str = ""
    reference_number: str = "UNKNOWN"
    bol_number: str = "UNKNOWN"
    customer_name: str = "UNKNOWN"
    trailer_type: str = "UNKNOWN"
    stops: list[ParsedStop] = []
    invoice_email_standard_pay: str = "UNKNOWN"
    invoice_email_quick_pay: str = "UNKNOWN"
    celery_task_id: str = ""
    ratecon_document_id: Optional[int] = None
```

**Purpose:** This is the main data contract between the Rate Con Processor and the Rate Con Load Creator. It holds everything extracted from a rate confirmation document.

### Field-by-Field Breakdown

| Field                         | Type              | Default      | Description                                                     |
|------------------------------|------------------|--------------|-----------------------------------------------------------------|
| `classification`             | `str`             | `"PASS"`     | Whether the document is a valid rate con (`"PASS"` or `"FAIL"`) |
| `classification_reason`      | `str`             | `""`         | Explanation when classification is `"FAIL"`                      |
| `reference_number`           | `str`             | `"UNKNOWN"`  | The load/reference number from the rate con                      |
| `bol_number`                 | `str`             | `"UNKNOWN"`  | Bill of Lading number (could be labeled BOL#, PU#, BM#)         |
| `customer_name`              | `str`             | `"UNKNOWN"`  | Customer/broker name as printed on the document                  |
| `trailer_type`               | `str`             | `"UNKNOWN"`  | Trailer description (e.g., `"53' Dry Van"`)                     |
| `stops`                      | `list[ParsedStop]`| `[]`         | All stops extracted from the document, in order                  |
| `invoice_email_standard_pay` | `str`             | `"UNKNOWN"`  | Email for standard payment invoices                              |
| `invoice_email_quick_pay`    | `str`             | `"UNKNOWN"`  | Email for quick pay invoices                                     |
| `celery_task_id`             | `str`             | `""`         | The Celery task ID that triggered this parsing (for traceability)|
| `ratecon_document_id`        | `Optional[int]`   | `None`       | FK to the `RateConDocument` model in the database                |

### The BOL Number Field Description

```python
bol_number: str = Field(
    default="UNKNOWN",
    description=(
        "Can be labeled PU#, BOL#, or BM. "
        "Reference number for the full trip, NOT a PO number."
    ),
)
```

> **Why does this need a description?** Because BOL numbers go by many names. On one rate con it's "BOL#", on another it's "PU#" (Pickup Number), on another it's "BM" (Bill of Material or Booking Number). The description guides the AI agent to recognize all these variations and -- critically -- not confuse them with PO numbers, which are per-stop, not per-trip.

### The UNKNOWN Convention

Notice that most string fields default to `"UNKNOWN"` rather than empty strings. This is deliberate:

- `""` (empty string) means "this field exists but has no value"
- `"UNKNOWN"` means "we couldn't find this on the document"

The distinction matters for downstream processing. If `reference_number` is `"UNKNOWN"`, the load creator knows it needs to handle a missing reference number. If it were `""`, it's ambiguous -- was it empty on the document, or did extraction fail?

### Dual Invoice Emails

```python
invoice_email_standard_pay: str = "UNKNOWN"
invoice_email_quick_pay: str = "UNKNOWN"
```

Many brokers offer two payment tracks: standard pay (30-60 day terms) and quick pay (faster, but with a fee). Rate confirmations often list separate email addresses for each. Capturing both means the financial team can choose the right one later.

### Metadata Fields: celery_task_id and ratecon_document_id

These two fields don't come from the PDF at all. They're injected by the Celery task layer to maintain traceability:

- `celery_task_id`: Links back to the async task that initiated the parsing
- `ratecon_document_id`: Links back to the uploaded document record

These fields travel through the pipeline and eventually reach `RateConLoadPayload`, where they're stripped before the load is created (they're metadata, not load data).

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

Great question. Here's the transformation:

| Aspect          | ParsedRateConData               | RateConLoadPayload               |
|----------------|--------------------------------|----------------------------------|
| Customer        | `customer_name: str` (human)   | `customer: int` (FK ID)          |
| Addresses       | `street_address`, `city`, etc. | `address: int` (FK ID)           |
| Stop actions    | `stop_type: "PICKUP"`          | `action: "LL"` (specific code)   |
| Appointments    | `appointment: "06/15/2025 08:00"` | `start_range: "2025-06-15T15:00:00Z"` |
| PO numbers      | `po_numbers: ["PO-1", "PO-2"]`| `po_numbers: "PO-1, PO-2"`      |
| Structure       | Flat list of stops             | Nested: legs > stops             |

`ParsedRateConData` is what the *processor* produces (human-readable, unresolved). `RateConLoadPayload` is what the *load creator* produces (database-ready, fully resolved).

### Nested Models: StopPayload and LegPayload

The nesting mirrors how Django's `LoadSerializer` expects data:

```
RateConLoadPayload
  |
  +-- legs: [LegPayload]
        |
        +-- stops: [StopPayload]
```

This structure maps directly to the database hierarchy: `Load` -> `Leg` -> `Stop`.

**StopPayload fields:**

| Field          | Type            | Description                                          |
|---------------|----------------|------------------------------------------------------|
| `stop_number` | `int`           | Order within the leg (1, 2, 3...)                    |
| `address`     | `int`           | FK to the Address table (resolved from street/city)  |
| `action`      | `str`           | Specific action code (LL, LU, HL, etc.)              |
| `start_range` | `str`           | ISO8601 UTC datetime string                          |
| `end_range`   | `Optional[str]` | Optional end of appointment window                   |
| `po_numbers`  | `str`           | Comma-separated PO numbers (converted from list)     |
| `driver_notes`| `str`           | Instructions for the driver                          |

> **Notice that `po_numbers` is a `str` here, not a `list[str]`.** The list-to-string conversion happens in the load creator agent between consuming `ParsedRateConData` (list) and producing `RateConLoadPayload` (string). This matches the database field, which is a `TextField`.

### The Metadata Strip

When `create_load_from_parsed()` in the LoadToolkit receives a `RateConLoadPayload`, it does this:

```python
stripped = payload.model_dump(exclude={'celery_task_id', 'ratecon_document_id'})
return self.create_load(run_context, json.dumps(stripped))
```

The `celery_task_id` and `ratecon_document_id` fields are excluded before passing the data to the Django serializer. The serializer doesn't know about these fields -- they're pipeline metadata, not load data. If they weren't stripped, the serializer would raise validation errors for unexpected fields.

> **Why include them in the payload model at all?** Because they need to travel through the pipeline alongside the load data. The load creator agent needs `ratecon_document_id` for Step 8 (linking the load back to its source document). By including these fields in the Pydantic model rather than passing them separately, the entire context stays in one clean object.

---

## How the Models Flow Through the Pipeline

```
PDF Text
   |
   v
Rate Con Processor (agent)
   |
   v
ParsedRateConData  <--- "Here's what I found on the document"
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

> **What if we skipped straight from PDF text to LoadSerializer?** We'd lose the ability to inspect and debug intermediate states. If a load is created with the wrong action code, you can check the `ParsedRateConData` to see what the processor extracted, then check the `RateConLoadPayload` to see how the load creator interpreted it. Each model is a snapshot in the transformation pipeline.

---

## Quick Reference: All Models in ratecon_payload.py

| Model                 | Role                     | Used By                     | Key Characteristic                |
|----------------------|--------------------------|-----------------------------|------------------------------------|
| `ParsedStop`         | Raw stop from PDF         | Rate Con Processor          | Human-readable, list PO numbers    |
| `ParsedFinancialInfo`| Financial data from PDF   | (Future use)                | All strings, defaults to UNKNOWN   |
| `ParsedRateConData`  | Complete parsed document  | Processor -> Load Creator   | Flat structure, UNKNOWN defaults   |
| `RateConLoadPayload` | DB-ready load payload     | Load Creator -> LoadToolkit | Nested legs/stops, FK IDs          |
