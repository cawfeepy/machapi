from pydantic import BaseModel, Field
from typing import Optional


class ParsedStop(BaseModel):
    stop_type: str = Field(
        default="PICKUP",
        description=(
            "PICKUP or DELIVERY. Used to infer the action code for load creation. "
            "First stop: default Live Load (LL); check stop history for address if found. "
            "Middle stops (3+ stops): default Live Load (LL); check stop history. "
            "Last stop: default Live Unload (LU); check stop history."
        ),
    )
    place_name: str = Field(
        default="",
        description=(
            "Facility or business name at the stop (e.g., 'Amazon Fulfillment Center'). "
            "Use empty string if not found. "
            "Formatting: When a dash separates the warehouse name from a vendor/tenant name, "
            "add spaces around the dash (e.g., 'DCG FULFILLMENT - CUTIE PIE BABY', not "
            "'DCG FULFILLMENT-CUTIE PIE BABY'). If the dash is part of the facility name itself "
            "(e.g., 'Wal-Mart'), leave it as-is."
        ),
    )
    street_address: str = Field(
        default="",
        description="Full street address (e.g., '123 Warehouse Blvd'). Do not include city, state, or zip here.",
    )
    city: str = Field(default="", description="City name")
    state: str = Field(
        default="",
        description="Two-letter US state abbreviation (e.g., 'CA', 'TX')",
    )
    zip_code: str = Field(
        default="",
        description="ZIP code (5-digit or ZIP+4)",
    )
    appointment: str = Field(
        default="",
        description="Appointment date and time in MM/DD/YYYY HH:MM format. Use 'UNKNOWN' if not found.",
    )
    po_numbers: list[str] = Field(
        default_factory=list,
        description="List of PO (Purchase Order) numbers for this stop. Each PO as a separate string. Use empty list if none.",
    )
    notes: str = Field(
        default="",
        description="Special instructions, dock numbers, or notes for this stop. Use empty string if none.",
    )


class ParsedFinancialInfo(BaseModel):
    line_haul_rate: str = Field(
        default="UNKNOWN",
        description="Flat rate line haul charge (e.g., '$2,500.00'). Only confirmed, real charges. Use 'UNKNOWN' if not found.",
    )
    fuel_surcharge: str = Field(
        default="UNKNOWN",
        description="Fuel surcharge amount. Use 'UNKNOWN' if not found.",
    )
    total_rate: str = Field(
        default="UNKNOWN",
        description="Total rate (informational only, not a line item). Use 'UNKNOWN' if not found.",
    )


class ParsedRateConData(BaseModel):
    classification: str = Field(
        default="PASS",
        description=(
            "PASS if this is a valid rate confirmation (has reference/load number, "
            "pickup/delivery addresses, appointment times, rate/payment info). FAIL otherwise."
        ),
    )
    classification_reason: str = Field(
        default="",
        description="If FAIL, explain why. Leave empty if PASS.",
    )
    reference_number: str = Field(
        default="UNKNOWN",
        description=(
            "The primary reference or load number for the shipment. Often labeled as "
            "Reference #, Load #, or Shipment #. Use 'UNKNOWN' if not found."
        ),
    )
    bol_number: str = Field(
        default="UNKNOWN",
        description=(
            "A single identifier for the full shipment. May be labeled BOL#, PU#, BM#, "
            "or Bill of Lading. This is NOT a PO number (PO numbers relate to individual "
            "items/stops). Use 'UNKNOWN' if not found."
        ),
    )
    customer_name: str = Field(
        default="UNKNOWN",
        description="The broker or customer company name on the rate confirmation. Use 'UNKNOWN' if not found.",
    )
    trailer_type: str = Field(
        default="UNKNOWN",
        description="The trailer type/size described on the rate con (e.g., '53' Dry Van', '48' Flatbed'). Use 'UNKNOWN' if not found.",
    )
    # financial: ParsedFinancialInfo = ParsedFinancialInfo()  # Not used by rate con load creator yet
    stops: list[ParsedStop] = Field(
        default_factory=list,
        description="All pickup and delivery stops in order as they appear on the rate confirmation.",
    )
    invoice_email_standard_pay: str = Field(
        default="UNKNOWN",
        description="Email address for submitting invoices under standard payment terms (e.g., Net 30). Use 'UNKNOWN' if not found.",
    )
    invoice_email_quick_pay: str = Field(
        default="UNKNOWN",
        description="Email address for submitting invoices under quick pay terms. Use 'UNKNOWN' if not found.",
    )
    celery_task_id: str = ""
    ratecon_document_id: Optional[int] = None


class RateConLoadPayload(BaseModel):
    """Pydantic model enforcing the structure expected by LoadSerializer.

    Matches the OpenAPI schema for load creation:
    - customer: FK ID (resolved from customer name)
    - reference_number, bol_number: from rate con
    - trailer_type: mapped to TrailerType choices
    - legs[].stops[]: address FK ID, action, start_range, etc.
    - No shipment_assignment (rate cons don't assign carriers)
    """

    class StopPayload(BaseModel):
        stop_number: int
        address: int  # FK ID
        action: str  # LL, LU, HL, LD, EMPP, EMPD, HUBP, HUBD
        start_range: str  # ISO8601 UTC
        end_range: Optional[str] = None
        po_numbers: str = ""
        driver_notes: str = ""

    class LegPayload(BaseModel):
        stops: list["RateConLoadPayload.StopPayload"]

    customer: Optional[int] = None  # FK ID
    reference_number: str = ""
    bol_number: str = ""
    trailer_type: str = ""
    status: str = "pending"
    billing_status: str = "pending_delivery"
    legs: list[LegPayload] = Field(default_factory=list)
    celery_task_id: str = ""
    ratecon_document_id: Optional[int] = None
