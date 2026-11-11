"""The weather that moves German electricity prices, from Open-Meteo (no API key).

German prices fall when the wind blows in the north (most wind farms stand there) and when
the sun shines in the south (most solar panels). So instead of the weather at one site we
average a few points across the country (docs/PLAN.md section 9.4):

- wind at 100 m, turbine height, at six points in northern Germany
- sunlight on flat ground at three points in southern Germany

One request asks for all nine points; Open-Meteo then answers with a list, one forecast per
point, in the order we asked. `past_days` adds the days before today, so the same call also
gives history for comparing with past prices.

Like in open_meteo.py, sunlight is the mean of the hour *before* the timestamp, so we move it
back one hour to key it on the hour start. Wind is the value at the full hour.
"""

import pandas as pd

from offpeak import http
from offpeak.config import OPEN_METEO_MODEL, OPEN_METEO_URL
from offpeak.weather.open_meteo import WeatherSourceError

NORTH_WIND = [
    ("Emden", 53.37, 7.21),
    ("Husum", 54.48, 9.05),
    ("Bremen", 53.08, 8.80),
    ("Rostock", 54.09, 12.13),
    ("Magdeburg", 52.13, 11.62),
    ("Cottbus", 51.76, 14.33),
]
SOUTH_SUN = [
    ("Munich", 48.14, 11.58),
    ("Stuttgart", 48.78, 9.18),
    ("Nuremberg", 49.45, 11.08),
]
POINTS = NORTH_WIND + SOUTH_SUN
COLUMNS = ["ts", "wind_north_ms", "sun_south_wm2"]


def build_params(past_days: int = 0, forecast_days: int = 3) -> dict:
    return {
        "latitude": ",".join(str(lat) for _, lat, _ in POINTS),
        "longitude": ",".join(str(lon) for _, _, lon in POINTS),
        "models": OPEN_METEO_MODEL,
        "hourly": "wind_speed_100m,shortwave_radiation",
        "wind_speed_unit": "ms",
        "past_days": past_days,
        "forecast_days": forecast_days,
        "timeformat": "unixtime",
    }


def _point_frame(block: dict) -> pd.DataFrame:
    hourly = block["hourly"]
    return pd.DataFrame(
        {
            "ts": pd.to_datetime(hourly["time"], unit="s", utc=True),
            "wind": pd.to_numeric(pd.Series(hourly["wind_speed_100m"]), errors="coerce"),
            "sun": pd.to_numeric(pd.Series(hourly["shortwave_radiation"]), errors="coerce"),
        }
    )


def parse_drivers(payload: list[dict] | dict) -> pd.DataFrame:
    """One row per hour start (UTC): mean wind in the north, mean sunlight in the south."""
    blocks = payload if isinstance(payload, list) else [payload]
    if len(blocks) != len(POINTS):
        raise WeatherSourceError(f"expected {len(POINTS)} points, got {len(blocks)}")
    frames = [_point_frame(b) for b in blocks]
    north = pd.concat(frames[: len(NORTH_WIND)]).groupby("ts")["wind"].mean()
    south = pd.concat(frames[len(NORTH_WIND) :]).groupby("ts")["sun"].mean()
    south.index = south.index - pd.Timedelta(hours=1)  # mean of the hour before -> hour start
    out = pd.DataFrame({"wind_north_ms": north, "sun_south_wm2": south}).dropna(how="all")
    out = out.loc[out.index >= north.index.min()]  # drop the hour the shift pushed earlier
    return out.rename_axis("ts").reset_index()[COLUMNS]


def fetch_drivers(past_days: int = 0, forecast_days: int = 3) -> pd.DataFrame:
    """National wind and sun, hourly, from `past_days` ago to `forecast_days` ahead."""
    response = http.get(OPEN_METEO_URL, params=build_params(past_days, forecast_days))
    if response.status_code != 200:
        raise WeatherSourceError(f"Open-Meteo HTTP {response.status_code}: {response.text[:200]}")
    return parse_drivers(response.json())


def daily_wind(drivers: pd.DataFrame, tz: str) -> pd.DataFrame:
    """Average wind in the north per local day. Columns: day, wind_north_ms."""
    day = drivers["ts"].dt.tz_convert(tz).dt.date.rename("day")
    return drivers["wind_north_ms"].groupby(day).mean().reset_index()
