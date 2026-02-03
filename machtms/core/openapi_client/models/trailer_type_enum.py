from enum import Enum


class TrailerTypeEnum(str, Enum):
    LARGE_48 = "LARGE_48"
    LARGE_53 = "LARGE_53"
    MEDIUM_40 = "MEDIUM_40"
    MEDIUM_45 = "MEDIUM_45"
    SMALL_20 = "SMALL_20"
    SMALL_28 = "SMALL_28"

    def __str__(self) -> str:
        return str(self.value)
