"""A measured day of a site, hour by hour, for the Home view's "Yesterday at home".

Input: 15-minute measurements (offpeak/load/fronius.py, or rows of site_measurements).
"""

from datetime import date

import pandas as pd

MIN_HOURS = 20  # a day with fewer measured hours is not shown


def full_days(slots: pd.DataFrame, tz: str) -> list[date]:
    """Local days with at least MIN_HOURS measured hours, oldest first."""
    if slots.empty:
        return []
    local = slots["ts"].dt.tz_convert(tz)
    hours = local.dt.floor("h").groupby(local.dt.date).nunique()
    return sorted(d for d, n in hours.items() if n >= MIN_HOURS)


def last_full_day(slots: pd.DataFrame, tz: str, before: date) -> date | None:
    """The newest full day before `before` (usually today: so yesterday if it is there)."""
    days = [d for d in full_days(slots, tz) if d < before]
    return days[-1] if days else None


def hourly_day(slots: pd.DataFrame, day: date, tz: str) -> pd.DataFrame:
    """24 rows, one per local hour 0..23 (23 or 25 on clock-change days are folded to 24 by
    hour of day): hour, pv_kw, load_kw, battery_kw (+ charging, - giving), grid_kw (+ buying,
    - selling), soc_pct. Hours without a measurement are 0 kW and keep the last charge level."""
    local = slots.assign(lt=slots["ts"].dt.tz_convert(tz))
    d = local[local["lt"].dt.date == day]
    by = d.groupby(d["lt"].dt.hour)
    out = pd.DataFrame({"hour": range(24)})

    def col(name):
        return by[name].mean().reindex(range(24)) if name in d else pd.Series(0.0, index=range(24))

    out["pv_kw"] = col("pv_kw").fillna(0).to_numpy()
    out["load_kw"] = col("load_kw").fillna(0).to_numpy()
    out["battery_kw"] = (
        col("battery_in_kw").fillna(0) - col("battery_out_kw").fillna(0)
    ).to_numpy()
    out["grid_kw"] = (col("grid_in_kw").fillna(0) - col("grid_out_kw").fillna(0)).to_numpy()
    soc = col("soc_pct").ffill().bfill()
    out["soc_pct"] = soc.fillna(0).to_numpy()
    return out
