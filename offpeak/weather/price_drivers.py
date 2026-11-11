"""The weather that moves German electricity prices, as it was *forecast* at the time.

Wind in the north and sun in the south decide how much cheap power is on the grid, so they
move day-ahead prices more than anything else. The price model (offpeak/forecast/model.py)
uses them, and it must learn from forecasts, not from measured weather: in real use it only
ever sees a forecast, and a forecast 5 days ahead is much less sure than the weather that
then happened.

Open-Meteo's previous-runs API gives, for every hour, what the forecast said k days before
(`..._previous_day{k}`, k = 1..7). We use the ECMWF IFS model: it is the one with all seven
days filled (DWD ICON stops after about 7 days ahead). The same request also covers the
coming days, so training and live forecasts come from the same model and the same lead.

Response shape (timeformat=unixtime, several points -> a list, one entry per point):

    [{"hourly": {"time": [unix, ...], "wind_speed_100m_previous_day2": [...], ...}}, ...]

Radiation is the mean of the hour *before* the timestamp, so it moves back one hour to the
hour start (same trap as in open_meteo.py). Wind and temperature are values at the full hour.
"""

from datetime import date

import numpy as np
import pandas as pd

from offpeak import http
from offpeak.config import OPEN_METEO_PREVIOUS_RUNS_URL

MODEL = "ecmwf_ifs025"
LEADS = range(1, 8)  # forecast made k days before the hour

# (latitude, longitude): where most wind turbines and solar panels are
WIND_POINTS = [
    (54.48, 9.05),  # Husum, North Sea coast
    (53.37, 7.21),  # Emden, East Frisia
    (54.09, 12.10),  # Rostock, Baltic coast
    (52.13, 11.62),  # Magdeburg, Saxony-Anhalt
    (52.40, 13.00),  # Brandenburg
]
SUN_POINTS = [
    (48.14, 11.58),  # Munich
    (48.78, 9.18),  # Stuttgart
    (49.45, 11.08),  # Nuremberg
    (47.99, 7.85),  # Freiburg
]
TEMP_POINTS = [(51.31, 9.48)]  # Kassel, the middle of Germany

WIND, SUN, TEMP = "wind_speed_100m", "shortwave_radiation", "temperature_2m"

# A typical turbine: nothing below 3 m/s, full power from 12 m/s, power grows with speed³.
CUT_IN_MS, RATED_MS = 3.0, 12.0


class DriverSourceError(RuntimeError):
    pass


def turbine_share(speed_ms: pd.Series | np.ndarray) -> np.ndarray:
    """Share of its full power (0..1) a typical turbine delivers at this wind speed (100 m)."""
    v = np.clip(np.asarray(speed_ms, dtype=float), CUT_IN_MS, RATED_MS)
    return (v**3 - CUT_IN_MS**3) / (RATED_MS**3 - CUT_IN_MS**3)


def build_params(points: list[tuple], variable: str, start: date, end: date) -> dict:
    return {
        "latitude": ",".join(str(p[0]) for p in points),
        "longitude": ",".join(str(p[1]) for p in points),
        "hourly": ",".join(f"{variable}_previous_day{k}" for k in LEADS),
        "models": MODEL,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "timezone": "GMT",
        "timeformat": "unixtime",
        "wind_speed_unit": "ms",
    }


def parse_points(payload, variable: str, name: str, shift_hours: int = 0) -> pd.DataFrame:
    """Average over the points, one column per lead: `{name}_{k}`, indexed by UTC hour start.
    For wind the average is of the turbine share, not of the speed."""
    points = payload if isinstance(payload, list) else [payload]
    frames = []
    for point in points:
        block = point["hourly"]
        ts = pd.to_datetime(block["time"], unit="s", utc=True) - pd.Timedelta(hours=shift_hours)
        cols = {}
        for k in LEADS:
            values = pd.Series(block[f"{variable}_previous_day{k}"], dtype=float).to_numpy()
            if name == "wind":
                values = np.where(np.isnan(values), np.nan, turbine_share(values))
            cols[f"{name}_{k}"] = values
        frames.append(pd.DataFrame(cols, index=ts))
    return pd.concat(frames).groupby(level=0).mean()  # NaN stays NaN unless every point has it


def _get(points, variable: str, start: date, end: date):
    response = http.get(
        OPEN_METEO_PREVIOUS_RUNS_URL, params=build_params(points, variable, start, end)
    )
    payload = response.json() if response.content else {}
    if response.status_code != 200 or (isinstance(payload, dict) and payload.get("error")):
        reason = payload.get("reason", response.text) if isinstance(payload, dict) else ""
        raise DriverSourceError(f"Open-Meteo previous runs: HTTP {response.status_code}: {reason}")
    return payload


def fetch_drivers(start: date, end: date) -> pd.DataFrame:
    """Wind (turbine share), sun (W/m²) and temperature (°C) as forecast 1..7 days before
    each hour, from `start` to `end` (UTC dates, the end may lie in the coming days)."""
    wind = parse_points(_get(WIND_POINTS, WIND, start, end), WIND, "wind")
    sun = parse_points(_get(SUN_POINTS, SUN, start, end), SUN, "sun", shift_hours=1)
    temp = parse_points(_get(TEMP_POINTS, TEMP, start, end), TEMP, "temp")
    return wind.join(sun, how="outer").join(temp, how="outer")
