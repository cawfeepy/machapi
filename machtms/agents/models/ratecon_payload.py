from pydantic import BaseModel, Field
from typing import Optional


class ParsedStop(BaseModel):
    stop_type: str  # "PICKUP" or "DELIVERY"
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    appointment: str = ""
    po_numbers: str = ""
    notes: str = ""


class ParsedFinancialInfo(BaseModel):
    line_haul_rate: str = "UNKNOWN"
    fuel_surcharge: str = "UNKNOWN"
    total_rate: str = "UNKNOWN"


class ParsedRateConData(BaseModel):
    classification: str = "PASS"  # PASS or FAIL
    classification_reason: str = ""
    reference_number: str = "UNKNOWN"
    bol_number: str = "UNKNOWN"
    customer_name: str = "UNKNOWN"
    trailer_type: str = "UNKNOWN"
    financial: ParsedFinancialInfo = ParsedFinancialInfo()
    stops: list[ParsedStop] = []
    invoice_email: str = "UNKNOWN"


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
