from enum import Enum


class StatusEnum(str, Enum):
    ASSIGNED = "assigned"
    AT_HUB = "at_hub"
    CLAIM = "claim"
    COMPLETE = "complete"
    DISPATCHED = "dispatched"
    IN_TRANSIT = "in_transit"
    PENDING = "pending"
    RESCHEDULED = "rescheduled"
    TIMES_MISSING = "times_missing"
    TONU = "tonu"

    def __str__(self) -> str:
        return str(self.value)
