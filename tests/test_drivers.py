"""National wind and sun, checked against a saved Open-Meteo answer for nine points
(captured 11 Nov 2026, one past day and two forecast days)."""

import pandas as pd
import pytest

from offpeak.weather.drivers import (
    NORTH_WIND,
    POINTS,
    build_params,
    daily_wind,
    parse_drivers,
)
from offpeak.weather.open_meteo import WeatherSourceError


@pytest.fixture
def raw(load_fixture):
    return load_fixture("drivers_sample.json")


@pytest.fixture
def national(raw):
    return parse_drivers(raw)


def test_asks_for_every_point_in_one_call():
    params = build_params(past_days=30, forecast_days=1)
    assert len(params["latitude"].split(",")) == len(POINTS)
    assert len(params["longitude"].split(",")) == len(POINTS)
    assert params["wind_speed_unit"] == "ms"
    assert params["past_days"] == 30


def test_one_row_per_hour_in_utc(national):
    assert national["ts"].is_unique
    assert national["ts"].diff().dropna().eq(pd.Timedelta(hours=1)).all()
    assert str(national["ts"].dt.tz) == "UTC"


def test_wind_is_the_mean_of_the_northern_points(raw, national):
    first = pd.Timestamp(raw[0]["hourly"]["time"][0], unit="s", tz="UTC")
    expected = sum(p["hourly"]["wind_speed_100m"][0] for p in raw[: len(NORTH_WIND)])
    row = national[national["ts"] == first].iloc[0]
    assert row["wind_north_ms"] == pytest.approx(expected / len(NORTH_WIND))


def test_sun_moves_back_to_the_hour_start(raw, national):
    # the value stamped 12:00 is the mean of 11:00-12:00, so it belongs to the hour 11:00
    south = raw[len(NORTH_WIND) :]
    i = 12
    stamped = pd.Timestamp(raw[0]["hourly"]["time"][i], unit="s", tz="UTC")
    expected = sum(p["hourly"]["shortwave_radiation"][i] for p in south) / len(south)
    row = national[national["ts"] == stamped - pd.Timedelta(hours=1)].iloc[0]
    assert row["sun_south_wm2"] == pytest.approx(expected)


def test_wrong_number_of_points_is_an_error(raw):
    with pytest.raises(WeatherSourceError):
        parse_drivers(raw[:3])


def test_daily_wind_per_local_day(national):
    days = daily_wind(national, "Europe/Berlin")
    assert days["day"].is_unique
    assert days["wind_north_ms"].between(0, 40).all()
