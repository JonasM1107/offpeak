"""From weather to energy: the site's expected solar and wind output, a 7-day outlook, and
how good yesterday's solar forecast was.

Solar uses the same simple model as offpeak/demo_site.py: power = irradiance on the panel
(GTI, W/m²) / 1000 × kWp × 0.85, where 0.85 covers inverter, wiring and heat losses. Wind uses
the generic small-turbine power curve from demo_site, with the 10 m forecast wind scaled up by
30 % to hub height.
"""

import pandas as pd

from offpeak.demo_site import turbine_kw
from offpeak.weather.codes import weather_label

PERFORMANCE_RATIO = 0.85  # same as offpeak/demo_site.py
HUB_HEIGHT_FACTOR = 1.3
SUNNY_WM2 = 120  # an hour counts as sunny from this irradiance on the panel


def pv_kw(gti_wm2: pd.Series, kwp: float) -> pd.Series:
    """Solar power in kW from irradiance on the tilted panel."""
    return gti_wm2.fillna(0).clip(lower=0) / 1000 * kwp * PERFORMANCE_RATIO


def generation(weather: pd.DataFrame, pv_kwp: float, wind_kw: float) -> pd.DataFrame:
    """Expected power per weather slot: ts, pv_kw, wind_kw (all turbines together; the power
    curve is linear in the rated power)."""
    wind = weather["wind_ms"].fillna(0) * HUB_HEIGHT_FACTOR
    return pd.DataFrame(
        {
            "ts": weather["ts"],
            "pv_kw": pv_kw(weather["gti_wm2"], pv_kwp),
            "wind_kw": [turbine_kw(v, wind_kw) for v in wind] if wind_kw else 0.0,
        }
    )


def _slot_hours(ts: pd.Series) -> float:
    """Length of one slot in hours (0.25 for 15-minute data)."""
    return ts.diff().dropna().median() / pd.Timedelta(hours=1) if len(ts) > 1 else 1.0


def daily_outlook(weather: pd.DataFrame, gen: pd.DataFrame, tz: str) -> pd.DataFrame:
    """One row per local day: date, temp_min, temp_max, label (weather around midday),
    sun_hours, solar_kwh, wind_kwh, best_solar (the three strongest solar hours, as text)."""
    h = _slot_hours(weather["ts"])
    df = weather.merge(gen, on="ts")
    local = df["ts"].dt.tz_convert(tz)
    df["day"], df["hour"] = local.dt.date, local.dt.hour
    rows = []
    for day, d in df.groupby("day"):
        midday = d[d["hour"].between(11, 14)]
        code = (midday if not midday.empty else d)["weather_code"].mode()
        by_hour = d.groupby("hour")["pv_kw"].mean()
        best = by_hour[by_hour > 0.1].nlargest(3).index.sort_values()
        rows.append(
            {
                "date": day,
                "temp_min": d["temp_c"].min(),
                "temp_max": d["temp_c"].max(),
                "label": weather_label(code.iloc[0] if not code.empty else None),
                "sun_hours": float((d["gti_wm2"] >= SUNNY_WM2).sum() * h),
                "solar_kwh": float(d["pv_kw"].sum() * h),
                "wind_kwh": float(d["wind_kw"].sum() * h),
                "best_solar": f"{best.min():02d}–{best.max() + 1:02d}" if len(best) else "–",
            }
        )
    return pd.DataFrame(rows)


def solar_accuracy(check: pd.DataFrame, kwp: float, tz: str) -> tuple[pd.DataFrame, dict]:
    """How well the day-ahead solar forecast matched the satellite measurement.

    `check` has ts, forecast_wm2, measured_wm2 per hour. Returns one row per local day
    (date, forecast_kwh, measured_kwh, error_pct) and a summary: mean absolute daily error
    in kWh and %, and the bias (positive = the forecast promised too much)."""
    df = check.assign(
        day=check["ts"].dt.tz_convert(tz).dt.date,
        forecast_kw=pv_kw(check["forecast_wm2"], kwp),
        measured_kw=pv_kw(check["measured_wm2"], kwp),
    )
    days = df.groupby("day").agg(
        forecast_kwh=("forecast_kw", "sum"), measured_kwh=("measured_kw", "sum")
    )
    days = days[df.groupby("day").size() >= 20]  # only (nearly) complete days
    days["error_pct"] = (
        (days["forecast_kwh"] - days["measured_kwh"])
        / days["measured_kwh"].where(days["measured_kwh"] > 0)
        * 100
    )
    total = days["measured_kwh"].sum()
    abs_err = (days["forecast_kwh"] - days["measured_kwh"]).abs()
    summary = {
        "days": len(days),
        "mae_kwh": float(abs_err.mean()) if len(days) else 0.0,
        "mae_pct": float(abs_err.sum() / total * 100) if total else 0.0,
        "bias_pct": float((days["forecast_kwh"].sum() - total) / total * 100) if total else 0.0,
    }
    return days.reset_index().rename(columns={"day": "date"}), summary
