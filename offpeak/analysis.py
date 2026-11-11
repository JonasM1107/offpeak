"""Simple price analysis used by the dashboard. Works on any prices table
with columns ts (UTC) and eur_mwh, at 15- or 60-minute resolution."""

from dataclasses import dataclass

import pandas as pd


@dataclass
class Window:
    start: pd.Timestamp  # UTC, first slot start
    end: pd.Timestamp  # UTC, end of the last slot
    avg_eur_mwh: float


def _slot_length(prices: pd.DataFrame) -> pd.Timedelta:
    return pd.Timedelta(minutes=int(prices["resolution_min"].iloc[0]))


def best_window(prices: pd.DataFrame, hours: float, cheapest: bool = True) -> Window | None:
    """The block of consecutive slots lasting `hours` with the lowest (or highest) average price.

    Returns None if there are not enough consecutive slots.
    """
    if prices.empty:
        return None
    df = prices.sort_values("ts").reset_index(drop=True)
    slot = _slot_length(df)
    n = int(pd.Timedelta(hours=hours) / slot)
    if n < 1 or len(df) < n:
        return None
    avg = df["eur_mwh"].rolling(n).mean()
    # only accept blocks without a gap: first and last slot exactly n-1 slots apart
    span = df["ts"] - df["ts"].shift(n - 1)
    avg = avg.where(span == slot * (n - 1))
    if avg.isna().all():
        return None
    last = int(avg.idxmin() if cheapest else avg.idxmax())
    first = last - n + 1
    return Window(df["ts"].iloc[first], df["ts"].iloc[last] + slot, float(avg.iloc[last]))


def window_mask(prices: pd.DataFrame, window: Window | None) -> pd.Series:
    """True for every row whose slot lies inside the window."""
    if window is None:
        return pd.Series(False, index=prices.index)
    return (prices["ts"] >= window.start) & (prices["ts"] < window.end)


def current_price(prices: pd.DataFrame, now: pd.Timestamp) -> pd.Series | None:
    """The row whose slot contains `now`, or None."""
    if prices.empty:
        return None
    slot = _slot_length(prices)
    hit = prices[(prices["ts"] <= now) & (prices["ts"] + slot > now)]
    return None if hit.empty else hit.iloc[0]


def ct_kwh(eur_mwh: float) -> float:
    """EUR/MWh to ct/kWh (divide by 10)."""
    return eur_mwh / 10


def daily_stats(prices: pd.DataFrame, tz: str = "Europe/Berlin") -> pd.DataFrame:
    """Min, mean and max per local day, in ct/kWh. Columns: day, min, mean, max."""
    day = prices["ts"].dt.tz_convert(tz).dt.date.rename("day")
    stats = (prices["eur_mwh"] / 10).groupby(day).agg(["min", "mean", "max"])
    return stats.reset_index()


def hourly_profile(prices: pd.DataFrame, tz: str = "Europe/Berlin") -> pd.DataFrame:
    """Average ct/kWh per local hour of day, workdays against weekends.
    Columns: hour, workday, weekend."""
    t = prices["ts"].dt.tz_convert(tz)
    kind = t.dt.day_of_week.map(lambda d: "weekend" if d >= 5 else "workday")
    profile = (prices["eur_mwh"] / 10).groupby([t.dt.hour.rename("hour"), kind]).mean()
    return profile.unstack().reindex(columns=["workday", "weekend"]).reset_index()
