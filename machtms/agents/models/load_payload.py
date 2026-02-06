from pydantic import BaseModel, Field
from typing import Optional


class StopPayload(BaseModel):
    stop_number: int
    address: int  # FK ID
    action: str  # LL, LU, HL, LD, EMPP, EMPD, HUBP, HUBD
    start_range: str  # ISO8601 UTC
    end_range: Optional[str] = None
    po_numbers: str = ""
    driver_notes: str = ""


class ShipmentAssignmentPayload(BaseModel):
    carrier: int  # FK ID
    driver: int  # FK ID


class LegPayload(BaseModel):
    stops: list[StopPayload]
    shipment_assignment: Optional[ShipmentAssignmentPayload] = None


class LoadCreationPayload(BaseModel):
    customer: Optional[int] = None  # FK ID
    reference_number: str = ""
    bol_number: str = ""
    trailer_type: str = ""
    status: str = "pending"
    billing_status: str = "pending_delivery"
    legs: list[LegPayload] = Field(default_factory=list)
