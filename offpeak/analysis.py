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


def hourly(prices: pd.DataFrame, tz: str = "Europe/Berlin") -> pd.DataFrame:
    """One row per hour (mean of its slots), so 15-minute and older hourly prices can be
    compared. Columns: ts (UTC hour start), local (local time), ct (ct/kWh)."""
    hours = prices.set_index("ts")["eur_mwh"].resample("h").mean().dropna() / 10
    out = hours.rename("ct").reset_index()
    out["local"] = out["ts"].dt.tz_convert(tz)
    return out


def weekday_hour(prices: pd.DataFrame, tz: str = "Europe/Berlin") -> pd.DataFrame:
    """Average ct/kWh for each weekday (rows, Monday first) and local hour (columns)."""
    h = hourly(prices, tz)
    table = h.groupby([h["local"].dt.day_of_week, h["local"].dt.hour])["ct"].mean().unstack()
    return table.reindex(index=range(7), columns=range(24))


def monthly_stats(prices: pd.DataFrame, tz: str = "Europe/Berlin") -> pd.DataFrame:
    """Per month: average ct/kWh, average daily spread (highest minus lowest hour) and the
    number of hours with a negative price. Columns: month, mean, spread, negative_hours."""
    h = hourly(prices, tz)
    h["month"] = h["local"].dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    h["day"] = h["local"].dt.date
    spread = h.groupby(["month", "day"])["ct"].agg(lambda s: s.max() - s.min())
    out = h.groupby("month").agg(
        mean=("ct", "mean"), negative_hours=("ct", lambda s: (s < 0).sum())
    )
    out["spread"] = spread.groupby("month").mean()
    return out.reset_index()


def price_summary(prices: pd.DataFrame, tz: str = "Europe/Berlin") -> dict:
    """Headline numbers for a period, based on hourly prices."""
    h = hourly(prices, tz)
    daily = h.groupby(h["local"].dt.date)["ct"].agg(["mean", "min", "max"])
    return {
        "mean_ct": float(h["ct"].mean()),
        "cheapest_day": daily["mean"].idxmin(),
        "cheapest_day_ct": float(daily["mean"].min()),
        "dearest_day": daily["mean"].idxmax(),
        "dearest_day_ct": float(daily["mean"].max()),
        "negative_hours": int((h["ct"] < 0).sum()),
        "hours": len(h),
        "avg_spread_ct": float((daily["max"] - daily["min"]).mean()),
        "days": len(daily),
    }


def covers_days(prices: pd.DataFrame, start, end, tz: str = "Europe/Berlin") -> bool:
    """True if every market day from start to end has (at least) 23 hours of prices, at
    15-minute or hourly resolution. 23 because the spring clock-change day is that long."""
    if prices.empty:
        return False
    local_day = prices["ts"].dt.tz_convert(tz).dt.date
    hours = (prices["resolution_min"] / 60).groupby(local_day).sum()
    days = pd.date_range(start, end, freq="D").date
    return bool(hours.reindex(days).fillna(0).ge(23).all())


def hourly_payload(prices: pd.DataFrame, tz: str = "Europe/Berlin") -> dict:
    """Hourly prices as plain lists for an interactive chart: UTC start (unix seconds),
    ct/kWh, and the local hour, weekday (Monday = 0) and date (YYYYMMDD) of each hour."""
    h = hourly(prices, tz)
    return {
        "t": ((h["ts"] - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)).tolist(),
        "ct": h["ct"].round(2).tolist(),
        "hour": h["local"].dt.hour.tolist(),
        "wd": h["local"].dt.day_of_week.tolist(),
        "day": (
            h["local"].dt.year * 10000 + h["local"].dt.month * 100 + h["local"].dt.day
        ).tolist(),
    }
