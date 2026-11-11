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
from offpeak.config import (
    FORECAST_DAYS,
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_MODEL,
    OPEN_METEO_PREVIOUS_RUNS_URL,
    OPEN_METEO_SATELLITE_URL,
    OPEN_METEO_URL,
    SLOT_MINUTES,
)
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


# ── Forecast accuracy: what the forecast said a day ahead against satellite data ─


def _hourly_slot_start(block: dict, column: str, name: str) -> pd.DataFrame:
    """Hourly radiation is the mean of the hour *before* the timestamp: move it back."""
    df = pd.DataFrame(
        {
            "ts": pd.to_datetime(block["time"], unit="s", utc=True) - pd.Timedelta(hours=1),
            name: pd.to_numeric(pd.Series(block[column]), errors="coerce"),
        }
    )
    return df


def parse_solar_check(previous_runs: dict, satellite: dict) -> pd.DataFrame:
    """One row per hour that both sources cover: ts (UTC hour start), forecast_wm2 (what the
    forecast made one day earlier said for the panel) and measured_wm2 (satellite)."""
    forecast = _hourly_slot_start(
        previous_runs["hourly"], "global_tilted_irradiance_previous_day1", "forecast_wm2"
    )
    measured = _hourly_slot_start(satellite["hourly"], "global_tilted_irradiance", "measured_wm2")
    both = forecast.merge(measured, on="ts", how="inner").dropna()
    return both.sort_values("ts").reset_index(drop=True)


def solar_check_params(site: Site, past_days: int) -> dict:
    return {
        "latitude": site.lat,
        "longitude": site.lon,
        "tilt": site.tilt_deg,
        "azimuth": open_meteo_azimuth(site.azimuth_deg),
        "past_days": past_days,
        "timeformat": "unixtime",
    }


def fetch_solar_check(site: Site, past_days: int = 7) -> pd.DataFrame:
    """Day-ahead solar forecast against satellite measurements for the last days."""
    params = solar_check_params(site, past_days)
    runs = http.get(
        OPEN_METEO_PREVIOUS_RUNS_URL,
        params=params
        | {
            "models": OPEN_METEO_MODEL,
            "hourly": "global_tilted_irradiance_previous_day1",
            "forecast_days": 1,
        },
    )
    sat = http.get(
        OPEN_METEO_SATELLITE_URL,
        params=params | {"hourly": "global_tilted_irradiance", "forecast_days": 0},
    )
    for response in (runs, sat):
        if response.status_code != 200:
            raise WeatherSourceError(f"Open-Meteo HTTP {response.status_code}")
    return parse_solar_check(runs.json(), sat.json())


# ── Past weather, for replaying what the plan would have saved ──────────────


def parse_archive(payload: dict) -> pd.DataFrame:
    """Hourly past weather: ts (UTC hour start), gti_wm2, wind_ms, temp_c. Irradiance is the
    mean of the hour before its timestamp, so it moves back one hour; wind and temperature
    are values at the timestamp."""
    h = payload["hourly"]
    stamp = pd.to_datetime(h["time"], unit="s", utc=True)
    gti = pd.DataFrame(
        {
            "ts": stamp - pd.Timedelta(hours=1),
            "gti_wm2": pd.to_numeric(pd.Series(h["global_tilted_irradiance"]), errors="coerce"),
        }
    )
    rest = pd.DataFrame(
        {
            "ts": stamp,
            "wind_ms": pd.to_numeric(pd.Series(h["wind_speed_10m"]), errors="coerce"),
            "temp_c": pd.to_numeric(pd.Series(h["temperature_2m"]), errors="coerce"),
        }
    )
    return gti.merge(rest, on="ts", how="inner").sort_values("ts").reset_index(drop=True)


def fetch_archive(site: Site, start, end) -> pd.DataFrame:
    """Measured weather for the days start..end (both inclusive)."""
    response = http.get(
        OPEN_METEO_ARCHIVE_URL,
        params={
            "latitude": site.lat,
            "longitude": site.lon,
            "start_date": str(start),
            "end_date": str(end),
            "hourly": "global_tilted_irradiance,wind_speed_10m,temperature_2m",
            "tilt": site.tilt_deg,
            "azimuth": open_meteo_azimuth(site.azimuth_deg),
            "wind_speed_unit": "ms",
            "timeformat": "unixtime",
        },
    )
    if response.status_code != 200:
        raise WeatherSourceError(f"Open-Meteo archive HTTP {response.status_code}")
    return parse_archive(response.json())
