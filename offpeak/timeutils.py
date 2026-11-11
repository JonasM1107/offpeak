"""Time helpers shared by every module.

Rule for the whole project: timestamps are stored in UTC, one row per 15-minute
slot start. Local time is only for the screen.
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

SLOT = timedelta(minutes=15)


def day_slots(day: date, tz: str) -> pd.DatetimeIndex:
    """UTC start of every 15-minute slot in one local calendar day.

    A normal day has 96 slots. The day clocks go forward has 92, the day they
    go back has 100. Example: day_slots(date(2026, 3, 29), "Europe/Berlin").
    """
    start = pd.Timestamp(day).tz_localize(tz)
    end = pd.Timestamp(day + timedelta(days=1)).tz_localize(tz)
    return pd.date_range(start, end, freq=SLOT, inclusive="left").tz_convert("UTC")


def to_local(ts: pd.Series | pd.DatetimeIndex, tz: str) -> pd.Series | pd.DatetimeIndex:
    """Convert UTC timestamps to local time, for display only."""
    if isinstance(ts, pd.Series):
        return ts.dt.tz_convert(tz)
    return ts.tz_convert(tz)


def floor_to_slot(ts: pd.Series | pd.DatetimeIndex) -> pd.Series | pd.DatetimeIndex:
    """Convert timestamps to UTC and floor them to the start of their 15-minute slot."""
    utc = pd.to_datetime(ts, utc=True)
    if isinstance(utc, pd.Series):
        return utc.dt.floor(SLOT)
    return utc.floor(SLOT)


def market_today(now: datetime | None = None, tz: str = "Europe/Berlin") -> date:
    """Today's date in market time, not in the computer's own time zone."""
    now = now or datetime.now(UTC)
    return now.astimezone(ZoneInfo(tz)).date()
