"""Turn the 15-minute weather forecast into one row per local day, for the Weather page."""

import pandas as pd

from offpeak.generation.pv import pv_kw
from offpeak.timeutils import SLOT

MIN_HOURS = 20  # the first and last forecast day are cut off; shorter days are left out


def daily_outlook(weather: pd.DataFrame, kwp: float, tz: str) -> pd.DataFrame:
    """One row per local day.

    Columns: day, sun_kwh_m2 (sunlight on the panel), solar_kwh (expected yield for `kwp`),
    temp_min, temp_max, wind_max (m/s at 10 m), precip_mm, weather_code (most common).
    """
    slot_h = SLOT / pd.Timedelta(hours=1)  # 0.25 hours per slot
    df = weather.assign(
        day=weather["ts"].dt.tz_convert(tz).dt.date,
        sun_kwh_m2=weather["gti_wm2"] / 1000 * slot_h,
        solar_kwh=pv_kw(weather["gti_wm2"], kwp) * slot_h,
    )
    days = df.groupby("day").agg(
        slots=("ts", "size"),
        sun_kwh_m2=("sun_kwh_m2", "sum"),
        solar_kwh=("solar_kwh", "sum"),
        temp_min=("temp_c", "min"),
        temp_max=("temp_c", "max"),
        wind_max=("wind_ms", "max"),
        precip_mm=("precip_mm", "sum"),
        weather_code=("weather_code", lambda s: s.mode().iloc[0] if s.notna().any() else None),
    )
    days = days[days["slots"] * slot_h >= MIN_HOURS].drop(columns="slots")
    return days.reset_index()
