"""Daily outlook, checked against the saved Open-Meteo response for Köln (11 and 12 Nov)."""

from datetime import date

import pandas as pd
import pytest

from offpeak.weather.daily import daily_outlook
from offpeak.weather.open_meteo import parse_weather


@pytest.fixture
def weather(load_fixture):
    return parse_weather(load_fixture("weather_sample.json"))


def test_one_row_per_local_day(weather):
    days = daily_outlook(weather, kwp=60, tz="Europe/Berlin")
    assert days["day"].is_unique
    assert set(days["day"]) <= {date(2026, 11, 11), date(2026, 11, 12)}


def test_solar_is_the_sum_of_quarter_hours(weather):
    days = daily_outlook(weather, kwp=60, tz="Europe/Berlin")
    first = days.iloc[0]
    rows = weather[weather["ts"].dt.tz_convert("Europe/Berlin").dt.date == first["day"]]
    sun = rows["gti_wm2"].sum() * 0.25 / 1000  # W/m² for 15 minutes -> kWh/m²
    assert first["sun_kwh_m2"] == pytest.approx(sun)
    assert first["solar_kwh"] == pytest.approx(sun * 60 * 0.85)


def test_temperature_range_and_most_common_code(weather):
    days = daily_outlook(weather, kwp=60, tz="Europe/Berlin")
    first = days.iloc[0]
    rows = weather[weather["ts"].dt.tz_convert("Europe/Berlin").dt.date == first["day"]]
    assert first["temp_min"] == rows["temp_c"].min()
    assert first["temp_max"] == rows["temp_c"].max()
    assert first["weather_code"] == rows["weather_code"].mode().iloc[0]


def test_cut_off_days_at_the_edges_are_left_out():
    ts = pd.date_range("2026-11-11 22:00", periods=8, freq="15min", tz="UTC")  # 2 hours
    short = pd.DataFrame(
        {
            "ts": ts,
            "gti_wm2": 0.0,
            "temp_c": 5.0,
            "wind_ms": 3.0,
            "precip_mm": 0.0,
            "weather_code": 3.0,
        }
    )
    assert daily_outlook(short, kwp=60, tz="Europe/Berlin").empty
