from enum import Enum


class ActionEnum(str, Enum):
    EMPD = "EMPD"
    EMPP = "EMPP"
    HL = "HL"
    HUBD = "HUBD"
    HUBP = "HUBP"
    LD = "LD"
    LL = "LL"
    LU = "LU"

    def __str__(self) -> str:
        return str(self.value)
