from enum import Enum


class BillingStatusEnum(str, Enum):
    BILLED = "billed"
    PAID = "paid"
    PAPERWORK_PENDING = "paperwork_pending"
    PENDING_DELIVERY = "pending_delivery"
    REJECTED = "rejected"

    def __str__(self) -> str:
        return str(self.value)
