import zoneinfo
from datetime import datetime

def utc_to_pst(utc_dt, tzone="America/Los_Angeles"):
    """
    Convert a UTC datetime object to America/Los_Angeles time using zoneinfo.

    Args:
        utc_dt (datetime): A timezone-aware datetime object in UTC.

    Returns:
        datetime: A timezone-aware datetime object in America/Los_Angeles time.
    """
    if utc_dt.tzinfo is None:
        raise ValueError("The datetime object must be timezone-aware (UTC).")

    local_tz = zoneinfo.ZoneInfo(tzone)
    return utc_dt.astimezone(local_tz)


def process_date_range(start_date, end_date):

    if not start_date or not end_date:
        raise Exception("Must include both start_date and end_date")

    start_dt_local = datetime.fromisoformat(start_date)
    end_dt_local = datetime.fromisoformat(end_date)

    start_dt_utc = start_dt_local.astimezone(zoneinfo.ZoneInfo("UTC"))
    end_dt_utc = end_dt_local.astimezone(zoneinfo.ZoneInfo("UTC"))
    return (start_dt_utc, end_dt_utc)


def parse_date(string_date):
    return datetime.strptime(
        string_date,
        "%Y-%m-%dT%H:%M:%S.%f%z")
