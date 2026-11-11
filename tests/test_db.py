from datetime import UTC, datetime, timedelta

import pandas as pd

from offpeak import db
from offpeak.markets.energy_charts import parse_prices
from offpeak.weather.open_meteo import parse_weather


def test_prices_round_trip_and_no_duplicates(engine, load_fixture):
    prices = parse_prices(load_fixture("prices_spring_forward.json"))  # 92 slots, negatives
    assert db.upsert_prices(engine, prices, "DE-LU") == 92
    db.upsert_prices(engine, prices, "DE-LU")  # second run must not duplicate
    stored = db.read_prices(engine, "DE-LU", prices["ts"].min(), prices["ts"].max() + timedelta(1))
    assert len(stored) == 92
    assert stored["eur_mwh"].min() < 0
    assert stored["ts"].tolist() == prices["ts"].tolist()
    assert str(stored["ts"].dt.tz) == "UTC"


def test_rerun_updates_a_changed_price(engine, load_fixture):
    prices = parse_prices(load_fixture("prices_sample.json"))
    db.upsert_prices(engine, prices, "DE-LU")
    prices.loc[0, "eur_mwh"] = 1.23
    db.upsert_prices(engine, prices, "DE-LU")
    stored = db.read_prices(engine, "DE-LU", prices["ts"].min(), prices["ts"].max() + timedelta(1))
    assert stored["eur_mwh"].iloc[0] == 1.23


def test_latest_weather_run_wins_and_nulls_stay_null(engine, load_fixture):
    raw = load_fixture("weather_sample.json")
    raw["hourly"]["temperature_2m"][5] = None
    old = parse_weather(raw)
    new = old.copy()
    new["temp_c"] = new["temp_c"] + 1
    t0 = datetime(2026, 11, 11, 6, tzinfo=UTC)
    db.upsert_weather(engine, old, 1, t0)
    db.upsert_weather(engine, new, 1, t0 + timedelta(hours=3))
    weather, latest = db.read_latest_weather(
        engine, 1, old["ts"].min(), old["ts"].max() + timedelta(1)
    )
    assert latest == t0 + timedelta(hours=3)
    assert len(weather) == len(old)
    assert weather["temp_c"].isna().sum() == 4  # stored as NULL, not 0
    pd.testing.assert_series_equal(
        weather["temp_c"].dropna().reset_index(drop=True),
        new["temp_c"].dropna().reset_index(drop=True),
        check_names=False,
        check_dtype=False,
        atol=1e-4,
    )


def test_job_log(engine):
    now = datetime.now(UTC)
    db.log_job(engine, "ingest_prices", now, now, "skipped", 0, "tomorrow already stored")
    runs = db.recent_job_runs(engine)
    assert runs.iloc[0]["status"] == "skipped"
