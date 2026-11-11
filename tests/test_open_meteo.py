"""Tests against a real Open-Meteo response for Köln (two days, captured 11 Nov 2026)."""

import pandas as pd
import pytest

from offpeak.models import Site
from offpeak.weather.codes import weather_label
from offpeak.weather.open_meteo import build_params, open_meteo_azimuth, parse_weather


@pytest.fixture
def raw(load_fixture):
    return load_fixture("weather_sample.json")


@pytest.fixture
def weather(raw):
    return parse_weather(raw)


def test_one_row_per_quarter_hour_in_utc(raw, weather):
    # two days; the last slot (23:45) would need the value stamped 00:00 the day after
    assert len(weather) == 191
    assert weather["ts"].iloc[0] == pd.Timestamp(raw["hourly"]["time"][0], unit="s", tz="UTC")
    assert weather["ts"].is_unique
    assert weather["ts"].diff().dropna().eq(pd.Timedelta(minutes=15)).all()


def test_radiation_moves_back_to_slot_start(raw, weather):
    m15 = raw["minutely_15"]
    # the value stamped 12:15 describes 12:00-12:15, so it belongs to the slot starting 12:00
    noon = raw["hourly"]["time"][12]
    i = m15["time"].index(noon + 900)
    row = weather[weather["ts"] == pd.Timestamp(noon, unit="s", tz="UTC")].iloc[0]
    assert row["gti_wm2"] == m15["global_tilted_irradiance"][i]
    assert row["precip_mm"] == m15["precipitation"][i]


def test_hourly_value_repeats_across_its_four_slots(raw, weather):
    hourly = raw["hourly"]
    hour = weather[
        weather["ts"].dt.floor("h") == pd.Timestamp(hourly["time"][10], unit="s", tz="UTC")
    ]
    assert len(hour) == 4
    assert (hour["temp_c"] == hourly["temperature_2m"][10]).all()
    assert (hour["wind_ms"] == hourly["wind_speed_10m"][10]).all()


def test_missing_values_stay_missing(raw):
    raw["minutely_15"]["global_tilted_irradiance"][50] = None
    raw["hourly"]["temperature_2m"][30] = None
    weather = parse_weather(raw)
    assert weather["gti_wm2"].isna().sum() == 1
    assert weather["temp_c"].isna().sum() == 4  # one hourly null covers four slots
    assert (weather["gti_wm2"].dropna() >= 0).all()


def test_weather_code_label(raw, weather):
    assert weather_label(weather["weather_code"].iloc[0]) == weather_label(
        raw["hourly"]["weather_code"][0]
    )
    assert weather_label(61) == "Light rain"
    assert weather_label(float("nan")) == "–"


def test_azimuth_conversion():
    assert open_meteo_azimuth(180) == 0  # south
    assert open_meteo_azimuth(90) == -90  # east
    assert open_meteo_azimuth(270) == 90  # west


def test_request_parameters():
    params = build_params(Site(id=1, name="x", lat=48.1, lon=11.6, azimuth_deg=180), days=7)
    assert params["models"] == "dwd_icon_seamless"
    assert params["timeformat"] == "unixtime"
    assert params["wind_speed_unit"] == "ms"
    assert params["azimuth"] == 0
