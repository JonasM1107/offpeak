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
    # 60 kWp at 1000 W/m², panels at 25 °C: 8.7 % system losses, then about 96 % inverter
    out = pv_kw(pd.Series([1000.0, 0.0, None, -5.0]), 60)
    assert out.round(2).tolist() == [52.66, 0.0, 0.0, 0.0]


def test_generation_per_slot(weather):
    gen = generation(weather, pv_kwp=60, wind_kw=30)
    assert len(gen) == len(weather)
    assert gen["pv_kw"].between(0, 60).all()  # never above the rating
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


def test_view_payload_has_every_list(weather, check):
    from offpeak.weather.outlook import view_payload

    gen = generation(weather, 60, 30)
    days = daily_outlook(weather, gen, TZ)
    p = view_payload(weather, gen, days, check, 60, TZ)
    s = p["series"]
    assert len(s["t"]) == len(s["pv_kw"]) == len(s["temp_c"]) == len(weather)
    assert p["days"][0]["end"] - p["days"][0]["start"] in (23 * 3600, 24 * 3600, 25 * 3600)
    assert len(p["accuracy"]["hourly"]["t"]) == len(check)
    assert view_payload(weather, gen, days, None, 60, TZ)["accuracy"] is None


def test_generation_without_temperature(weather):
    # a weather frame without temperature still works: panels taken at 25 °C
    gen = generation(weather.drop(columns=["temp_c"]), pv_kwp=60, wind_kw=0)
    assert gen["pv_kw"].between(0, 60).all()
