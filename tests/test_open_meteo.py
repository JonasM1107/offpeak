import pandas as pd
import pytest

from offpeak.models import Site
from offpeak.weather.open_meteo import build_params, open_meteo_azimuth, parse_weather


@pytest.fixture
def weather(load_fixture):
    return parse_weather(load_fixture("weather_sample.json"))


def test_one_row_per_quarter_hour_in_utc(weather):
    # two days; the last slot (23:45) would need the value stamped 00:00 the day after
    assert len(weather) == 191
    assert weather["ts"].iloc[0] == pd.Timestamp("2026-11-12 00:00", tz="UTC")
    assert str(weather["ts"].dt.tz) == "UTC"
    assert weather["ts"].is_unique
    assert weather["ts"].diff().dropna().eq(pd.Timedelta(minutes=15)).all()


def test_radiation_moves_back_to_slot_start(load_fixture, weather):
    raw = load_fixture("weather_sample.json")["minutely_15"]
    # the value stamped 12:15 describes 12:00-12:15, so it belongs to the slot starting 12:00
    i = raw["time"].index(1794441600 + 12 * 3600 + 900)
    row = weather[weather["ts"] == pd.Timestamp("2026-11-12 12:00", tz="UTC")].iloc[0]
    assert row["gti_wm2"] == raw["global_tilted_irradiance"][i]


def test_hourly_value_repeats_across_its_four_slots(load_fixture, weather):
    raw = load_fixture("weather_sample.json")["hourly"]
    hour = weather[weather["ts"].dt.floor("h") == pd.Timestamp("2026-11-12 10:00", tz="UTC")]
    assert len(hour) == 4
    assert (hour["temp_c"] == raw["temperature_2m"][10]).all()
    assert (hour["wind_ms"] == raw["wind_speed_10m"][10]).all()


def test_missing_values_stay_missing(weather):
    assert weather["gti_wm2"].isna().sum() == 1
    assert weather["temp_c"].isna().sum() == 4  # one hourly null covers four slots


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
