"""Tests for offpeak/weather/outlook.py against real Open-Meteo responses (Köln)."""

import pandas as pd
import pytest

from offpeak.weather.open_meteo import parse_solar_check, parse_weather
from offpeak.weather.outlook import daily_outlook, generation, pv_kw, solar_accuracy

TZ = "Europe/Berlin"


@pytest.fixture
def weather(load_fixture):
    return parse_weather(load_fixture("weather_sample.json"))


@pytest.fixture
def check(load_fixture):
    return parse_solar_check(
        load_fixture("weather_previous_runs.json"), load_fixture("weather_satellite.json")
    )


def test_pv_power_from_irradiance():
    assert list(pv_kw(pd.Series([1000.0, 0.0, None, -5.0]), 60)) == [51.0, 0.0, 0.0, 0.0]


def test_generation_per_slot(weather):
    gen = generation(weather, pv_kwp=60, wind_kw=30)
    assert len(gen) == len(weather)
    assert gen["pv_kw"].max() <= 60 * 0.85
    assert gen["wind_kw"].between(0, 30).all()
    assert (generation(weather, 60, 0)["wind_kw"] == 0).all()


def test_daily_outlook_adds_up_energy(weather):
    gen = generation(weather, pv_kwp=60, wind_kw=30)
    days = daily_outlook(weather, gen, TZ)
    assert len(days) >= 2
    # energy = power x 0.25 h per 15-minute slot, summed over the whole period
    assert days["solar_kwh"].sum() == pytest.approx(gen["pv_kw"].sum() * 0.25)
    assert (days["temp_min"] <= days["temp_max"]).all()
    assert days["label"].ne("").all()


def test_solar_check_matches_hours_and_shifts_to_hour_start(check, load_fixture):
    raw = load_fixture("weather_satellite.json")["hourly"]
    assert check["ts"].dt.minute.eq(0).all()
    # the satellite value stamped 13:00 describes 12:00-13:00
    stamp = raw["time"][13]
    row = check[check["ts"] == pd.Timestamp(stamp - 3600, unit="s", tz="UTC")].iloc[0]
    assert row["measured_wm2"] == raw["global_tilted_irradiance"][13]


def test_solar_accuracy(check):
    days, summary = solar_accuracy(check, kwp=60, tz=TZ)
    assert 5 <= summary["days"] <= 8
    assert summary["mae_kwh"] >= 0 and summary["mae_pct"] >= 0
    error = days["forecast_kwh"] - days["measured_kwh"]
    assert summary["mae_kwh"] == pytest.approx(error.abs().mean())
