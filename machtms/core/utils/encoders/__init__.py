import datetime, json


class TimedeltaEncoder(json.JSONEncoder):
    def default(self, obj):
        # Handle datetime.timedelta
        if isinstance(obj, datetime.timedelta):
            # Convert timedelta to string, e.g. "0:05:00" for 5 minutes
            return str(obj)
        # Handle datetime.datetime or datetime.date or datetime.time
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            # Convert to ISO format, e.g. "2025-01-01T12:34:56"
            return obj.isoformat()
        return super().default(obj)
