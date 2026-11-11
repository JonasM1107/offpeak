"""Weather forecast from Open-Meteo, DWD ICON models (no API key).

Response shape with timeformat=unixtime (see tests/fixtures/weather_sample.json):

    {"utc_offset_seconds": 0,
     "hourly":      {"time": [unix, ...], "temperature_2m": [...], ...},
     "minutely_15": {"time": [unix, ...], "global_tilted_irradiance": [...], ...}}

Two traps this module handles:

1. Radiation and precipitation are the mean (or sum) of the 15 minutes *before* the
   timestamp. Our rows are keyed on the slot *start*, so we move them back one slot.
2. Temperature, cloud cover and wind are only hourly. They are instantaneous values at the
   full hour, and we repeat each one across the four slots of that hour.

Missing values stay missing (NaN); they are never turned into 0.
"""

import pandas as pd

from offpeak import http
from offpeak.config import FORECAST_DAYS, OPEN_METEO_MODEL, OPEN_METEO_URL, SLOT_MINUTES
from offpeak.models import Site

# Open-Meteo name -> our column name
MINUTELY_15 = {
    "global_tilted_irradiance": "gti_wm2",
    "shortwave_radiation": "ghi_wm2",
    "precipitation": "precip_mm",
}
HOURLY = {
    "temperature_2m": "temp_c",
    "cloud_cover": "cloud_pct",
    "wind_speed_10m": "wind_ms",
    "weather_code": "weather_code",  # WMO code, see offpeak/weather/codes.py
}
COLUMNS = ["ts", *MINUTELY_15.values(), *HOURLY.values()]


class WeatherSourceError(RuntimeError):
    """Open-Meteo answered with an error."""


def open_meteo_azimuth(compass_deg: float) -> float:
    """Our sites use a compass bearing (180 = south); Open-Meteo uses 0 = south, -90 = east."""
    return (compass_deg % 360) - 180


def build_params(site: Site, days: int = FORECAST_DAYS) -> dict:
    return {
        "latitude": site.lat,
        "longitude": site.lon,
        "models": OPEN_METEO_MODEL,
        "minutely_15": ",".join(MINUTELY_15),
        "hourly": ",".join(HOURLY),
        "tilt": site.tilt_deg,
        "azimuth": open_meteo_azimuth(site.azimuth_deg),
        "wind_speed_unit": "ms",
        "forecast_days": days,
        "timeformat": "unixtime",
    }


def _block_to_frame(block: dict, names: dict) -> pd.DataFrame:
    df = pd.DataFrame({"ts": pd.to_datetime(block["time"], unit="s", utc=True)})
    for api_name, column in names.items():
        df[column] = pd.to_numeric(pd.Series(block[api_name]), errors="coerce")
    return df


def parse_weather(payload: dict) -> pd.DataFrame:
    """One row per 15-minute slot start (UTC) with every weather column."""
    slots = _block_to_frame(payload["minutely_15"], MINUTELY_15)
    slots["ts"] = slots["ts"] - pd.Timedelta(minutes=SLOT_MINUTES)  # trap 1

    hourly = _block_to_frame(payload["hourly"], HOURLY)
    slots["hour"] = slots["ts"].dt.floor("h")  # trap 2
    merged = slots.merge(hourly.rename(columns={"ts": "hour"}), on="hour", how="left")
    # The shift pushes the first value to before the forecast start; drop that one slot.
    merged = merged[merged["ts"] >= hourly["ts"].min()]
    return merged[COLUMNS].sort_values("ts").reset_index(drop=True)


def fetch_weather(site: Site, days: int = FORECAST_DAYS) -> pd.DataFrame:
    """Forecast for one site, one row per 15-minute slot (columns: see COLUMNS)."""
    response = http.get(OPEN_METEO_URL, params=build_params(site, days))
    if response.status_code != 200:
        try:
            reason = response.json().get("reason", response.text)
        except ValueError:
            reason = response.text
        raise WeatherSourceError(f"Open-Meteo HTTP {response.status_code}: {reason[:200]}")
    return parse_weather(response.json())
