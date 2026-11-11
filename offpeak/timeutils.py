"""Time helpers. Rule: everything is stored as UTC, one row per 15-minute slot start."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from offpeak.config import MARKET_TZ, SLOT_MINUTES


def floor_to_slot(ts: pd.Series | pd.DatetimeIndex, minutes: int = SLOT_MINUTES):
    """Convert timestamps to UTC and floor them to the start of their slot."""
    utc = pd.to_datetime(ts, utc=True)
    if isinstance(utc, pd.Series):
        return utc.dt.floor(f"{minutes}min")
    return utc.floor(f"{minutes}min")


def market_day_bounds(day: date, tz: str = MARKET_TZ) -> tuple[datetime, datetime]:
    """UTC start (inclusive) and end (exclusive) of one delivery day in market time.

    A normal day is 24 hours long; the clock-change days are 23 and 25 hours.
    """
    zone = ZoneInfo(tz)
    start = datetime(day.year, day.month, day.day, tzinfo=zone)
    end = start.date() + timedelta(days=1)
    end_dt = datetime(end.year, end.month, end.day, tzinfo=zone)
    return start.astimezone(ZoneInfo("UTC")), end_dt.astimezone(ZoneInfo("UTC"))


def market_today(now: datetime | None = None, tz: str = MARKET_TZ) -> date:
    """Today's date in market time (not in the computer's own time zone)."""
    now = now or datetime.now(ZoneInfo("UTC"))
    return now.astimezone(ZoneInfo(tz)).date()
