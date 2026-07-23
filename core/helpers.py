from datetime import datetime, timezone, timedelta
from core.database import get_connection

WAT = timezone(timedelta(hours=1))


def now_wat_str():
    """Returns current WAT (UTC+1) time as 'YYYY-MM-DD HH:MM:SS'."""
    return datetime.now(WAT).strftime("%Y-%m-%d %H:%M:%S")


def today_wat_date():
    """Returns current WAT date as 'YYYY-MM-DD'."""
    return datetime.now(WAT).strftime("%Y-%m-%d")


def generate_invoice_number():
    """Generates the next invoice number for today in SC-YYYYMMDD-NNN format."""
    date_part = datetime.now(WAT).strftime("%Y%m%d")

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM dropoff_records WHERE invoice_number LIKE ?",
        (f"SC-{date_part}-%",)
    )
    count_today = cursor.fetchone()[0]
    connection.close()

    next_seq = count_today + 1
    return f"SC-{date_part}-{next_seq:03d}"


def _to_int(value, field_name):
    """Safely converts a value to int, tolerating string input from the model."""
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in ("", "null", "none"):
            return None
        try:
            return int(float(cleaned))
        except ValueError:
            raise ValueError(f"Could not interpret '{value}' as a whole number for {field_name}.")
    return int(value)


def _to_float(value, field_name):
    """Safely converts a value to float, same tolerance as _to_int."""
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in ("", "null", "none"):
            return None
        try:
            return float(cleaned)
        except ValueError:
            raise ValueError(f"Could not interpret '{value}' as a number for {field_name}.")
    return float(value)
