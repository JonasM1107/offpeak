"""Replaying past days: real saved prices and real saved archive weather."""

import pandas as pd
import pytest

from offpeak import components as C
from offpeak import savings
from offpeak.markets.energy_charts import parse_prices
from offpeak.tariffs import germany_2026
from offpeak.weather.open_meteo import parse_archive

TZ = "Europe/Berlin"


@pytest.fixture
def archive(load_fixture):
    return parse_archive(load_fixture("weather_archive.json"))


def test_archive_moves_irradiance_to_the_hour_start(archive, load_fixture):
    raw = load_fixture("weather_archive.json")["hourly"]
    i = 13
    row = archive[archive["ts"] == pd.Timestamp(raw["time"][i] - 3600, unit="s", tz="UTC")].iloc[0]
    assert row["gti_wm2"] == raw["global_tilted_irradiance"][i]
    assert row["wind_ms"] == raw["wind_speed_10m"][i - 1]


def test_replay_one_day(load_fixture, archive):
    prices = parse_prices(load_fixture("prices_sample.json"))  # 10 Nov 2026
    day = prices["ts"].dt.tz_convert(TZ).dt.date.iloc[0]
    # put the archive's first day on the price day, so both describe the same day
    w = archive.iloc[:24].copy()
    w["ts"] = pd.date_range(pd.Timestamp(day, tz=TZ), periods=24, freq="h").tz_convert("UTC")
    comps = list(C.DEFAULT_COMPONENTS)
    assets, _ = C.site_model(comps)
    tariff = germany_2026(pv_kwp=assets.pv_kwp)
    days = savings.replay(prices, w, comps, tariff, TZ, [day])
    assert len(days) == 1
    d = days[0]
    assert d["saving_eur"] == pytest.approx(d["usual_eur"] - d["plan_eur"], abs=0.01)
    assert d["saving_eur"] >= -1e-6  # the plan never costs more than the usual pattern
    assert {x["name"] for x in d["devices"]} >= {"Electric furnace", "EV fleet chargers"}
    assert len(d["price_ct"]) == 24


def test_replay_skips_days_without_weather(load_fixture, archive):
    prices = parse_prices(load_fixture("prices_sample.json"))
    day = prices["ts"].dt.tz_convert(TZ).dt.date.iloc[0]
    tariff = germany_2026()
    assert (
        savings.replay(prices, archive.iloc[:0], list(C.DEFAULT_COMPONENTS), tariff, TZ, [day])
        == []
    )


def test_summary_adds_up():
    days = [
        {
            "date": "2026-11-01",
            "usual_eur": 100,
            "plan_eur": 90,
            "saving_eur": 10,
            "devices": [{"name": "EV", "saving_eur": 6}, {"name": "Furnace", "saving_eur": 4}],
        },
        {
            "date": "2026-11-02",
            "usual_eur": 100,
            "plan_eur": 70,
            "saving_eur": 30,
            "devices": [{"name": "EV", "saving_eur": 20}, {"name": "Furnace", "saving_eur": 10}],
        },
    ]
    s = savings.summary(days)
    assert s["saving_eur"] == 40 and s["share_pct"] == 20.0 and s["per_day_eur"] == 20
    assert s["best_day"] == "2026-11-02"
    assert list(s["by_device"]) == ["EV", "Furnace"]
    assert savings.summary([])["days"] == 0
