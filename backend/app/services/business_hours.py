"""Business hours and timezone utilities."""

from datetime import datetime, time
from typing import Optional
import os

# Default business timezone
DEFAULT_TIMEZONE = os.getenv("BUSINESS_TIMEZONE", "America/New_York")

# Default business hours (24h format)
DEFAULT_OPEN = time(9, 0)
DEFAULT_CLOSE = time(18, 0)
DEFAULT_DAYS_OPEN = [0, 1, 2, 3, 4, 5]  # Mon-Sat (0=Mon in Python)


def is_business_hours(
    dt: Optional[datetime] = None,
    open_time: time = DEFAULT_OPEN,
    close_time: time = DEFAULT_CLOSE,
    days_open: list = DEFAULT_DAYS_OPEN,
) -> bool:
    """Check if the given datetime falls within business hours."""
    if dt is None:
        dt = datetime.now()

    if dt.weekday() not in days_open:
        return False

    current_time = dt.time()
    return open_time <= current_time < close_time


def next_business_hour(
    dt: Optional[datetime] = None,
    open_time: time = DEFAULT_OPEN,
    days_open: list = DEFAULT_DAYS_OPEN,
) -> datetime:
    """Return the next datetime when business is open."""
    from datetime import timedelta

    if dt is None:
        dt = datetime.now()

    # Try today if before open
    candidate = dt.replace(hour=open_time.hour, minute=open_time.minute, second=0, microsecond=0)
    if candidate > dt and dt.weekday() in days_open:
        return candidate

    # Try subsequent days
    for i in range(1, 8):
        candidate = dt + timedelta(days=i)
        candidate = candidate.replace(hour=open_time.hour, minute=open_time.minute, second=0, microsecond=0)
        if candidate.weekday() in days_open:
            return candidate

    return dt  # fallback
