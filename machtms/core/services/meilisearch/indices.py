from django.conf import settings
from enum import Enum
from typing import Final

def _prefix(s: str) -> str:
    return f"{'DEBUG_' if settings.DEBUG else ''}{s}"

# 1) Define your Enum with string values for each valid index key.
class TMSIndex(Enum):
    TMS_LOAD = "TMS_LOAD"
    TMS_ADDRESSES = "TMS_ADDRESSES"
    TMS_CUSTOMERS = "TMS_CUSTOMERS"
    TMS_CARRIERS = "TMS_CARRIERS"

# 2) Use the Enum as keys in your dictionary.
#    The values can still be runtime-built depending on DEBUG.
MEILI_INDICES: Final[dict[TMSIndex, str]] = {
    member: _prefix(member.value)
    for member in TMSIndex
}
