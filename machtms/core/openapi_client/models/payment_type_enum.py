from enum import Enum


class PaymentTypeEnum(str, Enum):
    QUICKPAY = "quickpay"
    STANDARD = "standard"

    def __str__(self) -> str:
        return str(self.value)
